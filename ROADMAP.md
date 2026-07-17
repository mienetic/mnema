# Roadmap

This document describes the planned direction for Mnema. It's intentionally
short and prioritized — the goal is to be honest about what's next, not to
promise everything.

Status legend: ✅ done · 🚧 in progress · 📋 planned · 💭 considering

---

## Phase 1 — Make it usable and lovable ✅ done

The foundation is complete and tested end-to-end. Mnema installs in one line,
runs as an MCP server or a CLI, and gives agents durable, searchable memory.

| | Item | Status |
|---|---|---|
| ✅ | Python MCP server (FastMCP) with 11 tools, 3 resources, 3 prompts | done |
| ✅ | Pluggable backends: Chroma (default), Qdrant, sqlite-vec | done |
| ✅ | Embedding providers: sentence-transformers (offline), OpenAI, Ollama | done |
| ✅ | Hybrid search: vector similarity + tag overlap + decay scoring | done |
| ✅ | Summarization planner (LLM-free; the calling AI executes the plan) | done |
| ✅ | Multi-user / multi-session via scope-based namespaces | done |
| ✅ | Programmatic Python SDK (`MemoryClient` / `SyncMemoryClient`) | done |
| ✅ | `mnema` CLI for terminal use without an MCP client (15 subcommands) | done |
| ✅ | Import / export (`mnema export`, `mnema import`) | done |
| ✅ | `mnema re-embed` — migrate memories when switching embedding model | done |
| ✅ | `mnema --doctor --fix` — auto-remediate common setup problems | done |
| ✅ | Auto-recall / auto-remember prompt hooks (`SKILL.md` + `remember_this`) | done |
| ✅ | `mnema backup` / `mnema restore` — portable snapshots | done |
| ✅ | `mnema eval` — recall evaluation harness (recall@5 = 100%, MRR = 1.0) | done |
| ✅ | 🌙 Auto Dream — background memory consolidation (`MNEMA_DREAM_ENABLED=true`) | done |
| ✅ | One-line installer (`curl … \| bash`) + `mnema-update` | done |
| ✅ | Per-agent setup guides (Claude Desktop/Code, Cursor, Zed, Cline, Continue, Windsurf, ZCode) | done |
| ✅ | End-to-end tested (86 tests + manual CLI/MCP smoke test) | done |

## Phase 2 — Grow the ecosystem 📋 (starting)

Now that the core works and has its first contributors, expand to more stacks
and stores.

| | Item | Status |
|---|---|---|
| 🚧 | More backends: pgvector, LanceDB, Weaviate | pgvector claimed by @Adiiiipawar, LanceDB by @Oneshot1123 |
| 🚧 | More embedding providers: Cohere, Voyage, Nomic | claimed by @jaineel132 |
| 🚧 | **Web dashboard** — browse / search / forget memories in a browser | claimed by @NEMEZIZ1234 |
| ✅ | **REST API (non-MCP)** — `GET /memories`, `POST /search`, … via FastAPI (`mnema serve`) | done by @Nitjsefnie (#22) |
| 📋 | **Slack / Discord bot** — auto-remember facts from chat (`packages/mnema-bot/`) | planned |
| 📋 | **Browser extension** — capture facts from web pages into Mnema | planned (depends on REST API) |
| 📋 | TypeScript MCP server (`packages/mnema-ts/`) | planned (waiting for demand) |
| 📋 | Submit to the [MCP server registry](https://github.com/modelcontextprotocol/servers) | planned (maintainer task) |

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
