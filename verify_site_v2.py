#!/usr/bin/env python3
"""verify_site_v2.py - offline checks for the Pacta static site (docs/). Pure stdlib; no network.

  python3 verify_site_v2.py        # exit 0 = all checks passed
  python3 verify_site_v2.py --verify-sync-receipt PATH --verify-memory-centre http://127.0.0.1:<port>/mcp [--memory-env-file F]

Checks: <head> budget (<body> before byte 3000; OG + X tags inside the first 1.2 KB of <head>), zero data:image blobs,
required Open Graph / X card / canonical tags, zero "Security Quarantine" wording, count parity (sprints / records)
across index.html, llms.txt, README.md and /api/v1/index.json, summary SHA-256 digests, EIP-55 checksums, matrix row
count, og-preview.png = 1200x628 PNG, favicon sizes, discovery files (llms.txt, robots.txt, sitemap.xml,
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
import html
import json
import os
import re
import base64
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
RESULTS = []
# ---- EXPECT-BEGIN: the published numbers, in one place (tools/apply_sprint34_attestation.py rewrites this block when it stamps a Sprint)
EXPECT = {
    "sprints": 34, "records": 299, "eas_attestations": 34,              # index.json sprints_completed / records_indexed; Base EAS sprint UIDs
    "protocols": 313, "eas_protocols": 180, "rpc_protocols": 133,          # /protocols/ pages = EAS-attested + RPC-pinned; badges = protocols
    "briefs": 17, "badge_tiers": {"aligned": 119, "parameter_delta": 61, "rpc_observed": 133},
    "base_records": 36,                                                  # index.json records with chain "base"
    "rpc_by_chain": {"ethereum": 122, "base": 11},                         # rpc-pinned.json records per chain (sum = rpc_protocols)
    "multi_attest_txs": ["1–12", "13–16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34"],                              # attestation_coverage.eas_multi_attest_txs keys
    "summaries": {"15": "61c0cc292cfa1fc3840277cf312383d24a6c81af56afac303afdbd84e7316cf6",
                  "16": "91b8e29301ef0e625c4ddc9eadaf5388115812f5958f90b6e0ed53a4808ba8ae",
                  "17": "2fd7ab979c6dfc3aae44f6c46c8f0397959927874ff0358574043a056d3168ea",
                  "18": "fc2f39d1c8c9a0c301f1a664be5fcdee9391971598a24739dccd3fbd0364aeae",
                  "19": "be0b41a158027fb99a3b54d5411d13790c08047e40a1c6804412f82b1f183968",
                  "20": "ecf3ff31366c88541b265c13153f7dd3cd087d7f1f6ae7a801b63669d2fc94af",
                  "21": "a114b900050c2e71b026efb664dfaf6584603b053089f11ea245b8e75041e35b",
                  "22": "a6a933827b5c74a6d1839d747fd3d09b8c6b3ef11c278f7b395ca18aa26da35b",
                  "23": "98ac27b6847e96920e3479f7692adaa4056e2f21c94fae30624edf1442faea59",
                  "24": "3719c5f2ae685806b428a5dea0b9b62b8969bca591271f484cb97c20cb53a36d",
                  "25": "4046bfd661f631ceedb335ad428fa8285e7906b1bed34c25a29fe894510c94bc",
                  "26": "cbf6009b33bde0e22ec37fc45720aad3dad57bfcd91f8763e6b31fdf223c583d",
                  "27": "be4a0d34a555b52a23bf57a9852be083b669e19151323c42bb322c18f0df1d6b",
                  "28": "062632d4abf0411664883823e185de5f974c9e989bf8497c0e8863b557b878bd",
                  "29": "ba61b61feb65e1b23d10c998f70bcabce22a8b27203581542ef1cc3b68a4507f",
                  "30": "f51c2033847f5012027468eea28660c59c270c5f2592f06a248483f4c7c040fc",
                  "31": "98020d2a953d0c6ef6ef75ddca1a7f48a8c43a1b30ecef4926e33b8c1617816d",
                  "32": "d743b19a325763801e120af7b3bd48775dec49dd9a3a3888fbe32192d7f20094",
                  "33": "795432ee6da61e4eb4e8efde2a99e00975d206734bc513080fb28a7da559dea4",
                  "34": "0f68f60a5ab92cd74ca0fe2221ebf9c75e59ce7f9e5cf24d80488fd38eac6c6c"},   # audits/sprint-<n>/ summary SHA-256 (attested)
}
# ---- EXPECT-END
X = EXPECT
# sha256 of docs/api/v1/graph-manifest.json: changes only through a deliberate re-pin (a Sprint stage / stamp rewrites it after the
# rebuild); a merged Wave 2 claim or any site-only change must leave it as is
GRAPH_MANIFEST_SHA256 = "713555ca9cf53b81e183fe794599b452d51f02b955ab191e04d832fa20377806"
NON_PROTOCOL_PAGES = 39                                                  # docs/**/*.html pages that are not /protocols/<slug>/ (39: + /scan/ /webhook/ /seal/ /miniapp/, + the Cap, Compound V3 and Lista Lending briefs)


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


def png_rgb(path):
    """Minimal stdlib PNG decoder (8-bit RGB / RGBA, not interlaced): (width, height, channels, unfiltered rows)."""
    import zlib
    raw = open(path, "rb").read()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, hdr = 8, b"", None
    while pos < len(raw):
        n = struct.unpack(">I", raw[pos:pos + 4])[0]
        tag, data = raw[pos + 4:pos + 8], raw[pos + 8:pos + 8 + n]
        pos += 12 + n
        if tag == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", data)
        elif tag == b"IDAT":
            idat += data
        elif tag == b"IEND":
            break
    w, h, depth, ctype, _, _, interlace = hdr
    assert depth == 8 and ctype in (2, 6) and interlace == 0
    ch = 3 if ctype == 2 else 4
    stride, buf = w * ch, zlib.decompress(idat)
    rows, prev = [], bytearray(stride)
    for y in range(h):
        f = buf[y * (stride + 1)]
        line = bytearray(buf[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a, b, c = (line[i - ch] if i >= ch else 0), prev[i], (prev[i - ch] if i >= ch else 0)
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                q = a + b - c
                pa, pb, pc = abs(q - a), abs(q - b), abs(q - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return w, h, ch, rows


SOCIAL_CARDS = ["og-preview.png", "cards/x-card-scorecards-1200x628.png", "cards/x-card-scan19-1200x628.png", "cards/x-card-seal99-1200x628.png"]


def dom_tree(text):
    t = Tree()
    t.feed(text)
    return next(n for n in t.root[2] if isinstance(n, list) and n[0] == "html")


def app_behaviour(appjs, request_html, index_html, row_id, beacon="", protocol_html="", protocol_slug="", notfound_html="",
                  clearance_html="", clearance_slug="", brief_html="", brief_slug="", prefill_slug="", timelock_brief_html="", protocols_index_html="",
                  extra=None):
    """Run docs/app.js (and the docs/b.js beacon) under node against a synthetic DOM of the real pages. No network, no listener, no files."""
    node = shutil.which("node")
    if not node:
        return {"harness_error": "node not found"}
    payload = json.dumps({"app": appjs, "request": dom_tree(request_html), "index": dom_tree(index_html), "rowId": row_id, "beacon": beacon,
                          "protocol": dom_tree(protocol_html) if protocol_html else None, "protocolSlug": protocol_slug,
                          "notfound": dom_tree(notfound_html) if notfound_html else None,
                          "clearanceProtocol": dom_tree(clearance_html) if clearance_html else None, "clearanceSlug": clearance_slug,
                          "brief": dom_tree(brief_html) if brief_html else None, "briefSlug": brief_slug, "prefillSlug": prefill_slug,
                          "timelockBrief": dom_tree(timelock_brief_html) if timelock_brief_html else None,
                          "protocolsIndex": dom_tree(protocols_index_html) if protocols_index_html else None,
                          "indexJson": json.loads(read("docs/api/v1/index.json")), "scorecardsJson": json.loads(read("docs/api/v1/scorecards.json")), "whatDiffers": inspector_what_differs(),
                          "lookupJson": json.loads(read("docs/api/v1/lookup.json")),   # v4.7 W3: the command dialog + hero name lookup
                          # every published protocol slug (+ wave-2 shapes) must survive the beacon's client-side path redaction
                          "expectProtocols": X["protocols"],
                          "protocolSlugs": sorted(d for d in os.listdir(os.path.join(DOCS, "protocols")) if os.path.isdir(os.path.join(DOCS, "protocols", d))),
                          **(extra or {})})
    # 300 s: the harness replays every protocol page (309) and the visitor / basket matrices; ~2 min on a loaded host
    out = subprocess.run([node, os.path.join(ROOT, "tools", "app_harness.js")], input=payload, capture_output=True, text=True, timeout=300)
    try:
        return json.loads(out.stdout)
    except ValueError:
        return {"harness_error": (out.stderr or out.stdout)[-400:]}


NOWRAP_CLASSES = {"hx", "addr", "btn", "badge", "chip", "countdown", "opstate", "nowrap"}


def unwrappable_runs(pages, min_len=30):
    """Narrow-screen guard without a browser: every unbroken text run of min_len+ chars (a 42-char address is wider than the 319 px
    content box at 375 px) on a /protocols/<slug>/ page must sit inside .memo-wrap (where overflow-wrap: anywhere is inherited) or in a
    self-scrolling .term pre, and never inside a white-space: nowrap element. Returns the offending (page, run) pairs."""
    import html.parser as HP
    bad = []

    class Scan(HP.HTMLParser):
        def __init__(self, page):
            super().__init__(convert_charrefs=True)
            self.page, self.stack, self.skip = page, [], 0

        def handle_starttag(self, tag, attrs):
            if tag in ("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"):
                return
            self.stack.append((tag, set((dict(attrs).get("class") or "").split())))
            self.skip += tag in ("script", "style", "head")

        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    self.skip -= sum(t in ("script", "style", "head") for t, _ in self.stack[i:])
                    del self.stack[i:]
                    break

        def handle_data(self, data):
            if self.skip:
                return
            for tok in re.split(r"[\s\u00a0]+", data):
                for part in re.split(r"(?<=-)", tok):
                    if len(part) < min_len:
                        continue
                    cls = [c for _, cs in self.stack for c in cs]
                    in_term_pre = any(t == "pre" for t, _ in self.stack) and "term" in cls
                    wraps = "memo-wrap" in cls and not NOWRAP_CLASSES & set(cls)
                    if not (in_term_pre or wraps):
                        bad.append((self.page, part[:50]))

    for r, t in pages.items():
        if r.startswith("protocols" + os.sep) and r.count(os.sep) == 2:
            Scan(r).feed(t)
    return bad


def inspector_what_differs():
    """{record id: {"changed": [li text], "matched": [li text]}} for every flagged index.json record, from tools/control_diff.py: the
    inspector's app.js port must render exactly these lines."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import control_diff as CDV
    out = {}
    for e in json.loads(read("docs/api/v1/index.json"))["entries"]:
        wd = CDV.what_differs([e])
        if wd:
            out[e["id"]] = {"changed": [f'{c["parameter"]}: {c["observed"]} observed vs {c["documented"]} documented' for c in wd["changed"]],
                            "matched": [f'{m["parameter"]}: {m["value"]}' for m in wd["matched"]]}
    return out


def urllib_host(u):
    import urllib.parse
    return urllib.parse.urlsplit(u).hostname or ""


def llms_txt(read_):
    return read_("docs/llms.txt")


# ---------------------------------------------------------------- Phase 1 graph manifest (docs/api/v1/graph-manifest.json)
GRAPH_RELATIONS = ("governed_by_controller", "exhibits_control_plane_gap", "attested_by_base_eas", "collateral_contagion_upstream")
GRAPH_EPHEMERAL = ("discusses_protocol", "attention_spike_on")
GRAPH_EPHEMERAL_PREFIXES = ("analytics-", "forum-", "pacta-intent-")
GRAPH_TAU = 0.65
# U4 baseline: the node ids promoted before Sprint 24 (tools/graph_u4_baseline.json). Their texts are minted and immutable, and the word
# TF-IDF cosine of two short texts with rare shared tokens rises with every node added to the corpus, so pairs inside the baseline are held
# to their own ceiling and reported; every pair with at least one newer node stays below GRAPH_TAU. The token-count (bow) metric is
# applied to every pair, with no baseline. From Sprint 27 the same rule covers every node minted before the current Sprint: the apply
# script records them as minted_before {sprint, nodes} (the pre-Sprint tools/graph_minted.json ids), so only pairs of two already-published
# texts move to the ceiling; any pair with a node first published in the current Sprint stays below GRAPH_TAU.
GRAPH_TFIDF_BASELINE_CEILING = 0.70


def _graph_tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _graph_cos(a, b):
    num = sum(v * b.get(k, 0.0) for k, v in a.items())
    den = (sum(v * v for v in a.values()) * sum(v * v for v in b.values())) ** 0.5
    return num / den if den else 0.0


def graph_distinctiveness(texts, exempt_tfidf=()):
    """Max pairwise cosine of node texts: raw token counts (the expectation of FN-Memory's bow fake embedding) and word
    TF-IDF. Pure stdlib; the exact bow (numpy) audit runs in pacta-core test_protocol_graph_sync.py. exempt_tfidf: index pairs left
    out of the TF-IDF maximum (reported separately by the caller)."""
    import collections
    import math
    toks = [_graph_tokens(t) for t in texts]
    counts = [collections.Counter(t) for t in toks]
    n = len(toks)
    df = collections.Counter(w for t in toks for w in set(t))
    idf = {w: math.log((1 + n) / (1 + c)) + 1.0 for w, c in df.items()}
    tfidf = [{w: c * idf[w] for w, c in cc.items()} for cc in counts]
    best = {}
    for name, vecs in (("count", counts), ("tfidf", tfidf)):
        top = (0.0, None, None)
        for i in range(n):
            for j in range(i + 1, n):
                c = _graph_cos(vecs[i], vecs[j])
                if name == "tfidf" and (i, j) in exempt_tfidf:
                    if c > best.get(("exempt",), (0.0,))[0]:
                        best[("exempt",)] = (c, i, j)
                    continue
                if c > top[0]:
                    top = (c, i, j)
        best[name] = top
    return best


def repro_ok(e):
    """A record's cast / eth_call reproduction is complete and self-consistent: selector = keccak(signature), one 0x-hex string per
    argument, calldata = selector + the 32-byte argument words (a storage read has no signature and a 32-byte slot)."""
    if e["check_type"] == "eth_call":
        sig, args, cd = e.get("call_signature"), e.get("call_args"), e.get("repro_calldata")
        arity = 0 if not sig or sig.endswith("()") else sig.count(",") + 1
        return (bool(sig) and "0x" + keccak(sig.encode()).hex()[:8] == e["selector_or_slot"] and isinstance(args, list) and len(args) == arity
                and all(isinstance(a, str) and re.fullmatch(r"0x[0-9a-fA-F]{1,64}", a) for a in args)
                and cd == e["selector_or_slot"] + "".join(a[2:].lower().rjust(64, "0") for a in args))
    return e.get("call_signature") is None and re.fullmatch(r"0x[0-9a-f]{64}", e["selector_or_slot"]) is not None


def scrub_secret(text, secret):
    """Remove a secret (raw and JSON-escaped) from the COMPLETE text. Callers truncate only the scrubbed result, so a secret
    straddling a truncation boundary can never leave a fragment behind."""
    text = str(text)
    if secret:
        for form in {secret, json.dumps(secret)[1:-1]}:
            if form:
                text = text.replace(form, "<token>")
    return text


class _VerifyMcp:
    """Minimal outbound MCP (streamable HTTP) client for --verify-memory-centre (read-only memory_relation_list / memory_inspect).
    Requests are paced (min_interval_s; PACTA_VERIFY_MCP_MIN_INTERVAL_S, default 1.02 s over HTTP so a 20-token / 1-per-second
    per-agent bucket never runs dry, 0 in process) and an HTTP 429 waits Retry-After (at least 1.1 s) and retries up to 8 attempts.
    The bearer never appears in an error message."""

    def __init__(self, url, bearer, opener=None, min_interval_s=None, sleep=None, clock=None):
        import urllib.request
        self.url, self._bearer, self.session, self._id = url, bearer, None, 0
        self.opener = opener or urllib.request.build_opener()
        if min_interval_s is None:
            min_interval_s = float(os.environ.get("PACTA_VERIFY_MCP_MIN_INTERVAL_S", "0.0" if url.startswith("inproc://") else "1.02"))
        self.min_interval_s = float(min_interval_s)
        import time as _time
        self._sleep, self._clock, self._last = sleep or _time.sleep, clock or _time.monotonic, None
        self.posts = self.retries_429 = 0

    def _scrub(self, text):
        return scrub_secret(text, self._bearer)

    def _post(self, body, notify=False):
        import urllib.error
        import urllib.request
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "Authorization": "Bearer " + self._bearer}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        for attempt in range(8):
            if self._last is not None and self.min_interval_s > 0:
                wait = self._last + self.min_interval_s - self._clock()
                if wait > 0:
                    self._sleep(wait)
            self._last = self._clock()
            self.posts += 1
            req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers, method="POST")
            try:
                with self.opener.open(req, timeout=20) as r:
                    self.session = r.headers.get("Mcp-Session-Id") or self.session
                    raw = r.read().decode("utf-8", "replace")
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 7:
                    self.retries_429 += 1
                    try:
                        ra = float((e.headers.get("Retry-After") if e.headers else None) or 1.1)
                    except ValueError:
                        ra = 1.1
                    self._sleep(max(1.1, ra))
                    continue
                raise RuntimeError(self._scrub(f"HTTP {e.code} from the memory centre")) from None
            except urllib.error.URLError as e:
                raise RuntimeError(self._scrub(f"memory centre unreachable: {type(getattr(e, 'reason', e)).__name__}")) from None
        if notify:
            return None
        if raw.lstrip().startswith(("event:", "data:")):
            msgs = [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith("data:") and line[5:].strip()]
            return next((m for m in msgs if m.get("id") == body.get("id")), msgs[-1] if msgs else {})
        return json.loads(raw) if raw.strip() else {}

    def call(self, name, args):
        if self._id == 0:
            self._id = 1
            self._post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "pacta-verify-site", "version": "1"}}})
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, notify=True)
        self._id += 1
        msg = self._post({"jsonrpc": "2.0", "id": self._id, "method": "tools/call", "params": {"name": name, "arguments": args}})
        res = msg.get("result") or {}
        if msg.get("error") or res.get("isError"):
            raise RuntimeError(self._scrub(f"{name}: {json.dumps(msg.get('error') or res)}")[:220])    # scrub the whole text, then truncate
        if isinstance(res.get("structuredContent"), dict):
            return res["structuredContent"]
        return json.loads((res.get("content") or [{}])[0].get("text") or "{}")


def live_graph_snapshot(url, bearer, owner, node_ids=(), opener=None):
    """ONE MCP session (and, for inproc://<state dir>, ONE in-process FN-Memory runtime: tools/fn_memory_inproc.py, needs
    PACTA_FN_MEMORY_CHECKOUT / PACTA_FN_MEMORY_PYDEPS and a centre not open in another process) reads every active relation
    the token can see (paged memory_relation_list) and memory_inspect {"id"} for every node id (read-only).
    -> ({(relation, source, target): [rows]}, rows, {node_id: inspect record})"""
    centre = None
    if url.startswith("inproc://"):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import fn_memory_inproc
        centre = fn_memory_inproc.InProcFnMemoryCentre.attach(url[len("inproc://"):]).start()
        mcp = _VerifyMcp(centre.url, bearer, opener=centre.opener())
    else:
        mcp = _VerifyMcp(url, bearer, opener=opener)
    rows, after, inspected = [], None, {}
    try:
        for _ in range(600):                      # <= 60,000 rows; the per-centre cap is 50,000
            args = {"limit": 100}
            if after:
                args["after"] = after
            page = mcp.call("memory_relation_list", args)
            rows.extend(page.get("relations") or [])
            after = page.get("next_after")
            if not after:
                break
        for nid in node_ids:
            res = mcp.call("memory_inspect", {"id": nid})
            inspected[nid] = res if isinstance(res, dict) else {}
    finally:
        if centre is not None:
            centre.close()
    live = {}
    for r in rows:
        if owner and r.get("creator") != owner:
            continue
        src = next((p["id"] for p in r.get("participants") or [] if p.get("side") == "source"), None)
        tgt = next((p["id"] for p in r.get("participants") or [] if p.get("side") == "target"), None)
        live.setdefault((r.get("relation"), src, tgt), []).append(r)
    return live, rows, inspected


def live_graph_relations(url, bearer, owner):
    """Every active relation the token can see on the centre (paged), as {(relation, source, target): [rows]}."""
    live, rows, _ = live_graph_snapshot(url, bearer, owner)
    return live, rows


def node_parity(target_nodes, inspected, owner):
    """Closure Note 3: every manifest node is held by the centre with its id, writer = the owning principal, not superseded,
    not quarantined, and the SHA-256 of its text equals the manifest text's."""
    id_ok = sha_ok = missing = mismatched = 0
    for n in target_nodes:
        res = inspected.get(n["id"]) or {}
        want_sha = hashlib.sha256(n["text"].encode("utf-8")).hexdigest()
        if res.get("found") is not True:
            missing += 1
            continue
        meta_ok = (res.get("id") in (None, n["id"]) and res.get("superseded") is False and res.get("quarantined") is False
                   and res.get("writer") == owner)
        got_text = res.get("text")
        got_sha = hashlib.sha256(got_text.encode("utf-8")).hexdigest() if isinstance(got_text, str) else None
        if meta_ok:
            id_ok += 1
        if meta_ok and got_sha == want_sha:
            sha_ok += 1
        else:
            mismatched += 1
    return {"id_ok": id_ok, "sha_ok": sha_ok, "missing": missing, "mismatched": mismatched, "total": len(target_nodes)}


def _memory_bearer(env_file):
    bearer = os.environ.get("PACTA_VERIFY_MEMORY_TOKEN") or os.environ.get("SN_MEMORY_TOKEN")
    if env_file:
        for line in open(env_file, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k.strip() in ("PACTA_VERIFY_MEMORY_TOKEN", "SN_MEMORY_TOKEN") and v.strip():
                bearer = v.strip().strip('"').strip("'")
    return bearer


def graph_manifest_checks(args):
    """Offline (always): manifest parity / structure / FN-Memory scrubber / distinctiveness. Optional: sync receipt and live centre."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import fn_memory_scrub as SCRUB
    import graph_manifest as GM
    path = os.path.join(DOCS, "api", "v1", "graph-manifest.json")
    if not os.path.exists(path):
        check("graph-manifest.json exists (pacta.graph_manifest.v1)", False, "missing")
        return
    raw = read("docs/api/v1/graph-manifest.json")
    m = json.loads(raw)
    prot = json.loads(read("docs/api/v1/protocols.json"))["protocols"]
    slugs = sorted(p["slug"] for p in prot)
    rebuilt = GM.render(GM.build(ROOT))
    check("graph-manifest.json is the byte-identical deterministic build of protocols / index / rpc-pinned / graph_dependencies / "
          "graph_controller_facts (+ merged bounties/submissions): no wall clock",
          raw == rebuilt and m.get("schema") == GM.SCHEMA and m.get("generated_at") == json.loads(read("docs/api/v1/index.json"))["generated_at"],
          f"schema {m.get('schema')}, {len(raw)} bytes")
    nodes, edges = m.get("nodes") or [], m.get("edges") or []
    ids = [n["id"] for n in nodes]
    proto_nodes = sorted(i[len("pacta-proto-"):] for i in ids if i.startswith("pacta-proto-"))
    by_rel = {r: sum(1 for e in edges if e["relation"] == r) for r in GRAPH_RELATIONS}
    surfaces = [s for p in prot for s in p.get("surfaces") or []]
    n_pd = sum(1 for s in surfaces if s.get("classification") == "parameter_delta")
    n_bounty = len((m.get("sources") or {}).get("bounty_submissions") or [])
    n_att = sum(len(p.get("sprints") or []) for p in prot)
    gov = {e["participants"][0]["id"] for e in edges if e["relation"] == "governed_by_controller"}
    ctrl_ids = [i for i in ids if i.startswith("pacta-ctrl-")]
    check(f"graph manifest: {X['protocols']} protocols (1:1 slug parity with protocols.json), 4 durable relation types only, "
          f"every protocol governed_by_controller, {X['sprints']} pacta-eas-sprint-* nodes, attested / gap edge counts match the data, "
          "owning principal pacta@dri.network/gemini",
          m.get("protocols") == slugs == proto_nodes and len(slugs) == X["protocols"] and m["counts"]["protocols"] == len(slugs)
          and sorted(m.get("relation_types") or []) == sorted(GRAPH_RELATIONS) and all(by_rel[r] > 0 for r in GRAPH_RELATIONS)
          and {e["relation"] for e in edges} <= set(GRAPH_RELATIONS)
          and gov == {f"pacta-proto-{s}" for s in slugs}
          and sum(1 for i in ids if i.startswith("pacta-eas-sprint-")) == X["sprints"]
          and by_rel["attested_by_base_eas"] == n_att and by_rel["exhibits_control_plane_gap"] == n_pd + n_bounty
          and len(set(ids)) == len(ids) and len(set(ctrl_ids)) == len(ctrl_ids)
          and all(i.startswith(("pacta-proto-", "pacta-ctrl-", "pacta-gap-", "pacta-eas-sprint-")) for i in ids)
          and m.get("owning_principal") == "pacta@dri.network/gemini" and m.get("source_agent") == "pacta@dri.network",
          f"{len(nodes)} nodes {m['counts'].get('nodes_by_kind')}, {len(edges)} edges {by_rel}")
    bad = []
    for e in edges:
        ev = canonical_bytes = SCRUB.canonical(e["evidence"])
        if e["edge_key"] != f"{e['relation']}:{e['participants'][0]['id']}->{e['participants'][1]['id']}" or e["direction"] != "directed":
            bad.append(e["edge_key"] + ": key / direction")
        if [p["side"] for p in e["participants"]] != ["source", "target"] or any(p["id"] not in ids for p in e["participants"]):
            bad.append(e["edge_key"] + ": participants")
        if e["content_hash"] != GM.content_hash(e) or e["observed_at"] != m["observed_at"]:
            bad.append(e["edge_key"] + ": content_hash / observed_at")
        if len(canonical_bytes) > 4096 or re.search(r"0x[0-9a-fA-F]{40}", ev.decode()):
            bad.append(e["edge_key"] + ": evidence size / 0x hex")
        if re.search(r'"[^"]*(?:token|secret|key|password|passwd|pwd)[^"]*":', ev.decode(), re.I):
            bad.append(e["edge_key"] + ": credential-shaped evidence key")
    check("graph edges: edge_key = relation:source->target, directed source/target participants that exist, content_hash = sha256(canonical "
          "{relation, direction, participants, evidence}), observed_at = index.json generated_at, evidence <= 4096 canonical bytes, "
          "0x-free 40/64-hex, no token/secret/key/password keys; manifest_sha256 valid; no ephemeral labels or analytics-/forum-/pacta-intent- ids",
          not bad and m.get("manifest_sha256") == GM.manifest_sha256(m) and m["counts"]["max_evidence_bytes"] <= 4096
          and not any(e["relation"] in GRAPH_EPHEMERAL for e in edges) and not any(i.startswith(GRAPH_EPHEMERAL_PREFIXES) for i in ids),
          f"bad {bad[:4]}; max evidence {m['counts'].get('max_evidence_bytes')} B")
    hits = [n["id"] for n in nodes if SCRUB.looks_like_secret(n["text"])]
    hits += [e["edge_key"] for e in edges if SCRUB.looks_like_secret(SCRUB.relation_payload_text(
        e["relation"], e["direction"], e["participants"], e["observed_at"], e["evidence"]))]
    long0x = [n["id"] for n in nodes if re.search(r"0x[0-9a-fA-F]{9,}", n["text"])]
    check(f"FN-Memory {SCRUB.FN_MEMORY_COMMIT[:8]} pre-write scrubber (mcp_server.py looks_like_secret + custom_relations.py canonical payload): "
          "0 hits across every node text and every relation payload; node text abbreviates 0x values (0xABCD..1234)",
          not hits and not long0x, f"{len(nodes)} texts + {len(edges)} payloads; hits {hits[:4]}; unabbreviated {long0x[:4]}")
    u4 = json.loads(read("tools/graph_u4_baseline.json"))
    base_ids = set(u4["nodes"])
    mb = u4.get("minted_before") or {"sprint": None, "nodes": []}
    minted_before = set(mb["nodes"])
    minted_texts = json.loads(read("tools/graph_minted.json"))["nodes"]
    text_of = {n["id"]: n["text"] for n in nodes}
    mb_ok = (not minted_before or (mb["sprint"] == EXPECT["sprints"] and base_ids <= minted_before <= set(ids)
                                   and all(minted_texts.get(nid) == text_of[nid] for nid in minted_before)))
    held = base_ids | minted_before
    mb_note = f" or two nodes minted before Sprint {mb['sprint']}" if minted_before else ""
    inb = [nid in held for nid in ids]
    old = {(i, j) for i in range(len(ids)) for j in range(i + 1, len(ids)) if inb[i] and inb[j]}
    best = graph_distinctiveness([n["text"] for n in nodes], exempt_tfidf=old)
    ex = [v for k, v in best.items() if isinstance(k, tuple)]
    best = {k: v for k, v in best.items() if not isinstance(k, tuple)}
    worst = {k: (round(v[0], 3), ids[v[1]] if v[1] is not None else None, ids[v[2]] if v[2] is not None else None) for k, v in best.items()}
    top_old = max(ex) if ex else (0.0, None, None)
    check(f"graph node texts are distinct (U4): max pairwise token-count (bow expectation) and TF-IDF cosine < {GRAPH_TAU} "
          f"(TF-IDF pairs of two pre-Sprint-24 minted nodes{mb_note} < {GRAPH_TFIDF_BASELINE_CEILING}, reported)",
          all(v[0] < GRAPH_TAU for v in best.values()) and top_old[0] < GRAPH_TFIDF_BASELINE_CEILING and len(base_ids) == 283
          and base_ids <= set(ids) and mb_ok,
          f"{worst}; baseline max {round(top_old[0], 4)} {ids[top_old[1]] if top_old[1] is not None else None}~"
          f"{ids[top_old[2]] if top_old[2] is not None else None}")
    facts = json.loads(read("tools/graph_controller_facts.json"))
    moved = json.loads(json.dumps(facts))
    for f in moved["contracts"].values():          # every mutable control-plane fact changes (threshold 4 -> 3, delays, owners, code)
        if f.get("safe_threshold"):
            f["safe_threshold"] = max(1, f["safe_threshold"] - 1)
            f["safe_owner_hex"] = sorted(f.get("safe_owner_hex") or [])[1:]
            f["safe_owners"] = len(f["safe_owner_hex"])
            f["safe_nonce"] = (f.get("safe_nonce") or 0) + 1
        if f.get("timelock_min_delay") is not None:
            f["timelock_min_delay"] += 3600
        if f.get("code_keccak_hex"):
            f["code_keccak_hex"] = "0" * 64
    base_t = GM.build(ROOT, use_minted=False)           # the pure template on the real data (perturbed builds are compared to it)
    alt = GM.build(ROOT, controller_facts=moved, use_minted=False)
    texts = {n["id"]: n["text"] for n in base_t["nodes"]}
    alt_hash = {e["edge_key"]: e["content_hash"] for e in alt["edges"]}
    observed = [e for e in edges if e["relation"] == "governed_by_controller" and e["evidence"].get("observed_controller")]
    changed_text = [n["id"] for n in alt["nodes"] if texts.get(n["id"]) != n["text"]]
    check("pacta-ctrl-* node text is immutable identity: perturbing every mutable controller fact (Safe threshold / owners / "
          "nonce, timelock delay, code hash) rewrites 0 node texts and changes the content_hash of every governed_by_controller edge "
          "that carries observed_controller evidence (updated in place, never a node rewrite)",
          not changed_text and observed and all(alt_hash.get(e["edge_key"]) != e["content_hash"] for e in observed)
          and [n["id"] for n in alt["nodes"]] == [n["id"] for n in base_t["nodes"]],
          f"{len(changed_text)} node texts changed {changed_text[:3]}; {len(observed)} edges with observed_controller evidence")
    prot_doc = json.loads(read("docs/api/v1/protocols.json"))
    flip = {"aligned_baseline": "protective_delta", "protective_delta": "aligned_baseline", "parameter_delta": "protective_delta",
            "rpc_observed": "aligned_baseline", "mixed": "aligned_baseline"}
    tiers = ["aligned", "parameter_delta", "rpc_observed"]
    moved_p = json.loads(json.dumps(prot_doc))
    for q in moved_p["protocols"]:                  # every changing protocol fact moves (an rpc_observed <-> EAS conversion and more)
        q["badge"] = {**(q.get("badge") or {}), "tier": tiers[(tiers.index((q.get("badge") or {}).get("tier", "aligned")) + 1) % 3]}
        q["easAttested"] = not q.get("easAttested")
        q["evidenceBasis"] = "eas_attested" if q.get("evidenceBasis") == "rpc_observed" else "rpc_observed"
        q["classification"] = flip.get(q.get("classification"), "aligned_baseline")
        q["documentationComparison"] = "not_assessed" if q.get("documentationComparison") == "compared" else "compared"
        q["sprints"] = sorted(set(q.get("sprints") or []) | {1})
        q["baseEasUids"] = sorted(set(q.get("baseEasUids") or []) | {"0x" + "ab" * 32})
        q["controllerAddress"] = None if q.get("controllerAddress") else q["primaryContract"]
        q["controllerKind"] = None if q.get("controllerKind") else "timelock"
        q["targetLabel"] = (q.get("targetLabel") or "") + " (relabelled)"
        for su in q.get("surfaces") or []:
            su["classification"] = flip.get(su.get("classification"), "aligned_baseline")
            su["sprint"] = (su.get("sprint") or 0) + 100
            su["baseEasUid"] = "0x" + "cd" * 32
    alt_p = GM.build(ROOT, protocols_override=moved_p, use_minted=False)
    proto_text = {n["id"]: n["text"] for n in alt_p["nodes"] if n["id"].startswith("pacta-proto-")}
    changed_p = [i for i in ids if i.startswith("pacta-proto-") and proto_text.get(i) != texts[i]]
    n_proto = sum(1 for i in ids if i.startswith("pacta-proto-"))
    check(f"pacta-proto-* node text is immutable identity (name, slug, category, chain, assets, abbreviated primary contract): perturbing every "
          "changing protocol fact of every protocol (badge tier, sprints, Base EAS UIDs, easAttested, evidenceBasis rpc_observed <-> eas_attested, "
          "classification, surface classification / sprint / UID, controller address / kind, documentationComparison, targetLabel) rewrites "
          f"0 of {n_proto} protocol node texts",
          not changed_p and n_proto == len(slugs) and len(proto_text) == n_proto,
          f"{len(changed_p)}/{n_proto} protocol texts changed {changed_p[:3]}")
    minted = json.loads(read("tools/graph_minted.json"))
    m_nodes = {n["id"]: n["text"] for n in nodes}
    lost = sorted(set(minted["nodes"]) - set(m_nodes)) + sorted(set(minted["edges"]) - {e["edge_key"] for e in edges})
    rewritten = sorted(k for k, t in minted["nodes"].items() if k in m_nodes and m_nodes[k] != t)
    check("monotonic graph (tools/graph_minted.json): every node and edge ever published is still in the manifest and every published "
          "anchor text is byte-identical (an upgrade only adds nodes / edges or updates edge evidence in place; relations are never removed)",
          not lost and not rewritten and len(minted["nodes"]) >= 200 and len(minted["edges"]) >= 179,
          f"{len(minted['nodes'])} minted nodes, {len(minted['edges'])} minted edges; lost {lost[:4]}; rewritten {rewritten[:4]}")
    check("sitemap.xml lists /api/v1/graph-manifest.json", "/api/v1/graph-manifest.json</loc>" in read("docs/sitemap.xml"))
    # The live checks compare against target_m: the working-tree manifest, or --manifest PATH (e.g. an earlier published
    # manifest, to verify a backfill of it from a later checkout). A supplied manifest must itself be a valid graph manifest.
    target_m = m
    if getattr(args, "manifest", None):
        try:
            with open(args.manifest, encoding="utf-8") as fh:
                target_m = json.load(fh)
            t_edges = target_m.get("edges") or []
            valid = (target_m.get("schema") == GM.SCHEMA and target_m.get("manifest_sha256") == GM.manifest_sha256(target_m)
                     and all(e.get("content_hash") == GM.content_hash(e) for e in t_edges)
                     and not any(SCRUB.looks_like_secret(n["text"]) for n in target_m.get("nodes") or [])
                     and not any(SCRUB.looks_like_secret(SCRUB.relation_payload_text(e["relation"], e["direction"], e["participants"],
                                                                                    e["observed_at"], e["evidence"])) for e in t_edges)
                     and target_m.get("owning_principal") == "pacta@dri.network/gemini")
            detail = (f"{os.path.basename(args.manifest)}: manifest_sha256 {str(target_m.get('manifest_sha256'))[:12]}, "
                      f"{len(target_m.get('nodes') or [])} nodes, {len(t_edges)} edges, {(target_m.get('counts') or {}).get('protocols')} protocols")
        except (OSError, ValueError, KeyError, TypeError) as e:
            target_m, valid, detail = None, False, f"unreadable manifest: {type(e).__name__}"
        check("--manifest: the target manifest is a valid pacta.graph_manifest.v1 (manifest_sha256, every edge content_hash, 0 FN-Memory "
              "scrubber hits, owning principal pacta@dri.network/gemini)", valid, detail)
        if not valid:
            target_m = None
    t_nodes = (target_m or {}).get("nodes") or []
    t_edges = (target_m or {}).get("edges") or []
    t_by_rel = {r: sum(1 for e in t_edges if e["relation"] == r) for r in GRAPH_RELATIONS}
    t_protocols = ((target_m or {}).get("counts") or {}).get("protocols")
    if args.verify_sync_receipt:
        try:
            rc = json.load(open(args.verify_sync_receipt, encoding="utf-8"))
            ok = (target_m is not None and rc.get("status") == "SYNCED" and rc.get("writeEnabled") is True
                  and rc.get("protocols_in_graph") == t_protocols and rc.get("protocols_indexed") == t_protocols
                  and rc.get("edges_synced") == len(t_edges) and rc.get("manifest_sha256") == target_m["manifest_sha256"]
                  and rc.get("failed_writes") == 0)
            detail = (f"status {rc.get('status')}, writeEnabled {rc.get('writeEnabled')}, protocols {rc.get('protocols_in_graph')}/"
                      f"{rc.get('protocols_indexed')} of {t_protocols}, edges_synced {rc.get('edges_synced')}/{len(t_edges)}, manifest "
                      f"{str(rc.get('manifest_sha256'))[:12]}, failed_writes {rc.get('failed_writes')}")
        except (OSError, ValueError) as e:
            ok, detail = False, f"unreadable receipt: {type(e).__name__}"
        check(f"--verify-sync-receipt: status SYNCED, writeEnabled true, protocols_in_graph = the target manifest's {t_protocols}, "
              "edges_synced = its edge count (live-verified), manifest_sha256 = the target manifest, failed_writes 0", ok, detail)
    if args.verify_memory_centre:
        names = ("--verify-memory-centre: live active relations by the 4 structural labels (creator = owning principal) equal the manifest "
                 "label counts AND the exact (relation, source_id, target_id) edge set; no duplicates",
                 "--verify-memory-centre: the canonical content_hash recomputed over every live edge (relation, direction, participants, "
                 "evidence) equals the manifest content_hash, and every live evidence is canonically identical: 100%",
                 "--verify-memory-centre: live node ids and text SHA-256 hashes held by the centre (writer = owning principal, not superseded, "
                 "not quarantined) equal the manifest: 100%")
        bearer = _memory_bearer(args.memory_env_file)
        if target_m is None or not bearer:
            why = "no valid target manifest" if target_m is None else "no token (SN_MEMORY_TOKEN / PACTA_VERIFY_MEMORY_TOKEN / --memory-env-file)"
            for nm in names:
                check(nm, False, why)
            return
        try:
            live, rows, inspected = live_graph_snapshot(args.verify_memory_centre, bearer, target_m["owning_principal"], [n["id"] for n in t_nodes])
        except Exception as e:                    # report, never raise (a closed centre is a failed check, not a crash)
            why = f"{type(e).__name__}: {scrub_secret(str(e), bearer)[:160]}"           # scrub the whole message, then truncate
            for nm in names:
                check(nm, False, why)
            return
        want = {(e["relation"], e["participants"][0]["id"], e["participants"][1]["id"]) for e in t_edges}
        got = {k for k in live if k[0] in GRAPH_RELATIONS}
        live_counts = {r: sum(len(v) for k, v in live.items() if k[0] == r) for r in GRAPH_RELATIONS}
        dupes = sorted(k for k, v in live.items() if k[0] in GRAPH_RELATIONS and len(v) > 1)
        check(names[0], live_counts == t_by_rel and got == want and not dupes,
              f"live {live_counts} vs manifest {t_by_rel}; missing {len(want - got)}, extra {len(got - want)}, duplicates {len(dupes)}; "
              f"{len(rows)} rows paged")
        hash_ok = ev_ok = 0
        for e in t_edges:
            for row in live.get((e["relation"], e["participants"][0]["id"], e["participants"][1]["id"])) or []:
                rebuilt = {"relation": row.get("relation"), "direction": row.get("direction"),
                           "participants": [{"id": p.get("id"), "role": p.get("role"), "side": p.get("side")} for p in row.get("participants") or []],
                           "evidence": row.get("evidence") or {}}
                hash_ok += GM.content_hash(rebuilt) == e["content_hash"]
                ev_ok += SCRUB.canonical(row.get("evidence") or {}) == SCRUB.canonical(e["evidence"])
        check(names[1], hash_ok == ev_ok == len(t_edges) and got == want and not dupes,
              f"content_hash {hash_ok}/{len(t_edges)}, evidence {ev_ok}/{len(t_edges)}")
        np_ = node_parity(t_nodes, inspected, target_m["owning_principal"])
        check(names[2], np_["id_ok"] == np_["sha_ok"] == np_["total"] and np_["missing"] == 0 and np_["mismatched"] == 0,
              f"node_ids {np_['id_ok']}/{np_['total']}, text_sha256 {np_['sha_ok']}/{np_['total']}, missing {np_['missing']}, "
              f"mismatched {np_['mismatched']}")


def parse_args(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Offline checks for the Pacta static site (+ optional graph sync / live centre parity)")
    ap.add_argument("--verify-sync-receipt", metavar="PATH", help="graph-sync-receipt.json: SYNCED, writeEnabled, every target-manifest "
                    "protocol in the graph, edges_synced = its edges, manifest_sha256 matches, failed_writes == 0")
    ap.add_argument("--verify-memory-centre", metavar="MCP_URL", help="live sn-memory MCP URL, or inproc://<state dir> (socketless in-process "
                    "FN-Memory runtime, tools/fn_memory_inproc.py): label-count + edge parity + 100%% content_hash / evidence equality "
                    "+ node id / text SHA-256 parity (memory_inspect) with the target manifest (token from SN_MEMORY_TOKEN / PACTA_VERIFY_MEMORY_TOKEN or --memory-env-file)")
    ap.add_argument("--memory-env-file", metavar="PATH", help="env file with SN_MEMORY_TOKEN (never printed)")
    ap.add_argument("--manifest", metavar="PATH", help="target graph manifest for --verify-sync-receipt / --verify-memory-centre (default: "
                    "the working-tree docs/api/v1/graph-manifest.json); validated before use")
    return ap.parse_args(argv)


def workflow_run_blocks(text):
    """The `run: |` scripts of a workflow, in order (enough YAML for verify-bounty-pr.yml; no PyYAML dependency)."""
    lines, out, i = text.split("\n"), [], 0
    while i < len(lines):
        m = re.match(r"^(\s*)run: \|\s*$", lines[i])
        if not m:
            i += 1
            continue
        ind, body, i = len(m.group(1)), [], i + 1
        while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > ind):
            body.append(lines[i])
            i += 1
        cut = min((len(b) - len(b.lstrip()) for b in body if b.strip()), default=0)
        out.append("\n".join(b[cut:] for b in body).strip("\n") + "\n")
    return out


def bounty_gate_simulation():
    """Run the two run: scripts of .github/workflows/verify-bounty-pr.yml against throw-away git repos built from this checkout:
    a base commit (tools/, protocols.json, bounties/ + one already merged Wave 2 claim) and one PR commit per case.
    -> {case: (gate exit, validate exit or None)}. Nothing outside the scratch directory is touched; no network."""
    import tempfile
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import verify_bounty_submission as VBS2
    blocks = workflow_run_blocks(read(".github/workflows/verify-bounty-pr.yml"))
    if len(blocks) != 2 or not shutil.which("git") or not shutil.which("bash"):
        return {"setup": ("workflow / git / bash missing", None, "")}
    first = next(x for x in json.load(open(os.path.join(DOCS, "api", "v1", "protocols.json")))["protocols"] if x["chain"] == "ethereum")
    good = VBS2.valid_fixture_wave2("protocol_mismatch", first)
    merged = {**good, "slug": "merged-claim", "contractAddress": "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb",
              "castCommands": [c.replace(good["contractAddress"], "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb") for c in good["castCommands"]],
              "mcpProof": {"tool": "pacta_lookup_protocol", "arguments": {"query": "merged-claim"}, "result": {"totalMatches": 0, "query": "merged-claim"}}}
    env0 = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env0.update(GIT_AUTHOR_NAME="sim", GIT_AUTHOR_EMAIL="sim@example.invalid", GIT_COMMITTER_NAME="sim", GIT_COMMITTER_EMAIL="sim@example.invalid",
                GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1")
    res = {}
    with tempfile.TemporaryDirectory(prefix="bounty-gate-") as tmp:
        repo = os.path.join(tmp, "repo")
        g = lambda *a: subprocess.run(["git", "-C", repo, *a], env=env0, capture_output=True, text=True, timeout=60)
        os.makedirs(repo)
        g("init", "-q", "-b", "main")
        shutil.copytree(os.path.join(ROOT, "tools"), os.path.join(repo, "tools"), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(os.path.join(ROOT, "bounties"), os.path.join(repo, "bounties"))
        for f_ in glob.glob(os.path.join(repo, "bounties", "wave-2", "*.json")):     # this checkout's merged claims are not part of the cases
            os.remove(f_)
        shutil.copytree(os.path.join(ROOT, ".github"), os.path.join(repo, ".github"))
        shutil.copytree(os.path.join(DOCS, "api", "v1"), os.path.join(repo, "docs", "api", "v1"))
        with open(os.path.join(repo, "bounties", "wave-2", "ethereum-merged-claim.json"), "w") as fh:
            json.dump(merged, fh)
        g("add", "-A")
        g("commit", "-q", "-m", "base")
        base = g("rev-parse", "HEAD").stdout.strip()

        def case(name, files, symlink=None):
            g("checkout", "-q", "-B", "pr-" + name, base)
            for rel, content in files.items():
                path = os.path.join(repo, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as fh:
                    fh.write(content)
            if symlink:
                os.symlink(symlink[1], os.path.join(repo, symlink[0]))
            g("add", "-A")
            g("commit", "-q", "-m", name)
            head_ = g("rev-parse", "HEAD").stdout.strip()
            out_ = os.path.join(tmp, name + ".out")
            open(out_, "w").close()
            rt = os.path.join(tmp, "runner-" + name)
            os.makedirs(rt)
            e = dict(env0, BASE_SHA=base, HEAD_SHA=head_, GITHUB_OUTPUT=out_, RUNNER_TEMP=rt)
            r1 = subprocess.run(["bash", "-e", "-c", blocks[0]], cwd=repo, env=e, capture_output=True, text=True, timeout=120)
            if r1.returncode:
                res[name] = (r1.returncode, None, r1.stdout)
                return
            f_ = dict(l.split("=", 1) for l in open(out_).read().split("\n") if "=" in l).get("file", "")
            r2 = subprocess.run(["bash", "-e", "-c", blocks[1]], cwd=repo, env=dict(e, FILE=f_), capture_output=True, text=True, timeout=300)
            res[name] = (0, r2.returncode, r2.stdout + r2.stderr)
        ok_json = json.dumps(good, indent=2)
        case("valid", {"bounties/wave-2/ethereum-example-lending.json": ok_json})
        case("invalid_tvl", {"bounties/wave-2/ethereum-example-lending.json": json.dumps({**good, "tvlUsd": 1})})
        case("duplicate_of_merged", {"bounties/wave-2/ethereum-example-lending.json": json.dumps({**good, "contractAddress": merged["contractAddress"],
                                                                                                  "castCommands": merged["castCommands"]})})
        case("plus_validator_edit", {"bounties/wave-2/ethereum-example-lending.json": ok_json,
                                     "tools/verify_bounty_submission.py": "import sys\nsys.exit(0)\n"})
        case("validator_only", {"tools/verify_bounty_submission.py": "import sys\nsys.exit(0)\n"})
        case("workflow_edit", {"bounties/wave-2/ethereum-example-lending.json": ok_json, ".github/workflows/verify-bounty-pr.yml": "name: x\n"})
        case("wrong_path", {"bounties/wave-2/polygon-example-lending.json": ok_json})
        case("modify_existing", {"bounties/wave-2/ethereum-merged-claim.json": ok_json})
        case("symlink", {}, symlink=("bounties/wave-2/ethereum-example-lending.json", "../../tools/verify_bounty_submission.py"))
        case("chain_mismatch", {"bounties/wave-2/base-example-lending.json": ok_json})
        case("wave1_fixture", {"bounties/submissions/slot-1-example-vault.json": json.dumps(VBS2.valid_fixture())})
        w3_opt = VBS2.valid_fixture_wave3("optimism")
        w3_poly = VBS2.valid_fixture_wave3("polygon")
        case("wave3_valid", {"bounties/wave-3/optimism-example-lending.json": json.dumps(w3_opt, indent=2)})
        case("wave3_polygon_valid", {"bounties/wave-3/polygon-example-lending.json": json.dumps(w3_poly, indent=2)})
        case("wave3_shallow_memo", {"bounties/wave-3/optimism-example-lending.json": json.dumps({**w3_opt, "executive_risk_memo": "too short"})})
        case("wave3_wrong_chain", {"bounties/wave-3/solana-example-lending.json": json.dumps(w3_opt)})
    return res


def ready_fixture_brief(idx):
    """The Ethena timelock brief rendered from a copy of radar.json with both operations READY (delay elapsed, unexecuted), so
    the live re-check behaviour (READY -> EXECUTED / MIXED / kept) is tested whatever the live chain state is today."""
    rad = json.loads(read("docs/api/v1/radar.json"))
    ts = rad["refreshed_at"]["block_timestamp"]
    for it in rad["items"]:
        if it["brief"].endswith("ethena-ops-0x0ca0-0x1fe5/"):
            it["eta"] = ts - 3600
            for o in it["operations"]:
                o.update(pending=True, ready=True, done=False, eta=ts - 3600)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import build_site as BSR
    slug = "ethena-ops-0x0ca0-0x1fe5"
    return BSR.brief_page(slug, BSR.BRIEFS[slug], idx, rad)


def main(argv=None):
    cli = parse_args(argv)
    base = re.search(r'^BASE_URL = "([^"]+)"', read("tools/build_site.py"), re.M).group(1)
    raw = read("docs/index.html", "rb")
    page = raw.decode()
    hpos, bpos = raw.find(b"<head>"), raw.find(b"<body")
    # v4: + Inter preload (V4) and a light / dark theme-color pair (U2): the budget moves from 2500 to 3000 bytes
    check("<body> starts before byte 3000", 0 <= bpos < 3000, f"<body> at byte {bpos}")
    tw_end = raw.find(b">", raw.find(b'name="twitter:image"')) + 1
    check("OG + X card tags inside the first 1.2 KB of <head>", 0 < tw_end - hpos <= 1200, f"twitter:image ends {tw_end - hpos} bytes into <head>")
    check("zero data:image/ blobs in index.html", b"data:image/" not in raw)
    req = ['<meta charset="utf-8">', 'name="viewport"', "<title>", 'name="description"', f'<link rel="canonical" href="{base}/">',
           'property="og:type"', 'property="og:site_name"', 'property="og:title"', 'property="og:description"', f'property="og:url" content="{base}/"',
           f'property="og:image" content="{base}/og-preview.png"', 'property="og:image:width" content="1200"', 'property="og:image:height" content="628"',
           'name="twitter:card" content="summary_large_image"', 'name="twitter:title"', 'name="twitter:description"',
           '<meta name="theme-color" content="#f7f7f5" media="(prefers-color-scheme: light)">', '<meta name="theme-color" content="#0a0b0d" media="(prefers-color-scheme: dark)">',
           'rel="preload" href="fonts/inter-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin',
           f'name="twitter:image" content="{base}/og-preview.png"', 'href="styles.css?v=', 'href="favicon.svg"', 'href="favicon.png"']
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
    # M4 / M5 (v4): one tier family, byte-identical pricing cards on / and /request/ (only the relative link prefix differs)
    offer = ("Free scorecards, API &amp; MCP", "$0", "Instant Contract &amp; Safe Deep-Scan", "$19", "Live Timelock &amp; Signer Webhook", "$49",
             "24h Mainnet Control-Plane Seal", "$99", "Multi-contract dossiers", "$2,500–$5,000", "Continuous Control-Plane Monitoring", "$1,500 / month",
             "Community queue", "API SLA", "data-enterprise-strip")
    def plans_of(t):
        a = t.find('<div class="plans" data-pricing>')
        b = t.find('<p class="note">', a)
        return t[a:b] if 0 <= a < b else ""
    plans_h, plans_r = plans_of(page), plans_of(req_page).replace('href="../', 'href="')
    check("homepage #pricing and /request/ carry the same self-serve grid ($0 free / $19 scan / $49 per month webhook / $99 seal) and the enterprise strip "
          "($2,500-$5,000 dossiers / $1,500 per month Continuous Control-Plane Monitoring / free queue / API SLA), identical; vulnerabilities routed to Immunefi / Cantina",
          all(t in plans_h for t in offer) and plans_h == plans_r and plans_h.count('data-plan="') == 4
          and all(x in read("docs/protocols/stader-labs-ethx/index.html") for x in ("Immunefi", "Cantina")))
    check("public data stated free and real-time (homepage, llms.txt, README)",
          "free, with live re-check on demand" in page and "Free and real-time" in llms_txt(read) and "Free and real-time" in read("README.md"))   # v4.5 G-P2-1 wording on the pricing card
    radios = re.findall(r'name="tier" value="([\w-]+)"', req_page)
    check("request builder (/request/) offers exactly the pricing tiers in pricing order (community, rapid-500, clearance default, continuous, api_sla); the homepage links there",
          radios == ["community", "rapid-500", "clearance", "continuous", "api_sla"]
          and len(re.findall(r'name="tier" value="[\w-]+" checked', req_page)) == 1 and 'value="clearance" checked' in req_page
          and 'name="tier"' not in page and 'href="request/?tier=clearance" data-tier="clearance"' in page,
          str(radios))
    treasury = json.loads(read("docs/api/v1/index.json"))["onchain_anchoring"]["treasury_admin"]
    shown = set(re.findall(r'data-treasury="(0x[0-9a-fA-F]{40})"', page + req_page)) | set(re.findall(r'class="mono full">(0x[0-9a-fA-F]{40})<', page + req_page))
    check("payment address = index treasury address (EIP-55) everywhere it is shown", shown == {treasury} and eip55_ok(treasury)
          and treasury in read("REMEDIATION_SERVICES.md") and treasury in llms_txt(read) and treasury in read(".github/ISSUE_TEMPLATE/request-scan.yml"),
          f"{sorted(shown)}")
    tmpl = read(".github/ISSUE_TEMPLATE/request-scan.yml")
    opts = re.findall(r'^\s+- "(.+)"$', tmpl.split("id: package_tier", 1)[1].split("validations", 1)[0], re.M)
    js_opts = re.findall(r'"([^"]+)",\s*\n\s*"Pacta [^"]+ request"', read("tools/app.src.js"))
    set_opts = re.findall(r'^\s+- "(.+)"$', tmpl.split("id: settlement_preference", 1)[1].split("validations", 1)[0], re.M) if "id: settlement_preference" in tmpl else []
    js_set = re.findall(r'"(Option [AB]: [^"]+)"', read("tools/app.src.js"))
    check("GitHub dropdown prefill strings match the issue template exactly (5 tracks incl. the $500 Rapid Single-Gap Re-Verification + 2 settlement options)",
          sorted(opts) == sorted(js_opts) and len(opts) == 5 and "Rapid Single-Gap Re-Verification ($500 USDC, 24h SLA)" in opts and sorted(set_opts) == sorted(js_set) and len(set_opts) == 2
          and all(f'id: {k}' in tmpl for k in ("forum_proposal_url", "payment_tx_hash", "settlement_preference")),
          f"template {opts} {set_opts} app.js {js_opts} {js_set}")
    sums_ = {k: (hashlib.sha256(read(p_, "rb")).hexdigest() if os.path.exists(os.path.join(ROOT, p_)) else None)
             for k in X["summaries"] for p_ in glob.glob(os.path.join(ROOT, "audits", f"sprint-{k}", "block-*-summary.md"))[:1] or [f"audits/sprint-{k}/missing"]}
    idx_s = json.loads(read("docs/api/v1/index.json"))
    check(f"audits/ summaries for Sprints {', '.join(sorted(X['summaries'], key=int))} are byte-identical to the attested files (SHA-256), and every index.json "
          "summary_sha256 equals the SHA-256 of its summary_doc", sums_ == X["summaries"] and all(
              e["summary_sha256"] == "0x" + hashlib.sha256(read(e["summary_doc"], "rb")).hexdigest() for e in idx_s["entries"]
              if int(e["sprint"]) >= 15), str(sums_))
    check("attested_not_yet_indexed_sprints is empty (every attested Sprint is indexed)",
          idx_s["onchain_anchoring"]["attestation_coverage"].get("attested_not_yet_indexed_sprints") == []
          and sorted(map(int, idx_s["onchain_anchoring"]["sprint_eas_attestations"])) == sorted({int(e["sprint"]) for e in idx_s["entries"]}))
    appjs = read("tools/app.src.js")              # readable source: every source-text check reads it
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import build_site as BSM
    appjs_min = read("docs/app.js")               # the shipped file: deterministic minification of the source, executed by the harness
    check("docs/app.js is the deterministic minification of tools/app.src.js (comments and indentation removed, line breaks kept); "
          "styles.css / app.js / theme.js are linked with ?v=<sha8> of their exact bytes on every page",
          appjs_min == BSM.minify_js(appjs) and len(appjs_min) < len(appjs)
          and all(f'app.js?v={hashlib.sha256(appjs_min.encode()).hexdigest()[:8]}"' in t and f'styles.css?v={hashlib.sha256(read("docs/styles.css").encode()).hexdigest()[:8]}"' in t
                  and f'theme.js?v={hashlib.sha256(read("docs/theme.js").encode()).hexdigest()[:8]}"' in t for t in (open(p_, encoding="utf-8").read() for p_ in glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)) if "<head>" in t and 'class="topbar"' in t),
          f"{len(appjs_min):,} B minified from {len(appjs):,} B")
    check('radar says "Execution window opens in" (ETA = eligibility)', "Execution window opens in" in appjs and "Executing in" not in appjs)
    _pin_words = " + ".join(BSM.PIN_WORD[ch_] for ch_, _ in BSM.radar_pins(json.loads(read("docs/api/v1/radar.json"))))
    check(f'finality badge says "Scanner-pinned (L1 finalized)" (drawers); the radar pill names every chain it pins ("Scanner-pinned ({_pin_words} finalized)")',
          "Scanner-pinned (L1 finalized)" in appjs and f"data-prov-pill>Scanner-pinned ({_pin_words} finalized)</span>" in page)

    # counts
    idx = json.loads(read("docs/api/v1/index.json"))
    m, entries = idx["summary_metrics"], idx["entries"]
    n, sprints = len(entries), max(e["sprint"] for e in entries)
    check(f"index.json records_indexed == len(entries) == {X['records']}", m["records_indexed"] == n == X["records"], f"{m['records_indexed']} / {n}")
    check(f"index.json sprints_completed == max(sprint) == {X['sprints']}", m["sprints_completed"] == sprints == X["sprints"], f"{m['sprints_completed']} / {sprints}")
    check("classification counts sum to records", m["parameter_deltas"] + m["protective_deltas"] + m["aligned_baselines"] == n
          and all(sum(1 for e in entries if e["classification"] == k) == m[v] for k, v in
                  (("parameter_delta", "parameter_deltas"), ("protective_delta", "protective_deltas"), ("aligned_baseline", "aligned_baselines"))))
    # Batch D3 (receipt/1818): the coverage line names protocols, EAS-attested Sprint records (and their Sprints) and RPC-observed records
    n_pin = len(json.load(open(os.path.join(DOCS, "api", "v1", "rpc-pinned.json")))["entries"])
    # M4 (v4): one noun per number: "N protocols (E Base-EAS attested + O RPC-observed) · C attested checks across B Base EAS batch attestations"
    sc_cards = json.load(open(os.path.join(DOCS, "api", "v1", "scorecards.json")))["protocols"]
    n_eas_p = sum(1 for c in sc_cards if c["easAttested"])
    n_batches = len(idx["onchain_anchoring"]["sprint_eas_attestations"])
    line = (f"{X['protocols']} protocols ({n_eas_p} Base-EAS attested + {X['protocols'] - n_eas_p} RPC-observed) · {n} attested checks across "
            f"{n_batches} Base EAS batch attestations")
    for f in ("docs/index.html", "docs/llms.txt", "README.md"):
        t = read(f)
        nums_s = set(re.findall(r"\b(\d+) Sprints\b", t))
        nums_c = set(re.findall(r"\b(\d+) attested checks across\b", t))
        stale = [s for s in ("Base EAS-Attested Records", "block-pinned control checks", "live docs-vs-chain deltas") if s in t]
        check(f"count parity in {f}", line in t and nums_s <= {str(sprints)} and nums_c <= {str(n)} and not stale,
              f"sprints {sorted(nums_s)} checks {sorted(nums_c)} stale {stale}")
    # M4 contradiction guard (v4.1): every site-wide count phrase on every generated page, agent doc and the README carries the canonical
    # number (RPC-observed / RPC-pinned protocols, Base-EAS attested protocols, attested checks, protocols). Per-protocol drawer counts
    # ("N attested checks · pinned block") and the verbatim closed Wave 1 slot scopes (historic, data-bounty-slots) are not site-wide counts.
    n_rpc_c = X["rpc_protocols"]
    count_rules = [(r"\b(\d[\d,]*) RPC-(?:observed|Observed|pinned)\b", n_rpc_c),
                   (r"\b(\d[\d,]*) Base-EAS[- ]attested\b", X["protocols"] - n_rpc_c),
                   (r"\b(\d[\d,]*) attested checks?\b(?! · pinned block)", n),
                   (r"\b(\d[\d,]*) (?:indexed |published |DeFi |scored )?protocols\b", X["protocols"])]

    def count_contradictions(text):
        text = re.sub(r'<table class="ix" data-bounty-slots>.*?</table>', "", text, flags=re.S)
        text = re.sub(r'<details class="archive-details" id="wave-1-archive".*?</details>\n</article>', "", text, flags=re.S)   # v4.7 W4
        return [(m.group(0), want) for rx, want in count_rules for m in re.finditer(rx, text) if int(m.group(1).replace(",", "")) != want]
    probes = {"999 RPC-Observed": f"{X['protocols']} protocols · 999 RPC-Observed", "7 RPC-observed": "7 RPC-observed protocols",
              "79 Base-EAS attested": "79 Base-EAS attested", "158 attested checks": "158 attested checks across 24",
              "85 protocols": "Search 85 protocols"}
    probe_ok = all([h[0] for h in count_contradictions(t_)] == [k_] for k_, t_ in probes.items()) and not count_contradictions(
        f"{X['protocols']} protocols ({X['protocols'] - n_rpc_c} Base-EAS attested + {n_rpc_c} RPC-observed) · {n} attested checks · 3 attested checks · pinned block #1")
    cc_files = sorted(glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)) + [os.path.join(ROOT, f) for f in ("docs/llms.txt", "docs/llms-full.txt", "docs/SKILL.md", "README.md")]
    cc_bad = [(os.path.relpath(f, ROOT), h) for f in cc_files for h in count_contradictions(open(f, encoding="utf-8").read())]
    check("M4 count-contradiction guard: 0 wrong RPC-observed / Base-EAS attested / attested checks / protocols numbers across every page, llms.txt, "
          "llms-full.txt, SKILL.md and README (self-probe: injected 999 RPC-Observed, 79 Base-EAS, 158 checks, 85 protocols are each caught)",
          probe_ok and not cc_bad, f"probe {probe_ok}; {len(cc_files)} files; contradictions {cc_bad[:4]}")

    rows = len(re.findall(r'<tr class="sc-row(?: sc-m)?"', page))   # v4.7 W1: an 8-row preview, all shown below 640 px
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import build_site as BS
    check(f"homepage #scorecards ships the {len(BS.FLAGSHIP)} flagship protocols statically (every protocol hydrates from /api/v1/scorecards.json: harness)",
          rows == len(BS.FLAGSHIP) == 8 and f'data-sc-explore>Explore all {X["protocols"]} protocol scorecards{BS.ARR}</a>' in page, f"{rows} rows")
    cat_ = f"{X['protocols']} protocols + {X['briefs']} briefs"
    stale_ = {f: sorted(set(re.findall(r"\b(\d+) protocols \+ (\d+) briefs\b", read(f))) - {(str(X["protocols"]), str(X["briefs"]))})
              for f in ("docs/SKILL.md", "docs/llms.txt", "docs/llms-full.txt", "packages/mcp-server/SKILL.md")}
    check(f"agent docs carry the published catalog size ('{cat_}', '{X['eas_protocols']} EAS-attested / {X['rpc_protocols']} RPC-observed'); no stale count",
          all(cat_ in read(f) for f in stale_) and not any(stale_.values())
          and f"({X['eas_protocols']} EAS-attested / {X['rpc_protocols']} RPC-observed)" in read("docs/llms-full.txt"), str(stale_))
    anc = idx["onchain_anchoring"]
    eas = anc["sprint_eas_attestations"]
    uid_ok = all(re.fullmatch(r"0x[0-9a-f]{64}", u) for u in eas.values()) and len(set(eas.values())) == len(eas)
    ne = X["eas_attestations"]
    check(f"{ne} Base EAS sprint attestations (Sprints 1-{ne}); every record carries its sprint's UID", len(eas) == ne and sorted(map(int, eas)) == list(range(1, ne + 1))
          and uid_ok and all(e["base_eas_uid"] == eas[str(e["sprint"])] for e in entries) and f"**{ne} on-chain Base EAS sprint attestations**" in read("README.md"))
    # Sprints 13-16 batch, read back from Base on 2026-11-13 (tx status 1, Attested logs from the attester, schema 0x7ff4..df83,
    # not revoked; Sprint 13/14 block, block hash, record count and summary SHA-256 match this index)
    pinned = {"13": "0x6afd266541ea1643b680ce6ec15d218874356598820987c6b3eaf16342cd075c", "14": "0x8965ae6e51a78132a77eb14c0ac1c6cd1be357d6f261253efff28869478ae5b8",
              "15": "0x967a4935786194575835d5a46e3e39b1d553225deb6a96c7ff4acf52a34dff22", "16": "0x217d213de3cd9ef094670ff69d258af35adf132406caa547f729f487dc9d7e58"}
    check("Sprint 13-16 UIDs + batch tx equal the values verified on Base", all(eas.get(k) == v for k, v in pinned.items())
          and anc.get("eas_multi_attest_sprints_13_16_tx") == "0x11546aac53e3fe57fa6ac9f7e4397f06c58b6803252e099eb9349eca00f2edbf")
    mtx = anc["attestation_coverage"]["eas_multi_attest_txs"]
    check(f"multi-attest txs recorded (Sprints {', '.join(X['multi_attest_txs'])})", re.fullmatch(r"0x[0-9a-f]{64}", anc.get("eas_multi_attest_sprints_13_16_tx", "")) is not None
          and list(mtx) == X["multi_attest_txs"] and mtx["1–12"] == anc["eas_multi_attest_tx"] and mtx["13–16"] == anc["eas_multi_attest_sprints_13_16_tx"]
          and all(re.fullmatch(r"0x[0-9a-f]{64}", t_) for t_ in mtx.values()) and len(set(mtx.values())) == len(mtx), str(mtx))

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
    bad_repro = [e["id"] for e in entries if not repro_ok(e)]
    check("every record has a complete cast reproduction (signature, all args, calldata)", not bad_repro, f"bad: {bad_repro}")

    # assets
    og = read("docs/og-preview.png", "rb")
    soc_bad = {}
    for rel_ in SOCIAL_CARDS:   # X Website cards: 1.91:1, nothing within 96 px of the sides or 120 px of the bottom (X's headline pill)
        try:
            w_, h_, ch_, rows_ = png_rgb(os.path.join(DOCS, rel_))
            bg_ = rows_[0][:ch_]
            side_ = all(r_[:96 * ch_] == bg_ * 96 and r_[-96 * ch_:] == bg_ * 96 for r_ in rows_)
            bottom_ = all(r_ == bg_ * w_ for r_ in rows_[h_ - 120:])
            ink_ = sum(1 for r_ in rows_[:h_ - 120] if r_ != bg_ * w_)
            if not ((w_, h_) == (1200, 628) and side_ and bottom_ and ink_ > 200):
                soc_bad[rel_] = ((w_, h_), side_, bottom_, ink_)
        except Exception as e_:   # noqa: BLE001 - reported as a failed check
            soc_bad[rel_] = str(e_)[:80]
    check("social cards: og-preview.png + cards/x-card-{scorecards,scan19,seal99}-1200x628.png are 1200x628 (1.91:1) PNGs with >= 96 px clear left / right "
          "and >= 120 px clear bottom (pixel-checked: background only; tools/make_og.py)", og[:8] == b"\x89PNG\r\n\x1a\n" and not soc_bad, str(soc_bad))
    fav = read("docs/favicon.png", "rb")
    check("favicon.png is a PNG < 2 KB", fav[:8] == b"\x89PNG\r\n\x1a\n" and len(fav) < 2048, f"{len(fav)} bytes {struct.unpack('>II', fav[16:24])}")
    svg = read("docs/favicon.svg", "rb")
    try:
        ET.fromstring(svg)
        svg_ok = len(svg) < 1024
    except ET.ParseError:
        svg_ok = False
    check("favicon.svg is valid XML < 1 KB", svg_ok, f"{len(svg)} bytes")
    # the official Pacta Bowen-knot logo (2026-11-16): exact SVG, its compact favicon twin, the 512 px raster and every brand slot
    logo = read("docs/logo.svg", "rb")
    check("logo.svg is the official Pacta Bowen-knot logo (1,533 B, sha256 ab8f8780…5cb5da)",
          len(logo) == 1533 and hashlib.sha256(logo).hexdigest() == "ab8f87806925f7b8795f52be32a7847f822e678b5f27b6e02599bfdbb59cb5da",
          f"{len(logo)} bytes")

    def logo_geometry(raw):
        out = []
        for el in ET.fromstring(raw).iter():
            a = {k: v.lower().replace("#000000", "#000").replace("#ffffff", "#fff") for k, v in el.attrib.items() if k not in ("width", "height")}
            if "d" in a:
                a["d"] = re.findall(r"[mhvcz]|-?\d+(?:\.\d+)?", a["d"])
            out.append((el.tag, a))
        return out
    try:
        fav_geo_ok = logo_geometry(svg) == logo_geometry(logo)
    except ET.ParseError:
        fav_geo_ok = False
    check("favicon.svg = logo.svg geometry (4 double-tracked loops, mitered outer diamond, inner diamond, evenodd P; same elements, "
          "coordinates, radii, strokes and fills) in < 1 KB", fav_geo_ok and len(svg) < 1024, f"{len(svg)} bytes")
    l512 = read("docs/logo-512.png", "rb")
    check("logo-512.png is a 512x512 RGBA PNG", l512[:8] == b"\x89PNG\r\n\x1a\n" and l512[12:16] == b"IHDR"
          and struct.unpack(">II", l512[16:24]) == (512, 512) and l512[24:26] == bytes([8, 6]), f"{len(l512)} bytes")
    brand_pages = [p_ for p_ in sorted(glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)) if 'class="brand"' in read(p_)]
    brand_bad = [os.path.relpath(p_, ROOT) for p_ in brand_pages
                 if not re.search(r'<a class="brand" href="[^"]*"><img src="(?:/|(?:\.\./)*)favicon\.svg" alt="" width="24" height="24">PACTA', read(p_))
                 or not re.search(r'<div class="ftr-brand"><a class="brand" href="[^"]*"><img class="ftr-logo" src="(?:/|(?:\.\./)*)favicon\.svg" alt="" width="24" height="24">PACTA</a>', read(p_))]
    css_ = read("docs/styles.css")
    check("logo in every page header and footer (24x24, unclipped); Organization.logo = logo-512.png",
          brand_pages and not brand_bad and ".brand img { display: block; width: 24px; height: 24px; }" in css_ and ".ftr-logo {" in css_
          and f'"logo": "{base}/logo-512.png"' in page, f"{len(brand_pages)} pages; bad {brand_bad[:3]}")
    check("README lockups: the logo above the H1 (README.md: docs/logo.svg; packages/mcp-server/README.md: https://pacta.wtf/logo.svg)",
          read("README.md").startswith('<img src="docs/logo.svg" alt="Pacta" width="56" height="56" align="left">')
          and read("packages/mcp-server/README.md").startswith('<img src="https://pacta.wtf/logo.svg" alt="Pacta" width="48" height="48" align="left">'))

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
        # Codex F3: <lastmod> comes from the pinned data, never the wall clock (a rebuild after 00:00 UTC must be byte-identical)
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        sys.dont_write_bytecode = True
        import build_site as BSF
        lastmods = {e.text for e in sm.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod")}
        want_day = BSF.site_date(idx, json.loads(read("docs/api/v1/radar.json")), json.loads(read("docs/api/v1/rpc-pinned.json")),
                                 json.loads(read("docs/api/v1/onboarding.json")) if os.path.exists(os.path.join(DOCS, "api", "v1", "onboarding.json")) else None)
        wall = [f for f in ("tools/build_site.py", "tools/build_b2a_feeds.py", "tools/build_lookup.py")
                if re.search(r"date\.today\(|datetime\.now\(|datetime\.utcnow\(|time\.time\(|time\.gmtime\(\)|time\.localtime\(", read(f))]
        check("sitemap <lastmod> is deterministic: every entry = the newest pinned-data date (index / radar / rpc-pinned / onboarding), "
              "no wall-clock call in the build scripts (Codex F3)", lastmods == {want_day} and not wall, f"lastmod {sorted(lastmods)} want {want_day}; wall-clock in {wall}")
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
    etas = {str(i["eta"]) for i in radar["items"] if i.get("eta")}         # an executed item has no ETA (isOperationDone): shown as Executed
    shown = set(re.findall(r'data-eta="(\d+)"', page))
    check("executed radar items (eta null) render 'Executed' with isOperationDone, never an ETA",
          all(f'isOperationDone = true at block #{radar["refreshed_at"]["block_number"]:,}' in page for i in radar["items"] if not i.get("eta"))
          and all(o.get("done") for i in radar["items"] if not i.get("eta") for o in i["operations"]))
    r = radar["refreshed_at"]
    check("radar ETAs on the page match radar.json", etas == shown, f"{sorted(etas)} vs {sorted(shown)}")
    check("radar freshness badge states block and time (pinned snapshot, UTC observation + relative age slot)", f"#{r['block_number']:,}" in page and r["block_time_utc"] in page
          and "Pinned snapshot · observed" in page and f'data-age="{r["block_timestamp"]}"' in page and "Checking live chain state" in page)

    # html structure
    for f in ["docs/index.html"] + [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(DOCS, "briefs", "*", "index.html"))]:
        b = Balance()
        b.feed(read(f))
        check(f"HTML tag balance: {f}", not b.errors and not [t for t in b.stack if t not in ("html", "body")], "; ".join(b.errors[:3]))

    # v3 design / UX invariants
    pages = {os.path.relpath(p, DOCS): open(p).read() for p in glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)}
    mail = sorted(k for k, v in pages.items() if "mailto:" in v) + (["app.js"] if "mailto:" in appjs else [])
    check("no mailto: links on any page (every CTA works in the browser)", not mail, f"{len(pages)} pages; with mailto: {mail}")
    rq_ = pages.get(os.path.join("request", "index.html"), "")
    req_ok = all(t in rq_ for t in ('id="request"', 'id="req-form"', 'id="req-gh"', 'id="req-gmail"', 'id="req-copy"', "issues/new?template=request-scan.yml",
                                   "https://mail.google.com/mail/?view=cm")) and re.search(r'href="request/"[^>]*>Request a dossier</a>', page) is not None
    check("coverage-request builder at /request/ (linked from the homepage top bar)", req_ok)
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
            if re.match(r"^(https?:|mailto:|data:|javascript:|ethereum:)", h) or h.startswith("//"):
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
    # V8 (v4): one radius token (--radius: 0.375rem = 6 px, shadcn) and only values derived from it (calc(var(--radius) +/- n px)),
    # 50 % dots, 0, or <= 4 px inner details
    radius_ok = re.search(r":root \{[^}]*--radius: 0\.375rem;", css) is not None and len(re.findall(r"--radius:", css)) == 1
    bad_r = [r for r in radii if not re.fullmatch(r"(0|50%|var\(--radius\)|calc\(var\(--radius\) [+-] \d+px\)|[0-4]px|[0-4]px [0-4]px|0 0 calc\(var\(--radius\) \+ \d+px\) calc\(var\(--radius\) \+ \d+px\))", r.strip())]
    check("V8 radius: one --radius token (0.375rem) and every border-radius derived from it (dots 50%, details <= 4px)", radius_ok and not bad_r,
          f"{len(radii)} radii; token {radius_ok}; bad {bad_r}")
    chrome = [rel for rel in pages if rel.startswith("briefs" + os.sep) and not ('class="topbar"' in pages[rel] and 'href="../../styles.css?v=' in pages[rel]
                                                                           and "<style" not in pages[rel])]
    check("briefs share the site chrome and stylesheet (no inline styles)", not chrome, str(chrome))

    # behaviour: run app.js against a synthetic DOM of the real /request/ and homepage markup
    beacon_js = read("docs/b.js") if os.path.exists(os.path.join(DOCS, "b.js")) else ""
    res = app_behaviour(appjs_min, pages.get(os.path.join("request", "index.html"), ""), page, BS.curated_sample(idx)[0]["id"], beacon=beacon_js,
                        protocol_html=pages.get(os.path.join("protocols", "aave-v3-gho", "index.html"), ""), protocol_slug="aave-v3-gho",
                        notfound_html=pages.get("404.html", ""),
                        clearance_html=pages.get(os.path.join("protocols", "extra-finance-base", "index.html"), ""), clearance_slug="extra-finance-base",
                        brief_html=pages.get(os.path.join("briefs", "kerne-kusd-base", "index.html"), ""), brief_slug="kerne-kusd-base",
                        prefill_slug="across-protocol-hubpool",
                        timelock_brief_html=ready_fixture_brief(json.loads(read("docs/api/v1/index.json"))),
                        protocols_index_html=pages.get(os.path.join("protocols", "index.html"), ""),
                        extra={"rescue": read("docs/404-rescue.js") if os.path.exists(os.path.join(DOCS, "404-rescue.js")) else "",
                               "miniapp": dom_tree(pages[os.path.join("miniapp", "index.html")]) if os.path.join("miniapp", "index.html") in pages else None,
                               **{v_["route"]: dom_tree(pages[os.path.join(v_["route"], "index.html")]) for v_ in BS.CHECKOUT.values()
                                  if os.path.join(v_["route"], "index.html") in pages},
                               "checkout": {"api": BS.ORDERS_VERIFY_API, "treasury": BS.CHECKOUT_TREASURY, "usdc": BS.USDC["Base"],
                                            "skus": {k_: v_["atomic"] for k_, v_ in BS.CHECKOUT.items()},
                                            "amounts": {k_: v_["amount"] for k_, v_ in BS.CHECKOUT.items()}}})
    expected = ["default_is_clearance", "default_settlement_is_invoice", "clearance_pay_panel_shown", "invoice_hides_tx_and_direct",
                "clearance_github_href", "clearance_github_tier_exact", "clearance_brief_has_price_and_invoice", "pay_summary_tracks_tier",
                "direct_shows_tx_and_treasury", "tx_valid_in_brief", "tx_valid_in_github",
                "forum_in_brief_and_github", "tx_valid_not_flagged", "tx_invalid_flagged", "tx_invalid_not_in_github", "invoice_drops_tx",
                "community_pay_panel_hidden", "community_tx_field_hidden", "community_github_tier_exact", "community_no_tx_anywhere",
                "community_click_not_prevented", "clearance_restores_pay_panel", "continuous_track", "api_sla_track", "prefill_selects_community",
                "prefill_unknown_tier_keeps_clearance", "prefill_clearance_protocol_forum", "prefill_settlement_direct", "prefill_continuous_invoice",
                "prefill_api_sla", "prefill_unknown_slug_text_only", "prefill_hostile_inert", "prefill_enum_closed", "prefill_forum_https_only",

                "hash_ok #r-[unclosed", "hash_ok #r-x\\", 'hash_ok #r-"]', "hash_ok #r-%E0%A4%A", "livebar_skips_elapsed_etas", "prefill_rapid_500",
                "pf_present", "pf_no_fetch_on_load", "pf_preset_fetches_once", "pf_renders_verdict", "pf_text_only", "pf_cast_commands",
                "pf_invalid_address_no_fetch", "pf_http_error_reported", "req_form_submit_prevented"]
    failed_b = [k for k in expected if res.get(k) is not True] + (["harness_error: " + res["harness_error"][:200]] if "harness_error" in res else [])
    check("app.js behaviour: clearance / continuous / API SLA / community tracks, Option A invoice (default) vs Option B direct settlement, tx-hash + forum flow; malformed #hash never throws; live pre-flight checker (explicit click only, text-only render, cast repro, errors)", not failed_b,
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
    prot_ix = read("docs/protocols/index.html")
    linked = all(f'href="../briefs/{sl}/"' in prot_ix and f"{base}/briefs/{sl}/" in llms_t and f"{base}/briefs/{sl}/" in sm for sl in EXPECT_ONB)
    check("onboarding briefs linked from /protocols/ (#onboarding), llms.txt and sitemap.xml", linked and 'id="onboarding"' in prot_ix
          and "/api/v1/onboarding.json" in llms_t)

    # agent-first (B2A) feeds: proposals.json, llms-full.txt, .well-known/{agent,mcp}.json, SKILL.md
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.dont_write_bytecode = True                            # no __pycache__ writes into a possibly read-only checkout
    import build_b2a_feeds as B2A
    b2a_files = ["api/v1/proposals.json", "llms-full.txt", ".well-known/agent.json", ".well-known/mcp.json", "SKILL.md"]
    rendered = B2A.render_all(idx, radar, onb, json.loads(read("docs/api/v1/rpc-pinned.json")))   # in memory: no scratch files
    drift = [f for f in b2a_files if rendered.get(f, "").encode() != read("docs/" + f, "rb")] + sorted(set(rendered) - set(b2a_files))
    check("B2A feeds are a byte-identical deterministic build of index/radar/onboarding/rpc-pinned.json (no hand edits, no wall clock)", not drift, str(drift))
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
          and man["name"] == "io.github.Fractal-Neurons/pacta" and man["transport"]["type"] == "streamable-http" and man["transport"]["url"] == "https://pacta-x402.pacta.workers.dev/mcp"
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
               and re.search(r'<code class="mono">curl -s -A &quot;my-agent/1\.0&quot; &quot;' + re.escape(API_) + r'/v1/check/preflight\?chain=', hero) is not None
               and all(f'href="{h}"' in hero for h in (API_ + "/openapi.json", "SKILL.md", "llms.txt", ".well-known/agent.json")))
    heroS = re.search(r'<section class="hero">.*?</section>', home, re.S)
    heroS = heroS.group(0) if heroS else ""
    audS = re.search(r'<section class="sec" id="audiences">.*?</section>', home, re.S)
    audS = audS.group(0) if audS else ""
    hiwS = re.search(r'<section class="sec" id="how-it-works">.*?</section>', home, re.S)
    hiwS = hiwS.group(0) if hiwS else ""
    # v4 (V2): "Protocol docs drift." alone on line 1 (<br>, each sentence unbreakable); M1/M6 subhead with the data-derived count
    hero_ok = ('<h1><span class="l">Protocol docs drift.</span><br><span class="l">The chain doesn’t.</span></h1>' in heroS
               and html.escape(BS.HOME_SUB.format(n=X["protocols"]), quote=False) in heroS
               and len(re.findall(r'class="receipt"[^>]*data-receipt data-pf-chain="(?:ethereum|base)" data-pf-address="0x[0-9a-fA-F]{40}"', heroS)) == 3
               and f"claude mcp add --transport http pacta {MCP_}" in hiwS
               and "&quot;url&quot;: &quot;" + MCP_ + "&quot;" in hiwS
               and re.search(r'curl -s &quot;' + re.escape(API_) + r'/v1/check/preflight\?chain=', hiwS) is not None
               and all(f'href="{h}"' in audS for h in ("openapi.json", "SKILL.md", "agent.json", "mcp/")))
    pf_ok = (f'class="pf hero-pf" data-api="{API_}"' in heroS and 'id="pf-form"' in heroS and 'id="pf-out"' in heroS and 'name="chain"' in heroS
             and 'name="address"' in heroS and "Check protocol" in heroS and heroS.find('id="pf-form"') < heroS.find("data-proof")
             and 'id="pf-form" novalidate' in heroS and 'data-proof-card' in heroS)
    check("Edge v3 hero: h1 + subhead, 3 receipt pills (live check + pinned receipt), the instant checker in the hero (before the proof bar); remote MCP (Claude Code + Cursor), curl /v1/check/preflight, OpenAPI / SKILL / agent.json / MCP links in the agents column",
          hero_ok and pf_ok, f"hero {hero_ok}; checker {pf_ok}")
    pr = re.search(r'<section class="sec" id="pricing">.*?</section>', home, re.S)
    pricing_ok = bool(pr) and all(x in pr.group(0) for x in ("$0", "$19", "$49", "$99", "$2,500–$5,000", "$1,500", "Free scorecards, API &amp; MCP",
                                                              "Instant Contract &amp; Safe Deep-Scan", "Live Timelock &amp; Signer Webhook", "24h Mainnet Control-Plane Seal",
                                                              "Continuous Control-Plane Monitoring", "API SLA", "50 free preflight / MCP checks a day, then $0.01 a call over x402",
                                                              "data-x402-strip", "$0.02 / call", "$0.05 / call", "$0.25 / call", "$9.00 / call",
                                                              html.escape(BS.EDITORIAL_FIREWALL, quote=False)))
    req_ok = "Every scorecard, the API and the MCP server stay free" in req_page and 'id="pricing"' in req_page
    check("pricing: #pricing = Free $0 (50 checks / day, then $0.01 over x402) + Agent & API x402 strip ($0.02 / $0.05 / $0.25 / $9.00) / $19 scan / $49 per month webhook / $99 seal + dossiers $2,500-$5,000 / Continuous Control-Plane Monitoring $1,500 / API SLA under the editorial firewall; /request/ carries the same",
          pricing_ok and req_ok, f"#pricing {pricing_ok}; /request/ {req_ok}")
    # unbundled #pricing: 2 cards (free; issuers with no API jargon) + one high-throughput bar below the grid
    # M4 / M5 (v4): every pricing card links its own closed tier=; Continuous Control-Plane Monitoring says the result can still be Delta; no tier name
    # anywhere implies a paid Aligned status; the editorial firewall sits above the cards on / and /request/
    tier_ok = {}
    for rel, t in (("index.html", page), (os.path.join("request", "index.html"), req_page)):
        sec = re.search(r'<section class="sec" id="pricing">.*?</section>', t, re.S)
        sec = sec.group(0) if sec else ""
        pre_ = "" if rel == "index.html" else "../"
        req_ = pre_ + "request/"
        tier_ok[rel] = (re.findall(r'data-plan="([\w-]+)"', sec) == ["free", "instant-scan-19", "radar-webhook-49", "reverify-seal-99"]
                        and all(f'href="{pre_}{h_}" data-cta="{k_}"' in sec for _, _, _, _, _, (_, h_, k_), _ in BS.SELF_SERVE_PLANS)
                        and all(f'href="{req_}?tier={k}" data-tier="{k}"' in sec for k, _, _ in BS.ENTERPRISE_STRIP)
                        and "can still read Delta" in sec and "free, with live re-check on demand" in sec
                        and sec.find("data-editorial") < sec.find('data-pricing') and html.escape(BS.EDITORIAL_FIREWALL, quote=False) in sec)
    stale_m5 = sorted(f for f in [os.path.relpath(x, ROOT) for x in glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)]
                      + ["docs/llms.txt", "docs/llms-full.txt", ".github/ISSUE_TEMPLATE/request-scan.yml", "tools/build_site.py", "tools/app.src.js", "README.md"]
                      if re.search(r"Aligned Maintenance|Aligned Status|continuous Aligned", read(f), re.I))
    check("M4 + M5 pricing: four self-serve cards linking their own product page and the enterprise strip with its own tier= links on / and /request/; paid work can still read Delta, "
          "0 'Aligned Maintenance' / 'Aligned Status' strings on the site, feeds, issue template, generator, app.js or README",
          all(tier_ok.values()) and not stale_m5, f"{tier_ok}; stale {stale_m5[:4]}")

    # ---- issuer conversion callouts: every brief + every protocol page (aligned -> maintenance only; delta / RPC-observed -> clearance)
    import html as _html
    import urllib.parse as _up
    CLR_H = "Verify and reconcile the record"
    MNT_H = "Add Continuous Control-Plane Monitoring"

    def callout_ok(pg, kind, name, slug, forum=None, dossier="default"):
        q = f"tier={kind}&amp;protocol={slug}" + (f"&amp;forum={_up.quote(forum, safe='')}" if forum else "")
        if kind == "clearance":
            qf = q.replace("tier=clearance", "tier=community")
            return (f"<h2>Maintaining {_html.escape(name)}? {CLR_H}</h2>" in pg and pg.count('id="issuer-clearance"') == 1
                    and f'<a data-slot="button" data-variant="outline" href="../../request/?{qf}" data-cta="free_notify">{_html.escape(BS.FREE_NOTIFY_CTA)}</a>' in pg
                    and f'<a data-slot="button" data-variant="{dossier}" href="../../request/?{q}" data-cta="clearance">{_html.escape(BS.DOSSIER_CTA)}</a>' in pg
                    and f'<a href="../../request/?{q}&amp;settlement=invoice" data-cta="clearance_invoice">Request a commercial invoice (PDF)</a>' in pg
                    and "changes only when the onchain state or the documentation aligns at a new finalized block" in pg
                    and "within 24 hours" not in pg and "Clear findings" not in pg and "Request 24h Clearance" not in pg and MNT_H not in pg)
        return (f"<h2>Operating {_html.escape(name)}? {MNT_H}</h2>" in pg and "issuer-clearance" not in pg and CLR_H not in pg
                and "Request 24h Clearance" not in pg and "Clear findings" not in pg
                and f'<a data-slot="button" data-variant="outline" href="../../request/?{q}" data-cta="continuous">Start monitoring</a>' in pg
                and "the result can still be Delta" in pg and "Aligned Maintenance" not in pg
                and f'<a href="../../request/?{q}&amp;settlement=invoice" data-cta="continuous_invoice">Invoice option</a>' in pg)
    brief_bad = []
    radar_items = {it["brief"].rstrip("/").split("/")[-1]: it for it in json.loads(read("docs/api/v1/radar.json"))["items"]}
    for slug_ in BS.BRIEFS:
        pg = pages.get(os.path.join("briefs", slug_, "index.html"), "")
        if not callout_ok(pg, "clearance", radar_items[slug_]["protocol"], BS.BRIEF_PROTOCOL[slug_]):
            brief_bad.append(slug_)
    for b in onb["briefs"]:
        pg = pages.get(os.path.join("briefs", b["slug"], "index.html"), "")
        if not callout_ok(pg, "clearance", b["asset"], b["slug"], b["forum"]["url"]):
            brief_bad.append(b["slug"])
    check(f"{X['briefs']} brief pages carry the 'Maintaining <issuer>? Verify and reconcile the record' callout: a free public doc-update notice (tier=community, 'Submit updated docs') with equal weight next to 'Request a dossier' (tier=clearance) + invoice link, all data-cta; no 'within 24 hours' / 'Clear findings' / 'Request 24h Clearance' copy",
          len(BS.BRIEFS) + len(onb["briefs"]) == X["briefs"] and not brief_bad, str(brief_bad))
    sp_ = BS.site_protocols(json.loads(read("docs/api/v1/index.json")))
    proto_bad, n_al, n_cl = [], 0, 0
    for name_, v in sp_.items():
        pg = pages.get(os.path.join("protocols", v["slug"], "index.html"), "")
        cls_ = {e["classification"] for e in v["entries"]}
        aligned = cls_ == {"aligned_baseline"} and not v["pinned"]
        if aligned:
            n_al += 1
            ok_ = callout_ok(pg, "continuous", name_, v["slug"])
        else:
            n_cl += 1
            fu = v["entries"][0].get("governance_url") if v["pinned"] else None
            ok_ = callout_ok(pg, "clearance", name_, v["slug"], fu, dossier="outline") and (bool(cls_ & {"parameter_delta", "rpc_observed", "protective_delta"}))
        if not ok_:
            proto_bad.append(v["slug"])
    every_delta = all(not ({e["classification"] for e in v["entries"]} & {"parameter_delta", "rpc_observed"})
                      or 'id="issuer-clearance"' in pages.get(os.path.join("protocols", v["slug"], "index.html"), "") for v in sp_.values())
    check(f"{X['protocols']} protocol pages: every parameter_delta / rpc_observed page carries the 24h clearance callout (RPC-pinned pages pass their governance URL as &forum=); "
          "only all-aligned_baseline EAS-attested pages get the quiet $1,500/mo Continuous Control-Plane Monitoring callout (the result can still be Delta) and never a delta-remediation pitch",
          len(sp_) == X["protocols"] and not proto_bad and every_delta and n_al + n_cl == X["protocols"] and n_al == X["badge_tiers"]["aligned"], f"aligned {n_al}, clearance {n_cl}; bad {proto_bad[:5]}")

    # ---- #req-pay: Option A (invoice) first and default, Option B direct USDC to the treasury EOA, never called a Safe
    pay_ok = {}
    for rel, t in ((os.path.join("request", "index.html"), req_page),):
        m = re.search(r'<div class="pay" id="req-pay">.*?</dl><p class="hint">.*?</p></div>', t, re.S)
        blk = m.group(0) if m else ""
        a_, b_ = blk.find("Option A — Formal Commercial Invoice (PDF) &amp; Counterparty Settlement"), blk.find("Option B — Direct Express On-Chain USDC Settlement")
        pay_ok[rel] = (0 <= a_ < b_ and 'name="settlement" value="invoice" checked' in blk and 'name="settlement" value="direct">' in blk
                       and "Submit scope first (no upfront transfer required to open intake)" in blk
                       and f'<dt>Pacta treasury (direct settlement EOA)</dt><dd><span class="mono full">{treasury}</span>' in blk
                       and BS.USDC["Base"] in blk and BS.USDC["Ethereum"] in blk and not re.search(r"\bSafe\b|\bmultisig\b|\bGnosis\b", blk))
    safe_near = []
    for rel, t in pages.items():
        for mm in re.finditer(treasury, t, re.I):
            win = re.sub(r"<[^>]+>", " ", t[max(0, mm.start() - 300): mm.end() + 300])
            if re.search(r"\bSafe\b|\bmultisig\b|\bGnosis\b", win, re.I):
                safe_near.append(rel)
    check("#req-pay on /request/: Option A formal commercial invoice (PDF) first + default, Option B direct USDC to 'Pacta treasury (direct settlement EOA)' "
          f"{treasury[:6]}…{treasury[-4:]} (Base + Ethereum USDC); 0 Safe / multisig wording within 300 chars of the treasury on any HTML page",
          all(pay_ok.values()) and not safe_near, f"{pay_ok}; near {sorted(set(safe_near))[:4]}")

    # ---- prefill safety (static): the prefill code writes .value / .checked only; no inline scripts on the request surfaces
    pre = re.search(r"PREFILL-BEGIN(.*?)PREFILL-END", appjs, re.S)
    init_req = appjs[appjs.find("function initRequest()"): appjs.find("// ---- live pre-flight checker")]
    # no inline JS at all: the theme bootstrap is the same-origin, render-blocking docs/theme.js (CSP script-src 'self')
    THEME_BOOT = read("docs/theme.js") if os.path.exists(os.path.join(DOCS, "theme.js")) else ""
    inline = [rel for rel in ("index.html", os.path.join("request", "index.html"))
              if len(re.findall(r"<script(?![^>]*\bsrc=)(?![^>]*application/ld\+json)[^>]*>", pages.get(rel, ""))) != 0
              or not re.search(r'theme\.js\?v=[0-9a-f]{8}"></script>', pages.get(rel, "")) or not THEME_BOOT.startswith('(function(){var d=document.documentElement,')
              or 'd.classList.add("js")' not in THEME_BOOT
              or "URLSearchParams" in THEME_BOOT or THEME_BOOT != BS.THEME_JS]
    check("/request/ prefill (tier / protocol / forum / settlement): closed enums via hasOwnProperty, text <= 80 chars, https forum <= 300 chars without credentials, "
          "written with .value only (0 innerHTML / insertAdjacentHTML / document.write in the request builder); 0 inline <script> on / and /request/ (the theme bootstrap is docs/theme.js)",
          bool(pre) and "hasOwnProperty" in appjs and not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", pre.group(1) + init_req)
          and "slice(0, max)" in pre.group(1) and "s.length > 300" in pre.group(1) and 'u.protocol === "https:"' in pre.group(1)
          and not inline, f"inline {inline}")

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
    pinned_ = json.loads(read("docs/api/v1/rpc-pinned.json"))
    site_ = BS.site_protocols(idx_, pinned_)
    prot_bad, sm = [], read("docs/sitemap.xml")
    for name, v in site_.items():
        slug, es = v["slug"], v["entries"]
        rel = f"docs/protocols/{slug}/index.html"
        if not os.path.exists(os.path.join(ROOT, rel)):
            prot_bad.append(f"{slug}: missing"); continue
        t = read(rel)
        if t != BS.protocol_page(name, es, idx_, radar_, slug=slug):
            prot_bad.append(f"{slug}: not a deterministic rebuild")
        lds = re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S)
        try:
            ld_ok = bool(lds) and all(json.loads(x).get("@context") == "https://schema.org" for x in lds)
        except ValueError:
            ld_ok = False
        if not ld_ok or len(lds) != 2 or '"BreadcrumbList"' not in t:
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
    pidx_ok = bool(pidx) and pidx == BS.protocols_index_page(idx_, site_) and f"<loc>{BS.BASE_URL}/protocols/</loc>" in sm \
        and all(f'href="{v["slug"]}/"' in pidx for v in site_.values()) and '"@type": "ItemList"' in pidx.replace('"@type":"ItemList"', '"@type": "ItemList"')
    on_disk = sorted(d for d in os.listdir(os.path.join(DOCS, "protocols")) if os.path.isdir(os.path.join(DOCS, "protocols", d)))
    check(f"/protocols/<slug>/ SEO pages: one per published protocol ({len(site_)} = {len(groups)} index.json + {len(site_) - len(groups)} RPC-pinned), deterministic, Dataset + BreadcrumbList JSON-LD, pinned block + hash, cast repro, preflight quickstart, in the sitemap; /protocols/ index (ItemList); no stray protocol directories",
          not prot_bad and pidx_ok and len(groups) == len({e["protocol"] for e in idx_["entries"]}) == X["eas_protocols"] and len(site_) == X["protocols"]
          and on_disk == sorted(v["slug"] for v in site_.values()), f"bad {prot_bad[:4]}; index {pidx_ok}; dirs {len(on_disk)}")

    # RPC-pinned records: a separate, explicitly NOT EAS-attested dataset; never merged into index.json or its EAS counts
    pin_bad = []
    heads = pinned_.get("pinned_heads", {})
    idx_slugs = {BS.protocol_slug(e["protocol"]) for e in idx_["entries"]}
    for e in pinned_.get("entries", []):
        h = heads.get(e["chain"], {})
        if e.get("base_eas_uid") is not None or e.get("provenance") != "rpc_pinned" or any(k in e for k in ("sprint", "summary_doc", "summary_sha256")):
            pin_bad.append(f'{e["id"]}: attestation fields')
        if (e["block_number"], e["block_hash"]) != (h.get("block_number"), h.get("block_hash")) or e["chain_id"] != h.get("chain_id"):
            pin_bad.append(f'{e["id"]}: block != pinned head')
        if not all(eip55_ok(a) for a in (e["target_contract"], e.get("controller_address"), e.get("upstream_controller"), e.get("paired_contract")) if a):
            pin_bad.append(f'{e["id"]}: EIP-55')
        if e["slug"] in idx_slugs or e["rpc_env_var"] != {"ethereum": "$ETH_RPC_URL", "base": "$BASE_RPC_URL"}[e["chain"]]:
            pin_bad.append(f'{e["id"]}: slug / rpc')
        if e["check_type"] == "eth_call" and "0x" + keccak(e["call_signature"].encode()).hex()[:8] != e["selector_or_slot"]:
            pin_bad.append(f'{e["id"]}: selector')
        pt = read(f'docs/protocols/{e["slug"]}/index.html')
        ld0 = json.loads(re.findall(r'<script type="application/ld\+json">(.*?)</script>', pt, re.S)[0])
        if ("not EAS-attested" not in pt or "/api/v1/rpc-pinned.json" not in pt or "· sprint" in pt or "easscan" in pt
                or ld0["distribution"][0]["contentUrl"] != f"{BS.BASE_URL}/api/v1/rpc-pinned.json" or f'--rpc-url &quot;{e["rpc_env_var"]}&quot;' not in pt):
            pin_bad.append(f'{e["id"]}: page provenance')
    check(f"rpc-pinned.json (pacta.rpc_pinned_records.v1): {X['rpc_protocols']} records ({X['rpc_by_chain']['ethereum']} Ethereum + {X['rpc_by_chain']['base']} Base), NOT EAS-attested (attestation.eas_attested false, base_eas_uid null, no sprint / summary fields), every block = the chain's pinned head (number + hash), EIP-55 addresses, selector = keccak(signature), slugs disjoint from index.json; each page says not EAS-attested, links rpc-pinned.json (Dataset distribution too), uses the chain's RPC variable; index.json untouched ({X['records']} records)",
          pinned_.get("schema") == "pacta.rpc_pinned_records.v1" and pinned_.get("attestation", {}).get("eas_attested") is False
          and pinned_.get("summary") == {"protocols": X["rpc_protocols"], "records": X["rpc_protocols"], **X["rpc_by_chain"]}
          and len(pinned_.get("entries", [])) == X["rpc_protocols"] == sum(X["rpc_by_chain"].values())
          and not pin_bad and len(idx_["entries"]) == X["records"], f"bad {pin_bad[:4]}")

    pv_ = json.loads(read("docs/api/v1/rpc-pinned.json"))
    w2_pages = {e["slug"]: read(f'docs/protocols/{e["slug"]}/index.html') for e in pv_["entries"]}
    hub_ = read("docs/protocols/index.html")
    hub_rows = {sl: re.search(rf'<tr[^>]*><td><a href="{sl}/">.*?</tr>', hub_).group(0) for sl in w2_pages}
    f1_ok = {
        "all rpc_observed": [e["classification"] for e in pv_["entries"]] == ["rpc_observed"] * X["rpc_protocols"],
        "documentation not compared": all(e.get("documentation_comparison") == "not_assessed" and e["documented_delay_seconds"] is None
                                          and "publishes" not in e["documented_reference"] and "does not compare" in e["documented_reference"] for e in pv_["entries"]),
        # v4 (M3): one vocabulary: the record badge and the /protocols/ status read "Observed" (RPC-observed baseline); never Aligned / Delta
        "pages: RPC-observed badge only": all('<span class="badge observed">Observed</span>' in t and '<span class="badge aligned">' not in t
                                              and '<span class="badge delta">' not in t and '<span class="badge protect">' not in t and "not assessed" in t
                                              and "RPC-observed baseline" in t for t in w2_pages.values()),
        "hub rows: RPC-observed badge only": all('data-variant="outline"' in r and ">Observed</span>" in r and 'data-variant="warning"' not in r
                                                 and 'data-variant="neutral"' not in r for r in hub_rows.values()),
        "defined in llms.txt + llms-full.txt": all("rpc_observed (on-chain control plane pinned at an archive block height" in read(f) or
                                                   "Classification rpc_observed: on-chain control plane pinned at an archive block height" in read(f)
                                                   for f in ("docs/llms.txt", "docs/llms-full.txt")),
        "mcp.json packageVersion 0.1.5": json.loads(read("docs/.well-known/mcp.json")).get("packageVersion") == "0.1.5"
                                         == json.loads(read("packages/mcp-server/package.json"))["version"],
        "llms-full names v0.1.5": "@pacta/mcp-server v0.1.5" in read("docs/llms-full.txt"),
    }
    check(f"Codex F1: all {X['rpc_protocols']} RPC-pinned records are classification rpc_observed with documentation linked but not compared (no 'publishes' claim, no documented delays); their pages and /protocols/ rows show only the neutral 'RPC-observed baseline' badge; rpc_observed defined in llms.txt + llms-full.txt; mcp.json packageVersion 0.1.5; llms-full names v0.1.5",
          all(f1_ok.values()), str([k for k, v in f1_ok.items() if not v]))
    # free-tier MCP caller attribution (task-06d4550a8b0f): documented on every agent surface; the browser checker names itself
    roles_ = ["autonomous_agent", "defi_developer", "risk_curator_analyst", "security_researcher", "protocol_team", "institutional_allocator", "individual_user"]
    purposes_ = ["pre_trade_safety", "collateral_due_diligence", "yield_allocation", "security_audit", "governance_monitoring", "integration_testing", "general_research"]
    cdoc = {f: read(f) for f in ("docs/SKILL.md", "docs/llms.txt", "docs/llms-full.txt", "docs/llms/index.html", "packages/mcp-server/README.md")}
    cbad = [f for f, t in cdoc.items() if not (all(x in t for x in ["caller_agent", "requester_role", "caller_purpose"] + roles_ + purposes_)
                                              and "Cloudflare edge country" in t and re.search(r"never[^.]{0,40}(?:name|e-mail)", t))]
    check("free MCP tier caller fields (caller_agent slug + requester_role / caller_purpose closed enums) documented in SKILL.md, llms.txt, llms-full.txt, /llms/ and the MCP README (no personal data; location only from the Cloudflare edge); docs SKILL.md == packages/mcp-server/SKILL.md; the live checker passes caller_agent=pacta-wtf-checker",
          not cbad and read("docs/SKILL.md") == read("packages/mcp-server/SKILL.md")
          and "&caller_agent=pacta-wtf-checker&requester_role=individual_user&caller_purpose=general_research" in read("tools/app.src.js"), str(cbad))
    bare = []
    for dp, _dn, fns in os.walk(ROOT):
        if os.sep + ".git" in dp:
            continue
        for fn in fns:
            if fn.endswith((".py", ".md", ".txt", ".html", ".mjs", ".js", ".ts")):
                t = read(os.path.relpath(os.path.join(dp, fn), ROOT))
                for m in re.finditer(r"urlopen\(\s*[\"'](https://(?:pacta-x402\.pacta\.workers\.dev|pacta\.wtf)[^\"']*)", t):
                    bare.append(f"{fn}: {m.group(1)[:60]}")
    check("no bare Python urlopen('https://pacta-x402...' / 'https://pacta.wtf...'): every Python call to Pacta hosts goes through Request(..., headers={'User-Agent': 'pacta-preflight/1.0'}) (bare Python-urllib gets Cloudflare 403 / 1010)",
          not bare, str(bare[:4]))

    robots = read("docs/robots.txt")
    robots_ok = robots == "User-agent: *\nAllow: /\n\nSitemap: https://pacta.wtf/sitemap.xml\n" == BS.ROBOTS_TXT \
        and "Google-Extended" not in robots and "Disallow" not in robots
    check("robots.txt is exactly 'User-agent: *' / 'Allow: /' / sitemap (RFC 9309 admits every crawler; no bot-name stanzas, so no Google-Extended "
          "opt-out matcher can misfire on Gemini url_context; no Disallow)", robots_ok, repr(robots[:120]))

    # P0 task-0efd2038252a: unrestricted indexing / snippet meta on every generated page; /llms/ HTML mirror of llms.txt
    meta_ok_ = f'<meta name="robots" content="{BS.ROBOTS_META}">'
    gen_pages = sorted(r for r in pages if not r.startswith("demos" + os.sep))
    meta_bad = [r for r in gen_pages if len(re.findall(r'<meta name="robots"', pages[r])) != 1
                or (f'<meta name="robots" content="{BS.ROBOTS_META_404}">' if r in ("404.html", os.path.join("pricing", "index.html")) else meta_ok_)
                not in pages[r][:pages[r].index("</head>")]]   # /pricing/ is a noindex redirect stub to /#pricing (T5)
    llms_t = read("docs/llms.txt")
    lm = pages.get(os.path.join("llms", "index.html"), "")
    llms_ok = {
        "deterministic": lm == BS.llms_html(idx, llms_t),
        "exact llms.txt text": f'<pre class="llms" data-llms-mirror>{html.escape(llms_t)}</pre>' in lm,
        "canonical + text/plain alternate": f'<link rel="canonical" href="{BS.BASE_URL}/llms/">' in lm
            and f'<link rel="alternate" type="text/plain" href="{BS.BASE_URL}/llms.txt" title="llms.txt (plain text)">' in lm,
        "links llms.txt + llms-full.txt + b.js": 'href="../llms.txt"' in lm and 'href="../llms-full.txt"' in lm and 'src="../b.js"' in lm,
        "in sitemap": f"<loc>{BS.BASE_URL}/llms/</loc>" in read("docs/sitemap.xml"),
        "linked from the home head + footer": 'href="llms/" title="llms.txt (HTML mirror)"' in pages["index.html"] and '<a href="llms/">llms.txt (HTML)</a>' in pages["index.html"],
        "semantic main / article / pre": re.search(r'<main id="main"[^>]*>.*<article class="memo">.*<pre class="llms"', lm, re.S) is not None,
    }
    check(f"robots meta '{BS.ROBOTS_META}' exactly once in the head of all {len(gen_pages)} generated pages (404.html: noindex variant); /llms/ is an HTML mirror of llms.txt (exact escaped text, canonical, text/plain alternate, in the sitemap, linked from head + footer)",
          not meta_bad and len(gen_pages) >= 66 and all(llms_ok.values()), f"meta bad {meta_bad[:4]}; llms {[k for k, v in llms_ok.items() if not v]}")

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
        "Dockerfile stdio": 'CMD ["node", "/app/bin/pacta-mcp.mjs"]' in dockerfile and re.search(r"^USER node$", dockerfile, re.M) is not None
                            and not re.search(r"^ENTRYPOINT", dockerfile, re.M) and "EXPOSE" not in dockerfile,
    }
    check("registries: glama.json (schema + maintainer), smithery.yaml (stdio from the Dockerfile + remote URL), server.json + server.remote.json remotes (streamable-http), Dockerfile stdio entrypoint",
          all(reg_ok.values()), str({k: v for k, v in reg_ok.items() if not v}))

    # Codex F1 (task-70ae059323fc): the published replay scope is exact (best-effort; not globally atomic without Durable Objects)
    f1_files = ["docs/.well-known/agent.json", "docs/.well-known/mcp.json", "docs/llms.txt", "docs/llms-full.txt", "docs/llms/index.html",
                "docs/SKILL.md", "README.md", "REMEDIATION_SERVICES.md"]
    f1_bad = [f for f in f1_files if re.search(r"accepted once|buys one product only|buys exactly one product", read(f), re.I)]
    card_f1 = json.loads(read("docs/.well-known/agent.json"))["x402"]
    check("x402 settlement guard replay scope is exact on every agent surface: no 'accepted once' / 'buys one product only'; best-effort, not globally atomic without Durable Objects",
          not f1_bad and card_f1["settlementGuard"]["replay"].startswith("best-effort replay rejection: ")
          and card_f1["settlementGuard"]["replay"].endswith("not globally atomic without Durable Objects")
          and all("not globally atomic without Durable Objects" in read(f) for f in ("docs/.well-known/agent.json", "docs/.well-known/mcp.json", "docs/llms.txt", "docs/llms-full.txt")),
          str(f1_bad))
    remote_tools = ["pacta_lookup_protocol", "pacta_check_preflight", "pacta_scan_control_plane", "pacta_scan_timelock_op", "pacta_scan_proposal_diff",
                    "pacta_get_live_timelocks", "pacta_submit_request"]
    man_ = json.loads(read("docs/.well-known/mcp.json"))
    card_ = json.loads(read("docs/.well-known/agent.json"))
    man_remote = next((t_ for t_ in man_.get("transports", []) if t_.get("type") == "streamable-http"), {})
    srv_src = read("packages/mcp-server/src/server.mjs")
    surfaces5 = {
        "mcp.json": man_remote.get("url") == MCP_ and man_remote.get("tools") == remote_tools,
        "agent.json": card_.get("endpoints", {}).get("mcp_remote") == MCP_ and card_.get("pricing", {}).get("mode") == "free_launch"
                      and card_["x402"].get("pricingMode") == "free_launch" and [k["id"] for k in card_["skills"]][:2] == ["protocol-lookup", "contract-preflight"],
        "SKILL.md": all(n in primary["docs/SKILL.md"] for n in remote_tools),
        "llms.txt": all(n in primary["docs/llms.txt"] for n in remote_tools) and "## Free API for agents" in primary["docs/llms.txt"],
        "llms-full.txt": all(n in primary["docs/llms-full.txt"] for n in remote_tools),
        "@pacta/mcp-server": 'name: "pacta_check_preflight"' in srv_src and "PAID_ROUTES.checkPreflight" in srv_src,
        "SKILL.md copies": read("packages/mcp-server/SKILL.md") == primary["docs/SKILL.md"],
    }
    check("remote MCP: 6 read-only tools + pacta_submit_request (pacta_lookup_protocol, then pacta_check_preflight) on mcp.json, agent.json (free_launch pricing), SKILL.md, llms.txt, llms-full.txt; @pacta/mcp-server ships pacta_check_preflight; SKILL.md copies byte-identical",
          all(surfaces5.values()), str({k: v for k, v in surfaces5.items() if not v}))

    # ---- protocol / token lookup (task-14e685be73f9): docs/api/v1/lookup.json == packages/mcp-server/src/lookup.mjs, exact parity with the feeds
    import build_lookup as BL
    lk_doc = json.loads(read("docs/api/v1/lookup.json"))
    node_ = shutil.which("node")
    probe = ("import('" + os.path.join(ROOT, "packages", "mcp-server", "src", "lookup.mjs").replace("\\", "/") + "').then((M) => { const q = (x) => M.lookupProtocols(x); "
             "process.stdout.write(JSON.stringify({ catalog: M.LOOKUP_CATALOG, totals: M.LOOKUP_TOTALS, "
             "probes: Object.fromEntries(['ethena', 'usde', 'aave', 'moonwell', 'kusd', 'uniswap', 'ether.fi'].map((k) => [k, q({ query: k }).results.slice(0, 2).map((r) => [r.slug, r.match])])), "
             "empty: q({}), base: q({ chain: 'base', limit: 61 }).results.map((r) => r.chain), over: q({ query: 'x'.repeat(81) }) })); })")
    lk_run = subprocess.run([node_, "--input-type=module", "-e", probe], capture_output=True, text=True, timeout=60) if node_ else None
    lk = json.loads(lk_run.stdout) if lk_run and lk_run.returncode == 0 else {}
    sp_lk = BS.site_protocols(json.loads(read("docs/api/v1/index.json")))
    idx_lk, pin_lk = json.loads(read("docs/api/v1/index.json")), json.loads(read("docs/api/v1/rpc-pinned.json"))
    onb_lk, rad_lk = json.loads(read("docs/api/v1/onboarding.json")), json.loads(read("docs/api/v1/radar.json"))
    items_lk = lk_doc.get("items", [])
    by_lk = {x["slug"]: x for x in items_lk}
    surf_lk = {su["id"]: (x, su) for x in items_lk if x.get("easAttested") for su in x["surfaces"]}
    lk_ok = {
        "schema + totals (EXPECT)": lk_doc.get("schema") == "pacta.protocol_lookup_catalog.v1"
            and lk_doc.get("totals") == {"protocols": X["protocols"], "briefs": X["briefs"], "easAttestedProtocols": X["eas_protocols"],
                                         "rpcObservedProtocols": X["rpc_protocols"], "items": X["protocols"] + X["briefs"]},
        "lookup.json == src/lookup.mjs (node import)": bool(lk) and lk.get("catalog") == items_lk and lk.get("totals") == lk_doc.get("totals"),
        "regenerates byte-identically": BL.catalog_json(BL.build_items(sp_lk, onb_lk, rad_lk, BS.BRIEF_PROTOCOL)) == read("docs/api/v1/lookup.json"),
        "protocol slugs == /protocols/ pages": sorted(x["slug"] for x in items_lk if x["kind"] == "protocol") == sorted(v["slug"] for v in sp_lk.values()),
        "every index.json record -> its EAS protocol (uid, classification, target)": len(surf_lk) == len(idx_lk["entries"]) and all(
            e["id"] in surf_lk and surf_lk[e["id"]][1]["classification"] == e["classification"] and surf_lk[e["id"]][1]["targetContract"] == e["target_contract"]
            and e["base_eas_uid"] in surf_lk[e["id"]][0]["baseEasUids"] for e in idx_lk["entries"]),
        "every rpc-pinned record: rpc_observed, not EAS, not_assessed": all(
            e["slug"] in by_lk and by_lk[e["slug"]]["primaryContract"] == e["target_contract"] and by_lk[e["slug"]]["controllerAddress"] == e["controller_address"]
            and (by_lk[e["slug"]]["classification"], by_lk[e["slug"]]["easAttested"], by_lk[e["slug"]]["documentationComparison"]) == ("rpc_observed", False, "not_assessed")
            for e in pin_lk["entries"]),
        "rpc_observed never aligned / parameter_delta": not [x["slug"] for x in items_lk if not x.get("easAttested") and x["classification"] in
                                                             ("aligned_baseline", "parameter_delta", "protective_delta", "mixed")],
        f"{X['briefs']} briefs (onboarding + radar)": sorted(x["slug"] for x in items_lk if x["kind"] == "brief") == sorted(
            [b["slug"] for b in onb_lk["briefs"]] + [i["brief"].rstrip("/").split("/")[-1] for i in rad_lk["items"]]),
        "EIP-55 + preflightArgs": all(eip55_ok(x["primaryContract"]) and (x["controllerAddress"] is None or eip55_ok(x["controllerAddress"]))
                                      and x["preflightArgs"] == {"chain": x["chain"], "address": x["primaryContract"]} for x in items_lk),
        "search probes": lk.get("probes") == {"ethena": [["ethena-usde-susde", "prefix"], ["ethena-usdtb", "prefix"]],
                                              "usde": [["ethena-usde-susde", "exact"], ["ethena-ops-0x0ca0-0x1fe5", "exact"]],
                                              "aave": [["aave-v3-base", "exact"], ["aave-v3-gho", "exact"]],
                                              "moonwell": [["moonwell-lending-base", "prefix"]], "kusd": [["kerne-kusd-base", "exact"], ["steakhouse-financial-ethereum", "substring"]],
                                              "uniswap": [["uniswap-governance-timelock", "prefix"], ["uniswap-v4", "prefix"]],
                                              "ether.fi": [["ether-fi-core-eeth-weeth", "prefix"], ["ether-fi-liquid-veda-boringvault", "prefix"]]}
                          and (lk.get("empty") or {}).get("count") == 20 and (lk.get("empty") or {}).get("totalMatches") == X["protocols"] + X["briefs"]
                          and set(lk.get("base") or ["x"]) == {"base"} and (lk.get("over") or {}).get("error") == "invalid_input",
        "documented on every agent surface": all("pacta_lookup_protocol" in primary[f] and "/v1/protocols/lookup" in primary[f]
                                                 for f in ("docs/SKILL.md", "docs/llms.txt", "docs/llms-full.txt"))
            and card_["endpoints"].get("lookup") == API_ + "/v1/protocols/lookup" and man_.get("lookup", {}).get("tool") == "pacta_lookup_protocol"
            and "pacta_lookup_protocol" in read("docs/llms/index.html") and f"{BS.BASE_URL}/api/v1/lookup.json" in read("docs/sitemap.xml"),
        "@pacta/mcp-server 0.1.5 everywhere": {json.loads(read("packages/mcp-server/package.json"))["version"], json.loads(read("packages/mcp-server/server.json"))["version"],
                                               json.loads(read("packages/mcp-server/server.json"))["packages"][0]["version"], json.loads(read("packages/mcp-server/server.remote.json"))["version"],
                                               man_.get("packageVersion")} == {"0.1.5"}
            and 'version: "0.1.5"' in read("docs/SKILL.md") and 'version: "0.1.5"' in read("packages/mcp-server/src/server.mjs"),
    }
    check(f"protocol / token lookup: docs/api/v1/lookup.json ({X['protocols']} protocols + {X['briefs']} briefs; {X['eas_protocols']} EAS-attested, {X['rpc_protocols']} rpc_observed / not_assessed) regenerates byte-identically, "
          "equals packages/mcp-server/src/lookup.mjs, matches index.json / rpc-pinned.json / onboarding.json / radar.json record by record; search probes "
          "(ethena, usde, aave, moonwell, kusd, uniswap, listing, chain=base, overlong); documented on SKILL.md / llms / agent.json / mcp.json / sitemap; @pacta/mcp-server 0.1.5",
          all(lk_ok.values()), str([k for k, v in lk_ok.items() if not v]))

    # ---- Phase C: first-party beacon, 404, governance forum digest, MCP Registry workflow, root Dockerfile ----
    BEACON_URL = API_ + "/v1/telemetry/beacon"
    bjs_raw = read("docs/b.js", "rb") if os.path.exists(os.path.join(DOCS, "b.js")) else b""
    bjs = bjs_raw.decode()
    b_urls = set(re.findall(r"https?://[^\s\"'`)]+", bjs))
    b_events = {"page_load", "scroll_50", "scroll_90", "copy_mcp_url", "copy_curl", "copy_skill_md", "cta_click", "protocol_view", "not_found_404"}
    beacon_static = {
        "size < 2048 bytes": 0 < len(bjs_raw) < 2048,
        # https://pacta.wtf only appears as the string compared with the page's <link rel="canonical"> (never requested)
        "only the first-party endpoint": b_urls - {"https://pacta.wtf"} == {BEACON_URL} and bjs.count("https://pacta.wtf") == 1,
        "sendBeacon(url, string) + keepalive no-cors fallback": "sendBeacon(U,b)" in bjs.replace(" ", "") and "JSON.stringify" in bjs
                                                               and re.search(r'keepalive:\s*(!0|true)', bjs) is not None and '"no-cors"' in bjs,
        "Do Not Track gate": re.search(r'\.doNotTrack\s*!=\s*"1"', bjs) is not None,
        "every contract event (b.js page / scroll / 404 events; app.js copy / CTA / checker hooks via pactaBeacon)":
            all(f'"{e}"' in bjs for e in ("page_load", "scroll_50", "scroll_90", "protocol_view", "not_found_404"))
            and all(f'"{e}"' in appjs for e in ("copy_mcp_url", "copy_curl", "copy_skill_md", "cta_click", "live_checker_submit")),
        "no cookie / storage / fingerprint APIs": not re.search(r"cookie|localStorage|sessionStorage|indexedDB|userAgent|canvas|crypto|Math\.random|Date\.now",
                                                                re.sub(r"/\*.*?\*/", "", bjs, flags=re.S)),
    }
    check(f"beacon docs/b.js ({len(bjs_raw)} bytes): < 2 KB, posts only to {BEACON_URL} via sendBeacon (string body; fetch keepalive no-cors fallback), DNT gate, all 9 page events (+ live_checker_submit from app.js), no cookie/storage/fingerprint APIs",
          all(beacon_static.values()), str({k: v for k, v in beacon_static.items() if not v}))
    check("x-card-scorecards-1200x628.png wired on /scorecards/ and all 4 social cards present",
          f'<meta property="og:image" content="{BS.BASE_URL}/cards/x-card-scorecards-1200x628.png">' in pages.get(os.path.join("scorecards", "index.html"), "")
          and f'<meta name="twitter:image" content="{BS.BASE_URL}/cards/x-card-scorecards-1200x628.png">' in pages.get(os.path.join("scorecards", "index.html"), "")
          and all(os.path.exists(os.path.join(DOCS, c_)) for c_ in SOCIAL_CARDS))
    # ---- Option B v2: three single-SKU product pages, the site-wide entry points, the /request/ launcher and the checkout engine ----
    lk_v2 = {i_["slug"]: i_ for i_ in json.loads(read("docs/api/v1/lookup.json"))["items"]}
    sm_v2 = read("docs/sitemap.xml")
    CTA_V2 = {"instant-scan-19": "Pay $19 USDC on Base &amp; Unlock Full Report", "radar-webhook-49": "Pay $49 USDC on Base &amp; Activate Webhook",
              "reverify-seal-99": "Pay $99 USDC on Base &amp; Book 24h Re-Verification"}
    pd_bad = {}
    for k_, v_ in BS.CHECKOUT.items():
        t_ = pages.get(os.path.join(v_["route"], "index.html"), "")
        fm_ = re.search(r'<form class="co" id="co-form".*?</form>', t_, re.S)
        f_ = fm_.group(0) if fm_ else ""
        vis_ = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", t_, flags=re.S))
        img_ = f"{BS.BASE_URL}/cards/{v_['card']}" if v_["card"] else f"{BS.BASE_URL}/og-preview.png"
        probs = [n_ for n_, ok_ in (
            ("form", bool(f_) and f'data-sku="{k_}"' in f_ and f'data-api="{BS.ORDERS_VERIFY_API}"' in f_ and t_.count('id="co-form"') == 1),
            ("one product", 'name="sku"' not in t_ and t_.count("data-co-pay") == 1),
            ("h1 + price", f'<h1 id="co-title">{html.escape(v_["h1"])}</h1>' in t_ and f'<b>{html.escape(v_["price"])}</b>' in t_),
            ("primary CTA", f'<span>{CTA_V2[k_]}</span>' in f_ and 'id="co-wallet"' in f_ and 'id="co-wallet" hidden' not in f_),
            ("manual drawer collapsed", '<details class="co-manual" id="co-manual"><summary>Paying from a Safe multisig, CLI, or mobile wallet? Transfer manually' in f_
             and '<details class="co-manual" id="co-manual" open' not in f_),
            ("treasury pill", f'<span class="addr-pill mono" title="{BS.CHECKOUT_TREASURY}" data-co-treasury>0x4348…Ed14</span>' in f_
             and f'data-copy="{BS.CHECKOUT_TREASURY}"' in f_),
            ("no raw 42-char hex in visible text", not re.search(r"0x[0-9a-fA-F]{40}", vis_)),
            ("no EOA plumbing copy", "externally owned account" not in t_ and "not a contract" not in t_),
            ("exact EIP-681 link + amount", f'href="{html.escape(BS.eip681(v_["atomic"]))}"' in f_ and f'<b class="mono" data-co-amount>{v_["amount"]} USDC</b>' in f_),
            ("tx hash + verify inside the drawer", 0 <= f_.find('id="co-manual"') < f_.find('name="tx_hash"') < f_.find('id="co-verify"')),
            ("preview", f'<aside class="pd-preview" aria-label="What the payment unlocks"><div class="pv-card" data-slot="card" data-preview="{v_["route"]}">' in t_),
            ("social card + canonical + sitemap", f'<meta property="og:image" content="{img_}">' in t_ and '<meta property="og:image:height" content="628">' in t_
             and f'<link rel="canonical" href="{BS.BASE_URL}/{v_["route"]}/">' in t_ and f"<loc>{BS.BASE_URL}/{v_['route']}/</loc>" in sm_v2),
            ("firewall", html.escape(BS.EDITORIAL_FIREWALL, quote=False) in t_),
        ) if not ok_]
        if probs:
            pd_bad[v_["route"]] = probs
    scan_ = pages.get(os.path.join("scan", "index.html"), "")
    chips_v2 = {html.unescape(lbl_): a_ for a_, lbl_ in re.findall(r'data-receipt data-pf-chain="(?:ethereum|base)" data-pf-address="(0x[0-9a-fA-F]{40})" aria-label="Try ([^:]+):', scan_)}
    want_chips = {lbl: BS.LIVE_CHECK_TARGET.get(sl, (lk_v2[sl]["preflightArgs"]["chain"], lk_v2[sl]["preflightArgs"]["address"]))[1] for lbl, sl in BS.SCAN_CHIPS}
    st_r = next(x_ for x_ in BS.receipt_data(idx) if x_["slug"] == "stader-labs-ethx")
    web_ = pages.get(os.path.join("webhook", "index.html"), "")
    alert_ = BS.DECODED[BS.ALERT_EXAMPLE]["operations"][0]
    seal_ = pages.get(os.path.join("seal", "index.html"), "")
    previews_ok = {
        "scan: the free live checker is the scanner (4 real indexed protocol chips) and the sample is the real Stader record":
            'class="pf hero-pf"' in scan_ and 'data-lookup="../api/v1/lookup.json"' in scan_ and chips_v2 == want_chips
            and f'block #{int(st_r["e"]["block_number"]):,}' in scan_
            and f'data-variant="warning">Delta · {html.escape(st_r["chain"].replace("Manager Safe is ", ""), quote=False)} on chain vs {html.escape(st_r["docs"].replace("Manager Safe is ", ""), quote=False)} docs</span>' in scan_
            and "<svg" in scan_.split('data-preview="scan"')[-1].split('class="pv-rows"')[0]
            and all(f'<code class="sel-chip">{html.escape(c_)}</code>' in scan_ and c_ in pages.get(os.path.join("protocols", "stader-labs-ethx", "index.html"), "")
                    for c_ in BS.SCAN_SAMPLE_CHIPS)
            and 'id="pf-submit"' in scan_ and re.search(r'data-variant="default" data-size="lg" type="submit" id="pf-submit"', scan_) is not None,
        "webhook: quick picks + an alert card built from the decoded radar brief (block, decoded call, live ETA countdown)":
            web_.count("data-co-pick") == len(BS.WEBHOOK_PICKS) and f'Ethereum #{alert_["scheduled"]["block"]:,}' in web_
            and f'data-eta="{alert_["eta"]}"' in web_ and alert_["calls"][0]["function"] in web_,
        "seal: three deliverables (EAS seal with rosette + badge, Safe Transaction Builder JSON, docs PR diff) and the editorial guarantee":
            seal_.count('class="pv-d"') == 3 and "<svg" in seal_.split('data-preview="seal"')[-1] and f'src="../badges/{BS.BADGE_DEMO}.svg"' in seal_
            and html.escape(BS.SEAL_GUARANTEE, quote=False) in seal_,
    }
    scan_cold_part = scan_.split('id="scan-upgrade"')[0] if 'id="scan-upgrade"' in scan_ else scan_
    check("Cold-traffic explainer & progressive funnel (/scan/ & /seal/): zero upfront $19/$99 box on initial /scan/ load, 4 live preset chips, "
          "Docs-vs-Bytecode + 5-check explainer, progressive #scan-upgrade & #co-card reveal after free check or ?unlock=1, and /seal/ explainer + sample before #co-form (harness)",
          'id="scan-upgrade" data-scan-upgrade hidden' in scan_ and 'id="co-card" data-co-card hidden' in scan_
          and "$19" not in scan_cold_part and "$99" not in scan_cold_part
          and scan_.count('class="ex-item"') == 5 and "PUBLISHED DOCS PROMISE" in scan_ and "LIVE ON-CHAIN REALITY" in scan_
          and 0 < seal_.find("data-seal-explainer") < seal_.find('data-preview="seal"') < seal_.find('id="co-form"')
          and 'data-seal-free-first' in seal_ and res.get("co_progressive_scan_funnel") is True,
          f"funnel={res.get('co_progressive_scan_funnel')}; cold_$19={'$19' in scan_cold_part}")
    nav_bad = [r_ for r_, t_ in pages.items() if 'class="topbar"' in t_ and not all(x_ in (re.search(r'<nav data-slot="navigation-menu" class="nav" aria-label="Primary">.*?</nav>', t_, re.S) or re.search("$^", "")).group(0).replace(' aria-current="page"', "")
                                                                                 for x_ in ('scan/">Instant Scan</a>', '#pricing">Pricing</a>', 'bounties/">Bounties</a>',
                                                                                            'radar/">Radar</a>', 'scorecards/">Scorecards</a>', 'mcp/">MCP</a>'))]
    radar_v2 = pages.get(os.path.join("radar", "index.html"), "")
    seal_cta_bad = []
    for name_, v in BS.site_protocols(idx).items():
        pg_ = pages.get(os.path.join("protocols", v["slug"], "index.html"), "")
        has_ = f'href="../../seal/?protocol={v["slug"]}" data-cta="seal_99"' in pg_
        if has_ != ('id="issuer-clearance"' in pg_):
            seal_cta_bad.append(v["slug"])
    req_v2 = read("docs/request/index.html")
    launch_ok = ('<nav class="launcher" aria-label="Instant self-serve checks" data-launcher>' in req_v2 and "<h1>Request a dossier</h1>" in req_v2
                 and all(f'href="../{v_["route"]}/" data-sku="{k_}"' in req_v2 for k_, v_ in BS.CHECKOUT.items())
                 and req_v2.find("data-launcher") < req_v2.find('id="req-form"'))
    co_src = read("tools/app.src.js")
    co_js = co_src[co_src.find("var CO_TREASURY"):co_src.find("function initLauncher")]
    co_js_ok = (f'var CO_TREASURY = "{BS.CHECKOUT_TREASURY}", CO_USDC = "{BS.USDC["Base"]}", CO_CHAIN = "0x2105";' in co_js
                and hex(BS.CHECKOUT_CHAIN_ID) == "0x2105"
                and all(f'"{k_}": {{ atomic: {v_["atomic"]}, amount: "{v_["amount"]}", route: "{v_["route"]}"' in co_js for k_, v_ in BS.CHECKOUT.items())
                and all(f'"{v_["tier"]}": "{k_}"' in co_js for k_, v_ in BS.CHECKOUT.items())
                and '"0xa9059cbb" + coPad(CO_TREASURY.slice(2).toLowerCase()) + coPad(Number(atomic).toString(16))' in co_js
                and co_js.count('method: "eth_sendTransaction"') == 1 and "0x095ea7b3" not in co_src and "increaseAllowance" not in co_src
                and not re.search(r'method:\s*"(?:eth_sign|personal_sign|eth_signTypedData\w*)"', co_src)
                and co_js.count("fetch(api, opts)") == 1 and "innerHTML" not in co_js and "data-treasury" not in co_js
                and "var order = body(), from = \"\";" in co_js and "order.tx_hash = String(h);" in co_js and "attempt(order, 15)" in co_js
                and "attempt(body()" not in co_js and 0 <= co_js.find("setBusy(true);   // locked BEFORE the first wallet request") < co_js.find('eth.request({ method: "eth_requestAccounts" })')
                and '$$("[data-receipt], [data-co-pick]")' in co_js and "function manual()" in co_js)
    css_v2 = read("docs/styles.css")
    css_ok = (".addr-pill { display: inline-flex; align-items: center; white-space: nowrap;" in css_v2 and "html.co-print #co-form > :not(#co-result)" in css_v2
              and "#co-wallet { width: 100%; height: auto; min-height: 48px; padding: 12px 20px; white-space: normal;" in css_v2)
    # r2: one maintainer card per delta page (one solid button), the What differs pointer on every non-protective delta box,
    # the product pages in every footer, one visible target field on /webhook/
    maint_bad = []
    for name_, v in BS.site_protocols(idx).items():
        pg_ = pages.get(os.path.join("protocols", v["slug"], "index.html"), "")
        if 'id="issuer-clearance"' not in pg_:
            continue
        card_ = re.search(r'<section class="memo-sec convert maint" id="seal-cta">.*?</section>', pg_, re.S)
        wd_ = re.search(r'<section class="memo-sec whatdiffers( protective)?" data-what-differs>.*?</section>', pg_, re.S)
        ok_ = (card_ is not None and card_.group(0).count('data-variant="default"') == 1 and 'id="issuer-clearance"' in card_.group(0)
               and pg_.count('class="memo-sec convert') == 1
               and (wd_ is None or (('href="#seal-cta" data-cta="seal_wd"' in wd_.group(0)) == (wd_.group(1) is None))))
        if not ok_:
            maint_bad.append(v["slug"])
    ftr_v2 = [r_ for r_, t_ in pages.items() if 'class="ftr"' in t_ and not all(f'{x_}</a></li>' in t_ for x_ in ('scan/">Instant scan', 'webhook/">Timelock webhooks', 'seal/">24h mainnet seal'))]
    web_one = ('id="co-watch" type="text"' in web_ and '<input type="hidden" id="co-target" name="target_address">' in web_
               and '<input type="hidden" id="co-docs" name="protocol_or_docs">' in web_ and 'for="co-target"' not in web_ and 'for="co-docs"' not in web_)
    co_keys = ["co_single_sku_pages", "co_no_wallet_opens_drawer", "co_scan_chip_previews_and_orders", "co_verify_posts_exact_body", "co_result_text_only",
               "co_contract_codes", "co_errors_reported", "co_wallet_transfer_only", "co_wallet_cancel_sends_nothing", "co_wallet_single_flight",
               "co_snapshot_and_inputs_locked", "co_webhook_picks_and_rules", "co_webhook_single_target", "co_seal_protocol_prefill", "co_request_launcher_forward",
               "co_mobile_webview_deeplinks"]
    co_failed = [k_ for k_ in co_keys if res.get(k_) is not True]
    check(f"Option B v2: /scan/ /webhook/ /seal/ are single-product pages (one form, one primary Pay action, the manual transfer collapsed with a one-line "
          f"0x4348…Ed14 pill, no raw 42-char hex or EOA copy, exact EIP-681 + amount, real-data previews, 1200x628 cards); nav, /radar/, every flagged protocol "
          f"page and the /request/ launcher link them; app.js payee / token / chain / amounts = the build's, transfer only, frozen order, single flight; "
          f"behaviour {len(co_keys) - len(co_failed)}/{len(co_keys)} (harness)",
          not pd_bad and all(previews_ok.values()) and not nav_bad and 'href="../webhook/" data-cta="radar_webhook_49"' in radar_v2 and not seal_cta_bad
          and launch_ok and co_js_ok and css_ok and not co_failed and not maint_bad and not ftr_v2 and web_one,
          f"pages {pd_bad}; previews {[k_[:30] for k_, v_ in previews_ok.items() if not v_]}; nav {nav_bad[:3]}; seal cta {seal_cta_bad[:3]}; launcher {launch_ok}; "
          f"js {co_js_ok}; css {css_ok}; failed {co_failed[:4]}; maintainer card {maint_bad[:3]}; footer {ftr_v2[:3]}; webhook one field {web_one}")
    rescue_ = read("docs/404-rescue.js") if os.path.exists(os.path.join(DOCS, "404-rescue.js")) else ""
    nf_ = pages.get("404.html", "")
    csp_at = nf_.find(f'<meta http-equiv="Content-Security-Policy" content="{BS.CSP}">')
    r_at, b_at = nf_.find('<script src="/404-rescue.js"></script>'), nf_.find('<script src="/b.js" defer></script>')
    r_keys = ["r_rescues_known_routes", "r_leaves_everything_else", "b_v5_rescued_sends_nothing"]
    check("404.html stripped-? rescue: docs/404-rescue.js (same origin, right after the CSP meta, before b.js) sends /<route>/<utm_*|tier|ref>=... on the "
          "known routes to /<route>/?... with location.replace (also under /website-test/), leaves every other path alone; the beacon stays silent (harness)",
          rescue_ == BS.RESCUE_JS and 0 <= csp_at < r_at < b_at and sum(t_.count("404-rescue.js") for t_ in pages.values()) == 1
          and r'^\/((?:website-test|public\/web\/option-b-v2)\/)?(scorecards|request|scan|seal|webhook|miniapp|radar|bounties|leaderboard|methodology|protocols(?:\/[a-z0-9-]+)?)\/((?:utm_[a-z]+|tier|ref)=.+)$' in rescue_
          and "L.replace(" in rescue_ and "w.pactaRescued=1" in rescue_ and "&&!w.pactaRescued" in bjs and all(res.get(k_) is True for k_ in r_keys),
          f"csp {csp_at} rescue {r_at} b.js {b_at}; failed {[k_ for k_ in r_keys if res.get(k_) is not True]}")
    b5_keys = ["b_v5_routes", "b_v5_campaign_fields", "b_v5_host"]
    check("b.js v5.1: all live site routes (/pricing/ /about/ /for-protocols/ /integrations/ /mcp/ /demos/ /privacy/ /terms/ + core v5 set); production-host-only gate "
          "(pacta.wtf | pacta.fractalneurons.com | pacta-fractalneurons.pages.dev; staging sends 0 beacons); allowlisted m, c, and h (harness)",
          r"/^\/(protocols|scorecards|radar|bounties|leaderboard|methodology|request|scan|seal|webhook|miniapp|briefs|llms|pricing|about|for-protocols|integrations(\/vault-factories)?|mcp|demos(\/swapio-x402)?|privacy|terms)$/" in bjs
          and r"/^(pacta\.wtf|pacta\.fractalneurons\.com|pacta-fractalneurons\.pages\.dev)$/.test(L.hostname)" in bjs
          and r'/^(paid|paid_search|cpc|organic)$/.test(u=G("medium"))&&(b.m=u)' in bjs
          and r'/^[a-z\d_-]{1,32}$/.test(u=G("campaign"))&&!D.test(u)&&!/[\da-f]{12}/.test(u)&&(b.c=u)' in bjs
          and r'b.h=/\.com$/.test(L.hostname)?"com":"wtf"' in bjs and all(res.get(k_) is True for k_ in b5_keys),
          str([k_ for k_ in b5_keys if res.get(k_) is not True]))
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
    page_js = {"docs/app.js": appjs, "docs/b.js": bjs, "docs/theme.js": read("docs/theme.js")}
    # v4 (U2) + X conversion dedup: localStorage stores only THEME_KEY ("pacta-theme") and X_PURCHASE_KEY ("pacta-x-purchased");
    # createElement("script") appears once in app.js for the host-gated X tag (https://static.ads-twitter.com/uwt.js) and nowhere else.
    ls_vars = set(re.findall(r"localStorage\.\w+\((\w+)", appjs))
    ls_keys = set(re.findall(r'localStorage\.(?:getItem|setItem)\("([^"]+)"', appjs)) | (
        {"pacta-theme"} if 'var THEME_KEY = "pacta-theme";' in appjs and "THEME_KEY" in ls_vars else set()) | (
        {"pacta-x-purchased"} if 'X_PURCHASE_KEY = "pacta-x-purchased"' in appjs and "X_PURCHASE_KEY" in ls_vars else set())
    js_bad = sorted(f for f, t in page_js.items() if re.search(
        r"document\.cookie|sessionStorage|indexedDB|XMLHttpRequest|new Image\b|WebSocket|EventSource|importScripts"
        + (r"|createElement\(\s*\"script" if f != "docs/app.js" else r""), t))
    script_el_ok = len(re.findall(r'createElement\(\s*"script"', appjs)) == 1 and 'X_UWT_SRC = "https://static.ads-twitter.com/uwt.js"' in appjs
    data_api = set(re.findall(r'data-api="([^"]+)"', "".join(pages.values())))
    app_fetch = len(re.findall(r"\bfetch\(", appjs))
    check("page script boundaries: b.js/theme.js touch zero cookies/storage/third-party scripts; app.js uses localStorage only for pacta-theme + pacta-x-purchased dedup, injects only host-gated uwt.js, and fetch() calls only this site's JSON, data-api, data-live-timelocks, and the four allow-listed public RPCs",
          not js_bad and script_el_ok and ls_vars == {"THEME_KEY", "X_PURCHASE_KEY"} and ls_keys == {"pacta-theme", "pacta-x-purchased"} and appjs.count("localStorage") == 5 and data_api <= {API_, API_ + "/v1/requests", API_ + "/v1/orders/verify"}
          and app_fetch == 10 and appjs[appjs.find("function initCheckout()"):appjs.find("function initLauncher")].count("fetch(api, opts)") == 1 and "fetch(pfUrl," in appjs[appjs.find("function initMiniApp()"):] and "fetch(verifyApi," in appjs[appjs.find("function initMiniApp()"):] and 'j(root + "api/v1/lookup.json")' in appjs and 'j(root + "api/v1/scorecards.json")' in appjs and 'fetch(api, init)' in appjs[appjs.find("function initRequest()"):] and "REQ_API_RE.test(api)" in appjs and 'fetch(document.documentElement.getAttribute("data-api") || "api/v1/index.json")' in appjs
          and 'fetch(body.getAttribute("data-src") || "api/v1/scorecards.json")' in appjs
          # the 4th fetch: the user-initiated "Verify live on RPC" button, POSTing JSON-RPC only to the four allow-listed public RPCs
          and "      return fetch(url, opts).then(function (res) { return res.json(); })" in appjs
          and re.search(r'var LIVE_RPCS = \{ ethereum: \["https://ethereum-rpc\.publicnode\.com", "https://eth\.drpc\.org"\],\s*base: \["https://base-rpc\.publicnode\.com", "https://mainnet\.base\.org"\] \};', appjs) is not None
          and appjs.count("rpcCall(") == 10 and len(re.findall(r'rpcCall\([a-z.]+, "(\w+)"', appjs)) == 9
          and set(re.findall(r'rpcCall\([a-z.]+, "(\w+)"', appjs)) == {"eth_blockNumber", "eth_call", "eth_getStorageAt", "eth_getBlockByNumber", "eth_getCode"}
          and 'btn.addEventListener("click", function () {' in appjs[appjs.index("function liveVerifyBtn"):appjs.index("function pfRow")]
          and "    fetch(url, init)\n" in appjs and "if (!LIVE_TL_RE.test(url)) { liveSettled(false, null); return; }" in appjs
          and set(re.findall(r'data-live-timelocks="([^"]+)"', "".join(pages.values()))) == {html.escape(BS.LIVE_TIMELOCKS_URL)}
          and BS.LIVE_TIMELOCKS_URL.startswith(API_ + "/v1/briefs/live-timelocks?")
          and 'fetch(api + "/v1/check/preflight?chain=" + ch + "&address=" + a + "&caller_agent=pacta-wtf-checker&requester_role=individual_user&caller_purpose=general_research", opts)' in appjs,
          f"bad {js_bad}; localStorage keys {sorted(ls_keys)}; data-api {sorted(data_api)}; fetch {app_fetch}")
    b_keys = ["b_page_load_payload", "b_hook_exposed", "b_copy_and_cta_events", "b_scroll_once_each", "b_live_checker_submit", "b_invalid_submit_not_reported",
              "b_protocol_view", "b_protocol_copy_curl_and_cta", "b_not_found_404", "b_not_found_path_sanitised", "b_not_found_copy_mcp",
              "b_dnt_sends_nothing", "b_non_https_sends_nothing", "b_fetch_fallback", "b_no_cookie_access",
              "b_c1_spec_payloads", "b_c1_referrers_redacted", "b_c1_utm_redacted", "b_c1_all_protocol_slugs_kept", "b_c1_page_paths",
              "b_c2_slug_only_from_canonical", "b_cta_aligned_maintenance", "b_cta_clearance_protocol", "b_cta_clearance_brief", "b_cta_pricing"]
    failed_bk = [k for k in b_keys if res.get(k) is not True] + (["harness_error: " + res["harness_error"][:200]] if "harness_error" in res else [])
    check("beacon behaviour (node harness, mocked navigator.sendBeacon): page_load {r, u}, same-site r=self, protocol_view t=slug, copy_mcp_url / copy_curl / copy_skill_md / cta_click hooks, scroll_50/90 once, live_checker_submit t=chain:address, 404 path sanitised, DNT and http send nothing, fetch keepalive fallback",
          not failed_bk, f"{len(b_keys) - len([k for k in b_keys if res.get(k) is not True])}/{len(b_keys)}; failed {failed_bk[:4]}")
    f1_keys = ["pf_f1_stale_200_keeps_input_error", "pf_f1_previous_request_aborted", "pf_f1_no_abortcontroller_still_safe"]
    run_src = appjs[appjs.find("function run()"):appjs.find("form.addEventListener(\"submit\"", appjs.find("function run()"))]
    f1_static = run_src.find("++seq") != -1 and run_src.find("++seq") < run_src.find("problem(a)") and run_src.find(".abort()") < run_src.find("problem(a)")
    f1_static = f1_static and "ADDR_RE.test(a)" in appjs[appjs.find("function problem(a)"):appjs.find("function run()")]
    check("F1 regression: a pending valid pre-flight is superseded (seq bumped + AbortController.abort before validation); an invalid submit's error is never overwritten by the stale HTTP 200",
          f1_static and all(res.get(k) is True for k in f1_keys), f"static {f1_static}; {[k for k in f1_keys if res.get(k) is not True]}")

    # v4.2 staging build: python3 tools/build_site.py --base-path /website-test --out-dir <temp> builds a complete noindex copy for the
    # sub-path mount (https://pacta.dri.network/website-test/) and never touches docs/ or the repository
    import tempfile
    import urllib.parse as _upst

    def _tree_digest(d):
        out = {}
        for r_, _, fs_ in os.walk(d):
            for f_ in fs_:
                pth = os.path.join(r_, f_)
                out[os.path.relpath(pth, d)] = hashlib.sha256(open(pth, "rb").read()).hexdigest()
        return out
    st_ok, st_detail = {}, ""
    docs_before = _tree_digest(DOCS)
    tmp_root = tempfile.mkdtemp(prefix="pacta-staging-")
    try:
        out_st = os.path.join(tmp_root, "website-test")
        rc_st = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_site.py"), "--base-path", "/website-test", "--out-dir", out_st],
                               cwd=ROOT, capture_output=True, text=True, timeout=300)
        st = _tree_digest(out_st) if rc_st.returncode == 0 else {}
        html_st = {k: open(os.path.join(out_st, k), encoding="utf-8").read() for k in st if k.endswith(".html")}
        rootrel = [k for k, t in html_st.items() for u in re.findall(r'(?:href|src|action)="(/[^"]*)"', t) if not u.startswith(("/website-test/", "//"))]
        st_ok = {
            "build ok": rc_st.returncode == 0 and "staged:" in rc_st.stdout,
            "docs/ untouched": _tree_digest(DOCS) == docs_before,
            "same files as docs/ (+ marker)": set(st) - {".pacta-staging"} == set(docs_before),
            "non-HTML bytes identical (robots.txt disallows)": all(st[k] == docs_before[k] for k in st if not k.endswith(".html") and k not in (".pacta-staging", "robots.txt"))
                and open(os.path.join(out_st, "robots.txt")).read() == "User-agent: *\nDisallow: /\n",
            "every page noindex, nofollow": bool(html_st) and all(re.findall(r'<meta name="robots" content="([^"]*)">', t) == ["noindex, nofollow"] for t in html_st.values()),
            "every page records the base path": all('<html lang="en" data-base-path="/website-test">' in t for t in html_st.values()),
            "0 root-relative links outside /website-test/": not rootrel,
            "no beacon in staging": not any(re.search(r'<script src="[^"]*b\.js"', t) for t in html_st.values()),
            "404 links + assets prefixed": all(x_ in html_st.get("404.html", "") for x_ in ('href="/website-test/protocols/"', 'href="/website-test/styles.css?v=',
                                                                                 'src="/website-test/app.js?v=', 'href="/website-test/fonts/inter-latin-wght-normal.woff2"')),
            "/pricing/ resolves to /website-test/#pricing": (lambda m: bool(m) and _upst.urljoin("https://pacta.dri.network/website-test/pricing/", m.group(1)) == "https://pacta.dri.network/website-test/#pricing")(
                re.search(r'<meta http-equiv="refresh" content="0; url=([^"]+)">', html_st.get(os.path.join("pricing", "index.html"), ""))),
            "canonical docs/ stays indexable with no base path": not any("noindex, nofollow" in t or "data-base-path" in t
                                                                     for t in (open(p_, encoding="utf-8").read() for p_ in glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True))),
        }
        guard_dir = os.path.join(tmp_root, "not-staging")
        os.makedirs(guard_dir)
        open(os.path.join(guard_dir, "keep.txt"), "w").write("x")
        rc_guard = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_site.py"), "--base-path", "/website-test", "--out-dir", guard_dir],
                                  cwd=ROOT, capture_output=True, text=True, timeout=120)
        rc_docs = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_site.py"), "--base-path", "/website-test"], cwd=ROOT, capture_output=True, text=True, timeout=120)
        st_ok["refuses a non-staging out-dir and a base path on docs/"] = (rc_guard.returncode != 0 and os.path.exists(os.path.join(guard_dir, "keep.txt"))
                                                                          and rc_docs.returncode != 0 and _tree_digest(DOCS) == docs_before)
        st_ok["harness: runtime links follow the base path"] = all(res.get(k) is True for k in ("v42_base_path_catalog_link", "v42_base_path_rejects_bad_values",
                                                                                           "v421_base_path_rejects_dot_segments", "v421_base_path_allows_dotted_names"))
        # v4.2.1 D1: no standalone "." / ".." segment in a base path (Python validator + CLI), dotted names still valid
        bad_bp = ("/..", "/.", "/website-test/../../evil", "/website-test/.")
        dot_out = os.path.join(tmp_root, "dot-segment")
        rc_dot = [subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_site.py"), "--base-path", bp_, "--out-dir", dot_out],
                                 cwd=ROOT, capture_output=True, text=True, timeout=120).returncode for bp_ in ("/..", "/website-test/../../evil")]
        st_ok["D1: '.' / '..' base-path segments refused (validator + CLI), /release.v4 allowed"] = (
            not any(BS.valid_base_path(x_) for x_ in bad_bp) and BS.valid_base_path("/release.v4") and BS.valid_base_path("/website-test")
            and all(r_ != 0 for r_ in rc_dot) and not os.path.exists(dot_out))
        # v4.2.1 D2: symlinks are resolved before any containment check, marker or delete: an alias of the repository (and of docs/)
        # is refused and docs/ stays byte-identical (the test never writes inside the repository)
        alias = os.path.join(tmp_root, "alias-to-repo")
        os.symlink(ROOT, alias)
        rc_alias = [subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_site.py"), "--base-path", "/website-test", "--out-dir", t_],
                                   cwd=ROOT, capture_output=True, text=True, timeout=120).returncode
                    for t_ in (os.path.join(alias, "docs"), os.path.join(alias, "staging-inside-repo"), alias)]
        st_ok["D2: realpath containment refuses repo / docs aliases, paths inside the repo and its ancestors; docs/ untouched"] = (
            all(r_ != 0 for r_ in rc_alias) and BS.staging_target(os.path.join(alias, "docs"))[1] is not None
            and BS.staging_target(os.path.dirname(os.path.realpath(ROOT)))[1] is not None   # an ancestor of the repo: checked without running
            and BS.staging_target(os.path.join(tmp_root, "elsewhere"))[1] is None and _tree_digest(DOCS) == docs_before
            and not os.path.exists(os.path.join(ROOT, "staging-inside-repo")))
        # v4.3 N2: every staging page (and only staging pages) carries one subtle banner line right after the skip link
        banner_st = BS.staging_banner("/website-test")
        canon_html = [open(p_, encoding="utf-8").read() for p_ in glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)]
        st_ok["N2: one staging banner per staged page (after the skip link); none on docs/, which ships index, follow"] = (
            banner_st == ('<div class="staging-banner" role="note" data-staging-banner>Staging preview (/website-test/) · robots=noindex on this '
                          'test route; production pacta.wtf ships index, follow.</div>')
            and bool(html_st) and all(t.count("data-staging-banner") == 1 and (banner_st in t or ("styles.css" not in t and BS.staging_banner("/website-test", True) in t))
                                      for t in html_st.values())
            and all(BS.SKIP_LINK + "\n" + banner_st in t for t in html_st.values() if BS.SKIP_LINK in t)
            and not any("data-staging-banner" in t for t in canon_html)
            and all(re.findall(r'<meta name="robots" content="([^"]*)">', pages[r_])[0].startswith(
                        "noindex" if r_ in ("404.html", os.path.join("pricing", "index.html")) else "index, follow")
                    for r_ in pages if r_.endswith(".html") and '<meta name="robots"' in pages[r_]))
        st_detail = f"{len(html_st)} staged pages; root-relative {rootrel[:3]}; build rc {rc_st.returncode} {rc_st.stderr[-160:]}"
    finally:
        import shutil as _sh_st
        _sh_st.rmtree(tmp_root, ignore_errors=True)
    check("v4.2 staging build (--base-path /website-test --out-dir): complete noindex, nofollow copy with prefixed root links, no beacon, "
          "robots disallow, /pricing/ -> /website-test/#pricing; docs/ untouched and canonical pages unchanged; unsafe out-dirs refused",
          all(st_ok.values()) and bool(st_ok), f"{[k for k, x in st_ok.items() if not x]}; {st_detail}")

    # v4.3: the auditor re-check of /website-test/ (N1-N7); N2 is part of the staging-build check above
    home43, req43, meth43 = pages["index.html"], pages[os.path.join("request", "index.html")], pages[os.path.join("methodology", "index.html")]
    css43, app43 = read("docs/styles.css"), read("tools/app.src.js")

    def css_rule(sel):
        i_ = css43.find(sel + " {")
        return css43[i_:css43.index("}", i_)] if i_ >= 0 else ""

    def pricing43(t):
        sec = re.search(r'<section class="sec" id="pricing">.*?</section>', t, re.S)
        return sec.group(0) if sec else ""

    def plans43(t):
        return re.findall(r'<div class="(plan(?: plan-row)?(?: feat)?)" data-slot="card" data-plan="([\w-]+)">', pricing43(t))
    rad43 = json.loads(read("docs/api/v1/radar.json"))
    rh_a = home43.find('<div class="radar-head">')
    rhead = home43[rh_a:home43.find('<div class="tbl-wrap">', rh_a)] if rh_a >= 0 else ""
    rhead_txt = re.sub(r"<[^>]+>", " ", rhead)
    chips43 = re.findall(r'<button class="receipt"[^>]*data-receipt data-pf-chain="(ethereum|base)" data-pf-address="(0x[0-9a-fA-F]{40})"', home43)

    def ref_html(pre):
        return (f'<p class="note" data-referral>When code changes are needed, Pacta can refer teams to independent smart-contract auditors; '
                f'under our <a href="{pre}methodology/#independence">Independence Policy</a>, referrals never influence docs-vs-chain status.</p>')
    meth_ind = re.search(r'<section class="memo-sec" id="independence">.*?</section>', meth43, re.S)
    meth_ind = meth_ind.group(0) if meth_ind else ""
    executed43 = any(all(o.get("done") for o in it["operations"]) for it in rad43["items"])
    v43 = {
        "N1: 3 'Try:' examples carry chain + address; one click fills #pf-form, clears the error and runs one live check rendered under the form (harness)":
            len(chips43) == 3 and "tryReceipt(b);" in app43 and '$$("[data-pf-address]").forEach' not in app43
            and 0 < home43.find('id="pf-form"') < home43.find("data-receipt") < home43.find('id="pf-out"')   # v4.4 F3a: examples above the result
            and all(res.get(k) is True for k in ("v43_n1_try_fills_and_runs", "pf_preset_fetches_once", "v_hero_click_fetches")),
        "N1 robustness: every init starts on its own (a simulated early failure leaves the examples working and is still reported); 0 init errors (harness)":
            all(res.get(k) is True for k in ("v43_init_isolation", "v43_no_init_errors")),
        "N3 (v2): one 4-column self-serve grid ($19 scan featured; 2 x 2 tablet, 1 column phone), equal-height cards with every CTA on one baseline (the free card's MCP link row reserved in each card), badges as opaque tabs (/ and /request/)":
            all(plans43(t) == [("plan", "free"), ("plan feat", "instant-scan-19"), ("plan", "radar-webhook-49"), ("plan", "reverify-seal-99")] for t in (home43, req43))
            and "grid-template-columns: repeat(4, minmax(0, 1fr))" in css_rule(".plans") and "align-items: stretch;" in css_rule(".plans")
            and "display: flex; flex-direction: column;" in css_rule(".plan") and "margin-top: auto; display: grid; grid-template-rows: auto 24px;" in css_rule(".plan-cta")
            and "position: absolute;" in css_rule('.plan > [data-slot="badge"]') and "background: var(--card);" in css_rule('.plan > [data-slot="badge"]'),
        "N4: the audience cards do not stretch to equal height (align-items: start)": "align-items: start;" in css_rule(".aud"),
        "N5: radar counts 'Executed (N ops)' (never '(N operations)'); the radar header cites only the finalized read (one block per chain) (+ harness)":
            BS.radar_counts_text(rad43) in rhead and "operations)" not in rhead
            and ("Executed (" in BS.radar_counts_text(rad43)) == executed43
            and sorted(re.findall(r"\d{1,3}(?:,\d{3}){2,}", rhead_txt)) == sorted(f'{p_["block_number"]:,}' for _, p_ in BS.radar_pins(rad43))   # v4.6: one per chain
            and f'finalized block <a href="https://etherscan.io/block/{rad43["refreshed_at"]["block_number"]}"' in rhead
            and res.get("v43_n5_radar_header_one_block") is True and res.get("pp2_radar_counts") is True,
        "N6: the #how-it-works step grid is a reset list (no inline-start padding), flush with the h2":
            '<section class="sec" id="how-it-works">' in home43 and all(x_ in css_rule(".steps") for x_ in ("list-style: none;", "margin: 0;", "padding: 0;")),
        "N7: the auditor-referral note is its own line under the cards, linked to /methodology/#independence (which discloses the 15% terms); "
        "the vulnerability route no longer mentions referrals":
            "referral" not in BS.VULN_ROUTE and "15%" not in BS.VULN_ROUTE
            and ref_html("") in pricing43(home43) and ref_html("../") in pricing43(req43)
            and all(0 <= pricing43(t).find("data-editorial") < pricing43(t).find("data-pricing") < pricing43(t).find("data-referral") for t in (home43, req43))
            and not any("15%" in pricing43(t) for t in (home43, req43))
            and "15% referral partnership" in meth_ind and html.escape(BS.EDITORIAL_FIREWALL, quote=False) in meth_ind
            and "Referrals never influence docs-vs-chain status" in meth_ind
            and sorted(r_ for r_, t in pages.items() if re.search(r"15% referral|referral partnership", t)) == [os.path.join("methodology", "index.html")]
            and f"{BS.REFERRAL_NOTE} Independence policy: https://pacta.wtf/methodology/#independence" in read("docs/llms.txt"),
    }
    check("v4.3 auditor re-check (N1 Try examples run the live check, N3 pricing rows + 3 cards, N4 no stretched card, N5 'Executed (N ops)' + "
          "one header block, N6 flush How it works, N7 referral note linked to the independence policy)", all(v43.values()),
          str([k for k, x in v43.items() if not x]))

    # v4.4: internal review round 1 (screenshot and interaction review): R-V1..R-V4, P1-2, P2-1, P2-2
    idx44 = {e["id"]: e for e in json.loads(read("docs/api/v1/index.json"))["entries"]}
    chips44 = {m.group(3): (m.group(1), m.group(2)) for m in re.finditer(
        r'data-receipt data-pf-chain="(ethereum|base)" data-pf-address="(0x[0-9a-fA-F]{40})" data-r-name="([^"]+)"', home43)}
    want44 = {lbl: BS.LIVE_CHECK_TARGET.get(slug, (BS.chain_of(idx44[rid]), idx44[rid]["target_contract"])) for slug, rid, lbl, *_ in BS.RECEIPTS}
    glyph_pages = sorted(r_ for r_, t in pages.items()
                         if re.search("[\u2192\u2197]", re.sub(r"<[^>]+>", "", re.sub(r"<script.*?</script>", "", t[t.find("<body"):], flags=re.S))))
    arrows44 = sum(t.count('<svg class="i ia" viewBox="0 0 24 24" aria-hidden="true">') for t in pages.values())
    v44 = {
        "R-V1a: 'Try: Stader ETHx' checks the ETHx proxy (EIP-1967, timelocked admin; listed on the Stader record page); YO and Moonwell check their record targets":
            chips44.get("Stader ETHx") == ("ethereum", BS.HERO_EXAMPLE[2]) == BS.LIVE_CHECK_TARGET["stader-labs-ethx"]
            and BS.HERO_EXAMPLE[2] in pages[os.path.join("protocols", "stader-labs-ethx", "index.html")]
            and all(chips44.get(lbl) == (BS.chain_of(idx44[rid]), idx44[rid]["target_contract"]) for slug, rid, lbl, *_ in BS.RECEIPTS if slug not in BS.LIVE_CHECK_TARGET)
            and len(chips44) == 3,
        "R-V1b: verdict, metrics, then the indexed record with its Docs-vs-chain badge; one visible scope sentence; methodology and limits collapsed (harness)":
            res.get("v44_live_card_verdict_first") is True and "Methodology & single-address scope limits" in app43,
        "R-V3: the Try examples wrap at narrow widths (no swipe row, no clipped chip)":
            "  .try-row { flex-wrap: wrap; gap: 6px 8px; }" in css43 and "scroll-snap-type" not in css43 and "mask-image" not in css43,
        "R-V2: long radar identifiers break inside their mobile card":
            "  table.radar td, table.radar .op, table.radar .sub, table.radar .meta { overflow-wrap: anywhere; word-break: break-word; min-width: 0; }" in css43,
        "P1-2 / R5: every pre in a card or tab panel wraps (pre-wrap + overflow-wrap: anywhere)":
            '[data-slot="card"] pre, [data-slot="tabs-content"] pre { white-space: pre-wrap; overflow-wrap: anywhere;' in css43
            and "white-space: pre-wrap; overflow-wrap: anywhere;" in css_rule(".term pre"),
        "R-V4: 0 raw U+2192 / U+2197 in the visible text of every HTML page and in app.js; link arrows are inline aria-hidden Lucide icons":
            not glyph_pages and not re.search("[\u2192\u2197\u2713\u2260]", read("docs/app.js")) and arrows44 > 0
            and "svg.ia { width: 0.875em; height: 0.875em; margin-left: 0.25em; vertical-align: -0.125em; }" in css43
            and res.get("v44_runtime_link_arrow_icon") is True,
        "P2-1: the checker help line says the examples run a check too (v4.7: and that a protocol or token name finds its scorecard)":
            '<p class="checker-cap" id="pf-help">Free, read-only check — select or type a protocol or token (Aave, Lido, Pendle, Moonwell, LBTC, ETHx), '
            'or paste any 0x… contract address. No API key, no wallet. Runs when you press Check or pick an example below.</p>' in home43,
        "P2-2: a Try click scrolls the form (input + result) into view, clear of the sticky top bar (harness)":
            res.get("v44_try_scrolls_form") is True and "scroll-margin-top: 72px;" in css_rule(".checker"),
        "F3a: the Try examples sit between the checker and its result (a result never pushes them off screen) (harness)":
            0 < home43.find('id="pf-form"') < home43.find('<div class="try">') < home43.find('id="pf-out"')
            and res.get("v44_examples_between_form_and_result") is True,
        "F3b: the result card shows no raw enum (classification, controller kind) outside the raw JSON (harness)":
            res.get("v44_no_raw_enums_in_result") is True and 'Object.prototype.hasOwnProperty.call(CTL_LABEL, k)' in app43,
        "F5: after a live radar read the provenance pill says 'Live-checked · #<block>' and the livebar drops its pinned note (harness)":
            re.search(r'<span class="badge final" data-prov-pill>Scanner-pinned \(L1( \+ Base)? finalized\)</span>', home43) is not None   # v4.6: + Base
            and all(res.get(k) is True for k in ("v44_radar_live_pill", "v44_radar_pill_stays_pinned_offline")),
        "F6: the /request/ scope brief no longer repeats the address; 'Copy brief and address' prefixes it; secondary actions are outline":
            res.get("v44_request_brief_no_to") is True
            and f'id="req-copy" data-copy-from="req-brief" data-copy-prefix="To: {BS.CONTACT}"' in pages[os.path.join("request", "index.html")],
    }
    check("v4.4 review round 1 (R-V1 Stader ETHx proxy + verdict-first card, R-V2 radar wrap, R-V3 wrapping Try examples, R-V4 icon arrows, "
          "P1-2 code wrap, P2-1 help copy, P2-2 scroll to the form, F3a examples above the result, F3b no raw enums, F5 live radar pill, "
          "F6 request brief)", all(v44.values()),
          f"{[k for k, x in v44.items() if not x]}; chips {chips44}; want {want44}; raw-arrow pages {glyph_pages[:4]}; icons {arrows44}")

    # v4.5: consolidated review round 2 (R2-01..R2-06, G-P1-1, G-P1-3, G-P2-1..G-P2-9, OpenAPI sync)
    def lum45(h):
        h = h.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def cr45(a, b):
        la, lb = sorted((lum45(a), lum45(b)), reverse=True)
        return (la + 0.05) / (lb + 0.05)

    def tok45(block, name):
        m = re.search(r"--" + re.escape(name) + r":\s*(#[0-9a-fA-F]{6})", block)
        return m.group(1) if m else "#000000"
    light45 = css43[css43.index(":root {"):css43.index("}", css43.index(":root {"))]
    dark45 = css43[css43.index(".dark {"):css43.index("}", css43.index(".dark {"))]
    demo45 = read("docs/demos/swapio-x402/index.html")
    demo_css = demo45[demo45.index("<style>"):demo45.index("</style>")]
    clamps45 = [(int(a), int(b)) for a, b in re.findall(r"font(?:-size)?:\s*clamp\((\d+)px,[\d.]+vw,(\d+)px\)", demo45)]
    scale45 = {12, 14, 16, 18, 20, 24, 30, 36, 48}
    sc45 = {c["slug"]: c for c in json.loads(read("docs/api/v1/scorecards.json"))["protocols"]}
    req45, terms45 = pages[os.path.join("request", "index.html")], pages[os.path.join("terms", "index.html")]
    desc45 = lambda t: html.unescape(re.search(r'<meta name="description" content="([^"]*)"', t).group(1))
    radar45 = pages[os.path.join("radar", "index.html")]
    nums45 = BS.site_numbers(json.loads(read("docs/api/v1/index.json")))
    readme45, remed45 = read("README.md"), read("REMEDIATION_SERVICES.md")
    gen_html45 = {r_: t for r_, t in pages.items() if r_.endswith(".html") and not r_.startswith(os.path.join("demos", ""))}
    # item 16: the cards are 1200x675 PNGs, one per protocol page (+ the radar cards the feed names)
    import struct as _st45
    cards45 = {os.path.basename(c_)[:-4]: open(c_, "rb").read(24) for c_ in glob.glob(os.path.join(DOCS, "cards", "*.png"))
               if not os.path.basename(c_).startswith("x-card-")}
    proto_slugs45 = {r_.split(os.sep)[1] for r_ in pages if r_.startswith("protocols" + os.sep) and r_.count(os.sep) == 2}
    card_ok45 = (bool(cards45) and proto_slugs45 <= set(cards45)
                 and all(b[:8] == b"\x89PNG\r\n\x1a\n" and _st45.unpack(">II", b[16:24]) == (1200, 675) for b in cards45.values()))
    try:
        xf45, xh45 = json.loads(read("docs/api/v1/x-feed.json")), json.loads(read("docs/api/v1/x-handles.json"))
        kind_grade = {"adverse_delta": "delta", "protective_delta": "protective", "aligned_baseline": "aligned", "rpc_observed": "observed"}
        sc_g45 = {c["slug"]: c["grade"] for c in json.loads(read("docs/api/v1/scorecards.json"))["protocols"]}
        prot_items = [i for i in xf45["items"] if i.get("kind") in kind_grade]
        xfeed_ok45 = (xf45["schema"] == "pacta.x_feed.v1" and xh45["schema"] == "pacta.x_handles.v1"
                      and all(os.path.exists(os.path.join(DOCS, "cards", i["cardFilename"])) for i in xf45["items"])
                      and sorted(i["slug"] for i in prot_items) == sorted(sc_g45) and all(sc_g45[i["slug"]] == kind_grade[i["kind"]] for i in prot_items)
                      and all(xf45["counts"][k] == sum(g == v for g in sc_g45.values()) for k, v in kind_grade.items())
                      and sorted(p_["slug"] for p_ in xh45["protocols"]) == sorted(sc_g45)
                      and not re.search(r"[/]home[/]|[.]tmp[/]", read("docs/api/v1/x-feed.json") + read("docs/api/v1/x-handles.json")))
    except (KeyError, ValueError, TypeError, OSError):
        xfeed_ok45 = False
    v45 = {
        "R2-01: /protocols/ headers wrap below 640 px with the cells' padding (no clipped 'Docs vs chain')":
            "  #proto-table th { white-space: normal; padding: 10px 6px;" in css43,
        "R2-02: the Light 'S' rosette dot is >= 4.5:1 (white on the strong green); Dark keeps its own pair":
            ".fdot.r-g { background: var(--rosette-strong); color: #fff; }" in css43 and cr45("#ffffff", tok45(light45, "rosette-strong")) >= 4.5
            and ".dark .fdot.r-g { color: #052e16; }" in css43 and cr45("#052e16", tok45(dark45, "rosette-strong")) >= 4.5,
        "R2-03: editable controls use --input-border, >= 3:1 against the card and the page in Light and Dark":
            "border: 1px solid var(--input-border); border-radius: var(--radius);" in css43
            and all(cr45(tok45(b, "input-border"), tok45(b, k)) >= 3.0 for b in (light45, dark45) for k in ("card", "background")),
        "R2-04: /demos/swapio-x402/: every clamp ends on the type scale (12-48 px), disclaimer >= 12 px and >= 4.5:1, controls in their own row below 640 px":
            bool(clamps45) and all(a >= 12 and b in scale45 for a, b in clamps45)
            and ".foot { position:absolute; left:7%; right:7%; bottom:7%; font-size:clamp(12px,1.2vw,14px); color:var(--mute); }" in demo_css
            and cr45(re.search(r"--mute:(#[0-9a-f]{6})", demo_css).group(1), re.search(r"--bg:(#[0-9a-f]{6})", demo_css).group(1)) >= 4.5
            and ".scene { inset:0 0 48px 0; }" in demo_css and "#clock, #ctl { bottom:10px; }" in demo_css
            and not re.search(r"font-size:\s*0?\.\d+em", demo_css),   # no fractional-em sizes that fall between the scale steps
        "R2-05: the radar explanation cards keep their natural height (align-items: start)": "align-items: start;" in css_rule(".cases"),
        "R2-06: the tier is 'Continuous Control-Plane Monitoring' everywhere (site, generator, app.js, README, REMEDIATION, issue template)":
            all('<b>Continuous Control-Plane Monitoring</b>' in t for t in (home43, req43))
            and not any(re.search(r"Continuous Monitoring", read(f)) for f in ["README.md", "REMEDIATION_SERVICES.md", ".github/ISSUE_TEMPLATE/request-scan.yml",
                                                                             "tools/build_site.py", "tools/app.src.js", "docs/app.js", "docs/llms.txt"])
            and not any("Continuous Monitoring" in t for t in pages.values()),
        "G-P1-1: @pacta_fractal: twitter:site on every generated page, JSON-LD sameAs, top-bar X link, footer Company link":
            all('<meta name="twitter:site" content="@pacta_fractal">' in t for t in gen_html45.values())
            and BS.X_URL in BS.ORG_LD["sameAs"] and 'href="https://x.com/pacta_fractal" target="_blank" rel="noopener" aria-label="Pacta on X (@pacta_fractal, opens in a new tab)"' in home43
            and '<a href="https://x.com/pacta_fractal" target="_blank" rel="noopener">X (@pacta_fractal)</a>' in home43,
        "G-P1-3: every Try target (and every record address) is in its protocol's search index, scorecards.json and the /request/ combobox (+ harness)":
            all(a.lower() in sc45[slug]["search"] for slug, (_, a) in BS.LIVE_CHECK_TARGET.items())
            and all(BS.chain_of(e) and e["target_contract"].lower() in sc45[BS.protocol_slug(e["protocol"])]["search"]
                    for e in json.loads(read("docs/api/v1/index.json"))["entries"])
            and 'data-q="' in req43 and BS.HERO_EXAMPLE[2].lower() in req43
            and all(res.get(k) is True for k in ("v45_search_finds_try_addresses", "v45_combobox_prefix_address_click")),
        "G-P2-1: the Free card and the /request/ community track say 'free, with live re-check on demand'":
            "free, with live re-check on demand" in pricing43(home43) and "stays free, with live re-check on demand" in req43,
        "G-P2-2: 'Heuristic score' in the checker, limits link to /methodology/#live-checker, which explains the heuristic and the delta counts (+ harness)":
            '"Heuristic score"' in app43 and "Risk score" not in app43 and '<section class="memo-sec" id="live-checker">' in meth43
            and f'{nums45["delta"]} of the {nums45["protocols"]} protocols carry at least one adverse docs-vs-chain delta' in meth43
            and res.get("v45_live_checker_link") is True,
        "G-P2-3: combobox ranks prefix matches first, matches 0x addresses, a mouse pick closes it (aria-expanded=false) and clears the query (harness)":
            res.get("v45_combobox_prefix_address_click") is True,
        "G-P2-4 / G-P2-7 (v4.7 W1): the 8-row preview shows in full below 640 px (no row kept back); /radar/ lists the operations above the legend":
            len(re.findall(r'<tr class="sc-row sc-m"', home43)) == 0 and "#scorecards tbody:not([data-all]) tr.sc-row.sc-m { display: none; }" in css43
            and res.get("v45_mobile_six_then_all") is True
            and 0 < radar45.find('<table class="tbl radar">') < radar45.find('<div class="cases"'),
        "G-P2-5: the teams card shows a real badge and its one-line Markdown embed":
            re.search(r'class="teams-card".*?<img class="cp-badge" src="badges/aave-v3-gho.svg"[^>]*>.*?Copy the Markdown badge embed', home43, re.S) is not None,
        "G-P2-6: catalogMatch lines <= 140 characters and threshold lines name their Safe (harness: 'Matched: Security Council Safe threshold 3-of-5')":
            res.get("v45_catalog_lines") is True,
        "G-P2-8: /request/ description 150-160 characters, /terms/ about 115":
            150 <= len(desc45(req43)) <= 160 and 105 <= len(desc45(terms45)) <= 125,
        "G-P2-9: README and REMEDIATION_SERVICES carry the site's tiers and counts":
            all(x in readme45 and x in remed45 for x in ("$500", "$2,500–$5,000", "$1,500 USDC / month", "Continuous Control-Plane Monitoring"))
            and f'**{nums45["protocols"]} protocols ({nums45["eas_protocols"]} Base-EAS attested + {nums45["observed"]} RPC-observed)' in readme45
            and f'**{nums45["protocols"]} protocols ({nums45["eas_protocols"]} Base-EAS attested + {nums45["observed"]} RPC-observed)**' in remed45
            and "flat" not in remed45 and "$5,000 USDC` flat" not in readme45,
        "OpenAPI: the published snapshot (docs/api/v1/openapi.json) carries the Worker's /v1/x-feed":
            "/v1/x-feed" in json.loads(read("docs/api/v1/openapi.json"))["paths"],
        "16: every protocol page shares its own 1200x675 card (og:image + twitter:image); other pages use og-preview.png or their own 1200x628 social card":
            card_ok45 and all(
                f'<meta property="og:image" content="https://pacta.wtf/cards/{slug}.png">' in t
                and '<meta property="og:image:width" content="1200">' in t and '<meta property="og:image:height" content="675">' in t
                and f'<meta name="twitter:image" content="https://pacta.wtf/cards/{slug}.png">' in t
                for slug, t in ((r_.split(os.sep)[1], t) for r_, t in pages.items() if r_.startswith("protocols" + os.sep) and r_.count(os.sep) == 2))
            and '<meta property="og:image" content="https://pacta.wtf/og-preview.png">' in home43 and '<meta property="og:image:height" content="628">' in home43,
        "16: docs/api/v1/x-feed.json + x-handles.json mirror /v1/x-feed: every item's card exists, kinds match the grades, counts match the data":
            xfeed_ok45,
    }
    check("v4.5 round 2 (R2-01..R2-06 geometry / contrast / charter name, G-P1-1 @pacta_fractal, G-P1-3 address search, G-P2-1..G-P2-9 copy, "
          "combobox, mobile order, badge, catalog lines, meta lengths, repo docs; OpenAPI /v1/x-feed; 16 receipt cards + x-feed mirror)", all(v45.values()),
          str([k for k, x in v45.items() if not x]))

    # v4.5.1: neutral Aligned badges, the demo receipt link target, one line reconciling the delta tiles
    import build_lookup as LK451
    badges451 = {os.path.basename(b_): open(b_, encoding="utf-8").read() for b_ in glob.glob(os.path.join(DOCS, "badges", "*.svg"))}
    aligned451 = [t for t in badges451.values() if "Aligned · Base EAS" in t]
    al_col = LK451.BADGE_TIERS["aligned"][1]
    rgb451 = [int(al_col[i:i + 2], 16) for i in (1, 3, 5)]
    n451 = BS.site_numbers(json.loads(read("docs/api/v1/index.json")))
    line451 = (f'<p class="delta-line" data-delta-line>{n451["delta"] + n451["protective"]} of {n451["protocols"]} protocols differ from their docs: '
               f'{n451["delta"]} adverse, {n451["protective"]} protective.</p>')
    v451 = {
        "R3-01: every Aligned SVG badge is neutral (no #047857 / green anywhere in the badges; white on the Aligned fill >= 7.5:1)":
            bool(aligned451) and not any("#047857" in t for t in badges451.values())
            and all(f'fill="{al_col}"' in t for t in aligned451) and cr45("#ffffff", al_col) >= 7.5 and max(rgb451) - min(rgb451) <= 40,
        "R3-02: the demo receipt link is >= 24 px tall (inline-flex, min-height 24px; script unchanged)":
            ".live-receipt a { display:inline-flex; align-items:center; min-height:24px;" in demo_css,
        "'N of M protocols differ from their docs: D adverse, P protective.' under the homepage tiles and the /scorecards/ intro (from the data)":
            line451 in home43 and line451 in pages[os.path.join("scorecards", "index.html")]
            and home43.find('data-proof>') < home43.find(line451) and "<span>Deltas</span><small>Adverse: chain looser than docs</small>" in home43,
    }
    check("v4.5.1 polish (R3-01 neutral Aligned badges, R3-02 demo receipt link target, '36 of 90' reconciliation line)", all(v451.values()),
          str([k for k, x in v451.items() if not x]))

    # v4.6: multi-chain radar (Ethereum + Base; the Cap / Compound V3 refresh: 11 items / 17 ops), decoded pre-execution briefs (8: Sprint 28's 6 + Cap
    # and Compound V3), one receipt card per protocol + radar cards + x-feed mirror
    rad46 = json.loads(read("docs/api/v1/radar.json"))
    home46, radar46 = pages["index.html"], pages[os.path.join("radar", "index.html")]
    base46 = [it for it in rad46["items"] if it.get("chain_id") == 8453]
    new46 = ["lombard-ops-0xceee-0x2f2a-0x6404", "beefy-base-op-0x3302", "ethena-ops-0xb028-0xca05-0x108e-0x070a", "yearn-v3-op-0x2a14",
             "etherfi-liquid-op-0xf0fb", "lombard-op-0xd07f", "cap-op-0x3397", "compound-v3-op-0x86b4", "lista-lending-op-0x21df"]
    dec46 = json.loads(read("tools/briefs_decoded.json"))
    dec_by46 = {b_["slug"]: b_ for b_ in dec46["briefs"]}
    briefs46 = {sl: pages.get(os.path.join("briefs", sl, "index.html"), "") for sl in new46}
    lk46 = {x["slug"]: x for x in json.loads(read("docs/api/v1/lookup.json"))["items"]}
    rb46, r46 = rad46.get("refreshed_at_base") or {}, rad46["refreshed_at"]
    cards46 = [c_ for c_ in glob.glob(os.path.join(DOCS, "cards", "*.png")) if not os.path.basename(c_).startswith("x-card-")]
    xf46 = json.loads(read("docs/api/v1/x-feed.json"))
    rad46n = sum(1 for i_ in xf46["items"] if i_.get("kind") == "radar_timelock")      # radar operations the feed posts (active ones)
    beefy46 = briefs46["beefy-base-op-0x3302"]

    def ann46(it_, st_):   # a synthetic copy of an item with every operation in state st_ (banner wording)
        return {**it_, "eta": None if st_ == "executed" else it_["eta"],
                "operations": [{**o_, "done": st_ == "executed", "pending": st_ != "executed", "ready": st_ == "ready"} for o_ in it_["operations"]]}
    v46 = {
        "radar.json: 12 items / 18 ops (Lista refresh: 2 ready (ether.fi Liquid 0xf0fb + Lombard 0xd07f, matured, unexecuted), 5 pending (5 ops, Lista 0x21df among them), 0 mixed, executed (11 ops), Beefy on Base + Treehouse, the Lombard upgrades and both Ethena items executed); refreshed_at (Ethereum) + refreshed_at_base (Base)":
            len(rad46["items"]) == 12 and sum(len(it["operations"]) for it in rad46["items"]) == 18
            and [BS.item_state(it) for it in rad46["items"]].count("ready") == 2 and [BS.item_state(it) for it in rad46["items"]].count("pending") == 5
            and sum(len(it["operations"]) for it in rad46["items"] if BS.item_state(it) == "ready") == 2
            and sum(len(it["operations"]) for it in rad46["items"] if BS.item_state(it) == "pending") == 5
            and [BS.item_state(it) for it in rad46["items"]].count("mixed") == 0
            and sum(len(it["operations"]) for it in rad46["items"] if BS.item_state(it) == "executed") == 11
            and {it["brief"] for it in rad46["items"] if BS.item_state(it) == "ready"} == {"briefs/etherfi-liquid-op-0xf0fb/", "briefs/lombard-op-0xd07f/"}
            and all(BS.item_state(it) == "executed" for it in base46)
            and r46["tag"] == rb46.get("tag") == "finalized" and len(base46) == 1 and all(it.get("protocol_slug") and it.get("chain_id") in (1, 8453) for it in rad46["items"]),
        "counts text '2 ready · 5 pending · Executed (11 ops)' on / and /radar/":
            BS.radar_counts_text(rad46) == "2 ready · 5 pending · Executed (11 ops)"
            and all("data-radar-counts>2 ready · 5 pending · Executed (11 ops)</span>" in t for t in (home46, radar46)),
        "Base items link Basescan (never Etherscan) for the timelock on / and /radar/, carry a 'Base' tag, and the Base brief has 0 etherscan.io links":
            all(f'https://basescan.org/address/{it["timelock"]}' in t and f'etherscan.io/address/{it["timelock"]}' not in t and f'etherscan.io/address/{it["timelock"].lower()}' not in t
                and '<span class="chain-tag">Base</span>' in t for it in base46 for t in (home46, radar46))
            and beefy46.count("https://basescan.org/") >= 10 and "etherscan.io" not in beefy46
            and "Base Mainnet (chain id 8453)" in beefy46 and "Scanner-pinned (Base finalized)" in beefy46
            and f"Executed on Base by Finalized Block #{rb46['block_number']:,}" in beefy46
            and f'https://basescan.org/block/{rb46.get("block_number")}' in beefy46,
        "radar-live provenance names both pins (Ethereum #26,436,571-style and Base #58,747,369-style) on / and /radar/":
            all(f'Ethereum finalized block <a href="https://etherscan.io/block/{r46["block_number"]}" target="_blank" rel="noopener">#{r46["block_number"]:,}' in t
                and f'Base finalized block <a href="https://basescan.org/block/{rb46["block_number"]}" target="_blank" rel="noopener">#{rb46["block_number"]:,}' in t
                for t in (home46, radar46)),
        "post-ETA banner + brief header on Base: 'Executed on Base' / 'Unexecuted on Base at Finalized Block #N' (never 'on L1')":
            all(f"Unexecuted on Base at Finalized Block #{rb46['block_number']:,}" in BS.post_eta_banner(ann46(it, "ready"), rb46, "base")
                and f"Executed on Base by Finalized Block #{rb46['block_number']:,}" in BS.post_eta_banner(ann46(it, "executed"), rb46, "base")
                and "on L1" not in BS.post_eta_banner(ann46(it, "ready"), rb46, "base") for it in base46)
            and "on L1" not in beefy46,
        "9 decoded briefs: rendered from tools/briefs_decoded.json (every op id, call, risk note and reproduce command), in BRIEFS / BRIEF_PROTOCOL, sitemap, llms.txt, lookup.json + lookup.mjs":
            dec46["schema"] == "pacta.decoded_briefs.v1" and sorted(dec_by46) == sorted(new46)
            and all(sl in BS.BRIEFS and BS.BRIEF_PROTOCOL[sl] == dec_by46[sl]["protocol_slug"] for sl in new46)
            and all(all(o_["op_id"] in briefs46[sl] for o_ in dec_by46[sl]["operations"])
                    and briefs46[sl].count('<li><code>') == sum(len(o_["calls"]) for o_ in dec_by46[sl]["operations"])
                    and all(_html.escape(n_) in briefs46[sl] for n_ in dec_by46[sl]["risk_notes"])
                    and all(_html.escape(c_, quote=True) in briefs46[sl] for c_ in dec_by46[sl]["reproduce"])
                    and f"<loc>{BS.BASE_URL}/briefs/{sl}/</loc>" in read("docs/sitemap.xml") and f"{BS.BASE_URL}/briefs/{sl}/" in read("docs/llms.txt")
                    and sl in lk46 and lk46[sl]["relatedProtocolSlug"] == dec_by46[sl]["protocol_slug"]
                    and (lk46[sl]["chain"], lk46[sl]["chainId"]) == (("base", 8453) if dec_by46[sl]["chain_id"] == 8453 else ("ethereum", 1))
                    and f'"slug":"{sl}"' in read("packages/mcp-server/src/lookup.mjs") for sl in new46),
        f"{X['protocols'] + rad46n} receipt cards (1200x675 PNG: one per protocol + {rad46n} radar operations of the feed) + docs/api/v1/x-feed.json ({X['protocols'] + rad46n} items) whose every card exists":
            len(cards46) == X["protocols"] + rad46n and len([c_ for c_ in cards46 if os.path.basename(c_).startswith("radar-")]) == rad46n
            and len(xf46["items"]) == X["protocols"] + rad46n and all(os.path.exists(os.path.join(DOCS, "cards", i_["cardFilename"])) for i_ in xf46["items"]),
        "homepage within its 150,000 B budget (compact radar rows; /radar/ keeps summaries, labels, copy buttons and the timelock list)":
            len(read("docs/index.html").encode()) < 150000 and '<ul class="oplabels">' in radar46 and '<ul class="oplabels">' not in home46,
        "app.js keeps live blocks per chain (an Ethereum block is never compared with a Base block) (harness)":
            "blk[ch] = Math.floor(n)" in appjs and res.get("v46_live_blocks_per_chain") is True,
    }
    check(f"v4.6 multi-chain radar (12 items / 18 ops, Basescan for chain id 8453, two-chain provenance, 'on Base' wording), 9 decoded briefs, {X['protocols'] + rad46n} cards",
          all(v46.values()), str([k for k, x in v46.items() if not x]))

    # v4.7 W1-W5 (external UX evaluation quick wins)
    home47, bnt47 = pages["index.html"], pages[os.path.join("bounties", "index.html")]
    sc47 = {c["slug"]: c for c in json.loads(read("docs/api/v1/scorecards.json"))["protocols"]}
    rad47 = json.loads(read("docs/api/v1/radar.json"))
    idx47 = json.loads(read("docs/api/v1/index.json"))
    top47 = {}
    for e_ in idx47["entries"]:
        top47[e_.get("chain", "ethereum")] = max(top47.get(e_.get("chain", "ethereum"), 0), int(e_["block_number"]))
    pill47 = (f'<p class="fresh" data-fresh><span class="dot" aria-hidden="true"></span><span>Pinned blocks: Ethereum #{top47["ethereum"]:,} · '
              f'Base #{top47["base"]:,} · {X["eas_attestations"]} Base EAS batches</span></p>')
    rpill47 = ("Radar pinned at finalized blocks: Ethereum #" + format(rad47["refreshed_at"]["block_number"], ",") + " · Base #"
               + format(rad47["refreshed_at_base"]["block_number"], ","))
    order47 = [sc47[s_]["grade"] for s_ in BS.FLAGSHIP]
    rank47 = {"delta": 0, "protective": 1, "aligned": 2, "observed": 3}
    topbar_pages47 = [t for t in pages.values() if 'class="topbar"' in t]
    v47 = {
        "W1: / previews 8 protocols in severity order (deltas first), 'Explore all N protocol scorecards' -> scorecards/, the radar strip -> #radar; "
        "/scorecards/ keeps all of them (harness)":
            len(re.findall(r'<tr class="sc-row"', home47)) == 8 and order47[0] == "delta" and order47 == sorted(order47, key=rank47.get)
            and len(re.findall(r'<tr class="sc-row"', pages[os.path.join("scorecards", "index.html")])) == X["protocols"]
            and 'data-tl-strip' in home47 and '<a href="#radar">See the queue' in home47 and res.get("v47_w1_preview") is True,
        "W2: #how-it-works = 2 shadcn Tabs (risk & diligence default, AI agents & builders): steps + rosette legend + Deltas / radar / dossier CTAs; "
        "MCP config, SKILL.md / llms.txt / OpenAPI pills, curl + cast (arrow keys, Home / End, link-to-tab: harness)":
            'role="tablist" aria-label="Choose your audience"' in home47 and 'id="hiw-t-risk" aria-controls="hiw-p-risk" aria-selected="true"' in home47
            and f'href="scorecards/?grade=delta">Deltas ({BS.site_numbers(idx47)["delta"]})</a>' in home47
            and all(f'href="{h}"' in home47 for h in ("SKILL.md", "llms.txt", "openapi.json")) and 'id="hiw-legend"' in home47
            and res.get("v47_w2_tabs") is True,
        "W3: a search trigger (Ctrl/Cmd+K, /) in the top bar of every page; Command dialog over lookup.json + scorecards.json (protocol, token, brief, 0x); "
        "the hero checker resolves names with Open scorecard / Run live check (harness)":
            all('data-cmdk-open' in t and 'aria-keyshortcuts="Control+K Meta+K /"' in t for t in topbar_pages47) and len(topbar_pages47) >= 100
            and 'maxlength="42"' not in home47 and f'placeholder="{html.escape(BS.HERO_PLACEHOLDER)}"' in home47
            and 'role="combobox"' in home47 and 'aria-controls="pf-listbox"' in home47
            and res.get("v47_w3_cmdk") is True and res.get("v47_w3_hero_names") is True
            and res.get("pf_combobox_select_and_autocomplete") is True
            and all(any(os.path.exists(os.path.join(DOCS, "assets", "protocols", f"{it_['slug']}.{ext_}")) and os.path.getsize(os.path.join(DOCS, "assets", "protocols", f"{it_['slug']}.{ext_}")) >= 60
                        for ext_ in ("webp", "png", "svg"))
                    for it_ in json.loads(read("docs/api/v1/lookup.json"))["items"] if it_.get("kind") == "protocol"),
        "W4: build-pinned freshness pill on /, /scorecards/, /protocols/ (index.json pins + EAS batches) and /radar/ (radar pins); /bounties/ leads with "
        "Wave 2, the closed Nov 15 Wave 1 collapsed at the bottom; 0 '53 currently indexed' anywhere in docs/":
            all(pill47 in pages[r_] for r_ in ("index.html", os.path.join("scorecards", "index.html"), os.path.join("protocols", "index.html")))
            and rpill47 in pages[os.path.join("radar", "index.html")]
            and not [f_ for f_ in glob.glob(os.path.join(DOCS, "**", "*"), recursive=True) if os.path.isfile(f_) and not f_.endswith(".png")
                     and "53 currently indexed" in open(f_, encoding="utf-8", errors="ignore").read()]
            and re.search(r'<details class="archive-details" id="wave-1-archive" data-wave1-archive><summary>', bnt47) is not None
            and bnt47.find('id="wave-3"') < bnt47.find('id="quickstart"') < bnt47.find('id="wave-2-archive"') < bnt47.find('id="wave-1-archive"') < bnt47.find('id="wave-1"')
            and bnt47.find('id="issues"') < bnt47.find("</details>\n</article>"),
        "W5: the theme button is labelled (current choice, synced aria-label) >= 768 px; the mobile sheet has a Light / Dark / System row (harness)":
            all('<span class="tb-l" data-theme-label>Theme</span>' in t and t.count("data-theme-sheet>") == 3 for t in topbar_pages47)
            and ".theme-btn .tb-l { position: absolute; width: 1px;" not in read("docs/styles.css").split("@media (max-width: 767px)")[0]
            and res.get("v47_w5_theme_label") is True,
        "radar refreshed at current finalized blocks (Ethereum + Base, after the Beefy ETA); counts from the data":
            rad47["refreshed_at"]["block_number"] > 26436571 and rad47["refreshed_at_base"]["block_number"] > 58747369
            and f'data-radar-counts>{html.escape(BS.radar_counts_text(rad47))}</span>' in home47,
    }
    check("v4.7 quick wins (W1 8-row preview + radar strip, W2 audience tabs, W3 Cmd+K search + hero names, W4 freshness pill + Wave 1 archive, "
          "W5 labelled theme toggle) + refreshed radar", all(v47.values()), str([k for k, x in v47.items() if not x]))
    css471 = read("docs/styles.css")
    v471 = {
        "V47-01: the audience tabs share one grid cell once JavaScript runs (inactive panel invisible, inert, aria-hidden; stacked without JavaScript)":
            'data-tabs data-tabs-stable><div data-slot="tabs-list" role="tablist" aria-label="Choose your audience">' in home47
            and ".js [data-tabs-stable] > [data-slot=\"tabs-content\"] { grid-row: 2; grid-column: 1; min-width: 0; }" in css471
            and ".js [data-tabs-stable] > [data-slot=\"tabs-content\"][data-inactive] { display: block; visibility: hidden; pointer-events: none; }" in css471
            and 'p.setAttribute("inert", ""); p.setAttribute("aria-hidden", "true");' in appjs and res.get("v471_tabs_inert") is True,
        "V47-02: the command input paints a 2 px inset --ring outline on :focus-visible (both themes)":
            ".cmdk-head input:focus-visible { outline: 2px solid var(--ring); outline-offset: -2px; box-shadow: none; }" in css471
            and ".cmdk-head input:focus, .cmdk-head input:focus-visible { outline: none" not in css471,
        "V47-03: ?basket= keeps underscores (exact <option> values): stable_rwa 69, eth_lst_lrt 46, lending_vaults 121, base 33; combined with ?grade= and ?q= (harness)":
            "replace(/[^a-z0-9-]/g" not in appjs and res.get("v471_basket_urls") is True,
    }
    check("v4.7.1 review fixes (V47-01 stable audience-tab height, V47-02 command-input focus ring, V47-03 basket URLs with underscores)",
          all(v471.values()), str([k for k, x in v471.items() if not x]))

    # protocol pages: every EAS-attested record card links its own Base EAS attestation; RPC-pinned pages carry none
    sp_eas = BS.site_protocols(json.loads(read("docs/api/v1/index.json")))
    eas_bad = []
    for v_ in sp_eas.values():
        pg_ = pages.get(os.path.join("protocols", v_["slug"], "index.html"), "")
        if v_["pinned"]:
            if "base.easscan.org/attestation/view/" in pg_:
                eas_bad.append(v_["slug"])
        elif not all(f'<dt>Attestation</dt><dd><a href="https://base.easscan.org/attestation/view/{e_["base_eas_uid"]}" target="_blank" rel="noopener">'
                     f'Base EAS attestation {BS.short(e_["base_eas_uid"])}' in pg_ for e_ in v_["entries"]):
            eas_bad.append(v_["slug"])
    n_eas_pages = sum(1 for v_ in sp_eas.values() if not v_["pinned"])
    check(f"protocol pages: every Base-EAS-attested record card links its attestation ({n_eas_pages} pages, short UID text, full UID in href); "
          "RPC-pinned pages carry 0 base.easscan.org attestation links", n_eas_pages > 0 and not eas_bad, str(eas_bad[:6]))

    # /protocols/ basket filters and /scorecards/ basket counts never diverge: every row's data-pbaskets set equals scorecards.json
    sc_bk = {c_["slug"]: set(c_["baskets"]) for c_ in json.loads(read("docs/api/v1/scorecards.json"))["protocols"]}
    pidx_rows = re.findall(r'<tr data-ptier="[^"]*" data-pchains="[^"]*" data-pbaskets="([^"]*)"[^>]*><td><a href="([a-z0-9-]+)/">',
                           pages[os.path.join("protocols", "index.html")])
    bk_bad = [slug_ for bks_, slug_ in pidx_rows if set(bks_.split()) != sc_bk.get(slug_, {"<missing>"})]
    check(f"/protocols/ basket parity: all {len(pidx_rows)} rows carry exactly their scorecards.json baskets (data-pbaskets set equality)",
          len(pidx_rows) == len(sc_bk) == X["protocols"] and not bk_bad, str(bk_bad[:6]))

    nf = pages.get("404.html", "")
    nf_raw = nf.encode()
    nf_h, nf_b = nf_raw.find(b"<head>"), nf_raw.find(b"<body")
    nf_tw = nf_raw.find(b">", nf_raw.find(b'name="twitter:image"')) + 1
    nf_ok = {
        "head budget": bool(nf) and 0 <= nf_b < 3000 and 0 < nf_tw - nf_h <= 1200 and "<style" not in nf and "data:image/" not in nf,
        "noindex + data-nf": f'<meta name="robots" content="{BS.ROBOTS_META_404}">' in nf[:nf_b] and re.search(r'<main id="main"[^>]* data-nf>', nf) is not None,
        "root-relative navigation": all(f'href="{h}"' in nf for h in ("/protocols/", "/#scorecards", "/request/", "/llms.txt")) and 'href="/styles.css?v=' in nf and 'src="/b.js"' in nf
                                    and not re.search(r'(?:href|src)="(?!/|https://|#)', nf),
        "remote MCP URL + copy": f'data-copy="{MCP_}"' in nf and f"claude mcp add --transport http pacta {MCP_}" in nf,
        "deterministic build": nf == BS.not_found_page(idx_),
        "not in sitemap": "/404.html" not in sm,
    }
    check("404.html: same head rules (<body> < 3000 B, OG/X in 1.2 KB, no inline style), noindex, root-relative links to /protocols/ and /#scorecards, remote MCP URL, fires not_found_404 (harness), deterministic",
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
        want_ai.setdefault(f'{BS.chain_of(e)}:{e["target_contract"].lower()}', BS.protocol_family(e["protocol"]))   # own chain (Sprint 17: Base records)
    for e in sorted(pinned_["entries"], key=lambda e: e["id"]):               # RPC-pinned targets + paired protocol contracts, own chain
        for a in (e["target_contract"], e.get("paired_contract")):
            if a:
                want_ai.setdefault(f'{e["chain"]}:{a.lower()}', BS.protocol_family(e["protocol"]))
    fd_ok = {
        "schema": fd.get("schema") == "pacta.forum_digest.v1" and fd.get("readOnly") is True and isinstance(fd.get("forums"), dict)
                  and isinstance(fd.get("discussions"), list) and list(fd) == ["schema", "generatedAt", "readOnly", "forums", "discussions", "addressIndex"],
        "addressIndex": ai == want_ai and list(ai) == sorted(ai) and all(re.fullmatch(r"(ethereum|base):0x[0-9a-f]{40}", k) for k in ai)
                        and all(re.fullmatch(r"[a-z0-9]+", v) for v in ai.values()),
        "families": BS.protocol_family("Aave V3 / GHO") == "aave" and BS.protocol_family("Morpho Blue Core") == "morpho"
                    and BS.protocol_family("MetaMorpho (Re7 WETH vs. Re7 USDT)") == "morpho" and BS.protocol_family("Spark / Sky") == "sky"
                    and BS.protocol_family("Lido (stETH / Dual Governance)") == "lido" and BS.protocol_family("Compound V3 (Comet)") == "compound",
        "deterministic rebuild": fd_raw == BS.forum_digest_json(idx_, src_digest, pinned_) == BS.forum_digest_json(idx_, json.loads(json.dumps(src_digest)), pinned_),
        "no wall clock": "datetime" not in BS.forum_digest_json.__code__.co_names and "now" not in BS.forum_digest_json.__code__.co_names,
    }
    gov_pages = sorted(r for r, t in pages.items() if "Active governance discussions" in t)
    expect_gov = sorted(os.path.join("protocols", v["slug"], "index.html") for n, v in site_.items() if BS.governance_discussions(n, src_digest))
    check(f"forum-digest.json (pacta.forum_digest.v1): readOnly, deterministic addressIndex for all {len(want_ai)} index + RPC-pinned targets (chain:lowercase address -> family); governance sections only where the family has discussions",
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
                                             and "io.github.Fractal-Neurons/pacta" in wf.split("\nname:", 1)[0],
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
        "stdio CMD as USER node, no ENTRYPOINT / EXPOSE": 'CMD ["node", "/app/bin/pacta-mcp.mjs"]' in df and re.search(r"^USER node$", df, re.M) is not None
                                                       and not re.search(r"^ENTRYPOINT", df, re.M) and "EXPOSE" not in df and "RUN npm" not in df,
        "no Smithery": "smithery" not in df.lower() and "smithery" not in wf.lower() and "smithery" not in nf.lower(),
    }
    check("root Dockerfile (glama.ai mcp-proxy): node:22-alpine, copies only packages/mcp-server, PACTA_X402_URL = live gateway, USER node + CMD [node, /app/bin/pacta-mcp.mjs] (no ENTRYPOINT), no EXPOSE",
          all(df_ok.values()), str({k: v for k, v in df_ok.items() if not v}))
    readme = read("README.md")
    priv = readme[readme.find("## Analytics & privacy"):][:1800] if "## Analytics & privacy" in readme else ""
    check("README: Analytics & privacy note (first-party b.js beacon, Do Not Track, observed client metadata, and host-gated X uwt.js rjbqn disclosure)",
          bool(priv) and all(t in priv for t in ("first-party", "cookie", "Do Not Track", "observed client metadata", "/v1/telemetry/beacon", "uwt.js", "rjbqn")))

    priv_html = pages.get(os.path.join("privacy", "index.html"), "")
    ftr_pages = {r_: t_ for r_, t_ in pages.items() if 'class="ftr"' in t_}
    xp_keys = ["x_pixel_host_gate", "x_pixel_lead_dedup", "x_pixel_purchase_rules"]
    check("X Pixel (rjbqn) + honest privacy/footer disclosure: host-gated uwt.js on pacta.wtf / pacta.fractalneurons.com (in-memory __pactaTwqEvents on staging), "
          "Lead tw-rjbqn-rjhie once/page, Purchase tw-rjbqn-rjhif on verified non-canary non-replay orders, accurate footer & /privacy/ copy",
          all(res.get(k_) is True for k_ in xp_keys)
          and bool(ftr_pages)
          and all("First-party telemetry stores aggregate counts without raw IPs; X Ads conversion measurement (uwt.js) runs on public pages" in t_
                  and "no cookies, no IP stored" not in t_ for t_ in ftr_pages.values())
          and all(tok_ in priv_html for tok_ in ("static.ads-twitter.com/uwt.js", "rjbqn", "tw-rjbqn-rjhie", "tw-rjbqn-rjhif",
                                                 "analytics.twitter.com", "t.co", "pacta-x-purchased"))
          and "no third-party trackers" not in priv_html and "The site sets no cookies" not in priv_html,
          f"xp_failed {[k_ for k_ in xp_keys if res.get(k_) is not True]}")

    fc_raw = read("docs/.well-known/farcaster.json") if os.path.exists(os.path.join(DOCS, ".well-known", "farcaster.json")) else "{}"
    fc_doc = json.loads(fc_raw)
    fc_ma = fc_doc.get("miniapp") if isinstance(fc_doc, dict) else {}
    fc_aa = fc_doc.get("accountAssociation") if isinstance(fc_doc, dict) else {}
    ma_png_path = os.path.join(DOCS, "miniapp-preview.png")
    ma_png_b = open(ma_png_path, "rb").read() if os.path.exists(ma_png_path) else b""
    ma_png_ok = (len(ma_png_b) >= 24 and len(ma_png_b) <= 500 * 1024 and ma_png_b[:8] == b"\x89PNG\r\n\x1a\n"
                 and struct.unpack(">II", ma_png_b[16:24]) == (1200, 800))
    ma_html = pages.get(os.path.join("miniapp", "index.html"), "")
    scan_html = pages.get(os.path.join("scan", "index.html"), "")
    def valid_fc_embed(html_text):
        m_ = re.search(r'<meta name="fc:miniapp" content="([^"]+)">', html_text)
        if not m_:
            return False
        try:
            d_ = json.loads(html.unescape(m_.group(1)))
        except ValueError:
            return False
        act_ = (d_.get("button") or {}).get("action") or {}
        return (d_.get("version") == "1" and d_.get("imageUrl") == f"{BS.BASE_URL}/miniapp-preview.png"
                and (d_.get("button") or {}).get("title") == "Check Contract Safety"
                and act_.get("type") == "launch_miniapp" and act_.get("url") == f"{BS.BASE_URL}/miniapp/")
    ma_keys = ["ma_frame_ready_handshake", "ma_instant_verdicts", "ma_wallet_upgrade_19_and_99"]
    check("Base & Farcaster Mini-App: /.well-known/farcaster.json v1 manifest, 1200x800 (3:2 <=500KB) miniapp-preview.png, valid fc:miniapp meta on /miniapp/ & /scan/, "
          "embedded ready() postMessage + ALIGNED / ADVERSE DELTA / UNINDEXED checks + 1-tap $19/$99 Base USDC upgrades (harness)",
          isinstance(fc_ma, dict) and fc_ma.get("version") == "1" and fc_ma.get("name") == "Pacta Control-Plane Check"
          and fc_ma.get("homeUrl") == f"{BS.BASE_URL}/miniapp/" and fc_ma.get("splashBackgroundColor") == "#0a0b0d"
          and fc_ma.get("subtitle") == "Docs vs Chain DeFi Verdicts" and fc_ma.get("primaryCategory") == "developer-tools"
          and fc_ma.get("tags") == ["defi", "security", "base", "timelock", "x402"]
          and isinstance(fc_aa, dict) and set(fc_aa.keys()) >= {"header", "payload", "signature"}
          and ma_png_ok and valid_fc_embed(ma_html) and valid_fc_embed(scan_html)
          and 'id="ma-buy-scan"' in ma_html and 'id="ma-buy-seal"' in ma_html
          and all(res.get(k_) is True for k_ in ma_keys),
          f"ma_png {ma_png_ok}; embeds {valid_fc_embed(ma_html)}/{valid_fc_embed(scan_html)}; failed {[k_ for k_ in ma_keys if res.get(k_) is not True]}")

    ads_expected = (
        ("pacta-hypelab-728x90.png", (728, 90)),
        ("pacta-hypelab-300x250.png", (300, 250)),
        ("pacta-hypelab-320x50.png", (320, 50)),
        ("pacta-hypelab-1456x180.png", (1456, 180)),
        ("pacta-hypelab-600x500.png", (600, 500)),
        ("pacta-hypelab-640x100.png", (640, 100)),
        ("pacta-hypelab-640x200.png", (640, 200)),
        ("x-ad-1-docs-vs-chain.png", (1200, 675)),
        ("x-ad-2-five-keys.png", (1200, 675)),
        ("x-ad-3-vault-deposit-check.png", (1200, 675)),
        ("x-ad-4-paste-any-address.png", (1200, 675)),
    )
    ads_ok = True
    for ad_name, ad_dims in ads_expected:
        ad_src_p = os.path.join(ROOT, "tools", "ads", ad_name)
        ad_doc_p = os.path.join(DOCS, "assets", "ads", ad_name)
        if not (os.path.exists(ad_src_p) and os.path.exists(ad_doc_p)):
            ads_ok = False
            break
        b_src, b_doc = open(ad_src_p, "rb").read(), open(ad_doc_p, "rb").read()
        if b_src != b_doc or b_doc[:8] != b"\x89PNG\r\n\x1a\n" or len(b_doc) > 500 * 1024 or struct.unpack(">II", b_doc[16:24]) != ad_dims:
            ads_ok = False
            break
    check("HypeLab & X ad creatives persisted in tools/ads/ and emitted byte-identically to docs/assets/ads/ (7 HypeLab + 4 1200x675 X cards <= 500KB)", ads_ok)

    # private identifiers must never be published: compared by SHA-256 of lowercased tokens, so the
    # repository itself never contains the literal identifiers this check guards against
    # ================= Batch C (task-d40112b6b379) =================
    import build_lookup as BLC
    # C1: Glama mcp-proxy needs CMD (it replaces ENTRYPOINT); one maintainer; no stale "5 read-only tools" anywhere
    stale5 = sorted({os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "**", "*"), recursive=True)
                     if os.path.isfile(p) and "/.git/" not in p and "__pycache__" not in p and not p.endswith((".png", ".svg", ".pyc"))
                     and re.search(r"\b(?:5|five) read-only tools?\b", open(p, errors="replace").read(), re.I)
                     and os.path.relpath(p, ROOT) != "verify_site_v2.py"})
    c1 = {
        "Dockerfiles: USER node + CMD, no ENTRYPOINT line": all(
            re.search(r'^USER node$\n(?:.*\n)*?^CMD \["node", "/app/bin/pacta-mcp\.mjs"\]$', read(f), re.M) is not None and not re.search(r"^ENTRYPOINT", read(f), re.M)
            for f in ("Dockerfile", "packages/mcp-server/Dockerfile")),
        "glama maintainers": json.loads(read("glama.json"))["maintainers"] == ["pacta-fractal-neurons"],
        "6 + 1 remote / 10 + 1 stdio tools": "6 read-only inspection tools + 1 opt-in coverage/feature request tool (`pacta_submit_request`), led by `pacta_lookup_protocol`" in read("README.md")
            and "10 read-only inspection tools + 1 opt-in request tool" in read("README.md")
            and "`pacta_live_timelocks`" in read("README.md") and "6 read-only inspection tools led by pacta_lookup_protocol + 1 opt-in request tool" in read("smithery.yaml")
            and "Remote MCP (6 read-only inspection tools + 1 opt-in coverage/feature request tool (pacta_submit_request))" in home
            and "Remote MCP (6 read-only inspection tools + 1 opt-in coverage/feature request tool (pacta_submit_request))" in req_page,
        "no stale 5-tool strings": not stale5,
    }
    check("C1: root + package Dockerfile run as USER node with CMD [node, /app/bin/pacta-mcp.mjs] (Glama mcp-proxy), glama.json maintainers [pacta-fractal-neurons], 6 + 1 remote / 10 + 1 stdio tools everywhere, 0 stale '5 read-only tools' strings",
          all(c1.values()), f"{[k for k, v in c1.items() if not v]} stale {stale5[:4]}")

    # C2: post-ETA state from radar.json; READY never rendered as executed; live hydrate (harness)
    rad = json.loads(read("docs/api/v1/radar.json"))
    fin_ts = rad["refreshed_at"]["block_timestamp"]
    ready_ok = all(isinstance(o.get("ready"), bool) and o["ready"] == bool(o["pending"] and not o["done"] and (o["eta"] or 0) > 1 and fin_ts >= o["eta"])
                   for it in rad["items"] for o in it["operations"])
    want_state = {}
    for it in rad["items"]:
        for o in it["operations"]:
            want_state[o["op_id"]] = BS.op_state(o)
    badge_bad = []
    for rel, t in pages.items():
        for m in re.finditer(r'<span class="opstate (\w+)" data-opstate="(\w+)" data-ops="([^"]+)">([^<]+)</span>', t):
            sts = {want_state.get(i) for i in m.group(3).split()}
            exp = sts.pop() if len(sts) == 1 else "mixed"
            if not (m.group(1) == m.group(2) == exp and html.unescape(m.group(4)) == BS.OP_STATE_LABEL[exp]):
                badge_bad.append(rel)
    eth = pages.get(os.path.join("briefs", "ethena-ops-0x0ca0-0x1fe5", "index.html"), "")
    eth_ready = all(want_state[o["op_id"]] == "ready" for it in rad["items"] if it["brief"].endswith("ethena-ops-0x0ca0-0x1fe5/") for o in it["operations"])
    banner = re.search(r'<div class="poststatus (\w+)" id="post-eta-status".*?</div>', eth, re.S)
    live_keys = ["live_static_ready", "live_flips_executed", "live_mixed", "live_ready_kept", "live_failures_keep_static", "live_radar_row", "live_no_fetch_elsewhere",
                 # T1 (v4.1): a payload or JSON body resolving after the 9 s fallback leaves badges, counts and status unchanged; the guard aborts
                 "t1_late_payload_after_fallback_ignored", "t1_late_json_body_after_fallback_ignored"]
    c2 = {
        "refresh_radar computes ready": 'self.ts = int(fin["timestamp"], 16)' in read("tools/refresh_radar.py")
            and '"ready": bool(pending and not done and ts > 1 and ch.ts >= ts)' in read("tools/refresh_radar.py"),
        "radar.json ready consistent": ready_ok and rad["refreshed_at"]["block_number"] >= 26415856,
        "every state badge = radar state": not badge_bad,
        "Ethena: READY banner, never Executed": (not eth_ready) or (bool(banner) and banner.group(1) == "ready"
            and "READY · EXECUTABLE NOW" in banner.group(0) and f"Unexecuted on L1 at Finalized Block #{rad['refreshed_at']['block_number']:,}" in banner.group(0)
            and "24h Delay Elapsed" in banner.group(0) and "Post-ETA Live Status" in banner.group(0)
            and not re.search(r'data-opstate="executed"|>EXECUTED<|>Executed<', eth)),
        "no Executed label while done is false": not any(re.search(r'data-opstate="executed"|>EXECUTED<|>Executed at refresh<', t) for t in pages.values())
            or any(o["done"] for it in rad["items"] for o in it["operations"]),
        "live hydrate harness": all(res.get(k) is True for k in live_keys),
        # the only meta refresh is the one-shot /pricing/ -> /#pricing redirect stub (T5); no page reloads or polls live data
        "no reload / refresh": "location.reload" not in appjs and not any('http-equiv="refresh"' in t for r, t in pages.items() if r != os.path.join("pricing", "index.html")),
        # T1 (v4): one cleared fallback timer reveals the pinned state if the re-check never settles; never a polling loop
        "live block writes text only": (lambda b: bool(b) and not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|setInterval", b)
                                        and b.count("setTimeout(") == 1 and "clearTimeout(guard)" in b)(
            appjs[appjs.find("// ---- live timelock re-check"):appjs.find("// ---- first-party beacon hooks")]),
    }
    check("C2: radar.json carries ready (delay elapsed, unexecuted) at finalized block #26,415,856+; Ethena brief + #radar render READY · EXECUTABLE NOW (never Executed while done is false); app.js re-checks /v1/briefs/live-timelocks once (textContent only; failures keep the static state)",
          all(c2.values()), f"{[k for k, v in c2.items() if not v]} badges {badge_bad[:3]} live {[k for k in live_keys if res.get(k) is not True]}")

    # C3: 53 deterministic badges == the worker's badgeSvg (node), 3 truthful tiers, embed / explainer cards
    probe_b = ("import('" + os.path.join(ROOT, "packages", "mcp-server", "src", "lookup.mjs") + "').then((M) => process.stdout.write(JSON.stringify("
               "Object.fromEntries(M.LOOKUP_CATALOG.filter((x) => x.kind === 'protocol').map((x) => [x.slug, M.badgeSvg(x.slug)])))))")
    rb = subprocess.run([node_, "--input-type=module", "-e", probe_b], capture_output=True, text=True, timeout=60) if node_ else None
    js_badges = json.loads(rb.stdout) if rb and rb.returncode == 0 else {}
    svg_files = sorted(f for f in os.listdir(os.path.join(DOCS, "badges")) if f.endswith(".svg")) if os.path.isdir(os.path.join(DOCS, "badges")) else []
    tier_of = {v["slug"]: ("rpc_observed" if v["pinned"] else ("aligned" if BS.is_aligned_page(v["entries"]) else "parameter_delta")) for v in sp_lk.values()}
    card_bad = []
    for slug_, t in tier_of.items():
        pg = pages.get(os.path.join("protocols", slug_, "index.html"), "")
        md_ = f"[![Pacta Control Plane]({BS.BASE_URL}/badges/{slug_}.svg)]({BS.BASE_URL}/protocols/{slug_}/)"
        if t == "aligned":
            ok_ = 'id="embed-badge"' in pg and html.escape(md_) in pg and f'src="../../badges/{slug_}.svg"' in pg and 'id="badge-status"' not in pg \
                and f"{API_}/v1/badges/{slug_}.svg" in pg
        elif t == "parameter_delta":
            ok_ = 'id="badge-status"' in pg and f'href="../../request/?tier=clearance&amp;protocol={slug_}&amp;settlement=invoice"' in pg \
                and "Aligned · Base EAS" in pg and 'id="embed-badge"' not in pg
        else:   # RPC-observed: the slate status card with a copyable embed, and never an Aligned / Base EAS claim
            ok_ = 'id="embed-badge"' not in pg and 'class="memo-sec badge-card observed" id="badge-status"' in pg and html.escape(md_) in pg \
                and "Aligned · Base EAS" not in pg
        if t != "rpc_observed" and t == "parameter_delta" and html.escape(md_) not in pg:
            ok_ = False                                  # every published tier carries the copyable embed snippet
        if not ok_:
            card_bad.append(slug_)
    counts_ = {}
    for t in tier_of.values():
        counts_[t] = counts_.get(t, 0) + 1
    c3 = {
        "static badges (one per protocol)": svg_files == sorted(f"{s_}.svg" for s_ in tier_of),
        "== worker badgeSvg (node)": len(js_badges) == X["protocols"] == len(svg_files) and all(js_badges[s_] == read(f"docs/badges/{s_}.svg") for s_ in tier_of),
        "badge tiers (EXPECT)": counts_ == X["badge_tiers"]
            and all(("Aligned · Base EAS" if t == "aligned" else "Parameter Delta" if t == "parameter_delta" else "RPC-Observed") in read(f"docs/badges/{s_}.svg")
                    for s_, t in tier_of.items()),
        "RPC-observed never implies EAS": not any("EAS" in read(f"docs/badges/{s_}.svg") for s_, t in tier_of.items() if t == "rpc_observed"),
        "cards": not card_bad,
    }
    check(f"C3: {X['protocols']} deterministic /badges/<slug>.svg byte-identical to the worker's /v1/badges/<slug>.svg (badgeSvg); {X['badge_tiers']['aligned']} neutral Aligned · Base EAS, {X['badge_tiers']['parameter_delta']} amber Parameter Delta (protocol-level: any parameter / protective delta), {X['badge_tiers']['rpc_observed']} slate RPC-Observed (no EAS claim); embed card on aligned pages, clearance-to-Aligned explainer on delta pages, slate status card on RPC-observed pages; copyable Markdown / HTML embed on every page",
          all(c3.values()), f"{[k for k, v in c3.items() if not v]} cards {card_bad[:4]} tiers {counts_}")

    # C5: protocols.json, vault-factories page, sentinel-guard package, feeds + sitemap links, robots untouched
    pj = json.loads(read("docs/api/v1/protocols.json"))
    vf = pages.get(os.path.join("integrations", "vault-factories", "index.html"), "")
    sg = read("packages/sentinel-guard/contracts/PactaSentinelGuard.sol") if os.path.exists(os.path.join(ROOT, "packages", "sentinel-guard", "contracts", "PactaSentinelGuard.sol")) else ""
    c5 = {
        "protocols.json": pj.get("schema") == "pacta.protocols.v1" and pj["totals"]["protocols"] == X["protocols"] and pj["totals"]["easAttested"] == X["eas_protocols"]
            and pj["totals"]["rpcObserved"] == X["rpc_protocols"] and pj["totals"]["badgeTiers"] == counts_
            and BLC.protocols_json(sp_lk, BLC.build_items(sp_lk, onb_lk, rad_lk, BS.BRIEF_PROTOCOL)) == read("docs/api/v1/protocols.json")
            and all((p_["evidenceBasis"] == "rpc_observed") == (not p_["easAttested"]) and (p_["easAttested"] or (p_["documentationComparison"] == "not_assessed"
                     and p_["baseEasUids"] == [] and p_["classification"] == "rpc_observed")) for p_ in pj["protocols"]),
        "vault-factories page": bool(vf) and all(x in vf for x in ("Morpho Vault V2", "Euler EVK", "Veda (BoringVault), Lagoon, Upshift, Mellow", "PactaSentinelGuard",
            "../../api/v1/protocols.json", "never blocks a decrease", "not audited")) and 'rel="canonical" href="https://pacta.wtf/integrations/vault-factories/"' in vf,
        "sentinel-guard package": bool(sg) and "if (newCap <= currentCap) return;" in sg and "0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83" in sg
            and all(os.path.exists(os.path.join(ROOT, "packages", "sentinel-guard", f)) for f in ("foundry.toml", "README.md", "test/PactaSentinelGuard.t.sol",
                                                                                                   "contracts/interfaces/IPactaCommitmentRegistry.sol"))
            and 'src = "contracts"' in read("packages/sentinel-guard/foundry.toml") and "offline = true" in read("packages/sentinel-guard/foundry.toml"),
        "linked in llms / llms-full / /llms/ / sitemap": all(f"{BS.BASE_URL}/integrations/vault-factories/" in read(f) and f"{BS.BASE_URL}/api/v1/protocols.json" in read(f)
                                                           for f in ("docs/llms.txt", "docs/llms-full.txt", "docs/llms/index.html", "docs/sitemap.xml")),
        "robots.txt exact": read("docs/robots.txt") == "User-agent: *\nAllow: /\n\nSitemap: https://pacta.wtf/sitemap.xml\n" and len(read("docs/robots.txt").encode()) == 63,
    }
    check(f"C5: api/v1/protocols.json ({X['protocols']}: {X['eas_protocols']} eas_attested / {X['rpc_protocols']} rpc_observed not_assessed, badge tiers, Sprint ids + EAS UIDs, pinned surfaces) regenerates byte-identically; /integrations/vault-factories/; packages/sentinel-guard (never blocks a decrease); linked in llms.txt, llms-full.txt, /llms/, sitemap; robots.txt 63 B",
          all(c5.values()), str([k for k, v in c5.items() if not v]))

    # ================= Sprint 17 (task-6ea8c50607d1): multi-chain index.json records =================
    idx_mc = json.loads(read("docs/api/v1/index.json"))
    sp_mc = BS.site_protocols(idx_mc)
    slug_of = {e["id"]: v["slug"] for v in sp_mc.values() if not v["pinned"] for e in v["entries"]}
    lk_mc = {x["slug"]: x for x in json.loads(read("docs/api/v1/lookup.json"))["items"]}
    props_mc = json.loads(read("docs/api/v1/proposals.json"))["proposals"]
    mc_bad = []
    for e in idx_mc["entries"]:
        ch = BS.chain_of(e)
        rpc_, (_, xurl) = BS.CHAINS[ch][2], BS.EXPLORERS[ch]
        pg = pages.get(os.path.join("protocols", slug_of[e["id"]], "index.html"), "")
        if not (f'{xurl}/block/{e["block_number"]}"' in pg and f'{xurl}/address/{e["target_contract"]}"' in pg and f"--block {e['block_number']} --rpc-url &quot;{rpc_}&quot;" in pg):
            mc_bad.append(f'{e["id"]}: protocol page chain')
        in_sample = f'id="r-{e["id"]}"' in home       # static sample drawers; hydrated drawers are checked in the harness (pp2_hydrated_index)
        if (in_sample and f'{xurl}/block/{e["block_number"]}"' not in home) or ("chain" in e and e["rpc_env_var"] != rpc_):
            mc_bad.append(f'{e["id"]}: homepage drawer / rpc_env_var')
    for v in sp_mc.values():
        if not v["pinned"]:
            ch = BS.chain_of(v["entries"][0])
            x_ = lk_mc[v["slug"]]
            if (x_["chain"], x_["chainId"], x_["preflightArgs"]["chain"]) != (ch, BS.CHAIN_IDS[ch], ch):
                mc_bad.append(f'{v["slug"]}: lookup chain / chainId')
    by_id_mc = {e["id"]: e for e in idx_mc["entries"]}
    for p_ in props_mc:
        if p_.get("source_feed") == "/api/v1/index.json":
            chs = {BS.chain_of(by_id_mc[r]) for r in p_["source_record_ids"]}
            if chs != {p_["chain"]} or p_["chain_id"] != BS.CHAIN_IDS[p_["chain"]] or not all(f'--rpc-url "{BS.CHAINS[p_["chain"]][2]}"' in c for c in p_["repro_commands"]):
                mc_bad.append(f'{p_["proposal_id"]}: proposals chain')
    # docs/app.js castCmd (node) == build_site.cast_line for every record and for a synthetic Base clone of each
    clone = lambda e: {**e, "chain": "base", "rpc_env_var": "$BASE_RPC_URL"}
    sample = [e for e in idx_mc["entries"] if not e.get("extra_calls")]
    sample += [clone(e) for e in sample[:3]]
    a0 = appjs.index("  // A record's chain (index.json records without one are Ethereum Mainnet)")
    a1 = appjs.index("  function term(cmd, title", a0)
    js_cast = ("const recs = " + json.dumps(sample) + ";\n" + appjs[a0:a1] + "\nprocess.stdout.write(JSON.stringify(recs.map(castCmd)));")
    # the script embeds every record: fed on stdin (a single -e argument would exceed the 128 KiB per-argument limit, E2BIG)
    rc_ = subprocess.run([node_, "--input-type=module"], input=js_cast, capture_output=True, text=True, timeout=60) if node_ else None
    js_out = json.loads(rc_.stdout) if rc_ and rc_.returncode == 0 else None
    cast_ok = js_out == [BS.cast_line(e) for e in sample] and all("$BASE_RPC_URL" in c and "$ETH_RPC_URL" not in c for c in js_out[-3:])
    n_base = sum(BS.chain_of(e) == "base" for e in idx_mc["entries"])
    check(f"multi-chain index.json records ({n_base} on Base): protocol pages + homepage drawers link the record's own explorer (etherscan.io / basescan.org block + "
          "address) and cast with its RPC variable ($ETH_RPC_URL / $BASE_RPC_URL); lookup chain / chainId (1 / 8453) and preflightArgs follow the record; "
          "proposals.json chain_id + repro RPC follow the cross-referenced records; docs/app.js castCmd == build_site.cast_line (node), Base clones included",
          not mc_bad and cast_ok and n_base == X["base_records"], f"bad {mc_bad[:4]}; castCmd parity {cast_ok}")

    # staged Sprint bundles (tools/staged/sprint-<n>-records.json): consistent and attestable until the apply script stamps them
    st_bad = []
    for sp_path in sorted(glob.glob(os.path.join(ROOT, "tools", "staged", "sprint-*-records.json"))):
        stg = json.load(open(sp_path, encoding="utf-8"))
        rs, n_ = stg["records"], stg["sprint"]
        cl_ = [r["classification"] for r in rs]
        sha_ = "0x" + hashlib.sha256(read(stg["summary_doc"], "rb")).hexdigest()
        pins_ = {ch: (pv["block_number"], pv["block_hash"]) for ch, pv in stg["pins"].items()}
        if (str(n_) in idx_mc["onchain_anchoring"]["sprint_eas_attestations"] or any(e["sprint"] == n_ for e in idx_mc["entries"])
                or stg["summary_sha256"] != sha_ or any(r["summary_sha256"] != sha_ or r["summary_doc"] != stg["summary_doc"] for r in rs)
                or stg["eas"] != {"chainId": 1, "blockNumber": pins_["ethereum"][0], "blockHash": pins_["ethereum"][1],
                                  "verifiedCount": cl_.count("aligned_baseline") + cl_.count("protective_delta"),
                                  "driftCount": cl_.count("parameter_delta")}          # every Sprint: driftCount = parameter-delta records
                or ("drift_rescans" in stg and not (                                  # optional post-snapshot re-scan of earlier Sprints
                    stg["drift_rescans"]["block"] == pins_["ethereum"][0] and len(stg["drift_rescans"]["protocols"]) <= stg["drift_rescans"]["checks"]
                    and 0 <= stg["drift_rescans"]["drifted"] <= len(stg["drift_rescans"]["protocols"])
                    and f'{stg["drift_rescans"]["drifted"]} of {len(stg["drift_rescans"]["protocols"])}' in read(stg["summary_doc"])
                    and f'`{stg["drift_rescans"]["checks"]}` checks' in read(stg["summary_doc"])))
                or any(sl not in {e["slug"] for e in pinned_["entries"]} or stg.get("slug_overrides", {}).get(nm, BS.protocol_slug(nm)) != sl
                       or not any(r["protocol"] == nm for r in rs)
                       for sl, nm in ((sl, c_["name"] if isinstance(c_, dict) else c_) for sl, c_ in stg.get("converts_rpc_pinned", {}).items()))
                or any(r["base_eas_uid"] is not None or r["sprint"] != n_ or (r["block_number"], r["block_hash"]) != pins_[r["chain"]]
                       or r["rpc_env_var"] != BS.CHAINS[r["chain"]][2] or not eip55_ok(r["target_contract"])
                       or not repro_ok(r) for r in rs)
                or len({r["id"] for r in rs} | {e["id"] for e in idx_mc["entries"]}) != len(rs) + len(idx_mc["entries"])
                or str(pins_["ethereum"][0]) not in stg["summary_doc"] or not all(h_ in read(stg["summary_doc"]) for _, h_ in pins_.values())):
            st_bad.append(os.path.relpath(sp_path, ROOT))
    check("staged Sprint bundles (not yet indexed): summary SHA-256, EAS verified / drift counts (drift = parameter deltas; optional re-scan block / count stated in the summary), per-chain pins (number + hash, also in the summary), "
          "RPC variable, EIP-55 targets, complete cast reproduction (selector = keccak(signature), 0x-hex args, calldata), base_eas_uid null, ids disjoint from index.json",
          not st_bad, str(st_bad))

    # ================= Batch D3 + E1 (task-66ff0d53564a) =================
    import build_b2a_feeds as B2AV
    import verify_bounty_submission as VBS
    agent_docs = {f: read(f) for f in ("docs/llms.txt", "docs/llms-full.txt", "docs/llms/index.html", "docs/SKILL.md", "README.md", "tools/build_site.py",
                                       "packages/mcp-server/README.md", "packages/mcp-server/SKILL.md")}
    lds = [m for t in pages.values() for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S)]
    brand_hits = sorted(f for f, t in list(agent_docs.items()) + [("JSON-LD", "\n".join(lds))] if re.search(r"\bpacta\s+protocol", t, re.I))
    org = [o for o in (json.loads(x) for x in lds) if o.get("@type") == "Organization"]
    cov = BS.coverage_line(idx_)
    d3 = {
        "0 'Pacta Protocol' self-descriptions (llms, SKILL, README, build_site, JSON-LD)": not brand_hits,
        "disambiguation line in llms.txt / llms-full.txt / /llms/ / README": all(B2AV.DISAMBIGUATION in read(f) or html.escape(B2AV.DISAMBIGUATION, quote=False) in read(f)
                                                                              for f in ("docs/llms.txt", "docs/llms-full.txt", "docs/llms/index.html", "README.md", "docs/SKILL.md")),
        "Organization JSON-LD disambiguatingDescription (home + /llms/)": bool(org) and all(o["disambiguatingDescription"] == B2AV.DISAMBIGUATION for o in org)
            and '"disambiguatingDescription"' in read("docs/index.html") and '"disambiguatingDescription"' in read("docs/llms/index.html"),
        "coverage line from the data": cov == (f"{X['protocols']} protocols ({X['protocols'] - X['rpc_protocols']} Base-EAS attested + {X['rpc_protocols']} RPC-observed) · "
                                               f"{X['records']} attested checks across {len(idx_['onchain_anchoring']['sprint_eas_attestations'])} Base EAS batch attestations")
            and cov in read("README.md") and all(cov in t for r, t in pages.items() if 'class="ftr"' in t) and f"{cov}." in read("docs/llms.txt"),
        "0 stale 'Indexed Records' lines": not [r for r, t in pages.items() if "Indexed Records" in t] and "Indexed Records" not in read("README.md")
            and "Indexed Records" not in read("docs/llms.txt"),
        "6 + 1 remote / 10 + 1 stdio wording": all(B2AV.REMOTE_TOOLS_DOC in read(f) for f in ("docs/llms.txt", "docs/llms-full.txt", "docs/SKILL.md"))
            and all(B2AV.STDIO_TOOLS_DOC in read(f) for f in ("docs/llms.txt", "docs/llms-full.txt"))
            and not re.search(r"all read-only|Everything is read-only", read("docs/llms.txt") + read("docs/SKILL.md") + read("docs/llms-full.txt")),
        "mcp.json lists 7 remote tools + readOnly flags": man_["transport"]["tools"] == B2AV.REMOTE_TOOLS and len(B2AV.REMOTE_TOOLS) == 7
            and [t["name"] for t in man_["tools"] if not t["readOnly"]] == ["pacta_submit_request"],
        "radar: live note + each timelock on its own chain's explorer (Etherscan / Basescan)": "Every row is a live Ethereum Mainnet" in home
            and "timelock read, no demo data" in home
            and all(f'{BS.EXPLORERS[BS.radar_chain(it, rad)][1]}/address/{it["timelock"]}' in home for it in rad["items"])
            and f'https://etherscan.io/block/{rad["refreshed_at"]["block_number"]}' in home,
        "GitHub repo link in every header": all(re.search(r'<a class="gh"[^>]*href="' + re.escape(BS.REPO) + '"', t) for r, t in pages.items() if 'class="topbar"' in t),
        "MCP recipes (Claude Code / OpenAI Agents SDK / LangChain, <= 10 lines) in README + SKILL.md": all(code in read("README.md") and code in read("docs/SKILL.md")
                                                                                                         and len(code.splitlines()) <= 10 for _, _, code in B2AV.MCP_RECIPES)
            and [t for t, _, _ in B2AV.MCP_RECIPES] == ["Claude Code", "OpenAI Agents SDK (Python)", "LangChain (langchain-mcp-adapters)"],
        "/protocols/ filter: input + Docs vs chain (5), Chain (3) and Basket (5) groups, Clear all, active state, empty-state slot, data attrs on every protocol row":
            all(f'data-pfilter-status="{k}"' in hub_ for k in ("all", "delta", "protective", "aligned", "observed"))
            and all(f'data-pfilter-chain="{k}"' in hub_ for k in ("all", "ethereum", "base"))
            and all(x in hub_ for x in ('id="proto-clear"', 'id="proto-active"', 'id="proto-empty"', 'data-pgroup="status"', 'data-pgroup="chain"'))
            and 'id="proto-q"' in hub_ and len(re.findall(r'<tr data-ptier="(?:delta|protective|aligned|observed)" data-pchains="[a-z ]+" data-pbaskets="[a-z_ ]*" data-psearch="[^"]*">', hub_)) == X["protocols"]
            and all(f'data-pfilter-basket="{k}"' in hub_ for k in ["all"] + [b[0] for b in BS.BASKETS]),
        "/protocols/ filter: textContent / hidden only": (lambda m: bool(m) and not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|fetch\(", m.group(0)))(
            re.search(r"function initProtocolFilter\(\) \{.*?\n  \}\n", appjs, re.S)),
        "/protocols/ filter behaviour (harness): Status x Chain x search, Clear all, empty-state recovery": all(res.get(k) is True for k in (
            "pfilter_initial_all", "pfilter_pills_exact", "pfilter_status_x_chain", "pfilter_text_search", "pfilter_empty_prompt", "pfilter_recover_chain",
            "pfilter_inert", "pfilter_clear_all", "pfilter_reset")),
    }
    check("D3: v0.1.4 brand / RAG disambiguation (0 'Pacta Protocol', exact disambiguation line, Organization JSON-LD), data-derived coverage line, 6 + 1 / 10 + 1 tools, "
          "#radar live-mainnet note with Etherscan links, GitHub link in the header, MCP recipes, /protocols/ client-side filter (text only)",
          all(d3.values()), f"{[k for k, v in d3.items() if not v]} brand {brand_hits}")

    bounty = read("docs/bounties/index.html")
    bd = BS.load_bounties()
    tpl = read(".github/PULL_REQUEST_TEMPLATE/bounty_mismatch.md")
    links = {"README.md": read("README.md"), "docs/llms.txt": read("docs/llms.txt"), "docs/llms-full.txt": read("docs/llms-full.txt"),
             "docs/llms/index.html": read("docs/llms/index.html"), "docs/sitemap.xml": read("docs/sitemap.xml")}
    e1 = {
        "4 x $25 USDC = $100 USDC": [i["rewardUsdc"] for i in bd["issues"]] == [25] * 4 and bd["program"]["totalHardCapUsdc"] == 100
            and bounty.count('<td class="num">$25 USDC</td>') == 4 and "4 × $25 USDC = $100 USDC" in bounty and "Total hard cap: <b>$100 USDC</b>" in bounty,
        "sprint Nov 15 – Nov 22, 2026 (168 h exactly)": "Nov 15 – Nov 22, 2026" in bounty and bd["program"]["sprintWindow"] == "2026-11-15T00:00:00Z to 2026-11-22T00:00:00Z"
            and bd["program"]["sprintWindow"] in bounty and BS.bounty_hours(bd["program"]) == 168 and "Nov 15 00:00 UTC – Nov 22 00:00 UTC, 2026" in bounty and ", 168h)" in bounty
            and hashlib.sha256(read("tools/bounty_issues.json", "rb")).hexdigest() == "874df3fd179ad241e3f2e4a7e837e9aa07f462a8a842b25fb1803049a6b84954",
        "issues #21-#24 via BOUNTY_ISSUE_URLS": BS.BOUNTY_ISSUE_URLS == {n: f"https://github.com/Fractal-Neurons/pacta/issues/{20 + n}" for n in (1, 2, 3, 4)}
            and all(f'href="{u}"' in bounty for u in BS.BOUNTY_ISSUE_URLS.values()),
        "slot scopes": all(html.escape(v) in bounty for v in BS.BOUNTY_SLOTS.values()),
        "issue text verbatim (titles + bodies; v4.7 W4: the Nov 15 index size reads as historical)": all(html.escape(i["title"], quote=False) in bounty
                                                                                                          and BS.wave1_md(i["body"]) in bounty for i in bd["issues"])
            and BS.wave1_md(bd["issues"][3]["body"]) != BS.md_html(bd["issues"][3]["body"]),
        "truthful payout (receipt/1827), treasury an EOA, never a Safe": BS.BOUNTY_PAYOUT == (
            "Paid in USDC on Base Mainnet within 48h of maintainer merge from Pacta treasury (0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14) once the winner "
            "comments their public Base 0x... address on the merged PR. Funds are not pre-escrowed in an automated contract; zero automatic on-chain payouts.")
            and BS.BOUNTY_TITLE == "Pacta Chain-Feed Mismatch Challenge ($100 USDC Hard-Cap · 7-Day Sprint Nov 15 – Nov 22, 2026)"
            and html.escape(BS.BOUNTY_PAYOUT, quote=False) in bounty
            and "externally owned account (EOA)" in bounty and not re.search(r"0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14.{0,160}\b(?:Safe|multisig)\b", bounty, re.S),
        "quickstart + Apache-2.0 + rules": f"claude mcp add --transport http pacta {BS.MCP_URL}" in bounty and "Apache-2.0" in bounty
            and all(html.escape(k, quote=False) in bounty for k, _ in BS.BOUNTY_RULES) and len(BS.BOUNTY_PROOF) == 6,
        "linked: README, llms.txt, llms-full.txt, /llms/, sitemap, nav + footer": all("https://pacta.wtf/bounties/" in t for t in links.values())
            and all('bounties/">Bounties</a>' in t for r, t in pages.items() if 'class="topbar"' in t and 'class="ftr"' in t),
        "robots.txt exact 4 lines / 63 B": read("docs/robots.txt") == BS.ROBOTS_TXT and len(read("docs/robots.txt").encode()) == 63 and len(read("docs/robots.txt").splitlines()) == 4,
        "PR template: 6 sections + Apache-2.0 box": all(h in tpl for h in ("## 1. chainId & contract address", "## 2. Pinned finalized block", "## 3. Deterministic dual-RPC cast proof",
                                                                       "## 4. Live official documentation claim (HTTP 200)", "## 5. Pacta MCP output",
                                                                       "## 6. Apache-2.0 contribution & commercialization grant"))
            and "- [ ] " + VBS.GRANT in tpl and "blockHash" in tpl and "--block <blockNumber>" in tpl,
        "validator self-test + empty template rejected": VBS.self_test() and len(VBS.validate(VBS.parse_body(tpl))) >= 10,
        "canonical fixture path + agent-assisted eligibility (#23 addendum)": "bounties/submissions/slot-&lt;slot&gt;-&lt;protocol-slug&gt;.json" in bounty
            and "bounties/submissions/slot-<slot>-<protocol-slug>.json" in tpl and os.path.exists(os.path.join(ROOT, "bounties", "submissions", "README.md"))
            and all(k in read("bounties/submissions/README.md") for k in VBS.FIELDS_JSON)
            and "--json bounties/submissions/slot-<slot>-<protocol-slug>.json" in read("bounties/submissions/README.md")
            and all("Human, agent-assisted, and autonomous-agent submissions are equally eligible under the exact same deterministic dual-RPC archive replay" in t
                    for t in (bounty, read("bounties/submissions/README.md")))
            and "Agent-assisted &amp; autonomous-agent submissions welcome" in bounty,
    }
    check("E1: pacta.wtf/bounties/ ($100 USDC hard cap = 4 x $25 USDC, Nov 15 – Nov 22, 2026, issues #21-#24, issue text verbatim, truthful post-merge Base USDC payout "
          "from the Pacta treasury EOA, Apache-2.0, rules), linked everywhere; PR template + deterministic validator (self-test); robots.txt 63 B",
          all(e1.values()), str([k for k, v in e1.items() if not v]))

    # ================= Wave 2: 100 x $1 USDC pool + Wave 1 Genesis ledger + /leaderboard/ + hunter badges + CI gate =================
    import stamp_wave1_payouts as SWP
    from xml.sax.saxutils import escape as xesc
    w2cfg = json.loads(read("tools/bounty_wave2.json"))
    w3cfg = json.loads(read("tools/bounty_wave3.json"))
    lb_ = BS.load_leaderboard()
    claims_ = BS.load_wave2_claims()
    claims3_ = BS.load_wave3_claims()
    n_claims = len([f_ for f_ in os.listdir(os.path.join(ROOT, "bounties", "wave-2")) if f_.endswith(".json")])
    prots_all_ = json.loads(read("docs/api/v1/protocols.json"))["protocols"]
    n_prot = len(prots_all_)
    n_rpc_obs_ = sum(1 for p_ in prots_all_ if not p_.get("easAttested"))
    lbp = read("docs/leaderboard/index.html")
    master = read("bounties/WAVE2-MASTER-ISSUE.md")
    master3 = read("bounties/WAVE3-MASTER-ISSUE.md")
    rd3_ = read("bounties/wave-3/README.md")
    ex3_ = json.loads(re.search(r"```json\n(.*?)```", rd3_, re.S).group(1))
    wf = read(".github/workflows/verify-bounty-pr.yml")
    treas = w3cfg["settlement"]["treasuryAddress"]
    no_safe = lambda t: not re.search(re.escape(treas) + r".{0,160}\b(?:Safe|multisig)\b", t, re.S | re.I)
    hunters_ = BS.hunter_stats(lb_, claims_, claims3_)
    # Bounties: Wave 3 active on top, then Wave 2 retired archive and Wave 1 Genesis archive
    m_w1_ = re.search(r'<table class="ix" data-wave1-ledger>.*?</table>', bounty, re.S)
    w1_led_ = m_w1_.group(0) if m_w1_ else ""
    m_w2t_ = re.search(r'<div class="table-scroll" role="region" aria-label="[^"]+" tabindex="0"><table class="ix w2-table" data-wave2-claims>.*?</table></div>', bounty, re.S)
    w2_tab_ = m_w2t_.group(0) if m_w2t_ else ""
    w2_paid_ = {p_["fixture"]: p_["payoutTxHash"] for p_ in lb_["wave2Settlements"]}
    w2_rows_ = dict(re.findall(r'<tr data-wave2-claim="([^"]+)">(.*?)</tr>', w2_tab_, re.S))
    w2_set_ = sum(1 for c_ in claims_ if c_["_file"] in w2_paid_)
    w2 = {
        "Wave 3 single-sourced config (2 x $20.00 USDC = $40.00 USDC open on Base, 7 EVM chains, >= $10M TVL, >= 400-char memo, rpc_observed unlocked)":
            (BS.WAVE3_REWARD_USDC, BS.WAVE3_REWARD_ATOMIC, BS.WAVE3_OPEN_SLOTS, BS.WAVE3_POOL_CAP_USDC, BS.WAVE3_FUNDED_SLOTS, BS.WAVE3_FUNDED_USDC)
            == ("20.00", 20_000_000, 2, "40.00", 2, "40.00")
            and set(w3cfg["chains"].values()) == {"ethereum", "base", "arbitrum", "optimism", "polygon", "bnb", "avalanche"}
            and w3cfg["minTvlUsd"] == 10_000_000 and w3cfg["minMemoChars"] == 400
            and w3cfg["settlement"]["chainId"] == 8453 and w3cfg["settlement"]["treasuryKind"] == "EOA" and VBS.checksummed(treas)
            and VBS.W3 == w3cfg and "Wave 3 (OPEN)" in read("docs/llms.txt")
            and 0 < bounty.find('id="wave-3"') < bounty.find('id="wave-2-archive"') < bounty.find('id="wave-1-archive"')
            and all(f'data-wave3-part="{p_}"' in bounty for p_ in ("1", "2", "3"))
            and f"including all {n_rpc_obs_} un-assessed <code>rpc_observed</code>" in bounty and no_safe(bounty),
        "Wave 3 master issue & README: exact title, byte-identical regeneration, valid Optimism dossier example, all FIELDS_WAVE3 & repo_audit keys documented":
            master3.split("\n", 1)[0] == f"# {w3cfg['title']}"
            and master3 == BS.wave3_master_issue_md(n_prot, n_rpc_obs_) and BS.md_html(master3.split("\n", 2)[2]) in bounty
            and VBS.validate_wave3(ex3_) == [] and VBS.wave3_name_problems("bounties/wave-3/optimism-example-lending.json", ex3_) == []
            and all(f"`{k}`" in rd3_ for k in list(VBS.FIELDS_WAVE3) + list(VBS.WAVE3_REPO_FIELDS)) and no_safe(master3) and no_safe(rd3_),
        "Wave 1 archive source byte-identical (tools/bounty_issues.json 874df3fd...)":
            hashlib.sha256(read("tools/bounty_issues.json", "rb")).hexdigest() == "874df3fd179ad241e3f2e4a7e837e9aa07f462a8a842b25fb1803049a6b84954",
        "Wave 2 archive master issue & retired section: regenerates byte-identically, marked Completed & Retired on /bounties/":
            master.split("\n", 1)[0] == f"# {w2cfg['title']}"
            and "**Net-new only.**" in master and "strictly after Pacta's latest pinned block" in master
            and master == BS.wave2_master_issue_md(n_prot) and BS.md_html(master.split("\n", 2)[2]) in bounty
            and "python3 tools/verify_bounty_submission.py --json bounties/wave-2/<chain>-<slug>.json" in master and no_safe(master)
            and "data-wave2-retired" in bounty and "Completed &amp; Retired" in bounty
            and f'data-wave2-counter="{n_claims}" data-wave2-program="{n_claims}"' in bounty,
        "Wave 2 archived categories & settlement copy preserved accurately":
            all(f'data-wave2-category="{c}"' in bounty for c in ("protocol_mismatch", "curated_vault_mismatch", "post_pin_drift"))
            and "≥ $10M TVL" in bounty and "≥ $5M TVL" in bounty and f"any of Pacta&#x27;s {n_prot} indexed protocols" in bounty
            and all(x in bounty for x in ("Morpho (MetaMorpho)", "Euler V2 (EVK)", "Concrete", "Veda / BoringVault", "Yearn V3", "Pendle", "Maple", "Centrifuge"))
            and "3 concurrent open CI-passing PRs per contributor" in bounty and html.escape(BS.WAVE2_PAYOUT) in bounty,
        "Wave 1 Genesis Settlement Ledger (4 slots: PR #27 / #31 / #29 / #32 verified, settled only with a real tx)":
            [s_["slot"] for s_ in lb_["wave1Settlements"]] == [1, 2, 3, 4]
            and [(s_["pr"], s_["hunter"], s_["protocol"]) for s_ in lb_["wave1Settlements"]] == [(27, "veriton-dev", "Stake DAO"), (31, "scavenger-osan", "Resupply"),
                                                                                             (29, "kinshu7777", "YO Protocol"), (32, "givemehat", "Inverse Finance (FiRM)")]
            and all(s_["status"] == "verified" for s_ in lb_["wave1Settlements"])
            and all(f'data-w1-slot="{n}"' in bounty for n in (1, 2, 3, 4)) and all(f'/pull/{n}"' in bounty for n in (27, 31, 29, 32))
            and "In review through Nov 22, 2026" not in bounty and w1_led_.count('data-settled="pending"') == sum(1 for s_ in lb_["wave1Settlements"]
                                                                                                         if s_["status"] == "verified" and not s_["payoutTxHash"])
            and w1_led_.count("data-w1-slot=") == 4 and w1_led_.count("data-basescan-tx") == sum(1 for s_ in lb_["wave1Settlements"] if s_["payoutTxHash"]),
    }
    # settlement truthfulness: stamp in memory -> BaseScan link + $25.00; malformed hashes refused by the stamp tool and the loader
    fake = "0x" + "ab" * 32
    lb0 = {**lb_, "wave1Settlements": [{**s_, "payoutTxHash": None} for s_ in lb_["wave1Settlements"]]}     # unstamped baseline
    st_lb, st_changes = SWP.stamp(lb0, {1: fake})
    led = BS.wave1_ledger_html(st_lb)
    row1 = re.search(r'<tr data-w1-slot="1">.*?</tr>', led, re.S).group(0)
    row2 = re.search(r'<tr data-w1-slot="2">.*?</tr>', led, re.S).group(0)
    refused = []
    for bad_tx, slot_ in (("0x123", 1), ("0x" + "00" * 32, 1), ("0x" + "zz" * 32, 2), (fake, 5)):      # Slot #5 does not exist
        try:
            SWP.stamp(lb0, {slot_: bad_tx})
        except ValueError:
            refused.append(slot_)
    tmpd = os.environ.get("TMPDIR") or ROOT
    bad_lb = os.path.join(tmpd, "w2-bad-leaderboard.json")
    with open(bad_lb, "w") as fh:
        fh.write(SWP.dump({**lb_, "wave1Settlements": [{**lb_["wave1Settlements"][0], "payoutTxHash": "0xdeadbeef"}] + lb_["wave1Settlements"][1:]}))
    try:
        BS.load_leaderboard(bad_lb)
        loader_refuses = False
    except AssertionError:
        loader_refuses = True
    os.remove(bad_lb)
    copy_lb = os.path.join(tmpd, "w2-copy-leaderboard.json")
    with open(copy_lb, "w") as fh:
        fh.write(SWP.dump(lb0))
    dry_rc = SWP.main(["--slot1-tx", fake, "--dry-run", "--leaderboard", copy_lb])
    dry_same = open(copy_lb).read() == SWP.dump(lb0)
    real_rc = SWP.main(["--slot1-tx", fake.upper().replace("0X", "0x"), "--slot2-tx", fake, "--leaderboard", copy_lb])
    stamped = json.load(open(copy_lb))
    again_rc = SWP.main(["--slot1-tx", "0x" + "cd" * 32, "--leaderboard", copy_lb])
    os.remove(copy_lb)
    st_rows = {h_["handle"]: h_ for h_ in BS.hunter_stats(st_lb, claims_)}
    w2["stamp_wave1_payouts.py: 1-command stamp -> BaseScan tx link + $25.00 USDC; pending elsewhere; bad / zero hashes, unverified slot, silent overwrite refused"] = (
        f'href="https://basescan.org/tx/{fake}"' in row1 and "$25.00 USDC" in row1 and "Settled on Base" in row1 and "$0.00 (pending settlement)" in row2
        and len(st_changes) == 1 and refused == [1, 1, 2, 5] and loader_refuses and dry_rc == 0 and dry_same and real_rc == 0
        and [s_["payoutTxHash"] for s_ in stamped["wave1Settlements"]] == [fake, fake, None, None] and again_rc == 2
        and st_rows["veriton-dev"]["settled"] == 25_000_000 + 2 * BS.REWARD_ATOMIC and st_rows["kinshu7777"]["settled"] == 3 * BS.REWARD_ATOMIC   # + Wave 2 PR #54 (paid); kinshu7777: Wave 2 PRs #77 + #76 + #90 (paid) once Wave 1 is unstamped
        and SWP.dump(lb_) == read("bounties/leaderboard.json"))
    paid_ = [s_ for s_ in lb_["wave1Settlements"] if s_["payoutTxHash"]]
    w2["Wave 1 settlements stamped: each recorded payout hash is a real 0x + 64-hex tx, linked to BaseScan with $25.00 USDC on /bounties/ and credited on /leaderboard/"] = (
        all(BS.tx_ok(s_["payoutTxHash"]) and s_["status"] == "verified" for s_ in paid_)
        and all(f'href="https://basescan.org/tx/{s_["payoutTxHash"]}"' in re.search(rf'<tr data-w1-slot="{s_["slot"]}">.*?</tr>', bounty, re.S).group(0)
                and "Settled on Base" in re.search(rf'<tr data-w1-slot="{s_["slot"]}">.*?</tr>', bounty, re.S).group(0) for s_ in paid_)
        and all(f'href="https://basescan.org/tx/{s_["payoutTxHash"]}"' in lbp for s_ in paid_))
    # Wave 2 archive: a simulated unpaid claim (dropping one recorded payout) lowers only settled, never claimed
    lb_w2u_ = {**lb_, "wave2Settlements": lb_["wave2Settlements"][1:]}
    sec_w2u_ = BS.wave2_section_html(claims_, n_prot, lb_w2u_)
    w2u_drop_ = lb_["wave2Settlements"][0]["fixture"] if lb_["wave2Settlements"] else None
    w2u_rows_ = dict(re.findall(r'<tr data-wave2-claim="([^"]+)">(.*?)</tr>', sec_w2u_, re.S))
    w2u_set_ = sum(1 for c_ in claims_ if c_["_file"] in w2_paid_ and c_["_file"] != w2u_drop_)
    w2[f"/bounties/#wave-2 settlements: all {len(w2_rows_)} claims joined to wave2Settlements by fixture ({len(w2_paid_)} settled -> BaseScan tx + $1.00 USDC, "
       f"unpaid -> $0.00 pending); claimed and settled counted separately (a simulated unpaid claim raises only claimed)"] = (
        bool(w2_tab_) and len(w2_rows_) == len(claims_) == n_claims and set(w2_paid_) <= set(w2_rows_) and 25 <= len(w2_paid_) <= 30
        and "<th>Settled (Base USDC)</th>" in w2_tab_ and w2_tab_.count('class="lb-handle"') == len(claims_)
        and ".w2-table .lb-handle { white-space: nowrap; }" in read("docs/styles.css")
        and all(f'href="https://basescan.org/tx/{tx_}"' in w2_rows_[f_] and "data-basescan-tx" in w2_rows_[f_]
                and f'<b data-settled="{BS.REWARD_ATOMIC}">$1.00 USDC</b>' in w2_rows_[f_] for f_, tx_ in w2_paid_.items())
        and all('data-settled="pending"' in r_ and "$0.00 (pending settlement)" in r_ for f_, r_ in w2_rows_.items() if f_ not in w2_paid_)
        and w2_tab_.count("data-basescan-tx") == len(w2_paid_) and bounty.count("data-basescan-tx") == len(w2_paid_) + w1_led_.count("data-basescan-tx")
        and w2u_drop_ is not None and len(w2u_rows_) == len(claims_)
        and 'data-settled="pending"' in w2u_rows_[w2u_drop_] and "data-basescan-tx" not in w2u_rows_[w2u_drop_]
        and sec_w2u_.count("data-basescan-tx") == len(w2_paid_) - 1 and w2u_set_ == w2_set_ - 1
        and (f'<b>{n_claims} Wave 2 Micro-Bounty Claims Merged</b> · <b data-wave2-settled="{w2u_set_}">{w2u_set_} settled on Base '
             f'({BS.usdc(w2u_set_ * BS.REWARD_ATOMIC)} USDC)</b>') in sec_w2u_)
    # /leaderboard/ layout: the geometry is measured in Chromium, these are the static guarantees behind it
    lb_imgs_ = re.findall(r'<img class="cp-badge" src="\.\./badges/hunters/([^"]+)\.svg" alt="Pacta hunter: [^"]+" width="(\d+)" height="20">', lbp)
    lb_svgw_ = {h_: re.search(r'<svg [^>]*\bwidth="(\d+)" height="20"', read(f"docs/badges/hunters/{h_}.svg")) for h_, _ in lb_imgs_}
    lb_ncatch_ = {h_["handle"]: len(h_["catches"]) for h_ in hunters_}
    lb_labels_ = re.findall(r'<li data-catch-wave="[123]"><a [^>]*>([^<]+)<', lbp)
    css_lb_ = read("docs/styles.css")
    w2[f"/leaderboard/ layout: wide container; hunters table scrolls inside a labelled focusable region (never the document); handles and compact catch "
       f"labels never wrap; all {len(lb_imgs_)} hunter badges declare their intrinsic SVG width, unclamped (11 px labels)"] = (
        '<main id="main" class="memo-wrap memo-wide">' in lbp
        and lbp.count('<div class="table-scroll" role="region" aria-label="Hunter leaderboard table" tabindex="0"><table class="ix lb-table" data-leaderboard>') == 1
        and len(lb_imgs_) == len(hunters_)
        and all(lb_svgw_[h_] and int(w_) == int(lb_svgw_[h_].group(1)) == BS.hunter_badge_width(h_, lb_ncatch_[h_]) for h_, w_ in lb_imgs_)
        and lbp.count('class="lb-handle"') == len(hunters_)
        and len(lb_labels_) == sum(lb_ncatch_.values()) and all(len(l_) <= 32 and ".json" not in l_ for l_ in lb_labels_)
        and all(rule_ in css_lb_ for rule_ in (".memo-wrap.memo-wide { max-width: var(--container-wide); }", ".table-scroll { max-width: 100%; overflow-x: auto; }",
                                               ".table-scroll > table.ix { display: table; max-width: none; overflow: visible; }",
                                               ".lb-table .lb-handle { white-space: nowrap; }", ".lb-table .cp-badge { max-width: none; }",
                                               ".memo .lb-catches a { display: inline-flex; align-items: center; min-height: 24px; white-space: nowrap; }")))
    # /leaderboard/ + #<hunter> Verified Researcher Credentials
    lb_rows = re.findall(r'<tr id="hunter-([a-z0-9-]+)" data-hunter="([^"]+)"><td class="num">(\d+)</td>', lbp)
    w2["/leaderboard/: hunters ranked, Verified Base-EAS Researcher Credential cards (#<hunter> + LinkedIn & X share), frameworks, settled only with tx"] = (
        [h_ for _, h_, _ in lb_rows] == [h_["handle"] for h_ in hunters_] and len(lb_rows) == len(hunters_) >= 3
        and [int(r_) for _, _, r_ in lb_rows] == [h_["rank"] for h_ in hunters_]
        and all(f'data-copy="{html.escape(BS.badge_markdown(h_["handle"]))}"' in lbp and html.escape(BS.share_x_href(h_)) in lbp
                and html.escape(BS.share_linkedin_href(h_)) in lbp
                and f'id="{h_["handle"].lower()}" data-credential-card="{h_["handle"]}"' in lbp
                and f'src="../badges/hunters/{h_["handle"]}.svg"' in lbp for h_ in hunters_)
        and lbp.count("data-share-x") == len(hunters_) and all(u.startswith("https://x.com/intent/tweet?") for u in re.findall(r'href="([^"]+)"[^>]*data-share-x', lbp))
        and lbp.count("data-share-linkedin") == len(hunters_)
        and all(u.startswith("https://www.linkedin.com/sharing/share-offsite/?") for u in re.findall(r'href="([^"]+)"[^>]*data-share-linkedin', lbp))
        and ".cred-card:target" in css_lb_
        and lbp.count('data-settled="pending"') == sum(1 for h_ in hunters_ if not h_["txs"])
        and lbp.count("data-basescan-tx") == sum(len(set(h_["txs"])) for h_ in hunters_)
        and all(f'<b data-settled="{h_["settled"]}">{BS.usdc(h_["settled"])} USDC</b>' in lbp for h_ in hunters_ if h_["txs"])
        and 'data-frameworks' in lbp and 'data-framework="openclaw"' in lbp and 'data-framework="not stated"' in lbp
        and 'href="../leaderboard/"' in bounty and f"<loc>{BS.BASE_URL}/leaderboard/</loc>" in read("docs/sitemap.xml")
        and all(f"{BS.BASE_URL}/leaderboard/" in read(f_) for f_ in ("docs/llms.txt", "docs/llms-full.txt", "docs/llms/index.html"))
        and all('leaderboard/">Leaderboard</a>' in t for r, t in pages.items() if 'class="ftr"' in t)
        and not any('leaderboard/">' in re.search(r'<nav class="nav".*?</nav>', t, re.S).group(0) for t in pages.values() if '<nav class="nav"' in t))
    class _OnAttrs(html.parser.HTMLParser):          # attribute names as the browser sees them (values never match by accident)
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.hits = []

        def handle_starttag(self, tag, attrs):
            self.hits += [f"<{tag} {k}>" for k, _ in attrs if re.fullmatch(r"on[a-z]+", k or "")]
        handle_startendtag = handle_starttag
    all_html = sorted(glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True))
    inline_on = []
    for p_ in all_html:
        sc_ = _OnAttrs()
        sc_.feed(read(p_))
        inline_on += [f"{os.path.relpath(p_, DOCS)}: {h_}" for h_ in sc_.hits]
    inline_on += [os.path.relpath(p_, DOCS) for p_ in all_html if re.search(r"<[a-zA-Z][^>]*\son[a-z]+\s*=", re.sub(r'"[^"]*"|\'[^\']*\'', '""', read(p_)))]
    # the scanner itself must catch an inline handler (guards against a vacuous check)
    probe_ = _OnAttrs()
    probe_.feed('<form id="x" onsubmit="return false"><a href="#" ONCLICK=\'y()\'>z</a></form>')
    scanner_ok = len(probe_.hits) == 2
    extra_js = [r for r in ("bounties/index.html", "leaderboard/index.html")
                if len(re.findall(r"<script(?![^>]*\bsrc=)(?![^>]*application/ld\+json)[^>]*>", read("docs/" + r))) != 0]   # 0 inline JS (theme.js)
    w2[f"CSP-safe: 0 inline on* event handlers in ALL {len(all_html)} docs/**/*.html pages (the request form prevents submit from app.js); no new inline <script> on /bounties/ and /leaderboard/ (copy via data-copy, share via a plain link)"] = (
        not inline_on and scanner_ok and len(all_html) >= 90 and not extra_js and "javascript:" not in bounty + lbp
        and 'form.addEventListener("submit", function (e) {\n      e.preventDefault();' in appjs)
    # hunter badges
    bdir = os.path.join(DOCS, "badges", "hunters")
    bfiles = sorted(os.listdir(bdir))
    badge_bad = []
    for h_ in hunters_:
        raw_ = read(f"docs/badges/hunters/{h_['handle']}.svg")
        try:
            ET.fromstring(raw_)
            inner_raw = re.search(r'<svg x="4" y="2" width="16" height="16" viewBox="0 0 1000 1000">.*?</svg>', raw_, re.S).group(0)
            geo_ok = logo_geometry(inner_raw.replace('<svg x="4" y="2" width="16" height="16" viewBox', '<svg xmlns="http://www.w3.org/2000/svg" viewBox')) \
                == logo_geometry(read("docs/logo.svg"))
        except (ET.ParseError, AttributeError):
            geo_ok = False
        if not (geo_ok and raw_ == BS.hunter_badge_svg(h_["handle"], len(h_["catches"])) and "<script" not in raw_ and not re.search(r"\son[a-z]+=|href=", raw_)
                and f"{h_['handle']} · {len(h_['catches'])} verified" in raw_):
            badge_bad.append(h_["handle"])
    xss_refused = []
    for evil in ('<script>alert(1)</script>', "../../index", "a/b", "x" * 40, "", "dot.name", 'q"onload="x'):
        try:
            BS.hunter_badge_svg(evil, 1)
        except ValueError:
            try:
                BS.hunter_badge_path(evil)
            except ValueError:
                xss_refused.append(evil)
    ok_svg = BS.hunter_badge_svg("a_b-C9", 2)
    w2["hunter SVG badges: one per hunter (strict [A-Za-z0-9_-]{1,39} names, realpath containment), valid XML, official mark embedded, escaped text, 0 script / handlers / links; traversal + markup handles refused"] = (
        bfiles == sorted(f"{h_['handle']}.svg" for h_ in hunters_) and not badge_bad and len(xss_refused) == 7
        and ET.fromstring(ok_svg) is not None and "a_b-C9 · 2 verified" in ok_svg and xesc("<&>") == "&lt;&amp;&gt;"
        and os.path.dirname(BS.hunter_badge_path("ok-name")) == os.path.realpath(bdir))
    # Wave 2 validator v2 + README schema
    rd_ = read("bounties/wave-2/README.md")
    # adversarial review findings stay closed + net-new drift rule: each named bypass is refused for the right reason
    first_ = next(x for x in json.loads(read("docs/api/v1/protocols.json"))["protocols"] if x["chain"] == "ethereum")
    g_, d_ = VBS.valid_fixture_wave2("protocol_mismatch", first_), VBS.valid_fixture_wave2("post_pin_drift", first_)
    pin_ = VBS.max_pinned_block(first_["slug"])
    bypasses = {
        "contractAddress": {**g_, "contractAddress": VBS.TREASURY, "castCommands": [c.replace(g_["contractAddress"], VBS.TREASURY) for c in g_["castCommands"]]},
        "mcpProof": {**g_, "mcpProof": {"tool": "pacta_check_preflight", "arguments": {"address": g_["contractAddress"]},
                                        "result": {"schema": "pacta.preflight_check.v1", "verdict": "SAFE", "address": "0x" + "12" * 20}}},
        "castCommands": {**g_, "castCommands": [g_["castCommands"][0], g_["castCommands"][1].replace(g_["contractAddress"], g_["basePayoutAddress"])]},
        "tvlUsd": {**g_, "tvlUsd": float("inf")},
        "blockNumber": {**d_, "blockNumber": pin_, "castCommands": [c.replace(f"--block {d_['blockNumber']}", f"--block {pin_}") for c in d_["castCommands"]]},
    }
    bypass_ok = all(any(p_.startswith(k_ + ":") for p_ in VBS.validate_wave2(f_)) for k_, f_ in bypasses.items()) \
        and VBS.validate_wave2({**g_, "mcpProof": {**g_["mcpProof"], "arguments": {}}}) != [] and VBS.validate_wave2(d_) == [] and pin_ and d_["blockNumber"] > pin_
    ex = json.loads(re.search(r"```json\n(.*?)```", rd_, re.S).group(1))
    w2["validator v2+v3: Wave 1 + Wave 2 + Wave 3 self-tests pass, README examples valid, every FIELDS_WAVE2 & FIELDS_WAVE3 key documented, --wave 3 & auto-detect"] = (
        VBS.self_test() and VBS.self_test_wave2(VBS.indexed()) and VBS.self_test_wave3(VBS.indexed_wave3())
        and VBS.validate_wave2(ex) == [] and VBS.validate_wave3(ex3_) == [] and bypass_ok
        and VBS.wave2_name_problems("bounties/wave-2/ethereum-example-lending.json", ex) == [] and all(f"`{k}`" in rd_ for k in VBS.FIELDS_WAVE2)
        and VBS.is_wave2("bounties/wave-2/x.json", {}) and VBS.is_wave3("bounties/wave-3/polygon-x.json", {})
        and not VBS.is_wave2("bounties/submissions/slot-1-x.json", {"slot": 1}))
    # CI gate: static invariants + behaviour in throw-away repos
    runs = workflow_run_blocks(wf)
    w2["workflow static security: pull_request only (paths bounties/**), permissions contents: read, persist-credentials: false, SHAs via env only, validator from BASE_SHA, wave-3 7 chains"] = (
        "pull_request_target" not in re.sub(r"(?m)^\s*#.*$", "", wf) and re.search(r"^on:\n  pull_request:\n    paths: \[\"bounties/\*\*\"\]\n", wf, re.M) is not None
        and re.search(r"^permissions:\n  contents: read\n", wf, re.M) is not None and "write" not in re.sub(r"#.*", "", wf).split("jobs:")[0].replace("GITHUB_OUTPUT", "")
        and "persist-credentials: false" in wf and "fetch-depth: 0" in wf and "secrets." not in wf
        and len(runs) == 2 and not any("${{" in r_ for r_ in runs)
        and wf.count("BASE_SHA: ${{ github.event.pull_request.base.sha }}") == 2 and wf.count("HEAD_SHA: ${{ github.event.pull_request.head.sha }}") == 2
        and 'git show "$BASE_SHA:tools/verify_bounty_submission.py"' in runs[1] and "python3 -I tools/verify_bounty_submission.py" in runs[1]
        and r"^bounties/wave-3/(ethereum|base|arbitrum|optimism|polygon|bnb|avalanche)-[a-z0-9]+(-[a-z0-9]+)*\.json$" in runs[0]
        and r"^bounties/wave-2/(ethereum|base|arbitrum)-[a-z0-9]+(-[a-z0-9]+)*\.json$" in runs[0] and "100644" in runs[0] and "--no-renames" in runs[0])
    sim = bounty_gate_simulation()
    want = {"valid": (0, 0), "invalid_tvl": (0, 1), "duplicate_of_merged": (0, 1), "plus_validator_edit": (1, None), "validator_only": (1, None),
            "workflow_edit": (1, None), "wrong_path": (1, None), "modify_existing": (1, None), "symlink": (1, None), "chain_mismatch": (0, 1),
            "wave1_fixture": (0, 0), "wave3_valid": (0, 0), "wave3_polygon_valid": (0, 0), "wave3_shallow_memo": (0, 1), "wave3_wrong_chain": (1, None)}
    sim_bad = {k: v[:2] for k, v in sim.items() if want.get(k) != v[:2]}
    w2["CI gate behaviour (bash + git, throw-away repos): valid Wave 3 / Wave 2 / Wave 1 fixtures pass; shallow memo / bad TVL / duplicate / chain mismatch fail validation; validator or workflow edits, 2nd file, modified file, symlink or wrong path fail BEFORE Python"] = (
        set(sim) == set(want) and not sim_bad and "duplicate:" in sim["duplicate_of_merged"][2] and "executive_risk_memo:" in sim["wave3_shallow_memo"][2])
    m_ = json.loads(read("docs/api/v1/graph-manifest.json"))
    pub_slugs_ = {p_["slug"] for p_ in json.loads(read("docs/api/v1/protocols.json"))["protocols"]}
    sub_files_ = sorted(os.path.join("bounties", "submissions", f_) for f_ in os.listdir(os.path.join(ROOT, "bounties", "submissions")) if f_.endswith(".json"))
    w2[f"graph manifest = the pinned {GRAPH_MANIFEST_SHA256[:8]}... (Wave 2/3 never feed tools/graph_manifest.py; only merged Wave 1 fixtures whose pactaSlug is published)"] = (
        hashlib.sha256(read("docs/api/v1/graph-manifest.json", "rb")).hexdigest() == GRAPH_MANIFEST_SHA256
        and (m_.get("sources") or {}).get("bounty_submissions") == [f_ for f_ in sub_files_ if json.loads(read(f_)).get("pactaSlug") in pub_slugs_]
        and "wave-2" not in read("tools/graph_manifest.py") and "wave-3" not in read("tools/graph_manifest.py"))
    check("W2/W3: Wave 3 active pool (2 x $20.00 USDC = $40.00 3-Year Protocol Trajectory & Integrity Dossiers, 7 chains, rpc_observed unlocked), "
          "Wave 2 ($1 micro-bounties Completed & Retired) + Wave 1 Genesis Archive, /leaderboard/#<hunter> Verified Researcher Credentials, validator v3, "
          "hardened pull_request CI gate (static + simulated), graph manifest unchanged",
          all(w2.values()), f"{[k[:60] for k, v in w2.items() if not v]} sim {sim_bad} badges {badge_bad} refused {len(xss_refused)}")

    # ================= Community hub (GitHub Discussions) + Wave 3 / Wave 2 master issues =================
    cu, cqa, iss = BS.COMMUNITY_URL, BS.COMMUNITY_QA_URL, BS.WAVE2_ISSUE_URL
    ftr_pages = [r for r, t in pages.items() if 'class="ftr"' in t]
    c1 = {
        "config: communityUrl / communityQaUrl / wave2IssueUrl #41": (cu, cqa, iss) == ("https://github.com/Fractal-Neurons/pacta/discussions",
                                                                           "https://github.com/Fractal-Neurons/pacta/discussions/44",
                                                                           "https://github.com/Fractal-Neurons/pacta/issues/41"),
        "README Community badge links the Discussions hub": f"[![Community](https://img.shields.io/badge/Community-GitHub_Discussions-f59e0b?style=for-the-badge&labelColor=000000)]({cu})" in read("README.md"),
        f"footer Community link on all {len(ftr_pages)} footer pages": len(ftr_pages) >= 85
            and all(f'<a href="{cu}" target="_blank" rel="noopener">Community</a>' in pages[r] for r in ftr_pages),
        "/bounties/: Community Q&A (Discussions) + Q&A thread + Master issue #41": f'href="{cu}" target="_blank" rel="noopener">Community Q&amp;A (Discussions){BS.EXT}</a>' in bounty
            and f'href="{cqa}"' in bounty and f'<a href="{iss}" target="_blank" rel="noopener" data-wave2-issue>Master issue #41{BS.EXT}</a>' in bounty,
        "/leaderboard/: Community Q&A (Discussions)": f'href="{cu}" target="_blank" rel="noopener">Community Q&amp;A (Discussions){BS.EXT}</a>' in lbp and f'href="{cqa}"' in lbp,
        "llms.txt, llms-full.txt, /llms/: community hub, Q&A thread, issue #41": all(cu in read(f_) and cqa in read(f_) and iss in read(f_)
                                                                                  for f_ in ("docs/llms.txt", "docs/llms-full.txt", "docs/llms/index.html")),
        "WAVE3-MASTER-ISSUE.md + WAVE2-MASTER-ISSUE.md + READMEs: Questions -> Discussions": "## Questions" in master3 and cu in master3 and cqa in master3
            and "## Questions" in master and cu in master and cqa in master and cu in rd3_ and cqa in rd3_ and cu in rd_ and cqa in rd_ and iss in rd_,
        "/mcp/ landing page: endpoint, no key / wallet, rate limit, copy snippets, protocols.json, starter repo, Q&A #44, in the sitemap": os.path.exists(os.path.join(DOCS, "mcp", "index.html"))
            and all(x in pages[os.path.join("mcp", "index.html")] for x in (f'data-mcp-endpoint>{BS.MCP_URL}</code>', "no API key and no wallet", BS.RATE_LIMIT,
                    f'<pre>claude mcp add --transport http pacta {BS.MCP_URL}</pre>', 'data-copy-term aria-label="Copy the Claude Code MCP install command"', 'href="../api/v1/protocols.json"',
                    'https://github.com/Fractal-Neurons/defi-control-plane-mcp', f'href="{cqa}"'))
            and f"<loc>{BS.BASE_URL}/mcp/</loc>" in read("docs/sitemap.xml") and len(pages) == X["protocols"] + NON_PROTOCOL_PAGES,
        "nav + footer say 'Bounties' (no '$100' label) on every page": not [r for r, t in pages.items() if 'Bounties ($100)</a>' in t]
            and all('bounties/">Bounties</a>' in t for r, t in pages.items() if 'class="topbar"' in t),
        "Wave 1 archive labelled 'Historical Snapshot (Pinned at 53 Protocols on Nov 15)'": "<b>Historical Snapshot (Pinned at 53 Protocols on Nov 15)</b>" in bounty
            and bounty.index("data-wave1-snapshot") > bounty.index('id="wave-1"'),
        "funded capacity = confirmed unencumbered USDC only (Wave 3: 2 slots / $40.00 USDC unencumbered in Base EOA; Wave 2 retired; Wave 1 4/4 settled)":
            (w3cfg["settledSlots"], w3cfg["fundedUnencumberedSlots"], w3cfg["fundedUnencumberedUsdc"], w3cfg["ringFencedReserveUsdc"]) == (0, 2, "40.00", "0.05")
            and 25 <= len(lb_["wave2Settlements"]) <= 30 and all(BS.tx_ok(p_["payoutTxHash"]) for p_ in lb_["wave2Settlements"])
            and "data-wave3-capacity" in bounty and "Confirmed unencumbered on-chain now: <b>$40.00 USDC (2 slots)</b>" in bounty
            and "**$40.00 USDC (2 slots)**" in master3
            and "Confirmed unencumbered Wave 2 micro-bounty capacity: **$0.00 USDC (0 slots)**" in master
            and "funded this epoch" not in bounty + master + master3 + read("docs/llms.txt")
            and not re.search(r"\bfunded epochs?\b|pays out in funded", bounty + master + master3 + read("docs/llms.txt") + read("docs/llms-full.txt") + rd_ + rd3_)
            and "PRIOR_EPOCH_SLOTS + SETTLED_EPOCH_SLOTS + FUNDED_UNENCUMBERED_SLOTS" in read("tools/build_site.py"),
        "README: settled shield, @pacta/mcp-server 0.1.5, Wave 3 + Master Issue #41, live protocol count, Ethereum and Base block heights": (
            sum(25 for s_ in lb_["wave1Settlements"] if s_["payoutTxHash"]) == 100 and 25 <= len(lb_["wave2Settlements"]) <= 30
            and re.search(r'\[!\[Bounties & Leaderboard\]\(https://img\.shields\.io/badge/Bounties_%26_Leaderboard-%24\d+_USDC_Settled-10b981\?style=for-the-badge&labelColor=000000\)\]\(https://pacta\.wtf/leaderboard/\)', read("README.md")) is not None
            and "Wave 3 OPEN (`2 × $20.00 USDC = $40.00 USDC` on Base)" in read("README.md")
            and "`@pacta/mcp-server` 0.1.5" in read("README.md") and "0.1.4" not in read("README.md")
            and json.loads(read("packages/mcp-server/package.json"))["version"] == "0.1.5"
            and "[Master Issue #41](https://github.com/Fractal-Neurons/pacta/issues/41)" in read("README.md")
            and f"**{BS.coverage_line(idx_)}**" in read("README.md")
            and "Ethereum and Base Mainnet block heights" in read("README.md") and "Ethereum Mainnet block height" not in read("README.md")),
        f"graph manifest = the pinned {GRAPH_MANIFEST_SHA256[:8]}...": hashlib.sha256(read("docs/api/v1/graph-manifest.json", "rb")).hexdigest()
            == GRAPH_MANIFEST_SHA256,
    }
    check("C1: GitHub Discussions community hub + Wave 2 master issue #41 linked from README, every footer, /bounties/, /leaderboard/, llms.txt, llms-full.txt, /llms/ and the master issue text",
          all(c1.values()), str([k for k, v in c1.items() if not v]))

    # Every Wave 1 and Wave 2 hunter credit renders on its published protocol page (hunter handle + PR link + the credited record),
    # and bounties/leaderboard.json easAttestations counts every credit across both waves
    lbh = BS.load_leaderboard()
    idx_ids = {e_["id"] for e_ in json.loads(read("docs/api/v1/index.json"))["entries"]}
    hc_bad, per_hunter = [], {}
    w1_by_slot = {int(s_["slot"]): s_ for s_ in lbh["wave1Settlements"]}
    for f_name in sorted(os.listdir(os.path.join(ROOT, "bounties", "submissions"))):
        if not (f_name.startswith("slot-") and f_name.endswith(".json")):
            continue
        fx = json.loads(read(os.path.join("bounties", "submissions", f_name)))
        st_ = w1_by_slot[int(fx["slot"])]
        if st_["status"] != "verified" or not fx.get("pactaSlug"):
            continue
        pg = os.path.join(DOCS, "protocols", fx["pactaSlug"], "index.html")
        page_ = read(pg) if os.path.exists(pg) else ""
        per_hunter[st_["hunter"]] = per_hunter.get(st_["hunter"], 0) + 1
        if f'data-research-credit="{st_["hunter"]}"' not in page_ or f'/pull/{st_["pr"]}"' not in page_:
            hc_bad.append(f'wave 1 slot {fx["slot"]} @{st_["hunter"]} on /protocols/{fx["pactaSlug"]}/')
    w2_files = {c_["_file"]: c_ for c_ in BS.load_wave2_claims()}
    for c_ in lbh.get("wave2Credits", []):
        h_ = w2_files[c_["fixture"]]["hunter"]
        pg = os.path.join(DOCS, "protocols", c_["pactaSlug"], "index.html")
        page_ = read(pg) if os.path.exists(pg) else ""
        per_hunter[h_] = per_hunter.get(h_, 0) + 1
        if (f'data-research-credit="{h_}" data-research-wave="2"' not in page_ or f'/pull/{c_["pr"]}"' not in page_
                or f'href="#{c_["record"]}"' not in page_ or f'id="{c_["record"]}"' not in page_ or c_["record"] not in idx_ids):
            hc_bad.append(f'wave 2 PR #{c_["pr"]} @{h_} on /protocols/{c_["pactaSlug"]}/')
    check("Wave 1 + Wave 2 hunter credits: every credit renders on its protocol page (handle, PR, credited Base-EAS record); "
          "easAttestations = the credits across both waves",
          not hc_bad and lbh["easAttestations"] == {h_: per_hunter[h_] for h_ in sorted(per_hunter)}
          and set(c_["fixture"] for c_ in lbh.get("wave2Credits", [])) <= set(w2_files),
          str(hc_bad) + " " + str((lbh["easAttestations"], per_hunter)))

    # ================= Website, accessibility & trust polish pack v2 (Groups 2-4: copy, radar truth, freshness, a11y, nav, feeds, meta) =================
    import xml.etree.ElementTree as ETP
    pp = {}
    home_p = read("docs/index.html")
    css_p = read("docs/styles.css")
    app_p = read("tools/app.src.js")
    all_pages = {r: t for r, t in pages.items() if not r.startswith("demos" + os.sep)}
    pp["V06: no 'within 24 hours' / 'Clear findings' / 'Request 24h Clearance' / Aligned-attestation-for-payment copy on any page; every delta / RPC-observed protocol page offers the free notification next to the Verification & Reconciliation Dossier"] = (
        not [r for r, t in all_pages.items() if re.search(r"within 24 hours|Clear findings|Request 24h Clearance|Aligned Attestation \+ Curator", t)]
        and all('data-cta="free_notify"' in t and html.escape(BS.DOSSIER_CTA, quote=False) in t
                for r, t in all_pages.items() if r.startswith("protocols" + os.sep) and 'id="issuer-clearance"' in t))
    rad_p = json.loads(read("docs/api/v1/radar.json"))
    pp["F03: radar header = pending vs executed counts (executed ops never counted as queued); executed rows badged and de-emphasised (+ harness)"] = (
        f"<span class=\"radar-counts\" data-radar-counts>{html.escape(BS.radar_counts_text(rad_p))}</span>" in home_p
        and home_p.count('data-radar-row="executed"') == sum(1 for it in rad_p["items"] if all(o.get("done") for o in it["operations"]))
        and res.get("pp2_radar_counts") is True)
    n_el = len(re.findall(r"<[a-zA-Z]", home_p))
    pp[f"V04 + Edge v3: slim homepage: {len(home_p.encode())} bytes < 150,000 and {n_el} elements < 2,200; 8 high-signal scorecards static; every protocol hydrates from /api/v1/scorecards.json on search / filter (harness); all {X['protocols']} /protocols/<slug>/ pages static"] = (
        len(home_p.encode()) < 150000 and n_el < 2200 and all(res.get(k) is True for k in ("e3_static_preview", "e3_hydrated_all", "e3_search"))
        and f'href="scorecards/" data-sc-explore>Explore all {X["protocols"]} protocol scorecards' in home_p and 'href="protocols/">Browse all' in home_p
        and len([r for r in pages if r.startswith("protocols" + os.sep) and r.count(os.sep) == 2]) == X["protocols"])
    pp["Curator basket pills (All · Stablecoins & RWA · ETH LST / LRT · Curated Lending & Vaults · Base Ecosystem) on /protocols/ (combined with Status x Chain x search, Clear all resets) and the homepage scorecards (harness)"] = (
        all(f'>{html.escape(lbl, quote=False)}</button>' in pages[os.path.join("protocols", "index.html")] and f'<option value="{k}">{html.escape(lbl, quote=False)}</option>' in home_p
            for k, lbl, _, _ in BS.BASKETS)   # v4: the homepage basket is a Select next to the Docs-vs-chain toggle group
        and res.get("pp2_baskets_protocols") is True and res.get("e3_filter_basket") is True)
    i_h1, i_pf, i_proof = home_p.find("<h1>"), home_p.find('id="pf-form"'), home_p.find("data-proof>")
    pp[f"V01 + Edge v3: the contract checker sits in the hero under the h1 (before the proof bar: {X['protocols']} protocols · {X['eas_protocols']} Base-EAS attested · {X['records']} block-pinned checks); radar counts never say 'queued' for executed operations"] = (
        0 < i_h1 < i_pf < i_proof and f'class="stat" data-slot="card"><b>{X["protocols"]}</b><span>Protocols scored</span><small>{X["eas_protocols"]} Base-EAS attested · {X["rpc_protocols"]} RPC-observed</small>' in home_p
        and f'class="stat" data-slot="card"><b>{X["records"]}</b><span>Attested checks</span>' in home_p
        and f'data-radar-counts>{html.escape(BS.radar_counts_text(rad_p))}</span>' in home_p and "timelock operations queued" not in home_p)
    pp["V03 + R3: below 640 px the radar is a stack of cards and /protocols/ keeps Protocol, Chain and Docs vs chain (other columns hidden, tables fit: no blind sideways scroll)"] = (
        # v4 (R3): the radar becomes stacked cards below 640 px; /protocols/ keeps Protocol, Chain and Docs vs chain
        "table.sc, table.sc tbody, table.sc tr, table.sc td, table.radar, table.radar tbody, table.radar tr, table.radar td { display: block; width: 100%; }" in css_p
        and "#proto-table th:nth-child(6), #proto-table td:nth-child(6) { display: none; }" in css_p
        and '<th scope="col">Protocol</th><th scope="col">Category</th><th scope="col">Chain</th><th scope="col">Checks</th><th scope="col">Docs vs chain</th><th scope="col">Provenance</th>' in pages[os.path.join("protocols", "index.html")])
    csp_meta = f'<meta http-equiv="Content-Security-Policy" content="{BS.CSP}">'
    gen_pages = {r: t for r, t in all_pages.items()}
    csp_src = {d.split(" ")[0]: d.split(" ")[1:] for d in BS.CSP.split(";")}
    js_hosts = set(re.findall(r'"(https://[a-z0-9.-]+)', read("tools/app.src.js") + read("docs/b.js") + read("docs/theme.js")))
    js_hosts = {h for h in js_hosts if h not in ("https://pacta.wtf", "https://github.com", "https://base.easscan.org", "https://etherscan.io", "https://basescan.org", "https://x.com", "https://mail.google.com", "https://metamask.app.link", "https://go.cb-wallet.com", "https://static.ads-twitter.com")}   # link targets + script-src host
    pp["S01: meta Content-Security-Policy on every generated page (default-src 'self', script-src 'self' + static.ads-twitter.com with 0 'unsafe-inline', no frame-ancestors, before any <script>); 0 inline JS (theme bootstrap = docs/theme.js); no eval / new Function; every HTTPS origin the page scripts fetch is in connect-src"] = (
        "frame-ancestors" not in BS.CSP and csp_src.get("script-src") == ["'self'", "https://static.ads-twitter.com"] and csp_src.get("default-src") == ["'self'"]
        and csp_src.get("img-src") == ["'self'", "data:", "https://analytics.twitter.com", "https://t.co"]
        and "https://analytics.twitter.com" in csp_src.get("connect-src", []) and "https://t.co" in csp_src.get("connect-src", [])
        and "'unsafe-inline'" not in csp_src.get("script-src", []) and "'unsafe-eval'" not in csp_src.get("script-src", [])
        and all(t.count(csp_meta) == 1 and t.find(csp_meta) < t.find("<script") for t in gen_pages.values())
        and not [r for r, t in gen_pages.items() if re.search(r"<script(?![^>]*\bsrc=)(?![^>]*application/ld\+json)[^>]*>", t)]
        and read("docs/theme.js") == BS.THEME_JS and not re.search(r"\beval\(|new Function\(", read("tools/app.src.js") + read("docs/b.js"))
        and js_hosts <= set(csp_src.get("connect-src", [])))
    def top_level(css, rule):   # True when `rule` exists exactly once and sits outside every @media block
        i = css.find(rule)
        return css.count(rule) == 1 and css[:i].count("{") == css[:i].count("}")
    m639 = css_p[css_p.index("/* /protocols/ below 640 px"):css_p.index("\n}", css_p.index("/* /protocols/ below 640 px"))]
    m767 = css_p[css_p.index("@media (max-width: 767px) {"):css_p.index("\n}", css_p.index("@media (max-width: 767px) {"))]
    ths_ = re.findall(r'<th scope="col">([^<]+)</th>', pages[os.path.join("protocols", "index.html")].split('id="proto-table"')[1].split("</thead>")[0])
    hidden_ = {int(x) for x in re.findall(r"#proto-table td:nth-child\((\d)\)", m639)}
    cta_words = sorted({re.sub(r"<[^>]+>", "", m.group(1)).strip() for t in all_pages.values()
                        for m in re.finditer(r'<a[^>]*data-slot="button"[^>]*data-cta="[^"]+"[^>]*>(.*?)</a>|<a class="cta"[^>]*>(.*?)</a>', t) if m.group(1)})
    pp["U7 + R4 layout: every CTA button label is 3 words or fewer; NavigationMenu >= 768 px, hamburger Sheet below (menu button shown, nav hidden); "
       "/protocols/ <= 640 px = Protocol / Chain / Docs vs chain"] = (
        cta_words and all(len(w.split()) <= 3 for w in cta_words)
        and '[data-slot="navigation-menu"], .tools .gh, .tools .xl { display: none; }' in m767 and ".menu-btn { display: inline-flex; }" in m767
        and top_level(css_p, ".menu-btn { display: none; }")
        and [ths_[i - 1] for i in range(1, len(ths_) + 1) if i not in hidden_] == ["Protocol", "Chain", "Docs vs chain"]
        and res.get("e3_checker_aria_invalid") is True)
    pp["F02: scorecard filters: 0 matches -> every drawer closed + empty state + working Clear filters; a drawer opens / closes from its row (harness)"] = all(
        res.get(k) is True for k in ("e3_zero_match", "e3_clear_filters", "e3_drawer_toggle", "e3_filter_deltas"))
    pp["F04 + F06: ages re-run every 60 s; Snapshot pinned / Last live re-check / Refresh / pinned-snapshot fallback (> 15 min or failure); 10 s AbortController timeout + Retry + distinct timeout / 429 / network / validation states"] = (
        "setInterval(initAges, 60000)" in app_p and "STALE_S = 15 * 60" in app_p and "PF_TIMEOUT_MS = 10000" in app_p
        and all(f'data-pf-state' in app_p and k in app_p for k in ('"timeout"', '"ratelimit"', '"network"', '"http"')) and 'id="pf-addr-error"' in home_p
        and all(x in home_p for x in ("data-snapshot-pinned>Snapshot pinned at", "data-last-recheck>Last live re-check", "data-radar-refresh>Refresh",
                                      "data-snapshot-fallback>Showing pinned historical snapshot"))
        and res.get("pf_http_error_reported") is True)
    pp["F05 + V05: cast block hash check + getOwners() next to getThreshold() in the repro; plain-English verdict + heuristic framing + raw enum / JSON (IMMUTABLE_NO_ADMIN = 'No standard upgrade or admin authority detected'); live check vs pinned comparison; 1-click 'Verify live on RPC' (publicnode with drpc / mainnet.base.org fallback): eth_blockNumber first, then reads pinned to that hex block, full hex + decoded value + live block # + host + ms; pre-flight = pinned block hash match + live eth_getCode and owner() / EIP-1967 admin slot (harness click tests, mocked JSON-RPC)"] = (
        '"cast block " + r.pinnedBlock + " --field hash' in app_p and '"getOwners()(address[])"' in app_p
        and all(u in app_p for u in ("https://ethereum-rpc.publicnode.com", "https://eth.drpc.org", "https://base-rpc.publicnode.com", "https://mainnet.base.org"))
        and 'UNCLASSIFIED_CONTRACT_CONTROLLER: "Controller needs further review"' in app_p
        and 'IMMUTABLE_NO_ADMIN: "No standard upgrade or admin authority detected"' in app_p and "cannot be changed" not in app_p
        and res.get("pp2_verdict_plain") is True
        and all(res.get(k) is True for k in ("pp3_inspector_live_rpc", "pp3_preflight_live_rpc_proxy", "pp3_immutable_headline",
                                             "pp3_preflight_live_rpc_owner", "pp3_live_rpc_failure")))
    pp["S02 + V07 (v4.4 wording): 'Runs when you press Check or pick an example below' (nothing runs on page load: harness) + honest telemetry/conversion note; /bounties/ pill leads with funded slots open now"] = (
        "Runs when you press Check or pick an example below." in home_p and res.get("pf_no_fetch_on_load") is True
        and "First-party telemetry stores aggregate counts without raw IPs; X Ads conversion measurement (uwt.js) runs on public pages" in home_p
        and "no cookies" not in home_p
        and f'data-bounty-pill>Wave 3 Open · ${BS.WAVE3_REWARD_USDC} USDC / Protocol · {BS.WAVE3_FUNDED_SLOTS} Slots Open · ${BS.WAVE3_FUNDED_USDC} USDC On-Chain</span>' in read("docs/bounties/index.html")
        and "Wave 1 Genesis (4/4 = $100 USDC) 100% settled on Base" in read("docs/bounties/index.html"))
    def lum_(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    cr_ = lambda a, b: (max(lum_(a), lum_(b)) + 0.05) / (min(lum_(a), lum_(b)) + 0.05)
    # v4 (shadcn tokens): light = :root, dark = .dark; --muted-foreground (which absorbed the old --faint) on background, card and muted
    themes = {"light": css_p[css_p.index(":root {"):css_p.index("}", css_p.index(":root {"))],
              "dark": css_p[css_p.index(".dark {"):css_p.index("}", css_p.index(".dark {"))]}
    tok = lambda blk, k: re.search(rf"--{k}: (#[0-9a-f]{{6}});", blk).group(1)
    contrast = {th: min(cr_(tok(b, "muted-foreground"), tok(b, bg)) for bg in ("background", "card", "muted")) for th, b in themes.items()}
    sm_rule = css_p[css_p.index('[data-slot="button"][data-size="sm"], .btn.sm, .copy {'):css_p.index("}", css_p.index('[data-slot="button"][data-size="sm"], .btn.sm, .copy {'))]
    pp["A01: --muted-foreground >= 5.1:1 on background, card and muted in Light and Dark; Copy buttons are 32 px (sm) with contextual aria-label; inline prose links underlined; h1 on /protocols/ and /request/"] = (
        all(v >= 5.1 for v in contrast.values()) and "height: 32px" in sm_rule
        and not [r for r, t in all_pages.items() for m_ in re.finditer(r'<button class="copy"[^>]*>', t) if "aria-label=" not in m_.group(0)]
        and 'p a:not([data-slot="button"]):not(.btn):not(.copy), dd a:not([data-slot="button"]):not(.btn):not(.copy)' in css_p
        and "<h1>Protocol safety records</h1>" in pages[os.path.join("protocols", "index.html")] and "<h1>Request a dossier</h1>" in pages[os.path.join("request", "index.html")])
    ico_ = open(os.path.join(DOCS, "favicon.ico"), "rb").read() if os.path.exists(os.path.join(DOCS, "favicon.ico")) else b""
    atp_ = open(os.path.join(DOCS, "apple-touch-icon.png"), "rb").read() if os.path.exists(os.path.join(DOCS, "apple-touch-icon.png")) else b""
    pp["V02 + assets: MCP link in every header and footer, no nth-child nav hiding, brand never wraps; valid favicon.ico (16 + 32 px) and 180 px apple-touch-icon.png; referrer meta on every page"] = (
        all('mcp/">MCP</a>' in t for r, t in all_pages.items() if 'class="topbar"' in t) and all('mcp/">MCP server</a></li>' in t for t in all_pages.values() if 'class="ftr"' in t)
        and ".nav a:nth-child(3), .nav a:nth-child(5) { display: none; }" not in css_p and "white-space: nowrap; flex: none; }" in css_p
        and ico_[:4] == b"\x00\x00\x01\x00" and struct.unpack("<H", ico_[4:6])[0] == 2 and atp_[:8] == b"\x89PNG\r\n\x1a\n"
        and struct.unpack(">II", atp_[16:24]) == (180, 180)
        and all('<meta name="referrer" content="strict-origin-when-cross-origin">' in t for t in all_pages.values()))
    try:
        atom_ = ETP.fromstring(read("docs/feed.xml"))
        n_atom = len(atom_.findall("{http://www.w3.org/2005/Atom}entry"))
    except ETP.ParseError:
        n_atom = -1
    jf_ = json.loads(read("docs/api/v1/feed.json"))
    n_items = X["sprints"] + len(rad_p["items"])
    pp["Feeds + SEO: Atom 1.0 /feed.xml and JSON Feed 1.1 /api/v1/feed.json (one entry per Sprint attestation + radar item), discoverable in the home <head>, Subscribe link in the radar header; SoftwareApplication JSON-LD; Swap.io demo canonical + OG"] = (
        n_atom == n_items and jf_.get("version") == "https://jsonfeed.org/version/1.1" and len(jf_.get("items") or []) == n_items
        and 'type="application/atom+xml" href="feed.xml"' in home_p and 'type="application/feed+json" href="api/v1/feed.json"' in home_p
        and 'data-feed-subscribe>Subscribe (RSS / JSON Feed)</a>' in home_p and '"@type": "SoftwareApplication"' in home_p
        and '<link rel="canonical" href="https://pacta.wtf/demos/swapio-x402/">' in read("docs/demos/swapio-x402/index.html")
        and '<meta property="og:title"' in read("docs/demos/swapio-x402/index.html"))
    demo_ = read("docs/demos/swapio-x402/index.html")
    demo_inl = re.findall(r"<script>(.*?)</script>", demo_, re.S)
    demo_csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', demo_)
    demo_src = {d.split(" ")[0]: d.split(" ")[1:] for d in demo_csp.group(1).split(";")} if demo_csp else {}
    pp["S01 (demo): /demos/swapio-x402/ meta CSP before any <script>: script-src 'self' + the sha256 of its single inline script (recomputed here), style-src 'unsafe-inline' (inline style attributes), connect-src self + the first-party beacon Worker; no frame-ancestors"] = (
        len(demo_inl) == 1 and demo_.count('http-equiv="Content-Security-Policy"') == 1 and demo_.find(demo_csp.group(0)) < demo_.find("<script")
        and demo_src.get("script-src") == ["'self'", "'sha256-" + base64.b64encode(hashlib.sha256(demo_inl[0].encode("utf-8")).digest()).decode() + "'"]
        and demo_src.get("default-src") == ["'self'"] and demo_src.get("connect-src") == ["'self'", "https://pacta-x402.pacta.workers.dev"]
        and demo_src.get("object-src") == ["'none'"] and "frame-ancestors" not in demo_csp.group(1)
        and not re.search(r'<[^>]+\son[a-z]+=', demo_) and not re.search(r'(?:src|href)="(?:https?:)?//(?!pacta\.wtf)[^"]*"[^>]*>', re.sub(r"<a\b[^>]*>", "", demo_.split("<body")[0])))
    check("PP2: website, accessibility & trust polish v2 (V06 dossier + free path, F03 radar truth, F02 inspector sync, F04/F06 freshness + timeout, F05 repro, S02, V07, A01 contrast / copy / h1 / links, V02 nav + MCP, icons, referrer, feeds, JSON-LD)",
          all(pp.values()), str([k[:60] for k, v in pp.items() if not v]))

    # ================= Website Edge v3 (strategy-approved spec): scorecards, rosette, /for-protocols/, discovery files, assets =================
    e3 = {}
    sc_ = json.loads(read("docs/api/v1/scorecards.json"))
    cards_ = {c_["slug"]: c_ for c_ in sc_["protocols"]}
    pjp_ = {p_["slug"]: p_ for p_ in json.loads(read("docs/api/v1/protocols.json"))["protocols"]}
    e3["scorecards.json: one card per published protocol; grade OBSERVED <=> rpc_observed; DELTA <=> a parameter-delta record; slice 5 (docs-vs-chain parity) "
       "hollow 'u' for every RPC-observed protocol and never 'u' for an attested one; states only g/b/a/n/u; byte-identical rebuild"] = (
        sc_.get("schema") == "pacta.scorecards.v1" and set(cards_) == set(pjp_) and len(cards_) == X["protocols"]
        and all((c_["grade"] == "observed") == (not pjp_[k_]["easAttested"]) for k_, c_ in cards_.items())
        and all((c_["grade"] == "delta") == any(sf_["classification"] == "parameter_delta" for sf_ in pjp_[k_]["surfaces"]) for k_, c_ in cards_.items())
        and all((c_["factors"][4]["state"] == "u") == (not c_["easAttested"]) for c_ in cards_.values())
        and sum(c_["factors"][4]["state"] == "u" for c_ in cards_.values()) == X["rpc_protocols"]
        and all(f_["state"] in ("g", "b", "a", "n", "u") and [x_["key"] for x_ in c_["factors"]] == ["upgrade", "timelock", "quorum", "emergency", "parity"]
                for c_ in cards_.values() for f_ in c_["factors"])
        and read("docs/api/v1/scorecards.json") == BS.scorecards_json(BS.scorecards(json.loads(read("docs/api/v1/index.json")))))
    ro_bad = []
    for k_, c_ in cards_.items():
        pg_ = pages.get(os.path.join("protocols", k_, "index.html"), "")
        m_ = re.search(r'<svg class="rosette[^"]*"[^>]*aria-label="([^"]+)"', pg_)
        if not (m_ and 'id="scorecard"' in pg_ and all(lbl_ in m_.group(1) for lbl_ in ("Upgradeability", "Timelock floor", "Signer quorum", "Emergency / freeze scope", "Docs-vs-chain parity"))
                and pg_.count("data-factor=") == 5 and f'class="grade g-{c_["grade"]}"' in pg_
                and (c_["easAttested"] or ('data-factor="parity" data-state="u"' in pg_ and 'class="r-u"' in pg_))):
            ro_bad.append(k_)
    e3[f"every /protocols/<slug>/ page ({X['protocols']}): grade pill, 5-slice rosette whose aria-label names all 5 factors, the 5-factor breakdown; hollow uncompared parity on RPC-observed pages"] = not ro_bad
    fp_ = pages.get(os.path.join("for-protocols", "index.html"), "")
    e3["/for-protocols/: h1, 4 verified case studies (Stader, YO, Stake DAO, Moonwell), live badge widget over every protocol, 4-question FAQ, $0 / $500 / $2,500-$5,000 CTAs, in the sitemap"] = (
        "<h1>Turn control-plane transparency into allocator trust.</h1>" in fp_
        and all(f'data-case="{x_}"' in fp_ for x_ in ("stader-labs-ethx", "yo-protocol", "stake-dao", "moonwell-lending-base"))
        and fp_.count("<option value=") == X["protocols"] and "data-badge-widget" in fp_ and fp_.count("<dt>") >= 4
        and all(f'href="../request/?tier={t_}"' in fp_ for t_ in ("community", "rapid-500", "clearance"))
        and "Re-verification · $500, 24h" in fp_ and "Full dossier · $2,500–$5,000, 24h" in fp_ and f"<loc>{BS.BASE_URL}/for-protocols/</loc>" in read("docs/sitemap.xml"))
    oa_ = json.loads(read("docs/api/v1/openapi.json"))
    e3["root discovery files /agent.json, /mcp.json, /openapi.json are valid JSON and byte-identical to /.well-known/agent.json, /.well-known/mcp.json, /api/v1/openapi.json (OpenAPI 3.1 snapshot of the Worker)"] = (
        all(read(f"docs/{a_}") == read(f"docs/{b_}") and isinstance(json.loads(read(f"docs/{a_}")), dict)
            for a_, b_ in (("agent.json", ".well-known/agent.json"), ("mcp.json", ".well-known/mcp.json"), ("openapi.json", "api/v1/openapi.json")))
        and oa_.get("openapi") == "3.1.0" and len(oa_.get("paths", {})) >= 10
        and [s_.get("url") for s_ in oa_.get("servers", [])] == ["https://pacta.fractalneurons.com", API_])   # custom domain first (Worker 5a37bd4)
    rendered_ = "".join(pages.values())
    e3["0 'npx @pacta/mcp-server' / 'npx -y @pacta' install commands and 0 third-party list star counts (97.8k, awesome-mcp-servers) in any rendered page"] = (
        # v4 (M4 trust strip): the merged awesome-mcp-servers listing is linked by its PR (#19455), never as a star count
        not re.search(r"npx[^<\n]{0,8}@pacta/mcp-server|97\.8k|\d+(?:\.\d)?k stars", rendered_)
        and set(re.findall(r'href="([^"]*awesome-mcp-servers[^"]*)"', rendered_)) == {"https://github.com/punkpeye/awesome-mcp-servers/pull/19455"})
    # U2 (v4): Light / Dark / System DropdownMenu (menuitemradio + aria-checked), the button names the current choice, the .dark class
    # follows prefers-color-scheme for System, and a light / dark theme-color pair follows the OS
    e3["theme switcher: Light / Dark / System menu (menuitemradio, aria-checked), label names the current theme, .dark class follows the OS on System, theme-color pair"] = (
        'var word = pref === "system" ? "System" : pref === "dark" ? "Dark" : "Light";' in appjs and 'btn.setAttribute("aria-label", "Theme: " + word)' in appjs and 'classList.toggle("dark", dark)' in appjs
        and 'matchMedia("(prefers-color-scheme: dark)")' in appjs and 'matchMedia("(prefers-color-scheme: dark)")' in read("docs/theme.js")
        and all(t_.count('role="menuitemradio"') == 3 and all(f'data-theme-set="{k_}"' in t_ for k_ in ("light", "dark", "system"))
                and '<meta name="theme-color" content="#0a0b0d" media="(prefers-color-scheme: dark)">' in t_
                for t_ in pages.values() if 'class="topbar"' in t_))
    hv_ = read("docs/index.html")
    e3["hydrated scorecards: every protocol row carries a 5-slice rosette naming all five factors, slice 5 hollow 'uncompared' on every RPC-observed row; /request/?tier=rapid-500 pre-selects the $500 track (harness)"] = (
        all(res.get(k_) is True for k_ in ("e3_hydrated_all", "e3_observed_parity_hollow", "prefill_rapid_500", "v_hero_receipts")))
    e3["homepage = 7 blocks (hero, #how-it-works, #scorecards, #radar, audiences, #pricing, footer): no numbered section headers, no Findings / Inspector / Index / FAQ blocks; "
       "< 150,000 B and < 2,200 elements; h1 'Protocol docs drift. The chain doesn't.'; proof bar counts computed from the catalog"] = (
        len(hv_.encode()) < 150000 and len(re.findall(r"<[a-zA-Z]", hv_)) < 2200 and '<span class="n">' not in hv_
        and not any(f'id="{x_}"' in hv_ for x_ in ("findings", "inspector", "index", "faq", "verify", "onboarding", "about", "request"))
        and re.findall(r'<section class="(?:sec|hero hero-v3)" id="([a-z]+)"|<section class="hero hero-v3">', hv_) is not None
        and [m_ for m_ in re.findall(r'<section class="[^"]+"(?: id="([a-z-]+)")?[^>]*>', hv_)] == ["", "how-it-works", "scorecards", "radar", "audiences", "pricing"]
        and '<h1><span class="l">Protocol docs drift.</span><br><span class="l">The chain doesn’t.</span></h1>' in hv_ and 'class="ftr"' in hv_
        and f'class="stat" data-slot="card"><b>{sum(c_["grade"] == "delta" for c_ in cards_.values())}</b><span>Deltas</span>' in hv_
        and f'class="stat" data-slot="card"><b>{sum(c_["grade"] == "protective" for c_ in cards_.values())}</b><span>Protective</span>' in hv_
        and f'Deltas <span class="num">({sum(c_["grade"] == "delta" for c_ in cards_.values())})</span>' in hv_
        and f'All <span class="num">({X["protocols"]})</span>' in hv_)
    e3["every page: /for-protocols/ in the nav and the footer; the grouped footer (M9) links /protocols/, /mcp/, /bounties/, /leaderboard/, /llms/, /feed.xml, /api/v1/openapi.json, GitHub, the Q&A #44, About, Methodology, Privacy, Terms, security.txt"] = all(
        'for-protocols/">For protocols</a>' in t_ and all(x_ in t_ for x_ in ('protocols/">Protocols</a', 'mcp/">MCP</a', 'leaderboard/">Leaderboard</a',
                                                                                  'feed.xml">Atom feed</a', 'api/v1/openapi.json">OpenAPI 3.1</a', 'security.txt">security.txt</a',
                                                                                  'about/">About</a', 'methodology/">Methodology</a', 'privacy/">Privacy</a', 'terms/">Terms</a'))
        and f'href="{BS.COMMUNITY_QA_URL}"' in t_ for t_ in pages.values() if 'class="ftr"' in t_)
    check("E3: Website Edge v3 (scorecards + 5-factor rosette, /for-protocols/, root discovery files, theme label, no npx / star counts)",
          all(e3.values()), str([k_[:70] for k_, v_ in e3.items() if not v_]) + f" rosette bad {ro_bad[:4]}")

    # ================= Website Edge v3.1 (D1): every rosette factor bound to its own control surface; recon_trail provenance =================
    import scorecard as SCD
    d1 = {}
    st_ = {k_: {f_["key"]: f_["state"] for f_ in c_["factors"]} for k_, c_ in cards_.items()}
    d1["yo-protocol: vault upgrades bound to the 48h YO Timelock (upgrade 'g') while the 0s Approval Registry Safe sets the timelock floor ('a')"] = (
        st_["yo-protocol"]["upgrade"] == "g" and st_["yo-protocol"]["timelock"] == "a")
    d1["frax-usd-frxusd: the sfrxUSD ProxyAdmin owned directly by the 3-of-5 Safe (no timelock) is the weakest upgrade path (upgrade 'a', timelock 'a'), not the frxUSD 1d timelock"] = (
        st_["frax-usd-frxusd"]["upgrade"] == "a" and st_["frax-usd-frxusd"]["timelock"] == "a")
    d1["eigenlayer-core: the 1-of-2 ExecutorMultisig co-owned by the 10d timelock and the CommunityMultisig bypasses the delay (upgrade never 'g'; 'a')"] = (
        st_["eigenlayer-core"]["upgrade"] == "a" and st_["eigenlayer-core"]["timelock"] == "a")
    d1["falcon-finance-usdf-susdf: the user cooldownDuration() never counts as an admin timelock floor"] = (
        "cooldown" not in str(next(f_ for f_ in cards_["falcon-finance-usdf-susdf"]["factors"] if f_["key"] == "timelock")["evidence"]))
    A_ = lambda n_: "0x" + n_ * 40
    proxy_ = {"id": "syn-proxy", "surface": "Vault", "onchain_observed": f"Vault {A_('1')}: EIP-1967 admin = ProxyAdmin {A_('2')}"}
    cooldown_ = {"id": "syn-cooldown", "surface": "Unstaking cooldown: 7 days", "observed_delay_seconds": 604800,
                 "observed_delay_source": {"contract": A_("3"), "getter": "cooldownDuration()"}, "onchain_observed": f"sVault {A_('3')}: cooldownDuration() = 604800"}
    param_ = {"id": "syn-param", "surface": "Fee parameter timelock: 7 days", "observed_delay_seconds": 604800,
              "observed_delay_source": {"contract": A_("5"), "getter": "getMinDelay()"}, "onchain_observed": f"FeeTimelock {A_('5')}: getMinDelay() = 604800s; owner of FeeController {A_('6')}"}
    fs_ = lambda rs_: {f_["key"]: f_["state"] for f_ in SCD.factors(rs_, True, "aligned")}
    gate_ = {"id": "syn-gate", "surface": "Staked token unstaking: no withdrawal delay",
             "onchain_observed": f"WithdrawGate {A_('7')}: delay() = 0s; owner() = Safe {A_('8')}"}
    tl_ = {"id": "syn-tl", "surface": "Governance timelock: 5 days", "observed_delay_seconds": 432000,
           "observed_delay_source": {"contract": A_("9"), "getter": "getMinDelay()"}, "onchain_observed": f"TimelockController {A_('9')}: getMinDelay() = 432000s"}
    rbac_ = {"id": "syn-rbac", "surface": "Configuration owner: an RBACTimelock", "observed_delay_seconds": 10800,
             "observed_delay_source": {"contract": A_("c"), "getter": "getMinDelay()"},
             "onchain_observed": f"Router {A_('d')}: owner() = RBACTimelock {A_('c')} (getMinDelay() = 10800s for scheduled operations)"}
    byp_ = dict(rbac_, onchain_observed=rbac_["onchain_observed"] + f"; BYPASSER_ROLE has 1 member, {A_('e')}, which can execute calls immediately "
                                                                    "through bypasserExecuteBatch (no schedule, no delay).")
    ccip_tl = next((f_ for f_ in cards_.get("chainlink-ccip", {}).get("factors", []) if f_["key"] == "timelock"), None)
    d1["RBACTimelock bypass: a 3h scheduled delay with an active immediate bypasserExecuteBatch holder is a 0s floor ('a'), never '3h minimum'; "
       "without the bypass it stays 'b'; chainlink-ccip (when published) reads the bypass"] = (
        fs_([rbac_])["timelock"] == "b" and fs_([byp_])["timelock"] == "a"
        and (ccip_tl is None or (ccip_tl["state"] == "a" and "bypasser" in ccip_tl["value"] and "3h" not in ccip_tl["value"])))
    opx_ = dict(rbac_, onchain_observed=rbac_["onchain_observed"] + f"; operator() = {A_('f')} (no contract code), which can run "
                                                                     "executeOperatorProposal immediately (no delay) for proposals governance approved.")
    eoa_ = dict(rbac_, onchain_observed=rbac_["onchain_observed"] + f"; pauser() = {A_('f')} (no contract code)")
    # the quorum exemption is bound to the operator() relation itself: any other EOA holder in the same clause still counts
    opw_ = dict(rbac_, onchain_observed=rbac_["onchain_observed"] + "; executeOperatorProposal executes approved proposals, while owner() = EOA "
                                                                     + A_("2"))
    opp_ = dict(rbac_, onchain_observed=opx_["onchain_observed"][:-1] + f", and a separate pauser() = EOA {A_('3')}.")
    ops_ = dict(rbac_, onchain_observed=opx_["onchain_observed"] + f"; owner() = EOA {A_('2')}")
    d1["operator fast path: an approved-proposal executeOperatorProposal route with no delay is a 0s floor ('a') with its own label; only "
       "the operator()'s own key (no contract code) is exempt from the single-key quorum: an owner() EOA joined by 'while' or after ';', or a "
       "pauser() EOA inside the operator clause, still reads 'a'"] = (
        fs_([opx_])["timelock"] == "a" and "operator" in next(f_["value"] for f_ in SCD.factors([opx_], True, "aligned") if f_["key"] == "timelock")
        and fs_([opx_])["quorum"] == fs_([rbac_])["quorum"] == "n" and fs_([eoa_])["quorum"] == "a"
        and fs_([opw_])["quorum"] == "a" and fs_([opp_])["quorum"] == "a" and fs_([ops_])["quorum"] == "a")
    d1["text-parsed withdrawal delay: a 0s unstaking-gate delay() in the evidence text never sets the admin timelock floor (5d timelock stays 'g')"] = (
        fs_([gate_, tl_])["timelock"] == "g" and fs_([gate_])["timelock"] == "n")
    d1["synthetic authority separation: an undetermined proxy stays upgrade 'n' when an unrelated 7d withdrawal cooldown or 7d parameter timelock is added; a cooldown never sets the timelock floor"] = (
        fs_([proxy_])["upgrade"] == "n" and fs_([proxy_, cooldown_])["upgrade"] == "n" and fs_([proxy_, param_])["upgrade"] == "n"
        and fs_([proxy_, cooldown_])["timelock"] == "n" and fs_([proxy_, param_])["timelock"] == "g")
    fx_ = {"reconciled": True, "pinnedBlock": 200, "reconciledFrom": [{"blockNumber": 100, "easUid": "0x" + "a" * 64, "summary": "delta"}],
           "reconciledTo": [{"blockNumber": 200, "easUid": "0x" + "b" * 64, "docsCommit": "c0ffee1234567890", "docsSnapshot": "audits/sprint-99/x.md", "docsSha256": "d" * 64}]}
    rt_ = BS.recon_trail(fx_)
    d1["recon_trail: step 1 initial finding (block, Base EAS UID #1) -> step 2 verified resolution with its block, Base EAS UID #2 and docs commit / snapshot (synthetic reconciledFrom fixture)"] = (
        rt_.count("<li>") == 2 and "block #100 · Base EAS 0xaaaaaaaa…aaaaaa" in rt_
        and "block #200 · Base EAS 0xbbbbbbbb…bbbbbb · docs commit <code>c0ffee123456</code> · docs snapshot <code>audits/sprint-99/x.md</code>" in rt_
        and rt_.index("Initial finding") < rt_.index("Verified resolution") and BS.recon_trail({"reconciled": False}) == ""
        and all(len(c_["reconciledTo"]) == len(c_["reconciledFrom"]) for c_ in cards_.values()))
    check("E3.1 (D1): rosette factors bound per control surface (YO / Frax USD / EigenLayer regressions, cooldown and unrelated-delay separation); recon_trail step-2 provenance",
          all(d1.values()), str([k_[:70] for k_, v_ in d1.items() if not v_]) + str({k_: st_[k_] for k_ in ("yo-protocol", "frax-usd-frxusd", "eigenlayer-core")}))

    # ================= Website Edge v3.2: an upgrade path resolves only through a controller bound in its own clause =================
    d2 = {}
    up_ = lambda rs_: fs_(rs_)["upgrade"]
    multi_ = {"id": "syn-multi", "surface": "Proxy upgrade and parameter controls", "observed_delay_seconds": 604800,
              "observed_delay_source": {"contract": A_("b"), "getter": "getMinDelay()"},
              "onchain_observed": f"Vault {A_('1')}: EIP-1967 admin = ProxyAdmin {A_('a')}, owner unknown; ParamTimelock {A_('b')}: getMinDelay() = 604800s"}
    d2["same-record multi-surface probe: a record whose surface says 'upgrade' and whose 7d delay source is a parameter timelock in another clause leaves the proxy upgrade 'n'"] = (
        up_([multi_]) == "n")
    ctx_ = {"id": "syn-ctx", "surface": "Vault", "onchain_observed": f"ProxyAdmin {A_('a')} owner unknown, unrelated reference {A_('b')}"}
    pt_ = {"id": "syn-pt", "surface": "Parameter timelock: 7 days", "observed_delay_seconds": 604800,
           "observed_delay_source": {"contract": A_("b"), "getter": "getMinDelay()"}, "onchain_observed": f"ParamTimelock {A_('b')}: getMinDelay() = 604800s"}
    same_ = {"id": "syn-same", "surface": "Vault", "onchain_observed": f"ProxyAdmin {A_('a')}, owner unknown, ParamTimelock {A_('b')} getMinDelay() = 604800s"}
    d2["context-address probe: an address merely mentioned in the proxy clause (or a delay in the same clause) whose 7d delay another record establishes leaves the upgrade 'n'"] = (
        up_([ctx_, pt_]) == "n" and up_([same_]) == "n")
    bound_ = {"id": "syn-bound", "surface": "Vault", "onchain_observed": f"Vault {A_('1')}: EIP-1967 admin = ProxyAdmin {A_('a')}, owner() = Timelock {A_('b')}"}
    d2["positive control: the same 7d timelock explicitly bound as the ProxyAdmin owner() does decide the upgrade path ('g')"] = up_([bound_, pt_]) == "g"
    eq_ = next(f_ for f_ in cards_["eigenlayer-core"]["factors"] if f_["key"] == "quorum")
    d2["eigenlayer-core: the 1-of-2 ExecutorMultisig (owners: the 10d timelock and the 9-of-13 CommunityMultisig) is a contract-executor wrapper, never scored as a weak single-signer quorum"] = (
        eq_["state"] != "a" and "1-of-2" not in eq_["value"] and "contract-executor wrapper" in eq_["value"])
    check("E3.2: upgrade paths resolve only through a controller bound in their own clause (multi-surface, context-address and same-clause probes + positive control); EigenLayer contract-executor quorum",
          all(d2.values()), str([k_[:70] for k_, v_ in d2.items() if not v_]) + f" eigenlayer quorum {eq_['state']} {eq_['value']}")

    # ================= Visitor review P1 + P2 (first success, understanding, discovery, narrow screens, provenance, editorial independence) =================
    import control_diff as CDV1
    import build_b2a_feeds as B2AV1
    home_v = read("docs/index.html")
    sp_v = BS.site_protocols(idx_)
    v1 = {}
    i_try, i_conn, i_pf = home_v.find('class="hero-try"'), home_v.find('id="connect"'), home_v.find('id="preflight"')
    st_v = next(v for v in sp_v.values() if v["slug"] == "stader-labs-ethx")
    st_wd = CDV1.what_differs(st_v["entries"])
    v1["P1 first success (Edge v3): three receipt pills (Stader / YO / Moonwell) render their pinned, attested receipt instantly and run the live check of the same contract (harness)"] = (
        res.get("v_hero_receipts") is True and res.get("v_hero_click_fetches") is True
        and (st_wd["changed"][0]["observed"], st_wd["changed"][0]["documented"]) == ("3-of-6", "3-of-5"))
    ua_files = {f: read(f) for f in ("docs/index.html", "docs/mcp/index.html", "README.md", "docs/llms.txt", "docs/llms-full.txt", "docs/SKILL.md")}
    bare_curl = [f for f, t in ua_files.items() if re.search(r"curl -s (?!-A )[\"'&]", t)]
    bare_curl += [r for r, t in pages.items() if r.startswith("protocols" + os.sep) and re.search(r"curl -s (?!-A )&quot;", t)]
    # T2 (v4): no infrastructure excuses in the copy: plain curl and python-requests quickstarts (both work with their default
    # User-Agent), Python stdlib reads the static JSON on pacta.wtf; 0 'error 1010' / 'Cloudflare' mentions on pages and agent docs
    t2_files = list(pages.values()) + [read(f) for f in ("docs/llms.txt", "docs/llms-full.txt", "docs/SKILL.md", "README.md")]
    v1["T2: plain HTTP quickstarts (curl / python-requests / static JSON), 0 'error 1010' or Cloudflare-edge copy on any page, agent doc or the README"] = (
        not any(re.search(r"error 1010|Cloudflare(?:'|&#x27;|’)s edge", t) for t in t2_files)
        and all('curl -s &quot;' + API_ + '/v1/check/preflight' in read(f) for f in ("docs/index.html", "docs/mcp/index.html"))
        and all("import requests" in read(f) and "urllib.request.urlopen(&quot;" + BS.BASE_URL + "/api/v1/scorecards.json&quot;)" in read(f)
                for f in ("docs/index.html", "docs/mcp/index.html"))
        and not [r for r, t in pages.items() if '-A &quot;my-agent' in t] and 'curl -s -A' not in read("README.md")
        and 'curl -s "https://pacta-x402.pacta.workers.dev/v1/check/preflight' in read("README.md"))
    v1["P1 attribution never blocks a call: CALLER_FIELDS_DOC / SKILL.md / MCP README say optional (omitted or invalid values dropped, never -32602)"] = (
        "OPTIONAL" in B2AV1.CALLER_FIELDS_DOC and "never block a call" in B2AV1.CALLER_FIELDS_DOC and "-32602" not in B2AV1.CALLER_FIELDS_DOC
        and B2AV1.CALLER_FIELDS_DOC in read("docs/SKILL.md")
        and read("docs/SKILL.md") == read("packages/mcp-server/SKILL.md") and "Free-tier caller fields (optional attribution)" in read("packages/mcp-server/README.md")
        and "required on every gateway tool" not in read("packages/mcp-server/README.md"))
    wd_bad = []
    for name_v, v in sp_v.items():
        t = pages[os.path.join("protocols", v["slug"], "index.html")]
        wd = CDV1.what_differs(v["entries"])
        if not wd:
            if "data-what-differs" in t:
                wd_bad.append(v["slug"] + ": unexpected")
            continue
        # V8 (v4): a short structured value is shown as is; a long one as a whole-word excerpt (never mid-word / mid-address) with the
        # full verbatim record text behind "Show the full ..."
        by_v = {e["id"]: e for e in v["entries"]}
        ex_ = lambda short_, full_: short_ if (not short_.endswith("…") and len(short_) <= 60) else BS.clean_excerpt(full_ or short_)
        want = [f'<li data-wd-changed><b>{html.escape(c["parameter"])}</b>: <span class="obs">{html.escape(ex_(c["observed"], by_v[c["recordId"]]["onchain_observed"]))}</span> observed vs '
                f'<span class="doc">{html.escape(ex_(c["documented"], by_v[c["recordId"]]["documented_reference"]))}</span> documented' for c in wd["changed"]]
        if not (all(w in t for w in want) and t.find("</header>") < t.find("data-what-differs") < t.find("Check it live (free)")):
            wd_bad.append(v["slug"])
    n_flagged = sum(1 for v in sp_v.values() if CDV1.what_differs(v["entries"]))
    v1[f"P1 What differs: every flagged protocol page ({n_flagged}) leads with Changed / discrepant then Matched, right under the title; == tools/control_diff.py; inspector sheet + app.js port agree (harness)"] = (
        not wd_bad and n_flagged >= 20
        and all(("data-what-differs" in BS.sheet(e)) == bool(CDV1.what_differs([e])) for e in idx_["entries"])
        and all("data-what-differs" in pages[os.path.join("protocols", BS.protocol_slug(e["protocol"]), "index.html")] for e in idx_["entries"] if CDV1.what_differs([e])))
    v1["P1 discovery: Status x Chain x search filters, Clear all, empty-state recovery (harness)"] = all(res.get(k) is True for k in (
        "pfilter_status_x_chain", "pfilter_empty_prompt", "pfilter_recover_chain", "pfilter_clear_all"))
    css_v = read("docs/styles.css")
    v1["P1 narrow screens (375 / 753 px): overflow-x clip safety net, Sheet nav below 768 px, wrapping filter groups, one-column plans, wrapped code blocks"] = (
        "html, body { overflow-x: clip; }" in css_v and "@media (max-width: 767px)" in css_v and "@media (max-width: 639px)" in css_v
        and "display: inline-flex; flex-wrap: wrap;" in css_v[css_v.index('[data-slot="tabs-list"], .seg {'):css_v.index("}", css_v.index('[data-slot="tabs-list"], .seg {'))]
        and ".plans { grid-template-columns: minmax(0, 1fr); }" in css_v
        and "white-space: pre-wrap; overflow-wrap: anywhere;" in css_v[css_v.index(".term pre {"):css_v.index("}", css_v.index(".term pre {"))]
        and ".memo, .memo p, .memo li, .memo dd, .memo dt, .memo h1, .memo h2, .memo-foot { overflow-wrap: anywhere; }" in css_v
        and ".whatdiffers li { margin: 6px 0; overflow-wrap: anywhere; }" in css_v
        and not unwrappable_runs(pages))
    pl = B2AV1.protocols_line(idx_, json.loads(read("docs/api/v1/rpc-pinned.json")))
    v1["P2 template leak fixed + one protocol count everywhere (74 = 62 Base-EAS-attested / 98 Sprint records + 12 RPC-pinned)"] = (
        not any("{counts(" in read(f) or "counts(idx)" in read(f) for f in ("docs/llms.txt", "docs/llms-full.txt", "docs/llms/index.html", "docs/index.html"))
        and pl.startswith(f"{X['protocols']} indexed protocols: {X['eas_protocols']} Base-EAS-attested protocols ({X['records']} Sprint records")
        and f"+ {X['rpc_protocols']} RPC-pinned protocols" in pl
        and pl in read("docs/llms.txt") and pl in read("docs/llms-full.txt") and html.escape(pl, quote=False) in read("docs/llms/index.html")
        and re.search(r'class="stat" data-slot="card"><b>' + str(X["protocols"]) + r'</b><span>Protocols scored</span>', home_v) is not None)
    rad_v = json.loads(read("docs/api/v1/radar.json"))
    v1["P2 provenance: radar refreshed from live RPC (finalized block, 2 RPCs), UTC observation + relative age, pinned snapshot label (no block number: N5); executed only via isOperationDone"] = (
        rad_v["refreshed_at"]["tag"] == "finalized" and rad_v["refreshed_at"]["block_number"] >= 26434340 and rad_v["refreshed_at"]["rpcs_cross_checked"] == 2
        and home_v.count(f'data-age="{rad_v["refreshed_at"]["block_timestamp"]}"') >= 2 and "(pinned snapshot observed <time" in home_v
        and all(o["done"] for it in rad_v["items"] if not it.get("eta") for o in it["operations"]) and res.get("v_ages") is True)
    ed_bad = []
    for v in sp_v.values():
        t = pages[os.path.join("protocols", v["slug"], "index.html")]
        i_ed = t.find("data-editorial-independence")
        i_paid = max(t.find("Reconciliation Dossier"), t.find("callout"))
        last_rec = max(t.rfind(f'id="{html.escape(e["id"])}"') for e in v["entries"])
        paid_at = [m_.start() for m_ in re.finditer(r"\$5,000|\$1,500|\$99|\$19\b|Reconciliation Dossier|id=\"badge-status\"|id=\"issuer-clearance\"|data-cta=\"seal_99\"|data-cta=\"scan_19\"", t)]
        if not (0 < last_rec < i_ed and html.escape(BS.EDITORIAL_INDEPENDENCE, quote=False) in t and t.find("cast ") < i_ed
                and (t.find('class="callout') == -1 or i_ed < t.find('class="callout')) and paid_at and all(i_ed < p_ for p_ in paid_at)):
            ed_bad.append(v["slug"])
    pr_v = re.search(r'<section class="sec" id="pricing">.*?</section>', home_v, re.S)
    v1["P2 editorial independence: the exact firewall sentence on every protocol page (after the free evidence + cast workflow, before the badge card and every paid-service / $ mention) and on #pricing"] = (
        not ed_bad and bool(pr_v) and html.escape(BS.EDITORIAL_INDEPENDENCE, quote=False) in pr_v.group(0)
        and BS.EDITORIAL_INDEPENDENCE == "Payment never alters a Pacta classification. A status changes only when onchain contract state or public documentation changes and is verified at a new finalized block.")
    lk_v = json.loads(read("docs/api/v1/lookup.json"))
    st_item = next(x for x in lk_v["items"] if x.get("slug") == "stader-labs-ethx")
    v1["P1 catalog for the Worker / MCP: lookup items carry whatDiffers (== control_diff), pinnedBlock and relatedContracts (the ETHx token links Stader)"] = (
        "0xA35b1B31Ce002FBF2058D22F30f95D405200A15b" in st_item["relatedContracts"] and st_item["pinnedBlock"] == 26403676
        and st_item["whatDiffers"] == CDV1.what_differs(st_v["entries"])
        and all(x.get("whatDiffers") == CDV1.what_differs(next(v for v in sp_v.values() if v["slug"] == x["slug"])["entries"])
                for x in lk_v["items"] if x["kind"] == "protocol"))
    v1["P1 live checker shows confidence + catalogMatch next to the score, guards catalog URLs, renders the pinned fallback (harness)"] = all(res.get(k) is True for k in (
        "v_hero_receipts", "v_hero_click_fetches", "v_assessment_next_to_score", "v_catalog_match", "v_catalog_url_guard", "v_fallback_rendered"))
    v1["0 Discord links anywhere on the site or in the README"] = not any(re.search(r"discord\.(gg|com)", t, re.I) for t in list(pages.values()) + [read("README.md")])
    check("V1: visitor review P1 + P2 (live check first, User-Agent quickstarts, optional attribution, What differs, Status x Chain filters, 375 px layout, "
          "template leak + counts, radar provenance, editorial independence, catalog cross-link)", all(v1.values()), str([k[:70] for k, v in v1.items() if not v]))

    scope = [p for p in glob.glob(os.path.join(ROOT, "docs", "**", "*"), recursive=True) + glob.glob(os.path.join(ROOT, "audits", "**", "*"), recursive=True)
             + glob.glob(os.path.join(ROOT, "tools", "**", "*"), recursive=True) + [os.path.join(ROOT, "README.md"), os.path.abspath(__file__)]
             if os.path.isfile(p) and p.endswith((".html", ".txt", ".json", ".xml", ".js", ".css", ".md", ".py"))]
    leaks = sorted({os.path.relpath(p, ROOT) for p in scope if tokens(open(p, errors="replace").read()) & DENY_SHA256})
    check("no private / quarantined identifiers (SHA-256 token deny-list)", not leaks, f"{len(scope)} files scanned; leaks in: {leaks}")

    graph_manifest_checks(cli)

    width = max(len(n) for n, _, _ in RESULTS)
    for name, ok, detail in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
