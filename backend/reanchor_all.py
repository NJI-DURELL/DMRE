"""
Force re-anchor ALL memories against the current Ganache deployment.
Run this after every Ganache restart (when chain state is wiped).

Usage:
    .venv/Scripts/python reanchor_all.py
"""

import asyncio
import hashlib
import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
        memories_result = await db.execute(select(Memory))
        memories = memories_result.scalars().all()

        if not memories:
            log.info("No memories found in DB.")
            await engine.dispose()
            return

        log.info("Wiping %d old BlockchainRecord rows...", len(memories))
        await db.execute(delete(BlockchainRecord))
        await db.commit()

    log.info("Re-anchoring %d memories...", len(memories))

    async with Session() as db:
        for mem in memories:
            raw = mem.url + mem.title + mem.page_text
            content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
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
                log.info("  OK  %s  block=%s", mem.id, result["block_number"])
            except Exception as exc:
                if "already anchored" in str(exc):
                    # Hash is already on-chain (duplicate content). Record it so
                    # verify() can still confirm integrity via the shared hash.
                    bc = BlockchainRecord(
                        id=generate_uuid(),
                        memory_id=mem.id,
                        tx_hash="duplicate",
                        block_number=None,
                        content_hash=content_hash,
                    )
                    db.add(bc)
                    await db.commit()
                    log.info("  SHARED hash (already on-chain)  %s", mem.id)
                else:
                    log.error("  FAILED %s: %s", mem.id, exc)

    await engine.dispose()
    log.info("Done. All memories re-anchored on current chain.")


if __name__ == "__main__":
    asyncio.run(main())
