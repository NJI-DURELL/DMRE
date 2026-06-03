# =============================================================================
# backend/app/main.py
# FastAPI application entry point for the DMRE backend.
# Configures CORS, mounts all API routers, and exposes a /health endpoint
# that confirms the app is alive and the database connection is reachable.
# =============================================================================

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.services.blockchain_service import BlockchainUnavailable

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from app.routers import admin, auth, memories, search, verify

logger = logging.getLogger("dmre")


# ---------------------------------------------------------------------------
# Lifespan: runs once at startup and once at shutdown.
# Good place to verify DB connectivity and warm up ML models later.
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    import asyncio
    from app.services import embedding_service, reranker_service

    # --- Startup ---
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    print("[DMRE] Database connection verified.")

    # Pre-load ML models in a thread so the event loop stays free.
    # Without this, the first real query pays a 1-3 s cold-start penalty.
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, embedding_service.warmup)
    print("[DMRE] Sentence-BERT model loaded and ready.")
    await loop.run_in_executor(None, reranker_service._get_model)
    print("[DMRE] XGBoost re-ranker loaded and ready.")

    yield

    # --- Shutdown ---
    await engine.dispose()
    print("[DMRE] Database engine disposed.")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="DMRE — Digital Memory Reconstruction Engine",
    description=(
        "Backend API for capturing browsing memories, performing semantic "
        "retrieval via Sentence-BERT + XGBoost re-ranking, and verifying "
        "content integrity via a local Ganache blockchain."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware
# Origins from CORS_ORIGINS are split into:
#   • literal entries  → allow_origins
#   • wildcard entries (`chrome-extension://*`) → translated to a regex so any
#     extension ID matches. Required because Chrome injects the extension's
#     own ID into the Origin header.
# ---------------------------------------------------------------------------
def _build_cors_args(origins: list[str]) -> dict:
    literals: list[str] = []
    regex_parts: list[str] = []
    for origin in origins:
        if "*" in origin:
            # Escape any regex metacharacters except the wildcard itself.
            import re
            esc = re.escape(origin).replace(r"\*", ".+")
            regex_parts.append(esc)
        else:
            literals.append(origin)
    args = dict(
        allow_origins=literals,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if regex_parts:
        args["allow_origin_regex"] = "|".join(regex_parts)
    return args


app.add_middleware(CORSMiddleware, **_build_cors_args(settings.cors_origins_list))

# ---------------------------------------------------------------------------
# Global exception handlers
# Convert every unhandled error into a clean JSON response so the dashboard,
# extension, and curl users never see an HTML stack trace or a hung request.
# ---------------------------------------------------------------------------
@app.exception_handler(BlockchainUnavailable)
async def _blockchain_unavailable_handler(_: Request, exc: BlockchainUnavailable):
    return JSONResponse(
        status_code=503,
        content={"detail": f"Blockchain layer unavailable: {exc}"},
    )


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(_: Request, exc: RequestValidationError):
    # Flatten Pydantic errors into a string the UI can render directly
    # (the default list-of-dicts shape often crashes naive UIs).
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
        msg = err.get("msg", "invalid value")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(parts) or "Invalid request payload."},
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router,     prefix="/api", tags=["auth"])
app.include_router(memories.router, prefix="/api", tags=["memories"])
app.include_router(search.router,   prefix="/api", tags=["search"])
app.include_router(verify.router,   prefix="/api", tags=["verify"])
app.include_router(admin.router,    prefix="/api", tags=["admin"])


# ---------------------------------------------------------------------------
# Health endpoint — a quick liveness probe.
# curl http://localhost:8000/health  →  {"status": "ok", "version": "1.0.0"}
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health():
    """Liveness probe — confirms the app is running and DB is reachable."""
    return {"status": "ok", "version": app.version}
