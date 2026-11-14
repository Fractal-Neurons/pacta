// Shared test helpers (not a test file). No sockets, no network, nothing under HOME unless a caller points
// PACTA_TEST_SCRATCH_DIR / XDG_CACHE_HOME there.
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { join } from "node:path";
import { StringDecoder } from "node:string_decoder";
import { fileURLToPath } from "node:url";

// Errors that mean "this base is not usable, try the next one" (read-only or missing HOME, sandboxed cache, ...).
const UNUSABLE = new Set(["EACCES", "EROFS", "EPERM", "ENOENT", "ENOTDIR", "EEXIST", "ENOSPC"]);

/** Candidate scratch bases, in order: PACTA_TEST_SCRATCH_DIR, XDG_CACHE_HOME, cwd, then this package's test dir. */
export function scratchBases() {
  return [
    process.env.PACTA_TEST_SCRATCH_DIR,
    process.env.XDG_CACHE_HOME,
    process.cwd(),
    fileURLToPath(new URL(".", import.meta.url)),
  ].filter((b) => typeof b === "string" && b.trim());
}

/**
 * Create a fresh private scratch dir (mkdtemp) under the first usable base. Never uses HOME implicitly and never
 * the system temp dir. Callers must call cleanup() in a finally block; it removes only the mkdtemp dir.
 * @returns {{ dir: string, base: string, cleanup: () => void }}
 */
export function makeScratchDir(prefix = "pacta-mcp-test-") {
  const errors = [];
  for (const base of scratchBases()) {
    try {
      mkdirSync(base, { recursive: true });
      const dir = mkdtempSync(join(base, prefix));
      return { dir, base, cleanup: () => rmSync(dir, { recursive: true, force: true }) };
    } catch (err) {
      if (!UNUSABLE.has(err.code)) throw err;
      errors.push(`${base} (${err.code})`);
    }
  }
  throw new Error(`No writable scratch base: ${errors.join("; ")}. Set PACTA_TEST_SCRATCH_DIR.`);
}

/**
 * Collect newline-delimited output from a stream and wait deterministically for N complete lines (no fixed sleeps).
 * Attach before writing input. waitFor rejects on timeout or if the stream ends first, with the partial output and
 * `context()` (e.g. child stderr / exit code) in the message.
 */
export function collectLines(stream) {
  const decoder = new StringDecoder("utf8");
  const lines = [];
  const waiters = new Set();
  let partial = "";
  let ended = false;
  const settleAll = () => {
    for (const w of [...waiters]) if (lines.length >= w.n || ended) w.settle();
  };
  stream.on("data", (chunk) => {
    partial += typeof chunk === "string" ? chunk : decoder.write(chunk);
    let i;
    while ((i = partial.indexOf("\n")) !== -1) {
      const line = partial.slice(0, i).trim();
      partial = partial.slice(i + 1);
      if (line) lines.push(line);
    }
    settleAll();
  });
  const onEnd = () => {
    ended = true;
    settleAll();
  };
  stream.on("end", onEnd);
  stream.on("close", onEnd);

  return {
    lines,
    waitFor(n, { timeoutMs = 30000, context = () => "" } = {}) {
      return new Promise((resolve, reject) => {
        const w = {
          n,
          settle: () => {
            clearTimeout(timer);
            waiters.delete(w);
            if (lines.length >= n) resolve(lines.slice(0, n).map((l) => JSON.parse(l)));
            else reject(new Error(`stream ended after ${lines.length}/${n} lines; partial=${JSON.stringify(partial)} ${context()}`));
          },
        };
        const timer = setTimeout(() => {
          waiters.delete(w);
          reject(new Error(`timed out after ${timeoutMs} ms waiting for ${n} lines (got ${lines.length}); partial=${JSON.stringify(partial)} ${context()}`));
        }, timeoutMs);
        waiters.add(w);
        settleAll();
      });
    },
  };
}
