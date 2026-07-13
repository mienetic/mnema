# 🧠 Mnema — Long-term Memory for AI

> Give your AI agents persistent, searchable memory. Solve the context-window problem with **MCP × Vector DB**.

[![Install](https://img.shields.io/badge/install-one--line-22C55E.svg)](#-quick-start)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-1.x-purple.svg)](https://modelcontextprotocol.io/)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)](#status)

**Mnema** (μνῆμα — Greek for *"memory"*) is an open-source [Model Context Protocol](https://modelcontextprotocol.io) server that gives language-model agents a long-term memory layer. Instead of stuffing every relevant fact into a single conversation (and paying for it in tokens, latency, and lost context), store durable facts once and recall them later — by meaning, not by keyword.

---

## ✨ Features

- **🔌 MCP-native** — drop it into Claude Desktop, ZCode, Cursor, or any MCP-compatible client.
- **🗄️ Pluggable vector backends** — ChromaDB (embedded, default), Qdrant (local or remote), or sqlite-vec (pure-SQLite, zero-dep).
- **🧠 Hybrid search** — combines **semantic similarity** + **tag overlap** + **decay scoring** into a single ranked score.
- **⏳ Memory decay** — a forgetting curve (`recency × frequency × importance`) so the store stays focused on what matters.
- **📝 Summarization** — plans how to condense many memories into a few high-level ones; the calling AI executes the plan (Mnema never calls an LLM on its own).
- **👥 Multi-user / multi-session** — scope-based namespace isolation (`user:alice`, `session:abc`, `agent:bot-1`).
- **🔧 Offline by default** — local sentence-transformers embeddings; no API keys required to start.
- **📦 Programmatic SDK** — use Mnema from Python without standing up an MCP server.
- **💻 CLI** — `mnema add`, `mnema recall`, `mnema stats`… for terminal-first workflows.
- **🧪 Well-tested** — pure-function unit tests + a backend matrix that runs against every supported store.

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

Available extras: `chroma`, `qdrant`, `sqlite_vec`, `local`, `openai`, `default`
(= `chroma,local`), `all`. See [docs/backends.md](docs/backends.md) and
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

# Backup / migrate
mnema export -o memories.json
mnema import -i memories.json
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
| `MNEMA_EMBEDDING` | `local` | `local` (offline) \| `openai` |
| `MNEMA_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Model name |
| `MNEMA_EMBEDDING_DIM` | _auto_ | Override vector dim |
| `MNEMA_OPENAI_API_KEY` | — | Required when `embedding=openai` |
| `MNEMA_DEFAULT_SCOPE` | `global` | Scope when a tool omits it |
| `MNEMA_DECAY_HALF_LIFE_DAYS` | `30` | Recency half-life |
| `MNEMA_DECAY_FLOOR` | `0.05` | Min decay score |
| `MNEMA_VECTOR_WEIGHT` | `0.7` | Hybrid score weight (must sum to 1) |
| `MNEMA_KEYWORD_WEIGHT` | `0.2` | Hybrid score weight |
| `MNEMA_DECAY_WEIGHT` | `0.1` | Hybrid score weight |
| `MNEMA_TRANSPORT` | `stdio` | `stdio` \| `http` |
| `MNEMA_HTTP_HOST` | `127.0.0.1` | HTTP bind host |
| `MNEMA_HTTP_PORT` | `8000` | HTTP bind port |

---

## 🗄️ Choosing a backend

| Backend | Install extra | Embedded? | Best for |
|---|---|---|---|
| **Chroma** (default) | `chroma` | ✅ in-process + persistent | Quick start, single-user, dev |
| **Qdrant** | `qdrant` | ✅ local path / `:memory:` / remote | Production, high scale, metadata filtering |
| **sqlite-vec** | `sqlite_vec` | ✅ pure SQLite | Smallest footprint, constrained envs |

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

## 📦 Project layout

```
mnema/
├── packages/
│   ├── mnema-python/         # ⭐ MCP server + SDK (Python)
│   │   ├── src/mnema/
│   │   │   ├── backends/     # chroma, qdrant, sqlite_vec
│   │   │   ├── embeddings/   # sentence_transformers, openai
│   │   │   ├── tools/        # 10 MCP tools
│   │   │   ├── service.py    # orchestration
│   │   │   ├── decay.py      # forgetting curve
│   │   │   ├── summarize.py  # summarization planner
│   │   │   ├── sdk.py        # programmatic SDK
│   │   │   └── server.py     # FastMCP bootstrap
│   │   └── tests/
│   ├── mnema-ts/             # TypeScript MCP server (planned)
│   └── mnema-cli/            # Node CLI (planned)
├── docker/                   # Dockerfile + compose
├── docs/                     # architecture, backends, deployment
├── examples/                 # client config examples
├── SKILL.md                  # agent-facing usage guide
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
                    transformers │  sqlite-vec
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

- [x] Python MCP server (FastMCP)
- [x] Chroma / Qdrant / sqlite-vec backends
- [x] Local + OpenAI embeddings
- [x] Hybrid search with decay
- [x] Summarization planner
- [x] Programmatic Python SDK
- [ ] TypeScript MCP server (native Node runtime)
- [ ] CLI (`mnema add`, `mnema recall`, …)
- [ ] Web dashboard for browsing memories
- [ ] Evaluation harness (`docs/evaluations.xml`)

---

## 📄 License

[MIT](LICENSE) © Mnema Contributors.

## 🙏 Acknowledgements

- [Model Context Protocol](https://modelcontextprotocol.io) — the protocol that makes this possible.
- [ChromaDB](https://www.trychroma.com/), [Qdrant](https://qdrant.tech/), [sqlite-vec](https://github.com/asg017/sqlite-vec) — excellent open-source vector stores.
- [sentence-transformers](https://www.sbert.net/) — offline embeddings for everyone.

---

<p align="center"><i>μνῆμα — memory, made durable.</i></p>
