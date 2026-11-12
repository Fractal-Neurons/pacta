# Sprint 1 On-Chain Commitment Verification Summary (Block `26399876`)

- **Pinned Block**: Ethereum Mainnet `26399876` (`0x1b4506a29a1487792b3722fb26554e9b6fa9b6248e6eb9ca6b14cf6cb154f6c4`)
- **Cross-RPC Verification**: Replayed identically across `gateway.tenderly.co` and `rpc.mevblocker.io` (`exit 0`)
- **Independent Verifier Gate**: Verified by `pacta-codex` (`task-6ffb627fefef`, `DONE`)

## 1. Inverse Finance (`FiRM` & `GovernorMills`)
- **Policy Committee Safe (`0x4b6c4659db229A0B6C188F4622a5D394417111B7`)**: Live `4-of-7` Gnosis Safe (`getThreshold() = 4`, `getOwners().length = 7`) vs. documented `5-of-9` multisig (`https://docs.inverse.finance/inverse-finance/inverse-finance/product-guide/governance/working-groups`).
- **`jrDOLA` Operator Safe (`0x9D5Df30F475CEA915b1ed4C0CCa59255C8F7b61B`)**: Verified `3-of-6` Gnosis Safe.
- **Quarantined Security Finding (`I3` — `disclosure_only`)**: Redacted from public repository and provided **at no cost (`$0`)** via `pacta@dri.network` (`InverseFinance/FiRM#150`).

## 2. Origin Protocol (`OETH` / `OUSD`)
- **Guardian Multisig (`0x4FF1b9D9ba8558F5EAfCec096318eA0d8b541971`)**: Verified `2-of-8` Gnosis Safe; all `O1`–`O7` timelock and Vault admin invariants hold at block `26399876`.

## 3. Yearn V3
- **Protocol Governance & Vault Factory Invariants**: All 11 tested on-chain invariants hold at block `26399876`.
