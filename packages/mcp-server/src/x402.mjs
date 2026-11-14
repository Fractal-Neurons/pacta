import { randomBytes } from "node:crypto";
import { keccak256Hex } from "./keccak.mjs";

export { keccak256Hex };

// ---------------------------------------------------------------------------------------------------------------
// Pinned constants. Anything an upstream 402 says is checked against these; nothing upstream can widen them.
// ---------------------------------------------------------------------------------------------------------------

export const BASE_CHAIN_ID = 8453;
export const BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
/** Only these recipients may ever appear in a selected challenge, built typedData, or a forwarded X-PAYMENT. */
export const ALLOWED_PAY_TO = Object.freeze([
  "0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09", // attester / pacta.base.eth (gateway default PAY_TO)
  "0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14", // treasury owner EOA
]);
/** Default per-payment cap: 1_000_000 atomic USDC = $1.00. Override with PACTA_X402_MAX_ATOMIC / maxAtomic. */
export const DEFAULT_MAX_ATOMIC = "1000000";
/**
 * Hard ceiling for the cap: 5_000_000 atomic = $5.00, i.e. 20x the most expensive route ($0.25). No option or env var
 * can raise the cap above this, so a typo'd / hostile environment cannot turn one tool call into a large transfer.
 * In practice the per-route price (<= 250000) is the binding limit; the cap is defence in depth.
 */
export const HARD_MAX_ATOMIC = "5000000";
/** Upper bound for maxTimeoutSeconds in a challenge and for (validBefore - now) in an X-PAYMENT. */
export const MAX_TIMEOUT_SECONDS_CEILING = 600;
export const MAX_X_PAYMENT_LENGTH = 8192; // 8 KiB
export const MAX_UPSTREAM_HEADER_LENGTH = 16384; // Payment-Required / WWW-Authenticate / X-PAYMENT-RESPONSE
export const DEFAULT_TIMEOUT_MS = 8000;
export const MAX_TIMEOUT_MS = 60000;
export const MAX_RESPONSE_BYTES = 2 * 1024 * 1024;
export const SNIPPET_LENGTH = 300;

// Canonical live Pacta x402 edge Worker (Cloudflare). Published for discovery only: paid tools stay opt-in and are
// enabled solely by setting PACTA_X402_URL (defaultBaseUrl stays null, so nothing is ever paid without that choice).
export const X402_GATEWAY_URL = "https://pacta-x402.pacta.workers.dev";
/** CAIP-2 network id used by x402 v2 for Base mainnet (v1 uses the legacy name "base"). */
export const BASE_NETWORK_V2 = "eip155:8453";

export const X402_DEFAULTS = Object.freeze({
  deploymentStatus: "live_opt_in",
  gatewayUrl: X402_GATEWAY_URL,
  baseUrlEnvVar: "PACTA_X402_URL",
  maxAtomicEnvVar: "PACTA_X402_MAX_ATOMIC",
  timeoutEnvVar: "PACTA_X402_TIMEOUT_MS",
  defaultBaseUrl: null,
  x402Version: 1,
  x402Versions: Object.freeze([1, 2]),
  scheme: "exact",
  network: "base",
  networkV2: BASE_NETWORK_V2,
  networks: Object.freeze(["base", BASE_NETWORK_V2]),
  paymentHeaders: Object.freeze({ 1: "X-PAYMENT", 2: "PAYMENT-SIGNATURE" }),
  challengeHeaderV2: "PAYMENT-REQUIRED",
  receiptHeaders: Object.freeze(["PAYMENT-RESPONSE", "X-PAYMENT-RESPONSE"]),
  chainId: BASE_CHAIN_ID,
  asset: BASE_USDC,
  payTo: ALLOWED_PAY_TO[0],
  allowedPayTo: ALLOWED_PAY_TO,
  defaultMaxAtomic: DEFAULT_MAX_ATOMIC,
  hardMaxAtomic: HARD_MAX_ATOMIC,
  maxTimeoutSecondsCeiling: MAX_TIMEOUT_SECONDS_CEILING,
  defaultTimeoutMs: DEFAULT_TIMEOUT_MS,
  facilitatorUrl: "https://facilitator.payai.network",
  eip712Domain: Object.freeze({
    name: "USD Coin",
    version: "2",
    chainId: BASE_CHAIN_ID,
    verifyingContract: BASE_USDC,
  }),
});

export const PAID_ROUTES = Object.freeze({
  checkPreflight: Object.freeze({
    path: "/v1/check/preflight",
    priceUsdc: "0.01",
    maxAmountRequired: "10000",
    description: "One-call pre-execution safety check: verdict, 0-100 risk score, proxy / controller breakdown, pause / blacklist / upgrade capabilities, pinned block.",
  }),
  scanControlPlane: Object.freeze({
    path: "/v1/scan/control-plane",
    priceUsdc: "0.10",
    maxAmountRequired: "100000",
    description: "Pinned-block EVM control-plane scan (EIP-1967, Ownable, Safe, TimelockController).",
  }),
  liveTimelocks: Object.freeze({
    path: "/v1/briefs/live-timelocks",
    priceUsdc: "0.10",
    maxAmountRequired: "100000",
    description: "Live state and ETA countdowns of tracked public DeFi TimelockController operations.",
  }),
  scanTimelockOp: Object.freeze({
    path: "/v1/scan/timelock-op",
    priceUsdc: "0.25",
    maxAmountRequired: "250000",
    description: "Pinned-block OpenZeppelin TimelockController operation state and delay.",
  }),
  scanProposalDiff: Object.freeze({
    path: "/v1/scan/proposal-diff",
    priceUsdc: "0.15",
    maxAmountRequired: "150000",
    description: "Re-runs a tracked governance proposal's pinned control-plane reads live and returns pinned-vs-live diffs.",
  }),
});

// ---------------------------------------------------------------------------------------------------------------
// Structured errors
// ---------------------------------------------------------------------------------------------------------------

/**
 * Stable `code` values: x402_disabled, invalid_config, invalid_argument, invalid_x_payment, invalid_payment_signature,
 * malformed_header, rejected_challenge, timeout, network_error, response_too_large, upstream_http_error,
 * unverified_settlement.
 */
export class X402Error extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "X402Error";
    this.code = code;
    this.details = details;
  }
  toJSON() {
    return { error: this.message, code: this.code, ...this.details };
  }
}

const fail = (code, message, details) => {
  throw new X402Error(code, message, details);
};

// ---------------------------------------------------------------------------------------------------------------
// Primitive validators
// ---------------------------------------------------------------------------------------------------------------

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";
const ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;
const BYTES32_RE = /^0x[0-9a-fA-F]{64}$/;
const SIGNATURE_RE = /^0x[0-9a-fA-F]{130}$/;
const POSITIVE_INT_RE = /^[1-9][0-9]{0,77}$/; // uint256 fits in 78 decimal digits
const UINT_SECONDS_RE = /^(?:0|[1-9][0-9]{0,15})$/;
const BASE64_RE = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/;

/** Shape-only check (0x + 40 hex). Prefer `isValidAddress`, which also enforces EIP-55 when mixed-case. */
export const isAddress = (v) => typeof v === "string" && ADDRESS_RE.test(v);
export const isBytes32 = (v) => typeof v === "string" && BYTES32_RE.test(v);
export const isSignature65 = (v) => typeof v === "string" && SIGNATURE_RE.test(v);

export function isPlainObject(v) {
  if (v === null || typeof v !== "object" || Array.isArray(v)) return false;
  const proto = Object.getPrototypeOf(v);
  return proto === Object.prototype || proto === null;
}

/** EIP-55 checksum encoding. Throws on non-address input. */
export function toChecksumAddress(addr) {
  if (!isAddress(addr)) throw new X402Error("invalid_argument", "Not a 20-byte hex address.");
  const body = addr.slice(2).toLowerCase();
  const hash = keccak256Hex(body);
  let out = "0x";
  for (let i = 0; i < 40; i++) {
    const ch = body[i];
    out += ch >= "a" && ch <= "f" && parseInt(hash[i], 16) >= 8 ? ch.toUpperCase() : ch;
  }
  return out;
}

/** Returns null when OK, otherwise "not_address" | "bad_checksum". All-lower / all-upper hex skip EIP-55. */
export function addressProblem(v) {
  if (!isAddress(v)) return "not_address";
  const body = v.slice(2);
  if (body === body.toLowerCase() || body === body.toUpperCase()) return null;
  return toChecksumAddress(v) === v ? null : "bad_checksum";
}

export const isValidAddress = (v) => addressProblem(v) === null;
export const sameAddress = (a, b) => isAddress(a) && isAddress(b) && a.toLowerCase() === b.toLowerCase();

const isAllowedPayTo = (addr, allowlist = ALLOWED_PAY_TO) => allowlist.some((a) => sameAddress(a, addr));

/** Parse a strictly positive canonical decimal integer *string* (no sign, no leading zeros, no exponent). */
export function parsePositiveAtomic(v) {
  if (typeof v !== "string" || !POSITIVE_INT_RE.test(v)) return null;
  return BigInt(v);
}

/**
 * Resolve the per-payment cap. Never returns more than HARD_MAX_ATOMIC; garbage falls back to the default.
 * @returns {{ maxAtomic: bigint, warning: string | null }}
 */
export function resolveMaxAtomic(input) {
  const def = BigInt(DEFAULT_MAX_ATOMIC);
  const hard = BigInt(HARD_MAX_ATOMIC);
  if (input === undefined || input === null || input === "") return { maxAtomic: def, warning: null };
  const s = typeof input === "bigint" || typeof input === "number" ? String(input) : input;
  const v = parsePositiveAtomic(typeof s === "string" ? s.trim() : s);
  if (v === null) {
    return { maxAtomic: def, warning: `Ignoring invalid PACTA_X402_MAX_ATOMIC; using default ${DEFAULT_MAX_ATOMIC}.` };
  }
  if (v > hard) {
    return { maxAtomic: hard, warning: `PACTA_X402_MAX_ATOMIC above hard ceiling; clamped to ${HARD_MAX_ATOMIC}.` };
  }
  return { maxAtomic: v, warning: null };
}

/** Resolve fetch timeout in ms (integer 1..MAX_TIMEOUT_MS); garbage falls back to DEFAULT_TIMEOUT_MS. */
export function resolveTimeoutMs(input) {
  if (input === undefined || input === null || input === "") return DEFAULT_TIMEOUT_MS;
  const n = typeof input === "string" && /^[0-9]{1,6}$/.test(input.trim()) ? Number(input.trim()) : input;
  if (!Number.isSafeInteger(n) || n < 1) return DEFAULT_TIMEOUT_MS;
  return Math.min(n, MAX_TIMEOUT_MS);
}

const nowSecondsOr = (nowSeconds) =>
  Number.isSafeInteger(nowSeconds) && nowSeconds >= 0 ? nowSeconds : Math.floor(Date.now() / 1000);

// ---------------------------------------------------------------------------------------------------------------
// Strict Base64(JSON) decoding
// ---------------------------------------------------------------------------------------------------------------

/**
 * Strict canonical Base64 -> fatal UTF-8 -> JSON.parse. Never throws.
 * @returns {{ ok: true, value: unknown } | { ok: false, reason: string }}
 * reasons: not_string, empty, too_long, bad_base64, non_canonical_base64, bad_utf8, bad_json
 */
export function decodeStrictBase64Json(raw, { maxLength = MAX_UPSTREAM_HEADER_LENGTH } = {}) {
  if (typeof raw !== "string") return { ok: false, reason: "not_string" };
  if (raw.length === 0) return { ok: false, reason: "empty" };
  if (raw.length > maxLength) return { ok: false, reason: "too_long" };
  if (raw.length % 4 !== 0 || !BASE64_RE.test(raw)) return { ok: false, reason: "bad_base64" };
  const bytes = Buffer.from(raw, "base64");
  if (bytes.toString("base64") !== raw) return { ok: false, reason: "non_canonical_base64" };
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return { ok: false, reason: "bad_utf8" };
  }
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch {
    return { ok: false, reason: "bad_json" };
  }
}

/** Strict decoder that throws X402Error("malformed_header") instead of returning a `{raw}` placeholder. */
export function decodeBase64JsonHeader(raw, opts) {
  const r = decodeStrictBase64Json(raw, opts);
  if (!r.ok) fail("malformed_header", `Malformed base64 JSON header (${r.reason}).`, { reason: r.reason });
  return r.value;
}

// ---------------------------------------------------------------------------------------------------------------
// X-PAYMENT validation (caller-supplied payment envelope)
// ---------------------------------------------------------------------------------------------------------------

const AUTH_KEYS = ["from", "to", "value", "validAfter", "validBefore", "nonce"];
const hasOnlyKeys = (obj, keys) => Object.keys(obj).every((k) => keys.includes(k));

/**
 * Validate a base64 x402 v1 X-PAYMENT header. Never throws; never touches the network.
 * @returns {{ ok: true, payment: object } | { ok: false, error: { code: "invalid_x_payment", reason: string, message: string } }}
 */
export function validateXPaymentHeader(
  header,
  {
    routeMaxAmountRequired,
    maxAtomic = DEFAULT_MAX_ATOMIC,
    allowedPayTo = ALLOWED_PAY_TO,
    nowSeconds,
    maxTimeoutSeconds = MAX_TIMEOUT_SECONDS_CEILING,
    maxLength = MAX_X_PAYMENT_LENGTH,
  } = {}
) {
  const bad = (reason, message) => ({
    ok: false,
    error: { code: "invalid_x_payment", reason, message: `Invalid X-PAYMENT: ${message}` },
  });

  const dec = decodeStrictBase64Json(header, { maxLength });
  if (!dec.ok) return bad(dec.reason, `header failed strict base64/UTF-8/JSON decoding (${dec.reason}).`);
  const p = dec.value;
  if (!isPlainObject(p)) return bad("not_object", "decoded JSON must be an object.");
  if (!hasOnlyKeys(p, ["x402Version", "scheme", "network", "payload"])) return bad("unexpected_field", "unexpected top-level field.");
  if (p.x402Version !== 1) return bad("bad_x402_version", "x402Version must be 1.");
  if (p.scheme !== "exact") return bad("bad_scheme", 'scheme must be "exact".');
  if (p.network !== "base") return bad("bad_network", 'network must be "base".');
  const payload = p.payload;
  if (!isPlainObject(payload) || !hasOnlyKeys(payload, ["signature", "authorization"])) {
    return bad("bad_payload", "payload must be an object with signature and authorization.");
  }
  const auth = checkExactAuthorization(payload, { routeMaxAmountRequired, maxAtomic, allowedPayTo, nowSeconds, maxTimeoutSeconds });
  if (!auth.ok) return bad(auth.reason, auth.message);
  return { ok: true, payment: { x402Version: 1, scheme: "exact", network: "base", payload: auth.payload } };
}

/**
 * EIP-3009 `exact` payload checks shared by x402 v1 (X-PAYMENT) and v2 (PAYMENT-SIGNATURE): 65-byte signature,
 * exact authorization keys, EIP-55 from/to, allowlisted recipient, value <= cap and <= route price, validity window
 * within `maxTimeoutSeconds`, 32-byte nonce. Returns the normalized payload.
 */
function checkExactAuthorization(payload, { routeMaxAmountRequired, maxAtomic, allowedPayTo, nowSeconds, maxTimeoutSeconds }) {
  const bad = (reason, message) => ({ ok: false, reason, message });
  if (!isSignature65(payload.signature)) return bad("bad_signature", "signature must be 65-byte 0x hex.");
  const a = payload.authorization;
  if (!isPlainObject(a) || !hasOnlyKeys(a, AUTH_KEYS) || !AUTH_KEYS.every((k) => k in a)) {
    return bad("bad_authorization", "authorization must have exactly from,to,value,validAfter,validBefore,nonce.");
  }

  const fromProblem = addressProblem(a.from);
  if (fromProblem) return bad(fromProblem === "bad_checksum" ? "bad_checksum" : "bad_from", "authorization.from is invalid.");
  if (sameAddress(a.from, ZERO_ADDRESS)) return bad("bad_from", "authorization.from is the zero address.");
  const toProblem = addressProblem(a.to);
  if (toProblem) return bad(toProblem === "bad_checksum" ? "bad_checksum" : "bad_to", "authorization.to is invalid.");
  if (!isAllowedPayTo(a.to, allowedPayTo)) return bad("recipient_not_allowed", "authorization.to is not an allowed Pacta recipient.");

  const value = parsePositiveAtomic(a.value);
  if (value === null) return bad("bad_value", "authorization.value must be a positive integer string.");
  const cap = BigInt(resolveMaxAtomic(maxAtomic).maxAtomic);
  if (value > cap) return bad("value_over_cap", `authorization.value exceeds cap ${cap}.`);
  if (routeMaxAmountRequired !== undefined) {
    const routeMax = parsePositiveAtomic(String(routeMaxAmountRequired));
    if (routeMax === null) return bad("bad_route_price", "route price is not a positive integer.");
    if (value > routeMax) return bad("value_over_route_price", `authorization.value exceeds route price ${routeMax}.`);
  }

  if (typeof a.validAfter !== "string" || !UINT_SECONDS_RE.test(a.validAfter)) return bad("bad_valid_after", "validAfter must be a decimal string.");
  if (typeof a.validBefore !== "string" || !UINT_SECONDS_RE.test(a.validBefore)) return bad("bad_valid_before", "validBefore must be a decimal string.");
  const now = nowSecondsOr(nowSeconds);
  const va = Number(a.validAfter);
  const vb = Number(a.validBefore);
  if (va > now) return bad("not_yet_valid", "validAfter is in the future.");
  if (vb <= now) return bad("expired", "validBefore is not in the future.");
  if (vb - now > maxTimeoutSeconds) return bad("validity_window_too_long", `validBefore is more than ${maxTimeoutSeconds}s ahead.`);
  if (!isBytes32(a.nonce)) return bad("bad_nonce", "nonce must be 32-byte 0x hex.");

  return {
    ok: true,
    payload: {
      signature: payload.signature,
      authorization: { from: a.from, to: a.to, value: a.value, validAfter: a.validAfter, validBefore: a.validBefore, nonce: a.nonce },
    },
  };
}

const V2_PAYMENT_KEYS = ["x402Version", "scheme", "network", "accepted", "payload", "resource", "extensions"];
const V2_ACCEPTED_KEYS = ["scheme", "network", "amount", "asset", "payTo", "maxTimeoutSeconds", "extra"];

/**
 * Validate a base64 x402 v2 PAYMENT-SIGNATURE header under the same pins as v1. `scheme` / `network` may sit in the
 * standard `accepted` requirement, at the top level, or both: every value given must be "exact" / "eip155:8453" and
 * each must be given at least once. Any `accepted` field present must satisfy the pins (Base USDC, allowlisted payTo,
 * amount <= cap and <= route price and == authorization.value, maxTimeoutSeconds within the ceiling, USDC EIP-712
 * extra). An optional `resource` ({url} or string) must name `expectedResource` (origin + pathname). Never throws.
 * @returns {{ ok: true, payment: object } | { ok: false, error: { code: "invalid_payment_signature", reason, message } }}
 */
export function validatePaymentSignatureHeader(
  header,
  {
    routeMaxAmountRequired,
    maxAtomic = DEFAULT_MAX_ATOMIC,
    allowedPayTo = ALLOWED_PAY_TO,
    nowSeconds,
    maxTimeoutSeconds = MAX_TIMEOUT_SECONDS_CEILING,
    maxLength = MAX_X_PAYMENT_LENGTH,
    expectedResource,
  } = {}
) {
  const bad = (reason, message) => ({
    ok: false,
    error: { code: "invalid_payment_signature", reason, message: `Invalid PAYMENT-SIGNATURE: ${message}` },
  });
  const dec = decodeStrictBase64Json(header, { maxLength });
  if (!dec.ok) return bad(dec.reason, `header failed strict base64/UTF-8/JSON decoding (${dec.reason}).`);
  const p = dec.value;
  if (!isPlainObject(p)) return bad("not_object", "decoded JSON must be an object.");
  if (!hasOnlyKeys(p, V2_PAYMENT_KEYS)) return bad("unexpected_field", "unexpected top-level field.");
  if (p.x402Version !== 2) return bad("bad_x402_version", "x402Version must be 2.");
  const acc = p.accepted;
  if (acc !== undefined && (!isPlainObject(acc) || !hasOnlyKeys(acc, V2_ACCEPTED_KEYS))) {
    return bad("bad_accepted", `accepted must be an object with only ${V2_ACCEPTED_KEYS.join(",")}.`);
  }
  const pick = (k) => [p[k], acc && acc[k]].filter((v) => v !== undefined);
  const schemes = pick("scheme");
  const networks = pick("network");
  if (!schemes.length || schemes.some((v) => v !== "exact")) return bad("bad_scheme", 'scheme must be "exact".');
  if (!networks.length || networks.some((v) => v !== BASE_NETWORK_V2)) return bad("bad_network", `network must be "${BASE_NETWORK_V2}".`);
  const payload = p.payload;
  if (!isPlainObject(payload) || !hasOnlyKeys(payload, ["signature", "authorization"])) {
    return bad("bad_payload", "payload must be an object with signature and authorization.");
  }
  const auth = checkExactAuthorization(payload, { routeMaxAmountRequired, maxAtomic, allowedPayTo, nowSeconds, maxTimeoutSeconds });
  if (!auth.ok) return bad(auth.reason, auth.message);
  const a = auth.payload.authorization;
  if (acc) {
    if (acc.asset !== undefined && (!isAddress(acc.asset) || !sameAddress(acc.asset, BASE_USDC))) return bad("bad_asset", "accepted.asset must be Base USDC.");
    if (acc.payTo !== undefined && (!isValidAddress(acc.payTo) || !isAllowedPayTo(acc.payTo, allowedPayTo) || !sameAddress(acc.payTo, a.to))) {
      return bad("recipient_not_allowed", "accepted.payTo must be an allowed Pacta recipient equal to authorization.to.");
    }
    if (acc.amount !== undefined) {
      const amt = parsePositiveAtomic(acc.amount);
      if (amt === null) return bad("bad_value", "accepted.amount must be a positive integer string.");
      if (amt !== BigInt(a.value)) return bad("value_mismatch", "accepted.amount must equal authorization.value.");
    }
    if (acc.maxTimeoutSeconds !== undefined && (!Number.isSafeInteger(acc.maxTimeoutSeconds) || acc.maxTimeoutSeconds <= 0 || acc.maxTimeoutSeconds > MAX_TIMEOUT_SECONDS_CEILING)) {
      return bad("bad_max_timeout", "accepted.maxTimeoutSeconds is out of range.");
    }
    if (acc.extra !== undefined && (!isPlainObject(acc.extra) || acc.extra.name !== "USD Coin" || acc.extra.version !== "2")) {
      return bad("bad_extra", "accepted.extra must be the USD Coin / 2 EIP-712 domain.");
    }
  }
  if (p.resource !== undefined) {
    const url = typeof p.resource === "string" ? p.resource : isPlainObject(p.resource) ? p.resource.url : undefined;
    const exp = parseExpectedResource(expectedResource);
    if (resourceBindingReasons(typeof url === "string" ? url : 0, exp).length) return bad("resource_mismatch", "resource does not name the requested route.");
  }
  if (p.extensions !== undefined && !isPlainObject(p.extensions)) return bad("bad_extensions", "extensions must be an object.");
  return { ok: true, payment: { x402Version: 2, scheme: "exact", network: BASE_NETWORK_V2, payload: auth.payload } };
}

// ---------------------------------------------------------------------------------------------------------------
// Upstream 402 challenge validation
// ---------------------------------------------------------------------------------------------------------------

/**
 * Parse the expected resource (the exact URL this client requested). Must be an absolute http(s) URL.
 * @returns {URL | null}
 */
function parseExpectedResource(v) {
  if (typeof v !== "string" || !v || v.length > 2048) return null;
  try {
    const u = new URL(v);
    return u.protocol === "https:" || u.protocol === "http:" ? u : null;
  } catch {
    return null;
  }
}

/**
 * Resource binding: an entry's `resource` (absolute, or relative resolved against the request origin) must have
 * the same origin and pathname as the requested URL. A missing `resource` is accepted (it claims nothing); the
 * normalized entry always carries the requested URL, never the upstream string.
 * @returns {string[]} reasons (empty when bound)
 */
function resourceBindingReasons(entryResource, expected) {
  if (!expected) return ["missing_expected_resource"];
  if (entryResource === undefined || entryResource === null) return [];
  if (typeof entryResource !== "string" || !entryResource || entryResource.length > 2048) return ["bad_resource"];
  let u;
  try {
    u = new URL(entryResource, expected.origin);
  } catch {
    return ["bad_resource"];
  }
  if (u.protocol !== "https:" && u.protocol !== "http:") return ["bad_resource"];
  const reasons = [];
  if (u.origin !== expected.origin) reasons.push("resource_origin_mismatch");
  if (u.pathname !== expected.pathname) reasons.push("resource_path_mismatch");
  return reasons;
}

// Module-private opt-out of resource binding, used only for the locally generated discovery spec.
const LOCAL_SPEC = Symbol("pacta.localSpec");

function chainIdOk(v) {
  if (v === undefined) return true;
  if (v === BASE_CHAIN_ID) return true;
  return typeof v === "string" && ["8453", "0x2105", "eip155:8453"].includes(v.toLowerCase());
}

/**
 * Validate one `accepts[]` entry against the pinned Base/USDC/allowlist/cap/route-price policy and bind it to the
 * exact requested URL (`expectedResource`, required: origin + pathname must match the entry's `resource`).
 * Collects every failing reason. On success returns a *normalized* entry built from pinned constants
 * (asset = BASE_USDC, payTo = EIP-55 form of an allowlisted address, extra = {USD Coin, 2},
 * resource = expectedResource; the upstream `resource` string is never copied).
 */
export function validateAcceptsEntry(
  entry,
  {
    containerVersion,
    containerResource,
    routeMaxAmountRequired,
    maxAtomic = DEFAULT_MAX_ATOMIC,
    allowedPayTo = ALLOWED_PAY_TO,
    maxTimeoutSecondsCeiling = MAX_TIMEOUT_SECONDS_CEILING,
    expectedResource,
    [LOCAL_SPEC]: localSpec = false,
  } = {}
) {
  if (!isPlainObject(entry)) return { ok: false, reasons: ["not_object"] };
  const expected = parseExpectedResource(expectedResource);
  const reasons = [];
  const version = entry.x402Version !== undefined ? entry.x402Version : containerVersion;
  if (version !== 1 && version !== 2) reasons.push("bad_x402_version");
  const v2 = version === 2;
  if (entry.scheme !== "exact") reasons.push("bad_scheme");
  if (entry.network !== (v2 ? BASE_NETWORK_V2 : "base")) reasons.push("bad_network");
  if (!chainIdOk(entry.chainId) || (isPlainObject(entry.extra) && !chainIdOk(entry.extra.chainId))) {
    reasons.push("bad_chain_id");
  }

  const assetProblem = addressProblem(entry.asset);
  if (assetProblem === "not_address" || !sameAddress(entry.asset, BASE_USDC)) reasons.push("bad_asset");
  else if (assetProblem === "bad_checksum") reasons.push("bad_asset_checksum");

  const payToProblem = addressProblem(entry.payTo);
  if (payToProblem === "not_address") reasons.push("bad_pay_to");
  else {
    if (!isAllowedPayTo(entry.payTo, allowedPayTo)) reasons.push("pay_to_not_allowed");
    if (payToProblem === "bad_checksum") reasons.push("bad_pay_to_checksum");
  }

  const amountField = v2 ? "amount" : "maxAmountRequired"; // v1: maxAmountRequired; v2: amount
  const amount = parsePositiveAtomic(entry[amountField]);
  if (amount === null) reasons.push("bad_amount");
  else {
    if (amount > BigInt(resolveMaxAtomic(maxAtomic).maxAtomic)) reasons.push("amount_over_cap");
    const routeMax = routeMaxAmountRequired === undefined ? null : parsePositiveAtomic(String(routeMaxAmountRequired));
    if (routeMaxAmountRequired !== undefined && routeMax === null) reasons.push("bad_route_price");
    else if (routeMax !== null && amount > routeMax) reasons.push("amount_over_route_price");
  }

  const mts = entry.maxTimeoutSeconds;
  if (!Number.isSafeInteger(mts) || mts <= 0 || mts > maxTimeoutSecondsCeiling) reasons.push("bad_max_timeout");

  if (!isPlainObject(entry.extra) || entry.extra.name !== "USD Coin" || entry.extra.version !== "2") reasons.push("bad_extra");

  // v2 binds the resource at the container level ({resource: {url}}); an entry-level resource, when present, wins.
  if (!localSpec) reasons.push(...resourceBindingReasons(entry.resource !== undefined ? entry.resource : containerResource, expected));

  if (reasons.length) return { ok: false, reasons };
  const bounded = (v, n) => (typeof v === "string" ? v.slice(0, n) : undefined);
  return {
    ok: true,
    reasons: [],
    entry: {
      x402Version: v2 ? 2 : 1,
      scheme: "exact",
      network: v2 ? BASE_NETWORK_V2 : "base",
      chainId: BASE_CHAIN_ID,
      ...(v2 ? { amount: entry.amount } : { maxAmountRequired: entry.maxAmountRequired }),
      ...(expected ? { resource: expectedResource } : {}),
      ...(bounded(entry.description, 512) !== undefined ? { description: bounded(entry.description, 512) } : {}),
      mimeType: bounded(entry.mimeType, 128) ?? "application/json",
      payTo: toChecksumAddress(entry.payTo),
      maxTimeoutSeconds: mts,
      asset: BASE_USDC,
      extra: { name: "USD Coin", version: "2" },
    },
  };
}

/**
 * Parse `WWW-Authenticate` for an `x402` challenge. x402 v1 does not standardise this header, so we accept either
 * `x402 <base64-json>` (token68) or `x402 accepts="<base64-json>"` (also `payment-required=` / `requirements=`).
 * The decoded JSON may be `{ x402Version, accepts: [...] }` or a bare array.
 * @returns {{ ok: true, value: unknown } | { ok: false, reason: string } | null} null when no x402 challenge present
 */
export function parseWwwAuthenticateX402(header) {
  if (typeof header !== "string" || !header) return null;
  if (header.length > MAX_UPSTREAM_HEADER_LENGTH) return { ok: false, reason: "too_long" };
  const m = /(?:^|,)\s*x402(?:\s+(.*))?$/is.exec(header);
  if (!m) return null;
  const rest = (m[1] || "").trim();
  if (!rest) return { ok: false, reason: "empty" };
  if (/^[A-Za-z0-9+/]+=*$/.test(rest)) return decodeStrictBase64Json(rest); // token68 form
  const params = {};
  const re = /([A-Za-z0-9_-]+)\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^\s,]*))/g;
  let pm;
  while ((pm = re.exec(rest))) params[pm[1].toLowerCase()] = pm[2] !== undefined ? pm[2].replace(/\\(.)/g, "$1") : pm[3];
  const v = params.accepts ?? params["payment-required"] ?? params.requirements;
  if (v === undefined) return { ok: false, reason: "no_x402_param" };
  return decodeStrictBase64Json(v);
}

function collectCandidates(sourceName, value, out, sourceErrors) {
  if (Array.isArray(value)) {
    value.forEach((entry, index) => out.push({ source: sourceName, index, entry, containerVersion: undefined }));
  } else if (isPlainObject(value) && Array.isArray(value.accepts)) {
    const r = value.resource;
    const containerResource = isPlainObject(r) ? r.url : r;
    value.accepts.forEach((entry, index) =>
      out.push({ source: sourceName, index, entry, containerVersion: value.x402Version, containerResource })
    );
  } else {
    sourceErrors.push({ source: sourceName, reason: "no_accepts_array" });
  }
}

/**
 * Extract and validate every accepts[] entry from a 402: the JSON body (x402 v1), the base64 PAYMENT-REQUIRED header
 * (x402 v2; also v1-shaped) / X-Payment-Required, and WWW-Authenticate. Every entry is checked under the same pins
 * (Base USDC, payTo allowlist, cap, route price, timeout ceiling, resource binding). Returns the first valid entry of
 * `preferVersion` (default 1), else the first valid entry of any version, or a rejected_challenge X402Error with
 * per-entry reasons. Never falls back to an unvalidated entry.
 */
export function selectPaymentRequirements({ bodyText, headers, routeSpec, maxAtomic, resource, sourceLabel = "upstream_402", preferVersion = 1 }) {
  const candidates = [];
  const sourceErrors = [];
  let upstreamError;

  if (typeof bodyText === "string" && bodyText.length) {
    let body;
    try {
      body = JSON.parse(bodyText);
    } catch {
      sourceErrors.push({ source: "body", reason: "bad_json" });
    }
    if (body !== undefined) {
      if (isPlainObject(body) && typeof body.error === "string") upstreamError = body.error.slice(0, SNIPPET_LENGTH);
      if (isPlainObject(body) && body.accepts === undefined) sourceErrors.push({ source: "body", reason: "no_accepts_array" });
      else collectCandidates("body", body, candidates, sourceErrors);
    }
  }

  const get = (k) => {
    const v = headers?.get?.(k);
    return typeof v === "string" ? v : null;
  };
  for (const name of ["payment-required", "x-payment-required"]) {
    const raw = get(name);
    if (raw === null) continue;
    const dec = decodeStrictBase64Json(raw);
    if (!dec.ok) sourceErrors.push({ source: name, reason: dec.reason });
    else collectCandidates(name, dec.value, candidates, sourceErrors);
  }
  const www = parseWwwAuthenticateX402(get("www-authenticate"));
  if (www && !www.ok) sourceErrors.push({ source: "www-authenticate", reason: www.reason });
  else if (www) collectCandidates("www-authenticate", www.value, candidates, sourceErrors);

  const rejected = [];
  const valid = [];
  for (const c of candidates) {
    const r = validateAcceptsEntry(c.entry, {
      containerVersion: c.containerVersion,
      containerResource: c.containerResource,
      routeMaxAmountRequired: routeSpec.maxAmountRequired,
      maxAtomic,
      expectedResource: resource,
    });
    if (r.ok) valid.push({ entry: r.entry, from: { source: c.source, index: c.index } });
    else rejected.push({ source: c.source, index: c.index, reasons: r.reasons });
  }
  if (valid.length) {
    const pick = valid.find((v) => v.entry.x402Version === preferVersion) ?? valid[0];
    const alternatives = valid.filter((v) => v !== pick && v.entry.x402Version !== pick.entry.x402Version).map((v) => v.entry);
    return {
      selected: pick.entry,
      selectedFrom: pick.from,
      alternatives,
      availableVersions: [...new Set(valid.map((v) => v.entry.x402Version))].sort(),
      rejected,
      sourceErrors,
      upstreamError,
    };
  }
  throw new X402Error(
    "rejected_challenge",
    candidates.length
      ? `x402 challenge rejected: none of ${candidates.length} accepts[] entries satisfies the Base USDC / payTo allowlist / price / resource-binding policy.`
      : "x402 challenge rejected: 402 response carried no accepts[] entries.",
    { source: sourceLabel, status: 402, resource, entries: rejected, sourceErrors, ...(upstreamError ? { upstreamError } : {}) }
  );
}

// ---------------------------------------------------------------------------------------------------------------
// Settlement receipt (X-PAYMENT-RESPONSE)
// ---------------------------------------------------------------------------------------------------------------

const RECEIPT_RECIPIENT_FIELDS = ["payTo", "recipient", "to"];
const RECEIPT_AMOUNT_FIELDS = ["amount", "value"];

/**
 * Validate the gateway's X-PAYMENT-RESPONSE header. This checks the gateway's *assertion* only: success, network,
 * a non-zero tx hash, payer == authorization.from, and, when present, payTo / recipient / to == authorization.to
 * and amount / value == authorization.value. It does NOT look the transaction up on-chain.
 * @returns {{ ok: true, receipt: object } | { ok: false, reason: string }}
 */
export function validatePaymentReceipt(raw, { expectedPayer, expectedPayTo, expectedValue, network = "base" } = {}) {
  if (raw === null || raw === undefined) return { ok: false, reason: "missing_receipt" };
  const dec = decodeStrictBase64Json(raw);
  if (!dec.ok) return { ok: false, reason: `receipt_${dec.reason}` };
  const r = dec.value;
  if (!isPlainObject(r)) return { ok: false, reason: "receipt_not_object" };
  if (r.success !== true) return { ok: false, reason: "receipt_not_success" };
  if (r.network !== network) return { ok: false, reason: "receipt_bad_network" };
  if (!isBytes32(r.transaction) || /^0x0{64}$/.test(r.transaction)) return { ok: false, reason: "receipt_bad_transaction" };
  if (r.payer === undefined || r.payer === null || r.payer === "") return { ok: false, reason: "receipt_missing_payer" };
  if (!isValidAddress(r.payer)) return { ok: false, reason: "receipt_bad_payer" };
  if (!sameAddress(r.payer, expectedPayer)) return { ok: false, reason: "receipt_payer_mismatch" };

  let payTo;
  for (const k of RECEIPT_RECIPIENT_FIELDS) {
    if (r[k] === undefined) continue;
    if (!isValidAddress(r[k])) return { ok: false, reason: "receipt_bad_pay_to" };
    const matches = expectedPayTo !== undefined ? sameAddress(r[k], expectedPayTo) : isAllowedPayTo(r[k]);
    if (!matches) return { ok: false, reason: "receipt_pay_to_mismatch" };
    if (payTo !== undefined && !sameAddress(payTo, r[k])) return { ok: false, reason: "receipt_pay_to_mismatch" };
    payTo = toChecksumAddress(r[k]);
  }

  let amount;
  for (const k of RECEIPT_AMOUNT_FIELDS) {
    if (r[k] === undefined) continue;
    const v = typeof r[k] === "number" && Number.isSafeInteger(r[k]) ? String(r[k]) : r[k];
    const n = typeof v === "string" ? parsePositiveAtomic(v) : null;
    if (n === null) return { ok: false, reason: "receipt_bad_amount" };
    if (expectedValue !== undefined && n !== parsePositiveAtomic(String(expectedValue))) {
      return { ok: false, reason: "receipt_amount_mismatch" };
    }
    if (amount !== undefined && BigInt(amount) !== n) return { ok: false, reason: "receipt_amount_mismatch" };
    amount = n.toString();
  }

  return {
    ok: true,
    receipt: {
      success: true,
      network,
      transaction: r.transaction,
      payer: r.payer,
      ...(payTo !== undefined ? { payTo } : {}),
      ...(amount !== undefined ? { amount } : {}),
    },
  };
}

// ---------------------------------------------------------------------------------------------------------------
// Builders
// ---------------------------------------------------------------------------------------------------------------

export function buildPaymentRequirements(routeSpec, resource) {
  return {
    x402Version: 1,
    scheme: X402_DEFAULTS.scheme,
    network: X402_DEFAULTS.network,
    maxAmountRequired: String(routeSpec.maxAmountRequired),
    resource,
    description: routeSpec.description,
    mimeType: "application/json",
    payTo: routeSpec.payTo || X402_DEFAULTS.payTo,
    maxTimeoutSeconds: 60, // the live Worker's MAX_TIMEOUT_S
    asset: routeSpec.asset || X402_DEFAULTS.asset,
    extra: { name: "USD Coin", version: "2" },
  };
}

/**
 * Local-spec PaymentRequirements for discovery. Clearly labelled `source: "local_spec"` and passed through the same
 * validator as upstream entries; never presented as an upstream 402.
 */
export function localSpecRequirements(routeSpec, resource, { maxAtomic } = {}) {
  // The resource here is our own route URL (or bare path when no gateway is configured), so binding is skipped.
  const r = validateAcceptsEntry(buildPaymentRequirements(routeSpec, resource), {
    routeMaxAmountRequired: routeSpec.maxAmountRequired,
    maxAtomic,
    [LOCAL_SPEC]: true,
  });
  return r.ok
    ? { source: "local_spec", valid: true, entry: { ...r.entry, ...(typeof resource === "string" ? { resource } : {}) } }
    : { source: "local_spec", valid: false, reasons: r.reasons };
}

/**
 * EIP-712 TransferWithAuthorization typedData. Domain is pinned (USD Coin / 2 / 8453 / Base USDC); payTo must be
 * allowlisted; value must be <= HARD_MAX_ATOMIC. Overrides that disagree with the pinned domain throw.
 */
export function buildTransferWithAuthorizationTypedData({
  payer = ZERO_ADDRESS,
  payTo = X402_DEFAULTS.payTo,
  value,
  validAfter = "0",
  validBefore,
  nonce,
  nowSeconds,
  ttlSeconds = 300,
  chainId = BASE_CHAIN_ID,
  verifyingContract = BASE_USDC,
  tokenName = "USD Coin",
  tokenVersion = "2",
} = {}) {
  if (payer !== ZERO_ADDRESS && !isValidAddress(payer)) fail("invalid_argument", "Invalid payer address.");
  if (!isValidAddress(payTo) || !isAllowedPayTo(payTo)) fail("invalid_argument", "payTo is not an allowed Pacta recipient.");
  if (chainId !== BASE_CHAIN_ID) fail("invalid_argument", "EIP-712 chainId must be 8453 (Base).");
  if (!isValidAddress(verifyingContract) || !sameAddress(verifyingContract, BASE_USDC)) {
    fail("invalid_argument", "EIP-712 verifyingContract must be Base USDC.");
  }
  if (tokenName !== "USD Coin" || tokenVersion !== "2") fail("invalid_argument", "EIP-712 domain must be USD Coin / 2.");
  const v = parsePositiveAtomic(String(value ?? ""));
  if (v === null) fail("invalid_argument", "Invalid USDC value.");
  if (v > BigInt(HARD_MAX_ATOMIC)) fail("invalid_argument", `USDC value exceeds hard ceiling ${HARD_MAX_ATOMIC}.`);
  const resolvedNonce = nonce ?? `0x${randomBytes(32).toString("hex")}`;
  if (!isBytes32(resolvedNonce)) fail("invalid_argument", "Invalid 32-byte hex nonce.");
  const ttl = Number(ttlSeconds);
  if (!Number.isSafeInteger(ttl) || ttl < 1 || ttl > MAX_TIMEOUT_SECONDS_CEILING) {
    fail("invalid_argument", `ttlSeconds must be an integer in 1..${MAX_TIMEOUT_SECONDS_CEILING}.`);
  }
  const vb = validBefore ?? String(nowSecondsOr(nowSeconds) + ttl);
  if (!UINT_SECONDS_RE.test(String(validAfter)) || !UINT_SECONDS_RE.test(String(vb))) {
    fail("invalid_argument", "validAfter/validBefore must be non-negative integers.");
  }

  return {
    domain: { name: "USD Coin", version: "2", chainId: BASE_CHAIN_ID, verifyingContract: BASE_USDC },
    primaryType: "TransferWithAuthorization",
    types: {
      EIP712Domain: [
        { name: "name", type: "string" },
        { name: "version", type: "string" },
        { name: "chainId", type: "uint256" },
        { name: "verifyingContract", type: "address" },
      ],
      TransferWithAuthorization: [
        { name: "from", type: "address" },
        { name: "to", type: "address" },
        { name: "value", type: "uint256" },
        { name: "validAfter", type: "uint256" },
        { name: "validBefore", type: "uint256" },
        { name: "nonce", type: "bytes32" },
      ],
    },
    message: {
      from: payer,
      to: toChecksumAddress(payTo),
      value: String(value),
      validAfter: String(validAfter),
      validBefore: String(vb),
      nonce: resolvedNonce,
    },
  };
}

/**
 * Base64 x402 v2 PAYMENT-SIGNATURE header: {x402Version: 2, accepted, resource?, payload}. `accepted` is the
 * validated v2 requirement from the 402 (scheme exact, network eip155:8453, amount, asset, payTo, maxTimeoutSeconds,
 * extra); `resource` is the route URL without query.
 */
export function encodePaymentSignatureHeader({ signature, authorization, accepted, resource }) {
  if (!isSignature65(signature)) fail("invalid_argument", "Invalid 65-byte EIP-3009 signature.");
  if (!isPlainObject(authorization)) fail("invalid_argument", "authorization must be an object.");
  if (!isPlainObject(accepted)) fail("invalid_argument", "accepted must be the validated v2 requirement object.");
  const a = authorization;
  const acc = {
    scheme: "exact",
    network: BASE_NETWORK_V2,
    amount: String(accepted.amount ?? a.value),
    asset: BASE_USDC,
    payTo: accepted.payTo,
    maxTimeoutSeconds: accepted.maxTimeoutSeconds,
    extra: { name: "USD Coin", version: "2" },
  };
  return Buffer.from(
    JSON.stringify({
      x402Version: 2,
      accepted: acc,
      ...(typeof resource === "string" ? { resource: { url: resource } } : {}),
      payload: {
        signature,
        authorization: {
          from: a.from,
          to: a.to,
          value: String(a.value),
          validAfter: String(a.validAfter),
          validBefore: String(a.validBefore),
          nonce: a.nonce,
        },
      },
    }),
    "utf8"
  ).toString("base64");
}

export function encodeXPaymentHeader({ signature, authorization, network = X402_DEFAULTS.network }) {
  if (!isSignature65(signature)) fail("invalid_argument", "Invalid 65-byte EIP-3009 signature.");
  if (!isPlainObject(authorization)) fail("invalid_argument", "authorization must be an object.");
  const a = authorization;
  return Buffer.from(
    JSON.stringify({
      x402Version: 1,
      scheme: "exact",
      network,
      payload: {
        signature,
        authorization: {
          from: a.from,
          to: a.to,
          value: String(a.value),
          validAfter: String(a.validAfter),
          validBefore: String(a.validBefore),
          nonce: a.nonce,
        },
      },
    }),
    "utf8"
  ).toString("base64");
}

// ---------------------------------------------------------------------------------------------------------------
// Fetch with timeout + bounded body
// ---------------------------------------------------------------------------------------------------------------

const snippet = (text) =>
  String(text ?? "")
    .slice(0, SNIPPET_LENGTH)
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "?");

function abortPromiseFor(signal) {
  const p = new Promise((_, reject) => {
    const onAbort = () => reject(signal.reason ?? Object.assign(new Error("aborted"), { name: "AbortError" }));
    if (signal.aborted) onAbort();
    else signal.addEventListener("abort", onAbort, { once: true });
  });
  p.catch(() => {});
  return p;
}

function classifyFetchError(err, signal, url, timeoutMs) {
  if (err instanceof X402Error) return err;
  if (signal.aborted || err?.name === "TimeoutError" || err?.name === "AbortError") {
    return new X402Error("timeout", `Request timed out after ${timeoutMs} ms (${url}).`, { url, timeoutMs });
  }
  return new X402Error("network_error", `Network error (${url}): ${snippet(err?.message ?? err)}`, { url });
}

async function readBodyText(res, maxBytes) {
  const cl = Number(res.headers?.get?.("content-length"));
  if (Number.isFinite(cl) && cl > maxBytes) {
    throw new X402Error("response_too_large", `Response exceeds ${maxBytes} bytes.`, { status: res.status });
  }
  if (res.body && typeof res.body.getReader === "function") {
    const reader = res.body.getReader();
    const chunks = [];
    let total = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maxBytes) {
        reader.cancel().catch(() => {});
        throw new X402Error("response_too_large", `Response exceeds ${maxBytes} bytes.`, { status: res.status });
      }
      chunks.push(value);
    }
    return new TextDecoder("utf-8").decode(Buffer.concat(chunks.map((c) => Buffer.from(c))));
  }
  if (typeof res.text === "function") {
    const text = await res.text();
    if (Buffer.byteLength(String(text), "utf8") > maxBytes) {
      throw new X402Error("response_too_large", `Response exceeds ${maxBytes} bytes.`, { status: res.status });
    }
    return String(text);
  }
  return "";
}

/**
 * fetch() with AbortSignal.timeout(timeoutMs). The timeout is enforced even if fetchImpl ignores the signal, and
 * also covers reading the body. Throws X402Error timeout / network_error / response_too_large.
 * @returns {Promise<{ res: any, text: string }>}
 */
export async function fetchTextWithTimeout(fetchImpl, url, init = {}, { timeoutMs = DEFAULT_TIMEOUT_MS, maxBytes = MAX_RESPONSE_BYTES } = {}) {
  const ms = resolveTimeoutMs(timeoutMs);
  const signal = AbortSignal.timeout(ms);
  const aborted = abortPromiseFor(signal);
  // AbortSignal.timeout's timer is unref'd; hold a ref'd timer for the same window so a hung fetchImpl cannot let
  // the event loop drain before the timeout fires (which would leave the call pending forever).
  const keepAlive = setTimeout(() => {}, ms + 1000);
  try {
    const res = await Promise.race([fetchImpl(url, { ...init, signal }), aborted]);
    if (!res || typeof res.status !== "number") throw new X402Error("network_error", `Invalid fetch response (${url}).`, { url });
    const text = await Promise.race([readBodyText(res, maxBytes), aborted]);
    return { res, text };
  } catch (err) {
    throw classifyFetchError(err, signal, url, ms);
  } finally {
    clearTimeout(keepAlive);
  }
}

// ---------------------------------------------------------------------------------------------------------------
// Paid resource call
// ---------------------------------------------------------------------------------------------------------------

function assertBaseUrl(baseUrl) {
  if (!baseUrl || typeof baseUrl !== "string") {
    fail(
      "x402_disabled",
      `Paid x402 gateway is disabled by default. Set PACTA_X402_URL=${X402_GATEWAY_URL} to enable paid x402 tools, or use free pacta_list_commitments over https://pacta.wtf/api/v1/index.json.`
    );
  }
  let u;
  try {
    u = new URL(baseUrl);
  } catch {
    fail("invalid_config", "PACTA_X402_URL is not a valid URL.");
  }
  const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(u.hostname);
  if (!(u.protocol === "https:" || (u.protocol === "http:" && loopback))) {
    fail("invalid_config", "PACTA_X402_URL must be https:// (plain http only for localhost).");
  }
  if (u.username || u.password) fail("invalid_config", "PACTA_X402_URL must not embed credentials.");
}

/**
 * Call a paid x402 route (x402 v1 or v2).
 * - Without a payment header: expects 402; returns a challenge built ONLY from a validated accepts[] entry (v1 body
 *   or v2 PAYMENT-REQUIRED header; `x402Version` picks the preferred one, default 1) plus the EIP-712 typedData and
 *   the envelope template for that version (X-PAYMENT for v1, PAYMENT-SIGNATURE for v2).
 * - With xPaymentHeader (v1) or paymentSignatureHeader (v2), never both: validates it locally first (no network on
 *   failure); requires 2xx AND a valid PAYMENT-RESPONSE / X-PAYMENT-RESPONSE receipt on that version's network whose
 *   payer == authorization.from (and payTo / amount, when present, == authorization to / value), else throws
 *   unverified_settlement. The receipt is not checked on-chain (onchainReceiptVerified: false).
 * Throws X402Error on every failure path.
 */
export async function callX402Resource({
  fetchImpl = globalThis.fetch,
  baseUrl,
  routeSpec,
  query = {},
  xPaymentHeader,
  paymentSignatureHeader,
  x402Version,
  payer,
  validBeforeSeconds,
  nonce,
  nowSeconds,
  maxAtomic = DEFAULT_MAX_ATOMIC,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  maxResponseBytes = MAX_RESPONSE_BYTES,
}) {
  assertBaseUrl(baseUrl);
  if (!routeSpec || typeof routeSpec.path !== "string" || parsePositiveAtomic(String(routeSpec.maxAmountRequired)) === null) {
    fail("invalid_config", "Invalid paid route specification.");
  }
  if (payer !== undefined && payer !== null && (!isValidAddress(payer) || sameAddress(payer, ZERO_ADDRESS))) {
    fail("invalid_argument", "payer must be a non-zero 0x address (EIP-55 checksum if mixed-case).");
  }
  if (nonce !== undefined && nonce !== null && !isBytes32(nonce)) fail("invalid_argument", "nonce must be 32-byte 0x hex.");
  if (
    validBeforeSeconds !== undefined &&
    validBeforeSeconds !== null &&
    (!Number.isSafeInteger(validBeforeSeconds) || validBeforeSeconds < 30 || validBeforeSeconds > MAX_TIMEOUT_SECONDS_CEILING)
  ) {
    fail("invalid_argument", `validBeforeSeconds must be an integer in 30..${MAX_TIMEOUT_SECONDS_CEILING}.`);
  }

  if (x402Version !== undefined && x402Version !== null && x402Version !== 1 && x402Version !== 2) {
    fail("invalid_argument", "x402Version must be 1 or 2.");
  }
  const hasV1 = xPaymentHeader !== undefined && xPaymentHeader !== null;
  const hasV2 = paymentSignatureHeader !== undefined && paymentSignatureHeader !== null;
  if (hasV1 && hasV2) fail("invalid_argument", "Send exactly one of xPaymentHeader (x402 v1) and paymentSignatureHeader (x402 v2).");
  const paid = hasV1 || hasV2;

  const url = new URL(routeSpec.path, baseUrl);
  for (const [k, val] of Object.entries(query)) {
    if (val !== undefined && val !== null && val !== "") url.searchParams.set(k, String(val));
  }
  const resource = url.toString();
  const routeUrl = url.origin + url.pathname; // v2 resource binding: no query

  let payment = null;
  if (paid) {
    const v = hasV1
      ? validateXPaymentHeader(xPaymentHeader, { routeMaxAmountRequired: routeSpec.maxAmountRequired, maxAtomic, nowSeconds })
      : validatePaymentSignatureHeader(paymentSignatureHeader, {
          routeMaxAmountRequired: routeSpec.maxAmountRequired,
          maxAtomic,
          nowSeconds,
          expectedResource: resource,
        });
    if (!v.ok) fail(v.error.code, v.error.message, { reason: v.error.reason });
    payment = v.payment;
  }
  const headers = {
    Accept: "application/json",
    ...(hasV1 ? { "X-PAYMENT": xPaymentHeader } : {}),
    ...(hasV2 ? { "PAYMENT-SIGNATURE": paymentSignatureHeader } : {}),
  };

  // redirect: "error" — never let a 3xx carry the X-PAYMENT header (or a challenge) to another origin.
  const { res, text } = await fetchTextWithTimeout(
    fetchImpl,
    resource,
    { method: "GET", headers, redirect: "error" },
    { timeoutMs, maxBytes: maxResponseBytes }
  );
  const status = res.status;
  const ok = status >= 200 && status < 300;

  if (paid) {
    if (!ok) {
      let upstreamError;
      try {
        const j = JSON.parse(text);
        if (isPlainObject(j) && typeof j.error === "string") upstreamError = j.error.slice(0, SNIPPET_LENGTH);
      } catch {}
      fail("unverified_settlement", `Paid request not settled: upstream HTTP ${status}.`, {
        reason: status === 402 ? "payment_rejected" : "upstream_http_error",
        status,
        resource,
        snippet: snippet(text),
        ...(upstreamError ? { upstreamError } : {}),
      });
    }
    const h = (k) => res.headers?.get?.(k) ?? null;
    const rawReceipt = hasV2 ? h("payment-response") ?? h("x-payment-response") : h("x-payment-response") ?? h("payment-response");
    const auth = payment.payload.authorization;
    const rv = validatePaymentReceipt(rawReceipt, {
      expectedPayer: auth.from,
      expectedPayTo: auth.to,
      expectedValue: auth.value,
      network: payment.network,
    });
    if (!rv.ok) {
      fail("unverified_settlement", `Paid response has no valid PAYMENT-RESPONSE / X-PAYMENT-RESPONSE settlement receipt (${rv.reason}); body withheld.`, {
        reason: rv.reason,
        status,
        resource,
      });
    }
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { raw: snippet(text) };
    }
    return {
      status,
      paymentRequired: false,
      paid: true,
      x402Version: payment.x402Version,
      // The receipt is the gateway's header assertion, checked against our authorization. The client does not look
      // the settlement transaction up on Base, so on-chain settlement is NOT independently verified.
      gatewayReceiptVerified: true,
      onchainReceiptVerified: false,
      settlementVerificationScope: "gateway_header_assertion",
      resource,
      paymentReceipt: rv.receipt,
      data,
    };
  }

  if (status === 402) {
    const sel = selectPaymentRequirements({ bodyText: text, headers: res.headers, routeSpec, maxAtomic, resource, preferVersion: x402Version ?? 1 });
    const entry = sel.selected;
    const isV2 = entry.x402Version === 2;
    const ttl = Math.min(validBeforeSeconds ?? 300, entry.maxTimeoutSeconds);
    const eip712TypedData = buildTransferWithAuthorizationTypedData({
      payer: payer || ZERO_ADDRESS,
      payTo: entry.payTo,
      value: isV2 ? entry.amount : entry.maxAmountRequired,
      ttlSeconds: ttl,
      nonce: nonce ?? undefined,
      nowSeconds: nowSecondsOr(nowSeconds),
    });
    return {
      status: 402,
      paymentRequired: true,
      source: "upstream_402",
      resource,
      priceUsdc: routeSpec.priceUsdc,
      x402Version: entry.x402Version,
      availableVersions: sel.availableVersions,
      accepts: [entry],
      ...(sel.alternatives.length ? { alternativeAccepts: sel.alternatives } : {}),
      selectedFrom: sel.selectedFrom,
      rejectedEntries: sel.rejected,
      ...(sel.sourceErrors.length ? { sourceErrors: sel.sourceErrors } : {}),
      validBeforeSecondsApplied: ttl,
      eip712TypedData,
      ...(isV2
        ? {
            paymentSignatureEnvelopeTemplate: {
              headerName: "PAYMENT-SIGNATURE",
              toolArgument: "paymentSignatureHeader",
              encoding: "base64(JSON)",
              jsonShape: {
                x402Version: 2,
                accepted: {
                  scheme: "exact",
                  network: BASE_NETWORK_V2,
                  amount: entry.amount,
                  asset: entry.asset,
                  payTo: entry.payTo,
                  maxTimeoutSeconds: entry.maxTimeoutSeconds,
                  extra: entry.extra,
                },
                resource: { url: routeUrl },
                payload: { signature: "0x<65-byte-signature>", authorization: eip712TypedData.message },
              },
            },
          }
        : {
            xPaymentEnvelopeTemplate: {
              headerName: "X-PAYMENT",
              toolArgument: "xPaymentHeader",
              encoding: "base64(JSON)",
              jsonShape: {
                x402Version: 1,
                scheme: "exact",
                network: "base",
                payload: { signature: "0x<65-byte-signature>", authorization: eip712TypedData.message },
              },
            },
          }),
      ...(sel.upstreamError ? { upstreamError: sel.upstreamError } : {}),
    };
  }

  if (!ok) {
    let upstreamError;
    try {
      const j = JSON.parse(text);
      if (isPlainObject(j)) upstreamError = String(j.error ?? j.message ?? "").slice(0, SNIPPET_LENGTH) || undefined;
    } catch {}
    fail("upstream_http_error", `Upstream HTTP ${status}.`, {
      status,
      resource,
      snippet: snippet(text),
      ...(upstreamError ? { upstreamError } : {}),
    });
  }

  // 2xx without any payment sent: no money moved; returned as unpaid data.
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: snippet(text) };
  }
  return { status, paymentRequired: false, paid: false, resource, paymentReceipt: null, data };
}
