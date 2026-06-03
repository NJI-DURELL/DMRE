# =============================================================================
# backend/app/services/embedding_service.py
# Sentence-BERT embedding service for the DMRE semantic retrieval pipeline.
# Wraps the all-MiniLM-L6-v2 model (384-dim vectors) as a module-level
# singleton so the ~80 MB model is loaded once and reused across all requests.
#
# Query-level LRU cache: identical queries (same text, same case) skip
# re-embedding entirely — near-zero latency on repeated searches.
# =============================================================================

from __future__ import annotations

from collections import OrderedDict

_model = None          # lazy singleton — loaded once, reused forever
_CACHE_MAX  = 512      # maximum cached query embeddings
_embed_cache: OrderedDict[str, list[float]] = OrderedDict()


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

    _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def warmup() -> None:
    """Pre-load the model at startup so the first real query has no cold-start delay."""
    _get_model()


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
    """
    Embed a single query string.
    Results are cached by exact text — repeated identical queries cost ~0 ms.
    Cache is capped at _CACHE_MAX entries (LRU eviction).
    """
    if text in _embed_cache:
        _embed_cache.move_to_end(text)   # mark as recently used
        return _embed_cache[text]

    vector = embed([text])[0]

    if len(_embed_cache) >= _CACHE_MAX:
        _embed_cache.popitem(last=False)  # evict least-recently-used entry

    _embed_cache[text] = vector
    return vector
