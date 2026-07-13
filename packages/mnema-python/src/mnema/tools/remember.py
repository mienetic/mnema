"""``mnema_remember`` — store a new memory."""

from __future__ import annotations

from typing import Any

from mnema.models import Importance
from mnema.service import MemoryService
from mnema.tools._common import ResponseFormat, to_json


def register_remember_tools(mcp, service: MemoryService) -> None:
    """Register the remember tool on a FastMCP server.

    Uses flat keyword parameters (rather than a single Pydantic model) so
    FastMCP surfaces each field as a top-level tool argument — the convention
    AI clients expect.
    """

    @mcp.tool(
        name="mnema_remember",
        annotations={
            "title": "Remember",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def mnema_remember(
        text: str,
        scope: str | None = None,
        tags: list[str] | None = None,
        importance: int = int(Importance.NORMAL),
        metadata: dict[str, Any] | None = None,
        response_format: ResponseFormat = ResponseFormat.JSON,
    ) -> str:
        """Store a new memory so it can be recalled later.

        Use this whenever the user shares a durable fact, preference,
        decision, or piece of context worth remembering across sessions.
        Avoid storing transient / single-conversation details.

        Args:
            text: The memory to store, as natural language. Write it so
                future-you will understand it without the surrounding
                conversation.
            scope: Namespace for this memory, e.g. 'user:alice',
                'session:abc', 'agent:bot-1'. Defaults to the server's
                configured default scope.
            tags: Free-form labels for keyword/hybrid filtering.
            importance: How strongly this memory resists decay
                (1=low … 10=critical). Default 5.
            metadata: Arbitrary extra metadata (JSON object).
            response_format: 'json' (default) or 'markdown'.

        Returns:
            JSON or Markdown describing the stored memory (including its id).
        """
        record = await service.remember(
            text,
            scope=scope,
            tags=tags or [],
            importance=importance,
            metadata=metadata or {},
        )
        if response_format == ResponseFormat.MARKDOWN:
            return (
                f"# ✅ Remembered\n\n"
                f"- **id**: `{record.id}`\n"
                f"- **scope**: `{record.scope}`\n"
                f"- **importance**: {int(record.importance)}\n"
                f"- **tags**: {', '.join(record.tags) or '—'}\n\n"
                f"> {record.text}\n"
            )
        return to_json(record)
