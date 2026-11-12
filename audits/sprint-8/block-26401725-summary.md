# Sprint 8 Protocol Commitment Summary — Block `26401725`

- **Ethereum Mainnet Block**: `26401725` (`0x192dbbd`)
- **Canonical Block Hash**: `0xec3820f0a9db32c01728e66f78dc1958e410269e1077fd1db53df4fbce2ad7a1`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-fe16019fcbd3`, `receipt_seq: 287`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-a56208db3da5`, `receipt_seq: 296`, static proof-bundle decode: `14/14` `eth_call`s, `6/6` Gnosis Safe arrays, `15/15` harness unit tests passed)

## 1. Usual Money (`UL1`) — `RegistryAccess` Admin Delay Parameter Record

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26401725` | Documentation Reference |
| :--- | :--- | :--- | :--- | :--- |
| **`RegistryAccess.defaultAdminDelay()`** | `0x0D374775E962c3608B8F0A4b8B10567DF739bb56` | `0xcc8463c8` | `1` second (`0x01`) | `tech.usual.money/overview/architecture/role-management` lists `"A delay of three days must be observed before granting that role to a new address"` |
| **`RegistryAccess.pendingDefaultAdminDelay()`** | `0x0D374775E962c3608B8F0A4b8B10567DF739bb56` | `0xa1eda53c` | `(0, 0)` (two zero words) | — |
| **`RegistryAccess.defaultAdmin()`** | `0x0D374775E962c3608B8F0A4b8B10567DF739bb56` | `0x84ef8ffc` | `0x6e9d65eC80D69b1f508560Bc7aeA5003db1f7FB7` (`8-of-15` Gnosis Safe) | — |

## 2. Renzo Protocol (`RZ1`) — `DepositQueue` Fee Parameter Record

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26401725` | Documentation Reference |
| :--- | :--- | :--- | :--- | :--- |
| **`DepositQueue.feeBasisPoints()`** | `0xf2F305D14DCD8aaef887E0428B3c9534795D0d60` | `0xb8606eef` | `1500` (`15%` in basis points) | `docs.renzoprotocol.com/docs/products/staking-suite/ezeth` lists `"Renzo charges a 10% fee on rewards generated via restaking"` |
| **Renzo Admin Multisig (`getThreshold` / `getOwners`)** | `0xD1e6626310fD54Eceb5b9a51dA2eC329D6D4B68A` | `0xe75235b8` / `0xa0e67e2b` | `3-of-5` Gnosis Safe | — |
| **`ezETH.totalSupply()`** | `0xbf5495Efe5DB9ce00f80364C8B423567e58d2110` | `0x18160ddd` | `39495317039388094803510` (`39,495.32` `ezETH`) | — |

## 3. Yearn V3 (`YV1` & `YV2`) — `RoleManager` Governance & Safe Parameter Record

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26401725` |
| :--- | :--- | :--- | :--- |
| **`RoleManager.governance()` (`YV1`)** | `0xb3bd6B2E61753C311EFbCF0111f75D29706D9a41` | `0x5aa6e675` | `0x88Ba032be87d5EF1fbE87336B7090767F367BF73` (`TimelockController`) |
| **`RoleManager.pendingGovernance()`** | `0xb3bd6B2E61753C311EFbCF0111f75D29706D9a41` | `0xf39c38a0` | `0x0000000000000000000000000000000000000000` |
| **`TimelockController.getMinDelay()`** | `0x88Ba032be87d5EF1fbE87336B7090767F367BF73` | `0xf27a0c92` | `604800` seconds (`7` days; stricter than `"not behind a time lock"` note in `yearn-devdocs`) |
| **`RoleManager.getDaddy()` (`YV2`)** | `0xb3bd6B2E61753C311EFbCF0111f75D29706D9a41` | `0xe33c71d0` | `0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52` (`6-of-9` `ychad.eth` Safe) |
| **`RoleManager.getBrain()` (`YV2`)** | `0xb3bd6B2E61753C311EFbCF0111f75D29706D9a41` | `0xd811ae21` | `0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7` (`3-of-6` Safe) |
| **`Accountant.defaultConfig()` (word 2)** | `0x5A74Cb32D36f2f517DB6f7b0A0591e09b22cDE69` | `0x9e09ed5f` | `[0, 1000, 0, 10000, 20000, 1, 0]` (word 2 `= 1000`) |
