"""Request schemas for the REST API.

These mirror the keyword arguments of :class:`~mnema.service.MemoryService`
one-for-one — nothing is added that the service doesn't already accept. The
*response* shapes reuse the canonical models from :mod:`mnema.models`
(:class:`~mnema.models.MemoryRecord`, :class:`~mnema.models.SearchResponse`,
:class:`~mnema.models.Stats`) so the HTTP surface and the Python API never
drift.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mnema.models import Importance


class CreateMemoryRequest(BaseModel):
    """Body for ``POST /memories`` — mirrors :meth:`MemoryService.remember`."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=32_000,
        description="The memory content as natural language",
    )
    scope: str | None = Field(
        default=None,
        description="Namespace, e.g. 'user:alice' (defaults to the server's default scope)",
    )
    tags: list[str] | None = Field(
        default=None, description="Free-form labels for keyword/hybrid filtering"
    )
    importance: int = Field(
        default=int(Importance.NORMAL),
        ge=1,
        le=10,
        description="How strongly this memory resists decay (1=low … 10=critical)",
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Arbitrary extra metadata"
    )


class UpdateMemoryRequest(BaseModel):
    """Body for ``PATCH /memories/{id}`` — mirrors :meth:`MemoryService.update`.

    Every field is optional; only the ones provided are changed. Supplying a
    new ``text`` triggers a re-embed on the service side.
    """

    text: str | None = Field(default=None, min_length=1, max_length=32_000)
    tags: list[str] | None = None
    importance: int | None = Field(default=None, ge=1, le=10)
    metadata: dict[str, Any] | None = None


class SearchRequest(BaseModel):
    """Body for ``POST /search`` — mirrors :meth:`MemoryService.search`."""

    query: str = Field(..., min_length=1, description="What to search for")
    scope: str | None = Field(default=None, description="Restrict to one scope")
    tags: list[str] | None = Field(
        default=None, description="Tags to boost in the hybrid score"
    )
    limit: int = Field(default=10, ge=1, description="Max results to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class RecallRequest(BaseModel):
    """Body for ``POST /recall`` — mirrors :meth:`MemoryService.recall`."""

    query: str = Field(..., min_length=1, description="What to recall")
    scope: str | None = Field(default=None, description="Restrict to one scope")
    limit: int = Field(default=10, ge=1, description="Max results to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


__all__ = [
    "CreateMemoryRequest",
    "RecallRequest",
    "SearchRequest",
    "UpdateMemoryRequest",
]
