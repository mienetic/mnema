"""Qdrant backend — local embedded or remote, production grade.

Supports three connection modes selected automatically from ``backend_path``:

* ``:memory:``       → in-process (dev / tests, no persistence)
* a local directory  → embedded local disk mode (``path=...``)
* ``http://host:port``→ remote Qdrant server

Install with::

    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \\
      | MNEMA_EXTRAS="qdrant,local" bash
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

import anyio

from mnema.backends.base import BackendHit, BackendQuery, VectorBackend
from mnema.config import MnemaConfig
from mnema.errors import BackendInitError
from mnema.models import Importance, MemoryRecord


class QdrantBackend(VectorBackend):
    """Qdrant backend (local embedded or remote)."""

    name = "qdrant"

    def __init__(self, config: MnemaConfig) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models as qm
        except ImportError as exc:  # pragma: no cover - guarded by factory
            raise BackendInitError(
                "qdrant-client is not installed. Reinstall Mnema with the "
                "'qdrant' extra:\n"
                "    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh "
                "| MNEMA_EXTRAS='qdrant,local' bash"
            ) from exc

        self._config = config
        self._dim = config.embedding_dim
        self._qm = qm

        try:
            path = config.backend_path
            if path == ":memory:":
                self._client = QdrantClient(location=":memory:")
            elif path.startswith(("http://", "https://")):
                self._client = QdrantClient(url=path)
            else:
                self._client = QdrantClient(path=path)

            cols = [qm.PayloadSchemaType.KEYWORD for _ in ("scope", "tags")]
            # Ensure the collection exists with the right vector config.
            existing = {c.name for c in self._client.get_collections().collections}
            if config.backend_collection not in existing:
                self._client.create_collection(
                    collection_name=config.backend_collection,
                    vectors_config=qm.VectorParams(
                        size=self._dim or 384,
                        distance=qm.Distance.COSINE,
                    ),
                )
            # Create keyword index for scope/tags filtering. Local (embedded)
            # Qdrant ignores payload indexes, so we silence the harmless warning.
            import warnings

            for field in ("scope", "tags"):
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        self._client.create_payload_index(
                            collection_name=config.backend_collection,
                            field_name=field,
                            field_schema=qm.PayloadSchemaType.KEYWORD,
                        )
                except Exception:
                    # Already exists or not supported in local mode — safe to ignore.
                    pass
        except BackendInitError:
            raise
        except Exception as exc:
            raise BackendInitError(f"Failed to initialize Qdrant: {exc}") from exc
        finally:
            _ = cols  # silence unused warning

    # --- (de)serialization helpers -------------------------------------
    @staticmethod
    def _payload(r: MemoryRecord) -> dict[str, Any]:
        return {
            "text": r.text,
            "scope": r.scope,
            "tags": list(r.tags),
            "importance": int(r.importance),
            "metadata": json.dumps(r.metadata, default=str),
            "embedding_dim": r.embedding_dim,
            "created_at": r.created_at,
            "last_accessed_at": r.last_accessed_at,
            "access_count": r.access_count,
        }

    def _record(self, point_id: str, payload: dict[str, Any]) -> MemoryRecord:
        meta_raw = payload.get("metadata") or "{}"
        try:
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
        except Exception:
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        return MemoryRecord(
            id=str(point_id),
            text=payload.get("text", ""),
            scope=payload.get("scope", "global"),
            tags=list(payload.get("tags", []) or []),
            importance=Importance(int(payload.get("importance", 5))),
            metadata=meta,
            embedding_dim=int(payload.get("embedding_dim", self._dim or 0)),
            created_at=float(payload.get("created_at", 0.0)),
            last_accessed_at=float(payload.get("last_accessed_at", 0.0)),
            access_count=int(payload.get("access_count", 0)),
        )

    # --- API ------------------------------------------------------------
    async def add(self, record: MemoryRecord, embedding: Sequence[float]) -> None:
        qm = self._qm

        def _do() -> None:
            self._client.upsert(
                collection_name=self._config.backend_collection,
                points=[
                    qm.PointStruct(
                        id=record.id,
                        vector=list(embedding),
                        payload=self._payload(record),
                    )
                ],
            )

        await anyio.to_thread.run_sync(_do)

    async def get(self, memory_id: str) -> MemoryRecord | None:
        def _do() -> MemoryRecord | None:
            try:
                pts, _ = self._client.scroll(
                    collection_name=self._config.backend_collection,
                    scroll_filter=self._qm.Filter(
                        must=[self._qm.HasIdCondition(has_id=[memory_id])]
                    ),
                    limit=1,
                    with_payload=True,
                    with_vectors=False,
                )
            except Exception:
                return None
            if not pts:
                return None
            p = pts[0]
            return self._record(memory_id, p.payload or {})

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
            record = record.model_copy(update={"importance": Importance(int(importance))})
        if metadata is not None:
            record = record.model_copy(update={"metadata": dict(metadata)})

        payload = self._payload(record)

        def _do() -> None:
            self._client.set_payload(
                collection_name=self._config.backend_collection,
                payload=payload,
                points=[record.id],
            )
            if embedding is not None:
                self._client.update_vectors(
                    collection_name=self._config.backend_collection,
                    points=[
                        self._qm.PointVectors(
                            id=record.id, vector=list(embedding)
                        )
                    ],
                )

        await anyio.to_thread.run_sync(_do)
        return record

    async def delete(self, memory_id: str) -> bool:
        existing = await self.get(memory_id)
        if existing is None:
            return False

        def _do() -> None:
            self._client.delete(
                collection_name=self._config.backend_collection,
                points_selector=self._qm.PointIdsList(points=[memory_id]),
            )

        await anyio.to_thread.run_sync(_do)
        return True

    async def delete_by_scope(self, scope: str) -> int:
        existing = await self.iter_all(scope=scope).__anext__()
        count = 0
        # Drain the iterator fully so we can count, then delete.
        # (Iterating once above gives the first element only.)
        ids: list[str] = []
        async for r in self.iter_all(scope=scope):
            ids.append(r.id)
        ids = list(dict.fromkeys(ids))  # dedupe, preserve order
        _ = existing  # silence
        if not ids:
            return 0
        count = len(ids)

        def _do() -> None:
            self._client.delete(
                collection_name=self._config.backend_collection,
                points_selector=self._qm.PointIdsList(points=ids),
            )

        await anyio.to_thread.run_sync(_do)
        return count

    async def search(self, query: BackendQuery) -> list[BackendHit]:
        qm = self._qm
        must: list[Any] = []
        if query.scope:
            must.append(
                qm.FieldCondition(
                    key="scope", match=qm.MatchValue(value=query.scope)
                )
            )
        should: list[Any] = []
        if query.tags:
            should.append(
                qm.FieldCondition(
                    key="tags", match=qm.MatchAny(any=list(query.tags))
                )
            )
        flt = qm.Filter(must=must, should=should or None)

        def _do() -> list[BackendHit]:
            res = self._client.query_points(
                collection_name=self._config.backend_collection,
                query=list(query.query_embedding),
                query_filter=flt,
                limit=query.limit + query.offset,
                with_payload=True,
                with_vectors=False,
            )
            hits: list[BackendHit] = []
            for point in res.points:
                payload = point.payload or {}
                record = self._record(str(point.id), payload)
                ks = _keyword_overlap(record.tags, query.tags)
                hits.append(
                    BackendHit(
                        record=record,
                        score=float(max(0.0, min(1.0, point.score))),
                        keyword_score=ks,
                    )
                )
            return hits

        hits = await anyio.to_thread.run_sync(_do)
        return hits[query.offset : query.offset + query.limit]

    async def count(self, scope: str | None = None) -> int:
        qm = self._qm
        flt = None
        if scope:
            flt = qm.Filter(
                must=[qm.FieldCondition(key="scope", match=qm.MatchValue(value=scope))]
            )

        def _do() -> int:
            r = self._client.count(
                collection_name=self._config.backend_collection,
                count_filter=flt,
                exact=True,
            )
            return r.count

        return await anyio.to_thread.run_sync(_do)

    async def list_scopes(self) -> dict[str, int]:
        scopes: dict[str, int] = {}
        async for r in self.iter_all():
            scopes[r.scope] = scopes.get(r.scope, 0) + 1
        return scopes

    async def iter_all(self, scope: str | None = None) -> AsyncIterator[MemoryRecord]:
        qm = self._qm
        flt = None
        if scope:
            flt = qm.Filter(
                must=[qm.FieldCondition(key="scope", match=qm.MatchValue(value=scope))]
            )

        def _do() -> list[MemoryRecord]:
            pts, _ = self._client.scroll(
                collection_name=self._config.backend_collection,
                scroll_filter=flt,
                limit=10_000,
                with_payload=True,
                with_vectors=False,
            )
            return [self._record(str(p.id), p.payload or {}) for p in pts]

        records = await anyio.to_thread.run_sync(_do)
        for r in records:
            yield r

    async def touch(self, memory_id: str) -> None:
        """Bump ``last_accessed_at`` / ``access_count`` after a recall."""
        record = await self.get(memory_id)
        if record is None:
            return
        payload = {
            "last_accessed_at": time.time(),
            "access_count": record.access_count + 1,
        }

        def _do() -> None:
            self._client.set_payload(
                collection_name=self._config.backend_collection,
                payload=payload,
                points=[record.id],
            )

        await anyio.to_thread.run_sync(_do)


def _keyword_overlap(record_tags: Sequence[str], query_tags: Sequence[str] | None) -> float:
    if not query_tags or not record_tags:
        return 0.0
    a = {t.lower() for t in record_tags}
    b = {t.lower() for t in query_tags}
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


__all__ = ["QdrantBackend"]
