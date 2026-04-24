"""
Integration tests for GET /api/verify/{memory_id}.
"""

import hashlib
import pytest
from unittest.mock import patch

from app.models.memory import Memory
from app.models.blockchain_record import BlockchainRecord
from app.models.base import generate_uuid


# ---------------------------------------------------------------------------
# Helpers — seed DB rows directly via the test session
# ---------------------------------------------------------------------------

async def _seed_memory(db_session, url="https://example.com", title="T", page_text="P"):
    mid = generate_uuid()
    mem = Memory(
        id=mid,
        url=url,
        title=title,
        page_text=page_text,
        content_hash=hashlib.sha256((url + title + page_text).encode()).hexdigest(),
        visit_count=1,
        dwell_time=30.0,
    )
    db_session.add(mem)
    await db_session.commit()
    return mid


async def _seed_blockchain_record(db_session, memory_id, content_hash):
    bc = BlockchainRecord(
        id=generate_uuid(),
        memory_id=memory_id,
        tx_hash="0xdeadbeef",
        block_number=42,
        content_hash=content_hash,
    )
    db_session.add(bc)
    await db_session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_unknown_memory_returns_404(client):
    resp = await client.get("/api/verify/nonexistent-memory-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_verify_memory_without_blockchain_record_returns_404(client, db_session):
    mid = await _seed_memory(db_session)
    resp = await client.get(f"/api/verify/{mid}")
    assert resp.status_code == 404
    assert "blockchain" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_tampered_content_returns_verified_false(client, db_session):
    mid = await _seed_memory(db_session, page_text="Original content")
    # Anchor a hash for different content (simulate tampering)
    wrong_hash = hashlib.sha256(b"tampered").hexdigest()
    await _seed_blockchain_record(db_session, mid, wrong_hash)

    with patch(
        "app.routers.verify.blockchain_service.verify",
        return_value={"verified": False, "stored_hash": wrong_hash},
    ):
        resp = await client.get(f"/api/verify/{mid}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is False
    assert "INTEGRITY VIOLATION" in data["message"]


@pytest.mark.asyncio
async def test_verify_valid_memory_returns_verified_true(client, db_session):
    url, title, page_text = "https://example.com/v", "Verified", "Good content"
    mid = await _seed_memory(db_session, url=url, title=title, page_text=page_text)
    correct_hash = hashlib.sha256((url + title + page_text).encode()).hexdigest()
    await _seed_blockchain_record(db_session, mid, correct_hash)

    with patch(
        "app.routers.verify.blockchain_service.verify",
        return_value={"verified": True, "stored_hash": correct_hash},
    ):
        resp = await client.get(f"/api/verify/{mid}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert data["memory_id"] == mid
    assert data["tx_hash"] == "0xdeadbeef"
    assert data["block_number"] == 42
    assert "verified" in data["message"].lower()


@pytest.mark.asyncio
async def test_verify_response_schema(client, db_session):
    url, title, pt = "https://schema.test", "Schema", "Schema test"
    mid = await _seed_memory(db_session, url=url, title=title, page_text=pt)
    h = hashlib.sha256((url + title + pt).encode()).hexdigest()
    await _seed_blockchain_record(db_session, mid, h)

    with patch(
        "app.routers.verify.blockchain_service.verify",
        return_value={"verified": True, "stored_hash": h},
    ):
        resp = await client.get(f"/api/verify/{mid}")

    data = resp.json()
    for field in ("memory_id", "verified", "stored_hash", "expected_hash", "tx_hash", "block_number", "message"):
        assert field in data, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_verify_blockchain_unavailable_returns_503(client, db_session):
    url, title, pt = "https://bc-down.test", "BC Down", "Content"
    mid = await _seed_memory(db_session, url=url, title=title, page_text=pt)
    h = hashlib.sha256((url + title + pt).encode()).hexdigest()
    await _seed_blockchain_record(db_session, mid, h)

    with patch(
        "app.routers.verify.blockchain_service.verify",
        side_effect=ConnectionError("Ganache not reachable"),
    ):
        resp = await client.get(f"/api/verify/{mid}")

    assert resp.status_code == 503
