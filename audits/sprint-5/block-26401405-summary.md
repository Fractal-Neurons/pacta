# Sprint 5 Protocol Commitment Summary — Block `26401405`

- **Ethereum Mainnet Block**: `26401405` (`0x192da7d`)
- **Canonical Block Hash**: `0x26e155e1569d436406a52ecee31c94d8d8ef2ca4c45d82211a84c8c802be1510`
- **Block Timestamp**: `1794517103`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-f6d364d6a6b6`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-28f82bfc474f`, `receipt_seq: 204`, static proof-bundle & decode review: `16/16` `eth_call` decodes, `2/2` Gnosis Safe owner arrays)

## 1. Fluid / Instadapp (`VaultFactory` `0x324c5Dc1fC42c7a4D43d92df1eBA58a54d13Bf2d`)
- **Team Multisig (`0x4F6F977aCDD1177DCD81aB83074855EcB9C2D49e`, `3-of-5` Gnosis Safe) `isVaultAuth` Status**:
  - `isVaultAuth(vault, 0x4F6F977aCDD1177DCD81aB83074855EcB9C2D49e)` returns `true` on Vault 76 (`0x7fe0b032cb5982af72498f96be3dd6566f7b7de8`), Vault 110 (`0xee327311d8640156e87ec33ea55fcbf2309e0ce6`), Vault 111 (`0x984636a30ed2b4a61fb7150ced644096349275d3`), and Vault 144 (`0x0e19b64f3a79feee12df1b6f239929c6ab6c7ed0`) per `IGP-98`/`IGP-126` migration-period configuration (`1` public parameter drift recorded).

## 2. MetaMorpho (`Re7 WETH` & `Re7 USDT`)
- **`Re7 USDT` (`0x95EeF579155cd2C5510F312c8fA39208c3be01a8`)**: `owner()` = `0xE86399fE6d7007FdEcb08A2ee1434Ee677a04433` (`2-of-4` Re7 Safe), `timelock()` = `259200`s (3 days), `guardian()` = `0x2F80ba89362f86a9acC71BFfE5EcF4997F52BDd4` (Aragon Guardian).
- **`Re7 WETH` (`0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0`)**: `owner()` = `0xE86399fE6d7007FdEcb08A2ee1434Ee677a04433` (`2-of-4` Re7 Safe), `timelock()` = `259200`s (3 days), `guardian()` = `0x0000000000000000000000000000000000000000`, `pendingGuardian()` = `(0x0000000000000000000000000000000000000000, 0)` (`1` public parameter drift recorded).
