"""
One-shot script: anchor all Memory rows that have no BlockchainRecord yet.
Run once after deploying the smart contract to backfill existing memories.

Usage:
    .venv/Scripts/python anchor_existing.py
"""

import asyncio
import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.models.base import generate_uuid
from app.models.blockchain_record import BlockchainRecord
from app.models.memory import Memory
from app.services import blockchain_service

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        # Find memories with no blockchain record
        result = await db.execute(
            select(Memory).where(
                ~Memory.id.in_(select(BlockchainRecord.memory_id))
            )
        )
        memories = result.scalars().all()

    if not memories:
        log.info("All memories already anchored. Nothing to do.")
        await engine.dispose()
        return

    log.info("Found %d unanchored memories. Anchoring now...", len(memories))

    async with Session() as db:
        for mem in memories:
            raw = mem.url + mem.title + mem.page_text
            content_hash = hashlib.sha256(raw.encode()).hexdigest()
            try:
                result = blockchain_service.anchor_hash(mem.id, content_hash)
                bc = BlockchainRecord(
                    id=generate_uuid(),
                    memory_id=mem.id,
                    tx_hash=result["tx_hash"],
                    block_number=result["block_number"],
                    content_hash=content_hash,
                )
                db.add(bc)
                await db.commit()
                log.info("  Anchored %s  tx=%s  block=%s", mem.id, result["tx_hash"], result["block_number"])
            except Exception as exc:
                log.error("  FAILED %s: %s", mem.id, exc)

    await engine.dispose()
    log.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
