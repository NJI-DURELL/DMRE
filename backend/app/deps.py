# =============================================================================
# backend/app/deps.py
# FastAPI dependencies shared across routers.
# get_current_user resolves the bearer token to a User row; routes that depend
# on it are automatically protected (401 if the token is missing/invalid).
# =============================================================================

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import JWTError, decode_access_token

# tokenUrl is the endpoint Swagger UI's "Authorize" dialog will call.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise credentials_exc
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exc
    return user


async def get_current_verified_user(
    user: User = Depends(get_current_user),
) -> User:
    """Like get_current_user, but additionally rejects unverified emails.

    Use this on every route that should be unreachable until the user has
    completed the OTP flow (capture, search, history listing, exports).
    The auth router and /api/account explicitly use the unverified variant.
    """
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Check your inbox for the 6-digit code.",
        )
    return user
