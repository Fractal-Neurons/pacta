"""Build the Pacta static site (docs/) from the data files, so counts can never drift.

  python3 tools/refresh_radar.py            # (live, read-only) refresh docs/api/v1/radar.json
  python3 tools/make_og.py --font-dir DIR   # (optional) re-render og-preview.png / favicon.png
  python3 tools/build_site.py               # writes docs/index.html, request/, briefs/*/ (from tools/briefs_src/),
                                            # llms.txt, robots.txt, sitemap.xml, .well-known/security.txt, .nojekyll
  python3 verify_site_v2.py                 # checks the result

Domain cutover: change BASE_URL below (one line) and rebuild; every absolute URL (canonical, Open Graph, X card,
sitemap, robots, security.txt, llms.txt, brief metadata) is derived from it.

Design (v3): institutional editorial + data terminal. Hairline structure, 2-4px radii, Paper (light) default with a
Slate (dark) theme, tabular numerals, no web fonts and no third-party requests. Every call to action stays in the
browser: there are no mailto: links (they are dead clicks without a desktop mail client); requests go through the
coverage-request builder (#request and /request/), which opens a pre-filled GitHub intake issue, a Gmail web compose
window, or copies the scope brief.
"""

import datetime as dt
import html
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import onboarding_render as OR  # noqa: E402
import build_b2a_feeds as B2A  # noqa: E402

BASE_URL = "https://pacta.wtf"   # cutover: "https://pacta.fractalneurons.com"

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DOCS = os.path.join(ROOT, "docs")
BRIEF_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "briefs_src")
E = html.escape
CONTACT = "pacta@dri.network"
REPO = "https://github.com/Fractal-Neurons/pacta"
FN = "https://fractalneurons.com"
TITLE = "Pacta · Free pre-execution API for AI agents"
DESC = "Free pre-execution contract checks for AI agents. No API key, no wallet."
OG_TITLE = "Free pre-execution contract safety checks for AI agents"
H1 = "Free Pre-Execution Contract & Governance Safety API for AI Agents — Zero API Key, Zero Wallet, 1 Call"
API = "https://pacta-x402.pacta.workers.dev"          # live Cloudflare Worker (free launch: $0, no key, no wallet)
MCP_URL, OPENAPI_URL = API + "/mcp", API + "/openapi.json"
RATE_LIMIT = "60 requests / minute per caller"
# Live checker presets: (label, chain, address). Public contracts; the ETHx token is an indexed record (Stader, sprint 12).
PREFLIGHT_PRESETS = [("USDC on Base", "base", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"),
                     ("USDC on Ethereum", "ethereum", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
                     ("Stader ETHx", "ethereum", "0xA35b1B31Ce002FBF2058D22F30f95D405200A15b")]
BRIEFS = {
    "ethena-ops-0x0ca0-0x1fe5": "Pre-execution brief: two queued Ethena timelock operations onboard RLUSD and USAT to EthenaMinting "
                                "at 200M / 20M USDe-per-block caps (1-day delay; ETAs 2026-11-14 10:20–10:22 UTC).",
    "etherfi-op-0x244e": "Pre-execution brief: ether.fi operation 0x244e…359f moves the EtherfiL1SyncPoolETH LayerZero V2 "
                         "delegate behind the 10-day EtherFiTimelock (ETA 2026-11-20 16:54 UTC).",
    "treehouse-op-0x2f11": "Pre-execution brief: a queued 5-day timelock operation upgrades the Treehouse TREE token (not tETH) "
                           "and installs a 5-of-7 Safe blacklister (ETA 2026-11-17 04:51 UTC).",
}
NAV = [("preflight", "Free API"), ("protocols/", "Protocols"), ("inspector", "Inspector"), ("radar", "Radar"), ("findings", "Findings"), ("index", "Index"), ("verify", "Verify"),
       ("pricing", "Pricing"), ("faq", "FAQ")]
# Engagement tracks shown in #pricing and offered by the request builder. key -> (title, price, unit, summary, GitHub dropdown option)
# One commercial offer (for collateral issuers) plus the free community queue. The public data itself (every indexed
# record, the timelock radar, briefs, /api/v1/*.json and llms.txt) is free and real-time for everyone: no paywall, no delay.
# The GitHub dropdown option strings must match .github/ISSUE_TEMPLATE/request-scan.yml exactly (prefill is by value).
CLEARANCE_PRICE, MONITORING_PRICE = "$5,000 USDC", "$1,500 / month"
TRACKS = {
    "clearance": ("24h Collateral Onboarding & Delta Clearance Attestation", CLEARANCE_PRICE, "flat",
                  f"Block-pinned control-plane audit, GitBook / config reconciliation PR, Base EAS Aligned attestation and a "
                  f"Curator Diligence Dossier, delivered in 24 hours. Optional continuous Aligned monitoring: {MONITORING_PRICE}.",
                  "24h Collateral Onboarding & Delta Clearance Attestation ($5,000 USDC flat; optional $1,500/mo Aligned monitoring)"),
    "community": ("Community queue", "Free", "",
                  "Standard public queue, unscheduled (typically 6–8 weeks). Curators and risk stewards always have free, "
                  "real-time access to pacta.wtf and llms.txt.",
                  "Community queue (free; unscheduled, typically 6–8 weeks)"),
}
DEFAULT_TRACK = "clearance"
# Payment rail for the clearance offer. The treasury is an externally owned account (no contract code on Base or
# Ethereum), so the same key controls it on both chains; USDC contracts are Circle's native deployments.
USDC = {"Base": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "Ethereum": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"}
VULN_ROUTE = ("Exploit-sensitive vulnerabilities are never published here. They go through the protocol’s Immunefi or "
              "Cantina bounty programme, or to a partner audit firm under a 15% referral partnership.")
FINDINGS = [  # (record id, headline, explanation html, observed, documented, link, link label)
    ("ethena-minting-rlusd-usat-onboarding-ops",
     "New Ethena collateral can be approved on a 1-day timelock; the docs describe 7 days.",
     'Two queued operations onboard RLUSD and USAT at 200M / 20M USDe-per-block caps, the same as USDC / USDT, with '
     '<code>stablesDeltaLimit = 0</code>. <code>getMinDelay()</code> returns 86,400s.',
     ("Observed", "1d"), ("Docs", "7d"), "briefs/ethena-ops-0x0ca0-0x1fe5/", "Read the brief"),
    ("stader-ethx-manager-safe-and-timelock",
     "Stader’s Manager Safe is 3-of-6 on-chain; the docs say 3-of-5.",
     "The ETHx upgrade path itself sits behind a 7-day TimelockController, as documented. The difference is the Manager "
     "multisig’s signer set.",
     ("Observed", "3-of-6"), ("Docs", "3-of-5"), None, "View record"),
    ("curve-crvusd-factory-lending-owner-proxy",
     "crvUSD market creation now passes through a LendingOwnerProxy wrapper.",
     "ControllerFactory <code>admin()</code> is a LendingOwnerProxy whose <code>dao()</code> is the CurveOwnershipAgent "
     "(7-day Aragon vote), with a 5-of-9 EmergencyDAO. The docs still name the agent as the admin.",
     ("Observed", "LendingOwnerProxy"), ("Docs", "OwnershipAgent"), None, "View record"),
    ("inverse-firm-borrowcontroller-staleness-sentinel",
     "A zero staleness threshold switches FiRM’s oracle staleness check off for sDOLA; a queued 48h fix turns it on.",
     "<code>stalenessThreshold = 0</code> makes <code>isPriceStale</code> return false. A queued Timelock transaction sets "
     "86,500s.",
     ("Observed", "0 (off)"), ("Queued", "86,500s"), None, "View record"),
]


def short(h, a=6, b=4):
    return h[:a] + "…" + h[-b:]


def utc(t, secs_=False):
    return dt.datetime.fromtimestamp(t, dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC" if secs_ else "%Y-%m-%d %H:%M UTC")


def secs(s):
    """Exact compact duration: 0 -> 0s, 1 -> 1s, 86400 -> 1d, 129600 -> 1d 12h. Mirrors secs() in docs/app.js."""
    if s is None:
        return "—"
    s, parts = int(s), []
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        if s >= n:
            q, s = divmod(s, n)
            parts.append(f"{q}{unit}")
    return " ".join(parts) or "0s"


def copy_btn(value, label="Copy"):
    return f'<button class="copy" type="button" data-copy="{E(value)}">{label}</button>'


def hexref(value, a=6, b=4):
    """Truncated hex for display, full value in title + copy button. Never lets a 42/66-char string break a layout."""
    return f'<span class="addr" title="{E(value)}">{E(short(value, a, b))}</span>{copy_btn(value)}'


def head(title, desc, url, prefix="", og_title=OG_TITLE, og_type="website", image=f"{BASE_URL}/og-preview.png", extra=""):
    """Order matters: everything social/agent-relevant comes first and stays inside the first 1.2 KB.
    b.js is the first-party beacon (docs/b.js, < 1.5 KB): no cookies, no storage ids, no third parties, honours DNT."""
    t, d = E(title), E(desc)
    parts = [
        '<!doctype html><html lang="en"><head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{t}</title>",
        f'<meta name="description" content="{d}">',
        f'<link rel="canonical" href="{url}">',
        f'<meta property="og:type" content="{og_type}">',
        '<meta property="og:site_name" content="Pacta by Fractal Neurons">',
        f'<meta property="og:title" content="{E(og_title)}">',
        f'<meta property="og:description" content="{d}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{image}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{E(og_title)}">',
        f'<meta name="twitter:description" content="{d}">',
        f'<meta name="twitter:image" content="{image}">',
    ] + ([extra] if extra else []) + [
        f'<link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">',
        f'<link rel="icon" href="{prefix}favicon.png" type="image/png" sizes="32x32">',
        f'<link rel="stylesheet" href="{prefix}styles.css">',
        f'<link rel="alternate" type="text/markdown" href="{prefix}llms.txt" title="llms.txt">',
        '<script>document.documentElement.className="js";try{if(localStorage.getItem("pacta-theme")==="slate")'
        'document.documentElement.dataset.theme="slate"}catch(e){}</script>',
        f'<script src="{prefix}app.js" defer></script>',
        f'<script src="{prefix}b.js" defer></script>',
        "</head>",
    ]
    return "\n".join(parts)


def livebar_etas(radar):
    """Every queued ETA as "eta|protocol;…" (ascending), so app.js can move "Next" past ETAs that have elapsed since the
    deterministic build; the no-JS text names the earliest ETA and is dated by the radar block."""
    pairs = sorted({(int(op["eta"]), it["protocol"]) for it in radar["items"] for op in it.get("operations", []) if op.get("eta")}
                   | {(int(it["eta"]), it["protocol"]) for it in radar["items"] if it.get("eta")})
    return ";".join(f"{eta}|{name.replace(';', ',').replace('|', '/')}" for eta, name in pairs)


def topbar(home=""):
    """home = "" on the homepage, "../" or "../../" on sub-pages."""
    links = "".join(f'<a href="{home}{k if k.endswith("/") else "#" + k}">{lbl}</a>' for k, lbl in NAV)   # "x/" = a page
    req = "#request" if home == "" else f"{home}request/"
    return (f'<a class="skip" href="#main">Skip to content</a>\n'
            f'<header class="topbar"><div class="wrap">'
            f'<a class="brand" href="{home or "./"}"><img src="{home}favicon.svg" alt="" width="22" height="22">PACTA<small>by Fractal Neurons</small></a>'
            f'<nav class="nav" aria-label="Sections">{links}</nav>'
            f'<div class="tools"><button class="tt" type="button" aria-label="Theme: Paper (switch to Slate)">'
            f'<span data-t="paper" class="on">Paper</span><span data-t="slate">Slate</span></button>'
            f'<a class="btn sm primary" href="{req}">Request coverage</a></div>'
            f'</div></header>')


def footer(count_line, reg, home=""):
    return (f'<footer class="ftr"><div class="wrap">'
            f'<span>Pacta · Fractal Neurons · pacta.base.eth · {E(count_line)}</span>'
            f'<nav aria-label="Footer"><a href="{REPO}" target="_blank" rel="noopener">GitHub</a>'
            f'<a href="{home}api/v1/index.json">JSON feed</a><a href="{home}llms.txt">llms.txt</a>'
            f'<a href="https://basescan.org/address/{E(reg)}" target="_blank" rel="noopener">Base registry</a>'
            f'<a href="{home}.well-known/security.txt">security.txt</a>'
            f'<a href="{home}{"#request" if home == "" else "request/"}">Contact</a></nav>'
            f'</div></footer>')


def load():
    idx = json.load(open(os.path.join(DOCS, "api", "v1", "index.json")))
    radar = json.load(open(os.path.join(DOCS, "api", "v1", "radar.json")))
    m = idx["summary_metrics"]
    n = len(idx["entries"])
    assert m["records_indexed"] == n == m["parameter_deltas"] + m["protective_deltas"] + m["aligned_baselines"]
    assert m["sprints_completed"] == max(e["sprint"] for e in idx["entries"])
    return idx, radar


# RPC-pinned records (docs/api/v1/rpc-pinned.json): block-pinned read-only observations that are NOT EAS-attested (no sprint
# number, no summary document, no Base EAS UID). They get /protocols/<slug>/ pages next to the index.json Sprint records but
# never touch index.json, its counts or its EAS anchoring.
PINNED_SRC = os.path.join(DOCS, "api", "v1", "rpc-pinned.json")
PINNED_SCHEMA = "pacta.rpc_pinned_records.v1"
CHAINS = {"ethereum": ("Ethereum", "Ethereum Mainnet (chain id 1)", "$ETH_RPC_URL"), "base": ("Base", "Base Mainnet (chain id 8453)", "$BASE_RPC_URL")}


def load_pinned(path=None):
    p = json.load(open(path or PINNED_SRC))
    assert p["schema"] == PINNED_SCHEMA and p["attestation"]["eas_attested"] is False and p["attestation"]["base_eas_uid"] is None
    for e in p["entries"]:
        assert e["provenance"] == "rpc_pinned" and e["base_eas_uid"] is None and "sprint" not in e and "summary_doc" not in e, e["id"]
        assert e["chain"] in CHAINS and e["rpc_env_var"] == CHAINS[e["chain"]][2], e["id"]
    return p


def is_pinned(e):
    return e.get("provenance") == "rpc_pinned"


def site_protocols(idx, pinned=None):
    """Every published /protocols/<slug>/ page, sorted by name: the index.json Sprint protocols (Base-EAS-anchored) plus the
    RPC-pinned protocols (routed by their own slug). {name: {"slug", "entries", "pinned"}}; names and slugs never collide."""
    pinned = load_pinned() if pinned is None else pinned
    out = {n: {"slug": protocol_slug(n), "entries": es, "pinned": False} for n, es in protocol_groups(idx).items()}
    for e in sorted(pinned["entries"], key=lambda e: e["id"]):
        assert e["protocol"] not in out or out[e["protocol"]]["pinned"], f'{e["protocol"]}: already an index.json protocol'
        out.setdefault(e["protocol"], {"slug": e["slug"], "entries": [], "pinned": True})["entries"].append(e)
    slugs = [v["slug"] for v in out.values()]
    assert len(slugs) == len(set(slugs)) and all(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", x) for x in slugs), "protocol slug collision / shape"
    return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))


def counts(idx):
    m = idx["summary_metrics"]
    a = idx["onchain_anchoring"]
    eas = sorted(int(k) for k in a["sprint_eas_attestations"])
    assert eas == list(range(1, len(eas) + 1)), "sprint attestations must be contiguous from Sprint 1"
    s = m["sprints_completed"]
    pend = [n for n in range(1, s + 1) if n not in eas]                       # indexed but not yet attested
    later = [n for n in eas if n > s]                                           # attested, records not yet in the index
    rng = lambda xs: "" if not xs else (str(xs[0]) if len(xs) == 1 else f"{xs[0]}–{xs[-1]}")
    return {"sprints": s, "records": m["records_indexed"], "eas_n": len(eas), "eas_from": eas[0], "eas_to": eas[-1],
            "pending": rng(pend), "later": rng(later), "multi_txs": a["attestation_coverage"]["eas_multi_attest_txs"],
            "delta": m["parameter_deltas"], "protect": m["protective_deltas"], "aligned": m["aligned_baselines"]}


def multi_tx_html(c):
    return " and ".join(f"{hexref(tx)} (Sprints {rng})" for rng, tx in c["multi_txs"].items())


def anchoring_text(c):
    """One sentence on Base anchoring, derived from the data (never hand-edited)."""
    t = f'{c["eas_n"]} Base EAS sprint attestations cover Sprints {c["eas_from"]}–{c["eas_to"]}'
    if c["pending"]:
        t += f'; Sprints {c["pending"]} are pinned by block hash and SHA-256 summary digest until batch-attested'
    if c["later"]:
        t += f'; Sprint{"s" if "–" in c["later"] else ""} {c["later"]} records join the public index after review'
    return t + "."


CLASS_LABEL = {"parameter_delta": ("delta", "Parameter delta"), "protective_delta": ("protect", "Protective delta"),
               "aligned_baseline": ("", "Aligned baseline")}


def badge(c):
    cls, lbl = CLASS_LABEL.get(c, ("", "Aligned baseline"))
    return f'<span class="{("badge " + cls).strip()}">{lbl}</span>'


def dot(c):
    return f'<span class="dot {CLASS_LABEL.get(c, ("", ""))[0]}"></span>'


def cast_line(e):
    """Runnable cast commands for a record (full signature + all arguments). Mirrors castCmd() in docs/app.js."""
    rpc = f'--rpc-url "{e.get("rpc_env_var", "$ETH_RPC_URL")}"'
    if e["check_type"] == "eth_getStorageAt":
        first = f'cast storage {e["target_contract"]} \\\n  {e["selector_or_slot"]} \\\n  --block {e["block_number"]} {rpc}'
    else:
        args = (" " + " ".join(e["call_args"])) if e.get("call_args") else ""
        first = f'cast call {e["target_contract"]} \\\n  "{e["call_signature"]}"{args} \\\n  --block {e["block_number"]} {rpc}'
    extra = "".join(f'\ncast call {x["to"]} "{x["signature"]}" --block {e["block_number"]} {rpc}' for x in e.get("extra_calls", []))
    return f'{first}{extra}\ncast block {e["block_number"]} --field hash {rpc}\n# expect {e["block_hash"]}'


def term(cmd, title="Reproduce on any archive node"):
    return (f'<div class="term"><div class="term-h"><span>{E(title)}</span>'
            f'<button class="copy" type="button" data-copy-term>Copy command</button></div>'
            f'<pre>{E(cmd)}</pre></div>')


def proof_html(e):
    if e["base_eas_uid"]:
        return (f'<a href="https://base.easscan.org/attestation/view/{E(e["base_eas_uid"])}" target="_blank" rel="noopener">'
                f'Base EAS attestation {E(short(e["base_eas_uid"]))} ↗</a>')
    return 'Pending Base EAS batch attestation · pinned by block hash and summary SHA-256'


def multisig(text):
    seen = []
    for x in re.findall(r"\b\d+-of-\d+\b", text):
        if x not in seen:
            seen.append(x)
    return " · ".join(seen) if seen else None


def proxy_admin(text):
    m = re.search(r"ProxyAdmin \((0x[0-9a-fA-F]{40})\)", text) or re.search(r"admin\(\) = [A-Za-z ]*\((0x[0-9a-fA-F]{40})\)", text)
    return m.group(1) if m else None


def delay_cmp(e):
    o, d = e["observed_delay_seconds"], e["documented_delay_seconds"]
    if o is None and d is None:
        return '<span class="muted">No timelock delay in this record</span>'
    warn = o is not None and d is not None and o != d
    return (f'<span class="cmp"><span class="chip obs{" warn" if warn else ""}"><i>Observed</i><b>{secs(o)}</b></span>'
            f'<span class="vs">vs</span><span class="chip"><i>Docs</i><b>{secs(d)}</b></span></span>')


def sheet(e):
    """Specification sheet for one record (server-rendered default; docs/app.js renders the same structure)."""
    ms, pa = multisig(e["onchain_observed"]), proxy_admin(e["onchain_observed"])
    rows = [("Category", E(e["category"])),
            ("Target contract", f'{E(e["target_label"])} · {hexref(e["target_contract"])}'),
            ("Timelock delay", delay_cmp(e))]
    if ms:
        rows.append(("Safe quorum", f'<span class="mono">{E(ms)}</span>'))
    if pa:
        rows.append(("EIP-1967 ProxyAdmin", hexref(pa)))
    rows += [("Pinned block", f'<span class="num">#{e["block_number"]:,}</span> · Sprint {e["sprint"]} '
                              f'<span class="badge final">Scanner-pinned (L1 finalized)</span>'),
             ("Canonical block hash", hexref(e["block_hash"], 8, 6)),
             ("Proof", proof_html(e)),
             ("Summary", f'<a href="{REPO}/blob/main/{E(e["summary_doc"])}" target="_blank" rel="noopener">{E(os.path.basename(e["summary_doc"]))} ↗</a>'
                         f' · SHA-256 {hexref(e["summary_sha256"], 8, 4)}')]
    kv = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    return (f'<div class="sheet-h"><h3>{E(e["protocol"])}</h3>{badge(e["classification"])}</div>'
            f'<p class="sheet-sub">{E(e["surface"])}</p>'
            f'<dl class="kv">{kv}</dl>'
            f'<p class="obs-text">{prose(e["onchain_observed"])}</p>'
            + term(cast_line(e)))


HEX64 = re.compile(r"0x[0-9a-fA-F]{64}(?![0-9a-fA-F])")


def prose(text):
    """Escape record prose for display; 32-byte hashes (tx / op / block ids) are shortened with the full value in a
    tooltip, so a 66-character token can never force a mid-hash wrap. The JSON feed keeps the full text."""
    out, last = [], 0
    for m in HEX64.finditer(text):
        out.append(E(text[last:m.start()]))
        out.append(f'<span class="hx" title="{m.group(0)}">{E(short(m.group(0), 8, 6))}</span>')
        last = m.end()
    out.append(E(text[last:]))
    return "".join(out)


def sorted_entries(idx):
    return sorted(idx["entries"], key=lambda e: (-e["sprint"], e["protocol"].lower()))


def inspector(idx, c):
    ents = sorted_entries(idx)
    default = next(e for e in ents if e["protocol"].startswith("Ethena"))
    items = "".join(
        f'<li><a href="#r-{E(e["id"])}" data-id="{E(e["id"])}" data-class="{E(e["classification"])}"'
        f'{" aria-current=" + chr(34) + "true" + chr(34) if e is default else ""}>'
        f'{dot(e["classification"])}<span class="p">{E(e["protocol"])}</span><span class="sp">S{e["sprint"]}</span>'
        f'<span class="s">{E(e["surface"])}</span></a></li>'
        for e in ents)
    return f"""<section class="sec" id="inspector"><div class="wrap">
<div class="sec-head"><span class="n">01</span><h2>Control-plane inspector</h2><span class="aside">No wallet. Every value pinned to a block and reproducible.</span></div>
<div class="bench">
<div class="bench-side">
<div class="bench-search"><input id="insp-q" type="search" placeholder="Search protocol, contract or 0x address" aria-label="Search {c["records"]} indexed records" autocomplete="off">
<div class="bench-filter" role="group" aria-label="Filter by classification"><button type="button" data-f="all" aria-pressed="true">All</button><button type="button" data-f="parameter_delta" aria-pressed="false">Deltas</button><button type="button" data-f="protective_delta" aria-pressed="false">Protective</button><button type="button" data-f="aligned_baseline" aria-pressed="false">Aligned</button></div></div>
<ul class="bench-list" id="insp-list">{items}</ul>
<div class="bench-count" id="insp-count">{c["records"]} of {c["records"]} records</div>
</div>
<div class="sheet" id="insp-panel" aria-live="polite">{sheet(default)}</div>
</div>
</div></section>"""


def load_onboarding():
    p = os.path.join(DOCS, "api", "v1", "onboarding.json")
    return json.load(open(p)) if os.path.exists(p) else {"briefs": []}


def onboarding_section(onb):
    if not onb["briefs"]:
        return ""
    return f"""<section class="sec" id="onboarding"><div class="wrap">
<div class="sec-head"><span class="n">03</span><h2>Live onboarding verification briefs</h2><span class="aside">{len(onb["briefs"])} assets currently proposed as collateral · block-pinned</span></div>
<p class="sec-intro">Who can change each asset now in front of Aave and Euler governance, read at a canonical block on two RPC endpoints, with every call reproducible. Machine-readable: <a href="api/v1/onboarding.json">/api/v1/onboarding.json</a>.</p>
<div class="tbl-wrap"><table class="tbl radar"><thead><tr><th>Asset</th><th>Forum thread</th><th class="hide-m">Pinned block</th><th class="r">Brief</th></tr></thead>
<tbody>{OR.homepage_rows(onb)}</tbody></table></div>
</div></section>"""


def onboarding_page(b, idx):
    pin = b["pin"]
    cmd = OR.terms(b)
    content = OR.content(b, term(cmd, "Reproduce every value on any archive node"), CLEARANCE_PRICE)
    meta = (f'<dl class="memo-meta"><dt>Asset</dt><dd>{E(b["asset"])}</dd><dt>Venue</dt><dd>{E(b["venue"])}</dd>'
            f'<dt>Pinned block</dt><dd>{E(OR.CHAIN_NAME[b["chain"]])} <span class="num">#{pin["number"]:,}</span> · {E(utc(pin["timestamp"], True))} '
            f'<span class="badge final">Canonical (EIP-1898)</span></dd><dt>Block hash</dt><dd>{hexref(pin["hash"], 10, 6)}</dd>'
            f'<dt>Data</dt><dd><a href="../../api/v1/onboarding.json">/api/v1/onboarding.json</a> · slug <code>{E(b["slug"])}</code></dd></dl>')
    content = content.replace("</header>", "</header>\n" + meta, 1)
    c = counts(idx)
    count_line = f'{c["sprints"]} Sprints · {c["records"]} Indexed Records'
    reg = idx["onchain_anchoring"]["commitment_registry"]
    title = f'{b["asset"]}: onboarding verification brief'
    body = f"""<body>
{topbar("../../")}
<main id="main" class="memo-wrap">
<div class="crumbs"><a href="../../">Pacta</a> / <a href="../../#onboarding">Onboarding briefs</a> / {E(b["slug"])}</div>
<article class="memo">
{content}</article>
<div class="memo-foot"><span>Read-only on-chain analysis. Not investment advice. Exploit-sensitive vulnerabilities are never published here; they go through Immunefi or Cantina bounty programmes.</span><a href="../../request/?tier=clearance">Clear these findings in 24h · {E(CLEARANCE_PRICE)} →</a></div>
</main>
{footer(count_line, reg, "../../")}
</body></html>
"""
    return head(title, OR.summary(b), f"{BASE_URL}/briefs/{b['slug']}/", prefix="../../", og_title=title, og_type="article") + "\n" + body


def radar_section(radar):
    r = radar["refreshed_at"]
    rows = []
    for it in radar["items"]:
        ops = ", ".join(f'<span class="hx" title="{o["op_id"]}">{short(o["op_id"], 6, 4)}</span>' for o in it["operations"])
        state = "Pending" if all(o["pending"] for o in it["operations"]) else ("Executed" if all(o["done"] for o in it["operations"]) else "Mixed")
        rows.append(
            f'<tr><td><b>{E(it["protocol"])}</b><span class="sub">{state} at refresh</span></td>'
            f'<td><span class="op">{E(it["title"])}</span><span class="sub">{E(it["summary"])}</span>'
            f'<span class="meta">Timelock {hexref(it["timelock"])} · Operation{"s" if len(it["operations"]) > 1 else ""} {ops}</span></td>'
            f'<td class="nowrap num hide-m">{secs(it["min_delay_seconds"])}</td>'
            f'<td class="nowrap"><span class="countdown" data-eta="{it["eta"]}">ETA {E(utc(it["eta"]))}</span><span class="sub">{E(utc(it["eta"]))}</span></td>'
            f'<td class="r nowrap"><a href="{E(it["brief"])}">Read brief →</a></td></tr>')
    fresh = f'Last refreshed: {r["block_time_utc"]} (Mainnet finalized block #{r["block_number"]:,})'
    return f"""<section class="sec" id="radar"><div class="wrap">
<div class="sec-head"><span class="n">02</span><h2>Queued timelock radar</h2><span class="aside">{sum(len(it["operations"]) for it in radar["items"])} operations · {len(radar["items"])} protocols</span></div>
<div class="tbl-wrap"><table class="tbl radar"><thead><tr><th>Protocol</th><th>Queued operation</th><th class="hide-m">Delay</th><th>Execution window</th><th class="r">Brief</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<div class="prov"><span class="badge final">Scanner-pinned (L1 finalized)</span><span>{E(fresh)}</span><span>State and ETAs read at that block on {r.get("rpcs_cross_checked", 2)} independent RPCs; countdowns run in your browser from each on-chain ETA.</span></div>
</div></section>"""


def findings_section(idx):
    by_id = {e["id"]: e for e in idx["entries"]}
    rows = []
    for rid, h, expl, obs, doc, link, label in FINDINGS:
        e = by_id[rid]
        href = link or f"#r-{rid}"
        rows.append(
            f'<div class="frow"><div class="who">{E(e["protocol"])}<span class="sub">Sprint {e["sprint"]} · {E(e["category"])}</span>{badge(e["classification"])}</div>'
            f'<div><h3>{E(h)}</h3><p>{expl}</p></div>'
            f'<div class="cmpcol"><span class="chip obs{" warn" if e["classification"] == "parameter_delta" else ""}"><i>{obs[0]}</i><b>{E(obs[1])}</b></span>'
            f'<span class="chip"><i>{doc[0]}</i><b>{E(doc[1])}</b></span><a href="{E(href)}"{" data-open=" + chr(34) + E(rid) + chr(34) if not link else ""}>{label} →</a></div></div>')
    return f"""<section class="sec" id="findings"><div class="wrap">
<div class="sec-head"><span class="n">04</span><h2>Selected governance deltas</h2><span class="aside">What is on-chain versus what the docs say</span></div>
<div class="frows">{"".join(rows)}</div>
</div></section>"""


def index_rows(idx):
    rows = []
    for e in sorted_entries(idx):
        search = " ".join(str(e.get(k, "")) for k in ("protocol", "category", "surface", "target_contract", "target_label", "onchain_observed", "classification", "sprint")).lower()
        rid = E(e["id"])
        proof = (f'<a href="https://base.easscan.org/attestation/view/{E(e["base_eas_uid"])}" target="_blank" rel="noopener">EAS ↗</a>'
                 if e["base_eas_uid"] else '<span class="muted">Hash-pinned</span>')
        rows.append(
            f'<tr data-class="{E(e["classification"])}" class="rec" data-id="{rid}" data-search="{E(search)}">'
            f'<td><b class="ell">{E(e["protocol"])}</b><span class="sub ell">{E(e["category"])}</span></td>'
            f'<td class="hide-s"><span class="ell">{E(e["target_label"])}</span><span class="sub">{hexref(e["target_contract"])}</span></td>'
            f'<td>{badge(e["classification"])}</td>'
            f'<td class="hide-m num nowrap">{secs(e["observed_delay_seconds"])} <span class="muted">/ {secs(e["documented_delay_seconds"])}</span></td>'
            f'<td class="hide-m nowrap"><span class="num">S{e["sprint"]} · #{e["block_number"]:,}</span><span class="sub">{proof}</span></td>'
            f'<td class="x"><a class="inspect-btn" href="#r-{rid}" aria-expanded="false" aria-controls="r-{rid}">Details</a></td></tr>')
        kv = (f'<dt>Pinned block</dt><dd><span class="num">#{e["block_number"]:,}</span> · {hexref(e["block_hash"], 8, 6)}</dd>'
              f'<dt>Delay</dt><dd>{delay_cmp(e)}</dd>'
              f'<dt>Summary</dt><dd><a href="{REPO}/blob/main/{E(e["summary_doc"])}" target="_blank" rel="noopener">Sprint {e["sprint"]} summary ↗</a></dd>'
              f'<dt>SHA-256</dt><dd>{hexref(e["summary_sha256"], 10, 6)}</dd>'
              f'<dt>Proof</dt><dd>{proof_html(e)}</dd>')
        rows.append(
            f'<tr class="drawer" id="r-{rid}"><td colspan="6"><div class="drawer-in">'
            f'<div><p class="drawer-title">{E(e["surface"])}</p><span class="label">On-chain observation</span><p class="obs-text">{prose(e["onchain_observed"])}</p>'
            f'<p class="obs-text"><span class="label">Documented</span><br>{prose(e["documented_reference"])}</p>'
            f'<p class="obs-text"><button class="linkish" type="button" data-inspect="{rid}">Open in inspector ↑</button></p></div>'
            f'<div><dl class="kv">{kv}</dl>{term(cast_line(e))}</div>'
            f'</div></td></tr>')
    return "\n".join(rows)


def index_section(idx, c, count_line):
    return f"""<section class="sec" id="index"><div class="wrap">
<div class="sec-head"><span class="n">05</span><h2>Public control-plane index</h2><span class="aside">{E(count_line)}</span></div>
<div class="ix-tools">
<input id="matrix-q" type="search" placeholder="Filter by protocol, contract, address or text" aria-label="Filter records" autocomplete="off">
<div class="seg" role="group" aria-label="Filter by classification">
<button type="button" data-class="all" aria-pressed="true">All<span class="num">{c["records"]}</span></button><button type="button" data-class="parameter_delta" aria-pressed="false">Parameter deltas<span class="num">{c["delta"]}</span></button><button type="button" data-class="protective_delta" aria-pressed="false">Protective<span class="num">{c["protect"]}</span></button><button type="button" data-class="aligned_baseline" aria-pressed="false">Aligned<span class="num">{c["aligned"]}</span></button>
</div>
<span class="ix-count" id="matrix-count">{c["records"]} of {c["records"]} records shown</span>
</div>
<div class="tbl-wrap"><table class="tbl" id="matrix">
<colgroup><col class="c-p"><col class="c-s"><col class="c-c"><col class="c-d"><col class="c-b"><col class="c-x"></colgroup>
<thead><tr><th>Protocol</th><th class="hide-s">Surface</th><th>Status</th><th class="hide-m">Delay obs / docs</th><th class="hide-m">Block / proof</th><th class="x"><span class="skip">Details</span></th></tr></thead>
<tbody>
{index_rows(idx)}
</tbody></table></div>
</div></section>"""


def verify_section(idx, c):
    reg, schema = idx["onchain_anchoring"]["commitment_registry"], idx["onchain_anchoring"]["eas_schema_uid"]
    cmd = (f"# 1) Pull the block-pinned index\n"
           f"curl -s {BASE_URL}/api/v1/index.json \\\n  | jq '.entries[] | {{protocol, sprint, block_number, classification}}'\n\n"
           f"# 2) Replay one record: Stader Manager Safe threshold\n"
           f'cast call 0xAAfb31780e4b9c95Bc920e388f4925A874cd07AF \\\n  "getThreshold()" \\\n  --block 26403676 --rpc-url "$ETH_RPC_URL"\n'
           f'cast block 26403676 --field hash --rpc-url "$ETH_RPC_URL"\n\n'
           f"# 3) Reference Foundry suite (offline; fork tests need ETH_RPC_URL)\n"
           f'forge test --no-match-test "testFork" -vv')
    return f"""<section class="sec" id="verify"><div class="wrap">
<div class="sec-head"><span class="n">06</span><h2>Don’t trust, verify</h2><span class="aside">Everything here replays against any archive node</span></div>
<div class="split">
<dl class="deflist">
<div><dt>Ethereum Mainnet</dt><dd>All {c["records"]} indexed records are pinned to a block number and its canonical block hash; reads use EIP-1898 <code>requireCanonical</code>.</dd></div>
<div><dt>Open verifier spec</dt><dd>Each record lists the target contract, the full call signature and arguments (or EIP-1967 slot), the block and the block hash. Replay it with <code>cast</code> or raw <code>eth_call</code> / <code>eth_getStorageAt</code>.</dd></div>
<div><dt>On-chain anchoring on Base</dt><dd>{anchoring_text(c)} Multi-attest txs {multi_tx_html(c)} · Registry {hexref(reg)} (Sourcify verified) · EAS schema {hexref(schema)}.</dd></div>
<div><dt>Machine-readable</dt><dd><a href="api/v1/index.json">/api/v1/index.json</a> (schema <code>{E(idx["schema"])}</code>) · <a href="api/v1/radar.json">/api/v1/radar.json</a> · <a href="api/v1/onboarding.json">/api/v1/onboarding.json</a> · <a href="api/v1/proposals.json">/api/v1/proposals.json</a> · <a href="llms.txt">/llms.txt</a> · <a href="llms-full.txt">/llms-full.txt</a></dd></div>
<div><dt>For agents</dt><dd><a href=".well-known/agent.json">A2A Agent Card</a> · <a href=".well-known/mcp.json">MCP manifest</a> · <a href="SKILL.md">SKILL.md</a>. Read-only and free; optional x402 (Base USDC) live scans.</dd></div>
<div><dt>Reorg handling</dt><dd>Live monitoring uses a 64-block reorg-aware indexer: observations from orphaned blocks are retracted, never silently kept.</dd></div>
</dl>
{term(cmd, "Verify from your terminal")}
</div>
</div></section>"""


def pricing_section(home=""):
    req = "#request" if home == "" else f"{home}request/"

    def plan(key, tier, bullets, cta, feat=False, addon="", title=None, price=None):
        t_, p_, unit, _, _ = TRACKS[key]
        title, price = title or t_, price or p_
        lis = "".join(f"<li>{b}</li>" for b in bullets)
        return (f'<div class="plan{" feat" if feat else ""}"><span class="tier">{tier}</span><h3>{E(title)}</h3>'
                f'<div class="price">{price}{f"<small>{unit}</small>" if unit else ""}</div>{addon}<ul>{lis}</ul>'
                f'<a class="btn{" primary" if feat else ""}" href="{req}{"" if home == "" else "?tier=" + key}" data-tier="{key}">{cta} <span class="arr">→</span></a></div>')
    free_lis = "".join(f"<li>{b}</li>" for b in [
        "All 5 endpoints: <code>/v1/check/preflight</code>, control-plane, timelock-op, proposal-diff, live timelocks",
        f"Remote MCP (5 read-only tools) at <code>{E(MCP_URL)}</code> and OpenAPI 3.1",
        f"{E(RATE_LIMIT)}; 5-minute edge cache on unpinned checks",
        "Every indexed record, the timelock radar and briefs, free and real-time; no key, no delay, no paywall",
        "x402 v1 + v2 (USDC on Base) is wired in for metered use later; nothing to set up today"])
    free_plan = (f'<div class="plan feat"><span class="tier">AI agents, agent builders &amp; risk teams</span><h3>Free launch</h3>'
                 f'<div class="price">$0<small>no API key · no wallet</small></div><ul>{free_lis}</ul>'
                 f'<a class="btn primary" href="{"" if home == "" else home}#preflight">Run a check in one call <span class="arr">→</span></a>'
                 f'<a class="plan-sub" href="{req}{"" if home == "" else "?tier=community"}" data-tier="community">Suggest a protocol for the free community queue →</a></div>')
    plans = (free_plan
             + plan("clearance", "High volume, SLA &amp; on-chain clearance",
                    ["Canonical block-pinned control-plane audit of your proxy admins, Safes, roles and timelocks",
                     "GitBook / config reconciliation PR wherever docs and on-chain state differ",
                     "Base Mainnet EAS <i>Aligned</i> attestation in PactaCommitmentRegistry, clearing open <code>parameter_delta</code> flags",
                     "Paste-ready Curator Diligence Dossier (PDF + JSON) for Morpho, Euler, Aave and Sky forum proposals",
                     "Dedicated rate limits and an SLA for high-volume agent traffic: scoped in the request builder",
                     "USDC on Base or Ethereum; payment details are in the request builder"],
                    "Request SLA or a 24h clearance", feat=False,
                    addon=f'<p class="addon">Optional: continuous <i>Aligned</i> badge maintenance, {E(MONITORING_PRICE)}</p>'))
    return f"""<section class="sec" id="pricing"><div class="wrap">
<div class="sec-head"><span class="n">07</span><h2>Pricing</h2><span class="aside">The API, MCP server and all public data are free during the launch. Paid work is optional: high-volume SLAs and on-chain clearance.</span></div>
<div class="plans two">{plans}</div>
<p class="note">{E(VULN_ROUTE)}</p>
</div></section>"""


def protocol_options(idx, pinned=None):
    names = []
    for e in sorted_entries(idx):
        n = e["protocol"]
        if n not in names:
            names.append(n)
    pinned = load_pinned() if pinned is None else pinned
    names += [e["protocol"] for e in pinned["entries"] if e["protocol"] not in names]
    return sorted(set(names), key=str.lower)


def pay_panel(idx):
    treasury = idx["onchain_anchoring"]["treasury_admin"]
    rows = "".join(f'<dt>USDC on {k}</dt><dd>{hexref(v)}</dd>' for k, v in USDC.items())
    return (f'<div class="pay" id="req-pay"><span class="label">Payment · 24h clearance</span>'
            f'<p>{E(CLEARANCE_PRICE)} flat, sent to the Pacta treasury (EOA) on Base or Ethereum. USDC only; the same address on both chains.</p>'
            f'<dl class="kv"><dt>Pacta treasury (EOA)</dt><dd><span class="mono full">{treasury}</span>{copy_btn(treasury)}</dd>{rows}</dl>'
            f'<p class="hint">Paid already? Add the transaction hash on the left. Otherwise send the brief first: the 24-hour window '
            f'starts once scope and payment are both confirmed.</p></div>')


def request_builder(idx, home=""):
    tiers = "".join(
        f'<label><input type="radio" name="tier" value="{k}"{" checked" if k == DEFAULT_TRACK else ""}><span><b>{E(t)}</b>'
        f'{" · " + E(p) + (" " + E(u) if u else "")}<span class="sub">{E(sm)}</span></span></label>'
        for k, (t, p, u, sm, _) in TRACKS.items())
    protos = "".join(f'<label><input type="checkbox" name="protocol" value="{E(n)}"><span>{E(n)}</span></label>'
                     for n in protocol_options(idx))
    gh = f"{REPO}/issues/new?template=request-scan.yml&title=" + urllib.parse.quote("[Pacta Scope] ")
    gm = "https://mail.google.com/mail/?view=cm&fs=1&to=" + urllib.parse.quote(CONTACT) + "&su=" + urllib.parse.quote("Pacta 24h clearance request")
    return f"""<form class="req" id="req-form" autocomplete="off" onsubmit="return false" data-treasury="{idx["onchain_anchoring"]["treasury_admin"]}">
<div class="req-form">
<fieldset><legend>Track</legend><div class="opts one">{tiers}</div></fieldset>
<fieldset><legend>Protocols in scope <span class="legend-note">· {len(protocol_options(idx))} indexed; add others below</span></legend><div class="opts scroll" id="req-protocols">{protos}</div></fieldset>
<div class="field"><label for="req-org">Organization or protocol</label><input id="req-org" name="org" type="text" placeholder="e.g. Example Labs, or the asset you issue"></div>
<div class="field"><label for="req-scope">Contracts, docs or portfolio</label><textarea id="req-scope" name="scope" placeholder="Public docs URL, mainnet addresses, or the collateral list you curate"></textarea><p class="hint">Public information only. Never paste keys or exploit details here.</p></div>
<div class="field" id="req-forum-field"><label for="req-forum">Forum proposal URL <span class="legend-note">· optional</span></label><input id="req-forum" name="forum" type="url" placeholder="https://… Morpho, Euler, Aave or Sky forum listing proposal"></div>
<div class="field" id="req-tx-field"><label for="req-tx">Payment transaction hash <span class="legend-note">· optional</span></label><input id="req-tx" name="tx" type="text" spellcheck="false" placeholder="0x… (Base or Ethereum)"><p class="hint" id="req-tx-hint">A 66-character hash starting with 0x.</p></div>
<div class="field"><label for="req-contact">How should we reach you?</label><input id="req-contact" name="contact" type="text" placeholder="Work email, Telegram or GitHub handle"></div>
</div>
<div class="req-out">
<span class="label">Scope brief</span>
<div class="term"><div class="term-h"><span>To: {CONTACT}</span><button class="copy" type="button" data-copy-from="req-brief">Copy brief</button></div><pre id="req-brief">Choose a track and protocols; the brief updates as you type.</pre></div>
{pay_panel(idx)}
<div class="actions">
<a class="btn primary" id="req-gh" href="{E(gh)}" target="_blank" rel="noopener">Open a pre-filled GitHub intake issue <span class="arr">↗</span></a>
<a class="btn" id="req-gmail" href="{E(gm)}" target="_blank" rel="noopener">Compose in Gmail <span class="arr">↗</span></a>
<button class="btn" type="button" id="req-copy" data-copy-from="req-brief">Copy brief and address <span class="arr">⧉</span></button>
</div>
<p class="note">{E(VULN_ROUTE)}</p>
<p class="status" id="req-status" role="status" aria-live="polite"></p>
<div class="addrline">Or write to <b>{CONTACT}</b>{copy_btn(CONTACT, "Copy address")}</div>
</div>
</form>"""


def request_section(idx):
    return f"""<section class="sec" id="request"><div class="wrap">
<div class="sec-head"><span class="n">08</span><h2>Request coverage</h2><span class="aside">Builds a scope brief in your browser; nothing is sent until you choose a channel</span></div>
{request_builder(idx)}
</div></section>"""


def faq_section(c, r):
    qa = [
        ("What exactly is anchored on-chain?",
         f'{anchoring_text(c)} They are recorded by <code>pacta.base.eth</code> in PactaCommitmentRegistry (multi-attest txs {multi_tx_html(c)}); '
         f'each attestation commits to the sprint’s Ethereum block hash and summary SHA-256.'),
        ("Is the data free?",
         "Yes, and in real time. Every indexed record, the timelock radar, the briefs, /api/v1/index.json and llms.txt are free for vault "
         "curators, allocators and AI risk agents: no key, no delay and no paywall. Curators never pay."),
        ("What does the $5,000 clearance include?",
         "For collateral issuers onboarding an asset or clearing a <code>parameter_delta</code> flag: a canonical block-pinned control-plane audit, "
         "a GitBook / config reconciliation PR, a Base Mainnet EAS <i>Aligned</i> attestation and a Curator Diligence Dossier (PDF + JSON) "
         "ready to paste into Morpho, Euler, Aave or Sky forum proposals, in 24 hours, for $5,000 USDC flat. Continuous <i>Aligned</i> "
         "badge maintenance is optional at $1,500 / month."),
        ("How do I reproduce a record?",
         "Every record gives the contract, the call signature with all arguments (or the storage slot), the block and the canonical block hash. "
         "Copy its <code>cast</code> command from the inspector or the index and run it against any archive node."),
        ("What happens to exploit-sensitive findings?",
         E(VULN_ROUTE)),
        ("Do I need a wallet?",
         "No. The inspector, the radar, the briefs and the JSON feed are public and read-only. A wallet is only needed to pay for a clearance."),
        ("How fresh is the radar?",
         f'The radar states the exact finalized block it was refreshed at (#{r["block_number"]:,}, {E(r["block_time_utc"])}); countdowns are computed '
         f'from each operation’s on-chain ETA. An ETA is when execution becomes possible, not a guarantee that it happens.'),
        ("What do the classifications mean?",
         "Parameter delta: on-chain state differs from the documentation. Protective delta: a change that strengthens controls. "
         "Aligned baseline: on-chain state matches the documentation at the pinned block."),
    ]
    items = "".join(f"<div><dt>{q}</dt><dd>{a}</dd></div>" for q, a in qa)
    return f"""<section class="sec" id="faq"><div class="wrap">
<div class="sec-head"><span class="n">09</span><h2>Questions &amp; methodology</h2></div>
<dl class="faq">{items}</dl>
</div></section>"""


def about_section(idx):
    return f"""<section class="sec" id="about"><div class="wrap">
<div class="sec-head"><span class="n">10</span><h2>About</h2></div>
<div class="about">
<p>Pacta is built by <a href="{FN}" target="_blank" rel="noopener">Fractal Neurons</a>, a research engineering firm. <i>Pacta sunt servanda</i>: agreements must be kept. We check that the people who control DeFi collateral keep the commitments their documentation makes, and we tell you before that changes.</p>
<dl class="deflist">
<div><dt>Contact</dt><dd><a href="#request">Request builder</a> · <span class="mono">{CONTACT}</span>{copy_btn(CONTACT, "Copy")}</dd></div>
<div><dt>Code &amp; data</dt><dd><a href="{REPO}" target="_blank" rel="noopener">{REPO.replace("https://", "")} ↗</a></dd></div>
<div><dt>For agents</dt><dd><a href="llms.txt">/llms.txt</a> · <a href="llms-full.txt">/llms-full.txt</a> · <a href="api/v1/proposals.json">/api/v1/proposals.json</a> · <a href=".well-known/agent.json">agent.json</a> · <a href="SKILL.md">SKILL.md</a></dd></div>
<div><dt>Security</dt><dd><a href=".well-known/security.txt">/.well-known/security.txt</a></dd></div>
</dl>
</div>
</div></section>"""


def quickstart_block():
    """Above-the-fold, copyable agent quickstarts. Remote MCP and curl come first: the npm package is not published yet."""
    claude = f"claude mcp add --transport http pacta {MCP_URL}"
    cursor = '{"mcpServers": {"pacta": {"url": "' + MCP_URL + '"}}}'
    curl = f'curl -s "{API}/v1/check/preflight?chain=ethereum&address=0xA35b1B31Ce002FBF2058D22F30f95D405200A15b"'
    snippet = lambda label, value: (f'<div class="qs-snip"><span class="qs-l">{label}</span><code class="mono">{E(value)}</code>{copy_btn(value)}</div>')
    return (f'<div class="qs" aria-label="Agent quickstarts">'
            f'<div class="qs-item"><span class="tier">1 · Remote MCP, zero install</span><h3>Claude Code, Cursor, any MCP client</h3>'
            f'{snippet("Claude Code", claude)}{snippet("Cursor mcp.json", cursor)}{snippet("Any MCP client (Streamable HTTP)", MCP_URL)}</div>'
            f'<div class="qs-item"><span class="tier">2 · One curl</span><h3>Pre-flight check</h3>{snippet("Shell", curl)}'
            f'<p class="note">Returns a verdict, a 0–100 risk score, proxy / admin / timelock breakdown and the pinned block.</p></div>'
            f'<div class="qs-item"><span class="tier">3 · OpenAPI, Actions &amp; skills</span><h3>ChatGPT Actions, LangChain, skills</h3>'
            f'<p class="qs-links"><a href="{OPENAPI_URL}">openapi.json (3.1)</a><a href="SKILL.md">SKILL.md</a><a href="llms.txt">llms.txt</a>'
            f'<a href=".well-known/agent.json">agent.json</a><a href=".well-known/mcp.json">mcp.json</a></p>'
            f'<p class="note">$0 during the launch: no API key, no wallet, {E(RATE_LIMIT)}.</p></div>'
            f'</div>')


def preflight_section():
    """Live checker: app.js calls the free API on an explicit click and renders text only (textContent)."""
    presets = "".join(f'<button class="btn sm" type="button" data-pf-chain="{c}" data-pf-address="{a}">{E(l)}</button>' for l, c, a in PREFLIGHT_PRESETS)
    return f"""<section class="sec" id="preflight"><div class="wrap">
<div class="sec-head"><span class="n">00</span><h2>Live pre-flight check</h2><span class="aside">Calls the free API at {E(API)} when you press the button. Nothing is sent before that.</span></div>
<div class="pf" data-api="{API}">
<form class="pf-form" id="pf-form" autocomplete="off"><label>Chain<select name="chain"><option value="ethereum">Ethereum</option><option value="base">Base</option></select></label>
<label class="pf-addr">Contract address<input type="text" name="address" placeholder="0x…" maxlength="42" spellcheck="false" required></label>
<button class="btn primary" type="submit">Run pre-flight</button></form>
<div class="pf-presets"><span>Try:</span>{presets}</div>
<div class="pf-out" id="pf-out" aria-live="polite"><p class="note">The verdict, risk score, proxy, admin and timelock breakdown and the <code>cast</code> commands to verify it appear here.</p></div>
<noscript><p class="note">Without JavaScript, use the curl command above.</p></noscript>
</div>
</div></section>"""


def protocol_slug(name):
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def protocol_groups(idx):
    groups = {}
    for e in idx["entries"]:
        groups.setdefault(e["protocol"], []).append(e)
    return {k: sorted(v, key=lambda e: (e["sprint"], e["id"])) for k, v in sorted(groups.items(), key=lambda kv: kv[0].lower())}


def radar_for(name, radar):
    key = name.lower()
    return [it for it in radar["items"] if it["protocol"].lower() in key or key.startswith(it["protocol"].lower())]


# ---- governance forum digest (read-only; CONTRACTS §3) ---------------------------------------------------------------
# Optional source data/forum-digest.json (written by the read-only Discourse poller). Missing = empty digest. The build
# republishes it at /api/v1/forum-digest.json with an addressIndex that lets the gateway attach discussions to a
# preflight response. Deterministic: no wall clock; ordering and filtering depend only on the inputs.
FORUM_DIGEST_SRC = os.path.join(ROOT, "data", "forum-digest.json")
FORUM_SCHEMA = "pacta.forum_digest.v1"
FORUM_FAMILIES = ("aave", "euler", "morpho", "sky", "compound", "lido", "arbitrum", "uniswap", "curve", "frax")
# The family is the first word of the protocol name, lowercased. Two indexed names start with a word that is not the
# forum family that governs them: MetaMorpho vaults (Morpho forum) and Spark (a Sky star; forum.sky.money).
FAMILY_ALIAS = {"metamorpho": "morpho", "spark": "sky"}
GOV_MAX = 5
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})")
_HOST = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+")


def protocol_family(name):
    words = re.findall(r"[a-z0-9]+", name.lower())
    w0 = words[0] if words else ""
    return FAMILY_ALIAS.get(w0, w0)


def empty_forum_digest():
    return {"schema": FORUM_SCHEMA, "generatedAt": None, "readOnly": True, "forums": {}, "discussions": []}


def _iso_or_none(v):
    return v if isinstance(v, str) and _ISO.fullmatch(v) else None


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def _discussion(d):
    """One validated discussion (known keys only) or None. The url must be https on the discussion's own forum host."""
    if not isinstance(d, dict):
        return None
    forum, proto, tid, title, url = d.get("forum"), d.get("protocol"), _int(d.get("topicId")), d.get("title"), d.get("url")
    if not (isinstance(forum, str) and _HOST.fullmatch(forum) and isinstance(proto, str) and re.fullmatch(r"[a-z0-9-]{1,40}", proto)
            and tid is not None and isinstance(title, str) and title.strip() and isinstance(url, str)):
        return None
    pu = urllib.parse.urlsplit(url)
    if pu.scheme != "https" or pu.hostname != forum or pu.username or pu.password or pu.port:
        return None
    strs = lambda v: sorted({x.strip() for x in v if isinstance(x, str) and x.strip()})[:12] if isinstance(v, list) else []
    return {"forum": forum, "protocol": proto, "topicId": tid, "title": " ".join(title.split())[:300], "url": url,
            "createdAt": _iso_or_none(d.get("createdAt")), "lastPostedAt": _iso_or_none(d.get("lastPostedAt")),
            "postsCount": _int(d.get("postsCount")) or 0, "tags": strs(d.get("tags")), "riskTerms": strs(d.get("riskTerms"))}


def normalize_forum_digest(src):
    """Validate a pacta.forum_digest.v1 document; drop malformed discussions; deterministic order (forum, topicId)."""
    if not isinstance(src, dict) or src.get("schema") != FORUM_SCHEMA:
        raise ValueError(f"forum digest: schema must be {FORUM_SCHEMA}")
    forums = {}
    for host, f in sorted((src.get("forums") or {}).items()):
        if isinstance(host, str) and _HOST.fullmatch(host) and isinstance(f, dict) and isinstance(f.get("protocol"), str):
            forums[host] = {"protocol": f["protocol"], "lastPolledAt": _iso_or_none(f.get("lastPolledAt"))}
    seen, ds = set(), []
    for d in src.get("discussions") or []:
        n = _discussion(d)
        if n and (n["forum"], n["topicId"]) not in seen:
            seen.add((n["forum"], n["topicId"]))
            ds.append(n)
    ds.sort(key=lambda d: (d["forum"], d["topicId"]))
    return {"schema": FORUM_SCHEMA, "generatedAt": _iso_or_none(src.get("generatedAt")), "readOnly": True, "forums": forums, "discussions": ds}


def load_forum_digest(path=None):
    path = path or FORUM_DIGEST_SRC
    if not os.path.exists(path):
        return empty_forum_digest()
    with open(path) as fh:
        return normalize_forum_digest(json.load(fh))


def address_index(idx, pinned=None):
    """{"<chain>:0x<lower 40 hex>": family} from every target_contract in index.json (chain ethereum unless the entry says Base)
    and every RPC-pinned record's target and paired protocol contract (their own chain)."""
    pinned = load_pinned() if pinned is None else pinned
    out = {}
    for e in sorted(idx["entries"], key=lambda e: e["id"]) + sorted(pinned["entries"], key=lambda e: e["id"]):
        for a in (e.get("target_contract"), e.get("paired_contract")):
            a = str(a or "").lower()
            if not re.fullmatch(r"0x[0-9a-f]{40}", a):
                continue
            chain = "base" if str(e.get("chain", "")).lower() == "base" or e.get("chain_id") == 8453 else "ethereum"
            out.setdefault(f"{chain}:{a}", protocol_family(e["protocol"]))
    return dict(sorted(out.items()))


def forum_digest_doc(idx, digest, pinned=None):
    d = normalize_forum_digest(digest)
    d["addressIndex"] = address_index(idx, pinned)
    return d


def forum_digest_json(idx, digest, pinned=None):
    return json.dumps(forum_digest_doc(idx, digest, pinned), indent=2, ensure_ascii=False) + "\n"


def governance_discussions(name, digest):
    """At most GOV_MAX discussions of the protocol's family, newest lastPostedAt first (ties: higher topicId first)."""
    fam = protocol_family(name)
    ds = [d for d in normalize_forum_digest(digest)["discussions"] if d["protocol"] == fam]
    return sorted(ds, key=lambda d: (d["lastPostedAt"] or "", d["topicId"], d["forum"]), reverse=True)[:GOV_MAX]


def governance_section(name, digest, home="../../"):
    ds = governance_discussions(name, digest)
    if not ds:
        return ""
    rows = ""
    for d in ds:
        meta = f'{d["forum"]} · {d["postsCount"]} post{"" if d["postsCount"] == 1 else "s"}' + (f' · {", ".join(d["riskTerms"])}' if d["riskTerms"] else "")
        rows += (f'<tr><td><a href="{E(d["url"])}" target="_blank" rel="noopener nofollow">{E(d["title"])} ↗</a>'
                 f'<br><span class="muted">{E(meta)}</span></td><td class="num">{E((d["lastPostedAt"] or "—")[:10])}</td></tr>')
    hosts = ", ".join(sorted({d["forum"] for d in ds}))
    return (f'<section class="memo-sec" id="governance"><h2>Active governance discussions</h2>'
            f'<p>Most recently active public topics on {E(hosts)}, from a read-only digest '
            f'(<a href="{home}api/v1/forum-digest.json">/api/v1/forum-digest.json</a>). Pacta reads these forums and never posts to them.</p>'
            f'<div class="tbl-wrap"><table><thead><tr><th>Topic</th><th>Last post</th></tr></thead><tbody>{rows}</tbody></table></div></section>\n')


CONTROLLER_KIND = {"multisig_safe": "Safe", "timelock": "Timelock", "contract_controller": "Contract"}


def controller_dd(e):
    """Who controls an RPC-pinned record's target, as observed (kind, address, Safe quorum, owner of a controller contract)."""
    a, k, q, up = e.get("controller_address"), e.get("controller_kind"), e.get("safe_quorum"), e.get("upstream_controller")
    if not a:
        return "No single-key owner or admin getter (immutable or role-scoped modules)"
    lbl = f"{q} Safe" if k == "multisig_safe" and q else CONTROLLER_KIND.get(k, "Contract")
    out = f"{E(lbl)} {hexref(a)}"
    if up:
        uk = e.get("upstream_kind")
        ulbl = f"{q} Safe" if uk == "multisig_safe" and q else CONTROLLER_KIND.get(uk, "contract")
        out += f" · owned by {E(ulbl)} {hexref(up)}"
    return out


def protocol_page(name, entries, idx, radar, digest=None, slug=None):
    """Static, deterministic protocol safety record (no wall-clock time): every indexed surface with its pinned block.
    index.json Sprint records (Base-EAS-anchored) and RPC-pinned records (not EAS-attested) are labelled as such."""
    digest = load_forum_digest() if digest is None else digest
    slug = slug or protocol_slug(name)
    url = f"{BASE_URL}/protocols/{slug}/"
    c = counts(idx)
    count_line = f'{c["sprints"]} Sprints · {c["records"]} Indexed Records'
    reg = idx["onchain_anchoring"]["commitment_registry"]
    cat = entries[0]["category"]
    targets = sorted({e["target_contract"] for e in entries})
    first = entries[0]
    pinned = all(is_pinned(e) for e in entries)
    assert pinned or not any(is_pinned(e) for e in entries), f"{name}: mixed provenance"
    chains = sorted({e.get("chain", "ethereum") for e in entries}, key=list(CHAINS).index)
    chain_txt = " and ".join(CHAINS[ch][0] for ch in chains)
    n = len(entries)
    records = ""
    for e in entries:
        ch = CHAINS[e.get("chain", "ethereum")][0]
        prov = "RPC-pinned, not EAS-attested" if pinned else f'sprint {E(str(e["sprint"]))}'
        ctrl = f'<dt>Controller</dt><dd>{controller_dd(e)}</dd>' if pinned else ""
        doc_lbl = "Documentation." if pinned else "Documented."
        records += (f'<article class="memo-sec" id="{E(e["id"])}"><h2>{E(e["surface"])}</h2>'
                    f'<dl class="memo-meta"><dt>Status</dt><dd>{badge(e["classification"])}</dd>'
                    f'<dt>Target</dt><dd>{E(e["target_label"])} {hexref(e["target_contract"])}</dd>'
                    f'<dt>Pinned block</dt><dd>{ch} <span class="num">#{int(e["block_number"]):,}</span> · {prov}</dd>'
                    f'<dt>Block hash</dt><dd>{hexref(e["block_hash"], 10, 6)}</dd>{ctrl}</dl>'
                    f'<p><b>Observed on-chain.</b> {E(e["onchain_observed"])}</p>'
                    f'<p><b>{doc_lbl}</b> {E(e["documented_reference"])}</p>'
                    f'{term(cast_line(e))}</article>\n')
    ops = ""
    for it in radar_for(name, radar):
        lis = "".join(f'<li><code class="mono">{E(o["op_id"])}</code> · ETA {E(utc(o["eta"], True))} · {"pending" if o["pending"] else ("done" if o["done"] else "cancelled or unknown")}</li>'
                      for o in it["operations"])
        ops += (f'<article class="memo-sec"><h2>Queued timelock operations</h2><p>{E(it["title"])}. {E(it["summary"])}</p>'
                f'<p>Timelock {hexref(it["timelock"])} · {secs(it["min_delay_seconds"])} minimum delay · <a href="../../{E(it["brief"])}">Pre-execution brief →</a></p>'
                f'<ul>{lis}</ul></article>\n')
    provenance = ""
    if pinned:
        provenance = (f'<section class="memo-sec" id="provenance"><h2>Provenance</h2><p>RPC-pinned {"record" if n == 1 else "records"}: read over public '
                      f'JSON-RPC at the {chain_txt} block shown below and independently re-read at the same block by a second Pacta seat. '
                      f'{"It is" if n == 1 else "They are"} <b>not EAS-attested</b>: no sprint number, no summary document and no Base EAS UID. '
                      f'Machine-readable: <a href="../../api/v1/rpc-pinned.json">/api/v1/rpc-pinned.json</a>. The Base-EAS-attested Sprint records '
                      f'are in <a href="../../api/v1/index.json">/api/v1/index.json</a>.</p></section>\n')
    curl = f'curl -s "{API}/v1/check/preflight?chain={first.get("chain", "ethereum")}&address={first["target_contract"]}"'
    surfaces = f'{n} indexed {"surface" if n == 1 else "surfaces"}'
    data_url = f"{BASE_URL}/api/v1/rpc-pinned.json" if pinned else f"{BASE_URL}/api/v1/index.json"
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{name} control-plane safety record",
          "description": f"Block-pinned control-plane observations for {name} ({cat}): proxy admins, Safe quorums, roles and timelock delays, "
                         + (f"read over public JSON-RPC (RPC-pinned; not EAS-attested). {surfaces}." if pinned
                            else f"compared with the protocol's documentation. {surfaces}."),
          "url": url, "isAccessibleForFree": True, "keywords": [name, cat, "DeFi", "control plane", "timelock", "proxy admin", "Safe multisig"],
          "creator": {"@type": "Organization", "name": "Pacta by Fractal Neurons", "url": f"{BASE_URL}/"},
          "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": data_url}],
          "variableMeasured": [e["surface"] for e in entries],
          "spatialCoverage": "; ".join(CHAINS[ch][1] for ch in chains),
          "temporalCoverage": f"block {min(int(e['block_number']) for e in entries)}/{max(int(e['block_number']) for e in entries)}"}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Pacta", "item": f"{BASE_URL}/"},
        {"@type": "ListItem", "position": 2, "name": "Protocols", "item": f"{BASE_URL}/protocols/"},
        {"@type": "ListItem", "position": 3, "name": name, "item": url}]}
    ld_json = json.dumps(ld, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    crumbs_json = json.dumps(crumbs, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    title = f"{name}: control-plane safety record"
    desc = (f"Who can upgrade, pause or change {name}: {n} block-pinned control-plane {'check' if n == 1 else 'checks'} with "
            f"{'a cast reproduction' if n == 1 else 'cast reproductions'} and a free live pre-flight API.")
    pin_clause = (f"pinned to a canonical {chain_txt} block over public JSON-RPC (not EAS-attested), with the protocol's documentation linked" if pinned
                  else f"{'' if n == 1 else 'each '}pinned to a canonical {chain_txt} block and compared with what the protocol documents")
    codes = ", ".join(f'<code class="mono">{E(t)}</code>' for t in targets)
    lede = (f'{n} indexed control-plane {"surface" if n == 1 else "surfaces"} for {E(name)}, {pin_clause}. '
            f'{"Contract" if len(targets) == 1 else "Contracts"}: {codes}.')
    body = f"""<body>
{topbar("../../")}
<main id="main" class="memo-wrap">
<div class="crumbs"><a href="../../">Pacta</a> / <a href="../">Protocols</a> / {E(name)}</div>
<article class="memo">
<header><span class="tier">{E(cat)}</span><h1>{E(title)}</h1>
<p class="lede">{lede}</p></header>
<section class="memo-sec"><h2>Check it live (free)</h2><p>The pre-flight API re-reads the controller, proxy and capabilities of a contract at the latest block. No key, no wallet.</p>
{term(curl, "Live pre-flight check")}<p>MCP: <code class="mono">{E(MCP_URL)}</code> · tool <code>pacta_check_preflight</code>.</p></section>
{provenance}{governance_section(name, digest)}{records}{ops}</article>
<div class="memo-foot"><span>Read-only on-chain analysis. Not investment advice. Exploit-sensitive vulnerabilities are never published here; they go through Immunefi or Cantina bounty programmes.</span><a href="../../request/?tier=clearance">Clear findings in 24h · {E(CLEARANCE_PRICE)} →</a></div>
</main>
{footer(count_line, reg, "../../")}
<script type="application/ld+json">{ld_json}</script>
<script type="application/ld+json">{crumbs_json}</script>
</body></html>
"""
    return head(f"{name} control-plane safety · Pacta", desc, url, prefix="../../", og_title=title, og_type="article") + "\n" + body


def protocols_index_page(idx, sp=None):
    """/protocols/: every published protocol page (index.json Sprint protocols + RPC-pinned protocols), with provenance."""
    sp = site_protocols(idx) if sp is None else sp
    c = counts(idx)
    count_line = f'{c["sprints"]} Sprints · {c["records"]} Indexed Records'
    reg = idx["onchain_anchoring"]["commitment_registry"]
    n_surf = sum(len(v["entries"]) for v in sp.values())
    n_pin = sum(len(v["entries"]) for v in sp.values() if v["pinned"])

    def prov(v):
        if v["pinned"]:
            return '<span class="muted">RPC-pinned</span>'
        ss = sorted({e["sprint"] for e in v["entries"]})
        return f'Sprint{"s" if len(ss) > 1 else ""} {", ".join(str(x) for x in ss)} · Base EAS'

    rows = "".join(f'<tr><td><a href="{v["slug"]}/">{E(n)}</a></td><td>{E(v["entries"][0]["category"])}</td>'
                   f'<td>{" · ".join(sorted({CHAINS[e.get("chain", "ethereum")][0] for e in v["entries"]}))}</td><td class="num">{len(v["entries"])}</td>'
                   f'<td>{" ".join(badge(cl) for cl in sorted({e["classification"] for e in v["entries"]}))}</td><td>{prov(v)}</td></tr>' for n, v in sp.items())
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "Pacta protocol control-plane safety records", "numberOfItems": len(sp),
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{BASE_URL}/protocols/{v['slug']}/", "name": n}
                              for i, (n, v) in enumerate(sp.items())]}
    ld_json = json.dumps(ld, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    body = f"""<body>
{topbar("../")}
<main id="main">
<section class="sec"><div class="wrap">
<div class="crumbs"><a href="../">Pacta</a> / Protocols</div>
<div class="sec-head"><span class="n">→</span><h2>Protocol safety records</h2><span class="aside">{len(sp)} protocols · {n_surf} block-pinned surfaces</span></div>
<p class="sec-intro">Who can upgrade, pause or change each protocol, pinned to canonical Ethereum and Base blocks. The {c["records"]} Sprint records are anchored on Base by EAS attestations; the {n_pin} RPC-pinned records are reproducible with <code>cast</code> but not yet EAS-attested. Check any other contract live and free with <code>/v1/check/preflight</code>.</p>
<table class="ix"><thead><tr><th>Protocol</th><th>Category</th><th>Chain</th><th>Surfaces</th><th>Status</th><th>Provenance</th></tr></thead><tbody>{rows}</tbody></table>
</div></section>
</main>
{footer(count_line, reg, "../")}
<script type="application/ld+json">{ld_json}</script>
</body></html>
"""
    return head("Protocol control-plane safety records · Pacta", f"Block-pinned control-plane safety records for {len(sp)} DeFi protocols.",
                f"{BASE_URL}/protocols/", prefix="../", og_title="Protocol control-plane safety records") + "\n" + body


def not_found_page(idx, sp=None):
    """docs/404.html: GitHub Pages serves it for any missing path, so every link is root-relative. data-nf on <main>
    makes the beacon (b.js) send not_found_404 (sanitised path, plus the slug for /protocols/<slug>/...) instead of page_load."""
    c = counts(idx)
    count_line = f'{c["sprints"]} Sprints · {c["records"]} Indexed Records'
    reg = idx["onchain_anchoring"]["commitment_registry"]
    n_protocols = len(site_protocols(idx) if sp is None else sp)
    claude = f"claude mcp add --transport http pacta {MCP_URL}"
    snippet = lambda label, value: f'<div class="qs-snip"><span class="qs-l">{label}</span><code class="mono">{E(value)}</code>{copy_btn(value)}</div>'
    body = f"""<body>
{topbar("/")}
<main id="main" class="memo-wrap" data-nf>
<div class="crumbs"><a href="/">Pacta</a> / Page not found</div>
<article class="memo">
<header><span class="tier">404 · Not found</span><h1>This page does not exist</h1>
<p class="lede">The link may be old or mistyped. Everything Pacta publishes is free and one click away.</p></header>
<section class="memo-sec"><h2>Where to go</h2>
<dl class="deflist">
<div><dt><a href="/protocols/">Protocol safety records →</a></dt><dd>Block-pinned control-plane records for {n_protocols} DeFi protocols, each with a <code>cast</code> reproduction.</dd></div>
<div><dt><a href="/#preflight">Run a free pre-flight check →</a></dt><dd>Who can upgrade, pause or change any contract on Ethereum or Base. No key, no wallet.</dd></div>
<div><dt><a href="/request/">Request coverage →</a></dt><dd>High-volume SLA access or a 24h collateral clearance attestation.</dd></div>
<div><dt>For agents</dt><dd><a href="/llms.txt">llms.txt</a> · <a href="/SKILL.md">SKILL.md</a> · <a href="/.well-known/agent.json">agent.json</a> · <a href="/api/v1/index.json">/api/v1/index.json</a></dd></div>
</dl></section>
<section class="memo-sec"><h2>Remote MCP server (free)</h2>
<p>Five read-only tools over Streamable HTTP, zero install. Tool <code>pacta_check_preflight</code> runs the same check as the live checker on the homepage.</p>
{snippet("Any MCP client (Streamable HTTP)", MCP_URL)}{snippet("Claude Code", claude)}</section>
</article>
</main>
{footer(count_line, reg, "/")}
</body></html>
"""
    return head("Page not found · Pacta", "This page does not exist. Pacta: free pre-execution contract checks for AI agents.", f"{BASE_URL}/404.html",
                prefix="/", og_title="Page not found · Pacta", extra='<meta name="robots" content="noindex">') + "\n" + body


def page(idx, radar):
    c = counts(idx)
    r = radar["refreshed_at"]
    count_line = f'{c["sprints"]} Sprints · {c["records"]} Indexed Records'
    reg = idx["onchain_anchoring"]["commitment_registry"]
    nxt = min(radar["items"], key=lambda it: it["eta"])
    n_ops = sum(len(it["operations"]) for it in radar["items"])
    body = f"""<body>
{topbar()}
<main id="main">
<section class="hero"><div class="wrap">
<div class="eyebrow">For AI agents, agent builders, vault curators and risk teams</div>
<h1>{E(H1)}</h1>
<p class="lede">Before an agent approves, deposits into or calls a contract, one request tells it who can change that contract (an EOA, a Safe, a timelock, or nobody), how fast, and whether it can pause, blacklist or upgrade. Every answer is pinned to a block hash and reproducible with <code>cast</code>.</p>
{quickstart_block()}
<div class="ctas"><a class="btn primary" href="#preflight">Run a free check <span class="arr">→</span></a><a class="btn" href="protocols/">Protocol safety records</a><a class="btn" href="#inspector">Inspect a protocol</a></div>
<div class="livebar" data-etas="{E(livebar_etas(radar))}"><span class="dot live"></span><b>{n_ops} timelock operations queued across {len(radar["items"])} protocols.</b> <span class="lb-next">Next: <span class="lb-p">{E(nxt["protocol"])}</span>, <span class="countdown" data-eta="{nxt["eta"]}">ETA {E(utc(nxt["eta"]))}</span></span> <small class="lb-asof">(as of radar block {r["block_number"]:,})</small> · <a href="#radar">Radar →</a></div>
<div class="ledger">
<div><b>{c["sprints"]}</b><span>Sprints completed</span><small>Ethereum Mainnet control-plane reviews</small></div>
<div><b>{c["records"]}</b><span>Verified surfaces</span><small>Each pinned to a canonical block hash</small></div>
<div><b>{c["eas_n"]}</b><span>Base EAS attestations</span><small>Sprints {c["eas_from"]}–{c["eas_to"]}{"; " + c["pending"] + " hash-pinned" if c["pending"] else ""}{"; " + c["later"] + " records after review" if c["later"] else ""}</small></div>
<div><b>$0</b><span>Free launch API</span><small>{E(RATE_LIMIT)} · no key · no wallet</small></div>
</div>
</div></section>
{preflight_section()}
{inspector(idx, c)}
{radar_section(radar)}
{onboarding_section(load_onboarding())}
{findings_section(idx)}
{index_section(idx, c, count_line)}
{verify_section(idx, c)}
{pricing_section()}
{request_section(idx)}
{faq_section(c, r)}
{about_section(idx)}
</main>
{footer(count_line, reg)}
</body></html>
"""
    return head(TITLE, DESC, BASE_URL + "/") + "\n" + body


def request_page(idx):
    c = counts(idx)
    count_line = f'{c["sprints"]} Sprints · {c["records"]} Indexed Records'
    reg = idx["onchain_anchoring"]["commitment_registry"]
    desc = "The API is free for agents ($0, no key). Teams: request high-volume SLA access or a 24h collateral clearance attestation ($5,000 USDC)."
    body = f"""<body>
{topbar("../")}
<main id="main">
<section class="sec" id="request"><div class="wrap">
<div class="crumbs"><a href="../">Pacta</a> / Request coverage</div>
<div class="sec-head"><span class="n">→</span><h2>Request coverage</h2><span class="aside">Nothing is sent until you choose a channel</span></div>
<p class="sec-intro">Agents do not need this page: the API, MCP server and all public data are free with no key (<a href="../#preflight">start here</a>). For high-volume SLA access or an on-chain clearance, pick a track and the protocols you hold, run or issue. The scope brief builds in your browser; open it as a pre-filled GitHub intake issue, compose it in Gmail, or copy it with our address. Public data stays free either way.</p>
{request_builder(idx, "../")}
</div></section>
{pricing_section("../")}
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    return head("Request coverage · Pacta", desc, f"{BASE_URL}/request/", prefix="../", og_title="Request Pacta coverage") + "\n" + body


def brief_page(slug, desc, idx, radar):
    src = open(os.path.join(BRIEF_SRC, f"{slug}.html")).read()
    title = html.unescape(re.match(r"<!-- title: (.*?) -->\n", src).group(1))   # plain text; head() escapes once
    content = src.split("\n", 1)[1]
    item = next((it for it in radar["items"] if it["brief"].rstrip("/").endswith(slug)), None)
    r = radar["refreshed_at"]
    meta = ""
    if item:
        ops = " ".join(hexref(o["op_id"], 8, 4) for o in item["operations"])
        state = "Pending" if all(o["pending"] for o in item["operations"]) else ("Executed" if all(o["done"] for o in item["operations"]) else "Mixed")
        meta = (f'<dl class="memo-meta">'
                f'<dt>Protocol</dt><dd>{E(item["protocol"])}</dd>'
                f'<dt>Timelock</dt><dd>{hexref(item["timelock"])} · {secs(item["min_delay_seconds"])} minimum delay</dd>'
                f'<dt>Operation{"s" if len(item["operations"]) > 1 else ""}</dt><dd>{ops}</dd>'
                f'<dt>Execution window</dt><dd><span class="countdown" data-eta="{item["eta"]}">ETA {E(utc(item["eta"]))}</span> · {E(utc(item["eta"], True))}</dd>'
                f'<dt>State</dt><dd>{state} at finalized block <span class="num">#{r["block_number"]:,}</span> ({E(r["block_time_utc"])}) '
                f'<span class="badge final">Scanner-pinned (L1 finalized)</span></dd></dl>')
    content = content.replace("</header>", "</header>\n" + meta, 1)
    c = counts(idx)
    count_line = f'{c["sprints"]} Sprints · {c["records"]} Indexed Records'
    reg = idx["onchain_anchoring"]["commitment_registry"]
    body = f"""<body>
{topbar("../../")}
<main id="main" class="memo-wrap">
<div class="crumbs"><a href="../../">Pacta</a> / <a href="../../#radar">Timelock radar</a> / Pre-execution brief</div>
<article class="memo">
{content}</article>
<div class="memo-foot"><span>Read-only on-chain analysis. Not investment advice. Exploit-sensitive vulnerabilities are never published here; they go through Immunefi or Cantina bounty programmes.</span><a href="../../request/">Get briefs like this for your collateral →</a></div>
</main>
{footer(count_line, reg, "../../")}
</body></html>
"""
    return head(title, desc, f"{BASE_URL}/briefs/{slug}/", prefix="../../", og_title=title, og_type="article") + "\n" + body


def llms(idx, radar):
    c = counts(idx)
    a = idx["onchain_anchoring"]
    r = radar["refreshed_at"]
    lines = [
        "# Pacta (by Fractal Neurons)", "",
        f"> Free pre-execution contract and governance safety API for AI agents (launch: $0, no API key, no wallet), plus block-pinned DeFi control-plane snapshots and timelock alerts. {c['sprints']} Sprints · {c['records']} Indexed Records.", "",
        "Pacta checks who can change the rules of DeFi protocols (proxy admins, timelock delays, Safe quorums, roles) and compares that with what the protocols document. Every record is a read-only on-chain observation pinned to an Ethereum Mainnet block number and canonical block hash.", "",
        "## Free API for agents (launch: $0, no API key, no wallet)",
        f"- Remote MCP (Streamable HTTP, zero install): {MCP_URL} · Claude Code: `claude mcp add --transport http pacta {MCP_URL}` · Cursor: `{{\"mcpServers\": {{\"pacta\": {{\"url\": \"{MCP_URL}\"}}}}}}`. Tools: pacta_check_preflight, pacta_scan_control_plane, pacta_scan_timelock_op, pacta_scan_proposal_diff, pacta_get_live_timelocks (all read-only).",
        f"- One call: `curl -s \"{API}/v1/check/preflight?chain=ethereum&address=0x...\"` returns a verdict (IMMUTABLE_NO_ADMIN, TIMELOCK_PROTECTED, ZERO_DELAY_TIMELOCK_RISK, MULTISIG_NO_TIMELOCK, INSTANT_EOA_ADMIN_RISK, UNDEPLOYED_OR_EOA, UNCLASSIFIED_CONTRACT_CONTROLLER), a 0-100 risk score, proxy / admin / timelock breakdown and pause / blacklist / upgrade capabilities, pinned to a block hash.",
        f"- [{OPENAPI_URL}]({OPENAPI_URL}): OpenAPI 3.1 for ChatGPT Actions, LangChain and OpenAPI tools; every route takes GET query parameters or a POST JSON body. {RATE_LIMIT}; free during the launch (pricingMode free_launch), x402 v1 + v2 ready.",
        f"- [{BASE_URL}/protocols/]({BASE_URL}/protocols/): per-protocol control-plane safety records.", "",
        "## Agent feeds",
        f"- [{BASE_URL}/llms-full.txt]({BASE_URL}/llms-full.txt): complete single-file reference (feeds, MCP tools, x402, anchoring, every record, proposal and queued operation).",
        f"- [{BASE_URL}/api/v1/proposals.json]({BASE_URL}/api/v1/proposals.json): schema `pacta.governance_proposals_feed.v1`; live Aave / Euler / Morpho / Sky proposals mapped to block-pinned observations.",
        f"- [{BASE_URL}/.well-known/agent.json]({BASE_URL}/.well-known/agent.json) (A2A Agent Card) · [{BASE_URL}/.well-known/mcp.json]({BASE_URL}/.well-known/mcp.json) (MCP manifest) · [{BASE_URL}/SKILL.md]({BASE_URL}/SKILL.md) (portable agent skill).", "",
        "## Data",
        f"- [{BASE_URL}/api/v1/index.json]({BASE_URL}/api/v1/index.json): schema `{idx['schema']}`; `summary_metrics` (sprints_completed={c['sprints']}, records_indexed={c['records']}, parameter_deltas={c['delta']}, protective_deltas={c['protect']}, aligned_baselines={c['aligned']}); each entry has id, protocol, category, sprint, block_number, block_hash, classification, surface, target_contract, target_label, check_type, selector_or_slot, call_signature, call_args, repro_calldata, onchain_observed, documented_reference, observed/documented delay seconds, summary_doc, summary_sha256, base_eas_uid.",
        f"- [{BASE_URL}/api/v1/rpc-pinned.json]({BASE_URL}/api/v1/rpc-pinned.json): schema `{PINNED_SCHEMA}`; {len(load_pinned()['entries'])} RPC-pinned control-plane records on Ethereum and Base (block number + hash, cast reproduction). NOT EAS-attested: no sprint, summary document or Base EAS UID.",
        f"- [{BASE_URL}/api/v1/radar.json]({BASE_URL}/api/v1/radar.json): queued timelock operations, refreshed at finalized block {r['block_number']} ({r['block_time_utc']}).",
        f"- [{BASE_URL}/api/v1/forum-digest.json]({BASE_URL}/api/v1/forum-digest.json): schema `{FORUM_SCHEMA}`; read-only digest of active governance forum topics plus `addressIndex` (chain:address -> protocol family).", "",
        "## Live pre-execution briefs",
    ] + [f"- [{BASE_URL}/briefs/{k}/]({BASE_URL}/briefs/{k}/): {v}" for k, v in BRIEFS.items()] + [
        "", "## Live onboarding verification briefs (assets proposed as collateral; block-pinned)",
        f"- [{BASE_URL}/api/v1/onboarding.json]({BASE_URL}/api/v1/onboarding.json): schema `pacta.onboarding_briefs.v1`; every check with call, calldata, raw result and decoded value; role maps replayed from events.",
    ] + [f"- [{BASE_URL}/briefs/{b['slug']}/]({BASE_URL}/briefs/{b['slug']}/): {OR.summary(b)} ({b['forum']['name']} #{b['forum']['topic']}; {OR.CHAIN_NAME[b['chain']]} block {b['pin']['number']})"
         for b in load_onboarding()["briefs"]] + [
        f"- [{BASE_URL}/demos/swapio-x402/]({BASE_URL}/demos/swapio-x402/): 90-second x402 storyboard (TreasuryGuard) with a live, on-chain-verified Base USDC settlement receipt.", "",
        "## Methodology",
        "- Scanner seats replay read-only eth_call / eth_getStorageAt at the cited block (two independent archive RPCs); an isolated verifier seat re-checks selectors, EIP-55 checksums, EIP-1967 slots and arithmetic offline.",
        "- Classifications: parameter_delta (on-chain differs from docs), protective_delta (a change that strengthens controls), aligned_baseline (on-chain matches docs).",
        f"- {VULN_ROUTE}", "",
        "## Access",
        "- Free and real-time for everyone, including vault curators, allocators and AI risk agents: every indexed record, the timelock radar, the briefs, /api/v1/*.json and this file. No key, no delay, no paywall; curators never pay.", "",
        "## On-chain anchoring (Base, chain id 8453)",
        f"- PactaCommitmentRegistry: `{a['commitment_registry']}` (Sourcify verified); attester `pacta.base.eth` (`{a['attester_eoa']}`).",
        f"- EAS schema: `{a['eas_schema_uid']}`. {anchoring_text(c)}",
    ] + [f"- Multi-attest tx, Sprints {r_}: `{tx}`" for r_, tx in c["multi_txs"].items()] + [
        "- Per-sprint attestation UIDs: `onchain_anchoring.sprint_eas_attestations` in /api/v1/index.json; each record's `base_eas_uid`.", "",
        "## Engagements (collateral issuers)",
        f"- 24h Collateral Onboarding & Delta Clearance Attestation: {CLEARANCE_PRICE} flat (optional continuous Aligned badge maintenance: {MONITORING_PRICE}). Canonical block-pinned control-plane audit, GitBook / config reconciliation PR, Base Mainnet EAS Aligned attestation in PactaCommitmentRegistry, and a Curator Diligence Dossier (PDF + JSON) for Morpho, Euler, Aave and Sky forum proposals. Clears open parameter_delta flags or onboards a new asset.",
        f"- Payment: USDC on Base (`{USDC['Base']}`) or Ethereum (`{USDC['Ethereum']}`) to the Pacta treasury (EOA) `{a['treasury_admin']}` (same address on both chains).",
        "- Community queue: free, unscheduled (typically 6–8 weeks).",
        f"- Request: {BASE_URL}/request/ (builds a scope brief; opens a pre-filled GitHub intake issue or Gmail compose, or copies the brief).", "",
        "## x402 API (live; free during the launch)",
        f"- On-demand scans of contracts outside the index. Free launch: every route answers HTTP 200 at $0 with no payment header (pricingMode free_launch); the x402 flow below applies only when the operator switches pricingMode to x402_paid. Live gateway: {B2A.X402_URL} (Cloudflare Worker, x402Versions [1, 2]: v1 network `base` with `X-PAYMENT` / `X-PAYMENT-RESPONSE`, v2 network `{B2A.X402_NETWORK_V2}` with `PAYMENT-REQUIRED` / `PAYMENT-SIGNATURE` / `PAYMENT-RESPONSE`; USDC on Base, payTo `{B2A.PAY_TO}`, maxTimeoutSeconds {B2A.X402_MAX_TIMEOUT_S}). Routes (x402_paid prices): `GET /v1/check/preflight?chain=&address=` ($0.01), `GET /v1/scan/control-plane?chain=&address=` ($0.10), `GET /v1/scan/timelock-op?chain=&timelock=&opId=` ($0.25), `GET /v1/scan/proposal-diff?forum=&topicId=` ($0.15), `GET /v1/briefs/live-timelocks` ($0.10); free `/health`, `/.well-known/x402` (Bazaar discovery), `/v1/sample/control-plane`. A bare GET (no query) or zero-byte POST with no payment header on a paid route returns HTTP 402 with both challenges; the Bazaar extension carries a JSON Schema draft 2020-12 schema.",
        f"- Remote MCP: {MCP_URL} (free, no install). Local stdio server (from a clone of the repo; npm publication pending): set `PACTA_X402_URL={B2A.X402_URL}` to enable the scan tools; in x402_paid mode pay with `xPaymentHeader` (v1) or `paymentSignatureHeader` (v2). Settlement receipts are the facilitator's assertion (onchainReceiptVerified: false).", "",
        "## Contact",
        f"- {CONTACT} · {REPO} · {FN} · security: {BASE_URL}/.well-known/security.txt", "",
    ]
    return "\n".join(lines)


ROBOTS_TXT = ("# AI search engines and agent crawlers are welcome: everything here is public, free and read-only.\n"
              + "".join(f"User-agent: {b}\nAllow: /\n\n" for b in ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User",
                                                                   "Claude-SearchBot", "PerplexityBot", "Perplexity-User", "Googlebot", "Google-Extended", "Bingbot"))
              + f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n")


def main():
    idx, radar = load()
    today = dt.date.today().isoformat()

    def w(rel, text):
        p = os.path.join(DOCS, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(text)
    w("index.html", page(idx, radar))
    w("request/index.html", request_page(idx))
    for slug, desc in BRIEFS.items():
        w(f"briefs/{slug}/index.html", brief_page(slug, desc, idx, radar))
    onb = load_onboarding()
    for b in onb["briefs"]:
        w(f"briefs/{b['slug']}/index.html", onboarding_page(b, idx))
    pinned = load_pinned()                        # docs/api/v1/rpc-pinned.json (RPC-pinned, not EAS-attested)
    B2A.write_all(DOCS, idx, radar, onb, pinned)  # proposals.json, llms-full.txt, .well-known/{agent,mcp}.json, SKILL.md
    w("llms.txt", llms(idx, radar))
    sp = site_protocols(idx, pinned)
    digest = load_forum_digest()                  # data/forum-digest.json (optional; missing = empty digest)
    w("api/v1/forum-digest.json", forum_digest_json(idx, digest, pinned))
    for name, v in sp.items():
        w(f"protocols/{v['slug']}/index.html", protocol_page(name, v["entries"], idx, radar, digest, v["slug"]))
    w("protocols/index.html", protocols_index_page(idx, sp))
    w("404.html", not_found_page(idx, sp))       # GitHub Pages serves it for any missing path
    w("robots.txt", ROBOTS_TXT)
    urls = ["/", "/request/", "/llms.txt", "/api/v1/index.json", "/api/v1/radar.json"] + [f"/briefs/{k}/" for k in BRIEFS] + \
        [f"/briefs/{b['slug']}/" for b in load_onboarding()["briefs"]] + (["/api/v1/onboarding.json"] if load_onboarding()["briefs"] else []) + \
        ["/api/v1/proposals.json", "/api/v1/rpc-pinned.json", "/llms-full.txt", "/SKILL.md", "/.well-known/agent.json", "/.well-known/mcp.json",
         "/demos/swapio-x402/", "/protocols/"] + [f"/protocols/{v['slug']}/" for v in sp.values()]
    w("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
      + "".join(f"  <url><loc>{BASE_URL}{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    w(".well-known/security.txt", f"Contact: mailto:{CONTACT}\nExpires: 2027-11-13T00:00:00.000Z\nPreferred-Languages: en\n"
      f"Canonical: {BASE_URL}/.well-known/security.txt\nPolicy: {BASE_URL}/#faq\n")
    w(".nojekyll", "")    # GitHub Pages: serve dot-directories such as /.well-known/
    c = counts(idx)
    print(f"built: {c['sprints']} sprints, {c['records']} records; radar block {radar['refreshed_at']['block_number']}; base {BASE_URL}")


if __name__ == "__main__":
    main()
