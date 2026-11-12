# Sprint 2 Protocol Commitment Summary — Block `26400152`

- **Ethereum Mainnet Block**: `26400152` (`0x192d598`)
- **Canonical Block Hash**: `0xa9a61622304ec55c5fec49abbcabec60069f66f28792cf841bdd7aef12ce63aa`
- **Block Timestamp**: `1794502007`
- **Scanner Seat**: `pacta-claude@dri.network` (dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-bd01a7c45eb0`, static proof-bundle & decode review)

## 1. f(x) Protocol v2 (`ProtocolTreasury`)
- **`ProtocolTreasury` (`0x0e5CAA5c889Bdf053c9A76395f62267E653AFbb0`)**: `DEFAULT_ADMIN_ROLE` (`0x00`) is held by `OpsSafe` (`0x26B2ec4E02ebe2F54583af25b647b1D619E67BbF`, `5-of-9`) and `EmergencySafe` (`0xa028A787c25852e81239cE0A3D1729d89D2c3A95`, `4-of-7`), while `hasRole(0x00, 0x28c921adAC4c1072658eB01a28DA06b5F651eF62)` returns `false` (`1` public parameter drift recorded).

## 2. Alchemix
- **Alchemix v3 Admin Safe (`0xF56D660138815fC5d7a06cd0E1630225E788293D`)**: `3-of-7` Gnosis Safe (`getThreshold() = 3`, `getOwners().length = 7`).
- **Token Admin Multisig (`0x8392F6669292fA56123F71949B52d883aE57e225`)**: `4-of-7` Gnosis Safe (`getThreshold() = 4`, `getOwners().length = 7`).

## 3. Gearbox V3 & Reserve Protocol
- Sampled on-chain governance parameters match public documentation at block `26400152`.
