#!/bin/sh
# =============================================================================
# start.sh — Container entrypoint
# Runs Alembic migrations, then launches Uvicorn. Migration failures abort the
# boot so a half-migrated container never serves traffic.
# =============================================================================
set -e

echo "[DMRE] Running database migrations…"
alembic upgrade head

# Ensure the embedded Chroma persistence dir and HuggingFace model cache exist.
# These live on the persistent disk so a redeploy doesn't re-download Sentence-BERT.
mkdir -p "${CHROMA_PERSIST_DIR:-/data/chroma}"
mkdir -p "${HF_HOME:-/data/hf}"
mkdir -p "${SENTENCE_TRANSFORMERS_HOME:-/data/hf/sentence-transformers}"

echo "[DMRE] Starting Uvicorn on port ${PORT:-8000}…"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips="*"
