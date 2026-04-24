# =============================================================================
# backend/app/database.py
# SQLAlchemy async engine and session factory for the DMRE backend.
# Provides a get_db() dependency injected into every route that needs the DB;
# each request gets its own AsyncSession, committed or rolled back automatically.
# =============================================================================

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# ---------------------------------------------------------------------------
# Engine
# pool_pre_ping=True drops stale connections before use (survives DB restarts).
# echo=False in production; set to True locally if you want SQL logging.
# ---------------------------------------------------------------------------
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)

# ---------------------------------------------------------------------------
# Session factory
# expire_on_commit=False keeps ORM objects accessible after a commit without
# triggering an extra SELECT; important for returning Pydantic schemas from
# route handlers after the session has already committed.
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# Usage in a route:
#     async def my_route(db: AsyncSession = Depends(get_db)):
#         ...
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for a single request lifetime."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
