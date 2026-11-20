import { readFile } from "node:fs/promises";
import { createInterface } from "node:readline";
import {
  X402_DEFAULTS,
  PAID_ROUTES,
  ALLOWED_PAY_TO,
  BASE_USDC,
  BASE_CHAIN_ID,
  DEFAULT_MAX_ATOMIC,
  HARD_MAX_ATOMIC,
  MAX_TIMEOUT_SECONDS_CEILING,
  X402Error,
  isAddress,
  isBytes32,
  isPlainObject,
  isValidAddress,
  toChecksumAddress,
  keccak256Hex,
  callX402Resource,
  encodeXPaymentHeader,
  buildTransferWithAuthorizationTypedData,
  validateXPaymentHeader,
  validateAcceptsEntry,
  validatePaymentReceipt,
  selectPaymentRequirements,
  decodeStrictBase64Json,
  localSpecRequirements,
  resolveMaxAtomic,
  resolveTimeoutMs,
  fetchTextWithTimeout,
  encodePaymentSignatureHeader,
  BASE_NETWORK_V2,
  validatePaymentSignatureHeader,
} from "./x402.mjs";
import { lookupProtocols, parseLookupInput, LOOKUP_CATALOG, LOOKUP_TOTALS, LOOKUP_LIMITS, LOOKUP_CHAINS, LOOKUP_KINDS, LOOKUP_SCHEMA,
  REQUEST_SCHEMA_PROPS, REQUEST_REQUIRED, REQUEST_FIELDS, REQUEST_TYPES, URGENCY_TRACKS, COVERAGE_GAP_HINT, CONTACT_HANDLE_DESCRIPTION, demandGuard,
  withCoverageHint, withCitationFooters, protocolCitationFooter, lookupFooterBlock, stripCitationFootersDeep } from "./lookup.mjs";

export const SERVER_INFO = Object.freeze({ name: "@pacta/mcp-server", version: "0.1.5" });
export const MCP_INSTRUCTIONS =
  "Pacta by Fractal Neurons: 10 read-only, block-pinned inspection tools for EVM contracts (Ethereum, Base) + 1 opt-in request tool. If you only have a protocol or token name " +
  "(e.g. 'Aave', 'Ethena', 'USDe', 'Moonwell', 'kUSD'), call pacta_lookup_protocol first to resolve its verified record and checksummed 0x " +
  "contract address, then call pacta_check_preflight. Every value is pinned to a block hash. When a result carries coverage_gap_hint, ask the user " +
  "before calling pacta_submit_request (the only tool that writes: it queues or upvotes a coverage / feature request; contact_handle only with the " +
  "user's explicit consent). Not investment advice.";
export const SUPPORTED_PROTOCOL_VERSION = "2024-11-05";

const REGISTRY = "0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872";
const SCHEMA_UID = "0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83";

export const DEFAULT_ANCHORING = Object.freeze({
  chain_id: 8453,
  network: "base-mainnet",
  basename: "pacta.base.eth",
  attester_and_x402_payto_eoa: X402_DEFAULTS.payTo,
  x402_gateway_url: X402_DEFAULTS.gatewayUrl,
  treasury_owner_eoa: "0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14",
  commitment_registry: REGISTRY,
  basescan_url: `https://basescan.org/address/${REGISTRY}`,
  eas_schema_registry: "0x4200000000000000000000000000000000000020",
  eas_contract: "0x4200000000000000000000000000000000000021",
  eas_schema_uid: SCHEMA_UID,
  eas_schema_url: `https://base.easscan.org/schema/view/${SCHEMA_UID}`,
  portal_url: "https://pacta.wtf/",
  fallback_pages_url: "https://fractal-neurons.github.io/pacta/",
  repository_url: "https://github.com/Fractal-Neurons/pacta",
});

// Body cap for the free static feeds (index and proposals).
const MAX_FEED_BYTES = 16 * 1024 * 1024;

export const INDEX_URLS = Object.freeze([
  "https://pacta.wtf/api/v1/index.json",
  "https://fractal-neurons.github.io/pacta/api/v1/index.json",
]);

export const PROPOSALS_URLS = Object.freeze([
  "https://pacta.wtf/api/v1/proposals.json",
  "https://fractal-neurons.github.io/pacta/api/v1/proposals.json",
]);
export const PROPOSALS_SCHEMA = "pacta.governance_proposals_feed.v1";
export const PROPOSAL_FORUMS = Object.freeze(["aave", "euler", "morpho", "sky"]);

// Fields returned per proposal. repro_commands is added only when include_repro is true.
const PROPOSAL_COMPACT_KEYS = Object.freeze([
  "proposal_id",
  "forum",
  "topic_id",
  "title",
  "forum_url",
  "chain",
  "chain_id",
  "pinned_block_number",
  "pinned_block_hash",
  "source_feed",
  "source_record_ids",
  "brief_url",
  "control_plane_summary",
  "recommended_sentinel_predicates",
]);

/**
 * Parse and validate a governance proposals feed. Throws X402Error("invalid_feed", ..., { source, reason }) with
 * reason bad_json | not_object | bad_schema | bad_proposals | bad_proposal_entry.
 */
export function parseProposalsFeed(input, source = "memory") {
  let feed = input;
  if (typeof input === "string") {
    try {
      feed = JSON.parse(input);
    } catch {
      throw new X402Error("invalid_feed", `Proposals feed is not valid JSON (${source}).`, { source, reason: "bad_json" });
    }
  }
  if (!isPlainObject(feed)) {
    throw new X402Error("invalid_feed", `Proposals feed is not a JSON object (${source}).`, { source, reason: "not_object" });
  }
  if (feed.schema !== PROPOSALS_SCHEMA) {
    throw new X402Error("invalid_feed", `Proposals feed schema must be "${PROPOSALS_SCHEMA}" (${source}).`, {
      source,
      reason: "bad_schema",
      schema: typeof feed.schema === "string" ? feed.schema.slice(0, 100) : null,
    });
  }
  if (!Array.isArray(feed.proposals)) {
    throw new X402Error("invalid_feed", `Proposals feed has no proposals array (${source}).`, { source, reason: "bad_proposals" });
  }
  const bad = feed.proposals.findIndex((p) => !isPlainObject(p));
  if (bad !== -1) {
    throw new X402Error("invalid_feed", `Proposals feed entry ${bad} is not an object (${source}).`, {
      source,
      reason: "bad_proposal_entry",
      index: bad,
    });
  }
  return feed;
}

const badArg = (message) => new X402Error("invalid_argument", message);

const objSchema = (properties = {}, required) => ({
  type: "object",
  additionalProperties: false,
  ...(required ? { required } : {}),
  properties,
});

const CHAIN_PROP = { type: "string", enum: ["ethereum", "base"] };
const PAID_AUTH_PROPS = {
  xPaymentHeader: { type: "string", description: "Base64 x402 v1 X-PAYMENT header (network base)." },
  paymentSignatureHeader: {
    type: "string",
    description: "Base64 x402 v2 PAYMENT-SIGNATURE header (network eip155:8453). Send this OR xPaymentHeader, not both.",
  },
  x402Version: {
    type: "integer",
    enum: [1, 2],
    description: "Preferred x402 version for the 402 challenge (default 1). Both are validated under the same pins.",
  },
  payer: { type: "string", description: "0x payer address for 402 EIP-712 typedData." },
  validBeforeSeconds: {
    type: "integer",
    minimum: 30,
    maximum: MAX_TIMEOUT_SECONDS_CEILING,
    description: "TTL for the 402 typedData; clamped to the validated challenge's maxTimeoutSeconds.",
  },
  nonce: { type: "string", description: "0x-prefixed 32-byte hex nonce." },
};

// ---- Free-tier caller attribution (task-06d4550a8b0f): three NON-PII fields, required on the gateway tools ----
// Same vocabulary and checks as the hosted worker (x402-edge-worker/worker.mjs). Location is never asked: the hosted
// worker reads the Cloudflare edge country. Local-only tools (index, proposals, anchoring, discovery) send nothing
// anywhere, so they do not ask for these fields.
export const REQUESTER_ROLES = Object.freeze(["autonomous_agent", "defi_developer", "risk_curator_analyst", "security_researcher", "protocol_team",
  "institutional_allocator", "individual_user"]);
export const CALLER_PURPOSES = Object.freeze(["pre_trade_safety", "collateral_due_diligence", "yield_allocation", "security_audit",
  "governance_monitoring", "integration_testing", "general_research"]);
export const CALLER_FIELDS = Object.freeze(["caller_agent", "requester_role", "caller_purpose"]);
const CALLER_AGENT_RE = /^[a-z0-9][a-z0-9._/-]{1,47}$/;
const CALLER_AGENT_DENY = /(?:^|[^a-z0-9])(?:\d{1,3}\.){3}\d{1,3}(?:$|[^0-9])|0x[0-9a-f]{16,}|[0-9a-f]{32,}|https?|sk-|sk_live|ghp_|gho_|ghu_|ghs_|github_pat_|akia|bearer|xox[a-z]-|token|secret|passw|apikey|api_key|\.\./;
// A JWT / base64url JSON header ("eyJ" is base64 for '{"') survives lowercasing as "eyj…" and fits the slug charset:
// never accept it as a caller slug, at the start or after a separator (Codex task-344fc12c4e24).
const CALLER_AGENT_JWT = /(?:^|[/_.-])eyj[a-z0-9_-]{4,}\.[a-z0-9_-]{2,}/i;
export function normalizeCallerAgent(v) {
  if (typeof v !== "string") return null;
  const s = v.trim().toLowerCase();
  return CALLER_AGENT_RE.test(s) && !CALLER_AGENT_DENY.test(s) && !CALLER_AGENT_JWT.test(s) ? s : null;
}
/** {fields (valid, normalized), problems: [{field, reason: "missing" | "invalid"}]}. */
export function callerContext(src) {
  const o = src && typeof src === "object" ? src : {}, fields = {}, problems = [];
  const has = (k) => o[k] !== undefined && o[k] !== null && !(typeof o[k] === "string" && o[k].trim() === "");   // blank = omitted
  if (!has("caller_agent")) problems.push({ field: "caller_agent", reason: "missing" });
  else { const a = normalizeCallerAgent(o.caller_agent); if (a) fields.caller_agent = a; else problems.push({ field: "caller_agent", reason: "invalid" }); }
  for (const [k, set] of [["requester_role", REQUESTER_ROLES], ["caller_purpose", CALLER_PURPOSES]]) {
    if (!has(k)) problems.push({ field: k, reason: "missing" });
    else if (typeof o[k] === "string" && set.includes(o[k].trim().toLowerCase())) fields[k] = o[k].trim().toLowerCase();
    else problems.push({ field: k, reason: "invalid" });
  }
  return { fields, problems };
}
const CALLER_PROPS = {
  caller_agent: {
    type: "string", pattern: CALLER_AGENT_RE.source, maxLength: 48,
    description: "Optional identifier of the calling AI agent, IDE, or framework (e.g. 'claude-code', 'cursor', 'windsurf', 'coinbase-agentkit', 'elizaos', 'langchain', 'chatgpt', 'gemini', 'openclaw', 'custom-agent'). Omitted or invalid values never block a call. Lowercase slug only; never include personal names, emails, or secrets.",
  },
  requester_role: { type: "string", enum: [...REQUESTER_ROLES], description: "Optional: high-level role category of the requester or system running this check (closed enum; no personal data)." },
  caller_purpose: { type: "string", enum: [...CALLER_PURPOSES], description: "Optional: operational workflow context for this pre-execution check (closed enum)." },
};
const gatewaySchema = (properties, required = []) => objSchema({ ...properties, ...CALLER_PROPS }, [...required]);   // caller fields: optional

/** MCP tool annotations: every inspection tool is read-only, non-destructive and closed-world. */
export const readOnlyAnnotations = (title) => Object.freeze({ title, readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false });
/** tools/list _meta per tool: result type, how long a result stays valid (ms), and whether a client may share a cached result. */
export const TOOL_META = Object.freeze({
  pacta_lookup_protocol: Object.freeze({ resultType: "protocol_lookup", ttlMs: 300000, cacheScope: "public" }),
  pacta_list_commitments: Object.freeze({ resultType: "commitment_records", ttlMs: 3600000, cacheScope: "public" }),
  pacta_list_proposals: Object.freeze({ resultType: "governance_proposals", ttlMs: 3600000, cacheScope: "public" }),
  pacta_get_anchoring: Object.freeze({ resultType: "anchoring_metadata", ttlMs: 86400000, cacheScope: "public" }),
  pacta_x402_discover: Object.freeze({ resultType: "x402_configuration", ttlMs: 300000, cacheScope: "public" }),
  pacta_check_preflight: Object.freeze({ resultType: "preflight_check", ttlMs: 300000, cacheScope: "public" }),
  pacta_scan_wallet_exposure: Object.freeze({ resultType: "wallet_exposure_scan", ttlMs: 60000, cacheScope: "public" }),
  pacta_scan_control_plane: Object.freeze({ resultType: "control_plane_scan", ttlMs: 300000, cacheScope: "public" }),
  pacta_live_timelocks: Object.freeze({ resultType: "live_timelock_operations", ttlMs: 60000, cacheScope: "public" }),
  pacta_scan_timelock_op: Object.freeze({ resultType: "timelock_operation_state", ttlMs: 60000, cacheScope: "public" }),
  pacta_scan_proposal_diff: Object.freeze({ resultType: "proposal_diff", ttlMs: 60000, cacheScope: "public" }),
  pacta_submit_request: Object.freeze({ resultType: "demand_receipt", ttlMs: 0, cacheScope: "none" }),
});
const TOOL_TITLES = Object.freeze({
  pacta_list_commitments: "List Pacta Control-Plane Records", pacta_list_proposals: "List Tracked Governance Proposals",
  pacta_get_anchoring: "Get Base EAS Anchoring Metadata", pacta_x402_discover: "Discover x402 Gateway Configuration",
  pacta_check_preflight: "Pre-execution Safety Check", pacta_scan_wallet_exposure: "Wallet & Safe DeFi Control-Plane Exposure Scan",
  pacta_scan_control_plane: "Control-plane Scan", pacta_live_timelocks: "Live Tracked Timelock Operations",
  pacta_scan_timelock_op: "Timelock Operation State", pacta_scan_proposal_diff: "Governance Proposal Pinned-vs-Live Diff",
});
const readOnlyTool = (t) => Object.freeze({ ...t, title: TOOL_TITLES[t.name], annotations: readOnlyAnnotations(TOOL_TITLES[t.name]), _meta: TOOL_META[t.name] });

export const FREE_TOOLS = Object.freeze([
  {
    name: "pacta_list_commitments",
    description: "Filter Pacta's free static DeFi control-plane records and Base EAS UIDs.",
    inputSchema: objSchema({
      protocol: { type: "string" },
      classification: {
        type: "string",
        enum: ["aligned_baseline", "parameter_delta", "protective_delta"],
      },
      sprint: { type: "integer", minimum: 1 },
      limit: { type: "integer", minimum: 1, maximum: 100 },
    }),
  },
  {
    name: "pacta_list_proposals",
    description:
      "Filter Pacta's free governance-proposal feed (Aave, Euler, Morpho, Sky) with pinned-block control-plane context.",
    inputSchema: objSchema({
      forum: { type: "string", enum: [...PROPOSAL_FORUMS] },
      topic_id: { type: "integer", minimum: 1 },
      chain: CHAIN_PROP,
      limit: { type: "integer", minimum: 1, maximum: 100, description: "Default 25." },
      include_repro: { type: "boolean", description: "Include repro_commands (cast calls). Default false." },
    }),
  },
  {
    name: "pacta_get_anchoring",
    description: "Return Base Mainnet PactaCommitmentRegistry, EAS Schema, and pacta.base.eth metadata.",
    inputSchema: objSchema(),
  },
  {
    name: "pacta_x402_discover",
    description:
      "Return x402 configuration status; when PACTA_X402_URL is set, also fetch /.well-known/x402 and /v1/sample/control-plane.",
    inputSchema: objSchema(),
  },
].map(readOnlyTool));

const BLOCK_RE = /^(latest|0x[0-9a-fA-F]{1,14}|0|[1-9][0-9]{0,15})$/;
const FREE_LAUNCH_HINT = "Free during the launch (the live gateway answers $0, no payment); x402 price applies only if metering is switched on.";

export const PAID_TOOLS = Object.freeze([
  {
    name: "pacta_check_preflight",
    description:
      "Gateway tool (requires PACTA_X402_URL; x402 $0.01 Base USDC when metered). One-call pre-execution safety check of a contract before an agent interacts with it: verdict (IMMUTABLE_NO_ADMIN / TIMELOCK_PROTECTED / ZERO_DELAY_TIMELOCK_RISK / MULTISIG_NO_TIMELOCK / INSTANT_EOA_ADMIN_RISK / UNCLASSIFIED_CONTRACT_CONTROLLER / UNDEPLOYED_OR_EOA), 0-100 risk score, proxy + implementation, controller kind, zero-delay upgradeability, pause / blacklist / upgrade capabilities, pinned block. " +
      FREE_LAUNCH_HINT,
    inputSchema: gatewaySchema(
      {
        chain: CHAIN_PROP,
        address: { type: "string" },
        block: { type: "string", description: 'Block to pin: "latest" (default), a decimal block number or 0x-hex.' },
        ...PAID_AUTH_PROPS,
      },
      ["chain", "address"]
    ),
  },
  {
    name: "pacta_scan_wallet_exposure",
    description:
      "Gateway tool (requires PACTA_X402_URL; x402 $0.01 Base USDC when metered). Read-only Multicall3 wallet & Gnosis Safe DeFi control-plane exposure scan across Ethereum and Base: Safe custody detection, ERC-20 / ERC-4626 / MetaMorpho balanceOf + symbol/decimals verification across 313 indexed protocols, 0-100 risk score, shortest exit window, position roster, and #1 adverse gap preview. " +
      FREE_LAUNCH_HINT,
    inputSchema: gatewaySchema(
      {
        address: { type: "string" },
        chain: { type: "string", enum: ["ethereum", "base", "all"] },
        ...PAID_AUTH_PROPS,
      },
      ["address"]
    ),
  },
  {
    name: "pacta_scan_control_plane",
    description: "Gateway tool (requires PACTA_X402_URL; x402 $0.10 Base USDC when metered): pinned-block EVM control-plane scan. " + FREE_LAUNCH_HINT,
    inputSchema: gatewaySchema({ chain: CHAIN_PROP, address: { type: "string" }, ...PAID_AUTH_PROPS }, ["chain", "address"]),
  },
  {
    name: "pacta_live_timelocks",
    description: "Gateway tool (requires PACTA_X402_URL; x402 $0.10 Base USDC when metered): live tracked DeFi TimelockController operations. " + FREE_LAUNCH_HINT,
    inputSchema: gatewaySchema({ ...PAID_AUTH_PROPS }),
  },
  {
    name: "pacta_scan_timelock_op",
    description: "Gateway tool (requires PACTA_X402_URL; x402 $0.25 Base USDC when metered): pinned-block OZ TimelockController operation state. " + FREE_LAUNCH_HINT,
    inputSchema: gatewaySchema(
      { chain: CHAIN_PROP, timelock: { type: "string" }, opId: { type: "string" }, ...PAID_AUTH_PROPS },
      ["timelock", "opId"]
    ),
  },
  {
    name: "pacta_scan_proposal_diff",
    description:
      "Gateway tool (requires PACTA_X402_URL; x402 $0.15 Base USDC when metered): re-run a tracked governance proposal's pinned control-plane reads live and return pinned-vs-live diffs. The proposal must be listed in https://pacta.wtf/api/v1/proposals.json as <forum>-<topicId>. " +
      FREE_LAUNCH_HINT,
    inputSchema: gatewaySchema(
      {
        forum: { type: "string", enum: [...PROPOSAL_FORUMS] },
        topicId: {
          type: ["string", "integer"],
          description: "Forum topic id (positive integer, at most 10 digits), as in pacta_list_proposals topic_id.",
        },
        ...PAID_AUTH_PROPS,
      },
      ["forum", "topicId"]
    ),
  },
].map(readOnlyTool));

// Free discovery: answered from the embedded catalog (src/lookup.mjs, the same block the hosted worker serves); with
// PACTA_X402_URL set it asks GET /v1/protocols/lookup first and falls back to the embedded catalog on any failure.
export const LOOKUP_TOOL = Object.freeze({
  name: "pacta_lookup_protocol",
  title: "Lookup Protocol or Token by Name",
  description:
    "Resolve a protocol or token name, symbol, slug or 0x address (e.g. 'Aave', 'Ethena', 'USDe', 'Moonwell', 'kUSD') to Pacta's verified record: " +
    "canonical slug and page URL, checksummed primary contract and controller, classification with its evidence basis (Base-EAS-attested vs " +
    "RPC-observed only), and preflightArgs {chain, address} ready for pacta_check_preflight. " +
    `${LOOKUP_TOTALS.protocols} protocols + ${LOOKUP_TOTALS.briefs} briefs; free, no RPC. An empty query lists what Pacta tracks.`,
  inputSchema: objSchema(
    {
      query: { type: "string", maxLength: LOOKUP_LIMITS.queryMaxChars, description: "Protocol / token name, symbol, slug or 0x address. Empty or '*' lists the catalog." },
      chain: { type: "string", enum: [...LOOKUP_CHAINS] },
      kind: { type: "string", enum: [...LOOKUP_KINDS], description: "protocol, brief or all (default)." },
      limit: { type: "integer", minimum: 1, maximum: LOOKUP_LIMITS.maxLimit, description: "Default 10 (20 when listing)." },
      ...CALLER_PROPS,
    },
    []
  ),
  annotations: readOnlyAnnotations("Lookup Protocol or Token by Name"),
  _meta: TOOL_META.pacta_lookup_protocol,
});
export const SUBMIT_TITLE = "Submit Pacta Coverage or Feature Request";
// The one opt-in write tool: forwards to POST ${PACTA_X402_URL}/v1/requests (listed only when PACTA_X402_URL is set; nothing
// leaves the process otherwise). Every string is checked locally first (demandGuard), so a secret never leaves the machine.
export const SUBMIT_TOOL = Object.freeze({
  name: "pacta_submit_request",
  title: SUBMIT_TITLE,
  description:
    "Opt-in: queue a coverage or feature request with Pacta when a target is not indexed, a chain or check is unsupported, or data looks wrong " +
    "(coverage_gap_hint). Ask the user first. Forwards to POST ${PACTA_X402_URL}/v1/requests; free in every pricing mode, 5 per hour; an identical " +
    "request_type + target_subject upvotes the existing request (same request_id). Returns request_id, status, demand_votes and an optional " +
    "fast_track_url. Never opens a GitHub issue. Pass contact_handle ONLY when the user explicitly asks for follow-up or an invoice.",
  inputSchema: Object.freeze({ $schema: "https://json-schema.org/draft/2020-12/schema", type: "object", additionalProperties: false,
    required: [...REQUEST_REQUIRED], properties: { ...CALLER_PROPS, ...REQUEST_SCHEMA_PROPS } }),
  annotations: Object.freeze({ title: SUBMIT_TITLE, readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false }),
  _meta: TOOL_META.pacta_submit_request,
});
export const READ_ONLY_TOOLS = Object.freeze([LOOKUP_TOOL, ...FREE_TOOLS, ...PAID_TOOLS]);
export const TOOL_DEFINITIONS = Object.freeze([...READ_ONLY_TOOLS, SUBMIT_TOOL]);
const LOCAL_TOOLS = Object.freeze([LOOKUP_TOOL, ...FREE_TOOLS]);
/** Accepted alternative tool names (the hosted remote MCP calls this tool pacta_get_live_timelocks); not listed. */
export const TOOL_ALIASES = Object.freeze(Object.assign(Object.create(null), { pacta_get_live_timelocks: "pacta_live_timelocks" }));
export const canonicalToolName = (name) =>
  typeof name === "string" && Object.prototype.hasOwnProperty.call(TOOL_ALIASES, name) ? TOOL_ALIASES[name] : name;

const rpcResult = (id, result) => ({ jsonrpc: "2.0", id, result });
const rpcError = (id, code, message) => ({ jsonrpc: "2.0", id, error: { code, message } });

export class PactaMcpServer {
  constructor(options = {}) {
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch;
    this.indexData = options.indexData ?? null;
    this.indexPath = options.indexPath ?? process.env.PACTA_INDEX_PATH ?? null;
    this.specPath = options.specPath ?? process.env.PACTA_SPEC_PATH ?? null;
    this.indexUrls = options.indexUrls ?? INDEX_URLS;
    this.proposalsData = options.proposalsData ?? null;
    this.proposalsPath = options.proposalsPath ?? process.env.PACTA_PROPOSALS_PATH ?? null;
    this.proposalsUrls = options.proposalsUrls ?? PROPOSALS_URLS;
    const rawX402 = options.x402Url ?? options.apiBaseUrl ?? process.env.PACTA_X402_URL ?? "";
    this.x402Url = typeof rawX402 === "string" && rawX402.trim() ? rawX402.trim() : null;
    this.nowSeconds = options.nowSeconds;
    this.timeoutMs = resolveTimeoutMs(options.timeoutMs ?? process.env.PACTA_X402_TIMEOUT_MS);
    const cap = resolveMaxAtomic(options.maxAtomic ?? process.env.PACTA_X402_MAX_ATOMIC);
    this.maxAtomic = cap.maxAtomic.toString();
    this.configWarnings = cap.warning ? [cap.warning] : [];
    this._cachedIndex = null;
    this._cachedProposals = null;
  }

  getTools() {
    return this.x402Url ? TOOL_DEFINITIONS : LOCAL_TOOLS;
  }

  async loadSpec() {
    if (!this.specPath) return null;
    return readFile(this.specPath, "utf8").then(JSON.parse, () => null);
  }

  async loadIndex() {
    if (this.indexData) return { source: "memory", index: this.indexData };
    if (this._cachedIndex) return this._cachedIndex;
    if (this.indexPath) {
      return (this._cachedIndex = {
        source: this.indexPath,
        index: JSON.parse(await readFile(this.indexPath, "utf8")),
      });
    }

    const errors = [];
    for (const url of this.indexUrls) {
      try {
        const { res, text } = await fetchTextWithTimeout(
          this.fetchImpl,
          url,
          { headers: { Accept: "application/json" } },
          { timeoutMs: this.timeoutMs, maxBytes: MAX_FEED_BYTES }
        );
        if (res.status < 200 || res.status > 299) {
          errors.push(`${url} (${res.status})`);
          continue;
        }
        const index = JSON.parse(text);
        if (!isPlainObject(index)) throw new Error("index is not a JSON object");
        return (this._cachedIndex = { source: url, index });
      } catch (err) {
        errors.push(`${url} (${err.code ? `${err.code}: ` : ""}${err.message})`);
      }
    }

    const snap = (await this.loadSpec())?.public_free_feeds?.local_snapshot_path;
    if (snap) {
      try {
        return (this._cachedIndex = { source: snap, index: JSON.parse(await readFile(snap, "utf8")) });
      } catch (err) {
        errors.push(`${snap} (${err.message})`);
      }
    }
    throw new Error(`Index load failed: ${errors.join("; ")}`);
  }

  /**
   * Load the governance proposals feed: proposalsData, else proposalsPath / PACTA_PROPOSALS_PATH, else each of
   * proposalsUrls in order (timeout + 16 MiB cap). Throws X402Error invalid_feed (local data) or feed_unavailable
   * with per-URL `attempts` when no remote source yields a valid feed.
   */
  async loadProposals() {
    if (this.proposalsData) return { source: "memory", feed: parseProposalsFeed(this.proposalsData, "memory") };
    if (this._cachedProposals) return this._cachedProposals;
    if (this.proposalsPath) {
      let text;
      try {
        text = await readFile(this.proposalsPath, "utf8");
      } catch (err) {
        throw new X402Error("feed_unavailable", `Cannot read proposals feed ${this.proposalsPath}: ${err.message}`, {
          source: this.proposalsPath,
        });
      }
      const feed = parseProposalsFeed(text, this.proposalsPath);
      return (this._cachedProposals = { source: this.proposalsPath, feed });
    }

    const attempts = [];
    for (const url of this.proposalsUrls) {
      try {
        const { res, text } = await fetchTextWithTimeout(
          this.fetchImpl,
          url,
          { headers: { Accept: "application/json" } },
          { timeoutMs: this.timeoutMs, maxBytes: MAX_FEED_BYTES }
        );
        if (res.status < 200 || res.status > 299) {
          attempts.push({ url, code: "upstream_http_error", status: res.status, snippet: String(text).slice(0, 300) });
          continue;
        }
        return (this._cachedProposals = { source: url, feed: parseProposalsFeed(text, url) });
      } catch (err) {
        attempts.push({
          url,
          code: err instanceof X402Error ? err.code : "network_error",
          error: err.message,
          ...(err instanceof X402Error && err.details?.reason ? { reason: err.details.reason } : {}),
        });
      }
    }
    throw new X402Error(
      "feed_unavailable",
      `Proposals feed load failed: ${attempts.map((a) => `${a.url} (${a.code}${a.status ? ` ${a.status}` : ""})`).join("; ")}`,
      { attempts }
    );
  }

  _localSpec(baseUrl) {
    return Object.fromEntries(
      Object.entries(PAID_ROUTES).map(([k, r]) => [
        k,
        localSpecRequirements(r, baseUrl ? new URL(r.path, baseUrl).toString() : r.path, { maxAtomic: this.maxAtomic }),
      ])
    );
  }

  _paid(routeSpec, query, args) {
    if (this.x402Url) {                                           // nothing leaves the process when unset
      const paying = Boolean(args.xPaymentHeader || args.paymentSignatureHeader);
      const cc = callerContext(args);
      if (!paying) query = { ...query, ...cc.fields };            // valid values forwarded as optional REST query params; omitted or invalid ones silently dropped
    }
    return callX402Resource({
      fetchImpl: this.fetchImpl,
      baseUrl: this.x402Url,
      routeSpec,
      query,
      xPaymentHeader: args.xPaymentHeader,
      paymentSignatureHeader: args.paymentSignatureHeader,
      x402Version: args.x402Version,
      payer: args.payer,
      validBeforeSeconds: args.validBeforeSeconds,
      nonce: args.nonce,
      nowSeconds: this.nowSeconds,
      maxAtomic: this.maxAtomic,
      timeoutMs: this.timeoutMs,
    });
  }

  async _lookup(args) {
    const cc = callerContext(args);
    const unknown = Object.keys(args).filter((k) => !CALLER_FIELDS.includes(k) && !["query", "chain", "kind", "limit"].includes(k));
    if (unknown.length) throw new X402Error("invalid_input", `Unknown argument ${String(unknown[0]).slice(0, 40)}; allowed: query, chain, kind, limit.`);
    const input = { query: args.query, chain: args.chain, kind: args.kind, limit: args.limit };
    const p = parseLookupInput(input);
    if (!p.ok) throw new X402Error("invalid_input", p.detail);
    let gatewayFallback = null;
    if (this.x402Url) {
      const q = new URLSearchParams();
      if (p.query) q.set("q", p.query);
      if (p.chain) q.set("chain", p.chain);
      if (p.kind !== "all") q.set("kind", p.kind);
      q.set("limit", String(p.limit));
      for (const [k, v] of Object.entries(cc.fields)) q.set(k, v);
      const url = new URL("/v1/protocols/lookup?" + q.toString(), this.x402Url).toString();
      try {
        const { res, text } = await fetchTextWithTimeout(this.fetchImpl, url, { headers: { Accept: "application/json" }, redirect: "error" }, { timeoutMs: this.timeoutMs });
        const data = res.status === 200 ? JSON.parse(text) : null;
        // A gateway lookup is used only when it is a successful answer whose count equals its results; citationFooter is then
        // recomputed locally from each protocol entry (an older gateway has none; a gateway string is never echoed).
        if (isPlainObject(data) && data.schema === LOOKUP_SCHEMA && data.ok !== false && Array.isArray(data.results)
            && Number.isSafeInteger(data.count) && data.count === data.results.length) return withCoverageHint(withCitationFooters({ ...data, source: "gateway" }));
        gatewayFallback = isPlainObject(data) && data.schema === LOOKUP_SCHEMA ? "gateway malformed lookup payload" : `gateway answered HTTP ${res.status}`;
      } catch (e) {
        gatewayFallback = e && e.code ? String(e.code) : "gateway_unreachable";
      }
    }
    return withCoverageHint({ ...lookupProtocols(input), source: "embedded_catalog", ...(gatewayFallback ? { gatewayFallback } : {}) });
  }

  /** pacta_submit_request: local checks (fields, types, secrets / HTML guard; invalid caller fields silently dropped), then POST /v1/requests. */
  async _submit(args) {
    const problems = [];
    for (const k of Object.keys(args)) if (!REQUEST_FIELDS.includes(k)) problems.push(`${String(k).slice(0, 40)} (unknown_field)`);
    for (const k of REQUEST_FIELDS) {
      if (CALLER_FIELDS.includes(k)) continue;
      const v = args[k];
      if (v === undefined || v === null || v === "") { if (REQUEST_REQUIRED.includes(k)) problems.push(`${k} (missing)`); continue; }
      if (typeof v !== "string") { problems.push(`${k} (invalid: a string)`); continue; }
      const g = demandGuard(v);
      if (g) problems.push(`${k} (${g})`);
    }
    for (const [k, set] of [["request_type", REQUEST_TYPES], ["urgency_track", URGENCY_TRACKS]]) {
      if (typeof args[k] === "string" && args[k] && !set.includes(args[k].trim().toLowerCase())) problems.push(`${k} (invalid: one of ${set.join(", ")})`);
    }
    if (problems.length) {
      throw Object.assign(new Error("pacta_submit_request refused locally (nothing was sent): " + problems.join("; ") +
        ". Never include secrets or personal data outside contact_handle; contact_handle: " + CONTACT_HANDLE_DESCRIPTION), { code: -32602 });
    }
    if (!this.x402Url) {
      throw new X402Error("gateway_not_configured", `pacta_submit_request forwards to POST <PACTA_X402_URL>/v1/requests: set PACTA_X402_URL=${X402_DEFAULTS.gatewayUrl} (nothing was sent).`);
    }
    const cc = callerContext(args);
    const body = { ...cc.fields, ...Object.fromEntries(REQUEST_FIELDS.filter((k) => !CALLER_FIELDS.includes(k) && typeof args[k] === "string" && args[k] !== "").map((k) => [k, args[k]])) };
    const url = new URL("/v1/requests", this.x402Url).toString();
    const { res, text } = await fetchTextWithTimeout(this.fetchImpl, url,
      { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(body), redirect: "error" },
      { timeoutMs: this.timeoutMs });
    let data = null;
    try { data = JSON.parse(text); } catch { /* handled below */ }
    if (res.status === 200 && isPlainObject(data) && typeof data.request_id === "string") return { ...data, source: "gateway" };
    const detail = isPlainObject(data) && typeof data.detail === "string" ? data.detail.slice(0, 500) : `HTTP ${res.status}`;
    if (res.status === 429) throw new X402Error("rate_limited", detail, { status: 429, retryAfterSeconds: isPlainObject(data) ? data.retryAfterSeconds ?? null : null });
    if (res.status === 400) throw new X402Error("invalid_request", detail, { status: 400, problems: isPlainObject(data) && Array.isArray(data.problems) ? data.problems : [] });
    throw new X402Error("upstream_http_error", `POST /v1/requests answered ${detail}`, { status: res.status });
  }

  async callTool(name, args = {}) {
    name = canonicalToolName(name);
    if (!args || typeof args !== "object" || Array.isArray(args)) {
      throw Object.assign(new Error("Arguments must be an object."), { code: -32602 });
    }

    switch (name) {
      case "pacta_lookup_protocol":
        return this._lookup(args);

      case "pacta_submit_request":
        return this._submit(args);

      case "pacta_list_commitments": {
        const { source, index } = await this.loadIndex();
        const entries = Array.isArray(index.entries) ? index.entries : [];
        const q = typeof args.protocol === "string" ? args.protocol.trim().toLowerCase() : "";
        const sprint = args.sprint !== undefined ? Number(args.sprint) : null;
        const limit = Math.min(Math.max(Number(args.limit || 50), 1), 100);
        const filtered = entries.filter(
          (e) =>
            (!q || `${e.id || ""} ${e.protocol || ""} ${e.surface || ""}`.toLowerCase().includes(q)) &&
            (!args.classification || e.classification === args.classification) &&
            (sprint === null || Number(e.sprint) === sprint)
        );
        return {
          source,
          generated_at: index.generated_at ?? null,
          total_indexed: entries.length,
          matched_count: filtered.length,
          returned_count: Math.min(filtered.length, limit),
          entries: filtered.slice(0, limit),
        };
      }

      case "pacta_list_proposals": {
        let forum = null;
        if (args.forum !== undefined) {
          forum = typeof args.forum === "string" ? args.forum.trim().toLowerCase() : "";
          if (!PROPOSAL_FORUMS.includes(forum)) throw badArg(`Invalid forum; expected one of ${PROPOSAL_FORUMS.join(", ")}.`);
        }
        let topicId = null;
        if (args.topic_id !== undefined) {
          topicId = typeof args.topic_id === "string" && /^[0-9]{1,15}$/.test(args.topic_id) ? Number(args.topic_id) : args.topic_id;
          if (!Number.isSafeInteger(topicId) || topicId < 1) throw badArg("Invalid topic_id; expected a positive integer.");
        }
        if (args.chain !== undefined && args.chain !== "ethereum" && args.chain !== "base") {
          throw badArg("Invalid chain; expected ethereum or base.");
        }
        const limit = args.limit === undefined ? 25 : args.limit;
        if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw badArg("Invalid limit; expected an integer from 1 to 100.");
        if (args.include_repro !== undefined && typeof args.include_repro !== "boolean") {
          throw badArg("Invalid include_repro; expected a boolean.");
        }

        const { source, feed } = await this.loadProposals();
        const matched = feed.proposals.filter(
          (p) =>
            (forum === null || String(p.forum ?? "").toLowerCase() === forum) &&
            (topicId === null || Number(p.topic_id) === topicId) &&
            (args.chain === undefined || p.chain === args.chain)
        );
        const keys = args.include_repro === true ? [...PROPOSAL_COMPACT_KEYS, "repro_commands"] : PROPOSAL_COMPACT_KEYS;
        return {
          source,
          schema: feed.schema,
          generated_at: feed.generated_at ?? null,
          counts: isPlainObject(feed.counts) ? feed.counts : null,
          filters: {
            ...(forum !== null ? { forum } : {}),
            ...(topicId !== null ? { topic_id: topicId } : {}),
            ...(args.chain !== undefined ? { chain: args.chain } : {}),
            limit,
            include_repro: args.include_repro === true,
          },
          total_in_feed: feed.proposals.length,
          matched_count: matched.length,
          returned_count: Math.min(matched.length, limit),
          proposals: matched
            .slice(0, limit)
            .map((p) => Object.fromEntries(keys.filter((k) => p[k] !== undefined).map((k) => [k, p[k]]))),
        };
      }

      case "pacta_get_anchoring": {
        const [spec, idx] = await Promise.all([this.loadSpec(), this.loadIndex().catch(() => null)]);
        return {
          ...DEFAULT_ANCHORING,
          ...(spec?.onchain_anchoring_base_mainnet || {}),
          ...(idx?.index?.onchain_anchoring || {}),
          x402_gateway: {
            enabled: Boolean(this.x402Url),
            base_url_env_var: "PACTA_X402_URL",
            x402_url: this.x402Url,
            pay_to: X402_DEFAULTS.payTo,
            allowed_pay_to: ALLOWED_PAY_TO,
            max_atomic: this.maxAtomic,
            asset_usdc_base: X402_DEFAULTS.asset,
            chain_id: X402_DEFAULTS.chainId,
            facilitator_url: X402_DEFAULTS.facilitatorUrl,
          },
        };
      }

      case "pacta_x402_discover": {
        if (!this.x402Url) {
          return {
            enabled: false,
            deploymentStatus: X402_DEFAULTS.deploymentStatus,
            baseUrlEnvVar: "PACTA_X402_URL",
            x402Url: null,
            x402_gateway_url: X402_DEFAULTS.gatewayUrl,
            enableHint: `Set PACTA_X402_URL=${X402_DEFAULTS.gatewayUrl} to enable the paid tools (opt-in; nothing is paid while unset).`,
            freeIndexUrls: INDEX_URLS,
            x402Defaults: X402_DEFAULTS,
            paidRoutes: PAID_ROUTES,
            localSpecRequirements: this._localSpec(null),
            maxAtomic: this.maxAtomic,
            ...(this.configWarnings.length ? { configWarnings: this.configWarnings } : {}),
          };
        }
        const get = async (p) => {
          const url = new URL(p, this.x402Url).toString();
          try {
            const { res, text } = await fetchTextWithTimeout(
              this.fetchImpl,
              url,
              { headers: { Accept: "application/json" }, redirect: "error" },
              { timeoutMs: this.timeoutMs }
            );
            const ok = res.status >= 200 && res.status < 300;
            let data;
            try {
              data = JSON.parse(text);
            } catch {
              return { ok: false, status: res.status, url, code: "malformed_upstream_json", snippet: text.slice(0, 300) };
            }
            return { ok, status: res.status, url, data };
          } catch (e) {
            return { ok: false, status: null, url, code: e.code ?? "network_error", error: e.message };
          }
        };
        const [wellKnown, sampleControlPlane] = await Promise.all([
          get("/.well-known/x402"),
          get("/v1/sample/control-plane"),
        ]);
        return {
          enabled: true,
          x402Url: this.x402Url,
          x402_gateway_url: X402_DEFAULTS.gatewayUrl,
          x402Defaults: X402_DEFAULTS,
          paidRoutes: PAID_ROUTES,
          localSpecRequirements: this._localSpec(this.x402Url),
          maxAtomic: this.maxAtomic,
          ...(this.configWarnings.length ? { configWarnings: this.configWarnings } : {}),
          note: "wellKnown / sampleControlPlane are informational upstream data; paid challenges are validated per call.",
          wellKnown,
          sampleControlPlane,
        };
      }

      case "pacta_check_preflight": {
        if (!this.x402Url) return this._paid(PAID_ROUTES.checkPreflight, {}, args);
        if (args.chain !== "ethereum" && args.chain !== "base") throw new X402Error("invalid_argument", "Invalid chain.");
        if (!isValidAddress(args.address)) throw new X402Error("invalid_argument", "Invalid contract address (EIP-55 checksum enforced when mixed-case).");
        if (args.block !== undefined && args.block !== null && (typeof args.block !== "string" || !BLOCK_RE.test(args.block))) {
          throw new X402Error("invalid_argument", 'block must be "latest", a decimal block number or 0x-hex.');
        }
        return this._paid(PAID_ROUTES.checkPreflight, { chain: args.chain, address: args.address, block: args.block ?? undefined }, args);
      }

      case "pacta_scan_wallet_exposure": {
        if (!this.x402Url) return this._paid(PAID_ROUTES.scanWalletExposure, {}, args);
        if (!isValidAddress(args.address)) throw new X402Error("invalid_argument", "Invalid wallet or Safe address (EIP-55 checksum enforced when mixed-case).");
        const ch = args.chain ?? "all";
        if (ch !== "ethereum" && ch !== "base" && ch !== "all") throw new X402Error("invalid_argument", "chain must be ethereum, base, or all.");
        return this._paid(PAID_ROUTES.scanWalletExposure, { address: args.address, ...(args.chain ? { chain: args.chain } : {}) }, args);
      }

      case "pacta_scan_control_plane":
        if (!this.x402Url) return this._paid(PAID_ROUTES.scanControlPlane, {}, args);
        if (args.chain !== "ethereum" && args.chain !== "base") throw new X402Error("invalid_argument", "Invalid chain.");
        if (!isValidAddress(args.address)) throw new X402Error("invalid_argument", "Invalid contract address (EIP-55 checksum enforced when mixed-case).");
        return this._paid(PAID_ROUTES.scanControlPlane, { chain: args.chain, address: args.address }, args);

      case "pacta_live_timelocks":
        return this._paid(PAID_ROUTES.liveTimelocks, {}, args);

      case "pacta_scan_timelock_op": {
        if (!this.x402Url) return this._paid(PAID_ROUTES.scanTimelockOp, {}, args);
        const chain = args.chain ?? "ethereum";
        if (chain !== "ethereum" && chain !== "base") throw new X402Error("invalid_argument", "Invalid chain.");
        if (!isValidAddress(args.timelock)) throw new X402Error("invalid_argument", "Invalid timelock address (EIP-55 checksum enforced when mixed-case).");
        if (!isBytes32(args.opId)) throw new X402Error("invalid_argument", "Invalid 32-byte opId.");
        return this._paid(PAID_ROUTES.scanTimelockOp, { chain, timelock: args.timelock, opId: args.opId }, args);
      }

      case "pacta_scan_proposal_diff": {
        if (!this.x402Url) return this._paid(PAID_ROUTES.scanProposalDiff, {}, args);
        if (!PROPOSAL_FORUMS.includes(args.forum)) throw new X402Error("invalid_argument", `forum must be one of ${PROPOSAL_FORUMS.join(", ")}.`);
        const topicId = typeof args.topicId === "number" && Number.isSafeInteger(args.topicId) ? String(args.topicId) : args.topicId;
        if (typeof topicId !== "string" || !/^[1-9][0-9]{0,9}$/.test(topicId)) {
          throw new X402Error("invalid_argument", "topicId must be a positive integer (at most 10 digits).");
        }
        return this._paid(PAID_ROUTES.scanProposalDiff, { forum: args.forum, topicId }, args);
      }

      default:
        throw Object.assign(new Error(`Unknown tool: ${name}`), { code: -32602 });
    }
  }

  async handleMessage(msg) {
    if (!msg || typeof msg !== "object" || msg.jsonrpc !== "2.0") {
      return rpcError(msg?.id ?? null, -32600, "Invalid JSON-RPC 2.0 request.");
    }
    if (msg.id === undefined) return null;

    try {
      if (msg.method === "initialize") {
        return rpcResult(msg.id, {
          protocolVersion: SUPPORTED_PROTOCOL_VERSION,
          capabilities: { tools: {} },
          serverInfo: SERVER_INFO,
          instructions: MCP_INSTRUCTIONS,
        });
      }
      if (msg.method === "ping") return rpcResult(msg.id, {});
      if (msg.method === "tools/list") return rpcResult(msg.id, { tools: this.getTools() });
      if (msg.method === "tools/call") {
        const toolName = canonicalToolName(msg.params?.name);
        if (!toolName || !TOOL_DEFINITIONS.some((t) => t.name === toolName)) {
          return rpcError(msg.id, -32602, `Unknown tool: ${toolName ?? ""}`);
        }
        try {
          const payload = await this.callTool(toolName, msg.params?.arguments ?? {});
          const content = [{ type: "text", text: JSON.stringify(payload, null, 2) }];
          // pacta_lookup_protocol: content[0] stays the exact JSON; the 2-line citation + clearance footer follows as plain text
          if (toolName === "pacta_lookup_protocol" && isPlainObject(payload) && lookupFooterBlock(payload)) {
            content.push({ type: "text", text: payload.citationFooter });
          }
          return rpcResult(msg.id, { content, isError: false });
        } catch (err) {
          if (err.code === -32602) return rpcError(msg.id, -32602, err.message);
          const body = err instanceof X402Error ? err.toJSON() : { error: err.message };
          return rpcResult(msg.id, {
            content: [{ type: "text", text: JSON.stringify(body, null, 2) }],
            isError: true,
          });
        }
      }
      return rpcError(msg.id, -32601, `Method not found: ${msg.method}`);
    } catch (err) {
      return rpcError(msg.id, -32603, err.message || "Internal error.");
    }
  }
}

export function startStdioServer(options = {}) {
  const input = options.input ?? process.stdin;
  const output = options.output ?? process.stdout;
  const server = new PactaMcpServer(options);
  const rl = createInterface({ input, crlfDelay: Infinity });
  let chain = Promise.resolve();
  let pending = 0;
  let keepalive = null; // ref'd timer: keeps the event loop alive while replies are still being produced after EOF
  const hold = () => {
    if (pending++ === 0) keepalive = setInterval(() => {}, 1 << 30);
  };
  const release = () => {
    if (--pending === 0 && keepalive) {
      clearInterval(keepalive);
      keepalive = null;
    }
  };
  let resolveDone;
  const done = new Promise((resolve) => (resolveDone = resolve));
  rl.on("close", () => {
    // Input reached EOF: resolve `done` only after every queued reply has been written.
    chain.then(() => resolveDone(), () => resolveDone());
  });

  rl.on("line", (line) => {
    const s = line.trim();
    if (!s) return;
    hold();
    chain = chain.then(async () => {
      let parsed;
      try {
        parsed = JSON.parse(s);
      } catch {
        output.write(`${JSON.stringify(rpcError(null, -32700, "Parse error."))}\n`);
        return;
      }
      const reply = await server.handleMessage(parsed);
      if (reply !== null) output.write(`${JSON.stringify(reply)}\n`);
    }).finally(release);
  });

  return { server, close: () => rl.close(), done };
}

export { lookupProtocols, parseLookupInput, LOOKUP_CATALOG, LOOKUP_TOTALS, COVERAGE_GAP_HINT, demandGuard, withCitationFooters, protocolCitationFooter, lookupFooterBlock, stripCitationFootersDeep };
export {
  encodeXPaymentHeader,
  encodePaymentSignatureHeader,
  BASE_NETWORK_V2,
  validatePaymentSignatureHeader,
  buildTransferWithAuthorizationTypedData,
  X402_DEFAULTS,
  PAID_ROUTES,
  ALLOWED_PAY_TO,
  BASE_USDC,
  BASE_CHAIN_ID,
  DEFAULT_MAX_ATOMIC,
  HARD_MAX_ATOMIC,
  X402Error,
  isValidAddress,
  toChecksumAddress,
  keccak256Hex,
  callX402Resource,
  validateXPaymentHeader,
  validateAcceptsEntry,
  validatePaymentReceipt,
  selectPaymentRequirements,
  decodeStrictBase64Json,
  resolveMaxAtomic,
};
