"""Mnema Dashboard — a web UI over MemoryService.

Built as a FastAPI app that wraps the existing REST API and adds HTML-rendered
routes with Jinja2 templates and htmx for interactivity.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from mnema._version import __version__
from mnema.api.app import create_app
from mnema.config import MnemaConfig, load_config
from mnema.errors import MemoryNotFoundError
from mnema.models import Importance, MemoryRecord, Stats
from mnema.service import MemoryService

_HERE = Path(__file__).resolve().parent

TEMPLATES_DIR = _HERE / "templates"
STATIC_DIR = _HERE / "static"

_PAGE_SIZE = 20


def _importance_label(val: int) -> str:
    labels = {1: "LOW", 5: "NORMAL", 8: "HIGH", 10: "CRITICAL"}
    closest = min(labels, key=lambda k: abs(k - val))
    return labels[closest]


def _fmt_time(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts))


def _time_ago(ts: float) -> str:
    delta = time.time() - ts
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    days = int(delta // 86400)
    return f"{days}d ago" if days < 30 else f"{days // 30}mo ago"


def _decay_color(score: float | None) -> str:
    if score is None:
        return "var(--muted)"
    if score >= 0.5:
        return "var(--green)"
    if score >= 0.2:
        return "var(--yellow)"
    return "var(--red)"


def _paginate(records: list, page: int, page_size: int) -> tuple[list, int, int, int]:
    total = len(records)
    total_pages = max(1, math.ceil(total / page_size))
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return records[start:end], page, total_pages, total


async def _get_service(request: Request) -> MemoryService:
    return request.app.state._svc  # noqa: SLF001


def _make_templates() -> Jinja2Templates:
    t = Jinja2Templates(directory=str(TEMPLATES_DIR))
    t.env.globals.setdefault("int", int)
    return t


def create_dashboard_app(
    config: MnemaConfig | None = None,
    *,
    service: MemoryService | None = None,
) -> FastAPI:
    own_service = service is None
    svc = service if service is not None else MemoryService(config or load_config())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if own_service:
                await svc.aclose()

    app = FastAPI(
        title="Mnema Dashboard",
        summary="Web UI for Mnema long-term memory.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state._svc = svc  # noqa: SLF001

    templates = _make_templates()

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # --- helpers ----------------------------------------------------------------

    def _nav(stats: Stats | None = None) -> dict:
        return {
            "version": __version__,
            "stats": stats,
        }

    async def _stats_or_none() -> Stats | None:
        try:
            return await svc.stats()
        except Exception:
            return None

    # --- dashboard home ---------------------------------------------------------

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def home(request: Request):
        stats = await _stats_or_none()
        scopes_list = sorted(stats.scopes.items()) if stats and stats.scopes else []
        max_count = max((c for _, c in scopes_list), default=1)
        return templates.TemplateResponse(
            request,
            "index.html",
            {"request": request, "stats": stats, "scopes": scopes_list, "max_count": max_count, "nav": _nav(stats)},
        )

    # --- memories list ----------------------------------------------------------

    @app.get("/memories", response_class=HTMLResponse, include_in_schema=False)
    async def list_memories(
        request: Request,
        scope: str | None = Query(default=None),
        sort: str = Query(default="created_at"),
        page: int = Query(default=1, ge=1),
    ):
        stats = await _stats_or_none()
        records = [r async for r in svc.backend.iter_all(scope=scope)]
        if sort == "importance":
            records.sort(key=lambda r: int(r.importance), reverse=True)
        else:
            records.sort(key=lambda r: r.created_at, reverse=True)
        page_records, current_page, total_pages, total = _paginate(records, page, _PAGE_SIZE)
        all_scopes = sorted(stats.scopes.keys()) if stats and stats.scopes else []
        return templates.TemplateResponse(
            request,
            "memories.html",
            {
                "request": request,
                "records": page_records,
                "current_page": current_page,
                "total_pages": total_pages,
                "total": total,
                "scope_filter": scope or "",
                "sort": sort,
                "all_scopes": all_scopes,
                "stats": stats,
                "nav": _nav(stats),
                "_fmt_time": _fmt_time,
                "_time_ago": _time_ago,
                "_importance_label": _importance_label,
            },
        )

    # --- create memory ----------------------------------------------------------

    @app.post("/memories", include_in_schema=False)
    async def create_memory(request: Request):
        body = await request.json()
        record = await svc.remember(
            text=body["text"],
            scope=body.get("scope", "global"),
            importance=body.get("importance", 5),
            tags=body.get("tags"),
            metadata=body.get("metadata"),
        )
        return JSONResponse({"id": record.id}, status_code=201)

    # --- memory detail ----------------------------------------------------------

    @app.get("/memories/{memory_id}", response_class=HTMLResponse, include_in_schema=False)
    async def view_memory(request: Request, memory_id: str):
        stats = await _stats_or_none()
        try:
            record = await svc.get(memory_id)
        except MemoryNotFoundError:
            return templates.TemplateResponse(
                request,
                "error.html",
                {"request": request, "message": f"Memory not found: {memory_id}", "nav": _nav(stats)},
                status_code=404,
            )
        return templates.TemplateResponse(
            request,
            "memory_detail.html",
            {
                "request": request,
                "record": record,
                "stats": stats,
                "nav": _nav(stats),
                "_fmt_time": _fmt_time,
                "_time_ago": _time_ago,
                "_importance_label": _importance_label,
                "_decay_color": _decay_color,
                "json": json,
            },
        )

    # --- edit memory ------------------------------------------------------------

    @app.get("/memories/{memory_id}/edit", response_class=HTMLResponse, include_in_schema=False)
    async def edit_memory_form(request: Request, memory_id: str):
        stats = await _stats_or_none()
        try:
            record = await svc.get(memory_id)
        except MemoryNotFoundError:
            return templates.TemplateResponse(
                request,
                "error.html",
                {"request": request, "message": f"Memory not found: {memory_id}", "nav": _nav(stats)},
                status_code=404,
            )
        return templates.TemplateResponse(
            request,
            "memory_edit.html",
            {
                "request": request,
                "record": record,
                "stats": stats,
                "nav": _nav(stats),
                "importance_values": list(range(1, 11)),
                "_importance_label": _importance_label,
                "json": json,
            },
        )

    @app.post("/memories/{memory_id}/edit", include_in_schema=False)
    async def edit_memory_submit(
        request: Request,
        memory_id: str,
        text: str = Form(...),
        scope: str = Form(...),
        importance: int = Form(...),
        tags: str = Form(default=""),
        metadata_json: str = Form(default="{}"),
    ):
        stats = await _stats_or_none()
        parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]
        parsed_metadata = {}
        if metadata_json.strip():
            try:
                parsed_metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                pass
        try:
            await svc.update(
                memory_id,
                text=text or None,
                tags=parsed_tags or None,
                importance=importance,
                metadata=parsed_metadata or None,
            )
        except MemoryNotFoundError:
            return templates.TemplateResponse(
                request,
                "error.html",
                {"request": request, "message": f"Memory not found: {memory_id}", "nav": _nav(stats)},
                status_code=404,
            )
        return RedirectResponse(url=f"/memories/{memory_id}", status_code=303)

    # --- forget memory ----------------------------------------------------------

    @app.post("/memories/{memory_id}/forget", include_in_schema=False)
    async def forget_memory(request: Request, memory_id: str):
        stats = await _stats_or_none()
        scope_q = request.query_params.get("scope", "")
        page_q = request.query_params.get("page", "1")
        await svc.forget(memory_id)
        redirect = f"/memories?scope={scope_q}&page={page_q}" if scope_q else f"/memories?page={page_q}"
        return RedirectResponse(url=redirect, status_code=303)

    # --- search -----------------------------------------------------------------

    @app.get("/search", response_class=HTMLResponse, include_in_schema=False)
    async def search_page(request: Request):
        stats = await _stats_or_none()
        all_scopes = sorted(stats.scopes.keys()) if stats and stats.scopes else []
        return templates.TemplateResponse(
            request,
            "search.html",
            {
                "request": request,
                "results": None,
                "query": "",
                "scope_filter": "",
                "tags_filter": "",
                "all_scopes": all_scopes,
                "stats": stats,
                "nav": _nav(stats),
                "_importance_label": _importance_label,
                "_time_ago": _time_ago,
            },
        )

    @app.get("/search/results", response_class=HTMLResponse, include_in_schema=False)
    async def search_results(
        request: Request,
        query: str = Query(default=""),
        scope: str | None = Query(default=None),
        tags: str | None = Query(default=None),
    ):
        stats = await _stats_or_none()
        parsed_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
        t0 = time.time()
        res = await svc.search(query, scope=scope or None, tags=parsed_tags or None)
        elapsed = time.time() - t0
        return templates.TemplateResponse(
            request,
            "_search_results.html",
            {
                "request": request,
                "results": res,
                "elapsed": elapsed,
                "query": query,
                "_importance_label": _importance_label,
                "_time_ago": _time_ago,
            },
        )

    # --- decay ------------------------------------------------------------------

    @app.get("/decay", response_class=HTMLResponse, include_in_schema=False)
    async def decay_page(request: Request):
        stats = await _stats_or_none()
        all_scopes = sorted(stats.scopes.keys()) if stats and stats.scopes else []
        return templates.TemplateResponse(
            request,
            "decay.html",
            {
                "request": request,
                "candidates": None,
                "threshold": 0.05,
                "scope_filter": "",
                "applied": False,
                "all_scopes": all_scopes,
                "stats": stats,
                "nav": _nav(stats),
                "_truncate": lambda t, w=80: (t.replace("\n", " ").strip()[: w - 1] + "...") if len(t) > w else t,
            },
        )

    @app.post("/decay", response_class=HTMLResponse, include_in_schema=False)
    async def decay_run(
        request: Request,
        threshold: float = Form(default=0.05),
        scope: str = Form(default=""),
        apply: bool = Form(default=False),
    ):
        stats = await _stats_or_none()
        candidates = await svc.apply_decay(
            scope=scope or None,
            threshold=threshold,
            dry_run=not apply,
        )
        all_scopes = sorted(stats.scopes.keys()) if stats and stats.scopes else []
        return templates.TemplateResponse(
            request,
            "_decay_results.html",
            {
                "request": request,
                "candidates": candidates,
                "threshold": threshold,
                "scope_filter": scope,
                "applied": apply,
                "all_scopes": all_scopes,
                "stats": stats,
                "nav": _nav(stats),
                "_truncate": lambda t, w=80: (t.replace("\n", " ").strip()[: w - 1] + "...") if len(t) > w else t,
            },
        )

    # --- summarize --------------------------------------------------------------

    @app.get("/summarize", response_class=HTMLResponse, include_in_schema=False)
    async def summarize_page(request: Request):
        stats = await _stats_or_none()
        all_scopes = sorted(stats.scopes.keys()) if stats and stats.scopes else []
        return templates.TemplateResponse(
            request,
            "summarize.html",
            {
                "request": request,
                "plan": None,
                "scope_filter": "",
                "similarity_threshold": 0.75,
                "all_scopes": all_scopes,
                "stats": stats,
                "nav": _nav(stats),
            },
        )

    @app.post("/summarize", response_class=HTMLResponse, include_in_schema=False)
    async def summarize_run(
        request: Request,
        scope: str = Form(default=""),
        similarity_threshold: float = Form(default=0.75),
    ):
        stats = await _stats_or_none()
        all_scopes = sorted(stats.scopes.keys()) if stats and stats.scopes else []
        plan = None
        error = None
        try:
            plan = await svc.summarize(scope=scope, similarity_threshold=similarity_threshold)
        except Exception as exc:
            error = str(exc)
        return templates.TemplateResponse(
            request,
            "_summarize_results.html",
            {
                "request": request,
                "plan": plan,
                "scope_filter": scope,
                "similarity_threshold": similarity_threshold,
                "error": error,
                "all_scopes": all_scopes,
                "stats": stats,
                "nav": _nav(stats),
            },
        )

    return app
