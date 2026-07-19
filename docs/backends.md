# Vector backends

Mnema ships four pluggable backends. Pick one based on your scale and
operational preferences — they all implement the same `VectorBackend`
interface.

| Backend | Embedded? | Extra dep | Default dim | Persistence | Best for |
|---|---|---|---|---|---|
| **Chroma** | ✅ in-process | `chromadb` | 384 | local dir | default, dev, single-user |
| **Qdrant** | ✅ local path / `:memory:` / remote | `qdrant-client` | 384 | local or remote | production, high scale |
| **sqlite-vec** | ✅ pure SQLite | `sqlite-vec` | 384 | SQLite file | smallest footprint |
| **pgvector** | ✅ Postgres extension | `asyncpg` + `pgvector` | 384 | Postgres | teams with existing Postgres |
| **LanceDB** | ✅ embedded columnar | `lancedb` | 384 | local files | high-performance local |

## Selecting a backend

The default install includes **Chroma** (embedded, zero-config). To use a
different backend, **reinstall with the right extras** then switch via env:

```bash
# Reinstall (from the source checkout). MNEMA_EXTRAS is a comma-separated list.
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS="qdrant" bash

# Or, if you already have the source locally:
cd ~/.mnema-src/packages/mnema-python
VIRTUAL_ENV=~/.mnema-src/.venv uv pip install -e '.[qdrant]'

# Then point Mnema at the new backend:
echo 'MNEMA_BACKEND=qdrant' >> ~/.mnema.env   # or export in your shell
mnema --doctor
```

| Extra | What it installs |
|---|---|
| `default` (= `chroma,local`) | included automatically |
| `chroma` | ChromaDB (embedded, default backend) |
| `qdrant` | Qdrant client (local or remote) |
| `sqlite_vec` | sqlite-vec loadable extension |
| `lancedb` | LanceDB embedded columnar vector DB |
| `local` | sentence-transformers (offline embeddings) |
| `openai` | OpenAI embeddings |
| `all` | everything above |

You can combine extras: `MNEMA_EXTRAS="qdrant,openai"`, or install everything
with `MNEMA_EXTRAS=all`.

---

## Chroma (default)

**Embedded, persistent, zero-config.** Active out of the box.

```
MNEMA_BACKEND=chroma
MNEMA_BACKEND_PATH=~/.mnema-data
```

- Runs in-process via `chromadb.PersistentClient`. No server to start.
- Persists to `MNEMA_BACKEND_PATH` as SQLite + parquet.
- To use a **remote** Chroma server, set `MNEMA_BACKEND_PATH=http://host:8000`.
- Cosine similarity (`hnsw:space=cosine`).

## Qdrant

**Embedded local, in-memory, or remote — production grade.**

Install with: `MNEMA_EXTRAS=qdrant bash scripts/install.sh`

Three modes selected by `MNEMA_BACKEND_PATH`:

| `MNEMA_BACKEND_PATH` | Mode | Use case |
|---|---|---|
| `:memory:` | in-process, ephemeral | tests, throwaway |
| `./qdrant-data` | local disk | single-node prod |
| `http://localhost:6333` | remote server | scaled, Dockerized |

The backend auto-creates the collection on first use and builds payload
indexes on `scope` and `tags` for fast filtering.

## sqlite-vec

**Pure SQLite + the sqlite-vec loadable extension. Smallest possible footprint.**

Install with: `MNEMA_EXTRAS=sqlite_vec bash scripts/install.sh`

```
MNEMA_BACKEND=sqlite_vec
MNEMA_BACKEND_PATH=~/.mnema-data/mnema.db
```

- Loads `sqlite-vec` into a standard `sqlite3` connection.
- Stores vectors in a `vec0` virtual table; metadata in a normal table.
- Great for constrained environments (lambdas, edge, single-binary distros).

## LanceDB

**Embedded columnar vector DB built on the Lance format. High-performance local storage.**

Install with: `MNEMA_EXTRAS=lancedb bash scripts/install.sh`

```
MNEMA_BACKEND=lancedb
MNEMA_BACKEND_PATH=~/.mnema-data
```

- Runs in-process via `lancedb.connect()`. No server to start.
- Persists to `MNEMA_BACKEND_PATH` as Lance columnar files.
- Columnar format enables fast filter pushdown and efficient scans.
- Good for larger local stores where Chroma's SQLite-backed performance may degrade.

---



## Adding your own backend

1. Create `src/mnema/backends/yourbackend.py`:

   ```python
   from mnema.backends.base import VectorBackend, BackendHit, BackendQuery
   from mnema.config import MnemaConfig
   from mnema.models import MemoryRecord

   class YourBackend(VectorBackend):
       name = "yourbackend"

       def __init__(self, config: MnemaConfig) -> None:
           ...

       async def add(self, record, embedding): ...
       async def get(self, memory_id): ...
       async def update(self, memory_id, *, text, tags, importance, metadata, embedding): ...
       async def delete(self, memory_id): ...
       async def delete_by_scope(self, scope): ...
       async def search(self, query: BackendQuery) -> list[BackendHit]: ...
       async def count(self, scope=None): ...
       async def list_scopes(self): ...
       async def iter_all(self, scope=None): ...
       async def touch(self, memory_id): ...   # optional but recommended
   ```

2. Register it in `backends/__init__.py::make_backend`.
3. Add an optional dependency in `pyproject.toml`.
4. Add a test class in `tests/test_backends.py`.
5. Update the README and this doc.

See `CONTRIBUTING.md` for the full checklist.
