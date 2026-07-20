# Embedding providers

Mnema converts text to vectors via a pluggable provider. Six ship out of
the box; more are welcome (see CONTRIBUTING).

| Provider | Mode | Dim | Needs API key? | Install extra |
|---|---|---|---|---|
| **sentence-transformers** (default) | local, offline | 384 | no | `[local]` |
| **OpenAI** | API | 1536 / 3072 | yes | `[openai]` |
| **Ollama** | local server | model-dependent (e.g. 768) | no | `[ollama]` |
| **Cohere** | API | 1024 | yes | `[cohere]` |
| **Voyage AI** | API | 1024 | yes | `[voyage]` |
| **Nomic** | API | 768 | yes | `[nomic]` |

## sentence-transformers (default)

Loads a model once at startup, then runs inference on-device. The default
`all-MiniLM-L6-v2` is small (~80 MB), fast on CPU, and good enough for most
memory use cases. **Included in the default install** — nothing extra to do.

```
MNEMA_EMBEDDING=local
MNEMA_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

**Popular alternatives** (set with `MNEMA_EMBEDDING_MODEL`):

| Model | Dim | Notes |
|---|---|---|
| `all-MiniLM-L6-v2` | 384 | default, fastest |
| `all-MiniLM-L12-v2` | 384 | slightly better quality |
| `bge-small-en-v1.5` | 384 | strong English baseline |
| `bge-base-en-v1.5` | 768 | better recall, larger |
| `paraphrase-multilingual-MiniLM-L12-v2` | 384 | multilingual |

⚠️ Changing the model after memories exist will **break** vector search
(the new vectors will have a different geometry). To switch models, run
`mnema re-embed` after updating the env vars — see
[Switching embedding models](#switching-embedding-models) below.

## OpenAI

Uses the `text-embedding-3-*` family. Supports the `dimensions` parameter
to shorten vectors (e.g. 256-d from `text-embedding-3-large`) for big
storage savings with minimal recall loss.

Reinstall with the OpenAI extra first:

```bash
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS="default,openai" bash
```

Then configure:

```bash
export MNEMA_EMBEDDING=openai
export MNEMA_EMBEDDING_MODEL=text-embedding-3-small
export MNEMA_OPENAI_API_KEY=sk-...
# Optional: point at an OpenAI-compatible proxy / Azure
# export MNEMA_OPENAI_BASE_URL=https://my-proxy.example.com/v1
# Optional: shorten vectors
# export MNEMA_EMBEDDING_DIM=256
```

| Model | Default dim | $/1M tokens |
|---|---|---|
| `text-embedding-3-small` | 1536 | $0.02 |
| `text-embedding-3-large` | 3072 | $0.13 |
| `text-embedding-ada-002` | 1536 | legacy |

## Ollama

Uses [Ollama](https://ollama.com)'s local embedding API (e.g. `nomic-embed-text`)
so embeddings run fully locally — without loading a model in-process. Great
when you already run Ollama for chat models and want to share the GPU/CPU.

Install: nothing extra is required (httpx is a core dependency). Just point
Mnema at your Ollama server:

```bash
export MNEMA_EMBEDDING=ollama
export MNEMA_EMBEDDING_MODEL=nomic-embed-text
export MNEMA_OLLAMA_URL=http://localhost:11434
```

| Model | Dim |
|---|---|
| `nomic-embed-text` | 768 |

Pull the model once with `ollama pull nomic-embed-text`.

## Cohere

Uses [Cohere](https://cohere.com)'s embedding API. The `embed-english-v3.0`
model is 1024-d and supports the `search_document` input type.

Install with:

```bash
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS="default,cohere" bash
```

Then configure:

```bash
export MNEMA_EMBEDDING=cohere
export MNEMA_EMBEDDING_MODEL=embed-english-v3.0
export MNEMA_COHERE_API_KEY=...
```

| Model | Dim |
|---|---|
| `embed-english-v3.0` | 1024 |
| `embed-english-light-v3.0` | 384 |
| `embed-multilingual-v3.0` | 1024 |

## Voyage AI

Uses the [Voyage AI](https://voyageai.com) embedding API.

```bash
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS="default,voyage" bash
export MNEMA_EMBEDDING=voyage
export MNEMA_EMBEDDING_MODEL=voyage-2
export MNEMA_VOYAGE_API_KEY=...
```

| Model | Dim |
|---|---|
| `voyage-2` | 1024 |
| `voyage-large-2` | 1536 |
| `voyage-code-2` | 1536 |

## Nomic

Uses the [Nomic](https://atlas.nomic.ai) embedding API.

```bash
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS="default,nomic" bash
export MNEMA_EMBEDDING=nomic
export MNEMA_EMBEDDING_MODEL=nomic-embed-text-v1
export MNEMA_NOMIC_API_KEY=...
```

| Model | Dim |
|---|---|
| `nomic-embed-text-v1` | 768 |
| `nomic-embed-text-v1.5` | 768 |

## Switching embedding models

When you change `MNEMA_EMBEDDING` / `MNEMA_EMBEDDING_MODEL`, existing
vectors were produced by the old model and have the wrong geometry (and
possibly a different dimension). Re-embed everything:

```bash
# 1. Reinstall with the new extra (e.g. openai)
curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh \
  | MNEMA_EXTRAS="chroma,openai" bash

# 2. Switch the config
export MNEMA_EMBEDDING=openai
export MNEMA_EMBEDDING_MODEL=text-embedding-3-small
export MNEMA_OPENAI_API_KEY=sk-...

# 3. Re-embed every memory with the new model
mnema re-embed
```

This is safe to interrupt and re-run — `mnema re-embed` processes memories
in batches and just re-embeds everything again on the next run. Restrict to
a scope with `--scope`, or tune the batch size with `--batch-size`.

## Choosing

- **Default to local** for single-user / offline / privacy-sensitive setups.
- **Use Ollama** if you already run an Ollama server and want to share its
  model cache, or want to avoid loading a model in-process.
- **Use OpenAI / Cohere / Voyage / Nomic** when you want lower per-request
  latency under load, or when running in a constrained environment where
  loading a model is expensive.

## Adding your own provider

1. Implement `EmbeddingProvider` in `src/mnema/embeddings/yourprovider.py`:

   ```python
   class YourProvider(EmbeddingProvider):
       name = "yourprovider"
       dim = ...

       def __init__(self, config: MnemaConfig) -> None: ...
       async def embed(self, texts) -> list[list[float]]: ...
   ```

2. Register it in `embeddings/__init__.py::make_embedding`.
3. Add an optional dependency + tests.
4. Update this doc + the README.
