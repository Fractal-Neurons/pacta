# Sprint 12 Protocol Commitment Summary — Block `26403676`

- **Ethereum Mainnet Block**: `26403676` (`0x192e35c`)
- **Canonical Block Hash**: `0xf4246ca23c4c38d520de16080a11b5186d04c8242b2c85edcb04c455d291c3ae`
- **Block Timestamp**: `1794544415`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-b54117e26713`, `receipt_seq: 425`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`) + leader dual-RPC archive replay (`pacta-gemini@dri.network`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (static raw-word decode, EIP-55, selector/slot & quarantine review; offline verifier does not execute live RPC calls or test suites)

## 1. Stader (`ETHx`) — `Manager` Safe Quorum & 7-Day `TimelockController` Record

| Contract / Check | Address | Selector / Slot | Raw / Decoded Value at Block `26403676` |
| :--- | :--- | :--- | :--- |
| **`Manager` Safe (`getThreshold` / `getOwners`)** | `0xAAfb31780e4b9c95Bc920e388f4925A874cd07AF` | `0xe75235b8` / `0xa0e67e2b` | `getThreshold() = 3`, `getOwners()` length `= 6` (`3-of-6` Gnosis Safe) vs. `"The Manager multisig is a 3-of-5 and is tasked with maintaining the protocol"` in `staderlabs.gitbook.io/ethereum` (`1` public parameter delta recorded) |
| **`ETHx` EIP-1967 Admin Slot & `ProxyAdmin.owner()`** | `0xA35b1B31Ce002FBF2058D22F30f95D405200A15b` | `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` / `0x8da5cb5b` | Admin slot `= 0x67B12264Ca3e0037Fc7E22F2457b42643a04C86e` (`ProxyAdmin`), whose `owner()` (`0x8da5cb5b`) `= 0x1112D5C55670Cb5144BF36114C20a122908068B9` (`TimelockController`) |
| **`TimelockController.getMinDelay()` & `PROPOSER_ROLE`** | `0x1112D5C55670Cb5144BF36114C20a122908068B9` | `0xf27a0c92` / `0x91d14854` | `getMinDelay() = 604800` seconds (`7` days); `hasRole(0xb09aa5aeb3702cfd50b6b62bc4532604938f21248a27a1d5ca736082b6819cc1, 0x45B977CeCB9Dfaa17dFcBa88826ef684b8489fF6) = true` (`1`) (`6-of-9` Community Safe); `TimelockController` also holds `DEFAULT_ADMIN_ROLE` (`0x0000000000000000000000000000000000000000000000000000000000000000`) on `ETHx` and `StaderConfig` (`0x4ABEF2263d5A5ED582FC9A9789a41D85b68d69DB`) |
| **`ETHx.hasRole(MINTER_ROLE, StakePoolsManager)` / `totalSupply()`** | `0xA35b1B31Ce002FBF2058D22F30f95D405200A15b` | `0x91d14854` / `0x18160ddd` | `hasRole(0x9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a6, 0xcf5EA1b38380f6aF39068375516Daf40Ed70D299) = true` (`1`); `totalSupply() = 58434161592626677177972` (`58,434.16` `ETHx`, `decimals()` `0x313ce567 = 18`) |

## 2. StakeWise V3 (`osETH`) — Sampled `Keeper` Oracle Quorum, `osETH` Fee & LTV Config Alignment

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26403676` |
| :--- | :--- | :--- | :--- |
| **`Keeper` Oracle Quorum (`totalOracles` / `rewardsMinOracles` / `validatorsMinOracles`)** | `0x6B5815467da09DaA7DC83Db21c9239d98Bb487b5` | `0xf2fbad47` / `0x7386749e` / `0x203efb5e` | `totalOracles() = 11`, `rewardsMinOracles() = 6`, `validatorsMinOracles() = 6` (`6-of-11` oracle signature quorum, matching `"Both enforce a signature threshold, currently 6 of 11 Oracles."` in `docs.stakewise.io/docs/oracles/intro`) |
| **`osETH.owner()` / `totalSupply()`** | `0xf1C9acDc66974dFB6dEcB12aA385b9cD01190E38` | `0x8da5cb5b` / `0x18160ddd` | `owner() = 0x0000000000000000000000000000000000000000`; `totalSupply() = 148452016761354135194146` (`148,452.02` `osETH`, `decimals()` `0x313ce567 = 18`) |
| **`OsTokenVaultController.feePercent()` / `totalAssets()`** | `0x2A261e60FB14586B474C208b1B7AC6D0f5000306` | `0x7fd6f15c` / `0x01e1d114` | `feePercent() = 500` (`5%` = `500 / 10000`, matching `"StakeWise DAO charges a 5% fee on the rewards accumulated by osETH"` in `docs.stakewise.io/docs/fees/intro`); `totalAssets() = 160753177637531777236544` (`160,753.18` `ETH`) |
| **`OsTokenConfig.getConfig(address(0))`** | `0x287d1e2A8dE183A8bf8f2b09Fa1340fBd766eb59` | `0xe48a5f7b` | `(1010000000000000000, 920000000000000000, 900000000000000000)` (`90%` mint LTV, `92%` liquidation threshold, matching `"the liquidation threshold is set to 92% LTV"` in `docs.stakewise.io/docs/ostoken/how-ostoken-works`) |

## 3. Swell (`swETH` / `rswETH`) — Sampled 7-Day `SwellTimelock`, `ProxyAdmin` & Reprice Bounds Alignment

| Contract / Check | Address | Selector / Slot | Raw / Decoded Value at Block `26403676` |
| :--- | :--- | :--- | :--- |
| **`swETH` & `rswETH` EIP-1967 Admin Slots & `ProxyAdmin.owner()`** | `0xf951E335afb289353dc249e82926178EaC7DEd78` | `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` / `0x8da5cb5b` | `swETH` admin `= 0x25EAf579cA2255fAA5463c635eec28697b5b8846` (`ProxyAdmin`) and `rswETH` (`0xFAe103DC9cf190eD75350761e95403b7b8aFa6c0`) admin `= 0xD750B84845f1cAdfEAc63f96Ec74635e949bFd14` (`ProxyAdmin`), both returning `owner() = 0xbA829003e6b5dD858fbed3945719939a6DC3073b` (`SwellTimelock`) |
| **`SwellTimelock.delay()` / `admin()`** | `0xbA829003e6b5dD858fbed3945719939a6DC3073b` | `0x6a42b8f8` / `0xf851a440` | `delay() = 604800` seconds (`7` days); `admin() = 0x20fDF47509C5eFC0e1101e3CE443691781C17F90` (`4-of-7` Gnosis Safe, `getThreshold()` `0xe75235b8 = 4`, `getOwners()` `0xa0e67e2b` length `= 7`) |
| **Sampled `AccessControlManager` `PLATFORM_ADMIN` Enumeration** | `0x625087d72c762254a72CB22cC2ECa40da6b95EAC` | `0xca15c873` / `0x9010d07c` | `getRoleMemberCount(0x4ff52032f36e32ac782042a01802e20394d4255c84a3c046490be98ab632691b) = 1` and `getRoleMember(..., 0) = 0xbA829003e6b5dD858fbed3945719939a6DC3073b` (`SwellTimelock`) on both `swETH` `AccessControlManager` and `rswETH` `AccessControlManager` (`0x796592b2092F7E150C48643dA19Dd2F28be3333F`) |
| **Sampled Reprice Bounds, Reward Split & Supply** | `0xf951E335afb289353dc249e82926178EaC7DEd78` | `0xbb6a0139` / `0x537ef9b5` / `0x18160ddd` | `minimumRepriceTime() = 3600`s (`1` hour) and `maximumRepriceDifferencePercentage() = 10000000000000000` (`1%`) on both `swETH` and `rswETH`; `rswETH` `swellTreasuryRewardPercentage()` (`0x0f010466`) `= 50000000000000000` (`5%`) and `nodeOperatorRewardPercentage()` (`0x16b716d9`) `= 50000000000000000` (`5%`); `swETH.totalSupply() = 9635131740029354716790` (`9,635.13` `swETH`, `18` dec); `rswETH.totalSupply() = 10363439393219450262441` (`10,363.44` `rswETH`, `18` dec) |

## 4. Superstate (`USTB` / `USCC`) — Sampled `USDC` Subscription Fee & Fund Supply Alignment

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26403676` |
| :--- | :--- | :--- | :--- |
| **`USTB.supportedStablecoins(USDC)`** | `0x43415eB6ff9DB7E26A15b704e7A3eDCe97d31C4e` | `0xbf7d9119` | `(0x774AE279c21B6a17a6E2BD5ab5398FF98F398807, 0)` for `USDC` (`0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`) — sweep destination and `0` subscription fee, matching `"At time of writing, fees are set to 0 and only USDC is supported."` in `docs.superstate.com/investors/smart-contracts.md` |
| **`USTB.totalSupply()` / `USCC.totalSupply()`** | `0x43415eB6ff9DB7E26A15b704e7A3eDCe97d31C4e` | `0x18160ddd` / `0x313ce567` | `USTB.totalSupply() = 39459575142444` (`39,459,575.14` `USTB`, `decimals() = 6`); `USCC` (`0x14d60E7FDC0D71d8611742720E4C50E7a974020c`) `totalSupply() = 4066680133168` (`4,066,680.13` `USCC`, `decimals() = 6`) |

> **Scope & Evidence Limit**: Sampled read-only getter/slot observations at the pinned block compared against cited documentation; does not certify protocol-wide authority completeness, downstream mutation semantics, or exploitability.
