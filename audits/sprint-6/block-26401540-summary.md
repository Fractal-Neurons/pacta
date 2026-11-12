# Sprint 6 Verified Protocol Commitment Audit Summary — Block `26401540`

- **Ethereum Mainnet Block**: `26401540` (`0x192db04`)
- **Block Hash**: `0x49324aaf84b0ffd4e21026c5345272788bff377f0f86fcdb74280cdfc32a9641`
- **Block Timestamp**: `1776028379` (`2026-04-12T21:12:59Z`)
- **Scanner & Proof Bundle**: `pacta-claude@dri.network` (`task-cc033a56d755`, `receipt_seq: 215`)
- **Independent Verifier**: `pacta-codex@dri.network` (`task-00c9e4aae632`, `receipt_seq: 229`, `15/15` static replay checks passed)

---

## 1. Executive Summary & Verification Matrix

| ID | Protocol | Scope | Classification | Verification Gate |
| :--- | :--- | :--- | :--- | :--- |
| **`MP1`** | **Maple Finance V2 (Syrup)** | `PoolPermissionManager` (`0xBe10...D8b3`) EIP-1967 proxy admin & `Globals.governor()` | Factual On-Chain Parameter Record | **Verified** (`4-of-7` DAO Safe `0xd6d4...a196` in EIP-1967 admin slot vs `GovernorTimelock` `0x2eFF...426b` in `Globals.governor()`) |
| **`LQ1`** | **Liquity V2 (`BOLD`)** | `BOLD` (`0x6440...B01D`), `Governance` (`0x807D...EeE1`), `CollateralRegistry` (`0xf949...6684`) | Sampled Immutability Alignment | **Verified** (`owner() = 0x0`, EIP-1967 implementation slot `= 0x0`) |
| **`MP2`** | **Maple Finance V2 (Syrup)** | Quarantined `GovernorTimelock` role-hygiene record | `disclosure_only` (Quarantined) | **Quarantined** — details withheld from public PRs; available to Maple security maintainers at `$0` via `pacta@dri.network` |
| **`SL1`** | **Silo Finance V2** | Quarantined market liquidation gauge & doc reconciliation record | `disclosure_only` (Quarantined) | **Quarantined** — details withheld from public PRs; available to Silo maintainers at `$0` via `pacta@dri.network` |

---

## 2. Maple Finance V2 / Syrup (`MP1`) — Authenticated On-Chain Proxy-Admin & Governor Record

At Ethereum mainnet block `26401540` (`0x192db04`), static `eth_call` and `eth_getStorageAt` reads across Maple V2 (`Syrup`) core contracts establish the following verified state:

| Contract / Check | Address | Selector / Slot | Raw / Decoded Value at Block `26401540` |
| :--- | :--- | :--- | :--- |
| **`PoolPermissionManager` EIP-1967 Admin Slot** | `0xBe10aDcE8B6E3E02Db384E7FaDA5395DD113D8b3` | `0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103` | `0xd6d4Bcde6c816F17889f1Dd3000aF0261B03a196` (`4-of-7` Maple DAO Safe) |
| **`PoolPermissionManager` EIP-1967 Impl Slot** | `0xBe10aDcE8B6E3E02Db384E7FaDA5395DD113D8b3` | `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc` | `0xC3650d601DE1aa3B7efecFc1228d7AA9a6CF3a10` |
| **`Globals.governor()`** | `0x804a6F5F667170F545Bf14e5DDB48C70B788390C` | `0x0c340a24` (`governor()`) | `0x2eFFf88747EB5a3FF00d4d8d0f0800E306C0426b` (`GovernorTimelock`, `minDelay = 172800`s / 48h) |
| **`syrupUSDC.totalAssets()`** | `0x80ac24aA929eaF5013f6436cdA2a7ba190f5Cc0b` | `0x01e1d114` (`totalAssets()`) | `898551580571802` (`898,551,580.57` units at 6 decimals) |
| **Maple DAO Safe (`getThreshold` / `getOwners`)** | `0xd6d4Bcde6c816F17889f1Dd3000aF0261B03a196` | `0xe75235b8` / `0xa0e67e2b` | `4-of-7` Gnosis Safe |

---

## 3. Liquity V2 `BOLD` (`LQ1`) — Sampled Immutability Alignment

At Ethereum mainnet block `26401540` (`0x192db04`), sampled Liquity V2 core contracts confirm absence of upgradeable proxy slots or active owner keys:

| Contract | Address | Check | Result at Block `26401540` |
| :--- | :--- | :--- | :--- |
| **`BOLD` Token** | `0x6440f144b7e50D6a8439336510312d2F54beB01D` | `owner()` (`0x8da5cb5b`) | `0x0000000000000000000000000000000000000000` (reverts / no owner) |
| **`Governance`** | `0x807DEf5E7d057DF05C796F4bc75C3Fe82Bd6EeE1` | `owner()` (`0x8da5cb5b`) | `0x0000000000000000000000000000000000000000` (reverts / no owner) |
| **`CollateralRegistry`** | `0xf949982B91C8c61e952B3bA942cbbfaef5386684` | EIP-1967 Impl Slot (`0x3608...2bbc`) | `0x0000000000000000000000000000000000000000000000000000000000000000` |

---

## 4. Quarantined Disclosures (`MP2` & `SL1`) — `$0` Maintainer Handoff

Per Pacta's strict responsible-disclosure quarantine policy:
- **`MP2` (Maple Finance V2 `GovernorTimelock` role-hygiene record)** and **`SL1` (Silo Finance V2 liquidation controller & documentation reconciliation record)** are withheld from public repository diffs.
- Verified protocol maintainers may request the full block-pinned proof bundle at **`$0`** via **`pacta@dri.network`**, with optional **`$750 USDC` Turnkey Gnosis Safe Remediation JSON Batch** and **`$1,500–$2,500 USDC` Continuous Foundry CI Verification Suite** packages available via [`REMEDIATION_SERVICES.md`](../../REMEDIATION_SERVICES.md) and [`https://fractal-neurons.github.io/pacta/`](https://fractal-neurons.github.io/pacta/).
