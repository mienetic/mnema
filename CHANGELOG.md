# Changelog

All notable changes to Mnema are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`mnema` CLI** — full terminal interface that reuses `MemoryService`, so it
  behaves identically to an MCP-connected client. Subcommands: `add`,
  `recall`, `search`, `get`, `update`, `forget`, `forget-scope`, `list-scopes`,
  `stats`, `decay`, `summarize`, `export`, `import` (with aliases like
  `remember`, `delete`, `scopes`). `--json` output on every read command.
- **`mnema re-embed`** — re-embed all memories with the currently configured
  embedding provider, for migrating after switching `MNEMA_EMBEDDING` /
  `MNEMA_EMBEDDING_MODEL`. Safe to interrupt and re-run. ([#9](https://github.com/mienetic/mnema/issues/9))
- **`mnema --doctor --fix`** — attempts automatic remediation (creates a
  missing data directory, suggests the exact fix for a missing API key). ([#2](https://github.com/mienetic/mnema/issues/2))
- **`mnema backup` / `mnema restore`** — create a portable `.tar.gz` archive
  of all memories (+ manifest with backend/embedding metadata) and restore
  from it. Warns if the backup's backend differs from the current one. ([#12](https://github.com/mienetic/mnema/issues/12))
- **Ollama embedding provider** — talk to a local Ollama server
  (`nomic-embed-text`, 768-d) so embeddings run fully local without loading a
  model in-process. Contributed by [@faizmullaa](https://github.com/faizmullaa). ([#6](https://github.com/mienetic/mnema/issues/6), [#17](https://github.com/mienetic/mnema/pull/17))
- **Auto-recall & auto-remember prompt hooks** — new `remember_this` prompt
  template and a "Proactive memory workflow" section in `SKILL.md` so agents
  recall at the start of a task and store durable facts the moment they
  appear. ([#1](https://github.com/mienetic/mnema/issues/1))
- **One-line installer** (`curl … | bash`) that sets up `uv`, clones the repo,
  creates an isolated Python 3.11 venv, and installs the `mnema` +
  `mnema-update` launchers. Supports `MNEMA_EXTRAS` to pick backends/providers.
- **`mnema-update`** — one-command updater (git pull + reinstall + verify)
  that preserves the extras chosen at install time.
- **Per-agent setup guides** for 8 MCP clients: Claude Desktop, Claude Code,
  Cursor, Zed, Cline, Continue.dev, Windsurf, and ZCode.
- **Thai getting-started guide** (`GETTING_STARTED.md`) for non-developers.
- **`ROADMAP.md`** with prioritized phases 1–4 and status indicators.
- **GitHub issue/PR templates** + Discussions enabled.
- **CI** (GitHub Actions) running tests + lint across Python 3.10–3.13.

### Changed
- Installation is **git + uv only** (not published on PyPI). All docs,
  example configs, Dockerfile, and error messages point at the one-line
  installer instead of `pip install mnema-mcp`.

### Fixed
- **sqlite_vec backend path resolution** — `os.makedirs(dirname)` failed with
  `FileExistsError` when `backend_path` was a file whose name collided with a
  parent path component (e.g. `/data/data`). Now uses `os.path.abspath()` to
  compute the parent directory correctly.
- **Importance values 2–4, 6–7, 9 crashed** — `Importance` is an `IntEnum`
  with only named levels (1/5/8/10), so `--importance 9` raised `ValueError`.
  Added `_coerce_importance()` that snaps any int in [1, 10] to the nearest
  named level. Applied in both `remember()` and `update()`.
- **Installer backend inference** — installing with `MNEMA_EXTRAS=sqlite_vec,local`
  still defaulted `MNEMA_BACKEND=chroma`, so `--doctor` reported a missing
  `chromadb`. The installer now infers the default backend from the chosen
  extras and computes the right `backend_path` per backend
  (sqlite_vec → `data/mnema.db`, qdrant → `data/qdrant`, chroma → `data/`).

  All three were found during end-to-end testing after v0.2.0.

### Planned
- TypeScript MCP server (`packages/mnema-ts/`)
- Web dashboard for browsing memories
- Evaluation harness (`docs/evaluations.xml`)

## [0.1.0] — 2026-07-13

### Added
- 🎉 Initial public release.
- **MCP server** (Python, FastMCP) with 11 tools:
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

[Unreleased]: https://github.com/mienetic/mnema/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mienetic/mnema/releases/tag/v0.1.0
