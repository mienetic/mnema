"""``mnema_summarize`` — plan how to consolidate a scope's memories.

This tool returns a *plan* (clusters + forget candidates) and a ready-to-use
prompt. The calling AI does the actual summarization. This keeps Mnema
LLM-free by default while still enabling compact, long-term recall.
"""

from __future__ import annotations

from mnema.service import MemoryService
from mnema.summarize import build_summary_prompt
from mnema.tools._common import ResponseFormat, to_json


def register_summarize_tools(mcp, service: MemoryService) -> None:
    """Register the summarize tool."""

    @mcp.tool(
        name="mnema_summarize",
        annotations={
            "title": "Summarize scope",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def mnema_summarize(
        scope: str,
        similarity_threshold: float = 0.75,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Plan how to summarize a scope into a few high-level memories.

        Returns a clustering plan and a prompt you can act on immediately:
        store each cluster's summary with ``mnema_remember`` (importance=HIGH,
        tag 'summary'), then forget the originals with ``mnema_forget``.

        Mnema never calls an LLM on its own — the summarization is done by
        whichever AI invoked this tool.

        Args:
            scope: The scope to summarize, e.g. 'session:abc'.
            similarity_threshold: Tag-Jaccard threshold for grouping memories
                into clusters (0..1). Default 0.75.
            response_format: 'markdown' (default) renders a ready-to-use
                prompt; 'json' returns the structured plan.
        """
        plan = await service.summarize(
            scope=scope, similarity_threshold=similarity_threshold
        )
        if response_format == ResponseFormat.JSON:
            return to_json(plan)
        return build_summary_prompt(plan)
