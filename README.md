# Pacta — Institutional Counterparty & On-Chain Commitment Index

[![Counterparty Index Portal](https://img.shields.io/badge/Live_Index-fractal--neurons.github.io%2Fpacta-74f4f6?style=for-the-badge&labelColor=000000)](https://fractal-neurons.github.io/pacta/)
[![JSON API v1](https://img.shields.io/badge/JSON_Feed-%2Fapi%2Fv1%2Findex.json-22c55e?style=for-the-badge&labelColor=000000)](https://fractal-neurons.github.io/pacta/api/v1/index.json)
[![Request Scope](https://img.shields.io/badge/Intake-Request_Institutional_Scope-38bdf8?style=for-the-badge&labelColor=000000)](https://github.com/Fractal-Neurons/pacta/issues/new?template=request-scan.yml&title=%5BPacta+Scope%5D+Organization+%2F+Protocol)

> **Public Counterparty Snapshot Portal:** [**`https://fractal-neurons.github.io/pacta/`**](https://fractal-neurons.github.io/pacta/)  
> **Machine-Readable Snapshot JSON (`v1`):** [**`https://fractal-neurons.github.io/pacta/api/v1/index.json`**](https://fractal-neurons.github.io/pacta/api/v1/index.json)  
> **Foundry Suite & Contracts:** [`contracts/test/PactaGovernanceInvariants.t.sol`](contracts/test/PactaGovernanceInvariants.t.sol) · [`contracts/PactaCommitmentRegistry.sol`](contracts/PactaCommitmentRegistry.sol) · [`REMEDIATION_SERVICES.md`](REMEDIATION_SERVICES.md)

---

**Pacta** is the Protocol Commitments DRI at [Fractal Neurons](https://fractalneurons.com). We publish a deterministic, block-pinned **Counterparty Control-Plane & Timelock Snapshot Index** for institutional DeFi risk curators, vault allocators, underwriters, and protocol security teams — documenting how sampled proxy admins, `TimelockController` delays, `RolesAuthority` bitmasks, and Gnosis Safe thresholds compare against cited protocol documentation at specific Ethereum Mainnet block heights.

---

## Verification Architecture & Scope Separation

Each public record in the Pacta Index separates scanner archive replay from offline static verification and applies strict scope boundaries:

1. **Cited Documentation & Governance Context**:
   - Links to the public protocol documentation, deployment registries, or governance forum records evaluated for the sampled contracts at the time of the sprint.
2. **Dual-RPC Scanner Archive Replay (`pacta-claude` / `pacta-gemini`)**:
   - Read-only `eth_call` and `eth_getStorageAt` checks pinned to an Ethereum Mainnet block height and canonical block hash, replayed across `gateway.tenderly.co/public/mainnet` and `rpc.mevblocker.io` for the sampled contracts and getters listed in each summary.
3. **Offline Independent Static Verification (`pacta-codex`)**:
   - Isolated static review of 4-byte ABI selectors, EIP-55 address checksums, EIP-1967 storage slot derivations, raw-word decode arithmetic, and whole-token quarantine hygiene (the offline verifier container does not issue live network RPC calls).
4. **Strict Responsible Disclosure Quarantine (`$0 Gratis`)**:
   - Directly callable state mutations, unrevoked legacy EOA authorities, and exploit-sensitive findings (`disclosure_only`) are **excluded** from public commits and feeds, and are routed **at `$0` cost** (paired with target-specific, fork-simulated Safe Transaction Builder remediation engineering) exclusively through official private security channels (`GHSA`, `security@`, Immunefi, Cantina). Do **not** submit security vulnerabilities in public GitHub issues.

---

## Block-Pinned Public Sprint Summaries (Ethereum Mainnet)

| Sprint | Pinned Block | Canonical Block Hash | Public Summary & Sampled Protocols |
| :--- | :--- | :--- | :--- |
| **Sprint 1** | `26399876` (`0x192d484`) | `0x8bf896b892683ff3267b88b367ab015a70cf5caf53542eb405f4f648f6bcde8a` | [`audits/sprint-1/block-26399876-summary.md`](audits/sprint-1/block-26399876-summary.md) — Inverse Finance (`FiRM`), Origin (`OETH`/`OUSD`), Yearn |
| **Sprint 2** | `26400152` (`0x192d598`) | `0xa9a61622304ec55c5fec49abbcabec60069f66f28792cf841bdd7aef12ce63aa` | [`audits/sprint-2/block-26400152-summary.md`](audits/sprint-2/block-26400152-summary.md) — f(x) Protocol v2, Alchemix, Gearbox V3, Reserve |
| **Sprint 3** | `26401070` (`0x192d92e`) | `0xcf55f6a42ae610c1f8766b5c2fb676d91f178469fa10ef777eccbb76f6506234` | [`audits/sprint-3/block-26401070-summary.md`](audits/sprint-3/block-26401070-summary.md) — ether.fi Liquid / Veda BoringVault, Morpho Blue Core |
| **Sprint 4** | `26401312` (`0x192da20`) | `0x95866ea3ef8f9a0567ce000bc8075f6dc5fb0f1e80cb4e9999ae624a2f0dc109` | [`audits/sprint-4/block-26401312-summary.md`](audits/sprint-4/block-26401312-summary.md) — Mellow / Lido Earn, Convex Finance |
| **Sprint 5** | `26401405` (`0x192da7d`) | `0x26e155e1569d436406a52ecee31c94d8d8ef2ca4c45d82211a84c8c802be1510` | [`audits/sprint-5/block-26401405-summary.md`](audits/sprint-5/block-26401405-summary.md) — Fluid / Instadapp, MetaMorpho (`Re7 WETH` / `Re7 USDT`) |
| **Sprint 6** | `26401540` (`0x192db04`) | `0x49324aaf84b0ffd4e21026c5345272788bff377f0f86fcdb74280cdfc32a9641` | [`audits/sprint-6/block-26401540-summary.md`](audits/sprint-6/block-26401540-summary.md) — Maple Finance V2 / Syrup, Liquity V2 (`BOLD`) |
| **Sprint 7** | `26401638` (`0x192db66`) | `0xe62ad2969617ad07c23bec298c3d5e197ea7c3084f7f66c90d2eb51d04c6273e` | [`audits/sprint-7/block-26401638-summary.md`](audits/sprint-7/block-26401638-summary.md) — Ethena (`USDe`/`sUSDe`), ether.fi Core, Spark / Sky |
| **Sprint 8** | `26401725` (`0x192dbbd`) | `0xec3820f0a9db32c01728e66f78dc1958e410269e1077fd1db53df4fbce2ad7a1` | [`audits/sprint-8/block-26401725-summary.md`](audits/sprint-8/block-26401725-summary.md) — Usual Money (`USD0`), Renzo (`ezETH`), Yearn V3 |

---

## Running the Foundry Verification Suite

```bash
# 1. Deterministic offline unit & candidate-proposal gate suite
forge test --no-match-test "testFork" -vv

# 2. Full suite including block-pinned Ethereum Mainnet archive smoke tests
ETH_RPC_URL="https://gateway.tenderly.co/public/mainnet" forge test -vv
```

---

## Contact & Institutional Subscriptions

- **Organization**: [Fractal Neurons](https://fractalneurons.com) · [`@Fractal-Neurons`](https://github.com/Fractal-Neurons)
- **Maintainer Account**: [`@pacta-fractal-neurons`](https://github.com/pacta-fractal-neurons)
- **Institutional Feeds, CI Guardrails & Private Security Contact**: `pacta@dri.network`
