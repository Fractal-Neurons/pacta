# Pacta — Institutional Counterparty & On-Chain Commitment Index

[![Counterparty Index Portal](https://img.shields.io/badge/Live_Index-pacta.wtf-38bdf8?style=for-the-badge&labelColor=000000)](https://pacta.wtf/)
[![JSON API v1](https://img.shields.io/badge/JSON_Feed-%2Fapi%2Fv1%2Findex.json-22c55e?style=for-the-badge&labelColor=000000)](https://pacta.wtf/api/v1/index.json)
[![Base Registry](https://img.shields.io/badge/Base_Registry-pacta.base.eth-0052ff?style=for-the-badge&labelColor=000000)](https://sourcify.dev/#/lookup/0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872)
[![Base EAS Schema](https://img.shields.io/badge/Base_EAS-0x7ff4...df83-a855f7?style=for-the-badge&labelColor=000000)](https://base.easscan.org/schema/view/0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83)
[![Request Scope](https://img.shields.io/badge/Intake-Request_Institutional_Scope-38bdf8?style=for-the-badge&labelColor=000000)](https://github.com/Fractal-Neurons/pacta/issues/new?template=request-scan.yml&title=%5BPacta+Scope%5D+Organization+%2F+Protocol)

> **Public Counterparty Snapshot Portal:** [**`https://pacta.wtf/`**](https://pacta.wtf/)  
> **Machine-Readable Snapshot JSON (`v1`):** [**`https://pacta.wtf/api/v1/index.json`**](https://pacta.wtf/api/v1/index.json)  
> **On-Chain Base Registry (`pacta.base.eth`):** [`0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872`](https://basescan.org/address/0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872) ([Sourcify `exact_match`](https://sourcify.dev/#/lookup/0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872)) · [Base EAS Schema `0x7ff4...df83`](https://base.easscan.org/schema/view/0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83)  
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
4. **Free Private Disclosure**:
   - Directly callable state mutations, unrevoked legacy EOA authorities, and exploit-sensitive findings (`disclosure_only`) are **excluded** from public commits and feeds, and are routed **privately, free of charge** (paired with target-specific, fork-simulated Safe Transaction Builder remediation engineering) exclusively through official private security channels (`GHSA`, `security@`, Immunefi, Cantina). Do **not** submit security vulnerabilities in public GitHub issues.

---

## On-Chain Anchoring on Base Mainnet (`pacta.base.eth`)

**14 Sprints · 37 Indexed Records** (14 parameter deltas · 4 protective deltas · 19 aligned baselines).

Sprints 1–12 (zero quarantined findings) carry 12 on-chain Base EAS sprint attestations (multi-attest tx `0x8c53e155a4b2f28ffbf069f1b65952fc8f7d81740f362b8aafb39493c6bd001b`); Sprints 13–14 are pinned by canonical block hash and SHA-256 summary digest in `/api/v1/index.json` until batch-attested. Every attested sprint summary is cryptographically anchored on **Base Mainnet (`Chain ID 8453`)** by our dedicated Tier-2 Attester (`pacta.base.eth` / `0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09`, governed by cold Tier-1 owner `0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`):

- **`PactaCommitmentRegistry` (Base Mainnet):** [`0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872`](https://basescan.org/address/0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872) · [Sourcify `exact_match`](https://sourcify.dev/#/lookup/0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872)
- **Canonical Base EAS Schema (`0x4200...0020`):** [`0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83`](https://base.easscan.org/schema/view/0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83) (`uint64 sprint,uint64 ethereumBlock,bytes32 ethereumBlockHash,bytes32 summarySha256,uint16 publicRecordCount,string summaryPath`)
- **Official Basename:** `pacta.base.eth` (forward + reverse L2 resolver verified on Base Mainnet)

---

## Block-Pinned Public Sprint Summaries (Ethereum Mainnet)

**14 Sprints · 37 Indexed Records.** Site build: `python3 tools/refresh_radar.py && python3 tools/build_site.py && python3 verify_site_v2.py` (the canonical base URL is a single `BASE_URL` constant in `tools/build_site.py`; brief pages are rendered from `tools/briefs_src/` inside the shared site chrome, and every call to action goes through the in-browser request builder at `/request/`).

| Sprint | Pinned Block | Canonical Block Hash | Base EAS Attestation | Public Summary & Sampled Protocols |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint 1** | `26399876` (`0x192d484`) | `0x8bf896b892683ff3267b88b367ab015a70cf5caf53542eb405f4f648f6bcde8a` | [`0x3404...3058`](https://base.easscan.org/attestation/view/0x34049a2c64fe3355f8e325481234754c8422a48bb4784fed1d028fa40eb93058) | [`audits/sprint-1/block-26399876-summary.md`](audits/sprint-1/block-26399876-summary.md) — Inverse Finance (`FiRM`), Origin (`OETH`/`OUSD`), Yearn |
| **Sprint 2** | `26400152` (`0x192d598`) | `0xa9a61622304ec55c5fec49abbcabec60069f66f28792cf841bdd7aef12ce63aa` | [`0xca4b...8101`](https://base.easscan.org/attestation/view/0xca4b525bf5142d8e88433cbed2a1aa87bb06a97d1353cb77621ec41a51ce8101) | [`audits/sprint-2/block-26400152-summary.md`](audits/sprint-2/block-26400152-summary.md) — f(x) Protocol v2, Alchemix, Gearbox V3, Reserve |
| **Sprint 3** | `26401070` (`0x192d92e`) | `0xcf55f6a42ae610c1f8766b5c2fb676d91f178469fa10ef777eccbb76f6506234` | [`0x291e...95a8`](https://base.easscan.org/attestation/view/0x291e513f3d697eea41b20bd57bf53acdb085b5566e499dd655ff46d7cd9d95a8) | [`audits/sprint-3/block-26401070-summary.md`](audits/sprint-3/block-26401070-summary.md) — ether.fi Liquid / Veda BoringVault, Morpho Blue Core |
| **Sprint 4** | `26401312` (`0x192da20`) | `0x95866ea3ef8f9a0567ce000bc8075f6dc5fb0f1e80cb4e9999ae624a2f0dc109` | [`0xa26f...2986`](https://base.easscan.org/attestation/view/0xa26f81b0e68248c7f286527286b3d2e6b299502d53f4dfbc4397df7d22262986) | [`audits/sprint-4/block-26401312-summary.md`](audits/sprint-4/block-26401312-summary.md) — Mellow / Lido Earn, Convex Finance |
| **Sprint 5** | `26401405` (`0x192da7d`) | `0x26e155e1569d436406a52ecee31c94d8d8ef2ca4c45d82211a84c8c802be1510` | [`0x8042...28e5`](https://base.easscan.org/attestation/view/0x804289d4357b0a8d5a360911ec450c13ca36c4422d1e811c4c7040ef7d2628e5) | [`audits/sprint-5/block-26401405-summary.md`](audits/sprint-5/block-26401405-summary.md) — Fluid / Instadapp, MetaMorpho (`Re7 WETH` / `Re7 USDT`) |
| **Sprint 6** | `26401540` (`0x192db04`) | `0x49324aaf84b0ffd4e21026c5345272788bff377f0f86fcdb74280cdfc32a9641` | [`0x749d...09fa`](https://base.easscan.org/attestation/view/0x749d96e1a3d214a4ab66c528ca12c84dce085fa138dc370dd0eb817d890f09fa) | [`audits/sprint-6/block-26401540-summary.md`](audits/sprint-6/block-26401540-summary.md) — Maple Finance V2 / Syrup, Liquity V2 (`BOLD`) |
| **Sprint 7** | `26401638` (`0x192db66`) | `0xe62ad2969617ad07c23bec298c3d5e197ea7c3084f7f66c90d2eb51d04c6273e` | [`0x3e0e...8779`](https://base.easscan.org/attestation/view/0x3e0e0e1b62de65b277b1399f9833cd70baf627e5ba69e17f1f4f76be30008779) | [`audits/sprint-7/block-26401638-summary.md`](audits/sprint-7/block-26401638-summary.md) — Ethena (`USDe`/`sUSDe`), ether.fi Core, Spark / Sky |
| **Sprint 8** | `26401725` (`0x192dbbd`) | `0xec3820f0a9db32c01728e66f78dc1958e410269e1077fd1db53df4fbce2ad7a1` | [`0xfd7c...a6c2`](https://base.easscan.org/attestation/view/0xfd7ce0f2b980da6606c8cd755da45d99f9ae4826e6df1321ff52c2b0f8e6a6c2) | [`audits/sprint-8/block-26401725-summary.md`](audits/sprint-8/block-26401725-summary.md) — Usual Money (`USD0`), Renzo (`ezETH`), Yearn V3 |
| **Sprint 9** | `26402160` (`0x192dd70`) | `0xd04a5e8aa3500c5b60d90c25a810ef28eb9d1bfffadf28f1da58a31ed90582dc` | [`0x0e01...6eea`](https://base.easscan.org/attestation/view/0x0e017bc4399101f9fef3d98a434dd9f2829b6e386e7733408dfd4b626d186eea) | [`audits/sprint-9/block-26402160-summary.md`](audits/sprint-9/block-26402160-summary.md) — Compound V3 (`Comet`), Aave V3 / GHO, Kelp DAO (`rsETH`), EigenLayer Core |
| **Sprint 10** | `26403121` (`0x192e131`) | `0x71acee2313a2c8eacd7d2c87667dc505310b3e9224d84eaebb71d5a890ef9d1c` | [`0xfdd8...0e6c`](https://base.easscan.org/attestation/view/0xfdd83c8091ef6e8ffe67e8a55a78892fcfbb1092683b21ff2d85f8cc09750e6c) | [`audits/sprint-10/block-26403121-summary.md`](audits/sprint-10/block-26403121-summary.md) — Ondo Finance (`OUSG`/`Flux`), Mantle (`mETH`), Symbiotic Core, Lido (`DualGovernance`) |
| **Sprint 11** | `26403523` (`0x192e2c3`) | `0xfc7beaa2338e8054577c0b101b641bc42afca2af39cb85d3fc13cbee32d4681a` | [`0x754e...5e42`](https://base.easscan.org/attestation/view/0x754edd7612258b755ff2e56903243d1f8867bad53c29ce3febb5ed9114005e42) | [`audits/sprint-11/block-26403523-summary.md`](audits/sprint-11/block-26403523-summary.md) — Curve (`crvUSD`), Gearbox V3 / V3.1, Lombard (`LBTC`), Resolv (`USR`/`RLP`) |
| **Sprint 12** | `26403676` (`0x192e35c`) | `0xf4246ca23c4c38d520de16080a11b5186d04c8242b2c85edcb04c455d291c3ae` | [`0x7caa...6de9`](https://base.easscan.org/attestation/view/0x7caae9c22c86ae171392def07dce83fa5da6fbf904b1ba9b5ff66a5021b16de9) | [`audits/sprint-12/block-26403676-summary.md`](audits/sprint-12/block-26403676-summary.md) — Stader (`ETHx`), StakeWise V3 (`osETH`), Swell (`swETH`/`rswETH`), Superstate (`USTB`/`USCC`) |
| **Sprint 13** | `26405302` (`0x192e9b6`) | `0xe05f4fd5698556131e7514b3a8eb24960962a768f8e0bfe0e99e3f1681127f65` | Pending batch attestation (hash-pinned) | [`audits/sprint-13/block-26405302-summary.md`](audits/sprint-13/block-26405302-summary.md) — ether.fi Core Upgrade Timelock op `0x244e…359f` |
| **Sprint 14** | `26406106` (`0x192ecda`) | `0xcb24dfb0b8af01dff9550fbbf6eb589b30d29b9625f41af56c188ae10d086ecf` | Pending batch attestation (hash-pinned) | [`audits/sprint-14/block-26406106-summary.md`](audits/sprint-14/block-26406106-summary.md) — Ethena, Treehouse TREE, Inverse FiRM, Kelp rsETH |

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
