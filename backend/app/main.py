# =============================================================================
# backend/app/main.py
# FastAPI application entry point for the DMRE backend.
# Configures CORS, mounts all API routers, and exposes a /health endpoint
# that confirms the app is alive and the database connection is reachable.
# =============================================================================

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from app.routers import memories, search, verify


# ---------------------------------------------------------------------------
# Lifespan: runs once at startup and once at shutdown.
# Good place to verify DB connectivity and warm up ML models later.
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # --- Startup ---
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    print("[DMRE] Database connection verified.")
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
# Allow the React dashboard (localhost:3000) to call the backend during dev.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(memories.router, prefix="/api", tags=["memories"])
app.include_router(search.router,   prefix="/api", tags=["search"])
app.include_router(verify.router,   prefix="/api", tags=["verify"])


# ---------------------------------------------------------------------------
# Health endpoint — a quick liveness probe.
# curl http://localhost:8000/health  →  {"status": "ok", "version": "1.0.0"}
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health():
    """Liveness probe — confirms the app is running and DB is reachable."""
    return {"status": "ok", "version": app.version}
