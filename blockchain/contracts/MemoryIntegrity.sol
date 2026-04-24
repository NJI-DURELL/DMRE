// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * MemoryIntegrity — on-chain anchor for DMRE memory content hashes.
 *
 * Each memory captured by the extension gets its SHA-256 content hash
 * written here exactly once.  The backend can later call verify() to
 * confirm a given hash was anchored and retrieve the block timestamp,
 * providing tamper-evidence for the browsing record.
 */
contract MemoryIntegrity {
    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    /// Emitted when a new hash is anchored.
    event HashAnchored(
        bytes32 indexed contentHash,
        address indexed anchor,
        uint256 timestamp
    );

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    struct AnchorRecord {
        address anchor;     // address that wrote the record
        uint256 timestamp;  // block.timestamp at write time
        bool exists;
    }

    /// contentHash → AnchorRecord
    mapping(bytes32 => AnchorRecord) private _records;

    // -----------------------------------------------------------------------
    // External functions
    // -----------------------------------------------------------------------

    /**
     * @notice Anchor a content hash on-chain.
     * @dev Each hash can only be anchored once (idempotency guard).
     * @param contentHash  SHA-256 hash of the memory's page text (as bytes32).
     */
    function anchor(bytes32 contentHash) external {
        require(!_records[contentHash].exists, "MemoryIntegrity: already anchored");

        _records[contentHash] = AnchorRecord({
            anchor: msg.sender,
            timestamp: block.timestamp,
            exists: true
        });

        emit HashAnchored(contentHash, msg.sender, block.timestamp);
    }

    /**
     * @notice Check whether a hash was previously anchored.
     * @return exists     true if the hash is on-chain.
     * @return anchorAddr address that wrote the record (zero if not found).
     * @return timestamp  block timestamp of the anchoring (0 if not found).
     */
    function verify(bytes32 contentHash)
        external
        view
        returns (bool exists, address anchorAddr, uint256 timestamp)
    {
        AnchorRecord storage rec = _records[contentHash];
        return (rec.exists, rec.anchor, rec.timestamp);
    }

    /**
     * @notice Convenience: anchor multiple hashes in one transaction.
     * @param hashes  Array of SHA-256 hashes to anchor.
     */
    function anchorBatch(bytes32[] calldata hashes) external {
        for (uint256 i = 0; i < hashes.length; i++) {
            if (!_records[hashes[i]].exists) {
                _records[hashes[i]] = AnchorRecord({
                    anchor: msg.sender,
                    timestamp: block.timestamp,
                    exists: true
                });
                emit HashAnchored(hashes[i], msg.sender, block.timestamp);
            }
        }
    }
}
