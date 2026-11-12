# Sprint 2 On-Chain Commitment Verification Summary (Block `26400152`)

- **Pinned Block**: Ethereum Mainnet `26400152` (`0xc95550919ec2a58c3ec5f2136f85c4e18b498807db0b9f680da903f5dc783688`)
- **Cross-RPC Verification**: Replayed identically across `gateway.tenderly.co` and `rpc.mevblocker.io` (`exit 0`)
- **Independent Verifier Gate**: Verified by `pacta-codex` (`task-c990c1d127a5`, `DONE`)

## 1. f(x) Protocol v2 (`AladdinDAO/fx-protocol-contracts#28`)
- **`ProtocolTreasury` (`0x0e5CAA5c889Bdf053c9A76395f62267E653AFbb0` — `FX3`)**: Live `DEFAULT_ADMIN_ROLE` (`0x00`) is held by `OpsSafe` (`0x26B2ec4E02ebe2F54583af25b647b1D619E67BbF`, `5-of-9`, `0s` timelock) and `EmergencySafe` (`0xa028A787c25852e81239cE0A3D1729d89D2c3A95`, `4-of-7`, `0s` timelock), whereas `hasRole(0x00, 0x28c921adAC4c1072658eB01a28DA06b5F651eF62)` (3-day Governance Timelock) returns `false`.
- **Additional Capability Findings (`FX1` & `FX2`)**: Available at `$0` to f(x) Protocol maintainers via `pacta@dri.network`.

## 2. Alchemix (`alchemix-finance/v2-foundry#127`)
- **Alchemix v3 Admin Safe (`0xF56D660138815fC5d7a06cd0E1630225E788293D`)**: Verified `3-of-7` Gnosis Safe (`AX2`).
- **Token Admin Multisig (`0x8392F6669292fA56123F71949B52d883aE57e225`)**: Verified `4-of-7` Gnosis Safe with `600s` timelock.
- **Quarantined Security Finding (`AX3` — `disclosure_only`)**: Redacted from public files and provided **at no cost (`$0`)** via `pacta@dri.network`.

## 3. Gearbox V3 & Reserve Protocol
- All tested on-chain governance invariants hold at block `26400152`.
