/**
 * content.js — DMRE content script
 * Captures page text, click count, and scroll depth for each visit.
 *
 * Special handling:
 *  - Open Graph / Twitter meta tags are always read (available before JS renders).
 *  - YouTube and other SPAs get a 4-second delayed re-capture so dynamic content
 *    (video title, description, article body) has time to render.
 */

(function () {
  "use strict";

  // Hard cap on text we'll ever send. Background.js will clip again, but
  // doing it here saves on serialisation cost for huge pages.
  const MAX_PAGE_TEXT_LEN = 100_000;

  // Centralise messaging so we can swallow "Extension context invalidated"
  // errors that fire when the user disables/reloads the extension while a
  // tab is still alive.
  function sendToBackground(message) {
    try {
      const p = chrome.runtime.sendMessage(message);
      if (p && typeof p.catch === "function") p.catch(() => {});
    } catch {
      /* extension context gone — nothing to do */
    }
  }

  let url;
  try {
    url = window.location.href;
  } catch {
    return;
  }

  // Bridge: relay DMRE_OPEN_URL from the React dashboard → background.js
  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    if (!event.data || event.data.type !== "DMRE_OPEN_URL") return;
    if (!event.data.url) return;
    sendToBackground({ type: "OPEN_URL", url: event.data.url });
  });

  if (typeof url !== "string") return;
  if (!url.startsWith("http://") && !url.startsWith("https://")) return;
  if (!document || !document.body) return;

  let host, pathname;
  try {
    const u = new URL(url);
    host     = u.hostname;
    pathname = u.pathname;

    if (host === "localhost" || host === "127.0.0.1" || host === "::1") return;

    // Skip search engine result pages
    const SKIP_ENGINES = [
      { h: /^(www\.)?google\.[a-z]{2,6}(\.[a-z]{2})?$/, p: /^\/?$|^\/search/ },
      { h: /^(www\.)?bing\.com$/,                        p: /^\/search/       },
      { h: /^(www\.)?duckduckgo\.com$/,                  p: /.*/              },
      { h: /^(www\.|search\.)?yahoo\.com$/,              p: /^\/search|^\/?$/ },
      { h: /^(www\.)?baidu\.com$/,                       p: /^\/s|^\/?$/      },
    ];
    if (SKIP_ENGINES.some(r => r.h.test(host) && r.p.test(pathname))) return;

    // Skip login / auth pages
    const AUTH_PATH = /\/(log[io]n|sign[-_]?[io]n|sign[-_]?up|log[-_]?out|sign[-_]?out|register|registrat\w*|auth(?:enticate|oriz\w*)?|forgot[-_]?pass\w*|reset[-_]?pass\w*|account\/create|join|verify|2fa|mfa|otp|oauth\w*|callback)\/?(\?.*)?$/i;
    if (AUTH_PATH.test(pathname)) return;
  } catch { return; }

  // Skip sparse password forms (auth pages with non-standard URLs)
  try {
    const passwordFields = document.querySelectorAll('input[type="password"]');
    if (passwordFields.length > 0) {
      const visibleText = (document.body?.innerText || "").replace(/\s+/g, " ").trim();
      if (visibleText.length < 800) return;
    }
  } catch {
    /* hostile pages occasionally throw on querySelectorAll */
  }

  // ---------------------------------------------------------------------------
  // Interaction tracking
  // ---------------------------------------------------------------------------
  let clickCount    = 0;
  let maxScrollDepth = 0;

  document.addEventListener("click", () => { clickCount++; }, { passive: true });

  function updateScrollDepth() {
    const scrolled = window.scrollY + window.innerHeight;
    const total    = document.documentElement.scrollHeight || 1;
    const depth    = Math.min(1.0, scrolled / total);
    if (depth > maxScrollDepth) maxScrollDepth = depth;
  }
  window.addEventListener("scroll", updateScrollDepth, { passive: true });
  updateScrollDepth();

  // ---------------------------------------------------------------------------
  // Text extraction helpers
  // ---------------------------------------------------------------------------

  /** Read Open Graph / Twitter Card meta tags — populated server-side, always reliable. */
  function extractMetaTags() {
    try {
      const selectors = [
        'meta[property="og:title"]',
        'meta[property="og:description"]',
        'meta[name="description"]',
        'meta[name="keywords"]',
        'meta[property="twitter:title"]',
        'meta[property="twitter:description"]',
        'meta[name="twitter:title"]',
        'meta[name="twitter:description"]',
      ];
      return selectors
        .map(s => document.querySelector(s)?.content || "")
        .filter(Boolean)
        .join(" ");
    } catch {
      return "";
    }
  }

  /** Strip non-content tags and return visible text from the live DOM. */
  function extractVisibleText() {
    try {
      if (!document.body) return "";
      const clone = document.body.cloneNode(true);
      ["script", "style", "noscript", "svg", "canvas", "iframe"].forEach(tag =>
        clone.querySelectorAll(tag).forEach(el => el.remove())
      );
      return (clone.innerText || clone.textContent || "").replace(/\s+/g, " ").trim();
    } catch {
      // Some sites trap on cloneNode (custom elements, hostile JS). Fall back
      // to a read-only textContent scrape so we still capture *something*.
      try {
        return (document.body?.innerText || "").replace(/\s+/g, " ").trim();
      } catch {
        return "";
      }
    }
  }

  /**
   * YouTube-specific extraction — reads custom web components that
   * only exist after hydration.
   */
  function extractYouTubeText() {
    if (!/youtube\.com/.test(host)) return "";
    try {
      const parts = [];
      const selectors = [
        "h1.ytd-video-primary-info-renderer",
        "yt-formatted-string.ytd-video-primary-info-renderer",
        "#title h1",
        "#description-inline-expander",
        "ytd-text-inline-expander yt-formatted-string",
        "#description yt-formatted-string",
        "#channel-name #text",
        "ytd-channel-name #text",
      ];
      selectors.forEach(sel => {
        const el = document.querySelector(sel);
        if (el) parts.push(el.innerText || el.textContent || "");
      });
      return parts.join(" ").replace(/\s+/g, " ").trim();
    } catch {
      return "";
    }
  }

  /** Combine meta tags + DOM text + site-specific text into one string. */
  function fullPageText() {
    try {
      const text = [extractMetaTags(), extractYouTubeText(), extractVisibleText()]
        .filter(Boolean)
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      return text.length > MAX_PAGE_TEXT_LEN ? text.slice(0, MAX_PAGE_TEXT_LEN) : text;
    } catch {
      return "";
    }
  }

  // ---------------------------------------------------------------------------
  // SPAs: detect sites that render content after document_idle
  // ---------------------------------------------------------------------------
  const SPA_HOSTS = /\b(youtube\.com|twitter\.com|x\.com|reddit\.com|linkedin\.com|facebook\.com|instagram\.com|tiktok\.com|medium\.com|notion\.so)\b/;
  const isSPA = SPA_HOSTS.test(host);

  // ---------------------------------------------------------------------------
  // Initial capture
  // ---------------------------------------------------------------------------
  const initialText   = fullPageText();
  const initialLength = initialText.length;

  sendToBackground({
    type:        "PAGE_VISIT",
    url:         url,
    title:       (document.title || "").slice(0, 1000),
    pageText:    initialText,
    capturedAt:  new Date().toISOString(),
    clickCount:  0,
    scrollDepth: maxScrollDepth,
  });

  // ---------------------------------------------------------------------------
  // Delayed re-capture for SPAs
  // After 4 seconds, dynamic content (YouTube description, Twitter threads, etc.)
  // has had time to render.  Only re-send if we got meaningfully more text.
  // ---------------------------------------------------------------------------
  if (isSPA) {
    setTimeout(() => {
      try {
        const updatedText = fullPageText();
        if (updatedText.length > initialLength * 1.3) {
          sendToBackground({
            type:        "PAGE_VISIT",
            url:         url,
            title:       (document.title || "").slice(0, 1000),
            pageText:    updatedText,
            capturedAt:  new Date().toISOString(),
            clickCount:  clickCount,
            scrollDepth: maxScrollDepth,
          });
        }
      } catch { /* swallow */ }
    }, 4000);
  }

  // ---------------------------------------------------------------------------
  // Periodic interaction updates
  // ---------------------------------------------------------------------------
  const UPDATE_INTERVAL = 5000;
  const intervalId = setInterval(() => {
    try {
      sendToBackground({
        type:        "INTERACTION_UPDATE",
        url:         url,
        clickCount:  clickCount,
        scrollDepth: maxScrollDepth,
      });
    } catch {
      clearInterval(intervalId);
    }
  }, UPDATE_INTERVAL);

})();
