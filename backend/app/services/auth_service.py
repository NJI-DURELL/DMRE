# =============================================================================
# backend/app/services/auth_service.py
# Password hashing (bcrypt directly) and JWT issue/decode helpers.
#
# We use the `bcrypt` package directly rather than passlib because passlib 1.7.x
# (the latest release) is incompatible with bcrypt >= 4.1 — it crashes on
# import-time version detection on those wheels. bcrypt's own API is small
# enough that a thin wrapper here gives us a stable, future-proof primitive.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import settings

# bcrypt's classic 72-byte input cap. Anything longer is silently truncated by
# the algorithm itself; we truncate explicitly so the behaviour is documented
# and so longer passwords still match on verify.
_BCRYPT_INPUT_CAP = 72


def _coerce_password(plain: str) -> bytes:
    """UTF-8 encode and clip to bcrypt's 72-byte cap."""
    if plain is None:
        return b""
    return plain.encode("utf-8", errors="ignore")[:_BCRYPT_INPUT_CAP]


def hash_password(plain: str) -> str:
    """Generate a bcrypt hash. Returns the standard `$2b$...` ASCII form."""
    return bcrypt.hashpw(_coerce_password(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    """Constant-time comparison; never raises on malformed input."""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_coerce_password(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Bcrypt raises ValueError on a malformed hash; treat as a mismatch.
        return False


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Issue a JWT whose `sub` claim is the user_id."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


__all__ = [
    "JWTError",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
