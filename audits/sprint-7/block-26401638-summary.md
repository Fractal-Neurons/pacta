# Sprint 7 Protocol Commitment Summary — Block `26401638`

- **Ethereum Mainnet Block**: `26401638` (`0x192db66`)
- **Canonical Block Hash**: `0xe62ad2969617ad07c23bec298c3d5e197ea7c3084f7f66c90d2eb51d04c6273e`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-1dad57b4e323`, `receipt_seq: 253`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`, `15/15` scanner harness unit tests passed)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-1b5aa6d5a936`, `receipt_seq: 263`, static proof-bundle decode, EIP-55, selector & quarantine review; offline verifier does not execute live RPC calls or test suites)

## 1. Ethena (`ET2` & `ET3`) — On-Chain Timelock & Multisig Parameter Record

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26401638` | Documentation Reference |
| :--- | :--- | :--- | :--- | :--- |
| **Admin Timelock `getMinDelay()` (`ET2`)** | `0xE8Dc0Fab349EA169283C48Ccfd09d797E6DB7c94` | `0xf27a0c92` | `86400` seconds (`1` day) | `key-trust-assumptions.md` lists `"7 day time-locks"`; Risk Committee forum topic `810` (Jul 2026) notes `1` day |
| **Dev Multisig `getThreshold()` / `getOwners()` (`ET3`)** | `0x3B0AAf6e6fCd4a7cEEf8c92C32DFeA9E64dC1862` | `0xe75235b8` / `0xa0e67e2b` | `5-of-10` Gnosis Safe (`threshold = 5`, `owners = 10`) | `key-addresses.md` lists `5/11`; `key-trust-assumptions.md` lists `7` signatures |

## 2. ether.fi Core (`EC1`) — Sampled Timelock & Pool Parameter Record

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26401638` |
| :--- | :--- | :--- | :--- |
| **Upgrade Timelock `getMinDelay()`** | `0x9f26d4C958fD811A1F59B01B86Be7dFFc9d20761` | `0xf27a0c92` | `864000` seconds (`10` days) |
| **Operating Timelock `getMinDelay()`** | `0xcD425f44758a08BaAB3C4908f3e3dE5776e45d7a` | `0xf27a0c92` | `172800` seconds (`2` days) |
| **`LiquidityPool.getTotalPooledEther()`** | `0x308861A430be4cce5502d0A12724771Fc6DaF216` | `0x37cfdaca` | `2276605532665571773764692` (`2,276,605.53` ETH) |

## 3. Spark / Sky (`SP1`) — Sampled Governance Parameter Record

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26401638` |
| :--- | :--- | :--- | :--- |
| **`PoolAddressesProvider.owner()`** | `0x02C3eA4e34C0cBd694D2adFa2c690EECbC1793eE` | `0x8da5cb5b` | `0x3300f198988e4C9C63F75dF86De36421f06af8c4` (`SPARK_PROXY`) |
| **Sky `GSM_PAUSE_PROXY.delay()`** | `0xbE286431454714F511008713973d3B053A2d38f3` | `0x6a42b8f8` | `172800` seconds (`48` hours) |

> **Scope & Evidence Limit**: Sampled read-only getter/slot observations at the pinned block compared against cited documentation; does not certify protocol-wide authority completeness, downstream mutation semantics, or exploitability.
