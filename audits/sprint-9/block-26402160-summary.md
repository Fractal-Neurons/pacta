# Sprint 9 Protocol Commitment Summary — Block `26402160`

- **Ethereum Mainnet Block**: `26402160` (`0x192dd70`)
- **Canonical Block Hash**: `0xd04a5e8aa3500c5b60d90c25a810ef28eb9d1bfffadf28f1da58a31ed90582dc`
- **Block Timestamp**: `1794526199`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-a206bca418d0`, `receipt_seq: 381`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`) + leader dual-RPC archive replay (`pacta-gemini@dri.network`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (static raw-word decode, EIP-55, selector/slot & quarantine review; offline verifier does not execute live RPC calls or test suites)

## 1. Compound V3 (`Comet`) — Sampled Timelock & Pause-Guardian Alignment

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26402160` |
| :--- | :--- | :--- | :--- |
| **`cUSDCv3.governor()`** | `0xc3d688B66703497DAA19211EEdff47f25384cdc3` | `0x0c340a24` | `0x6d903f6003cca6255D85CcA4D3B5E5146dC33925` (`CompoundTimelock`) |
| **`cWETHv3.governor()`** | `0xA17581A9E3356d9A858b789D68B4d866e593aE94` | `0x0c340a24` | `0x6d903f6003cca6255D85CcA4D3B5E5146dC33925` (`CompoundTimelock`) |
| **`CompoundTimelock.delay()`** | `0x6d903f6003cca6255D85CcA4D3B5E5146dC33925` | `0x6a42b8f8` | `172800` seconds (`48` hours) |
| **`CompoundTimelock.admin()`** | `0x6d903f6003cca6255D85CcA4D3B5E5146dC33925` | `0xf851a440` | `0x309a862bbC1A00e45506cB8A802D1ff10004c8C0` (`CompoundGovernor`) |
| **`cUSDCv3.pauseGuardian()`** | `0xc3d688B66703497DAA19211EEdff47f25384cdc3` | `0x24a3d622` | `0xbbf3f1421D886E9b2c5D716B5192aC998af2012c` (`5-of-9` Community Pause Safe) |

## 2. Aave V3 & GHO — Sampled `ACLManager`, Executor Level 1 & Guardian Alignment

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26402160` |
| :--- | :--- | :--- | :--- |
| **`ACLManager.hasRole(0x00, ExecutorLvl1)`** | `0xc2aaCf6553D20d1e9d78E365AAba8032af9c85b0` | `0x91d14854` | `true` (`1`) for `0x5300A1a15135EA4dc7aD5a167152C01EFc9b192A` |
| **`PayloadsController.getExecutorSettingsByAccessControl(1)`** | `0xdAbad81aF85554E9ae636395611C58F7eC1aAEc5` | `0xf80281fb` | `(0x5300A1a15135EA4dc7aD5a167152C01EFc9b192A, 86400)` (`1` day delay) |
| **`ACLManager.hasRole(EMERGENCY_ADMIN, Guardian)`** | `0xc2aaCf6553D20d1e9d78E365AAba8032af9c85b0` | `0x91d14854` | `true` (`1`) for `0x2CFe3ec4d5a6811f4B8067F0DE7e47DfA938Aa30` (`4-of-7` Safe) |
| **`GHO.totalSupply()`** | `0x40D16FC0246aD3160Ccc09B8D0D3A2cD28aE6C2f` | `0x18160ddd` | `699000000000000000000000000` (`699,000,000.00` `GHO`) |

## 3. Kelp DAO (`rsETH`) — Sampled `ProxyAdmin`, 10-Day Timelock & Admin Safe Alignment

| Contract / Check | Address | Selector / Slot | Raw / Decoded Value at Block `26402160` |
| :--- | :--- | :--- | :--- |
| **`rsETH` EIP-1967 Admin Slot** | `0xA1290d69c65A6Fe4DF752f95823fae25cB99e5A7` | `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` | `0xb61e0E39b6d4030C36A176f576aaBE44BF59Dc78` (`ProxyAdmin`) |
| **`ProxyAdmin.owner()`** | `0xb61e0E39b6d4030C36A176f576aaBE44BF59Dc78` | `0x8da5cb5b` | `0x49bD9989E31aD35B0A62c20BE86335196A3135B1` (`TimelockController`) |
| **`TimelockController.getMinDelay()`** | `0x49bD9989E31aD35B0A62c20BE86335196A3135B1` | `0xf27a0c92` | `864000` seconds (`10` days) |
| **`LRTConfig.hasRole(0x00, AdminSafe)`** | `0x947Cb49334e6571ccBFEF1f1f1178d8469D65ec7` | `0x91d14854` | `true` (`1`) for `0xb3696a817D01C8623E66D156B6798291fa10a46d` (`6-of-11` Safe) |
| **`rsETH.totalSupply()`** | `0xA1290d69c65A6Fe4DF752f95823fae25cB99e5A7` | `0x18160ddd` | `338071327413287057158482` (`338,071.33` `rsETH`) |

## 4. EigenLayer Core — Sampled Core `ProxyAdmin`, 10-Day Timelock & `PauserRegistry` Alignment

| Contract / Check | Address | Selector / Slot | Raw / Decoded Value at Block `26402160` |
| :--- | :--- | :--- | :--- |
| **`DelegationManager` EIP-1967 Admin Slot** | `0x39053D51B77DC0d36036Fc1fCc8Cb819df8Ef37A` | `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` | `0x8b9566AdA63B64d1E1dcF1418b43fd1433b72444` (`Core ProxyAdmin`) |
| **`Core ProxyAdmin.owner()`** | `0x8b9566AdA63B64d1E1dcF1418b43fd1433b72444` | `0x8da5cb5b` | `0x369e6F597e22EaB55fFb173C6d9cD234BD699111` (`1-of-2` `ExecutorMultisig` owned by `10`d `TimelockController` `0xC06Fd4F821eaC1fF1ae8067b36342899b57BAa2d` and `9-of-13` `CommunityMultisig` `0xFEA47018D632A77bA579846c840d5706705Dc598`) |
| **`Core TimelockController.getMinDelay()`** | `0xC06Fd4F821eaC1fF1ae8067b36342899b57BAa2d` | `0xf27a0c92` | `864000` seconds (`10` days) |
| **`DelegationManager.pauserRegistry()`** | `0x39053D51B77DC0d36036Fc1fCc8Cb819df8Ef37A` | `0x886f1195` | `0xB8765ed72235d279c3Fb53936E4606db0Ef12806` (matches `Layr-Labs/eigenlayer-contracts` `main/README.md`; `unpauser()` `0xeab66d7a` = `0x369e6F597e22EaB55fFb173C6d9cD234BD699111`) |

> **Scope & Evidence Limit**: Sampled read-only getter/slot observations at the pinned block compared against cited documentation; does not certify protocol-wide authority completeness, downstream mutation semantics, or exploitability.
