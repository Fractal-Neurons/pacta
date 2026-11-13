# Sprint 10 Protocol Commitment Summary — Block `26403121`

- **Ethereum Mainnet Block**: `26403121` (`0x192e131`)
- **Canonical Block Hash**: `0x71acee2313a2c8eacd7d2c87667dc505310b3e9224d84eaebb71d5a890ef9d1c`
- **Block Timestamp**: `1794537755`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-f0ee10b58fd3`, `receipt_seq: 394`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`) + leader dual-RPC archive replay (`pacta-gemini@dri.network`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (static raw-word decode, EIP-55, selector/slot & quarantine review; offline verifier does not execute live RPC calls or test suites)

## 1. Ondo Finance (`OUSG` & `Flux Finance`) — `RateLimiter` Subscription Limit & `Flux` Timelock Record

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26403121` |
| :--- | :--- | :--- | :--- |
| **`RateLimiter.globalSubscriptionLimits(OUSG)`** | `0x98Db502215Da1ad9F626D4a0090A8A2f4971003c` | `0x435e3a08` | `(100000000000000000000000, 1794481163, 100000000000000000000000000, 86400)` — word `[2]` `= $100,000,000` (`100,000,000 * 10^18`) per `86,400`s window vs. `"Instant minting has a $50M Global Limit"` in `docs.ondo.finance/qualified-access-products/ousg/instant-limits.md` (`1` public parameter delta recorded; `OUSG` `= 0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92`) |
| **`RateLimiter.globalRedemptionLimits(OUSG)`** | `0x98Db502215Da1ad9F626D4a0090A8A2f4971003c` | `0x259ae938` | `(1427494610611018131366454, 1794328739, 50000000000000000000000000, 86400)` — word `[2]` `= $50,000,000` (`50,000,000 * 10^18`) per `86,400`s window |
| **`OUSG.totalSupply()`** | `0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92` | `0x18160ddd` | `1110569329550681747519603` (`1,110,569.33` `OUSG`, `decimals() = 18`) |
| **`Flux Comptroller.admin()`** | `0x95Af143a021DF745bc78e845b54591C53a8B3A51` | `0xf851a440` | `0x2c5898da4DF1d45EAb2B7B192a361C3b9EB18d9c` (`FluxTimelock`) |
| **`FluxTimelock.delay()` / `admin()`** | `0x2c5898da4DF1d45EAb2B7B192a361C3b9EB18d9c` | `0x6a42b8f8` / `0xf851a440` | `86400` seconds (`1` day); `admin()` `= 0x336505EC1BcC1A020EeDe459f57581725D23465A` (`FluxGovernor`) |

## 2. Mantle Liquid Staking (`mETH` / `cmETH`) — Sampled 3-Day `UpgradeTimelock` Protective Record

| Contract / Check | Address | Selector / Slot | Raw / Decoded Value at Block `26403121` |
| :--- | :--- | :--- | :--- |
| **`mETH` EIP-1967 Admin Slot** | `0xd5F7838F5C461fefF7FE49ea5ebaF7728bB0ADfa` | `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` | `0xc26016f1166bE7b6c5611AAB104122E0f6c2aCE2` (`UpgradeTimelock`) |
| **`Staking` EIP-1967 Admin Slot** | `0xe3cBd06D7dadB3F4e6557bAb7EdD924CD1489E8f` | `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` | `0xc26016f1166bE7b6c5611AAB104122E0f6c2aCE2` (`UpgradeTimelock`) |
| **`UpgradeTimelock.getMinDelay()`** | `0xc26016f1166bE7b6c5611AAB104122E0f6c2aCE2` | `0xf27a0c92` | `259200` seconds (`3` days; stricter than `"default delay of 0"` note in `docs.mantle.xyz/meth/concepts/risk-management/upgradability-and-timelock.md`) |
| **`UpgradeTimelock.hasRole(PROPOSER_ROLE, SecurityCouncil)`** | `0xc26016f1166bE7b6c5611AAB104122E0f6c2aCE2` | `0x91d14854` | `true` (`1`) for `0x4e59e778a0fb77fBb305637435C62FaeD9aED40f` (`6-of-14` Security Council Safe; `PROPOSER_ROLE` `= 0xb09aa5aeb3702cfd50b6b62bc4532604938f21248a27a1d5ca736082b6819cc1`) |
| **`mETH.totalSupply()`** | `0xd5F7838F5C461fefF7FE49ea5ebaF7728bB0ADfa` | `0x18160ddd` | `217256941697751297773983` (`217,256.94` `mETH`) |

## 3. Symbiotic Core — Sampled Non-Upgradeable Core Registries & Multisig Alignment

| Contract / Check | Address | Selector / Slot | Raw / Decoded Value at Block `26403121` |
| :--- | :--- | :--- | :--- |
| **`VaultFactory` EIP-1967 Impl & Admin Slots** | `0xAEb6bdd95c502390db8f52c8909F703E9Af6a346` | `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc` / `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` | `0x0000000000000000000000000000000000000000000000000000000000000000` (also zero on `OperatorRegistry` `0xAd817a6Bc954F678451A71363f04150FDD81Af9F` and `NetworkRegistry` `0xC773b1011461e7314CF05f97d95aa8e92C1Fd8aA`) |
| **`VaultFactory.owner()`** | `0xAEb6bdd95c502390db8f52c8909F703E9Af6a346` | `0x8da5cb5b` | `0x5721ce64Ee0D772Ce613b62D411350091C544cD0` (`2-of-3` Gnosis Safe, `getThreshold() = 2`, `getOwners().length = 3`) |
| **`AdapterRegistry.owner()`** | `0x788823C9579A049D986eB76718bC758C0998594a` | `0x8da5cb5b` | `0xf6BB2e64Bd201A862f2Fe5461fc7Ef01e2040b6A` (`3-of-5` Gnosis Safe, `getThreshold() = 3`, `getOwners().length = 5`) |

## 4. Lido (`DualGovernance` & `EmergencyProtectedTimelock`) — Sampled Timelock & Committee Alignment

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26403121` |
| :--- | :--- | :--- | :--- |
| **`EmergencyProtectedTimelock.getAfterSubmitDelay()`** | `0xCE0425301C85c5Ea2A0873A2dEe44d78E02D2316` | `0x709105d7` | `259200` seconds (`3` days) |
| **`EmergencyProtectedTimelock.getAfterScheduleDelay()`** | `0xCE0425301C85c5Ea2A0873A2dEe44d78E02D2316` | `0x5d5f5564` | `86400` seconds (`1` day) |
| **`EmergencyProtectedTimelock.getGovernance()`** | `0xCE0425301C85c5Ea2A0873A2dEe44d78E02D2316` | `0x289b3c0d` | `0xC1db28B3301331277e307FDCfF8DE28242A4486E` (`DualGovernance`) |
| **`EmergencyProtectedTimelock.getEmergencyProtectionDetails()`** | `0xCE0425301C85c5Ea2A0873A2dEe44d78E02D2316` | `0xc464d580` | `(2592000, 0, 1813449600)` (`30`-day emergency mode duration; protection window extended to timestamp `1813449600` per Lido forum `10032`) |
| **Emergency & Reseal Committee Safes** | `0xCE0425301C85c5Ea2A0873A2dEe44d78E02D2316` | `0x24dbfa0e` / `0x73ddf4c6` | Emergency Activation `0x8B7854488Fde088d686Ea672B6ba1A5242515f45` (`4-of-7` Safe); Emergency Execution `0xC7792b3F2B399bB0EdF53fECDceCeB97FBEB18AF` (`5-of-7` Safe); `DualGovernance.getResealCommittee()` (`0xf65ba167`) `= 0xFFe21561251c49AdccFad065C94Fb4931dF49081` (`5-of-6` Safe); `CircuitBreaker` committee `0x8772E3a2D86B9347A2688f9bc1808A6d8917760C` (`3-of-6` Safe) |
| **`stETH.totalSupply()`** | `0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84` | `0x18160ddd` | `9759371526071616970208160` (`9,759,371.53` `stETH`) |

> **Scope & Evidence Limit**: Sampled read-only getter/slot observations at the pinned block compared against cited documentation; does not certify protocol-wide authority completeness, downstream mutation semantics, or exploitability.
