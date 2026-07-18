"""pgvector backend — PostgreSQL with vector extension.

Requires a running Postgres with the pgvector extension installed server-side.
Connection via config.backend_path (or MNEMA_BACKEND_PATH env var).

Install with::

    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
      | MNEMA_EXTRAS='pgvector,local' bash
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Sequence
from typing import Any

from mnema.backends.base import BackendHit, BackendQuery, VectorBackend
from mnema.config import MnemaConfig
from mnema.errors import BackendInitError
from mnema.models import Importance, MemoryRecord


class PgVectorBackend(VectorBackend):
    """PostgreSQL + pgvector backend.

    Uses a single asyncpg connection. Connection is established lazily on
    the first API call so ``__init__`` stays synchronous (matching the
    factory pattern used by all other backends).
    """

    name = "pgvector"

    def __init__(self, config: MnemaConfig) -> None:
        try:
            import asyncpg  # noqa: F401
        except ImportError as exc:  # pragma: no cover - guarded by factory
            raise BackendInitError(
                "asyncpg is not installed. Reinstall Mnema with the "
                "'pgvector' extra:\n"
                "    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh "
                "| MNEMA_EXTRAS='pgvector,local' bash"
            ) from exc

        self._config = config
        self._dim = config.embedding_dim or 384
        self._conn: Any = None
        # ponytail: single connection, no pool. Add pool when concurrent
        # throughput measurements show a need.

    async def _ensure_connected(self) -> None:
        if self._conn is not None:
            return
        import asyncpg

        dsn = self._config.backend_path
        try:
            self._conn = await asyncpg.connect(dsn)
            await self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            from pgvector.asyncpg import register_vector

            await register_vector(self._conn)
            await self._conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '',
                    importance INTEGER NOT NULL DEFAULT 5,
                    metadata TEXT NOT NULL DEFAULT '{{}}',
                    embedding_dim INTEGER NOT NULL,
                    embedding vector({self._dim}),
                    created_at DOUBLE PRECISION NOT NULL,
                    last_accessed_at DOUBLE PRECISION NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await self._conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_memories_scope ON memories(scope)"
            )
        except Exception as exc:
            raise BackendInitError(f"Failed to connect to Postgres: {exc}") from exc

    @staticmethod
    def _row(row: dict[str, Any]) -> MemoryRecord:
        meta_raw = row.get("metadata") or "{}"
        try:
            meta = json.loads(meta_raw)
        except Exception:
            meta = {}
        return MemoryRecord(
            id=row["id"],
            text=row["text"],
            scope=row["scope"],
            tags=[t for t in (str(row.get("tags", "") or "")).split() if t],
            importance=Importance(int(row["importance"])),
            metadata=meta if isinstance(meta, dict) else {},
            embedding_dim=int(row["embedding_dim"]),
            created_at=float(row["created_at"]),
            last_accessed_at=float(row["last_accessed_at"]),
            access_count=int(row["access_count"]),
        )

    # --- API ------------------------------------------------------------

    async def add(self, record: MemoryRecord, embedding: Sequence[float]) -> None:
        await self._ensure_connected()
        await self._conn.execute(
            """
            INSERT INTO memories
                (id, text, scope, tags, importance, metadata, embedding_dim,
                 embedding, created_at, last_accessed_at, access_count)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector, $9, $10, $11)
            ON CONFLICT (id) DO UPDATE SET
                text=excluded.text, scope=excluded.scope, tags=excluded.tags,
                importance=excluded.importance, metadata=excluded.metadata,
                embedding_dim=excluded.embedding_dim,
                embedding=excluded.embedding,
                created_at=excluded.created_at,
                last_accessed_at=excluded.last_accessed_at,
                access_count=excluded.access_count
            """,
            record.id,
            record.text,
            record.scope,
            " ".join(record.tags),
            int(record.importance),
            json.dumps(record.metadata, default=str),
            record.embedding_dim,
            list(embedding),
            record.created_at,
            record.last_accessed_at,
            record.access_count,
        )

    async def get(self, memory_id: str) -> MemoryRecord | None:
        await self._ensure_connected()
        row = await self._conn.fetchrow(
            "SELECT * FROM memories WHERE id = $1", memory_id
        )
        return self._row(dict(row)) if row else None

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

        if embedding is not None:
            await self._conn.execute(
                """
                UPDATE memories SET text=$1, scope=$2, tags=$3, importance=$4,
                    metadata=$5, embedding_dim=$6, embedding=$7::vector,
                    last_accessed_at=$8
                WHERE id=$9
                """,
                record.text,
                record.scope,
                " ".join(record.tags),
                int(record.importance),
                json.dumps(record.metadata, default=str),
                record.embedding_dim,
                list(embedding),
                record.last_accessed_at,
                record.id,
            )
        else:
            await self._conn.execute(
                """
                UPDATE memories SET text=$1, scope=$2, tags=$3, importance=$4,
                    metadata=$5, embedding_dim=$6, last_accessed_at=$7
                WHERE id=$8
                """,
                record.text,
                record.scope,
                " ".join(record.tags),
                int(record.importance),
                json.dumps(record.metadata, default=str),
                record.embedding_dim,
                record.last_accessed_at,
                record.id,
            )
        return record

    async def delete(self, memory_id: str) -> bool:
        await self._ensure_connected()
        result = await self._conn.execute(
            "DELETE FROM memories WHERE id = $1", memory_id
        )
        return bool(result.split()[-1] != "0")

    async def delete_by_scope(self, scope: str) -> int:
        await self._ensure_connected()
        result = await self._conn.execute(
            "DELETE FROM memories WHERE scope = $1", scope
        )
        return int(result.split()[-1])

    async def search(self, query: BackendQuery) -> list[BackendHit]:
        await self._ensure_connected()
        k = query.limit + query.offset
        clauses: list[str] = []
        params: list[object] = []
        idx = 1

        if query.scope:
            clauses.append(f"scope = ${idx}")
            params.append(query.scope)
            idx += 1
        elif query.scope_in:
            ph = ", ".join(f"${i}" for i in range(idx, idx + len(query.scope_in)))
            clauses.append(f"scope IN ({ph})")
            params.extend(query.scope_in)
            idx += len(query.scope_in)

        where = " AND ".join(clauses) if clauses else "TRUE"
        emb_idx = idx
        params.append(list(query.query_embedding))
        limit_idx = idx + 1
        params.append(k)

        rows = await self._conn.fetch(
            f"""
            SELECT *, 1 - (embedding <=> ${emb_idx}::vector) AS sim
            FROM memories
            WHERE {where}
            ORDER BY embedding <=> ${emb_idx}::vector
            LIMIT ${limit_idx}
            """,
            *params,
        )
        hits = [
            BackendHit(
                record=self._row(dict(r)),
                score=max(0.0, min(1.0, float(r["sim"]))),
                keyword_score=_keyword_overlap(
                    [t for t in (str(r.get("tags", "") or "")).split() if t],
                    query.tags,
                ),
            )
            for r in rows
        ]
        return hits[query.offset : query.offset + query.limit]

    async def count(self, scope: str | None = None) -> int:
        await self._ensure_connected()
        if scope:
            val = await self._conn.fetchval(
                "SELECT COUNT(*) FROM memories WHERE scope = $1", scope
            )
        else:
            val = await self._conn.fetchval("SELECT COUNT(*) FROM memories")
        return val or 0

    async def list_scopes(self) -> dict[str, int]:
        await self._ensure_connected()
        rows = await self._conn.fetch(
            "SELECT scope, COUNT(*) AS n FROM memories GROUP BY scope"
        )
        return {r["scope"]: int(r["n"]) for r in rows}

    async def iter_all(self, scope: str | None = None) -> AsyncIterator[MemoryRecord]:
        await self._ensure_connected()
        if scope:
            rows = await self._conn.fetch(
                "SELECT * FROM memories WHERE scope = $1", scope
            )
        else:
            rows = await self._conn.fetch("SELECT * FROM memories")
        for row in rows:
            yield self._row(dict(row))

    async def touch(self, memory_id: str) -> None:
        record = await self.get(memory_id)
        if record is None:
            return
        await self._conn.execute(
            "UPDATE memories SET last_accessed_at=$1, access_count=$2 WHERE id=$3",
            time.time(),
            record.access_count + 1,
            record.id,
        )

    async def aclose(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


def _keyword_overlap(
    record_tags: Sequence[str], query_tags: Sequence[str] | None
) -> float:
    if not query_tags or not record_tags:
        return 0.0
    a = {t.lower() for t in record_tags}
    b = {t.lower() for t in query_tags}
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


__all__ = ["PgVectorBackend"]
