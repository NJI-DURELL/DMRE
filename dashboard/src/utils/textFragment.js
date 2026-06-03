/**
 * textFragment.js
 * Build a Text Fragment URL so the browser scrolls to and highlights
 * the matching section when the page opens.
 * Spec: https://wicg.github.io/scroll-to-text-fragment/
 * Supported in Chrome 80+, Edge 83+.
 *
 * Format: https://example.com#:~:text=start,end
 */

/**
 * Find the 80-character window inside `text` that contains the most
 * query keyword hits, then return it trimmed to a word boundary.
 * Falls back to the first sentence if no keywords match.
 */
function extractQueryAnchor(text, query, maxChars = 80) {
  if (!text) return ''
  const clean = text.replace(/\s+/g, ' ').trim()

  const tokens = query
    ? [...new Set(query.toLowerCase().split(/\s+/).filter(t => t.length > 2))]
    : []

  if (tokens.length > 0) {
    const lower = clean.toLowerCase()
    let bestPos = -1
    let bestCount = 0

    // Slide a 120-char window, step 15 chars — find the densest keyword region.
    for (let i = 0; i < clean.length - 15; i += 15) {
      const window = lower.slice(i, i + 120)
      const count = tokens.filter(t => window.includes(t)).length
      if (count > bestCount) {
        bestCount = count
        bestPos = i
      }
    }

    if (bestPos >= 0 && bestCount > 0) {
      // Trim to maxChars at a word boundary.
      let phrase = clean.slice(bestPos, bestPos + maxChars)
      const lastSpace = phrase.lastIndexOf(' ')
      if (lastSpace > 15) phrase = phrase.slice(0, lastSpace)
      return phrase.trim()
    }
  }

  // Fallback: first sentence, or first maxChars words.
  const window120 = clean.slice(0, 120)
  const sentenceEnd = window120.search(/[.!?]/)
  if (sentenceEnd > 15) {
    const sentence = window120.slice(0, sentenceEnd).trim()
    if (sentence.length >= 15) return sentence.slice(0, maxChars)
  }

  let phrase = clean.slice(0, maxChars)
  const lastSpace = phrase.lastIndexOf(' ')
  if (lastSpace > 15) phrase = phrase.slice(0, lastSpace)
  return phrase.trim()
}

/**
 * Return a URL with a #:~:text= fragment so the browser highlights and
 * scrolls to the part of the page that contains the query keywords.
 *
 * @param {string} url      - The original page URL
 * @param {string} snippet  - The matching text chunk from DMRE
 * @param {string} [query]  - The search query (used to target the right sentence)
 * @returns {string}        - URL with text fragment appended
 */
export function buildFragmentUrl(url, snippet, query) {
  if (!url) return url
  const phrase = extractQueryAnchor(snippet, query)
  if (!phrase) return url

  try {
    const u = new URL(url)
    u.hash = ''
    return `${u.toString()}#:~:text=${encodeURIComponent(phrase)}`
  } catch {
    return url
  }
}
