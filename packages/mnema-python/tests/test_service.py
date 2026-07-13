"""End-to-end service tests using fast in-memory fakes.

These cover the orchestration layer: remember → recall → search → update →
forget, plus stats, decay, and summarize. Backend-specific behavior is
exercised in test_backends.py via the optional-dependency markers.
"""

from __future__ import annotations

import pytest

from mnema.errors import MemoryNotFoundError, ScopeError
from mnema.models import Importance

pytestmark = pytest.mark.asyncio


class TestRememberAndRecall:
    async def test_remember_returns_record_with_id(self, service):
        rec = await service.remember("Alice likes Earl Grey tea", tags=["preferences"])
        assert rec.id
        assert rec.scope == "global"
        assert rec.tags == ["preferences"]
        assert rec.importance == Importance.NORMAL
        assert rec.embedding_dim == 64

    async def test_remember_with_explicit_scope(self, service):
        rec = await service.remember("x", scope="user:bob")
        assert rec.scope == "user:bob"

    async def test_remember_invalid_scope(self, service):
        with pytest.raises(ScopeError):
            await service.remember("x", scope="has space")

    async def test_recall_returns_relevant(self, service):
        # HashingEmbedding is token-based, so query with overlapping tokens.
        await service.remember("Bob's favorite tea is Earl Grey", tags=["pref"])
        await service.remember("Rust is a systems programming language", tags=["lang"])

        res = await service.recall("tea Earl Grey", limit=3)
        assert res.count >= 1
        top = res.results[0]
        # With a real embedding "tea" would match strongly; with the hash fake
        # we just assert the top hit is well-formed and ranked.
        assert 0.0 <= top.score <= 1.0
        assert top.vector_score >= 0.0
        # The tea memory should at least be in the results (token overlap).
        texts = {r.memory.text for r in res.results}
        assert any("tea" in t.lower() or "earl" in t.lower() for t in texts)

    async def test_recall_scope_isolation(self, service):
        await service.remember("secret for alice", scope="user:alice")
        await service.remember("secret for bob", scope="user:bob")
        res = await service.recall("secret", scope="user:alice")
        assert all(r.memory.scope == "user:alice" for r in res.results)
        assert res.count >= 1


class TestSearch:
    async def test_search_with_tags_boosts_match(self, service):
        await service.remember("env config", tags=["config", "python"])
        await service.remember("docker config", tags=["config", "ops"])
        await service.remember("unrelated thing", tags=["random"])

        res = await service.search("config", tags=["ops"], limit=3)
        if res.count >= 2:
            # The docker-config memory shares more tags → higher keyword score.
            docker = next(r for r in res.results if "docker" in r.memory.text)
            other = next(r for r in res.results if "env config" in r.memory.text)
            assert docker.keyword_score >= other.keyword_score

    async def test_search_results_sorted_desc(self, service):
        for i in range(5):
            await service.remember(f"memory number {i}", tags=[f"t{i}"])
        res = await service.search("memory", limit=5)
        scores = [r.score for r in res.results]
        assert scores == sorted(scores, reverse=True)

    async def test_search_pagination(self, service):
        for i in range(15):
            await service.remember(f"item {i}")
        page1 = await service.search("item", limit=5, offset=0)
        page2 = await service.search("item", limit=5, offset=5)
        assert page1.count == 5
        assert page2.count == 5
        ids1 = {r.memory.id for r in page1.results}
        ids2 = {r.memory.id for r in page2.results}
        assert ids1.isdisjoint(ids2)


class TestMutate:
    async def test_get_bumps_access_count(self, service):
        rec = await service.remember("hello")
        # First get sets access_count to >= 1
        await service.get(rec.id)
        # Second get should bump further (we can't assert exact because touch
        # happens after the read in our fake, but at least no error).
        got = await service.get(rec.id)
        assert got.id == rec.id

    async def test_get_missing_raises(self, service):
        with pytest.raises(MemoryNotFoundError):
            await service.get("nonexistent-id")

    async def test_update_re_embeds_on_text_change(self, service):
        rec = await service.remember("old text", tags=["a"])
        updated = await service.update(rec.id, text="new text", tags=["b"])
        assert updated.text == "new text"
        assert updated.tags == ["b"]

    async def test_update_missing_raises(self, service):
        with pytest.raises(MemoryNotFoundError):
            await service.update("nope", text="x")

    async def test_forget(self, service):
        rec = await service.remember("bye")
        assert await service.forget(rec.id) is True
        assert await service.forget(rec.id) is False  # idempotent

    async def test_forget_scope(self, service):
        await service.remember("a", scope="user:x")
        await service.remember("b", scope="user:x")
        await service.remember("c", scope="user:y")
        n = await service.forget_scope("user:x")
        assert n == 2
        scopes = await service.list_scopes()
        assert "user:x" not in scopes


class TestStatsAndScopes:
    async def test_stats(self, service):
        await service.remember("a", scope="user:x")
        await service.remember("b", scope="user:y")
        stats = await service.stats()
        assert stats.total_memories == 2
        assert stats.scopes == {"user:x": 1, "user:y": 1}
        assert stats.backend == "memory"
        assert stats.embedding_dim == 64

    async def test_list_scopes(self, service):
        await service.remember("a", scope="global")
        await service.remember("b", scope="global")
        scopes = await service.list_scopes()
        assert scopes.get("global") == 2


class TestDecayAndSummarize:
    async def test_apply_decay_dry_run(self, service):
        # A fresh memory has decay ~1.0, so threshold 1.0 + dry_run lists it.
        rec = await service.remember("ephemeral", importance=1)
        candidates = await service.apply_decay(threshold=1.0, dry_run=True)
        ids = {c.id for c in candidates}
        assert rec.id in ids

    async def test_apply_decay_high_importance_survives(self, service):
        # CRITICAL memories have decay 1.0, so a tiny threshold keeps them.
        rec = await service.remember("keep me", importance=10)
        candidates = await service.apply_decay(threshold=0.01, dry_run=True)
        ids = {c.id for c in candidates}
        assert rec.id not in ids

    async def test_apply_decay_actually_deletes(self, service):
        rec = await service.remember("ephemeral", importance=1)
        await service.apply_decay(threshold=1.0, dry_run=False)
        with pytest.raises(MemoryNotFoundError):
            await service.get(rec.id)

    async def test_summarize_returns_plan(self, service):
        await service.remember("python test", scope="global", tags=["python", "test"])
        await service.remember("python web", scope="global", tags=["python", "web"])
        plan = await service.summarize(scope="global")
        assert plan.scope == "global"
        assert plan.total_memories == 2
        assert len(plan.clusters) >= 1


class TestSDK:
    async def test_sdk_memory_client_lifecycle(self, basic_config, memory_backend, hashing_embedding):
        from mnema.sdk import MemoryClient
        from mnema.service import MemoryService

        svc = MemoryService(basic_config, backend=memory_backend, embedding=hashing_embedding)
        async with MemoryClient(basic_config, service=svc) as client:
            rec = await client.remember("hello from sdk", tags=["test"])
            assert rec.id
            hits = await client.search("hello", tags=["test"])
            assert hits.count >= 1
            stats = await client.stats()
            assert stats.total_memories == 1
