# =============================================================================
# backend/app/schemas/auth.py
# Pydantic schemas for the /api/auth/* endpoints.
# Sanitises email + username defensively so noisy input (leading whitespace,
# mixed case, embedded newlines) does not produce duplicate user rows.
# =============================================================================

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# bcrypt accepts up to 72 bytes; keep the upper bound well below that even
# after multibyte expansion so signup never silently truncates a password.
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128
MAX_USERNAME_LEN = 64

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LEN, max_length=MAX_PASSWORD_LEN)
    username: str | None = Field(default=None, max_length=MAX_USERNAME_LEN)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "username may only contain letters, numbers, '.', '_' and '-'"
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LEN)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until the token expires.")
    user: "UserPublic"


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    username: str
    created_at: datetime
    is_admin: bool = False
    email_verified: bool = False

    model_config = ConfigDict(from_attributes=True)


class VerifyEmailRequest(BaseModel):
    """6-digit code from the OTP email. Whitespace + dashes accepted."""
    code: str = Field(min_length=4, max_length=12)


class ResendOtpRequest(BaseModel):
    # Empty body is fine — current_user supplies the recipient.
    pass


TokenResponse.model_rebuild()
