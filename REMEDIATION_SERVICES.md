# Pacta Engagements: Free Open Data + Paid Verification for Protocol Teams

The catalog covers **316 protocols (189 Base-EAS attested + 127 RPC-observed)**, with 309 attested checks across 37 Base EAS batch attestations. The tiers below are the same on [`pacta.wtf/#pricing`](https://pacta.wtf/#pricing) and [`pacta.wtf/request/`](https://pacta.wtf/request/).

## 1. Free and Real-Time for Curators, Allocators and AI Risk Agents (`$0`, always)

Every public Pacta risk flag is open to everyone in real time, with no key, delay or paywall:

- every indexed record in [`docs/api/v1/index.json`](docs/api/v1/index.json) (block-pinned, canonical block hash, `cast` reproduction);
- the queued-timelock radar ([`docs/api/v1/radar.json`](docs/api/v1/radar.json)) and pre-execution briefs;
- [`llms.txt`](https://pacta.wtf/llms.txt) for AI risk agents.

Vault curators and risk stewards never pay. There are no curator subscriptions.

---

## 2. Paid Verification for Protocol Teams (payment never changes a classification)

For **protocol teams and collateral issuers** onboarding a new asset to Morpho, Euler, Aave or Sky, or clearing an open `parameter_delta` flag:

| Tier | Price | Scope |
| --- | --- | --- |
| Rapid Single-Gap Re-Verification | `$500 USDC` (24h SLA) | A fresh re-read of one fixed Safe, timelock or documentation gap at a finalized block on two archive RPCs, an updated docs diff and a new Base EAS attestation. |
| Full Protocol Control-Plane Dossier | `$2,500–$5,000 USDC` (24h SLA) | `$2,500` single chain (up to 8 contracts) · `$5,000` multi-chain with a 90-day drift watch; the four deliverables below. |
| Continuous Control-Plane Monitoring | `$1,500 USDC / month` | Re-checks after governance proposals, signer rotations and timelock upgrades, with a refreshed dossier and attestation after every change. The result can still be Delta. |

The Full Protocol Control-Plane Dossier delivers:

1. **Canonical block-pinned control-plane audit** of the asset's proxy admins, Safe quorums, roles and timelock delays (dual-RPC archive replay at a canonical Ethereum block hash).
2. **GitBook / config reconciliation PR** wherever the documentation and on-chain state differ.
3. **Base Mainnet EAS `Aligned` attestation** recorded in `PactaCommitmentRegistry` [`0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872`](https://basescan.org/address/0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872).
4. **Curator Diligence Dossier (PDF + JSON)**, paste-ready for Morpho, Euler, Aave and Sky forum listing proposals.

Delivered within **24 hours** of confirmed scope and settlement. The classification follows the verified onchain and documentation evidence; payment never changes it. Request at [`pacta.wtf/request/?tier=clearance`](https://pacta.wtf/request/?tier=clearance) or [`?tier=continuous`](https://pacta.wtf/request/?tier=continuous).

**Settlement, two tracks:**

- **Option A (recommended for protocol treasuries and CFOs): formal commercial invoice (PDF) and counterparty settlement.** Submit scope first; no upfront transfer is needed to open intake. Pacta issues a formal commercial invoice (PDF) and verified counterparty payment instructions once scope is confirmed, for foundation finance teams, legal review and multi-signer treasury workflows.
- **Option B (direct express): on-chain USDC.** The tier's price in USDC on Base (USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`) or Ethereum (USDC `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`) to the Pacta treasury (direct settlement EOA) **`0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`**, an externally owned account (the same address on both chains). Include the transaction hash and forum proposal URL in the request at [`pacta.wtf/request/`](https://pacta.wtf/request/).

**High-throughput API (more than 60 requests / minute or a dedicated SLA):** x402 metered endpoints, or an Enterprise API key priced on scope at [`pacta.wtf/request/?tier=api_sla`](https://pacta.wtf/request/?tier=api_sla).

**Community queue (free):** the standard public queue, unscheduled (typically 6–8 weeks).

---

## 3. Exploit-Sensitive Vulnerabilities

Security-sensitive and unrevoked-authority findings (`disclosure_only`) are never published in public repositories or feeds. They go through the protocol's **Immunefi** or **Cantina** bounty programme. Do not submit vulnerabilities in public GitHub issues.

When code changes are needed, Pacta can refer teams to independent smart-contract auditors under a **15% referral partnership**; under the [Independence Policy](https://pacta.wtf/methodology/#independence), referrals never influence docs-vs-chain status.

Request a clearance or join the community queue via [`pacta.wtf/request/`](https://pacta.wtf/request/) or the intake template [`.github/ISSUE_TEMPLATE/request-scan.yml`](.github/ISSUE_TEMPLATE/request-scan.yml); contact `pacta@dri.network`.
