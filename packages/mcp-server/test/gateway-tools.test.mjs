// Gateway on by default + clean tool schemas + buyer-first descriptions, and the 4 gateway tools pacta_who_controls_contract
// (GET /v1/check), pacta_verdict / pacta_dossier (GET /v1/x402/{verdict,dossier}, free 100/day then x402) and request_feature
// (POST /v1/feature-request). Every fetch is injected (no-network.mjs blocks the global one).
import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import {
  PactaMcpServer, TOOL_DEFINITIONS, READ_ONLY_TOOLS, REQUEST_TOOLS, WHO_CONTROLS_TOOL, FEATURE_TOOL, PAID_TOOLS, TOOL_META, TOOL_ALIASES,
  PAYMENT_ARGUMENTS, CALLER_FIELDS, MCP_INSTRUCTIONS, X402_DEFAULTS, PAID_ROUTES, ALLOWED_PAY_TO, BASE_USDC, hasIpLiteral, canonicalToolName,
} from "../src/server.mjs";
import { CALLER } from "./helpers.mjs";

const GW = "https://x402.example.invalid";
const NOW = 1794580000;
const ADDR = "0xA35b1B31Ce002FBF2058D22F30f95D405200A15b";   // Stader ETHx (EIP-55)
const FROM = "0x" + "11".repeat(20);
const mockRes = (status, body, headers = {}) => {
  const m = new Map(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return { ok: status >= 200 && status < 300, status, headers: { get: (k) => m.get(String(k).toLowerCase()) ?? null }, text: async () => text };
};
const rec = (responder) => {
  const calls = [];
  const f = async (url, init = {}) => { calls.push({ url: String(url), init }); return responder(String(url), init, calls.length); };
  f.calls = calls;
  return f;
};
const never = () => rec(() => { throw new Error("must not be called"); });
const rpc = (srv, name, args, id = 1) => srv.handleMessage({ jsonrpc: "2.0", id, method: "tools/call", params: { name, arguments: args } });
const bodyOf = (r) => JSON.parse(r.result.content[0].text);
const NINE = ["xPaymentHeader", "paymentSignatureHeader", "x402Version", "payer", "validBeforeSeconds", "nonce", "caller_agent", "requester_role", "caller_purpose"];
const b64 = (v) => Buffer.from(JSON.stringify(v), "utf8").toString("base64");
const PRICE_ENDINGS = [
  "Free ($0.00) today: rate-limited, no wallet or payment required.",
  "Free: 50 calls per caller per UTC day (no key, no payment), then $0.01 Base USDC per call via x402.",
  "Free: 100 calls per caller per UTC day (no key, no payment), then $0.01 Base USDC per call via x402.",
  "Free: 100 calls per caller per UTC day (no key, no payment), then $0.02 Base USDC per call via x402.",
  "Free: 100 calls per caller per UTC day (no key, no payment), then $0.05 Base USDC per call via x402.",
  "Free: 100 calls per caller per UTC day (no key, no payment).",
  "Free (no key, no payment).",
  "Free (static feed, no key, no payment).",
  "Free: 5 per caller per UTC day.",
  "Free in every pricing mode: 5 per hour.",
];

test("H1: 16 tools, 0 of the 9 payment / caller fields in any inputSchema, 0 setup labels, pricing text last, buyer words first", () => {
  assert.equal(TOOL_DEFINITIONS.length, 16);
  assert.deepEqual(REQUEST_TOOLS.map((t) => t.name), ["request_feature", "pacta_submit_request"]);
  assert.deepEqual([...PAYMENT_ARGUMENTS, ...CALLER_FIELDS], NINE);
  for (const t of TOOL_DEFINITIONS) {
    const props = Object.keys(t.inputSchema.properties || {});
    assert.deepEqual(props.filter((k) => NINE.includes(k)), [], t.name);
    assert.equal(t.inputSchema.additionalProperties, false, t.name);
    assert.doesNotMatch(t.description, /Gateway tool|requires PACTA_X402_URL/, t.name);
    // the price / free text is the last sentence of every description, and the only place it appears
    const end = PRICE_ENDINGS.find((e) => t.description.endsWith(" " + e));
    assert.ok(end, `${t.name}: ends with its price text: ${t.description.slice(-120)}`);
    assert.ok(!/\bFree\b|\$\d/.test(t.description.slice(0, -end.length).replace(/free \(\$0\.00\)/gi, "")), `${t.name}: no price text before the end`);
    assert.equal(typeof TOOL_META[t.name], "object", t.name);
    assert.equal(t.annotations.title, t.title, t.name);
  }
  assert.ok(READ_ONLY_TOOLS.every((t) => t.annotations.readOnlyHint === true && t.annotations.destructiveHint === false), "14 read-only tools");
  assert.equal(READ_ONLY_TOOLS.length, 14);
  const buyer = { pacta_who_controls_contract: /^who controls this contract/, pacta_check_preflight: /^Smart contract security pre-flight \/ rug check/,
    pacta_scan_wallet_exposure: /^Wallet risk \/ DeFi exposure/, pacta_verdict: /^Token safety/, pacta_scan_control_plane: /^Who can upgrade or control this contract/,
    pacta_lookup_protocol: /^Find a DeFi protocol or token/, request_feature: /^Request a missing tool/ };
  for (const [n, re] of Object.entries(buyer)) assert.match(TOOL_DEFINITIONS.find((t) => t.name === n).description, re, n);
  assert.match(MCP_INSTRUCTIONS, /^Pacta by Fractal Neurons: 14 read-only, block-pinned inspection tools for EVM contracts \(Ethereum, Base\) \+ 2 opt-in request tools\. /);
  assert.match(MCP_INSTRUCTIONS, /call pacta_who_controls_contract/);
  assert.match(MCP_INSTRUCTIONS, /call request_feature/);
});

test("pacta_who_controls_contract: exact description, schema of only chain + address, read-only annotations, alias who_controls", () => {
  assert.equal(WHO_CONTROLS_TOOL.description,
    "who controls this contract / token: owner, admin, upgradeable proxy, timelock, multisig, can mint, can pause; rug check, token safety. Block-pinned chain facts on Ethereum and Base confirmed by two independent RPC providers, with Foundry cast commands; never guesses or rates. Free: 100 calls per caller per UTC day (no key, no payment).");
  assert.deepEqual(WHO_CONTROLS_TOOL.inputSchema, {
    type: "object", additionalProperties: false, required: ["chain", "address"],
    properties: { chain: { type: "string", enum: ["ethereum", "base"] }, address: { type: "string", pattern: "^0x[0-9a-fA-F]{40}$" } },
  });
  assert.deepEqual(WHO_CONTROLS_TOOL.annotations, { title: WHO_CONTROLS_TOOL.title, readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false });
  assert.equal(TOOL_DEFINITIONS[1], WHO_CONTROLS_TOOL, "listed right after pacta_lookup_protocol");
  assert.equal(canonicalToolName("who_controls"), "pacta_who_controls_contract");
  assert.equal(canonicalToolName("pacta_request_feature"), "request_feature");
  assert.ok(!TOOL_DEFINITIONS.some((t) => t.name in TOOL_ALIASES), "aliases are never listed");
});

test("pacta_who_controls_contract: one GET /v1/check?chain=&address= (no caller or payment fields sent), the gateway JSON returned as is", async () => {
  const out = { schema: "pacta.who_controls.v1", chain: "ethereum", chainId: 1, address: ADDR, upgradeable: true, canMint: null, canPause: null,
    controllerType: "timelock", meter: { limit: 100, remaining: 99, reset: NOW } };
  const f = rec(() => mockRes(200, out));
  const srv = new PactaMcpServer({ x402Url: GW, fetchImpl: f });
  const r = await rpc(srv, "pacta_who_controls_contract", { chain: "ethereum", address: ADDR, ...CALLER, xPaymentHeader: "ignored" });
  assert.equal(r.result.isError, false);
  assert.deepEqual(bodyOf(r), out);
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].url, `${GW}/v1/check?chain=ethereum&address=${ADDR}`);
  assert.equal(f.calls[0].init.method ?? "GET", "GET");
  assert.deepEqual([f.calls[0].init.redirect, f.calls[0].init.headers.Accept, f.calls[0].init.headers["X-PAYMENT"]], ["error", "application/json", undefined]);
  // alias + lowercase address
  const r2 = await rpc(srv, "who_controls", { chain: "base", address: ADDR.toLowerCase() });
  assert.equal(r2.result.isError, false);
  assert.equal(f.calls[1].url, `${GW}/v1/check?chain=base&address=${ADDR.toLowerCase()}`);
});

test("pacta_who_controls_contract: invalid input never fetches; gateway refusals keep the gateway's code and meter; malformed 200 refused", async () => {
  const nf = never();
  const srv = new PactaMcpServer({ x402Url: GW, fetchImpl: nf });
  for (const bad of [{ chain: "polygon", address: ADDR }, { chain: "ethereum" }, { chain: "ethereum", address: "0x1234" },
    { chain: "ethereum", address: ADDR.replace("A35b", "a35B") }, { chain: "ethereum", address: ADDR, block: "latest" }, {}]) {
    const r = await rpc(srv, "pacta_who_controls_contract", bad);
    assert.equal(r.result.isError, true, JSON.stringify(bad));
    assert.equal(bodyOf(r).code, "invalid_argument", JSON.stringify(bad));
  }
  assert.equal(nf.calls.length, 0);
  const cases = [
    [400, { error: "bad_request", detail: "unknown query parameter x" }, "bad_request"],
    [429, { error: "free_quota_exhausted", detail: "100 per UTC day", meter: { limit: 100, remaining: 0, reset: NOW } }, "free_quota_exhausted"],
    [429, { error: "rate_limited", retryAfterSeconds: 30 }, "rate_limited"],
    [502, { error: "upstream_unavailable", detail: "providers disagree, could not read" }, "upstream_unavailable"],
    [500, "<html>oops</html>", "upstream_http_error"],
    [503, { error: "Not A Code!", detail: "x" }, "upstream_http_error"],
  ];
  for (const [status, body, code] of cases) {
    const s2 = new PactaMcpServer({ x402Url: GW, fetchImpl: rec(() => mockRes(status, body)) });
    const r = await rpc(s2, "pacta_who_controls_contract", { chain: "base", address: ADDR });
    const e = bodyOf(r);
    assert.deepEqual([r.result.isError, e.code, e.status], [true, code, status], JSON.stringify(body));
    if (code === "free_quota_exhausted") assert.deepEqual(e.meter, { limit: 100, remaining: 0, reset: NOW });
    if (code === "rate_limited") assert.equal(e.retryAfterSeconds, 30);
  }
  const bad200 = await rpc(new PactaMcpServer({ x402Url: GW, fetchImpl: rec(() => mockRes(200, { schema: "other" })) }), "pacta_who_controls_contract", { chain: "base", address: ADDR });
  assert.deepEqual([bad200.result.isError, bodyOf(bad200).code], [true, "malformed_upstream_json"]);
  // gateway off: x402_disabled, nothing sent
  const off = never();
  const r0 = await rpc(new PactaMcpServer({ x402Url: "", fetchImpl: off }), "pacta_who_controls_contract", { chain: "base", address: ADDR });
  assert.deepEqual([r0.result.isError, bodyOf(r0).code], [true, "x402_disabled"]);
  assert.equal(off.calls.length, 0);
});

test("pacta_verdict / pacta_dossier: GET /v1/x402/{verdict,dossier} with slug or chain + address; free 200 returned as unpaid data; caller fields never sent", async () => {
  for (const [name, path] of [["pacta_verdict", "/v1/x402/verdict"], ["pacta_dossier", "/v1/x402/dossier"]]) {
    const t = PAID_TOOLS.find((x) => x.name === name);
    assert.deepEqual(Object.keys(t.inputSchema.properties), ["slug", "chain", "address"], name);
    assert.deepEqual(t.inputSchema.required, [], name);
    assert.equal(t.annotations.readOnlyHint, true, name);
    const data = { schema: name === "pacta_verdict" ? "pacta.x402_verdict.v1" : "pacta.x402_dossier.v1", meter: { limit: 100, remaining: 98, reset: NOW } };
    const f = rec(() => mockRes(200, data));
    const srv = new PactaMcpServer({ x402Url: GW, fetchImpl: f, nowSeconds: NOW });
    const a = await srv.callTool(name, { slug: "aave-v3-gho", ...CALLER });
    const b = await srv.callTool(name, { chain: "ethereum", address: ADDR, caller_agent: "cursor" });
    assert.deepEqual([a.status, a.paid, a.paymentRequired, a.data], [200, false, false, data], name);
    assert.deepEqual(f.calls.map((c) => c.url), [`${GW}${path}?slug=aave-v3-gho`, `${GW}${path}?chain=ethereum&address=${ADDR}`], name);
    assert.ok(f.calls.every((c) => c.init.method === "GET" && c.init.headers["X-PAYMENT"] === undefined), name);
    const n = f.calls.length;
    for (const bad of [{}, { slug: "Aave V3" }, { slug: "x".repeat(81) }, { slug: "aave", chain: "ethereum", address: ADDR }, { chain: "ethereum" },
      { chain: "polygon", address: ADDR }, { address: ADDR }, { slug: "aave", target: ADDR }]) {
      await assert.rejects(srv.callTool(name, bad), (e) => e.code === "invalid_argument", `${name} ${JSON.stringify(bad)}`);
    }
    assert.equal(f.calls.length, n, "invalid arguments never fetch");
  }
});

test("pacta_verdict / pacta_dossier above the free quota: the route's 402 is a validated $0.02 / $0.05 challenge; a signed payment is forwarded", async () => {
  for (const [name, R, amount] of [["pacta_verdict", PAID_ROUTES.verdict, "20000"], ["pacta_dossier", PAID_ROUTES.dossier, "50000"]]) {
    assert.equal(R.maxAmountRequired, amount);
    const url = `${GW}${R.path}`;
    const req = { scheme: "exact", network: "base", maxAmountRequired: amount, resource: url, description: R.description, mimeType: "application/json",
      payTo: ALLOWED_PAY_TO[1], maxTimeoutSeconds: 60, asset: BASE_USDC, extra: { name: "USD Coin", version: "2" } };
    const f = rec(() => mockRes(402, { x402Version: 1, error: "free_quota_exhausted", accepts: [req] }));
    const srv = new PactaMcpServer({ x402Url: GW, fetchImpl: f, nowSeconds: NOW });
    const ch = await srv.callTool(name, { slug: "aave-v3-gho", payer: FROM });
    assert.deepEqual([ch.status, ch.paymentRequired, ch.accepts[0].maxAmountRequired, ch.eip712TypedData.message.value, ch.eip712TypedData.message.to],
      [402, true, amount, amount, ALLOWED_PAY_TO[1]], name);
    // an over-priced challenge is refused (the route ceiling binds)
    const rogue = rec(() => mockRes(402, { x402Version: 1, accepts: [{ ...req, maxAmountRequired: String(Number(amount) + 1) }] }));
    await assert.rejects(new PactaMcpServer({ x402Url: GW, fetchImpl: rogue, nowSeconds: NOW }).callTool(name, { slug: "aave-v3-gho" }),
      (e) => e.code === "rejected_challenge", name);
    // a signed X-PAYMENT (an argument accepted, never listed) is sent on the same GET; a bad one never leaves the process
    const p = rec(() => mockRes(402, { x402Version: 1, accepts: [req] }));
    const ps = new PactaMcpServer({ x402Url: GW, fetchImpl: p, nowSeconds: NOW });
    await assert.rejects(ps.callTool(name, { slug: "aave-v3-gho", xPaymentHeader: b64({ x402Version: 1, scheme: "exact", network: "base", payload: {} }) }),
      (e) => e.code === "invalid_x_payment", name);
    assert.equal(p.calls.length, 0, name);
  }
  // gateway off: x402_disabled, nothing sent
  const off = never();
  await assert.rejects(new PactaMcpServer({ x402Url: "", fetchImpl: off }).callTool("pacta_verdict", { slug: "aave-v3-gho" }), (e) => e.code === "x402_disabled");
  assert.equal(off.calls.length, 0);
});

test("request_feature: exact schema + annotations; one POST /v1/feature-request with {text, use_case?} (normalized), receipt returned", async () => {
  assert.deepEqual(FEATURE_TOOL.inputSchema.required, ["text"]);
  assert.deepEqual(Object.keys(FEATURE_TOOL.inputSchema.properties), ["text", "use_case"]);
  assert.deepEqual([FEATURE_TOOL.inputSchema.properties.text.maxLength, FEATURE_TOOL.inputSchema.properties.use_case.maxLength], [1000, 500]);
  assert.deepEqual(FEATURE_TOOL.annotations, { title: "Request a Pacta Feature or Tool", readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false });
  assert.deepEqual(FEATURE_TOOL._meta, { resultType: "feature_request_receipt", ttlMs: 0, cacheScope: "none" });
  assert.match(FEATURE_TOOL.description, /Free: 5 per caller per UTC day\.$/);
  const receipt = { ok: true, request_id: "FREQ-2026-0123abcd", message: "Thank you", meter: { limit: 5, remaining: 4, reset: NOW } };
  const f = rec(() => mockRes(200, receipt));
  const srv = new PactaMcpServer({ x402Url: GW, fetchImpl: f });
  const r = await rpc(srv, "request_feature", { text: "  Add Arbitrum\n support\tfor who_controls ", use_case: "pre-trade checks" });
  assert.equal(r.result.isError, false);
  assert.deepEqual(bodyOf(r), { ...receipt, source: "gateway" });
  assert.equal(f.calls[0].url, `${GW}/v1/feature-request`);
  assert.deepEqual([f.calls[0].init.method, f.calls[0].init.headers["Content-Type"], f.calls[0].init.redirect], ["POST", "application/json", "error"]);
  assert.deepEqual(JSON.parse(f.calls[0].init.body), { text: "Add Arbitrum support for who_controls", use_case: "pre-trade checks" });
  await rpc(srv, "pacta_request_feature", { text: "Solana support", use_case: "   " });
  assert.deepEqual(JSON.parse(f.calls[1].init.body), { text: "Solana support" }, "alias; blank use_case omitted");
});

test("request_feature refuses names / emails / IP literals / secrets / unknown fields LOCALLY (-32602, nothing sent, values never echoed); gateway errors keep their code", async () => {
  const nf = never();
  const srv = new PactaMcpServer({ x402Url: GW, fetchImpl: nf });
  for (const [args, needle] of [
    [{ text: "mail me at ops" + "@" + "example.org" }, "text (email_address)"],
    [{ text: "my node 10.0.0.7 is slow" }, "text (ip_address)"],
    [{ text: "node at [2001:db8::1]" }, "text (ip_address)"],
    [{ text: "use fe80::1 please" }, "text (ip_address)"],
    [{ text: "key " + "ab".repeat(32) }, "text (secret_or_key)"],
    [{ text: "<b>x</b>" }, "text (html)"],
    [{ text: "x".repeat(1001) }, "text (too_long)"],
    [{ text: "ok", use_case: "y".repeat(501) }, "use_case (too_long)"],
    [{ text: "   " }, "text (missing)"],
    [{}, "text (missing)"],
    [{ text: 7 }, "text (not_a_string)"],
    [{ text: "ok", email: "a" }, "email (unknown_field)"],
    [{ text: "ok", ...CALLER }, "caller_agent (unknown_field)"],
  ]) {
    const r = await rpc(srv, "request_feature", args);
    assert.equal(r.error?.code, -32602, JSON.stringify(args).slice(0, 80));
    assert.ok(r.error.message.includes(needle), r.error.message);
    for (const v of Object.values(args)) if (typeof v === "string" && v.length > 8 && v.trim()) assert.ok(!r.error.message.includes(v), "never echoed");
  }
  assert.equal(nf.calls.length, 0, "nothing left the process");
  assert.deepEqual(["0x2::coin::Coin", "std::vector", "at 12:30:45", "ratio 1.5:100"].map(hasIpLiteral), [false, false, false, false]);
  for (const [status, body, code] of [[429, { error: "rate_limited", detail: "Feature request limit reached (5 per caller per UTC day).", limit: 5, remaining: 0, reset: NOW }, "rate_limited"],
    [400, { error: "bad_request", detail: "text (email_address)", problems: [{ field: "text", reason: "email_address" }] }, "bad_request"],
    [503, { error: "storage_unavailable", detail: "We could not confirm that your feature request was saved." }, "storage_unavailable"]]) {
    const r = await rpc(new PactaMcpServer({ x402Url: GW, fetchImpl: rec(() => mockRes(status, body)) }), "request_feature", { text: "Solana support" });
    const e = bodyOf(r);
    assert.deepEqual([r.result.isError, e.code, e.status], [true, code, status]);
    if (status === 429) assert.deepEqual([e.limit, e.remaining, e.reset], [5, 0, NOW]);
  }
  const off = never();
  const r0 = await rpc(new PactaMcpServer({ x402Url: "", fetchImpl: off }), "request_feature", { text: "Solana support" });
  assert.deepEqual([r0.result.isError, bodyOf(r0).code], [true, "gateway_not_configured"]);
  assert.equal(off.calls.length, 0);
});

test("default gateway: PACTA_X402_URL unset -> https://api.pacta.wtf; explicit x402Url / env win; an empty value keeps the server local-only", () => {
  const prev = process.env.PACTA_X402_URL;
  try {
    delete process.env.PACTA_X402_URL;
    assert.equal(new PactaMcpServer({}).x402Url, X402_DEFAULTS.gatewayUrl);
    assert.equal(new PactaMcpServer({ x402Url: GW }).x402Url, GW);
    assert.equal(new PactaMcpServer({ x402Url: "" }).x402Url, null);
    process.env.PACTA_X402_URL = "http://127.0.0.1:8787";
    assert.equal(new PactaMcpServer({}).x402Url, "http://127.0.0.1:8787");
    process.env.PACTA_X402_URL = "  ";
    assert.equal(new PactaMcpServer({}).x402Url, null);
  } finally {
    if (prev === undefined) delete process.env.PACTA_X402_URL;
    else process.env.PACTA_X402_URL = prev;
  }
});
