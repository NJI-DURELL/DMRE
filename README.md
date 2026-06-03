# DMRE — Digital Memory Reconstruction Engine

A multi-modal personal memory engine: a Chrome extension silently captures
the pages you read, a FastAPI backend stores and embeds them, and a React
dashboard lets you find any of them again later by **meaning**, not just
keywords. Optional blockchain layer proves a page's content has not been
tampered with since you saw it.

```
┌─────────────────┐   capture     ┌─────────────────────────┐
│ Chrome Extension│──────────────▶│ FastAPI Backend         │
│  (popup + bg)   │               │   • Sentence-BERT embed │
└─────────────────┘               │   • XGBoost re-ranker   │
                                  │   • PostgreSQL          │
┌─────────────────┐  search/      │   • Embedded ChromaDB   │
│ React Dashboard │ ─history──────│   • (optional) on-chain │
└─────────────────┘               │     SHA-256 anchor      │
                                  └─────────────────────────┘
```

---

## What's in this repo

| Path           | Purpose                                                         |
|----------------|-----------------------------------------------------------------|
| `backend/`     | FastAPI app, ORM models, Alembic migrations, ML services        |
| `dashboard/`   | React + Vite single-page app (search, history, account control) |
| `extension/`   | Manifest V3 Chrome extension (capture + popup + auth)           |
| `blockchain/`  | Hardhat workspace with the `MemoryIntegrity` smart contract     |
| `render.yaml`  | One-click Render Blueprint deploy (web + Postgres + disk)       |
| `DEPLOY.md`    | Full deployment + Chrome Web Store submission walkthrough       |
| `PRIVACY.md`   | Privacy policy required by the Chrome Web Store                 |

---

## What changed from the original prototype, and why

The first version of DMRE was a working **single-user** prototype that
ran entirely on `localhost`. To make it publishable on the Chrome Web
Store — where any user can install and start using it — it needed real
authentication, multi-tenant isolation, hosting, hardening, self-service
privacy controls, an admin role, an iconic brand, and an active blockchain
layer. Here is the full list:

### 1. Per-user accounts and isolation

| Before | After |
|--------|-------|
| `Memory.user_id` was nullable; the extension never set it. | `user_id` is **NOT NULL** with `ON DELETE CASCADE`. Every memory is owned by one account. |
| No login screen anywhere. | Email + password signup/login on both the dashboard and the extension popup. JWT bearer tokens issued from `/api/auth/login-json` and `/api/auth/signup`. |
| One shared ChromaDB collection. | Every chunk's metadata is tagged with `user_id`; vector queries pass `where={"user_id": ...}` so search results are partitioned at the index level, not just at the SQL level. |
| Verify endpoint trusted any `memory_id`. | `/api/verify/{id}` returns `404` if the memory belongs to anyone other than the authenticated user — same response for "not found" and "not yours" so IDs cannot be probed. |

**Why:** Privacy. Every user's browsing history is sensitive. Without
isolation, a single bug or shared collection would leak data across
accounts.

### 2. Self-service privacy controls

| Before | After |
|--------|-------|
| No way to see what was captured beyond running a search. | New **History** tab in the dashboard lists every captured page and every search query, newest-first, paginated. |
| No way to delete an individual page. | `DELETE /api/memories/{id}` and a per-row Delete button in History. Cascades to vectors. |
| No way to delete an account. | `DELETE /api/account` and a "Danger zone" button. Wipes the user, every memory, every embedding, every blockchain record, every Chroma vector. |

**Why:** Chrome Web Store policy requires extensions that capture
content to give users a clear way to revoke access and erase their data.
Also a basic respect-your-users requirement.

### 3. Hostability

| Before | After |
|--------|-------|
| ChromaDB ran as a separate HTTP server (`chroma run …`). | ChromaDB now defaults to **embedded** `PersistentClient` mode (config-driven). One process, one container, fewer moving parts. The HTTP mode is still selectable via `CHROMA_MODE=http` for split deployments. |
| Local Ganache RPC was a hard requirement. | Blockchain anchoring is **best-effort**: `is_configured()` checks for both an RPC URL and contract address; missing config is a silent skip, not an error. The hosted backend never fails because the chain is absent; you can still demo the chain locally. |
| Hardcoded `localhost` URLs everywhere. | `extension/config.js` is the single source of truth for `BACKEND_URL` / `DASHBOARD_URL`. The dashboard reads `VITE_BACKEND_URL` at build time. |
| No deployment artifacts. | `backend/Dockerfile`, `backend/start.sh`, `backend/.dockerignore`, `backend/.env.example`, top-level `render.yaml` (Blueprint: web service + managed Postgres + 5 GB persistent disk for Chroma + HF cache). |

**Why:** Chrome Web Store users are not going to spin up Postgres,
Ganache, ChromaDB, and a FastAPI server on their own laptops. The
backend has to be one Docker pull.

### 4. Defensive error handling

This came from real "what if the user does something stupid" scenarios:

- **Backend** — a global `Exception` handler in `app/main.py` returns a
  JSON `{"detail": "Internal server error"}` 500 instead of leaking a
  stack trace. A typed `BlockchainUnavailable` exception is mapped to
  503. `RequestValidationError` is flattened from Pydantic's default
  list-of-objects shape to a single string the UI can render directly.
- **Schemas** — `MemoryCreate` caps `url` (4 KB), `title` (1 KB),
  `page_text` (200 KB), and rejects non-`http(s)` schemes. `SignupRequest`
  caps the password and validates the username character set.
- **Race conditions** — concurrent signups with the same email are
  caught at `IntegrityError` and translated to a clean 409.
- **Memory ingest** — chunking and embedding are wrapped in a
  last-resort barrier so a hostile page that crashes the embedder
  degrades to "stored without vectors" rather than failing the whole
  request.
- **Search** — `top_k` is clamped, query text is clipped, and the
  Chroma response is defensively shape-guarded.
- **Extension** — `safeStorageGet/Set/Remove` wrappers swallow
  `chrome.storage` quota errors. `background.js` clamps every text
  field, has a 20 s fetch timeout, and listens for
  `unhandledrejection` so the service worker never silently dies.
  `content.js` wraps every DOM extraction in try/catch (some sites
  trap on `cloneNode`; we still capture *something*). `popup.js`
  distinguishes timeout vs. abort vs. offline and renders Pydantic
  validation arrays as strings.
- **Dashboard** — `auth.js` swallows `localStorage` quota errors;
  `LoginScreen.jsx` flattens array-shaped error details and shows a
  friendly message when the network is the actual problem.

**Why:** End users will type 1-character passwords, paste 50 MB pages,
unplug the network mid-signup, and then file a bug report. The system
should stay up.

### 5. Light theme (white + mint)

The dashboard and the extension popup were originally a dark navy theme.
They are now white with mint-green accents (`bg-mint-500` for primary
actions, `text-mint-700` for emphasis, `bg-mint-100` for confirmations).
Tailwind palette extended in `dashboard/tailwind.config.js`; popup
inline-styled to match.

### 6. Iconic brand (brain + puzzle + sparkles)

`extension/icons/icon{16,48,128}.png` are now generated by
`extension/generate_icons.py` (Pillow). The icon depicts a stylised
**brain** (the "memory" cue) with a **puzzle piece docked to its right**
(the "reconstruction" cue) and **three sparkles** (the "AI" cue), all in
the mint palette. The 16x16 favicon variant simplifies to just the
brain silhouette so it stays readable at toolbar size.

To regenerate the icons (e.g. after tweaking the design):

```powershell
cd extension
..\backend\.venv\Scripts\python.exe generate_icons.py
```

### 7. Toolbar click → popup, never a full webpage

`manifest.json` declares `default_popup: popup.html` and there is no
`chrome.action.onClicked` listener. Result: clicking the toolbar icon
always opens the small popup (sign in / capture toggle / status / open
dashboard button). The popup never opens a full-page tab. The "Open
dashboard" button inside the popup is the only place that opens a
window, and even that uses `chrome.windows.create({ type: "popup" })`
so it appears as a chrome popup window rather than a tab.

### 8. Admin role + operational dashboard

The user activity log was already private-per-user. To run DMRE as a
real service we added a **count-only** admin role:

| Endpoint                            | Purpose                                           |
|-------------------------------------|---------------------------------------------------|
| `GET  /api/admin/stats`             | Total users, signups (24 h / 7 d), memory + search counts, on-chain anchor count |
| `GET  /api/admin/users`             | User roster — email, username, memory **count**, last-search timestamp. **No content.** |
| `DELETE /api/admin/users/{id}`      | Abuse / GDPR removal of a target account          |

All three are gated by `require_admin`, which checks the new
`User.is_admin` boolean (Alembic migration `004_user_is_admin.py`). A
non-admin user calling these gets a 403; an unauthenticated request
gets 401. Admins **never** see another user's captured page text.

A small operations CLI promotes a user:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli grant-admin you@example.com
.\.venv\Scripts\python.exe -m app.cli list-admins
.\.venv\Scripts\python.exe -m app.cli revoke-admin you@example.com
```

The dashboard adds an **Admin** tab (visible only when
`user.is_admin === true`) with stat cards and the user roster.

**Why this and not a fuller admin?** Because the most sensitive thing
admins could ever see is page contents, and that is the one thing they
can't. Operational visibility (signup velocity, capture volume, abuse
removal) without privacy compromise.

### 9. Active blockchain anchoring

Anchoring is no longer "best-effort and disabled by default" in
practice — the local stack runs Ganache and a deployed
`MemoryIntegrity` contract end-to-end:

```powershell
# Ganache (deterministic accounts)
cd blockchain
npx ganache --deterministic --port 7545
# In a second shell, deploy the contract
npx hardhat run scripts/deploy.js --network ganache
# The deploy script prints the contract address — paste it into backend/.env
# as CONTRACT_ADDRESS. With --deterministic, the address is stable across runs.
```

Once Ganache is up and `CONTRACT_ADDRESS` is set, every `/api/memories`
POST writes the SHA-256 of `(url + title + page_text)` on-chain in the
same request, and `/api/verify/{id}` reads the on-chain hash back and
compares. Verified results show transaction hash + block number.

If the chain is unreachable mid-request, the memory still persists
(because we caught the typed `BlockchainUnavailable` exception
explicitly) — so a Ganache crash does not block ingest.

### 10. Production-credentials posture (no mock data)

This was an audit pass to make sure the running stack is ready to
accept real users:

- `backend/.env` now contains a **real** 64-byte URL-safe random
  `JWT_SECRET` generated at install time. The placeholder default
  (`insecure-dev-jwt-secret-change-in-prod`) is no longer in use.
- `CORS_ORIGINS` now includes `chrome-extension://*`, and `main.py`
  splits literal vs. wildcard origins into `allow_origins` and
  `allow_origin_regex` so an installed Chrome extension's `Origin`
  header (`chrome-extension://<id>`) actually matches at preflight.
- No mock users, no test fixtures, no hardcoded credentials in app
  code. All accounts go through real signup → bcrypt → JWT. The only
  "mocks" anywhere in the repo are vitest mocks in
  `dashboard/src/test/*.test.jsx` — those run during `npm test`
  only.
- Render's `render.yaml` already had `JWT_SECRET: { generateValue:
  true }` so production deploys mint a fresh secret on first deploy.

### 11. Email-OTP verification + email-export

DMRE now requires real proof-of-email-ownership at signup, plus lets users
email themselves a copy of any search or their activity log.

| Endpoint                            | Behaviour                                          |
|-------------------------------------|----------------------------------------------------|
| `POST /api/auth/signup`             | Creates user, generates 6-digit OTP, sends via SMTP, returns JWT. If SMTP fails the account creation is rolled back and the client gets a 503. |
| `POST /api/auth/verify-email`       | Body `{code}`; flips `email_verified` to true on match. 5-attempt lockout, 15 min TTL, then must request a new code. |
| `POST /api/auth/resend-otp`         | Generates a fresh code; rate-limited to once every 30 s. |
| `POST /api/search/email-export`     | Runs the search and emails the top-N results.       |
| `POST /api/queries/email-export`    | Emails a digest of recent captures + search history.|

A new `get_current_verified_user` dependency is now required on every
protected route except `/api/auth/me`, `/verify-email`, `/resend-otp`,
and `DELETE /api/account`. Unverified users get **HTTP 403** trying to
capture, search, list memories, or anything else — the dashboard reacts
by showing a `EmailVerifyScreen` until they enter the code.

OTPs are stored as **bcrypt hashes**, never plaintext. They expire in 15
minutes, support a 5-attempt lockout, and a 30 s resend cooldown.

#### SMTP transport — production-only, no mock fallback

`backend/app/services/email_service.py` uses Python's stdlib `smtplib`. It
talks to any provider that speaks SMTP — **Resend**, **Mailgun**,
**SendGrid**, **Gmail app-password**, or your own MTA. Just set:

```bash
SMTP_HOST=smtp.resend.com   # or smtp.gmail.com / smtp-relay.sendgrid.net / …
SMTP_PORT=587               # 587 STARTTLS, 465 SSL, 25 plain (dev only)
SMTP_USER=resend            # provider-specific (often the API key user)
SMTP_PASS=re_xxxxxxxxx
SMTP_TLS=starttls           # or "ssl" or "none"
SMTP_FROM="DMRE <verified-sender@yourdomain.com>"
```

If `SMTP_HOST` is empty or the server is unreachable, signup returns a
clean 503 — there is **no console fallback**, so we never ship an
unverifiable account into the database.

#### Local development SMTP

Because we can't ship a real provider key in the repo, the local
default points at a tiny RFC-5321 server included in the repo:

```powershell
# Terminal 1
python backend/dev_smtp.py
# [dev_smtp] listening on 127.0.0.1:1025
# >>> OTP code: 384172 <<<     (printed when an email arrives)

# Terminal 2 — backend uses .env's SMTP_HOST=127.0.0.1 SMTP_PORT=1025 SMTP_TLS=none
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

`dev_smtp.py` is **not a mock** — it implements real RFC-5321 SMTP, just
echoes received emails to stdout instead of relaying. The same
`email_service.py` code that talks to it talks to Resend/Mailgun
unchanged when you switch the env vars in production.

### 12. Authentication architecture

Decision: **email + password + JWT**, not OAuth.

We use the `bcrypt` package directly rather than `passlib` because
passlib 1.7.4 is incompatible with bcrypt ≥ 4.1 (it crashes on
import-time version detection). The wrapper in
`backend/app/services/auth_service.py` is small enough that going
without passlib costs nothing.

JWT is signed with HS256 against a per-deploy secret (Render auto-
generates one with `generateValue: true`). Tokens default to 30-day
expiry; the dashboard's axios client clears them on 401 and the
extension's background worker does the same.

---

## Quick start (local development)

### Prerequisites

- Python 3.11+ (3.13 tested)
- Node 18+
- Docker Desktop (for the Postgres container — the project uses an
  existing Compose-style container named `d_m_r_e-postgres-1`)
- Chrome / Edge / Brave for loading the extension

### Boot everything

```powershell
# Windows convenience script — starts Docker, Ganache, Chroma, backend, dashboard
.\start.bat
```

### Or boot manually

```powershell
# 1. Start Postgres (via Docker)
docker start d_m_r_e-postgres-1

# 2. Backend
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt   # first run
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000

# 3. Dashboard (separate shell)
cd dashboard
npm install   # first run
npm run dev   # serves http://localhost:3000

# 4. Extension
# chrome://extensions → Developer mode → Load unpacked → pick D_M_R_E\extension
```

### First end-to-end run

1. Open http://localhost:3000 — you should see the **Sign in** screen.
2. Click **Create one** and sign up with any email and a ≥ 8-char password.
3. Click the toolbar icon — popup shows the same login form. Sign in
   with the same account.
4. Browse to a real page (e.g. en.wikipedia.org/wiki/Photosynthesis).
   Wait a few seconds, then re-open the popup — "Last captured page: ok".
5. Back on the dashboard, search for something on that page. The page
   appears in results. Click **Verify** to test the (optional) blockchain
   layer.
6. Click the **History** tab to audit your captures.

---

## Production deploy

See **[DEPLOY.md](./DEPLOY.md)** for the full walkthrough:

1. Push the repo to GitHub.
2. Render → **New Blueprint** → point at the repo. `render.yaml`
   provisions the web service, the managed Postgres, and the disk.
3. Edit `extension/config.js` to point at your Render URL.
4. Build the dashboard with `VITE_BACKEND_URL=https://...` baked in;
   host the `dist/` directory anywhere static.
5. Run `extension/package_for_store.ps1` (or `.sh`) to produce a clean
   zip in `extension/dist/`. Upload to the Chrome Web Store dev console.
6. Use **[PRIVACY.md](./PRIVACY.md)** as the basis for your store
   listing's privacy policy URL.

---

## Architecture deep dive

### Capture path
1. `content.js` extracts visible text + meta tags + site-specific
   selectors (YouTube has its own extractor) and posts to the service
   worker.
2. `background.js` debounces per tab, clamps text size, attaches the
   user's JWT bearer token, and POSTs to `/api/memories`.
3. The backend chunks the text (sliding window: 400 words, 100 overlap),
   embeds each chunk with Sentence-BERT (`all-MiniLM-L6-v2`), stores
   them in ChromaDB tagged by user_id and memory_id, and writes the
   metadata row in PostgreSQL.
4. If the blockchain layer is configured, the backend writes the
   SHA-256 of `(url + title + page_text)` to the smart contract and
   stores the tx hash. Otherwise this step is silently skipped.

### Search path
1. Dashboard sends `{query, top_k}` to `/api/search/text`.
2. `query_processor` strips conversational filler and extracts any
   temporal hints ("this morning", "last week" → time window).
3. The query is embedded; ChromaDB returns the top-50 nearest chunks
   filtered by `user_id`.
4. Candidates are dedup'd by memory_id and scored on `0.6 * cosine +
   0.4 * keyword coverage` to drop semantically irrelevant noise.
5. The XGBoost re-ranker (`reranker_model.ubj`) scores the survivors
   using semantic similarity, dwell, visit count, click count, scroll
   depth, recency, and term overlap, and returns the top-k.
6. Results are cached for 5 minutes per `(user_id, query_type, top_k,
   clean_query, temporal_hint)`.

### Storage layout
```
PostgreSQL
├── users                     # email, username, bcrypt hash, is_admin
├── memories                  # url, title, page_text, signals, user_id (NOT NULL)
├── embedding_references      # memory_id ↔ chroma_id
├── query_logs                # user's search history (user_id required)
└── blockchain_records        # tx_hash, block_number per anchored memory

ChromaDB (embedded, /data/chroma in production)
└── dmre_memories             # 384-d vectors, metadata.user_id for filtering

Chain (optional)
└── MemoryIntegrity contract  # mapping(bytes32 contentHash → AnchorRecord)
```

---

---

## API reference (current routes)

```
POST   /api/auth/signup            create account, send OTP email, return JWT
POST   /api/auth/login-json        login (JSON body)
POST   /api/auth/login             login (OAuth2 form, used by /docs)
GET    /api/auth/me                current user (includes is_admin + email_verified)
POST   /api/auth/verify-email      submit 6-digit OTP                  [authenticated]
POST   /api/auth/resend-otp        request a fresh OTP (30 s cooldown) [authenticated]

POST   /api/memories               capture a page                   [verified]
GET    /api/memories               list own captures (paginated)    [verified]
DELETE /api/memories/{id}          delete one of own captures       [verified]
GET    /api/queries                own search history (paginated)   [verified]
POST   /api/queries/email-export   email yourself a digest          [verified]
DELETE /api/account                delete current account + all data [authenticated]

POST   /api/search/text            semantic text search             [verified]
POST   /api/search/voice           voice search via Whisper         [verified]
POST   /api/search/image           image search via Tesseract       [verified]
POST   /api/search/email-export    run a search and email yourself  [verified]
GET    /api/verify/{memory_id}     blockchain integrity check       [verified, owner-only]

GET    /api/admin/stats            counts only — no content         [admin]
GET    /api/admin/users            roster + memory counts           [admin]
DELETE /api/admin/users/{id}       remove abusive account           [admin]

GET    /health                     liveness + version
```

Where `[verified]` means the route requires `email_verified=true`. Unverified
users get HTTP 403 with a clear "verify your email first" message.

## License & contact

Project author: **Durell Nji** &nbsp;·&nbsp; durellnji16@gmail.com
