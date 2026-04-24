require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks: {
    // Default local Hardhat node (hardhat node command)
    localhost: {
      url: "http://127.0.0.1:8545",
    },
    // Ganache desktop / CLI
    ganache: {
      url: "http://127.0.0.1:7545",
      chainId: 1337,
    },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};
