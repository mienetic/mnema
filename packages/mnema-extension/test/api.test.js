/**
 * Tests for the pure API layer (`src/lib/api.js`).
 *
 * These pin the extension to the *implemented* REST contract in
 * `packages/mnema-python/src/mnema/api/` — `POST /memories` with a
 * `CreateMemoryRequest` body (`text`, `scope?`, `tags?`, `importance`,
 * `metadata?`) returning `201` + a `MemoryRecord`, `400`/`404`/`422` carrying
 * a `detail` payload. Nothing here talks to `chrome.*` or the network: the
 * fetch implementation is injected, so every assertion is on real logic.
 *
 * Run with the repo's Node test runner: `npm test` (i.e. `node --test test/`).
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  DEFAULT_IMPORTANCE,
  DEFAULT_SERVER_URL,
  MAX_SCOPE_LENGTH,
  MAX_TAGS,
  MAX_TEXT_LENGTH,
  MnemaApiError,
  buildCreateMemoryRequest,
  describeApiError,
  memoriesEndpoint,
  normalizeServerUrl,
  originPattern,
  parseTags,
  saveMemory,
  statsEndpoint,
} from "../src/lib/api.js";

// ---------------------------------------------------------------------------
// normalizeServerUrl
// ---------------------------------------------------------------------------
describe("normalizeServerUrl", () => {
  it("keeps a plain origin untouched", () => {
    assert.equal(normalizeServerUrl("http://127.0.0.1:8000"), "http://127.0.0.1:8000");
  });

  it("trims surrounding whitespace", () => {
    assert.equal(normalizeServerUrl("  http://127.0.0.1:8000  "), "http://127.0.0.1:8000");
  });

  it("strips trailing slashes so the endpoint never doubles up", () => {
    assert.equal(normalizeServerUrl("http://127.0.0.1:8000/"), "http://127.0.0.1:8000");
    assert.equal(normalizeServerUrl("http://127.0.0.1:8000///"), "http://127.0.0.1:8000");
  });

  it("preserves a base path (server behind a reverse-proxy prefix)", () => {
    assert.equal(normalizeServerUrl("https://mnema.example.com/api/"), "https://mnema.example.com/api");
  });

  it("accepts https and non-localhost hosts", () => {
    assert.equal(normalizeServerUrl("https://mnema.example.com"), "https://mnema.example.com");
  });

  it("drops query and fragment", () => {
    assert.equal(normalizeServerUrl("http://localhost:8000/?a=1#x"), "http://localhost:8000");
  });

  it("rejects an empty URL", () => {
    assert.throws(() => normalizeServerUrl("   "), MnemaApiError);
  });

  it("rejects a non-URL string", () => {
    assert.throws(() => normalizeServerUrl("not a url"), MnemaApiError);
  });

  it("rejects non-http(s) schemes", () => {
    assert.throws(() => normalizeServerUrl("ftp://example.com"), MnemaApiError);
    assert.throws(() => normalizeServerUrl("javascript:alert(1)"), MnemaApiError);
  });
});

// ---------------------------------------------------------------------------
// memoriesEndpoint
// ---------------------------------------------------------------------------
describe("memoriesEndpoint", () => {
  it("targets the implemented POST /memories route", () => {
    assert.equal(memoriesEndpoint("http://127.0.0.1:8000"), "http://127.0.0.1:8000/memories");
  });

  it("normalizes before appending", () => {
    assert.equal(memoriesEndpoint("http://127.0.0.1:8000/"), "http://127.0.0.1:8000/memories");
  });

  it("respects a base path", () => {
    assert.equal(memoriesEndpoint("https://x.example/api"), "https://x.example/api/memories");
  });

  it("defaults to the server's own default bind address", () => {
    // mnema config.py: http_host=127.0.0.1, http_port=8000.
    assert.equal(DEFAULT_SERVER_URL, "http://127.0.0.1:8000");
  });
});

// ---------------------------------------------------------------------------
// statsEndpoint
// ---------------------------------------------------------------------------
describe("statsEndpoint", () => {
  it("targets the implemented GET /stats route", () => {
    assert.equal(statsEndpoint("http://127.0.0.1:8000/"), "http://127.0.0.1:8000/stats");
  });

  it("respects a base path", () => {
    assert.equal(statsEndpoint("https://x.example/api"), "https://x.example/api/stats");
  });
});

// ---------------------------------------------------------------------------
// originPattern
// ---------------------------------------------------------------------------
describe("originPattern", () => {
  it("builds a chrome match pattern from the origin", () => {
    assert.equal(originPattern("http://127.0.0.1:8000"), "http://127.0.0.1:8000/*");
    assert.equal(originPattern("https://mnema.example.com"), "https://mnema.example.com/*");
  });

  it("drops any base path — permissions are per-origin, not per-path", () => {
    assert.equal(originPattern("https://mnema.example.com/api/v1"), "https://mnema.example.com/*");
  });

  it("rejects an unusable URL rather than returning a bogus pattern", () => {
    assert.throws(() => originPattern("nope"), MnemaApiError);
  });
});

// ---------------------------------------------------------------------------
// parseTags
// ---------------------------------------------------------------------------
describe("parseTags", () => {
  it("splits on commas and trims", () => {
    assert.deepEqual(parseTags("a, b ,c"), ["a", "b", "c"]);
  });

  it("drops empty fragments", () => {
    assert.deepEqual(parseTags("a,,b,   ,"), ["a", "b"]);
  });

  it("de-duplicates while preserving order", () => {
    assert.deepEqual(parseTags("b, a, b"), ["b", "a"]);
  });

  it("returns an empty array for blank input", () => {
    assert.deepEqual(parseTags(""), []);
    assert.deepEqual(parseTags(null), []);
    assert.deepEqual(parseTags(undefined), []);
  });

  it("passes an array through, trimmed and de-duplicated", () => {
    assert.deepEqual(parseTags([" a ", "a", "b"]), ["a", "b"]);
  });
});

// ---------------------------------------------------------------------------
// buildCreateMemoryRequest
// ---------------------------------------------------------------------------
describe("buildCreateMemoryRequest", () => {
  it("builds the minimal body the API requires", () => {
    const body = buildCreateMemoryRequest({ text: "Alice likes tea" });
    assert.deepEqual(body, { text: "Alice likes tea", importance: DEFAULT_IMPORTANCE });
  });

  it("defaults importance to Importance.NORMAL (5)", () => {
    assert.equal(DEFAULT_IMPORTANCE, 5);
    assert.equal(buildCreateMemoryRequest({ text: "x" }).importance, 5);
  });

  it("trims the text", () => {
    assert.equal(buildCreateMemoryRequest({ text: "  spaced  " }).text, "spaced");
  });

  it("includes scope, tags and metadata when given", () => {
    const body = buildCreateMemoryRequest({
      text: "fact",
      scope: "user:alice",
      tags: ["docs", "api"],
      importance: 8,
      metadata: { source_url: "https://example.com" },
    });
    assert.deepEqual(body, {
      text: "fact",
      importance: 8,
      scope: "user:alice",
      tags: ["docs", "api"],
      metadata: { source_url: "https://example.com" },
    });
  });

  it("omits a blank scope so the server applies its own default_scope", () => {
    const body = buildCreateMemoryRequest({ text: "fact", scope: "   " });
    assert.ok(!("scope" in body), "blank scope must not be sent");
  });

  it("omits empty tags rather than sending []", () => {
    const body = buildCreateMemoryRequest({ text: "fact", tags: [] });
    assert.ok(!("tags" in body), "empty tags must not be sent");
  });

  it("omits empty metadata rather than sending {}", () => {
    const body = buildCreateMemoryRequest({ text: "fact", metadata: {} });
    assert.ok(!("metadata" in body), "empty metadata must not be sent");
  });

  it("accepts a tags string and parses it", () => {
    assert.deepEqual(buildCreateMemoryRequest({ text: "f", tags: "a, b" }).tags, ["a", "b"]);
  });

  it("rejects empty text (API requires min_length=1)", () => {
    assert.throws(() => buildCreateMemoryRequest({ text: "   " }), MnemaApiError);
    assert.throws(() => buildCreateMemoryRequest({}), MnemaApiError);
  });

  it("rejects text over the API's 32_000 max_length", () => {
    assert.equal(MAX_TEXT_LENGTH, 32000);
    const tooLong = "x".repeat(MAX_TEXT_LENGTH + 1);
    assert.throws(() => buildCreateMemoryRequest({ text: tooLong }), MnemaApiError);
    // Exactly at the limit is fine.
    assert.equal(buildCreateMemoryRequest({ text: "x".repeat(MAX_TEXT_LENGTH) }).text.length, MAX_TEXT_LENGTH);
  });

  it("rejects importance outside the API's 1..10 range", () => {
    assert.throws(() => buildCreateMemoryRequest({ text: "f", importance: 0 }), MnemaApiError);
    assert.throws(() => buildCreateMemoryRequest({ text: "f", importance: 11 }), MnemaApiError);
    assert.throws(() => buildCreateMemoryRequest({ text: "f", importance: 2.5 }), MnemaApiError);
    assert.throws(() => buildCreateMemoryRequest({ text: "f", importance: "high" }), MnemaApiError);
  });

  it("accepts the 1 and 10 boundaries", () => {
    assert.equal(buildCreateMemoryRequest({ text: "f", importance: 1 }).importance, 1);
    assert.equal(buildCreateMemoryRequest({ text: "f", importance: 10 }).importance, 10);
  });

  it("accepts a numeric importance string from a form field", () => {
    assert.equal(buildCreateMemoryRequest({ text: "f", importance: "8" }).importance, 8);
  });

  it("rejects a scope containing whitespace (models.Scope forbids it)", () => {
    assert.throws(() => buildCreateMemoryRequest({ text: "f", scope: "user alice" }), MnemaApiError);
  });

  it("rejects a scope over 200 characters (models.Scope caps value at 200)", () => {
    assert.equal(MAX_SCOPE_LENGTH, 200);
    const tooLong = "a".repeat(MAX_SCOPE_LENGTH + 1);
    assert.throws(
      () => buildCreateMemoryRequest({ text: "f", scope: tooLong }),
      (err) =>
        err instanceof MnemaApiError &&
        // The point of the client-side check: a readable sentence instead of the
        // server's raw pydantic dump.
        /at most 200/.test(err.message) &&
        !/pydantic/.test(err.message),
    );
    // Exactly at the limit still goes through.
    assert.equal(
      buildCreateMemoryRequest({ text: "f", scope: "a".repeat(MAX_SCOPE_LENGTH) }).scope.length,
      MAX_SCOPE_LENGTH,
    );
  });

  it("rejects more than 20 tags (models.Memory caps tags at 20)", () => {
    assert.equal(MAX_TAGS, 20);
    const tags = Array.from({ length: MAX_TAGS + 1 }, (_, i) => `t${i}`);
    assert.throws(() => buildCreateMemoryRequest({ text: "f", tags }), MnemaApiError);
    // Exactly 20 is fine.
    assert.equal(buildCreateMemoryRequest({ text: "f", tags: tags.slice(0, MAX_TAGS) }).tags.length, MAX_TAGS);
  });
});

// ---------------------------------------------------------------------------
// describeApiError
// ---------------------------------------------------------------------------
describe("describeApiError", () => {
  it("renders a 422 pydantic validation payload field-by-field", () => {
    const payload = {
      detail: [{ loc: ["body", "text"], msg: "Field required", type: "missing" }],
    };
    assert.equal(describeApiError(422, payload), "text: Field required");
  });

  it("joins multiple 422 errors", () => {
    const payload = {
      detail: [
        { loc: ["body", "text"], msg: "Field required" },
        { loc: ["body", "importance"], msg: "Input should be less than or equal to 10" },
      ],
    };
    assert.equal(
      describeApiError(422, payload),
      "text: Field required; importance: Input should be less than or equal to 10",
    );
  });

  it("renders a 400 ScopeError detail string", () => {
    assert.equal(
      describeApiError(400, { detail: "scope must not contain whitespace" }),
      "scope must not contain whitespace",
    );
  });

  it("renders a 404 detail string", () => {
    assert.equal(describeApiError(404, { detail: "Memory not found: 'abc'" }), "Memory not found: 'abc'");
  });

  it("falls back to the status code when the payload is not JSON/has no detail", () => {
    assert.equal(describeApiError(500, null), "Server returned HTTP 500");
    assert.equal(describeApiError(503, {}), "Server returned HTTP 503");
  });
});

// ---------------------------------------------------------------------------
// saveMemory
// ---------------------------------------------------------------------------
describe("saveMemory", () => {
  const okResponse = (record) => ({
    ok: true,
    status: 201,
    json: async () => record,
  });

  it("POSTs JSON to <server>/memories and returns the created record", async () => {
    const calls = [];
    const fetchImpl = async (url, init) => {
      calls.push({ url, init });
      return okResponse({ id: "abc123", text: "fact", scope: "global" });
    };

    const record = await saveMemory(
      { text: "fact", scope: "user:alice", tags: "a,b", importance: 8 },
      { serverUrl: "http://127.0.0.1:8000/", fetchImpl },
    );

    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "http://127.0.0.1:8000/memories");
    assert.equal(calls[0].init.method, "POST");
    assert.equal(calls[0].init.headers["Content-Type"], "application/json");
    assert.deepEqual(JSON.parse(calls[0].init.body), {
      text: "fact",
      scope: "user:alice",
      tags: ["a", "b"],
      importance: 8,
    });
    assert.equal(record.id, "abc123");
  });

  it("throws MnemaApiError carrying the server's message on a 422", async () => {
    const fetchImpl = async () => ({
      ok: false,
      status: 422,
      json: async () => ({ detail: [{ loc: ["body", "text"], msg: "Field required" }] }),
    });

    await assert.rejects(
      () => saveMemory({ text: "fact" }, { serverUrl: DEFAULT_SERVER_URL, fetchImpl }),
      (err) => {
        assert.ok(err instanceof MnemaApiError);
        assert.equal(err.status, 422);
        assert.match(err.message, /text: Field required/);
        return true;
      },
    );
  });

  it("throws MnemaApiError on a 400 scope rejection", async () => {
    const fetchImpl = async () => ({
      ok: false,
      status: 400,
      json: async () => ({ detail: "scope must not contain whitespace" }),
    });

    await assert.rejects(
      () => saveMemory({ text: "fact" }, { serverUrl: DEFAULT_SERVER_URL, fetchImpl }),
      (err) => err instanceof MnemaApiError && err.status === 400,
    );
  });

  it("survives a non-JSON error body (e.g. a proxy's HTML 502)", async () => {
    const fetchImpl = async () => ({
      ok: false,
      status: 502,
      json: async () => {
        throw new SyntaxError("Unexpected token <");
      },
    });

    await assert.rejects(
      () => saveMemory({ text: "fact" }, { serverUrl: DEFAULT_SERVER_URL, fetchImpl }),
      (err) => err instanceof MnemaApiError && err.status === 502 && /HTTP 502/.test(err.message),
    );
  });

  it("turns a network failure into a MnemaApiError mentioning the server", async () => {
    const fetchImpl = async () => {
      throw new TypeError("Failed to fetch");
    };

    await assert.rejects(
      () => saveMemory({ text: "fact" }, { serverUrl: "http://127.0.0.1:9999", fetchImpl }),
      (err) => {
        assert.ok(err instanceof MnemaApiError);
        assert.equal(err.status, null);
        assert.match(err.message, /http:\/\/127\.0\.0\.1:9999/);
        return true;
      },
    );
  });

  it("does not fire a request when the form is invalid", async () => {
    let called = false;
    const fetchImpl = async () => {
      called = true;
      return okResponse({});
    };

    await assert.rejects(
      () => saveMemory({ text: "" }, { serverUrl: DEFAULT_SERVER_URL, fetchImpl }),
      MnemaApiError,
    );
    assert.equal(called, false, "invalid form must not reach the network");
  });

  it("does not fire a request when the server URL is invalid", async () => {
    let called = false;
    const fetchImpl = async () => {
      called = true;
      return okResponse({});
    };

    await assert.rejects(
      () => saveMemory({ text: "fact" }, { serverUrl: "nope", fetchImpl }),
      MnemaApiError,
    );
    assert.equal(called, false, "invalid server URL must not reach the network");
  });
});
