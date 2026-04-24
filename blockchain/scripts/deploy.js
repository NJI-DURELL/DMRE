/**
 * deploy.js — Deploy MemoryIntegrity to the configured network.
 *
 * Usage:
 *   npx hardhat run scripts/deploy.js --network localhost   # Hardhat node
 *   npx hardhat run scripts/deploy.js --network ganache     # Ganache
 *
 * After deployment, copy the printed contract address into backend/.env:
 *   BLOCKCHAIN_CONTRACT_ADDRESS=0x...
 */

const { ethers } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();

  console.log("Deploying MemoryIntegrity with account:", deployer.address);
  console.log(
    "Account balance:",
    ethers.formatEther(await ethers.provider.getBalance(deployer.address)),
    "ETH"
  );

  const MemoryIntegrity = await ethers.getContractFactory("MemoryIntegrity");
  const contract = await MemoryIntegrity.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log("\nMemoryIntegrity deployed to:", address);
  console.log("\nAdd this to backend/.env:");
  console.log(`BLOCKCHAIN_CONTRACT_ADDRESS=${address}`);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
