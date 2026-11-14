// pacta_list_proposals over an injected fetchImpl and over a local proposalsPath fixture. No network, no listeners.
// test/fixtures/proposals.sample.json is hand-written (titles say "Fixture:"; addresses and block hashes are
// synthetic). It uses the exact key set of the site-generated pacta.governance_proposals_feed.v1.
import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { PactaMcpServer, PROPOSALS_URLS, PROPOSALS_SCHEMA, PROPOSAL_FORUMS } from "../src/server.mjs";

delete process.env.PACTA_PROPOSALS_PATH;

const FIXTURE_PATH = fileURLToPath(new URL("./fixtures/proposals.sample.json", import.meta.url));
const FEED = JSON.parse(readFileSync(FIXTURE_PATH, "utf8"));
const offline = async () => {
  throw new Error("offline");
};
const mockRes = (status, body) => ({
  ok: status >= 200 && status < 300,
  status,
  headers: { get: () => null },
  text: async () => (typeof body === "string" ? body : JSON.stringify(body)),
});
const callMsg = (id, name, args) => ({ jsonrpc: "2.0", id, method: "tools/call", params: { name, arguments: args } });
const rejectsCode = async (p, code) => {
  let err;
  await assert.rejects(p, (e) => ((err = e), e.code === code));
  return err;
};

test("proposals fixture matches the feed schema (keys, one entry per forum, counts)", () => {
  assert.equal(FEED.schema, PROPOSALS_SCHEMA);
  assert.deepEqual(FEED.generated_from, ["/api/v1/onboarding.json", "/api/v1/index.json"]);
  assert.ok(FEED.proposals.length >= 4);
  assert.deepEqual([...new Set(FEED.proposals.map((p) => p.forum))].sort(), [...PROPOSAL_FORUMS].sort());
  assert.equal(FEED.counts.total, FEED.proposals.length);
  const keys = [
    "proposal_id", "forum", "topic_id", "title", "forum_url", "chain", "chain_id", "pinned_block_number",
    "pinned_block_hash", "source_feed", "source_record_ids", "brief_url", "control_plane_summary",
    "recommended_sentinel_predicates", "repro_commands",
  ].sort();
  for (const p of FEED.proposals) {
    assert.deepEqual(Object.keys(p).sort(), keys, p.proposal_id);
    assert.equal(p.proposal_id, `${p.forum}-${p.topic_id}`);
    assert.equal(p.chain_id, p.chain === "base" ? 8453 : 1);
    assert.match(p.pinned_block_hash, /^0x[0-9a-f]{64}$/);
    assert.ok(Number.isInteger(p.pinned_block_number));
    assert.ok(["/api/v1/onboarding.json", "/api/v1/index.json"].includes(p.source_feed));
    assert.ok(p.brief_url === null || typeof p.brief_url === "string");
    assert.equal(FEED.counts.by_forum[p.forum], FEED.proposals.filter((q) => q.forum === p.forum).length);
  }
});

test("proposalsPath fixture: filters (forum, topic_id, chain), limit, compact output, include_repro", async () => {
  const srv = new PactaMcpServer({ proposalsPath: FIXTURE_PATH, fetchImpl: offline });

  const all = await srv.callTool("pacta_list_proposals", {});
  assert.equal(all.source, FIXTURE_PATH);
  assert.equal(all.schema, PROPOSALS_SCHEMA);
  assert.equal(all.generated_at, FEED.generated_at);
  assert.deepEqual(all.counts, FEED.counts);
  assert.equal(all.total_in_feed, FEED.proposals.length);
  assert.equal(all.matched_count, FEED.proposals.length);
  assert.equal(all.filters.limit, 25);
  for (const p of all.proposals) assert.equal("repro_commands" in p, false, "compact by default");

  const aave = await srv.callTool("pacta_list_proposals", { forum: "aave" });
  assert.equal(aave.matched_count, 2);
  assert.ok(aave.proposals.every((p) => p.forum === "aave"));

  const topic = await srv.callTool("pacta_list_proposals", { topic_id: 25128 });
  assert.deepEqual(topic.proposals.map((p) => p.proposal_id), ["aave-25128"]);
  assert.equal((await srv.callTool("pacta_list_proposals", { topic_id: "25128" })).matched_count, 1);

  const base = await srv.callTool("pacta_list_proposals", { chain: "base" });
  assert.deepEqual(base.proposals.map((p) => p.proposal_id).sort(), ["aave-25301", "morpho-842"]);
  assert.ok(base.proposals.every((p) => p.chain_id === 8453));

  const combo = await srv.callTool("pacta_list_proposals", { forum: "aave", chain: "base" });
  assert.deepEqual(combo.proposals.map((p) => p.proposal_id), ["aave-25301"]);
  assert.equal((await srv.callTool("pacta_list_proposals", { forum: "sky", chain: "base" })).matched_count, 0);

  const limited = await srv.callTool("pacta_list_proposals", { limit: 2 });
  assert.equal(limited.matched_count, FEED.proposals.length);
  assert.equal(limited.returned_count, 2);
  assert.equal(limited.proposals.length, 2);

  const repro = await srv.callTool("pacta_list_proposals", { forum: "sky", include_repro: true });
  assert.deepEqual(repro.proposals[0].repro_commands, FEED.proposals.find((p) => p.forum === "sky").repro_commands);
  assert.equal(repro.filters.include_repro, true);
});

test("pacta_list_proposals rejects bad arguments with invalid_argument", async () => {
  const srv = new PactaMcpServer({ proposalsPath: FIXTURE_PATH, fetchImpl: offline });
  for (const args of [
    { forum: "compound" },
    { forum: 3 },
    { topic_id: 0 },
    { topic_id: -4 },
    { topic_id: 1.5 },
    { topic_id: "12a" },
    { chain: "arbitrum" },
    { limit: 0 },
    { limit: 101 },
    { limit: "5" },
    { include_repro: "yes" },
  ]) {
    await rejectsCode(srv.callTool("pacta_list_proposals", args), "invalid_argument");
  }
});

test("injected fetch: primary URL, Accept header, abort signal; fallback URL when primary fails; cache", async () => {
  const seen = [];
  const srv = new PactaMcpServer({
    fetchImpl: async (u, init) => {
      seen.push(u);
      assert.ok(init.signal instanceof AbortSignal);
      assert.equal(init.headers.Accept, "application/json");
      return mockRes(200, FEED);
    },
  });
  const res = await srv.callTool("pacta_list_proposals", { forum: "morpho" });
  assert.equal(res.source, PROPOSALS_URLS[0]);
  assert.equal(res.source, "https://pacta.wtf/api/v1/proposals.json");
  assert.deepEqual(res.proposals.map((p) => p.proposal_id), ["morpho-842"]);
  await srv.callTool("pacta_list_proposals", {});
  assert.deepEqual(seen, [PROPOSALS_URLS[0]], "second call served from cache");

  const fb = new PactaMcpServer({
    fetchImpl: async (u) => (u.includes("pacta.wtf") ? mockRes(503, "down") : mockRes(200, FEED)),
  });
  const r2 = await fb.callTool("pacta_list_proposals", {});
  assert.equal(r2.source, "https://fractal-neurons.github.io/pacta/api/v1/proposals.json");
  assert.equal(r2.total_in_feed, FEED.proposals.length);
});

test("schema rejection: wrong schema / missing proposals array / non-object entries", async () => {
  const wrong = { ...FEED, schema: "pacta.counterparty_control_index.v1" };
  // Remote: every URL serves the wrong schema -> feed_unavailable listing invalid_feed per attempt.
  const remote = new PactaMcpServer({ fetchImpl: async () => mockRes(200, wrong) });
  const err = await rejectsCode(remote.callTool("pacta_list_proposals", {}), "feed_unavailable");
  assert.deepEqual(err.details.attempts.map((a) => a.url), [...PROPOSALS_URLS]);
  assert.ok(err.details.attempts.every((a) => a.code === "invalid_feed" && a.reason === "bad_schema"));

  // In-memory data is validated directly.
  const mem = new PactaMcpServer({ proposalsData: wrong, fetchImpl: offline });
  const e2 = await rejectsCode(mem.callTool("pacta_list_proposals", {}), "invalid_feed");
  assert.equal(e2.details.reason, "bad_schema");
  assert.equal(e2.details.schema, "pacta.counterparty_control_index.v1");

  const noArr = new PactaMcpServer({ proposalsData: { schema: PROPOSALS_SCHEMA, proposals: {} }, fetchImpl: offline });
  assert.equal((await rejectsCode(noArr.callTool("pacta_list_proposals", {}), "invalid_feed")).details.reason, "bad_proposals");

  const badEntry = new PactaMcpServer({ proposalsData: { schema: PROPOSALS_SCHEMA, proposals: [FEED.proposals[0], "x"] }, fetchImpl: offline });
  const e3 = await rejectsCode(badEntry.callTool("pacta_list_proposals", {}), "invalid_feed");
  assert.equal(e3.details.reason, "bad_proposal_entry");
  assert.equal(e3.details.index, 1);

  // Malformed JSON from upstream.
  const junk = new PactaMcpServer({ fetchImpl: async () => mockRes(200, "<html>not json</html>") });
  const e4 = await rejectsCode(junk.callTool("pacta_list_proposals", {}), "feed_unavailable");
  assert.ok(e4.details.attempts.every((a) => a.code === "invalid_feed" && a.reason === "bad_json"));

  // Missing local file -> feed_unavailable (no fallback to the network when a path is configured).
  const missing = new PactaMcpServer({
    proposalsPath: fileURLToPath(new URL("./fixtures/does-not-exist.json", import.meta.url)),
    fetchImpl: async () => {
      throw new Error("must not fetch when proposalsPath is set");
    },
  });
  await rejectsCode(missing.callTool("pacta_list_proposals", {}), "feed_unavailable");
});

test("timeout and transport errors are structured (per-URL attempts) and surface as isError over JSON-RPC", async () => {
  const hung = new PactaMcpServer({ timeoutMs: 25, fetchImpl: () => new Promise(() => {}) });
  const err = await rejectsCode(hung.callTool("pacta_list_proposals", {}), "feed_unavailable");
  assert.deepEqual(err.details.attempts.map((a) => a.code), ["timeout", "timeout"]);

  const honouring = new PactaMcpServer({
    timeoutMs: 25,
    fetchImpl: (_u, init) => new Promise((_, reject) => init.signal.addEventListener("abort", () => reject(init.signal.reason))),
  });
  const e2 = await rejectsCode(honouring.callTool("pacta_list_proposals", {}), "feed_unavailable");
  assert.ok(e2.details.attempts.every((a) => a.code === "timeout"));

  const mixed = new PactaMcpServer({
    fetchImpl: async (u) => {
      if (u.includes("pacta.wtf")) throw new Error("ECONNRESET");
      return mockRes(404, "nope");
    },
  });
  const reply = await mixed.handleMessage(callMsg(7, "pacta_list_proposals", {}));
  assert.equal(reply.result.isError, true);
  const body = JSON.parse(reply.result.content[0].text);
  assert.equal(body.code, "feed_unavailable");
  assert.equal(body.attempts[0].code, "network_error");
  assert.equal(body.attempts[1].code, "upstream_http_error");
  assert.equal(body.attempts[1].status, 404);

  const bad = await new PactaMcpServer({ proposalsPath: FIXTURE_PATH, fetchImpl: offline }).handleMessage(
    callMsg(8, "pacta_list_proposals", { forum: "nope" })
  );
  assert.equal(bad.result.isError, true);
  assert.equal(JSON.parse(bad.result.content[0].text).code, "invalid_argument");
});

test("PACTA_PROPOSALS_PATH env var is honoured like PACTA_INDEX_PATH", async () => {
  process.env.PACTA_PROPOSALS_PATH = FIXTURE_PATH;
  try {
    const srv = new PactaMcpServer({ fetchImpl: offline });
    assert.equal(srv.proposalsPath, FIXTURE_PATH);
    const res = await srv.callTool("pacta_list_proposals", { forum: "euler" });
    assert.equal(res.source, FIXTURE_PATH);
    assert.deepEqual(res.proposals.map((p) => p.proposal_id), ["euler-1204"]);
  } finally {
    delete process.env.PACTA_PROPOSALS_PATH;
  }
});

test("tools/list includes pacta_list_proposals with its filter schema (free, x402 off and on)", async () => {
  for (const x402Url of [null, "https://x402.example.invalid"]) {
    const srv = new PactaMcpServer({ x402Url, fetchImpl: offline });
    const list = await srv.handleMessage({ jsonrpc: "2.0", id: 1, method: "tools/list" });
    const t = list.result.tools.find((x) => x.name === "pacta_list_proposals");
    assert.ok(t, `listed with x402Url=${x402Url}`);
    assert.deepEqual(t.inputSchema.properties.forum.enum, ["aave", "euler", "morpho", "sky"]);
    assert.deepEqual(t.inputSchema.properties.chain.enum, ["ethereum", "base"]);
    assert.equal(t.inputSchema.properties.topic_id.type, "integer");
    assert.equal(t.inputSchema.properties.limit.maximum, 100);
    assert.equal(t.inputSchema.properties.include_repro.type, "boolean");
    assert.equal(t.inputSchema.additionalProperties, false);
  }
});

// The real feed generated by the site build (pacta-github-repo tools/build_b2a_feeds.py), copied verbatim as a fixture.
const REAL_FEED = fileURLToPath(new URL("./fixtures/proposals.pacta-wtf.json", import.meta.url));

test("real pacta.wtf proposals.json: schema accepted, all 4 forums, Euler entries on Base, repro commands pinned", async () => {
  const srv = new PactaMcpServer({ proposalsPath: REAL_FEED, fetchImpl: offline });
  const all = await srv.callTool("pacta_list_proposals", { limit: 100, include_repro: true });
  const raw = JSON.parse(readFileSync(REAL_FEED, "utf8"));
  assert.equal(raw.schema, PROPOSALS_SCHEMA);
  const list = all.proposals;
  assert.equal(list.length, raw.proposals.length);
  assert.deepEqual([...new Set(list.map((p) => p.forum))].sort(), ["aave", "euler", "morpho", "sky"]);
  for (const p of list) {
    assert.match(p.pinned_block_hash, /^0x[0-9a-f]{64}$/);
    assert.ok(p.repro_commands.length > 0 && p.repro_commands.some((c) => c.includes(`--block ${p.pinned_block_number}`)));
  }
  const euler = await srv.callTool("pacta_list_proposals", { forum: "euler" });
  assert.ok(euler.proposals.length >= 2 && euler.proposals.every((p) => p.chain === "base"));
  const sky = await srv.callTool("pacta_list_proposals", { forum: "sky", topic_id: 28390 });
  assert.equal(sky.proposals.length, 1);
});
