/**
 * MV3 service worker: owns the "Remember this" context-menu item.
 *
 * Flow: the user selects text on any page -> right-click -> "Remember this".
 * We stash the selection (plus where it came from) in `chrome.storage.session`
 * and open the popup as a small window, which reads the capture back and
 * pre-fills the form. The selection travels through session storage rather
 * than the URL because it can be up to 32_000 characters — far past what a
 * query string should carry.
 *
 * `chrome.action.openPopup()` would be tidier, but it only landed in Chrome
 * 127 and is still absent in Firefox, so a popup window is the portable path.
 */

import { setPendingCapture } from "../lib/storage.js";

const MENU_ID = "mnema-remember-this";

const POPUP_WINDOW = Object.freeze({
  url: "src/popup/popup.html",
  type: "popup",
  width: 460,
  height: 620,
});

/**
 * (Re)create the context-menu item.
 *
 * `removeAll` first keeps re-installs and worker restarts idempotent —
 * `create` would otherwise throw "Cannot create item with duplicate id".
 */
function installContextMenu() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: MENU_ID,
      title: "Remember this",
      contexts: ["selection"],
    });
  });
}

chrome.runtime.onInstalled.addListener(installContextMenu);
// The worker is torn down when idle; rebuild the menu when it wakes on startup.
chrome.runtime.onStartup.addListener(installContextMenu);

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== MENU_ID) {
    return;
  }

  const text = (info.selectionText ?? "").trim();
  if (!text) {
    return;
  }

  await setPendingCapture({
    text,
    // `info.pageUrl` is the page the selection lives on; the tab title is only
    // available when the click came from a real tab.
    sourceUrl: info.pageUrl ?? tab?.url ?? "",
    sourceTitle: tab?.title ?? "",
  });

  await chrome.windows.create(POPUP_WINDOW);
});

export { MENU_ID, installContextMenu };
