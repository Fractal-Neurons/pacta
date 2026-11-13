# Pacta Verification Methodology & Scope Boundaries

## 1. Sampled Control-Plane Surfaces

Production DeFi protocols evolve across proxy upgrades, role migrations, and multisig signer rotations. Pacta evaluates **sampled, block-pinned control-plane surfaces** across deployed Mainnet contracts and compares observed read-only return values against cited public documentation:

- **Proxy Storage Slots (EIP-1967 / EIP-2535)**: Reading standard `ERC1967Upgrade` implementation (`0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`) and admin (`0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103`) slots, or Diamond storage slots where applicable.
- **Role-Based Access Interfaces**: Querying standard OpenZeppelin `AccessControl` (`hasRole`, `getRoleAdmin`), `AccessControlDefaultAdminRules` (`defaultAdminDelay`, `pendingDefaultAdminDelay`), or Solmate `RolesAuthority` (`authority`, `owner`, `getUserRoles`) getters supported by the target contract version.
- **Multisig & Timelock Parameters**: Reading Gnosis Safe `getThreshold()` and `getOwners()` quorums and `TimelockController` delay getters (`getMinDelay()`, `delay()`, `timelock()`).

## 2. Two-Seat Separation & Evidence Limits

1. **Scanner Archive Replay (`pacta-claude` / `pacta-gemini`)**:
   - Executes read-only `eth_call` and `eth_getStorageAt` queries pinned to an Ethereum Mainnet block height and canonical block hash across `gateway.tenderly.co/public/mainnet` and `rpc.mevblocker.io`.
2. **Offline Static Verification (`pacta-codex`)**:
   - Independently checks 4-byte ABI selector derivations, EIP-55 address checksums, standard storage slot constants, decode arithmetic, and quarantine hygiene in an offline environment (without issuing live network RPC calls).
3. **Observation vs. Policy Inference**:
   - Public records in [`docs/api/v1/index.json`](docs/api/v1/index.json) and `audits/sprint-*` report sampled historical getter/slot observations alongside cited documentation references. Sampled alignment does **not** certify protocol-wide immutability or exhaustive governance coverage, and parameter deltas do **not** imply unprivileged exploitability.
4. **Private Responsible Disclosure Quarantine (`$0 Gratis`)**:
   - Callable state-mutation exposures, unrevoked legacy EOA authorities, and target-specific Safe Transaction Builder remediation batches (`grantRole`, `revokeRole`, `scheduleBatch`, `transferOwnership`) are strictly excluded from public commits and routed free of charge exclusively to official protocol security contacts after target-specific interface and fork-simulation verification.
