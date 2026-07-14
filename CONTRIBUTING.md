# Contributing to Mnema

Thanks for your interest in improving Mnema! 🧠

This project welcomes contributions of all kinds — bug reports, fixes, new
backends/embedding providers, docs, and evals. The bar is "make AI memory
better for everyone."

## Code of conduct

Be kind. Assume good intent. Disagree about ideas, not people. The
[GitHub community guidelines](https://docs.github.com/en/site-policy/github-terms/github-community-guidelines)
apply.

## Getting set up

```bash
git clone https://github.com/mienetic/mnema.git
cd mnema/packages/mnema-python

# Install with all optional deps + dev tooling
uv pip install -e '.[all,dev]'

# Verify
pytest
ruff check .
mypy src/mnema
```

You'll need Python 3.10+ and (recommended) [`uv`](https://docs.astral.sh/uv/).
The test suite automatically skips backend tests whose optional dependency
isn't installed, so a minimal install still runs the core + service tests.

## Project layout

- `src/mnema/` — the package
  - `backends/` — vector stores (one file each: `chroma.py`, `qdrant.py`, `sqlite_vec.py`)
  - `embeddings/` — embedding providers (`sentence_transformers.py`, `openai.py`)
  - `tools/` — the 10 MCP tools, one concern per file
  - `service.py` — orchestration (the only place backends + embeddings meet)
  - `decay.py`, `summarize.py` — pure functions, easy to unit-test
  - `sdk.py` — programmatic Python client
  - `server.py` — FastMCP bootstrap + lifespan
- `tests/` — pytest; `fakes.py` has the in-memory backend + hashing embedding

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
    async def get(self, memory_id) -> MemoryRecord | None
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

Here's a concrete walk-through you can follow for any new backend.

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

**6. Verify**: `ruff check . && pytest -m 'not openai' && mnema --doctor --fix`.

## How to add a new embedding provider

1. Create `src/mnema/embeddings/yourprovider.py` implementing `EmbeddingProvider`.
2. Register in `embeddings/__init__.py::make_embedding`.
3. Add an optional-dependency entry + tests.

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

## Before you submit

- [ ] `pytest` passes (and you've installed the relevant `[extra]` if you touched a backend).
- [ ] `ruff check .` is clean.
- [ ] `mypy src/mnema` is clean (strict mode).
- [ ] New public functions have docstrings.
- [ ] If you added a tool, update `SKILL.md` and the README tool table.

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

## Reporting bugs

Open an issue with:

1. Mnema version (`mnema --version`)
2. Backend + embedding provider in use
3. Minimal reproduction (config + commands)
4. Expected vs actual behavior
5. Logs (set `MNEMA_LOG_LEVEL=DEBUG` if helpful)

## Feature ideas we'd love help with

- TypeScript server (`packages/mnema-ts/`)
- CLI (`packages/mnema-cli/`)
- More backends: Weaviate, pgvector, LanceDB
- More embedding providers: Cohere, Voyage, Nomic, Ollama
- A web dashboard for browsing memories
- An evaluation harness with the evals in `docs/evaluations.xml`

Thanks for helping make AI memory better! 💜
