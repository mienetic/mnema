/**
 * `chrome.storage` access — the only place the extension touches it.
 *
 * Two stores, deliberately:
 *   - `chrome.storage.sync` holds the user's settings (server URL, default
 *     scope/tags/importance), so they follow a signed-in profile.
 *   - `chrome.storage.session` holds the *pending capture* handed from the
 *     context-menu click to the popup window. It is in-memory only and dies
 *     with the browser session, which is where a page selection belongs.
 *
 * Kept free of request/validation logic — that lives in `api.js` and is unit
 * tested there.
 */

import { DEFAULT_IMPORTANCE, DEFAULT_SERVER_URL } from "./api.js";

/** Settings keys and their fallbacks. */
export const DEFAULT_SETTINGS = Object.freeze({
  serverUrl: DEFAULT_SERVER_URL,
  defaultScope: "",
  defaultTags: "",
  defaultImportance: DEFAULT_IMPORTANCE,
});

const PENDING_CAPTURE_KEY = "pendingCapture";

/**
 * Read the user's settings, with defaults filled in.
 *
 * @returns {Promise<typeof DEFAULT_SETTINGS>}
 */
export async function loadSettings() {
  const stored = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...stored };
}

/**
 * Persist a partial settings patch.
 *
 * @param {Partial<typeof DEFAULT_SETTINGS>} patch
 * @returns {Promise<void>}
 */
export async function saveSettings(patch) {
  await chrome.storage.sync.set(patch);
}

/**
 * Stash the text a context-menu click captured, for the popup to pick up.
 *
 * @param {{text: string, sourceUrl?: string, sourceTitle?: string}} capture
 * @returns {Promise<void>}
 */
export async function setPendingCapture(capture) {
  await chrome.storage.session.set({ [PENDING_CAPTURE_KEY]: capture });
}

/**
 * Take the pending capture, clearing it so a reopened popup starts clean.
 *
 * @returns {Promise<{text: string, sourceUrl?: string, sourceTitle?: string}|null>}
 */
export async function takePendingCapture() {
  const stored = await chrome.storage.session.get(PENDING_CAPTURE_KEY);
  const capture = stored[PENDING_CAPTURE_KEY] ?? null;
  if (capture) {
    await chrome.storage.session.remove(PENDING_CAPTURE_KEY);
  }
  return capture;
}
