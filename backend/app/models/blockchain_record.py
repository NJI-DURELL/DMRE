# =============================================================================
# backend/app/models/blockchain_record.py
# ORM model for the `blockchain_records` table.
# Stores the result of anchoring a Memory's SHA-256 hash on the local Ganache
# blockchain; used by the /api/verify endpoint to confirm content integrity.
# =============================================================================

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class BlockchainRecord(Base, TimestampMixin):
    __tablename__ = "blockchain_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)

    # One-to-one: each Memory has at most one on-chain anchor.
    memory_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Ethereum transaction hash returned by web3.py after anchoring.
    tx_hash: Mapped[str] = mapped_column(
        String(66),
        nullable=False,
        doc="0x-prefixed 32-byte transaction hash from Ganache.",
    )

    # Block number in which the transaction was mined.
    block_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Snapshot of the hash that was anchored — allows detection of tampering
    # even if the Memory row is later modified.
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA-256 hex digest that was written to the smart contract.",
    )

    # --- Relationships ---
    memory: Mapped["Memory"] = relationship(  # noqa: F821
        back_populates="blockchain_record",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<BlockchainRecord memory={self.memory_id!r} "
            f"tx={self.tx_hash[:16]!r} block={self.block_number}>"
        )
