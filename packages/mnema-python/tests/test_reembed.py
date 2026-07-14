"""Tests for the re-embed migration (issue #9).

Verifies that ``MemoryService.reembed()`` re-embeds every memory with the
currently bound provider and writes the new vectors back. Uses the in-memory
fakes so no embedding model is loaded.
"""

from __future__ import annotations

import argparse
import io
from contextlib import redirect_stdout

import pytest

from mnema.cli import cmd_reembed
from tests.fakes import HashingEmbedding

pytestmark = pytest.mark.asyncio


@pytest.fixture
def two_embeddings() -> tuple[HashingEmbedding, HashingEmbedding]:
    """Return (old_provider, new_provider) with different dims."""
    return HashingEmbedding(dim=64), HashingEmbedding(dim=128)


class TestReembed:
    async def test_reembed_updates_all_memories(
        self, basic_config, memory_backend, hashing_embedding
    ):
        """reembed() should call update() on every memory with a new vector."""
        from mnema.service import MemoryService

        svc = MemoryService(basic_config, backend=memory_backend, embedding=hashing_embedding)
        try:
            await svc.remember("first memory", scope="user:a")
            await svc.remember("second memory", scope="user:b")
            await svc.remember("third memory", scope="user:a")

            original_vectors = dict(memory_backend._store)  # id -> (record, vec)
            n = await svc.reembed()

            assert n == 3
            for mid in original_vectors:
                new_vec = memory_backend._store[mid][1]
                assert len(new_vec) == hashing_embedding.dim
        finally:
            await svc.aclose()

    async def test_reembed_empty_store_returns_zero(
        self, basic_config, memory_backend, hashing_embedding
    ):
        from mnema.service import MemoryService

        svc = MemoryService(basic_config, backend=memory_backend, embedding=hashing_embedding)
        try:
            n = await svc.reembed()
            assert n == 0
        finally:
            await svc.aclose()

    async def test_reembed_scope_restricted(
        self, basic_config, memory_backend, hashing_embedding
    ):
        from mnema.service import MemoryService

        svc = MemoryService(basic_config, backend=memory_backend, embedding=hashing_embedding)
        try:
            await svc.remember("a1", scope="user:a")
            await svc.remember("a2", scope="user:a")
            await svc.remember("b1", scope="user:b")

            n = await svc.reembed(scope="user:a")
            assert n == 2
        finally:
            await svc.aclose()

    async def test_reembed_progress_callback(
        self, basic_config, memory_backend, hashing_embedding
    ):
        from mnema.service import MemoryService

        svc = MemoryService(basic_config, backend=memory_backend, embedding=hashing_embedding)
        try:
            await svc.remember("one")
            await svc.remember("two")
            await svc.remember("three")

            calls: list[tuple[int, int]] = []
            await svc.reembed(on_progress=lambda done, total: calls.append((done, total)))

            # Should report progress for each memory.
            assert len(calls) == 3
            assert calls[-1] == (3, 3)
        finally:
            await svc.aclose()

    async def test_reembed_with_changed_dimension(
        self, basic_config, memory_backend
    ):
        """Simulate switching from dim=64 to dim=128 by swapping the provider."""
        from mnema.service import MemoryService

        old = HashingEmbedding(dim=64)
        svc = MemoryService(basic_config, backend=memory_backend, embedding=old)
        try:
            await svc.remember("alpha")
            await svc.remember("beta")

            # Swap to a provider with a different dimension.
            new = HashingEmbedding(dim=128)
            svc._embedding = new

            n = await svc.reembed()
            assert n == 2
            # New vectors should have the new dimension.
            for _id, (_rec, vec) in memory_backend._store.items():
                assert len(vec) == 128
        finally:
            await svc.aclose()


class TestReembedCLI:
    async def test_reembed_cli_handler(self, service):
        """The CLI handler prints progress and a final count."""
        await service.remember("hello")
        await service.remember("world")

        args = argparse.Namespace(scope=None, batch_size=50)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_reembed(args, service)
        assert code == 0
        out = buf.getvalue()
        assert "re-embedded" in out
        assert "2 memories" in out

    async def test_reembed_cli_empty(self, service):
        args = argparse.Namespace(scope=None, batch_size=50)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_reembed(args, service)
        assert code == 0
        assert "No memories" in buf.getvalue()
