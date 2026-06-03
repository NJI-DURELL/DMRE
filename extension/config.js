/**
 * config.js — DMRE extension configuration (development).
 *
 * Loaded as a CLASSIC script so popup.html can include it via
 *   <script src="config.js">
 * and the service worker via
 *   importScripts("config.js")
 *
 * For production builds, `package_for_store.ps1` / `package_for_store.sh`
 * substitute `config.prod.js` in its place automatically. Do NOT edit this
 * file with production URLs — set them once in `config.prod.js` instead.
 *
 * Consumers read the constants from globalThis.DMRE_CONFIG.
 */

"use strict";

(function () {
  const CONFIG = {
    BACKEND_URL:   "http://localhost:8000",
    DASHBOARD_URL: "http://localhost:3000",
  };
  CONFIG.API_URL    = CONFIG.BACKEND_URL + "/api";
  CONFIG.HEALTH_URL = CONFIG.BACKEND_URL + "/health";

  // Works in window contexts (popup) AND service-worker contexts (background).
  globalThis.DMRE_CONFIG = CONFIG;
})();
