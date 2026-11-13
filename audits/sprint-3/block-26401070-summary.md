# Sprint 3 Protocol Commitment Summary — Block `26401070`

- **Ethereum Mainnet Block**: `26401070` (`0x192d92e`)
- **Canonical Block Hash**: `0xcf55f6a42ae610c1f8766b5c2fb676d91f178469fa10ef777eccbb76f6506234`
- **Block Timestamp**: `1794513083`
- **Scanner Seat**: `pacta-claude@dri.network` (dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`) + leader dual-RPC archive replay (`pacta-gemini@dri.network`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-cc0bbf599968` initial static proof-bundle decode; repaired archive reads verified via scanner/leader dual-RPC replay, while offline verifier performs static EIP-55, selector & quarantine review without live RPC calls)

## 1. ether.fi Liquid / Veda BoringVault
- **`AccountantWithRateProviders` (`0x0d05D94a5F1E76C18fbeB7A13d17C8a314088198`) & `RolesAuthority` (`0x485Bde66Bb668a51f2372E34e45B1c6226798122`)**:
  - `AccountantWithRateProviders.authority()` (`0xbf7e214f`) resolves to `RolesAuthority` (`0x485Bde66Bb668a51f2372E34e45B1c6226798122`).
  - `RolesAuthority.owner()` (`0x8da5cb5b`) resolves to `TimelockController` (`0xD829F278016b90FEc735F9A12Bf8b75E06102C89`, `getMinDelay() = 86400` seconds / 1 day).

## 2. Morpho Blue Core (`0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb`)
- **`owner()` (`0x8da5cb5b`)**: `0xcBa28b38103307Ec8dA98377ffF9816C164f9AFa`; sampled fee, owner, and LLTV parameters match public documentation at block `26401070`.

> **Scope & Evidence Limit**: Sampled read-only getter/slot observations at the pinned block compared against cited documentation; does not certify protocol-wide authority completeness, downstream mutation semantics, or exploitability.
