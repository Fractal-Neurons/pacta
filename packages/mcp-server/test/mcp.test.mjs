// MCP JSON-RPC smoke tests over the in-process handler, the stdio stream wrapper, and the real bin over stdio pipes.
// No sockets, no network: every fetch is injected, and the spawned child only answers initialize / tools/list.
import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { closeSync, openSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { PassThrough } from "node:stream";
import { fileURLToPath } from "node:url";
import { PactaMcpServer, startStdioServer, ALLOWED_PAY_TO, BASE_USDC, encodeXPaymentHeader } from "../src/server.mjs";
import { collectLines, makeScratchDir } from "./helpers.mjs";

const NOW = 1794580000;
const X402_URL = "https://x402.example.invalid";
const FROM = "0x" + "11".repeat(20);
const SIG = "0x" + "12".repeat(65);
const TIMELOCK = "0x2225DAbFfC7F862c99477381E971E8B1FDaB467e";
const OP_ID = "0x2f11a5192f46834e4f7c3318b980e8f17440196e57b4ef198f168f4162ca485a";
const b64 = (v) => Buffer.from(JSON.stringify(v)).toString("base64");
const mockRes = (status, body, headers = {}) => {
  const m = new Map(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  return { ok: status >= 200 && status < 300, status, headers: { get: (k) => m.get(k.toLowerCase()) ?? null }, text: async () => JSON.stringify(body) };
};
const entry = (o = {}) => ({
  scheme: "exact",
  network: "base",
  maxAmountRequired: "250000",
  payTo: ALLOWED_PAY_TO[0],
  maxTimeoutSeconds: 60,
  asset: BASE_USDC,
  extra: { name: "USD Coin", version: "2" },
  ...o,
});
const callMsg = (id, name, args) => ({ jsonrpc: "2.0", id, method: "tools/call", params: { name, arguments: args } });
const textOf = (reply) => JSON.parse(reply.result.content[0].text);

test("in-process tools/list + tools/call: valid 402 challenge, rogue 402 rejected, bad X-PAYMENT rejected offline", async () => {
  let accepts = [entry()];
  const calls = [];
  const srv = new PactaMcpServer({
    x402Url: X402_URL,
    nowSeconds: NOW,
    fetchImpl: async (u, init) => {
      calls.push(u);
      assert.ok(init.signal instanceof AbortSignal);
      return mockRes(402, { x402Version: 1, accepts });
    },
  });
  const list = await srv.handleMessage({ jsonrpc: "2.0", id: 1, method: "tools/list" });
  assert.equal(list.result.tools.length, 9);
  const tl = list.result.tools.find((t) => t.name === "pacta_scan_timelock_op");
  assert.equal(tl.inputSchema.properties.validBeforeSeconds.maximum, 600);

  const ok = await srv.handleMessage(callMsg(2, "pacta_scan_timelock_op", { timelock: TIMELOCK, opId: OP_ID, payer: FROM }));
  assert.equal(ok.result.isError, false);
  const challenge = textOf(ok);
  assert.equal(challenge.eip712TypedData.message.to, ALLOWED_PAY_TO[0]);
  assert.equal(challenge.eip712TypedData.message.value, "250000");
  assert.equal(challenge.eip712TypedData.domain.chainId, 8453);

  accepts = [entry({ payTo: "0x000000000000000000000000000000000000dEaD" }), entry({ maxAmountRequired: "250001" })];
  const rogue = await srv.handleMessage(callMsg(3, "pacta_scan_timelock_op", { timelock: TIMELOCK, opId: OP_ID }));
  assert.equal(rogue.result.isError, true);
  const body = textOf(rogue);
  assert.equal(body.code, "rejected_challenge");
  assert.deepEqual(body.entries.map((e) => e.reasons), [["pay_to_not_allowed"], ["amount_over_route_price"]]);

  const before = calls.length;
  const badPay = await srv.handleMessage(
    callMsg(4, "pacta_live_timelocks", {
      xPaymentHeader: encodeXPaymentHeader({
        signature: SIG,
        authorization: { from: FROM, to: ALLOWED_PAY_TO[0], value: "100001", validAfter: "0", validBefore: String(NOW + 60), nonce: "0x" + "cd".repeat(32) },
      }),
    })
  );
  assert.equal(badPay.result.isError, true);
  assert.equal(textOf(badPay).code, "invalid_x_payment");
  assert.equal(textOf(badPay).reason, "value_over_route_price");
  assert.equal(calls.length, before);

  const badAddr = await srv.handleMessage(
    callMsg(5, "pacta_scan_timelock_op", { timelock: "0xceCf30B925bf40129794A0810622354f2ACCD515", opId: OP_ID })
  );
  assert.equal(textOf(badAddr).code, "invalid_argument");
  assert.equal(calls.length, before);
});

test("server honours PACTA_X402_MAX_ATOMIC (cap below route price rejects the challenge) and clamps to hard ceiling", async () => {
  const prev = process.env.PACTA_X402_MAX_ATOMIC;
  try {
    process.env.PACTA_X402_MAX_ATOMIC = "200000";
    const srv = new PactaMcpServer({ x402Url: X402_URL, nowSeconds: NOW, fetchImpl: async () => mockRes(402, { x402Version: 1, accepts: [entry()] }) });
    assert.equal(srv.maxAtomic, "200000");
    const r = await srv.handleMessage(callMsg(1, "pacta_scan_timelock_op", { timelock: TIMELOCK, opId: OP_ID }));
    assert.deepEqual(textOf(r).entries[0].reasons, ["amount_over_cap"]);

    process.env.PACTA_X402_MAX_ATOMIC = "999999999999";
    const clamped = new PactaMcpServer({ indexData: { entries: [] } }); // x402 disabled: discover does no fetch
    assert.equal(clamped.maxAtomic, "5000000");
    assert.match((await clamped.callTool("pacta_x402_discover")).configWarnings[0], /clamped/);
  } finally {
    if (prev === undefined) delete process.env.PACTA_X402_MAX_ATOMIC;
    else process.env.PACTA_X402_MAX_ATOMIC = prev;
  }
});

test("free tools work via injected fetch with timeouts; index timeout falls through to fallback URL", async () => {
  const index = { generated_at: "x", entries: [{ id: "a", protocol: "Lido", sprint: 1, classification: "aligned_baseline" }] };
  const seen = [];
  const srv = new PactaMcpServer({
    timeoutMs: 25,
    fetchImpl: (u, init) => {
      seen.push(u);
      assert.ok(init.signal instanceof AbortSignal);
      if (u.includes("pacta.wtf")) return new Promise(() => {}); // hangs -> timeout
      return Promise.resolve(mockRes(200, index));
    },
  });
  const res = await srv.callTool("pacta_list_commitments", { protocol: "lido" });
  assert.equal(res.source, "https://fractal-neurons.github.io/pacta/api/v1/index.json");
  assert.equal(res.matched_count, 1);
  assert.equal(seen[0], "https://pacta.wtf/api/v1/index.json");

  const disc = await srv.callTool("pacta_x402_discover");
  assert.equal(disc.enabled, false);
  assert.equal(disc.localSpecRequirements.scanTimelockOp.source, "local_spec");
  assert.equal(disc.localSpecRequirements.scanTimelockOp.valid, true);

  const anc = await srv.callTool("pacta_get_anchoring");
  assert.deepEqual(anc.x402_gateway.allowed_pay_to, ALLOWED_PAY_TO);
  assert.equal(anc.x402_gateway.max_atomic, "1000000");
});

test("discovery reports upstream timeouts structurally", async () => {
  const srv = new PactaMcpServer({ x402Url: X402_URL, timeoutMs: 25, fetchImpl: () => new Promise(() => {}) });
  const out = await srv.callTool("pacta_x402_discover");
  assert.equal(out.wellKnown.ok, false);
  assert.equal(out.wellKnown.code, "timeout");
});

test("stdio stream wrapper: initialize + tools/list + structured paid error", async () => {
  const input = new PassThrough();
  const output = new PassThrough();
  const out = collectLines(output);
  const h = startStdioServer({ input, output, x402Url: X402_URL, fetchImpl: async () => mockRes(500, { error: "boom" }) });
  input.write(`${JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize" })}\n`);
  input.write(`${JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list" })}\n`);
  input.write(`${JSON.stringify(callMsg(3, "pacta_live_timelocks", {}))}\n`);
  input.write("not json\n");
  const lines = await out.waitFor(4);
  h.close();
  assert.equal(lines[0].result.serverInfo.name, "@pacta/mcp-server");
  assert.equal(lines[1].result.tools.length, 9);
  const err = JSON.parse(lines[2].result.content[0].text);
  assert.equal(lines[2].result.isError, true);
  assert.equal(err.code, "upstream_http_error");
  assert.equal(err.status, 500);
  assert.equal(lines[3].error.code, -32700);
});

test("bin/pacta-mcp.mjs over stdio file descriptors (no sockets, no listener): initialize + tools/list, unusable HOME, exit 0", async () => {
  // Regular files instead of pipes: libuv implements stdio pipes with socketpair(), which a socket-free (seccomp)
  // sandbox refuses; plain file descriptors only need open/dup2. The child must answer and exit 0 on EOF.
  const bin = fileURLToPath(new URL("../bin/pacta-mcp.mjs", import.meta.url));
  const env = { ...process.env };
  for (const k of ["PACTA_X402_URL", "PACTA_INDEX_PATH", "PACTA_PROPOSALS_PATH", "PACTA_SPEC_PATH", "PACTA_X402_MAX_ATOMIC", "PACTA_X402_TIMEOUT_MS", "NODE_OPTIONS"]) delete env[k];
  env.HOME = "/nonexistent-pacta-mcp-home";
  delete env.XDG_CACHE_HOME;
  const scratch = makeScratchDir("pacta-mcp-stdio-");
  try {
    const inPath = join(scratch.dir, "in.jsonl");
    const outPath = join(scratch.dir, "out.jsonl");
    const errPath = join(scratch.dir, "err.txt");
    writeFileSync(inPath, `${JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize" })}\n${JSON.stringify({ jsonrpc: "2.0", id: 2, method: "tools/list" })}\n`);
    const inFd = openSync(inPath, "r");
    const outFd = openSync(outPath, "w");
    const errFd = openSync(errPath, "w");
    let child;
    try {
      child = spawn(process.execPath, [bin], { stdio: [inFd, outFd, errFd], env });
    } finally {
      for (const fd of [inFd, outFd, errFd]) closeSync(fd);
    }
    const exit = await new Promise((resolve, reject) => {
      const killer = setTimeout(() => {
        child.kill();
        reject(new Error(`child did not exit within 60 s; stderr=${readFileSync(errPath, "utf8").slice(0, 2000)}`));
      }, 60000);
      child.on("error", (e) => {
        clearTimeout(killer);
        reject(e);
      });
      child.on("close", (code, signal) => {
        clearTimeout(killer);
        resolve({ code, signal });
      });
    });
    const stderr = readFileSync(errPath, "utf8");
    assert.equal(exit.code, 0, `exit=${JSON.stringify(exit)} stderr=${JSON.stringify(stderr.slice(0, 2000))}`);
    const lines = readFileSync(outPath, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
    assert.equal(lines.length, 2, `stdout lines: ${JSON.stringify(lines).slice(0, 500)} stderr=${stderr.slice(0, 500)}`);
    assert.equal(lines[0].id, 1);
    assert.equal(lines[0].result.protocolVersion, "2024-11-05");
    assert.equal(lines[1].id, 2);
    assert.deepEqual(
      lines[1].result.tools.map((t) => t.name),
      ["pacta_list_commitments", "pacta_list_proposals", "pacta_get_anchoring", "pacta_x402_discover"]
    );
  } finally {
    scratch.cleanup();
  }
});

test("startStdioServer exposes `done`: resolves after EOF once every queued reply is written", async () => {
  const input = new PassThrough();
  const output = new PassThrough();
  const out = collectLines(output);
  const h = startStdioServer({ input, output, fetchImpl: async () => mockRes(500, {}) });
  input.write(`${JSON.stringify({ jsonrpc: "2.0", id: 7, method: "initialize" })}\n`);
  input.end(`${JSON.stringify({ jsonrpc: "2.0", id: 8, method: "tools/list" })}\n`);
  await h.done;
  const lines = await out.waitFor(2);
  assert.deepEqual(lines.map((l) => l.id), [7, 8]);
});
