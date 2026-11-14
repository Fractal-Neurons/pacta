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

export const SERVER_INFO = Object.freeze({ name: "@pacta/mcp-server", version: "0.1.0" });
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
]);

const BLOCK_RE = /^(latest|0x[0-9a-fA-F]{1,14}|0|[1-9][0-9]{0,15})$/;
const FREE_LAUNCH_HINT = "Free during the launch (the live gateway answers $0, no payment); x402 price applies only if metering is switched on.";

export const PAID_TOOLS = Object.freeze([
  {
    name: "pacta_check_preflight",
    description:
      "Gateway tool (requires PACTA_X402_URL; x402 $0.01 Base USDC when metered). One-call pre-execution safety check of a contract before an agent interacts with it: verdict (IMMUTABLE_NO_ADMIN / TIMELOCK_PROTECTED / MULTISIG_NO_TIMELOCK / INSTANT_EOA_ADMIN_RISK / UNCLASSIFIED_CONTRACT_CONTROLLER / UNDEPLOYED_OR_EOA), 0-100 risk score, proxy + implementation, controller kind, zero-delay upgradeability, pause / blacklist / upgrade capabilities, pinned block. " +
      FREE_LAUNCH_HINT,
    inputSchema: objSchema(
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
    name: "pacta_scan_control_plane",
    description: "Gateway tool (requires PACTA_X402_URL; x402 $0.10 Base USDC when metered): pinned-block EVM control-plane scan. " + FREE_LAUNCH_HINT,
    inputSchema: objSchema({ chain: CHAIN_PROP, address: { type: "string" }, ...PAID_AUTH_PROPS }, [
      "chain",
      "address",
    ]),
  },
  {
    name: "pacta_live_timelocks",
    description: "Gateway tool (requires PACTA_X402_URL; x402 $0.10 Base USDC when metered): live tracked DeFi TimelockController operations. " + FREE_LAUNCH_HINT,
    inputSchema: objSchema({ ...PAID_AUTH_PROPS }),
  },
  {
    name: "pacta_scan_timelock_op",
    description: "Gateway tool (requires PACTA_X402_URL; x402 $0.25 Base USDC when metered): pinned-block OZ TimelockController operation state. " + FREE_LAUNCH_HINT,
    inputSchema: objSchema(
      { chain: CHAIN_PROP, timelock: { type: "string" }, opId: { type: "string" }, ...PAID_AUTH_PROPS },
      ["timelock", "opId"]
    ),
  },
  {
    name: "pacta_scan_proposal_diff",
    description:
      "Gateway tool (requires PACTA_X402_URL; x402 $0.15 Base USDC when metered): re-run a tracked governance proposal's pinned control-plane reads live and return pinned-vs-live diffs. The proposal must be listed in https://pacta.wtf/api/v1/proposals.json as <forum>-<topicId>. " +
      FREE_LAUNCH_HINT,
    inputSchema: objSchema(
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
]);

export const TOOL_DEFINITIONS = Object.freeze([...FREE_TOOLS, ...PAID_TOOLS]);

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
    return this.x402Url ? TOOL_DEFINITIONS : FREE_TOOLS;
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

  async callTool(name, args = {}) {
    if (!args || typeof args !== "object" || Array.isArray(args)) {
      throw Object.assign(new Error("Arguments must be an object."), { code: -32602 });
    }

    switch (name) {
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
        });
      }
      if (msg.method === "ping") return rpcResult(msg.id, {});
      if (msg.method === "tools/list") return rpcResult(msg.id, { tools: this.getTools() });
      if (msg.method === "tools/call") {
        const toolName = msg.params?.name;
        if (!toolName || !TOOL_DEFINITIONS.some((t) => t.name === toolName)) {
          return rpcError(msg.id, -32602, `Unknown tool: ${toolName ?? ""}`);
        }
        try {
          const payload = await this.callTool(toolName, msg.params?.arguments ?? {});
          return rpcResult(msg.id, {
            content: [{ type: "text", text: JSON.stringify(payload, null, 2) }],
            isError: false,
          });
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
