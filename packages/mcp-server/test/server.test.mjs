import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { PassThrough } from "node:stream";
import { fileURLToPath } from "node:url";
import {
  PactaMcpServer,
  startStdioServer,
  encodeXPaymentHeader,
  X402_DEFAULTS,
  DEFAULT_ANCHORING,
} from "../src/server.mjs";
import { collectLines, makeScratchDir } from "./helpers.mjs";

// `node --test test/server.test.mjs` (== `npm test`) must cover every suite, so the other files register here.
import "./x402.test.mjs";
import "./mcp.test.mjs";
import "./static-safety.test.mjs";
import "./proposals.test.mjs";
import "./registry-skill.test.mjs";
import "./x402-v2.test.mjs";

// Tests must not depend on the caller's environment.
for (const k of ["PACTA_X402_URL", "PACTA_X402_MAX_ATOMIC", "PACTA_X402_TIMEOUT_MS", "PACTA_INDEX_PATH", "PACTA_PROPOSALS_PATH", "PACTA_SPEC_PATH"]) {
  delete process.env[k];
}

const FIXTURE = {
  generated_at: "2026-11-13T10:05:00Z",
  onchain_anchoring: { sprint_eas_attestations: { "12": "0x" + "7c".repeat(32) } },
  entries: [
    {
      id: "ethena-admin-timelock",
      protocol: "Ethena",
      sprint: 7,
      classification: "parameter_delta",
      surface: "TimelockController MinDelay",
    },
    {
      id: "lido-dual-gov",
      protocol: "Lido",
      sprint: 10,
      classification: "aligned_baseline",
      surface: "EmergencyProtectedTimelock",
    },
    {
      id: "yearn-v3",
      protocol: "Yearn V3",
      sprint: 12,
      classification: "protective_delta",
      surface: "Role Manager Timelock",
    },
  ],
};

const TEST_X402_URL = "https://x402.example.invalid";

const mockJson = (status, body, headers = {}) => {
  const m = new Map(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (k) => m.get(String(k).toLowerCase()) ?? null },
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
};

test("default mode (PACTA_X402_URL unset) exposes only free tools and disables paid x402 gateway", async () => {
  assert.equal(X402_DEFAULTS.defaultBaseUrl, null);
  assert.equal(X402_DEFAULTS.gatewayUrl, "https://pacta-x402.pacta.workers.dev");
  assert.equal(X402_DEFAULTS.deploymentStatus, "live_opt_in");
  const srv = new PactaMcpServer({
    indexData: FIXTURE,
    fetchImpl: async () => {
      throw new Error("no network expected when x402 disabled");
    },
  });
  const init = await srv.handleMessage({ jsonrpc: "2.0", id: 1, method: "initialize" });
  assert.equal(init.result.protocolVersion, "2024-11-05");

  const list = await srv.handleMessage({ jsonrpc: "2.0", id: 2, method: "tools/list" });
  assert.deepEqual(
    list.result.tools.map((t) => t.name),
    ["pacta_list_commitments", "pacta_list_proposals", "pacta_get_anchoring", "pacta_x402_discover"]
  );

  const disc = await srv.callTool("pacta_x402_discover");
  assert.equal(disc.enabled, false);
  assert.equal(disc.x402Url, null);
  assert.equal(disc.baseUrlEnvVar, "PACTA_X402_URL");
  assert.equal(disc.x402_gateway_url, "https://pacta-x402.pacta.workers.dev", "live gateway published for discovery");
  assert.ok(disc.enableHint.includes("PACTA_X402_URL=https://pacta-x402.pacta.workers.dev"));
  assert.equal(disc.x402Defaults.gatewayUrl, "https://pacta-x402.pacta.workers.dev");

  const paidAttempt = await srv.handleMessage({
    jsonrpc: "2.0",
    id: 3,
    method: "tools/call",
    params: { name: "pacta_live_timelocks", arguments: {} },
  });
  assert.equal(paidAttempt.result.isError, true);
  assert.match(paidAttempt.result.content[0].text, /PACTA_X402_URL/);
  assert.ok(paidAttempt.result.content[0].text.includes("https://pacta-x402.pacta.workers.dev"));
});

test("setting PACTA_X402_URL enables all 8 free + paid x402 tools and live discovery", async () => {
  const srv = new PactaMcpServer({
    indexData: FIXTURE,
    x402Url: TEST_X402_URL,
    fetchImpl: async (u) =>
      u.endsWith("/.well-known/x402")
        ? mockJson(200, { x402Version: 1 })
        : mockJson(200, { chain: "base" }),
  });
  const list = await srv.handleMessage({ jsonrpc: "2.0", id: 1, method: "tools/list" });
  assert.equal(list.result.tools.length, 8);

  const out = await srv.callTool("pacta_x402_discover");
  assert.equal(out.enabled, true);
  assert.equal(out.wellKnown.data.x402Version, 1);
  assert.equal(out.sampleControlPlane.data.chain, "base");
});

test("free index fallback URL and anchoring metadata", async () => {
  const srv = new PactaMcpServer({
    fetchImpl: async (u) => {
      if (u.includes("pacta.wtf")) throw new Error("offline");
      return mockJson(200, FIXTURE);
    },
  });
  const res = await srv.callTool("pacta_list_commitments", {
    protocol: "ethena",
    classification: "parameter_delta",
    sprint: 7,
  });
  assert.equal(res.source, "https://fractal-neurons.github.io/pacta/api/v1/index.json");
  assert.equal(res.matched_count, 1);

  const anc = await srv.callTool("pacta_get_anchoring");
  assert.equal(anc.commitment_registry, DEFAULT_ANCHORING.commitment_registry);
  assert.equal(anc.eas_schema_uid, DEFAULT_ANCHORING.eas_schema_uid);
  assert.equal(anc.x402_gateway.enabled, false);
  assert.equal(anc.x402_gateway.x402_url, null, "PACTA_X402_URL unset stays opt-in: no configured gateway");
  assert.equal(anc.x402_gateway_url, "https://pacta-x402.pacta.workers.dev");
  assert.equal(DEFAULT_ANCHORING.x402_gateway_url, "https://pacta-x402.pacta.workers.dev");
});

test("402 challenge builds PaymentRequirements + EIP-712 typedData when x402Url is set", async () => {
  const payer = "0x" + "11".repeat(20);
  const nonce = "0x" + "ab".repeat(32);
  const srv = new PactaMcpServer({
    x402Url: TEST_X402_URL,
    nowSeconds: 1794580000,
    fetchImpl: async (u) =>
      mockJson(402, {
        x402Version: 1,
        accepts: [
          {
            scheme: "exact",
            network: "base",
            maxAmountRequired: "100000",
            resource: u,
            payTo: X402_DEFAULTS.payTo,
            maxTimeoutSeconds: 600,
            asset: X402_DEFAULTS.asset,
            extra: { name: "USD Coin", version: "2" },
          },
        ],
      }),
  });
  const c = await srv.callTool("pacta_scan_control_plane", {
    chain: "base",
    address: DEFAULT_ANCHORING.commitment_registry,
    payer,
    validBeforeSeconds: 600,
    nonce,
  });
  assert.equal(c.status, 402);
  assert.deepEqual(c.eip712TypedData.domain, {
    name: "USD Coin",
    version: "2",
    chainId: 8453,
    verifyingContract: X402_DEFAULTS.asset,
  });
  assert.equal(c.eip712TypedData.message.value, "100000");
  assert.equal(c.eip712TypedData.message.validBefore, "1794580600");
});

test("200 paid scan forwards X-PAYMENT and verifies X-PAYMENT-RESPONSE", async () => {
  const nowSeconds = 1794580000;
  const authorization = {
    from: "0x" + "11".repeat(20),
    to: X402_DEFAULTS.payTo,
    value: "250000",
    validAfter: "0",
    validBefore: "1794580600",
    nonce: "0x" + "cd".repeat(32),
  };
  const xPaymentHeader = encodeXPaymentHeader({ signature: "0x" + "12".repeat(65), authorization });
  // v2.1 fixture used `tx` and no payer; the gateway (packages/x402-gateway/worker.js) emits
  // { success, transaction, network, payer } and the client now requires exactly that.
  const receipt = { success: true, network: "base", transaction: "0x" + "ef".repeat(32), payer: authorization.from };
  const receiptB64 = Buffer.from(JSON.stringify(receipt)).toString("base64");
  let hdr = null;
  const srv = new PactaMcpServer({
    x402Url: TEST_X402_URL,
    nowSeconds,
    fetchImpl: async (_u, init) => {
      hdr = init.headers["X-PAYMENT"];
      return mockJson(200, { isOperationPending: true }, { "X-PAYMENT-RESPONSE": receiptB64 });
    },
  });
  const paid = await srv.callTool("pacta_scan_timelock_op", {
    // v2.1 used 0xceCf30B925bf40129794A0810622354f2ACCD515, which fails EIP-55 (see x402-gateway README);
    // addresses are now checksum-validated, so use the gateway's own example timelock.
    timelock: "0x2225DAbFfC7F862c99477381E971E8B1FDaB467e",
    opId: "0x2f11a5192f46834e4f7c3318b980e8f17440196e57b4ef198f168f4162ca485a",
    xPaymentHeader,
  });
  assert.equal(hdr, xPaymentHeader);
  assert.deepEqual(paid.paymentReceipt, receipt);
  assert.equal(paid.paid, true);
  assert.equal(paid.gatewayReceiptVerified, true);
  assert.equal(paid.onchainReceiptVerified, false);
  assert.equal(paid.settlementVerificationScope, "gateway_header_assertion");
  assert.deepEqual(paid.data, { isOperationPending: true });
});

test("stdio JSON-RPC roundtrip", async () => {
  const input = new PassThrough();
  const output = new PassThrough();
  const out = collectLines(output);
  const h = startStdioServer({ input, output, indexData: FIXTURE });
  input.write(
    `${JSON.stringify({
      jsonrpc: "2.0",
      id: 9,
      method: "tools/call",
      params: { name: "pacta_list_commitments", arguments: { classification: "protective_delta" } },
    })}\n`
  );
  const [reply] = await out.waitFor(1);
  h.close();
  assert.equal(JSON.parse(reply.result.content[0].text).entries[0].protocol, "Yearn V3");
});

test("loads specPath + local_snapshot_path fallback from a scratch fixture (works with a read-only HOME)", async () => {
  const scratch = makeScratchDir();
  const scratchDir = scratch.dir;
  try {
    const snapPath = join(scratchDir, "index.json");
    const specPath = join(scratchDir, "spec.json");
    writeFileSync(snapPath, JSON.stringify(FIXTURE));
    writeFileSync(specPath, JSON.stringify({ public_free_feeds: { local_snapshot_path: snapPath } }));
    const srv = new PactaMcpServer({
      specPath,
      fetchImpl: async () => {
        throw new Error("offline");
      },
    });
    const res = await srv.callTool("pacta_list_commitments", { limit: 100 });
    assert.equal(res.source, snapPath);
    assert.equal(res.total_indexed, 3);
  } finally {
    scratch.cleanup();
  }
});

const FIXTURE_INDEX = fileURLToPath(new URL("./fixtures/index.sample.json", import.meta.url));

test("loads a trimmed copy of the public pacta.wtf index (real records + real Base anchoring)", async () => {
  const srv = new PactaMcpServer({
    indexPath: FIXTURE_INDEX,
    fetchImpl: async () => {
      throw new Error("offline");
    },
  });
  const res = await srv.callTool("pacta_list_commitments", { limit: 100 });
  assert.equal(res.total_indexed, 5);
  const anch = await srv.callTool("pacta_get_anchoring", {});
  const text = JSON.stringify(anch);
  assert.ok(text.includes("0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872"), "registry address present");
  assert.ok(text.includes("0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83"), "EAS schema uid present");
});
