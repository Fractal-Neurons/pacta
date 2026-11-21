// pacta_submit_request (stdio, 0.1.5): listed only with PACTA_X402_URL, exact annotations / _meta / JSON Schema 2020-12,
// local secret / HTML / field checks (nothing is sent on a refusal), and forwarding to POST <PACTA_X402_URL>/v1/requests.
// Also: annotations + _meta on all 10 read-only tools and coverage_gap_hint on lookup misses.
import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { PactaMcpServer, TOOL_DEFINITIONS, READ_ONLY_TOOLS, SUBMIT_TOOL, SERVER_INFO, COVERAGE_GAP_HINT, demandGuard } from "../src/server.mjs";
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

test("0.1.5 tools/list: 11 read-only tools (annotations readOnlyHint/destructiveHint/openWorldHint + _meta) + 1 opt-in pacta_submit_request", async () => {
  assert.equal(SERVER_INFO.version, "0.1.6");
  assert.equal(READ_ONLY_TOOLS.length, 11);
  assert.deepEqual(TOOL_DEFINITIONS.map((t) => t.name).slice(-1), ["pacta_submit_request"]);
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
  assert.deepEqual(Object.keys(s.properties).sort(), ["caller_agent", "requester_role", "caller_purpose", ...s.required, "forum_proposal_url", "contact_handle"].sort());
  assert.equal(s.properties.contact_handle.description, "Optional work email, Telegram @handle, or GitHub handle ONLY if the human user explicitly asks for follow-up or an invoice. NEVER guess or populate without explicit user consent; never pass keys or secrets.");
  const local = new PactaMcpServer({ fetchImpl: rec(() => { throw new Error("no network"); }) });
  const gw = new PactaMcpServer({ x402Url: GW, fetchImpl: rec(() => { throw new Error("no network"); }) });
  const names = async (srv) => (await srv.handleMessage({ jsonrpc: "2.0", id: 1, method: "tools/list" })).result.tools.map((t) => t.name);
  assert.equal((await names(gw)).length, 12);
  assert.ok(!(await names(local)).includes("pacta_submit_request"), "listed only with PACTA_X402_URL (zero network otherwise)");
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
  const off = await call(new PactaMcpServer({ fetchImpl: f }), REQ);
  assert.deepEqual([off.result.isError, JSON.parse(off.result.content[0].text).code], [true, "gateway_not_configured"]);
  assert.equal(f.calls.length, 0);
});

test("pacta_lookup_protocol: a miss carries coverage_gap_hint (embedded catalog and gateway answer); a match does not", async () => {
  const local = new PactaMcpServer({ fetchImpl: rec(() => { throw new Error("no network"); }) });
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
