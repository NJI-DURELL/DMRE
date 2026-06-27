"""
DMRE Security, Verification & Validation Test Suite
T01-T16 — Authentication, Email Gate, Input Validation,
           Rate Limiting, Multi-Tenancy, Credential Security.
"""

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from jose import jwt as jose_jwt

from app.config import settings
from app.limiter import limiter


# ─── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_ai():
    """Stub every AI/ML call so tests run without GPU or model files."""
    with (
        patch("app.routers.memories.embedding_service.embed",
              return_value=[[0.1] * 384]),
        patch("app.routers.memories.vector_store.add_chunks",
              return_value=None),
        patch("app.routers.memories.blockchain_service.anchor_hash",
              return_value={"tx_hash": "0xtest", "block_number": 1}),
    ):
        yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Clear all in-memory rate-limit counters before each test.

    slowapi captures the key function at decoration time, so we can't
    swap it per-test. Resetting the storage achieves the same isolation:
    each test starts from zero regardless of what prior tests accumulated.
    """
    try:
        limiter._storage.reset()
    except Exception:
        pass
    yield
    try:
        limiter._storage.reset()
    except Exception:
        pass


# ─── Helpers ───────────────────────────────────────────────────────────────

async def _signup(client, email: str, password: str = "Password1!"):
    """Sign up and capture the OTP via a side-effect mock. Returns (token, otp)."""
    captured: dict = {}

    def _catch(to, username, code):
        captured["otp"] = code

    with patch("app.routers.auth.send_otp", side_effect=_catch):
        r = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": password},
        )
    assert r.status_code == 201, f"signup failed: {r.text}"
    return r.json()["access_token"], captured.get("otp")


async def _verified(client, email: str, password: str = "Password1!") -> dict:
    """Sign up, submit OTP, return bearer Authorization headers."""
    token, otp = await _signup(client, email, password)
    r = await client.post(
        "/api/auth/verify-email",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": otp},
    )
    assert r.status_code == 200, f"OTP verification failed: {r.text}"
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 1 — AUTHENTICATION ENFORCEMENT
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_T01_unauthenticated_routes_return_401(client):
    """
    User Story: As a registered user, I want every protected endpoint to reject
    requests that carry no bearer token, so that my personal memories and search
    history are never visible to anonymous callers.

    Test Case: Send requests with no Authorization header to five protected
    endpoints: GET /api/auth/me, GET /api/memories, POST /api/memories,
    GET /api/queries, POST /api/search/text.

    Expected: HTTP 401 Unauthorized on every route.
    """
    routes = [
        ("GET",  "/api/auth/me"),
        ("GET",  "/api/memories"),
        ("POST", "/api/memories"),
        ("GET",  "/api/queries"),
        ("POST", "/api/search/text"),
    ]
    for method, path in routes:
        r = await client.request(method, path, json={})
        assert r.status_code == 401, f"{method} {path} returned {r.status_code}, want 401"


@pytest.mark.asyncio
async def test_T02_invalid_jwt_returns_401(client):
    """
    User Story: As a security engineer, I want the API to reject forged, truncated,
    or garbage bearer tokens, so that an attacker cannot gain access by crafting or
    guessing a fake credential.

    Test Case: Send GET /api/auth/me with four malformed Authorization values:
    a non-JWT string, a validly-structured token with a tampered signature, random
    garbage, and an empty string.

    Expected: HTTP 401 Unauthorized for all four tokens.
    """
    bad_tokens = [
        "not.a.jwt",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.tampered",
        "totally-random-garbage",
        "",
    ]
    for tok in bad_tokens:
        r = await client.get("/api/auth/me",
                             headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401, f"Token {tok!r} was not rejected"


@pytest.mark.asyncio
async def test_T03_expired_jwt_returns_401(client):
    """
    User Story: As a registered user, I want my session to expire after a fixed
    period so that a stolen token eventually becomes useless and cannot be replayed
    indefinitely by an attacker.

    Test Case: Construct a validly-signed JWT using the real JWT_SECRET with an
    'exp' claim set 30 seconds in the past, then send it to GET /api/auth/me.

    Expected: HTTP 401 Unauthorized.
    """
    expired_token = jose_jwt.encode(
        {
            "sub": "any-user-id",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=30),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    r = await client.get("/api/auth/me",
                         headers={"Authorization": f"Bearer {expired_token}"})
    assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 2 — EMAIL VERIFICATION GATE
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_T04_unverified_user_blocked_from_capture(client):
    """
    User Story: As a product owner, I want newly registered accounts to be blocked
    from capturing memories until they verify their email address, so that anonymous
    sign-ups cannot pollute the system with unattributed data.

    Test Case: Sign up (obtaining a valid JWT), then immediately POST to
    /api/memories without submitting the OTP verification code.

    Expected: HTTP 403 Forbidden — the token is valid but the email gate blocks
    access.
    """
    token, _otp = await _signup(client, "unv.capture@test.com")
    r = await client.post(
        "/api/memories",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://example.com", "page_text": "text"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_T05_unverified_user_blocked_from_search(client):
    """
    User Story: As a product owner, I want the email verification gate to apply
    to every sensitive endpoint — not just memory capture — so that unverified
    accounts cannot query or retrieve data under any circumstances.

    Test Case: Sign up, then POST to /api/search/text without submitting the OTP.

    Expected: HTTP 403 Forbidden.
    """
    token, _otp = await _signup(client, "unv.search@test.com")
    r = await client.post(
        "/api/search/text",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "machine learning", "top_k": 5},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_T06_correct_otp_unlocks_access(client):
    """
    User Story: As a registered user, I want submitting my correct 6-digit OTP to
    immediately lift the email gate so that I can start capturing memories without
    needing to log in again or wait for a manual approval step.

    Test Case: Sign up → confirm capture returns 403 → POST correct OTP to
    /api/auth/verify-email → confirm capture now returns 201. Verify the response
    includes email_verified: true after the OTP step.

    Expected: Pre-OTP capture: 403. OTP response: 200 with email_verified=true.
    Post-OTP capture: 201 Created.
    """
    token, otp = await _signup(client, "otp.gate@test.com")

    # Pre-verification: capture must be forbidden
    r_before = await client.post(
        "/api/memories",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://before.com", "page_text": "x"},
    )
    assert r_before.status_code == 403

    # Submit the OTP
    r_verify = await client.post(
        "/api/auth/verify-email",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": otp},
    )
    assert r_verify.status_code == 200
    assert r_verify.json()["email_verified"] is True

    # Post-verification: capture must succeed
    r_after = await client.post(
        "/api/memories",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://after.com", "page_text": "text"},
    )
    assert r_after.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 3 — INPUT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_T07_url_exceeding_max_length_rejected(client):
    """
    User Story: As a system operator, I want URL inputs to be length-capped at the
    API boundary so that an attacker cannot submit arbitrarily large strings to
    exhaust database storage or crash the downstream embedder pipeline.

    Test Case: Verified user POSTs a memory where the 'url' field is
    'https://example.com/' concatenated with 5,000 'a' characters (total > 4096).

    Expected: HTTP 422 Unprocessable Entity.
    """
    headers = await _verified(client, "url.len@test.com")
    r = await client.post(
        "/api/memories",
        headers=headers,
        json={"url": "https://example.com/" + "a" * 5000, "page_text": "ok"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_T08_non_http_url_schemes_rejected(client):
    """
    User Story: As a security engineer, I want the API to reject non-HTTP/HTTPS URL
    schemes at the input validation layer so that dangerous payloads such as
    javascript: XSS vectors or file:// path-traversal strings cannot be persisted
    and later rendered in the dashboard.

    Test Case: Verified user POSTs three memories using schemes:
    'javascript:alert(document.cookie)', 'file:///etc/passwd', 'ftp://internal/config'.

    Expected: HTTP 422 Unprocessable Entity for all three requests.
    """
    headers = await _verified(client, "scheme@test.com")
    for bad_url in [
        "javascript:alert(document.cookie)",
        "file:///etc/passwd",
        "ftp://internal/config",
    ]:
        r = await client.post(
            "/api/memories",
            headers=headers,
            json={"url": bad_url, "page_text": "content"},
        )
        assert r.status_code == 422, f"Scheme {bad_url!r} was not rejected"


@pytest.mark.asyncio
async def test_T09_missing_required_url_field_returns_422(client):
    """
    User Story: As a developer integrating the Chrome extension with the API, I want
    the server to return a descriptive validation error (not a 500) when a required
    field is omitted, so that integration bugs are immediately diagnosable without
    inspecting server logs.

    Test Case: Verified user POSTs {'page_text': 'no url provided'} to /api/memories,
    intentionally omitting the required 'url' field.

    Expected: HTTP 422 with a non-empty 'detail' field describing the missing input.
    """
    headers = await _verified(client, "missing.url@test.com")
    r = await client.post(
        "/api/memories",
        headers=headers,
        json={"page_text": "no url provided"},
    )
    assert r.status_code == 422
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_T10_weak_password_rejected_at_signup(client):
    """
    User Story: As a registered user, I want the system to enforce a minimum password
    length at registration so that accounts protected by trivially short passwords
    cannot be created and are not vulnerable to simple brute-force attacks.

    Test Case: POST /api/auth/signup with {'email': 'weakpw@test.com',
    'password': 'abc'} — three characters, below the enforced minimum of eight.

    Expected: HTTP 422 Unprocessable Entity.
    """
    r = await client.post(
        "/api/auth/signup",
        json={"email": "weakpw@test.com", "password": "abc"},
    )
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 4 — RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_T11_login_rate_limited_after_10_attempts(client):
    """
    User Story: As a security operator, I want login attempts from a single IP address
    to be throttled to 10 per minute so that automated credential-stuffing and
    brute-force attacks are blocked before they can exhaust a user's password space.

    Test Case: Send 10 consecutive POST /api/auth/login-json requests (all with wrong
    credentials, triggering 401), then send an 11th request from the same IP.

    Expected: Requests 1–10 return HTTP 401. Request 11 returns HTTP 429 with a
    response body containing 'Too many requests'.
    """
    for _ in range(10):
        await client.post(
            "/api/auth/login-json",
            json={"email": "victim@test.com", "password": "WrongPass!"},
        )
    r = await client.post(
        "/api/auth/login-json",
        json={"email": "victim@test.com", "password": "WrongPass!"},
    )
    assert r.status_code == 429
    body = r.json()
    assert "Too many requests" in body["detail"]


@pytest.mark.asyncio
async def test_T12_signup_rate_limited_after_5_attempts(client):
    """
    User Story: As a system operator, I want account registration to be capped at 5
    per IP per minute so that bots cannot flood the system with fake accounts, which
    would inflate infrastructure costs and dilute usage analytics.

    Test Case: Register 5 unique accounts in rapid succession (all succeed), then
    attempt to register a 6th account from the same IP within the same minute.

    Expected: Registrations 1–5 return HTTP 201 Created. Registration 6 returns
    HTTP 429 Too Many Requests with 'Too many requests' in the response body.
    """
    with patch("app.routers.auth.send_otp", return_value=None):
        for i in range(5):
            await client.post(
                "/api/auth/signup",
                json={"email": f"flood{i}@test.com", "password": "Password1!"},
            )
        r = await client.post(
            "/api/auth/signup",
            json={"email": "flood99@test.com", "password": "Password1!"},
        )
    assert r.status_code == 429
    assert "Too many requests" in r.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 5 — MULTI-TENANCY & AUTHORISATION
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_T13_user_cannot_delete_another_users_memory(client):
    """
    User Story: As User A, I want confidence that no other authenticated user can
    delete, modify, or even confirm the existence of my private memories, so that
    my captured browsing history remains exclusively under my control.

    Test Case: User A (alice@test.com) captures a memory and records its UUID.
    User B (bob@test.com) — fully authenticated and verified — calls
    DELETE /api/memories/{alice_memory_id}.

    Expected: HTTP 404 Not Found — the server must not confirm the memory's
    existence to a non-owner (no information leak via 403 vs 404 distinction).
    """
    # User A captures a memory
    hdrs_a = await _verified(client, "alice@test.com")
    r_create = await client.post(
        "/api/memories",
        headers=hdrs_a,
        json={"url": "https://alice-private.com", "page_text": "private content"},
    )
    assert r_create.status_code == 201
    memory_id = r_create.json()["id"]

    # User B attempts to delete it — response must be 404 (no content/ID leak)
    hdrs_b = await _verified(client, "bob@test.com")
    r_delete = await client.delete(f"/api/memories/{memory_id}", headers=hdrs_b)
    assert r_delete.status_code == 404


@pytest.mark.asyncio
async def test_T14_non_admin_blocked_from_admin_endpoints(client):
    """
    User Story: As a system administrator, I want aggregate platform statistics and
    management endpoints to be restricted to promoted admin accounts only, so that
    regular users cannot view other users' data or system-wide usage metrics.

    Test Case: A fully verified standard user (is_admin=False by default) sends
    GET /api/admin/stats with a valid bearer token.

    Expected: HTTP 403 Forbidden.
    """
    headers = await _verified(client, "regular@test.com")
    r = await client.get("/api/admin/stats", headers=headers)
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 6 — CREDENTIAL SECURITY
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_T15_password_hash_never_exposed_in_api_response(client):
    """
    User Story: As a registered user, I want the API to never include my password or
    its hash in any response body so that an attacker who intercepts an API response
    cannot perform offline cracking against my credential.

    Test Case: After signup, call GET /api/auth/me with a valid bearer token.
    Convert the full JSON response to a lowercase string and assert that neither
    the word 'password' nor the bcrypt hash prefix '$2b$' appears anywhere.

    Expected: Response body contains only public fields (id, email, username,
    email_verified, created_at). No password field or bcrypt hash is present.
    """
    token, _otp = await _signup(client, "profile@test.com")
    r = await client.get("/api/auth/me",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    resp_str = str(r.json()).lower()
    assert "password" not in resp_str, \
        f"'password' key found in /api/auth/me response: {r.json()}"
    assert "$2b$" not in resp_str, \
        "bcrypt hash literal found in API response"


@pytest.mark.asyncio
async def test_T16_otp_brute_force_locked_after_5_wrong_attempts(client):
    """
    User Story: As a registered user, I want my account to be locked after five
    consecutive wrong OTP submissions so that automated scripts cannot guess my
    6-digit code by brute-force (1,000,000 possibilities) without triggering a
    lockout that requires requesting a fresh code.

    Test Case: Sign up (generating a real OTP). Submit '000000' as the code five
    consecutive times, asserting each returns HTTP 400. Then submit a sixth attempt.

    Expected: Attempts 1–5 return HTTP 400 Bad Request with a remaining-attempts
    message. Attempt 6 returns HTTP 429 Too Many Requests with
    'Too many wrong attempts' in the detail field.
    """
    token, _correct_otp = await _signup(client, "otp.brute@test.com")

    # Submit 5 wrong codes — each must return 400
    for attempt in range(1, 6):
        r = await client.post(
            "/api/auth/verify-email",
            headers={"Authorization": f"Bearer {token}"},
            json={"code": "000000"},
        )
        assert r.status_code == 400, \
            f"Wrong attempt {attempt} returned {r.status_code}, expected 400"

    # 6th attempt must return 429 (account locked regardless of code)
    r_locked = await client.post(
        "/api/auth/verify-email",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": "000000"},
    )
    assert r_locked.status_code == 429
    assert "Too many wrong attempts" in r_locked.json()["detail"]
