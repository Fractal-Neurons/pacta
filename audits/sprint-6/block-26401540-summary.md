# Sprint 6 Protocol Commitment Summary — Block `26401540`

- **Ethereum Mainnet Block**: `26401540` (`0x192db04`)
- **Canonical Block Hash**: `0x49324aaf84b0ffd4e21026c5345272788bff377f0f86fcdb74280cdfc32a9641`
- **Block Timestamp**: `1794518723`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-cc033a56d755`, `receipt_seq: 215`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`) + leader dual-RPC archive replay (`pacta-gemini@dri.network`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-00c9e4aae632` initial static proof-bundle decode; repaired archive reads verified via scanner/leader dual-RPC replay, while offline verifier performs static EIP-55, selector & quarantine review without live RPC calls)

## 1. Maple Finance V2 / Syrup (`MP1`) — On-Chain Proxy-Admin & Governor Record

| Contract / Check | Address | Selector / Slot | Raw / Decoded Value at Block `26401540` |
| :--- | :--- | :--- | :--- |
| **`PoolPermissionManager` EIP-1967 Admin Slot** | `0xBe10aDcE8B6E3E02Db384E7FaDA5395DD113D8b3` | `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` | `0xd6d4Bcde6c816F17889f1Dd3000aF0261B03a196` (`4-of-7` Maple DAO Safe) |
| **`PoolPermissionManager` EIP-1967 Impl Slot** | `0xBe10aDcE8B6E3E02Db384E7FaDA5395DD113D8b3` | `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc` | `0xC3530358e54bC81EfCe4A2e12A898E996B091753` |
| **`Globals.governor()`** | `0x804a6F5F667170F545Bf14e5DDB48C70B788390C` | `0x0c340a24` (`governor()`) | `0x2eFFf88747EB5a3FF00d4d8d0f0800E306C0426b` (`GovernorTimelock`, `getMinDelay() = 259200`s / 3 days) |
| **`syrupUSDC.totalAssets()`** | `0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b` | `0x01e1d114` (`totalAssets()`) | `898551580571802` (`898,551,580.57` units at 6 decimals) |
| **Maple DAO Safe (`getThreshold` / `getOwners`)** | `0xd6d4Bcde6c816F17889f1Dd3000aF0261B03a196` | `0xe75235b8` / `0xa0e67e2b` | `4-of-7` Gnosis Safe (`1` public parameter drift recorded) |

## 2. Liquity V2 `BOLD` (`LQ1`) — Sampled Immutability Alignment

| Contract | Address | Check | Result at Block `26401540` |
| :--- | :--- | :--- | :--- |
| **`BOLD` Token** | `0x6440f144b7e50D6a8439336510312d2F54beB01D` | `owner()` (`0x8da5cb5b`) | `0x0000000000000000000000000000000000000000` (raw `0x00...00` zero address) |
| **`Governance`** | `0x807DEf5E7d057DF05C796F4bc75C3Fe82Bd6EeE1` | `owner()` (`0x8da5cb5b`) | `0x0000000000000000000000000000000000000000` (raw `0x00...00` zero address) |
| **`CollateralRegistry`** | `0xf949982B91C8c61e952B3bA942cbbfaef5386684` | EIP-1967 Impl Slot (`0x3608...2bbc`) | `0x0000000000000000000000000000000000000000000000000000000000000000` |

> **Scope & Evidence Limit**: Sampled read-only getter/slot observations at the pinned block compared against cited documentation; does not certify protocol-wide authority completeness, downstream mutation semantics, or exploitability.
