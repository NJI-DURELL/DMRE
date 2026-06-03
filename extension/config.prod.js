/**
 * config.prod.js — Production URLs for the Chrome Web Store build.
 *
 * The packager script (`package_for_store.ps1` / `.sh`) substitutes this
 * file in place of `config.js` inside the zip. Both files MUST expose
 * `globalThis.DMRE_CONFIG` with identical keys.
 *
 * Replace the two URLs below with your real deployment before zipping:
 *   BACKEND_URL   — the Render web service URL (no trailing slash)
 *   DASHBOARD_URL — wherever you host the dashboard
 *
 * The `package_for_store` scripts refuse to build a zip while either URL
 * still points at localhost / 127.0.0.1, so you can't accidentally ship a
 * dev build.
 */

"use strict";

(function () {
  const CONFIG = {
    BACKEND_URL:   "https://dmre-backend.onrender.com",
    DASHBOARD_URL: "https://dmre-dashboard.onrender.com",
  };
  CONFIG.API_URL    = CONFIG.BACKEND_URL + "/api";
  CONFIG.HEALTH_URL = CONFIG.BACKEND_URL + "/health";

  globalThis.DMRE_CONFIG = CONFIG;
})();
