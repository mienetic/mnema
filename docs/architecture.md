# Architecture

Mnema is built in layers, each with a single responsibility. This makes the
codebase easy to extend (new backends, new embedding providers) without
touching unrelated layers.

## Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Interface Layer                                             │
│  ├── MCP (server.py + tools/ + resources.py + prompts.py)   │  ← AI clients
│  ├── CLI (cli.py — 20 subcommands)                          │  ← terminal
│  └── REST API (api/app.py — FastAPI, `mnema serve`)         │  ← non-AI apps
├─────────────────────────────────────────────────────────────┤
│ Service Layer (service.py)                                  │  ← orchestration
├─────────────────────────────────────────────────────────────┤
│ Domain Logic                                                │
│  ├── decay.py, summarize.py    (pure functions)             │
│  ├── dream.py                  (Auto Dream scheduler)       │
│  └── eval_harness.py           (recall@k evaluation)        │
├─────────────────────────────────────────────────────────────┤
│ Backends (backends/*)      Embeddings (embeddings/*)        │  ← I/O
└─────────────────────────────────────────────────────────────┘
```

All three interfaces (MCP, CLI, REST API) share the same `MemoryService` —
so behavior is identical regardless of how you access Mnema.

### MCP layer
- `server.py` — builds the FastMCP instance, wires the lifespan (creates
  and closes the service), and registers tools/resources/prompts.
- `tools/` — one file per concern. Each tool defines a Pydantic input
  model, calls the service, and returns JSON or Markdown.
- `resources.py` — URI-addressable reads (`mnema://memory/{id}`, …).
- `prompts.py` — canned prompt templates (`recall_for`, `remember_this`,
  `summarize_scope`).

The MCP layer never touches the vector store or embedding model directly.
It always goes through the service.

### CLI layer (`cli.py`)
20 subcommands (`add`, `recall`, `search`, `get`, `update`, `forget`,
`forget-scope`, `list-scopes`, `stats`, `decay`, `summarize`, `export`,
`import`, `backup`, `restore`, `re-embed`, `eval`, `dream`, `doctor`).
Each is a thin async handler that calls `MemoryService` and prints output.
Registered in `_CLI_COMMANDS` in `__main__.py` so the router dispatches
to the CLI instead of the MCP server.

### REST API layer (`api/app.py`)
A thin FastAPI wrapper (`mnema serve`) exposing all memory operations
over HTTP: `GET/POST /memories`, `GET/PATCH/DELETE /memories/{id}`,
`POST /search`, `POST /recall`, `GET /scopes`, `GET /stats`. Contributed
by @Nitjsefnie. Lazy-imported so `import mnema` stays light.

### Dashboard layer (`dashboard/app.py`)
A browser UI (`mnema dashboard`) built with FastAPI + Jinja2Templates + htmx
(no build step, no JS framework). Routes: `/` (stats + scope list),
`/memories` (CRUD), `/search` (hybrid search with htmx partials), `/decay`
(decay sweep), `/summarize` (scope summarization). Contributed by
@NEMEZIZ1234. Shares the same `MemoryService` as every other interface.

### Service layer (`service.py`)
The single orchestration point. It:
1. Resolves scopes (with validation).
2. Asks the embedding provider for vectors.
3. Asks the backend to store/search.
4. Computes decay scores and combines them into the final hybrid score.
5. Plans summarization (delegates to `summarize.py`).

Because everything flows through here, the SDK, the MCP server, and the
(planned) CLI all behave identically.

### Domain logic (`decay.py`, `summarize.py`)
Pure functions — no I/O, trivially testable, deterministic.

### Backends (`backends/`)
Each backend implements the `VectorBackend` ABC. They handle persistence
and the actual vector + keyword search. The service combines their raw
hits with decay afterward, so backends don't need to know about decay.

### Embeddings (`embeddings/`)
Each provider implements `EmbeddingProvider`. They turn text into vectors.
Independent from backends, so you can mix local embeddings with a remote
Qdrant server, or OpenAI embeddings with an embedded Chroma store.

## Data model

Every memory is a `MemoryRecord`:

```python
id              # stable uuid hex
text            # the memory content
embedding_dim   # dimensionality of the stored vector
scope           # namespace, e.g. "user:alice"
tags            # free-form labels for keyword filtering
importance      # 1..10 (IntEnum)
metadata        # arbitrary JSON object
created_at      # unix seconds
last_accessed_at
access_count    # bumped on every recall/get
score           # assigned during search
```

## Hybrid score

```
score = w_vec · vec   +   w_kw · kw   +   w_dec · decay

vec      ∈ [0, 1]   cosine similarity (backend-native)
kw       ∈ [0, 1]   tag Jaccard overlap
decay    ∈ [0, 1]   recency(half-life) × frequency × importance
```

Default weights `0.7 / 0.2 / 0.1` (configurable via env). The decay
component includes an importance buffer so `CRITICAL` (10) memories never
fade, and a floor so old memories stay faintly discoverable.

## Lifespan and resource management

The FastMCP lifespan creates the `MemoryService` once and yields it for
the server's lifetime. When `MNEMA_DREAM_ENABLED=true`, the lifespan also
starts the **Auto Dream** background scheduler (`Dreamer`) which runs
`dream_once` on an interval — forgetting decayed memories and planning
summarization while the server is idle. On shutdown, the dreamer is
stopped, then the service closes the embedding provider (releases any
model/HTTP client) and the backend (closes any connection/file handle).

## Transport / interfaces

Mnema exposes **five** interfaces, all sharing the same `MemoryService`:

| Interface | Command | Best for |
|---|---|---|
| **MCP (stdio)** | `mnema` | AI clients (Claude Desktop, Cursor, Zed, …) |
| **MCP (streamable HTTP)** | `mnema --transport http` | remote / multi-client MCP |
| **REST API** | `mnema serve --port 8000` | non-AI apps, browser extension |
| **Web dashboard** | `mnema dashboard --port 8080` | browsing memories in a browser |
| **CLI** | `mnema add`, `mnema recall`, … | terminal / scripting |
| **Python SDK** | `from mnema.sdk import MemoryClient` | embedding in Python apps |

## Why no LLM call inside the server?

Mnema deliberately doesn't call any LLM itself. Reasons:

1. **No circular dependency** — the thing asking Mnema for context *is*
   usually an LLM. Calling another LLM from inside would add cost, latency,
   and another failure mode.
2. **No API key required** — the default install runs fully offline.
3. **Predictability** — summarization plans are deterministic; the client
   executes them with whatever model it already has.

The `mnema_summarize` tool returns a plan + prompt; the client AI writes
the summaries back via `mnema_remember` and forgets the originals.
