"""Tests for the eval harness (issue #15).

Uses the in-memory fakes so the tests are fast and don't load an embedding
model. The HashingEmbedding is token-based (not semantic), so recall won't
be 100% like the real model — but the harness mechanics are fully exercised.
"""

from __future__ import annotations

import pytest

from mnema.eval_dataset import EVAL_QUESTIONS, SEED_MEMORIES
from mnema.eval_harness import EvalReport, run_eval, seed_eval_memories

pytestmark = pytest.mark.asyncio


class TestEvalDataset:
    def test_seed_memories_nonempty(self):
        assert len(SEED_MEMORIES) >= 20

    def test_eval_questions_nonempty(self):
        assert len(EVAL_QUESTIONS) >= 15

    def test_every_question_has_expected_substring(self):
        for query, expected, _ in EVAL_QUESTIONS:
            assert expected, f"query {query!r} has empty expected"
            assert isinstance(expected, str)

    def test_every_seed_memory_well_formed(self):
        for text, scope, tags, importance in SEED_MEMORIES:
            assert text and scope
            assert isinstance(tags, list)
            assert 1 <= importance <= 10


class TestSeedEvalMemories:
    async def test_seed_inserts_all(self, service):
        n = await seed_eval_memories(service)
        assert n == len(SEED_MEMORIES)
        count = await service.backend.count()
        assert count == len(SEED_MEMORIES)


class TestRunEval:
    async def test_eval_returns_report(self, service):
        report = await run_eval(service, k=5)
        assert isinstance(report, EvalReport)
        assert report.total_queries == len(EVAL_QUESTIONS)
        assert report.memory_count == len(SEED_MEMORIES)
        assert report.k == 5
        assert len(report.hits) == len(EVAL_QUESTIONS)
        assert report.elapsed_seconds > 0

    async def test_eval_no_seed_counts_existing(self, service):
        """With seed=False, eval runs against whatever is in the store."""
        await service.remember("one memory")
        report = await run_eval(service, k=5, seed=False)
        assert report.memory_count == 1
        # Recall will be low (no expected matches), but shouldn't crash.
        assert report.recall_at_k >= 0.0

    async def test_eval_custom_k(self, service):
        report = await run_eval(service, k=3)
        assert report.k == 3

    async def test_report_summary_format(self, service):
        report = await run_eval(service, k=5)
        s = report.summary()
        assert "recall@5" in s
        assert "MRR" in s

    async def test_report_detail_includes_all_queries(self, service):
        report = await run_eval(service, k=5)
        d = report.detail()
        # Every query should appear in the detail.
        for query, _, _ in EVAL_QUESTIONS:
            assert query[:20] in d

    async def test_report_metrics_bounds(self, service):
        report = await run_eval(service, k=5)
        assert 0.0 <= report.recall_at_k <= 1.0
        assert 0.0 <= report.mrr <= 1.0
        assert 0.0 <= report.avg_score <= 1.0


class TestEvalReportProperties:
    def test_empty_report_metrics(self):
        """An empty report should have safe defaults."""
        report = EvalReport()
        assert report.recall_at_k == 0.0
        assert report.mrr == 0.0
        assert report.avg_score == 0.0
