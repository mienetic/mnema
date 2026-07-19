"""LanceDB backend — embedded columnar vector store.

LanceDB is a serverless, embedded columnar vector DB built on the Lance
columnar format. It stores data locally and provides fast vector similarity
search without requiring a separate server.

Install with::

    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
      | MNEMA_EXTRAS='lancedb,local' bash
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

import anyio
import pyarrow as pa

from mnema.backends.base import BackendHit, BackendQuery, VectorBackend
from mnema.config import MnemaConfig
from mnema.errors import BackendInitError
from mnema.models import Importance, MemoryRecord

_INSTALL_HINT = (
    "lancedb is not installed. Reinstall Mnema with the 'lancedb' extra:\n"
    "    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh "
    "| MNEMA_EXTRAS='lancedb,local' bash"
)


def _esc(val: str) -> str:
    """Escape a string value for use in a LanceDB SQL filter."""
    return val.replace("'", "''")


class LanceDBBackend(VectorBackend):
    """LanceDB backend — embedded columnar vector store.

    LanceDB runs in-process and persists to a local directory. No server
    is required.
    """

    name = "lancedb"

    def __init__(self, config: MnemaConfig) -> None:
        try:
            import lancedb
        except ImportError as exc:
            raise BackendInitError(_INSTALL_HINT) from exc

        self._config = config
        self._dim = config.embedding_dim or 384

        try:
            self._db = lancedb.connect(config.backend_path)
            tbl_name = config.backend_collection
            try:
                self._table = self._db.open_table(tbl_name)
            except Exception:
                schema = pa.schema([
                    pa.field("id", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), self._dim)),
                    pa.field("text", pa.string()),
                    pa.field("scope", pa.string()),
                    pa.field("tags", pa.string()),
                    pa.field("importance", pa.int32()),
                    pa.field("metadata", pa.string()),
                    pa.field("embedding_dim", pa.int32()),
                    pa.field("created_at", pa.float64()),
                    pa.field("last_accessed_at", pa.float64()),
                    pa.field("access_count", pa.int32()),
                ])
                self._table = self._db.create_table(
                    tbl_name, schema=schema, mode="create"
                )
        except BackendInitError:
            raise
        except Exception as exc:
            raise BackendInitError(f"Failed to initialize LanceDB: {exc}") from exc

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_row(record: MemoryRecord, embedding: Sequence[float]) -> dict[str, Any]:
        return {
            "id": record.id,
            "vector": list(embedding),
            "text": record.text,
            "scope": record.scope,
            "tags": " ".join(record.tags),
            "importance": int(record.importance),
            "metadata": json.dumps(record.metadata, default=str),
            "embedding_dim": record.embedding_dim,
            "created_at": record.created_at,
            "last_accessed_at": record.last_accessed_at,
            "access_count": record.access_count,
        }

    def _from_row(self, data: dict[str, Any]) -> MemoryRecord:
        meta_raw = data.get("metadata", "{}")
        try:
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
        except Exception:
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        return MemoryRecord(
            id=str(data["id"]),
            text=str(data.get("text", "")),
            scope=str(data.get("scope", "global")),
            tags=[t for t in str(data.get("tags", "") or "").split() if t],
            importance=Importance(int(data.get("importance", 5))),
            metadata=meta,
            embedding_dim=int(data.get("embedding_dim", self._dim)),
            created_at=float(data.get("created_at", 0.0)),
            last_accessed_at=float(data.get("last_accessed_at", 0.0)),
            access_count=int(data.get("access_count", 0)),
        )

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    async def add(self, record: MemoryRecord, embedding: Sequence[float]) -> None:
        def _do() -> None:
            data = self._to_row(record, embedding)
            self._table.delete(f"id = '{_esc(record.id)}'")
            self._table.add([data])

        await anyio.to_thread.run_sync(_do)

    async def get(self, memory_id: str) -> MemoryRecord | None:
        def _do() -> MemoryRecord | None:
            results = (
                self._table.search()
                .where(f"id = '{_esc(memory_id)}'")
                .limit(1)
                .to_pandas()
            )
            if len(results) == 0:
                return None
            return self._from_row(results.iloc[0].to_dict())

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
                update={"importance": Importance(int(importance))}
            )
        if metadata is not None:
            record = record.model_copy(update={"metadata": dict(metadata)})

        def _do() -> None:
            esc_id = _esc(record.id)
            if embedding is not None:
                self._table.delete(f"id = '{esc_id}'")
                self._table.add([self._to_row(record, embedding)])
            else:
                self._table.update(
                    where=f"id = '{esc_id}'",
                    values={
                        "text": record.text,
                        "scope": record.scope,
                        "tags": " ".join(record.tags),
                        "importance": int(record.importance),
                        "metadata": json.dumps(record.metadata, default=str),
                    },
                )

        await anyio.to_thread.run_sync(_do)
        return record

    async def delete(self, memory_id: str) -> bool:
        existing = await self.get(memory_id)
        if existing is None:
            return False

        def _do() -> None:
            self._table.delete(f"id = '{_esc(memory_id)}'")

        await anyio.to_thread.run_sync(_do)
        return True

    async def delete_by_scope(self, scope: str) -> int:
        def _do() -> int:
            results = (
                self._table.search()
                .where(f"scope = '{_esc(scope)}'")
                .to_pandas()
            )
            count = len(results)
            if count > 0:
                self._table.delete(f"scope = '{_esc(scope)}'")
            return count

        return await anyio.to_thread.run_sync(_do)

    async def search(self, query: BackendQuery) -> list[BackendHit]:
        k = query.limit + query.offset

        def _do() -> list[BackendHit]:
            q = self._table.search(list(query.query_embedding))
            if query.scope:
                q = q.where(f"scope = '{_esc(query.scope)}'")
            elif query.scope_in:
                scopes = ", ".join(f"'{_esc(s)}'" for s in query.scope_in)
                q = q.where(f"scope IN ({scopes})")
            results = q.limit(k).to_pandas()

            hits: list[BackendHit] = []
            for _, row in results.iterrows():
                record = self._from_row(row.to_dict())
                dist = float(row.get("_distance", 1.0))
                sim = max(0.0, min(1.0, 1.0 - dist / 2.0))
                ks = _keyword_overlap(record.tags, query.tags)
                hits.append(BackendHit(record=record, score=sim, keyword_score=ks))
            return hits

        hits = await anyio.to_thread.run_sync(_do)
        return hits[query.offset : query.offset + query.limit]

    async def count(self, scope: str | None = None) -> int:
        def _do() -> int:
            if scope:
                results = (
                    self._table.search()
                    .where(f"scope = '{_esc(scope)}'")
                    .to_pandas()
                )
            else:
                results = self._table.search().to_pandas()
            return len(results)

        return await anyio.to_thread.run_sync(_do)

    async def list_scopes(self) -> dict[str, int]:
        def _do() -> dict[str, int]:
            results = self._table.search().to_pandas()
            scopes: dict[str, int] = {}
            for _, row in results.iterrows():
                s = str(row.get("scope", "global"))
                scopes[s] = scopes.get(s, 0) + 1
            return scopes

        return await anyio.to_thread.run_sync(_do)

    async def iter_all(
        self, scope: str | None = None
    ) -> AsyncIterator[MemoryRecord]:
        def _do() -> list[MemoryRecord]:
            if scope:
                results = (
                    self._table.search()
                    .where(f"scope = '{_esc(scope)}'")
                    .to_pandas()
                )
            else:
                results = self._table.search().to_pandas()
            return [self._from_row(row.to_dict()) for _, row in results.iterrows()]

        records = await anyio.to_thread.run_sync(_do)
        for r in records:
            yield r

    async def touch(self, memory_id: str) -> None:
        record = await self.get(memory_id)
        if record is None:
            return

        def _do() -> None:
            self._table.update(
                where=f"id = '{_esc(memory_id)}'",
                values={
                    "last_accessed_at": time.time(),
                    "access_count": record.access_count + 1,
                },
            )

        await anyio.to_thread.run_sync(_do)

    async def aclose(self) -> None:
        def _do() -> None:
            pass

        await anyio.to_thread.run_sync(_do)


def _keyword_overlap(
    record_tags: Sequence[str], query_tags: Sequence[str] | None
) -> float:
    """Jaccard-style overlap in ``[0, 1]``; 0 when either side is empty."""
    if not query_tags or not record_tags:
        return 0.0
    a = {t.lower() for t in record_tags}
    b = {t.lower() for t in query_tags}
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


__all__ = ["LanceDBBackend"]
