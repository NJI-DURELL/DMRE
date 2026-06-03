# =============================================================================
# backend/app/routers/auth.py
# /api/auth/signup, /api/auth/login (JSON + OAuth2 form), /api/auth/me,
# /api/auth/verify-email, /api/auth/resend-otp.
#
# Signup creates the user, issues a JWT, and emails a 6-digit OTP via real
# SMTP. The dashboard / extension keep the user gated to a "Verify your
# email" screen until they POST the correct code back to /verify-email.
# =============================================================================

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.base import generate_uuid
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    ResendOtpRequest,
    SignupRequest,
    TokenResponse,
    UserPublic,
    VerifyEmailRequest,
)
from app.services.auth_service import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.services.email_service import (
    EmailDeliveryError,
    send_otp,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OTP_TTL_MINUTES = 15
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 30  # client-side anti-spam


def _make_token_response(user: User) -> TokenResponse:
    token = create_access_token(
        subject=user.id,
        extra_claims={"email": user.email, "verified": user.email_verified},
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserPublic.model_validate(user),
    )


def _username_from_email(email: str, fallback_id: str) -> str:
    local = email.split("@", 1)[0][:60]
    return local or fallback_id[:8]


def _generate_otp() -> str:
    """Cryptographically random 6-digit numeric code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _normalise_code(code: str) -> str:
    return re.sub(r"\D", "", code or "")


def _stamp_new_otp(user: User) -> str:
    """Generate, hash, and store a new OTP on the user. Returns the plaintext
    code so the caller can email it. The caller is responsible for emailing."""
    code = _generate_otp()
    user.email_otp_hash = hash_password(code)
    user.email_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
    user.email_otp_attempts = 0
    user.email_otp_last_sent_at = datetime.now(timezone.utc)
    return code


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------

@router.post(
    "/auth/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account, send an OTP email, and return an access token.",
)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    email = payload.email.lower().strip()

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user_id = generate_uuid()
    username = (payload.username or "").strip() or _username_from_email(email, user_id)

    coll = await db.execute(select(User.id).where(User.username == username))
    if coll.scalar_one_or_none() is not None:
        username = f"{username}_{user_id[:6]}"

    user = User(
        id=user_id,
        email=email,
        username=username,
        password_hash=hash_password(payload.password),
        email_verified=False,
    )
    code = _stamp_new_otp(user)
    db.add(user)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email or username already exists.",
        )

    # Send the OTP email synchronously. If SMTP fails the get_db dependency
    # rolls back the user creation, so the client never ends up with an
    # un-emailable account.
    try:
        send_otp(to=email, username=username, code=code)
    except EmailDeliveryError as exc:
        # Roll back the user explicitly so the response is clean.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not send verification email: {exc}",
        )

    return _make_token_response(user)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Exchange email + password for a JWT access token (OAuth2 form).",
)
async def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    email = (form.username or "").lower().strip()
    return await _authenticate(email, form.password, db)


@router.post(
    "/auth/login-json",
    response_model=TokenResponse,
    summary="JSON login alternative used by the dashboard and extension.",
)
async def login_json(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    return await _authenticate(payload.email.lower().strip(), payload.password, db)


async def _authenticate(email: str, password: str, db: AsyncSession) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return _make_token_response(user)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get(
    "/auth/me",
    response_model=UserPublic,
    summary="Return the user record for the current bearer token.",
)
async def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(current_user)


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

@router.post(
    "/auth/verify-email",
    response_model=UserPublic,
    summary="Submit the 6-digit OTP from the verification email.",
)
async def verify_email(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPublic:
    if current_user.email_verified:
        # Already verified — just return the current state.
        return UserPublic.model_validate(current_user)

    if (
        current_user.email_otp_hash is None
        or current_user.email_otp_expires_at is None
        or current_user.email_otp_expires_at < datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Verification code expired. Request a new one.",
        )

    if current_user.email_otp_attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many wrong attempts. Request a new code.",
        )

    submitted = _normalise_code(payload.code)
    if not verify_password(submitted, current_user.email_otp_hash):
        current_user.email_otp_attempts += 1
        await db.flush()
        remaining = OTP_MAX_ATTEMPTS - current_user.email_otp_attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Wrong verification code. {remaining} attempt(s) left before lockout.",
        )

    current_user.email_verified = True
    current_user.email_otp_hash = None
    current_user.email_otp_expires_at = None
    current_user.email_otp_attempts = 0
    await db.flush()
    return UserPublic.model_validate(current_user)


@router.post(
    "/auth/resend-otp",
    response_model=UserPublic,
    summary="Request a fresh OTP email; rate-limited to once every 30 s.",
)
async def resend_otp(
    _: ResendOtpRequest = ResendOtpRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPublic:
    if current_user.email_verified:
        return UserPublic.model_validate(current_user)

    last = current_user.email_otp_last_sent_at
    if last is not None:
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            wait = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {wait}s before requesting another code.",
            )

    code = _stamp_new_otp(current_user)
    await db.flush()

    try:
        send_otp(to=current_user.email, username=current_user.username, code=code)
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not send verification email: {exc}",
        )

    return UserPublic.model_validate(current_user)
