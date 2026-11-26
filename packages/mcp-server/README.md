<img src="https://pacta.wtf/logo.svg" alt="Pacta" width="48" height="48" align="left">

# Pacta MCP server (`io.github.Fractal-Neurons/pacta`)
<br clear="left">

Zero-dependency Node.js MCP stdio server (v0.1.6) for [Pacta, by Fractal Neurons](https://pacta.wtf/) (`pacta.base.eth`): contract checks for 316 DeFi protocols on Ethereum & Base (189 Base-EAS attested). It serves DeFi control-plane commitments and Base Mainnet EAS attestations, with live gateway tools (who controls this contract, pre-flight check, verdict, dossier, control-plane / timelock / proposal scans) on by default: the gateway is `https://api.pacta.wtf` unless `PACTA_X402_URL` says otherwise (`PACTA_X402_URL=""` keeps the server local-only). The gateway is **free during the launch**: $0, no API key, no wallet, 60 requests / minute per caller. The x402 v1 + v2 Base USDC prices below apply only if metering is switched on.

It exposes **14 read-only inspection tools + 2 opt-in request tools** (`request_feature`, `pacta_submit_request`); the hosted remote MCP exposes 10 read-only inspection tools + the same 2 request tools. Every `inputSchema` lists only the tool's own inputs (no payment or caller-attribution fields), and every description opens with what the tool answers and ends with its price. Every inspection tool is annotated `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false` and carries `_meta` (`resultType`, `ttlMs`, `cacheScope`) in `tools/list`.

This package is stdio-only. It never opens a listening socket, and the test suite checks that statically. Nothing is published on npm: run it from a clone (`git clone https://github.com/Fractal-Neurons/pacta.git`, then `node packages/mcp-server/bin/pacta-mcp.mjs`), or use the hosted remote endpoint `https://api.pacta.wtf/mcp`, which is registered in the official MCP Registry as `io.github.Fractal-Neurons/pacta` (remote Streamable HTTP, from `server.remote.json`).

## Fastest: hosted remote MCP (zero install)

The live gateway serves the same gateway tools over Streamable HTTP at `https://api.pacta.wtf/mcp`:

```bash
claude mcp add --transport http pacta https://api.pacta.wtf/mcp
```

```json
{ "mcpServers": { "pacta": { "url": "https://api.pacta.wtf/mcp" } } }
```

Or call the API directly: `curl -s "https://api.pacta.wtf/v1/check/preflight?chain=ethereum&address=0x…"`. OpenAPI 3.1: `https://api.pacta.wtf/openapi.json`.

## Usage (stdio, zero-install local clone)

```bash
git clone https://github.com/Fractal-Neurons/pacta.git
```

```json
{
  "mcpServers": {
    "pacta": {
      "command": "node",
      "args": ["/path/to/pacta/packages/mcp-server/bin/pacta-mcp.mjs"],
      "env": { "PACTA_X402_URL": "https://api.pacta.wtf" }
    }
  }
}
```

## Tools

- **Start here: `pacta_lookup_protocol`** (always listed; free; no RPC). If you only have a protocol or token name (`Aave`, `Ethena`, `USDe`, `Moonwell`, `kUSD`, …), resolve it first, then pass the result's `preflightArgs` (`{chain, address}`) to `pacta_check_preflight`.
  - Inputs: `query` (name, token symbol, slug or `0x` address; at most 80 characters; empty or `*` lists the catalog), optional `chain` (`ethereum` | `base` | `eip155:1` | `eip155:8453`), `kind` (`protocol` | `brief` | `all`) and `limit` (1 to the catalog size; default 10, or 20 when listing).
  - Each result: `kind`, `slug`, `name`, `tokens`, `category`, `chain` / `chainId`, checksummed `primaryContract` + `targetLabel`, `controllerAddress` + `controllerKind`, observed / documented delays, `classification`, `evidenceBasis`, `easAttested`, `baseEasUids`, page `url` and `preflightArgs`, ranked exact → prefix → substring.
  - Scope: 189 Base-EAS-attested protocols (`evidenceBasis: "eas_attested"`, documentation compared), 135 RPC-observed protocols (`evidenceBasis: "rpc_observed"`, `easAttested: false`, `documentationComparison: "not_assessed"`; never labelled aligned or parameter delta) and 18 briefs (5 onboarding briefs and 13 timelock radar briefs).
  - The catalog is embedded (`src/lookup.mjs`, generated from `https://pacta.wtf/api/v1/lookup.json`). With the gateway on (the default), the tool asks the gateway's free `GET /v1/protocols/lookup` first (forwarding valid optional caller fields) and falls back to the embedded catalog on any failure (`source` says which answered).
- **Who controls this contract: `pacta_who_controls_contract`** (gateway, free: 100 calls per caller per UTC day, no key, no payment). Inputs: exactly `chain` (`ethereum` | `base`) and `address` (`0x` + 40 hex; a mixed-case address must carry a valid EIP-55 checksum). It sends one `GET <PACTA_X402_URL>/v1/check?chain=&address=` and returns the gateway's `pacta.who_controls.v1` JSON as is: owner, admin, upgradeable proxy, timelock, multisig, can mint, can pause, as block-pinned chain facts confirmed by two independent RPC providers, with Foundry `cast` commands; it never guesses or rates. `who_controls` is accepted as an alias in `tools/call`. Gateway refusals keep the gateway's code (`bad_request`, `rate_limited`, `free_quota_exhausted`, `upstream_unavailable`) and `meter`.
- **Default Free Tools** (static feed `https://pacta.wtf/api/v1/index.json`, fallback `https://fractal-neurons.github.io/pacta/api/v1/index.json`, or `PACTA_INDEX_PATH` / `PACTA_SPEC_PATH`):
  - `pacta_list_commitments`: filters dual-RPC-verified DeFi control-plane records (`protocol`, `classification`, `sprint`, `limit`).
  - `pacta_list_proposals`: filters the governance proposals feed (`https://pacta.wtf/api/v1/proposals.json`, fallback `https://fractal-neurons.github.io/pacta/api/v1/proposals.json`, or `PACTA_PROPOSALS_PATH` / the `proposalsPath` option). Filters: `forum` (`aave` | `euler` | `morpho` | `sky`), `topic_id`, `chain` (`ethereum` | `base`), `limit` (1 to 100, default 25). The output is compact, and `repro_commands` are included only with `include_repro: true`. The feed must have `schema === "pacta.governance_proposals_feed.v1"` and a `proposals` array of objects. Anything else is refused with `invalid_feed`. When no source yields a valid feed, the call fails with `feed_unavailable`, which carries per-URL `attempts` (`timeout`, `network_error`, `upstream_http_error`, `response_too_large`, `invalid_feed`). A configured local path is never replaced by a network fetch.
  - `pacta_get_anchoring`: returns the Base (`8453`) `PactaCommitmentRegistry` (`0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872`), the EAS Schema (`0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83`), and `pacta.base.eth`.
  - `pacta_x402_discover`: reports `PACTA_X402_URL` status, the live gateway `x402_gateway_url` and the local-spec payment requirements (labelled `source: "local_spec"`, validated by the same rules as upstream challenges). When `PACTA_X402_URL` is set, it also fetches `/.well-known/x402` and `/v1/sample/control-plane` for information only.
- **Live gateway.** The canonical Pacta x402 edge Worker is live at `https://api.pacta.wtf` (Cloudflare; free `/.well-known/x402`, `/v1/sample/control-plane`, `/openapi.json`). `pacta_get_anchoring` and `pacta_x402_discover` report it as `x402_gateway_url`. The server uses it by default: leaving `PACTA_X402_URL` unset is the same as `PACTA_X402_URL=https://api.pacta.wtf`. Set `PACTA_X402_URL=""` (empty) to keep the server local-only: then only the static-feed tools are listed and nothing is sent anywhere. Nothing is ever paid without a payment header you sign yourself (the server holds no keys).
- **Gateway tools, free during the launch; optional `x402` v1 + v2 Base USDC metering** (on by default; with `PACTA_X402_URL=""`, `tools/list` shows only the static-feed tools and gateway calls return `x402_disabled`). A free route answers HTTP 200 with no payment header, and the tool returns that as unpaid data (`paid: false`). Today the four scan tools are free ($0.00); preflight gives 50 and wallet exposure 100 free calls per caller per UTC day, then $0.01 Base USDC per call via x402; verdict and dossier give 100 free calls per caller per UTC day each, then $0.02 / $0.05 Base USDC per call via x402:
  - `pacta_check_preflight` → `/v1/check/preflight` (50 free calls per UTC day, then `$0.01` = `10000` atomic; `chain`, `address`, optional `block` = `latest` | decimal | 0x-hex). Verdict (`NO_CONTROLLER_FOUND` / `TIMELOCK_PROTECTED` / `ZERO_DELAY_TIMELOCK_RISK` / `MULTISIG_NO_TIMELOCK` / `INSTANT_EOA_ADMIN_RISK` / `UNCLASSIFIED_CONTRACT_CONTROLLER` / `UNDEPLOYED_OR_EOA`), 0–100 risk score, proxy + implementation, controller kind, zero-delay upgradeability, pause / blacklist / upgrade capabilities, pinned block.
  - `pacta_scan_wallet_exposure` → `/v1/check/wallet-exposure` (`$0.01` = `10000` atomic overflow / free 100 calls per UTC day; `address`, optional `chain` = `ethereum` | `base` | `all`). Read-only Multicall3 wallet & Gnosis Safe DeFi control-plane exposure scan across Ethereum and Base.
  - `pacta_scan_control_plane` → `/v1/scan/control-plane` (free, `$0.00` today; `chain`, `address`)
  - `pacta_live_timelocks` → `/v1/briefs/live-timelocks` (free, `$0.00` today). `pacta_get_live_timelocks`, the name used by the hosted remote MCP, is accepted as an alias in `tools/call`; it is not listed separately.
  - `pacta_scan_timelock_op` → `/v1/scan/timelock-op` (free, `$0.00` today; `chain`, `timelock`, `opId`)
  - `pacta_scan_proposal_diff` → `/v1/scan/proposal-diff` (free, `$0.00` today; `forum` = `aave` | `euler` | `morpho` | `sky`, `topicId` = the forum topic id). The proposal must be listed in `https://pacta.wtf/api/v1/proposals.json`.
  - `pacta_verdict` → `GET /v1/x402/verdict` (free 100 calls per UTC day, then `$0.02` = `20000` atomic; `slug`, or `chain` + `address`). Verdict, `riskScore` 0–100 and grade A–F (both `null` when not determined), a one-line verdict, upgrade / owner / pause / blacklist / mint capability flags, the controller (EOA, Safe threshold, timelock delay), the indexed Pacta record when there is one, and a shareable scan URL; one pinned block.
  - `pacta_dossier` → `GET /v1/x402/dossier` (free 100 calls per UTC day, then `$0.05` = `50000` atomic; `slug`, or `chain` + `address` of an indexed contract). Live EIP-1967 / owner / Safe reads, every controller Safe's signers and threshold, Safe signers shared with other indexed protocols, and the Base EAS attestation proof.

  **Free-tier caller fields (optional attribution).** `pacta_lookup_protocol`, `pacta_submit_request` and the `/v1/check/*` and `/v1/scan/*` / `/v1/briefs/*` gateway tools accept three optional, non-personal fields that no `inputSchema` lists (older clients may still send them); omitted, blank or invalid values never block a call. `pacta_who_controls_contract`, `pacta_verdict` and `pacta_dossier` accept and drop them (their routes take no extra query parameters):
  - `caller_agent`: a lowercase slug naming the calling AI agent, IDE or framework, `^[a-z0-9][a-z0-9._/-]{1,47}$` (e.g. `claude-code`, `cursor`, `windsurf`, `coinbase-agentkit`, `elizaos`, `langchain`, `openclaw`, `custom-agent`). E-mails, spaces, IP literals, `0x` addresses, URLs and secret-shaped tokens are dropped; never put a personal name here.
  - `requester_role`: one of `autonomous_agent`, `defi_developer`, `risk_curator_analyst`, `security_researcher`, `protocol_team`, `institutional_allocator`, `individual_user`.
  - `caller_purpose`: one of `pre_trade_safety`, `collateral_due_diligence`, `yield_allocation`, `security_audit`, `governance_monitoring`, `integration_testing`, `general_research`.

  Omitted or invalid caller attribution values are silently dropped locally (never stored, never sent, never rejected with `-32602`); valid values are forwarded as optional REST query or body parameters. A paying call (`xPaymentHeader` / `paymentSignatureHeader`) never fails on them and is sent without them. Location is never asked: the hosted Worker counts only the Cloudflare edge country. The static-feed tools send nothing anywhere, so they do not take these fields.

  **Payment arguments (accepted, not listed).** Every gateway tool still accepts `xPaymentHeader`, `paymentSignatureHeader`, `x402Version`, `payer`, `validBeforeSeconds` and `nonce` in `tools/call`, but no `inputSchema` lists them: a free call never needs them, and a `402` result carries the typedData and the envelope template to sign.

  When metering is on, the live Worker answers every metered route in both protocol versions. A bare request (no query, no payment header) gets the 402 immediately.
  - **x402 v1**: the 402 JSON body (`x402Version: 1`, `network: "base"`, `maxAmountRequired`). Pay with `xPaymentHeader`, sent as `X-PAYMENT`. The receipt is `X-PAYMENT-RESPONSE`.
  - **x402 v2**: the `PAYMENT-REQUIRED` header (base64 JSON, `x402Version: 2`, `network: "eip155:8453"`, `amount`, `extensions.bazaar` with a JSON Schema 2020-12 schema). Pay with `paymentSignatureHeader`, sent as `PAYMENT-SIGNATURE`. The receipt is `PAYMENT-RESPONSE`.

  If you send no payment argument, the tool returns the upstream `402` as a validated requirements entry for the version picked by `x402Version` (default `1`), along with:
  - `availableVersions` and `alternativeAccepts` for the other valid version;
  - EIP-712 `TransferWithAuthorization` `typedData`;
  - the envelope template for that version (`xPaymentEnvelopeTemplate` for v1, `paymentSignatureEnvelopeTemplate` for v2).

  Every challenge entry, v1 or v2, passes the same pins: allowlisted `payTo`, Base USDC, the `PACTA_X402_MAX_ATOMIC` cap, the route price, the `maxTimeoutSeconds` ceiling, and binding to the requested URL. Anything else is `rejected_challenge`. Sign the typedData yourself (the server holds no keys), base64-encode the envelope, and call the tool again with `xPaymentHeader` (v1) or `paymentSignatureHeader` (v2), never both.

  A paid call succeeds only with a 2xx and a valid `PAYMENT-RESPONSE` / `X-PAYMENT-RESPONSE` receipt on that version's network, whose payer, payTo and amount match your authorization. The receipt is the facilitator's assertion and is not looked up on Base (`onchainReceiptVerified: false`).

- **Opt-in request tool: `request_feature`** (listed with the gateway on; annotations `readOnlyHint: false`, `destructiveHint: false`, `idempotentHint: false`, `openWorldHint: false`; `_meta` `{resultType: "feature_request_receipt", ttlMs: 0, cacheScope: "none"}`). Tell Pacta what tool, chain, check or data your agent needs: exactly `text` (1–1000 characters) and an optional `use_case` (at most 500), sent as one JSON `POST <PACTA_X402_URL>/v1/feature-request`. Free, 5 per caller per UTC day; every request is read daily. Line breaks and tabs are normalized to spaces first; any other field, an e-mail address, an IP literal, a secret-shaped token or HTML is refused locally with `-32602` and nothing is sent. Returns `ok`, `request_id` (`FREQ-2026-xxxxxxxx`), `message` and `meter`. `pacta_request_feature` is accepted as an alias.
- **Opt-in request tool: `pacta_submit_request`** (listed with the gateway on; annotations `readOnlyHint: false`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false`; `_meta` `{resultType: "demand_receipt", ttlMs: 0, cacheScope: "none"}`). When a lookup misses or a pre-flight hits an unindexed target, the result carries `coverage_gap_hint`; ask the user, then call this tool to queue the coverage or feature request. It forwards one JSON `POST <PACTA_X402_URL>/v1/requests`.
  - Required: `request_type` (`missing_protocol` | `unsupported_chain` | `missing_check_surface` | `doc_or_data_discrepancy` | `mcp_or_api_feature`), `target_subject` (2–120 characters), `requested_capability` (5–280 characters), `urgency_track` (`community_queue_free` | `active_due_diligence` | `issuer_24h_clearance_5k` | `api_high_volume_sla`). Optional: `caller_agent`, `requester_role`, `caller_purpose`, `forum_proposal_url` (`https://`), `contact_handle` (only when the user explicitly asks for follow-up or an invoice; never guessed).
  - Returns `request_id` (`REQ-2026-xxxxxxxx`), `status` (`queued` | `upvoted_existing`), `demand_votes` and `fast_track_url`. An identical `request_type` + `target_subject` upvotes the existing request. Free in every pricing mode, 5 per hour per caller; never opens a GitHub issue.
  - Every string is checked locally first: private-key-shaped hex, API tokens, JWTs, `Bearer` credentials, seed-phrase-shaped word runs and HTML are refused with `-32602` and nothing is sent. The gateway stores `contact_handle` only in a private, write-only key; public records and the telemetry summary carry `has_contact_opt_in` (a boolean) only.

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `PACTA_X402_URL` | `https://api.pacta.wtf` | Base URL of the x402 gateway; unset means the canonical live one, `https://api.pacta.wtf`. An empty value (`PACTA_X402_URL=""`) turns the gateway tools off (local-only). Must be `https://`; plain `http://` is allowed only for `localhost` / `127.0.0.1` / `[::1]`. URLs with embedded credentials are refused. |
| `PACTA_X402_MAX_ATOMIC` | `1000000` ($1.00) | Per-payment cap in atomic USDC (6 decimals). Values above the hard ceiling `5000000` ($5.00) are clamped to it. Invalid values fall back to the default, and `pacta_x402_discover` reports a `configWarnings` entry. |
| `PACTA_X402_TIMEOUT_MS` | `8000` | Timeout for every outbound fetch (index, proposals, discovery, paid). Valid range is 1 to 60000. |
| `PACTA_INDEX_PATH` / `PACTA_SPEC_PATH` | unset | Local index / spec files for the free tools. |
| `PACTA_PROPOSALS_PATH` | unset | Local proposals feed (`pacta.governance_proposals_feed.v1`) for `pacta_list_proposals`. |

The hard ceiling is $5.00. No env var or option can raise it, so a mistyped or hostile environment cannot turn one tool call into a large transfer. In practice the route's own ceiling is the binding limit, and the cap is defence in depth.

## x402 payment safety rules

Pinned constants. Nothing an upstream response says can widen these:

- Network `base`, chain ID `8453`, asset Base USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`, EIP-712 domain `USD Coin` / `2` / `8453` / Base USDC.
- `payTo` allowlist:
  - `0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09` (attester / `pacta.base.eth`, the gateway's default)
  - `0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14` (treasury owner)
- Address comparison ignores case, but a mixed-case address must carry a valid EIP-55 checksum. Checksums are computed with a bundled pure-JS Keccak-256 (`src/keccak.mjs`), which is tested against known vectors and against `node:crypto` SHA3-256.

### Upstream `402` challenge (`accepts[]`)

Entries are collected from the JSON body `accepts`, from base64 `Payment-Required` / `X-Payment-Required` headers, and from `WWW-Authenticate: x402 <base64>` or `x402 accepts="<base64>"`. Each entry is validated independently. An entry is selected only if it meets all of the following:

- `x402Version` is `1` (on the entry, or on the enclosing object), `scheme` is `"exact"`, and `network` is `"base"`. If a `chainId` is present (on the entry or in `extra`), it must be `8453`.
- `asset` is Base USDC.
- `payTo` is in the allowlist.
- `maxAmountRequired` is a canonical positive integer string, no greater than the cap and no greater than the route's own price.
- `maxTimeoutSeconds` is an integer from 1 to 600.
- `extra` is `{ name: "USD Coin", version: "2" }`.
- The entry is bound to the exact URL that was requested. If `resource` is present, it may be absolute, or relative and resolved against the request origin. Either way it must have the same origin (scheme, host and port) and the same pathname as the requested URL. The query string is not compared. A challenge for another host, or for another route on the same gateway, is rejected. An entry with no `resource` makes no claim and is accepted.

The first valid entry is normalized from the pinned constants. Its `resource` is always the requested URL, and the upstream `resource` string is never copied into the output or the typedData. It is returned as `accepts: [entry]`, along with `selectedFrom` and `rejectedEntries` (per-entry reasons). The typedData is built only from that entry, and its TTL is `min(validBeforeSeconds ?? 300, entry.maxTimeoutSeconds)`.

If no entry passes, the call fails with `rejected_challenge`, which lists `{source, index, reasons[]}` for every entry. There is no fallback to `accepts[0]` and no typedData for an unvalidated entry.

Reason codes: `not_object`, `bad_x402_version`, `bad_scheme`, `bad_network`, `bad_chain_id`, `bad_asset`, `bad_asset_checksum`, `bad_pay_to`, `pay_to_not_allowed`, `bad_pay_to_checksum`, `bad_amount`, `amount_over_cap`, `amount_over_route_price`, `bad_max_timeout`, `bad_extra`, `missing_expected_resource` (the caller passed no absolute `expectedResource`), `bad_resource`, `resource_origin_mismatch`, `resource_path_mismatch`.

### Caller-supplied `X-PAYMENT` (`validateXPaymentHeader`)

This header is validated locally before any network call. Checks run in order:

1. It must be a non-empty string of at most 8 KiB.
2. It must be strict canonical Base64: standard alphabet, correct `=` padding, no whitespace, and a round-trip re-encode equal to the input.
3. It must decode as UTF-8 with `TextDecoder("utf-8", { fatal: true })`.
4. It must parse with `JSON.parse` into a plain object.
5. The envelope must have exactly `{x402Version: 1, scheme: "exact", network: "base", payload}`, and `payload` must have exactly `{signature, authorization}`.
6. `signature` must be 65-byte hex.
7. `authorization` must have exactly `from, to, value, validAfter, validBefore, nonce`:
   - `from` is a valid, non-zero address.
   - `to` is a valid address in the allowlist.
   - `value` is a positive integer string, no greater than the cap and no greater than the route price.
   - `validAfter <= now < validBefore`, and `validBefore - now <= 600`.
   - `nonce` is bytes32.

Failures return `{ code: "invalid_x_payment", reason }`. Reason codes: `not_string`, `empty`, `too_long`, `bad_base64`, `non_canonical_base64`, `bad_utf8`, `bad_json`, `not_object`, `unexpected_field`, `bad_x402_version`, `bad_scheme`, `bad_network`, `bad_payload`, `bad_signature`, `bad_authorization`, `bad_from`, `bad_to`, `bad_checksum`, `recipient_not_allowed`, `bad_value`, `value_over_cap`, `value_over_route_price`, `bad_route_price`, `bad_valid_after`, `bad_valid_before`, `not_yet_valid`, `expired`, `validity_window_too_long`, `bad_nonce`.

### Transport and settlement

- Every fetch uses `AbortSignal.timeout(ms)`. The timeout also covers reading the body, and it still fires if an injected `fetchImpl` ignores the signal. Response bodies are capped at 2 MiB (16 MiB for the free index and proposals feeds).
- Paid requests use `redirect: "error"`, so a 3xx response cannot carry `X-PAYMENT` to another origin.
- After `X-PAYMENT` is sent, the server requires HTTP 2xx and a valid `X-PAYMENT-RESPONSE` receipt. The receipt must meet all of the following:
  - It is strict base64 JSON with `success === true`, `network === "base"` and a non-zero 32-byte `transaction`.
  - `payer` equals `authorization.from` (case-insensitive).
  - Any recipient field present (`payTo`, `recipient` or `to`) is a valid address equal to `authorization.to`.
  - Any amount field present (`amount` or `value`) is a canonical positive integer equal to `authorization.value`.

  Anything else fails with `unverified_settlement` (`reason`, `status`, bounded `snippet`), and the body is not returned as a paid result. Receipt reasons: `missing_receipt`, `receipt_<base64 reason>`, `receipt_not_object`, `receipt_not_success`, `receipt_bad_network`, `receipt_bad_transaction`, `receipt_missing_payer`, `receipt_bad_payer`, `receipt_payer_mismatch`, `receipt_bad_pay_to`, `receipt_pay_to_mismatch`, `receipt_bad_amount`, `receipt_amount_mismatch`.
- **Settlement is not verified on-chain.** The receipt is the gateway's own assertion in a response header. The client checks that assertion against the authorization it signed, but it does not look up the `transaction` on Base or confirm that the USDC transfer happened. A paid result therefore carries `gatewayReceiptVerified: true`, `onchainReceiptVerified: false` and `settlementVerificationScope: "gateway_header_assertion"`. If you need proof, check `paymentReceipt.transaction` on Base yourself.
- Unpaid non-2xx responses (other than `402`) fail with `upstream_http_error`, which carries `status` and a snippet of at most 300 characters. Transport failures fail with `network_error` and timeouts with `timeout`. No offline challenge is ever fabricated.

### Error shape

MCP tool errors come back as `isError: true` with JSON `{ "error": "<message>", "code": "<stable code>", ...details }`.

Stable codes: `x402_disabled`, `gateway_not_configured`, `invalid_config`, `invalid_argument`, `invalid_x_payment`, `malformed_header`, `rejected_challenge`, `timeout`, `network_error`, `response_too_large`, `upstream_http_error`, `unverified_settlement`, and, for the proposals feed, `feed_unavailable` and `invalid_feed`.

## MCP registry and agent skill

- `server.json` is the manifest for the official MCP registry (`registry.modelcontextprotocol.io`, schema `2025-10-17`). The server name is `io.github.Fractal-Neurons/pacta`, and `package.json` (private, never published) carries the matching `mcpName`. It lists no npm package; the environment variables read in `src/` are all documented in this README, and the tests enforce that.
- `server.json` lists the hosted endpoint under `remotes` (`streamable-http`, `https://api.pacta.wtf/mcp`) and, like its remote-only twin `server.remote.json` (same name, version and metadata), carries no npm `packages` entry: nothing is published on npm. `io.github.Fractal-Neurons/pacta` is registered in the official MCP Registry from `server.remote.json`. The tests keep the two files in step.
- `SKILL.md` is a portable agent skill (`pacta-protocol-commitments`). It covers the free feeds, replaying a record with `cast call … --block N` and checking the block hash, these tools, and when an x402 payment is justified.

## Tests

```bash
node --test test/server.test.mjs   # == npm test; imports every other test file
```

The tests use injected `fetchImpl` only and pass with a missing or read-only `HOME` (for example `HOME=/nonexistent node --test test/server.test.mjs`). Scratch files go in a fresh `mkdtemp` directory under the first writable location among `PACTA_TEST_SCRATCH_DIR`, `XDG_CACHE_HOME`, the current directory, and `test/`. That directory is removed in a `finally` block. `src/` and `bin/` never write files or read `HOME`, and a static test enforces this. The stdio and CLI tests wait for complete JSON-RPC lines, with no fixed sleeps. A guard replaces the global `fetch` so that any real network call fails. Tests use fixed fake 65-byte signatures and no keys.

## Maintainer

Pacta is built by [Fractal Neurons](https://fractalneurons.com). Issues: <https://github.com/Fractal-Neurons/pacta/issues>. Contact: [pacta@dri.network](mailto:pacta@dri.network).

MIT
