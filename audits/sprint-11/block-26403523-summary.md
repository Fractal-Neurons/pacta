# Sprint 11 Protocol Commitment Summary — Block `26403523`

- **Ethereum Mainnet Block**: `26403523` (`0x192e2c3`)
- **Canonical Block Hash**: `0xfc7beaa2338e8054577c0b101b641bc42afca2af39cb85d3fc13cbee32d4681a`
- **Block Timestamp**: `1794542579`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-0cad934c5db0`, `receipt_seq: 409`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`) + leader dual-RPC archive replay (`pacta-gemini@dri.network`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (static raw-word decode, EIP-55, selector/slot & quarantine review; offline verifier does not execute live RPC calls or test suites)

## 1. Curve (`crvUSD` & `LendingOwnerProxy`) — `ControllerFactory` Admin & `EmergencyDAO` Ceiling Record

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26403523` |
| :--- | :--- | :--- | :--- |
| **`ControllerFactory.admin()`** | `0xC9332fdCB1C491Dcc683bAe86Fe3cb70360738BC` | `0xf851a440` | `0xeDA020b067872717901916a3B8C724C21f6080d1` (`LendingOwnerProxy`, updated in tx `0x52b52f633eaef7cb05bdd29b3386b69e3c5f3368be20f3d113e6c21f837ff163` at block `26300155`) vs. `"Only its admin, the CurveOwnershipAgent, can call to add a market."` in `curvefi/docs` `docs/developer/crvusd/factory.md` (`1` public parameter delta recorded) |
| **`LendingOwnerProxy.dao()` / `emergency_dao()`** | `0xeDA020b067872717901916a3B8C724C21f6080d1` | `0x4162169f` / `0x2b921d30` | `dao()` `= 0x40907540d8a6C65c637785e8f8B742ae6b0b9968` (`CurveOwnershipAgent`); `emergency_dao()` `= 0x467947EE34aF926cF1DCac093870f613C96B1E0c` (`5-of-9` `EmergencyDAO` Gnosis Safe, `getThreshold() = 5`, `getOwners().length = 9`) |
| **Aragon Ownership Voting (`voteTime` / Quorum / Support)** | `0xE478de485ad2fe566d49342Cbd03E49ed7DB3356` | `0xbcf93dd6` / `0xdc474b1a` / `0xfad167ab` | `voteTime() = 604800`s (`7` days), `minAcceptQuorumPct() = 300000000000000000` (`30%`), `supportRequiredPct() = 510000000000000000` (`51%`); Parameter Voting (`0xBCfF8B0b9419b9A88c44546519b1e909cF330399`) `voteTime() = 604800`s (`7` days), `15%` quorum, `60%` support |
| **`crvUSD.minter()` / `totalSupply()`** | `0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E` | `0x07546172` / `0x18160ddd` | `minter() = 0xC9332fdCB1C491Dcc683bAe86Fe3cb70360738BC` (`ControllerFactory`); `totalSupply() = 2134809204981834354272443571` (`2,134,809,204.98` `crvUSD`, `decimals() = 18`) |
| **`ControllerFactory.debt_ceiling(YieldBasis)`** | `0xC9332fdCB1C491Dcc683bAe86Fe3cb70360738BC` | `0x602b62d4` | `1000000000000000000000000000` (`1,000,000,000` `crvUSD` credit line for `0x370a449FeBb9411c95bf897021377fe0B7D100c0`, per Curve Ownership Vote `1279`) |

## 2. Gearbox V3 / V3.1 — `LegacyTimelock` Delay & `InstanceManager` Safe Quorum Record

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26403523` |
| :--- | :--- | :--- | :--- |
| **`LegacyTimelock.delay()` / `admin()`** | `0xa133C9A92Fb8dDB962Af1cbae58b2723A0bdf23b` | `0x6a42b8f8` / `0xf851a440` | `delay() = 129600` seconds (`36` hours, GIP-104) vs. `"Transactions related to technical changes and protocol improvements are behind a 2-day timelock"` (`172800`s) in `docs.gearbox.finance` (`1` public parameter delta recorded); `admin() = 0x29B97F37B3E0C704bCFD785F5b7bBa2A0B7df2c7` (`LegacyGovernor`); `LegacyACL` (`0x523dA3a8961E4dD4f6206DBf7E6c749f51796bb3`) `owner()` (`0x8da5cb5b`) `= LegacyTimelock`; `ControllerTimelockV3` (`0xD8CeB2580F22E13D17031740af2e91e9e7A13347`) `paused()` (`0x5c975abb`) `= true` (`1`) |
| **`InstanceManager.owner()` & Safe Quorum** | `0x77777777144339Bdc3aCceE992D8d4D31734CB2e` | `0x8da5cb5b` | `0x1E9ec044853611F4bCD4BBcFE7657508BD1c53D3` (`4-of-21` Gnosis Safe, `getThreshold()` `0xe75235b8 = 4`, `getOwners()` `0xa0e67e2b` length `= 21` vs. `"4-of-12"` in `docs.gearbox.finance`); `AddressProviderV3` (`0xF7f0a609BfAb9a0A98786951ef10e5FE26cC1E38`) `owner() = InstanceManager` |
| **Sampled Guard Multisigs (`getThreshold` / `getOwners`)** | `0xA7D5DDc1b8557914F158076b228AA91eF613f1D5` | `0xe75235b8` / `0xa0e67e2b` | Tech Guard `0xA7D5DDc1b8557914F158076b228AA91eF613f1D5` (`6-of-12`), Veto Safe `0xbb803559B4D58b75E12dd74641AB955e8B0Df40E` (`4-of-12`), Treasury Guard `0x7b065Fcb0760dF0CEA8CFd144e08554F3CeA73D1` (`5-of-10`), Fee Guard `0x3E965117A51186e41c2BB58b729A1e518A715e5F` (`5-of-10`) |

## 3. Lombard (`LBTC`) — Sampled Core `ProxyAdmin` & 24-Hour `TimelockController` Alignment

| Contract / Check | Address | Selector / Slot | Raw / Decoded Value at Block `26403523` |
| :--- | :--- | :--- | :--- |
| **`LBTC` EIP-1967 Admin Slot** | `0x8236a87084f8B84306f72007F36F2618A5634494` | `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` | `0xbae061C73876952aa2C5e483B74DfA785425f879` (`LBTC ProxyAdmin`) |
| **Sampled Core `ProxyAdmin.owner()` Wiring** | `0xbae061C73876952aa2C5e483B74DfA785425f879` | `0x8da5cb5b` | `0x055E84e7FE8955E2781010B866f10Ef6E1E77e59` (`TimelockController`; also `owner()` on `AssetRouter ProxyAdmin` `0xBf4202c8a0d852D432266dfE112ED624a1a36754` and `Consortium ProxyAdmin` `0x1629AE77cC70DaAc95Ec479caAEA23ECE77c67c5`) |
| **`TimelockController.getMinDelay()`** | `0x055E84e7FE8955E2781010B866f10Ef6E1E77e59` | `0xf27a0c92` | `86400` seconds (`24` hours, matching `"Each Proxy Upgrade Timelock enforces a 24-hour minimum delay on contract upgrades."` in `docs.lombard.finance/learn/transparency/smart-contracts`) |
| **`TimelockController.hasRole(EXECUTOR_ROLE, OwnerSafe)`** | `0x055E84e7FE8955E2781010B866f10Ef6E1E77e59` | `0x91d14854` | `true` (`1`) for `0x251a604E8E8f6906d60f8dedC5aAeb8CD38F4892` (`3-of-5` Gnosis Safe, Guard `0x87bde523e05Fee2C557d6F592F7EB686C69189Ab`; `EXECUTOR_ROLE` `= 0xd8aa0f3194971a2a116679f7c2090f6939c8d4e01a2a8d7e41d55e5351469e63`) |
| **`LBTC.totalSupply()`** | `0x8236a87084f8B84306f72007F36F2618A5634494` | `0x18160ddd` | `620353819856` (`6,203.54` `LBTC`, `decimals() = 8`) |

## 4. Resolv (`USR` / `RLP`) — Sampled `USR` `AccessControlDefaultAdminRules` Delay & Request Counter Alignment

| Contract / Check | Address | Selector | Raw / Decoded Value at Block `26403523` |
| :--- | :--- | :--- | :--- |
| **`USR.defaultAdmin()` / `defaultAdminDelay()`** | `0x66a1E37c9b0eAddca17d3662D6c05F4DECf3e110` | `0x84ef8ffc` / `0xcc8463c8` | `defaultAdmin() = 0xD6889F307BE1b83Bb355d5DA7d4478FB0d2Af547` (`4-of-6` Gnosis Safe, `getThreshold() = 4`, `getOwners().length = 6`); `defaultAdminDelay() = 86400` seconds (`1` day) |
| **Sampled External Request Counters `paused()`** | `0xa27a69Ae180e202fDe5D38189a3F24Fe24E55861` | `0x5c975abb` | `true` (`1`) on `UsrExternalRequestsManager` (`0xa27a69Ae180e202fDe5D38189a3F24Fe24E55861`) and `true` (`1`) on `RlpExternalRequestsManager` (`0xc7AB90c2Ea9271EFB31f5fA2843Eeb4B331eaFA0`) |
| **`USR.totalSupply()` / `RLP.totalSupply()`** | `0x66a1E37c9b0eAddca17d3662D6c05F4DECf3e110` | `0x18160ddd` | `USR.totalSupply() = 6085929526436824288269831` (`6,085,929.53` `USR`, `18` dec); `RLP` (`0x4956b52aE2fF65D74CA2d61207523288e4528f96`) `totalSupply() = 1592731623006060329714506` (`1,592,731.62` `RLP`, `18` dec) |

> **Scope & Evidence Limit**: Sampled read-only getter/slot observations at the pinned block compared against cited documentation; does not certify protocol-wide authority completeness, downstream mutation semantics, or exploitability.
