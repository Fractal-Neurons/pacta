# Sprint 1 Protocol Commitment Summary — Block `26399876`

- **Ethereum Mainnet Block**: `26399876` (`0x192d484`)
- **Canonical Block Hash**: `0x8bf896b892683ff3267b88b367ab015a70cf5caf53542eb405f4f648f6bcde8a`
- **Block Timestamp**: `1794498695`
- **Scanner Seat**: `pacta-claude@dri.network` (dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`) + leader dual-RPC archive replay (`pacta-gemini@dri.network`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-6ffb627fefef` initial static proof-bundle decode; repaired archive reads verified via scanner/leader dual-RPC replay, while offline verifier performs static EIP-55, selector & quarantine review without live RPC calls)

## 1. Inverse Finance (`FiRM` & `GovernorMills` `0xBeCCB6bb0aa4ab551966A7E4B97cec74bb359Bf6`)
- **Guardian Wrapper & Policy Committee Safe**: `GovernorMills.guardian()` (`0x452a9320`) points to `0x941c2699eC7E55a50Bde030d8E1e70649839259D`, referencing Policy Committee Safe `0x4b6c63E6a94ef26E2dF60b89372db2d8e211F1B7` (`getThreshold() = 4`, `getOwners().length = 7` -> `4-of-7` Gnosis Safe vs. `5-of-9` multisig in working-groups documentation; `1` public parameter drift recorded).
- **Governance Timelock (`0x926dF14a23BE491164dCF93f4c468A50ef659D5B`)**: `GovernorMills.timelock()` (`0xd33219b4`) enforces `delay() = 172800` seconds (48 hours).

## 2. Origin Protocol (`OETH` / `OUSD`)
- **Guardian Multisig (`0x4FF1b9D9ba8558F5EAfCec096318eA0d8b541971`)**: `2-of-8` Gnosis Safe (`getThreshold() = 2`, `getOwners().length = 8`); sampled Vault admin and timelock parameters match superseded governance documentation at block `26399876`.

## 3. Yearn V3
- **Protocol Governance & Vault Factory Parameters**: Sampled on-chain governance parameters match public documentation at block `26399876`.

> **Scope & Evidence Limit**: Sampled read-only getter/slot observations at the pinned block compared against cited documentation; does not certify protocol-wide authority completeness, downstream mutation semantics, or exploitability.
