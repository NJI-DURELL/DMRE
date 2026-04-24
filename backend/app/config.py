# =============================================================================
# backend/app/config.py
# Centralised application settings loaded from the .env file at startup.
# Uses Pydantic-Settings so every variable is type-checked and documented;
# a missing required variable raises a clear error before the app binds.
# =============================================================================

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Resolve .env relative to this file so it works regardless of working directory.
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    """
    All runtime configuration for the DMRE backend.
    Values are read from environment variables (or a .env file in the
    backend/ working directory).  Defaults are development-safe fallbacks.
    """

    # --- PostgreSQL ---
    database_url: str = Field(
        default="postgresql+asyncpg://dmre:dmre_pass@localhost:5432/dmre_db",
        description="Async SQLAlchemy URL (asyncpg driver) used by the app.",
    )
    database_url_sync: str = Field(
        default="postgresql://dmre:dmre_pass@localhost:5432/dmre_db",
        description="Sync SQLAlchemy URL (psycopg2) used by Alembic migrations.",
    )

    # --- ChromaDB ---
    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(default=8001)
    chroma_collection: str = Field(default="dmre_memories")

    # --- Blockchain ---
    ganache_rpc_url: str = Field(default="http://127.0.0.1:7545")
    contract_address: str = Field(default="")

    # --- Application ---
    secret_key: str = Field(default="insecure-dev-secret-change-in-prod")
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins.",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse the comma-separated CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Module-level singleton — imported by database.py and other services.
settings = Settings()
