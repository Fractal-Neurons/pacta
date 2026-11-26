// Static checks for the MCP registry manifest (server.json) and the portable agent skill (SKILL.md).
// The key sets below are pinned from https://static.modelcontextprotocol.io/schemas/2025-10-17/server.schema.json
// (ServerDetail / Package / StdioTransport / KeyValueInput / Repository). No network access.
import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
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

  // nothing is published on npm: the manifest carries the remote endpoint only (no npm "packages" block)
  assert.equal(SERVER.packages, undefined, "server.json advertises no npm package");
});

test("server.json name/version agree with package.json mcpName/version and SERVER_INFO", () => {
  assert.equal(PKG.mcpName, SERVER.name);
  assert.equal(SERVER.version, PKG.version);
  assert.equal(SERVER_INFO.version, PKG.version);
  assert.equal(SERVER_INFO.name, SERVER.name);
  assert.equal(PKG.private, true, "package.json is private: never published to npm");
  assert.equal(PKG.name, "pacta-mcp-server");
  assert.equal(PKG.repository.url.replace(/\.git$/, ""), SERVER.repository.url);
  assert.equal(PKG.repository.directory, SERVER.repository.subfolder);
  assert.ok(PKG.files.includes("SKILL.md") && PKG.files.includes("server.json"));
});

test("env vars read in src/ (regex scan): README documents each and SKILL.md mentions each", () => {
  const inSrc = envVarsReadInSrc();
  assert.ok(inSrc.includes("PACTA_PROPOSALS_PATH") && inSrc.includes("PACTA_INDEX_PATH") && inSrc.includes("PACTA_X402_URL"), inSrc.join(","));
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
  // 0.1.6: one canonical gateway address, https://api.pacta.wtf, in SKILL.md, README.md, server.json, the Dockerfile and X402_GATEWAY_URL.
  const U = "https://api.pacta.wtf";
  assert.ok(SKILL.includes(U), "SKILL.md");
  assert.ok(SKILL.includes("PACTA_X402_URL=" + U), "SKILL.md shows the opt-in");
  assert.match(read("Dockerfile"), /^ENV PACTA_X402_URL=https:\/\/api\.pacta\.wtf$/m, "Dockerfile opts in to the canonical gateway");
  assert.ok(README.includes("PACTA_X402_URL=" + U), "README.md shows the opt-in");
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
  const MCP = "https://api.pacta.wtf/mcp";
  assert.deepEqual(SERVER.remotes, [{ type: "streamable-http", url: MCP }]);
  const REMOTE = JSON.parse(read("server.remote.json"));
  subset(REMOTE, SERVER_KEYS, "server.remote.json");
  assert.equal(REMOTE.packages, undefined);
  assert.deepEqual(REMOTE.remotes, SERVER.remotes);
  for (const k of ["$schema", "name", "title", "description", "repository", "version", "websiteUrl", "icons"]) assert.deepEqual(REMOTE[k], SERVER[k], k);
});

// definitions.Icon of the 2025-10-17 server.schema.json (src: https URI, maxLength 255, required; mimeType / sizes / theme optional).
const ICON_KEYS = ["src", "mimeType", "sizes", "theme"];
const ICON_MIME = ["image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/webp"];
const ICON_SIZE = /^(\d+x\d+|any)$/;
test("0.1.5 icons: server.json and server.remote.json carry the same schema-valid https://pacta.wtf/ icons (PNG 32x32 + SVG any)", () => {
  const REMOTE = JSON.parse(read("server.remote.json"));
  assert.deepEqual(REMOTE.icons, SERVER.icons);
  assert.deepEqual(SERVER.icons, [
    { src: "https://pacta.wtf/favicon.png", mimeType: "image/png", sizes: ["32x32"] },
    { src: "https://pacta.wtf/favicon.svg", mimeType: "image/svg+xml", sizes: ["any"] },
  ]);
  for (const doc of [SERVER, REMOTE]) {
    assert.ok(Array.isArray(doc.icons) && doc.icons.length > 0);
    for (const icon of doc.icons) {
      subset(icon, ICON_KEYS, "icon");
      assert.equal(typeof icon.src, "string");
      assert.ok(icon.src.length <= 255 && icon.src.startsWith("https://pacta.wtf/"), icon.src);
      assert.equal(new URL(icon.src).protocol, "https:");
      assert.ok(ICON_MIME.includes(icon.mimeType), icon.mimeType);
      assert.ok(Array.isArray(icon.sizes) && icon.sizes.length > 0 && icon.sizes.every((z) => typeof z === "string" && ICON_SIZE.test(z)), String(icon.sizes));
      if ("theme" in icon) assert.ok(["light", "dark"].includes(icon.theme));
    }
    // ServerDetail: required name / description / version, description <= 100, a pinned (not ranged) version
    for (const k of ["name", "description", "version"]) assert.equal(typeof doc[k], "string", k);
    assert.ok(doc.description.length <= 100);
    assert.doesNotMatch(doc.version, VERSION_RANGE);
  }
  assert.equal(SERVER.version, "0.1.7");
  assert.equal(REMOTE.version, "0.1.7");
  // pacta-github-repo: the icon files are the site's own (32x32 PNG, SVG); skipped where the site docs are absent
  const DOCS = join(ROOT, "..", "..", "docs");
  if (existsSync(join(DOCS, "favicon.png"))) {
    const png = readFileSync(join(DOCS, "favicon.png"));
    assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
    assert.deepEqual([png.readUInt32BE(16), png.readUInt32BE(20)], [32, 32]);
    assert.match(readFileSync(join(DOCS, "favicon.svg"), "utf8"), /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg"/);
  }
});

test("0.1.7 metadata: title, public description and package author / bugs / homepage", () => {
  const REMOTE = JSON.parse(read("server.remote.json"));
  for (const doc of [SERVER, REMOTE]) {
    assert.equal(doc.title, "Pacta, by Fractal Neurons");
    assert.equal(doc.description, "Who can upgrade, pause or change a contract. Control facts for agents on Ethereum and Base.");
    assert.equal(doc.description.length, 91, `description is ${doc.description.length} chars`);
  }
  assert.equal(PKG.description, "Zero-dependency MCP server for Pacta, by Fractal Neurons: who can upgrade, pause or change a contract on Ethereum and Base, with optional x402 Base USDC live scans.");
  for (const d of [SERVER.description, REMOTE.description, PKG.description]) {
    for (const s of ["who can upgrade, pause or change a contract", "Ethereum and Base"]) assert.ok(d.toLowerCase().includes(s.toLowerCase()), `${d} names ${s}`);
    assert.doesNotMatch(d, /\b86\b|referral|\bsprint\b|\bDRI\b/i);
    assert.doesNotMatch(d, /\bnpm\b|workers\.dev/i);
  }
  assert.deepEqual(PKG.author, { name: "Fractal Neurons", url: "https://fractalneurons.com", email: "pacta@dri.network" });
  assert.deepEqual(PKG.bugs, { url: "https://github.com/Fractal-Neurons/pacta/issues", email: "pacta@dri.network" });
  assert.equal(PKG.homepage, "https://pacta.wtf");
  assert.doesNotMatch(README, /\b86 (indexed )?protocols\b|referral|\bpacta-(gemini|claude|codex|strategy)\b|\bSprint\b/);
  assert.doesNotMatch(README.replaceAll("pacta@dri.network", ""), /\bDRI\b/i);
  // MCP016-01: no Sprint prose in the shipped copy (the API parameter `sprint` stays)
  for (const [name, txt] of [["README.md", README], ["SKILL.md", read("SKILL.md")], ["src/server.mjs", read("src/server.mjs")]]) {
    assert.doesNotMatch(txt, /\bSprints?\b|\bsprints\b|sprint attestation|\(\d+ sprints?\)/, `${name} has Sprint prose`);
  }
});

// ---- 0.1.6 cleanup regressions (task-10b37c4d4fd7) ----
test("0.1.6: zero Cloudflare Workers origin addresses in README.md, SKILL.md, server.json, server.remote.json, Dockerfile and every src/*.mjs; X402_GATEWAY_URL is https://api.pacta.wtf", async () => {
  const NEEDLE = ["workers", "dev"].join(".");   // built, so this file itself stays free of the string
  const files = ["README.md", "SKILL.md", "server.json", "server.remote.json", "Dockerfile",
    ...readdirSync(join(ROOT, "src")).filter((f) => f.endsWith(".mjs")).map((f) => "src/" + f)];
  assert.ok(files.length >= 9, files.join(", "));
  for (const f of files) assert.ok(!read(f).includes(NEEDLE), `${f} names a ${NEEDLE} origin`);
  const { X402_GATEWAY_URL } = await import("../src/x402.mjs");
  assert.equal(X402_GATEWAY_URL, "https://api.pacta.wtf");
});

test("0.1.6: the packaged SKILL.md is evergreen (no Wave 4 / November 2026 dates; undated pointer to https://pacta.wtf/bounties/)", () => {
  assert.doesNotMatch(SKILL, /Wave 4|November 2026/);
  assert.ok(SKILL.split("\n").includes("- Bounties: active verification waves, open slots, and current submission rules are published at https://pacta.wtf/bounties/"));
});

test("0.1.6: publication status is truthful: registered in the official MCP Registry (remote); nothing published on npm", () => {
  for (const [name, text] of Object.entries({ "SKILL.md": SKILL, "README.md": README })) {
    assert.ok(!text.includes("not yet published to npm or the MCP registry"), name);
    assert.doesNotMatch(text, /not (?:yet )?(?:published|registered) (?:in|on|to) the (?:official )?MCP [Rr]egistry/, name);
  }
  assert.ok(SKILL.split("\n").includes("registry_remote: io.github.Fractal-Neurons/pacta is published in the official MCP Registry as a remote Streamable HTTP server (no install): https://api.pacta.wtf/mcp. Local stdio server: git clone https://github.com/Fractal-Neurons/pacta.git, then node packages/mcp-server/bin/pacta-mcp.mjs."));
  assert.doesNotMatch(SKILL, /^(?:publication_pending|npm_pending):/m);
  assert.match(README, /registered in the official MCP Registry as `io\.github\.Fractal-Neurons\/pacta`/);
  assert.match(README, /Nothing is published on npm/);
});

test("0.1.6: package.json files ships only the clean runtime set (no test/, fixtures, Dockerfile or server.remote.json)", () => {
  const pkg = JSON.parse(read("package.json"));
  assert.deepEqual(pkg.files, ["bin/", "src/", "index.d.ts", "README.md", "SKILL.md", "server.json"]);
  for (const d of ["bin", "src"]) {
    for (const f of readdirSync(join(ROOT, d))) assert.match(f, /^[a-z0-9-]+\.mjs$/, `${d}/${f}`);
  }
});

test("no npm package name in any machine-readable public file (package.json, server.json, server.remote.json, smithery.yaml, glama.json, README, SKILL, src, index.d.ts; docs mcp.json once it drops its package key)", () => {
  const NPM = ["@pacta", "mcp-server"].join("/");   // built, so this file itself stays free of the name
  const REPO = join(ROOT, "..", "..");
  const pkgFiles = ["package.json", "server.json", "server.remote.json", "README.md", "SKILL.md", "index.d.ts",
    ...readdirSync(join(ROOT, "src")).filter((f) => f.endsWith(".mjs")).map((f) => "src/" + f)];
  for (const f of pkgFiles) assert.ok(!read(f).includes(NPM), `packages/mcp-server/${f}`);
  for (const f of ["smithery.yaml", "glama.json", "README.md"]) {
    if (existsSync(join(REPO, f))) assert.ok(!readFileSync(join(REPO, f), "utf8").includes(NPM), f);
  }
  // site discovery manifests (the separate site commit): checked once they no longer carry a "package" key
  for (const f of ["docs/mcp.json", "docs/.well-known/mcp.json"]) {
    const p = join(REPO, f);
    if (!existsSync(p)) continue;
    const m = JSON.parse(readFileSync(p, "utf8"));
    if (!("package" in m)) assert.ok(!JSON.stringify(m).includes(NPM) && !("packageVersion" in m), f);
  }
  const PKG = JSON.parse(read("package.json"));
  assert.equal(PKG.private, true);
  assert.equal(JSON.parse(read("server.json")).packages, undefined);
});

