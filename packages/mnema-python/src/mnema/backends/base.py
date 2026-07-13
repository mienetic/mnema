"""Abstract vector backend interface.

A *backend* knows how to persist embeddings and run similarity + keyword
searches. It deliberately knows nothing about embeddings, decay, or MCP —
those concerns live in :mod:`mnema.service` and :mod:`mnema.embeddings`.

Three concrete backends are shipped:

* :class:`mnema.backends.chroma.ChromaBackend` — embedded, persistent (default)
* :class:`mnema.backends.qdrant.QdrantBackend` — local or remote, production grade
* :class:`mnema.backends.sqlite_vec.SqliteVecBackend` — pure-SQLite, zero-dep
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

from mnema.models import MemoryRecord


@dataclass(frozen=True)
class BackendQuery:
    """Parameters for a hybrid search at the backend layer.

    The backend is responsible for vector similarity and tag matching; the
    service layer combines those with the decay score afterward.

    Attributes:
        query_embedding: Pre-computed embedding of the search query.
        scope: Restrict to a single scope (exact match), or None for all.
        tags: Optional tags that boost ``keyword_score`` (OR semantics).
        scope_in: Restrict to one of these scopes (None = no scope filter).
        limit: Maximum hits to return.
        offset: Pagination offset.
    """

    query_embedding: Sequence[float]
    scope: str | None = None
    scope_in: Sequence[str] | None = None
    tags: Sequence[str] | None = None
    limit: int = 10
    offset: int = 0


@dataclass(frozen=True)
class BackendHit:
    """Raw hit returned by a backend, before service-layer scoring.

    ``score`` is the backend's native cosine similarity in ``[0, 1]``.
    ``keyword_score`` is the backend's tag-overlap contribution, also ``[0, 1]``
    (0 when tags aren't requested).
    """

    record: MemoryRecord
    score: float
    keyword_score: float = 0.0


class VectorBackend(ABC):
    """Pluggable vector-store interface used by :class:`MemoryService`.

    Implementations may be sync or async internally, but every method here is
    async so the service layer stays uniform. Implementations should make
    blocking work cooperative via :func:`anyio.to_thread.run_sync` when needed.
    """

    #: Short identifier used in stats and logs (e.g. ``"chroma"``).
    name: str = "base"

    @abstractmethod
    async def add(self, record: MemoryRecord, embedding: Sequence[float]) -> None:
        """Insert (or upsert by ``record.id``) a single memory."""

    @abstractmethod
    async def get(self, memory_id: str) -> MemoryRecord | None:
        """Return the memory with ``memory_id`` or ``None`` if missing."""

    @abstractmethod
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
        """Patch a memory. Returns the updated record, or ``None`` if missing.

        When ``text`` changes and ``embedding`` is supplied, the vector is
        replaced atomically with the metadata.
        """

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete one memory. Returns ``True`` if something was removed."""

    @abstractmethod
    async def delete_by_scope(self, scope: str) -> int:
        """Delete every memory in a scope. Returns the number removed."""

    @abstractmethod
    async def search(self, query: BackendQuery) -> list[BackendHit]:
        """Run a hybrid vector+tag search and return ranked hits."""

    @abstractmethod
    async def count(self, scope: str | None = None) -> int:
        """Total memory count, optionally restricted to a scope."""

    @abstractmethod
    async def list_scopes(self) -> dict[str, int]:
        """Return ``{scope: count}`` for every scope that has memories."""

    @abstractmethod
    async def iter_all(
        self, scope: str | None = None
    ) -> AsyncIterator[MemoryRecord]:
        """Iterate over all memories (optionally per scope). Used for decay."""

    async def aclose(self) -> None:
        """Release resources. Default no-op; override when needed."""
        return None


__all__ = ["BackendHit", "BackendQuery", "VectorBackend"]
