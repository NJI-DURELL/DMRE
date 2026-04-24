# =============================================================================
# backend/app/routers/search.py
# Search endpoints: text, voice (Whisper), and image (Tesseract).
# All three modalities feed into the same two-stage retrieval pipeline:
# Sentence-BERT + ChromaDB top-20 → XGBoost re-ranker → top-5 results.
# =============================================================================

from __future__ import annotations

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.base import generate_uuid
from app.models.blockchain_record import BlockchainRecord
from app.models.query_log import QUERY_TYPE_IMAGE, QUERY_TYPE_TEXT, QUERY_TYPE_VOICE, QueryLog
from app.schemas.search import SearchResponse, SearchResult, TextSearchRequest
from app.services import embedding_service, reranker_service, vector_store

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Shared retrieval helper — called by all three search endpoints
# ---------------------------------------------------------------------------

async def _search(
    query_text: str,
    query_type: str,
    top_k: int,
    db: AsyncSession,
) -> SearchResponse:
    """
    Core two-stage retrieval:
    1. Embed query → ChromaDB top-20 candidates
    2. Re-rank with XGBoost → top-k results
    """
    if not query_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query text must not be empty.",
        )

    # Stage 1 — semantic retrieval
    try:
        query_embedding = embedding_service.embed_query(query_text)
        raw = vector_store.query(query_embedding, n_results=20)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    ids_list = raw.get("ids", [[]])[0]
    if not ids_list:
        _log_query(db, query_text, query_type, 0)
        return SearchResponse(query=query_text, query_type=query_type, results=[], result_count=0)

    docs_list = raw.get("documents", [[]])[0]
    metas_list = raw.get("metadatas", [[]])[0]
    dists_list = raw.get("distances", [[]])[0]

    # De-duplicate by memory_id (multiple chunks per page) — keep best chunk
    seen: dict[str, dict] = {}
    for doc, meta, dist in zip(docs_list, metas_list, dists_list):
        mid = meta.get("memory_id", "")
        sim = 1.0 - float(dist)  # cosine distance → similarity
        if mid not in seen or sim > seen[mid]["semantic_similarity"]:
            raw_visited = meta.get("visited_at", datetime.now(timezone.utc).isoformat())
            try:
                visited_at = datetime.fromisoformat(raw_visited)
            except (ValueError, TypeError):
                visited_at = datetime.now(timezone.utc)

            seen[mid] = {
                "memory_id": mid,
                "url": meta.get("url", ""),
                "title": meta.get("title", ""),
                "snippet": doc[:300],
                "semantic_similarity": sim,
                "visited_at": visited_at,
                "visit_count": int(meta.get("visit_count", 1)),
                "dwell_time": float(meta.get("dwell_time", 0.0)),
            }

    candidates = list(seen.values())

    # Stage 2 — XGBoost re-ranking
    try:
        ranked = reranker_service.rerank(query_text, candidates, top_k=top_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Check blockchain status for each result
    results: list[SearchResult] = []
    for c in ranked:
        anchored = await _is_anchored(c["memory_id"], db)
        results.append(
            SearchResult(
                memory_id=c["memory_id"],
                url=c["url"],
                title=c["title"],
                snippet=c["snippet"],
                score=float(c.get("semantic_similarity", 0.0)),
                semantic_similarity=c["semantic_similarity"],
                visited_at=c["visited_at"],
                visit_count=c["visit_count"],
                dwell_time=c["dwell_time"],
                blockchain_anchored=anchored,
            )
        )

    _log_query(db, query_text, query_type, len(results))
    return SearchResponse(
        query=query_text,
        query_type=query_type,
        results=results,
        result_count=len(results),
    )


def _log_query(db: AsyncSession, query_text: str, query_type: str, result_count: int) -> None:
    log = QueryLog(
        id=generate_uuid(),
        query_text=query_text,
        query_type=query_type,
        result_count=result_count,
    )
    db.add(log)


async def _is_anchored(memory_id: str, db: AsyncSession) -> bool:
    """Return True if a BlockchainRecord exists for this memory."""
    from sqlalchemy import select  # noqa: PLC0415

    result = await db.execute(
        select(BlockchainRecord.id).where(BlockchainRecord.memory_id == memory_id).limit(1)
    )
    return result.scalar() is not None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/search/text",
    response_model=SearchResponse,
    summary="Semantic text search",
)
async def search_text(
    body: TextSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Embed a text query and return the top re-ranked memories."""
    return await _search(body.query, QUERY_TYPE_TEXT, body.top_k, db)


@router.post(
    "/search/voice",
    response_model=SearchResponse,
    summary="Voice search (Whisper transcription)",
)
async def search_voice(
    file: UploadFile = File(..., description="Audio file (WAV, MP3, M4A, etc.)"),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Transcribe an audio upload with Whisper, then perform semantic search."""
    try:
        from app.services import transcription_service  # noqa: PLC0415
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    audio_bytes = await file.read()
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        query_text = transcription_service.transcribe(tmp_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Transcription failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not query_text.strip():
        raise HTTPException(status_code=422, detail="No speech detected in audio file.")

    return await _search(query_text, QUERY_TYPE_VOICE, 5, db)


@router.post(
    "/search/image",
    response_model=SearchResponse,
    summary="Image search (Tesseract OCR)",
)
async def search_image(
    file: UploadFile = File(..., description="Image file (PNG, JPEG, etc.)"),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Extract text from an uploaded image with Tesseract, then perform semantic search."""
    try:
        from app.services import ocr_service  # noqa: PLC0415
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    image_bytes = await file.read()
    try:
        query_text = ocr_service.extract_text(image_bytes)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"OCR failed: {exc}") from exc

    if not query_text.strip():
        raise HTTPException(status_code=422, detail="No text detected in image.")

    return await _search(query_text, QUERY_TYPE_IMAGE, 5, db)
