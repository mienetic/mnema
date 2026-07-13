"""``mnema_recall`` — pure semantic vector search."""

from __future__ import annotations

from mnema.service import MemoryService
from mnema.tools._common import ResponseFormat, to_json


def register_recall_tools(mcp, service: MemoryService) -> None:
    """Register the recall tool on a FastMCP server."""

    @mcp.tool(
        name="mnema_recall",
        annotations={
            "title": "Recall (semantic)",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def mnema_recall(
        query: str,
        scope: str | None = None,
        limit: int = 10,
        offset: int = 0,
        response_format: ResponseFormat = ResponseFormat.JSON,
    ) -> str:
        """Find memories by meaning (vector similarity).

        Prefer this over keyword search when the user asks about a topic in
        different words than how it was stored. Use ``mnema_search`` instead
        when you also want to filter by tags.

        Args:
            query: What to recall — a natural-language query.
            scope: Restrict to a scope (e.g. 'user:alice').
            limit: Max hits (1..100). Default 10.
            offset: Pagination offset. Default 0.
            response_format: 'json' (default) or 'markdown'.

        Returns:
            Ranked hits as JSON or Markdown. Each hit has a combined
            ``score`` plus its ``vector_score`` and ``decay_score`` parts.
        """
        response = await service.recall(
            query, scope=scope, limit=limit, offset=offset
        )
        if response_format == ResponseFormat.MARKDOWN:
            return _markdown(query, response.results)
        return to_json(response)


def _markdown(query: str, results) -> str:
    if not results:
        return f"No memories matched **{query}**.\n"
    lines = [f"# Recall: {query}", "", f"{len(results)} match(es).", ""]
    for i, hit in enumerate(results, 1):
        m = hit.memory
        lines.append(f"## {i}. score={hit.score:.3f} `{m.id}`")
        lines.append(f"- scope: `{m.scope}` · importance: {int(m.importance)}")
        if m.tags:
            lines.append(f"- tags: {', '.join(m.tags)}")
        lines.append(f"- _vector={hit.vector_score:.3f} decay={hit.decay_score:.3f}_")
        lines.append("")
        lines.append(f"> {m.text}")
        lines.append("")
    return "\n".join(lines)
