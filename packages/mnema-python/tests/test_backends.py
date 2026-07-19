"""Backend matrix tests — exercise each real backend when its dep is present.

Skipped automatically if the optional dependency isn't installed, so the
suite runs green in a minimal environment (CI) but fully exercises real
backends in ``[all]`` installs.
"""

from __future__ import annotations

import os

import pytest

from mnema.config import MnemaConfig
from mnema.service import MemoryService
from tests.fakes import (
    HashingEmbedding,
    skip_no_chroma,
    skip_no_pgvector,
    skip_no_qdrant,
    skip_no_sqlite_vec,
)

pytestmark = pytest.mark.asyncio


async def _roundtrip(service: MemoryService) -> None:
    """Shared happy-path exercised against every backend."""
    rec = await service.remember("the user prefers vim over emacs", tags=["editor", "pref"])
    got = await service.get(rec.id)
    assert got.text.startswith("the user prefers")

    hits = await service.recall("text editor preference", limit=3)
    assert hits.count >= 1
    assert any("vim" in r.memory.text for r in hits.results)

    updated = await service.update(rec.id, text="the user now prefers helix")
    assert "helix" in updated.text

    deleted = await service.forget(rec.id)
    assert deleted is True


@skip_no_chroma
class TestChromaBackend:
    async def test_roundtrip(self, tmp_path):
        from mnema.backends.chroma import ChromaBackend

        cfg = MnemaConfig(
            backend="chroma",
            backend_path=str(tmp_path / "chroma"),
            embedding="local",
            embedding_model="all-MiniLM-L6-v2",
            embedding_dim=64,
        )
        emb = HashingEmbedding(dim=64)
        backend = ChromaBackend(cfg)
        svc = MemoryService(cfg, backend=backend, embedding=emb)
        try:
            await _roundtrip(svc)
        finally:
            await svc.aclose()


@skip_no_qdrant
class TestQdrantBackend:
    async def test_roundtrip(self):
        from mnema.backends.qdrant import QdrantBackend

        cfg = MnemaConfig(
            backend="qdrant",
            backend_path=":memory:",
            backend_collection="memories_test",
            embedding="local",
            embedding_model="all-MiniLM-L6-v2",
            embedding_dim=64,
        )
        emb = HashingEmbedding(dim=64)
        backend = QdrantBackend(cfg)
        svc = MemoryService(cfg, backend=backend, embedding=emb)
        try:
            await _roundtrip(svc)
        finally:
            await svc.aclose()


@skip_no_sqlite_vec
class TestSqliteVecBackend:
    async def test_roundtrip(self, tmp_path):
        from mnema.backends.sqlite_vec import SqliteVecBackend

        cfg = MnemaConfig(
            backend="sqlite_vec",
            backend_path=str(tmp_path / "mnema.db"),
            embedding="local",
            embedding_model="all-MiniLM-L6-v2",
            embedding_dim=64,
        )
        emb = HashingEmbedding(dim=64)
        backend = SqliteVecBackend(cfg)
        svc = MemoryService(cfg, backend=backend, embedding=emb)
        try:
            await _roundtrip(svc)
        finally:
            await svc.aclose()


@skip_no_pgvector
class TestPgVectorBackend:
    async def test_roundtrip(self):
        dsn = os.environ.get("MNEMA_PGVECTOR_TEST_DSN")
        if not dsn:
            pytest.skip("MNEMA_PGVECTOR_TEST_DSN environment variable not set")
        from mnema.backends.pgvector import PgVectorBackend

        cfg = MnemaConfig(
            backend="pgvector",
            backend_path=dsn,
            backend_collection="memories_test",
            embedding="local",
            embedding_model="all-MiniLM-L6-v2",
            embedding_dim=64,
        )
        emb = HashingEmbedding(dim=64)
        backend = PgVectorBackend(cfg)
        svc = MemoryService(cfg, backend=backend, embedding=emb)
        try:
            await _roundtrip(svc)
        finally:
            await svc.aclose()
