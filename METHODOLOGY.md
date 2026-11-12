# Pacta Verification Methodology

## 1. Authority Graph Extraction

Production DeFi protocols frequently evolve through incremental upgrades (Diamond facet cuts, `TransparentUpgradeableProxy` admin transfers, `AccessControl` role grants, and emergency Safe rotations). Over time, live on-chain permissions often drift from both public documentation and the invariant structure enforced on newer core contracts.

Pacta constructs a complete, block-pinned authority graph across:
- **EIP-1967 & EIP-2535 (Diamond) Proxy Ownership**: Reading `ERC1967Upgrade` admin slots (`0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103`) and `LibDiamond` storage slots (`0xc8fcad8db84d3cc18b4c41d551ea0ee66dd599cde068d998e57d5e09332c131f`).
- **OpenZeppelin `AccessControl` / `AccessControlEnumerable`**: Resolving `hasRole(bytes32, address)` and `getRoleAdmin(bytes32)` across protocol treasuries, pool managers, and peg keepers.
- **Solmate / Veda `RolesAuthority`**: Reconstructing bitmask capability tables (`getUserRoles`, `getRoleCapabilities`, `isCapabilityPublic`) via archive event logs and state reads.
- **Gnosis Safe Multisig & Timelock Topologies**: Auditing `getOwners()`, `getThreshold()`, enabled Safe modules (`getModulesPaginated`), and `TimelockController` `minDelay` / proposer / executor / canceller bindings.

## 2. Reproducibility Standard

Every Execution Proof published or delivered by Pacta includes:
1. **Pinned Block Coordinate**: Mainnet block number and 32-byte block hash.
2. **Self-Contained `cast` Commands**: Copy-pasteable commands that any protocol engineer can run against their own archive node in under 30 seconds.
3. **Peer-Contract Contrast**: Comparison against the protocol's own canonical reference contracts (e.g., comparing peripheral or pool-treasury role assignments against the core `PoolManager` or `TimelockController` wiring).
4. **Safe Transaction Builder Remediation**: Ready-to-simulate JSON batches (`grantRole`, `revokeRole`, `transferOwnership`) ordered to prevent lockouts during role handoffs.
