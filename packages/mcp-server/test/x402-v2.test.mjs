// x402 v2 (eip155:8453, PAYMENT-REQUIRED / PAYMENT-SIGNATURE / PAYMENT-RESPONSE) and pacta_scan_proposal_diff.
// No network: every fetch is an injected fetchImpl that mimics the live Worker's wire format (body = v1, header = v2).
// No real keys/signing: signatures are fixed fake 65-byte hex strings.
import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import {
  ALLOWED_PAY_TO,
  BASE_NETWORK_V2,
  BASE_USDC,
  PAID_ROUTES,
  X402_DEFAULTS,
  callX402Resource,
  encodePaymentSignatureHeader,
  selectPaymentRequirements,
  validateAcceptsEntry,
  validatePaymentReceipt,
  validatePaymentSignatureHeader,
} from "../src/x402.mjs";
import { PactaMcpServer, PAID_TOOLS, FREE_TOOLS, TOOL_ALIASES, TOOL_DEFINITIONS, canonicalToolName, REQUESTER_ROLES, CALLER_PURPOSES,
  normalizeCallerAgent } from "../src/server.mjs";
import { CALLER } from "./helpers.mjs";
// unpaid gateway calls forward the caller fields as optional REST query params; paid calls are sent unchanged
const CQ = "&caller_agent=pacta-test-agent&requester_role=defi_developer&caller_purpose=integration_testing";
const CALLER_REQ = ["caller_agent", "requester_role", "caller_purpose"];

const NOW = 1794580000;
const PAYTO = ALLOWED_PAY_TO[0];
const ROGUE = "0x000000000000000000000000000000000000dEaD";
const FROM = "0x" + "11".repeat(20);
const SIG = "0x" + "12".repeat(65);
const NONCE = "0x" + "cd".repeat(32);
const TX = "0x" + "ef".repeat(32);
const BASE_URL = "https://x402.example.invalid";
const b64 = (v) => Buffer.from(typeof v === "string" ? v : JSON.stringify(v), "utf8").toString("base64");
const unb64 = (s) => JSON.parse(Buffer.from(s, "base64").toString("utf8"));
const EXTRA = { name: "USD Coin", version: "2" };

const v1Req = (route, url, o = {}) => ({
  scheme: "exact", network: "base", maxAmountRequired: route.maxAmountRequired, resource: url, description: route.description,
  mimeType: "application/json", payTo: PAYTO, maxTimeoutSeconds: 60, asset: BASE_USDC, extra: EXTRA, ...o,
});
const v2Req = (route, o = {}) => ({
  scheme: "exact", network: BASE_NETWORK_V2, amount: route.maxAmountRequired, asset: BASE_USDC, payTo: PAYTO,
  maxTimeoutSeconds: 60, extra: EXTRA, ...o,
});
/** A 402 exactly as the live Worker sends it: v1 JSON body + base64 v2 PaymentRequired in PAYMENT-REQUIRED. */
function worker402(route, url, { v1 = {}, v2 = {}, v2Container = {}, bazaar = true } = {}) {
  const body = { x402Version: 1, error: "Payment required", accepts: [v1Req(route, url, v1)], extensions: { bazaar: { info: {} } } };
  const header = {
    x402Version: 2, error: "Payment required", resource: { url, description: route.description, mimeType: "application/json" },
    accepts: [v2Req(route, v2)], ...(bazaar ? { extensions: { bazaar: { info: {}, schema: { $schema: "https://json-schema.org/draft/2020-12/schema" } } } } : {}),
    ...v2Container,
  };
  return { body, header };
}
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
const auth = (o = {}) => ({ from: FROM, to: PAYTO, value: "100000", validAfter: "0", validBefore: String(NOW + 50), nonce: NONCE, ...o });
const v2Payment = (route, { shape = "accepted", top = {}, accepted = {}, authO = {}, resource } = {}) => {
  const p = { x402Version: 2, payload: { signature: SIG, authorization: auth({ value: route.maxAmountRequired, ...authO }) }, ...top };
  if (shape === "accepted" || shape === "both") p.accepted = { ...v2Req(route), ...accepted };
  if (shape === "top" || shape === "both") Object.assign(p, { scheme: "exact", network: BASE_NETWORK_V2 }, top);
  if (resource !== undefined) p.resource = resource;
  return p;
};
const receipt = (o = {}) => b64({ success: true, transaction: TX, network: BASE_NETWORK_V2, payer: FROM, ...o });

test("X402_DEFAULTS and PAID_ROUTES advertise v1 + v2 and all 6 live Worker routes", () => {
  assert.deepEqual(X402_DEFAULTS.x402Versions, [1, 2]);
  assert.deepEqual(X402_DEFAULTS.networks, ["base", "eip155:8453"]);
  assert.deepEqual(X402_DEFAULTS.paymentHeaders, { 1: "X-PAYMENT", 2: "PAYMENT-SIGNATURE" });
  assert.equal(BASE_NETWORK_V2, "eip155:8453");
  assert.deepEqual(
    Object.values(PAID_ROUTES).map((r) => [r.path, r.maxAmountRequired]).sort(),
    [["/v1/briefs/live-timelocks", "100000"], ["/v1/check/preflight", "10000"], ["/v1/check/wallet-exposure", "10000"], ["/v1/scan/control-plane", "100000"], ["/v1/scan/proposal-diff", "150000"], ["/v1/scan/timelock-op", "250000"]]
  );
});

test("v2 accepts[] entries: container resource binding + the same pins as v1 (hostile payTo / amount / network / asset / timeout rejected)", () => {
  const R = PAID_ROUTES.scanControlPlane, URL_ = `${BASE_URL}${R.path}`;
  const opts = { containerVersion: 2, containerResource: URL_, routeMaxAmountRequired: R.maxAmountRequired, expectedResource: `${URL_}?chain=base&address=${FROM}` };
  const ok = validateAcceptsEntry(v2Req(R), opts);
  assert.equal(ok.ok, true, JSON.stringify(ok.reasons));
  assert.deepEqual([ok.entry.x402Version, ok.entry.network, ok.entry.amount, ok.entry.maxAmountRequired, ok.entry.resource],
    [2, "eip155:8453", "100000", undefined, opts.expectedResource]);
  const reasons = (o, op = opts) => validateAcceptsEntry(v2Req(R, o), op).reasons;
  assert.deepEqual(reasons({ payTo: ROGUE }), ["pay_to_not_allowed"]);
  assert.deepEqual(reasons({ amount: "100001" }), ["amount_over_route_price"]);
  assert.deepEqual(reasons({ amount: "5000001" }), ["amount_over_cap", "amount_over_route_price"]);
  assert.deepEqual(reasons({ network: "base" }), ["bad_network"]);
  assert.deepEqual(reasons({ network: "eip155:84532" }), ["bad_network"]);
  assert.deepEqual(reasons({ asset: "0x" + "34".repeat(20) }), ["bad_asset"]);
  assert.deepEqual(reasons({ maxTimeoutSeconds: 601 }), ["bad_max_timeout"]);
  assert.deepEqual(reasons({ amount: undefined, maxAmountRequired: "100000" }), ["bad_amount"], "v2 uses `amount`");
  assert.deepEqual(reasons({}, { ...opts, containerResource: `${BASE_URL}/v1/scan/timelock-op` }), ["resource_path_mismatch"]);
  assert.deepEqual(reasons({}, { ...opts, containerResource: "https://evil.example.invalid/v1/scan/control-plane" }), ["resource_origin_mismatch"]);
});

test("selectPaymentRequirements reads the v1 body AND the v2 PAYMENT-REQUIRED header; preferVersion picks, the other is an alternative", () => {
  const R = PAID_ROUTES.scanTimelockOp, URL_ = `${BASE_URL}${R.path}`;
  const { body, header } = worker402(R, URL_);
  const headers = { get: (k) => (k.toLowerCase() === "payment-required" ? b64(header) : null) };
  const s1 = selectPaymentRequirements({ bodyText: JSON.stringify(body), headers, routeSpec: R, resource: URL_ });
  assert.deepEqual([s1.selected.x402Version, s1.selected.maxAmountRequired, s1.selectedFrom.source, s1.availableVersions], [1, "250000", "body", [1, 2]]);
  assert.equal(s1.alternatives[0].x402Version, 2);
  const s2 = selectPaymentRequirements({ bodyText: JSON.stringify(body), headers, routeSpec: R, resource: URL_, preferVersion: 2 });
  assert.deepEqual([s2.selected.x402Version, s2.selected.network, s2.selected.amount, s2.selectedFrom.source], [2, "eip155:8453", "250000", "payment-required"]);
  // hostile v2 header only: preferring v2 falls back to the valid v1 body and reports the rejected header entry
  const hostile = worker402(R, URL_, { v2: { payTo: ROGUE, amount: "999999" } });
  const s3 = selectPaymentRequirements({ bodyText: JSON.stringify(hostile.body),
    headers: { get: (k) => (k.toLowerCase() === "payment-required" ? b64(hostile.header) : null) }, routeSpec: R, resource: URL_, preferVersion: 2 });
  assert.equal(s3.selected.x402Version, 1);
  assert.deepEqual(s3.rejected, [{ source: "payment-required", index: 0, reasons: ["pay_to_not_allowed", "amount_over_route_price"] }]);
  // both hostile -> rejected_challenge, nothing selected
  const both = worker402(R, URL_, { v1: { payTo: ROGUE }, v2: { network: "base" } });
  assert.throws(() => selectPaymentRequirements({ bodyText: JSON.stringify(both.body),
    headers: { get: (k) => (k.toLowerCase() === "payment-required" ? b64(both.header) : null) }, routeSpec: R, resource: URL_ }),
  (e) => e.code === "rejected_challenge" && e.details.entries.length === 2);
});

test("PAYMENT-SIGNATURE validation: accepted envelope, top-level, or both; hostile payTo / amount / network / resource rejected offline", () => {
  const R = PAID_ROUTES.scanControlPlane, URL_ = `${BASE_URL}${R.path}?chain=base&address=${FROM}`;
  const opts = { routeMaxAmountRequired: R.maxAmountRequired, nowSeconds: NOW, expectedResource: URL_ };
  for (const shape of ["accepted", "top", "both"]) {
    const r = validatePaymentSignatureHeader(b64(v2Payment(R, { shape })), opts);
    assert.equal(r.ok, true, `${shape}: ${JSON.stringify(r.error)}`);
    assert.deepEqual([r.payment.x402Version, r.payment.network], [2, "eip155:8453"]);
  }
  assert.equal(validatePaymentSignatureHeader(b64(v2Payment(R, { resource: { url: `${BASE_URL}${R.path}` } })), opts).ok, true);
  const reason = (p) => {
    const r = validatePaymentSignatureHeader(b64(p), opts);
    assert.equal(r.ok, false, JSON.stringify(p).slice(0, 120));
    assert.equal(r.error.code, "invalid_payment_signature");
    return r.error.reason;
  };
  assert.equal(reason(v2Payment(R, { authO: { to: ROGUE } })), "recipient_not_allowed");
  assert.equal(reason(v2Payment(R, { accepted: { payTo: ROGUE } })), "recipient_not_allowed");
  assert.equal(reason(v2Payment(R, { authO: { value: "100001" } })), "value_over_route_price");
  assert.equal(reason(v2Payment(R, { accepted: { amount: "99999" } })), "value_mismatch");
  assert.equal(reason(v2Payment(R, { accepted: { network: "base" } })), "bad_network");
  assert.equal(reason(v2Payment(R, { shape: "both", top: { network: "eip155:84532" } })), "bad_network");
  assert.equal(reason({ ...v2Payment(R), accepted: undefined }), "bad_scheme");
  assert.equal(reason(v2Payment(R, { accepted: { asset: "0x" + "34".repeat(20) } })), "bad_asset");
  assert.equal(reason({ ...v2Payment(R), x402Version: 1 }), "bad_x402_version");
  assert.equal(reason({ ...v2Payment(R), foo: 1 }), "unexpected_field");
  assert.equal(reason(v2Payment(R, { resource: { url: `${BASE_URL}/v1/scan/timelock-op` } })), "resource_mismatch");
  assert.equal(reason(v2Payment(R, { authO: { validBefore: String(NOW) } })), "expired");
});

test("callX402Resource v2: 402 -> PAYMENT-SIGNATURE template; paid call forwards PAYMENT-SIGNATURE and checks PAYMENT-RESPONSE on eip155:8453", async () => {
  const R = PAID_ROUTES.scanControlPlane;
  const q = { chain: "base", address: FROM };
  const URL_ = `${BASE_URL}${R.path}`;
  const { body, header } = worker402(R, URL_);
  const f402 = recordingFetch(() => mockRes(402, body, { "PAYMENT-REQUIRED": b64(header) }));
  const ch = await callX402Resource({ fetchImpl: f402, baseUrl: BASE_URL, routeSpec: R, query: q, x402Version: 2, payer: FROM, nowSeconds: NOW, nonce: NONCE });
  assert.deepEqual([ch.status, ch.x402Version, ch.accepts[0].network, ch.accepts[0].amount, ch.availableVersions], [402, 2, "eip155:8453", "100000", [1, 2]]);
  assert.equal(ch.eip712TypedData.message.value, "100000");
  assert.equal(ch.eip712TypedData.message.to, PAYTO);
  const tpl = ch.paymentSignatureEnvelopeTemplate;
  assert.deepEqual([tpl.headerName, tpl.toolArgument, tpl.jsonShape.x402Version, tpl.jsonShape.accepted.network, tpl.jsonShape.resource.url],
    ["PAYMENT-SIGNATURE", "paymentSignatureHeader", 2, "eip155:8453", URL_]);
  assert.equal(ch.xPaymentEnvelopeTemplate, undefined);
  // default stays v1 for backward compatibility
  const ch1 = await callX402Resource({ fetchImpl: f402, baseUrl: BASE_URL, routeSpec: R, query: q, payer: FROM, nowSeconds: NOW });
  assert.deepEqual([ch1.x402Version, ch1.xPaymentEnvelopeTemplate.headerName, ch1.alternativeAccepts[0].x402Version], [1, "X-PAYMENT", 2]);

  // build the header with the encoder from the v2 challenge, then pay
  const hdr = encodePaymentSignatureHeader({ signature: SIG, authorization: { ...ch.eip712TypedData.message, from: FROM, validBefore: String(NOW + 50) },
    accepted: ch.accepts[0], resource: tpl.jsonShape.resource.url });
  assert.deepEqual(unb64(hdr).accepted, v2Req(R));
  const fPaid = recordingFetch(() => mockRes(200, { chain: "base" }, { "PAYMENT-RESPONSE": receipt(), "X-PAYMENT-RESPONSE": receipt() }));
  const paid = await callX402Resource({ fetchImpl: fPaid, baseUrl: BASE_URL, routeSpec: R, query: q, paymentSignatureHeader: hdr, nowSeconds: NOW });
  assert.deepEqual([paid.status, paid.paid, paid.x402Version, paid.paymentReceipt.network, paid.onchainReceiptVerified, paid.settlementVerificationScope],
    [200, true, 2, "eip155:8453", false, "gateway_header_assertion"]);
  assert.equal(fPaid.calls[0].init.headers["PAYMENT-SIGNATURE"], hdr);
  assert.equal(fPaid.calls[0].init.headers["X-PAYMENT"], undefined);

  // receipt only in PAYMENT-RESPONSE is enough; a v1-network receipt for a v2 payment is not
  const onlyV2 = recordingFetch(() => mockRes(200, {}, { "PAYMENT-RESPONSE": receipt() }));
  assert.equal((await callX402Resource({ fetchImpl: onlyV2, baseUrl: BASE_URL, routeSpec: R, query: q, paymentSignatureHeader: hdr, nowSeconds: NOW })).paid, true);
  for (const [hdrs, why] of [[{ "PAYMENT-RESPONSE": receipt({ network: "base" }) }, "receipt_bad_network"], [{}, "missing_receipt"],
    [{ "PAYMENT-RESPONSE": receipt({ payer: ROGUE }) }, "receipt_payer_mismatch"]]) {
    const fx = recordingFetch(() => mockRes(200, {}, hdrs));
    await assert.rejects(callX402Resource({ fetchImpl: fx, baseUrl: BASE_URL, routeSpec: R, query: q, paymentSignatureHeader: hdr, nowSeconds: NOW }),
      (e) => e.code === "unverified_settlement" && e.details.reason === why, why);
  }
  // invalid PAYMENT-SIGNATURE or both headers: rejected before any fetch
  const never = recordingFetch(() => { throw new Error("must not fetch"); });
  await assert.rejects(callX402Resource({ fetchImpl: never, baseUrl: BASE_URL, routeSpec: R, query: q, paymentSignatureHeader: b64(v2Payment(R, { authO: { to: ROGUE } })), nowSeconds: NOW }),
    (e) => e.code === "invalid_payment_signature" && e.details.reason === "recipient_not_allowed");
  await assert.rejects(callX402Resource({ fetchImpl: never, baseUrl: BASE_URL, routeSpec: R, query: q, paymentSignatureHeader: hdr, xPaymentHeader: "x", nowSeconds: NOW }),
    (e) => e.code === "invalid_argument");
  await assert.rejects(callX402Resource({ fetchImpl: never, baseUrl: BASE_URL, routeSpec: R, query: q, x402Version: 3, nowSeconds: NOW }),
    (e) => e.code === "invalid_argument");
  assert.equal(never.calls.length, 0);
  // receipt validator defaults to v1 network
  assert.equal(validatePaymentReceipt(receipt(), { expectedPayer: FROM }).reason, "receipt_bad_network");
  assert.equal(validatePaymentReceipt(receipt(), { expectedPayer: FROM, network: "eip155:8453" }).ok, true);
});

test("pacta_scan_proposal_diff: listed with the Worker contract, GET /v1/scan/proposal-diff?forum=&topicId=, $0.15 challenge, v2 payment", async () => {
  const tool = PAID_TOOLS.find((t) => t.name === "pacta_scan_proposal_diff");
  // free ($0.00) today: the description carries no metered figure; the client still answers a $0.15 challenge if one is ever issued
  assert.ok(tool && /Free \(\$0\.00\) today/.test(tool.description) && !/\$0\.1[05]|\$0\.25|when metered/.test(tool.description));
  assert.deepEqual(tool.inputSchema.required, ["forum", "topicId"]);
  assert.ok(CALLER_REQ.every((f) => tool.inputSchema.properties[f]), "caller fields documented as optional");
  assert.deepEqual(tool.inputSchema.properties.forum.enum, ["aave", "euler", "morpho", "sky"]);
  assert.ok(tool.inputSchema.properties.paymentSignatureHeader && tool.inputSchema.properties.xPaymentHeader);
  const R = PAID_ROUTES.scanProposalDiff, URL_ = `${BASE_URL}${R.path}`;
  const { body, header } = worker402(R, URL_);
  const f = recordingFetch((url) => (url.includes("/v1/scan/proposal-diff") ? mockRes(402, body, { "PAYMENT-REQUIRED": b64(header) }) : mockRes(404, {})));
  const srv = new PactaMcpServer({ x402Url: BASE_URL, fetchImpl: f, nowSeconds: NOW });
  assert.ok(srv.getTools().some((t) => t.name === "pacta_scan_proposal_diff"));
  const ch = await srv.callTool("pacta_scan_proposal_diff", { ...CALLER,  forum: "aave", topicId: 25128, x402Version: 2, payer: FROM });
  assert.equal(f.calls[0].url, `${URL_}?forum=aave&topicId=25128${CQ}`);
  assert.equal(f.calls[0].init.method, "GET");
  assert.deepEqual([ch.status, ch.x402Version, ch.accepts[0].amount, ch.priceUsdc], [402, 2, "150000", "0.15"]);
  for (const bad of [{ forum: "compound", topicId: "1" }, { forum: "aave", topicId: "0" }, { forum: "aave", topicId: "12345678901" }, { forum: "aave", topicId: "1x" }, { forum: "aave" }]) {
    const n = f.calls.length;
    await assert.rejects(srv.callTool("pacta_scan_proposal_diff", bad), (e) => e.code === "invalid_argument", JSON.stringify(bad));
    assert.equal(f.calls.length, n, "invalid arguments never fetch");
  }
  const hdr = b64(v2Payment(R, { resource: { url: URL_ } }));
  const fp = recordingFetch(() => mockRes(200, { proposalId: "aave-25128" }, { "PAYMENT-RESPONSE": receipt({ amount: "150000" }) }));
  const paidSrv = new PactaMcpServer({ x402Url: BASE_URL, fetchImpl: fp, nowSeconds: NOW });
  const paid = await paidSrv.callTool("pacta_scan_proposal_diff", { ...CALLER,  forum: "aave", topicId: "25128", paymentSignatureHeader: hdr });
  assert.deepEqual([paid.paid, paid.x402Version, paid.data.proposalId, paid.paymentReceipt.amount], [true, 2, "aave-25128", "150000"]);
  assert.equal(fp.calls[0].init.headers["PAYMENT-SIGNATURE"], hdr);
});

test("pacta_check_preflight: Worker contract GET /v1/check/preflight?chain=&address=[&block=], $0.01 challenge when metered, free-launch 200 as unpaid data", async () => {
  const tool = PAID_TOOLS.find((t) => t.name === "pacta_check_preflight");
  assert.ok(tool && /50 free calls per caller per UTC day, then \$0\.01 Base USDC per call via x402/.test(tool.description) && !/when metered/.test(tool.description));
  assert.equal(PAID_TOOLS[0].name, "pacta_check_preflight");
  assert.deepEqual(tool.inputSchema.required, ["chain", "address"]);
  assert.ok(CALLER_REQ.every((f) => tool.inputSchema.properties[f]), "caller fields documented as optional");
  assert.deepEqual(tool.inputSchema.properties.chain.enum, ["ethereum", "base"]);
  const R = PAID_ROUTES.checkPreflight, URL_ = `${BASE_URL}${R.path}`;
  assert.deepEqual([R.path, R.priceUsdc, R.maxAmountRequired], ["/v1/check/preflight", "0.01", "10000"]);
  // free launch: the live Worker answers 200 with no payment header; the tool returns it as unpaid data
  const verdict = { schema: "pacta.preflight_check.v1", verdict: "TIMELOCK_PROTECTED", riskScore: 15, pinnedBlock: 23800000 };
  const free = recordingFetch(() => mockRes(200, verdict));
  const srv = new PactaMcpServer({ x402Url: BASE_URL, fetchImpl: free, nowSeconds: NOW });
  assert.ok(srv.getTools().some((t) => t.name === "pacta_check_preflight"));
  const r = await srv.callTool("pacta_check_preflight", { ...CALLER,  chain: "base", address: FROM });
  assert.equal(free.calls[0].url, `${URL_}?chain=base&address=${FROM}${CQ}`);
  assert.equal(free.calls[0].init.method, "GET");
  assert.equal(free.calls[0].init.headers["X-PAYMENT"], undefined);
  assert.equal(free.calls[0].init.headers["PAYMENT-SIGNATURE"], undefined);
  assert.deepEqual([r.status, r.paid, r.paymentRequired, r.data.verdict], [200, false, false, "TIMELOCK_PROTECTED"]);
  await srv.callTool("pacta_check_preflight", { ...CALLER,  chain: "ethereum", address: FROM, block: "23800000" });
  assert.equal(free.calls[1].url, `${URL_}?chain=ethereum&address=${FROM}&block=23800000${CQ}`);
  // metered mode: the $0.01 challenge is validated like every other route
  const { body, header } = worker402(R, URL_);
  const f = recordingFetch(() => mockRes(402, body, { "PAYMENT-REQUIRED": b64(header) }));
  const paidMode = new PactaMcpServer({ x402Url: BASE_URL, fetchImpl: f, nowSeconds: NOW });
  const ch = await paidMode.callTool("pacta_check_preflight", { ...CALLER,  chain: "base", address: FROM, x402Version: 2, payer: FROM });
  assert.deepEqual([ch.status, ch.x402Version, ch.accepts[0].amount, ch.priceUsdc], [402, 2, "10000", "0.01"]);
  for (const bad of [{ chain: "polygon", address: FROM }, { chain: "base", address: "0x1234" }, { chain: "base" },
    { chain: "base", address: FROM, block: "pending" }, { chain: "base", address: FROM, block: 1 }, { chain: "base", address: FROM, block: "0x" }]) {
    const n = f.calls.length;
    await assert.rejects(paidMode.callTool("pacta_check_preflight", bad), (e) => e.code === "invalid_argument", JSON.stringify(bad));
    assert.equal(f.calls.length, n, "invalid arguments never fetch");
  }
  // gateway unset: x402_disabled, no network
  const off = recordingFetch(() => mockRes(500, {}));
  const offSrv = new PactaMcpServer({ x402Url: "", fetchImpl: off, nowSeconds: NOW });
  assert.ok(!offSrv.getTools().some((t) => t.name === "pacta_check_preflight"));
  await assert.rejects(offSrv.callTool("pacta_check_preflight", { ...CALLER,  chain: "base", address: FROM }), (e) => e.code === "x402_disabled");
  assert.equal(off.calls.length, 0);
});

test("tool alias: pacta_get_live_timelocks (the remote MCP name) runs pacta_live_timelocks; it is accepted, not listed; prototype keys are not aliases", async () => {
  assert.equal(canonicalToolName("pacta_get_live_timelocks"), "pacta_live_timelocks");
  for (const k of ["constructor", "__proto__", "toString", "pacta_live_timelocks"]) assert.equal(canonicalToolName(k), k);
  assert.ok(!TOOL_DEFINITIONS.some((t) => t.name in TOOL_ALIASES));
  const body = { schema: "pacta.live_timelocks.v1", count: 0, operations: [] };
  const f = recordingFetch(() => mockRes(200, body));
  const srv = new PactaMcpServer({ x402Url: BASE_URL, fetchImpl: f, nowSeconds: NOW });
  assert.ok(!srv.getTools().some((t) => t.name === "pacta_get_live_timelocks"));
  const a = await srv.callTool("pacta_live_timelocks", { ...CALLER });
  const b = await srv.callTool("pacta_get_live_timelocks", { ...CALLER });
  assert.deepEqual([a.status, b.status, a.data, b.data], [200, 200, body, body]);
  assert.deepEqual(f.calls.map((c) => c.url), [`${BASE_URL}/v1/briefs/live-timelocks?${CQ.slice(1)}`, `${BASE_URL}/v1/briefs/live-timelocks?${CQ.slice(1)}`]);
  const rpc = await srv.handleMessage({ jsonrpc: "2.0", id: 9, method: "tools/call", params: { name: "pacta_get_live_timelocks", arguments: { ...CALLER } } });
  assert.equal(rpc.result.isError, false);
  const bad = await srv.handleMessage({ jsonrpc: "2.0", id: 10, method: "tools/call", params: { name: "constructor", arguments: {} } });
  assert.equal(bad.error.code, -32602);
});

test("free-tier caller attribution (stdio): gateway tools document caller_agent / requester_role / caller_purpose as OPTIONAL; omitted or invalid values never reject (-32602) and are dropped before forwarding; paid calls and local tools are unaffected", async () => {
  for (const t of PAID_TOOLS) {
    assert.ok(["caller_agent", "requester_role", "caller_purpose"].every((f) => !t.inputSchema.required.includes(f) && t.inputSchema.properties[f]), t.name);
    assert.deepEqual([t.inputSchema.properties.requester_role.enum, t.inputSchema.properties.caller_purpose.enum], [[...REQUESTER_ROLES], [...CALLER_PURPOSES]]);
    assert.ok(!/\b(?:country|location|city|latitude|longitude|geo)\b/i.test(JSON.stringify(t.inputSchema.properties)), "never asks for location");
  }
  for (const t of FREE_TOOLS) assert.ok(!("caller_agent" in (t.inputSchema.properties || {})), "local-only tools send nothing, so they ask nothing: " + t.name);
  const f = recordingFetch(() => mockRes(200, { ok: true }));
  const srv = new PactaMcpServer({ x402Url: BASE_URL, fetchImpl: f, nowSeconds: NOW });
  const call = (args, id = 1) => srv.handleMessage({ jsonrpc: "2.0", id, method: "tools/call", params: { name: "pacta_check_preflight", arguments: { chain: "base", address: FROM, ...args } } });
  const badRole = await call({ requester_role: "ceo" });
  assert.deepEqual([badRole.error, badRole.result.isError], [undefined, false]);
  const tok = (p) => p + "abcdefghijklmnop0123456789";
  const jwt = "ey" + "JhbGciOiJIUzI1NiJ9.e30.sig";   // JWT: mixed case and already lowercased (Codex task-344fc12c4e24)
  for (const a of ["alice@example.com", "my agent", "0x" + "ab".repeat(20), "ab".repeat(16), "https://evil.example.com", "10.0.0.7", tok("sk" + "-"), tok("gh" + "p_"), "a", "x".repeat(49),
    jwt, jwt.toLowerCase(), "agent/" + "ey" + "jhbgcioi.x1"]) {
    const r = await call({ ...CALLER, caller_agent: a });
    assert.deepEqual([r.error, r.result.isError], [undefined, false], a);
  }
  assert.ok(f.calls.every((c) => !c.url.includes("caller_agent=") && !c.url.includes("ceo") && !c.url.includes("alice") && !/eyj/i.test(c.url)), "invalid attribution never sent upstream");
  f.calls.length = 0;
  assert.equal((await call({ ...CALLER, caller_agent: "Cursor" })).result.isError, false);
  assert.equal(f.calls[0].url, `${BASE_URL}/v1/check/preflight?chain=base&address=${FROM}&caller_agent=cursor&requester_role=defi_developer&caller_purpose=integration_testing`);
  assert.equal((await call({ caller_agent: "  ", requester_role: "" })).result.isError, false, "omitted / blank attribution: dispatched");
  assert.equal(f.calls[1].url, `${BASE_URL}/v1/check/preflight?chain=base&address=${FROM}`, "nothing is invented for omitted fields");
  assert.deepEqual([normalizeCallerAgent(" Claude-Code "), normalizeCallerAgent("user@example.com"), normalizeCallerAgent(jwt), normalizeCallerAgent("eyeglass-agent")],
    ["claude-code", null, null, "eyeglass-agent"]);
  // paying: never rejected for missing caller fields, and the request carries no attribution (x402 resource unchanged)
  f.calls.length = 0;
  const paid = await call({ xPaymentHeader: "not-base64!" });
  assert.notEqual(paid.error?.code, -32602);
  assert.ok(f.calls.length <= 2 && f.calls.every((c) => !c.url.includes("caller_agent=pacta")), "paid calls are sent without attribution");
  // gateway unset: nothing leaves the process, so nothing is required
  const off = new PactaMcpServer({ fetchImpl: recordingFetch(() => mockRes(500, {})), nowSeconds: NOW });
  const r0 = await off.handleMessage({ jsonrpc: "2.0", id: 9, method: "tools/call", params: { name: "pacta_check_preflight", arguments: { chain: "base", address: FROM } } });
  assert.notEqual(r0.error?.code, -32602);
});

test("pacta_scan_wallet_exposure: Worker contract GET /v1/check/wallet-exposure?address=[&chain=], free-launch 200 and invalid argument guard", async () => {
  const f = recordingFetch(() => mockRes(200, { schema: "pacta.wallet_exposure.v1", tier: "free_summary", wallet: FROM, summary: { totalPositions: 2 } }));
  const srv = new PactaMcpServer({ x402Url: BASE_URL, fetchImpl: f, nowSeconds: NOW });
  assert.ok(srv.getTools().some((t) => t.name === "pacta_scan_wallet_exposure"));
  const r = await srv.callTool("pacta_scan_wallet_exposure", { ...CALLER, address: FROM });
  assert.equal(r.paid, false);
  assert.equal(r.data.schema, "pacta.wallet_exposure.v1");
  assert.equal(f.calls[0].url, `${BASE_URL}/v1/check/wallet-exposure?address=${FROM}&caller_agent=pacta-test-agent&requester_role=defi_developer&caller_purpose=integration_testing`);
  await srv.callTool("pacta_scan_wallet_exposure", { address: FROM, chain: "base" });
  assert.equal(f.calls[1].url, `${BASE_URL}/v1/check/wallet-exposure?address=${FROM}&chain=base`);
  await assert.rejects(srv.callTool("pacta_scan_wallet_exposure", { address: "0x1234" }), (e) => e.code === "invalid_argument");
  await assert.rejects(srv.callTool("pacta_scan_wallet_exposure", { address: FROM, chain: "solana" }), (e) => e.code === "invalid_argument");
});
