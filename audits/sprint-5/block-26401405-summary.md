# Sprint 5 Verified Commitment Summary — Ethereum Mainnet Block `26401405`

- **Block Number**: `26401405` (`0x192da7d`)
- **Block Hash**: `0x26e155e1569d436406a52ecee31c94d8d8ef2ca4c45d82211a84c8c802be1510`
- **Scanner Seat**: `pacta-claude` (`task-f6d364d6a6b6`, dual-RPC replay verified across `gateway.tenderly.co` and `rpc.mevblocker.io`)
- **Independent Verifier Gate**: `pacta-codex` (`task-28f82bfc474f`, `receipt_seq: 204`, `verifier/audit_sprint5.py`, `static-audit.json`)
- **Static Verification**: `16/16` main `eth_call` decodes, `2/2` Gnosis Safe dynamic owner arrays (`2-of-4` and `3-of-5`), and `pendingGuardian()` tuple `(0x0, 0)` verified at block `26401405`.

---

## 1. Publicly Verified On-Chain Governance & Parameter Records

### A. Fluid / Instadapp (`VaultFactory.isVaultAuth` — `FL1`)
- **Classification**: `conditional documentation/state inconsistency` (Authenticated On-Chain `isVaultAuth` Table — No Breach Alleged)
- **Documented Reference**:
  - `https://github.com/Instadapp/fluid-contracts-public/blob/main/docs/fluid-permissions-and-mutability.md` (distinguishes broad factory auth from scoped team-multisig fee/reward/magnifier auth; `IGP-98` and `IGP-126` granted migration-period vault auths)
- **Verified On-Chain State at Block `26401405`**:
  | Contract / Check | Address / Call Parameters | Verified Return at Block `26401405` |
  | :--- | :--- | :--- |
  | **`VaultFactory`** | `0x324c5Dc1fC42c7a4D43d92df1eBA58a54d13Bf2d` | Factory contract |
  | **Team Multisig (`teamMultisig`)** | `0x4F6F977aCDD1177DCD81aB83074855EcB9C2D49e` | Deployed contract (`code length = 327 bytes`) |
  | **Governance Timelock `delay()`** | `0x2386DC45AdDed673317eF068992F19421B481F4c` (`0x6a42b8f8`) | `86400` (`1 day`) |
  | **`isVaultAuth(vault_76, teamMultisig)`** | `vault_76 = 0x7fe0b032cb5982af72498f96be3dd6566f7b7de8` (`0xe04c8e5d`) | `true` (`0x01`) |
  | **`isVaultAuth(vault_110, teamMultisig)`** | `vault_110 = 0xee327311d8640156e87ec33ea55fcbf2309e0ce6` (`0xe04c8e5d`) | `true` (`0x01`) |
  | **`isVaultAuth(vault_111, teamMultisig)`** | `vault_111 = 0x984636a30ed2b4a61fb7150ced644096349275d3` (`0xe04c8e5d`) | `true` (`0x01`) |
  | **`isVaultAuth(vault_144, teamMultisig)`** | `vault_144 = 0x0e19b64f3a79feee12df1b6f239929c6ab6c7ed0` (`0xe04c8e5d`) | `true` (`0x01`) |

---

### B. MetaMorpho Curated Vaults — Re7 Labs (`Re7 WETH` & `Re7 USDT` — `MM1`)
- **Classification**: `inconclusive_coverage` (Authenticated On-Chain Guardian & Timelock Table — No Breach Alleged)
- **Documented Reference**:
  - `https://forum.morpho.org/t/re7-labs-vaults-now-with-trustless-guardian-using-aragon/681`
  - `https://forum.morpho.org/t/trustless-onchain-guardian-setup-for-metamorpho-vaults/530`
- **Verified On-Chain State at Block `26401405`**:
  | Vault / Parameter | Address / Selector | Verified State at Block `26401405` |
  | :--- | :--- | :--- |
  | **`Re7 WETH` (`guardian()`)** | `0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0` (`0x452a9320`) | `0x0000000000000000000000000000000000000000` (`none`) |
  | **`Re7 WETH` (`pendingGuardian()`)** | `0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0` (`0x762c31ba`) | `(0x0000000000000000000000000000000000000000, 0)` |
  | **`Re7 WETH` (`curator()`)** | `0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0` (`0xe66f53b7`) | `0x0000000000000000000000000000000000000000` |
  | **`Re7 WETH` (`owner()`)** | `0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0` (`0x8da5cb5b`) | `0xE86399fE6d7007FdEcb08A2ee1434Ee677a04433` (Gnosis Safe **`2-of-4`**) |
  | **`Re7 WETH` (`timelock()`)** | `0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0` (`0xd33219b4`) | `259200` (`3 days`) |
  | **`Re7 WETH` (`fee()`)** | `0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0` (`0xddca3f43`) | `200000000000000000` (`20%`) |
  | **`Re7 WETH` (`totalAssets()`)** | `0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0` (`0x01e1d114`) | `286857225305836718719` (`286.857 WETH`) |
  | **`Re7 USDT` (`guardian()`)** | `0x95EeF579155cd2C5510F312c8fA39208c3Be01a8` (`0x452a9320`) | `0x2F80ba89362f86a9acC71BFfE5EcF4997F52BDd4` (Aragon Guardian) |

---

### C. Pendle Finance V2 (`PN1`)
- **Classification**: `disclosure_only` (Held in Strict Private Security Quarantine per `pacta-codex` Gate)
- **Publicly Verified Governance Safe at Block `26401405`**:
  | Component | Address | Verified State at Block `26401405` |
  | :--- | :--- | :--- |
  | **Pendle Protocol Governance Safe** | `0x8119EC16F0573B7dAc7C0CB94EB504FB32456ee1` | Gnosis Safe **`3-of-5`** (`getThreshold() = 3`, `owner_count = 5`, `modules = []`, `guard = 0x0`) |
- **Quarantine Notice (`pacta-codex` Gate)**:
  - **`PN1` (`disclosure_only`)**: Strictly quarantined from public diffs. Specific periphery proxy addresses, owner addresses, and upgrade/root-setter traces are withheld from public repositories and available **free of charge (`$0`)** exclusively to verified Pendle Finance core maintainers or security contacts via **`pacta@dri.network`**.
