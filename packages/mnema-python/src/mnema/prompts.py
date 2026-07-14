"""MCP prompt templates — canned, parameterized prompts the client can fill.

These are exposed alongside tools so AI clients get a ready-made workflow for
memory consolidation without having to invent the prompt themselves.

The two most important workflows are auto-recall (before answering) and
auto-remember (when a durable fact appears). The SKILL.md guide tells agents
to use these proactively.
"""

from __future__ import annotations

from mnema.service import MemoryService
from mnema.summarize import build_summary_prompt


def register_prompts(mcp, service: MemoryService) -> None:
    """Register Mnema prompt templates."""

    @mcp.prompt()
    def recall_for(query: str, scope: str = "") -> str:
        """Recall relevant context for a new user message.

        Call this at the start of a task to pull in related memories before
        answering. This is the core of Mnema's "auto-recall" workflow.

        Args:
            query: The user's latest message or topic.
            scope: Optional scope to restrict the recall to.
        """
        scope_clause = f" with scope='{scope}'" if scope else ""
        return (
            f"Before answering, recall relevant context for: {query!r}"
            f"{scope_clause}.\n\n"
            "Steps:\n"
            "1. Call `mnema_search` (or `mnema_recall`) to find related memories.\n"
            "2. If you find relevant context, summarize it in 1–3 bullets and weave "
            "it into your answer.\n"
            "3. If nothing relevant is found, proceed normally — don't force a "
            "memory connection that isn't there.\n"
            "4. If the user shares a durable new fact during the conversation, "
            "store it with `mnema_remember`.\n"
        )

    @mcp.prompt()
    def remember_this(fact: str, scope: str = "") -> str:
        """Store a durable fact the user just shared.

        Use this whenever a durable fact, preference, or decision appears in
        the conversation. This is the core of Mnema's "auto-remember" workflow.

        Args:
            fact: The fact to remember, phrased so future-you will understand
                it without the surrounding conversation.
            scope: Optional namespace (e.g. 'user:alice', 'project:web').
        """
        scope_clause = f" with scope='{scope}'" if scope else ""
        return (
            f"The user shared a durable fact worth remembering{scope_clause}:\n\n"
            f"  {fact}\n\n"
            "Store it now:\n"
            "1. Call `mnema_remember` with the fact above.\n"
            "2. Choose good tags — think about how future-you might search for "
            "this (e.g. 'preference', 'decision', 'config', 'person').\n"
            "3. Set importance: 8–10 for must-not-forget facts (account IDs, "
            "security decisions), 5 for normal context, 1–3 for nice-to-have.\n"
            "4. Confirm to the user that you've remembered it, briefly.\n"
        )

    @mcp.prompt()
    def summarize_scope(scope: str) -> str:
        """Plan and execute a memory-summarization workflow for a scope.

        Args:
            scope: The scope to summarize.
        """
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


# Re-export for users who want the raw prompt builder.
_ = build_summary_prompt

__all__ = ["register_prompts"]
