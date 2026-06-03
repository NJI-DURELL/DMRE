# =============================================================================
# backend/app/schemas/memory.py
# Pydantic schemas for the /api/memories endpoint.
# Hard-caps every text field so a hostile or accidentally huge payload (a
# 50 MB DOM dump, a runaway content script) cannot OOM the embedder or the
# Postgres row.  Also rejects non-http(s) URLs.
# =============================================================================

from __future__ import annotations

from datetime import datetime
from typing import Optional  # noqa: F401  — kept for downstream callers

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Limits chosen to keep memory bounded under heavy real-world pages while still
# capturing enough text to embed.  page_text > ~200 KB rarely contains useful
# signal once boilerplate is stripped.
MAX_URL_LEN       = 4_000
MAX_TITLE_LEN     = 1_000
MAX_PAGE_TEXT_LEN = 200_000


class MemoryCreate(BaseModel):
    """Payload sent by the Chrome extension for each captured page visit."""

    url: str = Field(..., max_length=MAX_URL_LEN, description="Full URL of the visited page.")
    title: str = Field(default="", max_length=MAX_TITLE_LEN, description="Page <title>.")
    page_text: str = Field(
        default="",
        max_length=MAX_PAGE_TEXT_LEN,
        description="Visible body text extracted by content.js.",
    )
    visited_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp of the visit. Defaults to server time if omitted.",
    )
    dwell_time: float = Field(default=0.0, ge=0.0, le=86_400.0, description="Seconds on page.")
    visit_count: int  = Field(default=1, ge=1, le=1_000_000, description="Cumulative visit count.")
    click_count: int  = Field(default=0, ge=0, le=1_000_000, description="Number of clicks.")
    scroll_depth: float = Field(default=0.0, ge=0.0, le=1.0, description="Fraction scrolled (0–1).")

    @field_validator("url")
    @classmethod
    def _validate_url_scheme(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("url must not be empty")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v

    @field_validator("title", "page_text")
    @classmethod
    def _coerce_optional_text(cls, v: str | None) -> str:
        # The extension occasionally sends null when a tag is missing; coerce
        # to empty string so the column constraint isn't violated.
        return v or ""


class MemoryResponse(BaseModel):
    """API response returned after a memory is successfully ingested."""

    id: str
    url: str
    title: str
    content_hash: str = Field(description="SHA-256 of (url + title + page_text).")
    visited_at: datetime
    dwell_time: float
    visit_count: int
    created_at: datetime
    chunk_count: int = Field(description="Number of text chunks embedded into ChromaDB.")
    blockchain_anchored: bool = Field(
        description="True if the hash was successfully anchored on the blockchain."
    )

    model_config = ConfigDict(from_attributes=True)


class MemoryListItem(BaseModel):
    """Compact row used by the History view (no page_text)."""

    id: str
    url: str
    title: str
    visited_at: datetime
    dwell_time: float
    visit_count: int
    click_count: int
    scroll_depth: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueryListItem(BaseModel):
    """Compact row for the search-history pane."""

    id: str
    query_text: str
    query_type: str
    result_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
