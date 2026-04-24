# =============================================================================
# backend/app/models/base.py
# Shared SQLAlchemy DeclarativeBase and TimestampMixin used by every ORM model.
# Centralising the base here ensures all models share the same metadata object,
# which Alembic uses for autogenerate and the test suite uses for table creation.
# =============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Project-wide SQLAlchemy declarative base.
    All ORM models must inherit from this class so they are registered in
    the shared MetaData instance that Alembic inspects for migrations.
    """
    pass


class TimestampMixin:
    """
    Adds created_at and updated_at columns to any model that inherits it.
    Both columns are timezone-aware UTC datetimes managed by the database.
    updated_at is refreshed automatically on every UPDATE via onupdate.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def generate_uuid() -> str:
    """Return a new UUID4 as a lowercase hex string (no hyphens)."""
    return uuid.uuid4().hex
