"""Mnema's MCP tools package.

Each tool is a thin wrapper around :class:`~mnema.service.MemoryService` that
exposes a typed Pydantic input model and returns JSON-serializable content.
"""

from __future__ import annotations

from mnema.tools.manage import register_manage_tools
from mnema.tools.recall import register_recall_tools
from mnema.tools.remember import register_remember_tools
from mnema.tools.search import register_search_tools
from mnema.tools.summarize import register_summarize_tools

__all__ = [
    "register_all_tools",
    "register_manage_tools",
    "register_recall_tools",
    "register_remember_tools",
    "register_search_tools",
    "register_summarize_tools",
]


def register_all_tools(mcp, service) -> None:
    """Register every Mnema tool on a FastMCP server instance."""
    register_remember_tools(mcp, service)
    register_recall_tools(mcp, service)
    register_search_tools(mcp, service)
    register_manage_tools(mcp, service)
    register_summarize_tools(mcp, service)
