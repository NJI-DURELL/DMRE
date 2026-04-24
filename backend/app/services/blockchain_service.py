# =============================================================================
# backend/app/services/blockchain_service.py
# Blockchain integrity service for the DMRE verification layer.
# Connects to the local Ganache instance via web3.py and calls the deployed
# MemoryIntegrity smart contract to anchor and verify SHA-256 content hashes.
# =============================================================================

from __future__ import annotations

from app.config import settings

# ABI matching MemoryIntegrity.sol exactly (bytes32 hashes, not strings).
_CONTRACT_ABI = [
    {
        "inputs": [{"internalType": "bytes32", "name": "contentHash", "type": "bytes32"}],
        "name": "anchor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "contentHash", "type": "bytes32"}],
        "name": "verify",
        "outputs": [
            {"internalType": "bool",    "name": "exists",     "type": "bool"},
            {"internalType": "address", "name": "anchorAddr", "type": "address"},
            {"internalType": "uint256", "name": "timestamp",  "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "contentHash", "type": "bytes32"},
            {"indexed": True, "internalType": "address", "name": "anchor",      "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp",  "type": "uint256"},
        ],
        "name": "HashAnchored",
        "type": "event",
    },
]

_w3 = None
_contract = None


def _get_web3():
    global _w3
    if _w3 is not None:
        return _w3
    try:
        from web3 import Web3  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("web3 is not installed. Run: pip install web3") from exc

    instance = Web3(Web3.HTTPProvider(settings.ganache_rpc_url))
    if not instance.is_connected():
        raise ConnectionError(
            f"Cannot reach Ganache at {settings.ganache_rpc_url}. "
            "Run: ganache --port 7545 --deterministic"
        )
    _w3 = instance
    return _w3


def _get_contract():
    global _contract
    if _contract is not None:
        return _contract
    if not settings.contract_address:
        raise ValueError(
            "CONTRACT_ADDRESS is not set in .env. "
            "Deploy: cd blockchain && npx hardhat run scripts/deploy.js --network ganache"
        )
    from web3 import Web3  # noqa: PLC0415

    w3 = _get_web3()
    _contract = w3.eth.contract(
        address=Web3.to_checksum_address(settings.contract_address),
        abi=_CONTRACT_ABI,
    )
    return _contract


def _hex_to_bytes32(hex_hash: str) -> bytes:
    """Convert a hex SHA-256 digest (with or without 0x prefix) to bytes32."""
    h = hex_hash[2:] if hex_hash.startswith("0x") else hex_hash
    return bytes.fromhex(h.zfill(64))


def anchor_hash(memory_id: str, content_hash: str) -> dict:
    """
    Write a SHA-256 content hash to the blockchain.

    Args:
        memory_id:    Memory.id (used only for logging; contract stores by hash).
        content_hash: 64-char hex SHA-256 digest of (url + title + page_text).

    Returns:
        Dict with ``tx_hash`` (0x-prefixed str) and ``block_number`` (int).
    """
    w3 = _get_web3()
    contract = _get_contract()
    account = w3.eth.accounts[0]

    hash_bytes = _hex_to_bytes32(content_hash)
    tx_hash = contract.functions.anchor(hash_bytes).transact({"from": account})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return {
        "tx_hash": receipt["transactionHash"].hex(),
        "block_number": receipt["blockNumber"],
    }


def verify(_memory_id: str, expected_hash: str) -> dict:
    """
    Verify that a content hash was previously anchored on-chain.

    Args:
        _memory_id:    Memory.id (kept for API consistency; contract is hash-indexed).
        expected_hash: SHA-256 hex digest currently in PostgreSQL.

    Returns:
        Dict with ``verified`` (bool) and ``stored_hash`` (hex str or "").
    """
    contract = _get_contract()
    hash_bytes = _hex_to_bytes32(expected_hash)
    exists, _, _ = contract.functions.verify(hash_bytes).call()
    return {
        "memory_id": _memory_id,
        "stored_hash": expected_hash if exists else "",
        "expected_hash": expected_hash,
        "verified": exists,
    }
