"""Mnema MCP server bootstrap.

This module wires the :class:`~mnema.service.MemoryService` into a FastMCP
server, registers all tools/resources/prompts, and exposes ``create_server``
plus ``run`` for the entry point in :mod:`mnema.__main__`.

The server supports both transports:

* ``stdio`` (default) — for local integrations (Claude Desktop, ZCode, etc.).
* ``http`` — streamable HTTP, for remote / multi-client deployments.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from mnema.config import MnemaConfig, load_config
from mnema.service import MemoryService


def _import_fastmcp():
    """Import FastMCP lazily so importing :mod:`mnema` doesn't require the SDK."""
    from mcp.server.fastmcp import FastMCP

    return FastMCP


def create_server(
    config: MnemaConfig | None = None,
    *,
    service: MemoryService | None = None,
) -> tuple[Any, MemoryService]:
    """Build a FastMCP server pre-loaded with all Mnema tools.

    Args:
        config: Optional configuration. Loaded from env when omitted.
        service: Optional pre-built service (useful in tests). When omitted,
            a fresh service is built from ``config``.

    Returns:
        ``(mcp_server, service)`` — the server is ready to ``.run()``.
    """
    cfg = config or load_config()
    own_service = service is None
    svc = service or MemoryService(cfg)
    FastMCP = _import_fastmcp()

    @asynccontextmanager
    async def lifespan(_app):
        # Start the Auto Dream background scheduler if enabled.
        dreamer = None
        if cfg.dream_enabled:
            from mnema.dream import Dreamer

            dreamer = Dreamer(svc, cfg)
            await dreamer.start()
        try:
            yield {"service": svc}
        finally:
            if dreamer is not None:
                await dreamer.stop()
            if own_service:
                await svc.aclose()

    mcp = FastMCP("mnema", lifespan=lifespan)

    # Register tools, resources, prompts.
    from mnema.prompts import register_prompts
    from mnema.resources import register_resources
    from mnema.tools import register_all_tools

    register_all_tools(mcp, svc)
    register_resources(mcp, svc)
    register_prompts(mcp, svc)

    return mcp, svc


def run(config: MnemaConfig | None = None) -> None:
    """Build the server and run it with the configured transport.

    For ``stdio`` (default) this blocks until the client disconnects. For
    ``http`` it serves on ``config.http_host:config.http_port``.
    """
    cfg = config or load_config()
    mcp, _svc = create_server(cfg)
    if cfg.transport == "http":
        mcp.run(transport="streamable_http", host=cfg.http_host, port=cfg.http_port)
    else:
        mcp.run()


__all__ = ["create_server", "run"]
