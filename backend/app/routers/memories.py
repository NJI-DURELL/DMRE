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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.base import generate_uuid
from app.models.blockchain_record import BlockchainRecord
from app.models.embedding_reference import EmbeddingReference
from app.models.memory import Memory
from app.schemas.memory import MemoryCreate, MemoryResponse
from app.services import chunker, embedding_service, vector_store
from app.services import blockchain_service

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
) -> MemoryResponse:
    # ------------------------------------------------------------------
    # 1. Compute SHA-256 content hash (url + title + page_text)
    # ------------------------------------------------------------------
    raw_content = payload.url + payload.title + payload.page_text
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
        page_text=payload.page_text,
        visited_at=visited_at,
        dwell_time=payload.dwell_time,
        visit_count=payload.visit_count,
        content_hash=content_hash,
        user_id=payload.user_id,
    )
    db.add(memory)
    await db.flush()  # assigns created_at / updated_at from DB defaults

    # ------------------------------------------------------------------
    # 3. Chunk + embed page text
    # ------------------------------------------------------------------
    try:
        chunks = chunker.chunk_text(payload.page_text)
        embeddings = embedding_service.embed(chunks)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding service unavailable: {exc}",
        ) from exc

    # ------------------------------------------------------------------
    # 4. Add chunks to ChromaDB
    # ------------------------------------------------------------------
    chroma_ids = [f"{memory_id}_{i}" for i in range(len(chunks))]
    chroma_metadatas = [
        {
            "memory_id": memory_id,
            "url": payload.url,
            "title": payload.title,
            # ChromaDB metadata values must be str/int/float/bool.
            "visited_at": visited_at.isoformat(),
            "visit_count": payload.visit_count,
            "dwell_time": float(payload.dwell_time),
        }
        for _ in chunks
    ]
    try:
        vector_store.add_chunks(chroma_ids, embeddings, chunks, chroma_metadatas)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vector store unavailable: {exc}",
        ) from exc

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
    # ------------------------------------------------------------------
    anchored = False
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
    except Exception as exc:  # noqa: BLE001
        logger.debug("Blockchain anchor skipped for memory %s: %s", memory_id, exc)

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
