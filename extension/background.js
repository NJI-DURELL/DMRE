/**
 * background.js — DMRE service worker
 * Receives page visit data from content.js, tracks dwell time per tab, and
 * POSTs the completed memory to the FastAPI backend when the user navigates
 * away or closes the tab.  All capture can be toggled via the popup.
 */

"use strict";

const BACKEND_URL = "http://localhost:8000/api/memories";

// In-memory store: tabId → { url, title, pageText, visitStart, visitCount }
const pendingVisits = new Map();

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Return true if capture is currently enabled (default: on). */
async function isEnabled() {
  const result = await chrome.storage.local.get({ dmreEnabled: true });
  return result.dmreEnabled;
}

/** Return the real visit count for a URL, incrementing the stored tally. */
async function incrementVisitCount(url) {
  const key = `vc:${url}`;
  const stored = await chrome.storage.local.get({ [key]: 0 });
  const count = stored[key] + 1;
  await chrome.storage.local.set({ [key]: count });
  return count;
}

/** POST a completed visit record to the DMRE backend. */
async function sendMemory(tabId, dwellTime) {
  const visit = pendingVisits.get(tabId);
  if (!visit) return;

  pendingVisits.delete(tabId);

  const payload = {
    url: visit.url,
    title: visit.title,
    page_text: visit.pageText,
    visited_at: visit.visitStart,
    dwell_time: Math.round(dwellTime),
    visit_count: visit.visitCount,
  };

  try {
    const response = await fetch(BACKEND_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const status = response.ok ? "ok" : `error ${response.status}`;
    await chrome.storage.local.set({
      dmreLastCapture: { url: visit.url, title: visit.title, status, ts: new Date().toISOString() },
    });
  } catch (err) {
    // Backend not running — silently record failure so popup can show it.
    await chrome.storage.local.set({
      dmreLastCapture: {
        url: visit.url,
        title: visit.title,
        status: `network error: ${err.message}`,
        ts: new Date().toISOString(),
      },
    });
  }
}

// ---------------------------------------------------------------------------
// Message handler — receives PAGE_VISIT from content.js
// ---------------------------------------------------------------------------
chrome.runtime.onMessage.addListener((message, sender) => {
  if (message.type !== "PAGE_VISIT") return;

  isEnabled().then((enabled) => {
    if (!enabled) return;

    const tabId = sender.tab?.id;
    if (!tabId) return;

    // If this tab already has a pending visit (e.g. SPA navigation), finalise
    // the previous one immediately with whatever dwell we have so far.
    if (pendingVisits.has(tabId)) {
      const prev = pendingVisits.get(tabId);
      const elapsed = (Date.now() - new Date(prev.visitStart).getTime()) / 1000;
      sendMemory(tabId, elapsed);
    }

    incrementVisitCount(message.url).then((count) => {
      pendingVisits.set(tabId, {
        url: message.url,
        title: message.title,
        pageText: message.pageText,
        visitStart: message.capturedAt,
        visitCount: count,
      });
    });
  });
});

// ---------------------------------------------------------------------------
// Tab closed — finalise dwell time
// ---------------------------------------------------------------------------
chrome.tabs.onRemoved.addListener((tabId) => {
  if (!pendingVisits.has(tabId)) return;
  const visit = pendingVisits.get(tabId);
  const elapsed = (Date.now() - new Date(visit.visitStart).getTime()) / 1000;
  sendMemory(tabId, elapsed);
});

// ---------------------------------------------------------------------------
// Tab navigated away — finalise dwell time for previous URL
// ---------------------------------------------------------------------------
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  // Only fire when a new page load is committed (not on every loading state).
  if (changeInfo.status !== "loading") return;
  if (!pendingVisits.has(tabId)) return;

  const visit = pendingVisits.get(tabId);
  const elapsed = (Date.now() - new Date(visit.visitStart).getTime()) / 1000;
  sendMemory(tabId, elapsed);
});

// ---------------------------------------------------------------------------
// Extension icon clicked — open the React dashboard as a popup window
// ---------------------------------------------------------------------------
chrome.action.onClicked.addListener(() => {
  chrome.windows.create({
    url: "http://localhost:3000",
    type: "popup",
    width: 860,
    height: 700,
    focused: true,
  });
});

// ---------------------------------------------------------------------------
// Extension installed / updated — set defaults
// ---------------------------------------------------------------------------
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ dmreEnabled: true });
  console.log("[DMRE] Extension installed. Capture enabled.");
});
