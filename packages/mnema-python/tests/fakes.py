"""Shared test fixtures: fakes, conftest, and a parametrized backend matrix.

To keep the test suite runnable without heavy optional deps, we provide an
:class:`InMemoryBackend` and a :class:`HashingEmbedding` (deterministic,
zero-dependency embedding). Real backends (Chroma/Qdrant/sqlite-vec) are
exercised only when their optional dep is installed (via markers).
"""

from __future__ import annotations

import hashlib
import math
import struct
import time
from collections.abc import AsyncIterator, Sequence

import pytest

from mnema.backends.base import BackendHit, BackendQuery, VectorBackend
from mnema.config import MnemaConfig
from mnema.embeddings.base import EmbeddingProvider
from mnema.models import Importance, MemoryRecord


# ---------------------------------------------------------------------------
# Deterministic zero-dependency embedding (hash-based).
# ---------------------------------------------------------------------------
class HashingEmbedding(EmbeddingProvider):
    """Deterministic, dependency-free embedding for tests.

    Hashes each word into a fixed-size vector and averages. Not a real
    semantic embedding, but stable and "good enough" for CRUD + ordering
    tests on the service layer.
    """

    name = "hash"
    dim = 64

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim
        self._name = "hash"

    @property
    def display_name(self) -> str:
        return self._name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            tokens = [t for t in text.lower().split() if t]
            for tok in tokens:
                h = hashlib.md5(tok.encode("utf-8")).digest()
                # Use 4 bytes at a time to index into vec and add a signed value.
                for j in range(0, min(len(h), 8), 2):
                    idx = h[j] % self.dim
                    val = (h[j + 1] / 255.0) * 2 - 1  # in [-1, 1]
                    vec[idx] += val
            # L2 normalize
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


# ---------------------------------------------------------------------------
# In-memory vector backend for fast service-layer tests.
# ---------------------------------------------------------------------------
class InMemoryBackend(VectorBackend):
    """A pure-Python vector backend for tests. Supports cosine + tag overlap."""

    name = "memory"

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim
        self._store: dict[str, tuple[MemoryRecord, list[float]]] = {}

    @staticmethod
    def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        sim = dot / (na * nb)
        # Map [-1, 1] → [0, 1]
        return (sim + 1) / 2

    async def add(self, record: MemoryRecord, embedding: Sequence[float]) -> None:
        self._store[record.id] = (record, list(embedding))

    async def get(self, memory_id: str) -> MemoryRecord | None:
        tup = self._store.get(memory_id)
        return tup[0] if tup else None

    async def update(self, memory_id, *, text=None, tags=None, importance=None,
                     metadata=None, embedding=None):
        tup = self._store.get(memory_id)
        if tup is None:
            return None
        record, emb = tup
        if text is not None:
            record = record.model_copy(update={"text": text})
        if tags is not None:
            record = record.model_copy(update={"tags": list(tags)})
        if importance is not None:
            record = record.model_copy(update={"importance": Importance(int(importance))})
        if metadata is not None:
            record = record.model_copy(update={"metadata": dict(metadata)})
        if embedding is not None:
            emb = list(embedding)
        self._store[memory_id] = (record, emb)
        return record

    async def delete(self, memory_id: str) -> bool:
        return self._store.pop(memory_id, None) is not None

    async def delete_by_scope(self, scope: str) -> int:
        ids = [mid for mid, (r, _) in self._store.items() if r.scope == scope]
        for mid in ids:
            self._store.pop(mid, None)
        return len(ids)

    async def search(self, query: BackendQuery) -> list[BackendHit]:
        hits: list[BackendHit] = []
        for _id, (record, emb) in self._store.items():
            if query.scope and record.scope != query.scope:
                continue
            if query.scope_in and record.scope not in query.scope_in:
                continue
            sim = self._cosine(query.query_embedding, emb)
            ks = self._keyword(record.tags, query.tags)
            hits.append(BackendHit(record=record, score=sim, keyword_score=ks))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[query.offset : query.offset + query.limit]

    async def count(self, scope: str | None = None) -> int:
        if not scope:
            return len(self._store)
        return sum(1 for r, _ in self._store.values() if r.scope == scope)

    async def list_scopes(self) -> dict[str, int]:
        scopes: dict[str, int] = {}
        for r, _ in self._store.values():
            scopes[r.scope] = scopes.get(r.scope, 0) + 1
        return scopes

    async def iter_all(self, scope: str | None = None) -> AsyncIterator[MemoryRecord]:
        for r, _ in list(self._store.values()):
            if scope is None or r.scope == scope:
                yield r

    @staticmethod
    def _keyword(record_tags: Sequence[str], query_tags: Sequence[str] | None) -> float:
        if not query_tags or not record_tags:
            return 0.0
        a = {t.lower() for t in record_tags}
        b = {t.lower() for t in query_tags}
        inter = len(a & b)
        return inter / len(a | b) if inter else 0.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_embedding() -> HashingEmbedding:
    return HashingEmbedding(dim=64)


@pytest.fixture
def fake_backend() -> InMemoryBackend:
    return InMemoryBackend(dim=64)


@pytest.fixture
def fake_config(tmp_path) -> MnemaConfig:
    """A config that points at a temp path; doesn't require optional deps."""
    cfg = MnemaConfig(
        backend="sqlite_vec",
        backend_path=str(tmp_path / "mnema.db"),
        embedding="local",
        embedding_model="all-MiniLM-L6-v2",
        embedding_dim=64,
    )
    return cfg


def make_service(config: MnemaConfig, backend: VectorBackend, embedding: EmbeddingProvider):
    """Build a MemoryService with injected fakes (bypassing make_backend)."""
    from mnema.service import MemoryService

    return MemoryService(config, backend=backend, embedding=embedding)


def make_record(
    *,
    text: str = "sample memory",
    scope: str = "global",
    tags: list[str] | None = None,
    importance: int = 5,
    dim: int = 64,
    age_days: float = 0.0,
    access_count: int = 0,
) -> MemoryRecord:
    """Factory for MemoryRecord with sensible test defaults."""
    return MemoryRecord(
        text=text,
        scope=scope,
        tags=tags or [],
        importance=Importance(int(importance)),
        embedding_dim=dim,
        created_at=time.time() - age_days * 86400,
        last_accessed_at=time.time() - age_days * 86400,
        access_count=access_count,
    )


# ---------------------------------------------------------------------------
# Optional-dependency markers / skips.
# ---------------------------------------------------------------------------
def chroma_available() -> bool:
    try:
        import chromadb  # noqa: F401

        return True
    except ImportError:
        return False


def qdrant_available() -> bool:
    try:
        import qdrant_client  # noqa: F401

        return True
    except ImportError:
        return False


def sqlite_vec_available() -> bool:
    try:
        import sqlite_vec  # noqa: F401

        return True
    except ImportError:
        return False


def st_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


skip_no_chroma = pytest.mark.skipif(not chroma_available(), reason="chromadb not installed")
skip_no_qdrant = pytest.mark.skipif(not qdrant_available(), reason="qdrant-client not installed")
skip_no_sqlite_vec = pytest.mark.skipif(
    not sqlite_vec_available(), reason="sqlite-vec not installed"
)
skip_no_st = pytest.mark.skipif(
    not st_available(), reason="sentence-transformers not installed"
)


# Keep struct imported for parity with real backends (silences flake in CI).
_ = struct
