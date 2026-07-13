"""Pydantic data models shared across Mnema.

These models are the *only* shape the rest of the package talks to. Backends
and embedding providers translate to/from them; the MCP layer serializes them.
Keeping them isolated means backends can be swapped without touching tools.
"""

from __future__ import annotations

import time
import uuid
from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _now() -> float:
    """Monotonic-ish wall-clock seconds (UTC, unix epoch)."""
    return time.time()


class Importance(IntEnum):
    """How strongly a memory should resist decay.

    Higher values survive longer. ``NORMAL`` is the sensible default for most
    user-supplied facts; ``CRITICAL`` is for things that must never be
    forgotten (e.g. account IDs, security decisions).
    """

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class Scope(BaseModel):
    """A hierarchical memory namespace.

    Scopes isolate memories between users, sessions, or agents. They are
    plain strings with an optional ``kind:value`` convention so backends can
    build efficient filters::

        user:alice
        session:abc-123
        agent:research-bot
        global

    Attributes:
        value: The raw scope string (e.g. ``"user:alice"``).
        kind: The part before the colon, or the whole string when no colon.
        ident: The part after the colon, or empty.
    """

    model_config = ConfigDict(frozen=True)

    value: str = Field(..., description="Raw scope string", min_length=1, max_length=200)

    @field_validator("value")
    @classmethod
    def _no_whitespace(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("scope must not be empty")
        if any(ch.isspace() for ch in v):
            raise ValueError("scope must not contain whitespace")
        return v

    @property
    def kind(self) -> str:
        """The namespace kind (e.g. ``user`` in ``user:alice``)."""
        return self.value.split(":", 1)[0] if ":" in self.value else self.value

    @property
    def ident(self) -> str:
        """The namespace identifier (e.g. ``alice`` in ``user:alice``)."""
        return self.value.split(":", 1)[1] if ":" in self.value else ""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class Memory(BaseModel):
    """User-facing memory payload (no embedding or internal ids)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(
        ...,
        description="The memory content as natural language",
        min_length=1,
        max_length=32_000,
    )
    scope: str = Field(
        default="global",
        description="Namespace for this memory, e.g. 'user:alice', 'session:abc'",
        max_length=200,
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form labels for keyword/hybrid filtering",
        max_length=20,
    )
    importance: Importance = Field(
        default=Importance.NORMAL,
        description="How strongly this memory resists decay (1..10)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary extra metadata; never used for filtering by default",
    )


class MemoryRecord(Memory):
    """A persisted memory with all bookkeeping fields populated."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Stable memory id")
    embedding_dim: int = Field(..., description="Dimensionality of the stored vector")
    created_at: float = Field(default_factory=_now, description="Creation time (unix seconds)")
    last_accessed_at: float = Field(
        default_factory=_now, description="Last read time (unix seconds)"
    )
    access_count: int = Field(default=0, ge=0, description="How many times recalled/searched")
    score: float | None = Field(
        default=None,
        description="Similarity/decayed score assigned during search (0..1)",
    )


class SearchResult(BaseModel):
    """A single hybrid-search hit with the score decomposed."""

    model_config = ConfigDict(extra="forbid")

    memory: MemoryRecord
    score: float = Field(..., ge=0.0, le=1.0, description="Combined final score")
    vector_score: float = Field(
        ..., ge=0.0, le=1.0, description="Cosine-similarity component"
    )
    keyword_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Tag/keyword component"
    )
    decay_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Recency/frequency component"
    )


class SearchResponse(BaseModel):
    """Paginated search envelope returned by tools and the SDK."""

    results: list[SearchResult]
    count: int
    offset: int
    has_more: bool
    total_count: int | None = None
    scope: str | None = None


class Stats(BaseModel):
    """Aggregate statistics about the memory store."""

    total_memories: int
    scopes: dict[str, int]
    embedding_provider: str
    embedding_dim: int
    backend: str


__all__ = [
    "Importance",
    "Memory",
    "MemoryRecord",
    "Scope",
    "SearchResponse",
    "SearchResult",
    "Stats",
]
