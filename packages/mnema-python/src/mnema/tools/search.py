"""``mnema_search`` — hybrid vector + keyword + decay search."""

from __future__ import annotations

from mnema.service import MemoryService
from mnema.tools._common import ResponseFormat, to_json


def register_search_tools(mcp, service: MemoryService) -> None:
    """Register the hybrid search tool."""

    @mcp.tool(
        name="mnema_search",
        annotations={
            "title": "Search (hybrid)",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def mnema_search(
        query: str,
        scope: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
        offset: int = 0,
        response_format: ResponseFormat = ResponseFormat.JSON,
    ) -> str:
        """Hybrid search: vector similarity + tag overlap + decay boost.

        Use this when you want to combine meaning with explicit tags. For
        pure semantic recall use ``mnema_recall`` instead.

        Args:
            query: A natural-language query.
            scope: Restrict to a scope (e.g. 'session:abc').
            tags: Tags to boost on (OR semantics). Empty = vector-only.
            limit: Max hits (1..100). Default 10.
            offset: Pagination offset. Default 0.
            response_format: 'json' (default) or 'markdown'.

        Returns:
            Ranked hits with decomposed ``vector_score``, ``keyword_score``,
            ``decay_score`` and combined ``score``.
        """
        response = await service.search(
            query, scope=scope, tags=tags, limit=limit, offset=offset
        )
        if response_format == ResponseFormat.MARKDOWN:
            return _markdown(query, tags or [], response.results)
        return to_json(response)


def _markdown(query: str, tags: list[str], results) -> str:
    if not results:
        tag_part = f" tags={tags}" if tags else ""
        return f"No memories matched **{query}**{tag_part}.\n"
    lines = [
        f"# Hybrid search: {query}",
        "",
        f"{len(results)} match(es)." + (f" (tags: {', '.join(tags)})" if tags else ""),
        "",
    ]
    for i, hit in enumerate(results, 1):
        m = hit.memory
        lines.append(f"## {i}. score={hit.score:.3f} `{m.id}`")
        lines.append(f"- scope: `{m.scope}` · importance: {int(m.importance)}")
        if m.tags:
            lines.append(f"- tags: {', '.join(m.tags)}")
        lines.append(
            f"- _vector={hit.vector_score:.3f} "
            f"keyword={hit.keyword_score:.3f} decay={hit.decay_score:.3f}_"
        )
        lines.append("")
        lines.append(f"> {m.text}")
        lines.append("")
    return "\n".join(lines)
