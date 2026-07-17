---
name: mnema
description: Use the Mnema MCP server to give the AI long-term, searchable memory. Use it whenever the user shares durable facts, preferences, decisions, or context worth recalling in future sessions. Mnema stores memories in a vector database and recalls them with semantic + hybrid search, with decay scoring and summarization so the store stays useful over time. Invoke `mnema_remember` when a durable fact appears; call `mnema_recall`/`mnema_search` at the start of a task to fetch relevant context; use `mnema_summarize` + `mnema_apply_decay` periodically to keep the store compact.
---

# Mnema — Long-term Memory Skill

Mnema (μνῆμα, Greek for "memory") is an MCP server that gives you persistent,
searchable memory across sessions. It solves the context-window problem: you
don't have to cram every relevant fact into one conversation — store it once,
recall it later by meaning.

## When to use

Use Mnema tools when you detect **durable** information that will matter
beyond the current turn:

- The user states a preference ("I prefer dark mode", "I use Dvorak")
- A decision is made ("we're using Postgres, not MySQL")
- A stable fact about the user, project, or environment is established
- The user explicitly says "remember this"

**Do not** use Mnema for transient, single-conversation details (the current
file being edited, today's error message). Those belong in context, not memory.

## ⚡ Proactive memory workflow (important)

Don't wait to be asked. Use memory proactively in every conversation:

### 1. Auto-recall — at the START of a substantive task

Before answering any non-trivial question, **search memory first** to see if
you already know something relevant:

```
mnema_search("<the user's question or task topic>")
```

- If you find relevant memories → weave them into your answer, cite by id.
- If nothing relevant → proceed normally. Don't force a connection that isn't there.

This is what makes memory feel "real" to the user — they don't have to ask
"do you remember…?", you just know.

### 2. Auto-remember — when a durable fact APPEARS

Whenever the conversation reveals a durable fact (preference, decision, config
value, relationship), store it **immediately** — don't wait until the end:

```
mnema_remember("<the fact>", tags=[...], importance=N, scope="user:...")
```

Signals that a fact is durable:
- "I always…" / "I prefer…" / "I use…" → preference (importance 5–8)
- "We decided to…" / "Let's go with…" → decision (importance 7–9)
- "My API key is…" / "the prod URL is…" → credential/config (importance 8–10)
- "Alice is my manager" / "Bob handles infra" → relationship (importance 5)

### 3. Periodically — keep the store healthy

- At the end of a long session, run `mnema_summarize` on busy scopes to
  condense clutter into summary memories.
- Run `mnema_apply_decay` (dry-run first) every few weeks to surface
  low-value memories for forgetting.
- Or let **Auto Dream** do both automatically: set `MNEMA_DREAM_ENABLED=true`
  and Mnema will forget decayed + plan summarization in the background while
  idle — like a brain consolidating memories during sleep. You can also run
  a single cycle manually from the terminal: `mnema dream`.
- **Backup regularly**: `mnema backup -o snapshot.tar.gz` creates a portable
  archive you can restore later with `mnema restore snapshot.tar.gz`.

## Tools

### Writing memories

```
mnema_remember(text, scope?, tags?, importance?, metadata?)
```
Store a memory. Always include:
- A clear `text` describing the fact (write it so future-you will understand
  it without the surrounding conversation)
- `tags` — keywords that will help hybrid search find it later
- `importance` — 1 (low) to 10 (critical); critical memories resist decay
- `scope` — namespace like `user:alice`, `session:abc`, `project:web`. Use a
  scope to isolate memories between users/projects/agents.

### Recalling memories

```
mnema_recall(query, scope?, limit?)        # pure semantic
mnema_search(query, scope?, tags?, limit?) # hybrid: semantic + tags + decay
```
- **At the start of a task**, call `mnema_search` with the task's topic to
  pull in relevant prior context. Cite what you find by id.
- Prefer `mnema_recall` when you don't have specific tags; `mnema_search`
  when you want to combine meaning with explicit labels.

### Managing memories

```
mnema_get_memory(id)                 # fetch + bump access counters
mnema_update_memory(id, text?, tags?, importance?, metadata?)
mnema_forget(id)                     # delete one
mnema_forget_scope(scope)            # delete a whole namespace
mnema_list_scopes()                  # enumerate namespaces + counts
mnema_stats()                        # store totals + config
```

### Keeping the store healthy

```
mnema_summarize(scope)               # plan: cluster → summary memories
mnema_apply_decay(scope?, threshold?, dry_run?)  # find/forget low-value
```

Mnema never calls an LLM on its own. `mnema_summarize` returns a *plan* and
a prompt — **you** execute it by writing summaries back with
`mnema_remember`, then forgetting the originals with `mnema_forget`.

## Recommended workflow

**1. On a new conversation**, recall first:

```
mnema_search("the user's current project and preferences", scope="user:alice", limit=5)
```

**2. When a durable fact appears**, store it:

```
mnema_remember(
  text="Alice's deployment target is fly.io (region sin).",
  scope="project:web",
  tags=["deploy", "infra"],
  importance=8,
)
```

**3. Periodically** (e.g. end of session, or when `mnema_stats` shows a large
store), summarize to keep things compact:

```
plan = mnema_summarize(scope="session:abc")
# For each cluster: write one summary memory, then forget the members.
```

## Score interpretation

Search results have a combined `score` in `[0, 1]` made of three parts:

- `vector_score` — semantic similarity (cosine)
- `keyword_score` — tag-overlap (Jaccard)
- `decay_score` — recency × frequency × importance

With default weights (0.7 / 0.2 / 0.1), a result with `score > 0.6` is
strongly relevant; `score < 0.3` is a weak match — consider refining the
query or tags.

## Configuration (env-driven)

```
MNEMA_BACKEND=chroma|qdrant|sqlite_vec     # default chroma (embedded)
MNEMA_BACKEND_PATH=./.mnema/data           # local path or remote URL
MNEMA_EMBEDDING=local|openai               # default local (offline)
MNEMA_EMBEDDING_MODEL=all-MiniLM-L6-v2
MNEMA_DEFAULT_SCOPE=global
MNEMA_DECAY_HALF_LIFE_DAYS=30
```

## Anti-patterns

- ❌ Storing every message verbatim — that's a chat log, not memory. Store
  *distilled facts*.
- ❌ Using `global` scope for user-specific data — it leaks across users.
- ❌ Calling `mnema_apply_decay` with `dry_run=false` without reviewing
  candidates first.
- ❌ Treating `score` as a probability. It's a ranking signal, not a
  confidence.
