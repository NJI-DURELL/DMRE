# =============================================================================
# backend/app/models/__init__.py
# Re-exports all ORM model classes from one import point.
# Also ensures that every model module is imported before Alembic's env.py
# inspects Base.metadata, so no table is missing from the migration graph.
# =============================================================================

from app.models.base import Base  # noqa: F401 — must be first
from app.models.blockchain_record import BlockchainRecord  # noqa: F401
from app.models.embedding_reference import EmbeddingReference  # noqa: F401
from app.models.memory import Memory  # noqa: F401
from app.models.query_log import QueryLog  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "Base",
    "User",
    "Memory",
    "EmbeddingReference",
    "QueryLog",
    "BlockchainRecord",
]
