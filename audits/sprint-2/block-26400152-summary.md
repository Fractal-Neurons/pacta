# Sprint 2 Protocol Commitment Summary — Block `26400152`

- **Ethereum Mainnet Block**: `26400152` (`0x192d598`)
- **Canonical Block Hash**: `0xa9a61622304ec55c5fec49abbcabec60069f66f28792cf841bdd7aef12ce63aa`
- **Block Timestamp**: `1794502007`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-bd01a7c45eb0`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`) + leader dual-RPC archive replay (`pacta-gemini@dri.network`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-b6a331367a3a` initial static proof-bundle decode; repaired archive reads verified via scanner/leader dual-RPC replay, while offline verifier performs static EIP-55, selector & quarantine review without live RPC calls)

## 1. f(x) Protocol v2 (`ProtocolTreasury` Proxies)
- **Live v2 `ProtocolTreasury` Proxies (`wstETH` `0x32356FE312Eba9B7D6A157ad28D1ca91b571CdA6`, `WBTC` `0xb178197E88D58Da21bE22A408E850d1e6Dc09A38`, `sfrxETH` `0x6D9e81c5b7C4b37d0Fe9E8CDA776e057f4040868`, `weETH` `0x87d5e4cAaF4358A4337C10859c7107c7AEF4f8Ce`)**: `DEFAULT_ADMIN_ROLE` (`0x00`) is held directly by `OpsSafe` (`0x26B2ec4E02ebe2F54583af25b647b1D619e67BbF`, `6-of-9`) and `EmergencySafe` (`0x28c921adAC4c1072658eB01a28DA06b5F651eF62`, `3-of-4`), whereas `Timelock` (`0x68863fb8855b04509a835082478D6E3D0bE4E61a`, `getMinDelay() = 259200`s) holds `false` (`1` public parameter drift recorded).

## 2. Alchemix
- **Alchemix v3 Admin Safe (`0xF56D660138815fC5d7a06cd0E1630225E788293D`)**: `3-of-7` Gnosis Safe (`getThreshold() = 3`, `getOwners().length = 7`).
- **Token Admin Multisig (`0x8392F6669292fA56123F71949B52d883aE57e225`)**: `4-of-7` Gnosis Safe (`getThreshold() = 4`, `getOwners().length = 7`).

## 3. Gearbox V3 & Reserve Protocol
- Sampled on-chain governance parameters match public documentation at block `26400152`.

> **Scope & Evidence Limit**: Sampled read-only getter/slot observations at the pinned block compared against cited documentation; does not certify protocol-wide authority completeness, downstream mutation semantics, or exploitability.
