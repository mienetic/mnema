# Mnema Browser Extension — "Remember this"

> 🧠 Select text on any page → right-click → **Remember this** → it's in your
> long-term memory.

A Manifest V3 extension (Chrome/Edge/Chromium; Firefox 115+) that captures
facts straight off the pages you're reading into Mnema, via the REST API that
`mnema serve` exposes. No build step, no dependencies — vanilla ES modules.

The full project README lives at the repo root:
**[../../README.md](../../README.md)**.

## Prerequisites

The extension is a thin client over the REST API, so a server has to be
running (the `[api]` extra provides FastAPI + uvicorn):

```bash
cd packages/mnema-python
uv pip install -e '.[api]'
mnema serve                 # http://127.0.0.1:8000 by default
```

## Install (unpacked)

**Chrome / Edge / Chromium**

1. Open `chrome://extensions`.
2. Turn on **Developer mode**.
3. **Load unpacked** → select this `packages/mnema-extension/` directory.

**Firefox** (temporary install)

1. Open `about:debugging#/runtime/this-firefox`.
2. **Load Temporary Add-on…** → select `manifest.json`.

## Use

1. Select text on any page.
2. Right-click → **Remember this**.
3. The capture form opens pre-filled with the selection. Adjust **scope**,
   **tags** and **importance**, then **Save to Mnema**.

The toolbar icon opens the same form for a memory you type yourself.

Every save reports its outcome in the form: the created memory's scope and id
on success, or the server's own error message (a bad scope, a validation
failure, an unreachable server) on failure.

## Settings

Extension options (`chrome://extensions` → **Details** → **Extension options**):

| Setting | Default | Notes |
|---|---|---|
| Mnema server URL | `http://127.0.0.1:8000` | Matches `MNEMA_HTTP_HOST`/`MNEMA_HTTP_PORT`. A remote host or reverse-proxy path (`https://mnema.example.com/api`) works. |
| Default scope | *(blank)* | Blank lets the server apply its own `default_scope`. |
| Default tags | *(blank)* | Comma separated, max 20. |
| Default importance | `5` (`Importance.NORMAL`) | 1..10. |

Settings live in `chrome.storage.sync`. **Test connection** hits `GET /stats`
to confirm the server is reachable before you rely on it.

Only `http://localhost` and `http://127.0.0.1` are permitted at install time.
Pointing the extension at any other host triggers an optional host-permission
prompt when you save — Chrome only grants that from a click, which is why the
grant happens on **Save settings**.

> **Note:** the REST API ships no authentication and no CORS middleware, so
> point this at a Mnema you control. The extension calls the API from its own
> pages using host permissions, which is why it works without CORS — a plain
> web page could not.

## What it sends

`POST {server}/memories`, mirroring
[`CreateMemoryRequest`](../mnema-python/src/mnema/api/schemas.py):

```jsonc
{
  "text": "Mnema's decay half-life defaults to 30 days",  // required, 1..32000
  "scope": "user:alice",                                  // omitted -> server default_scope; max 200, no whitespace
  "tags": ["docs", "decay"],                              // omitted when empty, max 20
  "importance": 8,                                        // 1..10, defaults to 5
  "metadata": {                                           // omitted when empty
    "source_url": "https://example.com/docs/decay",
    "source_title": "Decay — Mnema docs",
    "captured_by": "mnema-extension"
  }
}
```

> **Importance snaps to a named level.** The API accepts any integer `1..10`,
> but the service stores the *nearest* `Importance` level — `1` (LOW), `5`
> (NORMAL), `8` (HIGH) or `10` (CRITICAL) — see `_coerce_importance` in
> [`service.py`](../mnema-python/src/mnema/service.py). Sending `7` therefore
> comes back as `8`. That's the server's behavior, not the extension's; the
> slider is 1..10 because that's what the API's contract accepts.

Source URL/title are attached only when **Save the page URL and title as
metadata** is ticked. `metadata` is never used for filtering by default — it's
there so a captured fact remembers where it came from.

## Layout

```
manifest.json                    # MV3 manifest
src/lib/api.js                   # pure REST client: build, POST, map errors (unit tested)
src/lib/storage.js               # chrome.storage.sync (settings) + .session (pending capture)
src/background/service-worker.js # "Remember this" context menu -> opens the form
src/popup/                       # capture form (popup.html/.js/.css)
src/options/                     # settings page
test/api.test.js                 # node:test suite for src/lib/api.js
```

All request building and error mapping lives in `src/lib/api.js`, which takes
its `fetch` by injection and touches no `chrome.*` API — that's what makes it
testable under plain Node.

## Tests

No dependencies and no test framework to install — the suite runs on Node's
built-in runner (Node 18+):

```bash
cd packages/mnema-extension
npm test          # node --test "test/**/*.test.js"
```

## Contributing

See the repo-root [CONTRIBUTING.md](../../CONTRIBUTING.md). For this package:

- Keep `src/lib/api.js` pure — no `chrome.*`, no ambient `fetch`. New API
  logic goes there with a test in `test/api.test.js`.
- The request shape must track
  [`api/schemas.py`](../mnema-python/src/mnema/api/schemas.py). If the API's
  constraints change, update the mirrored constants (`MAX_TEXT_LENGTH`,
  `MAX_TAGS`, importance bounds) and their tests.
- No build step. Vanilla ES modules, loaded straight from disk.

License: MIT.
