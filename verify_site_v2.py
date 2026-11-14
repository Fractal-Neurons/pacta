#!/usr/bin/env python3
"""verify_site_v2.py - offline checks for the Pacta static site (docs/). Pure stdlib; no network.

  python3 verify_site_v2.py        # exit 0 = all checks passed

Checks: <head> budget (<body> before byte 2500; OG + X tags inside the first 1.2 KB of <head>), zero data:image blobs,
required Open Graph / X card / canonical tags, zero "Security Quarantine" wording, count parity (sprints / records)
across index.html, llms.txt, README.md and /api/v1/index.json, summary SHA-256 digests, EIP-55 checksums, matrix row
count, og-preview.png = 1200x630 PNG, favicon sizes, discovery files (llms.txt, robots.txt, sitemap.xml,
.well-known/security.txt, .nojekyll), brief metadata, radar freshness, HTML tag balance, and a deny-list of private
identifiers that must never appear on the public site.

v3 design checks: no mailto: links (dead clicks without a desktop mail client), a working coverage-request builder on
the homepage and at /request/, no spec-letter labels such as "(a)" in the UI, every internal link and #anchor
resolves, no duplicate ids, no raw 32-byte hashes in visible text (they are shortened, full value in a tooltip / copy
button), hairline design radii (<= 4px; dots only), and briefs rendered inside the shared site chrome.

Commercial copy (single offer): zero "private disclosure" / "$0" / gratis charity copy on any public file; the one paid
offer ($5,000 USDC 24h clearance, optional $1,500/month monitoring) and the free community queue are the only tracks;
no curator subscription tracks; public data stated as free and real-time; the payment address equals the index's treasury
address and is EIP-55; the GitHub dropdown options match the issue template exactly; Sprint 15 stays out of audits/.

Behaviour check: docs/app.js is executed under node (tools/app_harness.js; pure node, no network, no listener, no files)
against a synthetic DOM built from the real /request/ and homepage HTML: the clearance track is the default and shows
the payment panel; a valid tx hash and forum URL reach the brief and the GitHub prefill, a malformed hash is flagged and
never forwarded; the community queue hides payment and drops the hash; ?tier= prefill and homepage plan buttons work;
malformed #r-... hashes never throw during initialization.
"""

import datetime as dt
import glob
import hashlib
import html.parser
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def read(rel, mode="r"):
    with open(os.path.join(ROOT, rel), mode) as fh:
        return fh.read()


# keccak-256 for EIP-55 (stdlib only)
_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
       0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
       0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
       0x000000000000800A, 0x800000008000000A, 0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_R = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M = (1 << 64) - 1


def keccak(data):
    msg = bytearray(data) + b"\x01"
    while len(msg) % 136:
        msg.append(0)
    msg[-1] |= 0x80
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(msg), 136):
        for i in range(17):
            a[i % 5][i // 5] ^= int.from_bytes(msg[off + 8 * i:off + 8 * i + 8], "little")
        for rc in _RC:
            c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
            d = [c[(x - 1) % 5] ^ (((c[(x + 1) % 5] << 1) | (c[(x + 1) % 5] >> 63)) & _M) for x in range(5)]
            a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
            b = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    r = _R[x][y]
                    b[y][(2 * x + 3 * y) % 5] = ((a[x][y] << r) | (a[x][y] >> (64 - r))) & _M if r else a[x][y]
            a = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
            a[0][0] ^= rc
    return b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


def eip55_ok(addr):
    body = addr[2:]
    if body in (body.lower(), body.upper()):
        return True
    h = keccak(body.lower().encode()).hex()
    return addr == "0x" + "".join(ch.upper() if ch.isalpha() and int(h[i], 16) >= 8 else ch.lower() for i, ch in enumerate(body.lower()))


DENY_SHA256 = {
    "f55b134784e0408e7fbb9a364e013a187abb61892ea83954861e6e470ca402a1",
    "26dcfbfa28f206ba2e67081ecd67fa16331088cf386b934ae5121ca28c79d26c",
    "ec3a34ebe07e5a8760c88cc8c4e03add1763276b0c95c163315ddfb11fb772af",
    "b75e8778d665f8a51e220eb42aee997a4b5e48c9db2ccee7bb6adede42ead7cb",
    "1d7e457b5fce8750db412fc55deed23e9d7c26e284e2c69f9423edadf2d54d1c",
    "a0e9089ab4b858049538fa2530221a1afdb7e16398ac259a87ae0ca1a69283db",
    "898a774ab7bfbf9b4224a7cb5f6a5786d7b2b59117f8a8cce103ad115d84bc1c",
    "46920406b7b239f06f469b02f97a960d542633a98cda0155b1f52fc1effa41f5",
    "1b115d312ebaa63cacc24bdc63a2a21b4b1c678a209b99b285fdbd8e0c9b0def",
    "5804b00ea2b294160e7cb6ab7e121d2eba3c9fc11002811461d90475c6b65793",
    "2c34c6bb2c5960486f7d2015b7994b28cf9a874828e30fb590ce09793d06b057",
    "29ff56a35bc5fb00e4d761eea222a75774a3b5a574aa63aa044cc7d58a6f2203",
    "b3b4916f8b7424956ae178f84959899c8ae2424c8fbc0a5cd9cfeba2959385d5",
    "4fef04a481f14b8a454d887bd0a9f788ab769440a3c9d5755c7fa8a0fbdd48fd",
    "8b57e629f3becdad3b267292c773469eab75034edbea0677588a25892e6789d9",
}


def tokens(text):
    """SHA-256 digests of lowercased tokens: words, hyphenated words, and 0x-hex bodies without the prefix."""
    t = text.lower()
    words = set(re.findall(r"[a-z0-9]+", t)) | set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)+", t))
    words |= {w[2:] for w in words if w.startswith("0x")}
    return {hashlib.sha256(w.encode()).hexdigest() for w in words}


class Balance(html.parser.HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append(f"unexpected </{tag}> (open: {self.stack[-3:]})")


class Tree(html.parser.HTMLParser):
    """HTML -> ["tag", {attrs}, [children]] tree for tools/app_harness.js (the synthetic DOM)."""
    VOID = Balance.VOID

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = ["#root", {}, []]
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = [tag, {k: ("" if v is None else v) for k, v in attrs}, []]
        self.stack[-1][2].append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1][2].append([tag, {k: ("" if v is None else v) for k, v in attrs}, []])

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1][2].append(data)


def dom_tree(text):
    t = Tree()
    t.feed(text)
    return next(n for n in t.root[2] if isinstance(n, list) and n[0] == "html")


def app_behaviour(appjs, request_html, index_html, row_id, beacon="", protocol_html="", protocol_slug="", notfound_html=""):
    """Run docs/app.js (and the docs/b.js beacon) under node against a synthetic DOM of the real pages. No network, no listener, no files."""
    node = shutil.which("node")
    if not node:
        return {"harness_error": "node not found"}
    payload = json.dumps({"app": appjs, "request": dom_tree(request_html), "index": dom_tree(index_html), "rowId": row_id, "beacon": beacon,
                          "protocol": dom_tree(protocol_html) if protocol_html else None, "protocolSlug": protocol_slug,
                          "notfound": dom_tree(notfound_html) if notfound_html else None})
    out = subprocess.run([node, os.path.join(ROOT, "tools", "app_harness.js")], input=payload, capture_output=True, text=True, timeout=120)
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {"harness_error": (out.stderr or out.stdout)[-400:]}


def urllib_host(u):
    import urllib.parse
    return urllib.parse.urlsplit(u).hostname or ""


def llms_txt(read_):
    return read_("docs/llms.txt")


def main():
    base = re.search(r'^BASE_URL = "([^"]+)"', read("tools/build_site.py"), re.M).group(1)
    raw = read("docs/index.html", "rb")
    page = raw.decode()
    hpos, bpos = raw.find(b"<head>"), raw.find(b"<body")
    check("<body> starts before byte 2500", 0 <= bpos < 2500, f"<body> at byte {bpos}")
    tw_end = raw.find(b">", raw.find(b'name="twitter:image"')) + 1
    check("OG + X card tags inside the first 1.2 KB of <head>", 0 < tw_end - hpos <= 1200, f"twitter:image ends {tw_end - hpos} bytes into <head>")
    check("zero data:image/ blobs in index.html", b"data:image/" not in raw)
    req = ['<meta charset="utf-8">', 'name="viewport"', "<title>", 'name="description"', f'<link rel="canonical" href="{base}/">',
           'property="og:type"', 'property="og:site_name"', 'property="og:title"', 'property="og:description"', f'property="og:url" content="{base}/"',
           f'property="og:image" content="{base}/og-preview.png"', 'property="og:image:width" content="1200"', 'property="og:image:height" content="630"',
           'name="twitter:card" content="summary_large_image"', 'name="twitter:title"', 'name="twitter:description"',
           f'name="twitter:image" content="{base}/og-preview.png"', 'href="styles.css"', 'href="favicon.svg"', 'href="favicon.png"']
    head = page[:bpos]
    missing = [r for r in req if r not in head]
    check("required head tags present", not missing, f"missing: {missing}" if missing else f"{len(req)} tags")
    check("no inline <style> in index.html head", "<style" not in head)

    # wording
    public = ["docs/index.html", "docs/llms.txt", "README.md"] + [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(DOCS, "briefs", "*", "index.html"))]
    bad = [p for p in public if "Security Quarantine" in read(p)]
    check('zero "Security Quarantine" wording', not bad, str(bad))
    # single commercial offer; no private-disclosure charity copy anywhere public
    req_page = read("docs/request/index.html")
    copy_files = ["docs/index.html", "docs/request/index.html", "docs/llms.txt", "docs/llms-full.txt", "docs/SKILL.md", "docs/.well-known/agent.json",
                  "docs/.well-known/mcp.json", "docs/api/v1/proposals.json", "docs/app.js", "docs/api/v1/index.json", "README.md",
                  "REMEDIATION_SERVICES.md", "METHODOLOGY.md", ".github/ISSUE_TEMPLATE/request-scan.yml"] + \
                 [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(DOCS, "briefs", "*", "index.html"))]
    charity = re.compile(r"private disclosure|\$0 private|\$0 gratis|gratis|free of charge|at no cost|at \$0 cost|no cost to the protocol", re.I)
    bad_c = sorted({f"{f}: {m.group(0)}" for f in copy_files for m in charity.finditer(read(f))})
    check('zero "private disclosure" / "$0" / gratis copy in public files', not bad_c, f"{len(copy_files)} files; {bad_c[:4]}")
    subs = re.compile(r"Curator Radar|Commitment CI Gate|\$3,000|/ year|USDC/mo\)|USDC/yr", re.I)
    bad_s = sorted({f"{f}: {m.group(0)}" for f in copy_files for m in subs.finditer(read(f))})
    check("no curator / SaaS subscription tracks (one paid offer only)", not bad_s, str(bad_s[:4]))
    offer = ("24h Collateral Onboarding &amp; Delta Clearance Attestation", "$5,000 USDC", "$1,500 / month", "Curator Diligence Dossier")
    check("homepage + /request/ carry the $5,000 USDC 24h clearance offer and $1,500/month add-on",
          all(t in page and t in req_page for t in offer) and "$5,000 USDC flat" in llms_txt(read)
          and "Immunefi" in page and "Cantina" in page and "15% referral" in page)
    check("public data stated free and real-time (homepage, llms.txt, README)",
          "free and real-time" in page and "Free and real-time" in llms_txt(read) and "Free and real-time" in read("README.md"))
    radios = re.findall(r'name="tier" value="(\w+)"', req_page)
    radios_home = re.findall(r'name="tier" value="(\w+)"', page)
    check("request builder offers exactly clearance (default) + community, on both pages", radios == radios_home == ["clearance", "community"]
          and all(len(re.findall(r'name="tier" value="\w+" checked', t)) == 1 and 'value="clearance" checked' in t for t in (page, req_page)),
          str(radios))
    treasury = json.loads(read("docs/api/v1/index.json"))["onchain_anchoring"]["treasury_admin"]
    shown = set(re.findall(r'data-treasury="(0x[0-9a-fA-F]{40})"', page + req_page)) | set(re.findall(r'class="mono full">(0x[0-9a-fA-F]{40})<', page + req_page))
    check("payment address = index treasury address (EIP-55) everywhere it is shown", shown == {treasury} and eip55_ok(treasury)
          and treasury in read("REMEDIATION_SERVICES.md") and treasury in llms_txt(read) and treasury in read(".github/ISSUE_TEMPLATE/request-scan.yml"),
          f"{sorted(shown)}")
    tmpl = read(".github/ISSUE_TEMPLATE/request-scan.yml")
    opts = re.findall(r'^\s+- "(.+)"$', tmpl.split("id: package_tier", 1)[1].split("validations", 1)[0], re.M)
    js_opts = re.findall(r'"([^"]+)",\s*\n\s*"Pacta (?:24h clearance|community queue) request"', read("docs/app.js"))
    check("GitHub dropdown prefill strings match the issue template exactly", sorted(opts) == sorted(js_opts) and len(opts) == 2
          and all(f'id: {k}' in tmpl for k in ("forum_proposal_url", "payment_tx_hash")), f"template {opts} app.js {js_opts}")
    check("Sprint 15 summary stays out of audits/ (embargo)", not os.path.exists(os.path.join(ROOT, "audits", "sprint-15")))
    appjs = read("docs/app.js")
    check('radar says "Execution window opens in" (ETA = eligibility)', "Execution window opens in" in appjs and "Executing in" not in appjs)
    check('finality badge says "Scanner-pinned (L1 finalized)"', "Scanner-pinned (L1 finalized)" in appjs and "Scanner-pinned (L1 finalized)" in page)

    # counts
    idx = json.loads(read("docs/api/v1/index.json"))
    m, entries = idx["summary_metrics"], idx["entries"]
    n, sprints = len(entries), max(e["sprint"] for e in entries)
    check("index.json records_indexed == len(entries) == 37", m["records_indexed"] == n == 37, f"{m['records_indexed']} / {n}")
    check("index.json sprints_completed == max(sprint) == 14", m["sprints_completed"] == sprints == 14, f"{m['sprints_completed']} / {sprints}")
    check("classification counts sum to records", m["parameter_deltas"] + m["protective_deltas"] + m["aligned_baselines"] == n
          and all(sum(1 for e in entries if e["classification"] == k) == m[v] for k, v in
                  (("parameter_delta", "parameter_deltas"), ("protective_delta", "protective_deltas"), ("aligned_baseline", "aligned_baselines"))))
    line = f"{sprints} Sprints · {n} Indexed Records"
    for f in ("docs/index.html", "docs/llms.txt", "README.md"):
        t = read(f)
        nums_s = set(re.findall(r"\b(\d+) Sprints\b", t))
        nums_r = set(re.findall(r"\b(\d+) (?:Indexed )?Records\b", t))
        check(f"count parity in {f}", line in t and nums_s <= {str(sprints)} and nums_r <= {str(n)},
              f"sprints {sorted(nums_s)} records {sorted(nums_r)}")
    rows = len(re.findall(r'<tr data-class="', page))
    check("homepage matrix renders every record", rows == n, f"{rows} rows")
    anc = idx["onchain_anchoring"]
    eas = anc["sprint_eas_attestations"]
    uid_ok = all(re.fullmatch(r"0x[0-9a-f]{64}", u) for u in eas.values()) and len(set(eas.values())) == len(eas)
    check("16 Base EAS sprint attestations (Sprints 1-16); every record carries its sprint's UID", len(eas) == 16 and sorted(map(int, eas)) == list(range(1, 17))
          and uid_ok and all(e["base_eas_uid"] == eas[str(e["sprint"])] for e in entries) and "16 Base EAS sprint attestations" in page
          and re.search(r"<b>16</b><span>Base EAS attestations</span>", page) is not None)
    # Sprints 13-16 batch, read back from Base on 2026-11-13 (tx status 1, Attested logs from the attester, schema 0x7ff4..df83,
    # not revoked; Sprint 13/14 block, block hash, record count and summary SHA-256 match this index)
    pinned = {"13": "0x6afd266541ea1643b680ce6ec15d218874356598820987c6b3eaf16342cd075c", "14": "0x8965ae6e51a78132a77eb14c0ac1c6cd1be357d6f261253efff28869478ae5b8",
              "15": "0x967a4935786194575835d5a46e3e39b1d553225deb6a96c7ff4acf52a34dff22", "16": "0x217d213de3cd9ef094670ff69d258af35adf132406caa547f729f487dc9d7e58"}
    check("Sprint 13-16 UIDs + batch tx equal the values verified on Base", all(eas.get(k) == v for k, v in pinned.items())
          and anc.get("eas_multi_attest_sprints_13_16_tx") == "0x11546aac53e3fe57fa6ac9f7e4397f06c58b6803252e099eb9349eca00f2edbf")
    check("multi-attest txs recorded (Sprints 1-12 and 13-16)", re.fullmatch(r"0x[0-9a-f]{64}", anc.get("eas_multi_attest_sprints_13_16_tx", "")) is not None
          and anc["attestation_coverage"]["eas_multi_attest_txs"] == {"1–12": anc["eas_multi_attest_tx"], "13–16": anc["eas_multi_attest_sprints_13_16_tx"]})

    # data integrity
    bad_sha = [e["id"] for e in entries if "0x" + hashlib.sha256(read(e["summary_doc"], "rb")).hexdigest() != e["summary_sha256"]]
    check("every summary_sha256 matches its summary file", not bad_sha, str(bad_sha))
    bad_hash = [e["id"] for e in entries if not re.fullmatch(r"0x[0-9a-f]{64}", e["block_hash"])]
    check("every block_hash is a 32-byte hex", not bad_hash, str(bad_hash))
    corpus = {"docs/index.html": re.sub(r'data-search="[^"]*"', "", page), "docs/llms.txt": read("docs/llms.txt"),
              "docs/api/v1/index.json": json.dumps(idx), "README.md": read("README.md")}
    for f in ("docs/llms-full.txt", "docs/SKILL.md", "docs/.well-known/agent.json", "docs/.well-known/mcp.json", "docs/api/v1/proposals.json",
              "docs/api/v1/onboarding.json"):
        if os.path.exists(os.path.join(ROOT, f)):
            corpus[f] = read(f)
    for p in glob.glob(os.path.join(DOCS, "briefs", "**", "*.html"), recursive=True) + glob.glob(os.path.join(ROOT, "audits", "**", "*.md"), recursive=True):
        corpus[os.path.relpath(p, ROOT)] = open(p).read()
    bad55 = sorted({f"{f}: {a}" for f, t in corpus.items() for a in re.findall(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])", t) if not eip55_ok(a)})
    n55 = len({a for t in corpus.values() for a in re.findall(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])", t)})
    check("EIP-55 on every address: site, index, README, briefs, audits", not bad55, f"{n55} addresses in {len(corpus)} files; bad: {bad55[:5]}")

    # reproducibility: every record carries a complete, self-consistent cast/eth_call reproduction
    bad_repro = []
    for e in entries:
        if e["check_type"] == "eth_call":
            sig, args, cd = e.get("call_signature"), e.get("call_args"), e.get("repro_calldata")
            arity = 0 if not sig or sig.endswith("()") else sig.count(",") + 1
            ok = bool(sig) and "0x" + keccak(sig.encode()).hex()[:8] == e["selector_or_slot"] and isinstance(args, list) and len(args) == arity \
                and cd == e["selector_or_slot"] + "".join(a[2:].lower().rjust(64, "0") for a in args)
        else:
            ok = e.get("call_signature") is None and re.fullmatch(r"0x[0-9a-f]{64}", e["selector_or_slot"]) is not None
        if not ok:
            bad_repro.append(e["id"])
    check("every record has a complete cast reproduction (signature, all args, calldata)", not bad_repro, f"bad: {bad_repro}")

    # assets
    og = read("docs/og-preview.png", "rb")
    check("og-preview.png is a 1200x630 PNG", og[:8] == b"\x89PNG\r\n\x1a\n" and og[12:16] == b"IHDR" and struct.unpack(">II", og[16:24]) == (1200, 630),
          f"{len(og)} bytes")
    fav = read("docs/favicon.png", "rb")
    check("favicon.png is a PNG < 2 KB", fav[:8] == b"\x89PNG\r\n\x1a\n" and len(fav) < 2048, f"{len(fav)} bytes {struct.unpack('>II', fav[16:24])}")
    svg = read("docs/favicon.svg", "rb")
    try:
        ET.fromstring(svg)
        svg_ok = len(svg) < 1024
    except ET.ParseError:
        svg_ok = False
    check("favicon.svg is valid XML < 1 KB", svg_ok, f"{len(svg)} bytes")

    # discovery files
    llms = read("docs/llms.txt")
    check("llms.txt: H1, index.json, EAS schema, registry, x402 section", llms.startswith("# ") and "/api/v1/index.json" in llms
          and idx["onchain_anchoring"]["eas_schema_uid"] in llms and idx["onchain_anchoring"]["commitment_registry"] in llms and "x402" in llms)
    robots = read("docs/robots.txt")
    check("robots.txt allows / and lists the sitemap", "Allow: /" in robots and f"Sitemap: {base}/sitemap.xml" in robots)
    try:
        sm = ET.fromstring(read("docs/sitemap.xml", "rb"))
        locs = {e.text for e in sm.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
        need = {f"{base}/", f"{base}/request/", f"{base}/llms.txt", f"{base}/api/v1/index.json", f"{base}/demos/swapio-x402/"} | \
               {f"{base}/briefs/{os.path.basename(os.path.dirname(p))}/" for p in glob.glob(os.path.join(DOCS, "briefs", "*", "index.html"))}
        check("sitemap.xml lists home, request, llms.txt, API, every brief and the demo", need <= locs, f"missing {sorted(need - locs)}")
    except ET.ParseError as e:
        check("sitemap.xml parses", False, str(e))
    sec = read("docs/.well-known/security.txt")
    exp = re.search(r"^Expires: (\S+)$", sec, re.M)
    exp_ok = bool(exp) and dt.datetime.fromisoformat(exp.group(1).replace("Z", "+00:00")) > dt.datetime.now(dt.UTC)
    check("security.txt (RFC 9116): Contact, future Expires, Canonical", "Contact: mailto:pacta@dri.network" in sec and exp_ok
          and f"Canonical: {base}/.well-known/security.txt" in sec)
    check(".nojekyll present (so /.well-known/ is served by GitHub Pages)", os.path.exists(os.path.join(DOCS, ".nojekyll")))

    # briefs
    for p in glob.glob(os.path.join(DOCS, "briefs", "*", "index.html")):
        s = open(p).read()
        slug = os.path.basename(os.path.dirname(p))
        ok = all(t in s for t in ('property="og:title"', 'property="og:image"', 'name="twitter:card"', f'href="{base}/briefs/{slug}/"')) and "data:image/" not in s
        check(f"brief {slug}: OG/X/canonical tags, no data:image", ok)

    # radar
    radar = json.loads(read("docs/api/v1/radar.json"))
    etas = {str(i["eta"]) for i in radar["items"]}
    shown = set(re.findall(r'data-eta="(\d+)"', page))
    r = radar["refreshed_at"]
    check("radar ETAs on the page match radar.json", etas == shown, f"{sorted(etas)} vs {sorted(shown)}")
    check("radar freshness badge states block and time", f"#{r['block_number']:,}" in page and r["block_time_utc"] in page and "Last refreshed" in page)

    # html structure
    for f in ["docs/index.html"] + [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(DOCS, "briefs", "*", "index.html"))]:
        b = Balance()
        b.feed(read(f))
        check(f"HTML tag balance: {f}", not b.errors and not [t for t in b.stack if t not in ("html", "body")], "; ".join(b.errors[:3]))

    # v3 design / UX invariants
    pages = {os.path.relpath(p, DOCS): open(p).read() for p in glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)}
    mail = sorted(k for k, v in pages.items() if "mailto:" in v) + (["app.js"] if "mailto:" in appjs else [])
    check("no mailto: links on any page (every CTA works in the browser)", not mail, f"{len(pages)} pages; with mailto: {mail}")
    req_ok = all(t in page for t in ('id="request"', 'id="req-form"', 'id="req-gh"', 'id="req-gmail"', 'id="req-copy"', "issues/new?template=request-scan.yml",
                                     "https://mail.google.com/mail/?view=cm")) and 'id="req-form"' in pages.get(os.path.join("request", "index.html"), "")
    check("coverage-request builder on the homepage (#request) and at /request/", req_ok)
    spec = sorted(k for k, v in pages.items() if re.search(r">\s*\([a-d]\)\s", v))
    check('no spec-letter labels such as "(a)" in the UI', not spec, str(spec))
    fmt_bad = sorted({f"{k}: {m}" for k, v in pages.items() for m in re.findall(r"&amp;(?:amp|lt|gt|quot|#x?[0-9a-f]+);|\b\d+\.\d{3,}h\b|\b0\.0\d*h\b", v)})
    check("no double-escaped entities or long float durations in any page", not fmt_bad, str(fmt_bad[:4]))

    class Links(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids, self.hrefs, self.dups = set(), [], []

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if a.get("id"):
                if a["id"] in self.ids:
                    self.dups.append(a["id"])
                self.ids.add(a["id"])
            for k in ("href", "src"):
                if a.get(k) and tag not in ("link",) or (tag == "link" and a.get("rel") in ("stylesheet", "icon")):
                    if a.get(k):
                        self.hrefs.append(a[k])
    parsed = {}
    for rel, text in pages.items():
        lp = Links()
        lp.feed(text)
        parsed[rel] = lp
    broken, dups = [], []
    for rel, lp in parsed.items():
        dups += [f"{rel}#{d}" for d in lp.dups]
        for h in lp.hrefs:
            if re.match(r"^(https?:|mailto:|data:|javascript:)", h) or h.startswith("//"):
                continue
            path, _, frag = h.partition("#")
            path = path.split("?")[0]
            if path.startswith("/"):                      # root-relative (404.html): resolve against docs/
                target = os.path.normpath(path.lstrip("/")) if path.strip("/") else ""
            else:
                target = os.path.normpath(os.path.join(os.path.dirname(rel), path)) if path else rel
            if path.endswith("/") or (path and os.path.isdir(os.path.join(DOCS, target))):
                target = os.path.join(target, "index.html")
            if not os.path.exists(os.path.join(DOCS, target)):
                broken.append(f"{rel}: {h}")
            elif frag and target in parsed and frag not in parsed[target].ids:
                broken.append(f"{rel}: {h} (no id)")
    check("every internal link and #anchor resolves; no duplicate ids", not broken and not dups, f"broken {broken[:4]} dup ids {dups[:4]}")
    visible = re.sub(r"<pre\b.*?</pre>", " ", page, flags=re.S)
    visible = re.sub(r"<[^>]+>", " ", visible)
    raw64 = re.findall(r"0x[0-9a-fA-F]{64}", visible)
    check("no raw 32-byte hashes in visible homepage text (shortened, full value in tooltip/copy)", not raw64, f"{len(raw64)} found {raw64[:2]}")
    css = read("docs/styles.css")
    radii = re.findall(r"border-radius:\s*([^;}]+)", css)
    bad_r = [r for r in radii if not all(v in ("0", "50%", "var(--r)") or (v.endswith("px") and float(v[:-2]) <= 4) for v in r.strip().split())]
    check("hairline design: every border-radius <= 4px (dots 50%)", not bad_r, f"{len(radii)} radii; bad {bad_r}")
    chrome = [rel for rel in pages if rel.startswith("briefs" + os.sep) and not ('class="topbar"' in pages[rel] and 'href="../../styles.css"' in pages[rel]
                                                                           and "<style" not in pages[rel])]
    check("briefs share the site chrome and stylesheet (no inline styles)", not chrome, str(chrome))

    # behaviour: run app.js against a synthetic DOM of the real /request/ and homepage markup
    beacon_js = read("docs/b.js") if os.path.exists(os.path.join(DOCS, "b.js")) else ""
    res = app_behaviour(appjs, pages.get(os.path.join("request", "index.html"), ""), page, entries[0]["id"], beacon=beacon_js,
                        protocol_html=pages.get(os.path.join("protocols", "aave-v3-gho", "index.html"), ""), protocol_slug="aave-v3-gho",
                        notfound_html=pages.get("404.html", ""))
    expected = ["default_is_clearance", "clearance_pay_panel_shown", "clearance_tx_field_shown", "clearance_github_href",
                "clearance_github_tier_exact", "clearance_brief_has_price_and_treasury", "tx_valid_in_brief", "tx_valid_in_github",
                "forum_in_brief_and_github", "tx_valid_not_flagged", "tx_invalid_flagged", "tx_invalid_not_in_github",
                "community_pay_panel_hidden", "community_tx_field_hidden", "community_github_tier_exact", "community_no_tx_anywhere",
                "community_click_not_prevented", "clearance_restores_pay_panel", "prefill_selects_community",
                "prefill_unknown_tier_keeps_clearance", "homepage_plan_button_preselects",
                "hash_ok #r-[unclosed", "hash_ok #r-x\\", 'hash_ok #r-"]', "hash_ok #r-%E0%A4%A", "valid_hash_opens_drawer", "livebar_skips_elapsed_etas",
                "pf_present", "pf_no_fetch_on_load", "pf_preset_fetches_once", "pf_renders_verdict", "pf_text_only", "pf_cast_commands",
                "pf_invalid_address_no_fetch", "pf_http_error_reported"]
    failed_b = [k for k in expected if res.get(k) is not True] + (["harness_error: " + res["harness_error"][:200]] if "harness_error" in res else [])
    check("app.js behaviour: clearance/community tracks, payment panel, tx-hash + forum prefill; malformed #hash never throws; live pre-flight checker (explicit click only, text-only render, cast repro, errors)", not failed_b,
          f"{len(expected) - len([k for k in expected if res.get(k) is not True])}/{len(expected)} assertions; failed {failed_b[:4]}")

    # live onboarding verification briefs (rendered from docs/api/v1/onboarding.json by tools/onboarding_scan.py + build_site.py)
    onb_path = os.path.join(DOCS, "api", "v1", "onboarding.json")
    EXPECT_ONB = {"kerne-kusd-base": ("base", 57050397, "0xd6d02efb420f81b3f0e095d78453362c4488afb9adc0f8e1c411bb265beb88a7"),
                  "efix-efixdi-base": ("base", 57050397, "0xd6d02efb420f81b3f0e095d78453362c4488afb9adc0f8e1c411bb265beb88a7"),
                  "circle-cirbtc-eth": ("eth", 26408330, "0x8efc8256deb932e65b5117f040db264dc8200850636d90eecd5daccb99979f4d"),
                  "paxos-paxgy-eth": ("eth", 26408330, "0x8efc8256deb932e65b5117f040db264dc8200850636d90eecd5daccb99979f4d"),
                  "tether-usat-eth": ("eth", 26408330, "0x8efc8256deb932e65b5117f040db264dc8200850636d90eecd5daccb99979f4d")}
    onb = json.loads(read("docs/api/v1/onboarding.json")) if os.path.exists(onb_path) else {"briefs": []}
    got = {b["slug"]: (b["chain"], b["pin"]["number"], b["pin"]["hash"]) for b in onb["briefs"]}
    check("onboarding.json: 5 briefs at the specified pinned blocks (schema pacta.onboarding_briefs.v1)",
          onb.get("schema") == "pacta.onboarding_briefs.v1" and got == EXPECT_ONB, f"{sorted(got)}")
    bad_cd, bad_page, n_checks = [], [], 0
    for b in onb["briefs"]:
        pg = pages.get(os.path.join("briefs", b["slug"], "index.html"), "")
        casts = len(re.findall(r"^cast (?:call|storage|code|nonce) ", html.unescape(pg), re.M))
        if casts != len(b["checks"]) or f'--block {b["pin"]["number"]}' not in pg or b["pin"]["hash"] not in pg \
                or 'href="../../request/?tier=clearance"' not in pg or "$5,000 USDC" not in pg or len(b["checks"]) < 8:
            bad_page.append(f'{b["slug"]}: casts {casts}/{len(b["checks"])}')
        for c in b["checks"]:
            n_checks += 1
            if c["kind"] == "eth_call":
                want = "0x" + keccak(c["sig"].encode()).hex()[:8] + "".join(
                    (hex(a)[2:] if isinstance(a, int) else a[2:].lower()).rjust(64, "0") for a in c["args"])
                if c["calldata"] != want:
                    bad_cd.append(f'{b["slug"]}:{c["id"]}')
            val = c["value"]
            if isinstance(val, (int, str)) and not isinstance(val, bool) and c["kind"] != "eth_getCode" and str(val) not in html.unescape(pg):
                bad_page.append(f'{b["slug"]}:{c["id"]} value not shown')
    check("onboarding briefs: every eth_call calldata re-derives from signature + args", not bad_cd and n_checks > 0, f"{n_checks} checks; bad {bad_cd[:3]}")
    check("onboarding briefs: one cast line per check, pin block + hash, every value shown, $5,000 clearance CTA", not bad_page and onb["briefs"],
          str(bad_page[:4]))
    llms_t, sm = read("docs/llms.txt"), read("docs/sitemap.xml")
    linked = all(f'href="briefs/{sl}/"' in page and f"{base}/briefs/{sl}/" in llms_t and f"{base}/briefs/{sl}/" in sm for sl in EXPECT_ONB)
    check("onboarding briefs linked from the homepage (#onboarding), llms.txt and sitemap.xml", linked and 'id="onboarding"' in page
          and "/api/v1/onboarding.json" in llms_t)

    # agent-first (B2A) feeds: proposals.json, llms-full.txt, .well-known/{agent,mcp}.json, SKILL.md
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.dont_write_bytecode = True                            # no __pycache__ writes into a possibly read-only checkout
    import build_b2a_feeds as B2A
    b2a_files = ["api/v1/proposals.json", "llms-full.txt", ".well-known/agent.json", ".well-known/mcp.json", "SKILL.md"]
    rendered = B2A.render_all(idx, radar, onb)               # in memory: no scratch files, works with a read-only HOME
    drift = [f for f in b2a_files if rendered.get(f, "").encode() != read("docs/" + f, "rb")] + sorted(set(rendered) - set(b2a_files))
    check("B2A feeds are a byte-identical deterministic build of index/radar/onboarding.json (no hand edits, no wall clock)", not drift, str(drift))
    prop = json.loads(read("docs/api/v1/proposals.json"))
    PKEYS = {"proposal_id", "forum", "topic_id", "title", "forum_url", "relation", "chain", "chain_id", "pinned_block_number", "pinned_block_hash",
             "source_feed", "source_record_ids", "brief_url", "control_plane_summary", "recommended_sentinel_predicates", "repro_commands"}
    idx_ids, onb_slugs = {e["id"] for e in entries}, {b["slug"] for b in onb["briefs"]}
    pbad = []
    for pp in prop.get("proposals", []):
        if not PKEYS <= set(pp) or pp["proposal_id"] != f'{pp["forum"]}-{pp["topic_id"]}':
            pbad.append(f'{pp.get("proposal_id")}: keys')
            continue
        if not re.fullmatch(r"0x[0-9a-f]{64}", pp["pinned_block_hash"]) or (pp["chain"], pp["chain_id"]) not in (("ethereum", 1), ("base", 8453)):
            pbad.append(f'{pp["proposal_id"]}: pin')
        if urllib_host(pp["forum_url"]) != B2A.FORUM_HOST[pp["forum"]]:
            pbad.append(f'{pp["proposal_id"]}: forum host')
        pool = onb_slugs if pp["source_feed"] == "/api/v1/onboarding.json" else idx_ids
        if not pp["source_record_ids"] or not set(pp["source_record_ids"]) <= pool:
            pbad.append(f'{pp["proposal_id"]}: source_record_ids')
        if pp["brief_url"] and not os.path.exists(os.path.join(DOCS, pp["brief_url"].replace(base + "/", "").rstrip("/"), "index.html")):
            pbad.append(f'{pp["proposal_id"]}: brief_url')
        if not pp["repro_commands"] or not any(f'--block {pp["pinned_block_number"]}' in c for c in pp["repro_commands"]) \
                or not set(pp["recommended_sentinel_predicates"]) <= set(B2A.PREDICATES) or not pp["control_plane_summary"]:
            pbad.append(f'{pp["proposal_id"]}: repro/predicates/summary')
    forums = {pp["forum"] for pp in prop.get("proposals", [])}
    need_ids = {"aave-25128", "aave-25499", "aave-25927", "aave-25721", "aave-26304", "aave-25902", "euler-1862", "euler-1850", "morpho-2301", "sky-28390"}
    check("proposals.json (pacta.governance_proposals_feed.v1): all 4 forums, the 10 specified proposals, pins, forum hosts, record ids + brief URLs resolve",
          prop.get("schema") == "pacta.governance_proposals_feed.v1" and forums == {"aave", "euler", "morpho", "sky"}
          and need_ids <= {pp["proposal_id"] for pp in prop["proposals"]} and prop["counts"]["total"] == len(prop["proposals"]) and not pbad,
          f'{len(prop.get("proposals", []))} proposals; bad {pbad[:4]}')
    full = read("docs/llms-full.txt")
    miss = [i for i in idx_ids | {pp["proposal_id"] for pp in prop["proposals"]} if i not in full]
    check("llms-full.txt: every indexed record, every proposal and every feed URL; registry, EAS schema, x402 payTo and Pacta Treasury",
          not miss and all(f"{base}{p_}" in full for p_, _ in B2A.FEEDS) and B2A.REGISTRY in full and B2A.EAS_SCHEMA in full
          and B2A.PAY_TO in full and f"Pacta Treasury: {B2A.TREASURY}" in full, f"missing {miss[:4]}")
    card, man = json.loads(read("docs/.well-known/agent.json")), json.loads(read("docs/.well-known/mcp.json"))
    eps = list(card.get("endpoints", {}).get("feeds", {}).values()) + [card["endpoints"]["mcp_manifest"], card["endpoints"]["skill"]] + list(man["feeds"].values())
    unresolved = [u for u in eps if not os.path.exists(os.path.join(DOCS, u.replace(base + "/", "")))]
    check("agent.json (A2A card: name/url/version/provider/capabilities/modes/skills/x402) + mcp.json (name, remote streamable-http + stdio transports, tools, status): endpoints resolve",
          all(k in card for k in ("protocolVersion", "name", "description", "url", "version", "provider", "documentationUrl", "capabilities",
                                   "defaultInputModes", "defaultOutputModes", "skills")) and len(card["skills"]) >= 3
          and card["x402"]["payTo"] == B2A.PAY_TO and card["x402"]["asset"] == B2A.USDC_BASE and card["x402"]["chainId"] == 8453
          and man["name"] == "io.github.fractal-neurons/pacta" and man["transport"]["type"] == "streamable-http" and man["transport"]["url"] == "https://pacta-x402.pacta.workers.dev/mcp"
          and {t_["type"] for t_ in man.get("transports", [])} >= {"streamable-http", "stdio"} and "pacta_list_proposals" in {t["name"] for t in man["tools"]}
          and man["status"].startswith("publication_pending") and not unresolved, f"unresolved {unresolved[:3]}")
    skill = read("docs/SKILL.md")
    fm = re.match(r"---\n(.*?)\n---\n", skill, re.S)
    check("SKILL.md: YAML frontmatter (name pacta-protocol-commitments, one-line description), feed URLs, verification recipe",
          bool(fm) and "name: pacta-protocol-commitments" in fm.group(1) and re.search(r"^description: .{60,}$", fm.group(1), re.M) is not None
          and all(f"{base}{p_}" in skill for p_, _ in B2A.FEEDS) and "--block" in skill)
    X402 = "https://pacta-x402.pacta.workers.dev"   # literal on purpose: the generator constant must match it
    llms_now = read("docs/llms.txt")
    surfaces = {"agent.json": card["x402"].get("gatewayUrl") == X402 and card["x402"].get("status") == "live"
                and card["endpoints"].get("x402_gateway") == X402 and card["x402"].get("discovery") == X402 + "/.well-known/x402",
                "mcp.json": man.get("x402", {}).get("gatewayUrl") == X402 and man["x402"].get("enableWith") == "PACTA_X402_URL=" + X402
                and any(e["name"] == "PACTA_X402_URL" and X402 in e["description"] for e in man["environment"]),
                "llms.txt": X402 in llms_now and "## x402 API (live" in llms_now, "llms-full.txt": f"Live gateway: {X402}" in full and f"GET {X402}/v1/scan/control-plane" in full,
                "SKILL.md": f"Live gateway: `{X402}`" in skill and f"PACTA_X402_URL={X402}" in skill}
    stale = [f for f in ["docs/" + x for x in b2a_files] + ["docs/llms.txt"]
             if re.search(r"deployment pending|planned, not live|not yet live|api\.pacta\.wtf|<worker-origin>", read(f))]
    check("canonical live x402 gateway https://pacta-x402.pacta.workers.dev in agent.json, mcp.json, llms.txt, llms-full.txt, SKILL.md; no stale 'pending' wording",
          B2A.X402_URL == X402 and all(surfaces.values()) and not stale,
          f"missing {[k for k, v in surfaces.items() if not v]}; stale {stale}")
    paid_paths = ["/v1/check/preflight", "/v1/scan/control-plane", "/v1/scan/timelock-op", "/v1/scan/proposal-diff", "/v1/briefs/live-timelocks"]
    v2_tokens = ["eip155:8453", "PAYMENT-REQUIRED", "PAYMENT-SIGNATURE"]
    v2_surfaces = {"SKILL.md": skill, "agent.json": read("docs/.well-known/agent.json"), "mcp.json": read("docs/.well-known/mcp.json"),
                   "llms.txt": llms_now, "llms-full.txt": full}
    has_v2_version = lambda t: bool(re.search(r'x402Versions?"?:?\s*\[\s*1\s*,\s*2\s*\]', t))
    v2_missing = {k: [tok for tok in v2_tokens if tok not in t] + ([] if has_v2_version(t) else ["x402Versions [1, 2]"]) for k, t in v2_surfaces.items()}
    v2_missing = {k: v for k, v in v2_missing.items() if v}
    skill_paths = [p_ for p_ in paid_paths if f"{X402}{p_}" not in skill]
    card_routes = {r_["path"]: r_ for r_ in card["x402"]["routes"]}
    wire_ok = (card["x402"].get("x402Versions") == [1, 2] and card["x402"].get("networks") == ["base", "eip155:8453"]
               and card["x402"].get("maxTimeoutSeconds") == 60 and card["x402"]["wire"]["v2"]["paymentHeader"] == "PAYMENT-SIGNATURE"
               and card["x402"]["wire"]["v2"]["receiptHeader"] == "PAYMENT-RESPONSE" and card["x402"]["wire"]["v1"]["paymentHeader"] == "X-PAYMENT"
               and card["x402"]["settlement"]["onchainReceiptVerified"] is False and sorted(card_routes) == sorted(paid_paths)
               and {p_: card_routes[p_]["amount"] for p_ in paid_paths} == {"/v1/check/preflight": "10000", "/v1/scan/control-plane": "100000", "/v1/scan/timelock-op": "250000",
                                                                          "/v1/scan/proposal-diff": "150000", "/v1/briefs/live-timelocks": "100000"}
               and man["x402"].get("x402Versions") == [1, 2] and man["x402"].get("onchainReceiptVerified") is False
               and "pacta_scan_proposal_diff" in {t["name"] for t in man["tools"]})
    check("x402 v1 + v2 on all 5 agent surfaces: SKILL.md lists the 5 metered routes; x402Versions [1, 2] / eip155:8453 / PAYMENT-REQUIRED / PAYMENT-SIGNATURE everywhere; agent.json wire + prices; onchainReceiptVerified false",
          not v2_missing and not skill_paths and wire_ok, f"missing {v2_missing}; SKILL paths missing {skill_paths}; wire_ok {wire_ok}")
    near = []
    for f in ["docs/" + x for x in b2a_files] + ["docs/llms.txt", "docs/index.html", "README.md"]:
        t = read(f)
        for mm in re.finditer(B2A.TREASURY, t, re.I):
            if re.search(r"\bSafe\b|\bmultisig\b|\bGnosis\b", t[max(0, mm.start() - 120): mm.end() + 120], re.I):
                near.append(f)
    check("0x4348…Ed14 is never labelled a Safe / multisig anywhere in the agent feeds, llms.txt, homepage or README", not near, str(near))

    # ---- free agent launch (Phase B): hero quickstarts, live checker, pricing, no dead npx, protocol pages, robots, registries ----
    import build_site as BS
    API_ = "https://pacta-x402.pacta.workers.dev"
    MCP_ = API_ + "/mcp"
    home = read("docs/index.html")
    req_page = read("docs/request/index.html")
    hero = home[home.find('<section class="hero"'):home.find("</section>", home.find('<section class="hero"'))]
    hero_ok = (BS.H1.replace("&", "&amp;") in hero
               and f'<code class="mono">claude mcp add --transport http pacta {MCP_}</code>' in hero
               and "&quot;url&quot;: &quot;" + MCP_ + "&quot;" in hero
               and re.search(r'<code class="mono">curl -s &quot;' + re.escape(API_) + r'/v1/check/preflight\?chain=', hero) is not None
               and all(f'href="{h}"' in hero for h in (API_ + "/openapi.json", "SKILL.md", "llms.txt", ".well-known/agent.json")))
    pf = re.search(r'<section class="sec" id="preflight">.*?</section>', home, re.S)
    pf_ok = bool(pf) and f'data-api="{API_}"' in pf.group(0) and 'id="pf-form"' in pf.group(0) and 'id="pf-out"' in pf.group(0) \
        and len(re.findall(r'data-pf-address="0x[0-9a-fA-F]{40}"', pf.group(0))) >= 3 and 'name="chain"' in pf.group(0) and 'name="address"' in pf.group(0)
    check("free-launch hero: H1, remote MCP (Claude Code + Cursor), curl /v1/check/preflight, OpenAPI / SKILL / llms.txt / agent.json links; live #preflight checker (form, presets, output)",
          hero_ok and pf_ok, f"hero {hero_ok}; checker {pf_ok}")
    pr = re.search(r'<section class="sec" id="pricing">.*?</section>', home, re.S)
    pricing_ok = bool(pr) and "$0" in pr.group(0) and "Free launch" in pr.group(0) and "60 requests / minute" in pr.group(0) \
        and "High volume, SLA &amp; on-chain clearance" in pr.group(0) and "remote MCP" in pr.group(0).lower().replace("remote mcp", "remote MCP")
    req_ok = "free with no key" in req_page and "#preflight" in req_page and "High volume" in req_page
    check("pricing: $0 free launch tier (60 req/min, 5 endpoints + remote MCP) and the high-volume SLA / on-chain clearance tier, on #pricing and /request/",
          pricing_ok and req_ok, f"#pricing {pricing_ok}; /request/ {req_ok}")

    DEAD_NPX = re.compile(r"npx\s+(?:-y\s+|--yes\s+)?@pacta/mcp-server")
    npx_scope = sorted(set(
        [os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(DOCS, "**", "*"), recursive=True)
         if os.path.isfile(f) and f.endswith((".html", ".txt", ".json", ".md", ".js", ".xml"))]
        + ["README.md", "glama.json", "smithery.yaml", "packages/mcp-server/README.md", "packages/mcp-server/SKILL.md",
           "packages/mcp-server/server.json", "packages/mcp-server/server.remote.json", "packages/mcp-server/Dockerfile", "Dockerfile",
           ".github/workflows/publish-mcp.yml"]))
    dead = [f for f in npx_scope if DEAD_NPX.search(read(f))]
    primary = {"docs/index.html": home, "docs/request/index.html": req_page, "docs/SKILL.md": read("docs/SKILL.md"),
               "docs/.well-known/mcp.json": read("docs/.well-known/mcp.json"), "docs/llms.txt": read("docs/llms.txt"),
               "docs/llms-full.txt": read("docs/llms-full.txt"), "README.md": read("README.md")}
    no_remote = [k for k, t in primary.items() if MCP_ not in t or "/v1/check/preflight" not in t]
    check("unshipped npm install removed: 0 'npx @pacta/mcp-server' strings on the site, feeds, README, server.json, glama.json, smithery.yaml; remote MCP + /v1/check/preflight on every primary surface",
          not dead and not no_remote and len(npx_scope) > 50, f"{len(npx_scope)} files scanned; dead npx in {dead}; missing remote/preflight in {no_remote}")

    idx_ = json.load(open(os.path.join(DOCS, "api", "v1", "index.json")))
    radar_ = json.load(open(os.path.join(DOCS, "api", "v1", "radar.json")))
    groups = BS.protocol_groups(idx_)
    prot_bad, sm = [], read("docs/sitemap.xml")
    for name, es in groups.items():
        slug = BS.protocol_slug(name)
        rel = f"docs/protocols/{slug}/index.html"
        if not os.path.exists(os.path.join(ROOT, rel)):
            prot_bad.append(f"{slug}: missing"); continue
        t = read(rel)
        if t != BS.protocol_page(name, es, idx_, radar_):
            prot_bad.append(f"{slug}: not a deterministic rebuild")
        lds = re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S)
        try:
            ld_ok = bool(lds) and all(json.loads(x).get("@context") == "https://schema.org" for x in lds)
        except ValueError:
            ld_ok = False
        if not ld_ok:
            prot_bad.append(f"{slug}: JSON-LD")
        if not all(str(e["block_number"]) in t.replace(",", "") and e["block_hash"] in t for e in es):
            prot_bad.append(f"{slug}: pinned block/hash")
        if "cast call" not in t and "cast storage" not in t:
            prot_bad.append(f"{slug}: cast repro")
        if f"{API_}/v1/check/preflight" not in t:
            prot_bad.append(f"{slug}: preflight quickstart")
        if f"<loc>{BS.BASE_URL}/protocols/{slug}/</loc>" not in sm:
            prot_bad.append(f"{slug}: sitemap")
    pidx = read("docs/protocols/index.html") if os.path.exists(os.path.join(DOCS, "protocols", "index.html")) else ""
    pidx_ok = bool(pidx) and pidx == BS.protocols_index_page(idx_, groups) and f"<loc>{BS.BASE_URL}/protocols/</loc>" in sm \
        and all(f'href="{BS.protocol_slug(n)}/"' in pidx for n in groups) and '"@type": "ItemList"' in pidx.replace('"@type":"ItemList"', '"@type": "ItemList"')
    check(f"/protocols/<slug>/ SEO pages: one per indexed protocol ({len(groups)}), deterministic, schema.org JSON-LD, pinned block + hash, cast repro, preflight quickstart, in the sitemap; /protocols/ index (ItemList)",
          not prot_bad and pidx_ok and len(groups) == len({e["protocol"] for e in idx_["entries"]}), f"bad {prot_bad[:4]}; index {pidx_ok}")

    robots = read("docs/robots.txt")
    bots = ["GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot", "Googlebot", "*"]
    robots_ok = all(re.search(rf"^User-agent: {re.escape(b)}\nAllow: /$", robots, re.M) for b in bots) \
        and not re.search(r"^Disallow:\s*\S", robots, re.M) and f"Sitemap: {BS.BASE_URL}/sitemap.xml" in robots
    check("robots.txt welcomes GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot, Googlebot and * (no Disallow) and points at the sitemap", robots_ok)

    glama = json.loads(read("glama.json"))
    smith = read("smithery.yaml")
    srv = json.loads(read("packages/mcp-server/server.json"))
    srv_r = json.loads(read("packages/mcp-server/server.remote.json"))
    dockerfile = read("packages/mcp-server/Dockerfile")
    reg_ok = {
        "glama.json": glama == {"$schema": "https://glama.ai/mcp/schemas/server.json", "maintainers": ["pacta-fractal-neurons"]},
        "smithery.yaml": bool(re.search(r"^startCommand:\n  type: stdio$", smith, re.M)) and "dockerfile: packages/mcp-server/Dockerfile" in smith
                         and MCP_ in smith and '"/app/bin/pacta-mcp.mjs"' in smith,
        "server.json remotes": srv.get("remotes") == [{"type": "streamable-http", "url": MCP_}] and srv_r.get("remotes") == srv["remotes"]
                               and "packages" not in srv_r and srv_r["name"] == srv["name"] and srv_r["version"] == srv["version"],
        "Dockerfile stdio": 'ENTRYPOINT ["node", "/app/bin/pacta-mcp.mjs"]' in dockerfile and "EXPOSE" not in dockerfile,
    }
    check("registries: glama.json (schema + maintainer), smithery.yaml (stdio from the Dockerfile + remote URL), server.json + server.remote.json remotes (streamable-http), Dockerfile stdio entrypoint",
          all(reg_ok.values()), str({k: v for k, v in reg_ok.items() if not v}))

    remote_tools = ["pacta_check_preflight", "pacta_scan_control_plane", "pacta_scan_timelock_op", "pacta_scan_proposal_diff", "pacta_get_live_timelocks"]
    man_ = json.loads(read("docs/.well-known/mcp.json"))
    card_ = json.loads(read("docs/.well-known/agent.json"))
    man_remote = next((t_ for t_ in man_.get("transports", []) if t_.get("type") == "streamable-http"), {})
    srv_src = read("packages/mcp-server/src/server.mjs")
    surfaces5 = {
        "mcp.json": man_remote.get("url") == MCP_ and man_remote.get("tools") == remote_tools,
        "agent.json": card_.get("endpoints", {}).get("mcp_remote") == MCP_ and card_.get("pricing", {}).get("mode") == "free_launch"
                      and card_["x402"].get("pricingMode") == "free_launch" and card_["skills"][0]["id"] == "contract-preflight",
        "SKILL.md": all(n in primary["docs/SKILL.md"] for n in remote_tools),
        "llms.txt": all(n in primary["docs/llms.txt"] for n in remote_tools) and "## Free API for agents" in primary["docs/llms.txt"],
        "llms-full.txt": all(n in primary["docs/llms-full.txt"] for n in remote_tools),
        "@pacta/mcp-server": 'name: "pacta_check_preflight"' in srv_src and "PAID_ROUTES.checkPreflight" in srv_src,
        "SKILL.md copies": read("packages/mcp-server/SKILL.md") == primary["docs/SKILL.md"],
    }
    check("remote MCP: 5 tools (pacta_check_preflight first) on mcp.json, agent.json (free_launch pricing), SKILL.md, llms.txt, llms-full.txt; @pacta/mcp-server ships pacta_check_preflight; SKILL.md copies byte-identical",
          all(surfaces5.values()), str({k: v for k, v in surfaces5.items() if not v}))

    # ---- Phase C: first-party beacon, 404, governance forum digest, MCP Registry workflow, root Dockerfile ----
    BEACON_URL = API_ + "/v1/telemetry/beacon"
    bjs_raw = read("docs/b.js", "rb") if os.path.exists(os.path.join(DOCS, "b.js")) else b""
    bjs = bjs_raw.decode()
    b_urls = set(re.findall(r"https?://[^\s\"'`)]+", bjs))
    b_events = {"page_load", "scroll_50", "scroll_90", "copy_mcp_url", "copy_curl", "copy_skill_md", "cta_click", "protocol_view", "not_found_404"}
    beacon_static = {
        "size < 1500 bytes": 0 < len(bjs_raw) < 1500,
        "only the first-party endpoint": b_urls == {BEACON_URL},
        "sendBeacon(url, string) + keepalive no-cors fallback": "sendBeacon(U,b)" in bjs.replace(" ", "") and "JSON.stringify" in bjs
                                                               and re.search(r'keepalive:\s*(!0|true)', bjs) is not None and '"no-cors"' in bjs,
        "Do Not Track gate": re.search(r'\.doNotTrack\s*!=\s*"1"', bjs) is not None,
        "every contract event": all(f'"{e}"' in bjs for e in b_events) and "live_checker_submit" in appjs,
        "no cookie / storage / fingerprint APIs": not re.search(r"cookie|localStorage|sessionStorage|indexedDB|userAgent|canvas|crypto|Math\.random|Date\.now",
                                                                re.sub(r"/\*.*?\*/", "", bjs, flags=re.S)),
    }
    check(f"beacon docs/b.js ({len(bjs_raw)} bytes): < 1.5 KB, posts only to {BEACON_URL} via sendBeacon (string body; fetch keepalive no-cors fallback), DNT gate, all 9 page events (+ live_checker_submit from app.js), no cookie/storage/fingerprint APIs",
          all(beacon_static.values()), str({k: v for k, v in beacon_static.items() if not v}))
    script_re = re.compile(r'<script\b([^>]*)>(.*?)</script>', re.S)
    no_beacon, third, bad_inline = [], [], []
    for rel, text in sorted(pages.items()):
        bpos_ = text.find("<body")
        srcs = [re.search(r'src="([^"]+)"', a).group(1) for a, _ in script_re.findall(text) if 'src="' in a]
        b_src = [x for x in srcs if x.split("/")[-1] == "b.js"]
        ok_b = len(b_src) == 1 and f'<script src="{b_src[0]}" defer></script>' in text[:bpos_] and \
            os.path.normpath(b_src[0].lstrip("/") if b_src[0].startswith("/") else os.path.join(os.path.dirname(rel), b_src[0])) == "b.js"
        if not ok_b:
            no_beacon.append(rel)
        for tag_, attr_ in re.findall(r'<(script|link|img|iframe|source|video|audio)\b([^>]*)>', text):
            for u in re.findall(r'\b(?:src|href)="([^"]+)"', attr_):
                if (tag_ != "link" or re.search(r'rel="(?:stylesheet|icon|preload|modulepreload|prefetch)"', attr_)) and \
                        (u.startswith("//") or (re.match(r"https?://", u) and urllib_host(u) not in ("pacta.wtf",))):
                    third.append(f"{rel}: <{tag_}> {u}")
        for attrs_, body_ in script_re.findall(text):
            if "src=" in attrs_ or "application/ld+json" in attrs_:
                continue
            if re.search(r"fetch\(\s*[\"'`](?:https?:)?//|document\.cookie|sessionStorage|indexedDB|sendBeacon|XMLHttpRequest|new Image\b|WebSocket", body_) or \
                    set(re.findall(r'localStorage\.(?:getItem|setItem)\("([^"]+)"', body_)) - {"pacta-theme"}:
                bad_inline.append(rel)
    check(f"beacon loaded (defer, in <head>) on every HTML page incl. 404.html ({len(pages)} pages); no third-party script/style/image hosts; inline scripts make no requests",
          not no_beacon and not third and not bad_inline and "404.html" in pages, f"missing beacon {no_beacon[:4]}; third-party {third[:4]}; inline {bad_inline[:4]}")
    page_js = {"docs/app.js": appjs, "docs/b.js": bjs}
    ls_keys = set(re.findall(r'localStorage\.(?:getItem|setItem)\("([^"]+)"', appjs))
    js_bad = sorted(f for f, t in page_js.items() if re.search(r"document\.cookie|sessionStorage|indexedDB|XMLHttpRequest|new Image\b|WebSocket|EventSource|importScripts|createElement\(\s*\"script", t))
    data_api = set(re.findall(r'data-api="([^"]+)"', "".join(pages.values())))
    app_fetch = len(re.findall(r"\bfetch\(", appjs))
    check("no cookies, no storage identifiers, no third-party requests in page scripts: localStorage only for the theme preference; app.js fetches only this site's JSON and the first-party API (data-api)",
          not js_bad and ls_keys == {"pacta-theme"} and appjs.count("localStorage") == 2 and data_api <= {API_}
          and app_fetch == 2 and 'fetch(document.documentElement.getAttribute("data-api") || "api/v1/index.json")' in appjs
          and 'fetch(api + "/v1/check/preflight?chain=" + ch + "&address=" + a, opts)' in appjs,
          f"bad {js_bad}; localStorage keys {sorted(ls_keys)}; data-api {sorted(data_api)}; fetch {app_fetch}")
    b_keys = ["b_page_load_payload", "b_hook_exposed", "b_copy_and_cta_events", "b_scroll_once_each", "b_live_checker_submit", "b_invalid_submit_not_reported",
              "b_protocol_view", "b_protocol_copy_curl_and_cta", "b_not_found_404", "b_not_found_path_sanitised", "b_not_found_copy_mcp",
              "b_dnt_sends_nothing", "b_non_https_sends_nothing", "b_fetch_fallback", "b_no_cookie_access"]
    failed_bk = [k for k in b_keys if res.get(k) is not True] + (["harness_error: " + res["harness_error"][:200]] if "harness_error" in res else [])
    check("beacon behaviour (node harness, mocked navigator.sendBeacon): page_load {r, u}, same-site r=self, protocol_view t=slug, copy_mcp_url / copy_curl / copy_skill_md / cta_click hooks, scroll_50/90 once, live_checker_submit t=chain:address, 404 path sanitised, DNT and http send nothing, fetch keepalive fallback",
          not failed_bk, f"{len(b_keys) - len([k for k in b_keys if res.get(k) is not True])}/{len(b_keys)}; failed {failed_bk[:4]}")
    f1_keys = ["pf_f1_stale_200_keeps_input_error", "pf_f1_previous_request_aborted", "pf_f1_no_abortcontroller_still_safe"]
    run_src = appjs[appjs.find("function run()"):appjs.find("form.addEventListener(\"submit\"", appjs.find("function run()"))]
    f1_static = run_src.find("++seq") != -1 and run_src.find("++seq") < run_src.find("ADDR_RE.test") and run_src.find(".abort()") < run_src.find("ADDR_RE.test")
    check("F1 regression: a pending valid pre-flight is superseded (seq bumped + AbortController.abort before validation); an invalid submit's error is never overwritten by the stale HTTP 200",
          f1_static and all(res.get(k) is True for k in f1_keys), f"static {f1_static}; {[k for k in f1_keys if res.get(k) is not True]}")

    nf = pages.get("404.html", "")
    nf_raw = nf.encode()
    nf_h, nf_b = nf_raw.find(b"<head>"), nf_raw.find(b"<body")
    nf_tw = nf_raw.find(b">", nf_raw.find(b'name="twitter:image"')) + 1
    nf_ok = {
        "head budget": bool(nf) and 0 <= nf_b < 2500 and 0 < nf_tw - nf_h <= 1200 and "<style" not in nf and "data:image/" not in nf,
        "noindex + data-nf": '<meta name="robots" content="noindex">' in nf[:nf_b] and re.search(r'<main id="main"[^>]* data-nf>', nf) is not None,
        "root-relative navigation": all(f'href="{h}"' in nf for h in ("/protocols/", "/#preflight", "/request/", "/styles.css", "/llms.txt")) and 'src="/b.js"' in nf
                                    and not re.search(r'(?:href|src)="(?!/|https://|#)', nf),
        "remote MCP URL + copy": f'data-copy="{MCP_}"' in nf and f"claude mcp add --transport http pacta {MCP_}" in nf,
        "deterministic build": nf == BS.not_found_page(idx_),
        "not in sitemap": "/404.html" not in sm,
    }
    check("404.html: same head rules (<body> < 2500 B, OG/X in 1.2 KB, no inline style), noindex, root-relative links to /protocols/ and /#preflight, remote MCP URL, fires not_found_404 (harness), deterministic",
          all(nf_ok.values()) and res.get("b_not_found_404") is True, str({k: v for k, v in nf_ok.items() if not v}))

    # forum digest (CONTRACTS §3, site side)
    fd_path = os.path.join(DOCS, "api", "v1", "forum-digest.json")
    fd_raw = read("docs/api/v1/forum-digest.json") if os.path.exists(fd_path) else ""
    try:
        fd = json.loads(fd_raw)
    except ValueError:
        fd = {}
    src_digest = BS.load_forum_digest()
    ai = fd.get("addressIndex", {})
    want_ai = {}
    for e in sorted(idx_["entries"], key=lambda e: e["id"]):
        want_ai.setdefault("ethereum:" + e["target_contract"].lower(), BS.protocol_family(e["protocol"]))
    fd_ok = {
        "schema": fd.get("schema") == "pacta.forum_digest.v1" and fd.get("readOnly") is True and isinstance(fd.get("forums"), dict)
                  and isinstance(fd.get("discussions"), list) and list(fd) == ["schema", "generatedAt", "readOnly", "forums", "discussions", "addressIndex"],
        "addressIndex": ai == want_ai and list(ai) == sorted(ai) and all(re.fullmatch(r"(ethereum|base):0x[0-9a-f]{40}", k) for k in ai)
                        and all(re.fullmatch(r"[a-z0-9]+", v) for v in ai.values()),
        "families": BS.protocol_family("Aave V3 / GHO") == "aave" and BS.protocol_family("Morpho Blue Core") == "morpho"
                    and BS.protocol_family("MetaMorpho (Re7 WETH vs. Re7 USDT)") == "morpho" and BS.protocol_family("Spark / Sky") == "sky"
                    and BS.protocol_family("Lido (stETH / Dual Governance)") == "lido" and BS.protocol_family("Compound V3 (Comet)") == "compound",
        "deterministic rebuild": fd_raw == BS.forum_digest_json(idx_, src_digest) == BS.forum_digest_json(idx_, json.loads(json.dumps(src_digest))),
        "no wall clock": "datetime" not in BS.forum_digest_json.__code__.co_names and "now" not in BS.forum_digest_json.__code__.co_names,
    }
    gov_pages = sorted(r for r, t in pages.items() if "Active governance discussions" in t)
    expect_gov = sorted(os.path.join("protocols", BS.protocol_slug(n), "index.html") for n in groups if BS.governance_discussions(n, src_digest))
    check(f"forum-digest.json (pacta.forum_digest.v1): readOnly, deterministic addressIndex for all {len(want_ai)} index targets (chain:lowercase address -> family); governance sections only where the family has discussions",
          all(fd_ok.values()) and gov_pages == expect_gov, f"{ {k: v for k, v in fd_ok.items() if not v} }; rendered {gov_pages[:3]} expected {expect_gov[:3]}")
    # synthetic digest, in memory only (clearly fake topics on the real forum hosts; never written to data/ or docs/)
    syn = {"schema": "pacta.forum_digest.v1", "generatedAt": "2026-01-01T00:00:00Z", "readOnly": True,
           "forums": {"governance.aave.com": {"protocol": "aave", "lastPolledAt": "2026-01-01T00:00:00Z"}},
           "discussions": [{"forum": "governance.aave.com", "protocol": "aave", "topicId": 900000 + i, "title": f"SYNTHETIC verifier topic {i}" + (" <b>x</b>" if i == 6 else ""),
                            "url": f"https://governance.aave.com/t/synthetic-verifier-topic/{900000 + i}", "createdAt": "2026-01-01T00:00:00Z",
                            "lastPostedAt": f"2026-01-{10 + i:02d}T00:00:00Z", "postsCount": i, "tags": ["synthetic"], "riskTerms": ["cap"] if i % 2 else []}
                           for i in range(1, 8)]
           + [{"forum": "governance.aave.com", "protocol": "aave", "topicId": 999999, "title": "SYNTHETIC wrong host", "url": "https://evil.example.invalid/t/1",
               "lastPostedAt": "2026-02-01T00:00:00Z", "postsCount": 1},
              {"forum": "forum.euler.finance", "protocol": "euler", "topicId": 999998, "title": "SYNTHETIC euler topic",
               "url": "https://forum.euler.finance/t/synthetic/999998", "lastPostedAt": "2026-02-02T00:00:00Z", "postsCount": 2}]}
    aave_name = next(n for n in groups if BS.protocol_family(n) == "aave")
    morpho_name = next(n for n in groups if BS.protocol_family(n) == "morpho")
    aave_es = groups[aave_name]
    syn_page = BS.protocol_page(aave_name, aave_es, idx_, radar_, syn)
    sec = re.search(r'<section class="memo-sec" id="governance">.*?</section>', syn_page, re.S)
    titles = re.findall(r"SYNTHETIC verifier topic (\d)", sec.group(0)) if sec else []
    empty = BS.empty_forum_digest()
    syn_doc = BS.forum_digest_doc(idx_, syn)
    syn_ok = {
        "rendered, max 5, newest first": titles == ["7", "6", "5", "4", "3"],
        "escaped, https on the forum host only": bool(sec) and "&lt;b&gt;x&lt;/b&gt;" in sec.group(0) and "<b>x</b>" not in sec.group(0)
                                                 and "evil.example.invalid" not in syn_page and 'rel="noopener nofollow"' in sec.group(0),
        "other families unaffected": "Active governance discussions" not in BS.protocol_page(morpho_name, groups[morpho_name], idx_, radar_, syn),
        "empty digest renders nothing": BS.governance_section(aave_name, empty) == "" and "Active governance discussions" not in BS.protocol_page(aave_name, aave_es, idx_, radar_, empty),
        "normalised doc": [d["topicId"] for d in syn_doc["discussions"]] == [999998] + list(range(900001, 900008)) and syn_doc["addressIndex"] == want_ai
                          and BS.forum_digest_json(idx_, syn) == BS.forum_digest_json(idx_, syn),
    }
    check("governance discussions (synthetic in-memory digest via the generator): <= 5 newest first on the matching family page, HTML-escaped, foreign-host URLs dropped, nothing for other families or an empty digest",
          all(syn_ok.values()), str({k: v for k, v in syn_ok.items() if not v}))

    wf_path = os.path.join(ROOT, ".github", "workflows", "publish-mcp.yml")
    wf = read(".github/workflows/publish-mcp.yml") if os.path.exists(wf_path) else ""
    wf_ok = {
        "triggers": re.search(r"^on:\n  push:\n    branches: \[\"main\"\]", wf, re.M) is not None and re.search(r"^  workflow_dispatch:", wf, re.M) is not None,
        "permissions": re.search(r"^permissions:\n  id-token: write\n  contents: read$", wf, re.M) is not None and "write-all" not in wf
                       and len(re.findall(r"^\s*[\w-]+:\s*write\b", wf, re.M)) == 1,
        "pinned + verified mcp-publisher": re.search(r'MCP_PUBLISHER_VERSION: "v\d+\.\d+\.\d+"', wf) is not None and re.search(r'MCP_PUBLISHER_SHA256: "[0-9a-f]{64}"', wf) is not None
                                           and "sha256sum -c" in wf and "checksums.txt" in wf and "releases/latest" not in wf,
        "oidc login + remotes-only publish": "mcp-publisher login github-oidc" in wf and "mcp-publisher publish" in wf
                                             and re.search(r'cp packages/mcp-server/server\.remote\.json "\$ws/server\.json"', wf) is not None and 'ws="$RUNNER_TEMP/' in wf
                                             and "io.github.fractal-neurons/pacta" in wf.split("\nname:", 1)[0],
        "no secrets / PATs": not re.search(r"secrets\.|GITHUB_TOKEN|_PAT\b|NPM_TOKEN|login github\b(?!-oidc)|--token", wf),
    }
    check(".github/workflows/publish-mcp.yml: push to main + workflow_dispatch, id-token: write + contents: read only, pinned sha256-verified mcp-publisher, github-oidc login, publishes server.remote.json (staged in the runner temp dir), no secrets",
          all(wf_ok.values()), str({k: v for k, v in wf_ok.items() if not v}))
    df = read("Dockerfile") if os.path.exists(os.path.join(ROOT, "Dockerfile")) else ""
    copies = re.findall(r"^COPY\s+(.+)$", df, re.M)
    df_ok = {
        "base": re.search(r"^FROM node:22-alpine$", df, re.M) is not None and len(re.findall(r"^FROM ", df, re.M)) == 1,
        "copies only packages/mcp-server": bool(copies) and all(all(x.startswith("packages/mcp-server/") for x in c.split()[:-1]) for c in copies)
                                            and {"packages/mcp-server/bin", "packages/mcp-server/src"} <= {x for c in copies for x in c.split()[:-1]},
        "gateway env": f"ENV PACTA_X402_URL={API_}" in df,
        "stdio entrypoint, no EXPOSE": 'ENTRYPOINT ["node", "/app/bin/pacta-mcp.mjs"]' in df and "EXPOSE" not in df and "RUN npm" not in df,
        "no Smithery": "smithery" not in df.lower() and "smithery" not in wf.lower() and "smithery" not in nf.lower(),
    }
    check("root Dockerfile (glama.ai): node:22-alpine, copies only packages/mcp-server, PACTA_X402_URL = live gateway, stdio ENTRYPOINT node /app/bin/pacta-mcp.mjs, no EXPOSE",
          all(df_ok.values()), str({k: v for k, v in df_ok.items() if not v}))
    readme = read("README.md")
    priv = readme[readme.find("## Analytics & privacy"):][:1500] if "## Analytics & privacy" in readme else ""
    check("README: Analytics & privacy note (first-party beacon, no cookies, Do Not Track, observed client metadata only)",
          bool(priv) and all(t in priv for t in ("first-party", "cookie", "Do Not Track", "observed client metadata", "/v1/telemetry/beacon")))

    # private identifiers must never be published: compared by SHA-256 of lowercased tokens, so the
    # repository itself never contains the literal identifiers this check guards against
    scope = [p for p in glob.glob(os.path.join(ROOT, "docs", "**", "*"), recursive=True) + glob.glob(os.path.join(ROOT, "audits", "**", "*"), recursive=True)
             + glob.glob(os.path.join(ROOT, "tools", "**", "*"), recursive=True) + [os.path.join(ROOT, "README.md"), os.path.abspath(__file__)]
             if os.path.isfile(p) and p.endswith((".html", ".txt", ".json", ".xml", ".js", ".css", ".md", ".py"))]
    leaks = sorted({os.path.relpath(p, ROOT) for p in scope if tokens(open(p, errors="replace").read()) & DENY_SHA256})
    check("no private / quarantined identifiers (SHA-256 token deny-list)", not leaks, f"{len(scope)} files scanned; leaks in: {leaks}")

    width = max(len(n) for n, _, _ in RESULTS)
    for name, ok, detail in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
