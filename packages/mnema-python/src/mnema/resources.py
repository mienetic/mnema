"""MCP resources — direct, URI-addressable reads of memory data.

Resources complement tools: they're ideal for clients that want to dereference
a stable URI without composing a query. Three templates are exposed:

* ``mnema://memory/{id}``            — a single memory
* ``mnema://scope/{scope}/summary``  — a quick snapshot of a scope
* ``mnema://stats``                  — the same JSON ``mnema_stats`` returns
"""

from __future__ import annotations

import json

from mnema.service import MemoryService


def register_resources(mcp, service: MemoryService) -> None:
    """Register all Mnema resources on a FastMCP server."""

    @mcp.resource("mnema://memory/{memory_id}")
    async def get_memory_resource(memory_id: str) -> str:
        """A single memory as JSON, addressed by id."""
        from mnema.errors import MemoryNotFoundError

        try:
            record = await service.get(memory_id)
        except MemoryNotFoundError as exc:
            return json.dumps({"error": str(exc)})
        return record.model_dump_json(indent=2)

    @mcp.resource("mnema://scope/{scope}/summary")
    async def get_scope_summary(scope: str) -> str:
        """A quick summary of a scope: counts, tags, importance histogram."""
        items = [m async for m in service.backend.iter_all(scope=scope)]
        if not items:
            return json.dumps({"scope": scope, "count": 0})
        tag_counts: dict[str, int] = {}
        importance_counts: dict[int, int] = {}
        for m in items:
            importance_counts[int(m.importance)] = importance_counts.get(int(m.importance), 0) + 1
            for t in m.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        top_tags = sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        return json.dumps(
            {
                "scope": scope,
                "count": len(items),
                "top_tags": top_tags,
                "importance": dict(sorted(importance_counts.items(), reverse=True)),
            },
            indent=2,
        )

    @mcp.resource("mnema://stats")
    async def get_stats_resource() -> str:
        """Aggregate store stats (same data as the ``mnema_stats`` tool)."""
        stats = await service.stats()
        return stats.model_dump_json(indent=2)


__all__ = ["register_resources"]
