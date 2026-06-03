# =============================================================================
# Dockerfile — DMRE backend (FastAPI + embedded ChromaDB)
# Single-process image used by Render / Fly / Railway. Embedded Chroma stores
# its data inside the container at $CHROMA_PERSIST_DIR (default /data/chroma);
# mount a persistent volume there so vectors survive deploys.
# =============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/root/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface/sentence-transformers

# System packages: tesseract for OCR, ffmpeg for Whisper audio, libpq for psycopg
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        ffmpeg \
        libgomp1 \
        ca-certificates \
        curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first so layer caching works on code changes.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Application source
COPY app          ./app
COPY alembic.ini  ./alembic.ini
COPY alembic      ./alembic
COPY start.sh     ./start.sh
RUN chmod +x ./start.sh

# Render injects $PORT; default to 8000 for `docker run` smoke tests.
ENV PORT=8000

# Health check used by Render's autodetect; harmless elsewhere.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

EXPOSE 8000

CMD ["./start.sh"]
