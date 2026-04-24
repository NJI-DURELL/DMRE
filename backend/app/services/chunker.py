# =============================================================================
# backend/app/services/chunker.py
# Sliding-window text chunker for the DMRE preprocessing pipeline.
# Splits raw page text into overlapping word-level windows before embedding;
# window=400 and overlap=100 are fixed project constraints documented in the
# project report and must not be changed without retraining the re-ranker.
# =============================================================================


def chunk_text(
    text: str,
    window: int = 400,
    overlap: int = 100,
) -> list[str]:
    """
    Split *text* into overlapping word windows.

    Args:
        text:    Raw page text (any length).
        window:  Number of words per chunk.  Default: 400.
        overlap: Number of words shared between consecutive chunks.  Default: 100.

    Returns:
        List of non-empty chunk strings.  Returns ``[""]`` for empty input so
        callers always receive at least one item to embed.
    """
    if not text or not text.strip():
        return [""]

    words = text.split()
    if len(words) <= window:
        # Short page — entire text is one chunk.
        return [" ".join(words)]

    step = window - overlap          # words advanced per iteration
    chunks: list[str] = []
    start = 0

    while start < len(words):
        chunk_words = words[start : start + window]
        chunks.append(" ".join(chunk_words))
        start += step

    return chunks


def chunk_count(text: str, window: int = 400, overlap: int = 100) -> int:
    """Return how many chunks *text* will produce without materialising them."""
    words = text.split() if text and text.strip() else []
    if not words or len(words) <= window:
        return 1
    step = window - overlap
    count = 0
    start = 0
    while start < len(words):
        count += 1
        start += step
    return count
