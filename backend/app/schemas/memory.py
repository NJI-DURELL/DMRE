# =============================================================================
# backend/app/schemas/memory.py
# Pydantic schemas for the /api/memories endpoint.
# MemoryCreate mirrors the payload the Chrome extension POSTs; MemoryResponse
# is what the API returns after ingestion, including derived fields like
# chunk_count and blockchain_anchored.
# =============================================================================

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    """Payload sent by the Chrome extension for each captured page visit."""

    url: str = Field(..., description="Full URL of the visited page.")
    title: str = Field(default="", description="Page <title> extracted by the extension.")
    page_text: str = Field(default="", description="Visible body text extracted by content.js.")
    visited_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp of the visit. Defaults to server time if omitted.",
    )
    dwell_time: float = Field(
        default=0.0,
        ge=0.0,
        description="Seconds the user spent on the page.",
    )
    visit_count: int = Field(
        default=1,
        ge=1,
        description="Number of times this URL has been visited (cumulative).",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user ID if the dashboard is logged in.",
    )


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
        description="True if the hash was successfully anchored on Ganache."
    )

    model_config = ConfigDict(from_attributes=True)
