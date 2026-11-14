---
name: pacta-protocol-commitments
description: Run Pacta's free pre-execution check on any Ethereum or Base contract before an agent approves, deposits into or calls it (who can upgrade, pause or blacklist it, how fast), query the free block-pinned DeFi control-plane feeds, verify any value on an archive node, and map live Aave / Euler / Morpho / Sky governance proposals to on-chain state.
version: "0.1.0"
homepage: https://pacta.wtf/
---

# Pacta protocol commitments

Use this skill when a task involves DeFi collateral risk, governance or upgrade authority, timelocks, Safe quorums or roles,
or a live collateral onboarding proposal. Pacta publishes 37 block-pinned records (14 sprints) and
10 governance proposals mapped to on-chain state. Everything is read-only and free.

## Free pre-execution API (launch: $0, no API key, no wallet)
- Remote MCP, zero install: `https://pacta-x402.pacta.workers.dev/mcp` (Streamable HTTP). Claude Code: `claude mcp add --transport http pacta https://pacta-x402.pacta.workers.dev/mcp`.
  Tools: `pacta_check_preflight`, `pacta_scan_control_plane`, `pacta_scan_timelock_op`, `pacta_scan_proposal_diff`, `pacta_get_live_timelocks`.
- One call: `curl -s "https://pacta-x402.pacta.workers.dev/v1/check/preflight?chain=ethereum&address=0x..."` returns `verdict`, `riskScore` (0-100), proxy /
  implementation (EIP-1967, EIP-1822 or beacon), `controller` (eoa, multisig_safe, timelock, contract,
  access_control_enumerable, access_control or none), `canUpgradeZeroDelay`, `capabilities` (pause, blacklist, upgrade) and
  `pinnedBlock` + `pinnedBlockHash`. Verdicts: `IMMUTABLE_NO_ADMIN`, `TIMELOCK_PROTECTED`, `ZERO_DELAY_TIMELOCK_RISK` (0 s
  timelock: no exit window), `MULTISIG_NO_TIMELOCK`, `INSTANT_EOA_ADMIN_RISK`, `UNDEPLOYED_OR_EOA`,
  `UNCLASSIFIED_CONTRACT_CONTROLLER` (never treat it as safe).
- OpenAPI 3.1: `https://pacta-x402.pacta.workers.dev/openapi.json`. Every route takes GET query parameters or a POST JSON body. 60 requests / minute per caller.
- Protocol safety records: `https://pacta.wtf/protocols/`.

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
publication_pending: @pacta/mcp-server is not yet published to npm or the MCP registry. Use the remote MCP server now (no install): https://pacta-x402.pacta.workers.dev/mcp. The stdio server runs from a clone of the repository: node packages/mcp-server/bin/pacta-mcp.mjs.

- `pacta_list_commitments` (free): Filter indexed records (protocol, classification, sprint, limit)
- `pacta_get_anchoring` (free): Base EAS anchoring: PactaCommitmentRegistry, schema, sprint attestation UIDs
- `pacta_list_proposals` (free): Governance proposals feed (forum, topic_id, chain, limit, include_repro)
- `pacta_x402_discover` (free): x402 gateway status and discovery manifest (only when PACTA_X402_URL is set)
- `pacta_check_preflight` (x402 $0.01): Pre-execution check of a contract: verdict, 0-100 risk score, proxy / admin / timelock, capabilities (chain, address, block)
- `pacta_scan_control_plane` (x402 $0.10): Live control-plane scan of a contract (chain, address)
- `pacta_scan_timelock_op` (x402 $0.25): Live TimelockController operation state (timelock, opId)
- `pacta_live_timelocks` (x402 $0.10): Live state of tracked queued timelock operations
- `pacta_scan_proposal_diff` (x402 $0.15): Re-run a tracked governance proposal's pinned reads live, pinned-vs-live diffs (forum, topicId)

Environment (all optional, none secret):
- `PACTA_INDEX_PATH`: Local snapshot of /api/v1/index.json (offline use)
- `PACTA_PROPOSALS_PATH`: Local snapshot of /api/v1/proposals.json
- `PACTA_SPEC_PATH`: Local spec JSON (anchoring overrides, local index fallback)
- `PACTA_X402_URL`: Enables paid x402 tools against this gateway URL; the live gateway is https://pacta-x402.pacta.workers.dev (unset: free tools only)
- `PACTA_X402_MAX_ATOMIC`: Per-call USDC cap in atomic units (default 1000000 = $1.00; hard ceiling 5000000)
- `PACTA_X402_TIMEOUT_MS`: Timeout per outbound request in ms (default 8000)

## x402 (wired in; free during the launch)
- Live gateway: `https://pacta-x402.pacta.workers.dev` (discovery `https://pacta-x402.pacta.workers.dev/.well-known/x402`; free `/health`, `/v1/sample/control-plane`, `/v1/sample/preflight`).
- Free launch: every route answers HTTP 200 at $0 with no API key and no wallet (60 requests / minute per caller). The x402 prices below apply only if the operator switches pricingMode to x402_paid.
- The local stdio MCP server's scan tools are opt-in: set `PACTA_X402_URL=https://pacta-x402.pacta.workers.dev` to enable them.
- Base (8453), scheme `exact`, USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`, payTo `0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09`, `maxTimeoutSeconds` 60. Never sign for any other `payTo`.
- Routes and their x402_paid prices (GET query or POST JSON body with the same names; default client cap $1.00):
  - `https://pacta-x402.pacta.workers.dev/v1/check/preflight` ($0.01, `10000` atomic USDC): `?chain=ethereum|base&address=0x…`
  - `https://pacta-x402.pacta.workers.dev/v1/scan/control-plane` ($0.10, `100000` atomic USDC): `?chain=ethereum|base&address=0x…`
  - `https://pacta-x402.pacta.workers.dev/v1/scan/timelock-op` ($0.25, `250000` atomic USDC): `?chain=ethereum|base&timelock=0x…&opId=0x…`
  - `https://pacta-x402.pacta.workers.dev/v1/scan/proposal-diff` ($0.15, `150000` atomic USDC): `?forum=aave|euler|morpho|sky&topicId=<id>`
  - `https://pacta-x402.pacta.workers.dev/v1/briefs/live-timelocks` ($0.10, `100000` atomic USDC)
- `x402Versions: [1, 2]`, `networks: ["base", "eip155:8453"]`:
  - x402 v1: 402 JSON body (`x402Version: 1`, `network: "base"`, `maxAmountRequired`), pay with `X-PAYMENT`, receipt `X-PAYMENT-RESPONSE`.
  - x402 v2: `PAYMENT-REQUIRED` header (base64 JSON, `x402Version: 2`, `network: "eip155:8453"`, `amount`, `extensions.bazaar` with a JSON Schema draft 2020-12 schema), pay with `PAYMENT-SIGNATURE`, receipt `PAYMENT-RESPONSE`.
- Bare probe: a bare `GET` (no query) or zero-byte `POST` with no payment header returns HTTP 402 with both challenges.
- MCP tools take `xPaymentHeader` (v1) or `paymentSignatureHeader` (v2); `x402Version` picks the challenge to answer.
- A settled call returns 200 with both PAYMENT-RESPONSE and X-PAYMENT-RESPONSE (base64 {success, transaction, network, payer}). That receipt is the facilitator's settlement assertion bound to the payer; the MCP client checks it against the signed authorization but does not look the transaction up on Base (onchainReceiptVerified: false).
- Pacta Treasury `0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14` is an EOA (externally owned account) that receives issuer clearance payments; it is not an x402 payTo.

## Anchoring (Base, chain id 8453)
- PactaCommitmentRegistry `0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872`; EAS schema `0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83`. Per-sprint attestation UIDs are in `/api/v1/index.json`.

## Sentinel
PactaSentinelTripwire.sol: an ownerless, immutable contract granted Morpho Vault V2 isSentinel. Vault owners register rules (predicate module + config, cap id, adapter, liquidity reader). trigger(ruleId) is permissionless but re-checks the broken invariant on-chain in the same transaction, then sets the absolute cap to 0 (committed even if deallocate or the EAS receipt revert), deallocates min(allocation, liquid assets), and sweepRemaining(ruleId) drains the rest as liquidity returns. Zero custody. Predicates: AdminUpgradePredicate, OracleGovernanceSwapPredicate, PausePrivilegeEscalationPredicate, CapSupplyViolationPredicate. Status: built and tested (Foundry, 107 tests incl. invariants and fork tests); not audited, not deployed.

## Rules
- Report observed values with their block; do not infer exploitability from a parameter delta.
- Pacta reads governance forums and never posts on them: there is no live forum posting.
- Exploit-sensitive findings go to Immunefi or Cantina, never to public channels.
