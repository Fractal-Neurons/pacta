# `@pacta/mcp-server`

Zero-dependency Node.js MCP stdio server for [Pacta](https://pacta.wtf/) DeFi control-plane commitments and Base Mainnet EAS attestations, with live gateway tools (pre-flight check, control-plane / timelock / proposal scans) when `PACTA_X402_URL` is configured. The gateway is **free during the launch**: $0, no API key, no wallet, 60 requests / minute per caller. The x402 v1 + v2 Base USDC prices below apply only if metering is switched on.

This package is stdio-only. It never opens a listening socket, and the test suite checks that statically. It is **not published on npm yet**: run it from a clone, or use the hosted remote endpoint.

## Fastest: hosted remote MCP (zero install)

The live gateway serves the same gateway tools over Streamable HTTP at `https://pacta-x402.pacta.workers.dev/mcp`:

```bash
claude mcp add --transport http pacta https://pacta-x402.pacta.workers.dev/mcp
```

```json
{ "mcpServers": { "pacta": { "url": "https://pacta-x402.pacta.workers.dev/mcp" } } }
```

Or call the API directly: `curl -s "https://pacta-x402.pacta.workers.dev/v1/check/preflight?chain=ethereum&address=0x…"`. OpenAPI 3.1: `https://pacta-x402.pacta.workers.dev/openapi.json`.

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
      "env": { "PACTA_X402_URL": "https://pacta-x402.pacta.workers.dev" }
    }
  }
}
```

## Tools

- **Default Free Tools** (static feed `https://pacta.wtf/api/v1/index.json`, fallback `https://fractal-neurons.github.io/pacta/api/v1/index.json`, or `PACTA_INDEX_PATH` / `PACTA_SPEC_PATH`):
  - `pacta_list_commitments`: filters dual-RPC-verified DeFi control-plane records (`protocol`, `classification`, `sprint`, `limit`).
  - `pacta_list_proposals`: filters the governance proposals feed (`https://pacta.wtf/api/v1/proposals.json`, fallback `https://fractal-neurons.github.io/pacta/api/v1/proposals.json`, or `PACTA_PROPOSALS_PATH` / the `proposalsPath` option). Filters: `forum` (`aave` | `euler` | `morpho` | `sky`), `topic_id`, `chain` (`ethereum` | `base`), `limit` (1 to 100, default 25). The output is compact, and `repro_commands` are included only with `include_repro: true`. The feed must have `schema === "pacta.governance_proposals_feed.v1"` and a `proposals` array of objects. Anything else is refused with `invalid_feed`. When no source yields a valid feed, the call fails with `feed_unavailable`, which carries per-URL `attempts` (`timeout`, `network_error`, `upstream_http_error`, `response_too_large`, `invalid_feed`). A configured local path is never replaced by a network fetch.
  - `pacta_get_anchoring`: returns the Base (`8453`) `PactaCommitmentRegistry` (`0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872`), the EAS Schema (`0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83`), and `pacta.base.eth`.
  - `pacta_x402_discover`: reports `PACTA_X402_URL` status, the live gateway `x402_gateway_url` and the local-spec payment requirements (labelled `source: "local_spec"`, validated by the same rules as upstream challenges). When `PACTA_X402_URL` is set, it also fetches `/.well-known/x402` and `/v1/sample/control-plane` for information only.
- **Live gateway.** The canonical Pacta x402 edge Worker is live at `https://pacta-x402.pacta.workers.dev` (Cloudflare; free `/health`, `/.well-known/x402`, `/v1/sample/control-plane`). `pacta_get_anchoring` and `pacta_x402_discover` report it as `x402_gateway_url` even while paid tools are off. To opt in, set `PACTA_X402_URL=https://pacta-x402.pacta.workers.dev`.
- **Gateway tools, free during the launch; optional `x402` v1 + v2 Base USDC metering** (enabled only when `PACTA_X402_URL` is set; when unset, `tools/list` shows only the static-feed tools and gateway calls return `x402_disabled`). While the gateway is in free-launch mode it answers HTTP 200 with no payment header, and the tool returns that as unpaid data (`paid: false`). The prices are the metered x402 prices:
  - `pacta_check_preflight` → `/v1/check/preflight` (`$0.01` = `10000` atomic; `chain`, `address`, optional `block` = `latest` | decimal | 0x-hex). Verdict (`IMMUTABLE_NO_ADMIN` / `TIMELOCK_PROTECTED` / `MULTISIG_NO_TIMELOCK` / `INSTANT_EOA_ADMIN_RISK` / `UNCLASSIFIED_CONTRACT_CONTROLLER` / `UNDEPLOYED_OR_EOA`), 0–100 risk score, proxy + implementation, controller kind, zero-delay upgradeability, pause / blacklist / upgrade capabilities, pinned block.
  - `pacta_scan_control_plane` → `/v1/scan/control-plane` (`$0.10` = `100000` atomic; `chain`, `address`)
  - `pacta_live_timelocks` → `/v1/briefs/live-timelocks` (`$0.10` = `100000` atomic)
  - `pacta_scan_timelock_op` → `/v1/scan/timelock-op` (`$0.25` = `250000` atomic; `chain`, `timelock`, `opId`)
  - `pacta_scan_proposal_diff` → `/v1/scan/proposal-diff` (`$0.15` = `150000` atomic; `forum` = `aave` | `euler` | `morpho` | `sky`, `topicId` = the forum topic id). The proposal must be listed in `https://pacta.wtf/api/v1/proposals.json`.

  When metering is on, the live Worker answers every metered route in both protocol versions. A bare request (no query, no payment header) gets the 402 immediately.
  - **x402 v1**: the 402 JSON body (`x402Version: 1`, `network: "base"`, `maxAmountRequired`). Pay with `xPaymentHeader`, sent as `X-PAYMENT`. The receipt is `X-PAYMENT-RESPONSE`.
  - **x402 v2**: the `PAYMENT-REQUIRED` header (base64 JSON, `x402Version: 2`, `network: "eip155:8453"`, `amount`, `extensions.bazaar` with a JSON Schema 2020-12 schema). Pay with `paymentSignatureHeader`, sent as `PAYMENT-SIGNATURE`. The receipt is `PAYMENT-RESPONSE`.

  If you send no payment argument, the tool returns the upstream `402` as a validated requirements entry for the version picked by `x402Version` (default `1`), along with:
  - `availableVersions` and `alternativeAccepts` for the other valid version;
  - EIP-712 `TransferWithAuthorization` `typedData`;
  - the envelope template for that version (`xPaymentEnvelopeTemplate` for v1, `paymentSignatureEnvelopeTemplate` for v2).

  Every challenge entry, v1 or v2, passes the same pins: allowlisted `payTo`, Base USDC, the `PACTA_X402_MAX_ATOMIC` cap, the route price, the `maxTimeoutSeconds` ceiling, and binding to the requested URL. Anything else is `rejected_challenge`. Sign the typedData yourself (the server holds no keys), base64-encode the envelope, and call the tool again with `xPaymentHeader` (v1) or `paymentSignatureHeader` (v2), never both.

  A paid call succeeds only with a 2xx and a valid `PAYMENT-RESPONSE` / `X-PAYMENT-RESPONSE` receipt on that version's network, whose payer, payTo and amount match your authorization. The receipt is the facilitator's assertion and is not looked up on Base (`onchainReceiptVerified: false`).

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `PACTA_X402_URL` | unset | Base URL of the x402 gateway; the canonical live one is `https://pacta-x402.pacta.workers.dev`. If unset, paid tools are disabled. Must be `https://`; plain `http://` is allowed only for `localhost` / `127.0.0.1` / `[::1]`. URLs with embedded credentials are refused. |
| `PACTA_X402_MAX_ATOMIC` | `1000000` ($1.00) | Per-payment cap in atomic USDC (6 decimals). Values above the hard ceiling `5000000` ($5.00) are clamped to it. Invalid values fall back to the default, and `pacta_x402_discover` reports a `configWarnings` entry. |
| `PACTA_X402_TIMEOUT_MS` | `8000` | Timeout for every outbound fetch (index, proposals, discovery, paid). Valid range is 1 to 60000. |
| `PACTA_INDEX_PATH` / `PACTA_SPEC_PATH` | unset | Local index / spec files for the free tools. |
| `PACTA_PROPOSALS_PATH` | unset | Local proposals feed (`pacta.governance_proposals_feed.v1`) for `pacta_list_proposals`. |

The hard ceiling of $5.00 is 20 times the most expensive route ($0.25). No env var or option can raise it, so a mistyped or hostile environment cannot turn one tool call into a large transfer. In practice the route's own price is the binding limit, and the cap is defence in depth.

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

Stable codes: `x402_disabled`, `invalid_config`, `invalid_argument`, `invalid_x_payment`, `malformed_header`, `rejected_challenge`, `timeout`, `network_error`, `response_too_large`, `upstream_http_error`, `unverified_settlement`, and, for the proposals feed, `feed_unavailable` and `invalid_feed`.

## MCP registry and agent skill

- `server.json` is the manifest for the official MCP registry (`registry.modelcontextprotocol.io`, schema `2025-10-17`). The server name is `io.github.fractal-neurons/pacta`, and `package.json` carries the matching `mcpName`, which the registry uses for npm ownership verification. Its `environmentVariables` must list exactly the variables read in `src/`, and the tests enforce that.
- `server.json` also lists the hosted endpoint under `remotes` (`streamable-http`, `https://pacta-x402.pacta.workers.dev/mcp`). The registry checks that an npm package exists, and `@pacta/mcp-server` is not published yet, so `server.remote.json` is a remote-only twin (same name, version and metadata, no `packages`) that can be registered first. The tests keep the two files in step.
- `SKILL.md` is a portable agent skill (`pacta-protocol-commitments`). It covers the free feeds, replaying a record with `cast call … --block N` and checking the block hash, these tools, and when an x402 payment is justified.

## Tests

```bash
node --test test/server.test.mjs   # == npm test; imports every other test file
```

The tests use injected `fetchImpl` only and pass with a missing or read-only `HOME` (for example `HOME=/nonexistent node --test test/server.test.mjs`). Scratch files go in a fresh `mkdtemp` directory under the first writable location among `PACTA_TEST_SCRATCH_DIR`, `XDG_CACHE_HOME`, the current directory, and `test/`. That directory is removed in a `finally` block. `src/` and `bin/` never write files or read `HOME`, and a static test enforces this. The stdio and CLI tests wait for complete JSON-RPC lines, with no fixed sleeps. A guard replaces the global `fetch` so that any real network call fails. Tests use fixed fake 65-byte signatures and no keys.

MIT
