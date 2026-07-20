# Contributing to Mnema

Thanks for your interest in improving Mnema! 🧠

This project welcomes contributions of all kinds — bug reports, fixes, new
backends/embedding providers, REST API routes, CLI commands, docs, and evals.
The bar is "make AI memory better for everyone."

## Code of conduct

Be kind. Assume good intent. Disagree about ideas, not people. The
[GitHub community guidelines](https://docs.github.com/en/site-policy/github-terms/github-community-guidelines)
apply.

## Getting set up

```bash
git clone https://github.com/mienetic/mnema.git
cd mnema/packages/mnema-python

# Create a venv and install with all optional deps + dev tooling
uv venv --python 3.11 .venv
VIRTUAL_ENV=.venv uv pip install -e '.[all,dev]'

# Verify
.venv/bin/ruff check src/ tests/
.venv/bin/pytest
.venv/bin/mypy src/mnema    # informational — see note below
```

You'll need Python 3.10+ and (recommended) [`uv`](https://docs.astral.sh/uv/).
The test suite automatically skips backend tests whose optional dependency
isn't installed, so a minimal install still runs the core + service tests.

> **Note on mypy:** type-checking is currently *informational* — it won't
> block your PR. We're working toward full annotations. Run it, fix what's
> easy, but don't stress about every error.

## Project layout

```
src/mnema/
├── backends/          # vector stores: chroma, qdrant, sqlite_vec, pgvector, lancedb
├── embeddings/        # embedding providers: sentence_transformers, openai, ollama, cohere, voyage, nomic
├── tools/             # 11 MCP tools, one concern per file
├── api/               # REST API (FastAPI) — `mnema serve`
├── dashboard/         # web UI (htmx + Jinja2) — `mnema dashboard`
├── cli.py             # terminal CLI (22 subcommands)
├── service.py         # orchestration (the only place backends + embeddings meet)
├── decay.py           # forgetting curve (pure functions)
├── summarize.py       # summarization planner (pure functions)
├── dream.py           # Auto Dream background scheduler
├── eval_harness.py    # recall evaluation (recall@k + MRR)
├── diagnostics.py     # logging + error reporting
├── sdk.py             # programmatic Python client
└── server.py          # FastMCP bootstrap + lifespan
tests/                 # pytest (164 tests); fakes.py has in-memory backend + hashing embedding
```

## How to add a new vector backend

1. Create `src/mnema/backends/yourbackend.py` implementing `VectorBackend`.
2. Register it in `backends/__init__.py::make_backend`.
3. Add a `[project.optional-dependencies]` entry in `pyproject.toml`.
4. Add a test class in `tests/test_backends.py` using the marker pattern.
5. Update `docs/backends.md` and the README table.

The interface contract:

```python
class VectorBackend(ABC):
    async def add(self, record, embedding) -> None
    async def get(self,memory_id) -> MemoryRecord | None
    async def update(self, memory_id, *, text, tags, importance, metadata, embedding) -> MemoryRecord | None
    async def delete(self, memory_id) -> bool
    async def delete_by_scope(self, scope) -> int
    async def search(self, query: BackendQuery) -> list[BackendHit]
    async def count(self, scope=None) -> int
    async def list_scopes(self) -> dict[str, int]
    async def iter_all(self, scope=None) -> AsyncIterator[MemoryRecord]
```

A `touch(memory_id)` method is optional — the service layer uses it to bump
`last_accessed_at` / `access_count` after a recall.

### Worked example: adding a Postgres (pgvector) backend

**1. Implement the backend** — `src/mnema/backends/pgvector.py`:

```python
from mnema.backends.base import BackendHit, BackendQuery, VectorBackend
from mnema.config import MnemaConfig
from mnema.errors import BackendInitError
from mnema.models import MemoryRecord

class PgVectorBackend(VectorBackend):
    name = "pgvector"

    def __init__(self, config: MnemaConfig) -> None:
        try:
            import asyncpg
        except ImportError as exc:
            raise BackendInitError(
                "asyncpg is not installed. Reinstall Mnema with the 'pgvector' extra:\n"
                "    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh "
                "| MNEMA_EXTRAS='pgvector,local' bash"
            ) from exc
        # ... open the connection, ensure the 'vector' extension + table exist

    async def add(self, record, embedding): ...
    async def search(self, query: BackendQuery) -> list[BackendHit]:
        # ORDER BY embedding <=> query_embedding  (cosine distance)
        ...
    # ... implement the rest of the interface
```

**2. Register it** in `src/mnema/backends/__init__.py`:

```python
if backend == "pgvector":
    from mnema.backends.pgvector import PgVectorBackend  # lazy import
    return PgVectorBackend(config)
```

**3. Add the optional dependency** in `pyproject.toml`:

```toml
pgvector = ["asyncpg>=0.29", "pgvector>=0.3"]
```
Also add `"pgvector"` to the `BackendName` Literal in `config.py`.

**4. Add tests** in `tests/test_backends.py` — copy the `TestSqliteVecBackend`
class and swap the backend name + config. It auto-skips if `asyncpg` isn't
installed.

**5. Update docs**: add a row to the backend table in `README.md` and
`docs/backends.md`.

**6. Verify**: `ruff check . && pytest && mnema --doctor --fix`.

## How to add a new embedding provider

1. Create `src/mnema/embeddings/yourprovider.py` implementing `EmbeddingProvider`.
2. Register in `embeddings/__init__.py::make_embedding`.
3. Add a `[yourprovider]` extra in `pyproject.toml`.
4. Add tests that mock httpx (see `tests/test_embeddings.py`).

### Worked example: adding a Cohere provider

The Ollama provider (`src/mnema/embeddings/ollama.py`, contributed by
@faizmullaa) is the best template — it's a thin async HTTP client with
proper error handling. Copy that structure for any API-based provider:

```python
class CohereEmbeddingProvider(EmbeddingProvider):
    name = "cohere"

    def __init__(self, config: MnemaConfig) -> None:
        self._model = config.embedding_model or "embed-english-v3.0"
        self._api_key = config.cohere_api_key  # add this field to MnemaConfig
        self._client = httpx.AsyncClient(...)
        self.dim = ...

    async def embed(self, texts):
        # POST to Cohere's /v1/embeddings, parse, return list[list[float]]
        ...
```

Then:
- Add a `cohere_api_key` field to `MnemaConfig` (and a `ConfigError` if it's missing when `embedding=cohere`).
- Register in `make_embedding` with a lazy import.
- Add tests that mock `httpx` (see `tests/test_embeddings.py` for the pattern).
- Add a `[cohere]` extra in `pyproject.toml`.

The whole change is typically <100 lines + tests.

## How to add a CLI subcommand

CLI subcommands live in `src/mnema/cli.py`. The pattern:

1. Write an `async def cmd_yourcommand(args, svc: MemoryService) -> int` —
   it calls `svc` methods and prints output. Return 0 on success.
2. Register a subparser in `_build_parser()`:
   ```python
   sp = sub.add_parser("yourcommand", help="Do X")
   sp.add_argument("--flag", ...)
   sp.set_defaults(func=cmd_yourcommand)
   ```
3. Add the command name to `_CLI_COMMANDS` in `__main__.py` so the router
   dispatches to the CLI (not the MCP server).
4. Add `--json` output if it's a read command.
5. Add tests in `tests/test_cli.py` (call the handler directly with fakes).

See `cmd_backup` / `cmd_dream` / `cmd_eval` for reference.

## How to add a REST API route

Routes live in `src/mnema/api/app.py` — every route is a thin delegation to
`MemoryService`. The pattern (contributed by @Nitjsefnie in the REST API PR):

1. Add a request schema in `src/mnema/api/schemas.py` (Pydantic model
   mirroring the service method's kwargs).
2. Add a route in `create_app()`:
   ```python
   @app.post("/your-route", response_model=YourResponse, tags=["your-tag"])
   async def your_route(body: YourRequest) -> YourResponse:
       return await svc.your_method(**body.model_dump())
   ```
3. Add tests in `tests/test_api.py` using FastAPI's `TestClient` against the
   in-memory fake service (no live server needed).

## How to add a dashboard page

The web dashboard lives in `src/mnema/dashboard/` (htmx + Jinja2Templates,
contributed by @NEMEZIZ1234). The pattern:

1. Add a Jinja2 template in `src/mnema/dashboard/templates/your_page.html`
   (extend `base.html`).
2. Add a route in `create_dashboard_app()` in `src/mnema/dashboard/app.py`:
   ```python
   @app.get("/your-page", response_class=HTMLResponse, include_in_schema=False)
   async def your_page(request: Request):
       stats = await _stats_or_none()
       return templates.TemplateResponse(
           request, "your_page.html",
           {"request": request, "stats": stats, "nav": _nav(stats)},
       )
   ```
3. For htmx partials (inline updates), use `hx-post` / `hx-get` pointing at
   a route that returns a partial template (see `_search_results.html`).
4. Note: `ruff` may flag `stats` as unused — it's used by the Jinja2
   template context, so it's already suppressed in `pyproject.toml`.

## Before you submit

- [ ] `ruff check src/ tests/` is clean.
- [ ] `pytest` passes (and you've installed the relevant `[extra]` if you touched a backend).
- [ ] `mypy src/mnema` — run it, fix what's easy, but it won't block your PR.
- [ ] New public functions have docstrings.
- [ ] If you added an MCP tool, update `SKILL.md` and the README tool table.
- [ ] If you added a CLI subcommand, add it to `_CLI_COMMANDS` in `__main__.py`.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(backends): add Weaviate backend
fix(decay): correct half-life for sub-day values
docs(readme): clarify backend selection
test(service): add scope-isolation coverage
```

## Pull requests

- Keep PRs focused — one feature or fix per PR.
- Include tests for any new behavior.
- Update docs (`README.md`, `SKILL.md`, `docs/`) when user-facing behavior changes.
- Don't bump the version yourself; maintainers do that on release.
- Open a **draft PR early** for large features — we're happy to review as you go.

## Reporting bugs

Open an issue with:

1. Mnema version (`mnema --version`)
2. Backend + embedding provider in use
3. Minimal reproduction (config + commands)
4. Expected vs actual behavior
5. Output of `mnema --doctor`

## Open issues we'd love help with

Check the [issue tracker](https://github.com/mienetic/mnema/issues) for the
full list. Look for `good first issue` and `claimed` labels. Highlights:

- **#8** — TypeScript MCP server
- **#10** — Auth + multi-tenant for HTTP transport
- **#11** — Observability (Prometheus metrics)
- **#19** — Slack / Discord bot

Thanks for helping make AI memory better! 💜
