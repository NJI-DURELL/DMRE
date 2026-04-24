/**
 * popup.js — DMRE popup controller
 * Reads and writes the capture toggle state via chrome.storage.local, checks
 * backend liveness with a /health ping, and displays the last captured page.
 */

"use strict";

const BACKEND_HEALTH = "http://localhost:8000/health";

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const toggleEl        = document.getElementById("toggleCapture");
const backendStatusEl = document.getElementById("backendStatus");
const lastSection     = document.getElementById("lastCaptureSection");
const lastTitleEl     = document.getElementById("lastTitle");
const lastUrlEl       = document.getElementById("lastUrl");
const lastTsEl        = document.getElementById("lastTs");

// ---------------------------------------------------------------------------
// Initialise — read stored state
// ---------------------------------------------------------------------------
chrome.storage.local.get({ dmreEnabled: true, dmreLastCapture: null }, (data) => {
  toggleEl.checked = data.dmreEnabled;
  if (data.dmreLastCapture) {
    renderLastCapture(data.dmreLastCapture);
  }
});

// ---------------------------------------------------------------------------
// Toggle handler
// ---------------------------------------------------------------------------
toggleEl.addEventListener("change", () => {
  chrome.storage.local.set({ dmreEnabled: toggleEl.checked });
});

// ---------------------------------------------------------------------------
// Backend health check
// ---------------------------------------------------------------------------
async function checkBackend() {
  try {
    const res = await fetch(BACKEND_HEALTH, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      setStatus("ok", "Backend online");
    } else {
      setStatus("error", `Backend error ${res.status}`);
    }
  } catch {
    setStatus("error", "Backend offline");
  }
}

function setStatus(type, text) {
  backendStatusEl.className = `status-pill ${type}`;
  backendStatusEl.textContent = text;
}

// ---------------------------------------------------------------------------
// Last capture display
// ---------------------------------------------------------------------------
function renderLastCapture(capture) {
  lastSection.style.display = "block";
  lastTitleEl.textContent = capture.title || "(no title)";
  lastUrlEl.textContent   = capture.url   || "";
  lastTsEl.textContent    = capture.ts
    ? `${new Date(capture.ts).toLocaleString()} — ${capture.status}`
    : "";
}

// ---------------------------------------------------------------------------
// Run on popup open
// ---------------------------------------------------------------------------
checkBackend();
