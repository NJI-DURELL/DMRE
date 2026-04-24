# =============================================================================
# backend/app/models/embedding_reference.py
# ORM model for the `embedding_references` table.
# Tracks the mapping between a Memory record and its vector chunks stored in
# ChromaDB; one Memory produces multiple chunks via the sliding-window chunker.
# =============================================================================

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class EmbeddingReference(Base, TimestampMixin):
    __tablename__ = "embedding_references"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)

    memory_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identifier used to retrieve this chunk's vector from ChromaDB.
    chroma_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        doc="ID passed to ChromaDB when the chunk was added; format: {memory_id}_{chunk_index}",
    )

    # Position of this chunk within the page text (0-based).
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # The actual text slice — stored here so snippets can be returned without
    # a round-trip to ChromaDB.
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # --- Relationships ---
    memory: Mapped["Memory"] = relationship(  # noqa: F821
        back_populates="embedding_references",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<EmbeddingReference memory={self.memory_id!r} "
            f"chunk={self.chunk_index} chroma={self.chroma_id!r}>"
        )
