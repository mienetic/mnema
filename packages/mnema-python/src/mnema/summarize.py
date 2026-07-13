"""Summarization planner — turn many memories into a few high-level ones.

Mnema is *deliberately* LLM-free by default. Rather than calling an LLM API
itself (which would create a circular dependency, cost money, and require a
key), the server plans the summarization and hands the work to whichever
client invoked the tool. The client (Claude, ZCode, Cursor, …) is an LLM, so
it can do the actual writing.

Two entry points:

* :func:`plan_summarization` — cluster memories, pick representatives, return
  a plan the client can execute (no LLM call).
* :func:`build_summary_prompt` — render the plan into a ready-to-use prompt.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from mnema.models import MemoryRecord


@dataclass(frozen=True)
class SummarizationPlan:
    """A plan describing how a scope's memories could be condensed."""

    scope: str
    clusters: list[MemoryCluster]
    candidates_to_forget: list[str]
    total_memories: int


@dataclass(frozen=True)
class MemoryCluster:
    """A group of memories that look topically similar."""

    representative_id: str
    member_ids: list[str]
    preview: str


def plan_summarization(
    memories: Sequence[MemoryRecord],
    *,
    scope: str,
    similarity_threshold: float = 0.75,
    max_cluster_size: int = 12,
) -> SummarizationPlan:
    """Cluster memories by tag overlap into a summarization plan.

    This is a lightweight greedy tag-based clustering — no embeddings needed.
    It groups memories that share most of their tags, picks the most-accessed
    member as the representative, and flags the rest as candidates to forget
    once they've been rolled into a summary.

    Args:
        memories: All memories in a scope (sorted however the caller likes).
        scope: The scope these memories belong to.
        similarity_threshold: Jaccard threshold for "same cluster".
        max_cluster_size: Don't let a single cluster grow beyond this.
    """
    items = list(memories)
    used: set[str] = set()
    clusters: list[MemoryCluster] = []

    # Sort by access_count desc so the representative is the most "tested".
    items.sort(key=lambda m: m.access_count, reverse=True)

    for anchor in items:
        if anchor.id in used:
            continue
        anchor_tags = {t.lower() for t in anchor.tags}
        members: list[MemoryRecord] = [anchor]
        used.add(anchor.id)

        for other in items:
            if other.id in used or len(members) >= max_cluster_size:
                continue
            if not anchor_tags and not other.tags:
                # No tags to compare; skip to avoid over-merging.
                continue
            other_tags = {t.lower() for t in other.tags}
            union = anchor_tags | other_tags
            if not union:
                continue
            sim = len(anchor_tags & other_tags) / len(union)
            if sim >= similarity_threshold:
                members.append(other)
                used.add(other.id)

        preview = anchor.text[:160].replace("\n", " ")
        if len(anchor.text) > 160:
            preview += "…"
        clusters.append(
            MemoryCluster(
                representative_id=anchor.id,
                member_ids=[m.id for m in members],
                preview=preview,
            )
        )

    candidates = [m.id for m in items if m.id not in used]
    return SummarizationPlan(
        scope=scope,
        clusters=clusters,
        candidates_to_forget=candidates,
        total_memories=len(items),
    )


def build_summary_prompt(plan: SummarizationPlan) -> str:
    """Render a plan into a prompt the client LLM can execute.

    The returned string is meant to be returned from the
    ``mnema_summarize`` MCP tool so the AI that called it writes the summary.
    """
    lines = [
        f"# Summarize memories in scope '{plan.scope}'",
        "",
        f"You are about to consolidate {plan.total_memories} memories into "
        f"{len(plan.clusters)} higher-level summary memories.",
        "",
        "For each cluster below, write ONE concise summary memory that "
        "preserves the key facts. After you've stored the summaries with "
        "`mnema_remember`, you may forget the originals with `mnema_forget`.",
        "",
    ]
    for i, cluster in enumerate(plan.clusters, 1):
        lines.append(f"## Cluster {i} ({len(cluster.member_ids)} memories)")
        lines.append(f"Representative: {cluster.representative_id}")
        lines.append(f"> {cluster.preview}")
        lines.append(f"Members: {', '.join(cluster.member_ids)}")
        lines.append("")
    if plan.candidates_to_forget:
        lines.append("## Other candidates to forget after summarizing")
        lines.append(", ".join(plan.candidates_to_forget))
        lines.append("")
    lines.append(
        "Suggested tags for each new summary memory: `summary`, plus the "
        "scope's dominant topic tag. Use importance=HIGH (8)."
    )
    return "\n".join(lines)


__all__ = [
    "MemoryCluster",
    "SummarizationPlan",
    "build_summary_prompt",
    "plan_summarization",
]
