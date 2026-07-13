"""sqlite-vec backend — pure-SQLite, zero-dependency vector store.

Loads the ``sqlite-vec`` loadable extension into a plain ``sqlite3``
connection. No server, no Docker — ideal when you want the smallest possible
footprint or are running inside constrained environments.

Install with::

    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \\
      | MNEMA_EXTRAS='sqlite_vec,local' bash
"""

from __future__ import annotations

import json
import sqlite3
import struct
import threading
import time
from collections.abc import AsyncIterator, Sequence

import anyio

from mnema.backends.base import BackendHit, BackendQuery, VectorBackend
from mnema.config import MnemaConfig
from mnema.errors import BackendInitError
from mnema.models import Importance, MemoryRecord


def _vec_to_blob(vec: Sequence[float]) -> bytes:
    """Pack a float32 vector into the BLOB layout sqlite-vec expects."""
    return struct.pack(f"{len(vec)}f", *vec)


class SqliteVecBackend(VectorBackend):
    """SQLite + sqlite-vec backend.

    sqlite-vec's ``vec0`` virtual table requires an INTEGER rowid, but Mnema
    memory ids are UUID hex strings. We keep a separate ``memories`` table
    that maps the string id to an autoincrement integer rowid used as the
    vector table key.
    """

    name = "sqlite_vec"

    def __init__(self, config: MnemaConfig) -> None:
        try:
            import sqlite_vec
        except ImportError as exc:  # pragma: no cover - guarded by factory
            raise BackendInitError(
                "sqlite-vec is not installed. Reinstall Mnema with the "
                "'sqlite_vec' extra:\n"
                "    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh "
                "| MNEMA_EXTRAS='sqlite_vec,local' bash"
            ) from exc

        self._config = config
        self._dim = config.embedding_dim or 384
        self._ext = sqlite_vec
        # SQLite connections are thread-bound by default; anyio may run each
        # call on a different worker thread, so we allow cross-thread use and
        # serialize all access with a lock.
        self._lock = threading.Lock()

        try:
            if config.backend_path == ":memory:":
                self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            else:
                import os

                os.makedirs(os.path.dirname(config.backend_path) or ".", exist_ok=True)
                self._conn = sqlite3.connect(
                    config.backend_path, check_same_thread=False
                )
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._conn.row_factory = sqlite3.Row
            with self._lock:
                self._init_schema()
        except BackendInitError:
            raise
        except Exception as exc:
            raise BackendInitError(f"Failed to initialize sqlite-vec: {exc}") from exc

    def _init_schema(self) -> None:
        dim = self._dim
        c = self._conn
        c.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories
            USING vec0(embedding float[{dim}])
            """
        )
        # `rowid` is the implicit integer key; `mnema_id` is the string id.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                mnema_id TEXT NOT NULL UNIQUE,
                text TEXT NOT NULL,
                scope TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '',
                importance INTEGER NOT NULL DEFAULT 5,
                metadata TEXT NOT NULL DEFAULT '{}',
                embedding_dim INTEGER NOT NULL,
                created_at REAL NOT NULL,
                last_accessed_at REAL NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS ix_memories_scope ON memories(scope)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_memories_mnema_id ON memories(mnema_id)")
        c.commit()

    # --- helpers --------------------------------------------------------
    @staticmethod
    def _row(row: sqlite3.Row) -> MemoryRecord:
        try:
            meta = json.loads(row["metadata"] or "{}")
        except Exception:
            meta = {}
        return MemoryRecord(
            id=row["mnema_id"],
            text=row["text"],
            scope=row["scope"],
            tags=[t for t in (row["tags"] or "").split() if t],
            importance=Importance(int(row["importance"])),
            metadata=meta if isinstance(meta, dict) else {},
            embedding_dim=int(row["embedding_dim"]),
            created_at=float(row["created_at"]),
            last_accessed_at=float(row["last_accessed_at"]),
            access_count=int(row["access_count"]),
        )

    def _locked(self, fn):
        def _wrapped(*args, **kwargs):
            with self._lock:
                return fn(*args, **kwargs)

        return _wrapped

    async def _run(self, fn):
        return await anyio.to_thread.run_sync(self._locked(fn))

    # --- API ------------------------------------------------------------
    async def add(self, record: MemoryRecord, embedding: Sequence[float]) -> None:
        def _do() -> None:
            with self._conn:
                cur = self._conn.execute(
                    "INSERT INTO memories "
                    "(mnema_id, text, scope, tags, importance, metadata, embedding_dim, "
                    " created_at, last_accessed_at, access_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(mnema_id) DO UPDATE SET "
                    "text=excluded.text, scope=excluded.scope, tags=excluded.tags, "
                    "importance=excluded.importance, metadata=excluded.metadata, "
                    "embedding_dim=excluded.embedding_dim, "
                    "created_at=excluded.created_at, "
                    "last_accessed_at=excluded.last_accessed_at, "
                    "access_count=excluded.access_count",
                    (
                        record.id,
                        record.text,
                        record.scope,
                        " ".join(record.tags),
                        int(record.importance),
                        json.dumps(record.metadata, default=str),
                        record.embedding_dim,
                        record.created_at,
                        record.last_accessed_at,
                        record.access_count,
                    ),
                )
                int_id = cur.lastrowid
                # On UPDATE the lastrowid may be the existing row; look it up.
                if int_id == 0 or int_id is None:
                    row = self._conn.execute(
                        "SELECT rowid FROM memories WHERE mnema_id = ?", (record.id,)
                    ).fetchone()
                    int_id = row["rowid"] if row else None
                else:
                    # For ON CONFLICT UPDATE, lastrowid may not reflect the row.
                    row = self._conn.execute(
                        "SELECT rowid FROM memories WHERE mnema_id = ?", (record.id,)
                    ).fetchone()
                    if row:
                        int_id = row["rowid"]
                if int_id is None:
                    raise BackendInitError(f"Could not resolve rowid for {record.id!r}")
                # Upsert the vector: delete + insert (vec0 has no upsert).
                self._conn.execute("DELETE FROM vec_memories WHERE rowid = ?", (int_id,))
                self._conn.execute(
                    "INSERT INTO vec_memories (rowid, embedding) VALUES (?, ?)",
                    (int_id, _vec_to_blob(embedding)),
                )

        await self._run(_do)

    async def get(self, memory_id: str) -> MemoryRecord | None:
        def _do() -> MemoryRecord | None:
            row = self._conn.execute(
                "SELECT * FROM memories WHERE mnema_id = ?", (memory_id,)
            ).fetchone()
            return self._row(row) if row else None

        return await self._run(_do)

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

        def _do() -> None:
            with self._conn:
                self._conn.execute(
                    "UPDATE memories SET text=?, scope=?, tags=?, importance=?, "
                    "metadata=?, embedding_dim=?, last_accessed_at=? WHERE mnema_id=?",
                    (
                        record.text,
                        record.scope,
                        " ".join(record.tags),
                        int(record.importance),
                        json.dumps(record.metadata, default=str),
                        record.embedding_dim,
                        record.last_accessed_at,
                        record.id,
                    ),
                )
                if embedding is not None:
                    row = self._conn.execute(
                        "SELECT rowid FROM memories WHERE mnema_id = ?", (record.id,)
                    ).fetchone()
                    if row:
                        int_id = row["rowid"]
                        self._conn.execute(
                            "DELETE FROM vec_memories WHERE rowid = ?", (int_id,)
                        )
                        self._conn.execute(
                            "INSERT INTO vec_memories (rowid, embedding) VALUES (?, ?)",
                            (int_id, _vec_to_blob(embedding)),
                        )

        await self._run(_do)
        return record

    async def delete(self, memory_id: str) -> bool:
        existing = await self.get(memory_id)
        if existing is None:
            return False

        def _do() -> None:
            with self._conn:
                row = self._conn.execute(
                    "SELECT rowid FROM memories WHERE mnema_id = ?", (memory_id,)
                ).fetchone()
                if row:
                    self._conn.execute(
                        "DELETE FROM vec_memories WHERE rowid = ?", (row["rowid"],)
                    )
                self._conn.execute("DELETE FROM memories WHERE mnema_id=?", (memory_id,))

        await self._run(_do)
        return True

    async def delete_by_scope(self, scope: str) -> int:
        ids = [r.id for r in await self._collect(scope=scope)]
        if not ids:
            return 0

        def _do() -> None:
            with self._conn:
                placeholders = ",".join("?" for _ in ids)
                rows = self._conn.execute(
                    f"SELECT rowid FROM memories WHERE mnema_id IN ({placeholders})", ids
                ).fetchall()
                int_ids = [r["rowid"] for r in rows]
                if int_ids:
                    vph = ",".join("?" for _ in int_ids)
                    self._conn.execute(
                        f"DELETE FROM vec_memories WHERE rowid IN ({vph})", int_ids
                    )
                self._conn.execute(
                    f"DELETE FROM memories WHERE mnema_id IN ({placeholders})", ids
                )

        await self._run(_do)
        return len(ids)

    async def search(self, query: BackendQuery) -> list[BackendHit]:
        k = query.limit + query.offset

        def _do() -> list[BackendHit]:
            # sqlite-vec requires MATCH + an explicit k constraint on the
            # vec0 virtual table. We query it first, then hydrate metadata.
            vec_rows = self._conn.execute(
                "SELECT rowid, distance FROM vec_memories "
                "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                (_vec_to_blob(query.query_embedding), k),
            ).fetchall()
            if not vec_rows:
                return []
            rowid_to_dist = {r["rowid"]: float(r["distance"]) for r in vec_rows}
            placeholders = ",".join("?" for _ in rowid_to_dist)
            sql = (
                f"SELECT * FROM memories WHERE rowid IN ({placeholders})"
            )
            params: list[object] = list(rowid_to_dist.keys())
            if query.scope:
                sql += " AND scope = ?"
                params.append(query.scope)
            elif query.scope_in:
                sph = ",".join("?" for _ in query.scope_in)
                sql += f" AND scope IN ({sph})"
                params.extend(query.scope_in)
            rows = self._conn.execute(sql, params).fetchall()
            hits: list[BackendHit] = []
            for row in rows:
                record = self._row(row)
                dist = rowid_to_dist.get(row["rowid"], 1.0)
                # cosine distance ∈ [0, 2] → similarity ∈ [0, 1]
                sim = max(0.0, min(1.0, 1.0 - dist / 2.0))
                ks = _keyword_overlap(record.tags, query.tags)
                hits.append(BackendHit(record=record, score=sim, keyword_score=ks))
            # Re-sort by similarity (scope filtering may have changed order).
            hits.sort(key=lambda h: h.score, reverse=True)
            return hits

        hits = await self._run(_do)
        return hits[query.offset : query.offset + query.limit]

    async def count(self, scope: str | None = None) -> int:
        def _do() -> int:
            if scope:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE scope=?", (scope,)
                ).fetchone()
            else:
                row = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()
            return int(row[0])

        return await self._run(_do)

    async def list_scopes(self) -> dict[str, int]:
        def _do() -> dict[str, int]:
            rows = self._conn.execute(
                "SELECT scope, COUNT(*) AS n FROM memories GROUP BY scope"
            ).fetchall()
            return {row["scope"]: int(row["n"]) for row in rows}

        return await self._run(_do)

    async def _collect(self, scope: str | None = None) -> list[MemoryRecord]:
        def _do() -> list[MemoryRecord]:
            if scope:
                rows = self._conn.execute(
                    "SELECT * FROM memories WHERE scope=?", (scope,)
                ).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM memories").fetchall()
            return [self._row(r) for r in rows]

        return await self._run(_do)

    async def iter_all(self, scope: str | None = None) -> AsyncIterator[MemoryRecord]:
        for r in await self._collect(scope=scope):
            yield r

    async def touch(self, memory_id: str) -> None:
        record = await self.get(memory_id)
        if record is None:
            return

        def _do() -> None:
            with self._conn:
                self._conn.execute(
                    "UPDATE memories SET last_accessed_at=?, access_count=? WHERE mnema_id=?",
                    (time.time(), record.access_count + 1, record.id),
                )

        await self._run(_do)

    async def aclose(self) -> None:
        def _do() -> None:
            with self._lock:
                self._conn.close()

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


__all__ = ["SqliteVecBackend"]
