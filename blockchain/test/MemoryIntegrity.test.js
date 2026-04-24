const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("MemoryIntegrity", function () {
  let contract;
  let owner, addr1;

  // A deterministic test hash (bytes32)
  const HASH_A = ethers.id("page content alpha");
  const HASH_B = ethers.id("page content beta");

  beforeEach(async function () {
    [owner, addr1] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("MemoryIntegrity");
    contract = await Factory.deploy();
    await contract.waitForDeployment();
  });

  // -------------------------------------------------------------------------
  // anchor()
  // -------------------------------------------------------------------------

  it("anchors a new hash and emits HashAnchored", async function () {
    const before = await latestTimestamp();
    const tx = await contract.anchor(HASH_A);
    const receipt = await tx.wait();
    const block = await ethers.provider.getBlock(receipt.blockNumber);
    const blockTs = BigInt(block.timestamp);

    // Event should have been emitted with the block's timestamp
    expect(blockTs).to.be.gte(before);

    const [exists, anchorAddr, ts] = await contract.verify(HASH_A);
    expect(exists).to.be.true;
    expect(anchorAddr).to.equal(owner.address);
    expect(ts).to.equal(blockTs);
  });

  it("reverts when anchoring the same hash twice", async function () {
    await contract.anchor(HASH_A);
    await expect(contract.anchor(HASH_A)).to.be.revertedWith(
      "MemoryIntegrity: already anchored"
    );
  });

  it("allows different addresses to anchor different hashes", async function () {
    await contract.connect(owner).anchor(HASH_A);
    await contract.connect(addr1).anchor(HASH_B);

    const [existsA] = await contract.verify(HASH_A);
    const [existsB] = await contract.verify(HASH_B);
    expect(existsA).to.be.true;
    expect(existsB).to.be.true;
  });

  // -------------------------------------------------------------------------
  // verify()
  // -------------------------------------------------------------------------

  it("returns exists=false for an unknown hash", async function () {
    const [exists] = await contract.verify(HASH_A);
    expect(exists).to.be.false;
  });

  it("returns correct anchor address and non-zero timestamp after anchoring", async function () {
    await contract.connect(addr1).anchor(HASH_A);
    const [exists, anchorAddr, timestamp] = await contract.verify(HASH_A);
    expect(exists).to.be.true;
    expect(anchorAddr).to.equal(addr1.address);
    expect(timestamp).to.be.gt(0n);
  });

  // -------------------------------------------------------------------------
  // anchorBatch()
  // -------------------------------------------------------------------------

  it("anchors a batch of hashes in one transaction", async function () {
    const hashes = [HASH_A, HASH_B];
    const tx = await contract.anchorBatch(hashes);
    const receipt = await tx.wait();

    // Two HashAnchored events should have been emitted
    const events = receipt.logs.filter(
      (l) => l.fragment?.name === "HashAnchored"
    );
    expect(events.length).to.equal(2);

    const [existsA] = await contract.verify(HASH_A);
    const [existsB] = await contract.verify(HASH_B);
    expect(existsA).to.be.true;
    expect(existsB).to.be.true;
  });

  it("skips already-anchored hashes in anchorBatch without reverting", async function () {
    await contract.anchor(HASH_A);
    // HASH_A is already anchored — anchorBatch should skip it silently
    await expect(contract.anchorBatch([HASH_A, HASH_B])).to.not.be.reverted;

    const [existsB] = await contract.verify(HASH_B);
    expect(existsB).to.be.true;
  });

  it("batch with zero hashes succeeds without events", async function () {
    const tx = await contract.anchorBatch([]);
    const receipt = await tx.wait();
    const events = receipt.logs.filter(
      (l) => l.fragment?.name === "HashAnchored"
    );
    expect(events.length).to.equal(0);
  });
});

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------
async function latestTimestamp() {
  const block = await ethers.provider.getBlock("latest");
  return BigInt(block.timestamp);
}
