"""Mnema programmatic SDK — use Mnema from Python without MCP.

This is the layer you reach for when you want memory in your own app, agent
framework, or notebook — without standing up an MCP server. It's a thin,
ergonomic facade over :class:`~mnema.service.MemoryService`.

Example::

    import asyncio
    from mnema.sdk import MemoryClient

    async def main():
        async with MemoryClient() as client:
            await client.remember("Alice likes Earl Grey tea", tags=["preferences"])
            hits = await client.search("what does Alice drink?")
            print(hits[0].memory.text)

    asyncio.run(main())

For a quick *synchronous* helper (handy in scripts), see :func:`sync_client`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Sequence
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from mnema.config import MnemaConfig, load_config
from mnema.errors import MemoryNotFoundError
from mnema.models import Importance, MemoryRecord, SearchResponse, Stats
from mnema.service import MemoryService
from mnema.summarize import SummarizationPlan


class MemoryClient:
    """Async programmatic client wrapping :class:`MemoryService`.

    This is the same engine the MCP server uses, so any app built on the SDK
    behaves identically to an MCP-connected client.
    """

    def __init__(
        self,
        config: MnemaConfig | None = None,
        *,
        service: MemoryService | None = None,
    ) -> None:
        self._config = config or load_config()
        self._service = service or MemoryService(self._config)
        self._owns_service = service is None

    # --- context manager ----------------------------------------------
    async def __aenter__(self) -> MemoryClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_service:
            await self._service.aclose()

    @property
    def service(self) -> MemoryService:
        """Escape hatch to the underlying service for advanced use."""
        return self._service

    # --- write ---------------------------------------------------------
    async def remember(
        self,
        text: str,
        *,
        scope: str | None = None,
        tags: Sequence[str] | None = None,
        importance: int | Importance = Importance.NORMAL,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """Store a memory. Returns the persisted record (with id)."""
        return await self._service.remember(
            text, scope=scope, tags=tags, importance=importance, metadata=metadata
        )

    # --- read ----------------------------------------------------------
    async def get(self, memory_id: str) -> MemoryRecord:
        """Fetch a memory by id (raises :class:`MemoryNotFoundError`)."""
        return await self._service.get(memory_id)

    async def recall(
        self,
        query: str,
        *,
        scope: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> SearchResponse:
        """Semantic vector search."""
        return await self._service.recall(
            query, scope=scope, limit=limit, offset=offset
        )

    async def search(
        self,
        query: str,
        *,
        scope: str | None = None,
        tags: Sequence[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> SearchResponse:
        """Hybrid search (vector + tag overlap + decay)."""
        return await self._service.search(
            query, scope=scope, tags=tags, limit=limit, offset=offset
        )

    # --- mutate --------------------------------------------------------
    async def update(
        self,
        memory_id: str,
        *,
        text: str | None = None,
        tags: list[str] | None = None,
        importance: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        return await self._service.update(
            memory_id, text=text, tags=tags, importance=importance, metadata=metadata
        )

    async def forget(self, memory_id: str) -> bool:
        """Delete one memory. Returns True if it existed."""
        return await self._service.forget(memory_id)

    async def forget_scope(self, scope: str) -> int:
        """Delete every memory in a scope."""
        return await self._service.forget_scope(scope)

    async def list_scopes(self) -> dict[str, int]:
        return await self._service.list_scopes()

    async def stats(self) -> Stats:
        return await self._service.stats()

    # --- decay & summarize --------------------------------------------
    async def apply_decay(
        self,
        *,
        scope: str | None = None,
        threshold: float = 0.05,
        dry_run: bool = True,
    ) -> list[MemoryRecord]:
        return await self._service.apply_decay(
            scope=scope, threshold=threshold, dry_run=dry_run
        )

    async def summarize(
        self,
        *,
        scope: str,
        similarity_threshold: float = 0.75,
    ) -> SummarizationPlan:
        return await self._service.summarize(
            scope=scope, similarity_threshold=similarity_threshold
        )


# ---------------------------------------------------------------------------
# Synchronous helpers
# ---------------------------------------------------------------------------
class SyncMemoryClient:
    """A thin synchronous wrapper around :class:`MemoryClient`.

    Handy for scripts and REPL use where async would be awkward. Every method
    runs the corresponding async method on a private event loop.
    """

    def __init__(
        self,
        config: MnemaConfig | None = None,
        *,
        service: MemoryService | None = None,
    ) -> None:
        self._loop = asyncio.new_event_loop()
        self._client = MemoryClient(config=config, service=service)

    def __enter__(self) -> SyncMemoryClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._loop.run_until_complete(self._client.close())
        finally:
            self._loop.close()

    def _run(self, coro: Any) -> Any:
        return self._loop.run_until_complete(coro)

    def remember(self, *args: Any, **kwargs: Any) -> MemoryRecord:
        return self._run(self._client.remember(*args, **kwargs))

    def get(self, memory_id: str) -> MemoryRecord:
        return self._run(self._client.get(memory_id))

    def recall(self, *args: Any, **kwargs: Any) -> SearchResponse:
        return self._run(self._client.recall(*args, **kwargs))

    def search(self, *args: Any, **kwargs: Any) -> SearchResponse:
        return self._run(self._client.search(*args, **kwargs))

    def update(self, *args: Any, **kwargs: Any) -> MemoryRecord:
        return self._run(self._client.update(*args, **kwargs))

    def forget(self, memory_id: str) -> bool:
        return self._run(self._client.forget(memory_id))

    def forget_scope(self, scope: str) -> int:
        return self._run(self._client.forget_scope(scope))

    def list_scopes(self) -> dict[str, int]:
        return self._run(self._client.list_scopes())

    def stats(self) -> Stats:
        return self._run(self._client.stats())

    def apply_decay(self, *args: Any, **kwargs: Any) -> list[MemoryRecord]:
        return self._run(self._client.apply_decay(*args, **kwargs))

    def summarize(self, *args: Any, **kwargs: Any) -> SummarizationPlan:
        return self._run(self._client.summarize(*args, **kwargs))


@asynccontextmanager
async def open_client(config: MnemaConfig | None = None) -> Iterator[MemoryClient]:
    """Async context manager that yields a ready :class:`MemoryClient`."""
    async with MemoryClient(config) as client:
        yield client


@contextmanager
def sync_client(config: MnemaConfig | None = None) -> Iterator[SyncMemoryClient]:
    """Sync context manager that yields a ready :class:`SyncMemoryClient`."""
    with SyncMemoryClient(config) as client:
        yield client


# Re-export errors so SDK users can catch them without a second import.
__all__ = [
    "MemoryClient",
    "MemoryNotFoundError",
    "SyncMemoryClient",
    "open_client",
    "sync_client",
]
