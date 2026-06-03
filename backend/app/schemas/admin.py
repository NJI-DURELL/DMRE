# =============================================================================
# backend/app/schemas/admin.py
# Schemas for /api/admin/* — count-only operational stats and a user roster.
# Crucially, NO captured content is exposed to admins.
# =============================================================================

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminStats(BaseModel):
    total_users: int
    admins: int
    users_signed_up_24h: int
    users_signed_up_7d: int
    total_memories: int
    memories_24h: int
    total_searches: int
    searches_24h: int
    blockchain_anchored: int = Field(description="Memories with an on-chain hash record.")


class AdminUserRow(BaseModel):
    id: str
    email: EmailStr
    username: str
    is_admin: bool
    created_at: datetime
    memory_count: int = Field(description="Count only; the page contents are not exposed.")
    last_search_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
