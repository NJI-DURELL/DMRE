# =============================================================================
# backend/app/routers/memories.py
# POST /api/memories — ingest a browser visit captured by the Chrome extension.
# Full pipeline: hash → store in PostgreSQL → chunk → embed → store in ChromaDB
# → anchor hash on Ganache (skipped gracefully if not deployed yet).
# =============================================================================

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, get_current_verified_user
from app.models.base import generate_uuid
from app.models.blockchain_record import BlockchainRecord
from app.models.embedding_reference import EmbeddingReference
from app.models.memory import Memory
from app.models.query_log import QueryLog
from app.models.user import User
from app.schemas.memory import (
    MAX_PAGE_TEXT_LEN,
    MemoryCreate,
    MemoryListItem,
    MemoryResponse,
    QueryListItem,
)
from app.schemas.search import EmailExportResponse
from app.services import chunker, embedding_service, vector_store
from app.services import blockchain_service
from app.services.blockchain_service import BlockchainUnavailable
from app.services.email_service import EmailDeliveryError, send_activity_export

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/memories",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a browser memory",
    description=(
        "Accepts a page visit captured by the Chrome extension. "
        "Chunks the page text, embeds each chunk with Sentence-BERT, stores vectors "
        "in ChromaDB, persists metadata in PostgreSQL, and anchors a SHA-256 hash "
        "on the local Ganache blockchain."
    ),
)
async def create_memory(
    payload: MemoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> MemoryResponse:
    # ------------------------------------------------------------------
    # 0. Defensive truncation
    # The Pydantic schema already enforces a max_length, but we belt-and-brace
    # truncate here so any future caller that bypasses the schema can't OOM
    # the embedder.  page_text is the only realistic risk in practice.
    # ------------------------------------------------------------------
    page_text = (payload.page_text or "")[:MAX_PAGE_TEXT_LEN]

    # ------------------------------------------------------------------
    # 1. Compute SHA-256 content hash (url + title + page_text)
    # ------------------------------------------------------------------
    raw_content = payload.url + payload.title + page_text
    content_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # 2. Create and persist the Memory row
    # ------------------------------------------------------------------
    memory_id = generate_uuid()
    visited_at = payload.visited_at or datetime.now(timezone.utc)

    memory = Memory(
        id=memory_id,
        url=payload.url,
        title=payload.title,
        page_text=page_text,
        visited_at=visited_at,
        dwell_time=payload.dwell_time,
        visit_count=payload.visit_count,
        click_count=payload.click_count,
        scroll_depth=payload.scroll_depth,
        content_hash=content_hash,
        user_id=current_user.id,
    )
    db.add(memory)
    await db.flush()  # assigns created_at / updated_at from DB defaults

    # ------------------------------------------------------------------
    # 3. Chunk + embed page text
    # ------------------------------------------------------------------
    try:
        chunks = chunker.chunk_text(page_text)
        embeddings = embedding_service.embed(chunks) if chunks else []
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding service unavailable: {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001 — last-resort barrier
        # Garbled / encoding-broken pages occasionally crash the chunker or
        # the embedder.  Better to drop the chunks and keep the Memory row
        # than to fail the whole request and leave the user with a
        # half-saved capture.
        logger.warning("Chunk/embed failed for memory %s: %s", memory_id, exc)
        chunks, embeddings = [], []

    # ------------------------------------------------------------------
    # 4. Add chunks to ChromaDB
    # ------------------------------------------------------------------
    chroma_ids = [f"{memory_id}_{i}" for i in range(len(chunks))]
    chroma_metadatas = [
        {
            "memory_id":   memory_id,
            "user_id":     current_user.id,
            "url":         payload.url,
            "title":       payload.title,
            "visited_at":  visited_at.isoformat(),
            "visit_count": payload.visit_count,
            "dwell_time":  float(payload.dwell_time),
            "click_count": payload.click_count,
            "scroll_depth": float(payload.scroll_depth),
        }
        for _ in chunks
    ]
    if chunks:
        try:
            vector_store.add_chunks(chroma_ids, embeddings, chunks, chroma_metadatas)
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Vector store unavailable: {exc}",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chroma add_chunks failed for memory %s: %s", memory_id, exc)
            chunks = []  # treat as un-indexed; metadata row still saved

    # ------------------------------------------------------------------
    # 5. Persist EmbeddingReference rows in PostgreSQL
    # ------------------------------------------------------------------
    refs = [
        EmbeddingReference(
            id=generate_uuid(),
            memory_id=memory_id,
            chroma_id=chroma_ids[i],
            chunk_index=i,
            chunk_text=chunks[i],
        )
        for i in range(len(chunks))
    ]
    db.add_all(refs)

    # ------------------------------------------------------------------
    # 6. Anchor hash on Ganache (best-effort — memory saved regardless)
    # When the chain is not configured (typical in hosted production), we
    # short-circuit instead of hitting the network.
    # ------------------------------------------------------------------
    anchored = False
    if blockchain_service.is_configured():
        try:
            bc_result = blockchain_service.anchor_hash(memory_id, content_hash)
            bc_record = BlockchainRecord(
                id=generate_uuid(),
                memory_id=memory_id,
                tx_hash=bc_result["tx_hash"],
                block_number=bc_result["block_number"],
                content_hash=content_hash,
            )
            db.add(bc_record)
            anchored = True
            logger.info("Memory %s anchored on-chain at block %s", memory_id, bc_result["block_number"])
        except BlockchainUnavailable as exc:
            logger.debug("Blockchain anchor skipped for memory %s: %s", memory_id, exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Blockchain anchor failed for memory %s: %s", memory_id, exc)

    await db.flush()

    return MemoryResponse(
        id=memory.id,
        url=memory.url,
        title=memory.title,
        content_hash=memory.content_hash,
        visited_at=memory.visited_at,
        dwell_time=memory.dwell_time,
        visit_count=memory.visit_count,
        created_at=memory.created_at,
        chunk_count=len(chunks),
        blockchain_anchored=anchored,
    )


# =============================================================================
# Per-user activity log endpoints
# Each user can browse, audit, and delete *their own* captures and search
# history.  No admin-style cross-user view exists by design — page content
# is private to the account that captured it.
# =============================================================================


@router.get(
    "/memories",
    response_model=list[MemoryListItem],
    summary="List the current user's captured memories (newest first).",
)
async def list_memories(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10_000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> list[MemoryListItem]:
    result = await db.execute(
        select(Memory)
        .where(Memory.user_id == current_user.id)
        .order_by(desc(Memory.visited_at))
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    return [MemoryListItem.model_validate(m) for m in rows]


@router.get(
    "/queries",
    response_model=list[QueryListItem],
    summary="List the current user's recent search queries (newest first).",
)
async def list_queries(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10_000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> list[QueryListItem]:
    result = await db.execute(
        select(QueryLog)
        .where(QueryLog.user_id == current_user.id)
        .order_by(desc(QueryLog.created_at))
        .limit(limit)
        .offset(offset)
    )
    rows = result.scalars().all()
    return [QueryListItem.model_validate(q) for q in rows]


@router.delete(
    "/memories/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete one of the current user's memories (and its vectors).",
)
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> None:
    result = await db.execute(
        select(Memory).where(
            Memory.id == memory_id,
            Memory.user_id == current_user.id,
        )
    )
    memory = result.scalar_one_or_none()
    if memory is None:
        # Same 404 whether the memory does not exist or belongs to someone
        # else — never confirm a foreign memory_id.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found.",
        )

    # Best-effort vector store cleanup; the Postgres cascade still wins if
    # Chroma is unreachable.
    try:
        vector_store.delete_memory_chunks(memory_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chroma cleanup failed for memory %s: %s", memory_id, exc)

    await db.delete(memory)


@router.delete(
    "/account",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Permanently delete the current user's account and ALL data.",
)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Wipes the user, all of their captured memories, embedding references,
    blockchain records, query logs, and Chroma vectors.  Required by the
    Chrome Web Store privacy policy: users must be able to revoke access
    and erase their data.
    """
    # Find every memory_id we'll need to scrub from Chroma before the cascade
    # nukes the rows.
    result = await db.execute(
        select(Memory.id).where(Memory.user_id == current_user.id)
    )
    memory_ids = [row[0] for row in result.all()]
    for mid in memory_ids:
        try:
            vector_store.delete_memory_chunks(mid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chroma cleanup failed for memory %s: %s", mid, exc)

    # Postgres CASCADE handles memories + embedding_references + blockchain_records.
    await db.delete(current_user)


@router.post(
    "/queries/email-export",
    response_model=EmailExportResponse,
    summary="Email the current user a digest of recent captures + searches.",
)
async def email_activity_export(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> EmailExportResponse:
    captures = (
        await db.execute(
            select(Memory)
            .where(Memory.user_id == current_user.id)
            .order_by(desc(Memory.visited_at))
            .limit(50)
        )
    ).scalars().all()

    queries = (
        await db.execute(
            select(QueryLog)
            .where(QueryLog.user_id == current_user.id)
            .order_by(desc(QueryLog.created_at))
            .limit(50)
        )
    ).scalars().all()

    cap_payload = [
        {"title": m.title, "url": m.url, "visited_at": m.visited_at.isoformat()}
        for m in captures
    ]
    q_payload = [
        {
            "query_text": q.query_text,
            "query_type": q.query_type,
            "result_count": q.result_count,
            "created_at": q.created_at.isoformat(),
        }
        for q in queries
    ]

    try:
        send_activity_export(
            to=current_user.email,
            username=current_user.username,
            captures=cap_payload,
            queries=q_payload,
        )
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not send the email: {exc}",
        )

    return EmailExportResponse(
        sent_to=current_user.email,
        items=len(cap_payload) + len(q_payload),
    )
