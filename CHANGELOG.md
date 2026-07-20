# Changelog

All notable changes to Mnema are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- TypeScript MCP server (`packages/mnema-ts/`)
- Slack / Discord bot

## [0.4.0] — 2026-07-19

### Added
- **pgvector backend** — Postgres + the `vector` extension, via `asyncpg`
  with parameterized queries (`$1, $2, ...` + `*params`). Cosine distance
  via `<=>`. Contributed by [@Adiiiipawar](https://github.com/Adiiiipawar).
  ([#4](https://github.com/mienetic/mnema/issues/4), [#25](https://github.com/mienetic/mnema/pull/25))
- **LanceDB backend** — embedded, serverless columnar vector store. Wraps
  the sync LanceDB API in `anyio.to_thread.run_sync`. Contributed by
  [@Oneshot1123](https://github.com/Oneshot1123).
  ([#5](https://github.com/mienetic/mnema/issues/5), [#27](https://github.com/mienetic/mnema/pull/27))
- **🖥️ Web dashboard** (`mnema dashboard`) — browser UI (htmx + Jinja2) to
  browse, search, edit, forget memories + trigger decay/summarize. No build
  step, no JS framework. Contributed by [@NEMEZIZ1234](https://github.com/NEMEZIZ1234).
  ([#3](https://github.com/mienetic/mnema/issues/3), [#28](https://github.com/mienetic/mnema/pull/28))
- **MCP registry manifest** (`server.json`) — ready for submission to the
  official MCP server registry. Contributed by [@Nitjsefnie](https://github.com/Nitjsefnie).
  ([#21](https://github.com/mienetic/mnema/issues/21), [#26](https://github.com/mienetic/mnema/pull/26))

### Changed
- README: 7 stale spots fixed (extras list, prompts, backend values, config
  table, architecture diagram, acknowledgements).
- CONTRIBUTING.md: synced project layout (5 backends, dashboard/), test count
  (142), added "How to add a dashboard page" guide, updated open issues.
- docs/architecture.md, docs/deployment.md, docs/backends.md: all synced
  with 5 backends + dashboard + REST API.

## [0.3.0] — 2026-07-18

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
- **`mnema eval`** — recall evaluation harness. Seeds a curated dataset
  (30 memories, 24 queries) and reports **recall@5 = 100%, MRR = 1.0** on
  the default `all-MiniLM-L6-v2` model. Use it to prove Mnema works and to
  guard against regressions. ([#15](https://github.com/mienetic/mnema/issues/15))
- **🌙 Auto Dream** — optional background scheduler that consolidates the
  memory store while the server is idle. Each cycle forgets decayed
  memories (below `MNEMA_DREAM_DECAY_THRESHOLD`) and plans summarization
  for cluttered scopes. Enable with `MNEMA_DREAM_ENABLED=true`. Also
  available as `mnema dream` for a one-shot manual cycle. Inspired by the
  way the brain consolidates memories during sleep.
- **`mnema serve` — REST API** — a thin FastAPI layer over `MemoryService`
  exposing all memory operations over plain HTTP: `GET/POST /memories`,
  `GET/PATCH/DELETE /memories/{id}`, `POST /search`, `POST /recall`,
  `GET /scopes`, `GET /stats`. Opens Mnema to non-AI apps. Contributed by
  [@Nitjsefnie](https://github.com/Nitjsefnie). ([#18](https://github.com/mienetic/mnema/issues/18), [#22](https://github.com/mienetic/mnema/pull/22))
- **🐛 Friendly error reporting + debug logging** — unexpected crashes now
  produce a pre-filled GitHub issue link (with version, backend, embedding,
  traceback) so users can report bugs in one click. Expected errors
  (`MnemaError` subclasses) print cleanly without the noise. Set
  `MNEMA_LOG_LEVEL=DEBUG` for verbose logs (backend queries, embed latency,
  search scores).
- **🧩 Browser extension** — Manifest V3 extension (Chrome/Edge/Firefox 115+)
  that captures selected text from any page: **select text → right-click
  "Remember this" → adjust scope/tags/importance → Save.** Vanilla ES modules,
  no build step, 51 unit tests. Contributed by
  [@Nitjsefnie](https://github.com/Nitjsefnie). ([#20](https://github.com/mienetic/mnema/issues/20), [#23](https://github.com/mienetic/mnema/pull/23))
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
- **pgvector backend** — Postgres + the `vector` extension, via `asyncpg`
  with parameterized queries (`$1, $2, ...` + `*params`). Cosine distance
  via `<=>`. Contributed by [@Adiiiipawar](https://github.com/Adiiiipawar).
  ([#4](https://github.com/mienetic/mnema/issues/4), [#25](https://github.com/mienetic/mnema/pull/25))
- **LanceDB backend** — embedded, serverless columnar vector store. Wraps
  the sync LanceDB API in `anyio.to_thread.run_sync`. Contributed by
  [@Oneshot1123](https://github.com/Oneshot1123).
  ([#5](https://github.com/mienetic/mnema/issues/5), [#27](https://github.com/mienetic/mnema/pull/27))
- **🖥️ Web dashboard** (`mnema dashboard`) — browser UI (htmx + Jinja2) to
  browse, search, edit, forget memories + trigger decay/summarize. No build
  step, no JS framework. Contributed by [@NEMEZIZ1234](https://github.com/NEMEZIZ1234).
  ([#3](https://github.com/mienetic/mnema/issues/3), [#28](https://github.com/mienetic/mnema/pull/28))
- **MCP registry manifest** (`server.json`) — ready for submission to the
  official MCP server registry. Contributed by [@Nitjsefnie](https://github.com/Nitjsefnie).
  ([#21](https://github.com/mienetic/mnema/issues/21), [#26](https://github.com/mienetic/mnema/pull/26))

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

[Unreleased]: https://github.com/mienetic/mnema/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/mienetic/mnema/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mienetic/mnema/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/mienetic/mnema/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mienetic/mnema/releases/tag/v0.1.0
