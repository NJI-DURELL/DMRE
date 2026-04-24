# =============================================================================
# backend/app/__init__.py
# Package marker for the DMRE FastAPI application.
# Importing this package initialises nothing at module load time; all
# heavy resources (DB engine, ML models) are created lazily on first use.
# =============================================================================
