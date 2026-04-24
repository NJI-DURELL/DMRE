# =============================================================================
# backend/app/schemas/search.py
# Pydantic schemas for the /api/search/* endpoints.
# A single SearchResponse shape is reused across text, voice, and image search
# so the dashboard's ResultsList component needs only one response parser.
# =============================================================================

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TextSearchRequest(BaseModel):
    """Request body for POST /api/search/text."""

    query: str = Field(..., min_length=1, description="Raw query string from the user.")
    top_k: int = Field(default=5, ge=1, le=20, description="Max results to return.")


class SearchResult(BaseModel):
    """A single re-ranked memory returned in the search response."""

    memory_id: str
    url: str
    title: str
    snippet: str = Field(description="First 300 chars of the best-matching chunk.")
    score: float = Field(description="XGBoost re-ranker predicted relevance score.")
    semantic_similarity: float = Field(description="Raw cosine similarity from ChromaDB.")
    visited_at: datetime
    visit_count: int
    dwell_time: float
    blockchain_anchored: bool = Field(
        default=False,
        description="True if this memory has an on-chain integrity record.",
    )


class SearchResponse(BaseModel):
    """Response for all three search endpoints (text / voice / image)."""

    query: str = Field(description="The final text query used for retrieval.")
    query_type: str = Field(description="One of: text, voice, image.")
    results: list[SearchResult]
    result_count: int


class VerifyResponse(BaseModel):
    """Response for GET /api/verify/{memory_id}."""

    memory_id: str
    verified: bool = Field(
        description="True if the on-chain hash matches the current content hash."
    )
    stored_hash: str = Field(description="Hash retrieved from the smart contract.")
    expected_hash: str = Field(description="SHA-256 recomputed from current DB content.")
    tx_hash: str = Field(description="Transaction hash of the anchoring transaction.")
    block_number: int | None
    message: str = Field(description="Human-readable verification summary.")
