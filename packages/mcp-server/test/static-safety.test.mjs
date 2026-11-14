// Static guarantees: stdio-only (no listening sockets), no temp-dir usage in shipped code or tests.
// Patterns are assembled from fragments so this file does not match its own scan.
import "./no-network.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const walk = (dir) =>
  readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
const filesIn = (...dirs) => dirs.flatMap((d) => walk(join(ROOT, d))).filter((p) => /\.(m?js|cjs|ts)$/.test(p));

const CREATE_SERVER = new RegExp("create" + "Server");
const LISTEN_CALL = new RegExp("\\.listen" + "\\s*\\(");
const NET_MODULES = new RegExp("(?:from|import\\s*\\(|require\\s*\\()\\s*[\"'](?:node:)?(?:" + ["http", "https", "net", "http2", "dgram", "tls"].join("|") + ")[\"']");
const TMP = new RegExp("/" + "tmp\\b");
const OS_TMPDIR = new RegExp("tmp" + "dir\\s*\\(");

test("src/ and bin/ never open a listening socket", () => {
  const files = filesIn("src", "bin");
  assert.ok(files.length >= 4, `expected source files, got ${files}`);
  for (const f of files) {
    const s = readFileSync(f, "utf8");
    assert.doesNotMatch(s, CREATE_SERVER, f);
    assert.doesNotMatch(s, LISTEN_CALL, f);
    assert.doesNotMatch(s, NET_MODULES, f);
  }
});

test("no file under src/ (or bin/, test/) references the system temp dir", () => {
  for (const f of filesIn("src", "bin", "test")) {
    const s = readFileSync(f, "utf8");
    assert.doesNotMatch(s, TMP, f);
    assert.doesNotMatch(s, OS_TMPDIR, f);
  }
});

test("tests never listen either", () => {
  for (const f of filesIn("test")) {
    const s = readFileSync(f, "utf8");
    assert.doesNotMatch(s, CREATE_SERVER, f);
    assert.doesNotMatch(s, LISTEN_CALL, f);
  }
});

test("package stays zero-dependency", () => {
  const pkg = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf8"));
  for (const k of ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]) {
    assert.equal(Object.keys(pkg[k] ?? {}).length, 0, k);
  }
});

test("src/ and bin/ never write files or touch HOME (startup works with a read-only or missing HOME)", () => {
  const WRITES = new RegExp(
    "\\b(?:" + ["writeFile", "appendFile", "mkdir", "mkdtemp", "createWriteStream", "rm", "rmdir", "unlink", "rename", "copyFile", "chmod", "open"].join("|") + ")(?:Sync)?\\s*\\("
  );
  const HOME_REFS = new RegExp("\\bhome" + "dir\\s*\\(|process\\.env\\.(?:HOME|USERPROFILE|XDG_[A-Z_]+)\\b|[\"']~/");
  for (const f of filesIn("src", "bin")) {
    const s = readFileSync(f, "utf8");
    assert.doesNotMatch(s, WRITES, f);
    assert.doesNotMatch(s, HOME_REFS, f);
  }
});

test("tests never derive scratch paths from HOME (they use test/helpers.mjs makeScratchDir)", () => {
  for (const f of filesIn("test")) {
    assert.doesNotMatch(readFileSync(f, "utf8"), new RegExp("\\bhome" + "dir\\s*\\("), f);
  }
});
