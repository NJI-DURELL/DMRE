# =============================================================================
# backend/app/routers/search.py
# Search endpoints: text, voice (Whisper), and image (Tesseract).
# All three modalities feed into the same two-stage retrieval pipeline:
# Sentence-BERT + ChromaDB top-20 → XGBoost re-ranker → top-5 results.
# =============================================================================

import logging
import tempfile
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status

from app.limiter import limiter, _user_id_or_ip
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_verified_user
from app.models.base import generate_uuid
from app.models.blockchain_record import BlockchainRecord
from app.models.query_log import QUERY_TYPE_IMAGE, QUERY_TYPE_TEXT, QUERY_TYPE_VOICE, QueryLog
from app.models.user import User
from app.schemas.search import (
    EmailExportResponse,
    SearchResponse,
    SearchResult,
    TextSearchRequest,
)
from app.services import embedding_service, query_processor, reranker_service, vector_store
from app.services.email_service import EmailDeliveryError, send_search_export

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Result cache — identical queries within 5 minutes return instantly.
# ---------------------------------------------------------------------------
_RESULT_CACHE_TTL  = 300   # seconds
_RESULT_CACHE_MAX  = 100   # maximum entries
_result_cache: OrderedDict[str, tuple[float, SearchResponse]] = OrderedDict()


def _cache_get(key: str) -> SearchResponse | None:
    if key not in _result_cache:
        return None
    ts, resp = _result_cache[key]
    if time.monotonic() - ts > _RESULT_CACHE_TTL:
        del _result_cache[key]
        return None
    _result_cache.move_to_end(key)
    return resp


def _cache_set(key: str, resp: SearchResponse) -> None:
    if len(_result_cache) >= _RESULT_CACHE_MAX:
        _result_cache.popitem(last=False)
    _result_cache[key] = (time.monotonic(), resp)


# ---------------------------------------------------------------------------
# Shared retrieval helper — called by all three search endpoints
# ---------------------------------------------------------------------------

def _keyword_coverage(query: str, text: str) -> float:
    """Fraction of meaningful query tokens (len > 2) that appear in the chunk text."""
    tokens = [t for t in query.lower().split() if len(t) > 2]
    if not tokens:
        return 0.0
    text_lower = text.lower()
    return sum(1 for t in tokens if t in text_lower) / len(tokens)


async def _search(
    query_text: str,
    query_type: str,
    top_k: int,
    db: AsyncSession,
    user: User,
) -> SearchResponse:
    """
    Core two-stage retrieval:
    1. Embed query → ChromaDB top-20 candidates
    2. Re-rank with XGBoost → top-k results
    Results are cached for 5 minutes so repeated identical queries are instant.
    """
    if not query_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query text must not be empty.",
        )

    # Defensive clamp — the schema enforces this for /search/text, but voice
    # and image both pass top_k=5 unconditionally; guard for any future caller.
    top_k = max(1, min(int(top_k or 5), 50))
    # Guard against a runaway query string crashing the embedder downstream.
    query_text = query_text[:2_000]

    # Strip conversational filler and extract any temporal hint.
    # "an article on scholarships I read in the morning"
    #   → clean_query = "scholarships", temporal_hint = "morning"
    clean_query, temporal_hint = query_processor.preprocess(query_text)
    time_window = query_processor.get_time_window(temporal_hint) if temporal_hint else None

    # Cache key uses the cleaned query so "find me a page about X" and
    # "X" hit the same cache slot.  user.id is part of the key so two users
    # who happen to type the same query never share results.
    cache_key = f"{user.id}:{query_type}:{top_k}:{clean_query}:{temporal_hint}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Stage 1 — semantic retrieval using the clean content query
    try:
        query_embedding = embedding_service.embed_query(clean_query)
        raw = vector_store.query(
            query_embedding,
            n_results=50,
            where={"user_id": user.id},
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vector store unavailable: {exc}",
        ) from exc

    # ChromaDB normally returns dicts with the expected keys, but a corrupted
    # collection or a future API change could produce something different.
    # Default every key to an empty 1-element list so the rest of the
    # pipeline never indexes off the end of None.
    raw = raw or {}
    ids_list = (raw.get("ids") or [[]])[0] or []
    if not ids_list:
        _log_query(db, query_text, query_type, 0, user.id)
        return SearchResponse(query=query_text, query_type=query_type, results=[], result_count=0, not_found=True)

    docs_list  = (raw.get("documents")  or [[]])[0] or []
    metas_list = (raw.get("metadatas")  or [[]])[0] or []
    dists_list = (raw.get("distances")  or [[]])[0] or []

    # De-duplicate by memory_id — keyword coverage also uses clean_query so
    # noise words like "read", "article", "morning" don't inflate scores for
    # unrelated pages.
    seen: dict[str, dict] = {}
    for doc, meta, dist in zip(docs_list, metas_list, dists_list):
        mid = meta.get("memory_id", "")
        sim = 1.0 - float(dist)
        chunk_score = 0.6 * sim + 0.4 * _keyword_coverage(clean_query, doc)
        if mid not in seen or chunk_score > seen[mid]["_chunk_score"]:
            raw_visited = meta.get("visited_at", datetime.now(timezone.utc).isoformat())
            try:
                visited_at = datetime.fromisoformat(raw_visited)
            except (ValueError, TypeError):
                visited_at = datetime.now(timezone.utc)

            seen[mid] = {
                "memory_id":           mid,
                "url":                 meta.get("url", ""),
                "title":               meta.get("title", ""),
                "snippet":             doc,
                "semantic_similarity": sim,
                "visited_at":          visited_at,
                "visit_count":         int(meta.get("visit_count", 1)),
                "dwell_time":          float(meta.get("dwell_time", 0.0)),
                "click_count":         int(meta.get("click_count", 0)),
                "scroll_depth":        float(meta.get("scroll_depth", 0.0)),
                "_chunk_score":        chunk_score,
            }

    # Drop candidates with low semantic similarity to the content query.
    # 0.20 is the practical floor — pages below this have no meaningful topic
    # overlap with the query and should not appear regardless of how recent or
    # engaging they are (e.g. claude.ai at 13% when searching "scholarships").
    _SEM_THRESHOLD = 0.20
    candidates = [c for c in seen.values() if c["semantic_similarity"] >= _SEM_THRESHOLD]

    if not candidates:
        _log_query(db, query_text, query_type, 0, user.id)
        return SearchResponse(query=query_text, query_type=query_type, results=[], result_count=0, not_found=True)

    # Stage 2 — XGBoost re-ranking; pass clean_query so term_overlap and
    # phrase-boost features only reward actual topic words, not filler.
    try:
        ranked = reranker_service.rerank(
            clean_query, candidates, top_k=top_k,
            query_embedding=query_embedding, time_window=time_window,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Re-ranker unavailable: {exc}",
        ) from exc

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

    _log_query(db, query_text, query_type, len(results), user.id)
    response = SearchResponse(
        query=query_text,
        query_type=query_type,
        results=results,
        result_count=len(results),
    )
    _cache_set(cache_key, response)
    return response


def _log_query(
    db: AsyncSession,
    query_text: str,
    query_type: str,
    result_count: int,
    user_id: str,
) -> None:
    log = QueryLog(
        id=generate_uuid(),
        user_id=user_id,
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
@limiter.limit("60/minute", key_func=_user_id_or_ip)
async def search_text(
    request: Request,
    body: TextSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> SearchResponse:
    """Embed a text query and return the top re-ranked memories."""
    return await _search(body.query, QUERY_TYPE_TEXT, body.top_k, db, current_user)


@router.post(
    "/search/voice",
    response_model=SearchResponse,
    summary="Voice search (Whisper transcription)",
)
async def search_voice(
    file: UploadFile = File(..., description="Audio file (WAV, MP3, M4A, etc.)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
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

    return await _search(query_text, QUERY_TYPE_VOICE, 5, db, current_user)


@router.post(
    "/search/image",
    response_model=SearchResponse,
    summary="Image search (Tesseract OCR)",
)
async def search_image(
    file: UploadFile = File(..., description="Image file (PNG, JPEG, etc.)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
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

    return await _search(query_text, QUERY_TYPE_IMAGE, 5, db, current_user)


@router.post(
    "/search/email-export",
    response_model=EmailExportResponse,
    summary="Run a text search and email the results to the current user.",
)
async def email_search_results(
    body: TextSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> EmailExportResponse:
    response = await _search(body.query, QUERY_TYPE_TEXT, body.top_k, db, current_user)

    payload = [
        {
            "url": r.url,
            "title": r.title,
            "snippet": r.snippet,
            "score": r.score,
        }
        for r in response.results
    ]
    try:
        send_search_export(
            to=current_user.email,
            username=current_user.username,
            query=response.query,
            results=payload,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not send the email: {exc}",
        )

    return EmailExportResponse(sent_to=current_user.email, items=len(payload))
