# 🧠 Mnema — Long-term Memory for AI

> Give your AI agents persistent, searchable memory. Solve the context-window problem with **MCP × Vector DB**.

[![CI](https://github.com/mienetic/mnema/actions/workflows/python-ci.yml/badge.svg)](https://github.com/mienetic/mnema/actions/workflows/python-ci.yml)
[![Install](https://img.shields.io/badge/install-one--line-22C55E.svg)](#-quick-start)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-1.x-purple.svg)](https://modelcontextprotocol.io/)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)](#status)

**Mnema** (μνῆμα — Greek for *"memory"*) is an open-source [Model Context Protocol](https://modelcontextprotocol.io) server that gives language-model agents a long-term memory layer. Instead of stuffing every relevant fact into a single conversation (and paying for it in tokens, latency, and lost context), store durable facts once and recall them later — by meaning, not by keyword.

---

## ✨ Features

- **🔌 MCP-native** — drop it into Claude Desktop, Claude Code, Cursor, Zed, Cline, Continue, Windsurf, ZCode, or any MCP-compatible client.
- **🗄️ Pluggable vector backends** — ChromaDB (embedded, default), Qdrant (local or remote), sqlite-vec (pure-SQLite), or LanceDB (columnar, high-performance).
- **🧠 Pluggable embeddings** — sentence-transformers (offline, default), OpenAI, or Ollama (local server).
- **🔍 Hybrid search** — combines **semantic similarity** + **tag overlap** + **decay scoring** into a single ranked score.
- **⏳ Memory decay** — a forgetting curve (`recency × frequency × importance`) so the store stays focused on what matters.
- **🌙 Auto Dream** — optional background scheduler that consolidates memories while the server is idle (forget decayed + plan summarization), like a brain sleeping.
- **📝 Summarization** — plans how to condense many memories into a few high-level ones; the calling AI executes the plan (Mnema never calls an LLM on its own).
- **👥 Multi-user / multi-session** — scope-based namespace isolation (`user:alice`, `session:abc`, `agent:bot-1`).
- **🔧 Offline by default** — local sentence-transformers embeddings; no API keys required to start.
- **📦 Programmatic SDK** — use Mnema from Python without standing up an MCP server.
- **💻 CLI** — `mnema add`, `mnema recall`, `mnema stats`… for terminal-first workflows.
- **🌐 REST API** — `mnema serve` exposes all memory operations over plain HTTP (FastAPI) for non-AI apps.
- **🧩 Browser extension** — select text on any page → right-click "Remember this" → adjust scope/tags → save (Chrome/Edge/Firefox 115+, Manifest V3).
- **🧪 Well-tested** — 142 Python tests + 51 JS tests across pure-function unit tests + a backend matrix that runs against every supported store. Plus a built-in **recall eval harness** (`mnema eval`) — **recall@5 = 100%, MRR = 1.0** on the bundled dataset.
- **🐛 Friendly error reporting** — unexpected crashes produce a pre-filled GitHub issue link with full diagnostics (version, backend, embedding, traceback) so users can report bugs in one click. Set `MNEMA_LOG_LEVEL=DEBUG` for verbose logs.

---

## 🚀 Quick start

### One-line install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh | bash
```

That's it. The installer:
1. Installs [`uv`](https://docs.astral.sh/uv/) (no pip / no virtualenv wrangling).
2. Clones Mnema from GitHub.
3. Creates an isolated Python 3.11 environment with all dependencies.
4. Installs the `mnema` and `mnema-update` commands.
5. Runs `mnema --doctor` to verify.

> 🇹🇭 **New to this?** See [GETTING_STARTED.md](GETTING_STARTED.md) — step-by-step guide (in Thai).

### Verify & update

```bash
mnema --doctor          # check backend + embedding loaded
mnema --doctor --fix    # attempt to fix common problems (missing dir, etc.)
mnema                   # run the MCP server (stdio, for clients)
mnema-update            # git pull + reinstall + verify (run this to upgrade)
```

### Pick different backends / embeddings (optional)

The default install ships **Chroma + local embeddings** — enough for most
users. To use another backend, reinstall with the matching extra(s):

```bash
# Qdrant (local or remote)
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS="qdrant,local" bash

# sqlite-vec (smallest footprint)
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS="sqlite_vec,local" bash

# Everything (all backends + OpenAI embeddings)
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS=all bash
```

Available extras: `chroma`, `qdrant`, `sqlite_vec`, `lancedb`, `local`, `openai`, `ollama`,
`default` (= `chroma,local`), `all`. See [docs/backends.md](docs/backends.md) and
[docs/embedding-providers.md](docs/embedding-providers.md).

### Manual / from source

```bash
git clone https://github.com/mienetic/mnema
cd mnema/packages/mnema-python
uv venv --python 3.11 .venv
VIRTUAL_ENV=.venv uv pip install -e '.[default]'
.venv/bin/mnema --doctor
```

### Wire it into your AI client

Pick your client below. **Each example assumes Mnema is already installed**
(`mnema` is on your `PATH` after running the installer).

<details>
<summary><b>Claude Desktop</b> (Anthropic's desktop app)</summary>

1. Find or create the config file:
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
     *(in Finder, press `Cmd+Shift+G` and paste the path)*
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
2. Paste this into the file (merge with existing `mcpServers` if present):

   ```json
   {
     "mcpServers": {
       "mnema": {
         "command": "mnema",
         "env": {
           "MNEMA_BACKEND": "chroma",
           "MNEMA_BACKEND_PATH": "~/.mnema-data",
           "MNEMA_DEFAULT_SCOPE": "user:me"
         }
       }
     }
   }
   ```
3. **Fully quit Claude Desktop** (menu → Quit, not just close the window) and reopen it.
4. Verify: click the **🔌 plug icon** in the chat — `mnema` should appear in the list.
5. Try: *"Remember that I prefer dark mode."* then, in a new chat, *"What do you know about my preferences?"*

</details>

<details>
<summary><b>Claude Code</b> (the <code>claude</code> CLI)</summary>

1. From your project root, add the server:
   ```bash
   claude mcp add mnema mnema
   ```
   Or add it to `~/.claude.json` (user scope) directly:

   ```json
   {
     "mcpServers": {
       "mnema": {
         "command": "mnema",
         "env": { "MNEMA_DEFAULT_SCOPE": "user:me" }
       }
     }
   }
   ```
2. Start `claude` and run `/mcp` to confirm `mnema` is connected.
3. Tools are available automatically — try *"remember that this project uses Postgres"*.

</details>

<details>
<summary><b>Cursor</b> (the AI code editor)</summary>

1. Create `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project-level):
   ```json
   {
     "mcpServers": {
       "mnema": {
         "command": "mnema",
         "env": {
           "MNEMA_BACKEND": "chroma",
           "MNEMA_BACKEND_PATH": "~/.mnema-data",
           "MNEMA_DEFAULT_SCOPE": "project:current"
         }
       }
     }
   }
   ```
2. Open Cursor → **Settings → MCP** (or reload the window: `Cmd+Shift+P` → "Reload Window").
3. `mnema` should show a green dot. If red, check the path with `which mnema`.
4. Use it in chat: *"search my memory for past decisions about the auth module."*

</details>

<details>
<summary><b>Zed</b> (the editor)</summary>

1. Open `~/.config/zed/settings.json` (macOS) and add under `context_servers`:
   ```json
   {
     "context_servers": {
       "mnema": {
         "command": { "path": "mnema" },
         "env": { "MNEMA_DEFAULT_SCOPE": "user:me" }
       }
     }
   }
   ```
2. Restart Zed, then enable the server in Assistant panel settings.
3. In the Assistant, tag `@mnema` to pull memory context into the conversation.

</details>

<details>
<summary><b>Cline</b> (VS Code extension)</summary>

1. Open the Cline sidebar → **MCP** icon → **"Edit MCP Settings"**.
2. Add the entry to `cline_mcp_settings.json`:
   ```json
   {
     "mcpServers": {
       "mnema": {
         "command": "mnema",
         "env": { "MNEMA_DEFAULT_SCOPE": "workspace" },
         "disabled": false,
         "alwaysAllow": []
       }
     }
   }
   ```
3. Cline auto-detects the change — no restart needed.
4. Ask Cline: *"search memory for anything I decided about testing strategy."*

</details>

<details>
<summary><b>Continue.dev</b> (VS Code / JetBrains)</summary>

1. Open `~/.continue/config.json` and add under `experimental.modelContextProtocolServers`:
   ```json
   {
     "experimental": {
       "modelContextProtocolServers": [
         {
           "transport": { "type": "stdio", "command": "mnema" }
         }
       ]
     }
   }
   ```
2. Reload the window (`Cmd+Shift+P` → "Reload Window").
3. Use `@mnema` in the Continue chat to scope memory tools.

</details>

<details>
<summary><b>Windsurf</b> (Codeium's editor)</summary>

1. Open **Settings → MCP Servers** → **"Add Server"** (or edit `~/.codeium/windsurf/mcp_config.json`):
   ```json
   {
     "mcpServers": {
       "mnema": { "command": "mnema" }
     }
   }
   ```
2. Click **Refresh** on the MCP panel — `mnema` should turn active.
3. Use Cascade with `@mnema` to recall project context.

</details>

<details>
<summary><b>Any other MCP client</b> (generic)</summary>

Mnema is a standard **stdio** MCP server. Any client that supports the
[Model Context Protocol](https://modelcontextprotocol.io) can launch it:

```json
{
  "mcpServers": {
    "mnema": { "command": "mnema" }
  }
}
```

For **remote / multi-client** setups, run Mnema over streamable HTTP:

```bash
mnema --transport http --host 127.0.0.1 --port 8000
# then point clients at http://127.0.0.1:8000/mcp
```

</details>

Ready-to-copy configs for all clients are in [`examples/`](examples/).

---

## 🛠️ Tools

| Tool | Description | Read-only? |
|---|---|---|
| `mnema_remember` | Store a new memory | ✏️ |
| `mnema_recall` | Pure semantic vector search | 🔍 |
| `mnema_search` | Hybrid: vector + tags + decay | 🔍 |
| `mnema_get_memory` | Fetch one memory by id | 🔍 |
| `mnema_update_memory` | Patch text/tags/importance/metadata | ✏️ |
| `mnema_forget` | Delete one memory | 🗑️ |
| `mnema_forget_scope` | Delete all memories in a scope | 🗑️ |
| `mnema_list_scopes` | Enumerate scopes + counts | 🔍 |
| `mnema_summarize` | Plan how to condense a scope | 🔍 |
| `mnema_apply_decay` | Find/forget low-value memories | 🗑️ |
| `mnema_stats` | Aggregate store stats | 🔍 |

Plus **resources** (`mnema://memory/{id}`, `mnema://scope/{s}/summary`, `mnema://stats`) and **prompt templates** (`summarize_scope`, `recall_for`).

See **[SKILL.md](SKILL.md)** for the full agent-facing usage guide.

---

## 💻 CLI

You don't need an AI client to use Mnema — the `mnema` command works as a
terminal tool too. (Comes free with the installer.)

```bash
# Store a memory
mnema add "Alice prefers Earl Grey tea" --tags pref,tea --scope user:alice

# Recall by meaning
mnema recall "what does alice drink?" --scope user:alice

# Hybrid search (vector + tags + decay)
mnema search "preferences" --tag pref --scope user:alice

# Inspect
mnema get <id>
mnema list-scopes
mnema stats

# Maintain
mnema decay --threshold 0.1            # dry-run: list low-value memories
mnema decay --threshold 0.1 --apply    # actually forget them
mnema summarize session:abc            # plan how to condense a scope

# Backup / migrate / snapshot
mnema export -o memories.json
mnema import -i memories.json
mnema backup -o mnema-backup.tar.gz     # portable archive (memories + manifest)
mnema restore mnema-backup.tar.gz

# Evaluate recall quality (recall@k + MRR)
mnema eval                               # seed + run 24 queries, print report

# Dream — consolidate memories (forget decayed + plan summarization)
mnema dream                              # run a single dream cycle manually
# (or enable background dreaming: MNEMA_DREAM_ENABLED=true)

# Re-embed after switching embedding model (see docs/embedding-providers.md)
mnema re-embed

# REST API (for non-AI apps, dashboards, browser extension)
mnema serve --port 8000             # GET/POST /memories, POST /search, ...
```

Add `--json` to any read command for machine-readable output. Run
`mnema <command> --help` for full options.

---

## 🧑‍💻 Programmatic SDK

Use Mnema from Python without MCP — same engine, no IPC:

```python
import asyncio
from mnema.sdk import MemoryClient

async def main():
    async with MemoryClient() as client:
        await client.remember(
            "Alice's deployment target is fly.io (region sin).",
            scope="project:web",
            tags=["deploy", "infra"],
            importance=8,
        )
        hits = await client.search("where do we deploy?", scope="project:web")
        print(hits.results[0].memory.text)

asyncio.run(main())
```

Synchronous helper for scripts:

```python
from mnema.sdk import sync_client

with sync_client() as client:
    client.remember("a durable fact", tags=["x"])
    print(client.recall("durable").results)
```

---

## ⚙️ Configuration

All settings are environment-driven (or `.env`):

| Variable | Default | Description |
|---|---|---|
| `MNEMA_BACKEND` | `chroma` | `chroma` \| `qdrant` \| `sqlite_vec` |
| `MNEMA_BACKEND_PATH` | `.mnema/data` | Local path or remote URL (`http://…`) |
| `MNEMA_BACKEND_COLLECTION` | `memories` | Collection/table name |
| `MNEMA_EMBEDDING` | `local` | `local` (offline) \| `openai` \| `ollama` |
| `MNEMA_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Model name |
| `MNEMA_EMBEDDING_DIM` | _auto_ | Override vector dim |
| `MNEMA_OPENAI_API_KEY` | — | Required when `embedding=openai` |
| `MNEMA_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL (when `embedding=ollama`) |
| `MNEMA_DEFAULT_SCOPE` | `global` | Scope when a tool omits it |
| `MNEMA_DECAY_HALF_LIFE_DAYS` | `30` | Recency half-life |
| `MNEMA_DECAY_FLOOR` | `0.05` | Min decay score |
| `MNEMA_VECTOR_WEIGHT` | `0.7` | Hybrid score weight (must sum to 1) |
| `MNEMA_KEYWORD_WEIGHT` | `0.2` | Hybrid score weight |
| `MNEMA_DECAY_WEIGHT` | `0.1` | Hybrid score weight |
| `MNEMA_TRANSPORT` | `stdio` | `stdio` \| `http` |
| `MNEMA_HTTP_HOST` | `127.0.0.1` | HTTP bind host |
| `MNEMA_HTTP_PORT` | `8000` | HTTP bind port |
| `MNEMA_DREAM_ENABLED` | `false` | Auto Dream background consolidation |
| `MNEMA_DREAM_INTERVAL_SECONDS` | `3600` | Seconds between dream cycles |
| `MNEMA_DREAM_DECAY_THRESHOLD` | `0.05` | Decay cutoff for forgetting during dreams |
| `MNEMA_LOG_LEVEL` | `WARNING` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` — verbose logs for bug reports |

---

## 🗄️ Choosing a backend

| Backend | Install extra | Embedded? | Best for |
|---|---|---|---|---|
| **Chroma** (default) | `chroma` | ✅ in-process + persistent | Quick start, single-user, dev |
| **Qdrant** | `qdrant` | ✅ local path / `:memory:` / remote | Production, high scale, metadata filtering |
| **sqlite-vec** | `sqlite_vec` | ✅ pure SQLite | Smallest footprint, constrained envs |
| **LanceDB** | `lancedb` | ✅ embedded columnar | High-performance local, large stores |

Switch backends by reinstalling with the right extra and setting the env var:

```bash
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS="qdrant,local" bash
export MNEMA_BACKEND=qdrant
mnema --doctor
```

See [docs/backends.md](docs/backends.md) for full details.

---

## 🧠 Embedding providers

| Provider | Install extra | Mode | Dim |
|---|---|---|---|
| **sentence-transformers** (default) | `local` | Offline (CPU/GPU) | 384 (`all-MiniLM-L6-v2`) |
| **OpenAI** | `openai` | API (requires key) | 1536 (`text-embedding-3-small`) |
| **Ollama** | `ollama` | Local server | 768 (`nomic-embed-text`) |

```bash
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS="chroma,openai" bash
export MNEMA_EMBEDDING=openai
export MNEMA_OPENAI_API_KEY=sk-...
mnema --doctor
```

See [docs/embedding-providers.md](docs/embedding-providers.md) for model options.

---

## 🧪 Development

```bash
git clone https://github.com/mienetic/mnema.git
cd mnema/packages/mnema-python

# Install with dev deps + all backends
uv venv --python 3.11 .venv
VIRTUAL_ENV=.venv uv pip install -e '.[all,dev]'

# Run tests (skips backends whose deps are missing)
pytest

# Run a specific backend's tests after installing its extra
pytest -m chroma

# Lint + typecheck
ruff check .
mypy src/mnema
```

### Test the server interactively

```bash
npx @modelcontextprotocol/inspector uv run mnema
```

This opens the MCP Inspector web UI where you can call every tool.

---

## 🐳 Docker

```bash
docker compose -f docker/docker-compose.yml up mnema
# Streamable HTTP on http://localhost:8000/mcp
```

See [`docker/`](docker/) for the Dockerfile and compose setup.

---

## 📋 MCP Registry

Mnema is not yet listed on the [official MCP Registry](https://registry.modelcontextprotocol.io/)
([modelcontextprotocol/registry](https://github.com/modelcontextprotocol/registry)). Listing
there is a **maintainer-only action** — the registry namespace
(`io.github.mienetic/mnema`) is proven via GitHub OAuth for the `mienetic` account,
so only the repo owner can complete the submission. This section tracks what's
ready and what's left.

> **Process note:** [issue #21](https://github.com/mienetic/mnema/issues/21) pointed
> at `modelcontextprotocol/servers`' "Adding your server" flow (a PR adding a row to
> a categorized README list). That process has since been retired — that repo's
> README now states it "is dedicated to housing just the small number of reference
> servers maintained by the MCP steering group" and points elsewhere for the actual
> server directory. The current mechanism is the separate
> [`modelcontextprotocol/registry`](https://github.com/modelcontextprotocol/registry)
> project: a live, searchable API (`registry.modelcontextprotocol.io`) that servers
> publish to directly via the `mcp-publisher` CLI, using a `server.json` manifest
> validated against a published [JSON Schema](https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json).
> There is no PR to open and no `category` field anymore (that schema has no
> category/tag taxonomy at all — discovery is via the API's search).

**Prepared:** [`packages/mnema-python/server.json`](packages/mnema-python/server.json) —
a schema-valid manifest with the server's name, description, version, and
repository metadata (including the `packages/mnema-python` monorepo subfolder).

**Not yet possible:** the manifest has no `packages` entry. The registry only
resolves ownership for packages published to a **supported** package registry —
currently npm, PyPI, NuGet, Cargo/crates.io, Docker/OCI, or MCPB releases (see
[Package Types](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx)).
Mnema isn't on any of them yet — as [`.github/workflows/release.yml`](.github/workflows/release.yml)
says today: *"Mnema is NOT published to PyPI — installation is via the one-line
installer (git + uv)."* That installer has no representation in the current
`server.json` schema, so a submission today would be a bare, install-less
listing (discovery only, no auto-install for MCP clients).

**To complete the listing** (maintainer, once ready to publish to PyPI):

1. Publish the [`mnema-mcp`](packages/mnema-python/pyproject.toml) package to
   PyPI (already named/versioned there; needs a PyPI account + `uv build` +
   `twine upload`, or equivalent). The
   `<!-- mcp-name: io.github.mienetic/mnema -->` ownership marker is already
   in [`packages/mnema-python/README.md`](packages/mnema-python/README.md),
   ready for the registry's PyPI verification step.
2. Add a `packages` entry to `server.json`:
   `{"registryType": "pypi", "identifier": "mnema-mcp", "version": "<published version>", "transport": {"type": "stdio"}}`.
3. Install [`mcp-publisher`](https://github.com/modelcontextprotocol/registry/releases),
   run `mcp-publisher login github`, then `mcp-publisher publish` from
   `packages/mnema-python/`.
4. Verify: `curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.mienetic/mnema"`.

---

## 📦 Project layout

```
mnema/
├── packages/
│   ├── mnema-python/         # ⭐ MCP server + SDK + CLI + REST API (Python)
│   │   ├── src/mnema/
│   │   │   ├── backends/     # chroma, qdrant, sqlite_vec, lancedb
│   │   │   ├── embeddings/   # sentence_transformers, openai, ollama
│   │   │   ├── tools/        # 11 MCP tools
│   │   │   ├── api/          # REST API (FastAPI) — `mnema serve`
│   │   │   ├── cli.py        # terminal CLI (20 subcommands)
│   │   │   ├── service.py    # orchestration
│   │   │   ├── decay.py      # forgetting curve
│   │   │   ├── summarize.py  # summarization planner
│   │   │   ├── dream.py      # 🌙 Auto Dream scheduler
│   │   │   ├── eval_harness.py  # recall@k evaluation
│   │   │   ├── diagnostics.py   # logging + error reporting
│   │   │   ├── sdk.py        # programmatic SDK
│   │   │   └── server.py     # FastMCP bootstrap
│   │   └── tests/            # 142 tests (unit + backend matrix + eval + dream + diagnostics)
│   └── mnema-extension/      # 🧩 browser extension (MV3) — "Remember this" over the REST API
│       ├── src/              # popup, options, background service worker
│       └── test/             # 51 JS tests (node:test)
├── docker/                   # Dockerfile + compose
├── docs/                     # architecture, backends, deployment, embedding-providers
├── examples/                 # client config examples
├── scripts/                  # one-line installer + updater
├── SKILL.md                  # agent-facing usage guide
├── ROADMAP.md                # prioritized roadmap (Phase 1–4)
└── README.md
```

---

## 🤝 How it works

```
┌──────────────┐    MCP     ┌──────────────────┐
│  AI Client   │◄──────────►│   Mnema Server   │
└──────────────┘  (stdio/   │  ┌────────────┐  │
                  HTTP)     │  │ 10 tools   │  │
                            │  └──────┬─────┘  │
                            │  ┌──────▼─────┐  │
                            │  │  Service   │  │
                            │  └──┬─────┬───┘  │
                            │ ┌────▼─┐ ┌─▼────┐ │
                            │ │embed │ │vector│ │
                            │ └──┬───┘ └──┬───┘ │
                            └────┼─────────┼────┘
                                 │         │
                     sentence-    │  Chroma/Qdrant/
                     transformers │  sqlite-vec/LanceDB
                    (local)      │
                                 ▼         ▼
                              vectors  + metadata
```

Every memory is embedded, stored alongside its scope/tags/importance, and
ranked on retrieval by:

```
score = 0.7·vector + 0.2·keyword + 0.1·decay
```

where `decay = recency(half-life) × frequency × importance`.

---

## 🗺️ Roadmap

**Shipped:** Python MCP server · CLI (20 subcommands) · REST API (`mnema serve`) · browser extension · Chroma/Qdrant/sqlite-vec/LanceDB backends · local/OpenAI/Ollama embeddings · hybrid search with decay · Auto Dream consolidation · recall eval (100% recall@5) · backup/restore · re-embed migration · friendly error reporting.

**In progress (contributors):** pgvector backend · Cohere/Voyage/Nomic embeddings · web dashboard · Slack/Discord bot.

See **[ROADMAP.md](ROADMAP.md)** for the full prioritized plan (Phase 1–4) and the [open issues](https://github.com/mienetic/mnema/issues) to pick from.

---

## 📄 License

[MIT](LICENSE) © Mnema Contributors.

## 🙏 Acknowledgements

- [Model Context Protocol](https://modelcontextprotocol.io) — the protocol that makes this possible.
- [ChromaDB](https://www.trychroma.com/), [Qdrant](https://qdrant.tech/), [sqlite-vec](https://github.com/asg017/sqlite-vec) — excellent open-source vector stores.
- [sentence-transformers](https://www.sbert.net/) — offline embeddings for everyone.
- **Contributors:** [@faizmullaa](https://github.com/faizmullaa) (Ollama embedding provider), [@Nitjsefnie](https://github.com/Nitjsefnie) (REST API + browser extension).

---

<p align="center"><i>μνῆμα — memory, made durable.</i></p>
