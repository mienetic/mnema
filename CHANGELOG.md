# Changelog

All notable changes to Mnema are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- TypeScript MCP server (`packages/mnema-ts/`)
- Node CLI (`packages/mnema-cli/`)
- Evaluation harness (`docs/evaluations.xml`)
- Web dashboard

## [0.1.0] — 2026-07-13

### Added
- 🎉 Initial public release.
- **MCP server** (Python, FastMCP) with 10 tools:
  `mnema_remember`, `mnema_recall`, `mnema_search`, `mnema_get_memory`,
  `mnema_update_memory`, `mnema_forget`, `mnema_forget_scope`,
  `mnema_list_scopes`, `mnema_summarize`, `mnema_apply_decay`, `mnema_stats`.
- **3 vector backends**: Chroma (embedded, default), Qdrant (local/remote),
  sqlite-vec (pure-SQLite).
- **2 embedding providers**: sentence-transformers (offline, default),
  OpenAI (`text-embedding-3-*`).
- **Hybrid search** combining vector similarity, tag overlap, and a decay
  component (`recency × frequency × importance`).
- **Summarization planner** that clusters memories by tag overlap and
  produces a ready-to-use prompt (Mnema never calls an LLM on its own).
- **Multi-user / multi-session** support via scope-based namespaces.
- **Programmatic Python SDK** (`mnema.sdk.MemoryClient` /
  `SyncMemoryClient`) for using Mnema without MCP.
- **MCP resources** (`mnema://memory/{id}`, `mnema://scope/{s}/summary`,
  `mnema://stats`) and **prompt templates** (`summarize_scope`, `recall_for`).
- **SKILL.md** describing the agent-facing usage guide.
- Environment-driven configuration via `pydantic-settings`.
- Docker setup and client config examples (Claude Desktop, ZCode, Cursor).
- Test suite with in-memory fakes + a backend matrix that runs against
  every supported store.

[Unreleased]: https://github.com/your-org/mnema/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/mnema/releases/tag/v0.1.0
