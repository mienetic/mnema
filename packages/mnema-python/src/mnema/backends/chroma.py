"""Chroma backend — embedded, persistent vector store.

This is the default backend. Chroma runs in-process and persists to a local
directory, so there is **no separate server to run**. If a remote Chroma
server is preferred, set ``backend_path`` to its ``http://host:port`` URL.

Install with::

    pip install 'mnema-mcp[chroma]'
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncIterator, Sequence
from typing import Any

import anyio

from mnema.backends.base import BackendHit, BackendQuery, VectorBackend
from mnema.config import MnemaConfig
from mnema.errors import BackendInitError
from mnema.models import MemoryRecord


def _cosine_to_unit(raw: float) -> float:
    """Normalize a similarity value that might be in ``[-1, 1]`` into ``[0, 1]``.

    Chroma's ``hnsw:space=cosine`` returns distances, not similarities; we
    convert distance ``d ∈ [0, 2]`` to similarity ``s = 1 - d/2 ∈ [0, 1]``.
    """
    return max(0.0, min(1.0, 1.0 - raw / 2.0))


class ChromaBackend(VectorBackend):
    """Embedded Chroma backend.

    The Chroma client API is synchronous and blocking, so every call is
    dispatched to a worker thread via :func:`anyio.to_thread.run_sync`.
    """

    name = "chroma"

    def __init__(self, config: MnemaConfig) -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - guarded by factory
            raise BackendInitError(
                "chromadb is not installed. Install with: "
                "pip install 'mnema-mcp[chroma]'"
            ) from exc

        self._config = config
        self._dim = config.embedding_dim

        try:
            if config.backend_path.startswith(("http://", "https://")):
                self._client = chromadb.HttpClient(url=config.backend_path)
            else:
                self._client = chromadb.PersistentClient(path=config.backend_path)
            self._collection = self._client.get_or_create_collection(
                name=config.backend_collection,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise BackendInitError(f"Failed to initialize Chroma: {exc}") from exc

    # --- helpers --------------------------------------------------------
    def _to_record(self, meta: dict[str, Any], doc: str | None) -> MemoryRecord:
        """Reconstruct a :class:`MemoryRecord` from a Chroma row."""
        return MemoryRecord(
            id=meta["mnema_id"],
            text=doc or meta.get("text", ""),
            scope=meta.get("scope", "global"),
            tags=_split(meta.get("tags", "")),
            importance=int(meta.get("importance", 5)),
            metadata=_loads(meta.get("metadata", "{}")),
            embedding_dim=int(meta.get("embedding_dim", self._dim or 0)),
            created_at=float(meta.get("created_at", 0.0)),
            last_accessed_at=float(meta.get("last_accessed_at", 0.0)),
            access_count=int(meta.get("access_count", 0)),
        )

    @staticmethod
    def _meta(record: MemoryRecord) -> dict[str, Any]:
        import json

        return {
            "mnema_id": record.id,
            "scope": record.scope,
            "tags": " ".join(record.tags),
            "importance": int(record.importance),
            "metadata": json.dumps(record.metadata, default=str),
            "embedding_dim": record.embedding_dim,
            "created_at": record.created_at,
            "last_accessed_at": record.last_accessed_at,
            "access_count": record.access_count,
        }

    # --- API ------------------------------------------------------------
    async def add(self, record: MemoryRecord, embedding: Sequence[float]) -> None:
        def _do() -> None:
            self._collection.upsert(
                ids=[record.id],
                documents=[record.text],
                embeddings=[list(embedding)],
                metadatas=[self._meta(record)],
            )

        await anyio.to_thread.run_sync(_do)

    async def get(self, memory_id: str) -> MemoryRecord | None:
        def _do() -> MemoryRecord | None:
            try:
                got = self._collection.get(ids=[memory_id], limit=1)
            except Exception:
                return None
            if not got or not got.get("ids"):
                return None
            meta = got["metadatas"][0]
            doc = got["documents"][0] if got.get("documents") else None
            return self._to_record(meta, doc)

        return await anyio.to_thread.run_sync(_do)

    async def update(
        self,
        memory_id: str,
        *,
        text: str | None = None,
        tags: list[str] | None = None,
        importance: int | None = None,
        metadata: dict[str, object] | None = None,
        embedding: Sequence[float] | None = None,
    ) -> MemoryRecord | None:
        record = await self.get(memory_id)
        if record is None:
            return None
        if text is not None:
            record = record.model_copy(update={"text": text})
        if tags is not None:
            record = record.model_copy(update={"tags": list(tags)})
        if importance is not None:
            record = record.model_copy(
                update={"importance": __import__("mnema.models", fromlist=["Importance"]).Importance(importance)}  # noqa: E501
            )
        if metadata is not None:
            record = record.model_copy(update={"metadata": dict(metadata)})

        def _do() -> None:
            kwargs: dict[str, Any] = {
                "ids": [record.id],
                "documents": [record.text],
                "metadatas": [self._meta(record)],
            }
            if embedding is not None:
                kwargs["embeddings"] = [list(embedding)]
            self._collection.update(**kwargs)

        await anyio.to_thread.run_sync(_do)
        return record

    async def delete(self, memory_id: str) -> bool:
        existing = await self.get(memory_id)
        if existing is None:
            return False

        def _do() -> None:
            self._collection.delete(ids=[memory_id])

        await anyio.to_thread.run_sync(_do)
        return True

    async def delete_by_scope(self, scope: str) -> int:
        def _do() -> int:
            got = self._collection.get(where={"scope": scope}, limit=10_000)
            ids = got.get("ids", []) if got else []
            if not ids:
                return 0
            self._collection.delete(ids=ids)
            return len(ids)

        return await anyio.to_thread.run_sync(_do)

    async def search(self, query: BackendQuery) -> list[BackendHit]:
        where: dict[str, Any] = {}
        if query.scope:
            where["scope"] = query.scope
        elif query.scope_in:
            where["scope"] = {"$in": list(query.scope_in)}

        def _do() -> list[BackendHit]:
            kwargs: dict[str, Any] = {
                "query_embeddings": [list(query.query_embedding)],
                "n_results": query.limit + query.offset,
                "include": ["metadatas", "documents", "distances"],
            }
            if where:
                kwargs["where"] = where
            res = self._collection.query(**kwargs)
            hits: list[BackendHit] = []
            ids = (res.get("ids") or [[]])[0]
            metas = (res.get("metadatas") or [[]])[0]
            docs = (res.get("documents") or [[]])[0]
            dists = (res.get("distances") or [[]])[0]
            for i, _id in enumerate(ids):
                meta = metas[i] if i < len(metas) else {}
                doc = docs[i] if i < len(docs) else None
                dist = dists[i] if i < len(dists) else 1.0
                record = self._to_record(meta, doc)
                ks = _keyword_overlap(record.tags, query.tags)
                hits.append(
                    BackendHit(record=record, score=_cosine_to_unit(float(dist)), keyword_score=ks)
                )
            return hits

        hits = await anyio.to_thread.run_sync(_do)
        return hits[query.offset : query.offset + query.limit]

    async def count(self, scope: str | None = None) -> int:
        def _do() -> int:
            if scope:
                got = self._collection.get(where={"scope": scope}, limit=10_000)
                return len((got or {}).get("ids", []))
            return self._collection.count()

        return await anyio.to_thread.run_sync(_do)

    async def list_scopes(self) -> dict[str, int]:
        def _do() -> dict[str, int]:
            got = self._collection.get(limit=10_000, include=["metadatas"])
            scopes: dict[str, int] = {}
            for meta in (got or {}).get("metadatas", []):
                s = (meta or {}).get("scope", "global")
                scopes[s] = scopes.get(s, 0) + 1
            return scopes

        return await anyio.to_thread.run_sync(_do)

    async def iter_all(self, scope: str | None = None) -> AsyncIterator[MemoryRecord]:
        def _do() -> list[MemoryRecord]:
            kwargs: dict[str, Any] = {"limit": 10_000, "include": ["metadatas", "documents"]}
            if scope:
                kwargs["where"] = {"scope": scope}
            got = self._collection.get(**kwargs)
            records: list[MemoryRecord] = []
            ids = (got or {}).get("ids", [])
            metas = (got or {}).get("metadatas", [])
            docs = (got or {}).get("documents", [])
            for i, _id in enumerate(ids):
                meta = metas[i] if i < len(metas) else {}
                doc = docs[i] if i < len(docs) else None
                records.append(self._to_record(meta, doc))
            return records

        records = await anyio.to_thread.run_sync(_do)
        for r in records:
            yield r

    async def touch(self, memory_id: str) -> None:
        """Update ``last_accessed_at`` / ``access_count`` for a memory.

        Not part of the abstract interface; called by the service layer after
        a recall to refresh recency. Kept thin so it can be overridden.
        """
        record = await self.get(memory_id)
        if record is None:
            return
        import time

        updated = record.model_copy(
            update={
                "last_accessed_at": time.time(),
                "access_count": record.access_count + 1,
            }
        )

        def _do() -> None:
            self._collection.update(
                ids=[updated.id],
                metadatas=[self._meta(updated)],
            )

        await anyio.to_thread.run_sync(_do)


def _split(s: str) -> list[str]:
    return [t for t in s.split() if t]


def _loads(s: str) -> dict[str, Any]:
    import json

    if not s:
        return {}
    try:
        out = json.loads(s)
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


def _keyword_overlap(record_tags: Sequence[str], query_tags: Sequence[str] | None) -> float:
    """Jaccard-style overlap in ``[0, 1]``; 0 when either side is empty."""
    if not query_tags or not record_tags:
        return 0.0
    a = {t.lower() for t in record_tags}
    b = {t.lower() for t in query_tags}
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


# Silence unused-import warnings for math (kept for future metric tweaks).
_ = math, asyncio

__all__ = ["ChromaBackend"]
