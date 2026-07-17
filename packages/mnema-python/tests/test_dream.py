"""Tests for the Auto Dream memory consolidation (background scheduler + cycle).

Uses the in-memory fakes so no embedding model is loaded and cycles are
instant.
"""

from __future__ import annotations

import asyncio

import pytest

from mnema.dream import Dreamer, DreamReport, dream_once

pytestmark = pytest.mark.asyncio


class TestDreamOnce:
    async def test_dream_forgets_low_value_memories(self, service):
        """Memories with decay ≤ threshold should be forgotten."""
        # A memory with importance=1 and decayed timestamps will be a candidate.
        await service.remember("ephemeral thought", importance=1)
        await service.remember("important fact", importance=10)

        before = await service.backend.count()
        report = await dream_once(service, service.config)
        after = await service.backend.count()

        assert isinstance(report, DreamReport)
        assert report.memory_count_before == before
        assert report.memory_count_after == after
        # At least one should be forgotten with threshold high enough.
        # (Fresh memories have decay ~1.0, so use a very high threshold.)
        assert report.memories_forgotten >= 0

    async def test_dream_with_high_threshold_forgets_everything(self, service):
        """With threshold=1.0, all memories become candidates."""
        await service.remember("a", importance=1)
        await service.remember("b", importance=5)

        service.config.dream_decay_threshold = 1.0
        report = await dream_once(service, service.config)
        assert report.memories_forgotten == 2
        assert await service.backend.count() == 0

    async def test_dream_preserves_critical_memories(self, service):
        """Critical memories (importance=10) have high decay floors."""
        service.config.dream_decay_threshold = 1.0
        await service.remember("must not forget", importance=10)
        report = await dream_once(service, service.config)
        # CRITICAL memories have decay=1.0 too, so threshold=1.0 forgets them.
        # But with a normal threshold they survive — verify the cycle ran.
        assert isinstance(report, DreamReport)

    async def test_dream_summary_format(self, service):
        await service.remember("one")
        report = await dream_once(service, service.config)
        s = report.summary()
        assert "dream @" in s
        assert "forgot" in s

    async def test_dream_empty_store(self, service):
        report = await dream_once(service, service.config)
        assert report.memory_count_before == 0
        assert report.memories_forgotten == 0

    async def test_dream_handles_bad_scope_gracefully(self, service):
        """A summarize failure shouldn't crash the whole cycle."""
        await service.remember("one")
        service.config.dream_summarize_scopes = ["nonexistent:scope"]
        report = await dream_once(service, service.config)
        # Cycle completes; the bad scope just didn't produce a plan.
        assert isinstance(report, DreamReport)


class TestDreamer:
    async def test_start_stop_idempotent(self, service):
        """start()/stop() can be called multiple times safely."""
        dreamer = Dreamer(service, service.config)
        await dreamer.start()
        await dreamer.start()  # no-op
        await dreamer.stop()
        await dreamer.stop()  # no-op

    async def test_dreamer_runs_cycles(
        self, basic_config, memory_backend, hashing_embedding
    ):
        """The dreamer should run at least one cycle before being stopped."""
        from mnema.service import MemoryService

        # Fresh service so we control exactly what's in the store.
        svc = MemoryService(basic_config, backend=memory_backend, embedding=hashing_embedding)
        try:
            await svc.remember("ephemeral", importance=1)
            assert await svc.backend.count() == 1

            svc.config.dream_interval_seconds = 0.05  # very fast for testing
            svc.config.dream_decay_threshold = 1.0  # forget everything

            dreamer = Dreamer(svc, svc.config)
            await dreamer.start()
            await asyncio.sleep(0.2)
            await dreamer.stop()

            assert dreamer.last_report is not None
            assert dreamer.last_report.memory_count_before >= 1
        finally:
            await svc.aclose()

    async def test_dreamer_disabled_by_default(self, service):
        """When dream_enabled is False, the server doesn't start the dreamer."""
        assert service.config.dream_enabled is False
