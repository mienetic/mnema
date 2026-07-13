#!/usr/bin/env python3
"""Demo: seed Mnema with a few memories, then search them.

Run after installing Mnema (e.g. via the one-line installer — see README) —
exercises the programmatic SDK without needing an MCP client.

    python examples/demo_memories.py
"""

from __future__ import annotations

import asyncio

from mnema.sdk import MemoryClient


async def main() -> None:
    async with MemoryClient() as client:
        # 1. Seed some durable memories.
        await client.remember(
            "Alice prefers Earl Grey tea and avoids coffee after 2pm.",
            scope="user:alice",
            tags=["preferences", "food"],
            importance=8,
        )
        await client.remember(
            "The web project deploys to fly.io in the sin region.",
            scope="project:web",
            tags=["deploy", "infra"],
            importance=8,
        )
        await client.remember(
            "Bob's timezone is Asia/Bangkok (ICT, UTC+7).",
            scope="user:bob",
            tags=["timezone"],
            importance=5,
        )

        # 2. Semantic recall — different words, same meaning.
        print("=== recall: 'what does Alice like to drink?' ===")
        hits = await client.recall("what does Alice like to drink?", scope="user:alice")
        for h in hits.results:
            print(f"  [{h.score:.3f}] {h.memory.text}")

        # 3. Hybrid search with tag filtering.
        print("\n=== search: 'infrastructure' tags=['deploy'] ===")
        hits = await client.search("infrastructure", tags=["deploy"])
        for h in hits.results:
            print(f"  [{h.score:.3f}] {h.memory.text}  tags={h.memory.tags}")

        # 4. Stats.
        print("\n=== stats ===")
        stats = await client.stats()
        print(f"  total={stats.total_memories} scopes={stats.scopes}")


if __name__ == "__main__":
    asyncio.run(main())
