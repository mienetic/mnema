# Architecture

Mnema is built in layers, each with a single responsibility. This makes the
codebase easy to extend (new backends, new embedding providers) without
touching unrelated layers.

## Layers

```
┌─────────────────────────────────────────────────────────────┐
│ MCP Layer (server.py + tools/ + resources.py + prompts.py)  │  ← protocol
├─────────────────────────────────────────────────────────────┤
│ Service Layer (service.py)                                  │  ← orchestration
├─────────────────────────────────────────────────────────────┤
│ Domain Logic (decay.py, summarize.py)                       │  ← pure fns
├─────────────────────────────────────────────────────────────┤
│ Backends (backends/*)      Embeddings (embeddings/*)        │  ← I/O
└─────────────────────────────────────────────────────────────┘
```

### MCP layer
- `server.py` — builds the FastMCP instance, wires the lifespan (creates
  and closes the service), and registers tools/resources/prompts.
- `tools/` — one file per concern. Each tool defines a Pydantic input
  model, calls the service, and returns JSON or Markdown.
- `resources.py` — URI-addressable reads (`mnema://memory/{id}`, …).
- `prompts.py` — canned prompt templates for common workflows.

The MCP layer never touches the vector store or embedding model directly.
It always goes through the service.

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
the server's lifetime. On shutdown, the service closes the embedding
provider (releases any model/HTTP client) and the backend (closes any
connection/file handle).

## Transport

- **stdio** (default) — local integrations. The AI client spawns Mnema as
  a subprocess and talks over stdin/stdout.
- **streamable HTTP** — remote or multi-client deployments. Bind to
  `127.0.0.1` for local-only, or `0.0.0.0` behind a reverse proxy for
  production.

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
