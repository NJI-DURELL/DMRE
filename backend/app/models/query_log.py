# =============================================================================
# backend/app/models/query_log.py
# ORM model for the `query_logs` table.
# Records every search submitted by the user (text / voice / image) for
# analytics, debugging re-ranker performance, and academic evaluation.
# =============================================================================

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid

# Allowed query_type values — kept as constants to avoid magic strings.
QUERY_TYPE_TEXT = "text"
QUERY_TYPE_VOICE = "voice"
QUERY_TYPE_IMAGE = "image"


class QueryLog(Base, TimestampMixin):
    __tablename__ = "query_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)

    # Nullable FK: anonymous users may also search.
    user_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # The raw or transcribed query text fed into the embedding pipeline.
    query_text: Mapped[str] = mapped_column(Text, nullable=False)

    # One of: "text", "voice", "image"
    query_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=QUERY_TYPE_TEXT,
    )

    # Number of results returned after re-ranking.
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- Relationships ---
    user: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="query_logs",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<QueryLog id={self.id!r} type={self.query_type!r} "
            f"query={self.query_text[:40]!r}>"
        )
