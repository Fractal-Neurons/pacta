// Static checks for the MCP registry manifest (server.json) and the portable agent skill (SKILL.md).
// The key sets below are pinned from https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json
// (ServerDetail / Package / StdioTransport / KeyValueInput / Repository). No network access.
import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { SERVER_INFO, TOOL_DEFINITIONS } from "../src/server.mjs";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const read = (p) => readFileSync(join(ROOT, p), "utf8");
const PKG = JSON.parse(read("package.json"));
const SERVER = JSON.parse(read("server.json"));
const SKILL = read("SKILL.md");
const README = read("README.md");

const SCHEMA_URL = "https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json";
const SERVER_KEYS = ["$schema", "_meta", "description", "icons", "name", "packages", "remotes", "repository", "title", "version", "websiteUrl"];
const PACKAGE_KEYS = [
  "environmentVariables", "fileSha256", "identifier", "packageArguments", "registryBaseUrl", "registryType",
  "runtimeArguments", "runtimeHint", "transport", "version",
];
const ENV_KEYS = ["name", "description", "format", "isRequired", "isSecret", "default", "placeholder", "choices", "value", "variables"];
const REPO_KEYS = ["url", "source", "subfolder", "id"];
const VERSION_RANGE = /^[\^~<>=]|\.x$|\.\*$|^latest$/;
const subset = (obj, allowed, label) => {
  for (const k of Object.keys(obj)) assert.ok(allowed.includes(k), `${label}: unexpected key ${k}`);
};

/** Every PACTA_* env var read by shipped code (process.env.X and process.env["X"]). */
function envVarsReadInSrc() {
  const found = new Set();
  for (const f of readdirSync(join(ROOT, "src")).filter((n) => /\.m?js$/.test(n))) {
    const s = read(join("src", f));
    assert.doesNotMatch(s, /process\.env\[\s*[^"'\s]/, `${f}: dynamic process.env[...] access defeats the scan`);
    for (const m of s.matchAll(/process\.env(?:\.([A-Za-z0-9_]+)|\[\s*["']([A-Za-z0-9_]+)["']\s*\])/g)) found.add(m[1] ?? m[2]);
  }
  for (const f of readdirSync(join(ROOT, "bin"))) assert.doesNotMatch(read(join("bin", f)), /process\.env/, `bin/${f}`);
  return [...found].sort();
}

/** Minimal YAML frontmatter reader: `key: scalar` lines between the leading `---` fences. */
function frontmatter(md) {
  const m = /^---\n([\s\S]*?)\n---\n/.exec(md);
  assert.ok(m, "SKILL.md must start with a --- frontmatter block");
  const out = {};
  for (const line of m[1].split("\n")) {
    if (!line.trim()) continue;
    const kv = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line);
    assert.ok(kv, `unparseable frontmatter line: ${line}`);
    out[kv[1]] = kv[2].replace(/^(["'])(.*)\1$/, "$2");
  }
  return out;
}

test("server.json: registry schema shape (required fields, limits, known keys)", () => {
  subset(SERVER, SERVER_KEYS, "server.json");
  assert.equal(SERVER.$schema, SCHEMA_URL);
  for (const k of ["name", "description", "version"]) assert.equal(typeof SERVER[k], "string", k);
  assert.match(SERVER.name, /^[a-zA-Z0-9.-]+\/[a-zA-Z0-9._-]+$/);
  assert.ok(SERVER.name.length >= 3 && SERVER.name.length <= 200);
  assert.equal(SERVER.name, "io.github.Fractal-Neurons/pacta");
  assert.ok(SERVER.description.length >= 1 && SERVER.description.length <= 100, `description is ${SERVER.description.length} chars`);
  assert.ok(!SERVER.title || SERVER.title.length <= 100);
  assert.doesNotMatch(SERVER.version, VERSION_RANGE);
  assert.equal(SERVER.websiteUrl, "https://pacta.wtf/");

  subset(SERVER.repository, REPO_KEYS, "repository");
  assert.deepEqual(
    { url: SERVER.repository.url, source: SERVER.repository.source, subfolder: SERVER.repository.subfolder },
    { url: "https://github.com/Fractal-Neurons/pacta", source: "github", subfolder: "packages/mcp-server" }
  );
  assert.doesNotMatch(SERVER.repository.subfolder, /^\/|\.\.|\/$/, "clean relative subfolder");

  assert.ok(Array.isArray(SERVER.packages) && SERVER.packages.length === 1);
  const pkg = SERVER.packages[0];
  subset(pkg, PACKAGE_KEYS, "packages[0]");
  assert.equal(pkg.registryType, "npm");
  assert.equal(pkg.identifier, "@pacta/mcp-server");
  assert.deepEqual(pkg.transport, { type: "stdio" });
  assert.ok(pkg.version && pkg.version !== "latest");
  assert.doesNotMatch(pkg.version, VERSION_RANGE);
  for (const ev of pkg.environmentVariables) {
    subset(ev, ENV_KEYS, `env ${ev.name}`);
    assert.match(ev.name, /^[A-Z][A-Z0-9_]*$/);
    assert.ok(typeof ev.description === "string" && ev.description.length > 10, `${ev.name} description`);
    assert.equal(ev.isRequired, false, `${ev.name} isRequired`);
    assert.equal(ev.isSecret, false, `${ev.name} isSecret`);
    if (ev.format !== undefined) assert.ok(["string", "number", "boolean", "filepath"].includes(ev.format), ev.name);
    if (ev.default !== undefined) assert.equal(typeof ev.default, "string", ev.name);
  }
});

test("server.json name/version agree with package.json mcpName/version and SERVER_INFO", () => {
  assert.equal(PKG.mcpName, SERVER.name);
  assert.equal(SERVER.version, PKG.version);
  assert.equal(SERVER.packages[0].version, PKG.version);
  assert.equal(SERVER.packages[0].identifier, PKG.name);
  assert.equal(SERVER_INFO.version, PKG.version);
  assert.equal(SERVER_INFO.name, PKG.name);
  assert.equal(PKG.repository.url.replace(/\.git$/, ""), SERVER.repository.url);
  assert.equal(PKG.repository.directory, SERVER.repository.subfolder);
  assert.ok(PKG.files.includes("SKILL.md") && PKG.files.includes("server.json"));
});

test("server.json environmentVariables == env vars read in src/ (regex scan), and README documents each", () => {
  const listed = SERVER.packages[0].environmentVariables.map((e) => e.name);
  assert.equal(new Set(listed).size, listed.length, "no duplicates");
  const inSrc = envVarsReadInSrc();
  assert.ok(inSrc.includes("PACTA_PROPOSALS_PATH") && inSrc.includes("PACTA_INDEX_PATH"), inSrc.join(","));
  assert.deepEqual([...listed].sort(), inSrc);
  for (const v of inSrc) assert.ok(README.includes(v), `README documents ${v}`);
  for (const v of inSrc) assert.ok(SKILL.includes(v), `SKILL.md mentions ${v}`);
});

test("SKILL.md: frontmatter, feed URLs, tool list, pinned addresses, and Treasury wording", () => {
  const fm = frontmatter(SKILL);
  assert.equal(fm.name, "pacta-protocol-commitments");
  assert.ok(fm.description && fm.description.length > 40 && !fm.description.includes("\n"), "one-paragraph description");
  if (fm.version) assert.equal(fm.version, PKG.version);
  if (fm.homepage) assert.equal(fm.homepage, "https://pacta.wtf/");

  for (const url of [
    "https://pacta.wtf/api/v1/index.json",
    "https://pacta.wtf/api/v1/onboarding.json",
    "https://pacta.wtf/api/v1/proposals.json",
    "https://pacta.wtf/api/v1/radar.json",
    "https://pacta.wtf/llms-full.txt",
    "https://pacta.wtf/.well-known/agent.json",
    "https://pacta.wtf/.well-known/mcp.json",
  ]) {
    assert.ok(SKILL.includes(url), `SKILL.md lists ${url}`);
  }
  for (const t of TOOL_DEFINITIONS) {
    assert.ok(SKILL.includes(`\`${t.name}\``), `SKILL.md lists ${t.name}`);
    assert.ok(README.includes(`\`${t.name}\``), `README lists ${t.name}`);
  }
  for (const s of [
    "0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09",
    "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872",
    "0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83",
    "PactaCommitmentRegistry",
    "PactaSentinelTripwire.sol",
    "--block",
    "$1.00",
  ]) {
    assert.ok(SKILL.includes(s), `SKILL.md mentions ${s}`);
  }
  assert.match(SKILL, /not been audited|not audited/);
  assert.match(SKILL, /not deployed/);
  assert.match(SKILL, /no live forum posting/i);
  assert.match(SKILL, /[Nn]ever sign for any other `payTo`/);
  assert.doesNotMatch(SKILL, /mailto:|[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}/, "no email addresses");
});

test("canonical live x402 gateway URL is published in SKILL.md, README.md and server.json, but stays opt-in", () => {
  const U = "https://pacta-x402.pacta.workers.dev";
  assert.ok(SKILL.includes(U), "SKILL.md");
  assert.ok(SKILL.includes("PACTA_X402_URL=" + U), "SKILL.md shows the opt-in");
  assert.ok(README.includes("PACTA_X402_URL=" + U), "README.md shows the opt-in");
  const ev = SERVER.packages.flatMap((p) => p.environmentVariables || []).find((e) => e.name === "PACTA_X402_URL");
  assert.ok(ev && ev.description.includes(U), "server.json PACTA_X402_URL description");
  assert.equal(ev.isRequired, false);
  for (const k of ["default", "value"]) assert.equal(ev[k], undefined, `PACTA_X402_URL has no ${k}: paid tools stay opt-in`);
  assert.doesNotMatch(SKILL + README, /deployment pending|not yet live|planned, not live/);
});

test("0x4348… is never called a Safe (SKILL.md, README.md, server.json); SKILL.md calls it the Pacta Treasury EOA", () => {
  const ADDR = /0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14/gi;
  const docs = { "SKILL.md": SKILL, "README.md": README, "server.json": JSON.stringify(SERVER) };
  for (const [name, text] of Object.entries(docs)) {
    for (const m of text.matchAll(ADDR)) {
      const win = text.slice(Math.max(0, m.index - 120), m.index + m[0].length + 120);
      assert.doesNotMatch(win, /\bSafe\b|\bmultisig\b|\bGnosis\b/i, `${name}: "Safe" near treasury address`);
      if (name === "SKILL.md") {
        assert.match(win, /Pacta Treasury/, "SKILL.md: called Pacta Treasury");
        assert.match(win, /\bEOA\b/, "SKILL.md: identified as an EOA");
      }
    }
  }
  assert.ok(SKILL.match(ADDR)?.length >= 1);
});

test("server.json advertises the live remote MCP endpoint; server.remote.json is a remote-only twin (registrable before npm publish)", () => {
  const MCP = "https://pacta-x402.pacta.workers.dev/mcp";
  assert.deepEqual(SERVER.remotes, [{ type: "streamable-http", url: MCP }]);
  const REMOTE = JSON.parse(read("server.remote.json"));
  subset(REMOTE, SERVER_KEYS, "server.remote.json");
  assert.equal(REMOTE.packages, undefined);
  assert.deepEqual(REMOTE.remotes, SERVER.remotes);
  for (const k of ["$schema", "name", "title", "description", "repository", "version", "websiteUrl"]) assert.deepEqual(REMOTE[k], SERVER[k], k);
});
