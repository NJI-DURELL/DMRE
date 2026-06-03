/**
 * background.js — DMRE service worker
 * Tracks dwell time, click count, and scroll depth per tab.
 * Sends captures to the backend with the user's JWT bearer token.
 */

"use strict";

// Load config as a classic script so the same file works for both the popup
// (window context) and this service worker (worker context).
importScripts("config.js");
const { API_URL, DASHBOARD_URL } = self.DMRE_CONFIG;

const MEMORIES_URL = `${API_URL}/memories`;

// Match the server-side cap (MAX_PAGE_TEXT_LEN = 200_000). Truncating client-side
// keeps the payload small and avoids a 422 response for users with massive pages.
const MAX_PAGE_TEXT_LEN = 100_000;
const MAX_TITLE_LEN     = 1_000;
const MAX_URL_LEN       = 4_000;

// Safe wrappers around chrome.storage so a quota error never crashes the
// service worker (which would silently drop subsequent captures).
async function safeStorageGet(defaults) {
  try {
    return await chrome.storage.local.get(defaults);
  } catch (err) {
    console.warn("[DMRE] storage.get failed:", err);
    return defaults;
  }
}

async function safeStorageSet(items) {
  try {
    await chrome.storage.local.set(items);
  } catch (err) {
    console.warn("[DMRE] storage.set failed:", err);
  }
}

async function safeStorageRemove(key) {
  try {
    await chrome.storage.local.remove(key);
  } catch (err) {
    console.warn("[DMRE] storage.remove failed:", err);
  }
}

// Pages we never want to index — search engines, auth pages, etc.
const SKIP_ENGINE_PATTERNS = [
  { host: /^(www\.)?google\.[a-z]{2,6}(\.[a-z]{2})?$/, path: /^\/?$|^\/search/ },
  { host: /^(www\.)?bing\.com$/,                        path: /^\/search/        },
  { host: /^(www\.)?duckduckgo\.com$/,                  path: /.*/               },
  { host: /^(www\.|search\.)?yahoo\.com$/,              path: /^\/search|^\/?$/  },
  { host: /^(www\.)?baidu\.com$/,                       path: /^\/s|^\/?$/       },
];

const AUTH_PATH_RE = /\/(log[io]n|sign[-_]?[io]n|sign[-_]?up|log[-_]?out|sign[-_]?out|register|registrat\w*|auth(?:enticate|oriz\w*)?|forgot[-_]?pass\w*|reset[-_]?pass\w*|account\/create|join|verify|2fa|mfa|otp|oauth\w*|callback)\/?(\?.*)?$/i;

function shouldSkip(url) {
  if (typeof url !== "string" || !url) return true;
  if (!url.startsWith("http://") && !url.startsWith("https://")) return true;
  if (url.length > MAX_URL_LEN) return true;
  try {
    const u = new URL(url);
    if (SKIP_ENGINE_PATTERNS.some(p => p.host.test(u.hostname) && p.path.test(u.pathname))) return true;
    if (AUTH_PATH_RE.test(u.pathname)) return true;
    return false;
  } catch {
    return true;
  }
}

function clip(s, max) {
  if (typeof s !== "string") return "";
  return s.length > max ? s.slice(0, max) : s;
}

// tabId → { url, title, pageText, visitStart, visitCount, clickCount, scrollDepth }
const pendingVisits = new Map();

async function isEnabled() {
  const result = await safeStorageGet({ dmreEnabled: true });
  return result.dmreEnabled !== false;
}

async function getAuthToken() {
  const { dmreAuth } = await safeStorageGet({ dmreAuth: null });
  return dmreAuth?.access_token || null;
}

async function clearAuthToken() {
  await safeStorageRemove("dmreAuth");
}

async function incrementVisitCount(url) {
  const key    = `vc:${url}`;
  const stored = await safeStorageGet({ [key]: 0 });
  const count  = (Number(stored[key]) || 0) + 1;
  await safeStorageSet({ [key]: count });
  return count;
}

async function sendMemory(tabId, dwellTime) {
  const visit = pendingVisits.get(tabId);
  if (!visit) return;
  pendingVisits.delete(tabId);

  // Final sanity checks before serialising.
  if (!visit.url || shouldSkip(visit.url)) return;

  const token = await getAuthToken();
  if (!token) {
    // No session — silently drop the capture; the popup tells the user to sign in.
    await safeStorageSet({
      dmreLastCapture: {
        url: visit.url,
        title: visit.title,
        status: "skipped: not signed in",
        ts: new Date().toISOString(),
      },
    });
    return;
  }

  // Clamp every text field — defends against misbehaving content scripts.
  const payload = {
    url:          clip(visit.url, MAX_URL_LEN),
    title:        clip(visit.title || "", MAX_TITLE_LEN),
    page_text:    clip(visit.pageText || "", MAX_PAGE_TEXT_LEN),
    visited_at:   visit.visitStart,
    dwell_time:   Math.max(0, Math.round(Number(dwellTime) || 0)),
    visit_count:  Math.max(1, Number(visit.visitCount)  || 1),
    click_count:  Math.max(0, Number(visit.clickCount)  || 0),
    scroll_depth: Math.max(0, Math.min(1, Number(visit.scrollDepth) || 0)),
  };

  let body;
  try {
    body = JSON.stringify(payload);
  } catch (err) {
    console.warn("[DMRE] serialise failed:", err);
    return;
  }

  try {
    const response = await fetch(MEMORIES_URL, {
      method:  "POST",
      headers: {
        "Content-Type":  "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body,
      signal: AbortSignal.timeout(20_000),
    });

    // Token rejected — clear so the popup forces a re-login.
    if (response.status === 401) {
      await clearAuthToken();
      await safeStorageSet({
        dmreLastCapture: {
          url: visit.url,
          title: visit.title,
          status: "session expired — sign in again",
          ts: new Date().toISOString(),
        },
      });
      return;
    }

    const status = response.ok ? "ok" : `error ${response.status}`;
    await safeStorageSet({
      dmreLastCapture: { url: visit.url, title: visit.title, status, ts: new Date().toISOString() },
    });
  } catch (err) {
    const reason = err?.name === "TimeoutError" ? "timeout" : (err?.message || "unknown");
    await safeStorageSet({
      dmreLastCapture: {
        url:    visit.url,
        title:  visit.title,
        status: `network error: ${reason}`,
        ts:     new Date().toISOString(),
      },
    });
  }
}

async function flushAllPending() {
  const now   = Date.now();
  const tabIds = [...pendingVisits.keys()];
  for (const tabId of tabIds) {
    const visit = pendingVisits.get(tabId);
    if (!visit) continue;
    const elapsed = (now - new Date(visit.visitStart).getTime()) / 1000;
    await sendMemory(tabId, elapsed);
  }
}

// ---------------------------------------------------------------------------
// Message handler
// ---------------------------------------------------------------------------
chrome.runtime.onMessage.addListener((message, sender) => {
  if (message.type === "OPEN_URL" && message.url) {
    chrome.tabs.create({ url: message.url, active: true });
    return;
  }

  // Periodic interaction update — update cached counts without resetting visit
  if (message.type === "INTERACTION_UPDATE") {
    const tabId = sender.tab?.id;
    if (!tabId) return;
    const visit = pendingVisits.get(tabId);
    if (!visit || visit.url !== message.url) return;
    visit.clickCount  = Math.max(visit.clickCount  || 0, message.clickCount  || 0);
    visit.scrollDepth = Math.max(visit.scrollDepth || 0, message.scrollDepth || 0);
    pendingVisits.set(tabId, visit);
    return;
  }

  if (message.type !== "PAGE_VISIT") return;
  if (!message.url) return;

  isEnabled().then((enabled) => {
    if (!enabled) return;
    if (shouldSkip(message.url)) return;
    const tabId = sender.tab?.id;
    if (!tabId) return;

    if (pendingVisits.has(tabId)) {
      const prev    = pendingVisits.get(tabId);
      const elapsed = (Date.now() - new Date(prev.visitStart).getTime()) / 1000;
      sendMemory(tabId, elapsed);
    }

    incrementVisitCount(message.url).then((count) => {
      pendingVisits.set(tabId, {
        url:         message.url,
        title:       message.title,
        pageText:    message.pageText,
        visitStart:  message.capturedAt,
        visitCount:  count,
        clickCount:  message.clickCount  || 0,
        scrollDepth: message.scrollDepth || 0.0,
      });
    });
  });
});

// ---------------------------------------------------------------------------
// Tab events
// ---------------------------------------------------------------------------
chrome.tabs.onRemoved.addListener((tabId) => {
  if (!pendingVisits.has(tabId)) return;
  const visit   = pendingVisits.get(tabId);
  const elapsed = (Date.now() - new Date(visit.visitStart).getTime()) / 1000;
  sendMemory(tabId, elapsed);
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status !== "loading") return;
  if (!pendingVisits.has(tabId)) return;
  const visit   = pendingVisits.get(tabId);
  const elapsed = (Date.now() - new Date(visit.visitStart).getTime()) / 1000;
  sendMemory(tabId, elapsed);
});

// "Open dashboard" requests from the popup.
chrome.runtime.onMessage.addListener((message) => {
  if (message?.type !== "OPEN_DASHBOARD") return;
  flushAllPending().finally(() => {
    chrome.windows.create({
      url:     DASHBOARD_URL,
      type:    "popup",
      width:   860,
      height:  700,
      focused: true,
    });
  });
});

chrome.runtime.onInstalled.addListener(() => {
  safeStorageSet({ dmreEnabled: true });
  console.log("[DMRE] Extension installed. Capture enabled.");
});

// Don't let an unhandled rejection in any async listener crash the service worker.
self.addEventListener("unhandledrejection", (event) => {
  console.warn("[DMRE] Unhandled promise rejection:", event.reason);
  event.preventDefault();
});
