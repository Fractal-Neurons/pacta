import type { Readable, Writable } from "node:stream";

export interface Eip712Domain {
  name: string;
  version: string;
  chainId: number;
  verifyingContract: string;
}

export interface TransferWithAuthorizationMessage {
  from: string;
  to: string;
  value: string;
  validAfter: string;
  validBefore: string;
  nonce: string;
}

export interface TransferWithAuthorizationTypedData {
  domain: Eip712Domain;
  primaryType: "TransferWithAuthorization";
  types: Record<string, Array<{ name: string; type: string }>>;
  message: TransferWithAuthorizationMessage;
}

export interface PactaServerOptions {
  fetchImpl?: typeof fetch;
  indexData?: Record<string, unknown>;
  indexPath?: string;
  specPath?: string;
  indexUrls?: readonly string[];
  /** In-memory proposals feed (validated like a fetched one). */
  proposalsData?: Record<string, unknown>;
  /** Local proposals feed path. Default PACTA_PROPOSALS_PATH. When set, no network fetch is made for proposals. */
  proposalsPath?: string;
  /** Proposals feed URLs tried in order. Default PROPOSALS_URLS. */
  proposalsUrls?: readonly string[];
  x402Url?: string | null;
  apiBaseUrl?: string | null;
  nowSeconds?: number;
  /** Per-fetch timeout (ms, 1..60000). Default 8000 or PACTA_X402_TIMEOUT_MS. */
  timeoutMs?: number | string;
  /** Per-payment cap in atomic USDC. Default "1000000" or PACTA_X402_MAX_ATOMIC; clamped to HARD_MAX_ATOMIC. */
  maxAtomic?: string | number | bigint;
  input?: Readable;
  output?: Writable;
}

export interface JsonRpcRequest {
  jsonrpc: "2.0";
  id?: string | number | null;
  method: string;
  params?: Record<string, unknown>;
}

export interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: string | number | null;
  result?: unknown;
  error?: { code: number; message: string };
}

export declare const SERVER_INFO: Readonly<{ name: "@pacta/mcp-server"; version: string }>;
export declare const SUPPORTED_PROTOCOL_VERSION: "2024-11-05";
export declare const INDEX_URLS: ReadonlyArray<string>;
export declare const PROPOSALS_URLS: ReadonlyArray<string>;
export declare const PROPOSALS_SCHEMA: "pacta.governance_proposals_feed.v1";
export declare const PROPOSAL_FORUMS: ReadonlyArray<ProposalForum>;

export type ProposalForum = "aave" | "euler" | "morpho" | "sky";

export interface GovernanceProposal {
  proposal_id: string;
  forum: ProposalForum;
  topic_id: number;
  title: string;
  forum_url: string;
  chain: "ethereum" | "base";
  chain_id: 1 | 8453;
  pinned_block_number: number;
  pinned_block_hash: string;
  source_feed: "/api/v1/onboarding.json" | "/api/v1/index.json";
  source_record_ids: string[];
  brief_url: string | null;
  control_plane_summary: string[];
  recommended_sentinel_predicates: string[];
  repro_commands: string[];
}

export interface GovernanceProposalsFeed {
  schema: "pacta.governance_proposals_feed.v1";
  generated_at: string;
  generated_from: string[];
  counts: { total: number; by_forum: Partial<Record<ProposalForum, number>> };
  proposals: GovernanceProposal[];
}

export interface ListProposalsArgs {
  forum?: ProposalForum;
  topic_id?: number;
  chain?: "ethereum" | "base";
  /** 1..100, default 25. */
  limit?: number;
  /** Include repro_commands (default false). */
  include_repro?: boolean;
}

/** pacta_list_proposals result. repro_commands is present only when include_repro is true. */
export interface ListProposalsResult {
  source: string;
  schema: "pacta.governance_proposals_feed.v1";
  generated_at: string | null;
  counts: GovernanceProposalsFeed["counts"] | null;
  filters: Omit<ListProposalsArgs, "limit" | "include_repro"> & { limit: number; include_repro: boolean };
  total_in_feed: number;
  matched_count: number;
  returned_count: number;
  proposals: Array<Omit<GovernanceProposal, "repro_commands"> & { repro_commands?: string[] }>;
}

/** pacta_check_preflight arguments (gateway GET /v1/check/preflight). */
export interface CheckPreflightArgs {
  chain: "ethereum" | "base";
  address: string;
  /** "latest" (default), a decimal block number or 0x-hex. */
  block?: string;
}

/** Gateway /v1/check/preflight body (schema pacta.preflight_check.v1), returned as `data` by pacta_check_preflight. */
export interface PreflightCheck {
  schema: "pacta.preflight_check.v1";
  chain: "ethereum" | "base";
  chainId: number;
  address: string;
  pinnedBlock: number;
  pinnedBlockHash?: string;
  blockTimestamp?: number;
  verdict: "IMMUTABLE_NO_ADMIN" | "TIMELOCK_PROTECTED" | "ZERO_DELAY_TIMELOCK_RISK" | "MULTISIG_NO_TIMELOCK" | "INSTANT_EOA_ADMIN_RISK" | "UNCLASSIFIED_CONTRACT_CONTROLLER" | "UNDEPLOYED_OR_EOA";
  /** 0..100; null when there is no contract. */
  riskScore: number | null;
  isContract: boolean;
  isProxy: boolean;
  proxyType?: "eip1967" | "eip1967_beacon" | "eip1822" | null;
  implementation: string | null;
  beacon?: string | null;
  hasAdminSlot: boolean;
  canUpgradeZeroDelay: boolean | null;
  capabilities: { pause: boolean; blacklist: boolean; upgrade: boolean };
  paused: boolean | null;
  controller: {
    address: string | null;
    kind: "none" | "eoa" | "multisig_safe" | "timelock" | "contract" | "access_control_enumerable" | "access_control";
    safeThreshold: number | null;
    timelockDelaySec: number | null;
    safeOwnerCount?: number;
    proxyAdmin?: string;
    beacon?: string;
    /** DEFAULT_ADMIN_ROLE member count when kind is access_control_enumerable. */
    roleAdminCount?: number;
    source?: string | null;
  };
  summary: string;
}

/** Validates a feed (object or JSON text). Throws X402Error "invalid_feed" with details.reason. */
export declare function parseProposalsFeed(input: unknown, source?: string): GovernanceProposalsFeed;
export declare const DEFAULT_ANCHORING: Readonly<Record<string, unknown>>;
export declare const FREE_TOOLS: ReadonlyArray<Record<string, unknown>>;
export declare const PAID_TOOLS: ReadonlyArray<Record<string, unknown>>;
export declare const TOOL_DEFINITIONS: ReadonlyArray<Record<string, unknown>>;
export declare const PAID_ROUTES: Readonly<Record<string, Record<string, string>>>;
export declare const X402_DEFAULTS: Readonly<Record<string, unknown>>;

export declare function buildTransferWithAuthorizationTypedData(
  options: Record<string, unknown>
): TransferWithAuthorizationTypedData;

export declare function encodeXPaymentHeader(options: {
  signature: string;
  authorization: TransferWithAuthorizationMessage;
  network?: string;
}): string;

/** CAIP-2 network id for Base mainnet used by x402 v2 ("eip155:8453"); x402 v1 uses "base". */
export declare const BASE_NETWORK_V2: "eip155:8453";

/** x402 v2 requirement as returned in a validated 402 (`accepts[0]` when x402Version is 2). */
export interface PaymentRequirementsEntryV2 {
  x402Version: 2;
  scheme: "exact";
  network: "eip155:8453";
  chainId: 8453;
  amount: string;
  resource?: string;
  description?: string;
  mimeType: string;
  payTo: string;
  maxTimeoutSeconds: number;
  asset: string;
  extra: { name: "USD Coin"; version: "2" };
}

/** Base64 x402 v2 PAYMENT-SIGNATURE header: {x402Version: 2, accepted, resource?: {url}, payload}. */
export declare function encodePaymentSignatureHeader(options: {
  signature: string;
  authorization: TransferWithAuthorizationMessage;
  accepted: { amount?: string; payTo: string; maxTimeoutSeconds: number };
  resource?: string;
}): string;

export interface PaymentSignatureEnvelope {
  x402Version: 2;
  scheme: "exact";
  network: "eip155:8453";
  payload: { signature: string; authorization: TransferWithAuthorizationMessage };
}

/**
 * Validates a base64 x402 v2 PAYMENT-SIGNATURE header under the same pins as v1 (allowlisted payTo, Base USDC, cap,
 * route price, validity window). scheme/network may be in `accepted`, at the top level, or both.
 */
export declare function validatePaymentSignatureHeader(
  header: unknown,
  options?: XPaymentValidationOptions & { expectedResource?: string }
):
  | { ok: true; payment: PaymentSignatureEnvelope }
  | { ok: false; error: { code: "invalid_payment_signature"; reason: string; message: string } };

/** Stable error codes surfaced by the x402 path and the free feed loaders (thrown as X402Error, rendered as JSON in MCP tool results). */
export type X402ErrorCode =
  | "x402_disabled"
  | "invalid_config"
  | "invalid_argument"
  | "invalid_x_payment"
  | "invalid_payment_signature"
  | "malformed_header"
  | "rejected_challenge"
  | "timeout"
  | "network_error"
  | "response_too_large"
  | "upstream_http_error"
  | "unverified_settlement"
  | "feed_unavailable"
  | "invalid_feed";

export declare class X402Error extends Error {
  constructor(code: X402ErrorCode | string, message: string, details?: Record<string, unknown>);
  readonly name: "X402Error";
  readonly code: X402ErrorCode | string;
  readonly details: Record<string, unknown>;
  toJSON(): { error: string; code: string } & Record<string, unknown>;
}

export declare const ALLOWED_PAY_TO: ReadonlyArray<string>;
export declare const BASE_USDC: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
export declare const BASE_CHAIN_ID: 8453;
export declare const DEFAULT_MAX_ATOMIC: "1000000";
export declare const HARD_MAX_ATOMIC: "5000000";

export interface PaymentRequirementsEntry {
  x402Version: 1;
  scheme: "exact";
  network: "base";
  chainId: 8453;
  maxAmountRequired: string;
  resource?: string;
  description?: string;
  mimeType: string;
  payTo: string;
  maxTimeoutSeconds: number;
  asset: string;
  extra: { name: "USD Coin"; version: "2" };
}

export interface XPaymentEnvelope {
  x402Version: 1;
  scheme: "exact";
  network: "base";
  payload: { signature: string; authorization: TransferWithAuthorizationMessage };
}

export interface XPaymentValidationOptions {
  routeMaxAmountRequired?: string;
  maxAtomic?: string | number | bigint;
  allowedPayTo?: ReadonlyArray<string>;
  nowSeconds?: number;
  maxTimeoutSeconds?: number;
  maxLength?: number;
}

export declare function validateXPaymentHeader(
  header: unknown,
  options?: XPaymentValidationOptions
):
  | { ok: true; payment: XPaymentEnvelope }
  | { ok: false; error: { code: "invalid_x_payment"; reason: string; message: string } };

export declare function validateAcceptsEntry(
  entry: unknown,
  options?: {
    /** 1 (network base, maxAmountRequired) or 2 (network eip155:8453, amount); an entry-level x402Version wins. */
    containerVersion?: unknown;
    /** v2 binds the resource at the container level ({resource: {url}}); used when the entry has no resource. */
    containerResource?: unknown;
    routeMaxAmountRequired?: string;
    maxAtomic?: string | number | bigint;
    allowedPayTo?: ReadonlyArray<string>;
    maxTimeoutSecondsCeiling?: number;
    /**
     * Required: the exact absolute URL that was requested. The entry's `resource` (absolute, or relative to the request
     * origin) must have the same origin and pathname, else resource_origin_mismatch / resource_path_mismatch.
     * Missing or relative -> missing_expected_resource. The normalized entry's `resource` is this URL.
     */
    expectedResource?: string;
  }
): { ok: true; reasons: []; entry: PaymentRequirementsEntry | PaymentRequirementsEntryV2 } | { ok: false; reasons: string[] };

export declare function selectPaymentRequirements(options: {
  bodyText?: string;
  headers?: { get(name: string): string | null };
  routeSpec: { maxAmountRequired: string };
  maxAtomic?: string | number | bigint;
  /** The exact absolute URL requested; every accepts[] entry is bound to it (origin + pathname). */
  resource: string;
  sourceLabel?: string;
  /** Preferred x402 version (default 1); falls back to the first valid entry of any version. */
  preferVersion?: 1 | 2;
}): {
  selected: PaymentRequirementsEntry | PaymentRequirementsEntryV2;
  selectedFrom: { source: string; index: number };
  /** Valid entries of the other version (e.g. the v2 PAYMENT-REQUIRED header when v1 was selected). */
  alternatives: Array<PaymentRequirementsEntry | PaymentRequirementsEntryV2>;
  availableVersions: Array<1 | 2>;
  rejected: Array<{ source: string; index: number; reasons: string[] }>;
  sourceErrors: Array<{ source: string; reason: string }>;
  upstreamError?: string;
};

/** Normalized gateway receipt. payTo / amount are present only when the gateway sent them (then they matched). */
export interface PaymentReceipt {
  success: true;
  /** "base" for x402 v1, "eip155:8453" for x402 v2. */
  network: "base" | "eip155:8453";
  transaction: string;
  payer: string;
  payTo?: string;
  amount?: string;
}

/**
 * Validates the gateway's X-PAYMENT-RESPONSE header assertion: payer == expectedPayer; payTo / recipient / to ==
 * expectedPayTo (allowlist if omitted) and amount / value == expectedValue when present. Does NOT verify the
 * transaction on-chain.
 */
export declare function validatePaymentReceipt(
  raw: unknown,
  options: { expectedPayer: string; expectedPayTo?: string; expectedValue?: string; network?: "base" | "eip155:8453" }
): { ok: true; receipt: PaymentReceipt } | { ok: false; reason: string };

/**
 * Successful paid call. The client checks the gateway's receipt header against the signed authorization but does not
 * independently verify the settlement transaction on-chain: onchainReceiptVerified is always false.
 */
export interface PaidResourceResult {
  status: number;
  paymentRequired: false;
  paid: true;
  x402Version: 1 | 2;
  gatewayReceiptVerified: true;
  onchainReceiptVerified: false;
  settlementVerificationScope: "gateway_header_assertion";
  resource: string;
  paymentReceipt: PaymentReceipt;
  data: unknown;
}

export declare function decodeStrictBase64Json(
  raw: unknown,
  options?: { maxLength?: number }
): { ok: true; value: unknown } | { ok: false; reason: string };

export declare function resolveMaxAtomic(input: unknown): { maxAtomic: bigint; warning: string | null };

/** Ethereum Keccak-256 (not SHA3-256). Returns 64 lowercase hex chars, no 0x. */
export declare function keccak256Hex(input: Uint8Array | string): string;
export declare function toChecksumAddress(address: string): string;
/** 0x + 40 hex; if mixed-case, the EIP-55 checksum must be correct. */
export declare function isValidAddress(value: unknown): boolean;

export declare function callX402Resource(options: {
  fetchImpl?: typeof fetch;
  baseUrl: string | null;
  routeSpec: Record<string, string>;
  query?: Record<string, unknown>;
  /** x402 v1 payment (network base). Send this OR paymentSignatureHeader, never both. */
  xPaymentHeader?: string;
  /** x402 v2 payment (network eip155:8453), sent as PAYMENT-SIGNATURE. */
  paymentSignatureHeader?: string;
  /** Preferred version when answering a 402 challenge (default 1). */
  x402Version?: 1 | 2;
  payer?: string;
  validBeforeSeconds?: number;
  nonce?: string;
  nowSeconds?: number;
  maxAtomic?: string | number | bigint;
  timeoutMs?: number;
  maxResponseBytes?: number;
}): Promise<PaidResourceResult | Record<string, unknown>>;

export declare class PactaMcpServer {
  constructor(options?: PactaServerOptions);
  readonly maxAtomic: string;
  readonly timeoutMs: number;
  readonly configWarnings: string[];
  getTools(): ReadonlyArray<Record<string, unknown>>;
  loadSpec(): Promise<Record<string, unknown> | null>;
  loadIndex(): Promise<{ source: string; index: Record<string, unknown> }>;
  loadProposals(): Promise<{ source: string; feed: GovernanceProposalsFeed }>;
  callTool(name: string, args?: Record<string, unknown>): Promise<unknown>;
  handleMessage(msg: JsonRpcRequest): Promise<JsonRpcResponse | null>;
}

export declare function startStdioServer(options?: PactaServerOptions): {
  server: PactaMcpServer;
  close: () => void;
};
