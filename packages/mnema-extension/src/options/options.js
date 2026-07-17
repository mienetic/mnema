/**
 * Options controller: pick the Mnema server and the capture-form defaults.
 *
 * Only localhost is in `host_permissions` at install time. Pointing the
 * extension at any other host therefore needs an optional-permission grant,
 * which Chrome only allows from a user gesture — so `permissions.request` is
 * fired straight from the submit handler, before any `await` that would spend
 * the gesture.
 */

import { MnemaApiError, normalizeServerUrl, originPattern, statsEndpoint } from "../lib/api.js";
import { DEFAULT_SETTINGS, loadSettings, saveSettings } from "../lib/storage.js";

const els = {
  form: document.getElementById("options-form"),
  serverUrl: document.getElementById("server-url"),
  defaultScope: document.getElementById("default-scope"),
  defaultTags: document.getElementById("default-tags"),
  defaultImportance: document.getElementById("default-importance"),
  defaultImportanceValue: document.getElementById("default-importance-value"),
  save: document.getElementById("save"),
  test: document.getElementById("test"),
  status: document.getElementById("status"),
};

/**
 * @param {string} message
 * @param {"success"|"error"|"info"} kind
 */
function setStatus(message, kind) {
  els.status.textContent = message;
  els.status.className = kind;
  els.status.hidden = false;
}

async function initialize() {
  const settings = await loadSettings();
  els.serverUrl.value = settings.serverUrl;
  els.defaultScope.value = settings.defaultScope;
  els.defaultTags.value = settings.defaultTags;
  els.defaultImportance.value = String(settings.defaultImportance);
  els.defaultImportanceValue.textContent = String(settings.defaultImportance);
}

els.defaultImportance.addEventListener("input", () => {
  els.defaultImportanceValue.textContent = els.defaultImportance.value;
});

els.form.addEventListener("submit", (event) => {
  event.preventDefault();

  let serverUrl;
  let pattern;
  try {
    serverUrl = normalizeServerUrl(els.serverUrl.value);
    pattern = originPattern(serverUrl);
  } catch (error) {
    setStatus(error instanceof MnemaApiError ? error.message : String(error), "error");
    return;
  }

  // Must be the first thing in the gesture — no `await` before it.
  chrome.permissions.request({ origins: [pattern] }, async (granted) => {
    if (!granted) {
      setStatus(
        `Not saved: without permission for ${pattern} the extension cannot reach that server.`,
        "error",
      );
      return;
    }
    try {
      await saveSettings({
        serverUrl,
        defaultScope: els.defaultScope.value.trim(),
        defaultTags: els.defaultTags.value.trim(),
        defaultImportance: Number(els.defaultImportance.value),
      });
      els.serverUrl.value = serverUrl;
      setStatus(`Saved. Capturing to ${serverUrl}`, "success");
    } catch (error) {
      setStatus(`Could not save settings: ${error?.message ?? error}`, "error");
    }
  });
});

els.test.addEventListener("click", async () => {
  els.test.disabled = true;
  setStatus("Testing…", "info");
  try {
    const endpoint = statsEndpoint(els.serverUrl.value);
    const response = await fetch(endpoint);
    if (!response.ok) {
      setStatus(`Server answered HTTP ${response.status} on ${endpoint}`, "error");
      return;
    }
    const stats = await response.json();
    setStatus(
      `Connected — ${stats.total_memories} memories, backend "${stats.backend}", ` +
        `embeddings "${stats.embedding_provider}".`,
      "success",
    );
  } catch (error) {
    const message =
      error instanceof MnemaApiError
        ? error.message
        : `Could not reach the server (is \`mnema serve\` running, and is this host permitted?): ${
            error?.message ?? error
          }`;
    setStatus(message, "error");
  } finally {
    els.test.disabled = false;
  }
});

initialize().catch((error) => {
  setStatus(`Could not load settings: ${error?.message ?? error}`, "error");
  els.serverUrl.value = DEFAULT_SETTINGS.serverUrl;
});
