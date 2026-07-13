# Roadmap

This document describes the planned direction for Mnema. It's intentionally
short and prioritized — the goal is to be honest about what's next, not to
promise everything.

Status legend: ✅ done · 🚧 in progress · 📋 planned · 💭 considering

---

## Phase 1 — Make it usable and lovable ✅ (mostly done)

The foundation works. The focus now is reducing friction so people can try
Mnema in 30 seconds and trust it enough to keep installed.

| | Item | Status |
|---|---|---|
| ✅ | Python MCP server (FastMCP) with 11 tools, 3 resources, 2 prompts | done |
| ✅ | Pluggable backends: Chroma (default), Qdrant, sqlite-vec | done |
| ✅ | Embedding providers: sentence-transformers (offline), OpenAI | done |
| ✅ | Hybrid search: vector similarity + tag overlap + decay scoring | done |
| ✅ | Summarization planner (LLM-free; the calling AI executes the plan) | done |
| ✅ | Multi-user / multi-session via scope-based namespaces | done |
| ✅ | Programmatic Python SDK (`MemoryClient` / `SyncMemoryClient`) | done |
| ✅ | One-line installer (`curl … \| bash`) + `mnema-update` | done |
| ✅ | Per-agent setup guides (Claude Desktop/Code, Cursor, Zed, Cline, Continue, Windsurf) | done |
| ✅ | `mnema` CLI for terminal use without an MCP client | done |
| ✅ | Import / export (`mnema export > memories.json`, `mnema import`) | done |
| 📋 | `mnema doctor --fix` that suggests concrete fixes | planned |
| 📋 | Auto-recall / auto-remember prompt hooks (improve `SKILL.md`) | planned |

## Phase 2 — Grow the ecosystem 📋

Once the core is loved by a small group, expand to more stacks and stores.

| | Item | Status |
|---|---|---|
| 📋 | **Web dashboard** — browse / search / forget memories in a browser | planned |
| 📋 | More backends: pgvector, LanceDB, Weaviate | planned |
| 📋 | More embedding providers: Ollama (local!), Cohere, Voyage, Nomic | planned |
| 📋 | TypeScript MCP server (`packages/mnema-ts/`) | planned |
| 📋 | Migration helper: re-embed all memories when switching embedding model | planned |

## Phase 3 — Production-grade 📋

For teams and organizations running Mnema as a shared service.

| | Item | Status |
|---|---|---|
| 📋 | Auth + multi-tenant enforcement (API keys, per-user scope hardening) | planned |
| 📋 | Observability: Prometheus metrics, structured logging | planned |
| 📋 | Backup / snapshot (S3, rsync) | planned |
| 📋 | Hardened streamable-HTTP transport (TLS, rate limits) | planned |

## Phase 4 — Differentiators 💭

The "wouldn't it be cool if" tier. Pursued only when Phase 1–2 validate demand.

| | Item | Status |
|---|---|---|
| 💭 | **Memory graph** — link memories and traverse relationships | considering |
| 💭 | **Smart forgetting** — optional LLM-assisted decay decisions | considering |
| 💭 | **Eval harness** — runnable version of `docs/evaluations.xml` measuring recall quality | considering |
| 💭 | **Benchmarks** vs Mem0, Zep, LangMem | considering |

---

## How to influence this roadmap

The best signal is real usage. If something here matters to you:

1. **Open an issue** describing your use case (not just the feature).
2. **Up-vote** existing issues with 👍.
3. **Open a PR** — `good first issue` items are scoped to be approachable.

We'd rather ship 3 features people use than 10 nobody does.

## What we explicitly are NOT doing (yet)

To keep Mnema focused, the following are intentionally out of scope until
there's clear demand:

- A hosted/managed cloud offering.
- Tight coupling to any single LLM vendor.
- Replacing a full RAG pipeline — Mnema is for *durable agent memory*, not
  document retrieval over large corpora.
