"""Shared Pydantic input models and helpers for MCP tools.

These models are intentionally explicit and well-documented because FastMCP
derives the tool's ``inputSchema`` from them — clear field descriptions make
the tools discoverable by AI clients.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResponseFormat(str, Enum):
    """Output format selector for tools that return data."""

    MARKDOWN = "markdown"
    JSON = "json"


def to_json(obj: Any) -> str:
    """Serialize a Pydantic model or dict to indented JSON."""
    import json

    if hasattr(obj, "model_dump_json"):
        return obj.model_dump_json(indent=2)
    if isinstance(obj, BaseModel):
        return json.dumps(obj.model_dump(mode="json"), indent=2, default=str)
    return json.dumps(obj, indent=2, default=str)


class _BaseToolInput(BaseModel):
    """Common config for every tool input model."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )


class _PaginatedInput(_BaseToolInput):
    """Inputs that support pagination."""

    limit: int = Field(default=10, ge=1, le=100, description="Max results to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


__all__ = ["ResponseFormat", "to_json"]
