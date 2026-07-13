# 🧠 Mnema — Long-term Memory for AI

> Give your AI agents persistent, searchable memory. Solve the context-window problem with **MCP × Vector DB**.

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
- **🧪 Well-tested** — pure-function unit tests + a backend matrix that runs against every supported store.

---

## 🚀 Quick start

### 1. Install

```bash
# Default: Chroma backend + local embeddings (offline)
pip install 'mnema-mcp[default]'

# Or everything (all backends + providers)
pip install 'mnema-mcp[all]'
```

Or with [`uv`](https://docs.astral.sh/uv/):

```bash
uv pip install 'mnema-mcp[default]'
```

### 2. Run the server

```bash
mnema                      # stdio transport (for MCP clients)
mnema --transport http     # streamable HTTP (remote / multi-client)
mnema --doctor             # check config + backend/embedding availability
```

### 3. Wire it into your AI client

<details>
<summary><b>Claude Desktop</b> — <code>claude_desktop_config.json</code></summary>

```json
{
  "mcpServers": {
    "mnema": {
      "command": "uvx",
      "args": ["mnema-mcp"],
      "env": {
        "MNEMA_BACKEND": "chroma",
        "MNEMA_BACKEND_PATH": "~/.mnema/data",
        "MNEMA_DEFAULT_SCOPE": "user:me"
      }
    }
  }
}
```
</details>

<details>
<summary><b>ZCode</b> — MCP config</summary>

```json
{
  "mcpServers": {
    "mnema": {
      "command": "uvx",
      "args": ["mnema-mcp"],
      "env": { "MNEMA_BACKEND": "chroma" }
    }
  }
}
```
</details>

<details>
<summary><b>Cursor</b> — <code>mcp.json</code></summary>

```json
{
  "mcpServers": {
    "mnema": {
      "command": "uvx",
      "args": ["mnema-mcp"]
    }
  }
}
```
</details>

### 4. Try it

In your AI client:

> "Remember that I prefer dark mode and use a Dvorak keyboard layout."

Then in a future session:

> "What do you know about my preferences?"

The agent stores the first message via `mnema_remember` and recalls it via `mnema_search` — across sessions, across conversations.

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
| **Chroma** (default) | `[chroma]` | ✅ in-process + persistent | Quick start, single-user, dev |
| **Qdrant** | `[qdrant]` | ✅ local path / `:memory:` / remote | Production, high scale, metadata filtering |
| **sqlite-vec** | `[sqlite_vec]` | ✅ pure SQLite | Smallest footprint, constrained envs |

```bash
pip install 'mnema-mcp[chroma]'     # or [qdrant] or [sqlite_vec]
export MNEMA_BACKEND=qdrant
```

---

## 🧠 Embedding providers

| Provider | Install extra | Mode | Dim |
|---|---|---|---|
| **sentence-transformers** (default) | `[local]` | Offline (CPU/GPU) | 384 (`all-MiniLM-L6-v2`) |
| **OpenAI** | `[openai]` | API (requires key) | 1536 (`text-embedding-3-small`) |

```bash
pip install 'mnema-mcp[openai]'
export MNEMA_EMBEDDING=openai
export MNEMA_OPENAI_API_KEY=sk-...
```

---

## 🧪 Development

```bash
git clone https://github.com/your-org/mnema.git
cd mnema/packages/mnema-python

# Install with dev deps + all backends
uv pip install -e '.[all,dev]'

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
