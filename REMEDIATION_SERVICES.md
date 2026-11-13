# Pacta Institutional Counterparty Feeds & Commitment CI Subscriptions

## 1. Responsible Security Disclosures & Remediation Engineering (`$0 Gratis`)

Security-sensitive and unrevoked-authority findings (`disclosure_only`) are strictly excluded from public repositories and feeds. Pacta delivers the block-pinned proof bundle **at zero cost (`$0`)** exclusively to official protocol security contacts (`GHSA`, `security@`, Immunefi, or Cantina), paired with **gratis Safe Transaction Builder remediation engineering** (fork-simulated against current target-contract code and live state prior to maintainer signing).

---

## 2. Scoped Institutional Subscriptions & Engineering Engagements

In addition to the public block-pinned snapshot feed ([`docs/api/v1/index.json`](docs/api/v1/index.json)) and open-source reference test suite ([`contracts/test/PactaGovernanceInvariants.t.sol`](contracts/test/PactaGovernanceInvariants.t.sol)), Pacta offers two scoped institutional engagements:

1. **Curator & Allocator Counterparty Control-Plane Subscription (`$2,000 – $5,000 USDC / month`)**
   - Custom portfolio coverage extending [`docs/api/v1/index.json`](docs/api/v1/index.json) with dedicated archive monitoring and webhook alerts on emitted control-plane events (`CallScheduled`, `Upgraded`, `RoleGranted`, `RoleRevoked`, `MinDelayChange`, `ChangedThreshold`, `EnabledModule`) across underlying vault collateral (`USDe`, `syrupUSDC`, `weETH`, `ezETH`, `USD0`, curated Morpho/Euler/BoringVault markets).
2. **Protocol Commitment CI & Pre-Flight Proposal Gate Engagement (`$3,000 – $10,000 USDC / year`)**
   - Tailored Foundry fork-invariant suite modeled on [`contracts/test/PactaGovernanceInvariants.t.sol`](contracts/test/PactaGovernanceInvariants.t.sol) integrated into the protocol's GitHub Actions workflow, plus pre-execution fork simulation of queued Governor / Timelock payloads against documented delay, proxy-admin, and role-separation rules.

Contact **`pacta@dri.network`** or submit a scoped intake request via [`.github/ISSUE_TEMPLATE/request-scan.yml`](.github/ISSUE_TEMPLATE/request-scan.yml).
