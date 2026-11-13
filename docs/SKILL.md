---
name: pacta-protocol-commitments
description: Query Pacta's free, block-pinned DeFi control-plane feeds (who can upgrade, pause, mint or change delays behind collateral), verify any value on an archive node, map live Aave / Euler / Morpho / Sky governance proposals to on-chain state, and optionally pay x402 Base USDC for live scans of unindexed contracts.
version: "0.1.0"
homepage: https://pacta.wtf/
---

# Pacta protocol commitments

Use this skill when a task involves DeFi collateral risk, governance or upgrade authority, timelocks, Safe quorums or roles,
or a live collateral onboarding proposal. Pacta publishes 37 block-pinned records (14 sprints) and
10 governance proposals mapped to on-chain state. Everything is read-only and free.

## Feeds (no key, no paywall)
- `https://pacta.wtf/api/v1/index.json`: Block-pinned control-plane index (every record: target, call, block, block hash, classification, Base EAS UID)
- `https://pacta.wtf/api/v1/onboarding.json`: Onboarding verification scans: every check with call, calldata, raw result, decoded value; role maps
- `https://pacta.wtf/api/v1/proposals.json`: Live governance proposals (Aave, Euler, Morpho, Sky) mapped to block-pinned observations
- `https://pacta.wtf/api/v1/radar.json`: Queued timelock operations with on-chain ETAs at a finalized block
- `https://pacta.wtf/llms.txt`: Short index for language models
- `https://pacta.wtf/llms-full.txt`: This file: the complete agent reference
- `https://pacta.wtf/.well-known/agent.json`: A2A Agent Card
- `https://pacta.wtf/.well-known/mcp.json`: MCP discovery manifest
- `https://pacta.wtf/SKILL.md`: Portable agent skill

## Verify before you trust
Every record carries a target contract, call signature and arguments, block number and canonical block hash:

```bash
cast call <target> "<signature>" <args> --block <N> --rpc-url "$ETH_RPC_URL"
cast block <N> --field hash --rpc-url "$ETH_RPC_URL"   # must equal the recorded block hash
```

Use EIP-1898 `{"blockHash": "<hash>", "requireCanonical": true}` when calling eth_call directly.

## MCP server (io.github.fractal-neurons/pacta)
publication_pending: @pacta/mcp-server is not yet published to npm or the MCP registry; the install commands below apply once it is. Until then use the free HTTPS feeds directly.

- `pacta_list_commitments` (free): Filter indexed records (protocol, classification, sprint, limit)
- `pacta_get_anchoring` (free): Base EAS anchoring: PactaCommitmentRegistry, schema, sprint attestation UIDs
- `pacta_list_proposals` (free): Governance proposals feed (forum, topic_id, chain, limit, include_repro)
- `pacta_x402_discover` (free): x402 gateway status and discovery manifest (only when PACTA_X402_URL is set)
- `pacta_scan_control_plane` (x402 $0.10): Live control-plane scan of a contract (chain, address)
- `pacta_scan_timelock_op` (x402 $0.25): Live TimelockController operation state (timelock, opId)
- `pacta_live_timelocks` (x402 $0.10): Live state of tracked queued timelock operations

Environment (all optional, none secret):
- `PACTA_INDEX_PATH`: Local snapshot of /api/v1/index.json (offline use)
- `PACTA_PROPOSALS_PATH`: Local snapshot of /api/v1/proposals.json
- `PACTA_SPEC_PATH`: Local spec JSON (anchoring overrides, local index fallback)
- `PACTA_X402_URL`: Enables paid x402 tools against this gateway URL (unset: free tools only)
- `PACTA_X402_MAX_ATOMIC`: Per-call USDC cap in atomic units (default 1000000 = $1.00; hard ceiling 5000000)
- `PACTA_X402_TIMEOUT_MS`: Timeout per outbound request in ms (default 8000)

## x402 (optional, only for live scans of contracts not in the index)
- Base (8453), scheme `exact`, USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`, payTo `0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09`. Never sign for any other `payTo`.
- Prices: control-plane scan $0.10, timelock operation $0.25, proposal diff $0.15, live timelocks $0.10. Default client cap $1.00.
- Pacta Treasury `0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14` is an EOA (externally owned account) that receives issuer clearance payments; it is not an x402 payTo.

## Anchoring (Base, chain id 8453)
- PactaCommitmentRegistry `0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872`; EAS schema `0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83`. Per-sprint attestation UIDs are in `/api/v1/index.json`.

## Sentinel
PactaSentinelTripwire.sol: an ownerless, immutable contract granted Morpho Vault V2 isSentinel. Vault owners register rules (predicate module + config, cap id, adapter, liquidity reader). trigger(ruleId) is permissionless but re-checks the broken invariant on-chain in the same transaction, then sets the absolute cap to 0 (committed even if deallocate or the EAS receipt revert), deallocates min(allocation, liquid assets), and sweepRemaining(ruleId) drains the rest as liquidity returns. Zero custody. Predicates: AdminUpgradePredicate, OracleGovernanceSwapPredicate, PausePrivilegeEscalationPredicate, CapSupplyViolationPredicate. Status: built and tested (Foundry, 107 tests incl. invariants and fork tests); not audited, not deployed.

## Rules
- Report observed values with their block; do not infer exploitability from a parameter delta.
- Pacta reads governance forums and never posts on them: there is no live forum posting.
- Exploit-sensitive findings go to Immunefi or Cantina, never to public channels.
