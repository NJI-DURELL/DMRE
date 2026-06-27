# =============================================================================
# backend/app/limiter.py
# Shared slowapi Limiter singleton used across all routers.
# =============================================================================

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def _user_id_or_ip(request: Request) -> str:
    """Key function for per-user limits.

    Extracts the user_id claim from a Bearer JWT so each authenticated account
    gets its own counter. Falls back to the client IP for unauthenticated
    requests so anonymous callers can't bypass the limit.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from jose import jwt as _jwt
            from app.config import settings

            payload = _jwt.decode(
                auth[7:],
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass
    return get_remote_address(request)


# IP-based limiter — used for auth endpoints where no JWT exists yet.
limiter = Limiter(key_func=get_remote_address, default_limits=[])
