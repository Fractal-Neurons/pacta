# [Wave 3: 2 × $20 USDC | 3-Year Protocol Trajectory & Integrity Dossiers] Human-Researcher Control-Plane Due-Diligence Pool

**Wave 3 — 3-Year Protocol Trajectory & Integrity Dossier ($20.00 USDC / Protocol on Base).** **2 human-researcher dossier slots open now (`2 × $20.00 USDC = $40.00 USDC`).** Confirmed unencumbered on-chain now in `0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09` (an externally owned account on Base Mainnet, chainId 8453, USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`): **$40.00 USDC (2 slots)** plus `$0.05` operational buffer. Wave 2 (`$1.00` single-gap micro-bounties) and Wave 1 (`4 × $25.00 = $100.00 USDC` Genesis) are permanently completed and retired. Live board: https://pacta.wtf/bounties/#wave-3 · Researcher credentials & leaderboard: https://pacta.wtf/leaderboard/

## Eligible Targets (`>= $10M` TVL Across 7 EVM Chains + `133` `rpc_observed` Protocols Unlocked)

- **Chains:** `ethereum` (1), `base` (8453), `arbitrum` (42161), `optimism` (10), `polygon` (137), `bnb` (56), `avalanche` (43114)
- **TVL Floor:** `tvl_usd >= 10,000,000` (`$10M+` verified on DefiLlama or official analytics)
- **`rpc_observed` Targets Unlocked:** All **133 un-assessed `rpc_observed` (`easAttested: false`) protocols** in https://pacta.wtf/api/v1/protocols.json are eligible alongside unindexed `$10M+` protocols (only the 180 already Base-EAS attested protocols are excluded as duplicates).

## Mandatory 3-Part Human-Researcher Dossier (`2023–2026`)

1. **Part 1 — 3-Year On-Chain Control-Plane Timeline (`historical_transitions`):** `>= 2` distinct chronological blocks (`strictly increasing` `block_number` + `block_date` + `tx_hash` + reproducible `cast`/RPC proof) reconstructing proxy implementation upgrades, multi-owner signer/threshold changes, or timelock mutations across `2023–2026` (or multi-block proof of 3-year immutability + controller verification).
2. **Part 2 — Historical Docs & DAO Governance Forensics (`docs_and_governance_forensics`):** `>= 2` dated archival sources (including at least one dated GitHub docs commit/blob/PR, `web.archive.org` snapshot, or Snapshot/Tally/Discourse governance proposal) proving historical gap windows and exact **`MTTR` repair duration** (`mttr_days` or `unrepaired_open` duration).
3. **Part 3 — Repository & Engineering Reality Audit + Executive Risk Memo (`repo_audit` + `executive_risk_memo`):** 12-month smart-contract commits (`commits_12m_contracts`), non-contract commits (`commits_12m_frontend_or_other`), distinct human contributors (`human_contributors_12m`), `bus_factor`, `code_before_upgrade_verified` (`true`/`false`), and a substantive **`>= 400`-character `executive_risk_memo`** (shallow 1-liner or repetitive bot spam is deterministically rejected).
4. **Attribution, Payout & MCP Receipt:** `contributor_github`, EIP-55 `base_payout_address`, `mcp_tool_receipt` from `https://pacta-x402.pacta.workers.dev/mcp`, `apache2_commercial_grant: true`, and `rules_accepted: [true, true, true, true]`.

## How to Validate & Submit

1. Query Pacta's free keyless MCP server (`claude mcp add --transport http pacta https://pacta-x402.pacta.workers.dev/mcp`) and save the tool output in `mcp_tool_receipt`.
2. Commit **one** newly added JSON dossier at `bounties/wave-3/<chain>-<slug>.json` (full schema & valid example: `bounties/wave-3/README.md`).
3. Validate locally before opening your PR: `python3 tools/verify_bounty_submission.py --wave 3 --json bounties/wave-3/<chain>-<slug>.json`
4. Open a PR to `Fractal-Neurons/pacta`. CI (`verify-bounty-pr`) validates the single added JSON file with the base-branch validator; maintainers replay every historical block and archival commit before merging.

## Payout

Paid in USDC on Base Mainnet within 7 days of maintainer merge and historical archive replay, from the Pacta treasury (0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09, an externally owned account) directly to the base_payout_address committed in the merged bounties/wave-3 dossier. Funds are held on-chain in the EOA treasury and are not pre-escrowed in an automated contract.

## Questions

Ask in Community Q&A (GitHub Discussions): https://github.com/Fractal-Neurons/pacta/discussions · Builder & Bounty Q&A thread: https://github.com/Fractal-Neurons/pacta/discussions/44

## Rules

- At most 2 concurrent open Wave 3 dossier PRs per researcher.
- Every block height, transaction hash, cast/RPC output, archival commit URL, and 12-month repo audit metric in this dossier is real and reproducible.
- I have not opened PRs, issues or comments in any third-party repository on Pacta's behalf.
- This dossier contains clinical due-diligence evidence only and zero exploit PoC.
