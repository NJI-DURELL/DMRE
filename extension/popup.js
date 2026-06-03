/**
 * popup.js — DMRE popup controller
 *
 * Handles signup/login when no token is stored, and shows the capture toggle +
 * status panel once authenticated. The JWT and user record are kept in
 * chrome.storage.local under `dmreAuth` so background.js can read them.
 */

"use strict";

const { API_URL, HEALTH_URL } = window.DMRE_CONFIG;

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const authSection      = document.getElementById("authSection");
const appSection       = document.getElementById("appSection");
const authTitle        = document.getElementById("authTitle");
const authError        = document.getElementById("authError");
const authEmail        = document.getElementById("authEmail");
const authPassword     = document.getElementById("authPassword");
const authUsername     = document.getElementById("authUsername");
const authUsernameField = document.getElementById("authUsernameField");
const authSubmit       = document.getElementById("authSubmit");
const authSwitchText   = document.getElementById("authSwitchText");
const authSwitchLink   = document.getElementById("authSwitchLink");

const accountEmailEl    = document.getElementById("accountEmail");
const accountUsernameEl = document.getElementById("accountUsername");
const logoutBtn         = document.getElementById("logoutBtn");
const openDashboardBtn  = document.getElementById("openDashboardBtn");
const toggleEl          = document.getElementById("toggleCapture");
const backendStatusEl   = document.getElementById("backendStatus");
const lastSection       = document.getElementById("lastCaptureSection");
const lastTitleEl       = document.getElementById("lastTitle");
const lastUrlEl         = document.getElementById("lastUrl");
const lastTsEl          = document.getElementById("lastTs");

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let authMode = "login"; // "login" | "signup"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function showError(msg) {
  authError.textContent = msg;
  authError.classList.add("show");
}
function clearError() {
  authError.textContent = "";
  authError.classList.remove("show");
}

function setMode(mode) {
  authMode = mode;
  clearError();
  if (mode === "signup") {
    authTitle.textContent = "Create your account";
    authSubmit.textContent = "Create account";
    authUsernameField.style.display = "block";
    authSwitchText.textContent = "Already have an account?";
    authSwitchLink.textContent = "Sign in";
    authPassword.setAttribute("autocomplete", "new-password");
  } else {
    authTitle.textContent = "Sign in";
    authSubmit.textContent = "Sign in";
    authUsernameField.style.display = "none";
    authSwitchText.textContent = "Don't have an account?";
    authSwitchLink.textContent = "Create one";
    authPassword.setAttribute("autocomplete", "current-password");
  }
}

function showAuthScreen() {
  authSection.classList.remove("hidden");
  appSection.classList.add("hidden");
}

function showAppScreen(user) {
  authSection.classList.add("hidden");
  appSection.classList.remove("hidden");
  accountEmailEl.textContent    = user?.email    || "—";
  accountUsernameEl.textContent = user?.username || "";
  initApp();
}

// ---------------------------------------------------------------------------
// Auth API calls
// ---------------------------------------------------------------------------
function flattenDetail(detail, fallback) {
  // FastAPI's RequestValidationError default body is a list of objects.
  // Our backend now flattens these to strings, but be defensive against
  // older deployments or other 4xx responses with mixed shapes.
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => (typeof d === "string" ? d : (d?.msg || JSON.stringify(d))))
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  if (detail && typeof detail === "object" && detail.msg) return String(detail.msg);
  return fallback;
}

async function callAuth(path, body) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    });
  } catch (err) {
    if (err?.name === "TimeoutError") {
      throw new Error("Request timed out. Check your connection.");
    }
    if (err?.name === "AbortError") {
      throw new Error("Request was cancelled.");
    }
    throw new Error("Cannot reach the DMRE backend. Check your connection.");
  }

  let data = null;
  try { data = await res.json(); } catch { /* may be empty / non-JSON */ }

  if (!res.ok) {
    throw new Error(flattenDetail(data?.detail, `Request failed (${res.status})`));
  }
  return data;
}

async function doLogin(email, password) {
  return callAuth("/auth/login-json", { email, password });
}

async function doSignup(email, password, username) {
  return callAuth("/auth/signup", { email, password, username: username || null });
}

authSubmit.addEventListener("click", async () => {
  clearError();
  const email    = authEmail.value.trim();
  const password = authPassword.value;
  const username = authUsername.value.trim();

  if (!email || !password) {
    showError("Email and password are required.");
    return;
  }
  if (authMode === "signup" && password.length < 8) {
    showError("Password must be at least 8 characters.");
    return;
  }

  authSubmit.disabled = true;
  const previousLabel = authSubmit.textContent;
  authSubmit.textContent = authMode === "signup" ? "Creating…" : "Signing in…";
  try {
    const tokenResp = authMode === "signup"
      ? await doSignup(email, password, username)
      : await doLogin(email, password);

    await chrome.storage.local.set({
      dmreAuth: {
        access_token: tokenResp.access_token,
        token_type:   tokenResp.token_type,
        expires_in:   tokenResp.expires_in,
        user:         tokenResp.user,
        issued_at:    Date.now(),
      },
    });
    showAppScreen(tokenResp.user);
  } catch (err) {
    showError(err.message || "Authentication failed.");
  } finally {
    authSubmit.disabled = false;
    authSubmit.textContent = previousLabel;
  }
});

authSwitchLink.addEventListener("click", () => {
  setMode(authMode === "login" ? "signup" : "login");
});

logoutBtn.addEventListener("click", async () => {
  await chrome.storage.local.remove("dmreAuth");
  setMode("login");
  authEmail.value = "";
  authPassword.value = "";
  authUsername.value = "";
  showAuthScreen();
});

// ---------------------------------------------------------------------------
// Authenticated app
// ---------------------------------------------------------------------------
function initApp() {
  chrome.storage.local.get({ dmreEnabled: true, dmreLastCapture: null }, (data) => {
    toggleEl.checked = data.dmreEnabled;
    if (data.dmreLastCapture) renderLastCapture(data.dmreLastCapture);
  });
  checkBackend();
}

toggleEl.addEventListener("change", () => {
  chrome.storage.local.set({ dmreEnabled: toggleEl.checked });
});

openDashboardBtn.addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "OPEN_DASHBOARD" });
  window.close();
});

async function checkBackend() {
  try {
    const res = await fetch(HEALTH_URL, { signal: AbortSignal.timeout(5000) });
    setStatus(res.ok ? "ok" : "error", res.ok ? "Backend online" : `Backend error ${res.status}`);
  } catch (err) {
    const text = err?.name === "TimeoutError" ? "Backend slow / unreachable" : "Backend offline";
    setStatus("error", text);
  }
}

function setStatus(type, text) {
  backendStatusEl.className = `status-pill ${type}`;
  backendStatusEl.textContent = text;
}

function renderLastCapture(capture) {
  lastSection.style.display = "block";
  lastTitleEl.textContent = capture.title || "(no title)";
  lastUrlEl.textContent   = capture.url   || "";
  lastTsEl.textContent    = capture.ts
    ? `${new Date(capture.ts).toLocaleString()} — ${capture.status}`
    : "";
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
function safeStorageGet(defaults) {
  return new Promise((resolve) => {
    try {
      chrome.storage.local.get(defaults, (data) => resolve(data || defaults));
    } catch {
      resolve(defaults);
    }
  });
}

safeStorageGet({ dmreAuth: null }).then(({ dmreAuth }) => {
  if (dmreAuth?.access_token) {
    showAppScreen(dmreAuth.user);
  } else {
    setMode("login");
    showAuthScreen();
  }
});

// Catch any rejection that escapes async handlers so the popup never goes
// blank when something throws (Chrome closes the popup on uncaught errors).
window.addEventListener("unhandledrejection", (event) => {
  console.warn("[DMRE popup] Unhandled rejection:", event.reason);
  event.preventDefault();
});
