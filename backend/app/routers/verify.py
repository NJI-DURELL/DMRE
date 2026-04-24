# =============================================================================
# backend/app/routers/verify.py
# GET /api/verify/{memory_id} — integrity verification endpoint.
# Recomputes the SHA-256 hash of the stored content and checks it against
# the hash anchored on the local Ganache blockchain via the smart contract.
# =============================================================================

from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.blockchain_record import BlockchainRecord
from app.models.memory import Memory
from app.schemas.search import VerifyResponse
from app.services import blockchain_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/verify/{memory_id}",
    response_model=VerifyResponse,
    summary="Verify memory integrity on the blockchain",
    description=(
        "Recomputes the SHA-256 hash of the memory content stored in PostgreSQL "
        "and compares it with the hash anchored on Ganache. "
        "Returns verified=True only if both hashes match exactly."
    ),
)
async def verify_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
) -> VerifyResponse:
    # ------------------------------------------------------------------
    # 1. Fetch Memory from PostgreSQL
    # ------------------------------------------------------------------
    result = await db.execute(select(Memory).where(Memory.id == memory_id))
    memory: Memory | None = result.scalar_one_or_none()
    if memory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory '{memory_id}' not found.",
        )

    # ------------------------------------------------------------------
    # 2. Fetch BlockchainRecord (must exist to verify)
    # ------------------------------------------------------------------
    bc_result = await db.execute(
        select(BlockchainRecord).where(BlockchainRecord.memory_id == memory_id)
    )
    bc_record: BlockchainRecord | None = bc_result.scalar_one_or_none()
    if bc_record is None:
        raw_content = memory.url + memory.title + memory.page_text
        expected_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
        return VerifyResponse(
            memory_id=memory_id,
            verified=False,
            stored_hash="",
            expected_hash=expected_hash,
            tx_hash="",
            block_number=None,
            message="This memory has not been anchored on the blockchain yet.",
        )

    # ------------------------------------------------------------------
    # 3. Recompute SHA-256 from current DB content
    # ------------------------------------------------------------------
    raw_content = memory.url + memory.title + memory.page_text
    expected_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # 4. Verify against the blockchain
    # ------------------------------------------------------------------
    try:
        verification = blockchain_service.verify(memory_id, expected_hash)
    except (ConnectionError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Blockchain verification unavailable: {exc}",
        ) from exc

    verified = verification["verified"]
    message = (
        "Content integrity verified: on-chain hash matches the current record."
        if verified
        else (
            "INTEGRITY VIOLATION: on-chain hash does NOT match the current record. "
            "The content may have been tampered with after anchoring."
        )
    )

    logger.info("Verify memory=%s verified=%s", memory_id, verified)

    return VerifyResponse(
        memory_id=memory_id,
        verified=verified,
        stored_hash=verification["stored_hash"],
        expected_hash=expected_hash,
        tx_hash=bc_record.tx_hash,
        block_number=bc_record.block_number,
        message=message,
    )
