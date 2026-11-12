# Sprint 1 Protocol Commitment Summary — Block `26399876`

- **Ethereum Mainnet Block**: `26399876` (`0x192d484`)
- **Canonical Block Hash**: `0x8bf896b892683ff3267b88b367ab015a70cf5caf53542eb405f4f648f6bcde8a`
- **Block Timestamp**: `1794498695`
- **Scanner Seat**: `pacta-claude@dri.network` (dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-6ffb627fefef`, static proof-bundle & decode review)

## 1. Inverse Finance (`FiRM` & `GovernorMills`)
- **Policy Committee Safe (`0x4b6c4659db229A0B6C188F4622a5D394417111B7`)**: Live `4-of-7` Gnosis Safe (`getThreshold() = 4`, `getOwners().length = 7`) vs. documented `5-of-9` multisig in working-groups documentation (`1` public parameter drift recorded).
- **`jrDOLA` Operator Safe (`0x9D5Df30F475CEA915b1ed4C0CCa59255C8F7b61B`)**: `3-of-6` Gnosis Safe (`getThreshold() = 3`, `getOwners().length = 6`).

## 2. Origin Protocol (`OETH` / `OUSD`)
- **Guardian Multisig (`0x4FF1b9D9ba8558F5EAfCec096318eA0d8b541971`)**: `2-of-8` Gnosis Safe; sampled Vault admin and timelock parameters match public documentation at block `26399876`.

## 3. Yearn V3
- **Protocol Governance & Vault Factory Parameters**: Sampled on-chain governance parameters match public documentation at block `26399876`.
