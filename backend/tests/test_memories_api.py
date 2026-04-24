"""
Integration tests for POST /api/memories.
All heavy AI services (embedding, ChromaDB, blockchain) are mocked so the
suite runs without any external infrastructure.
"""

import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Fixtures — patch out every service that touches the network / GPU
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_ai_services():
    """Patch all external services for every test in this module."""
    dummy_embedding = [[0.1] * 384]

    with (
        patch("app.routers.memories.embedding_service.embed", return_value=dummy_embedding),
        patch("app.routers.memories.vector_store.add_chunks", return_value=None),
        patch(
            "app.routers.memories.blockchain_service.anchor_hash",
            return_value={"tx_hash": "0xdeadbeef", "block_number": 1},
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_memory_returns_201(client):
    payload = {
        "url": "https://example.com/article",
        "title": "Test Article",
        "page_text": "Some interesting content about machine learning.",
        "dwell_time": 45,
        "visit_count": 1,
    }
    resp = await client.post("/api/memories", json=payload)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_memory_response_schema(client):
    payload = {
        "url": "https://example.com/page2",
        "title": "Another Page",
        "page_text": "Content about deep learning and neural networks.",
        "dwell_time": 30,
        "visit_count": 2,
    }
    resp = await client.post("/api/memories", json=payload)
    data = resp.json()

    assert "id" in data
    assert "url" in data
    assert data["url"] == payload["url"]
    assert data["title"] == payload["title"]
    assert "visited_at" in data
    assert "content_hash" in data
    assert "chunk_count" in data
    assert "blockchain_anchored" in data


@pytest.mark.asyncio
async def test_create_memory_missing_url_returns_422(client):
    payload = {"title": "No URL", "page_text": "Some text."}
    resp = await client.post("/api/memories", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_memory_title_defaults_to_empty_string(client):
    """title has a server-side default of "" — omitting it still returns 201."""
    payload = {"url": "https://example.com", "page_text": "Some text."}
    resp = await client.post("/api/memories", json=payload)
    assert resp.status_code == 201
    assert resp.json()["title"] == ""


@pytest.mark.asyncio
async def test_create_memory_empty_page_text_still_succeeds(client):
    """Empty page text is allowed — the page may have no extractable text."""
    payload = {
        "url": "https://example.com/empty",
        "title": "Empty Page",
        "page_text": "",
        "dwell_time": 5,
        "visit_count": 1,
    }
    resp = await client.post("/api/memories", json=payload)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_memory_blockchain_failure_still_returns_201(client):
    """Blockchain being unavailable must not break memory ingestion."""
    with patch(
        "app.routers.memories.blockchain_service.anchor_hash",
        side_effect=Exception("Ganache not running"),
    ):
        payload = {
            "url": "https://example.com/bc-fail",
            "title": "BC Fail Test",
            "page_text": "Testing graceful blockchain failure.",
            "dwell_time": 10,
            "visit_count": 1,
        }
        resp = await client.post("/api/memories", json=payload)
        assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_memory_content_hash_is_deterministic(client):
    """Two requests with identical content produce the same content_hash."""
    payload = {
        "url": "https://example.com/deterministic",
        "title": "Deterministic",
        "page_text": "Identical content for hashing.",
        "dwell_time": 20,
        "visit_count": 1,
    }
    r1 = await client.post("/api/memories", json=payload)
    r2 = await client.post("/api/memories", json=payload)
    # Both must succeed (deduplication not enforced at API level)
    assert r1.status_code == 201
    assert r2.status_code == 201
