# =============================================================================
# backend/app/services/embedding_service.py
# Sentence-BERT embedding service for the DMRE semantic retrieval pipeline.
# Wraps the all-MiniLM-L6-v2 model (384-dim vectors) as a module-level
# singleton so the ~80 MB model is loaded once and reused across all requests.
# =============================================================================

from __future__ import annotations

_model = None  # lazy singleton


def _get_model():
    """Load all-MiniLM-L6-v2 on first call; return cached instance thereafter."""
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers==2.7.0"
        ) from exc

    # all-MiniLM-L6-v2 is the only model permitted by the project constraints.
    _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts.

    Args:
        texts: Non-empty list of strings to embed.

    Returns:
        List of 384-dimensional float vectors, one per input string.
    """
    model = _get_model()
    vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    """Convenience wrapper — embed a single query string and return its vector."""
    return embed([text])[0]
