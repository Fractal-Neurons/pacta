# Pacta Engagements: Free Open Data + 24h Issuer Clearance

## 1. Free and Real-Time for Curators, Allocators and AI Risk Agents (`$0`, always)

Every public Pacta risk flag is open to everyone in real time, with no key, delay or paywall:

- every indexed record in [`docs/api/v1/index.json`](docs/api/v1/index.json) (block-pinned, canonical block hash, `cast` reproduction);
- the queued-timelock radar ([`docs/api/v1/radar.json`](docs/api/v1/radar.json)) and pre-execution briefs;
- [`llms.txt`](https://pacta.wtf/llms.txt) for AI risk agents.

Vault curators and risk stewards never pay. There are no curator subscriptions.

---

## 2. 24h Collateral Onboarding & Delta Clearance Attestation (`$5,000 USDC` flat)

For **collateral issuers** onboarding a new asset to Morpho, Euler, Aave or Sky, or clearing an open `parameter_delta` flag:

1. **Canonical block-pinned control-plane audit** of the asset's proxy admins, Safe quorums, roles and timelock delays (dual-RPC archive replay at a canonical Ethereum block hash).
2. **GitBook / config reconciliation PR** wherever the documentation and on-chain state differ.
3. **Base Mainnet EAS `Aligned` attestation** recorded in `PactaCommitmentRegistry` [`0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872`](https://basescan.org/address/0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872).
4. **Curator Diligence Dossier (PDF + JSON)**, paste-ready for Morpho, Euler, Aave and Sky forum listing proposals.

Delivered within **24 hours** of confirmed scope and payment. Optional **continuous `Aligned` badge maintenance: `$1,500 / month`** (continuous monitoring of the attested control plane).

**Payment:** `5,000 USDC` on Base (USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`) or Ethereum (USDC `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`) to the Pacta treasury **`0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`** (same address on both chains). Include the transaction hash and forum proposal URL in the request at [`pacta.wtf/request/`](https://pacta.wtf/request/), or send the scope first and pay after confirmation.

**Community queue (free):** the standard public queue, unscheduled (typically 6–8 weeks).

---

## 3. Exploit-Sensitive Vulnerabilities

Security-sensitive and unrevoked-authority findings (`disclosure_only`) are never published in public repositories or feeds. They go through the protocol's **Immunefi** or **Cantina** bounty programme, or to a partner audit firm under a **15% referral partnership**. Do not submit vulnerabilities in public GitHub issues.

Request a clearance or join the community queue via [`pacta.wtf/request/`](https://pacta.wtf/request/) or the intake template [`.github/ISSUE_TEMPLATE/request-scan.yml`](.github/ISSUE_TEMPLATE/request-scan.yml); contact `pacta@dri.network`.
