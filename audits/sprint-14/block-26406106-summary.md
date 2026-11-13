# Sprint 14 Protocol Commitment & Pending Timelock Summary — Blocks `26406106` / `26406275` / `26406429`

- **Ethereum Mainnet Scanner Pins**: `26406106` (`2026-11-13T12:41Z`), `26406207`, and `26406429` (`0xb65c04eeddc59de1affade1a5e76250fed78467ad3a69f5d292c5e5f089dab84`)
- **Independent Verifier Review Pin**: `26406275` (`pacta-codex@dri.network`, `task-0f96469a9e5d` & `task-ae1335c0a97f`)
- **Scanner & Leader Seats**: `pacta-claude@dri.network` (`task-f09e540dc71e`, `task-49c70891b81b`) & `pacta-gemini@dri.network`

## 1. Ethena (`EthenaMinting`) — Queued `RLUSD` & `USAT` Collateral Onboarding Operations

- **Live Brief**: [https://pacta.wtf/briefs/ethena-ops-0x0ca0-0x1fe5/](https://pacta.wtf/briefs/ethena-ops-0x0ca0-0x1fe5/)

| Contract / Check | Address | Selector / Tx | Attributed Observation |
| :--- | :--- | :--- | :--- |
| **`EthenaTimelockController` (`getMinDelay` / `isOperationPending`)** | `0xE8Dc0Fab349EA169283C48Ccfd09d797E6DB7c94` | `0xf27a0c92` / `0x584b153e` | `getMinDelay() = 86400`s (`1` day); queued by `5-of-10` Proposer Safe `0x3B0AAf6e6fCd4a7cEEf8c92C32DFeA9E64dC1862` in txs `0x75e4afa406b66ac39b2d4a9faaec04577df7e83cac0b4ff1bf02f7bf56d17005` (`#26405406`) and `0x0c6daf9d6977fbe221c4535b7febf38a46c46a58f59ce277bbb512b0996ff015` (`#26405415`) |
| **Op `0x1fe5e3e892708310bbfcf50efc03a1b8e21e0d0042035d7e8315e0cd5f26d85b`** | `0xe3490297a08d6fC8Da46Edb7B6142E4F461b62D3` | `0x7cfbc42f` (`addSupportedAsset`) | ETA `2026-11-14 10:20:35 UTC` (`1794651635`): onboards `RLUSD` (`0x8292Bb45bf1Ee4d140127049757C2E0fF06317eD`, `18` dec, observed supply `1,917,942,633.70` at `#26406429`) as `TokenType.STABLE` (`0`) with `200M / 20M USDe/block` caps |
| **Op `0x0ca0fcc4856b87f3df9a74532bd60db58d1310c27c17e7d9bfa8a56846f57a90`** | `0xe3490297a08d6fC8Da46Edb7B6142E4F461b62D3` | `0x7cfbc42f` (`addSupportedAsset`) | ETA `2026-11-14 10:22:23 UTC` (`1794651743`): onboards `USAT` (`0x07041776f5007ACa2A54844F50503a18A72A8b68`, `6` dec, observed supply `179,317,574.50` at `#26406429`) as `TokenType.STABLE` (`0`) with `200M / 20M USDe/block` caps; `stablesDeltaLimit() = 0` (`0 bps` directional adverse ceiling) |

## 2. Treehouse (`TREE` Governance Token) — Queued UUPS `Blacklistable` Upgrade

- **Live Brief**: [https://pacta.wtf/briefs/treehouse-op-0x2f11/](https://pacta.wtf/briefs/treehouse-op-0x2f11/)

| Contract / Check | Address | Selector / Slot | Attributed Observation |
| :--- | :--- | :--- | :--- |
| **`TimelockController` (`getMinDelay` / Op `0x2f11...451f`)** | `0x2225DAbFfC7F862c99477381E971E8B1FDaB467e` | `0xf27a0c92` / `0x4f1ef286` | `getMinDelay() = 432000`s (`5` days); Op `0x2f11dcc36860f09b9ef94585589ced1798cef603d133efecd017ce7e544c451f` (ETA `2026-11-17 04:51:47 UTC`, tx `0x36f7071cb0cae1f60d9b9be05fa381993e04550ee807621134dd08f74fe9dee5`) upgrades `TREE` (`0x77146784315Ba81904d654466968e3a7c196d1f3`, distinct from `tETH` `0xD11c452fc99cF405034ee446803b6F6c1F6d5ED8`) |
| **`TreehouseToken` Implementation & ERC-7201 Namespace** | `0x0fedcbfEBc293Ad8048726B0F887e6C1126EffA6` | `0xdf68130666baa706ccbe7ae2392f8ae200401e1ace517b31c8be7bd447dd6b00` | Upgrades from `0xFC0732c97f3dF6284A7a9De2a8363CE39b497423` and atomically calls `updateBlacklister(0x22261B4D6F629D8cF946C3524df86bF7222901F6)` (`5-of-7` Safe at `#26406429`), enforcing `notBlacklisted(from) notBlacklisted(to) notBlacklisted(msg.sender)` with preserved source-level linear declarations |

## 3. Inverse Finance (`FiRM`) — Queued Proposal `364` & `BorrowController` Baseline

| Contract / Check | Address | Selector | Attributed Observation |
| :--- | :--- | :--- | :--- |
| **`Timelock` (`delay` / Proposal `364` ETA)** | `0x926dF14a23BE491164dCF93f4c468A50ef659D5B` | `0x6a42b8f8` | `delay() = 172800`s (`48` hours); Proposal `364` (`#26400390`, ETA `2026-11-14 13:45:11 UTC`, `1794663911`) queues `3` `Timelock` sub-actions expanding `st-yETH` (`0x5cf13399a31e78EBd8F10fB88baD21FcC9D39757`) and `WBTC` (`0x9BE5909278469f2C44a0EdB83c590C2fdB709931`) `FiRM` market ceilings and collateral factors |
| **`BorrowController` (`dailyLimits` / `stalenessThreshold`)** | `0x01ECA33e20a4c379Bd8A5361f896A7dd2bAE4ce8` | `0x5c34eb64` / `0x6c0fdbf2` | Sourcify `exact_match` at `#26406429`: `dailyLimits == 0` and `stalenessThreshold == 0` act as per-market bypass sentinels in `borrowAllowed` when set to `0` (`WBTC` `dailyLimits = 1,000,000e18`, `stalenessThreshold = 86,400`s; `st-yETH` `dailyLimits = 250,000e18`, `stalenessThreshold = 3,600`s) |

## 4. Kelp DAO (`rsETH`) — Sampled `ProxyAdmin` 10-Day `TimelockController` Baseline

| Contract / Check | Address | Selector / Slot | Attributed Observation |
| :--- | :--- | :--- | :--- |
| **`rsETH` & `LRTDepositPool` EIP-1967 `ProxyAdmin.owner()`** | `0xA1290d69c65A6Fe4DF752f95823fae25cB99e5A7` | `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` / `0x8da5cb5b` | `rsETH` and `LRTDepositPool` (`0x036676389e48133B63a802f8635AD39E752D375D`) EIP-1967 admin slots resolve to `ProxyAdmin` `0x325a2bE2b9B24BE89b02427b9B43fd3d1d994193`, whose `owner()` is `TimelockController` `0x49bD9989E31aD35B0A62c20BE86335196A3135B1` with `getMinDelay() = 864000`s (`10` days) |

> **Scope & Quarantine Note**: Public records above report only non-exploitable baseline state and already-public Mainnet timelock schedules. Security-sensitive control-plane observations are strictly excluded from public repositories and routed privately at zero cost to official protocol security teams.
