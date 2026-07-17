/**
 * Popup controller: pre-fill the form from the pending capture, then save.
 *
 * All request building and error mapping lives in `../lib/api.js` (pure, unit
 * tested); this file only moves values between the DOM and that module, and
 * makes sure *every* outcome — success or failure — lands visibly in the
 * status line. A save button that silently does nothing is the one thing this
 * must never do.
 */

import { MAX_TEXT_LENGTH, MnemaApiError, saveMemory } from "../lib/api.js";
import { loadSettings, takePendingCapture } from "../lib/storage.js";

const els = {
  form: document.getElementById("capture-form"),
  text: document.getElementById("text"),
  scope: document.getElementById("scope"),
  tags: document.getElementById("tags"),
  importance: document.getElementById("importance"),
  importanceValue: document.getElementById("importance-value"),
  includeSource: document.getElementById("include-source"),
  charCount: document.getElementById("char-count"),
  save: document.getElementById("save"),
  cancel: document.getElementById("cancel"),
  status: document.getElementById("status"),
  serverLine: document.getElementById("server-line"),
  openOptions: document.getElementById("open-options"),
};

/** Where the captured text came from; attached as metadata when opted in. */
let source = { sourceUrl: "", sourceTitle: "" };

/**
 * Show a message in the status line.
 *
 * @param {string} message
 * @param {"success"|"error"|"info"} kind
 */
function setStatus(message, kind) {
  els.status.textContent = message;
  els.status.className = kind;
  els.status.hidden = false;
}

function updateCharCount() {
  const { length } = els.text.value;
  els.charCount.textContent = String(length);
  els.charCount.classList.toggle("over", length > MAX_TEXT_LENGTH);
}

/** Load settings + the pending capture into the form. */
async function initialize() {
  const settings = await loadSettings();
  els.scope.value = settings.defaultScope;
  els.tags.value = settings.defaultTags;
  els.importance.value = String(settings.defaultImportance);
  els.importanceValue.textContent = String(settings.defaultImportance);
  els.serverLine.textContent = `Server: ${settings.serverUrl}`;

  const capture = await takePendingCapture();
  if (capture) {
    els.text.value = capture.text ?? "";
    source = {
      sourceUrl: capture.sourceUrl ?? "",
      sourceTitle: capture.sourceTitle ?? "",
    };
    if (source.sourceUrl) {
      els.includeSource.parentElement.title = source.sourceUrl;
    }
  } else {
    // Opened from the toolbar with no selection pending — nothing to attribute.
    els.includeSource.checked = false;
    els.includeSource.disabled = true;
  }

  updateCharCount();
  els.text.focus();
}

/** Metadata for the request, or `{}` when the user opted out / there's none. */
function buildMetadata() {
  if (!els.includeSource.checked) {
    return {};
  }
  const metadata = {};
  if (source.sourceUrl) {
    metadata.source_url = source.sourceUrl;
  }
  if (source.sourceTitle) {
    metadata.source_title = source.sourceTitle;
  }
  if (Object.keys(metadata).length) {
    metadata.captured_by = "mnema-extension";
  }
  return metadata;
}

els.text.addEventListener("input", updateCharCount);

els.importance.addEventListener("input", () => {
  els.importanceValue.textContent = els.importance.value;
});

els.openOptions.addEventListener("click", (event) => {
  event.preventDefault();
  chrome.runtime.openOptionsPage();
});

els.cancel.addEventListener("click", () => {
  window.close();
});

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  els.save.disabled = true;
  setStatus("Saving…", "info");

  try {
    const { serverUrl } = await loadSettings();
    const record = await saveMemory(
      {
        text: els.text.value,
        scope: els.scope.value,
        tags: els.tags.value,
        importance: els.importance.value,
        metadata: buildMetadata(),
      },
      { serverUrl },
    );
    setStatus(`Saved to scope "${record.scope}" (id ${record.id.slice(0, 8)}…)`, "success");
    els.save.textContent = "Saved ✓";
    setTimeout(() => window.close(), 1200);
  } catch (error) {
    // MnemaApiError messages are written for humans; anything else is a bug in
    // this extension and still deserves to be seen rather than swallowed.
    const message =
      error instanceof MnemaApiError ? error.message : `Unexpected error: ${error?.message ?? error}`;
    setStatus(message, "error");
    els.save.disabled = false;
  }
});

initialize().catch((error) => {
  setStatus(`Could not open the capture form: ${error?.message ?? error}`, "error");
});
