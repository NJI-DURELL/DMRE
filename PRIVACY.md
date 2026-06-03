# DMRE — Privacy Policy

**Effective date: 2026-05-09**

This privacy policy describes how the DMRE browser extension and its
companion backend service (collectively, "DMRE") handle the data you
generate while using them. The Chrome Web Store requires extensions that
read page content to publish a clear policy; this is ours.

> **TL;DR** DMRE captures the pages **you** browse so that **you** can
> search them later. Your captured data is private to your account, never
> shared with anyone, and you can delete any individual page or your
> entire account at any time.

---

## 1. Who is the data controller?

The data controller for hosted DMRE is **the operator of the backend you
sign in to**. If you are using the public hosted instance run by the DMRE
project author (Durell Nji), contact details are at the bottom of this
document. If your organisation has self-hosted DMRE, the controller is
your organisation.

## 2. What data we collect

When the DMRE extension is enabled and you are signed in, every time you
visit an `http(s)://` web page the extension transmits the following to
the configured backend:

| Field            | Why                                                          |
|------------------|--------------------------------------------------------------|
| URL              | So you can re-open the page later                            |
| Page title       | Displayed in search results                                  |
| Visible page text (≤ 200 KB, truncated) | Indexed for semantic search       |
| Visit timestamp  | Sorting + recency boost in the re-ranker                     |
| Dwell time       | Engagement signal in the re-ranker                           |
| Visit count      | Engagement signal in the re-ranker                           |
| Click count      | Engagement signal in the re-ranker                           |
| Scroll depth     | Engagement signal in the re-ranker                           |

When you sign up we also collect **your email address**, **a username**
(optional, derived from email if blank), and a **bcrypt hash** of your
password. We never store your password in plaintext.

**Email verification.** At signup we send a 6-digit verification code to
the address you provided. The code itself is stored as a bcrypt hash, not
in plaintext, and expires after 15 minutes. We deliver the email through
your operator's chosen SMTP provider (Resend, Mailgun, SendGrid, Gmail, or
self-hosted) — that provider handles delivery on our behalf and is bound
by their own privacy terms. No content of any captured page ever leaves
the DMRE backend in an email *unless* you explicitly click "Email me my
activity" or "Email me these results."

## 3. What we do **not** collect

DMRE does **not**:

- read pages where the URL contains common login/auth patterns
  (`/login`, `/signup`, `/oauth`, `/2fa`, …),
- read search-engine result pages (Google, Bing, DuckDuckGo, Yahoo, Baidu),
- transmit form contents or input values,
- transmit cookies, local storage, or session tokens from the pages you visit,
- read the page if the page contains a password field unless the visible
  text is substantial (> 800 chars), as a heuristic to avoid sparse
  auth/profile pages,
- track you across sites for advertising,
- share your data with any third party.

## 4. Where the data lives

- **PostgreSQL** holds the user record, captured page metadata, search
  history, and (optional) blockchain anchor records.
- **ChromaDB** (embedded vector store) holds the sentence-embedding
  vectors used for semantic search.
- **Chrome local storage** (in your browser) holds your access token,
  your capture-enabled preference, and a small "last capture" status object.
- **Optional blockchain** anchoring stores only the SHA-256 hash of
  `(url + title + page_text)`. The on-chain hash cannot be reversed back
  to the original content.

All transport between the extension/dashboard and the backend is over HTTPS
in production deployments.

## 5. Multi-tenancy and isolation

Every captured page is tagged with the user_id of the account that captured
it. **Search, verification, and listing endpoints filter strictly by that
user_id.** No user can read, list, or verify another user's pages. There
is no admin-style "see everyone's data" view of page content.

The only operational logging the backend retains beyond per-user data is
non-identifying server logs (request method, path, status code, request
duration). These logs are used to diagnose outages and are not shared.

## 6. Your rights

You can, at any time, from the dashboard's **History** tab:

- **List** every page you have captured.
- **Delete** any individual page (cascades to vectors).
- **Delete your entire account** (the "Danger zone" button), which
  removes:
  - your user record,
  - every captured memory + embedding reference + blockchain record,
  - every vector in the embedded vector store.

Account deletion is immediate and irreversible. Your token is invalidated
the next time it is used.

You can also disable capture without deleting anything by toggling the
"Capture enabled" switch in the extension popup.

## 7. Data retention

DMRE retains your data **for as long as your account exists**. We do not
expire or auto-prune it. Server logs (HTTP request lines, see §5) are
retained per the host platform's defaults — typically 7-30 days on
Render/Railway/Fly.

## 8. Security

- Passwords are hashed with bcrypt (cost factor 12).
- Authentication uses signed JWT bearer tokens with a 30-day lifetime;
  signing keys are randomly generated per deployment and never logged.
- The backend rejects requests that do not present a valid token for any
  endpoint that touches per-user data.
- The backend caps each captured page at 200 KB of visible text to limit
  blast radius from a hostile page or runaway content script.

## 9. Children's privacy

DMRE is not directed to children under 13 and we do not knowingly collect
data from them.

## 10. Changes

If this policy changes materially, the extension's "version" in
`manifest.json` will be bumped and the new policy date above will be
updated. The current version is always available at the URL listed in
the Chrome Web Store listing.

## 11. Contact

For privacy questions, data-deletion requests, or breach notifications,
contact: **durellnji16@gmail.com**.
