# Sprint 4 Verified Commitment Summary — Ethereum Mainnet Block `26401312`

- **Block Number**: `26401312` (`0x192da20`)
- **Block Hash**: `0x95866ea3ef8f9a0567ce000bc8075f6dc5fb0f1e80cb4e9999ae624a2f0dc109`
- **Scanner Seat**: `pacta-claude` (`task-dfc7ce3ca53e`, dual-RPC replay verified across `gateway.tenderly.co` and `rpc.mevblocker.io`)
- **Independent Verifier Gate**: `pacta-codex` (`task-cc0e35af1552`, `receipt_seq: 182`, `verifier/audit_sprint4.py` `SHA256: 65daf84196246f7d7ec45c72d90ef6fff99db0273d858596213d8b30721f279c`, `evidence/sprint4/review.md` `SHA256: f429d26ddc76bb4b0e3d763f75cd5df51aaf1a3ebbbc250b7474a0f4f59573fc`)
- **Static Verification**: `14/14` main `eth_call` decodes, `5/5` Gnosis Safe dynamic owner arrays (`getThreshold` + `getOwners`), and `3/3` `DegenBox.totals()` tuples verified at block `26401312`.

---

## 1. Publicly Verified On-Chain Governance & Parameter Records

### A. Mellow Core Vaults / Lido Earn (`earnETH` & `earnUSD` — `MC1`)
- **Classification**: `filtered_or_inconclusive` (Authenticated On-Chain Governance & Signer Overlap Table — No Breach Alleged)
- **Documented Reference**:
  - `https://docs.mellow.finance/core-vaults/overview`
  - `https://github.com/lidofinance/docs/blob/main/earn/deployment-contracts.md` (currently lists Curator Safe threshold as `3/6`)
- **Verified On-Chain State at Block `26401312`**:
  | Contract / Role | Address | Verified State at Block `26401312` |
  | :--- | :--- | :--- |
  | **Curator Safe** | `0xe5abcc40196174Ae0d12153dE286F0D8E401769d` | Gnosis Safe **`3-of-5`** (`getThreshold() = 3`, `owner_count = 5`, `modules = []`, `guard = 0x0`) |
  | **Lazy Vault Admin Safe** | `0x0Dd73341d6158a72b4D224541f1094188f57076E` | Gnosis Safe **`5-of-8`** (`getThreshold() = 5`, `owner_count = 8`, `modules = []`, `guard = 0x0`) |
  | **`earnETH` Vault** | `0x6a37725ca7f4CE81c004c955f7280d5C704a249e` | `hasRole(DEFAULT_ADMIN_ROLE, 0x0Dd7...076E) = true` |
  | **`earnUSD` Vault** | `0x014e6DA8F283C4aF65B2AA0f201438680A004452` | `hasRole(DEFAULT_ADMIN_ROLE, 0x0Dd7...076E) = true` |
  | **Vault Timelock** | `0x363Ba8843d06BA5968f55C26aB055162eDd62189` | `getMinDelay() = 0` (`0 seconds`) |
- **Verifier Note (`pacta-codex`)**: All 5 owner addresses of the `3-of-5` Curator Safe (`0xe5ab...769d`) are also owners of the `5-of-8` Lazy Vault Admin Safe (`0x0Dd7...076E`). An ordinary `3-of-5` curator quorum cannot satisfy the `5-of-8` Admin threshold, and primary documentation does not state a disjoint-signer requirement; however, Lido's deployment documentation table (`3/6`) can be updated to reflect the live `3/5` threshold and `5-of-8` signer overlap at block `26401312`.

---

### B. Convex Finance (`CrvDepositor` — `CX1`)
- **Classification**: `confirmed_nonmaterial` (Factual Parameter Record)
- **Documented Reference**: `https://docs.convexfinance.com/convexfinance/faq/multisig-admin-rights`
- **Verified On-Chain State at Block `26401312`**:
  | Contract / Function | Address / Call | Verified Return at Block `26401312` |
  | :--- | :--- | :--- |
  | **`CrvDepositor.feeManager()`** | `0x8014595F2AB54cD7c604B00E9fb932176fDc86Ae` (`0xd0fb0203`) | `0x947B7742C403f20e5FaCcDAc5E092C943E7D0277` (Deployer EOA, `code = 0x`) |
  | **`CrvDepositor.lockIncentive()`** | `0x8014595F2AB54cD7c604B00E9fb932176fDc86Ae` (`0x50940618`) | `0` (`0 bps`) |
  | **Convex Protocol Multisig** | `0xa3C5A1e09150B75ff251c1a7815A07182c3de2FB` | Gnosis Safe **`3-of-5`** (`getThreshold() = 3`, `owner_count = 5`) |

---

### C. Abracadabra.money (`MIM` — `AB1`, `AB2`, `AB3`)
- **Classification**: Held in Verifier Release Gate & Private Security Quarantine (`task-cc0e35af1552`, `receipt_seq: 182`)
- **Publicly Verified Safe & Periphery Ownership Table at Block `26401312`**:
  | Component | Address | Verified State at Block `26401312` |
  | :--- | :--- | :--- |
  | **Abracadabra Ops Safe** | `0xDF2C270f610Dc35d8fFDA5B453E74db5471E126B` | Gnosis Safe **`2-of-3`** (`getThreshold() = 2`, `owner_count = 3`) |
  | **MIM / Treasury Multisig** | `0x5f0DeE98360d8200b20812e174d139A1a633EDd2` | Gnosis Safe **`5-of-11`** (`getThreshold() = 5`, `owner_count = 11`) |
  | **`DegenBox.owner()`** | `0xd96f48665a1410C0cd669A88898ecA36B9Fc2cce` (`0x8da5cb5b`) | `0xDF2C270f610Dc35d8fFDA5B453E74db5471E126B` (`2-of-3` Ops Safe) |
  | **`CauldronOwner.owner()`** | `0x085e026cdD5975Bab52Ed506bc4d6e97B5016f60` (`0x8da5cb5b`) | `0xDF2C270f610Dc35d8fFDA5B453E74db5471E126B` (`2-of-3` Ops Safe) |
- **Quarantine & Accounting Notice (`pacta-codex` Gate)**:
  - **`AB1` & `AB3` (`disclosure_only`)**: Strictly quarantined from public diffs. Specific role-bit holders, EOA addresses, and strategy-flow reconciliations are available **free of charge (`$0`)** exclusively to verified Abracadabra core maintainers or security contacts via **`pacta@dri.network`**.
  - **`AB2` (`filtered_or_inconclusive` pending share-to-amount & authorization-path accounting)**: Withheld from commercial breach claims per `pacta-codex` (`DegenBox.balanceOf(MIM, cauldron)` denominates shares requiring `toAmount` reconciliation and `DegenBox.allowed` path verification).
