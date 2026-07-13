"""Memory management tools: get, update, forget, list_scopes, stats, decay."""

from __future__ import annotations

from typing import Any

from mnema.errors import MemoryNotFoundError
from mnema.service import MemoryService
from mnema.tools._common import to_json


def register_manage_tools(mcp, service: MemoryService) -> None:
    """Register the memory-management tools (flat params)."""

    @mcp.tool(
        name="mnema_get_memory",
        annotations={
            "title": "Get memory",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def mnema_get_memory(
        memory_id: str,
    ) -> str:
        """Fetch a single memory by id (bumps its access counters).

        Args:
            memory_id: The memory id to fetch.
        """
        try:
            record = await service.get(memory_id)
        except MemoryNotFoundError as exc:
            return f"Error: {exc}"
        return to_json(record)

    @mcp.tool(
        name="mnema_update_memory",
        annotations={
            "title": "Update memory",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def mnema_update_memory(
        memory_id: str,
        text: str | None = None,
        tags: list[str] | None = None,
        importance: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Patch a memory's text/tags/importance/metadata. Re-embeds on text change.

        Args:
            memory_id: The memory to update.
            text: New text (re-embeds when set).
            tags: New tags list.
            importance: New importance (1..10).
            metadata: New metadata object.
        """
        try:
            record = await service.update(
                memory_id, text=text, tags=tags, importance=importance, metadata=metadata
            )
        except MemoryNotFoundError as exc:
            return f"Error: {exc}"
        return to_json(record)

    @mcp.tool(
        name="mnema_forget",
        annotations={
            "title": "Forget memory",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def mnema_forget(
        memory_id: str,
    ) -> str:
        """Delete a single memory by id. Idempotent.

        Args:
            memory_id: The memory id to delete.
        """
        ok = await service.forget(memory_id)
        return to_json({"forgotten": ok, "memory_id": memory_id})

    @mcp.tool(
        name="mnema_forget_scope",
        annotations={
            "title": "Forget scope",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def mnema_forget_scope(
        scope: str,
    ) -> str:
        """Delete every memory in a scope. Returns the count removed.

        Args:
            scope: Scope whose memories to delete.
        """
        n = await service.forget_scope(scope)
        return to_json({"forgotten": n, "scope": scope})

    @mcp.tool(
        name="mnema_list_scopes",
        annotations={
            "title": "List scopes",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def mnema_list_scopes(
    ) -> str:
        """Enumerate every scope that contains at least one memory."""
        scopes = await service.list_scopes()
        return to_json({"scopes": scopes, "count": len(scopes)})

    @mcp.tool(
        name="mnema_stats",
        annotations={
            "title": "Stats",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def mnema_stats(
    ) -> str:
        """Return aggregate stats about the memory store."""
        stats = await service.stats()
        return to_json(stats)

    @mcp.tool(
        name="mnema_apply_decay",
        annotations={
            "title": "Apply decay",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def mnema_apply_decay(
        scope: str | None = None,
        threshold: float = 0.05,
        dry_run: bool = True,
    ) -> str:
        """Find (and optionally forget) memories with a low decay score.

        By default runs in dry-run mode — nothing is deleted. Set
        ``dry_run=false`` to actually forget the candidates.

        Args:
            scope: Restrict the sweep to one scope, or omit for all.
            threshold: Decay score at or below which a memory is a candidate.
            dry_run: When True (default) nothing is deleted.
        """
        candidates = await service.apply_decay(
            scope=scope, threshold=threshold, dry_run=dry_run
        )
        return to_json(
            {
                "mode": "dry_run" if dry_run else "forget",
                "scope": scope,
                "threshold": threshold,
                "candidate_count": len(candidates),
                "candidates": [c.model_dump(mode="json") for c in candidates],
            }
        )
