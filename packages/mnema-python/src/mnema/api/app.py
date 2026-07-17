"""FastAPI application factory for the Mnema REST API.

A thin HTTP layer over :class:`~mnema.service.MemoryService`: every route is a
direct delegation to a service method plus (de)serialization — no business
logic lives here. Service exceptions are mapped to sensible status codes
(:class:`~mnema.errors.MemoryNotFoundError` → 404,
:class:`~mnema.errors.ScopeError` → 400); request-body validation is handled by
FastAPI/pydantic (→ 422).

This module imports FastAPI at load time, so it is only imported on demand (by
``mnema serve`` / :func:`create_app`). ``import mnema`` never touches it, which
keeps the optional ``api`` extra out of the core install — the same lazy-import
discipline the backends and embedding providers use.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from mnema._version import __version__
from mnema.api.schemas import (
    CreateMemoryRequest,
    RecallRequest,
    SearchRequest,
    UpdateMemoryRequest,
)
from mnema.config import MnemaConfig, load_config
from mnema.errors import MemoryNotFoundError, ScopeError
from mnema.models import MemoryRecord, SearchResponse, Stats
from mnema.service import MemoryService


def create_app(
    config: MnemaConfig | None = None,
    *,
    service: MemoryService | None = None,
) -> FastAPI:
    """Build a FastAPI app wrapping a :class:`MemoryService`.

    Args:
        config: Optional configuration. Loaded from env when omitted and no
            ``service`` is supplied.
        service: Optional pre-built service (useful in tests). When omitted, a
            fresh service is built from ``config`` and closed on shutdown.

    Returns:
        A ready-to-serve :class:`fastapi.FastAPI` application.
    """
    own_service = service is None
    svc = service if service is not None else MemoryService(config or load_config())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            # Only tear down a service we created ourselves; an injected one
            # is owned by the caller (e.g. the test fixture).
            if own_service:
                await svc.aclose()

    app = FastAPI(
        title="Mnema REST API",
        summary="Long-term memory for AI — REST layer over MemoryService.",
        version=__version__,
        lifespan=lifespan,
    )

    # --- exception mapping ------------------------------------------------
    @app.exception_handler(MemoryNotFoundError)
    async def _handle_not_found(_request: object, exc: MemoryNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(ScopeError)
    async def _handle_bad_scope(_request: object, exc: ScopeError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    # --- memories ---------------------------------------------------------
    @app.get("/memories", response_model=list[MemoryRecord], tags=["memories"])
    async def list_memories(
        scope: Annotated[str | None, Query(description="Restrict to one scope")] = None,
        limit: Annotated[int, Query(ge=1, description="Max records to return")] = 100,
        offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
    ) -> list[MemoryRecord]:
        records = [record async for record in svc.backend.iter_all(scope=scope)]
        return records[offset : offset + limit]

    @app.post(
        "/memories",
        response_model=MemoryRecord,
        status_code=status.HTTP_201_CREATED,
        tags=["memories"],
    )
    async def create_memory(body: CreateMemoryRequest) -> MemoryRecord:
        return await svc.remember(
            body.text,
            scope=body.scope,
            tags=body.tags,
            importance=body.importance,
            metadata=body.metadata,
        )

    @app.get("/memories/{memory_id}", response_model=MemoryRecord, tags=["memories"])
    async def get_memory(memory_id: str) -> MemoryRecord:
        return await svc.get(memory_id)

    @app.patch("/memories/{memory_id}", response_model=MemoryRecord, tags=["memories"])
    async def update_memory(memory_id: str, body: UpdateMemoryRequest) -> MemoryRecord:
        return await svc.update(
            memory_id,
            text=body.text,
            tags=body.tags,
            importance=body.importance,
            metadata=body.metadata,
        )

    @app.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["memories"])
    async def delete_memory(memory_id: str) -> Response:
        deleted = await svc.forget(memory_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory not found: {memory_id!r}",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # --- search -----------------------------------------------------------
    @app.post("/search", response_model=SearchResponse, tags=["search"])
    async def search(body: SearchRequest) -> SearchResponse:
        return await svc.search(
            body.query,
            scope=body.scope,
            tags=body.tags,
            limit=body.limit,
            offset=body.offset,
        )

    @app.post("/recall", response_model=SearchResponse, tags=["search"])
    async def recall(body: RecallRequest) -> SearchResponse:
        return await svc.recall(
            body.query,
            scope=body.scope,
            limit=body.limit,
            offset=body.offset,
        )

    # --- aggregate --------------------------------------------------------
    @app.get("/scopes", response_model=dict[str, int], tags=["stats"])
    async def scopes() -> dict[str, int]:
        return await svc.list_scopes()

    @app.get("/stats", response_model=Stats, tags=["stats"])
    async def stats() -> Stats:
        return await svc.stats()

    return app


__all__ = ["create_app"]
