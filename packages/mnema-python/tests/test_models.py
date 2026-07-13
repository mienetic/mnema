"""Unit tests for pure functions: models, decay, summarize, scope."""

from __future__ import annotations

import time

import pytest

from mnema.decay import DecayParams, combine, decay_score
from mnema.models import Importance, Memory, MemoryRecord, Scope


class TestScope:
    def test_kind_ident_split(self):
        s = Scope(value="user:alice")
        assert s.kind == "user"
        assert s.ident == "alice"

    def test_no_colon_whole_string(self):
        s = Scope(value="global")
        assert s.kind == "global"
        assert s.ident == ""

    def test_rejects_whitespace(self):
        with pytest.raises(Exception):
            Scope(value="user: alice")
        with pytest.raises(Exception):
            Scope(value="")

    def test_frozen(self):
        s = Scope(value="user:alice")
        with pytest.raises(Exception):
            s.value = "user:bob"  # type: ignore[misc]


class TestImportance:
    def test_ordering(self):
        assert Importance.LOW < Importance.NORMAL < Importance.HIGH < Importance.CRITICAL

    def test_int_values(self):
        assert int(Importance.CRITICAL) == 10
        assert int(Importance.LOW) == 1


class TestMemoryRecord:
    def test_defaults(self):
        m = MemoryRecord(text="hi", embedding_dim=64)
        assert m.scope == "global"
        assert m.tags == []
        assert m.importance == Importance.NORMAL
        assert m.access_count == 0
        assert m.score is None
        assert len(m.id) == 32  # uuid hex

    def test_text_max_length(self):
        with pytest.raises(Exception):
            MemoryRecord(text="x" * 100_000, embedding_dim=64)


class TestDecay:
    def test_recent_memory_high_score(self):
        now = time.time()
        score = decay_score(
            created_at=now,
            last_accessed_at=now,
            access_count=0,
            importance=5,
            params=DecayParams(),
            now=now,
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.9  # brand new

    def test_old_memory_decays_toward_floor(self):
        now = time.time()
        old = now - 365 * 86400  # 1 year old
        score = decay_score(
            created_at=old,
            last_accessed_at=old,
            access_count=0,
            importance=1,
            params=DecayParams(half_life_days=30, floor=0.05),
            now=now,
        )
        assert score <= 0.1
        assert score >= 0.05  # floor protects it

    def test_importance_resists_decay(self):
        now = time.time()
        old = now - 365 * 86400
        low = decay_score(
            created_at=old, last_accessed_at=old, access_count=0,
            importance=1, params=DecayParams(), now=now,
        )
        crit = decay_score(
            created_at=old, last_accessed_at=old, access_count=0,
            importance=10, params=DecayParams(), now=now,
        )
        assert crit > low

    def test_frequency_boost(self):
        now = time.time()
        fresh = decay_score(
            created_at=now, last_accessed_at=now, access_count=0,
            importance=5, params=DecayParams(), now=now,
        )
        popular = decay_score(
            created_at=now, last_accessed_at=now, access_count=50,
            importance=5, params=DecayParams(), now=now,
        )
        assert popular >= fresh

    def test_combine_weights(self):
        s = combine(
            vector_score=1.0, keyword_score=0.0, decay=0.0,
            vector_weight=0.7, keyword_weight=0.2, decay_weight=0.1,
        )
        assert abs(s - 0.7) < 1e-9

    def test_combine_clamps(self):
        s = combine(
            vector_score=2.0, keyword_score=2.0, decay=2.0,
            vector_weight=1.0, keyword_weight=1.0, decay_weight=1.0,
        )
        assert s == 1.0


class TestSummarizePlan:
    def test_clusters_by_tag_overlap(self):
        from mnema.summarize import plan_summarization

        records = [
            MemoryRecord(
                text=f"m{i}",
                tags=tags,
                embedding_dim=64,
                access_count=i,
            )
            for i, tags in enumerate(
                [["python", "test"], ["python", "test"], ["rust"], ["rust", "wasm"]]
            )
        ]
        plan = plan_summarization(records, scope="global", similarity_threshold=0.5)
        # Two natural clusters: python+python, rust+rust
        assert len(plan.clusters) >= 2
        assert plan.total_memories == 4

    def test_build_summary_prompt_contains_scope(self):
        from mnema.summarize import SummarizationPlan, build_summary_prompt

        plan = SummarizationPlan(scope="user:alice", clusters=[], candidates_to_forget=[], total_memories=0)
        prompt = build_summary_prompt(plan)
        assert "user:alice" in prompt


class TestModelsSerialization:
    def test_memory_roundtrip(self):
        m = Memory(text="hello", scope="user:x", tags=["a"], importance=Importance.HIGH)
        d = m.model_dump()
        assert d["text"] == "hello"
        assert d["importance"] == 8
