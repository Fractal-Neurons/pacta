"""Build the Pacta static site (docs/) from the data files, so counts can never drift.

  python3 tools/refresh_radar.py            # (live, read-only) refresh docs/api/v1/radar.json
  python3 tools/make_og.py --font-dir DIR   # (optional) re-render og-preview.png / favicon.png
  python3 tools/build_site.py               # writes docs/index.html, llms.txt, robots.txt, sitemap.xml,
                                            # .well-known/security.txt, .nojekyll and brief <head> metadata
  python3 verify_site_v2.py                 # checks the result

Domain cutover: change BASE_URL below (one line) and rebuild; every absolute URL (canonical, Open Graph, X card,
sitemap, robots, security.txt, llms.txt, brief metadata) is derived from it.
"""

import datetime as dt
import html
import json
import os
import re

BASE_URL = "https://pacta.wtf"   # cutover: "https://pacta.fractalneurons.com"

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DOCS = os.path.join(ROOT, "docs")
E = html.escape
CONTACT = "pacta@dri.network"
REPO = "https://github.com/Fractal-Neurons/pacta"
FN = "https://fractalneurons.com"
TITLE = "Pacta · DeFi control-plane monitoring"
DESC = "Block-pinned DeFi control-plane snapshots and timelock alerts."
OG_TITLE = "Know when your DeFi collateral’s rules change — before they do"
H1 = "Know when the people who control your DeFi collateral can change the rules — before they do."
BRIEFS = {
    "ethena-ops-0x0ca0-0x1fe5": "Pre-execution brief: two queued Ethena timelock operations onboard RLUSD and USAT to EthenaMinting "
                                "at 200M / 20M USDe-per-block caps (1-day delay; ETAs 2026-11-14 10:20–10:22 UTC).",
    "etherfi-op-0x244e": "Pre-execution brief: ether.fi operation 0x244e…359f moves the EtherfiL1SyncPoolETH LayerZero V2 "
                         "delegate behind the 10-day EtherFiTimelock (ETA 2026-11-20 16:54 UTC).",
    "treehouse-op-0x2f11": "Pre-execution brief: a queued 5-day timelock operation upgrades the Treehouse TREE token (not tETH) "
                           "and installs a 5-of-7 Safe blacklister (ETA 2026-11-17 04:51 UTC).",
}
PILLS = [("Ethena", "Ethena"), ("Lido", "Lido"), ("Curve crvUSD", "Curve Finance (crvUSD)"), ("Stader ETHx", "Stader"), ("Kelp rsETH", "Kelp")]


def short(h, a=6, b=4):
    return h[:a] + "…" + h[-b:]


def utc(t):
    return dt.datetime.fromtimestamp(t, dt.UTC).strftime("%Y-%m-%d %H:%M UTC")


def secs(s):
    if s is None:
        return "—"
    d = s / 86400
    return (f"{int(d)}d" if d >= 1 and d == int(d) else f"{s / 3600:g}h")


def head(title, desc, url, image=f"{BASE_URL}/og-preview.png", css="styles.css", js=True, icon_prefix=""):
    """Order matters: everything social/agent-relevant comes first and stays inside the first 1.2 KB."""
    t, d = E(title), E(desc)
    parts = [
        '<!doctype html><html lang="en"><head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{t}</title>",
        f'<meta name="description" content="{d}">',
        f'<link rel="canonical" href="{url}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="Pacta by Fractal Neurons">',
        f'<meta property="og:title" content="{E(OG_TITLE)}">',
        f'<meta property="og:description" content="{d}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{image}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{E(OG_TITLE)}">',
        f'<meta name="twitter:description" content="{d}">',
        f'<meta name="twitter:image" content="{image}">',
        f'<link rel="icon" href="{icon_prefix}favicon.svg" type="image/svg+xml">',
        f'<link rel="icon" href="{icon_prefix}favicon.png" type="image/png" sizes="32x32">',
        f'<link rel="stylesheet" href="{css}">',
        f'<link rel="alternate" type="text/markdown" href="{icon_prefix}llms.txt" title="llms.txt">',
    ]
    if js:
        parts.append('<script>try{if(localStorage.getItem("pacta-theme")==="paper")document.documentElement.dataset.theme="paper"}catch(e){}</script>')
        parts.append('<script src="app.js" defer></script>')
    parts.append("</head>")
    return "\n".join(parts)


def load():
    idx = json.load(open(os.path.join(DOCS, "api", "v1", "index.json")))
    radar = json.load(open(os.path.join(DOCS, "api", "v1", "radar.json")))
    m = idx["summary_metrics"]
    n = len(idx["entries"])
    assert m["records_indexed"] == n == m["parameter_deltas"] + m["protective_deltas"] + m["aligned_baselines"]
    assert m["sprints_completed"] == max(e["sprint"] for e in idx["entries"])
    return idx, radar


def counts(idx):
    m = idx["summary_metrics"]
    eas = sorted(int(k) for k in idx["onchain_anchoring"]["sprint_eas_attestations"])
    return {"sprints": m["sprints_completed"], "records": m["records_indexed"], "eas_n": len(eas), "eas_from": eas[0], "eas_to": eas[-1],
            "pending": f"{eas[-1] + 1}–{m['sprints_completed']}", "multi_tx": idx["onchain_anchoring"]["eas_multi_attest_tx"],
            "delta": m["parameter_deltas"], "protect": m["protective_deltas"], "aligned": m["aligned_baselines"]}


def badge(c):
    return {"parameter_delta": '<span class="badge delta">parameter delta</span>',
            "protective_delta": '<span class="badge protect">protective delta</span>'}.get(c, '<span class="badge ok">aligned baseline</span>')


def matrix_rows(idx):
    rows = []
    for e in sorted(idx["entries"], key=lambda e: (-e["sprint"], e["protocol"])):
        proof = (f'<a href="https://base.easscan.org/attestation/view/{E(e["base_eas_uid"])}" target="_blank" rel="noopener">EAS {E(short(e["base_eas_uid"]))}</a>'
                 if e["base_eas_uid"] else '<span class="count">EAS pending (hash-pinned)</span>')
        search = " ".join(str(e.get(k, "")) for k in ("protocol", "category", "surface", "target_contract", "target_label", "onchain_observed", "classification", "sprint")).lower()
        rows.append(
            f'<tr data-class="{E(e["classification"])}" data-search="{E(search)}">'
            f'<td><b>{E(e["protocol"])}</b><div class="count">{E(e["category"])}</div></td>'
            f'<td>S{e["sprint"]}<div class="count">#{e["block_number"]:,}</div><div class="addr" title="{E(e["block_hash"])}">{E(short(e["block_hash"], 10, 6))}</div></td>'
            f'<td><b>{E(e["target_label"])}</b> <span class="addr">{E(e["target_contract"])}</span><div>{E(e["surface"])}</div><div class="obs">{E(e["onchain_observed"])}</div></td>'
            f'<td>{badge(e["classification"])}</td>'
            f'<td class="mono">{secs(e["observed_delay_seconds"])} / {secs(e["documented_delay_seconds"])}</td>'
            f'<td><a href="{REPO}/blob/main/{E(e["summary_doc"])}" target="_blank" rel="noopener">Summary</a><div>{proof}</div>'
            f'<div class="addr" title="SHA-256 of the summary">{E(short(e["summary_sha256"], 10, 4))}</div></td></tr>')
    return "\n".join(rows)


def cast_line(e):
    """Runnable cast command for a record (full signature + all arguments); mirrors castCmd() in docs/app.js."""
    rpc = '--rpc-url "$ETH_RPC_URL"'
    if e["check_type"] == "eth_getStorageAt":
        return f'cast storage {e["target_contract"]} {e["selector_or_slot"]} --block {e["block_number"]} {rpc}'
    args = (" " + " ".join(e["call_args"])) if e.get("call_args") else ""
    return f'cast call {e["target_contract"]} "{e["call_signature"]}"{args} --block {e["block_number"]} {rpc}'


def static_inspector(idx):
    """Server-rendered default (Ethena, most recent record) so crawlers and no-JS readers see a real record."""
    e = sorted([x for x in idx["entries"] if "Ethena" in x["protocol"]], key=lambda x: -x["sprint"])[0]
    return (f'<div><b>{E(e["protocol"])}</b> {badge(e["classification"])} <span class="count">Sprint {e["sprint"]} · {E(e["surface"])}</span></div>'
            f'<div class="cell"><h3>(a) Pinned block &amp; canonical hash</h3><p>#{e["block_number"]:,} <span class="badge ok">Scanner-pinned (L1 finalized)</span></p><p class="addr">{E(e["block_hash"])}</p></div>'
            f'<div class="cell"><h3>(c) Timelock &amp; proxy control plane</h3><p>minDelay observed {secs(e["observed_delay_seconds"])} vs docs {secs(e["documented_delay_seconds"])}</p></div>'
            f'<div class="cell"><h3>(d) Reproduce it yourself</h3><div class="cmd"><pre>{E(cast_line(e))}\n'
            f'cast block {e["block_number"]} --field hash --rpc-url "$ETH_RPC_URL"   # expect {E(e["block_hash"])}</pre></div></div>'
            f'<p class="count">{E(e["onchain_observed"])}</p>')


def radar_cards(radar):
    out = []
    for it in radar["items"]:
        ops = " &amp; ".join(f'<span class="addr">{E(short(o["op_id"], 6, 4))}</span>' for o in it["operations"])
        state = "pending" if all(o["pending"] for o in it["operations"]) else ("executed" if all(o["done"] for o in it["operations"]) else "mixed")
        out.append(
            f'<article class="card"><div class="meta">{E(it["protocol"])} · ETA {E(utc(it["eta"]))} · {secs(it["min_delay_seconds"])} timelock · {state} at refresh</div>'
            f'<h3>{E(it["title"])}</h3><p>{E(it["summary"])}</p><p class="meta">Op {ops}</p>'
            f'<div class="countdown" data-eta="{it["eta"]}">ETA {E(utc(it["eta"]))}</div>'
            f'<a class="more" href="{E(it["brief"])}">Read the pre-execution brief →</a></article>')
    return "\n".join(out)


def page(idx, radar):
    c = counts(idx)
    r = radar["refreshed_at"]
    count_line = f'{c["sprints"]} Sprints · {c["records"]} Indexed Records'
    fresh = f'Last refreshed: {r["block_time_utc"]} (Mainnet finalized block #{r["block_number"]:,})'
    pills = "".join(f'<button class="pill" type="button" data-key="{E(k)}" aria-pressed="false">{E(lbl)}</button>' for lbl, k in PILLS)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    schema = idx["onchain_anchoring"]["eas_schema_uid"]
    body = f"""<body>
<a class="skip" href="#main">Skip to content</a>
<header class="hdr"><div class="wrap">
<a class="brand" href="./"><img src="favicon.svg" alt="" width="26" height="26">PACTA <small>by Fractal Neurons</small></a>
<nav class="nav" aria-label="Sections"><a href="#inspector">Inspector</a><a href="#radar">Radar</a><a href="#findings">Findings</a><a href="#index">Index</a><a href="#pricing">Pricing</a><a href="#verify">Verify</a><a href="#about">About</a></nav>
<button class="theme-toggle" type="button" aria-label="Switch theme"><span data-t="slate" class="on">Slate</span>/<span data-t="paper">Paper</span></button>
</div></header>
<main id="main">
<section class="hero"><div class="wrap hero-grid">
<div>
<div class="eyebrow">PACTA SUNT SERVANDA · BY FRACTAL NEURONS</div>
<h1>{E(H1)}</h1>
<p class="sub"><strong>Built for DeFi vault curators, institutional allocators, and protocol risk teams.</strong> Point-in-time smart contract audit PDFs go stale the moment a multisig rotates signers, attaches a Safe module, or lowers a timelock delay. Pacta delivers deterministic, block-pinned control-plane snapshots and pre-execution timelock alerts reproducible against any archive node.</p>
<div class="ctas">
<a class="btn primary" href="mailto:{CONTACT}?subject=Pacta%20Collateral%20Control-Plane%20Alerts">Get Alerts on Your Collateral</a>
<a class="btn" href="mailto:{CONTACT}?subject=Pacta%20Curator%20Walkthrough">Book a Risk Walkthrough</a>
<a class="btn" href="#radar">Explore Live Radar ↓</a>
</div>
<div class="stats">
<div class="stat"><b>{E(count_line)}</b><span>Ethereum Mainnet, each pinned to a canonical block hash</span></div>
<div class="stat"><b>{c["eas_n"]} Base EAS sprint attestations</b><span>Sprints {c["eas_from"]}–{c["eas_to"]} · multi-attest tx <span class="mono">{E(short(c["multi_tx"]))}</span></span></div>
<div class="stat"><b>Sprints {c["pending"]} hash-pinned</b><span>block hash + SHA-256 summary digest in <a href="api/v1/index.json">/api/v1/index.json</a> until batch-attested</span></div>
<div class="stat"><b>Free Private Disclosure</b><span>Exploit-sensitive findings are never published here; they go privately to official security teams at no cost</span></div>
</div>
</div>
<aside class="inspector" id="inspector" aria-label="Control-plane inspector">
<h2>Control-Plane Inspector · no wallet required</h2>
<p class="hint">Pick a protocol or search the {c["records"]} indexed records. Every value is pinned to a block and reproducible.</p>
<div class="pills">{pills}</div>
<input class="search" id="insp-q" type="search" placeholder="Paste 0x address or filter {c["records"]} indexed records…" aria-label="Search indexed records">
<div class="results" id="insp-results"></div>
<div class="panel" id="insp-panel">{static_inspector(idx)}</div>
</aside>
</div></section>

<section class="sec" id="radar"><div class="wrap">
<div class="sec-h"><span class="kicker">01</span><h2>Queued Timelock Radar</h2><span class="fresh">{E(fresh)}</span></div>
<p class="count">State and ETAs are read at the finalized block above on two independent RPCs; countdowns run in your browser from each operation's on-chain ETA.</p>
<div class="grid3">{radar_cards(radar)}</div>
</div></section>

<section class="sec" id="findings"><div class="wrap">
<div class="sec-h"><span class="kicker">02</span><h2>Headline findings, in plain English</h2><p>Each card links to a block-pinned record below.</p></div>
<div class="grid4">
<article class="card"><div class="meta">Ethena · Sprint 7 &amp; 14 · parameter delta</div><h3>New Ethena collateral can be approved on a 1-day timelock, while the docs describe 7 days.</h3><p>Two queued operations onboard RLUSD and USAT at 200M / 20M USDe-per-block caps (the same as USDC / USDT), with <span class="mono">stablesDeltaLimit = 0</span> (0 bps). Observed <span class="mono">getMinDelay() = 86,400s</span>; key-trust-assumptions.md lists 7-day time-locks, and a July 2026 Risk Committee post mentions the 1-day delay.</p><a class="more" href="briefs/ethena-ops-0x0ca0-0x1fe5/">Brief →</a></article>
<article class="card"><div class="meta">Stader ETHx · Sprint 12 · parameter delta</div><h3>Stader's Manager Safe is 3-of-6 on-chain; the docs say 3-of-5.</h3><p>The ETHx upgrade path itself sits behind a 7-day TimelockController, as documented. The difference is the Manager multisig's signer set.</p><a class="more" href="#index">Record →</a></article>
<article class="card"><div class="meta">Curve crvUSD · Sprint 11 · parameter delta</div><h3>crvUSD market creation now passes through a LendingOwnerProxy wrapper.</h3><p>ControllerFactory <span class="mono">admin()</span> is a LendingOwnerProxy whose <span class="mono">dao()</span> is the CurveOwnershipAgent (7-day Aragon vote), with a 5-of-9 EmergencyDAO. The docs still name the agent as the admin.</p><a class="more" href="#index">Record →</a></article>
<article class="card"><div class="meta">Inverse FiRM · Sprint 14 · protective delta</div><h3>A zero staleness threshold switches FiRM's oracle staleness check off for sDOLA; a queued 48h fix turns it on.</h3><p><span class="mono">stalenessThreshold = 0</span> makes <span class="mono">isPriceStale</span> return false; a queued Timelock transaction sets 86,500s.</p><a class="more" href="#index">Record →</a></article>
</div>
</div></section>

<section class="sec" id="index"><div class="wrap">
<div class="sec-h"><span class="kicker">03</span><h2>Public Control-Plane Index</h2><p>{E(count_line)} · {c["delta"]} parameter deltas · {c["protect"]} protective deltas · {c["aligned"]} aligned baselines</p></div>
<details class="matrix" open><summary>Full {c["records"]}-record address matrix (filterable)</summary>
<div class="matrix-tools">
<input class="search" id="matrix-q" type="search" placeholder="Filter by protocol, address or text…" aria-label="Filter records">
<button class="chip" type="button" data-class="all" aria-pressed="true">All</button>
<button class="chip" type="button" data-class="parameter_delta" aria-pressed="false">Parameter deltas</button>
<button class="chip" type="button" data-class="protective_delta" aria-pressed="false">Protective deltas</button>
<button class="chip" type="button" data-class="aligned_baseline" aria-pressed="false">Aligned baselines</button>
<span class="count" id="matrix-count">{c["records"]} of {c["records"]} records shown</span>
</div>
<div class="tbl-wrap"><table id="matrix"><thead><tr><th>Protocol</th><th>Sprint / block</th><th>Contract &amp; observation</th><th>Class</th><th>Delay obs / docs</th><th>Proof</th></tr></thead>
<tbody>
{matrix_rows(idx)}
</tbody></table></div>
</details>
</div></section>

<section class="sec" id="verify"><div class="wrap">
<div class="sec-h"><span class="kicker">04</span><h2>Don't trust, verify</h2><p>Everything here can be replayed against any archive node.</p></div>
<div class="grid2">
<div class="card"><h3>Chain &amp; finality coverage</h3><ul class="clean">
<li><b>Ethereum Mainnet</b>: all {c["records"]} indexed records, each pinned to a block number and its canonical block hash (reads use EIP-1898 <span class="mono">requireCanonical</span>).</li>
<li><b>Base</b>: on-chain anchoring (PactaCommitmentRegistry + EAS) and the x402 paid API.</li>
<li><b>Arbitrum</b>: available for engagements on request.</li>
<li>Live monitoring uses a 64-block reorg-aware indexer: observations from orphaned blocks are retracted, never silently kept.</li></ul></div>
<div class="card"><h3>Open verifier spec</h3><ul class="clean">
<li>Each record lists the target contract, the 4-byte selector or EIP-1967 slot, the block number and the canonical block hash: replay it with <span class="mono">cast call</span> / <span class="mono">cast storage</span> or raw <span class="mono">eth_call</span> / <span class="mono">eth_getStorageAt</span>.</li>
<li>Machine-readable feed: <a href="api/v1/index.json">/api/v1/index.json</a> (schema <span class="mono">{E(idx["schema"])}</span>) and <a href="api/v1/radar.json">/api/v1/radar.json</a>.</li>
<li>Sourcify-verified PactaCommitmentRegistry <a href="https://sourcify.dev/#/lookup/{E(reg)}" target="_blank" rel="noopener" class="mono">{E(short(reg))}</a> on Base; EAS schema <a href="https://base.easscan.org/schema/view/{E(schema)}" target="_blank" rel="noopener" class="mono">{E(short(schema))}</a>.</li></ul></div>
</div>
<pre class="block"># 1) Pull the block-pinned index
curl -s {BASE_URL}/api/v1/index.json | jq '.entries[] | {{protocol, sprint, block_number, classification, observed_delay_seconds}}'
# 2) Replay one record (Stader Manager Safe threshold at block 26403676)
cast call 0xAAfb31780e4b9c95Bc920e388f4925A874cd07AF "getThreshold()" --block 26403676 --rpc-url "$ETH_RPC_URL"
cast block 26403676 --field hash --rpc-url "$ETH_RPC_URL"   # expect 0xf4246ca2…c3ae
# 3) Run the reference Foundry suite (offline unit tests; fork tests when ETH_RPC_URL is set)
forge test --no-match-test "testFork" -vv</pre>
</div></section>

<section class="sec" id="pricing"><div class="wrap">
<div class="sec-h"><span class="kicker">05</span><h2>Engagements</h2><p>One-time checks priced per engagement; continuous coverage priced per month.</p></div>
<div class="grid4">
<article class="card"><h3>Express Single-Contract Check</h3><div class="price">$250 <small>one-time</small></div><p>4h turnaround. Block-pinned control-plane snapshot of one contract: proxy admin, owner, Safe quorum, timelock delay, versus its docs.</p><a class="more" href="mailto:{CONTACT}?subject=Pacta%20Express%20Single-Contract%20Check">Request →</a></article>
<article class="card"><h3>Protocol Control-Plane Audit</h3><div class="price">$1,500 <small>one-time</small></div><p>24h turnaround. Full control-plane map of a protocol with reproducible records and a written brief.</p><a class="more" href="mailto:{CONTACT}?subject=Pacta%20Protocol%20Control-Plane%20Audit">Request →</a></article>
<article class="card"><h3>Protocol CI &amp; Pre-Execution Guard</h3><div class="price">$1,500 <small>/ mo</small></div><p>Continuous GitHub CI role-diff gate, fork simulation of queued timelock payloads, and Base EAS anchoring.</p><a class="more" href="mailto:{CONTACT}?subject=Pacta%20Protocol%20CI%20%26%20Pre-Execution%20Guard">Request →</a></article>
<article class="card featured"><h3>Institutional Curator &amp; Allocator Radar</h3><div class="price">$3,000 <small>/ mo</small></div><p>24/7 monitoring across up to 25 collateral protocols, queued-timelock impact briefs, Slack / Telegram / webhook alerts, and x402 API access.</p><a class="more" href="mailto:{CONTACT}?subject=Pacta%20Curator%20%26%20Allocator%20Radar">Request →</a></article>
</div>
<article class="card disclosure" style="margin-top:16px"><h3>Free Private Disclosure</h3><p>Exploit-sensitive findings are never published here — they are routed privately at no cost to official protocol security teams.</p><a class="more" href="mailto:{CONTACT}?subject=Private%20Security%20Disclosure%20Verification">Verify a disclosure →</a></article>
</div></section>

<section class="sec faq" id="faq"><div class="wrap">
<div class="sec-h"><span class="kicker">06</span><h2>Questions</h2></div>
<details><summary>What exactly is anchored on-chain?</summary><p>Sprints {c["eas_from"]}–{c["eas_to"]} carry {c["eas_n"]} on-chain Base EAS sprint attestations (multi-attest tx <span class="mono">{E(short(c["multi_tx"]))}</span>), recorded by <span class="mono">pacta.base.eth</span> in PactaCommitmentRegistry. Sprints {c["pending"]} are pinned by canonical block hash and SHA-256 summary digest in /api/v1/index.json until they are batch-attested.</p></details>
<details><summary>How do I reproduce a record?</summary><p>Every record gives the contract, selector or storage slot, block number and canonical block hash. Run the listed <span class="mono">cast</span> command against any archive node and compare the block hash.</p></details>
<details><summary>What happens to exploit-sensitive findings?</summary><p>Free Private Disclosure: they are never published here and are routed privately, at no cost, to official protocol security teams (security contacts, private advisories or bounty platforms).</p></details>
<details><summary>Do I need a wallet?</summary><p>No. The inspector, the radar and the JSON feed are public and read-only. Paid API access uses x402 (USDC on Base) and is optional.</p></details>
<details><summary>How fresh is the radar?</summary><p>The radar states the exact finalized block it was refreshed at ({r["block_number"]:,}, {E(r["block_time_utc"])}); countdowns are computed from each operation's on-chain ETA.</p></details>
</div></section>

<section class="sec" id="about"><div class="wrap">
<div class="sec-h"><span class="kicker">07</span><h2>About Fractal Neurons</h2></div>
<div class="grid2">
<div class="card"><p>Pacta is built by <a href="{FN}" target="_blank" rel="noopener">Fractal Neurons</a>, a research engineering firm. <i>Pacta sunt servanda</i>: agreements must be kept. We check that the people who control DeFi collateral keep the commitments their documentation makes, and we tell you before that changes.</p></div>
<div class="card"><ul class="clean">
<li>Contact: <a href="mailto:{CONTACT}">{CONTACT}</a></li>
<li>Code &amp; data: <a href="{REPO}" target="_blank" rel="noopener">{REPO.replace("https://", "")}</a></li>
<li>For agents: <a href="llms.txt">/llms.txt</a> · <a href="api/v1/index.json">/api/v1/index.json</a></li>
<li>Security: <a href=".well-known/security.txt">/.well-known/security.txt</a></li></ul></div>
</div>
</div></section>
</main>
<footer class="ftr"><div class="wrap"><span>Pacta · Fractal Neurons · pacta.base.eth · {E(count_line)}</span><span><a href="{REPO}">GitHub</a> · <a href="api/v1/index.json">JSON</a> · <a href="llms.txt">llms.txt</a> · <a href="https://basescan.org/address/{E(reg)}">Base registry</a> · <a href="mailto:{CONTACT}">{CONTACT}</a></span></div></footer>
</body></html>
"""
    return head(TITLE, DESC, BASE_URL + "/") + "\n" + body


def llms(idx, radar):
    c = counts(idx)
    a = idx["onchain_anchoring"]
    r = radar["refreshed_at"]
    lines = [
        "# Pacta (by Fractal Neurons)", "",
        f"> Block-pinned control-plane snapshots and pre-execution timelock alerts for DeFi collateral. {c['sprints']} Sprints · {c['records']} Indexed Records.", "",
        "Pacta checks who can change the rules of DeFi protocols (proxy admins, timelock delays, Safe quorums, roles) and compares that with what the protocols document. Every record is a read-only on-chain observation pinned to an Ethereum Mainnet block number and canonical block hash.", "",
        "## Data",
        f"- [{BASE_URL}/api/v1/index.json]({BASE_URL}/api/v1/index.json): schema `{idx['schema']}`; `summary_metrics` (sprints_completed={c['sprints']}, records_indexed={c['records']}, parameter_deltas={c['delta']}, protective_deltas={c['protect']}, aligned_baselines={c['aligned']}); each entry has id, protocol, category, sprint, block_number, block_hash, classification, surface, target_contract, target_label, check_type, selector_or_slot, onchain_observed, documented_reference, observed/documented delay seconds, summary_doc, summary_sha256, base_eas_uid.",
        f"- [{BASE_URL}/api/v1/radar.json]({BASE_URL}/api/v1/radar.json): queued timelock operations, refreshed at finalized block {r['block_number']} ({r['block_time_utc']}).", "",
        "## Live pre-execution briefs",
    ] + [f"- [{BASE_URL}/briefs/{k}/]({BASE_URL}/briefs/{k}/): {v}" for k, v in BRIEFS.items()] + [
        f"- [{BASE_URL}/demos/swapio-x402/]({BASE_URL}/demos/swapio-x402/): 90-second x402 storyboard (TreasuryGuard).", "",
        "## Methodology",
        "- Scanner seats replay read-only eth_call / eth_getStorageAt at the cited block (two independent archive RPCs); an isolated verifier seat re-checks selectors, EIP-55 checksums, EIP-1967 slots and arithmetic offline.",
        "- Classifications: parameter_delta (on-chain differs from docs), protective_delta (a change that strengthens controls), aligned_baseline (on-chain matches docs).",
        "- Exploit-sensitive findings are never published; they are disclosed privately, free of charge, to official protocol security teams.", "",
        "## On-chain anchoring (Base, chain id 8453)",
        f"- PactaCommitmentRegistry: `{a['commitment_registry']}` (Sourcify verified); attester `pacta.base.eth` (`{a['attester_eoa']}`).",
        f"- EAS schema: `{a['eas_schema_uid']}`; {c['eas_n']} sprint attestations for Sprints {c['eas_from']}–{c['eas_to']} (multi-attest tx `{c['multi_tx']}`).",
        f"- Sprints {c['pending']}: pinned by canonical block hash + SHA-256 summary digest in /api/v1/index.json until batch-attested.", "",
        "## x402 paid API (USDC on Base)",
        "- Planned endpoint: https://api.pacta.wtf (deployment pending; not yet live). Routes: `GET /v1/scan/control-plane?chain=&address=` ($0.10), `GET /v1/scan/timelock-op?timelock=&opId=` ($0.25), `GET /v1/briefs/live-timelocks` ($0.10); free `/health`, `/.well-known/x402`, `/v1/sample/control-plane`.", "",
        "## Contact",
        f"- {CONTACT} · {REPO} · {FN} · security: {BASE_URL}/.well-known/security.txt", "",
    ]
    return "\n".join(lines)


def inject_brief_meta(slug, desc):
    p = os.path.join(DOCS, "briefs", slug, "index.html")
    s = open(p).read()
    s = re.sub(r"\n?<!-- pacta-meta v2 -->.*?<!-- /pacta-meta -->", "", s, flags=re.S)
    t = re.search(r"<title>(.*?)</title>", s, re.S)
    url = f"{BASE_URL}/briefs/{slug}/"
    meta = "\n".join([
        "<!-- pacta-meta v2 -->",
        f'<meta name="description" content="{E(desc)}">',
        f'<link rel="canonical" href="{url}">',
        '<meta property="og:type" content="article">',
        '<meta property="og:site_name" content="Pacta by Fractal Neurons">',
        f'<meta property="og:title" content="{t.group(1).strip()}">',
        f'<meta property="og:description" content="{E(desc)}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{BASE_URL}/og-preview.png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{t.group(1).strip()}">',
        f'<meta name="twitter:description" content="{E(desc)}">',
        f'<meta name="twitter:image" content="{BASE_URL}/og-preview.png">',
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
        '<link rel="icon" href="/favicon.png" type="image/png" sizes="32x32">',
        "<!-- /pacta-meta -->"])
    s = s.replace(t.group(0), t.group(0) + "\n" + meta, 1)
    open(p, "w").write(s)


def main():
    idx, radar = load()
    today = dt.date.today().isoformat()
    w = lambda rel, text: open(os.path.join(DOCS, rel), "w").write(text)
    w("index.html", page(idx, radar))
    w("llms.txt", llms(idx, radar))
    w("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n")
    urls = ["/", "/llms.txt", "/api/v1/index.json", "/api/v1/radar.json"] + [f"/briefs/{k}/" for k in BRIEFS] + ["/demos/swapio-x402/"]
    w("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
      + "".join(f"  <url><loc>{BASE_URL}{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    os.makedirs(os.path.join(DOCS, ".well-known"), exist_ok=True)
    w(".well-known/security.txt", f"Contact: mailto:{CONTACT}\nExpires: 2027-11-13T00:00:00.000Z\nPreferred-Languages: en\n"
      f"Canonical: {BASE_URL}/.well-known/security.txt\nPolicy: {BASE_URL}/#faq\n")
    w(".nojekyll", "")    # GitHub Pages: serve dot-directories such as /.well-known/
    for slug, desc in BRIEFS.items():
        inject_brief_meta(slug, desc)
    c = counts(idx)
    print(f"built: {c['sprints']} sprints, {c['records']} records; radar block {radar['refreshed_at']['block_number']}; base {BASE_URL}")


if __name__ == "__main__":
    main()
