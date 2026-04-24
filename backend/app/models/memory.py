# =============================================================================
# backend/app/models/memory.py
# ORM model for the `memories` table — the core entity of the DMRE system.
# Each row represents one browser visit captured by the Chrome extension;
# content_hash (SHA-256) is used to anchor the record on the blockchain.
# =============================================================================

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Memory(Base, TimestampMixin):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=generate_uuid,
    )

    # Nullable FK: extension can capture pages without a logged-in user.
    user_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # --- Captured page data ---
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # --- Engagement signals used by the re-ranker ---
    visit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    dwell_time: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        doc="Seconds spent on the page, reported by the extension.",
    )
    visited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp of the page visit (from the extension, UTC).",
    )

    # --- Integrity ---
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        doc="SHA-256 hex digest of (url + title + page_text); anchored on-chain.",
    )

    # --- Relationships ---
    user: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="memories",
        lazy="select",
    )
    embedding_references: Mapped[list["EmbeddingReference"]] = relationship(  # noqa: F821
        back_populates="memory",
        cascade="all, delete-orphan",
        lazy="select",
    )
    blockchain_record: Mapped["BlockchainRecord | None"] = relationship(  # noqa: F821
        back_populates="memory",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Memory id={self.id!r} url={self.url[:60]!r}>"
