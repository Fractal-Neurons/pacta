// pacta_submit_request (stdio, 0.1.5): listed only with the gateway on (the default), exact annotations / _meta / JSON Schema 2020-12,
// local secret / HTML / field checks (nothing is sent on a refusal), and forwarding to POST <PACTA_X402_URL>/v1/requests.
// Also: annotations + _meta on all 14 read-only tools and coverage_gap_hint on lookup misses.
import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { PactaMcpServer, TOOL_DEFINITIONS, READ_ONLY_TOOLS, SUBMIT_TOOL, SERVER_INFO, COVERAGE_GAP_HINT, demandGuard, hasIpLiteral } from "../src/server.mjs";
import { CALLER } from "./helpers.mjs";

const GW = "https://gateway.example.test";
const REQ = { ...CALLER, request_type: "missing_protocol", target_subject: "pendle-v2", requested_capability: "Index the Pendle V2 router timelock on Arbitrum One.",
  urgency_track: "community_queue_free" };
const rec = (reply) => {
  const calls = [];
  const f = async (url, init = {}) => { calls.push({ url: String(url), init }); return reply(String(url), init); };
  f.calls = calls;
  return f;
};
const json = (status, obj) => new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });
const call = (srv, args, name = "pacta_submit_request") => srv.handleMessage({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } });

test("tools/list: 14 read-only tools (annotations readOnlyHint/destructiveHint/openWorldHint + _meta) + 2 opt-in request tools (request_feature, pacta_submit_request)", async () => {
  assert.equal(SERVER_INFO.version, "0.1.8");
  assert.equal(READ_ONLY_TOOLS.length, 14);
  assert.equal(TOOL_DEFINITIONS.length, 16);
  assert.deepEqual(TOOL_DEFINITIONS.map((t) => t.name).slice(-2), ["request_feature", "pacta_submit_request"]);
  assert.deepEqual(TOOL_DEFINITIONS.filter((t) => t.annotations.readOnlyHint !== true).map((t) => t.name), ["request_feature", "pacta_submit_request"]);
  for (const t of READ_ONLY_TOOLS) {
    assert.deepEqual([t.annotations.readOnlyHint, t.annotations.destructiveHint, t.annotations.openWorldHint], [true, false, false], t.name);
    assert.equal(typeof t.title, "string", t.name);
    assert.equal(t.annotations.title, t.title, t.name);
    assert.deepEqual(Object.keys(t._meta), ["resultType", "ttlMs", "cacheScope"], t.name);
    assert.ok(t._meta.ttlMs > 0 && t._meta.cacheScope === "public", t.name);
  }
  assert.deepEqual(SUBMIT_TOOL.annotations, { title: "Submit Pacta Coverage or Feature Request", readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: false });
  assert.deepEqual(SUBMIT_TOOL._meta, { resultType: "demand_receipt", ttlMs: 0, cacheScope: "none" });
  const s = SUBMIT_TOOL.inputSchema;
  assert.equal(s.$schema, "https://json-schema.org/draft/2020-12/schema");
  assert.deepEqual(s.required, ["request_type", "target_subject", "requested_capability", "urgency_track"]);
  assert.deepEqual(Object.keys(s.properties).sort(), [...s.required, "forum_proposal_url", "contact_handle"].sort(), "clean schema: 0 caller fields");
  assert.equal(s.properties.contact_handle.description, "Optional work email, Telegram @handle, or GitHub handle ONLY if the human user explicitly asks for follow-up or an invoice. NEVER guess or populate without explicit user consent; never pass keys or secrets.");
  const local = new PactaMcpServer({ x402Url: "", fetchImpl: rec(() => { throw new Error("no network"); }) });
  const gw = new PactaMcpServer({ x402Url: GW, fetchImpl: rec(() => { throw new Error("no network"); }) });
  const dflt = new PactaMcpServer({ fetchImpl: rec(() => { throw new Error("no network"); }) });
  const names = async (srv) => (await srv.handleMessage({ jsonrpc: "2.0", id: 1, method: "tools/list" })).result.tools.map((t) => t.name);
  assert.equal((await names(gw)).length, 16);
  assert.deepEqual(await names(dflt), await names(gw), "the gateway is on by default (https://api.pacta.wtf)");
  assert.ok(!(await names(local)).includes("pacta_submit_request"), "not listed with the gateway off (zero network)");
});

test("pacta_submit_request forwards one JSON POST to <PACTA_X402_URL>/v1/requests and returns the receipt", async () => {
  const receipt = { schema: "pacta.demand_receipt.v1", request_id: "REQ-2026-0123abcd", status: "queued", demand_votes: 1, fast_track_url: "https://pacta.wtf/request/?tier=community&protocol=pendle-v2" };
  const f = rec(() => json(200, receipt));
  const srv = new PactaMcpServer({ x402Url: GW, fetchImpl: f });
  const r = await call(srv, { ...REQ, contact_handle: "@pacta_ops" });
  assert.equal(r.result.isError, false);
  assert.deepEqual(JSON.parse(r.result.content[0].text), { ...receipt, source: "gateway" });
  assert.equal(f.calls.length, 1);
  assert.equal(f.calls[0].url, GW + "/v1/requests");
  assert.deepEqual([f.calls[0].init.method, f.calls[0].init.headers["Content-Type"], f.calls[0].init.redirect], ["POST", "application/json", "error"]);
  assert.deepEqual(JSON.parse(f.calls[0].init.body), { ...REQ, contact_handle: "@pacta_ops" });
  // upstream refusals are tool errors with the gateway's code
  const bad = await call(new PactaMcpServer({ x402Url: GW, fetchImpl: rec(() => json(400, { error: "invalid_request", detail: "target_subject (personal_data)", problems: [{ field: "target_subject", reason: "personal_data" }] })) }), REQ);
  assert.deepEqual([bad.result.isError, JSON.parse(bad.result.content[0].text).code], [true, "invalid_request"]);
  const rl = await call(new PactaMcpServer({ x402Url: GW, fetchImpl: rec(() => json(429, { error: "rate_limited", detail: "more than 5 requests per hour", retryAfterSeconds: 120 })) }), REQ);
  assert.deepEqual([rl.result.isError, JSON.parse(rl.result.content[0].text).code], [true, "rate_limited"]);
});

test("pacta_submit_request refuses secrets, HTML, unknown / missing / bad fields LOCALLY (-32602, nothing sent, values never echoed); unset URL sends nothing", async () => {
  const f = rec(() => { throw new Error("must not be called"); });
  const srv = new PactaMcpServer({ x402Url: GW, fetchImpl: f });
  const key = "ab".repeat(32);
  for (const [patch, needle] of [
    [{ requested_capability: "my key " + key }, "requested_capability (secret_or_key)"],
    [{ requested_capability: "token " + "sk" + "-" + "A1b2C3d4E5f6G7h8" }, "requested_capability (secret_or_key)"],
    [{ requested_capability: "apple river stone cloud tiger lemon piano rocket candle forest silver orange" }, "requested_capability (secret_or_key)"],
    [{ target_subject: "<b>x</b>" }, "target_subject (html)"],
    [{ extra: "x" }, "extra (unknown_field)"],
    [{ urgency_track: undefined }, "urgency_track (missing)"],
    [{ urgency_track: "asap" }, "urgency_track (invalid"],
    [{ target_subject: 7 }, "target_subject (invalid"],
  ]) {
    const r = await call(srv, { ...REQ, ...patch });
    assert.equal(r.error?.code, -32602, JSON.stringify(patch));
    assert.ok(r.error.message.includes(needle), r.error.message);
    for (const v of Object.values(patch)) if (typeof v === "string" && v.length > 8) assert.ok(!r.error.message.includes(v), "never echoed");
  }
  assert.equal(f.calls.length, 0, "nothing left the process");
  // omitted or invalid caller attribution fields never reject locally and are silently stripped before POST /v1/requests
  const receipt = { schema: "pacta.demand_receipt.v1", request_id: "REQ-2026-0123abcd", status: "queued", demand_votes: 1, fast_track_url: "https://pacta.wtf/request/?tier=community&protocol=pendle-v2" };
  const fOk = rec(() => json(200, receipt));
  const srvOk = new PactaMcpServer({ x402Url: GW, fetchImpl: fOk });
  const rDrop = await call(srvOk, { ...REQ, caller_agent: "bob@example.org", requester_role: "ceo", caller_purpose: undefined });
  assert.equal(rDrop.result.isError, false);
  const sentBody = JSON.parse(fOk.calls[0].init.body);
  assert.equal(sentBody.caller_agent, undefined);
  assert.equal(sentBody.requester_role, undefined);
  assert.equal(sentBody.caller_purpose, undefined);
  assert.equal(demandGuard("tx:0x" + key), null);
  const off = await call(new PactaMcpServer({ x402Url: "", fetchImpl: f }), REQ);
  assert.deepEqual([off.result.isError, JSON.parse(off.result.content[0].text).code], [true, "gateway_not_configured"]);
  assert.equal(f.calls.length, 0);
});

test("pacta_lookup_protocol: a miss carries coverage_gap_hint (embedded catalog and gateway answer); a match does not", async () => {
  const local = new PactaMcpServer({ x402Url: "", fetchImpl: rec(() => { throw new Error("no network"); }) });
  const miss = JSON.parse((await call(local, { ...CALLER, query: "zzunknownprotocol" }, "pacta_lookup_protocol")).result.content[0].text);
  assert.deepEqual([miss.totalMatches, miss.coverage_gap_hint], [0, COVERAGE_GAP_HINT]);
  const hit = JSON.parse((await call(local, { ...CALLER, query: "ethena" }, "pacta_lookup_protocol")).result.content[0].text);
  assert.ok(hit.totalMatches > 0 && !("coverage_gap_hint" in hit));
  const old = { schema: "pacta.protocol_lookup.v1", query: "zz", totalMatches: 0, count: 0, results: [] };   // a pre-0.1.4 gateway answer
  const gw = new PactaMcpServer({ x402Url: GW, fetchImpl: rec(() => json(200, old)) });
  const g = JSON.parse((await call(gw, { ...CALLER, query: "zz" }, "pacta_lookup_protocol")).result.content[0].text);
  assert.deepEqual([g.source, g.coverage_gap_hint], ["gateway", COVERAGE_GAP_HINT]);
});

test("F5: PERSONAL_RES refuses IPv6 (::, bracketed, 3+ colon-hex groups) and host:port; keeps <chain>:0x<40>, tx:/block: hashes and 'Note:' punctuation", async () => {
  const { PERSONAL_RES, requestTargetOk } = await import("../src/lookup.mjs");
  const hit = (t) => PERSONAL_RES.some((re) => re.test(t));
  for (const t of ["::1", "::", "fe80::1", "fe80::1%eth0", "2001:db8::abcd", "::ffff:10.0.0.1", "[::1]", "[2001:db8::1]", "[2001:db8::1]:8080", "[fe80::1%eth0]", "2001:0db8:85a3:0000:0000:8a2e:0370:7334", "fe80:0:0:0:202:b3ff:fe1e:8329", "localhost:3000", "node.example.org:8545"]) {
    assert.ok(hit(t), t);
    assert.ok(hit("Check node " + t + " control plane"), "in a sentence: " + t);
  }
  for (const t of ["base:0x833589fcd6edb6e08f4c7c32d4f71b54bda02913", "tx:0x" + "ab".repeat(32), "block:0x" + "cd".repeat(32), "Note: check M0 minter delay",
    "Pendle V2: router timelock", "index Morpho at 10:30 UTC"]) assert.ok(!hit(t), t);
  assert.deepEqual(["base:0x" + "ab".repeat(20), "pendle v2", "note: x", "fe80::1", "a:0x" + "ab".repeat(20)].map(requestTargetOk), [true, true, false, false, false]);
});

test("F5b: punctuation-wrapped host:port and @handle are refused; times, ratios, 'Note:' and tx:/chain ids still pass", async () => {
  const { PERSONAL_RES } = await import("../src/lookup.mjs");
  const hit = (t) => PERSONAL_RES.some((re) => re.test(t));
  for (const t of ["(localhost:3000)", "(node.example.org:8545)", "\"localhost:3000\"", ",node.example.org:8545;", "(@sample_ops)"]) assert.ok(hit("Check " + t + " endpoint"), t);
  for (const t of ["at 10:30 UTC", "ratio 1.5:100", "Note: check M0 minter delay", "Diff tx:0xabababababababababababababababababababababababababababababababab against docs", "index base:0xabababababababababababababababababababab please"]) assert.ok(!hit(t), t);
  assert.ok(hit("mail ops" + "@" + "pendle-team.xyz"), "e-mails stay refused");
});

// request_feature's local pre-check is the hosted worker's coarse hasIpLiteral (the same block, byte for byte). The vectors below
// are the worker suite's own (worker.test.mjs): R1 contextual, R2 adjacent, R3 structural and R4 IP forms, the shapes the coarse
// filter refuses on purpose, and the agent-text controls.
const CONTEXTUAL_IPS = ["node=2001:db8::1", "address:fe80::1", "[fe80::1%eth0]:8080"];
const R3_IPS = ["addr=2001:db8::1&port=443", "server[0]:fe80::1", "IPv6\u21922001:db8::1", "ip%3D2001:db8::1", "node%20fe80::1", "fe80::1-2001:db8::2",
  "2001:db8::1%26port%3D443", "tcp/2001:db8::1/64", "_fe80::1_", "-::1-", "fe80::1...", "1st_peer:fe80::1", "0-node:fe80::1", "99999:fe80::1",
  "IPv6\u2014fe80::1", "addr\uff1afe80::1", "\u201cfe80::1\u201d", "host#fe80::1", "a+2001:db8::1", "q?ip=fe80::1", "1:2:3:4:5:6:7::",
  "::2:3:4:5:6:7:8", "peer.ip:2001:db8::1%eth0x/128", "net.addr=192.0.2.9/24", "zone:fe80::1%en0x", "[FE80::1%ETH0X]:443", "0abcde:fe80::1",
  "fe80::1:primary", "host=2001:db8::1:http", "2001%3Adb8%3A%3A1", "ip=10%2E0%2E0%2E1", "2001%253Adb8%253A%253A1", "My server is 192.168.1.1.",
  "64:ff9b::192.0.2.1.", "node-1:1:2:3:4:5:6:7:8%en0:http"];
const ADJACENT_IPS = ["peer.ip:2001:db8::1", "cfg.host.addr:fe80::1", "address:fe80::1%eth0x", "fe80::1%eth0x", "server-1:fe80::1%en0",
  "addr=[fe80::1%eth0]:8080", "node=2001:db8::1/64", "ip_address:fe80::1/64", "a.b:c.d:fe80::1", "eth0x:fe80::1"];
const R4_IPS = ["peer.ip:::ffff:c000:201", "server[0]:::ffff:c000:201", "address:::1", "node-1:::1"];
const COARSE_REFUSED = ["2001:db8:0:1", "a:b:c", "1:2:3:4:5:6:7:8:9", "fe80:::1", "see std:: docs", "12:30:45:", "fe80:12:30:45", "v.1:2:3",
  "ffff:12:30:45", "00:1A:2B:3C:4D:5E", "1:2:3:4:5:6:7:8::", "a::b::c", "crate::abc::def", "ratio 3:2:1", "v1.2.3.4.5 release", "1.2.3.4.5.",
  "fee.cfg:12:30:45:pm", "dead::Foo", "Vec::new:x", "12345::"];
const AGENT_TEXT = ["0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B", "base:0xabc", "ethereum:0xA35b1B31Ce002FBF2058D22F30f95D405200A15b",
  "eip155:8453:0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "12:30", "09:30 UTC", "12:30:45", "3:1", "10:1", "100:1",
  "https://api.pacta.wtf:8443/v1/check", "http://localhost:8545", "0x2::coin::Coin", "0x2::fee::Fee", "sui::coin", "std::vector",
  "cfg.host:std::vector", "@openzeppelin/contracts",
  "std::vec::Vec", "Vec::new", "std::fs::read", "alloc::vec::Vec", "time:12:30:45", "ETA:12:30:45", "fee.cfg:12:30:45"];
test("request_feature local IP check = the hosted worker's coarse hasIpLiteral: R1-R4 forms and the coarse shapes refused locally in text and use_case (-32602, \"please remove addresses and resend\", nothing sent); agent text (0x addresses, chain:address, times, ratios, URLs with a port, Move / npm paths) is forwarded", async () => {
  const IPS = ["192.168.1.1", "::1", "fe80::1", "2001:db8::1", "2001:0db8:85a3:0000:0000:8a2e:0370:7334", "[2001:db8::1]:8080", "::ffff:192.0.2.1"];
  const OK = ["@openzeppelin/contracts", "sui::coin", "0x2::coin::Coin", "0x2::fee::Fee", "std::vector", "12:30:45"];
  for (const s of [...IPS, "fe80::1%eth0", "[fe80::1%eth0]", "(::1)", "node fe80::1.", "2001:DB8::A, please", "[::1]", "fe80:0:0:0:202:b3ff:fe1e:8329",
    "1:2:3:4:5:6:7:8", "2001:db8::", "::", "fe80::1/64", "fe80::/10", "2001:db8::1/128.", "node fe80::1: down", "10.0.0.0/8",
    // P1C-01: contextual forms (key=value, label:, a zone inside brackets)
    ...CONTEXTUAL_IPS, "ip=::1", "host:2001:db8::1/64", "peer = fe80::1", "addr:[::1]", "[2001:db8::1%25en0]", "a=1,b=fe80::2;c",
    ...ADJACENT_IPS, "my node peer.ip:2001:db8::1.", "x:y:z:2001:db8::1", "ADDR:FE80::1%ETH0X", ...R3_IPS, ...R4_IPS, ...COARSE_REFUSED])
    assert.equal(hasIpLiteral(s), true, s);
  for (const s of [...OK, ...AGENT_TEXT, "at 12:30 UTC", "v1.2.3 and 10.0", "Note: Base::Bridge", "tx:0x1", "aptos 0x1::coin::CoinStore",
    "ethereum:0x" + "ab".repeat(20), "@openzeppelin/contracts/token/ERC20", "path a/b/12", "key=value", "chain:base", "time=12:30:45",
    "label:sui::coin", "module=std::vector", "at=12:30", "x=0x2::coin::Coin", "peer.ip:0x2::coin::Coin", "cfg.host:std::vector", "eth0x rocks",
    "0xabc%eth0", "pkg.mod:sui::coin", "0X2::Coin", "0x2::coin::Coin<0x2::sui::SUI>", "a.b:ethereum:0x" + "12".repeat(20),
    "a.b:c.d:0x2::coin::Coin", "0X" + "CD".repeat(20), "module=0x2::coin::Coin", "2026-11-25T12:30:45Z", "12:30:45.123", "dead:beef",
    "see [docs](https://x.test/a:b)", "IPv6\u2192 none", "100%25 sure", "50%2C 30%", "100% organic", "%FF%FE", "tokio::sync::Mutex"])
    assert.equal(hasIpLiteral(s), false, s);
  const nf = rec(() => { throw new Error("must not be called"); });
  const srv = new PactaMcpServer({ x402Url: GW, fetchImpl: nf });
  for (const ip of [...CONTEXTUAL_IPS, ...ADJACENT_IPS, ...R3_IPS, ...R4_IPS, ...COARSE_REFUSED]) {
    for (const [args, field] of [[{ text: ip }, "text"], [{ text: "Solana support", use_case: `call ${ip}` }, "use_case"]]) {
      const r = await call(srv, args, "request_feature");
      assert.equal(r.error?.code, -32602, JSON.stringify(args));
      assert.ok(r.error.message.includes(`${field} (ip_address); please remove addresses and resend. `) && r.error.message.includes("nothing was sent"), r.error.message);
    }
  }
  assert.equal(nf.calls.length, 0, "nothing left the process");
  const receipt = { ok: true, request_id: "FREQ-2026-0123abcd", message: "Thank you", meter: { limit: 5, remaining: 4, reset: 1 } };
  const f = rec(() => json(200, receipt));
  const fwd = new PactaMcpServer({ x402Url: GW, fetchImpl: f });
  const allowed = [...AGENT_TEXT, "tokio::sync::Mutex", "100% organic"];
  for (const ok of allowed) {
    const r = await call(fwd, { text: `Need coverage for ${ok}` }, "request_feature");
    assert.equal(r.result.isError, false, ok);
  }
  assert.deepEqual(f.calls.map((c) => [c.url, JSON.parse(c.init.body).text]), allowed.map((ok) => [`${GW}/v1/feature-request`, `Need coverage for ${ok}`]));
});
