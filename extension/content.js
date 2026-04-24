/**
 * content.js — DMRE content script
 * Injected into every HTTP/HTTPS page at document_idle.
 * Extracts the page title and visible body text, then sends the data to the
 * background service worker which handles dwell-time tracking and the POST.
 */

(function () {
  "use strict";

  /**
   * Extract visible text from the page body.
   * Removes <script>, <style>, <noscript>, and <svg> nodes before reading
   * innerText so only human-readable content is captured.
   */
  function extractVisibleText() {
    // Clone the body to avoid mutating the live DOM.
    const clone = document.body.cloneNode(true);

    // Strip non-visible / non-text elements.
    const STRIP_TAGS = ["script", "style", "noscript", "svg", "canvas", "iframe"];
    STRIP_TAGS.forEach((tag) => {
      clone.querySelectorAll(tag).forEach((el) => el.remove());
    });

    // innerText respects CSS visibility; trim and collapse whitespace.
    const raw = clone.innerText || clone.textContent || "";
    return raw.replace(/\s+/g, " ").trim();
  }

  // Only send data for real navigable pages (skip extension pages, etc.).
  const url = window.location.href;
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    return;
  }

  const pageData = {
    type: "PAGE_VISIT",
    url: url,
    title: document.title || "",
    pageText: extractVisibleText(),
    capturedAt: new Date().toISOString(),
  };

  // Send to the background service worker.
  // chrome.runtime.sendMessage is fire-and-forget from content script side.
  chrome.runtime.sendMessage(pageData).catch(() => {
    // Ignore errors if background is not ready yet.
  });
})();
