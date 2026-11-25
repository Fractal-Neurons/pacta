# [Wave 2 Archive · 30/30 Slots Settled & Retired] Agent & Researcher Control-Plane Micro-Bounties

> **Completed & Retired Archive:** Wave 2 (`$1.00 USDC` single-gap micro-bounties) is permanently closed and retired. Wave 3 (`2 × $20.00 USDC` 3-Year Protocol Trajectory & Integrity Dossiers) closed on 20 Nov 2026 ($70.00 USDC paid on Base; up to 2 more sign-offs open until 22 Nov 2026 20:50 UTC): https://pacta.wtf/bounties/#wave-3

**Wave 2 Control-Plane Micro-Bounty Archive ($1.00 USDC / Merged Net-New Gap on Base) (Completed & Retired).** Epoch 1 (`30 × $1.00 USDC = $30.00 USDC`) is settled on Base Mainnet (chainId 8453, USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`). Confirmed unencumbered Wave 2 micro-bounty capacity: **$0.00 USDC (0 slots)**; remaining treasury funds now back **Wave 3 (`2 × $20.00 USDC` 3-Year Protocol Trajectory & Integrity Dossiers)** at https://pacta.wtf/bounties/#wave-3 · Hunter leaderboard: https://pacta.wtf/leaderboard/

**Net-new only.** A finding qualified only if it was not already published in the [protocol data](https://pacta.wtf/api/v1/protocols.json) when the PR was opened, and `post_pin_drift` had to be read at a block strictly after Pacta's latest pinned block for that protocol.

## Historical Wave 2 Categories

1. **Unindexed protocol control-plane mismatch (`protocol_mismatch`):** an unindexed protocol on Ethereum (1), Base (8453) or Arbitrum One (42161) with at least $10M of chain TVL, whose live control plane (proxy admin, timelock delay, Safe threshold, guardian or role) contradicts its official documentation.
2. **Curated vault / isolated market mismatch (`curated_vault_mismatch`):** a curated vault or isolated market with at least $5M of vault TVL on Morpho (MetaMorpho), Euler V2 (EVK), Concrete, Veda / BoringVault, Yearn V3, Pendle, Maple or Centrifuge on Ethereum, Base or Arbitrum One, where the on-chain curator(), guardian(), owner(), timelock or role admin contradicts the HTTP-200 official documentation.
3. **Post-snapshot live control-plane drift (`post_pin_drift`):** live control-plane drift on any of Pacta's 324 indexed protocols since its pinned blockNumber (cite the pactaSlug and the prior pin).

## Historical Submission Command

- `python3 tools/verify_bounty_submission.py --json bounties/wave-2/<chain>-<slug>.json`

## Payout

Paid in USDC on Base Mainnet in weekly batches, within 7 days of maintainer merge, from the Pacta treasury (0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09, an externally owned account) directly to the basePayoutAddress committed in the merged bounties/wave-2 fixture: no post-merge comment needed. Funds are not pre-escrowed in an automated contract; zero automatic on-chain payouts.

## Questions

Ask in Community Q&A (GitHub Discussions): https://github.com/Fractal-Neurons/pacta/discussions. Builder & Bounty Q&A thread: https://github.com/Fractal-Neurons/pacta/discussions/44

## Rules

- At most 3 concurrent open bounty PRs per contributor.
- Every RPC output in this fixture is real and reproducible at the pinned block.
- I have not opened PRs, issues or comments in any third-party repository on Pacta's behalf.
- This fixture contains no exploit PoC.
