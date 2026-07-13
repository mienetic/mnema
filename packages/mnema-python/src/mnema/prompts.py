"""MCP prompt templates — canned, parameterized prompts the client can fill.

These are exposed alongside tools so AI clients get a ready-made workflow for
memory consolidation without having to invent the prompt themselves.
"""

from __future__ import annotations

from mnema.service import MemoryService
from mnema.summarize import build_summary_prompt


def register_prompts(mcp, service: MemoryService) -> None:
    """Register Mnema prompt templates."""

    @mcp.prompt()
    def summarize_scope(scope: str) -> str:
        """Plan and execute a memory-summarization workflow for a scope.

        Args:
            scope: The scope to summarize.
        """
        # The body is a static instruction — the actual plan is fetched via
        # the mnema_summarize tool. This keeps prompts cheap and side-effect-free.
        return (
            f"Summarize the memories in scope '{scope}'.\n\n"
            "Steps:\n"
            "1. Call `mnema_summarize` with this scope to get the plan.\n"
            "2. For each cluster, write ONE concise summary memory and store "
            "it with `mnema_remember` (importance=HIGH, tags=['summary', ...]).\n"
            "3. After confirming the summaries are stored, forget the original "
            "members with `mnema_forget`.\n"
            "4. Report the before/after memory count using `mnema_stats`.\n"
        )

    @mcp.prompt()
    def recall_for(query: str, scope: str = "") -> str:
        """Recall relevant context for a new user message.

        Args:
            query: The user's latest message or topic.
            scope: Optional scope to restrict the recall to.
        """
        scope_clause = f" with scope='{scope}'" if scope else ""
        return (
            f"Before answering, recall relevant context for: {query!r}"
            f"{scope_clause}.\n"
            "1. Call `mnema_search` (or `mnema_recall`) to find related memories.\n"
            "2. Summarize what you found into 1–3 bullet points.\n"
            "3. Answer the user, citing any important recalled facts by id.\n"
            "4. When the user shares a durable new fact, store it with "
            "`mnema_remember`.\n"
        )


# Re-export for users who want the raw prompt builder.
_ = build_summary_prompt

__all__ = ["register_prompts"]
