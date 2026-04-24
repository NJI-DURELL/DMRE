"""
Integration tests for POST /api/search/text|voice|image.
ChromaDB, embedding, and re-ranker are fully mocked.
"""

import io
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

MOCK_MEMORY_ID = "mem-test-1234"

_CHROMA_HIT = {
    "ids": [[MOCK_MEMORY_ID + "_0"]],
    "documents": [["Machine learning is a subset of artificial intelligence."]],
    "metadatas": [[{
        "memory_id": MOCK_MEMORY_ID,
        "url": "https://example.com/ml",
        "title": "Intro to ML",
        "visited_at": datetime.now(timezone.utc).isoformat(),
        "visit_count": 3,
        "dwell_time": 120.0,
    }]],
    "distances": [[0.15]],
}

_RANKED = [{
    "memory_id": MOCK_MEMORY_ID,
    "url": "https://example.com/ml",
    "title": "Intro to ML",
    "snippet": "Machine learning is a subset of artificial intelligence.",
    "semantic_similarity": 0.85,
    "visited_at": datetime.now(timezone.utc),
    "visit_count": 3,
    "dwell_time": 120.0,
}]


@pytest.fixture(autouse=True)
def mock_search_services():
    with (
        patch("app.routers.search.embedding_service.embed_query", return_value=[0.1] * 384),
        patch("app.routers.search.vector_store.query", return_value=_CHROMA_HIT),
        patch("app.routers.search.reranker_service.rerank", return_value=_RANKED),
    ):
        yield


# ---------------------------------------------------------------------------
# Text search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_text_search_returns_200(client):
    resp = await client.post("/api/search/text", json={"query": "machine learning"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_text_search_response_schema(client):
    resp = await client.post("/api/search/text", json={"query": "machine learning"})
    data = resp.json()
    assert data["query"] == "machine learning"
    assert data["query_type"] == "text"
    assert isinstance(data["results"], list)
    assert data["result_count"] == len(data["results"])


@pytest.mark.asyncio
async def test_text_search_result_fields(client):
    resp = await client.post("/api/search/text", json={"query": "machine learning"})
    result = resp.json()["results"][0]
    for field in ("memory_id", "url", "title", "snippet", "score", "visited_at"):
        assert field in result, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_text_search_empty_query_returns_422(client):
    resp = await client.post("/api/search/text", json={"query": "   "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_text_search_no_results(client):
    empty = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    with patch("app.routers.search.vector_store.query", return_value=empty):
        resp = await client.post("/api/search/text", json={"query": "obscure query"})
    assert resp.status_code == 200
    assert resp.json()["results"] == []
    assert resp.json()["result_count"] == 0


@pytest.mark.asyncio
async def test_text_search_top_k_respected(client):
    resp = await client.post("/api/search/text", json={"query": "test", "top_k": 3})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Voice search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_voice_search_returns_200(client):
    with patch("app.services.transcription_service.transcribe", return_value="machine learning"):
        dummy_audio = io.BytesIO(b"RIFF" + b"\x00" * 36)
        resp = await client.post(
            "/api/search/voice",
            files={"file": ("test.wav", dummy_audio, "audio/wav")},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_voice_search_empty_transcript_returns_422(client):
    with patch("app.services.transcription_service.transcribe", return_value="   "):
        dummy_audio = io.BytesIO(b"RIFF" + b"\x00" * 36)
        resp = await client.post(
            "/api/search/voice",
            files={"file": ("silent.wav", dummy_audio, "audio/wav")},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Image search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_image_search_returns_200(client):
    with patch("app.services.ocr_service.extract_text", return_value="machine learning"):
        dummy_img = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        resp = await client.post(
            "/api/search/image",
            files={"file": ("test.png", dummy_img, "image/png")},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_image_search_no_text_returns_422(client):
    with patch("app.services.ocr_service.extract_text", return_value=""):
        dummy_img = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        resp = await client.post(
            "/api/search/image",
            files={"file": ("blank.png", dummy_img, "image/png")},
        )
    assert resp.status_code == 422
