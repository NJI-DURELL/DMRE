# =============================================================================
# backend/alembic/env.py
# Alembic migration environment for DMRE.
# Uses asyncpg (the same driver as the FastAPI app) so psycopg2 is not needed.
# Reads DATABASE_URL from the .env file in backend/ at migration time.
# =============================================================================

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Make `app` importable when alembic is run from the backend/ directory.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# Import all models so their tables are registered in Base.metadata.
# ---------------------------------------------------------------------------
from app.models import Base  # noqa: E402

# ---------------------------------------------------------------------------
# Standard Alembic boilerplate
# ---------------------------------------------------------------------------
alembic_cfg = context.config
if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

target_metadata = Base.metadata

# Use the async DATABASE_URL (asyncpg) — no psycopg2 needed.
_db_url = os.environ.get("DATABASE_URL", "")
if not _db_url:
    raise RuntimeError(
        "DATABASE_URL is not set. "
        "Copy .env.example → .env and fill in your PostgreSQL credentials."
    )

# Render's managed Postgres exports postgresql:// (sync) and Heroku-style
# providers sometimes use postgres://. Force the asyncpg scheme so the
# create_async_engine call below doesn't blow up on a sync URL.
if _db_url.startswith("postgres://"):
    _db_url = "postgresql://" + _db_url[len("postgres://"):]
if _db_url.startswith("postgresql://"):
    _db_url = "postgresql+asyncpg://" + _db_url[len("postgresql://"):]


# ---------------------------------------------------------------------------
# Offline mode — generates SQL without a live DB connection
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connects to PostgreSQL via asyncpg and applies migrations
# ---------------------------------------------------------------------------
def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(_db_url, future=True)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
