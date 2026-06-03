# =============================================================================
# backend/app/config.py
# Centralised application settings loaded from the .env file at startup.
# Uses Pydantic-Settings so every variable is type-checked and documented;
# a missing required variable raises a clear error before the app binds.
# =============================================================================

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

# Resolve .env relative to this file so it works regardless of working directory.
_ENV_FILE = Path(__file__).parent.parent / ".env"


def _coerce_async_url(url: str) -> str:
    """Force the async SQLAlchemy driver scheme.

    Render's managed Postgres injects ``postgresql://...``; the app uses
    ``create_async_engine`` which requires ``postgresql+asyncpg://...``.
    Without this rewrite the engine fails at boot.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


def _coerce_sync_url(url: str) -> str:
    """Force a sync (psycopg2-style) scheme for Alembic.

    Alembic's ``env.py`` here uses asyncpg too, but keep the sync form clean
    in case offline migrations are ever used.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    return url


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

    @field_validator("database_url", mode="after")
    @classmethod
    def _ensure_async_scheme(cls, v: str) -> str:
        return _coerce_async_url(v)

    @field_validator("database_url_sync", mode="after")
    @classmethod
    def _ensure_sync_scheme(cls, v: str) -> str:
        return _coerce_sync_url(v)

    # --- ChromaDB ---
    # When chroma_mode == "embedded" (default for hosted deploys) the app uses
    # chromadb.PersistentClient and stores vectors at chroma_persist_dir.
    # When chroma_mode == "http" the legacy HttpClient is used (chroma_host/port).
    chroma_mode: str = Field(default="embedded", description="'embedded' or 'http'.")
    chroma_persist_dir: str = Field(
        default="./chroma_data",
        description="Directory where embedded ChromaDB persists its data.",
    )
    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(default=8001)
    chroma_collection: str = Field(default="dmre_memories")

    # --- Blockchain (best-effort; skipped silently if missing) ---
    ganache_rpc_url: str = Field(default="")
    contract_address: str = Field(default="")

    # --- Auth ---
    jwt_secret: str = Field(
        default="insecure-dev-jwt-secret-change-in-prod",
        description="HMAC secret used to sign access tokens.",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(
        default=60 * 24 * 30,
        description="Access token lifetime in minutes (default: 30 days).",
    )

    # --- SMTP (real email delivery — required for OTP + email-export) ---
    smtp_host: str = Field(
        default="",
        description="SMTP server hostname (e.g. smtp.resend.com, smtp-relay.gmail.com).",
    )
    smtp_port: int = Field(default=587, description="SMTP port (587 for STARTTLS, 465 for SSL).")
    smtp_user: str = Field(default="")
    smtp_pass: str = Field(default="")
    smtp_tls: str = Field(
        default="starttls",
        description="One of: 'starttls' (port 587), 'ssl' (port 465), 'none' (port 25 / dev).",
    )
    smtp_from: str = Field(
        default="DMRE <noreply@dmre.local>",
        description="The From: header. Most providers require this match a verified sender.",
    )
    app_base_url: str = Field(
        default="http://localhost:3000",
        description="Used to build links inside emails (e.g. dashboard URL).",
    )

    # --- Application ---
    secret_key: str = Field(default="insecure-dev-secret-change-in-prod")
    cors_origins: str = Field(
        default="http://localhost:3000,chrome-extension://*",
        description=(
            "Comma-separated list of allowed CORS origins. "
            "Add the production dashboard origin and the published Chrome "
            "Extension ID (chrome-extension://<id>) before going live."
        ),
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
