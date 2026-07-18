/**
 * Pure API layer for the Mnema extension.
 *
 * This module owns every rule that decides *what* to send to the Mnema server
 * and *how* to read what comes back — URL normalization, request-body building,
 * client-side validation that mirrors the server's pydantic models, and error
 * mapping. It deliberately touches neither `chrome.*` nor the network directly:
 * `saveMemory` takes an injected `fetchImpl`, so the whole contract is unit
 * testable without a browser or a running server.
 *
 * The validation limits below are pinned to the implemented REST contract in
 * `packages/mnema-python/src/mnema/` (see `models.py` / `config.py`): text is
 * `1..32_000` chars, importance is an integer `1..10` (default `NORMAL = 5`),
 * a scope is whitespace-free and at most `200` chars, and a memory carries at
 * most `20` tags.
 */

/** Server default bind address (mnema config.py: http_host=127.0.0.1, http_port=8000). */
export const DEFAULT_SERVER_URL = "http://127.0.0.1:8000";

/** Importance.NORMAL — the value the server assigns when none is given. */
export const DEFAULT_IMPORTANCE = 5;

/** CreateMemoryRequest.text max_length. */
export const MAX_TEXT_LENGTH = 32000;

/** models.Scope caps a scope value at 200 characters. */
export const MAX_SCOPE_LENGTH = 200;

/** models.Memory caps a memory at 20 tags. */
export const MAX_TAGS = 20;

/**
 * An error whose `message` is fit to show a human and whose `status` carries the
 * HTTP status that produced it (or `null` for a client-side / network failure).
 */
export class MnemaApiError extends Error {
  /**
   * @param {string} message
   * @param {number|null} [status]
   */
  constructor(message, status = null) {
    super(message);
    this.name = "MnemaApiError";
    this.status = status;
  }
}

/**
 * Normalize a user-entered server URL to a bare, trailing-slash-free origin
 * (plus any reverse-proxy base path), dropping query and fragment.
 *
 * @param {string} value
 * @returns {string}
 * @throws {MnemaApiError} when the URL is blank, unparseable, or not http(s).
 */
export function normalizeServerUrl(value) {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) {
    throw new MnemaApiError("Enter a server URL.");
  }

  let url;
  try {
    url = new URL(trimmed);
  } catch {
    throw new MnemaApiError(`"${trimmed}" is not a valid URL.`);
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new MnemaApiError("The server URL must start with http:// or https://.");
  }

  // origin + pathname keeps a proxy base path but drops query/fragment; the
  // trailing-slash strip keeps the appended endpoint from doubling up.
  return `${url.origin}${url.pathname}`.replace(/\/+$/, "");
}

/**
 * The `POST /memories` endpoint for a given server URL.
 *
 * @param {string} serverUrl
 * @returns {string}
 */
export function memoriesEndpoint(serverUrl) {
  return `${normalizeServerUrl(serverUrl)}/memories`;
}

/**
 * The `GET /stats` endpoint for a given server URL.
 *
 * @param {string} serverUrl
 * @returns {string}
 */
export function statsEndpoint(serverUrl) {
  return `${normalizeServerUrl(serverUrl)}/stats`;
}

/**
 * A Chrome host-permission match pattern for the server's origin. Permissions
 * are per-origin, so any base path is dropped.
 *
 * @param {string} serverUrl
 * @returns {string}
 * @throws {MnemaApiError} when the URL cannot be parsed.
 */
export function originPattern(serverUrl) {
  let url;
  try {
    url = new URL(String(serverUrl ?? "").trim());
  } catch {
    throw new MnemaApiError(`"${serverUrl}" is not a valid URL.`);
  }
  return `${url.origin}/*`;
}

/**
 * Parse tags from a comma-separated string (or pass an array through): trim
 * each, drop the blanks, de-duplicate while preserving first-seen order.
 *
 * @param {string|string[]|null|undefined} input
 * @returns {string[]}
 */
export function parseTags(input) {
  if (input == null) {
    return [];
  }
  const raw = Array.isArray(input) ? input : String(input).split(",");
  const seen = new Set();
  const tags = [];
  for (const item of raw) {
    const tag = String(item).trim();
    if (!tag || seen.has(tag)) {
      continue;
    }
    seen.add(tag);
    tags.push(tag);
  }
  return tags;
}

/**
 * Coerce and validate the importance field: an integer in `1..10`, defaulting
 * to {@link DEFAULT_IMPORTANCE}. Accepts a numeric string from a form field.
 *
 * @param {number|string|null|undefined} value
 * @returns {number}
 * @throws {MnemaApiError}
 */
function normalizeImportance(value) {
  if (value === undefined || value === null || value === "") {
    return DEFAULT_IMPORTANCE;
  }
  const importance = typeof value === "number" ? value : Number(value);
  if (!Number.isInteger(importance) || importance < 1 || importance > 10) {
    throw new MnemaApiError("Importance must be a whole number between 1 and 10.");
  }
  return importance;
}

/**
 * Build the `CreateMemoryRequest` body from raw form values, validating each
 * field against the server's contract and omitting optional fields that are
 * empty so the server can apply its own defaults.
 *
 * @param {{
 *   text?: string,
 *   scope?: string,
 *   tags?: string|string[],
 *   importance?: number|string,
 *   metadata?: Record<string, unknown>,
 * }} [input]
 * @returns {Record<string, unknown>}
 * @throws {MnemaApiError}
 */
export function buildCreateMemoryRequest(input = {}) {
  const text = String(input.text ?? "").trim();
  if (text.length < 1) {
    throw new MnemaApiError("Enter some text to remember.");
  }
  if (text.length > MAX_TEXT_LENGTH) {
    throw new MnemaApiError(`Text must be at most ${MAX_TEXT_LENGTH} characters.`);
  }

  const body = { text, importance: normalizeImportance(input.importance) };

  if (input.scope !== undefined && input.scope !== null) {
    const scope = String(input.scope).trim();
    if (scope) {
      if (/\s/.test(scope)) {
        throw new MnemaApiError("Scope must not contain whitespace.");
      }
      if (scope.length > MAX_SCOPE_LENGTH) {
        throw new MnemaApiError(`Scope must be at most ${MAX_SCOPE_LENGTH} characters.`);
      }
      body.scope = scope;
    }
  }

  const tags = parseTags(input.tags);
  if (tags.length > MAX_TAGS) {
    throw new MnemaApiError(`A memory may have at most ${MAX_TAGS} tags.`);
  }
  if (tags.length) {
    body.tags = tags;
  }

  if (
    input.metadata != null &&
    typeof input.metadata === "object" &&
    Object.keys(input.metadata).length
  ) {
    body.metadata = input.metadata;
  }

  return body;
}

/**
 * Turn a server error response into a single human-readable sentence.
 *
 * @param {number} status
 * @param {unknown} payload  The parsed JSON body, or `null` when it wasn't JSON.
 * @returns {string}
 */
export function describeApiError(status, payload) {
  const detail = payload && typeof payload === "object" ? payload.detail : undefined;

  if (Array.isArray(detail)) {
    const parts = detail
      .map((entry) => {
        const field = Array.isArray(entry.loc) && entry.loc.length
          ? entry.loc[entry.loc.length - 1]
          : "";
        return field ? `${field}: ${entry.msg}` : String(entry.msg ?? "");
      })
      .filter(Boolean);
    if (parts.length) {
      return parts.join("; ");
    }
  } else if (typeof detail === "string" && detail) {
    return detail;
  }

  return `Server returned HTTP ${status}`;
}

/**
 * Validate a capture, POST it to `<server>/memories`, and return the created
 * `MemoryRecord`. Nothing reaches the network until both the form and the
 * server URL pass client-side validation.
 *
 * @param {Parameters<typeof buildCreateMemoryRequest>[0]} input
 * @param {{ serverUrl: string, fetchImpl?: typeof fetch }} options
 * @returns {Promise<Record<string, unknown>>}
 * @throws {MnemaApiError}
 */
export async function saveMemory(input, { serverUrl, fetchImpl = fetch } = {}) {
  // Both of these throw MnemaApiError *before* any request is fired.
  const endpoint = memoriesEndpoint(serverUrl);
  const body = buildCreateMemoryRequest(input);

  let response;
  try {
    response = await fetchImpl(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    throw new MnemaApiError(
      `Could not reach the Mnema server at ${normalizeServerUrl(serverUrl)}: ${error?.message ?? error}`,
      null,
    );
  }

  if (!response.ok) {
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new MnemaApiError(describeApiError(response.status, payload), response.status);
  }

  return response.json();
}
