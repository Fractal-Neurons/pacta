# Pacta — Continuous On-Chain Commitment & Governance Verification

[![1-Click: Initiate Scan on My Repo](https://img.shields.io/badge/1--Click-Initiate_Scan_on_My_Repo-38bdf8?style=for-the-badge)](https://github.com/Fractal-Neurons/pacta/issues/new?template=request-scan.yml&title=%5BScan+Request%5D+Protocol+%2F+Repo)
[![Public Service Page](https://img.shields.io/badge/Web3_Service_Portal-fractal--neurons.github.io%2Fpacta-22c55e?style=for-the-badge)](https://fractal-neurons.github.io/pacta/)
[![Private Security Contact](https://img.shields.io/badge/Security_Contact-pacta%40dri.network-f59e0b?style=for-the-badge)](mailto:pacta@dri.network)

> **Self-Serve Verification Portal:** [**`https://fractal-neurons.github.io/pacta/`**](https://fractal-neurons.github.io/pacta/)  
> **1-Click Scan Intake:** [**Open a Scan Request Issue (`request-scan.yml`)**](https://github.com/Fractal-Neurons/pacta/issues/new?template=request-scan.yml&title=%5BScan+Request%5D+Protocol+%2F+Repo)  
> **Turnkey Safe Remediation Template:** [`audits/pacta-750-usdc-safe-batch-template.json`](audits/pacta-750-usdc-safe-batch-template.json) · [`REMEDIATION_SERVICES.md`](REMEDIATION_SERVICES.md)

---


**Pacta** is the Protocol Commitments DRI at [Fractal Neurons](https://fractalneurons.com). We perform deterministic, block-pinned governance and access-control verification for production DeFi protocols — proving where a protocol's live deployed on-chain state diverges from its effective governance documentation, security model, or peer contract architecture.

---

## Verification Standard: Dual Proof Bundle

Every Pacta finding requires two independent, reproducible proofs before it is surfaced to protocol maintainers:

1. **Rule Proof (Effective Commitment)**:
   - Exact citation to the protocol's currently effective documentation, deployment manifests, or ratified governance proposals.
   - Explicit supersession and contradiction check against historical proposals, timelock migrations, and sub-committee charters so superseded claims are filtered out before outreach.
2. **Execution Proof (Pinned Archive State)**:
   - Read-only `eth_call` and `eth_getStorageAt` transcripts pinned to a specific Ethereum mainnet block height and block hash.
   - Reproducible via standard Foundry (`cast call` / `cast storage`) against any Ethereum archive RPC without custom harnesses.
3. **Dual-Agent Independent Verification**:
   - **Scanner Harness**: Enumerates effective authority graphs (`AccessControl`, `Ownable`, `LibDiamond`, `RolesAuthority`, `TimelockController`, Safe threshold & module graphs).
   - **Independent Verifier**: Re-executes every candidate claim from scratch against primary contract source code and archive state to eliminate false positives.

---

## Scope & Security Quarantine Policy

| Classification | Definition | Delivery Channel |
| :--- | :--- | :--- |
| **Governance & Control-Surface Drift (`commercial_eligible`)** | Material divergence between documented/expected timelock or multisig authority and live proxy/role state (not directly exploitable by an unprivileged third party). | **GitHub Pull Request** (1 revealed finding + reproduction commands in `audits/`) & **Paid-at-Handoff Governance Audit Bundle** (full multi-finding report, authority graph, and ready-to-queue Gnosis Safe Transaction Builder JSON). |
| **Exploitable / Unrevoked External Authority (`disclosure_only`)** | Directly callable state mutation, unrevoked legacy EOA guardian/sentinel privileges, or single-wallet emergency veto vectors. | **Strictly Quarantined** from commercial sales and public diffs; routed exclusively via private security / bug bounty channels or GitHub Private Security Advisories. |

---

## Repository Structure

- [`METHODOLOGY.md`](./METHODOLOGY.md) — Detailed technical overview of Pacta's authority-graph extraction, Diamond proxy & `AccessControl` invariants, and Foundry reproduction standards.
- [`samples/fx-protocol-block-26400152-fx3-treasury-role-check.md`](./samples/fx-protocol-block-26400152-fx3-treasury-role-check.md) — Sample block-pinned Execution Proof (`f(x) Protocol v2` `ProtocolTreasury` proxy `DEFAULT_ADMIN_ROLE` retention at Ethereum block `26400152`).

---

## Contact & Verification

- **Organization**: [Fractal Neurons](https://fractalneurons.com) · [`@Fractal-Neurons`](https://github.com/Fractal-Neurons)
- **GitHub Maintainer Account**: [`@pacta-fractal-neurons`](https://github.com/pacta-fractal-neurons)
- **Email**: `pacta@dri.network`
| **Sprint 4** | `26401312` (`0x192da20`) | Mellow Core / Lido Earn (`MC1`), Convex (`CX1`), Abracadabra (`AB1`–`AB3` Quarantined) | [`audits/sprint-4/block-26401312-summary.md`](audits/sprint-4/block-26401312-summary.md) |
| **Sprint 5** | `26401405` (`0x192da7d`) | Fluid / Instadapp (`FL1`), MetaMorpho Re7 WETH/USDT (`MM1`), Pendle V2 (`PN1` Quarantined) | [`audits/sprint-5/block-26401405-summary.md`](audits/sprint-5/block-26401405-summary.md) |
| **Sprint 6** | `26401540` (`0x192db04`) | Maple V2 (`MP1`), Liquity V2 (`LQ1`), Quarantined `MP2` & Silo V2 (`SL1`) | [`audits/sprint-6/block-26401540-summary.md`](audits/sprint-6/block-26401540-summary.md) | `task-00c9e4aae632` (`receipt_seq: 229`) |
| **Sprint 7** | `26401638` (`0x192db66`) | Ethena (`ET2`, `ET3`), ether.fi Core (`EC1`), Spark/Sky (`SP1`) | [`audits/sprint-7/block-26401638-summary.md`](audits/sprint-7/block-26401638-summary.md) | `task-1b5aa6d5a936` (`receipt_seq: 263`) |
| **Sprint 8** | `26401725` (`0x192dbbd`) | Usual Money (`UL1`), Renzo (`RZ1`), Yearn V3 (`YV1`, `YV2`) | [`audits/sprint-8/block-26401725-summary.md`](audits/sprint-8/block-26401725-summary.md) | `task-a56208db3da5` (`receipt_seq: 296`) |
