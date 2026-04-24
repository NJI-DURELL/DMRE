"""Unit tests for the sliding-window text chunker."""

from app.services.chunker import chunk_text


def test_short_text_single_chunk():
    text = "hello world"
    chunks = chunk_text(text, window=400, overlap=100)
    assert chunks == ["hello world"]


def test_empty_string():
    # Empty input → single empty-string chunk so callers always get ≥1 item to embed.
    chunks = chunk_text("", window=400, overlap=100)
    assert chunks == [""]


def test_exact_window_size():
    words = ["word"] * 400
    text = " ".join(words)
    chunks = chunk_text(text, window=400, overlap=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_two_chunks_with_overlap():
    # 450 words → window=400, overlap=100 → 2 chunks
    words = [f"w{i}" for i in range(450)]
    text = " ".join(words)
    chunks = chunk_text(text, window=400, overlap=100)
    assert len(chunks) == 2
    # Last 100 words of chunk 0 should be first 100 words of chunk 1
    chunk0_words = chunks[0].split()
    chunk1_words = chunks[1].split()
    assert chunk0_words[-100:] == chunk1_words[:100]


def test_many_words_produces_correct_count():
    # 900 words: chunk0 = 0-399, chunk1 = 300-699, chunk2 = 600-899
    words = [f"x{i}" for i in range(900)]
    text = " ".join(words)
    chunks = chunk_text(text, window=400, overlap=100)
    assert len(chunks) == 3


def test_whitespace_only_returns_empty_chunk():
    # Whitespace-only input behaves the same as empty: one empty-string chunk.
    chunks = chunk_text("   \t\n  ", window=400, overlap=100)
    assert chunks == [""]


def test_no_overlap_variant():
    words = [f"a{i}" for i in range(800)]
    text = " ".join(words)
    chunks = chunk_text(text, window=400, overlap=0)
    assert len(chunks) == 2
    assert len(chunks[0].split()) == 400
    assert len(chunks[1].split()) == 400
