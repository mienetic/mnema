# Deployment

Mnema runs in three modes depending on how many clients need it and where
they live.

## 1. Local stdio (default)

The simplest mode. Each AI client spawns Mnema as a subprocess and talks
over stdin/stdout. Best for desktop clients (Claude Desktop, ZCode).

```json
{
  "mcpServers": {
    "mnema": { "command": "mnema" }
  }
}
```

(Requires Mnema to be installed first — see the one-line installer in the
[README](../README.md#-quick-start) or [GETTING_STARTED.md](../GETTING_STARTED.md).)

- ✅ Zero network configuration.
- ✅ Per-client data isolation (each client gets its own store path).
- ❌ Multiple clients each pay the model-load cost.
- ❌ No shared memory across clients.

## 2. Local streamable HTTP

Run Mnema as a long-lived local server on `127.0.0.1`. Multiple clients on
the same machine share one store.

```bash
mnema --transport http --host 127.0.0.1 --port 8000
```

Connect clients via their HTTP-MCP support (URL: `http://127.0.0.1:8000/mcp`).

- ✅ One model load shared across clients.
- ✅ Shared memory (if desired).
- ⚠️ Bind only to `127.0.0.1` unless you've added auth.

## 3. Remote HTTP (production)

Deploy Mnema behind a reverse proxy with TLS + auth for team-wide or
multi-tenant use.

```bash
mnema --transport http --host 0.0.0.0 --port 8000
```

Recommendations:

- **TLS**: terminate at the proxy (nginx, Caddy, Cloudflare).
- **Auth**: put an auth layer in front (OAuth proxy, API gateway, mTLS).
  Mnema itself is unauthenticated — like most MCP servers.
- **Backend**: switch to a real server-mode vector DB for scale:
  ```bash
  export MNEMA_BACKEND=qdrant
  export MNEMA_BACKEND_PATH=http://qdrant:6333
  ```
- **Embeddings**: for many concurrent clients, prefer `MNEMA_EMBEDDING=openai`
  (no local model load, lower per-request CPU).
- **Persist data**: mount a volume at `MNEMA_BACKEND_PATH` (or use a
  managed Qdrant/Chroma service).

## Docker

```bash
docker compose -f docker/docker-compose.yml up -d
# HTTP MCP on http://localhost:8000/mcp
```

The compose file mounts a persistent volume for the embedded Chroma store.
To use Qdrant instead, uncomment the `qdrant` service and set the env vars.

## 4. REST API mode (`mnema serve`)

For non-AI apps (dashboards, scripts, other services) that want to use
Mnema over plain HTTP:

```bash
mnema serve --port 8000
# REST API on http://localhost:8000
```

Endpoints: `GET/POST /memories`, `GET/PATCH/DELETE /memories/{id}`,
`POST /search`, `POST /recall`, `GET /scopes`, `GET /stats`. See
[`docs/architecture.md`](architecture.md#rest-api-layer-apiapppy) for the
full list.

This is what the **browser extension** builds on.

## 5. Dashboard mode (`mnema dashboard`)

A browser UI (htmx + Jinja2) for browsing, searching, editing, and forgetting
memories without any AI client or terminal:

```bash
mnema dashboard --port 8080
# Open http://localhost:8080 in your browser
```

Features: stats overview, paginated memory list (filter by scope), memory
detail/edit/forget, hybrid search with score breakdown, decay sweep, scope
summarization planner. Needs the `[api]` extra.

## Auto Dream (background consolidation)

Enable with `MNEMA_DREAM_ENABLED=true` to have Mnema periodically forget
decayed memories and plan summarization while idle — no manual maintenance
needed. Tune the cycle with `MNEMA_DREAM_INTERVAL_SECONDS` (default 3600)
and `MNEMA_DREAM_DECAY_THRESHOLD` (default 0.05). Run a single cycle
manually with `mnema dream`.

## Resource sizing (rough)

For the default local mode (`all-MiniLM-L6-v2` + Chroma):

- **RAM**: ~500 MB (mostly the embedding model).
- **CPU**: ~50 ms per embed on a modern laptop core.
- **Disk**: ~1 KB per memory (text + 384-dim float32 vector).

For OpenAI embeddings + remote Qdrant, the local footprint drops to a
few tens of MB and embed latency is bounded by network RTT.

## Health check

```bash
mnema --doctor
```

Probes the backend and embedding provider and reports any missing
optional dependencies. Run this after install or when troubleshooting.
