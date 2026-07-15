"""Recall evaluation harness for Mnema.

Seeds a memory store with a curated dataset, then asks natural-language
queries and checks whether the expected answer appears in the top-k results.
Produces recall@k metrics that can be used to:

* prove Mnema works (e.g. in a blog post or README)
* guard against regressions when changing the embedding/search logic
* compare against other memory tools (issue #16)

Usage::

    from mnema.eval_harness import run_eval, EvalReport
    report = await run_eval(service, k=5)
    print(report.summary())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from mnema.eval_dataset import EVAL_QUESTIONS, SEED_MEMORIES
from mnema.service import MemoryService


@dataclass(frozen=True)
class EvalHit:
    """One query's outcome."""

    query: str
    expected: str
    found: bool
    rank: int | None  # 1-based rank of the first hit, None if not found
    score: float
    top_text: str


@dataclass
class EvalReport:
    """Aggregate results of an eval run."""

    hits: list[EvalHit] = field(default_factory=list)
    total_queries: int = 0
    k: int = 5
    elapsed_seconds: float = 0.0
    memory_count: int = 0

    @property
    def recall_at_k(self) -> float:
        """Fraction of queries where the expected answer was in the top-k."""
        if self.total_queries == 0:
            return 0.0
        return sum(1 for h in self.hits if h.found) / self.total_queries

    @property
    def mrr(self) -> float:
        """Mean Reciprocal Rank — 1/rank averaged over all queries."""
        if self.total_queries == 0:
            return 0.0
        return sum(
            (1.0 / h.rank if h.rank else 0.0) for h in self.hits
        ) / self.total_queries

    @property
    def avg_score(self) -> float:
        """Average score of the first hit across all queries."""
        scored = [h.score for h in self.hits if h.found]
        if not scored:
            return 0.0
        return sum(scored) / len(scored)

    def summary(self) -> str:
        """Human-readable one-liner."""
        return (
            f"recall@{self.k}: {self.recall_at_k:.1%} "
            f"({sum(1 for h in self.hits if h.found)}/{self.total_queries})  "
            f"MRR: {self.mrr:.3f}  "
            f"avg_score: {self.avg_score:.3f}  "
            f"({self.memory_count} memories, {self.elapsed_seconds:.2f}s)"
        )

    def detail(self) -> str:
        """Per-query breakdown."""
        lines = [self.summary(), ""]
        for i, h in enumerate(self.hits, 1):
            mark = "✓" if h.found else "✗"
            rank = f"#{h.rank}" if h.rank else "—"
            lines.append(
                f"{i:2d}. {mark} rank={rank:<3} score={h.score:.3f}  "
                f"Q: {h.query[:50]}"
            )
            lines.append(f"    want: {h.expected}")
            if h.found:
                lines.append(f"    got:  {h.top_text[:60]}")
            lines.append("")
        return "\n".join(lines)


async def seed_eval_memories(service: MemoryService) -> int:
    """Seed the store with the eval dataset. Returns the count inserted."""
    n = 0
    for text, scope, tags, importance in SEED_MEMORIES:
        await service.remember(text, scope=scope, tags=tags, importance=importance)
        n += 1
    return n


async def run_eval(
    service: MemoryService,
    *,
    k: int = 5,
    seed: bool = True,
) -> EvalReport:
    """Run the recall evaluation against ``service``.

    Args:
        service: A MemoryService instance (use a fresh/empty store for
            accurate results, or ``seed=False`` to eval an existing store).
        k: The cutoff for recall@k (default 5).
        seed: When True, seed the dataset first (clear the store externally
            if you want a clean run).

    Returns:
        An :class:`EvalReport` with per-query hits and aggregate metrics.
    """
    memory_count = 0
    if seed:
        memory_count = await seed_eval_memories(service)
    else:
        memory_count = await service.backend.count()

    report = EvalReport(k=k, memory_count=memory_count)
    start = time.time()

    for query, expected, tags in EVAL_QUESTIONS:
        response = await service.search(query, tags=tags or None, limit=k)
        hits = response.results
        found = False
        rank = None
        score = 0.0
        top_text = ""
        for i, hit in enumerate(hits, 1):
            if expected.lower() in hit.memory.text.lower():
                found = True
                rank = i
                score = hit.score
                top_text = hit.memory.text
                break
        if not found and hits:
            score = hits[0].score
            top_text = hits[0].memory.text
        report.hits.append(
            EvalHit(
                query=query,
                expected=expected,
                found=found,
                rank=rank,
                score=score,
                top_text=top_text,
            )
        )
        report.total_queries += 1

    report.elapsed_seconds = time.time() - start
    return report


__all__ = ["EvalHit", "EvalReport", "run_eval", "seed_eval_memories"]
