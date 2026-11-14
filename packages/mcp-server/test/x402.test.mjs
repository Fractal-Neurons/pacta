// Adversarial tests for the x402 paid path. No network: every fetch is an injected fetchImpl.
// No real keys/signing: signatures are fixed fake 65-byte hex strings.
import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { createHash, randomBytes } from "node:crypto";
import { keccak256Hex, sha3_256Hex } from "../src/keccak.mjs";
import {
  ALLOWED_PAY_TO,
  BASE_USDC,
  PAID_ROUTES,
  HARD_MAX_ATOMIC,
  X402Error,
  buildTransferWithAuthorizationTypedData,
  callX402Resource,
  decodeStrictBase64Json,
  decodeBase64JsonHeader,
  encodeXPaymentHeader,
  isValidAddress,
  localSpecRequirements,
  parseWwwAuthenticateX402,
  resolveMaxAtomic,
  resolveTimeoutMs,
  toChecksumAddress,
  validateAcceptsEntry,
  validatePaymentReceipt,
  validateXPaymentHeader,
} from "../src/x402.mjs";

const NOW = 1794580000;
const PAYTO = ALLOWED_PAY_TO[0];
const TREASURY = ALLOWED_PAY_TO[1];
const ROGUE = "0x000000000000000000000000000000000000dEaD";
const FROM = "0x" + "11".repeat(20);
const SIG = "0x" + "12".repeat(65); // fixed fake 65-byte signature
const NONCE = "0x" + "cd".repeat(32);
const TX = "0x" + "ef".repeat(32);
const BASE_URL = "https://x402.example.invalid";
const ROUTE = PAID_ROUTES.scanControlPlane; // 100000 atomic
const b64 = (v) => Buffer.from(typeof v === "string" ? v : JSON.stringify(v), "utf8").toString("base64");

const goodAuth = (o = {}) => ({
  from: FROM,
  to: PAYTO,
  value: "100000",
  validAfter: "0",
  validBefore: String(NOW + 300),
  nonce: NONCE,
  ...o,
});
const envelope = (authO = {}, topO = {}) => ({
  x402Version: 1,
  scheme: "exact",
  network: "base",
  payload: { signature: SIG, authorization: goodAuth(authO) },
  ...topO,
});
const XOPTS = { routeMaxAmountRequired: "100000", nowSeconds: NOW };
const xReason = (hdr, opts = XOPTS) => {
  const r = validateXPaymentHeader(hdr, opts);
  assert.equal(r.ok, false, `expected rejection for ${String(hdr).slice(0, 40)}`);
  assert.equal(r.error.code, "invalid_x_payment");
  return r.error.reason;
};

const goodEntry = (o = {}) => ({
  scheme: "exact",
  network: "base",
  maxAmountRequired: "100000",
  resource: `${BASE_URL}${ROUTE.path}`,
  description: "scan",
  mimeType: "application/json",
  payTo: PAYTO,
  maxTimeoutSeconds: 60,
  asset: BASE_USDC,
  extra: { name: "USD Coin", version: "2" },
  ...o,
});
const RESOURCE = `${BASE_URL}${ROUTE.path}`; // the exact URL callX402Resource requests for ROUTE (no query)
const EOPTS = { containerVersion: 1, routeMaxAmountRequired: "100000", expectedResource: RESOURCE };
const eReasons = (entry, opts = EOPTS) => {
  const r = validateAcceptsEntry(entry, opts);
  assert.equal(r.ok, false);
  return r.reasons;
};

const mockRes = (status, body, headers = {}) => {
  const m = new Map(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return { ok: status >= 200 && status < 300, status, headers: { get: (k) => m.get(String(k).toLowerCase()) ?? null }, text: async () => text };
};
const recordingFetch = (responder) => {
  const calls = [];
  const f = async (url, init) => {
    calls.push({ url, init });
    return responder(url, init, calls.length);
  };
  f.calls = calls;
  return f;
};
const noNetwork = recordingFetch(() => {
  throw new Error("network must not be touched");
});
const call = (o) => callX402Resource({ baseUrl: BASE_URL, routeSpec: ROUTE, nowSeconds: NOW, ...o });
async function rejectsWith(promise, code, reason) {
  try {
    await promise;
  } catch (err) {
    assert.ok(err instanceof X402Error, `expected X402Error, got ${err}`);
    assert.equal(err.code, code, err.message);
    if (reason) assert.equal(err.details.reason, reason, err.message);
    return err;
  }
  assert.fail(`expected ${code} rejection`);
}

// ---------------------------------------------------------------------------------------------------------------
// keccak-256 + EIP-55
// ---------------------------------------------------------------------------------------------------------------

test("keccak256 known-answer vectors", () => {
  assert.equal(keccak256Hex(""), "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470");
  assert.equal(keccak256Hex("abc"), "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45");
  assert.equal(
    keccak256Hex("The quick brown fox jumps over the lazy dog"),
    "4d741b6f1eb29cb2a9b9911c82f56fa8d73b04959d3d9d222895df6c0b28aa15"
  );
  // Function selector sanity: keccak256("transfer(address,uint256)")[0:4] = a9059cbb
  assert.equal(keccak256Hex("transfer(address,uint256)").slice(0, 8), "a9059cbb");
});

test("keccak permutation cross-checked against node:crypto sha3-256 across block boundaries", () => {
  for (const n of [0, 1, 55, 135, 136, 137, 271, 272, 273, 1000]) {
    const buf = randomBytes(n);
    assert.equal(sha3_256Hex(buf), createHash("sha3-256").update(buf).digest("hex"), `len ${n}`);
  }
});

test("EIP-55 checksum vectors and bad-checksum rejection", () => {
  const mixed = [
    "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
    "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
    "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB",
    "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb",
    BASE_USDC,
    ...ALLOWED_PAY_TO,
  ];
  for (const a of mixed) {
    assert.equal(toChecksumAddress(a.toLowerCase()), a);
    assert.equal(isValidAddress(a), true);
  }
  assert.equal(isValidAddress("0x52908400098527886E0F7030069857D2E4169EE7"), true); // all-caps: no checksum
  assert.equal(isValidAddress("0xde709f2102306220921060314715629080e2fb77"), true); // all-lower: no checksum
  assert.equal(isValidAddress("0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeD"), false); // last char case flipped
  assert.equal(isValidAddress("0xceCf30B925bf40129794A0810622354f2ACCD515"), false); // known-bad (gateway README)
  assert.equal(isValidAddress("0x123"), false);
});

// ---------------------------------------------------------------------------------------------------------------
// Strict base64 JSON
// ---------------------------------------------------------------------------------------------------------------

test("strict base64: bad chars, URL-safe alphabet, whitespace, padding errors, non-canonical, non-UTF-8, non-JSON", () => {
  const r = (s, o) => decodeStrictBase64Json(s, o).reason;
  assert.deepEqual(decodeStrictBase64Json(b64({ a: 1 })), { ok: true, value: { a: 1 } });
  assert.equal(r(123), "not_string");
  assert.equal(r(""), "empty");
  assert.equal(r("eyJ!!x=="), "bad_base64");
  assert.equal(r("eyJhIjoxfQ-_"), "bad_base64"); // URL-safe alphabet rejected
  assert.equal(r(` ${b64({ a: 1 })}`), "bad_base64"); // no trimming
  assert.equal(r(`${b64({ a: 1 })}\n`), "bad_base64");
  assert.equal(r("QQ="), "bad_base64"); // wrong length
  assert.equal(r("QQ==="), "bad_base64");
  assert.equal(r("Q==="), "bad_base64");
  assert.equal(r("QQ"), "bad_base64"); // missing padding
  assert.equal(r("QQ=A"), "bad_base64"); // padding in the middle
  assert.equal(r("QR=="), "non_canonical_base64"); // non-zero trailing bits
  assert.equal(r(Buffer.from([0xff, 0xfe, 0x7b, 0x7d]).toString("base64")), "bad_utf8");
  assert.equal(r(Buffer.from([0x22, 0xc0, 0xaf, 0x22]).toString("base64")), "bad_utf8"); // overlong encoding
  assert.equal(r(Buffer.from([0x22, 0xed, 0xa0, 0x80, 0x22]).toString("base64")), "bad_utf8"); // lone surrogate
  assert.equal(r(b64("not json")), "bad_json");
  assert.equal(r("A".repeat(20), { maxLength: 16 }), "too_long");
  assert.throws(() => decodeBase64JsonHeader("QR=="), (e) => e.code === "malformed_header" && e.details.reason === "non_canonical_base64");
});

// ---------------------------------------------------------------------------------------------------------------
// X-PAYMENT validation
// ---------------------------------------------------------------------------------------------------------------

test("X-PAYMENT: well-formed envelope is accepted (incl. treasury recipient and encodeXPaymentHeader output)", () => {
  const ok = validateXPaymentHeader(b64(envelope()), XOPTS);
  assert.equal(ok.ok, true);
  assert.equal(ok.payment.payload.authorization.to, PAYTO);
  assert.equal(validateXPaymentHeader(b64(envelope({ to: TREASURY.toLowerCase() })), XOPTS).ok, true);
  const enc = encodeXPaymentHeader({ signature: SIG, authorization: goodAuth() });
  assert.equal(validateXPaymentHeader(enc, XOPTS).ok, true);
});

test("X-PAYMENT: type, size, encoding and JSON-shape rejections", () => {
  assert.equal(xReason(12345), "not_string");
  assert.equal(xReason({ x402Version: 1 }), "not_string");
  assert.equal(xReason(""), "empty");
  assert.equal(xReason("A".repeat(8192 + 4)), "too_long");
  assert.equal(xReason("eyJ4NDAyVmVyc2lvbiI6MX0-"), "bad_base64");
  assert.equal(xReason(b64(envelope()).slice(0, -1)), "bad_base64");
  assert.equal(xReason("QR=="), "non_canonical_base64");
  assert.equal(xReason(Buffer.from([0x7b, 0xff, 0x7d, 0x20]).toString("base64")), "bad_utf8");
  assert.equal(xReason(b64("{not json")), "bad_json");
  for (const v of ["[]", "1", '"str"', "null", "true"]) assert.equal(xReason(b64(v)), "not_object", v);
  assert.equal(xReason(b64(envelope({}, { x402Version: 2 }))), "bad_x402_version");
  assert.equal(xReason(b64(envelope({}, { x402Version: "1" }))), "bad_x402_version");
  assert.equal(xReason(b64(envelope({}, { scheme: "upto" }))), "bad_scheme");
  assert.equal(xReason(b64(envelope({}, { network: "base-sepolia" }))), "bad_network");
  assert.equal(xReason(b64(envelope({}, { extra: 1 }))), "unexpected_field");
  assert.equal(xReason(b64({ ...envelope(), payload: [] })), "bad_payload");
  assert.equal(xReason(b64({ ...envelope(), payload: { signature: "0x" + "12".repeat(64), authorization: goodAuth() } })), "bad_signature");
  assert.equal(xReason(b64({ ...envelope(), payload: { signature: "0x" + "zz".repeat(65), authorization: goodAuth() } })), "bad_signature");
  const missing = goodAuth();
  delete missing.nonce;
  assert.equal(xReason(b64({ ...envelope(), payload: { signature: SIG, authorization: missing } })), "bad_authorization");
  assert.equal(xReason(b64(envelope({ extraField: "x" }))), "bad_authorization");
});

test("X-PAYMENT: rogue / malformed recipients and payers", () => {
  assert.equal(xReason(b64(envelope({ to: ROGUE }))), "recipient_not_allowed");
  assert.equal(xReason(b64(envelope({ to: "0xca4e2ff22b69a7284210c47bdee21aac1269dA09" }))), "bad_checksum");
  assert.equal(xReason(b64(envelope({ to: "0x1234" }))), "bad_to");
  assert.equal(xReason(b64(envelope({ from: "0x0000000000000000000000000000000000000000" }))), "bad_from");
  assert.equal(xReason(b64(envelope({ from: 42 }))), "bad_from");
  assert.equal(xReason(b64(envelope({ from: "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeD" }))), "bad_checksum");
});

test("X-PAYMENT: amounts — non-integer, negative, huge, over cap, over route price", () => {
  for (const v of ["0", "-1", "1.5", "1e5", "0100", " 100", "0x10", "", "9".repeat(79), 100000, null]) {
    assert.equal(xReason(b64(envelope({ value: v }))), "bad_value", String(v));
  }
  assert.equal(xReason(b64(envelope({ value: "100001" }))), "value_over_route_price");
  assert.equal(xReason(b64(envelope({ value: "9".repeat(78) }))), "value_over_cap");
  assert.equal(xReason(b64(envelope({ value: "1000001" })), { nowSeconds: NOW, routeMaxAmountRequired: "5000000" }), "value_over_cap");
  assert.equal(xReason(b64(envelope({ value: "60000" })), { ...XOPTS, maxAtomic: "50000" }), "value_over_cap");
  assert.equal(validateXPaymentHeader(b64(envelope({ value: "99999" })), XOPTS).ok, true);
});

test("X-PAYMENT: validity window — expired, not yet valid, too long, malformed, bad nonce", () => {
  assert.equal(xReason(b64(envelope({ validBefore: String(NOW) }))), "expired");
  assert.equal(xReason(b64(envelope({ validBefore: String(NOW - 1000) }))), "expired");
  assert.equal(xReason(b64(envelope({ validAfter: String(NOW + 10) }))), "not_yet_valid");
  assert.equal(xReason(b64(envelope({ validBefore: String(NOW + 601) }))), "validity_window_too_long");
  assert.equal(xReason(b64(envelope({ validBefore: String(NOW + 86400 * 365) }))), "validity_window_too_long");
  assert.equal(xReason(b64(envelope({ validBefore: String(NOW + 120) })), { ...XOPTS, maxTimeoutSeconds: 60 }), "validity_window_too_long");
  assert.equal(xReason(b64(envelope({ validBefore: NOW + 300 }))), "bad_valid_before");
  assert.equal(xReason(b64(envelope({ validAfter: "-1" }))), "bad_valid_after");
  assert.equal(xReason(b64(envelope({ nonce: "0x1234" }))), "bad_nonce");
  assert.equal(xReason(b64(envelope({ nonce: 7 }))), "bad_nonce");
});

test("invalid X-PAYMENT is rejected before any network call", async () => {
  const f = recordingFetch(() => mockRes(200, {}));
  const err = await rejectsWith(
    call({ fetchImpl: f, xPaymentHeader: b64(envelope({ to: ROGUE })) }),
    "invalid_x_payment",
    "recipient_not_allowed"
  );
  assert.match(JSON.stringify(err), /"code":"invalid_x_payment"/);
  await rejectsWith(call({ fetchImpl: f, xPaymentHeader: "" }), "invalid_x_payment", "empty");
  await rejectsWith(call({ fetchImpl: f, xPaymentHeader: 123 }), "invalid_x_payment", "not_string");
  await rejectsWith(
    call({ fetchImpl: f, routeSpec: PAID_ROUTES.liveTimelocks, xPaymentHeader: b64(envelope({ value: "250000" })) }),
    "invalid_x_payment",
    "value_over_route_price"
  );
  assert.equal(f.calls.length, 0);
});

// ---------------------------------------------------------------------------------------------------------------
// accepts[] entry validation
// ---------------------------------------------------------------------------------------------------------------

test("accepts[]: good entry normalizes to pinned constants", () => {
  const r = validateAcceptsEntry(goodEntry({ payTo: PAYTO.toLowerCase(), asset: BASE_USDC.toLowerCase(), chainId: 8453 }), EOPTS);
  assert.equal(r.ok, true);
  assert.equal(r.entry.payTo, PAYTO);
  assert.equal(r.entry.asset, BASE_USDC);
  assert.equal(r.entry.chainId, 8453);
  assert.equal(validateAcceptsEntry(goodEntry({ chainId: "eip155:8453" }), EOPTS).ok, true);
  assert.equal(validateAcceptsEntry(goodEntry({ x402Version: 1 }), { routeMaxAmountRequired: "100000", expectedResource: RESOURCE }).ok, true);
  assert.equal(r.entry.resource, RESOURCE);
});

test("accepts[]: rogue payTo, wrong asset, wrong network, chainId != 8453, bad checksum", () => {
  assert.deepEqual(eReasons(goodEntry({ payTo: ROGUE })), ["pay_to_not_allowed"]);
  assert.deepEqual(eReasons(goodEntry({ payTo: "0xca4e2ff22b69a7284210c47bdee21aac1269dA09" })), ["bad_pay_to_checksum"]);
  assert.deepEqual(eReasons(goodEntry({ payTo: undefined })), ["bad_pay_to"]);
  assert.deepEqual(eReasons(goodEntry({ asset: "0x036CbD53842c5426634e7929541eC2318f3dCF7e" })), ["bad_asset"]); // Base Sepolia USDC
  assert.deepEqual(eReasons(goodEntry({ asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913".replace("fC", "Fc") })), ["bad_asset_checksum"]);
  assert.deepEqual(eReasons(goodEntry({ network: "ethereum" })), ["bad_network"]);
  assert.deepEqual(eReasons(goodEntry({ network: "base-sepolia" })), ["bad_network"]);
  assert.deepEqual(eReasons(goodEntry({ chainId: 1 })), ["bad_chain_id"]);
  assert.deepEqual(eReasons(goodEntry({ chainId: "84532" })), ["bad_chain_id"]);
  assert.deepEqual(eReasons(goodEntry({ extra: { name: "USD Coin", version: "2", chainId: 1 } })), ["bad_chain_id"]);
  assert.deepEqual(eReasons(goodEntry({ scheme: "upto" })), ["bad_scheme"]);
  // a v1-shaped entry inside a v2 container is judged by v2 rules: wrong network name, no `amount`
  assert.deepEqual(eReasons(goodEntry(), { ...EOPTS, containerVersion: 2 }), ["bad_network", "bad_amount"]);
  assert.deepEqual(eReasons(goodEntry(), { ...EOPTS, containerVersion: 3 }), ["bad_x402_version"]);
  assert.deepEqual(eReasons(goodEntry(), { routeMaxAmountRequired: "100000", expectedResource: RESOURCE }), ["bad_x402_version"]); // version missing
  assert.deepEqual(eReasons(goodEntry({ extra: { name: "USDC", version: "2" } })), ["bad_extra"]);
  assert.deepEqual(eReasons(goodEntry({ extra: undefined })), ["bad_extra"]);
  assert.deepEqual(eReasons("nope"), ["not_object"]);
  assert.deepEqual(eReasons(null), ["not_object"]);
  assert.deepEqual(eReasons([goodEntry()]), ["not_object"]);
});

test("accepts[]: amount over cap / over route price / non-integer / negative / huge; maxTimeoutSeconds bounds", () => {
  assert.deepEqual(eReasons(goodEntry({ maxAmountRequired: "100001" })), ["amount_over_route_price"]);
  assert.deepEqual(eReasons(goodEntry({ maxAmountRequired: "1000001" })), ["amount_over_cap", "amount_over_route_price"]);
  assert.deepEqual(eReasons(goodEntry({ maxAmountRequired: "100000" }), { ...EOPTS, maxAtomic: "50000" }), ["amount_over_cap"]);
  for (const v of ["0", "-100000", "100000.0", "1e5", 100000, "", "abc", "9".repeat(80), "0x186a0"]) {
    assert.deepEqual(eReasons(goodEntry({ maxAmountRequired: v })), ["bad_amount"], String(v));
  }
  for (const t of [0, -1, 601, 1.5, "60", undefined, Number.MAX_SAFE_INTEGER + 2]) {
    assert.deepEqual(eReasons(goodEntry({ maxTimeoutSeconds: t })), ["bad_max_timeout"], String(t));
  }
  // every reason is reported, not just the first
  const all = eReasons(goodEntry({ payTo: ROGUE, asset: ROGUE, network: "x", maxAmountRequired: "-1" }));
  assert.deepEqual(all, ["bad_network", "bad_asset", "pay_to_not_allowed", "bad_amount"]);
});

test("local_spec requirements pass the same validator and are labelled", () => {
  for (const r of Object.values(PAID_ROUTES)) {
    const ls = localSpecRequirements(r, `${BASE_URL}${r.path}`);
    assert.equal(ls.source, "local_spec");
    assert.equal(ls.valid, true);
    assert.equal(ls.entry.maxAmountRequired, r.maxAmountRequired);
  }
  const rogue = localSpecRequirements({ ...ROUTE, payTo: ROGUE }, "x");
  assert.deepEqual(rogue, { source: "local_spec", valid: false, reasons: ["pay_to_not_allowed"] });
});

// ---------------------------------------------------------------------------------------------------------------
// Spoofed 402 responses
// ---------------------------------------------------------------------------------------------------------------

test("spoofed 402 with mixed good/bad entries: only the good entry is selected and signed for", async () => {
  const accepts = [
    goodEntry({ payTo: ROGUE }),
    goodEntry({ asset: "0x" + "ab".repeat(20) }),
    goodEntry({ maxAmountRequired: "99000000" }),
    goodEntry({ network: "base-sepolia" }),
    goodEntry({ chainId: 1 }),
    goodEntry({ payTo: TREASURY, maxAmountRequired: "100000" }),
    goodEntry(), // also valid, but the first valid one wins
  ];
  const f = recordingFetch(() => mockRes(402, { x402Version: 1, error: "X-PAYMENT header is required", accepts }));
  const c = await call({ fetchImpl: f, payer: FROM, nonce: NONCE });
  assert.equal(c.status, 402);
  assert.equal(c.source, "upstream_402");
  assert.deepEqual(c.selectedFrom, { source: "body", index: 5 });
  assert.equal(c.accepts.length, 1);
  assert.equal(c.accepts[0].payTo, TREASURY);
  assert.deepEqual(
    c.rejectedEntries.map((e) => e.reasons),
    [["pay_to_not_allowed"], ["bad_asset"], ["amount_over_cap", "amount_over_route_price"], ["bad_network"], ["bad_chain_id"]]
  );
  assert.deepEqual(c.eip712TypedData.domain, { name: "USD Coin", version: "2", chainId: 8453, verifyingContract: BASE_USDC });
  assert.equal(c.eip712TypedData.message.to, TREASURY);
  assert.equal(c.eip712TypedData.message.value, "100000");
  assert.equal(c.eip712TypedData.message.from, FROM);
  assert.equal(c.eip712TypedData.message.validBefore, String(NOW + 60)); // clamped to entry maxTimeoutSeconds
  assert.equal(c.validBeforeSecondsApplied, 60);
  assert.equal(c.upstreamError, "X-PAYMENT header is required");
  assert.ok(!JSON.stringify(c).toLowerCase().includes(ROGUE.toLowerCase().slice(2)));
});

test("spoofed 402 with only bad entries is rejected with per-entry reasons; no typedData, no list[0] fallback", async () => {
  const accepts = [goodEntry({ payTo: ROGUE }), goodEntry({ maxAmountRequired: "100001" }), "garbage", null];
  const f = recordingFetch(() => mockRes(402, { x402Version: 1, accepts }));
  const err = await rejectsWith(call({ fetchImpl: f }), "rejected_challenge");
  assert.equal(err.details.status, 402);
  assert.deepEqual(
    err.details.entries.map((e) => [e.source, e.index, e.reasons]),
    [
      ["body", 0, ["pay_to_not_allowed"]],
      ["body", 1, ["amount_over_route_price"]],
      ["body", 2, ["not_object"]],
      ["body", 3, ["not_object"]],
    ]
  );
  assert.equal(JSON.stringify(err).includes("eip712TypedData"), false);
});

test("402 with no usable accepts (empty, non-JSON, accepts not array) is rejected", async () => {
  for (const body of ["", "<html>pay me</html>", { x402Version: 1 }, { x402Version: 1, accepts: {} }, { x402Version: 1, accepts: [] }]) {
    const err = await rejectsWith(call({ fetchImpl: async () => mockRes(402, body) }), "rejected_challenge");
    assert.deepEqual(err.details.entries, []);
  }
});

test("402 via base64 Payment-Required / X-Payment-Required headers and WWW-Authenticate; malformed headers reported", async () => {
  const hdrChallenge = b64({ x402Version: 1, accepts: [goodEntry()] });
  const viaPR = await call({ fetchImpl: async () => mockRes(402, "", { "Payment-Required": hdrChallenge }) });
  assert.deepEqual(viaPR.selectedFrom, { source: "payment-required", index: 0 });

  const viaXPR = await call({
    fetchImpl: async () =>
      mockRes(402, { x402Version: 1, accepts: [goodEntry({ payTo: ROGUE })] }, { "X-Payment-Required": hdrChallenge }),
  });
  assert.deepEqual(viaXPR.selectedFrom, { source: "x-payment-required", index: 0 });
  assert.deepEqual(viaXPR.rejectedEntries, [{ source: "body", index: 0, reasons: ["pay_to_not_allowed"] }]);

  const viaWww = await call({ fetchImpl: async () => mockRes(402, "", { "WWW-Authenticate": `x402 accepts="${hdrChallenge}"` }) });
  assert.deepEqual(viaWww.selectedFrom, { source: "www-authenticate", index: 0 });
  const viaToken68 = await call({ fetchImpl: async () => mockRes(402, "", { "WWW-Authenticate": `X402 ${hdrChallenge}` }) });
  assert.equal(viaToken68.accepts[0].payTo, PAYTO);

  const err = await rejectsWith(
    call({ fetchImpl: async () => mockRes(402, "", { "Payment-Required": "QR==", "WWW-Authenticate": 'Bearer realm="x"' }) }),
    "rejected_challenge"
  );
  assert.deepEqual(err.details.sourceErrors, [{ source: "payment-required", reason: "non_canonical_base64" }]);

  const rogueHdr = b64({ x402Version: 1, accepts: [goodEntry({ payTo: ROGUE })] });
  await rejectsWith(call({ fetchImpl: async () => mockRes(402, "", { "WWW-Authenticate": `x402 ${rogueHdr}` }) }), "rejected_challenge");
  assert.equal(parseWwwAuthenticateX402('Basic realm="x402"'), null);
  assert.deepEqual(parseWwwAuthenticateX402("x402 realm=foo"), { ok: false, reason: "no_x402_param" });
});

test("typedData builder refuses non-allowlisted payTo, non-Base domain, oversized value, bad TTL", () => {
  const base = { payTo: PAYTO, value: "100000", nonce: NONCE, nowSeconds: NOW };
  assert.equal(buildTransferWithAuthorizationTypedData(base).message.validBefore, String(NOW + 300));
  const bad = (o) => assert.throws(() => buildTransferWithAuthorizationTypedData({ ...base, ...o }), (e) => e.code === "invalid_argument");
  bad({ payTo: ROGUE });
  bad({ chainId: 1 });
  bad({ verifyingContract: "0x036CbD53842c5426634e7929541eC2318f3dCF7e" });
  bad({ tokenName: "USDC" });
  bad({ tokenVersion: "1" });
  bad({ value: String(BigInt(HARD_MAX_ATOMIC) + 1n) });
  bad({ value: "-1" });
  bad({ ttlSeconds: 86400 });
  bad({ payer: "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeD" });
});

test("paid-tool argument validation (payer, nonce, validBeforeSeconds) happens before network", async () => {
  await rejectsWith(call({ fetchImpl: noNetwork, payer: "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeD" }), "invalid_argument");
  await rejectsWith(call({ fetchImpl: noNetwork, nonce: "0x12" }), "invalid_argument");
  await rejectsWith(call({ fetchImpl: noNetwork, validBeforeSeconds: 86400 }), "invalid_argument");
  await rejectsWith(call({ fetchImpl: noNetwork, validBeforeSeconds: 10 }), "invalid_argument");
  assert.equal(noNetwork.calls.length, 0);
});

// ---------------------------------------------------------------------------------------------------------------
// Timeouts and transport errors
// ---------------------------------------------------------------------------------------------------------------

test("every paid fetch carries an AbortSignal and redirect: error", async () => {
  const f = recordingFetch(() => mockRes(402, { x402Version: 1, accepts: [goodEntry()] }));
  await call({ fetchImpl: f });
  assert.ok(f.calls[0].init.signal instanceof AbortSignal);
  assert.equal(f.calls[0].init.redirect, "error");
  assert.equal(f.calls[0].init.headers["X-PAYMENT"], undefined);
});

test("timeout via a fetchImpl that honours the abort signal -> structured timeout", async () => {
  const honouring = (_u, init) =>
    new Promise((_, reject) => init.signal.addEventListener("abort", () => reject(init.signal.reason), { once: true }));
  const err = await rejectsWith(call({ fetchImpl: honouring, timeoutMs: 25 }), "timeout");
  assert.equal(err.details.timeoutMs, 25);
  // Paid path too:
  await rejectsWith(call({ fetchImpl: honouring, timeoutMs: 25, xPaymentHeader: b64(envelope()) }), "timeout");
});

test("timeout enforced even if fetchImpl ignores the signal, and while reading the body", async () => {
  await rejectsWith(call({ fetchImpl: () => new Promise(() => {}), timeoutMs: 25 }), "timeout");
  const slowBody = async () => ({ status: 200, headers: { get: () => null }, text: () => new Promise(() => {}) });
  await rejectsWith(call({ fetchImpl: slowBody, timeoutMs: 25 }), "timeout");
});

test("network error -> structured network_error; no fabricated offline challenge", async () => {
  const boom = async () => {
    throw new TypeError("fetch failed");
  };
  const err = await rejectsWith(call({ fetchImpl: boom }), "network_error");
  assert.match(err.message, /fetch failed/);
  assert.equal("eip712TypedData" in err.details, false);
  await rejectsWith(call({ fetchImpl: boom, xPaymentHeader: b64(envelope()) }), "network_error");
});

test("resolveTimeoutMs / resolveMaxAtomic bounds", () => {
  assert.equal(resolveTimeoutMs(undefined), 8000);
  assert.equal(resolveTimeoutMs("1500"), 1500);
  assert.equal(resolveTimeoutMs("abc"), 8000);
  assert.equal(resolveTimeoutMs(10 ** 9), 60000);
  assert.equal(resolveMaxAtomic(undefined).maxAtomic, 1000000n);
  assert.equal(resolveMaxAtomic("50000").maxAtomic, 50000n);
  assert.equal(resolveMaxAtomic("99999999").maxAtomic, 5000000n);
  assert.match(resolveMaxAtomic("99999999").warning, /clamped/);
  assert.equal(resolveMaxAtomic("1e9").maxAtomic, 1000000n);
  assert.equal(resolveMaxAtomic("-5").maxAtomic, 1000000n);
});

test("non-https PACTA_X402_URL refused (http only for localhost); disabled when unset", async () => {
  await rejectsWith(call({ fetchImpl: noNetwork, baseUrl: "http://x402.example.invalid" }), "invalid_config");
  await rejectsWith(call({ fetchImpl: noNetwork, baseUrl: "https://user:pw@example.invalid" }), "invalid_config");
  await rejectsWith(call({ fetchImpl: noNetwork, baseUrl: "not a url" }), "invalid_config");
  const e = await rejectsWith(call({ fetchImpl: noNetwork, baseUrl: null }), "x402_disabled");
  assert.match(e.message, /PACTA_X402_URL/);
  const local = await call({
    baseUrl: "http://localhost:8787",
    fetchImpl: async () => mockRes(402, { x402Version: 1, accepts: [goodEntry({ resource: `http://localhost:8787${ROUTE.path}` })] }),
  });
  assert.equal(local.status, 402);
  assert.equal(noNetwork.calls.length, 0);
});

// ---------------------------------------------------------------------------------------------------------------
// Settlement verification
// ---------------------------------------------------------------------------------------------------------------

const receipt = (o = {}) => b64({ success: true, transaction: TX, network: "base", payer: FROM, ...o });

test("end-to-end: 402 -> typedData -> caller-supplied X-PAYMENT -> 200 with valid receipt accepted", async () => {
  let seenHeader;
  const f = recordingFetch((_u, init) => {
    seenHeader = init.headers["X-PAYMENT"];
    if (!seenHeader) return mockRes(402, { x402Version: 1, accepts: [goodEntry()] });
    return mockRes(200, { result: "scan" }, { "X-PAYMENT-RESPONSE": receipt({ payer: FROM.toUpperCase().replace("0X", "0x") }) });
  });
  const challenge = await call({ fetchImpl: f, payer: FROM, nonce: NONCE });
  const xPaymentHeader = encodeXPaymentHeader({ signature: SIG, authorization: challenge.eip712TypedData.message });
  const paid = await call({ fetchImpl: f, xPaymentHeader, nowSeconds: NOW + 5 });
  assert.equal(seenHeader, xPaymentHeader);
  assert.equal(paid.paid, true);
  assert.equal(paid.gatewayReceiptVerified, true);
  assert.equal(paid.onchainReceiptVerified, false);
  assert.equal(paid.settlementVerificationScope, "gateway_header_assertion");
  assert.equal("settlementVerified" in paid, false);
  assert.equal(paid.paymentReceipt.transaction, TX);
  assert.deepEqual(paid.data, { result: "scan" });
  assert.equal(f.calls.length, 2);
});

test("200 after X-PAYMENT without / with bad receipt -> unverified_settlement, body withheld", async () => {
  const cases = [
    [{}, "missing_receipt"],
    [{ "X-PAYMENT-RESPONSE": "QR==" }, "receipt_non_canonical_base64"],
    [{ "X-PAYMENT-RESPONSE": "%%%" }, "receipt_bad_base64"],
    [{ "X-PAYMENT-RESPONSE": b64("[1]") }, "receipt_not_object"],
    [{ "X-PAYMENT-RESPONSE": receipt({ success: false }) }, "receipt_not_success"],
    [{ "X-PAYMENT-RESPONSE": receipt({ success: "true" }) }, "receipt_not_success"],
    [{ "X-PAYMENT-RESPONSE": receipt({ network: "base-sepolia" }) }, "receipt_bad_network"],
    [{ "X-PAYMENT-RESPONSE": receipt({ transaction: "0x1234" }) }, "receipt_bad_transaction"],
    [{ "X-PAYMENT-RESPONSE": receipt({ transaction: "0x" + "00".repeat(32) }) }, "receipt_bad_transaction"],
    [{ "X-PAYMENT-RESPONSE": receipt({ transaction: undefined, tx: TX }) }, "receipt_bad_transaction"],
    [{ "X-PAYMENT-RESPONSE": receipt({ payer: undefined }) }, "receipt_missing_payer"],
    [{ "X-PAYMENT-RESPONSE": receipt({ payer: "nope" }) }, "receipt_bad_payer"],
    [{ "X-PAYMENT-RESPONSE": receipt({ payer: "0x" + "22".repeat(20) }) }, "receipt_payer_mismatch"],
  ];
  for (const [headers, reason] of cases) {
    const f = async () => mockRes(200, { secret_paid_body: true }, headers);
    const err = await rejectsWith(call({ fetchImpl: f, xPaymentHeader: b64(envelope()) }), "unverified_settlement", reason);
    assert.equal(JSON.stringify(err).includes("secret_paid_body"), false, reason);
  }
  assert.equal(validatePaymentReceipt(receipt(), { expectedPayer: FROM }).ok, true);
});

test("paid request answered with 402/4xx/5xx -> unverified_settlement carrying status + bounded snippet", async () => {
  const e402 = await rejectsWith(
    call({ fetchImpl: async () => mockRes(402, { x402Version: 1, error: "invalid_exact_evm_payload_signature", accepts: [goodEntry()] }), xPaymentHeader: b64(envelope()) }),
    "unverified_settlement",
    "payment_rejected"
  );
  assert.equal(e402.details.status, 402);
  assert.equal(e402.details.upstreamError, "invalid_exact_evm_payload_signature");
  const e502 = await rejectsWith(
    call({ fetchImpl: async () => mockRes(502, { error: "facilitator_unavailable", detail: "x".repeat(5000), settled: false }), xPaymentHeader: b64(envelope()) }),
    "unverified_settlement",
    "upstream_http_error"
  );
  assert.equal(e502.details.status, 502);
  assert.ok(e502.details.snippet.length <= 300);
  assert.equal(e502.details.upstreamError, "facilitator_unavailable");
});

test("unpaid 4xx/5xx propagated as upstream_http_error with status + bounded snippet", async () => {
  for (const status of [400, 404, 422, 500, 503]) {
    const err = await rejectsWith(call({ fetchImpl: async () => mockRes(status, "E".repeat(10000)) }), "upstream_http_error");
    assert.equal(err.details.status, status);
    assert.equal(err.details.snippet.length, 300);
  }
  const j = await rejectsWith(call({ fetchImpl: async () => mockRes(503, { error: "payments_disabled" }) }), "upstream_http_error");
  assert.equal(j.details.upstreamError, "payments_disabled");
  const redirect = await rejectsWith(call({ fetchImpl: async () => mockRes(302, "") }), "upstream_http_error");
  assert.equal(redirect.details.status, 302);
});

test("oversized responses are refused (content-length and streamed body)", async () => {
  await rejectsWith(
    call({ fetchImpl: async () => mockRes(402, "x", { "content-length": String(10 * 1024 * 1024) }) }),
    "response_too_large"
  );
  await rejectsWith(call({ fetchImpl: async () => mockRes(200, "y".repeat(5000)), maxResponseBytes: 1000 }), "response_too_large");
  const streamed = async () => new Response(new Uint8Array(3000), { status: 200 });
  await rejectsWith(call({ fetchImpl: streamed, maxResponseBytes: 1000 }), "response_too_large");
});

// ---------------------------------------------------------------------------------------------------------------
// Resource binding (accepts[].resource must name the exact requested URL: same origin + pathname)
// ---------------------------------------------------------------------------------------------------------------

test("resource binding: unrelated origin and other route on the same gateway are rejected; matching resource passes", async () => {
  const GW = "https://gateway.invalid";
  const requested = `${GW}/v1/scan/control-plane`;
  const scan = (resource, extra = {}) =>
    callX402Resource({
      baseUrl: GW,
      routeSpec: ROUTE,
      nowSeconds: NOW,
      query: { chain: "base", address: PAYTO },
      payer: FROM,
      nonce: NONCE,
      fetchImpl: async () => mockRes(402, { x402Version: 1, accepts: [goodEntry({ resource, ...extra })] }),
    });
  assert.equal(ROUTE.path, "/v1/scan/control-plane");

  // Valid Base USDC + allowlisted payTo + in-price, but bound to an unrelated origin.
  const e1 = await rejectsWith(scan("https://unrelated.invalid/other"), "rejected_challenge");
  assert.deepEqual(e1.details.entries, [{ source: "body", index: 0, reasons: ["resource_origin_mismatch", "resource_path_mismatch"] }]);
  assert.equal(JSON.stringify(e1).includes("eip712TypedData"), false);
  assert.equal(JSON.stringify(e1).includes("unrelated.invalid"), false, "rogue resource never echoed");

  // Same gateway, different route.
  const e2 = await rejectsWith(scan(`${GW}/v1/other-route`), "rejected_challenge");
  assert.deepEqual(e2.details.entries[0].reasons, ["resource_path_mismatch"]);
  // Same path on another origin / scheme / port.
  for (const r of ["https://evil.invalid/v1/scan/control-plane", "http://gateway.invalid/v1/scan/control-plane", "https://gateway.invalid:8443/v1/scan/control-plane"]) {
    const e = await rejectsWith(scan(r), "rejected_challenge");
    assert.deepEqual(e.details.entries[0].reasons, ["resource_origin_mismatch"], r);
  }
  // Relative resources resolve against the request origin.
  await rejectsWith(scan("/v1/other-route"), "rejected_challenge");
  await rejectsWith(scan("//unrelated.invalid/v1/scan/control-plane"), "rejected_challenge");
  // Garbage resources.
  for (const r of [42, "", "javascript:alert(1)", "x".repeat(3000)]) {
    const e = await rejectsWith(scan(r), "rejected_challenge");
    assert.deepEqual(e.details.entries[0].reasons, ["bad_resource"], String(r).slice(0, 20));
  }

  // Matching resource passes: absolute with or without query, relative path, or absent.
  for (const r of [requested, `${requested}?chain=base&address=${PAYTO}`, `${requested}?other=1`, "/v1/scan/control-plane", undefined]) {
    const c = await scan(r);
    assert.equal(c.status, 402, String(r));
    // Output/typedData carry only the URL we requested, never the upstream string.
    assert.equal(c.accepts[0].resource, c.resource);
    assert.equal(c.resource, `${requested}?chain=base&address=${PAYTO}`);
    assert.equal(c.eip712TypedData.message.to, PAYTO);
  }
});

test("resource binding: the first bound entry wins over earlier unbound ones; validator requires expectedResource", async () => {
  const accepts = [goodEntry({ resource: "https://unrelated.invalid/other" }), goodEntry({ payTo: TREASURY })];
  const c = await call({ fetchImpl: async () => mockRes(402, { x402Version: 1, accepts }), payer: FROM, nonce: NONCE });
  assert.deepEqual(c.selectedFrom, { source: "body", index: 1 });
  assert.equal(c.accepts[0].payTo, TREASURY);
  assert.deepEqual(c.rejectedEntries[0].reasons, ["resource_origin_mismatch", "resource_path_mismatch"]);

  assert.deepEqual(eReasons(goodEntry(), { containerVersion: 1, routeMaxAmountRequired: "100000" }), ["missing_expected_resource"]);
  assert.deepEqual(eReasons(goodEntry(), { ...EOPTS, expectedResource: "/v1/scan/control-plane" }), ["missing_expected_resource"]);
  assert.deepEqual(eReasons(goodEntry({ resource: `${BASE_URL}/v1/other` })), ["resource_path_mismatch"]);
});

// ---------------------------------------------------------------------------------------------------------------
// Receipt scoping (payTo / amount cross-checked against the authorization when present)
// ---------------------------------------------------------------------------------------------------------------

test("receipt payTo / recipient / to and amount / value must match the authorization when present", async () => {
  const OTHER_ALLOWED = TREASURY; // allowlisted, but not the authorization's `to`
  const bad = [
    [{ payTo: ROGUE }, "receipt_pay_to_mismatch"],
    [{ payTo: OTHER_ALLOWED }, "receipt_pay_to_mismatch"],
    [{ recipient: ROGUE }, "receipt_pay_to_mismatch"],
    [{ to: OTHER_ALLOWED }, "receipt_pay_to_mismatch"],
    [{ payTo: PAYTO, to: ROGUE }, "receipt_pay_to_mismatch"],
    [{ payTo: "nope" }, "receipt_bad_pay_to"],
    [{ to: "0xca4e2ff22b69a7284210c47bdee21aac1269dA09" }, "receipt_bad_pay_to"], // bad EIP-55 checksum
    [{ amount: "100001" }, "receipt_amount_mismatch"],
    [{ value: "1" }, "receipt_amount_mismatch"],
    [{ amount: 99999 }, "receipt_amount_mismatch"],
    [{ amount: "100000", value: "250000" }, "receipt_amount_mismatch"],
    [{ amount: "1e5" }, "receipt_bad_amount"],
    [{ amount: "-100000" }, "receipt_bad_amount"],
    [{ value: "" }, "receipt_bad_amount"],
    [{ amount: 1.5 }, "receipt_bad_amount"],
  ];
  for (const [o, reason] of bad) {
    const f = async () => mockRes(200, { secret_paid_body: true }, { "X-PAYMENT-RESPONSE": receipt(o) });
    const err = await rejectsWith(call({ fetchImpl: f, xPaymentHeader: b64(envelope()) }), "unverified_settlement", reason);
    assert.equal(JSON.stringify(err).includes("secret_paid_body"), false, reason);
  }

  for (const o of [{}, { payTo: PAYTO.toLowerCase(), amount: "100000" }, { to: PAYTO, value: 100000 }, { recipient: PAYTO, payTo: PAYTO }]) {
    const f = async () => mockRes(200, { ok: 1 }, { "X-PAYMENT-RESPONSE": receipt(o) });
    const paid = await call({ fetchImpl: f, xPaymentHeader: b64(envelope()) });
    assert.equal(paid.gatewayReceiptVerified, true, JSON.stringify(o));
    assert.equal(paid.onchainReceiptVerified, false);
    assert.equal(paid.settlementVerificationScope, "gateway_header_assertion");
    if (Object.keys(o).length) assert.equal(paid.paymentReceipt.payTo, PAYTO);
    if (o.amount || o.value) assert.equal(paid.paymentReceipt.amount, "100000");
  }

  // Direct validator: explicit expectations, and allowlist fallback when no expected payTo is given.
  const ok = validatePaymentReceipt(receipt({ payTo: PAYTO, amount: "100000" }), { expectedPayer: FROM, expectedPayTo: PAYTO, expectedValue: "100000" });
  assert.deepEqual(ok, { ok: true, receipt: { success: true, network: "base", transaction: TX, payer: FROM, payTo: PAYTO, amount: "100000" } });
  assert.equal(validatePaymentReceipt(receipt({ payTo: ROGUE }), { expectedPayer: FROM }).reason, "receipt_pay_to_mismatch");
  assert.equal(validatePaymentReceipt(receipt({ payTo: TREASURY }), { expectedPayer: FROM }).ok, true);
});
