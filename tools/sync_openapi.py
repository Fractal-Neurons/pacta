#!/usr/bin/env python3
"""sync_openapi.py - snapshot the live Worker's OpenAPI 3.1 document into docs/api/v1/openapi.json (no network).

    python3 tools/sync_openapi.py --core ../pacta-core [--check]

Runs pacta-core packages/x402-edge-worker/worker.mjs locally under node and asks its own fetch handler for /openapi.json with the
public [vars] of wrangler.toml (pricing mode unset = free_launch, exactly as deployed). The response body is written byte for byte;
build_site.py publishes the same bytes at /openapi.json. --check exits 1 when the snapshot is out of date."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "api", "v1", "openapi.json")
ORIGIN = "https://api.pacta.wtf"   # LW-01-R2: the canonical API host, so info.x-service.links.openapi matches https://api.pacta.wtf/openapi.json
JS = """
const mod = await import(process.argv[1]);
const env = JSON.parse(process.argv[2]);
const res = await mod.default.fetch(new Request(process.argv[3] + "/openapi.json"), env, { waitUntil() {}, passThroughOnException() {} });
if (res.status !== 200) { console.error("status " + res.status); process.exit(2); }
process.stdout.write(await res.text());
"""


def worker_vars(toml_text):
    """The [vars] table of wrangler.toml (string values only; comments ignored)."""
    m = re.search(r"^\[vars\]\n(.*?)(?=^\[|\Z)", toml_text, re.S | re.M)
    out = {}
    for line in (m.group(1) if m else "").splitlines():
        kv = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*"([^"]*)"\s*$', line.strip())
        if kv:
            out[kv.group(1)] = kv.group(2)
    return out


def generate(core):
    w = os.path.join(core, "packages", "x402-edge-worker")
    env = worker_vars(open(os.path.join(w, "wrangler.toml"), encoding="utf-8").read())
    node = os.environ.get("NODE") or shutil.which("node")
    r = subprocess.run([node, "--input-type=module", "-e", JS, os.path.join(w, "worker.mjs"), json.dumps(env), ORIGIN],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        sys.exit(f"sync_openapi: worker did not answer /openapi.json: {r.stderr.strip()[:300]}")
    doc = json.loads(r.stdout)
    assert doc.get("openapi") == "3.1.0" and doc.get("paths"), "not an OpenAPI 3.1 document"
    return r.stdout


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--core", default=os.path.join(ROOT, "..", "pacta-core"))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    body = generate(os.path.abspath(a.core))
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else None
    if a.check:
        print("openapi snapshot " + ("in sync" if old == body else "OUT OF DATE"))
        return 0 if old == body else 1
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(f"wrote {os.path.relpath(OUT, ROOT)} ({len(body):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
