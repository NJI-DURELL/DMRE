# =============================================================================
# backend/app/services/__init__.py
# Package marker for the DMRE AI services layer.
# Each service module is independently importable; heavy models (SBERT, Whisper)
# are lazy-loaded on first call so the FastAPI app starts instantly.
# =============================================================================
