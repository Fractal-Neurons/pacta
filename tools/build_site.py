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
import hashlib
import html
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import onboarding_render as OR  # noqa: E402
import build_b2a_feeds as B2A  # noqa: E402
import build_lookup as LK  # noqa: E402
import control_diff as CD  # noqa: E402  "What differs": changed vs matched parameters of flagged records
import graph_manifest as GM  # noqa: E402  docs/api/v1/graph-manifest.json (pacta.graph_manifest.v1)
import summary_short as SS  # noqa: E402  M7: <= 90-char human "What differs" line per protocol
import ui as U  # noqa: E402  shadcn/ui component markup (data-slot anatomy)
import decoded_briefs as DB  # noqa: E402  v4.6: radar briefs rendered from tools/briefs_decoded.json

ARR, EXT = U.arrow("right"), U.arrow("up-right")   # v4.4 (R-V4): inline icons, never a raw arrow glyph (U+2192 / U+2197) in HTML

BASE_URL = "https://pacta.wtf"   # cutover: "https://pacta.fractalneurons.com"
# Batch E: the $100 USDC capped bounty (pacta.wtf/bounties/). Issues #21-#24 on Fractal-Neurons/pacta, one per $25 slot; the
# issue text is tools/bounty_issues.json (verbatim, rendered on the page). Update the numbers here if GitHub assigns others.
BOUNTY_ISSUE_URLS = {1: "https://github.com/Fractal-Neurons/pacta/issues/21", 2: "https://github.com/Fractal-Neurons/pacta/issues/22",
                     3: "https://github.com/Fractal-Neurons/pacta/issues/23", 4: "https://github.com/Fractal-Neurons/pacta/issues/24"}

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DOCS = os.path.join(ROOT, "docs")
BRIEF_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "briefs_src")
E = html.escape
CONTACT = "pacta@dri.network"
REPO = "https://github.com/Fractal-Neurons/pacta"
FN = "https://fractalneurons.com"
TITLE = "Pacta · Protocol docs drift. The chain doesn’t."
DESC = ("Pacta reads who can upgrade, pause or change DeFi protocols on Ethereum and Base, flags where that differs from their docs, "
        "and attests every finding onchain.")
OG_TITLE = "Protocol docs drift. The chain doesn’t."
H1 = "Protocol docs drift. The chain doesn’t."
API = "https://pacta.fractalneurons.com"              # canonical custom domain on the live Cloudflare Worker
WORKERS_API = "https://pacta-x402.pacta.workers.dev"  # underlying Workers origin (kept in CSP connect-src for b.js)
MCP_URL, OPENAPI_URL = API + "/mcp", API + "/openapi.json"
RATE_LIMIT = "60 requests / minute per caller"
# T2: plain clients. curl and python-requests reach the API with their default User-Agent; Python's stdlib quickstart reads the
# static JSON on pacta.wtf (GitHub Pages), so no snippet needs a custom header and no copy talks about edge errors.
CURL = "curl -s"
EDITORIAL_INDEPENDENCE = ("Payment never alters a Pacta classification. A status changes only when onchain contract state or public "
                          "documentation changes and is verified at a new finalized block.")
HERO_EXAMPLE = ("stader-labs-ethx", "ethereum", "0xA35b1B31Ce002FBF2058D22F30f95D405200A15b")   # (record slug, chain, ETHx token)
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
    # v4.6: rendered from tools/briefs_decoded.json (decoded_briefs.py)
    "lombard-ops-0xceee-0x2f2a-0x6404": "Pre-execution brief: three Lombard timelock operations upgrade AssetRouter, BTC.b and LBTC to add "
                                        "a per-mint deposit fee, starting at 0 (1-day delay; ETA 2026-11-17 18:29 UTC).",
    "beefy-base-op-0x3302": "Pre-execution brief: a queued Base timelock operation widens the Beefy CLM USDC-VVV calm check from 9 to "
                            "25 ticks with setDeviation(25) (6-hour delay; ETA 2026-11-17 22:57 UTC).",
    "ethena-ops-0xb028-0xca05-0x108e-0x070a": "Pre-execution brief: four Ethena timelock operations cut USDe mint caps to 50M per block, "
                                              "delist USDm, reset two bridge limits to 25M per hour and add a custodian (ETAs 2026-11-18).",
    "yearn-v3-op-0x2a14": "Pre-execution brief: one 16-call Yearn V3 timelock batch adds 8 strategies to 6 vaults with max-debt caps "
                          "from 10,000 WETH to 10B USDC (7-day delay; ETA 2026-11-23 16:39 UTC).",
    # Sprint 27: fifth decoded brief
    "etherfi-liquid-op-0xf0fb": "Pre-execution brief: one 5-call ether.fi Liquid timelock batch rotates the strategist Merkle roots of the "
                                "liquidUSD, liquidETH and liquidBTC managers and clears one (1-day delay; ETA 2026-11-19 04:47 UTC).",
    # Sprint 28: sixth decoded brief
    "lombard-op-0xd07f": "Pre-execution brief: one 5-call Lombard timelock batch sets a 2,000-sat deposit fee on every LBTC and BTC.b "
                         "proof mint, doubles the router minimum to 4,000 sats and moves LBTC's redeem charge (1-day delay; ETA 2026-11-19 08:33 UTC).",
    # seventh and eighth decoded briefs
    "cap-op-0x3397": "Pre-execution brief: a queued Cap timelock operation upgrades the EigenLayer service manager (UUPS) so slashes pay out "
                     "only after EigenLayer's resolution delay and rewards are USDC-only (1-day delay; ETA 2026-11-19 16:23 UTC).",
    "compound-v3-op-0x86b4": "Pre-execution brief: Compound proposal 625 sends a Linea message that withdraws all 25.94 WETH of reserves "
                             "from Linea cWETHv3 and bridges the ETH to the Ethereum Timelock (2-day + 1-day delays; ETA 2026-11-20 18:58 UTC).",
    # ninth decoded brief
    "lista-lending-op-0x21df": "Pre-execution brief: one 16-call Lista timelock batch upgrades four liquidators to add an emergency pause and grants "
                               "PAUSER to a 1-of-15 Safe and the EmergencySwitchHub (1-day delay; ETA 2026-11-20 07:20 UTC).",
}
NAV = [("scorecards/", "Scorecards"), ("radar/", "Radar"), ("curators/", "Curators"), ("scan/", "Instant Scan"), ("#pricing", "Pricing"), ("bounties/", "Bounties"),
       ("mcp/", "MCP")]   # v2: the self-serve scan, curators matrix and #pricing in the bar; Protocols and For protocols stay in the footer
# Brand / RAG disambiguation (receipt/1817): the exact line in llms.txt, llms-full.txt, /llms/ and the Organization JSON-LD.
DISAMBIGUATION = B2A.DISAMBIGUATION
BRAND = B2A.BRAND
REMOTE_TOOLS_DOC, STDIO_TOOLS_DOC = B2A.REMOTE_TOOLS_DOC, B2A.STDIO_TOOLS_DOC
CARD_SIZE = (1200, 675)   # v4.5 item 16: per-protocol social receipt cards in docs/cards/ (shared with /v1/x-feed)
X_HANDLE, X_URL = "@pacta_fractal", "https://x.com/pacta_fractal"   # v4.5 G-P1-1: Pacta's official X account
ORG_LD = {"@context": "https://schema.org", "@type": "Organization", "name": "Pacta by Fractal Neurons", "alternateName": ["Pacta", "pacta.base.eth"],
          "url": f"{BASE_URL}/", "logo": f"{BASE_URL}/logo-512.png", "image": f"{BASE_URL}/logo.svg", "sameAs": [REPO, X_URL, "https://fractalneurons.com", "https://basescan.org/name-lookup-search?id=pacta.base.eth"],
          "parentOrganization": {"@type": "Organization", "name": "Fractal Neurons", "url": "https://fractalneurons.com"},
          "disambiguatingDescription": DISAMBIGUATION}
# Engagement tracks offered by the request builder (and linked from #pricing). key -> (title, price, unit, summary,
# GitHub dropdown option). Issuer work (24h dossier, re-verification, Continuous Control-Plane Monitoring), the high-throughput API SLA and
# the free community queue. The public data itself (every indexed record, the timelock radar, briefs, /api/v1/*.json
# and llms.txt) is free and real-time for everyone: no paywall, no delay. The keys are the closed `tier=` enum that
# /request/?tier=… prefills; the GitHub dropdown option strings must match .github/ISSUE_TEMPLATE/request-scan.yml
# exactly (prefill is by value).
CLEARANCE_PRICE, MONITORING_PRICE = "$2,500–$5,000 USDC", "$500–$2,500 USDC / month"
SPONSOR_POOL_ADDRESS = ""   # empty until dedicated 2-of-N Sponsor Pool Gnosis Safe is activated (never use 0x4348…Ed14 or 0xcA4E…da09)
PILOT_WATCH_API = f"{API}/v1/pilot/watch"
SPONSOR_POOL_API = f"{API}/v1/pilot/sponsor-pool"
# One tier family, shown identically on / (#pricing) and /request/ (M4): key -> (title, price, unit, summary, GitHub dropdown option).
# The keys are the closed tier= enum /request/?tier=… prefills; the option strings match .github/ISSUE_TEMPLATE/request-scan.yml.
TRACKS = {
    "community": ("Free Post-Fix Re-Verification & Queue", "$0", "within 7 days",
                  "Every scorecard, record and feed stays free, with live re-check on demand. Free factual re-verification within 7 days "
                  "whenever a protocol merges a public docs or on-chain fix.",
                  "Free factual re-verification within 7 days (merged docs or on-chain fix)"),
    "wholesale-150": ("Wholesale Ecosystem & Curator Vault Sweep", "$150 / protocol", "multi-protocol",
                      "For L2 ecosystems, grant councils and vault curators commissioning multi-protocol control-plane sweeps "
                      "($150 per protocol; undelivered targets never charged).",
                      "Wholesale Ecosystem & Curator Vault Sweep ($150 per protocol)"),
    "clearance": ("Full Protocol Control-Plane Dossier", CLEARANCE_PRICE, "24h SLA",
                  "Pre-launch or multi-contract suite diligence across proxies, Safes, governors and timelocks, reconciled with your docs and attested on "
                  "Base within 24h. The classification follows verified onchain and documentation evidence; payment never changes it.",
                  "Full Protocol Control-Plane Dossier ($2,500–$5,000 USDC, 24h SLA)"),
    "continuous": ("Continuous Control-Plane Monitoring", MONITORING_PRICE, "institutional SLA",
                   "Re-checks your control plane after governance proposals, signer rotations and timelock upgrades, and refreshes "
                   "the dossier and attestation. The result can still read Docs differ whenever docs and chain diverge.",
                   "Continuous Control-Plane Monitoring ($500–$2,500 USDC per month)"),
    "api_sla": ("Enterprise API SLA", "Custom", "priced on scope",
                "For wallets, custodians and agents that need more than 60 requests / minute or a dedicated SLA.",
                "Enterprise / High-Throughput API SLA (priced on scope)"),
}
DEFAULT_TRACK = "clearance"
PAID_TRACKS = ("wholesale-150", "clearance", "continuous", "api_sla")
# Settlement tracks in #req-pay (closed `settlement=` enum). Option A first: no transfer is needed to open intake.
# key -> (heading, sub-line, explanation, GitHub dropdown option)
SETTLEMENT = {
    "invoice": ("Option A — Formal Commercial Invoice (PDF) & Counterparty Settlement", "Recommended for protocol treasuries & CFOs",
                "Submit scope first (no upfront transfer required to open intake): Pacta issues a formal commercial invoice (PDF) "
                "and verified counterparty payment instructions upon scope confirmation — designed for foundation finance teams, "
                "legal review, and multi-signer treasury workflows.",
                "Option A: formal commercial invoice (PDF) and counterparty settlement"),
    "direct": ("Option B — Direct Express On-Chain USDC Settlement", "Immediate 24h turnaround",
               "USDC on Base or Ethereum to the Pacta treasury (direct settlement EOA) below; paste the transaction hash in the "
               "form and the 24-hour window starts once scope is confirmed.",
               "Option B: direct on-chain USDC settlement"),
}
DEFAULT_SETTLEMENT = "invoice"
TREASURY_LABEL = "Pacta treasury (direct settlement EOA)"     # an externally owned account: never a Safe / multisig
# Payment rail for the clearance offer. The treasury is an externally owned account (no contract code on Base or
# Ethereum), so the same key controls it on both chains; USDC contracts are Circle's native deployments.
USDC = {"Base": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "Ethereum": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"}
# ---- Option B v2: three self-serve products, each with its own page (/scan/, /webhook/, /seal/) and one Base USDC checkout --------
# Payment is ONE exact Base USDC transfer to the treasury; POST /v1/orders/verify reads the transaction receipt. app.js carries the
# same payee, token, chain and amounts as constants: the page's data-* attributes are display only and never decide where money goes.
ORDERS_VERIFY_API = f"{API}/v1/orders/verify"
CHECKOUT_CHAIN_ID = 8453
CHECKOUT_TREASURY = "0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14"
CHECKOUT = {   # the checkout engine's SKUs. None is live: automated paid webhook delivery is not active, so /webhook/ is the free pilot
    "radar-webhook-49": {
        "live": False,   # unpublished test fixture for the checkout engine's money-safety harness; no page renders it
        "tier": "webhook-49", "route": "webhook", "amount": "49.00", "atomic": 49_000_000, "price": "$49 USDC", "unit": "per month after 30-day free pilot · Base mainnet",
        "badge": "30-Day Free Pilot · Slack, Telegram, Discord, Email, HTTPS", "h1": "Live Timelock & Signer Alerts", "label": "Live Timelock & Signer Webhook",
        "lede": "Pacta polls the timelocks and Safes you choose every 30 minutes on Ethereum and Base, and alerts you when an operation "
                "is queued or a signer set changes, before it can execute. Start with a 30-day free pilot above, or activate a paid $49/month webhook directly on Base.",
        "cta": "Pay $49 USDC on Base & Activate Webhook",
        "title": "Live timelock & signer alerts · Free 30-Day Pilot · Pacta", "card": None,
        "desc": "Email, Slack, Telegram, Discord or HTTPS alerts when a watched timelock queues an operation or a Safe changes signers. Free 30-day pilot, then 49 USDC a month on Base."},
}
assert all(v["atomic"] == round(float(v["amount"]) * 10 ** 6) and v["price"] == f"${v['amount'][:-3]} USDC" for v in CHECKOUT.values())
SEAL_GUARANTEE = ("Verification never buys a grade: your Base-EAS record reads Aligned when "
                  "on-chain controls match the published documentation, and Docs differ when they do not.")
# real indexed contracts behind the example chips (resolved from api/v1/lookup.json at build time)
SCAN_SAMPLE_CHIPS = ("getMinDelay()", "PROPOSER_ROLE", "DEFAULT_ADMIN_ROLE", "MINTER_ROLE")
SCAN_CHIPS = [
    ("Moonwell", "moonwell-lending-base"),
    ("Aave V3", "aave-v3-gho"),
    ("Lido", "lido-steth-dual-governance"),
    ("Pendle V2", "pendle-finance-v2"),
    ("Inverse FiRM", "inverse-finance-firm"),
    ("Circle", "circle-usdc"),
]
CHIP_TICKERS = {
    "moonwell-lending-base": "WELL",
    "aave-v3-gho": "AAVE",
    "lido-steth-dual-governance": "stETH",
    "pendle-finance-v2": "PENDLE",
    "inverse-finance-firm": "INV",
    "circle-usdc": "USDC",
    "stader-labs-ethx": "SD",
    "yo-protocol": "YO",
}


def proto_icon_rel(slug):
    p_dir = os.path.join(ROOT, "tools", "protocol_icons")
    for ext in ("webp", "png", "svg"):
        if os.path.exists(os.path.join(p_dir, f"{slug}.{ext}")):
            return f"assets/protocols/{slug}.{ext}"
    return f"assets/protocols/{slug}.svg"


def proto_monogram_svg(slug, name):
    words = [w for w in re.split(r"[^A-Za-z0-9]+", re.sub(r"\([^)]*\)", "", name)) if w]
    letters = ((words[0][0] + words[1][0]) if len(words) >= 2 else (words[0][:2] if words else slug[:2])).upper()
    pal = (("#0f766e", "#14b8a6"), ("#1d4ed8", "#3b82f6"), ("#4338ca", "#6366f1"), ("#6d28d9", "#8b5cf6"),
           ("#be123c", "#f43f5e"), ("#b45309", "#f59e0b"), ("#047857", "#10b981"), ("#0369a1", "#0ea5e9"))
    h = int(hashlib.sha256(slug.encode("utf-8")).hexdigest()[:8], 16)
    c1, c2 = pal[h % len(pal)]
    gid = "g" + hashlib.sha256(slug.encode("utf-8")).hexdigest()[:6]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">'
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/></linearGradient></defs>'
            f'<circle cx="24" cy="24" r="23" fill="url(#{gid})"/>'
            f'<circle cx="24" cy="24" r="22" fill="none" stroke="#ffffff" stroke-opacity="0.22" stroke-width="1.5"/>'
            f'<text x="24" y="29" text-anchor="middle" fill="#ffffff" font-family="Inter,system-ui,sans-serif" '
            f'font-size="16" font-weight="700" letter-spacing="-0.4">{E(letters)}</text></svg>')


def chain_icon_svg(chain):
    if chain == "base":
        return ('<svg class="ch-ico ch-base" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">'
                '<circle cx="8" cy="8" r="8" fill="#0052FF"/>'
                '<path d="M8.15 12.4A4.4 4.4 0 1 0 3.76 8.5h5.19v-1H3.76A4.4 4.4 0 0 1 8.15 3.6a4.4 4.4 0 0 1 0 8.8Z" fill="#fff"/></svg>')
    return ('<svg class="ch-ico ch-eth" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">'
            '<circle cx="8" cy="8" r="8" fill="#627EEA"/>'
            '<path d="M8 2.5 4.6 8.1 8 6.55l3.4 1.55L8 2.5Z" fill="#fff" fill-opacity="0.9"/>'
            '<path d="M8 6.55 4.6 8.1 8 10.15l3.4-2.05L8 6.55Z" fill="#fff" fill-opacity="0.65"/>'
            '<path d="M8 10.9 4.6 8.85 8 13.5l3.4-4.65L8 10.9Z" fill="#fff" fill-opacity="0.9"/></svg>')


def chip_status_meta(cls_name):
    if cls_name in ("parameter_delta", "mixed"):
        return "GAP", "gap"
    if cls_name == "protective_delta":
        return "PROTECTIVE", "protective"
    if cls_name == "aligned_baseline":
        return "ALIGNED", "aligned"
    return "PINNED", "observed"


def receipt_inner_html(slug, label, chain, st_text, st_tone, prefix=""):
    sym = CHIP_TICKERS.get(slug, "")
    sym_html = f'<span class="rc-sym">{E(sym)}</span>' if sym and sym.lower() not in label.lower() else ""
    ch_lbl = "Base" if chain == "base" else "Ethereum"
    return (f'<img class="rc-logo" src="{prefix}{proto_icon_rel(slug)}" alt="" width="18" height="18">'
            f'<span class="rc-name">{E(label)}</span>{sym_html}'
            f'<span class="rc-sep" aria-hidden="true">·</span><span class="rc-chain">{ch_lbl}</span>'
            f'<span class="rc-st" data-tone="{st_tone}">{E(st_text)}</span>')
WEBHOOK_PICKS = [("Ethena", "ethena-usde-susde"), ("Morpho", "morpho-blue-core"), ("Aave v3", "aave-v3-gho"), ("Treehouse", "treehouse-tree-teth")]
ALERT_EXAMPLE = "lombard-op-0xd07f"     # the alert preview is built from this decoded radar brief
SOCIAL_SIZE = (1200, 628)   # X Website cards (1.91:1): og-preview.png and docs/cards/x-card-*-1200x628.png
VULN_ROUTE = ("Exploit-sensitive vulnerabilities are never published here. They go through the protocol’s Immunefi or "
              "Cantina bounty programme.")
# N7 (v4.3): the auditor referral is its own note, apart from "Pacta never sells grades", and links to the independence policy
# (/methodology/#independence), which also discloses the referral terms.
REFERRAL_NOTE = ("When code changes are needed, Pacta can refer teams to independent smart-contract auditors; under our Independence "
                 "Policy, referrals never influence docs-vs-chain status.")


def referral_note(prefix=""):
    """N7: REFERRAL_NOTE with "Independence Policy" linked to /methodology/#independence (prefix = path to the site root)."""
    a, b = REFERRAL_NOTE.split("Independence Policy")
    return (f'<p class="note" data-referral>{E(a)}<a href="{prefix}methodology/#independence">Independence Policy</a>{E(b)}</p>')
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


def copy_btn(value, label="Copy", what=None):
    """Ghost sm Button (32 px). A4: the accessible name says what is copied (an explicit `what`, else the value itself)."""
    aria = what or ("Copy " + (value if len(value) <= 60 else value[:57] + "…"))
    return (f'<button class="copy" data-slot="button" data-variant="ghost" data-size="sm" type="button" data-copy="{E(value)}" '
            f'aria-label="{E(aria)}">{U.icon("copy")}<span>{label}</span></button>')


def hexref(value, a=6, b=4):
    """Truncated hex for display, full value in title + copy button. Never lets a 42/66-char string break a layout."""
    return f'<span class="addr" title="{E(value)}">{E(short(value, a, b))}</span>{copy_btn(value)}'


ROBOTS_META = "index, follow, max-snippet:-1, max-image-preview:large"     # unrestricted indexing, snippets and grounding
ROBOTS_META_404 = "noindex, follow, max-snippet:-1, max-image-preview:large"   # 404.html: never index the not-found page itself


# S01: one policy for every generated page (meta CSP cannot carry frame-ancestors; send that as a response header at the edge)
CSP = ("default-src 'self';script-src 'self' https://static.ads-twitter.com;style-src 'self' 'unsafe-inline';"
       "img-src 'self' data: https://analytics.twitter.com https://t.co;font-src 'self';"
       "connect-src 'self' https://pacta.fractalneurons.com https://pacta-x402.pacta.workers.dev https://ethereum-rpc.publicnode.com https://base-rpc.publicnode.com "
       "https://eth.drpc.org https://mainnet.base.org https://analytics.twitter.com https://t.co;object-src 'none';base-uri 'self'")
# U2: Light / Dark / System on a .dark class; System (the default) follows prefers-color-scheme. Legacy values map: slate -> dark, paper -> light.
# X Ads strips the "?" from a Website-card URL (/scorecards/utm_source=x... then lands on 404.html): 404.html loads this first
# (render-blocking, same origin) and sends a stripped query on a known route back to /<route>/?<query> with location.replace.
RESCUE_JS = ('(function(w,L){var m=/^\\/((?:website-test|public\\/web\\/option-b-v2)\\/)?(scorecards|curators|request|scan|seal|webhook|miniapp|radar|bounties|leaderboard|methodology|'
             'protocols(?:\\/[a-z0-9-]+)?)\\/((?:utm_[a-z]+|tier|ref)=.+)$/.exec(L.pathname);'
             'if(m){w.pactaRescued=1;L.replace("/"+(m[1]||"")+m[2]+"/?"+m[3]+(L.search?"&"+L.search.slice(1):"")+L.hash)}})(window,location);\n')
THEME_JS = ('(function(){var d=document.documentElement,t="system",m=false;d.classList.add("js");'
            'try{t=localStorage.getItem("pacta-theme")||"system"}catch(e){}'
            'if(t==="slate")t="dark";if(t==="paper")t="light";if(t!=="light"&&t!=="dark")t="system";'
            'try{m=window.matchMedia("(prefers-color-scheme: dark)").matches}catch(e){}'
            'if(t==="dark"||(t==="system"&&m))d.classList.add("dark");d.setAttribute("data-theme-pref",t)})();\n')


APP_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.src.js")
_JS_REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^")
_JS_REGEX_WORDS = ("return", "typeof", "case", "in", "of", "new", "delete", "void", "throw", "instanceof")


def minify_js(src):
    """Deterministic, conservative minifier for tools/app.src.js (no template literals): drops /* */ and // comments outside
    strings and regex literals, trims every line and removes blank lines. Line breaks are kept, so automatic semicolon insertion
    behaves exactly as in the source; verify_site_v2 asserts docs/app.js == minify_js(tools/app.src.js) and runs the result."""
    assert "`" not in src, "template literals are not supported by minify_js"
    out, line = [], []
    i, n, prev = 0, len(src), ""

    def flush():
        t = "".join(line).strip()
        if t:
            out.append(t)
        line.clear()
    while i < n:
        ch = src[i]
        if ch in "\"'":                                     # string literal (copied verbatim)
            j = i + 1
            while j < n and src[j] != ch:
                j += 2 if src[j] == "\\" else 1
            line.append(src[i:j + 1])
            prev, i = ch, j + 1
        elif src.startswith("/*", i):                       # block comment
            j = src.index("*/", i + 2)
            if "\n" in src[i:j]:
                flush()
            i = j + 2
        elif src.startswith("//", i):                       # line comment
            while i < n and src[i] != "\n":
                i += 1
        elif ch == "/":
            words = "".join(line).split()
            last = words[-1] if words else ""
            if prev == "" or prev in _JS_REGEX_PREV or last in _JS_REGEX_WORDS:   # regex literal
                j, cls = i + 1, False
                while j < n:
                    c = src[j]
                    if c == "\\":
                        j += 2
                        continue
                    if c == "[":
                        cls = True
                    elif c == "]":
                        cls = False
                    elif c == "/" and not cls:
                        break
                    j += 1
                j += 1
                while j < n and src[j].isalpha():           # flags
                    j += 1
                line.append(src[i:j])
                prev, i = "x", j
            else:
                line.append(ch)
                prev, i = ch, i + 1
        elif ch == "\n":
            flush()
            i += 1
        else:
            line.append(ch)
            if not ch.isspace():
                prev = ch
            i += 1
    flush()
    return "\n".join(out) + "\n"


_ASSET_V = {}


def asset_v(name):
    """?v=<sha8> cache-busting for the three same-origin assets, from the exact bytes the build writes."""
    if name not in _ASSET_V:
        body = {"app.js": lambda: minify_js(open(APP_SRC, encoding="utf-8").read()), "theme.js": lambda: THEME_JS,
                "styles.css": lambda: open(os.path.join(DOCS, "styles.css"), encoding="utf-8").read()}[name]()
        _ASSET_V[name] = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
    return _ASSET_V[name]


def head(title, desc, url, prefix="", og_title=OG_TITLE, og_type="website", image=f"{BASE_URL}/og-preview.png", extra="", robots=ROBOTS_META,
         rich=False, canonical=True, image_size=SOCIAL_SIZE, early_script=""):
    """Order matters: everything social/agent-relevant comes first and stays inside the first 1.2 KB.
    T3: summary_large_image (the og:image is 1200x628, X's 1.91:1 Website card). T4: error pages pass canonical=False. V4: Inter is self-hosted and
    preloaded (font-src 'self'). b.js is the first-party beacon (docs/b.js, < 2 KB): no cookies, no storage ids, honours DNT."""
    t, d = E(title), E(desc)
    parts = [
        '<!doctype html><html lang="en"><head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{t}</title>",
        f'<meta name="description" content="{d}">',
    ] + [
        f'<meta property="og:type" content="{og_type}">',
        '<meta property="og:site_name" content="Pacta by Fractal Neurons">',
        f'<meta property="og:title" content="{E(og_title)}">',
        f'<meta property="og:description" content="{d}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{image}">',
        f'<meta property="og:image:width" content="{image_size[0]}">',
        f'<meta property="og:image:height" content="{image_size[1]}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{E(og_title)}">',
        f'<meta name="twitter:description" content="{d}">',
        f'<meta name="twitter:image" content="{image}">',
        f'<meta name="twitter:site" content="{X_HANDLE}">',
    ] + ([f'<link rel="canonical" href="{url}">'] if canonical else []) + [
        f'<meta name="robots" content="{robots}">',
    ] + ([extra] if extra else []) + [
        f'<link rel="icon" href="{prefix}favicon.svg" type="image/svg+xml">',
        f'<link rel="icon" href="{prefix}favicon.png" type="image/png" sizes="32x32">',
        '<meta name="referrer" content="strict-origin-when-cross-origin">',
        '<meta name="theme-color" content="#f7f7f5" media="(prefers-color-scheme: light)">',
        '<meta name="theme-color" content="#0a0b0d" media="(prefers-color-scheme: dark)">',
        f'<meta http-equiv="Content-Security-Policy" content="{CSP}">',
    ] + ([f'<script src="{early_script}"></script>'] if early_script else []) + ([   # homepage only (sub-pages keep <body> small; browsers also fetch /favicon.ico and /apple-touch-icon.png from the root)
        f'<link rel="icon" href="{prefix}favicon.ico" sizes="any">',
        f'<link rel="apple-touch-icon" href="{prefix}apple-touch-icon.png">',
        f'<link rel="alternate" type="application/atom+xml" href="{prefix}feed.xml">',
        f'<link rel="alternate" type="application/feed+json" href="{prefix}api/v1/feed.json">',
    ] if rich else []) + [
        f'<link rel="preload" href="{prefix}{FONT_FILE}" as="font" type="font/woff2" crossorigin>',
        f'<link rel="stylesheet" href="{prefix}styles.css?v={asset_v("styles.css")}">',
        f'<link rel="alternate" type="text/markdown" href="{prefix}llms.txt">',
        f'<link rel="alternate" type="text/html" href="{prefix}llms/"' + (' title="llms.txt (HTML mirror)">' if rich else '>'),
        f'<script src="{prefix}theme.js?v={asset_v("theme.js")}"></script>',
        f'<script src="{prefix}app.js?v={asset_v("app.js")}" defer></script>',
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


def topbar(home="", current=None):
    """NavigationMenu (>= 768 px) + hamburger Sheet (< 768 px, R4) + Light / Dark / System DropdownMenu (U2).
    home = "" on the homepage, "../" or "../../" on sub-pages, "/" on 404.html. Bounties live in the footer (M9)."""
    def link(k, lbl):
        cur = ' aria-current="page"' if current == k else ""
        return f'<a href="{nav_href(home, k)}"{cur}>{lbl}</a>'
    links = "".join(link(k, lbl) for k, lbl in NAV)
    req = f"{home}request/"
    items = "".join(
        f'<button data-slot="dropdown-menu-item" type="button" role="menuitemradio" aria-checked="false" data-theme-set="{k}">'
        f'{U.icon(ic)}<span>{lbl}</span>{U.icon("check", "check")}</button>'
        for k, lbl, ic in (("light", "Light", "sun"), ("dark", "Dark", "moon"), ("system", "System", "monitor")))
    theme = (f'<div class="dd" data-theme-menu>'
             + U.button(U.icon("sun", "i-sun") + U.icon("moon", "i-moon") + '<span class="tb-l" data-theme-label>Theme</span>', variant="ghost",
                        size="sm", attrs='aria-haspopup="menu" aria-expanded="false" aria-controls="theme-menu" aria-label="Theme: System" data-theme-btn',
                        cls="theme-btn")
             + f'<div data-slot="dropdown-menu-content" role="menu" id="theme-menu" aria-label="Theme" hidden>'
             f'<p data-slot="dropdown-menu-label">Theme</p>{items}</div></div>')
    gh = U.button(U.icon("github"), href=REPO, variant="ghost", size="icon",
                  attrs='target="_blank" rel="noopener" aria-label="Pacta source on GitHub (opens in a new tab)"', cls="gh")
    xl = U.button(U.icon("x-logo", "i-fill"), href=X_URL, variant="ghost", size="icon",
                  attrs=f'target="_blank" rel="noopener" aria-label="Pacta on X ({X_HANDLE}, opens in a new tab)"', cls="xl")
    # v4.7 W3: the global search (Command dialog built by app.js from scorecards.json + lookup.json on first use)
    search = U.button(U.icon("search") + '<span class="sb-l">Search</span><kbd class="sb-k" data-cmdk-kbd>Ctrl K</kbd>', variant="outline", size="sm",
                      attrs='title="Search protocols, tokens or 0x addresses" aria-haspopup="dialog" aria-keyshortcuts="Control+K Meta+K /" data-cmdk-open',
                      cls="search-btn")
    sheet_theme = ('<div class="sheet-theme" role="group" aria-labelledby="sheet-theme-l"><span id="sheet-theme-l">Theme</span>'
                   + "".join(f'<button data-slot="button" data-variant="outline" data-size="sm" type="button" aria-pressed="false" data-theme-set="{k}" '
                             f'data-theme-sheet>{U.icon(ic)}<span>{lbl}</span></button>'
                             for k, lbl, ic in (("light", "Light", "sun"), ("dark", "Dark", "moon"), ("system", "System", "monitor"))) + '</div>')
    menu = U.button(U.icon("menu"), variant="ghost", size="icon",
                    attrs='aria-label="Open menu" aria-haspopup="dialog" aria-expanded="false" aria-controls="nav-sheet" data-sheet-open',
                    cls="menu-btn")
    sheet_links = "".join(f'<a href="{nav_href(home, k)}">{lbl}</a>' for k, lbl in NAV)
    sheet = (f'<div data-slot="sheet" id="nav-sheet" role="dialog" aria-modal="true" aria-labelledby="nav-sheet-title" hidden>'
             f'<div data-slot="sheet-overlay" data-sheet-close></div><div data-slot="sheet-content">'
             f'<div data-slot="sheet-header"><p data-slot="sheet-title" id="nav-sheet-title">Menu</p>'
             + U.button(U.icon("x"), variant="ghost", size="icon", attrs='aria-label="Close menu" data-sheet-close')
             + f'</div><nav aria-label="Mobile">{sheet_links}<a href="{REPO}" target="_blank" rel="noopener">GitHub</a><a href="{X_URL}" target="_blank" rel="noopener">X ({X_HANDLE})</a></nav>'
             f'{sheet_theme}<div class="sheet-cta">{U.button("Request a dossier", href=req, variant="default", size="lg")}</div></div></div>')
    return (f'<a class="skip" href="#main">Skip to content</a>\n'
            f'<header class="topbar"><div class="wrap">'
            f'<a class="brand" href="{home or "./"}"><img src="{home}favicon.svg" alt="" width="24" height="24">PACTA<small>by Fractal Neurons</small></a>'
            f'<nav data-slot="navigation-menu" class="nav" aria-label="Primary">{links}</nav>'
            f'<div class="tools">{search}{theme}{gh}{xl}'
            + U.button("Request a dossier", href=req, variant="default", size="sm", cls="cta") + menu
            + f'</div></div></header>\n{sheet}')


_STAMP_CACHE = None


def catalog_stamp(idx=None):
    """Deterministic catalog freshness stamp from index.json generated_at (never wall clock)."""
    global _STAMP_CACHE
    if idx is None and _STAMP_CACHE is not None:
        return _STAMP_CACHE
    d = idx if idx is not None else json.load(open(os.path.join(DOCS, "api", "v1", "index.json"), encoding="utf-8"))
    gen = str(d.get("generated_at") or "").replace("T", " ").replace("Z", "")
    ts = gen[:16] + " UTC" if len(gen) >= 16 else gen
    max_sp = max(int(e["sprint"]) for e in d["entries"])
    n_eas = len({e["protocol"] for e in d["entries"]})
    res = f"Catalog updated {ts} · Sprint {max_sp} ({n_eas} Base-EAS verified)"
    if idx is None:
        _STAMP_CACHE = res
    return res


def footer(count_line, reg, home=""):
    """M9: four grouped columns (Product, For agents, Company, Legal); one count line, the same numbers as the hero (M4)."""
    def col(title, links):
        lis = "".join(f'<li><a href="{E(h)}"{" target=" + chr(34) + "_blank" + chr(34) + " rel=" + chr(34) + "noopener" + chr(34) if ext else ""}>{E(l)}</a></li>'
                      for l, h, ext in links)
        return f'<div><h2>{title}</h2><ul>{lis}</ul></div>'
    product = [("Scorecards", f"{home}scorecards/", 0), ("Curator matrix", f"{home}curators/", 0), ("Protocols", f"{home}protocols/", 0), ("Timelock radar", f"{home}radar/", 0),
               ("Pricing", nav_href(home, "#pricing"), 0), ("Instant scan", f"{home}scan/", 0), ("Timelock watchlist", f"{home}webhook/", 0),
               ("Base-EAS attestation", f"{home}seal/", 0), ("Base Mini-App", f"{home}miniapp/", 0), ("For protocols", f"{home}for-protocols/", 0),
               ("Bounties", f"{home}bounties/", 0), ("Leaderboard", f"{home}leaderboard/", 0)]
    agents = [("MCP server", f"{home}mcp/", 0), ("llms.txt", f"{home}llms.txt", 0), ("llms.txt (HTML)", f"{home}llms/", 0),
              ("SKILL.md", f"{home}SKILL.md", 0), ("OpenAPI 3.1", f"{home}api/v1/openapi.json", 0), ("JSON API", f"{home}api/v1/index.json", 0),
              ("Atom feed", f"{home}feed.xml", 0), ("Builder Q&A", COMMUNITY_QA_URL, 1)]
    company = [("About", f"{home}about/", 0), ("Verified addresses", f"{home}about/#official-addresses", 0), ("Methodology", f"{home}methodology/", 0),
               ("Request a dossier", f"{home}request/", 0), ("GitHub", REPO, 1), (f"X ({X_HANDLE})", X_URL, 1), ("Community", COMMUNITY_URL, 1),
               ("Base registry", f"https://basescan.org/address/{reg}", 1)]
    legal = [("Privacy", f"{home}privacy/", 0), ("Terms", f"{home}terms/", 0), ("security.txt", f"{home}.well-known/security.txt", 0)]
    return (f'<footer class="ftr"><div class="wrap"><div class="ftr-grid">'
            f'<div class="ftr-brand"><a class="brand" href="{home or "./"}"><img class="ftr-logo" src="{home}favicon.svg" alt="" width="24" height="24">PACTA</a>'
            f'<p>Independent control-plane scorecards for DeFi. Pacta by Fractal Neurons · pacta.base.eth</p>'
            f'<p class="ftr-stamp" data-catalog-stamp>{E(catalog_stamp())}</p></div>'
            + col("Product", product) + col("For agents", agents) + col("Company", company) + col("Legal", legal)
            + f'</div><div class="ftr-bottom"><span data-count-line>{E(count_line)}</span><span>Read-only onchain analysis. Not investment advice. First-party telemetry stores aggregate counts without raw IPs; X Ads conversion measurement (uwt.js) runs on public pages — see <a href="{home}privacy/">Privacy</a>.</span></div>'
            f'</div></footer>\n<div class="toaster" id="toaster" aria-live="polite" aria-atomic="true"></div>')


def load():
    idx = json.load(open(os.path.join(DOCS, "api", "v1", "index.json")))
    radar = json.load(open(os.path.join(DOCS, "api", "v1", "radar.json")))
    m = idx["summary_metrics"]
    n = len(idx["entries"])
    assert m["records_indexed"] == n == m["parameter_deltas"] + m["protective_deltas"] + m["aligned_baselines"]
    assert m["sprints_completed"] == max(e["sprint"] for e in idx["entries"])
    check_index_chains(idx)
    return idx, radar


# RPC-pinned records (docs/api/v1/rpc-pinned.json): block-pinned read-only observations that are NOT EAS-attested (no sprint
# number, no summary document, no Base EAS UID). They get /protocols/<slug>/ pages next to the index.json Sprint records but
# never touch index.json, its counts or its EAS anchoring.
PINNED_SRC = os.path.join(DOCS, "api", "v1", "rpc-pinned.json")
PINNED_SCHEMA = "pacta.rpc_pinned_records.v1"
CHAINS = {"ethereum": ("Ethereum", "Ethereum Mainnet (chain id 1)", "$ETH_RPC_URL"), "base": ("Base", "Base Mainnet (chain id 8453)", "$BASE_RPC_URL")}
CHAIN_IDS = {"ethereum": 1, "base": 8453}
EXPLORERS = {"ethereum": ("Etherscan", "https://etherscan.io"), "base": ("Basescan", "https://basescan.org")}


def chain_of(e):
    """A record's chain: index.json records without a chain field are Ethereum Mainnet (Sprints 1-16)."""
    return e.get("chain", "ethereum")


def check_index_chains(idx):
    """index.json records may carry chain + rpc_env_var (both or neither); the pair must be one of CHAINS."""
    for e in idx["entries"]:
        assert ("chain" in e) == ("rpc_env_var" in e), e["id"]
        assert chain_of(e) in CHAINS and e.get("rpc_env_var", "$ETH_RPC_URL") == CHAINS[chain_of(e)][2], e["id"]


def record_chains(idx):
    return sorted({chain_of(e) for e in idx["entries"]}, key=list(CHAINS).index)


def explorer_link(e, kind="block"):
    """Block (or target address) on the record's own chain explorer."""
    name, url = EXPLORERS[chain_of(e)]
    ref = e["block_number"] if kind == "block" else e["target_contract"]
    return f'<a href="{url}/{"block" if kind == "block" else "address"}/{E(str(ref))}" target="_blank" rel="noopener">{name}{EXT}</a>'


# v4.6: radar.json is multi-chain. An item's chain_id (else the file's) picks its finalized pin (refreshed_at for Ethereum,
# refreshed_at_base for Base) and its explorer: Etherscan for chain id 1, Basescan for chain id 8453 (never Etherscan for Base).
RADAR_CHAINS = {v: k for k, v in CHAIN_IDS.items()}
PIN_WORD = {"ethereum": "L1", "base": "Base"}      # "Executed on L1" / "Unexecuted on Base at Finalized Block #…"
PIN_KEY = {"ethereum": "refreshed_at", "base": "refreshed_at_base"}


def radar_chain(it, radar):
    cid = it.get("chain_id", radar.get("chain_id", 1))
    assert cid in RADAR_CHAINS, (it.get("protocol"), cid)
    return RADAR_CHAINS[cid]


def radar_pin(it, radar):
    """The finalized block an item was read at, on its own chain."""
    return radar[PIN_KEY[radar_chain(it, radar)]]


def radar_pins(radar):
    """[(chain, pin)] for every chain on the radar, Ethereum first."""
    chains = {radar_chain(it, radar) for it in radar["items"]} | {"ethereum"}
    return [(ch, radar[PIN_KEY[ch]]) for ch in CHAINS if ch in chains]


def xlink(chain, kind, value, text):
    """kind = address | tx | block on the chain's own explorer."""
    return f'<a href="{EXPLORERS[chain][1]}/{kind}/{E(str(value))}" target="_blank" rel="noopener">{text}{EXT}</a>'


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


CONTROLLER_FACTS_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graph_controller_facts.json")


def protocol_addresses(slug, es):
    """v4.5 (G-P1-3): every 0x address a protocol's records name (targets, controllers, delay sources, Safes, ProxyAdmins,
    timelocks and tokens in the observed and documented evidence), its lookup aliases / continuity contracts and the hero
    example's live-check target, lowercased, so pasting any of them into a search or the /request/ combobox finds the protocol."""
    out = set()
    for e in es:
        for k in ("target_contract", "paired_contract", "controller_address", "upstream_controller", "onchain_observed", "documented_reference"):
            v_ = e.get(k)
            out.update(a.lower() for a in LK.ADDR_RE.findall(v_ if isinstance(v_, str) else ""))
        src = e.get("observed_delay_source") or {}
        if isinstance(src.get("contract"), str):
            out.add(src["contract"].lower())
    out.update(a.lower() for a in LK.ADDRESS_ALIASES.get(slug, []))
    keep = LK.CONVERTED_CONTINUITY.get(slug) or {}
    out.update(keep[k].lower() for k in ("primaryContract", "controllerAddress") if isinstance(keep.get(k), str))
    if slug in LIVE_CHECK_TARGET:
        out.add(LIVE_CHECK_TARGET[slug][1].lower())
    return {a for a in out if LK.ADDR_RE.fullmatch(a)}


TVL_SRC = os.path.join(ROOT, "data", "defillama-protocol-tvls.json")
_TVL_BY_SLUG = None


def load_tvl_map():
    global _TVL_BY_SLUG
    if _TVL_BY_SLUG is None:
        raw = json.load(open(TVL_SRC, encoding="utf-8")) if os.path.exists(TVL_SRC) else {"protocols": []}
        _TVL_BY_SLUG = {
            p["pacta_slug"]: round(float(p["total_tvl_usd"]))
            for p in raw.get("protocols", [])
            if p.get("pacta_slug") and isinstance(p.get("total_tvl_usd"), (int, float)) and p["total_tvl_usd"] > 0
        }
    return _TVL_BY_SLUG


def fmt_tvl(v):
    if not isinstance(v, (int, float)) or v <= 0:
        return ""
    if v >= 1e9:
        return f"${v / 1e9:.2f}B TVL" if v < 10e9 else f"${v / 1e9:.1f}B TVL"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M TVL" if v < 100e6 else f"${round(v / 1e6):,}M TVL"
    if v >= 1e3:
        return f"${round(v / 1e3):,}K TVL"
    return f"${round(v):,} TVL"


def scorecards(idx, pinned=None, sp=None):
    """One scorecard per published protocol (grade, 5-factor rosette with evidence, key finding, chains, baskets), derived only
    from the published records and controller facts (tools/scorecard.py). Ordered by name; consumed by the homepage scorecard,
    /protocols/<slug>/ and /api/v1/scorecards.json."""
    import scorecard as SC
    pinned = load_pinned() if pinned is None else pinned
    sp = site_protocols(idx, pinned) if sp is None else sp
    cf = json.load(open(CONTROLLER_FACTS_SRC, encoding="utf-8"))["contracts"]
    tvls = load_tvl_map()
    out = []
    for name, v in sp.items():
        es, eas = v["entries"], not v["pinned"]
        chains = sorted({chain_of(e) for e in es})
        addrs = set()
        for e in es:
            ch = chain_of(e)
            addrs.add((ch, e["target_contract"].lower()))
            src = e.get("observed_delay_source") or {}
            if src.get("contract"):
                addrs.add((ch, src["contract"].lower()))
            for k in ("controller_address", "upstream_controller"):
                if e.get(k):
                    addrs.add((ch, e[k].lower()))
        facts = [dict(cf[f"{c}:{a[2:]}"], address=a) for c, a in sorted(addrs) if f"{c}:{a[2:]}" in cf]
        cls = [e["classification"] for e in es]
        recon = [e for e in es if e.get("reconciledFrom")]
        g = SC.grade(cls, eas, bool(recon))
        fs = SC.factors(es, eas, g, facts)
        wd = CD.what_differs(es) if eas else None
        if wd and wd.get("changed"):
            c0 = wd["changed"][0]
            finding = f'{c0["parameter"]}: docs say {c0["documented"]} · chain says {c0["observed"]}'
        else:
            lead = next((e for e in es if e["classification"] == "parameter_delta"), None) or next(
                (e for e in es if e["classification"] == "protective_delta"), None) or es[0]
            finding = lead["surface"]
        cats = {e.get("category", "") for e in es}
        lead = next((e for e in es if e["classification"] == "parameter_delta"), es[0])
        probe = {k: lead.get(k) for k in ("id", "chain", "target_contract", "target_label", "check_type", "selector_or_slot", "call_signature",
                                           "call_args", "repro_calldata", "block_number", "block_hash", "rpc_env_var", "extra_calls")}
        probe["chain"] = chain_of(lead)
        probe["rpc_env_var"] = CHAINS[probe["chain"]][2]
        probe["call_args"] = probe["call_args"] or []
        probe["extra_calls"] = probe["extra_calls"] or []
        search = " ".join([name, v["slug"], es[0].get("category", "")] + list(LK.TOKENS.get(v["slug"], []))
                          + sorted(protocol_addresses(v["slug"], es))).lower()
        _SHORT_SEARCH[v["slug"]] = " ".join([name, v["slug"], es[0].get("category", "")] + list(LK.TOKENS.get(v["slug"], []))
                                            + sorted({e["target_contract"] for e in es})).lower()
        ev_e = next((e for e in es if wd and wd.get("changed") and e["id"] == wd["changed"][0]["recordId"]), None) or lead
        assert v["slug"] in SS.SUMMARY and not SS.problems(SS.SUMMARY[v["slug"]]), v["slug"]
        out.append({"slug": v["slug"], "name": name, "grade": g, "gradeLabel": SC.GRADES[g][0], "reconciled": bool(recon),
                    "summary_short": SS.SUMMARY[v["slug"]],
                    "tvlUsd": tvls.get(v["slug"]),
                    "evidence": {"recordId": ev_e["id"], "surface": ev_e["surface"], "documented": ev_e["documented_reference"],
                                 "observed": ev_e["onchain_observed"]},
                    "reconciledFrom": [e["reconciledFrom"] for e in recon],
                    "reconciledTo": [{"blockNumber": int(e["block_number"]), "easUid": e.get("base_eas_uid"),
                                      "docsCommit": e.get("docsCommit") or e.get("docs_commit"),
                                      "docsSnapshot": e.get("docsSnapshot") or e.get("docs_snapshot") or e.get("summary_doc"),
                                      "docsSha256": e.get("summary_sha256")} for e in recon],
                    "easAttested": eas, "chains": chains,
                    "category": es[0].get("category", ""), "baskets": sorted({b for c in cats for b in baskets_of(c, chains)}),
                    "records": len(es), "deltas": cls.count("parameter_delta"), "finding": finding,
                    "pinnedBlock": max(int(e["block_number"]) for e in es),
                    "factors": fs, "rosetteAria": SC.aria(fs, name), "url": f"{BASE_URL}/protocols/{v['slug']}/",
                    "probe": probe, "search": search})
    return out


def scorecards_json(cards):
    import scorecard as SC
    totals = {g: sum(c["grade"] == g for c in cards) for g in SC.GRADES}
    coverage = {k: sum(next(f for f in c["factors"] if f["key"] == k)["state"] not in ("n", "u") for c in cards) for k, _ in SC.FACTORS}
    doc = {"schema": "pacta.scorecards.v1",
           "description": "One canonical grade per published protocol (DELTA / PROTECTIVE / ALIGNED / OBSERVED) and a 5-factor control-plane "
                          "rosette derived deterministically from Pacta's published records (index.json, rpc-pinned.json) and controller facts. "
                          "A factor the published evidence does not decide is 'n' (not determined); docs-vs-chain parity is 'u' (uncompared) "
                          "for every RPC-observed protocol. States: g strong, b moderate, a weak, n not determined, u uncompared.",
           "grades": {g: {"label": SC.GRADES[g][0], "meaning": SC.GRADES[g][1], "protocols": totals[g]} for g in SC.GRADES},
           "factors": [{"key": k, "label": lbl} for k, lbl in SC.FACTORS], "factorCoverage": coverage,
           "protocols": cards}
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


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
            "delta": m["parameter_deltas"], "protect": m["protective_deltas"], "aligned": m["aligned_baselines"],
            "chains": " + ".join(CHAINS[ch][1].split(" (")[0] for ch in record_chains(idx))}


def coverage_line(idx, pinned=None):
    """The site-wide count line (footer, llms.txt): one noun per number, the same numbers as the hero and the filters (M4)."""
    s = site_numbers(idx, pinned=pinned)
    return (f'{s["protocols"]} protocols ({s["eas_protocols"]} Base-EAS attested + {s["observed"]} RPC-observed) · '
            f'{s["checks"]} attested checks across {s["batches"]} Base EAS batch attestations')


def org_ld_script():
    return '<script type="application/ld+json">' + json.dumps(ORG_LD, ensure_ascii=False, sort_keys=True).replace("</", "<\\/") + "</script>"


def app_ld_script(idx):
    """SoftwareApplication JSON-LD (homepage): the free pre-execution API / MCP server, priced $0, with the catalog size."""
    c = counts(idx)
    ld = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Pacta pre-execution contract & governance safety API",
          "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (HTTP API, remote MCP)", "url": f"{BASE_URL}/",
          "description": f"Free pre-execution checks for AI agents: who can upgrade, pause or change a contract, how fast, with "
                         f"{len(site_protocols(idx))} block-pinned protocol records ({c['records']} attested checks).",
          "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
          "publisher": {"@type": "Organization", "name": "Pacta by Fractal Neurons", "url": f"{BASE_URL}/"},
          "softwareHelp": f"{BASE_URL}/mcp/", "sameAs": [REPO, X_URL]}
    return '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False, sort_keys=True).replace("</", "<\\/") + "</script>"


def anchoring_text(c):
    """One sentence on Base anchoring, derived from the data (never hand-edited)."""
    t = f'{c["eas_n"]} Base EAS sprint attestations cover Sprints {c["eas_from"]}–{c["eas_to"]}'
    if c["pending"]:
        t += f'; Sprints {c["pending"]} are pinned by block hash and SHA-256 summary digest until batch-attested'
    if c["later"]:
        t += f'; Sprint{"s" if "–" in c["later"] else ""} {c["later"]} records join the public index after review'
    return t + "."


CLASS_LABEL = {"parameter_delta": ("delta", "Docs differ"), "protective_delta": ("protect", "Protective"),
               "aligned_baseline": ("aligned", "Aligned"),
               # RPC-pinned records: on-chain control plane pinned at an archive block; documentation comparison not assessed
               "rpc_observed": ("observed", "Observed")}
CLASS_DEFINITIONS = ("parameter_delta (on-chain differs from docs), protective_delta (a change that strengthens controls), aligned_baseline "
                     "(on-chain matches docs), rpc_observed (on-chain control plane pinned at an archive block height over JSON-RPC; "
                     "documentation parameter comparison unassessed)")


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


def term(cmd, title="Reproduce on any archive node", what=None):
    """Code block with a uniquely named Copy button (A4) and wrapped lines (R5)."""
    aria = what or f"Copy command: {title}"
    return (f'<div class="term"><div class="term-h"><span>{E(title)}</span>'
            f'<button class="copy" data-slot="button" data-variant="ghost" data-size="sm" type="button" data-copy-term '
            f'aria-label="{E(aria)}">{U.icon("copy")}<span>Copy</span></button></div>'
            f'<pre>{E(cmd)}</pre></div>')


def proof_html(e):
    if e["base_eas_uid"]:
        return (f'<a href="https://base.easscan.org/attestation/view/{E(e["base_eas_uid"])}" target="_blank" rel="noopener">'
                f'Base EAS attestation {E(short(e["base_eas_uid"]))}{EXT}</a>')
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


def utc_iso(ts):
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def what_differs_html(entries, compact=False, seal_cta=False):
    """Visitor review P1 (understanding): the "What differs" callout on every page with a flagged record: discrepant parameters
    first, matched ones below. V8: each value is a whole-word excerpt with the full verbatim record text one click away.
    V7: amber only when a looser-than-documented (parameter_delta) record is present; protective-only pages use the info palette."""
    wd = CD.what_differs(entries)
    if not wd:
        return ""
    by = {e["id"]: e for e in entries}

    def val(full, short_v):
        """(visible excerpt, full text or "" when the excerpt already is the whole text)"""
        if not short_v.endswith("…") and len(short_v) <= 60:
            return E(short_v), ""
        ex = clean_excerpt(full or short_v)
        norm = re.sub(r"\s+", " ", (full or "").strip())
        return E(ex), ("" if not full or ex == norm else full)

    items = []
    for c in wd["changed"]:
        e = by.get(c["recordId"], {})
        o_ex, o_full = val(e.get("onchain_observed", ""), c["observed"])
        d_ex, d_full = val(e.get("documented_reference", ""), c["documented"])
        more = "".join(f'<details class="ev-full"><summary>{lbl}</summary><p>{prose(t)}</p></details>'
                       for lbl, t in (("Show the full onchain evidence", o_full), ("Show the full documented text", d_full)) if t)
        items.append(f'<li data-wd-changed><b>{E(c["parameter"])}</b>: <span class="obs">{o_ex}</span> observed vs '
                     f'<span class="doc">{d_ex}</span> documented{more}</li>')
    mt = "".join(f'<li data-wd-matched>{E(m["parameter"])}: {E(m["value"])}</li>' for m in wd["matched"])
    tag = "div" if compact else "section"
    protective = all(c.get("classification") == "protective_delta" for c in wd["changed"])
    wd_cta = (f'<p class="wd-cta">Protocol maintainer and merged a fix? <a href="#seal-cta" data-cta="seal_wd">Submit for free 7-day re-verification{ARR}</a></p>'
              if seal_cta and not protective else "")
    return (f'<{tag} class="{"memo-sec " if not compact else ""}whatdiffers{" protective" if protective else ""}" data-what-differs><h2 class="wd-h">What differs</h2>'
            f'<p class="wd-l">Changed / discrepant</p><ul class="wd-changed">{"".join(items)}</ul>'
            + (f'<p class="wd-l">Matched</p><ul class="wd-matched">{mt}</ul>' if mt else "") + wd_cta + f'</{tag}>\n')


def editorial_box():
    """The editorial-independence firewall, shown before any paid issuer service (two sentences, Alert)."""
    return (f'<aside class="editorial" data-editorial-independence>'
            + U.alert("Editorial independence", f'{E(EDITORIAL_FIREWALL)} {E(EDITORIAL_INDEPENDENCE)}', icon_name="scale")
            + '</aside>\n')

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
    rows += [("Pinned block", f'{"" if chain_of(e) == "ethereum" else E(CHAINS[chain_of(e)][0]) + " "}<span class="num">#{e["block_number"]:,}</span> · Sprint {e["sprint"]} '
                              f'<span class="badge final">Scanner-pinned (L1 finalized)</span>'),
             ("Canonical block hash", hexref(e["block_hash"], 8, 6)),
             ("Proof", proof_html(e)),
             ("Summary", f'<a href="{REPO}/blob/main/{E(e["summary_doc"])}" target="_blank" rel="noopener">{E(os.path.basename(e["summary_doc"]))}{EXT}</a>'
                         f' · SHA-256 {hexref(e["summary_sha256"], 8, 4)}')]
    kv = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    return (f'<div class="sheet-h"><h3>{E(e["protocol"])}</h3>{badge(e["classification"])}</div>'
            f'<p class="sheet-sub">{E(e["surface"])}</p>'
            + what_differs_html([e], compact=True) +
            f'<dl class="kv">{kv}</dl>'
            f'<p class="obs-text">{prose(e["onchain_observed"])}</p>'
            + term(cast_line(e)))


HEX64 = re.compile(r"0x[0-9a-fA-F]{64}(?![0-9a-fA-F])|(?<![0-9A-Za-z])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
ADDR40 = re.compile(r"0x[0-9a-fA-F]{40}")


def prose(text):
    """Escape record prose for display; 32-byte hashes (tx / op / block ids) are shortened with the full value in a
    tooltip, so a 66-character token can never force a mid-hash wrap. 20-byte addresses stay complete (readers copy
    them) in a no-wrap span sized to fit the column. The JSON feed keeps the full text."""
    out, last = [], 0
    for m in HEX64.finditer(text):
        out.append(E(text[last:m.start()]))
        if len(m.group(0)) == 42:
            out.append(f'<span class="hx-a">{m.group(0)}</span>')
        else:
            out.append(f'<span class="hx" title="{m.group(0)}">{E(short(m.group(0), 8, 6))}</span>')
        last = m.end()
    out.append(E(text[last:]))
    return "".join(out)


def sorted_entries(idx):
    return sorted(idx["entries"], key=lambda e: (-e["sprint"], e["protocol"].lower()))


# Curator baskets: key -> (label, category regex (case-insensitive) or None, chain or None). A record / protocol joins every
# basket whose category regex matches or whose chain matches. Used by /protocols/ and the homepage inspector (app.js reads the
# same rules from the pills' data-basket-re / data-basket-chain attributes).
BASKETS = [("stable_rwa", "Stablecoins & RWA", r"stable|rwa|dollar|credit|treasur|cdp|reinsur|borrowing", None),
           ("eth_lst_lrt", "ETH LST / LRT", r"staking|restak|\blst\b|\blrt\b|validator", None),
           ("lending_vaults", "Curated Lending & Vaults", r"lend|vault|curat|yield|allocator|market", None),
           ("base", "Base Ecosystem", None, "base")]


def baskets_of(category, chains):
    out = []
    for k, _, rx, ch in BASKETS:
        if (rx and re.search(rx, category or "", re.I)) or (ch and ch in chains):
            out.append(k)
    return out


def basket_pills(attr="data-basket", rules=False):
    """All + the four baskets as a pill group; rules=True also carries the matching rule (for client-side hydrated records)."""
    pills = [f'<button type="button" {attr}="all" aria-pressed="true">All</button>']
    for k, lbl, rx, ch in BASKETS:
        extra = ((f' data-basket-re="{E(rx)}"' if rx else "") + (f' data-basket-chain="{ch}"' if ch else "")) if rules else ""
        pills.append(f'<button type="button" {attr}="{k}" aria-pressed="false"{extra}>{E(lbl)}</button>')
    return f'<div class="seg basket" role="group" aria-label="Curator baskets"><span class="seg-l">Basket</span>{"".join(pills)}</div>'


SAMPLE_SIZE = 12


def curated_sample(idx, n=SAMPLE_SIZE):
    """Deterministic flagship sample for the static homepage: the inspector default (Ethena) and Stader first, then round-robin
    over (chain, classification) buckets in sorted_entries order (one record per protocol), so Ethereum + Base parameter /
    protective deltas and aligned baselines are all represented. Returned in sorted_entries order."""
    ents = sorted_entries(idx)
    pick = [next(e for e in ents if e["protocol"].startswith("Ethena")), next(e for e in ents if e["protocol"].startswith("Stader"))]
    buckets = [(ch, cl) for cl in ("parameter_delta", "protective_delta", "aligned_baseline") for ch in ("ethereum", "base")]
    while len(pick) < n:
        added = False
        for ch, cl in buckets:
            if len(pick) >= n:
                break
            names = {x["protocol"] for x in pick}
            nxt = next((e for e in ents if chain_of(e) == ch and e["classification"] == cl and e["protocol"] not in names), None)
            if nxt is not None:
                pick.append(nxt)
                added = True
        if not added:
            break
    ids = {e["id"] for e in pick}
    return [e for e in ents if e["id"] in ids]


def inspector(idx, c):
    ents = curated_sample(idx)
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
{basket_pills("data-insp-basket", rules=True)}
<div class="bench-filter" role="group" aria-label="Filter by classification"><button type="button" data-f="all" aria-pressed="true">All</button><button type="button" data-f="parameter_delta" aria-pressed="false">Docs differ</button><button type="button" data-f="protective_delta" aria-pressed="false">Protective</button><button type="button" data-f="aligned_baseline" aria-pressed="false">Aligned</button></div></div>
<ul class="bench-list" id="insp-list" data-sample="{len(ents)}">{items}</ul>
<div class="bench-count"><span id="insp-count">{len(ents)} of {c["records"]} records (curated sample)</span> <button type="button" class="linkish" data-insp-all>Show all {c["records"]} records</button></div>
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
    content = content.replace("</header>", "</header>\n" + meta, 1) + clearance_callout(b["asset"], b["slug"], b["forum"]["url"])
    c = counts(idx)
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    title = f'{b["asset"]}: onboarding verification brief'
    body = f"""<body>
{topbar("../../")}
<main id="main" class="memo-wrap">
<div class="crumbs"><a href="../../">Pacta</a> / <a href="../../#onboarding">Onboarding briefs</a> / {E(b["slug"])}</div>
<article class="memo">
{content}</article>
<div class="memo-foot"><span>Read-only on-chain analysis. Not investment advice. Exploit-sensitive vulnerabilities are never published here; they go through Immunefi or Cantina bounty programmes.</span><a href="../../request/?tier=clearance">Request a suite dossier · {E(CLEARANCE_PRICE)}{ARR}</a></div>
</main>
{footer(count_line, reg, "../../")}
</body></html>
"""
    return head(title, OR.summary(b), f"{BASE_URL}/briefs/{b['slug']}/", prefix="../../", og_title=title, og_type="article") + "\n" + body


# ---- timelock operation state (radar.json, read at a finalized block) ----
# executed: isOperationDone; ready: the delay has elapsed at the finalized block and the op is still unexecuted
# (execute() is callable); pending: queued, delay not elapsed. Never "executed" while done is false.
LIVE_TIMELOCKS_URL = f"{API}/v1/briefs/live-timelocks?caller_agent=pacta-wtf-radar&requester_role=individual_user&caller_purpose=governance_monitoring"
OP_STATE_LABEL = {"executed": "EXECUTED", "ready": "READY · EXECUTABLE NOW", "pending": "PENDING", "unknown": "CANCELLED OR UNKNOWN", "mixed": "MIXED"}


def op_state(o):
    if o.get("done"):
        return "executed"
    if o.get("ready"):
        return "ready"
    return "pending" if o.get("pending") else "unknown"


def item_state(item):
    s = {op_state(o) for o in item["operations"]}
    return s.pop() if len(s) == 1 else "mixed"


def state_badge(state, ops):
    """Status badge; data-ops lets app.js re-check these operations live (textContent / class only)."""
    return (f'<span class="opstate {state}" data-opstate="{state}" data-ops="{" ".join(o["op_id"] for o in ops)}">'
            f'{E(OP_STATE_LABEL[state])}</span>')


def delay_text(seconds):
    return f"{seconds // 3600}h" if seconds % 3600 == 0 else secs(seconds)


def post_eta_banner(item, r, chain="ethereum"):
    """Prominent post-ETA status at the top of a brief once any operation's delay has elapsed (or it was executed).
    v4.6: r is the item's own chain pin; Base items read "Executed on Base" / "Unexecuted on Base at Finalized Block #…"."""
    st = item_state(item)
    if st not in ("ready", "executed", "mixed"):
        return ""
    n = len(item["operations"])
    blk = f'Finalized Block #{r["block_number"]:,}'
    if st == "executed":
        clause = f'{delay_text(item["min_delay_seconds"])} Delay Elapsed · Executed on {PIN_WORD[chain]} by {blk}'
        detail = f'isOperationDone = true for {"the operation" if n == 1 else f"all {n} operations"}'
    elif st == "ready":
        clause = f'{delay_text(item["min_delay_seconds"])} Delay Elapsed · Unexecuted on {PIN_WORD[chain]} at {blk}'
        detail = (f'isOperationPending = true and isOperationDone = false for {"the operation" if n == 1 else f"both operations" if n == 2 else f"all {n} operations"}: '
                  f'the timelock delay has elapsed, so execute() is callable, but {"it has" if n == 1 else "they have"} not been executed')
    else:
        clause = f'Operations differ · read at {blk}'
        detail = "; ".join(f'{short(o["op_id"], 6, 4)}: {OP_STATE_LABEL[op_state(o)]}' for o in item["operations"])
    return (f'<div class="poststatus {st}" id="post-eta-status" data-live-timelocks="{E(LIVE_TIMELOCKS_URL)}">'
            f'<span class="label">Post-ETA Live Status</span>'
            f'<p class="ps-head"><b>Post-ETA Verification:</b> {state_badge(st, item["operations"])} <span class="ps-clause">({E(clause)})</span></p>'
            f'<p class="s">{E(detail)}. Read at {"" if chain == "ethereum" else CHAINS[chain][0] + " "}finalized block #{r["block_number"]:,} ({E(r["block_time_utc"])}) on '
            f'{r.get("rpcs_cross_checked", 2)} independent RPCs. <span class="live-line" data-live-line></span></p></div>\n')


def radar_counts_text(radar):
    """M4: the radar header counts the rows the table shows (one per radar.json item, by state). N5 (v4.3): executed rows are
    counted by their operations, so the line never reads as a total: "1 ready · 1 pending · Executed (2 ops)". app.js re-derives
    the same text after a live re-check (radarCounts / radarPart)."""
    by, ops = {}, {}
    for it in radar["items"]:
        st = item_state(it)
        by[st] = by.get(st, 0) + 1
        ops[st] = ops.get(st, 0) + len(it["operations"])
    word = lambda n: f'{n} op' + ("" if n == 1 else "s")
    parts = []
    for st in RADAR_STATE_ORDER:
        if by.get(st):
            parts.append(f'Executed ({word(ops[st])})' if st == "executed" else
                         f'{by[st]} {RADAR_STATE_WORD[st]}' + (f' ({word(ops[st])})' if ops[st] != by[st] else ""))
    return " · ".join(parts)


def radar_section(radar, prefix="", full=False):
    """T1: with JavaScript the state badges start as skeletons and appear once the live re-check settles (or fails), so a label never
    changes after first paint; without JavaScript the pinned snapshot shows. R3: cards below 640 px. A5: caption.
    v4.6: multi-chain. Every row links its timelock on its own chain's explorer (Etherscan for chain id 1, Basescan for 8453) and a
    subtle "Base" tag marks Base rows; the provenance names each chain's finalized block. The homepage (full=False) keeps rows compact
    for the page budget (no summary line, no copy button); /radar/ adds the summary, copy buttons, per-operation labels and the
    timelock list."""
    r = radar["refreshed_at"]
    pins = radar_pins(radar)
    rows = []
    for it in radar["items"]:
        ch, pin = radar_chain(it, radar), radar_pin(it, radar)
        n = len(it["operations"])
        st = item_state(it)
        labelled = full and n > 1 and all(o.get("label") for o in it["operations"])
        ops = ", ".join(f'<span class="hx" title="{o["op_id"]}">{short(o["op_id"], 6, 4)}</span>' for o in it["operations"])
        cue = "" if ch == "ethereum" else f'<span class="chain-tag">{E(CHAINS[ch][0])}</span> '
        tl = xlink(ch, "address", it["timelock"], f'<span class="addr">{E(short(it["timelock"]))}</span>') + (copy_btn(it["timelock"]) if full else "")
        labels = ('<ul class="oplabels">' + "".join(f'<li><span class="hx" title="{o["op_id"]}">{short(o["op_id"], 6, 4)}</span> {E(o["label"])}</li>'
                                                    for o in it["operations"]) + '</ul>') if labelled else ""
        where = "" if ch == "ethereum" else f"{CHAINS[ch][0]} "
        tl_kind = it.get("timelock_kind", "oz")
        op_etas = ",".join(str(o.get("eta") or 0) for o in it["operations"])
        p_name = f'<b>{E(it["protocol"])}</b>'
        p_cell = ident_cell(it["protocol_slug"], p_name, prefix) if it.get("protocol_slug") else p_name
        rows.append(
            f'<tr data-radar-row="{st}" data-timelock="{it["timelock"]}" data-chain="{ch}" data-tl-kind="{E(tl_kind)}" data-op-etas="{op_etas}"{" class=" + chr(34) + "is-executed" + chr(34) if st == "executed" else ""}>'
            f'<td>{p_cell}<span class="sub" data-skel>{state_badge(st, it["operations"])}</span></td>'
            f'<td data-label="Queued operation"><span class="op">{E(it["title"])}</span>' + (f'<span class="sub">{E(it["summary"])}</span>' if full else "") +
            f'<span class="meta">{cue}Timelock {tl} · '
            + (f'Operation{"s" if n > 1 else ""} {ops}' if full and not labelled else f'{n} operation{"s" if n > 1 else ""}') + f'</span>{labels}</td>'
            + (f'<td class="nowrap num hide-m" data-label="Delay">{secs(it["min_delay_seconds"])}</td>' if full else "")
            + (f'<td data-label="Execution window"><span class="countdown" data-eta="{it["eta"]}">ETA {E(utc(it["eta"]))}</span><span class="sub">{E(utc(it["eta"]))}'
               + ("" if full else f' · {secs(it["min_delay_seconds"])} delay') + '</span></td>'
               if it.get("eta") else
               f'<td data-label="Execution window"><span class="sub">Executed: isOperationDone = true at {where}block #{pin["block_number"]:,}</span></td>') +
            f'<td class="r nowrap" data-label="Brief"><a href="{prefix}{E(it["brief"])}">Read brief{ARR}</a></td></tr>')
    seen, tls = set(), ""
    for it in radar["items"] if full else []:
        ch = radar_chain(it, radar)
        if (ch, it["timelock"].lower()) not in seen:
            seen.add((ch, it["timelock"].lower()))
            tls += " · " + xlink(ch, "address", it["timelock"], f'{E(it["protocol"])} timelock')
    multi = len(pins) > 1
    blocks = " and ".join(f'{CHAINS[ch][0] + " " if multi else ""}finalized block {xlink(ch, "block", p_["block_number"], "#" + format(p_["block_number"], ","))}'
                          for ch, p_ in pins)
    tl_items = "".join(f"<li>{t_}</li>" for t_ in tls.split(" · ") if t_)
    live_note = (f'<div class="radar-tls" data-radar-live><span class="radar-tls-l">Timelock contracts</span><ul>{tl_items}</ul></div>' if full else
                 f'<p class="radar-live" data-radar-live><b>Block-pinned timelock queue — auto-rechecked via RPC in your browser</b>: read at {blocks}{tls}.</p>')
    pill = f'Scanner-pinned ({" + ".join(PIN_WORD[ch] for ch, _ in pins)} finalized)'
    prov_more = "".join(f' {CHAINS[ch][0]} rows: finalized block #{p_["block_number"]:,} ({E(p_["block_time_utc"])}), also cross-checked.'
                        for ch, p_ in pins[1:])
    explain = ("" if not full else
               f'<div class="cases" style="margin-top:24px">'
               + U.card(U.card_header("States", "") + '<div data-slot="card-content"><dl class="deflist">'
                        '<div><dt>Pending</dt><dd>Queued; the timelock delay has not elapsed.</dd></div>'
                        '<div><dt>Ready · executable now</dt><dd>The delay has elapsed and the operation is still unexecuted: anyone with the executor role can run it.</dd></div>'
                        '<div><dt>Executed</dt><dd>isOperationDone is true at the block read.</dd></div></dl></div>')
               + U.card(U.card_header("How the radar reads the chain", "") + '<div data-slot="card-content"><p class="s">State and ETAs are read at a finalized '
                        + (f'block on each item\'s own chain ({", ".join(CHAINS[ch][1].split(" (")[0] for ch, _ in pins)})' if multi else 'Ethereum block')
                        + f' on {r.get("rpcs_cross_checked", 2)} independent RPCs, then re-checked live in your browser through the free '
                        '/v1/briefs/live-timelocks endpoint. Countdowns run locally from each onchain ETA.</p></div>') + '</div>')
    return f"""<section class="sec" id="radar" data-live-timelocks="{E(LIVE_TIMELOCKS_URL)}"><div class="wrap">
<div class="sec-head"><{"h1" if full else "h2"}>Queued timelock radar</{"h1" if full else "h2"}><p class="aside">Governance changes waiting in onchain timelocks, and when each one can execute.</p></div>
<div class="radar-head"><span class="radar-counts" data-radar-counts>{E(radar_counts_text(radar))}</span><span class="live-status" data-live-status><span class="spinner" aria-hidden="true" hidden></span><span data-live-status-text>Pinned snapshot</span></span><a href="{prefix}feed.xml" data-feed-subscribe>Subscribe (RSS / JSON Feed)</a></div>
{livebar_html(radar)}
{live_note}
<div class="tbl-wrap"><table class="tbl radar"><caption class="sr-only">Queued timelock operations: protocol and state, operation, {"minimum delay, execution window" if full else "execution window with minimum delay"} and brief.</caption><thead><tr><th scope="col">Protocol</th><th scope="col">Queued operation</th>{'<th scope="col" class="hide-m">Delay</th>' if full else ""}<th scope="col">Execution window</th><th scope="col" class="r">Brief</th></tr></thead>
<tbody data-live-pending>{"".join(rows)}</tbody></table></div>
<div class="prov"><span class="badge final" data-prov-pill>{E(pill)}</span><span data-snapshot-pinned>Snapshot pinned at {E(r["block_time_utc"])}<span class="obs-age" data-age="{r["block_timestamp"]}"></span></span><span data-last-recheck>Last live re-check: not yet</span>{U.button("Refresh", variant="outline", size="sm", attrs="data-radar-refresh")}<span class="snap-fallback" data-snapshot-fallback>Showing pinned historical snapshot</span><span>Pinned snapshot · observed {E(r["block_time_utc"])} (Mainnet finalized block #{r["block_number"]:,}) on {r.get("rpcs_cross_checked", 2)} independent RPCs.{prov_more} Ready means the delay has elapsed and the operation is still unexecuted.</span><span class="live-line" data-live-line></span></div>
{explain}</div></section>"""


def pricing_section(idx, home=""):
    """#pricing: the same tiers on / and /request/ (M4); Continuous Control-Plane Monitoring never implies a paid status (M5)."""
    return f"""<section class="sec" id="pricing"><div class="wrap">
<div class="sec-head"><h2>Pricing</h2><p class="aside">Every scorecard, wallet scan, the API and the MCP server are free. Fund a verification pool or watch your positions for alerts when contract controls change.</p></div>
{U.alert(EDITORIAL_FIREWALL, E(EDITORIAL_INDEPENDENCE), icon_name="scale", cls="editorial-note", attrs="data-editorial")}
{pricing_cards(idx, home)}
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
    """#req-pay: two settlement tracks, Option A (invoice) first and checked; app.js switches them (settlement=invoice|direct)."""
    treasury = idx["onchain_anchoring"]["treasury_admin"]
    rows = "".join(f'<dt>USDC on {k}</dt><dd>{hexref(v)}</dd>' for k, v in USDC.items())
    opts = "".join(
        f'<label class="pay-opt"><input type="radio" name="settlement" value="{k}"{" checked" if k == DEFAULT_SETTLEMENT else ""}>'
        f'<span><b>{E(h)}</b><span class="tag">{E(t)}</span><span class="sub">{E(x)}</span></span></label>'
        for k, (h, t, x, _) in SETTLEMENT.items())
    t0 = TRACKS[DEFAULT_TRACK]
    return (f'<div class="pay" id="req-pay"><p class="pay-sum" id="req-pay-sum">{E(t0[0])} · {E(t0[1])} {E(t0[2])}</p>'
            f'<div class="opts settle" role="radiogroup" aria-label="Settlement track">{opts}</div>'
            f'<dl class="kv" id="req-direct"><dt>{E(TREASURY_LABEL)}</dt><dd><span class="mono full">{treasury}</span>{copy_btn(treasury, "Copy", "Copy the Pacta treasury address")}</dd>{rows}</dl>'
            f'<p class="hint">Option B only: USDC to this externally owned account, the same address on Base and Ethereum. '
            f'Not a smart-contract wallet.</p></div>')


def request_builder(idx, home=""):
    """U6: a real submission (POST /v1/requests, CORS) with a confirmation receipt; a searchable protocol combobox replaces the 86
    checkboxes; the GitHub issue and the copyable brief stay as secondary channels."""
    tiers = "".join(
        f'<label data-slot="radio-card"><input type="radio" name="tier" value="{k}"{" checked" if k == DEFAULT_TRACK else ""}><span><b>{E(t)}</b>'
        f'<span class="tag">{E(p)}{" · " + E(u) if u and u != "free" else ""}</span><span class="sub">{E(sm)}</span></span></label>'
        for k, (t, p, u, sm, _) in TRACKS.items())
    sp_ = site_protocols(idx)
    slugs = {n: v["slug"] for n, v in sp_.items()}
    addrs = {n: " ".join(sorted(protocol_addresses(v["slug"], v["entries"]))) for n, v in sp_.items()}   # G-P2-3: 0x matches
    names = protocol_options(idx)
    opts = "".join(f'<li data-slot="command-item" role="option" id="opt-{slugs.get(n, "x" + str(i))}" aria-selected="false" '
                   f'data-name="{E(n)}"{f" data-slug={chr(34)}{slugs[n]}{chr(34)}" if n in slugs else ""}{f" data-q={chr(34)}{addrs[n]}{chr(34)}" if addrs.get(n) else ""}>{U.icon("check", "ck")}<span>{E(n)}</span></li>'
                   for i, n in enumerate(names))
    sel = lambda name, items, lbl, first=None: (f'<div class="field"><label for="req-{name}">{lbl}</label><select id="req-{name}" name="{name}">'
                                                + "".join(f'<option value="{k}"{" selected" if k == first else ""}>{E(v)}</option>' for k, v in items)
                                                + '</select></div>')
    gh = f"{REPO}/issues/new?template=request-scan.yml&title=" + urllib.parse.quote("[Pacta Scope] ")
    gm = "https://mail.google.com/mail/?view=cm&fs=1&to=" + urllib.parse.quote(CONTACT) + "&su=" + urllib.parse.quote("Pacta verification request")
    form = (f'<form class="req-form" data-slot="card" id="req-form" novalidate autocomplete="off" data-api="{E(REQUEST_API)}" '
            f'data-treasury="{idx["onchain_anchoring"]["treasury_admin"]}">'
            f'<fieldset><legend>Track</legend><div class="opts" role="radiogroup" aria-label="Track">{tiers}</div></fieldset>'
            f'<div class="field combo" data-combo><label for="req-proto-q" id="req-proto-l">Protocols in scope <span class="legend-note">· {len(names)} indexed; '
            f'name others under Scope</span></label><div class="combo-chips" id="req-proto-chips" data-combo-chips></div>'
            f'<div class="search">{U.icon("search")}<input id="req-proto-q" type="text" role="combobox" aria-autocomplete="list" aria-expanded="false" '
            f'aria-controls="req-proto-list" aria-describedby="req-proto-err" placeholder="Search {len(names)} protocols" autocomplete="off"></div>'
            f'<ul data-slot="command-list" id="req-proto-list" role="listbox" aria-labelledby="req-proto-l" aria-multiselectable="true" hidden>{opts}'
            f'<li data-slot="command-empty" role="presentation" hidden>No protocol found. Name it under Scope.</li></ul>'
            f'<p class="form-message" id="req-proto-err" data-slot="form-message" hidden></p></div>'
            f'<div class="req-grid">{sel("request_type", REQUEST_TYPES, "What do you need?", "doc_or_data_discrepancy")}'
            f'{sel("requester_role", REQUESTER_ROLES, "Your role", "protocol_team")}</div>'
            f'<div class="req-grid">{sel("caller_purpose", PURPOSES, "Purpose", "collateral_due_diligence")}'
            f'<div class="field"><label for="req-org">Organization or protocol</label><input id="req-org" name="org" type="text" maxlength="80" '
            f'placeholder="e.g. Example Labs" aria-describedby="req-org-err"><p class="form-message" id="req-org-err" data-slot="form-message" hidden></p></div></div>'
            f'<div class="field"><label for="req-scope">Scope</label><textarea id="req-scope" name="scope" maxlength="400" aria-describedby="req-scope-hint req-scope-err" '
            f'placeholder="Public docs URL, mainnet addresses, or the collateral list you curate"></textarea>'
            f'<p class="hint" id="req-scope-hint">Public contract addresses &amp; scope links only (no private keys or exploit PoCs — put your email or Telegram in the Contact field below).</p>'
            f'<p class="form-message" id="req-scope-err" data-slot="form-message" hidden></p></div>'
            f'<div class="req-grid"><div class="field" id="req-forum-field"><label for="req-forum">Forum proposal URL <span class="legend-note">· optional</span></label>'
            f'<input id="req-forum" name="forum" type="url" maxlength="200" placeholder="https://…" aria-describedby="req-forum-err">'
            f'<p class="form-message" id="req-forum-err" data-slot="form-message" hidden></p></div>'
            f'<div class="field"><label for="req-contact">Contact <span class="legend-note">· optional</span></label><input id="req-contact" name="contact" type="text" '
            f'maxlength="120" placeholder="Email or Telegram" aria-describedby="req-contact-err">'
            f'<p class="form-message" id="req-contact-err" data-slot="form-message" hidden></p></div></div>'
            f'<div class="field" id="req-tx-field" hidden><label for="req-tx">Payment transaction hash <span class="legend-note">· Option B · optional</span></label>'
            f'<input id="req-tx" name="tx" type="text" spellcheck="false" placeholder="0x… (Base or Ethereum)"><p class="hint" id="req-tx-hint">A 66-character hash starting with 0x.</p></div>'
            f'<div class="req-actions">' + U.button('<span class="spinner" aria-hidden="true" hidden></span><span data-req-label>Send request</span>',
                                                    variant="default", size="lg", type_="submit", attrs='id="req-send"')
            + f'<span class="req-status" id="req-status" role="status" aria-live="polite"></span></div>'
            f'<noscript><p class="note">Sending needs JavaScript. Without it, open a <a href="{E(gh)}">GitHub intake issue</a> or write to {CONTACT}.</p></noscript>'
            f'</form>')
    done = (U.card(U.card_header('<span data-req-done-title>Request received</span>', "Pacta queued your request. Keep the ID for follow-up.")
                   + U.alert("", '<span data-req-done-text>Your request is in the public queue.</span>', icon_name="circle-check")
                   + '<dl><div><dt>Request ID</dt><dd><span class="mono" data-req-id></span></dd></div><div><dt>Status</dt><dd data-req-st></dd></div>'
                   '<div><dt>Demand votes</dt><dd data-req-votes></dd></div><div data-req-fast-row hidden><dt>Next step</dt><dd><a data-req-fast href="#">Fast-track this request</a></dd></div></dl>'
                   + '<div data-slot="card-footer">' + U.button("Send another request", variant="outline", attrs="data-req-again") + '</div>',
                   cls="receipt-card", attrs='id="req-done" tabindex="-1" hidden'))
    side = (U.card(U.card_header("Scope brief", "Also send it another way: a GitHub issue for crypto-native teams, or email.")
                   + f'<div class="term"><div class="term-h"><span>To: {CONTACT}</span>'
                     f'<button class="copy" data-slot="button" data-variant="ghost" data-size="sm" type="button" data-copy-from="req-brief" '
                     f'aria-label="Copy the request brief">{U.icon("copy")}<span>Copy</span></button></div>'
                     f'<pre id="req-brief">Choose a track and protocols; the brief updates as you type.</pre></div>'
                   + '<div class="actions">'
                   + U.button("Open a GitHub issue", href=gh, variant="outline", attrs='id="req-gh" target="_blank" rel="noopener"')
                   + U.button("Compose in Gmail", href=gm, variant="outline", attrs='id="req-gmail" target="_blank" rel="noopener"')
                   + U.button("Copy brief and address", variant="outline", attrs=f'id="req-copy" data-copy-from="req-brief" data-copy-prefix="To: {CONTACT}"')
                   + '</div>')
            + U.card(U.card_header("Settlement", "Paid tracks only. No transfer is needed to open a request.") + pay_panel(idx))
            + U.card(U.card_header("Contact", "") + f'<p class="s">{E(CONTACT_NOTE)}</p><div class="addrline">Email <b>{CONTACT}</b>'
                     f'{copy_btn(CONTACT, "Copy", "Copy the Pacta contact address")}</div>'
                     f'<p class="s"><a href="{home}about/#official-addresses">Official domains &amp; verified on-chain addresses{ARR}</a></p>'
                     f'<p class="note">{E(VULN_ROUTE)}</p>'))
    return f'<div class="req"><div class="req-main">{form}{done}</div><aside class="req-side" aria-label="Other channels">{side}</aside></div>'


def launcher_links(home, n_protocols):
    """/request/: the three human doors above the dossier builder (?tier=webhook-49 | wallet-9 | seal-99 still forward cleanly)."""
    doors = (
        ("scan-free", "scan", "Instant scan", "$0", f"Wallet, Safe & {n_protocols} protocols", "launch_scan"),
        ("sponsor-pool", "bounties/#sponsor-pool", "Verification pools", "$50+ USDC", "Pool or $150/proto sweep", "launch_sponsor"),
        ("watch-pilot", "webhook", "Timelock watchlist", "$0", "Free 30-day pilot", "launch_watch_pilot"),
    )
    out = []
    for sku, route, name, price, sub, cta in doors:
        sep = "" if ("#" in route or route.endswith("/")) else "/"
        out.append(f'<a class="launch" href="{home}{route}{sep}" data-sku="{sku}" data-cta="{cta}"><span class="l-n">{E(name)}{ARR}</span>'
                   f'<span class="l-p"><b>{E(price)}</b><small>{E(sub)}</small></span></a>')
    return "".join(out)


def watch_pilot_box(prefix="", default_target="", heading="Watch This Safe or Protocol Free (30-Day Pilot)",
                    sub="Instant Email, @Telegram, or HTTPS Webhook alerts before queued timelock ops or Safe signer rotations execute — 30 days free, no payment now.",
                    id_attr="watch-pilot", compact=False):
    """Reusable 30-day free watch pilot capture (alerts when contract controls change; (POST /v1/pilot/watch -> PactaLedgerDO)."""
    cls = "watch-pilot-box wp-compact" if compact else "watch-pilot-box"
    id_part = f' id="{E(id_attr)}"' if id_attr else ""
    return (
        f'<section class="{cls}"{id_part} data-watch-pilot data-api="{E(PILOT_WATCH_API)}" data-fallback-api="{E(REQUEST_API)}">'
        f'<div class="wp-head"><span class="step-k mono">FREE 30-DAY WATCH PILOT · NO PAYMENT NOW</span>'
        f'<h3>{E(heading)}</h3>'
        + (f'<p class="wp-sub">{E(sub)}</p>' if sub else "")
        + '</div>'
        f'<form class="wp-form" data-watch-pilot-form novalidate autocomplete="off">'
        f'<div class="wp-fields">'
        f'<div class="field"><label class="sr-only" for="{E(id_attr or "wp")}-target">Safe, wallet or protocol</label>'
        f'<input id="{E(id_attr or "wp")}-target" name="target" type="text" maxlength="120" spellcheck="false" autocapitalize="off" '
        f'value="{E(default_target)}" placeholder="Wallet or protocol" data-wp-target></div>'
        f'<div class="field"><label class="sr-only" for="{E(id_attr or "wp")}-dest">Email, @Telegram, or HTTPS Webhook</label>'
        f'<input id="{E(id_attr or "wp")}-dest" name="destination" type="text" maxlength="240" spellcheck="false" autocapitalize="off" '
        f'placeholder="Email, Telegram or webhook" data-wp-dest></div>'
        + U.button('<span class="spinner" aria-hidden="true" hidden></span><span data-wp-btn-lbl>Enable free alerts</span>',
                   variant="default", size="default", type_="submit", attrs="data-wp-submit")
        + '</div>'
        f'<p class="wp-privacy" data-wp-privacy>Used only to deliver the alerts you ask for and opted-in setup replies from Pacta '
        f'(<code>pacta@dri.network</code>); never sold or used for cold marketing — see <a href="{prefix}privacy/#watch-pilot">Privacy</a>.</p>'
        f'<p class="form-message" data-slot="form-message" data-wp-err hidden></p>'
        f'<p class="wp-status" role="status" aria-live="polite" data-wp-status hidden></p>'
        f'</form>'
        f'<div class="wp-done" data-wp-done hidden tabindex="-1">'
        f'<span data-slot="badge" data-variant="success">30-Day Free Pilot Active</span>'
        f'<p data-wp-done-msg>Alert pilot enabled.</p>'
        f'</div></section>'
    )


def eip681(atomic):
    """EIP-681 payment request: an exact Base USDC transfer(treasury, atomic) on chain 8453 (wallet apps, Safe apps, mobile QR)."""
    return f"ethereum:{USDC['Base']}@{CHECKOUT_CHAIN_ID}/transfer?address={CHECKOUT_TREASURY}&uint256={atomic}"


def lookup_items():
    return {i["slug"]: i for i in json.load(open(os.path.join(DOCS, "api", "v1", "lookup.json")))["items"]}


_IDENT = {}


def proto_extra_syms():
    """PROTO_EXTRA_SYMS from tools/app.src.js, so server-rendered and browser-built identity cells read the same ticker."""
    if "extra" not in _IDENT:
        src = open(os.path.join(ROOT, "tools", "app.src.js"), encoding="utf-8").read()
        i = src.index("var PROTO_EXTRA_SYMS = {")
        _IDENT["extra"] = dict(re.findall(r'"([a-z0-9-]+)":\s*"([^"]*)"', src[i:src.index("};", i)]))
    return _IDENT["extra"]


def proto_ticker(slug, name, tokens):
    """app.src.js protoTickerText in Python: a mapped symbol only (never invented), at most two, short symbols without spaces."""
    raw = list(tokens or [])
    ex = proto_extra_syms().get(slug)
    if ex:
        raw.insert(0, ex)
    seen, clean, nm = set(), [], (name or "").lower()
    for t in raw:
        s_ = str(t or "").strip()
        if not s_ or re.search(r"\s", s_) or len(s_) > 10 or (s_.lower() == nm and len(s_) > 5):
            continue
        if s_.upper() not in seen:
            seen.add(s_.upper())
            clean.append(s_)
    return " · ".join(clean[:2])


def proto_ident(slug):
    """(icon path relative to the site root, ticker text) for one indexed protocol."""
    if slug not in _IDENT:
        if "lk" not in _IDENT:
            _IDENT["lk"] = lookup_items()
        it = _IDENT["lk"].get(slug) or {}
        _IDENT[slug] = (proto_icon_rel(slug), proto_ticker(slug, it.get("name") or "", it.get("tokens")))
    return _IDENT[slug]


def ident_cell(slug, name_html, prefix="", size=22):
    """B8: one identity cell everywhere: a fixed-size logo that never shrinks, the readable name, then a subtle ticker."""
    icon, tk = proto_ident(slug)
    return (f'<span class="pid"><img class="pid-logo" src="{prefix}{icon}" alt="" width="{size}" height="{size}" loading="lazy" decoding="async">'
            f'{name_html}' + (f'<span class="pid-tk mono">{E(tk)}</span>' if tk else "") + '</span>')


def entity_cell(name, name_html):
    """Curators and allocators have no protocol logo: a neutral initials mark, never a borrowed protocol logo."""
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name) if w]
    ini = ((words[0][0] + words[1][0]) if len(words) >= 2 else (words[0][:2] if words else "?")).upper()
    return f'<span class="pid"><span class="pid-ent" aria-hidden="true">{E(ini)}</span>{name_html}</span>'


def short_addr(a):
    return a[:6] + "…" + a[-4:]


def mobile_wallet_deeplinks(c):
    """Progressive enhancement on /scan/ and /seal/ when window.ethereum is absent on a mobile browser (e.g. X in-app WebView):
    app.js unhides this block and keeps the canonical pacta.wtf/<route>/?... deep-links synced with the selected chain and contract."""
    canon = f"/{c['route']}/"
    mm = f"https://metamask.app.link/dapp/pacta.wtf{canon}"
    cb = "https://go.cb-wallet.com/dapp?cb_url=" + urllib.parse.quote(f"https://pacta.wtf{canon}", safe="")
    return (f'<div class="co-deeplinks" id="co-deeplinks" data-co-deeplinks hidden>'
            f'<p class="co-dl-head">In-app mobile browser detected — open in your wallet app for 1-tap Base USDC checkout:</p>'
            f'<div class="co-dl-btns">'
            f'<a class="co-dl-btn" href="{E(mm)}" rel="noopener" data-cta="wallet_metamask" data-co-metamask>'
            f'<span>Open in MetaMask</span>{EXT}</a>'
            f'<a class="co-dl-btn" href="{E(cb)}" rel="noopener" data-cta="wallet_coinbase" data-co-coinbase>'
            f'<span>Open in Coinbase Wallet</span>{EXT}</a>'
            f'</div></div>')


def manual_drawer(c):
    """The manual / Safe / CLI path, collapsed by default: the exact amount, the treasury as a one-line pill (full value copied), the
    EIP-681 link and the transaction-hash check."""
    uri = eip681(c["atomic"])
    amount_copy = copy_btn(c["amount"], "Copy", f"Copy the exact USDC amount ({c['amount']})")
    addr_copy = copy_btn(CHECKOUT_TREASURY, "Copy address", "Copy the full Pacta treasury address")
    link_copy = copy_btn(uri, "Copy link", "Copy the EIP-681 payment link")
    return (f'<details class="co-manual" id="co-manual"><summary>Paying from a Safe multisig, CLI, or mobile wallet? Transfer manually{ARR}</summary>'
            f'<div class="co-manual-b"><dl class="co-kv">'
            f'<dt>Amount</dt><dd><b class="mono" data-co-amount>{c["amount"]} USDC</b> on Base{amount_copy}</dd>'
            f'<dt>Network</dt><dd>Base mainnet · chain ID {CHECKOUT_CHAIN_ID} · native USDC <span class="addr-pill mono" title="{USDC["Base"]}">{short_addr(USDC["Base"])}</span></dd>'
            f'<dt>Send to</dt><dd><span class="addr-pill mono" title="{CHECKOUT_TREASURY}" data-co-treasury>{short_addr(CHECKOUT_TREASURY)}</span>{addr_copy}</dd></dl>'
            f'<div class="co-actions">' + U.button("Open in wallet app", href=uri, variant="outline", size="sm", attrs="data-co-eip681") + link_copy + '</div>'
            f'<div class="field"><label for="co-tx">Base transaction hash</label><input id="co-tx" name="tx_hash" type="text" spellcheck="false" maxlength="66" '
            f'placeholder="0x…" aria-describedby="co-tx-err"><p class="form-message" id="co-tx-err" data-slot="form-message" hidden></p></div>'
            + U.button('<span class="spinner" aria-hidden="true" hidden></span><span>Verify on-chain &amp; unlock</span>', variant="outline", type_="submit",
                       attrs='id="co-verify"')
            + '</div></details>')


def receipt_card():
    return U.card(U.card_header("Order verified", '<span data-co-r-desc>Payment confirmed on Base.</span>')
                  + '<dl class="kv"><dt>Order</dt><dd class="mono" data-co-r-order></dd><dt>Product</dt><dd data-co-r-sku></dd>'
                  '<dt>Payment</dt><dd data-co-r-pay></dd><dt>Status</dt><dd data-co-r-status></dd></dl>'
                  + f'<div class="term"><div class="term-h"><span>Report (JSON)</span><button class="copy" data-slot="button" data-variant="ghost" '
                    f'data-size="sm" type="button" data-copy-from="co-json" aria-label="Copy the report JSON">{U.icon("copy")}<span>Copy</span></button></div>'
                    '<pre id="co-json"></pre></div><div class="co-actions">'
                  + U.button("Download JSON", variant="outline", size="sm", attrs="data-co-download")
                  + U.button("Print report", variant="outline", size="sm", attrs="data-co-print") + '</div>',
                  cls="co-result", attrs='id="co-result" tabindex="-1" hidden')


def field(id_, name, label, ph, optional=False, maxlength=200, help_=""):
    opt = ' <span class="legend-note">· optional</span>' if optional else ""
    return (f'<div class="field"><label for="{id_}">{label}{opt}</label>'
            f'<input id="{id_}" name="{name}" type="text" maxlength="{maxlength}" placeholder="{E(ph)}" aria-describedby="{id_}-err">'
            + (f'<p class="hint">{help_}</p>' if help_ else "")
            + f'<p class="form-message" id="{id_}-err" data-slot="form-message" hidden></p></div>')


def chain_target(target_label, optional=False):
    opt = ' <span class="legend-note">· optional</span>' if optional else ""
    ph = "Select or type a protocol / token (Aave, Lido, Moonwell…) or paste 0x…"
    return (f'<div class="co-row"><div class="field co-chain-f"><label for="co-chain">Chain</label><select id="co-chain" name="target_chain">'
            f'<option value="ethereum" selected>Ethereum</option><option value="base">Base</option></select></div>'
            f'<div class="field"><label for="co-target">{target_label}{opt}</label>'
            f'<div class="pf-combo pf-combo-seal" data-seal-combo>'
            f'<input id="co-target" name="target_address" type="text" maxlength="80" spellcheck="false" autocapitalize="off" '
            f'role="combobox" aria-expanded="false" aria-controls="co-target-listbox" aria-autocomplete="list" '
            f'placeholder="{E(ph)}" aria-describedby="co-target-err">'
            f'<button type="button" class="pf-toggle-btn" data-seal-toggle aria-label="Browse indexed protocols">'
            f'<span class="pf-toggle-lbl">Protocols</span>{U.icon("chevron-down")}</button>'
            f'<div class="pf-dropdown" id="co-target-listbox" role="listbox" aria-label="Indexed protocols" hidden></div></div>'
            f'<p class="form-message" id="co-target-err" data-slot="form-message" hidden></p></div></div>')


def scan_sample_finding(idx, lk):
    """Static zero-network example finding shown inside #pf-out on /scan/ cold load (replaced immediately on first check)."""
    mw = next((x for x in receipt_data(idx) if x["slug"] == "moonwell-lending-base"), receipt_data(idx)[0])
    blk = int(mw["e"]["block_number"])
    addr = mw["e"]["target_contract"]
    return (
        f'<div class="pf-sample-card" id="pf-sample-card" data-pf-sample data-pf-sample-slug="moonwell-lending-base">'
        f'<div class="pf-sample-top">'
        f'<span class="pf-sample-id">{chain_icon_svg("base")}<b>Moonwell Lending (Base)</b>'
        f'<span class="pf-opt-sym">WELL</span><span class="pf-st-pill" data-tone="gap">GAP</span></span>'
        f'<span class="pf-sample-k mono">LIVE EXAMPLE · TAP ANY PROTOCOL ABOVE</span></div>'
        f'<div class="pf-sample-grid">'
        f'<div class="pf-s-box pf-s-docs"><span class="pf-s-lbl mono">PUBLISHED DOCS</span>'
        f'<span>{E(mw["docs"])}</span></div>'
        f'<div class="pf-s-box pf-s-chain"><span class="pf-s-lbl mono">LIVE CHAIN STORAGE</span>'
        f'<span><b>{E(mw["chain"])}</b> · 0s delay · Base #{blk:,} ({short_addr(addr)})</span></div>'
        f'</div></div>'
    )


SCAN_OMNIBOX_PLACEHOLDER = "0x… or protocol name"   # <= 30 characters; examples live in the helper line under the field
WALLET_DEMO_CHIPS = (
    ("demo_safe_eth_base", "0x5afE00003f5D8B29c4107E3A92d1b64E8C410305", "Demo Treasury Safe (4 positions · 2 Gaps)", "3-of-5 SAFE", "2 GAPS"),
    ("demo_base_yield", "0xba5E00007C41D92e8A305F6b11c8E92D40A20845", "Demo Base Yield Wallet (3 positions · 2 Gaps)", "BASE EOA", "2 GAPS"),
)


def scan_checker(lk, idx=None):
    """/scan/: unified above-the-fold Wallet, Safe & Protocol omnibox; 2 zero-shift instant wallet/Safe demo chips + 6 real protocol chips."""
    demos = []
    for mode, d_addr, d_lbl, d_kind, d_st in WALLET_DEMO_CHIPS:
        d_inner = (f'{U.icon("shield")}<span class="rc-name">{E(d_lbl)}</span>'
                   f'<span class="rc-sym">{E(d_kind)}</span><span class="rc-st" data-tone="gap">{E(d_st)}</span>')
        demos.append(U.button(d_inner, variant="outline", size="sm", cls="receipt wl-demo-chip",
                              attrs=(f'data-wallet-demo="{mode}" data-demo-addr="{d_addr}" '
                                     f'aria-label="Run instant read-only {E(d_lbl)} scan"')))
    chips = []
    for label, slug in SCAN_CHIPS:
        it = lk[slug]
        ch, addr = LIVE_CHECK_TARGET.get(slug, (it["preflightArgs"]["chain"], it["preflightArgs"]["address"]))
        st_txt, st_tone = chip_status_meta(it.get("classification", ""))
        inner = receipt_inner_html(slug, label, ch, st_txt, st_tone, prefix="../")
        sym = CHIP_TICKERS.get(slug, "")
        chips.append(U.button(inner, variant="outline", size="sm", cls="receipt",
                              attrs=(f'data-receipt data-pf-chain="{ch}" data-pf-address="{addr}" '
                                     f'aria-label="Try {E(label)}: run a free live check of its indexed contract" '
                                     f'data-pf-slug="{slug}" data-pf-disp="{E(it["name"])}" data-pf-sym="{E(sym)}" '
                                     f'data-pf-icon="../{proto_icon_rel(slug)}"')))
    examples = (f'<div class="try try-omnibox">'
                f'<div class="try-row try-demos" role="group" aria-label="Instant wallet and Safe demos">'
                f'<span class="try-l">Instant wallet demos</span><div class="try-chips">{"".join(demos)}</div></div>'
                f'<div class="try-row" role="group" aria-label="Example contracts">'
                f'<span class="try-l">Popular protocols</span><div class="try-chips">{"".join(chips)}</div></div></div>')
    cap = (f"Paste a wallet or Safe address, or search {_total_protocols()} protocols and tickers (steakUSDC, Moonwell, ETHx). "
           "Read-only contract checks on Ethereum & Base: no wallet connection, no signature, no payment.")
    init_out = scan_sample_finding(idx, lk) if idx is not None else ""
    return hero_checker(examples, prefix="../", cap=cap, label="Wallet, Safe or protocol",
                        cta_variant="default", cta_label="Scan Exposure (Free)", initial_out=init_out,
                        placeholder=SCAN_OMNIBOX_PLACEHOLDER, visible_label=True,
                        extra_attrs=' data-wallet-scanner="1" data-wallet-tokens="../api/v1/wallet-tokens.json"')


def scan_explainer_section():
    """/scan/: plain-English + technical explainer shown on initial cold load right beneath the Free Checker (zero price tags)."""
    items = (
        ("1. Upgrade Authority & Proxy Chain",
         "Reads EIP-1967, UUPS, Transparent, Beacon and Diamond diamondCut storage slots to expose active implementation addresses and who can swap them."),
        ("2. Multisig Signers & Real Quorum",
         "Extracts exact Gnosis Safe threshold (e.g. 3-of-6), owner list, Safe guard status, and nested Safes holding admin power."),
        ("3. Timelock Delay & Bypass Check",
         "Queries live getMinDelay() in seconds alongside PROPOSER_ROLE, EXECUTOR_ROLE, and DEFAULT_ADMIN_ROLE holders."),
        ("4. Emergency Pause, Mint & Fee Keys",
         "Flags single EOAs or low-quorum multisigs able to pause withdrawals, mint tokens, blacklist users, or hike fees."),
        ("5. Verifiable Dual-RPC Proof",
         "Every read is block-pinned across two independent archive RPCs with copyable Foundry cast reproduction commands."),
    )
    cards = "".join(f'<li class="ex-item"><b>{E(t)}</b><span>{E(d)}</span></li>' for t, d in items)
    return (
        '<section class="scan-explain" id="what-pacta-checks" data-what-pacta-checks>'
        '<div class="ex-head"><span class="step-k mono">WHAT PACTA CHECKS · DOCS VS LIVE BYTECODE</span>'
        '<h2>Why smart contract security docs are not enough</h2>'
        '<p class="ex-sub">Static code audits check logic at one point in time. Post-deployment admin keys, proxy pointers, and Safe signers can change quietly without touching immutable code.</p></div>'
        '<div class="dvc-compare" role="region" aria-label="Docs vs live on-chain reality example">'
        '<div class="dvc-box dvc-docs"><span class="dvc-k mono">PUBLISHED DOCS PROMISE</span>'
        '<p class="dvc-q">&ldquo;All smart contract upgrades pass through a 48-hour Timelock.&rdquo;</p></div>'
        '<div class="dvc-box dvc-chain"><span class="dvc-k mono">LIVE ON-CHAIN REALITY</span>'
        '<p class="dvc-q"><b>ADVERSE DELTA</b> — 3-of-6 Gnosis Safe owns ProxyAdmin directly (0-second upgrade delay, no timelock in path).</p></div></div>'
        f'<ul class="ex-grid" aria-label="Five control-plane checks">{cards}</ul>'
        '<div class="scan-reveal-row" id="scan-reveal-row" data-scan-actions>'
        '<a class="scan-reveal-btn" href="../bounties/#sponsor-pool" data-cta="scan_fund_pool">Fund a Pool</a>'
        '<a class="scan-reveal-btn" href="../request/?tier=community" data-cta="scan_free_fix">Submit Updated Docs</a></div>'
        '</section>'
    )


def seal_how_section(preview_html):
    """/seal/: 3-step explainer + honest Independence callout + real sample scorecard/badge deliverable preview."""
    return (
        '<section class="seal-explain" id="how-seal-works" data-seal-explainer>'
        '<div class="ex-head"><span class="step-k mono">HOW BASE-EAS VERIFICATION WORKS &amp; WHAT YOU RECEIVE</span>'
        '<h2>Three steps from contract or docs submission to permanent Base-EAS attestation</h2></div>'
        '<ol class="seal-steps">'
        '<li><b>1 · Submit primary contract(s) &amp; docs URL</b><span>Provide your Ethereum or Base vault, proxy, Safe, or timelock address plus your merged public security docs or PR.</span></li>'
        '<li><b>2 · Automated dual-RPC extraction + independent verifier pass</b><span>Pacta extracts live proxy/Safe/timelock storage across two RPCs and verifies every published governance, timelock, and role claim.</span></li>'
        '<li><b>3 · Permanent Base Mainnet EAS UID + public scorecard + live SVG badge</b><span>Receive an on-chain Base EAS attestation UID, public Pacta scorecard, embeddable README/docs badge, and Safe remediation JSON if any step remains.</span></li>'
        '</ol>'
        f'<div class="seal-indep" role="note"><b>{E(EDITORIAL_FIREWALL)}</b> {E(SEAL_GUARANTEE)}</div>'
        f'<aside class="pd-preview" aria-label="Sample Base-EAS deliverables">{preview_html}</aside>'
        '</section>'
    )


def scan_preview(idx, lk):
    """/scan/: a sample unlocked report from Pacta's published Stader ETHx record: the rosette, status pills, the record's own
    role and getter names and the three deliverables. Every value comes from the record; nothing is illustrative."""
    import scorecard as SC
    r = next(x for x in receipt_data(idx) if x["slug"] == "stader-labs-ethx")
    it, card = lk["stader-labs-ethx"], card_for(idx, "stader-labs-ethx")
    uid = (it.get("baseEasUids") or [""])[0]
    secs = it["observedDelaySeconds"]
    days = secs // 86400
    onchain, docs = r["chain"].replace("Manager Safe is ", ""), r["docs"].replace("Manager Safe is ", "")
    pills = (U.badge("EIP-1967 proxy", "neutral") + U.badge(f"Docs differ · {E(onchain)} on chain vs {E(docs)} docs", "warning")
             + U.badge(f"{days}d timelock · {secs:,} s", "success"))
    chips = "".join(f'<code class="sel-chip">{E(s_)}</code>' for s_ in SCAN_SAMPLE_CHIPS)
    deliv = ('<span class="dl-badge">SHA-256 JSON receipt</span><span class="dl-badge">1-page printable report</span>'
             + (f'<a class="dl-badge" href="https://base.easscan.org/attestation/view/{uid}" target="_blank" rel="noopener">Base EAS {short(uid, 6, 4)}{EXT}</a>'
                if uid else ""))
    return (f'<div class="pv-card" data-slot="card" data-preview="scan"><div class="pv-head"><span class="pv-k">Sample unlocked report</span>'
            f'<span class="pv-t">Stader ETHx · Ethereum · block #{int(r["e"]["block_number"]):,}</span></div>'
            f'<div class="pv-score">{SC.rosette_svg(card["factors"], 56, card["name"])}<div class="pv-pills">{pills}</div></div>'
            f'<ol class="pv-rows"><li><b>Proxy &amp; implementation chain</b><span>Admin behind a {days}-day TimelockController '
            f'<span class="addr-pill mono" title="{it["controllerAddress"]}">{short_addr(it["controllerAddress"])}</span></span></li>'
            f'<li><b>Safe quorum &amp; cross-protocol signer overlap</b><span>getThreshold() and getOwners() read live; signers matched against every indexed Safe</span></li>'
            f'<li><b>Roles &amp; live bytecode capabilities</b><span class="sel-row">{chips}</span></li></ol>'
            f'<div class="pv-deliv-row" aria-label="Deliverables">{deliv}</div>'
            f'<p class="pv-foot">Built from Pacta&#x27;s published Stader ETHx record. Your report covers the contract you enter.</p></div>')

def webhook_preview():
    b = DECODED[ALERT_EXAMPLE]
    op = b["operations"][0]
    calls = op["calls"]
    tl = b["timelock"]["address"]
    first = calls[0]
    ch = first.get("lombardChange") or {}
    change = f': {ch.get("from"):,} to {ch.get("to"):,} {E(ch.get("unit") or "")}' if isinstance(ch.get("from"), int) and isinstance(ch.get("to"), int) else ""
    payload = json.dumps({"event": "timelock_queued", "protocol": b["protocol"], "chain": "ethereum", "block": op["scheduled"]["block"],
                          "calls": len(calls), "first_call": first["function"], "eta_utc": op["eta_utc"]}, indent=2, ensure_ascii=False)
    return (f'<div class="pv-card" data-slot="card" data-preview="webhook"><div class="pv-head"><span class="pv-k pv-alert">Timelock queued · Ethereum #{op["scheduled"]["block"]:,}</span>'
            f'<span class="pv-t">{E(b["protocol"])} · {E(b["timelock"]["verified"]["sourcify"]["name"])} <span class="addr-pill mono" title="{tl}">{short_addr(tl)}</span></span></div>'
            f'<ol class="pv-rows"><li><b>Decoded action</b><span><code>{E(first["function"])}</code><span>{change.lstrip(": ") if change else ""} · +{len(calls) - 1} more calls in the batch</span></span></li>'
            f'<li><b>Earliest execution</b><span><span class="countdown" data-eta="{op["eta"]}">ETA {E(op["eta_utc"])}</span></span></li>'
            f'<li><b>Signer watch</b><span>Scheduled by Safe <span class="addr-pill mono" title="{op["scheduled"]["to"]}">{short_addr(op["scheduled"]["to"])}</span> via execTransaction · owner or threshold changes alert too</span></li></ol>'
            f'<div class="pv-msg"><span class="pv-k">Slack / Telegram</span><p>Lombard timelock queued a {len(calls)}-call batch at Ethereum #{op["scheduled"]["block"]:,}: '
            f'{E(first["function"].split("(")[0])} and {len(calls) - 1} more. Executable from {E(op["eta_utc"])}.</p></div>'
            f'<div class="term"><div class="term-h"><span>Historical Example Payload (2026-11-19) · HTTPS webhook (JSON)</span></div><pre>{E(payload)}</pre></div>'
            f'<p class="pv-foot">A real radar observation: <a href="../{b["brief"]}">the decoded Lombard brief{ARR}</a></p></div>')


def seal_preview(idx, lk):
    import scorecard as SC
    demo = card_for(idx, BADGE_DEMO)
    it = lk[BADGE_DEMO]
    uid = (it.get("baseEasUids") or [""])[0]
    r = next(x for x in receipt_data(idx) if x["slug"] == "stader-labs-ethx")
    label = LK.BADGE_TIERS["aligned"][0]
    width = (len(LK.BADGE_TITLE) + len(label)) * 7 + 24
    stb = ('{\n  "version": "1.0", "chainId": "1",\n  "meta": {"name": "Pacta seal: remaining step"},\n'
           '  "transactions": [\n    {"to": "0x…", "value": "0", "data": "0x…"}\n  ]\n}')
    return (f'<div class="pv-card" data-slot="card" data-preview="seal"><div class="pv-head"><span class="pv-k">The three seal deliverables</span>'
            f'<span class="pv-t">Examples from published Pacta records</span></div>'
            f'<div class="pv-deliv"><div class="pv-d"><span class="pv-n" aria-hidden="true">1</span><div><b>Verified Base EAS attestation seal</b>'
            f'<div class="pv-seal">{SC.rosette_svg(demo["factors"], 48, demo["name"])}<div><span>{E(demo["name"])} · {E(demo["gradeLabel"])} · 5-factor control-strength graphic</span>'
            f'<img class="cp-badge" src="../badges/{BADGE_DEMO}.svg" alt="{E(LK.BADGE_TITLE)}: {E(label)}" width="{width}" height="20">'
            + (f'<a href="https://base.easscan.org/attestation/view/{uid}" target="_blank" rel="noopener">EAS {short(uid, 6, 4)}{EXT}</a>' if uid else "")
            + '</div></div></div></div>'
            f'<div class="pv-d"><span class="pv-n" aria-hidden="true">2</span><div><b>Safe Transaction Builder JSON</b><span class="s">When a parameter, timelock or owner step still has to be queued.</span>'
            f'<pre class="pv-pre">{E(stb)}</pre></div></div>'
            f'<div class="pv-d"><span class="pv-n" aria-hidden="true">3</span><div><b>Upstream documentation PR</b><span class="s">Aligning the published docs with live contract storage.</span>'
            f'<pre class="pv-pre pv-diff"><span class="del">- {E(r["docs"])}</span>\n<span class="add">+ {E(r["chain"])} (on chain at block #{int(r["e"]["block_number"]):,})</span></pre></div></div></div>'
            f'<p class="pv-foot">Examples from Pacta&#x27;s published Aave V3 / GHO and Stader ETHx records; yours cover the contract you book.</p></div>')


def scan_page(idx):
    """/scan/: 100% free full Wallet, Safe & Protocol scanner (who can change the contracts behind your positions) + inline free 30-day watch pilot."""
    lk = lookup_items()
    count_line = coverage_line(idx)
    n_proto = len(site_protocols(idx))
    n_eas = sum(1 for v in lk.values() if v.get("kind") == "protocol" and v.get("easAttested"))
    s_nums = site_numbers(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    crumbs = '<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span><span>Instant Scan</span></nav>'
    hero_scan = (
        '<div class="pd-head pd-hero-explain pd-head-scan"><span data-slot="badge" data-variant="info">100% Free Ethereum &amp; Base Wallet, Safe &amp; Protocol Scanner</span>'
        '<h1 id="co-title">Paste any wallet, Safe, or protocol to see who can change the contracts behind your positions.</h1></div>'
    )
    lede = (f"Instant read-only contract checks of your balances and Safe custody across {n_proto} Ethereum & Base protocols "
            f"({n_eas} Base-EAS attested · {s_nums['delta']} verified adverse control-plane gaps). "
            "Every held position, Safe quorum, and documented-vs-observed breakdown renders free — zero wallet connection, zero signature, zero paywall.")
    trust_scan = (
        f'<div class="scan-trust-strip" aria-label="Verification coverage">'
        f'<p class="pd-lede">{E(lede)} Inspect institutional vault stacks in the <a href="../curators/">Curator Exposure Matrix</a>.</p>'
        f'<ul class="pd-proof">'
        f'<li><b>{n_proto} protocols indexed · {n_eas} Base-EAS verified</b></li>'
        f'<li><b>{len(idx["entries"])} attested checks</b></li>'
        f'<li><b>Read-only checks on 2 RPCs</b></li>'
        f'<li><b>No Wallet · No Signup</b></li></ul></div>'
    )
    next_doors = (
        f'<section class="scan-next-doors" id="scan-next-doors" data-scan-next-doors>'
        f'{watch_pilot_box("../", heading="Watch This Safe or Protocol Free (30-Day Pilot)", id_attr="watch-pilot")}'
        f'<div class="scan-door-pair">'
        f'<article class="wl-tier" data-wl-tier="sponsor-pool">'
        f'<div class="wl-tier-top"><span class="wl-tier-k mono">COMMUNITY &amp; CURATORS</span><b class="wl-tier-p">Verification Pools</b></div>'
        f'<h3>Hold an unassessed or RPC-observed vault?</h3>'
        f'<p>Sponsor an independent protocol Verification Pool on Base or commission a multi-protocol curator sweep under Pacta&#x27;s editorial firewall.</p>'
        + U.button("Fund a Pool", href="../bounties/#sponsor-pool", variant="outline", size="default", attrs='data-cta="scan_sponsor_pool"')
        + '</article>'
        f'<article class="wl-tier wl-tier-agent" data-wl-tier="agent-mcp">'
        f'<div class="wl-tier-top"><span class="wl-tier-k mono">AI AGENTS &amp; BUILDERS</span><b class="wl-tier-p">Remote MCP &amp; API</b></div>'
        f'<h3>Automate pre-deposit checks in your agent</h3>'
        f'<p>Run <code>pacta_scan_wallet_exposure</code> and <code>pacta_check_preflight</code> over keyless Streamable HTTP MCP or metered x402 REST.</p>'
        + U.button("MCP & API", href="../mcp/", variant="outline", size="default", attrs='data-cta="scan_mcp_docs"')
        + '</article></div>'
        f'<aside class="pd-preview" aria-label="Sample unlocked protocol breakdown">{scan_preview(idx, lk)}</aside>'
        f'</section>'
    )
    foot_note = (f'<section class="sec pd-how" id="how"><div class="wrap">'
                 f'<p class="note">{E(EDITORIAL_FIREWALL)} {E(EDITORIAL_SHORT)} Merged a public docs or on-chain fix? '
                 f'<a href="../request/?tier=community">Free factual re-verification within 7 days{ARR}</a></p></div></section>')
    main_inner = (
        f'<section class="sec pd-sec pd-sec-scan" id="checkout"><div class="wrap">{crumbs}'
        f'<div class="pd-funnel">{hero_scan}'
        f'<div class="pd-free-box" id="free-check" data-free-check>'
        f'{scan_checker(lk, idx)}</div>'
        f'{next_doors}{trust_scan}{scan_explainer_section()}</div></div></section>{foot_note}'
    )
    body = f"""<body>
{topbar("../", "scan/")}
<main id="main">
{main_inner}
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    title = "Free Wallet, Safe & Protocol Scanner: Who Can Change Your Contracts · Pacta"
    desc = "Paste any Ethereum or Base wallet, Gnosis Safe, or protocol to see who can change the contracts behind your positions, in 3 seconds — 100% free, read-only, no wallet or signup."
    img = f"{BASE_URL}/cards/x-card-scan19-1200x628.png"
    return head(title, desc, f"{BASE_URL}/scan/", prefix="../", og_title="Free wallet, Safe & protocol scanner: who can change the contracts behind your positions",
                image=img, image_size=SOCIAL_SIZE, extra=fc_miniapp_meta()) + "\n" + body


def seal_page(idx):
    """/seal/: kept 200 OK (zero broken links), reframed cleanly around Free 7-Day Post-Fix Re-Verification, Community Verification Pools,
    and Pre-Launch / Multi-Contract Suite Scope (zero $99 or $500 flagged-protocol speed-up pitches)."""
    lk = lookup_items()
    count_line = coverage_line(idx)
    n_proto = len(site_protocols(idx))
    n_eas = sum(1 for v in lk.values() if v.get("kind") == "protocol" and v.get("easAttested"))
    reg = idx["onchain_anchoring"]["commitment_registry"]
    crumbs = ('<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span>'
              '<span>Base-EAS Attestation &amp; Re-Verification</span></nav>')
    hero_seal = (
        f'<div class="pd-head pd-hero-explain"><span data-slot="badge" data-variant="info">For DeFi Protocols, Vault Curators &amp; Institutional LPs</span>'
        f'<h1 id="co-title">Reconcile your smart contract and security docs — attested on Base Mainnet EAS.</h1>'
        f'<p class="pd-lede">Flagged protocols never pay to clear a delta: merge a public docs or on-chain fix for free factual re-verification within 7 days. '
        f'Community members and curators can fund independent Verification Pools, and pre-launch teams can commission full multi-contract suite dossiers.</p>'
        f'<ul class="pd-proof" aria-label="Attestation guarantees">'
        f'<li><b>{n_proto} protocols indexed · {n_eas} Base-EAS verified</b></li>'
        f'<li><b>Free 7-Day Post-Fix Re-Verification</b></li>'
        f'<li><b>Dual-RPC + Independent Verifier</b></li></ul>'
        f'<div class="seal-precheck-bar"><span>Want to run a free 3-second authority check on your contract or Safe first?</span>'
        + U.button("Scan Contract Free", href="../scan/", variant="outline", size="sm", attrs='data-seal-free-first data-cta="seal_scan_free"')
        + '</div></div>'
    )
    paths_seal = (
        '<section class="seal-paths" id="seal-paths" data-seal-paths>'
        '<div class="wl-ladder">'
        '<article class="wl-tier wl-tier-primary" data-seal-path="free-7d">'
        '<div class="wl-tier-top"><span class="wl-tier-k mono">MERGED A FIX · FREE</span><b class="wl-tier-p">$0 · Within 7 Days</b></div>'
        '<h3>Free Post-Fix Factual Re-Verification</h3>'
        '<p>Free factual re-verification within 7 days whenever a protocol merges a public docs or on-chain fix. Your Base-EAS badge updates automatically once verified at a finalized block.</p>'
        + U.button("Submit Updated Docs", href="../request/?tier=community", variant="default", size="lg",
                   attrs='id="seal-free-btn" data-seal-community-link data-cta="seal_free_7d"')
        + '</article>'
        '<article class="wl-tier" data-seal-path="sponsor-pool">'
        '<div class="wl-tier-top"><span class="wl-tier-k mono">COMMUNITY &amp; CURATORS</span><b class="wl-tier-p">$50 minimum pool</b></div>'
        '<h3>Fund a Protocol Verification Pool</h3>'
        '<p>A $50 minimum pool funds an independent check ($25 fixed verification fee, the rest to the researcher), or $150 per protocol for a sweep of 20 or more. Opening soon: reservation or invoice only.</p>'
        + U.button("Fund a Pool", href="../bounties/#sponsor-pool", variant="outline", size="lg",
                   attrs='id="seal-pool-btn" data-seal-pool-link data-cta="seal_sponsor_pool"')
        + '</article>'
        '<article class="wl-tier" data-seal-path="suite-dossier">'
        '<div class="wl-tier-top"><span class="wl-tier-k mono">PRE-LAUNCH &amp; SUITES · 24H SLA</span><b class="wl-tier-p">$2,500–$5,000</b></div>'
        '<h3>Full Multi-Contract Suite Dossier</h3>'
        '<p>Pre-launch or collateral-onboarding diligence across proxies, Safes, governors and timelocks, with Safe Transaction Builder JSON and a Curator Diligence Dossier (PDF + JSON).</p>'
        + U.button("Request a Dossier", href="../request/?tier=clearance", variant="outline", size="lg",
                   attrs='id="seal-dossier-btn" data-seal-dossier-link data-cta="seal_suite_dossier"')
        + '</article></div></section>'
    )
    foot_note = (f'<section class="sec pd-how" id="how"><div class="wrap">'
                 f'<p class="note">{E(EDITORIAL_FIREWALL)} {E(EDITORIAL_SHORT)} Need formal PDF invoicing or continuous SLA monitoring? '
                 f'<a href="../request/">Enterprise &amp; protocol diligence{ARR}</a></p></div></section>')
    main_inner = (
        f'<section class="sec pd-sec" id="checkout"><div class="wrap">{crumbs}'
        f'<div class="pd-funnel">{hero_seal}{paths_seal}{seal_how_section(seal_preview(idx, lk))}</div></div></section>{foot_note}'
    )
    body = f"""<body>
{topbar("../", "seal/")}
<main id="main">
{main_inner}
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    title = "Base-EAS Attestation & Free 7-Day Post-Fix Re-Verification · Pacta"
    desc = "Reconcile your Ethereum or Base smart contract and security docs: free factual re-verification within 7 days of a merged fix, community Verification Pools, or pre-launch suite dossiers."
    img = f"{BASE_URL}/cards/x-card-seal99-1200x628.png"
    return head(title, desc, f"{BASE_URL}/seal/", prefix="../", og_title="Base-EAS Attestation & Free 7-Day Post-Fix Re-Verification",
                image=img, image_size=SOCIAL_SIZE) + "\n" + body


def product_page(idx, sku):
    """/webhook/: Free 30-day pilot capture at top + single-SKU $49/mo Base USDC Safe Guard checkout below."""
    c, lk = CHECKOUT[sku], lookup_items()
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    crumbs = (f'<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span>'
              f'<a href="../#pricing">Pricing</a><span aria-hidden="true">/</span><span>{E(c["label"])}</span></nav>')
    picks = "".join(U.button(E(label), variant="outline", size="sm", cls="pick",
                             attrs=(f'data-co-pick data-chain="{lk[s]["chain"]}" data-address="{lk[s].get("controllerAddress") or ""}" '
                                    f'data-protocol="{E(lk[s]["name"])}" aria-pressed="false"'))
                    for label, s in WEBHOOK_PICKS)
    fields = (f'<div class="try"><div class="try-row" role="group" aria-label="Quick picks"><span class="try-l">Watch:</span>{picks}</div></div>'
              + '<div class="co-row"><div class="field co-chain-f"><label for="co-chain">Chain</label><select id="co-chain" name="target_chain">'
                '<option value="ethereum" selected>Ethereum</option><option value="base">Base</option></select></div>'
                '<div class="field"><label for="co-watch">Timelock, Safe or protocol</label>'
                '<input id="co-watch" type="text" maxlength="80" spellcheck="false" autocapitalize="off" '
                'placeholder="0x… address, or a protocol (Lombard)" aria-describedby="co-watch-hint co-target-err">'
                '<p class="hint" id="co-watch-hint" data-co-watch-hint>Pick a protocol above or paste a timelock or Safe address.</p>'
                '<p class="form-message" id="co-target-err" data-slot="form-message" hidden></p></div></div>'
                '<input type="hidden" id="co-target" name="target_address"><input type="hidden" id="co-docs" name="protocol_or_docs">'
              + field("co-contact", "webhook_or_contact", "Alert destination", "Webhook URL or @telegram",
                      help_="Kept private for delivery, never published."))
    preview = webhook_preview()
    deeplinks = mobile_wallet_deeplinks(c)
    form = (f'<form class="co" id="co-form" novalidate autocomplete="off" data-api="{E(ORDERS_VERIFY_API)}" data-sku="{sku}" data-chain-id="{CHECKOUT_CHAIN_ID}">'
            f'{fields}<div class="co-cta">'
            + U.button(f'<span>{E(c["cta"])}</span>', variant="default", size="lg", attrs='id="co-wallet" data-co-pay')
            + '<span class="req-status" id="co-status" role="status" aria-live="polite"></span></div>'
            f'<p class="co-assure">One exact USDC transfer on Base. No approvals, no allowances, no account.</p>'
            f'{deeplinks}{manual_drawer(c)}{receipt_card()}'
            f'<noscript><p class="note">Paying needs JavaScript. Without it, open the manual transfer above and send the transaction hash '
            f'through the <a href="../request/">request form</a> or to {CONTACT}.</p></noscript></form>')

    head_ = (f'<div class="pd-head"><span data-slot="badge" data-variant="info">{E(c["badge"])}</span><h1 id="co-title">{E(c["h1"])}</h1>'
             f'<p class="pd-lede">{E(c["lede"])}</p><p class="pd-price"><b>{E(c["price"])}</b><span>{E(c["unit"])}</span></p></div>')
    pilot_top = watch_pilot_box("../", heading="Start a free 30-day alert pilot (no wallet required)", id_attr="watch-pilot", compact=True)
    steps = (f'<section class="sec pd-how" id="how"><div class="wrap"><ol class="pd-steps">'
             f'<li><b>1 · Enter the target</b><span>The contract, Safe or protocol, and where to deliver.</span></li>'
             f'<li><b>2 · Start 30-day free pilot or pay {E(c["amount"])} USDC on Base</b><span>Enable the free pilot above in one click, or settle a paid monthly Safe Guard directly on Base.</span></li>'
             f'<li><b>3 · Receive pre-execution alerts</b><span>Alerts fire before queued timelock upgrades or Safe signer rotations execute.</span></li></ol>'
             f'<p class="note">{E(EDITORIAL_FIREWALL)} {E(EDITORIAL_SHORT)} Need institutional multi-vault watch SLAs ($500–$2,500 / month)? '
             f'<a href="../request/?tier=continuous">Enterprise &amp; allocator monitoring{ARR}</a></p></div></section>')
    main_inner = (
        f'<section class="sec pd-sec" id="checkout"><div class="wrap">{crumbs}'
        f'{pilot_top}'
        f'<div class="pd" style="margin-top:24px"><div class="pd-main">{head_}{form}</div><aside class="pd-preview" aria-label="What the payment unlocks">{preview}</aside></div>'
        f'</div></section>\n{steps}'
    )

    body = f"""<body>
{topbar("../", c["route"] + "/")}
<main id="main">
{main_inner}
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    img = f"{BASE_URL}/cards/{c['card']}" if c["card"] else f"{BASE_URL}/og-preview.png"
    return head(c["title"], c["desc"], f"{BASE_URL}/{c['route']}/", prefix="../", og_title=c["title"].rsplit(" · Pacta", 1)[0], image=img,
                image_size=SOCIAL_SIZE) + "\n" + body


WATCH_PAGE_LEDE = ("Automated paid webhook delivery is not active yet, so nothing is sold here. Start the free 30-day alert pilot below "
                   "or subscribe to the live timelock RSS / Atom feed. No payment is collected.")


def watch_page(idx):
    """/webhook/: the free timelock & signer watchlist: the existing 30-day pilot form and the RSS / Atom feed. No price, no checkout."""
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    crumbs = ('<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span>'
              '<a href="../#pricing">Pricing</a><span aria-hidden="true">/</span><span>Timelock &amp; Signer Watchlist</span></nav>')
    head_ = ('<div class="pd-head"><span data-slot="badge" data-variant="info">Free 30-day pilot · RSS / Atom feed</span>'
             '<h1 id="co-title">Timelock &amp; Signer Watchlist</h1>'
             f'<p class="pd-lede">{E(WATCH_PAGE_LEDE)}</p>'
             f'<p class="hero-routes"><span><a href="../feed.xml" data-cta="watch_feed">Subscribe via RSS / Atom (feed.xml){ARR}</a></span>'
             f'<span><a href="../radar/">Open the timelock radar{ARR}</a></span></p></div>')
    pilot = watch_pilot_box("../", heading="Start a free 30-day alert pilot (no wallet required)", id_attr="watch-pilot", compact=True)
    body = f"""<body>
{topbar("../", "webhook/")}
<main id="main">
<section class="sec pd-sec" id="watch"><div class="wrap">{crumbs}{head_}{pilot}</div></section>
<section class="sec pd-how" id="how"><div class="wrap"><p class="note">{E(EDITORIAL_FIREWALL)} {E(EDITORIAL_SHORT)} Need institutional multi-vault watch SLAs ($500–$2,500 / month)? <a href="../request/?tier=continuous">Enterprise &amp; allocator monitoring{ARR}</a></p></div></section>
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    return head("Timelock & signer watchlist (free 30-day pilot) · Pacta",
                "A free 30-day alert pilot and the live timelock RSS / Atom feed for queued timelock operations and Safe signer changes on "
                "Ethereum and Base. No payment collected.", f"{BASE_URL}/webhook/", prefix="../", og_title="Timelock & signer watchlist (free)",
                image=f"{BASE_URL}/og-preview.png", image_size=SOCIAL_SIZE) + "\n" + body


MINIAPP_PRESETS = [
    ("Moonwell (Base)", "base", "0xfBb21d0380beE3312B33c4353c8936a0F13EF26C", "moonwell-lending-base"),
    ("USDC (Base)", "base", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "circle-usdc"),
    ("Aerodrome (Base)", "base", "0x420DD381b31aEf6683db6B902084cB0FFECe40Da", "aerodrome-finance-base"),
    ("Stader ETHx (Eth)", "ethereum", "0xA35b1B31Ce002FBF2058D22F30f95D405200A15b", "stader-labs-ethx"),
]


def fc_miniapp_meta(target_url=None):
    """Farcaster Mini-App v1 (fc:miniapp) + Frame v2 (fc:frame) JSON embed tags."""
    u = target_url or f"{BASE_URL}/miniapp/"
    img = f"{BASE_URL}/miniapp-preview.png"
    splash = f"{BASE_URL}/logo-512.png"
    mini = {
        "version": "1",
        "imageUrl": img,
        "button": {
            "title": "Check Contract Safety",
            "action": {
                "type": "launch_miniapp",
                "name": "Pacta Control-Plane Check",
                "url": u,
                "splashImageUrl": splash,
                "splashBackgroundColor": "#0a0b0d",
            },
        },
    }
    frame = {
        "version": "1",
        "imageUrl": img,
        "button": {
            "title": "Check Contract Safety",
            "action": {
                "type": "launch_frame",
                "name": "Pacta Control-Plane Check",
                "url": u,
                "splashImageUrl": splash,
                "splashBackgroundColor": "#0a0b0d",
            },
        },
    }
    return (f'<meta name="fc:miniapp" content="{E(json.dumps(mini, separators=(",", ":")))}">'
            f'<meta name="fc:frame" content="{E(json.dumps(frame, separators=(",", ":")))}">')


def farcaster_manifest_json():
    """docs/.well-known/farcaster.json: Farcaster Mini-App v1 + Coinbase Base App manifest."""
    app_cfg = {
        "version": "1",
        "name": "Pacta Control-Plane Check",
        "homeUrl": f"{BASE_URL}/miniapp/",
        "iconUrl": f"{BASE_URL}/logo-512.png",
        "imageUrl": f"{BASE_URL}/miniapp-preview.png",
        "buttonTitle": "Check Contract Safety",
        "splashImageUrl": f"{BASE_URL}/logo-512.png",
        "splashBackgroundColor": "#0a0b0d",
        "subtitle": "Docs vs Chain DeFi Verdicts",
        "description": "Block-pinned Base and Ethereum control-plane verdicts: check who can upgrade, pause or drain a DeFi contract before depositing.",
        "primaryCategory": "developer-tools",
        "tags": ["defi", "security", "base", "timelock", "x402"],
        "heroImageUrl": f"{BASE_URL}/miniapp-preview.png",
        "tagline": "Docs drift. The chain doesn't.",
        "ogTitle": "Pacta Control-Plane Check",
        "ogDescription": "Instant Base & Ethereum control-plane verdicts + 1-tap Base USDC deep scans.",
        "ogImageUrl": f"{BASE_URL}/miniapp-preview.png",
    }
    doc = {
        "accountAssociation": {
            "header": "",
            "payload": "",
            "signature": "",
        },
        "baseBuilder": {
            "allowedAddresses": [
                "0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09",
                CHECKOUT_TREASURY,
            ],
        },
        "_signingNote": "Populate accountAssociation.{header,payload,signature} at production promotion via Farcaster Domain Manifest signing for pacta.wtf.",
        "miniapp": app_cfg,
        "frame": dict(app_cfg),
    }
    return json.dumps(doc, indent=2) + "\n"


def miniapp_page(idx):
    """docs/miniapp/index.html: mobile-first Farcaster / Coinbase Base App Mini-App (zero 'unsafe-inline' CSP)."""
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    lk = lookup_items()
    sample = lk["moonwell-lending-base"]
    b_label = LK.BADGE_TIERS["parameter_delta"][0]
    b_w = (len(LK.BADGE_TITLE) + len(b_label)) * 7 + 24
    chips = "".join(
        f'<button type="button" class="ma-chip" data-ma-preset data-chain="{ch}" data-address="{addr}" data-slug="{slug}">{E(lbl)}</button>'
        for lbl, ch, addr, slug in MINIAPP_PRESETS
    )
    mm_init = "https://metamask.app.link/dapp/pacta.wtf/miniapp/"
    cb_init = "https://go.cb-wallet.com/dapp?cb_url=" + urllib.parse.quote("https://pacta.wtf/miniapp/", safe="")
    body = f"""<body>
{topbar("../", "miniapp/")}
<main id="main">
<section class="sec ma-sec">
<div class="wrap ma-wrap">
<div class="ma-shell" id="ma-root" data-miniapp data-api="{E(API)}" data-verify-api="{E(ORDERS_VERIFY_API)}" data-lookup="../api/v1/lookup.json" data-badges="../badges/">
  <header class="ma-head">
    <div class="ma-topline">
      <span data-slot="badge" data-variant="info">Base · Farcaster Mini-App</span>
      <span class="ma-wallet-pill mono" id="ma-wallet-pill" data-state="detecting">Ready · Base + Ethereum</span>
    </div>
    <h1>Control-Plane Check</h1>
    <p class="ma-sub">Verify who can upgrade, pause or change any Base or Ethereum contract before depositing.</p>
  </header>

  <form class="ma-card" id="ma-check-form" novalidate autocomplete="off">
    <div class="ma-bar">
      <div class="ma-seg" role="radiogroup" aria-label="Target chain">
        <button type="button" class="ma-seg-btn" role="radio" aria-checked="true" data-ma-chain="base">Base</button>
        <button type="button" class="ma-seg-btn" role="radio" aria-checked="false" data-ma-chain="ethereum">Ethereum</button>
      </div>
      <span class="ma-free-tag mono">50 free / day · no key</span>
    </div>
    <input type="hidden" id="ma-chain" name="chain" value="base">
    <div class="ma-input-row">
      <label class="sr-only" for="ma-address">Contract or Safe address</label>
      <input id="ma-address" name="address" type="text" class="mono" spellcheck="false" autocapitalize="off"
             value="0xfBb21d0380beE3312B33c4353c8936a0F13EF26C" placeholder="0x… contract, token or Safe">
      <button data-slot="button" data-variant="default" data-size="default" type="submit" id="ma-submit">Check</button>
    </div>
    <p class="form-message" id="ma-addr-err" data-slot="form-message" hidden></p>
    <div class="ma-presets" role="group" aria-label="Live contract presets">
      <span class="ma-presets-l">Tap live:</span>{chips}
    </div>
  </form>

  <section class="ma-card ma-verdict" id="ma-verdict" aria-live="polite" data-ma-status="ADVERSE DELTA">
    <div class="ma-v-head">
      <div>
        <span class="ma-status-pill" id="ma-v-pill" data-tone="delta">ADVERSE DELTA</span>
        <h2 id="ma-v-title">{E(sample["name"])} · Base</h2>
      </div>
      <img class="cp-badge" id="ma-v-badge" src="../badges/moonwell-lending-base.svg" alt="{E(LK.BADGE_TITLE)}: {E(b_label)}" width="{b_w}" height="20">
    </div>
    <p class="ma-v-summary" id="ma-v-summary">Published docs vs live Base control plane: tap Check or pick any preset above to run a fresh block-pinned read.</p>
    <dl class="ma-v-grid" id="ma-v-grid">
      <div><dt>Target</dt><dd class="mono" id="ma-v-target">base:0xfBb2…EF26C</dd></div>
      <div><dt>Controller</dt><dd class="mono" id="ma-v-ctrl">Timelock / Multisig</dd></div>
      <div><dt>Timelock floor</dt><dd class="mono" id="ma-v-delay">Indexed record (tap Check for live)</dd></div>
      <div><dt>Provenance</dt><dd id="ma-v-prov"><a href="../protocols/moonwell-lending-base/">Published scorecard</a></dd></div>
    </dl>
  </section>

  <section class="ma-card ma-upgrade" id="ma-upgrade" aria-label="1-tap Base USDC upgrades">
    <div class="ma-up-head">
      <h2>Need deeper diligence or a 24h Base EAS seal?</h2>
      <span class="mono ma-up-net">Base USDC · Chain 8453</span>
    </div>
    <div class="ma-up-btns">
      <button type="button" class="ma-buy-btn ma-buy-primary" id="ma-buy-scan" data-ma-buy="instant-scan-19">
        <span class="ma-buy-t">Unlock Full Scan ($19 Base USDC)</span>
        <span class="ma-buy-s">2-RPC proxy, Safe signer &amp; role report + Base EAS ticket</span>
      </button>
      <button type="button" class="ma-buy-btn ma-buy-secondary" id="ma-buy-seal" data-ma-buy="reverify-seal-99">
        <span class="ma-buy-t">24h Mainnet EAS Seal ($99 Base USDC)</span>
        <span class="ma-buy-s">Maintainer + independent verifier docs-vs-chain attestation</span>
      </button>
    </div>
    <div class="ma-contact-row" id="ma-contact-row">
      <label for="ma-contact">Delivery @telegram, email or webhook <span class="opt">(optional for $19 · required for $99 Seal)</span></label>
      <input id="ma-contact" type="text" maxlength="200" spellcheck="false" placeholder="@handle or team@protocol.xyz">
      <p class="form-message" id="ma-contact-err" data-slot="form-message" hidden></p>
    </div>
    <p class="ma-quote" id="ma-quote">Deterministic quote: exact USDC transfer on Base to Pacta Treasury <span class="addr-pill mono" title="{CHECKOUT_TREASURY}">0x4348…Ed14</span> · zero approvals.</p>
    <p class="req-status" id="ma-pay-status" role="status" aria-live="polite"></p>

    <div class="co-result" id="ma-receipt" tabindex="-1" hidden>
      <div class="co-r-head"><span data-slot="badge" data-variant="success">Verified on Base</span><b id="ma-r-sku">Instant Scan · 19.00 USDC</b></div>
      <dl class="co-r-dl">
        <div><dt>Order</dt><dd class="mono" id="ma-r-order">—</dd></div>
        <div><dt>Settlement</dt><dd id="ma-r-tx">—</dd></div>
      </dl>
      <pre class="pv-pre" id="ma-r-json"></pre>
    </div>

    <details class="co-manual ma-manual" id="ma-manual">
      <summary>No injected wallet or paid from Safe/CLI? Open in Base Wallet or verify tx hash</summary>
      <div class="co-manual-b">
        <div class="co-dl-btns">
          <a class="co-dl-btn" href="{E(cb_init)}" rel="noopener" data-ma-coinbase data-cta="wallet_coinbase"><span>Open in Coinbase Wallet</span>{EXT}</a>
          <a class="co-dl-btn" href="{E(mm_init)}" rel="noopener" data-ma-metamask data-cta="wallet_metamask"><span>Open in MetaMask</span>{EXT}</a>
        </div>
        <div class="ma-tx-row">
          <label class="sr-only" for="ma-tx">Base USDC transaction hash</label>
          <input id="ma-tx" type="text" class="mono" maxlength="68" spellcheck="false" placeholder="0x… 64-hex Base payment tx hash">
          <select id="ma-manual-sku" aria-label="Order tier">
            <option value="instant-scan-19">$19 Scan</option>
            <option value="reverify-seal-99">$99 Seal</option>
          </select>
          <button data-slot="button" data-variant="outline" data-size="sm" type="button" id="ma-verify-btn">Verify tx</button>
        </div>
      </div>
    </details>
  </section>
</div>
</div>
</section>
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    return head(
        "Pacta Control-Plane Check · Base & Farcaster Mini-App",
        "Instant Base and Ethereum DeFi control-plane verdicts: check proxy upgradeability, Safe thresholds, and timelock delays, with 1-tap Base USDC deep-scans.",
        f"{BASE_URL}/miniapp/",
        prefix="../",
        og_title="Pacta Control-Plane Check",
        image=f"{BASE_URL}/miniapp-preview.png",
        image_size=(1200, 800),
        extra=fc_miniapp_meta(),
    ) + "\n" + body


def maintainer_card(name, slug, forum=None, home="../../"):
    """Delta / RPC-observed protocol pages: one maintainer & allocator card, after the editorial firewall. Left: sponsor an independent
    Verification Pool (the card's one solid button) or run a free wallet scan; right: free 7-day fix re-verification and pre-launch dossier."""
    return (f'<section class="memo-sec convert maint" id="seal-cta"><span class="label">For maintainers, curators &amp; allocators</span>'
            f'<div class="maint-grid"><div class="maint-paid"><h2>Fund a Verification Pool or scan exposure</h2>'
            f'<p>Sponsor a community Verification Pool for {E(name)} ($50 minimum pool, $25 fixed verification fee; opening soon, reservation or invoice only) '
            f'or scan any wallet holding {E(name)}. {E(SEAL_GUARANTEE)}</p><div class="convert-cta">'
            + U.button("Fund a Pool", href=f"{home}bounties/?protocol={slug}#sponsor-pool", variant="default", attrs='data-cta="sponsor_pool"')
            + U.button("Scan Free", href=f"{home}scan/", variant="outline", attrs='data-cta="scan_free"')
            + '</div></div><div class="maint-free" id="issuer-clearance">' + clearance_body(name, slug, forum, home, dossier="outline")
            + '</div></div></section>\n')


# A protocol whose published name does not slug to its published slug (an RPC-pinned page converted to EAS-attested keeps
# both its name and its /protocols/ slug, so its graph anchor and page never change).
SLUG_OVERRIDES = {"Frax Ether (frxETH / sfrxETH)": "frax-ether-sfrxeth", "Re Protocol (reUSD / reUSDe)": "re",
                  "Balancer V2 Vault & TimelockAuthorizer": "balancer-v2-vault-timelock",
                  # Sprint 23 conversions keep their published RPC-pinned slugs
                  "Uniswap V3 & Governance Timelock": "uniswap-governance-timelock", "Reserve Protocol (eUSD RToken)": "reserve-protocol-rtoken",
                  # Sprint 24 conversion keeps its published RPC-pinned slug
                  "Centrifuge V3 Root (Base)": "centrifuge-liquidity-pools-base",
                  # Sprint 25 conversion keeps its published RPC-pinned slug
                  "Superform Core v2 (Base)": "superform-v2-base",
                  "Safe Smart Account (v1.4.1 Singleton)": "safe-singleton-core", "Origin Protocol (SuperOETHb Base)": "origin-superoeth-base"}


def protocol_slug(name):
    return SLUG_OVERRIDES.get(name) or re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def protocol_groups(idx):
    groups = {}
    for e in idx["entries"]:
        groups.setdefault(e["protocol"], []).append(e)
    return {k: sorted(v, key=lambda e: (e["sprint"], e["id"])) for k, v in sorted(groups.items(), key=lambda kv: kv[0].lower())}


def radar_for(name, radar):
    """Radar items whose protocol name appears in this protocol's name as whole words ("Cap" never matches "K3 Capital")."""
    key = name.lower()
    return [it for it in radar["items"] if re.search(r"(?<![a-z0-9])" + re.escape(it["protocol"].lower()) + r"(?![a-z0-9])", key)]


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
        rows += (f'<tr><td><a href="{E(d["url"])}" target="_blank" rel="noopener nofollow">{E(d["title"])}{EXT}</a>'
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


# ---- issuer conversion callouts (briefs + protocol pages) ----
# /request/?tier=…&protocol=<slug>[&forum=<url>][&settlement=invoice]: app.js prefills the request builder from these
# (closed enums, sanitised text, .value only). Aligned records never get a delta-remediation pitch.
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# radar briefs -> the protocol page of the issuer they concern (the request builder checks that protocol)
BRIEF_PROTOCOL = {"ethena-ops-0x0ca0-0x1fe5": "ethena-usde-susde", "etherfi-op-0x244e": "ether-fi-core-eeth-weeth",
                  "treehouse-op-0x2f11": "treehouse-tree-teth", "lombard-ops-0xceee-0x2f2a-0x6404": "lombard-lbtc",
                  "beefy-base-op-0x3302": "beefy-finance-base", "ethena-ops-0xb028-0xca05-0x108e-0x070a": "ethena-usde-susde",
                  "yearn-v3-op-0x2a14": "yearn-v3", "etherfi-liquid-op-0xf0fb": "ether-fi-liquid-veda-boringvault",
                  "lombard-op-0xd07f": "lombard-lbtc", "cap-op-0x3397": "cap", "compound-v3-op-0x86b4": "compound-v3-comet",
                  "lista-lending-op-0x21df": "lista-lending"}


def request_href(tier, slug, forum=None, settlement=None, home="../../"):
    assert tier in TRACKS and SLUG_RE.fullmatch(slug), (tier, slug)
    q = f"tier={tier}&protocol={slug}"
    if forum:
        assert forum.startswith("https://") and len(forum) <= 300 and "@" not in forum.split("/")[2], forum
        q += "&forum=" + urllib.parse.quote(forum, safe="")
    if settlement:
        assert settlement in SETTLEMENT
        q += "&settlement=" + settlement
    return f"{home}request/?{q}"


def is_aligned_page(entries):
    """Only pages whose every record is an EAS-attested aligned_baseline get the maintenance (not the clearance) callout."""
    return all(e["classification"] == "aligned_baseline" and not is_pinned(e) for e in entries)


DOSSIER_CTA = "Request a dossier"
FREE_NOTIFY_CTA = "Submit updated docs"


def clearance_body(name, slug, forum=None, home="../../", dossier="default"):
    """The issuer path: free factual re-verification within 7 days of a merged fix with equal standing next to the pre-launch/suite dossier,
    which buys verification work, never an outcome. U7: two- to three-word CTAs."""
    return (f'<h2>Maintaining {E(name)}? Verify and reconcile the record</h2>'
            f'<p>Two paths, both public. Free factual re-verification within 7 days whenever a protocol merges a public docs or on-chain fix; '
            f'anyone can submit it. A Full Control-Plane Dossier ({E(CLEARANCE_PRICE)}, 24h SLA) covers pre-launch or multi-contract suite diligence '
            f'across proxies, Safes and timelocks and prepares an upstream docs reconciliation PR. Either way the classification '
            f'changes only when the onchain state or the documentation aligns at a new finalized block.</p>'
            f'<div class="convert-cta">'
            + U.button(E(FREE_NOTIFY_CTA), href=request_href("community", slug, forum, home=home), variant="outline", attrs='data-cta="free_notify"')
            + U.button(E(DOSSIER_CTA), href=request_href("clearance", slug, forum, home=home), variant=dossier, attrs='data-cta="clearance"')
            + f'</div><p class="s">Need procurement paperwork? <a href="{E(request_href("clearance", slug, forum, "invoice", home))}" '
              f'data-cta="clearance_invoice">Request a commercial invoice (PDF)</a>.</p>')


def clearance_callout(name, slug, forum=None, home="../../"):
    """Issuer path on the decoded briefs (protocol pages fold it into maintainer_card)."""
    return (f'<section class="memo-sec convert" id="issuer-clearance"><span class="label">For issuers and maintainers</span>'
            + clearance_body(name, slug, forum, home) + '</section>\n')


def maintenance_callout(name, slug, home="../../"):
    """Aligned pages (M5): Continuous Control-Plane Monitoring keeps re-checking; it never buys or preserves a status."""
    return (f'<section class="memo-sec convert quiet" id="continuous-monitoring">'
            f'<h2>Operating {E(name)}? Add Continuous Control-Plane Monitoring</h2>'
            f'<p>Continuous Control-Plane Monitoring ({E(MONITORING_PRICE)}) re-checks your control plane after governance proposals, signer rotations '
            f'and timelock upgrades, and refreshes the dossier and attestation. It does not buy a status: the result can still read Docs differ '
            f'whenever docs and chain diverge.</p>'
            f'<div class="convert-cta">' + U.button("Start monitoring", href=request_href("continuous", slug, home=home), variant="outline",
                                                    attrs='data-cta="continuous"')
            + f'<a href="{E(request_href("continuous", slug, settlement="invoice", home=home))}" data-cta="continuous_invoice">Invoice option</a></div></section>\n')


def snippet(text, title, label):
    return term(text, title, f"{label} ({title})")


_CARDS = {}


def card_for(idx, slug):
    """The scorecard of one published protocol (computed once per build for all protocols)."""
    if not _CARDS:
        _CARDS.update({c["slug"]: c for c in scorecards(idx)})
    return _CARDS[slug]


def grade_pill(card):
    import scorecard as SC
    lbl, v = GRADE_UI[card["grade"]]
    sub = '<span class="grade-sub">Reconciled</span>' if card["reconciled"] else ""
    return (f'<span class="grade g-{card["grade"]}" data-slot="badge" data-variant="{v}" title="{E(SC.GRADES[card["grade"]][1])}">'
            f'{lbl}</span>{sub}')


def factor_list(card):
    """A1: every factor carries a letter (S / M / W / —) next to its colour, and its state in words."""
    import scorecard as SC
    rows = "".join(f'<div data-factor="{f["key"]}" data-state="{f["state"]}"><dt><span class="fdot r-{f["state"]}" aria-hidden="true">'
                   f'{FACTOR_LETTER[f["state"]]}</span>{E(f["label"])}</dt>'
                   f'<dd><b>{E(SC.STATE_LABEL[f["state"]])}</b> · {E(f["value"])}'
                   + (f'<small class="ev">Evidence: {E(f["evidence"])}</small>' if f["evidence"] else "") + "</dd></div>" for f in card["factors"])
    return f'<dl class="factors">{rows}</dl>'


def recon_trail(card):
    """Resolution provenance (spec 3.4): initial finding -> verified resolution, when a record carries reconciledFrom."""
    if not card["reconciled"]:
        return ""
    def docs(p):
        out = []
        if p.get("docsCommit"):
            out.append(f'docs commit <code>{E(str(p["docsCommit"])[:12])}</code>')
        if p.get("docsSnapshot"):
            out.append(f'docs snapshot <code>{E(p["docsSnapshot"])}</code>'
                       + (f' (sha256 {E(short(p["docsSha256"], 10, 6))})' if p.get("docsSha256") else ""))
        return "".join(f" · {x}" for x in out)

    tos = card.get("reconciledTo") or [{} for _ in card["reconciledFrom"]]
    steps = ""
    for r, t in zip(card["reconciledFrom"], tos):
        steps += (f'<li><b>Initial finding</b> · block #{int(r["blockNumber"]):,} · Base EAS {E(short(r["easUid"], 10, 6))}{docs(r)}: {E(r.get("summary", ""))}</li>'
                  f'<li><b>Verified resolution</b> · block #{int(t.get("blockNumber") or card["pinnedBlock"]):,}'
                  f'{" · Base EAS " + E(short(t["easUid"], 10, 6)) if t.get("easUid") else ""}{docs(t)} · ALIGNED · Reconciled</li>')
    return f'<ol class="recon">{steps}</ol>'


def scorecard_section(card):
    import scorecard as SC
    svg = SC.rosette_svg(card["factors"], 72, card["name"], interactive=True)
    return (f'<section class="memo-sec scorecard" id="scorecard"><h2>Control-plane scorecard</h2>'
            f'<div class="sc-head">{svg}<p>{grade_pill(card)} <span>{E(SC.GRADES[card["grade"]][1])}</span></p></div>'
            + U.alert("", "Aligned means the docs are accurate, not that the protocol is low-risk. The control-strength graphic rates the controls themselves.",
                      icon_name="info") +
            f'{factor_list(card)}{recon_trail(card)}'
            f'<p class="s">Each slice is derived only from the pinned records on this page and their controller facts (<a href="../../api/v1/scorecards.json">/api/v1/scorecards.json</a>). '
            f'A hollow slice is <i>not determined</i> by the published evidence (never a guess); docs-vs-chain parity is <i>uncompared</i> for RPC-observed protocols. '
            f'<a href="../../methodology/">How to read it</a>.</p></section>\n')


def badge_embed(name, slug, tier):
    """Copyable Markdown / HTML for the live status badge (every tier; the badge always says exactly what Pacta verified)."""
    label = LK.BADGE_TIERS[tier][0]
    md = f"[![{LK.BADGE_TITLE}]({BASE_URL}/badges/{slug}.svg)]({BASE_URL}/protocols/{slug}/)"
    htm = f'<a href="{BASE_URL}/protocols/{slug}/"><img src="{BASE_URL}/badges/{slug}.svg" alt="{LK.BADGE_TITLE}: {label}" height="20"></a>'
    return f'{snippet(md, "Markdown", "Copy Markdown")}{snippet(htm, "HTML", "Copy HTML")}'


def badge_section(name, slug, tier):
    """Control-plane badge on protocol pages: an embed card when aligned, the amber status + clearance path when a delta.
    RPC-observed pages carry no badge card (their slate badge exists but makes no documentation claim)."""
    label = LK.BADGE_TIERS[tier][0]
    width = (len(LK.BADGE_TITLE) + len(label)) * 7 + 24
    img = f'<img class="cp-badge" src="../../badges/{slug}.svg" alt="{E(LK.BADGE_TITLE)}: {E(label)}" width="{width}" height="20">'
    live = f"{API}/v1/badges/{slug}.svg"
    if tier == "aligned":
        md = f"[![{LK.BADGE_TITLE}]({BASE_URL}/badges/{slug}.svg)]({BASE_URL}/protocols/{slug}/)"
        htm = f'<a href="{BASE_URL}/protocols/{slug}/"><img src="{BASE_URL}/badges/{slug}.svg" alt="{LK.BADGE_TITLE}: {label}" height="20"></a>'
        return (f'<section class="memo-sec badge-card" id="embed-badge"><h2>Embed Live Control-Plane Badge</h2>'
                f'<p class="badge-preview">{img}</p>'
                f'<p>Show {E(name)}\'s Base-EAS-attested <i>Aligned</i> control-plane status in a README, docs page or forum post. The badge links back to this record.</p>'
                f'{snippet(md, "Markdown", "Copy Markdown")}{snippet(htm, "HTML", "Copy HTML")}'
                f'<p class="s">Static badge: <code>{E(BASE_URL)}/badges/{E(slug)}.svg</code> (rebuilt with the site). Live edge badge: '
                f'<code>{E(live)}</code> (5-minute cache).</p></section>\n')
    if tier == "parameter_delta":
        href = request_href("clearance", slug, settlement="invoice")
        return (f'<section class="memo-sec badge-card delta" id="badge-status"><h2>Control-plane badge: Docs differ</h2>'
                f'<p class="badge-preview">{img}</p>'
                f'<p>This badge is amber because at least one Base-EAS-attested surface of {E(name)} differs from what the protocol documents. '
                f'It turns to the neutral <b>Aligned · Base EAS</b> shield only when the on-chain state or the documentation changes and '
                f'the two match at a new finalized block, whoever requests the re-check.</p>'
                f'<p><a class="btn" href="{E(request_href("community", slug))}" data-cta="badge_free_notify">{E(FREE_NOTIFY_CTA)} <span class="arr">{ARR}</span></a></p>'
                f'<p class="s">Embed this badge (it updates when the status changes):</p>{badge_embed(name, slug, tier)}'
                f'<p class="s">Badge: <code>{E(BASE_URL)}/badges/{E(slug)}.svg</code> · live: <code>{E(live)}</code>.</p></section>\n')
    return (f'<section class="memo-sec badge-card observed" id="badge-status"><h2>Control-plane badge: RPC-Observed</h2>'
            f'<p class="badge-preview">{img}</p>'
            f'<p>The slate badge states only what Pacta pinned on-chain; it makes no documentation claim until {E(name)} is compared with its '
            f'documentation and attested on Base.</p>{badge_embed(name, slug, tier)}'
            f'<p class="s">Badge: <code>{E(BASE_URL)}/badges/{E(slug)}.svg</code> · live: <code>{E(live)}</code>.</p></section>\n')


BOUNTY_SUBMISSIONS_DIR = os.path.join(ROOT, "bounties", "submissions")


def bounty_credit(slug, lb=None, sub_dir=None):
    """The merged Wave 1 catch whose fixture names this published protocol (pactaSlug), with its hunter / PR / payout from the
    settlement ledger; None when no merged fixture points here. A fixture's pactaSlug is set only once a Sprint indexes the protocol
    (tools/apply_sprint<N>_attestation.py), so the credit appears together with the attested records."""
    d = sub_dir or BOUNTY_SUBMISSIONS_DIR
    hits = []
    for f_name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f_name.startswith("slot-") and f_name.endswith(".json"):
            f = json.load(open(os.path.join(d, f_name), encoding="utf-8"))
            if f.get("pactaSlug") == slug:
                hits.append(f)
    if not hits:
        return None
    assert len(hits) == 1, f"{slug}: {len(hits)} merged Wave 1 fixtures name this protocol"
    lb = lb or load_leaderboard()
    s = next(x for x in lb["wave1Settlements"] if int(x["slot"]) == int(hits[0]["slot"]))    # the Slot #4 fixture writes "slot": "4"
    assert s["status"] == "verified" and hits[0].get("apacheGrant") is True, f"{slug}: credit needs a verified, Apache-2.0-granted catch"
    return {"slot": s["slot"], "hunter": s["hunter"], "pr": s["pr"], "payoutTxHash": s["payoutTxHash"] if tx_ok(s["payoutTxHash"]) else None}


def wave2_credits(slug, lb=None, claims=None):
    """The Wave 2 catches credited to this published protocol (bounties/leaderboard.json wave2Credits, written by the Sprint stamp
    that attests them), each with its merged fixture's hunter and its payout tx; [] when none."""
    lb = lb or load_leaderboard()
    mine = [c for c in lb.get("wave2Credits", []) if c["pactaSlug"] == slug]
    if not mine:
        return []
    by_file = {c["_file"]: c for c in (claims if claims is not None else load_wave2_claims())}
    paid = {p["fixture"]: p["payoutTxHash"] for p in lb["wave2Settlements"]}
    out = []
    for c in sorted(mine, key=lambda c: c["pr"]):
        f = by_file.get(c["fixture"])
        assert f is not None and f.get("apache2CommercialGrant") is True, f"{slug}: Wave 2 credit {c['fixture']} needs a merged, Apache-2.0-granted fixture"
        tx = paid.get(c["fixture"])
        out.append({"hunter": f["hunter"], "pr": c["pr"], "fixture": c["fixture"], "record": c["record"], "payoutTxHash": tx if tx_ok(tx) else None})
    return out


def research_credit_html(slug, credit, wave2=()):
    """Provenance section crediting the researchers (EAS-attested pages only; the records stay Pacta's own pinned re-reads): the
    Wave 1 catch (if any) and every Wave 2 catch credited to this protocol."""
    if not credit and not wave2:
        return ""
    tail = (f'Pacta then re-read every value below on two independent RPCs at its own Sprint pin and compared it with the '
            f'documentation; the classifications and the Base EAS attestation are Pacta\'s. ')
    paras = []
    if credit:
        h, pr, slot, tx = credit["hunter"], credit["pr"], credit["slot"], credit["payoutTxHash"]
        paid = (f' and paid $25.00 USDC (<a href="https://basescan.org/tx/{E(tx)}" target="_blank" rel="noopener" data-basescan-tx>tx {E(short(tx, 6, 4))}{EXT}</a>)'
                if tx else "")
        paras.append(f'<p>First reported by <a href="https://github.com/{E(h)}" target="_blank" rel="noopener">@{E(h)}</a> through the Pacta Wave 1 bounty '
                     f'(<a href="{E(REPO)}/pull/{int(pr)}" target="_blank" rel="noopener">Slot #{int(slot)}, PR #{int(pr)}</a>), merged under the Apache-2.0 '
                     f'grant{paid}. {tail}See <a href="../../leaderboard/">the leaderboard</a>.</p>')
    for c in wave2:
        h, pr, tx = c["hunter"], c["pr"], c["payoutTxHash"]
        paid = (f' and paid $1.00 USDC (<a href="https://basescan.org/tx/{E(tx)}" target="_blank" rel="noopener" data-basescan-tx>tx {E(short(tx, 6, 4))}{EXT}</a>)'
                if tx else "")
        paras.append(f'<p data-research-credit="{E(h)}" data-research-wave="2">Reported by <a href="https://github.com/{E(h)}" target="_blank" rel="noopener">@{E(h)}</a> '
                     f'through the Pacta Wave 2 pool (<a href="{E(REPO)}/pull/{int(pr)}" target="_blank" rel="noopener">PR #{int(pr)}</a>, fixture '
                     f'<code>{E(WAVE2["fixtureDir"])}/{E(c["fixture"])}</code>), merged under the Apache-2.0 commercial grant{paid}; credited on '
                     f'<a href="#{E(c["record"])}">{E(c["record"])}</a>. {tail}See <a href="../../leaderboard/">the leaderboard</a>.</p>')
    attr = f' data-research-credit="{E(credit["hunter"])}"' if credit else ""
    return (f'<section class="memo-sec" id="provenance"{attr}><h2>Provenance · research credit</h2>' + "".join(paras) + '</section>\n')


def protocol_page(name, entries, idx, radar, digest=None, slug=None):
    """Static, deterministic protocol safety record (no wall-clock time): every indexed surface with its pinned block.
    index.json Sprint records (Base-EAS-anchored) and RPC-pinned records (not EAS-attested) are labelled as such."""
    digest = load_forum_digest() if digest is None else digest
    slug = slug or protocol_slug(name)
    url = f"{BASE_URL}/protocols/{slug}/"
    # v4.5 item 16: each protocol page shares its own 1200 x 675 receipt card (docs/cards/<slug>.png, the same card the X feed posts)
    assert os.path.exists(os.path.join(DOCS, "cards", f"{slug}.png")), f"{slug}: docs/cards/{slug}.png missing"
    count_line = coverage_line(idx)
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
        eas_dd = "" if pinned else f'<dt>Attestation</dt><dd>{proof_html(e)}</dd>'   # EAS-attested records link their Base EAS UID
        doc_lbl = "Documentation (linked, not compared)." if pinned else "Documented."
        records += (f'<article class="memo-sec" id="{E(e["id"])}"><h2>{E(e["surface"])}</h2>'
                    f'<dl class="memo-meta"><dt>Status</dt><dd>{badge(e["classification"])}</dd>'
                    f'<dt>Target</dt><dd>{E(e["target_label"])} {hexref(e["target_contract"])} · {explorer_link(e, "address")}</dd>'
                    f'<dt>Pinned block</dt><dd>{ch} <span class="num">#{int(e["block_number"]):,}</span> · {explorer_link(e)} · {prov}</dd>'
                    f'<dt>Block hash</dt><dd>{hexref(e["block_hash"], 10, 6)}</dd>{eas_dd}{ctrl}</dl>'
                    f'<p><b>Observed onchain.</b> {prose(e["onchain_observed"])}</p>'
                    f'<p><b>{doc_lbl}</b> {prose(e["documented_reference"])}</p>'
                    f'{term(cast_line(e), "Reproduce on any archive node", "Copy the cast reproduction for " + e["surface"])}</article>\n')
    ops = ""
    for it in radar_for(name, radar):
        lis = "".join(f'<li><code class="mono">{E(o["op_id"])}</code> · {"ETA " + E(utc(o["eta"], True)) if o.get("eta") else "executed onchain (isOperationDone = true)"} · {state_badge(op_state(o), [o])}</li>'
                      for o in it["operations"])
        ops += (f'<article class="memo-sec"><h2>Queued timelock operations</h2><p>{E(it["title"])}. {E(it["summary"])}</p>'
                f'<p>Timelock {hexref(it["timelock"])} · {secs(it["min_delay_seconds"])} minimum delay · <a href="../../{E(it["brief"])}">Pre-execution brief{ARR}</a></p>'
                f'<ul>{lis}</ul></article>\n')
    provenance = ""
    if pinned:
        provenance = (f'<section class="memo-sec" id="provenance"><h2>Provenance</h2><p>RPC-pinned {"record" if n == 1 else "records"}: read over public '
                      f'JSON-RPC at the {chain_txt} block shown below and independently re-read at the same block by a second Pacta seat. '
                      f'{"It is" if n == 1 else "They are"} <b>not EAS-attested</b>: no sprint number, no summary document and no public attestation receipt. '
                      f'Status <b>Observed</b> (RPC-observed baseline): the onchain control plane is pinned at block height; whether it matches the '
                      f'protocol\'s documented parameters is <b>not assessed</b> here (the documentation is linked for reference). '
                      f'Machine-readable: <a href="../../api/v1/rpc-pinned.json">/api/v1/rpc-pinned.json</a>. The Base-EAS-attested Sprint records '
                      f'are in <a href="../../api/v1/index.json">/api/v1/index.json</a>.</p></section>\n')
    else:
        provenance = research_credit_html(slug, bounty_credit(slug), wave2_credits(slug))
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
    pin_clause = (f"with its controller and timelock state pinned to a canonical {chain_txt} block over archive JSON-RPC (not EAS-attested; "
                  f"documentation parameters are linked, not compared)" if pinned
                  else f"{'' if n == 1 else 'each '}pinned to a canonical {chain_txt} block and compared with what the protocol documents")
    codes = ", ".join(f'<span class="addr-pill mono" title="{t}">{short_addr(t)}</span>{copy_btn(t, "Copy", "Copy the contract address " + t)}'
                      if ADDR40.fullmatch(t) else f'<code class="mono">{E(t)}</code>' for t in targets)
    lede = (f'{n} indexed control-plane {"surface" if n == 1 else "surfaces"} for {E(name)}, {pin_clause}. '
            f'{"Contract" if len(targets) == 1 else "Contracts"}: {codes}{"" if targets and ADDR40.fullmatch(targets[-1]) else "."}')
    forum = first.get("governance_url") if pinned else None
    tier = "rpc_observed" if pinned else ("aligned" if is_aligned_page(entries) else "parameter_delta")
    badge_html = badge_section(name, slug, tier)
    if is_aligned_page(entries):
        callout = maintenance_callout(name, slug)
        foot = f'<a href="{E(request_href("continuous", slug))}">Continuous Control-Plane Monitoring · {E(MONITORING_PRICE)}{ARR}</a>'
    else:
        callout = maintainer_card(name, slug, forum)
        foot = f'<a href="{E(request_href("clearance", slug, forum))}">Request a dossier (24h SLA){ARR}</a>'
    live = live_check_tabs(first.get("chain", "ethereum"), first["target_contract"])
    body = f"""<body>
{topbar("../../", "protocols/")}
<main id="main" class="memo-wrap">
<nav class="crumbs" aria-label="Breadcrumb"><a href="../../">Pacta</a><span aria-hidden="true">/</span><a href="../">Protocols</a><span aria-hidden="true">/</span><span>{E(name)}</span></nav>
<article class="memo">
<header><span class="tier">{E(cat)}</span><h1>{E(title)}</h1>
<p class="lede">{lede}</p></header>
{what_differs_html(entries, seal_cta=not is_aligned_page(entries))}{scorecard_section(card_for(idx, slug))}<section class="memo-sec" id="live-check"><h2>Check it live (free)</h2><p>The pre-flight API re-reads the controller, proxy and capabilities of one contract at the latest block. No key, no wallet. The score rates that single contract, not the whole protocol.</p>
{live}</section>
{watch_pilot_box("../../", default_target=slug, heading=f"Watch {name} free (30-day alert pilot)", id_attr="watch-pilot", compact=True)}
{provenance}{governance_section(name, digest)}{records}{ops}{editorial_box()}{badge_html}{callout}</article>
<div class="memo-foot"><span>Read-only onchain analysis. Not investment advice. Exploit-sensitive vulnerabilities are never published here; they go through Immunefi or Cantina bounty programmes.</span>{foot}</div>
</main>
{footer(count_line, reg, "../../")}
<script type="application/ld+json">{ld_json}</script>
<script type="application/ld+json">{crumbs_json}</script>
</body></html>
"""
    return (head(f"{name} control-plane safety · Pacta", desc, url, prefix="../../", og_title=title, og_type="article",
                 image=f"{BASE_URL}/cards/{slug}.png", image_size=CARD_SIZE) + "\n" + body)


def briefs_block(prefix="../"):
    """The onboarding verification briefs, linked from /protocols/ (relative links from that page)."""
    return onboarding_section(load_onboarding()).replace('href="briefs/', f'href="{prefix}briefs/').replace('href="api/', f'href="{prefix}api/')


def protocols_index_page(idx, sp=None):
    """/protocols/: every published protocol page, filtered by the same Docs-vs-chain statuses and counts as the scorecards (M3/M4)."""
    sp = site_protocols(idx) if sp is None else sp
    c = counts(idx)
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    cards = {x["slug"]: x for x in scorecards(idx)}
    n_surf = sum(len(v["entries"]) for v in sp.values())
    n_pin = sum(len(v["entries"]) for v in sp.values() if v["pinned"])

    def prov(v):
        if v["pinned"]:
            return '<span class="muted">RPC-pinned</span>'
        ss = sorted({e["sprint"] for e in v["entries"]})
        return f'Sprint{"s" if len(ss) > 1 else ""} {", ".join(str(x) for x in ss)} · Base EAS'

    def attrs(n, v):
        chains = " ".join(sorted({e.get("chain", "ethereum") for e in v["entries"]}))
        cats = sorted({e["category"] for e in v["entries"]})   # every surface's category, so the text filter finds secondary ones too
        text = " ".join([n, v["slug"]] + cats + [chains] + [e["target_contract"] for e in v["entries"]]).lower()
        bk = " ".join(cards[v["slug"]]["baskets"])   # the canonical scorecard baskets (identical to /scorecards/ and scorecards.json)
        return f' data-ptier="{cards[v["slug"]]["grade"]}" data-pchains="{E(chains)}" data-pbaskets="{bk}" data-psearch="{E(text)}"'

    g = {k: sum(x["grade"] == k for x in cards.values()) for k in GRADE_UI}
    n_chain = {ch: sum(any(e.get("chain", "ethereum") == ch for e in v["entries"]) for v in sp.values()) for ch in ("ethereum", "base")}
    status = [("all", "All", len(sp)), ("delta", "Docs differ", g["delta"]), ("protective", "Protective", g["protective"]),
              ("aligned", "Aligned", g["aligned"]), ("observed", "Observed", g["observed"])]
    chain_pills = [("all", "All chains", len(sp)), ("ethereum", "Ethereum", n_chain["ethereum"]), ("base", "Base", n_chain["base"])]
    group = lambda kind, label, pills: (f'<div class="seg" data-slot="toggle-group" role="group" aria-label="{label}" data-pgroup="{kind}"><span class="seg-l">{label}</span>'
                                        + "".join(f'<button type="button" data-slot="toggle-group-item" data-pfilter-{kind}="{k}" aria-pressed="{"true" if k == "all" else "false"}">{E(lbl)}'
                                                  f' <span class="num">({cnt})</span></button>' for k, lbl, cnt in pills) + '</div>')
    tools = (f'<div class="ix-tools" data-pfilter-root><div class="search">{U.icon("search")}<label class="sr-only" for="proto-q">Filter protocols</label>'
             f'<input id="proto-q" type="search" placeholder="Filter by name, token, category or 0x address" autocomplete="off"></div>'
             f'{group("status", "Docs vs chain", status)}{group("chain", "Chain", chain_pills)}'
             f'{basket_pills("data-pfilter-basket")}'
             f'<button type="button" class="linkish" id="proto-clear" hidden>Clear all</button>'
             f'<span class="ix-count" id="proto-count" aria-live="polite">{len(sp)} of {len(sp)} protocols shown</span>'
             f'<p class="ix-active" id="proto-active" aria-live="polite"></p></div>'
             f'<div class="ix-empty" id="proto-empty" hidden></div>')
    rows = "".join(f'<tr{attrs(n, v)}><td><a href="{v["slug"]}/">{E(n)}</a></td><td>{E(v["entries"][0]["category"])}</td>'
                   f'<td>{" · ".join(sorted({CHAINS[e.get("chain", "ethereum")][0] for e in v["entries"]}))}</td><td class="num">{len(v["entries"])}</td>'
                   f'<td>{grade_pill(cards[v["slug"]])}</td><td>{prov(v)}</td></tr>' for n, v in sp.items())
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "Pacta by Fractal Neurons: protocol control-plane safety records", "numberOfItems": len(sp),
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{BASE_URL}/protocols/{v['slug']}/", "name": n}
                              for i, (n, v) in enumerate(sp.items())]}
    ld_json = json.dumps(ld, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    body = f"""<body>
{topbar("../", "protocols/")}
<main id="main">
<section class="sec"><div class="wrap">
<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span><span>Protocols</span></nav>
<div class="sec-head"><h1>Protocol safety records</h1>{fresh_pill(idx)}<p class="aside">{len(sp)} protocols · {n_surf} block-pinned surfaces</p></div>
<p class="sec-intro">Who can upgrade, pause or change each protocol, pinned to canonical Ethereum and Base blocks. The {c["records"]} attested checks are anchored on Base by EAS attestations; the {n_pin} RPC-pinned records are reproducible with <code>cast</code> but not yet attested. Check any other contract live and free with <code>/v1/check/preflight</code>.</p>
{U.alert("Aligned means the docs are accurate, not that the protocol is low-risk.", "", icon_name="info", cls="aligned-note")}
{tools}
<div class="tbl-wrap"><table class="ix" id="proto-table"><caption class="sr-only">Every published protocol: category, chain, number of pinned checks, docs-vs-chain status and provenance.</caption><thead><tr><th scope="col">Protocol</th><th scope="col">Category</th><th scope="col">Chain</th><th scope="col">Checks</th><th scope="col">Docs vs chain</th><th scope="col">Provenance</th></tr></thead><tbody>{rows}</tbody></table></div>
</div></section>
{briefs_block("../")}
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
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    n_protocols = len(site_protocols(idx) if sp is None else sp)
    claude = f"claude mcp add --transport http pacta {MCP_URL}"
    snippet = lambda label, value: f'<div class="qs-snip"><span class="qs-l">{label}</span><code class="mono">{E(value)}</code>{copy_btn(value, "Copy", "Copy the " + label + " MCP setting")}</div>'
    body = f"""<body>
{topbar("/")}
<main id="main" class="memo-wrap" data-nf>
<div class="crumbs"><a href="/">Pacta</a> / Page not found</div>
<article class="memo">
<header><span class="tier">404 · Not found</span><h1>This page does not exist</h1>
<p class="lede">The link may be old or mistyped. Everything Pacta publishes is free and one click away.</p></header>
<section class="memo-sec"><h2>Where to go</h2>
<dl class="deflist">
<div><dt><a href="/protocols/">Protocol safety records{ARR}</a></dt><dd>Block-pinned control-plane records for {n_protocols} DeFi protocols, each with a <code>cast</code> reproduction.</dd></div>
<div><dt><a href="/#scorecards">Run a free pre-flight check{ARR}</a></dt><dd>Who can upgrade, pause or change any contract on Ethereum or Base. No key, no wallet.</dd></div>
<div><dt><a href="/request/">Request a dossier{ARR}</a></dt><dd>Protocol teams &amp; curators: free 7-day fix re-verification, Verification Pools, $150/protocol wholesale sweeps, $2,500–$5,000 suite dossiers, or Continuous Control-Plane Monitoring.</dd></div>
<div><dt>For agents</dt><dd class="links"><a href="/llms.txt">llms.txt</a><a href="/SKILL.md">SKILL.md</a><a href="/.well-known/agent.json">agent.json</a><a href="/api/v1/index.json">/api/v1/index.json</a></dd></div>
</dl></section>
<section class="memo-sec"><h2>Remote MCP server (free)</h2>
<p>Six read-only inspection tools + one opt-in coverage / feature request tool (<code>pacta_submit_request</code>) over Streamable HTTP, zero install, led by <code>pacta_lookup_protocol</code> (resolve a protocol or token name first). Tool <code>pacta_check_preflight</code> runs the same check as the live checker on the homepage.</p>
{snippet("Any MCP client (Streamable HTTP)", MCP_URL)}{snippet("Claude Code", claude)}</section>
</article>
</main>
{footer(count_line, reg, "/")}
</body></html>
"""
    return head("Page not found · Pacta", "This page does not exist. Pacta: protocol docs vs. onchain controls for DeFi.", f"{BASE_URL}/404.html",
                prefix="/", og_title="Page not found · Pacta", robots=ROBOTS_META_404, canonical=False,
                early_script="/404-rescue.js") + "\n" + body


# ---- Website Edge v3 homepage (spec sections 2-4): six blocks, one centerpiece ------------------------------------------------
HOME_H1 = "Protocol docs drift. The chain doesn’t."
HOME_EYEBROW = "For DeFi risk curators & diligence teams"
HOME_SUB = ("Pacta reads who can upgrade, pause or change {n} DeFi protocols on Ethereum and Base, and flags where that differs from their "
            "docs. Every finding is pinned to a block and attested onchain.")
# v4.7 W1: the homepage previews 8 high-signal protocols, by severity: adverse deltas first, then one protective and two aligned
# references (the grades come from the data; build_site asserts the order). /scorecards/ and /protocols/ keep all of them.
FLAGSHIP = ["stader-labs-ethx", "yo-protocol", "moonwell-lending-base", "ethena-usde-susde", "axelar-network",
            "ethena-usdtb", "aave-v3-gho", "eigenlayer-core"]
GRADE_RANK = {"delta": 0, "protective": 1, "aligned": 2, "observed": 3}
# (slug, record id, label, "docs say", "chain says", tokens asserted in the documented / observed evidence)
# (slug, record id, label, "docs say", "chain says", tokens asserted in the documented / observed evidence)
RECEIPTS = [
    ("stader-labs-ethx", "stader-ethx-manager-safe-and-timelock", "Stader ETHx", "Manager Safe is 3-of-5", "Manager Safe is 3-of-6",
     ("3-of-5",), ("3-of-6",)),
    ("yo-protocol", "yo-protocol-approval-registry-owner-admin-safe-s22", "YO Protocol", "Vault caps are timelocked",
     "A 4-of-6 Safe, no delay", ("timelocked",), ("4-of-6", "not the YO Timelock")),
    ("moonwell-lending-base", "moonwell-pause-guardian-2of4-safe-s18", "Moonwell (Base)", "Pause needs a 3-of-5 council",
     "Pause guardian is a 2-of-4 Safe", ("3-of-5",), ("2-of-4",)),
]
MCP_REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.Fractal-Neurons/pacta"
GLAMA_URL = "https://glama.ai/mcp/servers/Fractal-Neurons/pacta"
EAS_SCHEMA_VIEW = "https://base.easscan.org/schema/view/0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83"
EDITORIAL_FIREWALL = "Pacta never sells grades."


HERO_PLACEHOLDER = "Aave, Lido or 0x address"   # <= 30 characters; the visible label above names the field


_PROTO_COUNT_CACHE = None


def _total_protocols():
    global _PROTO_COUNT_CACHE
    if _PROTO_COUNT_CACHE is None:
        idx_d = json.load(open(os.path.join(DOCS, "api", "v1", "index.json"), encoding="utf-8"))
        _PROTO_COUNT_CACHE = len(site_protocols(idx_d))
    return _PROTO_COUNT_CACHE


def hero_checker(examples="", prefix="", cap=None, label="Protocol, token or contract address", cta_variant="default", cta_label="Check protocol",
                 initial_out="", placeholder=None, extra_attrs="", visible_label=False):
    """U3/A3 + Protocol Select & Autocomplete Combobox: zero-type dropdown of featured gaps & top protocols with official logos,
    instant <2ms search across all indexed protocols & tickers, 1-click live check, and inline 0x + 40-hex paste support."""
    ph = placeholder or HERO_PLACEHOLDER
    n_p = _total_protocols()
    return (f'<div class="pf hero-pf" data-api="{API}" data-lookup="{prefix}api/v1/lookup.json"{extra_attrs}>'
            + (f'<label class="pf-field-l" for="pf-address">{E(label)}</label>' if visible_label else "")
            + f'<form class="checker" id="pf-form" novalidate autocomplete="off">'
            f'<label class="sr-only" for="pf-chain">Chain</label>'
            f'<div class="pf-chain-wrap">'
            f'<span class="pf-chain-dot" data-pf-chain-ico aria-hidden="true">{chain_icon_svg("ethereum")}</span>'
            f'<select id="pf-chain" name="chain"><option value="ethereum">Ethereum</option><option value="base">Base</option></select></div>'
            + ("" if visible_label else f'<label class="sr-only" for="pf-address">{E(label)}</label>')
            + f'<div class="pf-combo" data-pf-combo>'
            f'<span class="pf-combo-lead" data-pf-lead aria-hidden="true">{U.icon("search")}</span>'
            f'<input id="pf-address" type="text" name="address" role="combobox" aria-expanded="false" aria-controls="pf-listbox" '
            f'aria-autocomplete="list" placeholder="{E(ph)}" maxlength="80" spellcheck="false" '
            f'autocapitalize="off" aria-describedby="pf-help">'
            f'<div class="pf-sel-overlay" id="pf-sel-chip" data-pf-sel-chip hidden></div>'
            f'<button type="button" class="pf-clear-btn" id="pf-combo-clear" data-pf-clear aria-label="Clear selected protocol" hidden>×</button>'
            f'<button type="button" class="pf-toggle-btn" id="pf-combo-toggle" data-pf-toggle aria-label="Browse {n_p} protocols">'
            f'<span class="pf-toggle-lbl">Protocols</span>{U.icon("chevron-down")}</button>'
            f'<div class="pf-dropdown" id="pf-listbox" role="listbox" aria-label="Indexed protocols and tokens" hidden></div></div>'
            + U.button(f'<span class="spinner" aria-hidden="true" hidden></span><span data-pf-label>{E(cta_label)}</span>', variant=cta_variant,
                       size="lg", type_="submit", attrs='id="pf-submit"')
            + f'<p class="form-message" id="pf-addr-error" data-slot="form-message" hidden></p></form>'
            + (f'<p class="checker-cap" id="pf-help">{E(cap)}</p>' if cap else
               f'<p class="checker-cap" id="pf-help">Free, read-only check — select or type a protocol or token (Aave, Lido, Pendle, Moonwell, LBTC, ETHx), '
               f'or paste any 0x… contract address. No API key, no wallet. Runs when you press Check or pick an example below.</p>')
            +
            f'<noscript><p class="note">Without JavaScript, use the free API: <code>{E(CURL)} "{E(API)}/v1/check/preflight?chain=ethereum&amp;address=0x…"</code></p></noscript>'
            f'{examples}<div class="pf-out" id="pf-out" aria-live="polite">{initial_out}</div></div>')


def sc_drawer(c, prefix=""):
    import scorecard as SC
    p = c["probe"]
    n = c["records"]
    noun = ("attested check" if n == 1 else "attested checks") if c["easAttested"] else ("block-pinned check" if n == 1 else "block-pinned checks")
    meta = (f'{"Base EAS attested" if c["easAttested"] else "RPC-observed, not EAS-attested"} · {n} {noun} · pinned block #{c["pinnedBlock"]:,}')
    return (f'<tr class="sc-drawer" id="sc-d-{c["slug"]}" hidden><td colspan="5"><div class="sc-dr">'
            f'<div class="sc-ros">{SC.rosette_svg(c["factors"], 72, c["name"], interactive=True)}<span class="sc-meta">Hover or focus a slice</span></div>'
            f'<div><div class="sc-ev"><p class="sc-full"><b>Docs say: </b>{E(c["evidence"]["documented"])}</p>'
            f'<p class="sc-full"><b>{"Chain says: " if c["easAttested"] else "Chain (pinned; docs not compared): "}</b>{E(c["evidence"]["observed"])}</p></div>'
            f'{factor_list(c)}</div>'
            f'<p class="sc-meta">{meta}</p>'
            f'<div class="sc-live" data-probe-chain="{p["chain"]}" data-probe-target="{p["target_contract"]}" data-probe-kind="{p["check_type"]}" '
            f'data-probe-sos="{E(p["selector_or_slot"])}" data-probe-data="{E(p["repro_calldata"] or "")}" data-probe-sig="{E(p["call_signature"] or "")}"></div>'
            f'{term(cast_line(p), "Reproduce on any archive node", "Copy the cast reproduction for " + c["name"])}'
            f'<p class="links"><a href="{prefix}protocols/{c["slug"]}/">Full scorecard for {E(c["name"])}{ARR}</a></p></div></td></tr>')


_SHORT_SEARCH = {}   # slug -> search text with the record targets only (filled by scorecards())


def short_search(c):
    """The search text without the extra addresses (name, slug, category, tokens, record targets): the homepage's 16 static rows
    use it to stay inside the page budget; any homepage search hydrates every row from scorecards.json (full address index)."""
    return _SHORT_SEARCH.get(c["slug"], c["search"])


MOBILE_FIRST_ROWS = 8   # v4.7 W1: the 8-row preview shows in full below 640 px too (v4.5 kept 6 of 16 back)


def sc_tvl_rank_key(c):
    tvl = c.get("tvlUsd")
    return (GRADE_RANK[c["grade"]], -(tvl if isinstance(tvl, (int, float)) and tvl > 0 else -1), c["name"].lower())


def sc_row(c, prefix="", short=False, mobile_more=False):
    """U4/A2: the whole row (>= 56 px) toggles the drawer; the name button stays the accessible trigger; chevron + hover."""
    import scorecard as SC
    nets = " · ".join(CHAINS[ch][0] for ch in c["chains"])
    tvl = c.get("tvlUsd")
    tvl_lbl = fmt_tvl(tvl)
    sub_meta = f"{nets} · {tvl_lbl}" if tvl_lbl else nets
    tvl_attr = f' data-tvl="{int(tvl)}"' if isinstance(tvl, (int, float)) and tvl > 0 else ' data-tvl="-1"'
    eas_attr = ' data-eas="1"' if c.get("easAttested") else ' data-eas="0"'
    toggle = f'<button class="sc-toggle" type="button" aria-expanded="false" aria-controls="sc-d-{c["slug"]}">{E(c["name"])}</button>'
    return (f'<tr class="sc-row{" sc-m" if mobile_more else ""}" data-slug="{c["slug"]}" data-name="{E(c["name"].lower())}" data-grade="{c["grade"]}"{tvl_attr}{eas_attr} data-baskets="{" ".join(c["baskets"])}" data-search="{E(short_search(c) if short else c["search"])}">'
            f'<td>{ident_cell(c["slug"], toggle, prefix)}'
            f'<span class="sc-chain">{E(sub_meta)}</span></td><td>{grade_pill(c)}</td><td>{SC.rosette_svg(c["factors"], 32, c["name"])}</td>'
            f'<td class="sc-find">{E(c["summary_short"])}</td><td class="sc-chev"><span class="chev" aria-hidden="true">{U.icon("chevron-down")}</span></td></tr>'
            + sc_drawer(c, prefix))


def scorecards_section(cards, prefix="", full=False, heading="h2"):
    """M2 (Docs vs chain, neutral Aligned, callout), M4 (counts from the data), M7 (<= 90-char summaries), V5/A1 (legend beside the
    filters), A5 (caption), R2 (cards below 640 px). The homepage ships the flagship rows; /scorecards/ ships all of them sorted by
    Severity (DELTA first) + Highest TVL at Risk."""
    by = {c["slug"]: c for c in cards}
    shown = sorted(cards, key=sc_tvl_rank_key) if full else [by[s] for s in FLAGSHIP]
    if not full:   # W1: severity order (deltas, then protective, then aligned references), never an aligned row first
        assert [GRADE_RANK[c["grade"]] for c in shown] == sorted(GRADE_RANK[c["grade"]] for c in shown) and shown[0]["grade"] == "delta"
    rows = "".join(sc_row(c, prefix, short=not full, mobile_more=not full and i >= MOBILE_FIRST_ROWS) for i, c in enumerate(shown))
    ident_map = {c_["slug"]: list(proto_ident(c_["slug"])) for c_ in cards}   # B8: the browser rebuild reuses these exact identities
    ident_attr = "" if full else f' data-ident="{E(json.dumps(ident_map, sort_keys=True, separators=(",", ":"), ensure_ascii=False))}"'
    n = len(cards)
    n_eas = sum(1 for c in cards if c.get("easAttested"))
    g = {k: sum(c["grade"] == k for c in cards) for k in GRADE_UI}
    filt = [("all", "All", n), ("delta", "Docs differ", g["delta"]), ("protective", "Protective", g["protective"]),
            ("aligned", "Aligned", g["aligned"]), ("observed", "Observed", g["observed"])]
    pills = "".join(f'<button data-slot="toggle-group-item" type="button" data-sc-f="{k}" aria-pressed="{"true" if k == "all" else "false"}">'
                    f'{lbl} <span class="num">({cnt})</span></button>' for k, lbl, cnt in filt)
    sort_bar = (f'<div data-slot="toggle-group" class="seg sc-sort" role="group" aria-label="Sort and view scorecards" data-sc-sort-group>'
                f'<button data-slot="toggle-group-item" type="button" data-sc-sort="tvl" aria-pressed="true">Severity &amp; TVL</button>'
                f'<button data-slot="toggle-group-item" type="button" data-sc-sort="gaps" aria-pressed="false">Adverse Gaps <span class="num">({g["delta"]})</span></button>'
                f'<button data-slot="toggle-group-item" type="button" data-sc-sort="eas" aria-pressed="false">Base-EAS Verified <span class="num">({n_eas})</span></button>'
                f'<button data-slot="toggle-group-item" type="button" data-sc-sort="az" aria-pressed="false">A–Z</button></div>'
                if full else "")
    baskets = "".join(f'<option value="{k}">{E(lbl)}</option>' for k, lbl, _, _ in BASKETS)
    more = (U.button(f"Explore all {n} protocol scorecards{ARR}", href=f"{prefix}scorecards/", variant="default", attrs="data-sc-explore")
            + f'<a href="{prefix}protocols/">Browse all {n} protocol pages{ARR}</a>'
            if not full else
            f'<a href="{prefix}bounties/#sponsor-pool" data-cta="sc_sponsor_pool">Fund a Verification Pool ($50+ USDC){ARR}</a>'
            f'<a href="{prefix}protocols/">Browse all {n} protocol pages{ARR}</a><a href="{prefix}api/v1/scorecards.json">scorecards.json</a>')
    head_html = (f'<div class="sec-head"><{heading}>Protocol scorecards</{heading}><p class="aside">Sorted by control-plane severity and capital exposure (DefiLlama TVL) across {n} protocols ({n_eas} Base-EAS verified). Select a row for the evidence.</p></div>' if full else
                 f'<div class="sec-head"><{heading}>Protocol scorecards</{heading}><p class="aside">{len(shown)} of {n} protocols, highest signal '
                 f'first: Docs differ (adverse), then protective and aligned references. Search or filter to load all {n}.</p></div>')
    intro_line = delta_line({"delta": g["delta"], "protective": g["protective"], "protocols": n}) if full else ""   # v4.5.1 "36 of 90"
    return f"""<section class="sec" id="scorecards"><div class="wrap">
{head_html}{intro_line}
{U.alert("Aligned means the docs are accurate, not that the protocol is low-risk.", "Docs vs chain compares what a protocol publishes with what its contracts enforce at a finalized block. The control-strength graphic shows how strong the controls themselves are.", icon_name="info", cls="aligned-note", attrs="data-aligned-note")}
<div class="sc-tools">
<div class="search">{U.icon("search")}<label class="sr-only" for="sc-q">Search protocol scorecards</label><input id="sc-q" type="search" placeholder="Search protocols" autocomplete="off">{U.button(U.icon("x"), variant="ghost", size="icon-sm", attrs='data-sc-qclear aria-label="Clear search" hidden', cls="clear")}</div>
{sort_bar}<div class="sc-filters"><div data-slot="toggle-group" class="seg sc-filter" role="group" aria-label="Filter by docs vs chain">{pills}</div>
<label class="sr-only" for="sc-basket">Collateral basket</label><select id="sc-basket" data-sc-basket style="width:auto"><option value="all">All baskets</option>{baskets}</select></div>
{rosette_legend()}
</div>
<div class="tbl-wrap"><table class="sc" id="sc-table" aria-describedby="rosette-legend"><caption class="sr-only">Protocol scorecards: docs-vs-chain status, five-factor control-strength graphic and the main difference for each protocol. Select a row to expand its evidence.</caption>
<thead><tr><th scope="col">Protocol</th><th scope="col">Docs vs chain</th><th scope="col"><span class="sr-only">Control-strength graphic</span><span aria-hidden="true">Control strength</span></th><th scope="col">What differs</th><th scope="col"><span class="sr-only">Expand</span></th></tr></thead>
<tbody data-sc-body data-src="{prefix}api/v1/scorecards.json" data-prefix="{prefix}"{" data-full" if full else ident_attr}>{rows}</tbody></table></div>
<div class="sc-empty" data-sc-empty hidden><p>No protocol matches these filters.</p>{U.button("Clear filters", variant="outline", size="sm", attrs="data-sc-clear")}</div>
<div class="sc-more">{more}</div>
</div></section>"""


REST_CURL = f'curl -s "{API}/v1/check/preflight?chain=base&address=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"'
REST_PY = ("import requests\n"
           f'r = requests.get("{API}/v1/check/preflight",\n'
           '                 params={"chain": "base", "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"})\n'
           'print(r.json()["verdict"])')


def livebar_html(radar):
    r = radar["refreshed_at"]
    later = [it for it in radar["items"] if it["eta"] and it["eta"] > r["block_timestamp"]]
    nxt = min(later or [it for it in radar["items"] if it.get("eta")] or radar["items"], key=lambda it: it.get("eta") or 0)
    return (f'<div class="livebar" data-etas="{E(livebar_etas(radar))}"><span class="dot live" aria-hidden="true"></span>'
            f'<span class="lb-next">Next: <span class="lb-p">{E(nxt["protocol"])}</span>, <span class="countdown" data-eta="{nxt["eta"]}">ETA {E(utc(nxt["eta"]))}</span></span> '
            f'<small class="lb-asof">(pinned snapshot observed <time datetime="{E(utc_iso(r["block_timestamp"]))}" '
            f'data-observed="{r["block_timestamp"]}">{E(r["block_time_utc"])}</time><span class="obs-age" data-age="{r["block_timestamp"]}"></span>)</small></div>')


def page(idx, radar):
    cards = scorecards(idx)
    s = site_numbers(idx, cards)
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    body = f"""<body>
{topbar()}
<main id="main">
{hero_section(idx, cards, radar)}
{how_it_works(idx, cards, radar)}
{scorecards_section(cards)}
{radar_section(radar)}
{agents_section()}
{pricing_section(idx)}
</main>
{footer(count_line, reg)}
{org_ld_script()}
{app_ld_script(idx)}
</body></html>
"""
    return head(TITLE, home_desc(s["protocols"]), BASE_URL + "/", rich=True) + "\n" + body


def vault_factories_page(idx, sp):
    """/integrations/vault-factories/: the zero-cost Control-Plane & Role Map tab (api/v1/protocols.json), status badges and
    PactaSentinelGuard.sol wiring for vault factories and curators. Platform-neutral; no claim of any partner integration."""
    c = counts(idx)
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    tiers = {}
    for v in sp.values():
        t = "rpc_observed" if v["pinned"] else ("aligned" if is_aligned_page(v["entries"]) else "parameter_delta")
        tiers[t] = tiers.get(t, 0) + 1
    n_eas = sum(1 for v in sp.values() if not v["pinned"])
    url = f"{BASE_URL}/integrations/vault-factories/"
    title = "Vault factories: control-plane tab, status badges and PactaSentinelGuard"
    desc = "Free building blocks for vault factories and curators: a Control-Plane & Role Map tab from one static JSON file, embeddable status badges, and a cap-increase tripwire."
    js = ('const res = await fetch("https://pacta.wtf/api/v1/protocols.json");\n'
          'const { protocols } = await res.json();\n'
          'const p = protocols.find((x) => x.slug === "aave-v3-gho");\n'
          '// p.badge.svg, p.evidenceBasis ("eas_attested" | "rpc_observed"), p.classification, p.controllerAddress,\n'
          '// p.surfaces[i].blockNumber / blockHash, p.preflightArgs (for a live re-read)\n'
          'badgeImg.src = p.badge.svg;            // render text with textContent, never innerHTML\n'
          'statusCell.textContent = p.badge.label;')
    sol = ('PactaSentinelGuard guard = new PactaSentinelGuard(\n'
           f'    {reg}, // PactaCommitmentRegistry (Base)\n'
           '    0x4200000000000000000000000000000000000021, // EAS predeploy (Base)\n'
           '    curatorSafe,                                // binds collateral\n'
           '    0                                           // maxStaleness: 0 = 30 days (1 to 365 days)\n'
           ');\n'
           'guard.bind(collateral, sprintId, easUid);       // from protocols.json `sprints` / `baseEasUids`\n'
           'guard.validateCapIncrease(collateral, currentCap, newCap); // reverts only on an unhealthy increase')
    md = f"[![{LK.BADGE_TITLE}]({BASE_URL}/badges/aave-v3-gho.svg)]({BASE_URL}/protocols/aave-v3-gho/)"
    rows = "".join(f'<tr><td><img class="cp-badge" src="../../badges/{s_}.svg" alt="{E(LK.BADGE_TITLE)}: {E(LK.BADGE_TIERS[t][0])}" height="20"></td>'
                   f'<td class="num">{tiers.get(t, 0)}</td><td>{E(d)}</td></tr>'
                   for t, s_, d in (("aligned", "aave-v3-gho", "Every record is a Base-EAS-attested aligned baseline: on-chain state matches the documentation."),
                                    ("parameter_delta", "curve-finance-crvusd", "Base-EAS-attested; at least one surface differs from the documentation."),
                                    ("rpc_observed", "bedrock-unieth", "RPC-pinned only: control plane pinned at an archive block; documentation not assessed; not EAS-attested.")))
    plat = "".join(f"<tr><td><b>{E(a)}</b></td><td><code>{E(b)}</code></td><td>{E(d)}</td></tr>" for a, b, d in (
        ("Morpho Vault V2", "checkMorphoV2AbsoluteCapIncrease(vault, collateral, idData, newCap)",
         "Before a curator submits increaseAbsoluteCap. Reads absoluteCap(keccak256(idData)); decreaseAbsoluteCap and sentinel revoke are never gated."),
        ("Euler EVK", "checkEulerCapsChange(evault, collateral, newSupplyCap, newBorrowCap)",
         "Before setCaps. AmountCap 0 means unlimited, so setting a cap to 0 counts as an increase; lowering a cap never needs the attestation."),
        ("Veda (BoringVault), Lagoon, Upshift, Mellow", "validateCapIncrease(collateral, currentCap, newCap)",
         "In your cap-setting path: a manager or strategist module, a Safe transaction guard, or an off-chain approval bot."),
        ("Off-chain Sentinel bots", "attestationHealth(collateral)",
         "Poll the health state (it never reverts on a malformed attestation) and alert or de-risk.")))
    body = f"""<body>
{topbar("../../")}
<main id="main" class="memo-wrap">
<div class="crumbs"><a href="../../">Pacta</a> / Integrations / Vault factories</div>
<article class="memo">
<header><span class="tier">Integrations</span><h1>{E(title)}</h1>
<p class="lede">Free building blocks for vault factories and curator tooling: a <b>Control-Plane &amp; Role Map</b> tab from one static JSON file, embeddable status badges, and <code>PactaSentinelGuard.sol</code>, an on-chain tripwire that refuses cap increases for collateral without a healthy Pacta attestation and never blocks a decrease.</p></header>
<section class="memo-sec" id="control-plane-tab"><h2>1. Control-Plane &amp; Role Map tab (free, no key)</h2>
<p>The <a href="../../api/v1/protocols.json">protocol data</a> (<code>/api/v1/protocols.json</code>, schema <code>pacta.protocols.v1</code>) lists every published protocol record: {len(sp)} protocols, of which {n_eas} are Base-EAS-attested (<code>evidenceBasis: "eas_attested"</code>, documentation compared) and {len(sp) - n_eas} are RPC-observed only (<code>evidenceBasis: "rpc_observed"</code>, <code>documentationComparison: "not_assessed"</code>). Each record carries the checksummed target and controller, every pinned surface with its block number and block hash, the badge URLs and ready-to-use <code>preflightArgs</code>.</p>
{snippet(js, "JavaScript", "Copy JavaScript")}
<p>Show RPC-observed protocols as observed control planes only: never present them as aligned or as having a documentation delta. For a live re-read of any contract, call the free <code>{E(API)}/v1/check/preflight</code> with <code>preflightArgs</code>.</p></section>
<section class="memo-sec" id="badges"><h2>2. Control-plane status badges</h2>
<p>Static: <code>{E(BASE_URL)}/badges/&lt;slug&gt;.svg</code> (rebuilt with the site). Live: <code>{E(API)}/v1/badges/&lt;slug&gt;.svg</code> (5-minute cache, CORS open). Three tiers, per protocol page:</p>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Badge</th><th class="r">Protocols</th><th>Meaning</th></tr></thead><tbody>{rows}</tbody></table></div>
{snippet(md, "Markdown", "Copy Markdown")}</section>
<section class="memo-sec" id="sentinel-guard"><h2>3. PactaSentinelGuard.sol: refuse unhealthy cap increases, never block a decrease</h2>
<p>An MIT, zero-dependency, non-custodial Solidity <code>^0.8.24</code> contract (source and offline Foundry tests in <a href="{E(REPO)}/tree/main/packages/sentinel-guard"><code>packages/sentinel-guard</code></a>; not audited, review before production use). A cap increase passes only if the collateral's binding resolves to:</p>
<ul><li>a Sprint receipt in PactaCommitmentRegistry {hexref(reg)} on Base with <code>driftCount == 0</code> (the receipt covers the whole Sprint, so drift anywhere in it blocks increases);</li>
<li>a Base EAS attestation with the Pacta schema, made by the registry's current attester, not revoked or expired, younger than <code>maxStaleness</code> (default 30 days), whose payload matches the registry receipt.</li></ul>
<p>Decreases, equal caps and zeroing always pass, so curators and sentinels can de-risk during an incident. Pacta deploys no shared instance: each curator deploys one on Base, where the registry and EAS live (vaults on other chains can run the same checks from an off-chain bot), and binds collateral with Sprint ids and UIDs from <code>protocols.json</code>. RPC-observed protocols have no attestation to bind, so an increase guarded for them always reverts.</p>
{snippet(sol, "Solidity", "Copy Solidity")}
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Platform</th><th>Call</th><th>Where</th></tr></thead><tbody>{plat}</tbody></table></div></section>
</article>
<div class="memo-foot"><span>Read-only on-chain analysis. Not investment advice. No partner integration is implied: these are open building blocks.</span><a href="../../protocols/">Protocol records{ARR}</a></div>
</main>
{footer(count_line, reg, "../../")}
</body></html>
"""
    return head(f"{title} · Pacta", desc, url, prefix="../../", og_title=title, og_type="article") + "\n" + body


# ---- /for-protocols/ (Website Edge v3, spec section 5) ---------------------------------------------------------------------
# Each case study names its record and the exact numbers it states; the build asserts every number appears in that record's
# documented / observed evidence, so the page can never claim more than the attested record says.
CASES = [
    ("stader-labs-ethx", "stader-ethx-manager-safe-and-timelock", "Stader Labs (ETHx)", "Ethereum",
     "Official GitBook: the Manager multisig is a 3-of-5.", "Finalized Ethereum state: the Manager Safe runs at a 3-of-6 quorum; upgrades still wait the 7-day TimelockController.",
     ("3-of-5",), ("3-of-6", "604800s")),
    ("yo-protocol", "yo-protocol-approval-registry-owner-admin-safe-s22", "YO Protocol", "Base",
     "Docs: “Onchain, timelocked caps” on what each vault may approve.", "YoApprovalRegistry.owner() is the 4-of-6 Admin Safe directly, not the 48-hour YO Timelock: no enforced delay.",
     ("timelocked caps",), ("4-of-6", "not the YO Timelock")),
    ("stake-dao", "stake-dao-protocol-timelock-min-delay-5d-s22", "Stake DAO", "Ethereum",
     "Docs: a 48-hour timelock on all protocol changes; all wallets 4-of-7.", "ProtocolTimelock enforces 5 days (432,000s), stronger than documented (protective); the Treasury Safe is 3-of-5 (delta).",
     ("48-hour",), ("432000s",)),
    ("moonwell-lending-base", "moonwell-pause-guardian-2of4-safe-s18", "Moonwell (Base)", "Base",
     "Governance Constitution 8.1: emergency actions need a 3-of-5 Security Council approval.", "Unitroller.pauseGuardian() resolves to a 2-of-4 Safe.",
     ("3-of-5",), ("2-of-4",)),
]


def check_cases(idx):
    by = {e["id"]: e for e in idx["entries"]}
    tre = by["stake-dao-treasury-safe-3of5-s22"]
    assert "4-of-7" in tre["documented_reference"] and "3-of-5" in tre["onchain_observed"]
    for slug, rid, _, _, _, _, docs_tok, chain_tok in CASES:
        e = by[rid]
        assert protocol_slug(e["protocol"]) == slug, (rid, slug)
        assert all(t in e["documented_reference"] for t in docs_tok), (rid, docs_tok)
        assert all(t in e["onchain_observed"] for t in chain_tok), (rid, chain_tok)


FOR_PROTOCOLS_FAQ = [
    ("Does paying for a dossier or a verification pool guarantee an Aligned badge?",
     "No. Payment covers expedited engineering review and the Base EAS attestation only. The status strictly reflects what finalized "
     "on-chain state and the public documentation show."),
    ("We fixed our docs (or rotated signers). Can we notify Pacta for free?",
     "Yes. Submit the updated docs commit or URL through /request/?tier=community at $0: once a public docs or on-chain fix is "
     "merged, we re-verify it for free within 7 days."),
    ("Do we need to share private keys, grant repo access or connect a wallet?",
     "Never. Every scan is read-only against finalized public archive blocks and public documentation; invoices settle by standard "
     "invoice or Base USDC."),
    ("What if a finding exposes an active security vulnerability?",
     "Pacta quarantines exploit-sensitive paths privately under coordinated disclosure (/.well-known/security.txt) and never publishes "
     "exploit primitives in public scorecards."),
]


def for_protocols_page(idx):
    import scorecard as SC
    check_cases(idx)
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    cards = {x["slug"]: x for x in scorecards(idx)}
    case_html = "".join(
        f'<article class="case" data-case="{slug}"><h3><a href="../protocols/{slug}/">{E(name)}</a> <span class="case-chain">{E(chain)}</span></h3>'
        f'<p class="case-grade">{grade_pill(cards[slug])}{SC.rosette_svg(cards[slug]["factors"], 32, name)}</p>'
        f'<p><b>Documented:</b> {E(docs)}</p><p><b>Onchain:</b> {E(onchain)}</p>'
        f'<p class="links"><a href="../protocols/{slug}/">Full scorecard{ARR}</a></p></article>'
        for slug, rid, name, chain, docs, onchain, _, _ in CASES)
    opts = "".join(f'<option value="{x["slug"]}"{" selected" if x["slug"] == "stader-labs-ethx" else ""}>{E(x["name"])}</option>'
                   for x in sorted(cards.values(), key=lambda x: x["name"].lower()))
    slug0 = "stader-labs-ethx"
    tier0 = {"delta": "parameter_delta", "protective": "parameter_delta", "aligned": "aligned", "observed": "rpc_observed"}[cards[slug0]["grade"]]
    widget = (f'<div class="badge-widget" data-badge-widget data-base="{E(BASE_URL)}">'
              f'<label>Protocol <select data-bw-select aria-label="Protocol for the badge preview">{opts}</select></label>'
              f'<p class="badge-preview"><img data-bw-img src="../badges/{slug0}.svg" alt="{E(LK.BADGE_TITLE)} badge for the selected protocol" height="20"></p>'
              f'{badge_embed(cards[slug0]["name"], slug0, tier0)}</div>')
    faq = "".join(f'<div><dt>{E(q)}</dt><dd>{E(a)}</dd></div>' for q, a in FOR_PROTOCOLS_FAQ)
    ctas = "".join(
        f'<div><h3>{E(t)}</h3><p>{E(d)}</p>' + U.button(E(cta), href=href, variant="default" if href.endswith("clearance") else "outline") + '</div>'
        for href, t, d, cta in (
            ("../request/?tier=community", "Free 7-day fix re-check · $0", "Free factual re-verification within 7 days whenever a protocol merges a public docs or on-chain fix.", "Submit updated docs"),
            ("../bounties/#sponsor-pool", "Verification pools & wholesale · $50+ / $150 per protocol", "Sponsor an independent protocol pool ($50 live check / $150 3-year dossier) or a $150/protocol curator sweep.", "Fund a pool"),
            ("../request/?tier=clearance", "Full dossier · $2,500–$5,000, 24h", "Every proxy, Safe, governor and timelock across a pre-launch or multi-contract suite, reconciled with your docs and attested on Base.", "Request a dossier")))
    body = f"""<body>
{topbar("../", "for-protocols/")}
<main id="main">
<section class="hero fp-hero"><div class="wrap">
<span class="eyebrow">For protocol &amp; security teams</span>
<h1>Turn control-plane transparency into allocator trust.</h1>
<p class="lede">Risk curators, DAO delegates and AI risk agents check Pacta before they allocate. Verify your live multisig quorums and timelocks, reconcile outdated docs, and publish a block-pinned Base EAS badge.</p>
<p class="ctas">{U.button("Request a dossier", href="#request", variant="default", size="lg")}{U.button("Curator matrix", href="../curators/", variant="outline", size="lg")}{U.button("Embed your badge", href="#embed", variant="outline", size="lg")}{U.button("Browse scorecards", href="../scorecards/", variant="ghost", size="lg")}</p>
</div></section>
<section class="sec" id="cases"><div class="wrap">
<div class="sec-head"><h2>Verified findings from the public index</h2><p class="aside">Four real records, each pinned to a finalized block and attested on Base. The numbers are the record's own.</p></div>
<div class="cases">{case_html}</div>
</div></section>
<section class="sec" id="embed"><div class="wrap">
<div class="sec-head"><h2>Embed a live "Pacta Attested" badge</h2><p class="aside">Every published protocol has a status badge that says exactly what Pacta verified.</p></div>
<p class="sec-intro">The badge reads <i>Aligned · Base EAS</i>, <i>Parameter Delta</i> or <i>RPC-Observed</i> (the badge words for Aligned, Docs differ and Observed), links back to the scorecard and changes when the chain or the documentation changes.</p>
{widget}
</div></section>
<section class="sec" id="faq"><div class="wrap">
<div class="sec-head"><h2>Editorial independence &amp; security</h2></div>
<dl class="fp-faq">{faq}</dl>
</div></section>
<section class="sec" id="request"><div class="wrap">
<div class="sec-head"><h2>Work with Pacta</h2><p class="aside">Continuous Control-Plane Monitoring ({E(MONITORING_PRICE)}) and API SLAs are on the <a href="../request/">request page</a>.</p></div>
<div class="fp-ctas">{ctas}</div>
<p class="s" style="margin-top:16px">{E(EDITORIAL_INDEPENDENCE)}</p>
</div></section>
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    return head("For protocols: control-plane transparency & the Pacta badge · Pacta",
                "Verify your multisig quorums and timelocks against your docs, reconcile drift and embed a live Base-EAS-attested Pacta badge.",
                f"{BASE_URL}/for-protocols/", prefix="../", og_title="Turn control-plane transparency into allocator trust") + "\n" + body


def request_page(idx):
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    desc = ("Request Pacta verification: free 7-day fix re-verification, $150/protocol wholesale sweeps, $2,500–$5,000 dossiers, "
            "or Continuous Control-Plane Monitoring.")
    body = f"""<body>
{topbar("../")}
<main id="main">
<section class="sec" id="request"><div class="wrap">
<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span><span>Request a dossier</span></nav>
<div class="sec-head"><h1>Request a dossier</h1><p class="aside">Every scorecard, the API and the MCP server stay free. This form is for verification work.</p></div>
<nav class="launcher" aria-label="Instant self-serve checks" data-launcher>{launcher_links("../", len(site_protocols(idx)))}</nav>
<p class="sec-intro">Agents do not need this page: the API (<code>/v1/check/preflight</code>) and the <a href="../mcp/">remote MCP server</a> (<code>{E(MCP_URL)}</code>) are free, with no key and no wallet. Remote MCP ({E(REMOTE_TOOLS_DOC)}). Pick a track and the protocols in scope; you get a request ID right away. {E(EDITORIAL_FIREWALL)} {E(EDITORIAL_SHORT)}</p>
{request_builder(idx, "../")}
</div></section>
{pricing_section(idx, "../")}
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    return head("Request a dossier · Pacta", desc, f"{BASE_URL}/request/", prefix="../", og_title="Request a Pacta dossier") + "\n" + body


DECODED = DB.load()   # v4.6: slug -> decoded brief (tools/briefs_decoded.json, the decoder's output byte-for-byte)


def brief_page(slug, desc, idx, radar):
    item = next((it for it in radar["items"] if it["brief"].rstrip("/").endswith(slug)), None)
    if slug in DECODED:   # v4.6: every address, amount, block and transaction comes from the decoder's JSON
        DB.check_against_radar(DECODED[slug], item, BRIEF_PROTOCOL[slug])
        title, content = DB.render(DECODED[slug], item, sys.modules[__name__])
    else:
        src = open(os.path.join(BRIEF_SRC, f"{slug}.html")).read()
        title = html.unescape(re.match(r"<!-- title: (.*?) -->\n", src).group(1))   # plain text; head() escapes once
        content = src.split("\n", 1)[1].replace("<table>", '<table class="stack">')   # v4.6: stacked below 640 px (styles.css)
    meta = ""
    if item:
        ch, r = radar_chain(item, radar), radar_pin(item, radar)
        where = "" if ch == "ethereum" else f"{CHAINS[ch][0]} "
        blk = xlink(ch, "block", r["block_number"], f'<span class="num">#{r["block_number"]:,}</span>')
        ops = " ".join(hexref(o["op_id"], 8, 4) for o in item["operations"])
        meta = (f'<dl class="memo-meta">'
                f'<dt>Protocol</dt><dd>{E(item["protocol"])}</dd>'
                f'<dt>Chain</dt><dd>{E(CHAINS[ch][1])}</dd>'
                f'<dt>Timelock</dt><dd>{hexref(item["timelock"])} · {secs(item["min_delay_seconds"])} minimum delay · '
                f'{xlink(ch, "address", item["timelock"], EXPLORERS[ch][0])}</dd>'
                f'<dt>Operation{"s" if len(item["operations"]) > 1 else ""}</dt><dd>{ops}</dd>'
                + (f'<dt>Execution window</dt><dd><span class="countdown" data-eta="{item["eta"]}">ETA {E(utc(item["eta"]))}</span> · {E(utc(item["eta"], True))}</dd>' if item.get("eta") else
                   f'<dt>Execution</dt><dd>Executed on-chain: isOperationDone = true at {where}finalized block {blk}</dd>') +
                f'<dt>State</dt><dd>{state_badge(item_state(item), item["operations"])} at {where}finalized block {blk} ({E(r["block_time_utc"])}) '
                f'<span class="badge final">Scanner-pinned ({PIN_WORD[ch]} finalized)</span></dd></dl>')
    content = content.replace("</header>", "</header>\n" + meta, 1)
    if item:
        content = post_eta_banner(item, r, ch) + content
    issuer = item["protocol"] if item else title
    content = content.rstrip("\n") + "\n" + clearance_callout(issuer, BRIEF_PROTOCOL[slug])
    c = counts(idx)
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    body = f"""<body>
{topbar("../../")}
<main id="main" class="memo-wrap">
<div class="crumbs"><a href="../../">Pacta</a> / <a href="../../#radar">Timelock radar</a> / Pre-execution brief</div>
<article class="memo">
{content}</article>
<div class="memo-foot"><span>Read-only on-chain analysis. Not investment advice. Exploit-sensitive vulnerabilities are never published here; they go through Immunefi or Cantina bounty programmes.</span><a href="../../request/">Get briefs like this for your collateral{ARR}</a></div>
</main>
{footer(count_line, reg, "../../")}
</body></html>
"""
    return head(title, desc, f"{BASE_URL}/briefs/{slug}/", prefix="../../", og_title=title, og_type="article") + "\n" + body


# ---- Batch E: pacta.wtf/bounties/ ($100 USDC hard cap, 4 x $25 USDC slots) --------------------------------------------
BOUNTY_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bounty_issues.json")
BOUNTY_TEMPLATE = ".github/PULL_REQUEST_TEMPLATE/bounty_mismatch.md"
BOUNTY_TEMPLATE_URL = f"{REPO}/blob/main/{BOUNTY_TEMPLATE}"
BOUNTY_COMPARE_URL = f"{REPO}/compare/main...main?quick_pull=1&template=bounty_mismatch.md"
BOUNTY_TITLE = "Pacta Chain-Feed Mismatch Challenge ($100 USDC · Completed Early Nov 17, 2026 · 4/4 Genesis Slots Settled)"
BOUNTY_SLOTS = {   # slot -> scope line (receipt/1825)
    1: "Ethereum Mainnet (chainId: 1, >=$25M TVL) unindexed control-plane parameter_delta #1",
    2: "Ethereum Mainnet (chainId: 1, >=$25M TVL) unindexed control-plane parameter_delta #2",
    3: "Base (8453) or Arbitrum One (42161) (>=$10M TVL) unindexed control-plane parameter_delta",
    4: "Live chain-feed drift catch on any of Pacta's 53 indexed protocols OR 4th unindexed (>=$15M TVL) mismatch",
}
# receipt/1827: the truthful settlement statement (word for word); the treasury is an externally owned account, never a Safe.
BOUNTY_PAYOUT = ("Paid in USDC on Base Mainnet within 48h of maintainer merge from Pacta treasury (0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14) "
                 "once the winner comments their public Base 0x... address on the merged PR. Funds are not pre-escrowed in an automated contract; "
                 "zero automatic on-chain payouts.")
BOUNTY_PROOF = [   # the 6 required PR proof items (the PR template enforces them; tools/verify_bounty_submission.py checks them)
    ("chainId & contract address", "chainId (1, 8453 or 42161), the checksummed 0x target contract, the protocol name and a verifiable TVL reference (or the Pacta slug for indexed drift)."),
    ("Pinned finalized block", "The finalized blockNumber and its exact 32-byte blockHash (plus the prior pinned Pacta block / tx for post-snapshot drift)."),
    ("Deterministic dual-RPC cast proof", "The exact cast call / cast storage commands with --block <blockNumber> and their raw outputs, identical on 2 independent RPC endpoints."),
    ("Live official documentation claim (HTTP 200)", "A direct https:// URL to the protocol's official docs and the verbatim quote that conflicts with the on-chain state."),
    ("Pacta MCP output", "The JSON from pacta_lookup_protocol / pacta_check_preflight / pacta_scan_control_plane."),
    ("Apache-2.0 contribution & commercialization grant", "A checked confirmation granting Pacta by Fractal Neurons perpetual, irrevocable rights under Apache-2.0 to ingest, Base EAS-attest, publish on pacta.wtf, and commercialize the merged mismatch record."),
]
BOUNTY_RULES = [
    ("First valid merged PR wins", "it must pass deterministic CI and an independent dual-RPC archive replay at the pinned blockHash."),
    ("Max 1 open PR per contributor", "across all bounty slots at a time; Slots #1 and #2 must cover two distinct protocols."),
    ("Zero AI-slop", "fabricated RPC outputs, unpinned block reads, or broken / hallucinated doc URLs are closed and disqualified."),
    ("Strict ban on third-party spam", "never open unsolicited PRs, issues or comments in third-party repositories on Pacta's behalf; submissions are PRs to Fractal-Neurons/pacta only."),
    ("No public exploit PoCs", "governance and documentation parameter mismatches only; route security vulnerabilities via Immunefi / Cantina per /.well-known/security.txt."),
    ("Agent-assisted & autonomous-agent submissions welcome", "Human, agent-assisted, and autonomous-agent submissions are equally eligible under the exact "
     "same deterministic dual-RPC archive replay, HTTP 200 official-docs verification, and 1-open-PR-per-contributor rules (0 fabricated outputs)."),
]
BOUNTY_FIXTURE = "bounties/submissions/slot-<slot>-<protocol-slug>.json"


def bounty_hours(pr):
    """Length of the sprint window in hours (sprintWindow "<ISO start> to <ISO end>"): 168 for the 7-day sprint."""
    start, end = (dt.datetime.fromisoformat(x.strip().replace("Z", "+00:00")) for x in pr["sprintWindow"].split(" to "))
    return int((end - start).total_seconds() // 3600)


def load_bounties(path=None):
    d = json.load(open(path or BOUNTY_SRC))
    pr, issues = d["program"], d["issues"]
    assert pr["totalHardCapUsdc"] == 100 and pr["slots"] == 4 and pr["slotRewardUsdc"] == 25 and len(issues) == 4
    assert [i["slot"] for i in issues] == [1, 2, 3, 4] and all(i["rewardUsdc"] == 25 for i in issues)
    assert sum(i["rewardUsdc"] for i in issues) == pr["totalHardCapUsdc"] and set(BOUNTY_ISSUE_URLS) == {1, 2, 3, 4}
    assert pr["treasuryAddress"] == "0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14"
    assert bounty_hours(pr) == 168, "the sprint window must be exactly 7 days (168 h)"
    return d


def md_inline(t):
    """Escape, then [text](https://…) links, **bold**, *italic* and `code` (code spans are protected first, so bold may contain code)."""
    codes = []
    t = re.sub(r"`([^`]+)`", lambda m: codes.append(m.group(1)) or f"\x00{len(codes) - 1}\x00", t)
    t = E(t, quote=False)
    t = re.sub(r'\[([^\]\x00]+)\]\((https://[^\s()<>"]+)\)', r'<a href="\2">\1</a>', t)   # C: "protocol data" instead of a raw API path
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<i>\1</i>", t)
    return re.sub("\x00(\\d+)\x00", lambda m: f"<code>{E(codes[int(m.group(1))], quote=False)}</code>", t)


def md_html(text):
    """The small Markdown subset the bounty issues use: ## / ### headings, paragraphs (one per line, as GitHub renders issue line
    breaks), - and 1. lists, --- rules and ``` fences. Deterministic; every text node is escaped."""
    out, lst, code = [], None, None
    def close():
        nonlocal lst
        if lst:
            out.append(f"</{lst}>")
            lst = None
    for line in text.split("\n"):
        if code is not None:
            if line.startswith("```"):
                out.append(f'<pre class="term-pre"><code>{E(chr(10).join(code), quote=False)}</code></pre>')
                code = None
            else:
                code.append(line)
            continue
        if line.startswith("```"):
            close()
            code = []
        elif not line.strip():
            close()
        elif line.strip() == "---":
            close()
            out.append("<hr>")
        elif line.startswith("### "):
            close()
            out.append(f"<h4>{md_inline(line[4:])}</h4>")
        elif line.startswith("## "):
            close()
            out.append(f"<h3>{md_inline(line[3:])}</h3>")
        elif re.match(r"^- ", line) or re.match(r"^\d+\. ", line):
            kind = "ul" if line.startswith("- ") else "ol"
            if lst != kind:
                close()
                out.append(f"<{kind}>")
                lst = kind
            item = re.sub(r"^(?:- |\d+\. )", "", line)
            out.append(f"<li>{md_inline(item)}</li>")
        else:
            close()
            out.append(f"<p>{md_inline(line)}</p>")
    close()
    assert code is None, "unterminated code fence"
    return "\n".join(out)


# v4.7 W4: the closed Wave 1 issue text names the index size of Nov 15 ("53 currently indexed protocols"); the archive states it
# as historical so no page claims 53 indexed protocols today (tools/bounty_issues.json, the GitHub source, is unchanged)
WAVE1_ARCHIVAL = (("53 currently indexed protocols", "53 protocols indexed on Nov 15"),)


def wave1_md(body):
    h = md_html(body)
    for a, b in WAVE1_ARCHIVAL:
        h = h.replace(a, b)
    return h


SPONSOR_POOL_VERIFIED = None   # {"threshold": ..., "modules": ..., "guard": ..., "block": ...} only after the deployed Sponsor Safe is read on Base
SPONSOR_CUSTODY_DEPLOYED = ("Sponsor funds sit in a 2-of-3 Safe on Base. The founder holds two keys on separate devices. "
                            "One is held by an automated system run by the project. Nothing moves without a founder signature.")
SPONSOR_OPENING = "Opening soon — reservation or invoice only; no sponsor funds collected"
SPONSOR_TERMS = {"pool_min": "$50", "fee": "$25", "sweep_per": "$150", "sweep_min_protocols": 20}
SPONSOR_TERMS_TEXT = (f"{SPONSOR_TERMS['pool_min']} minimum pool; {SPONSOR_TERMS['fee']} fixed verification fee; "
                      f"{SPONSOR_TERMS['sweep_per']} per protocol for a sweep of {SPONSOR_TERMS['sweep_min_protocols']} or more")


def sponsor_pool_live():
    """True only once the Sponsor Safe is deployed AND its quorum, modules and guard were read on Base."""
    return bool(SPONSOR_POOL_ADDRESS) and bool(SPONSOR_POOL_VERIFIED)


def sponsor_pool_section_html():
    """/bounties/#sponsor-pool & #sponsor-ledger. Until the Sponsor Safe is deployed and verified the pool is plainly pending:
    no deposit address, every on-chain observation reads "Not verified", refunds are described as a signed policy, and the
    custody sentence below appears only after verification."""
    assert SPONSOR_POOL_ADDRESS == "" or (HEX40.fullmatch(SPONSOR_POOL_ADDRESS) and SPONSOR_POOL_ADDRESS.lower() not in
                                          ("0x4348df1befaffcba248b5118b1b782b1b2bded14", "0xca4e2ff22b69a7284210c47bdee21aac1269da09"))
    live = sponsor_pool_live()
    obs = SPONSOR_POOL_VERIFIED or {}
    nv = "Not verified"
    custody = (f'<p class="sp-verbatim" data-sponsor-custody-verbatim>{E(SPONSOR_CUSTODY_DEPLOYED)}</p>' if live else
               f'<p class="sp-verbatim" data-sponsor-custody-pending><b>{E(SPONSOR_OPENING)}.</b> The Sponsor Safe is not deployed yet, '
               f'so there is no deposit address and nothing on-chain to verify.</p>')
    status = (f'<b>Deposit address:</b> <code class="mono">{E(SPONSOR_POOL_ADDRESS)}</code>, verified at Base block #{obs.get("block", 0):,}.' if live else
              f'<b>Deposit address:</b> none yet. {E(SPONSOR_OPENING)}.')
    ledger_lead = (E(SPONSOR_CUSTODY_DEPLOYED) if live else
                   "No Sponsor Safe is deployed yet. This ledger and the self-check below fill in once it is deployed and verified.")
    return (
        f'<section class="memo-sec sponsor-sec" id="sponsor-pool" data-sponsor-pool data-sponsor-address="{E(SPONSOR_POOL_ADDRESS)}" '
        f'data-sponsor-state="{"live" if live else "pending"}">'
        f'<div class="sp-head"><span data-slot="badge" data-variant="info">Community, curators &amp; ecosystems</span>'
        f'<h2>Sponsor or fund a verification pool</h2>'
        f'<p>Pay for an independent check of a protocol nobody has assessed yet, or of a multi-vault stack you depend on. '
        f'Sponsors pay for checking, never for a result.</p></div>'
        f'<div class="sp-tiers">'
        f'<article class="sp-tier sp-tier-feat" data-sp-tier="option-a">'
        f'<span class="step-k mono">VERIFICATION POOL</span>'
        f'<h3>{SPONSOR_TERMS["pool_min"]} minimum pool</h3>'
        f'<p>Fund an independent check of one protocol or contract with at least <b>{SPONSOR_TERMS["pool_min"]} USDC</b>. A fixed '
        f'<b>{SPONSOR_TERMS["fee"]} USDC</b> verification fee covers our independent second check and the public attestation receipt; '
        f'the rest pays the researcher who does the work.</p>'
        f'</article>'
        f'<article class="sp-tier" data-sp-tier="option-b">'
        f'<span class="step-k mono">ECOSYSTEM OR VAULT SWEEP</span>'
        f'<h3>{SPONSOR_TERMS["sweep_per"]} per protocol</h3>'
        f'<p>For sweeps of <b>{SPONSOR_TERMS["sweep_min_protocols"]} or more protocols</b>: L2 ecosystems, grant councils and vault curators '
        f'checking collateral baskets. Settled by invoice or Base USDC; <b>undelivered targets are never charged</b>.</p>'
        f'</article></div>'
        f'<div class="sp-firewall" role="note" data-sponsor-firewall>'
        f'<b>Editorial firewall:</b> sponsors fund independent checking, never an Aligned rating. Every result is published, '
        f'and sponsors are disclosed on the scorecard.</div>'
        f'<div class="sp-custody" data-sponsor-custody-rules>'
        f'<h3>Custody</h3>{custody}'
        f'<p class="s"><b>Intended policy</b> (applies once the Safe is deployed and verified; nothing below is an on-chain observation):</p>'
        f'<ol class="sp-rules">'
        f'<li data-custody-rule="a"><b>Separate custody:</b> a dedicated Sponsor Safe, never mixed with Pacta&#x27;s commercial wallet '
        f'(<code>0x4348…Ed14</code>) or the researcher payout wallet (<code>0xcA4E…da09</code>).</li>'
        f'<li data-custody-rule="b"><b>Signatures:</b> a 2-of-3 Safe on Base in which the founder holds two keys and an automated project '
        f'system holds one; no payout or refund moves without a founder signature.</li>'
        f'<li data-custody-rule="c"><b>Public ledger (<a href="#sponsor-ledger">#sponsor-ledger</a>):</b> every deposit, payout and refund '
        f'is listed below with its Base transaction.</li>'
        f'<li data-custody-rule="d"><b>$500 cap and 30-day refunds:</b> at most $500 USDC held at a time. If no submission is accepted '
        f'within 30 days, the sponsor can ask for a refund; refunds are a policy that needs the Safe&#x27;s approvals and signatures, '
        f'not an automatic on-chain guarantee.</li>'
        f'</ol></div>'
        f'<div class="sp-firewall" role="status" data-sponsor-safe-status>{status}</div>'
        f'<form class="sp-form" id="sponsor-pool-form" data-sponsor-pool-form data-api="{E(SPONSOR_POOL_API)}" data-fallback-api="{E(REQUEST_API)}" novalidate autocomplete="off">'
        f'<div class="sp-form-grid">'
        f'<div class="field"><label for="sp-target">Target protocol or contract</label>'
        f'<input id="sp-target" name="target" type="text" maxlength="160" spellcheck="false" placeholder="Protocol or address" data-sp-target></div>'
        f'<div class="field"><label for="sp-tier">Pool or sweep</label>'
        f'<select id="sp-tier" name="tier" data-sp-tier-select>'
        f'<option value="pool-50" selected>{SPONSOR_TERMS["pool_min"]} minimum pool</option>'
        f'<option value="wholesale-150">Sweep · {SPONSOR_TERMS["sweep_per"]}/protocol</option>'
        f'</select></div>'
        f'<div class="field"><label for="sp-settlement">Settlement</label>'
        f'<select id="sp-settlement" name="settlement" data-sp-settlement>'
        f'<option value="safe_reserve" selected>Reserve — pay nothing now</option>'
        f'<option value="invoice">Request an invoice</option>'
        f'</select></div>'
        f'<div class="field"><label for="sp-attribution">Public attribution <span class="legend-note">· optional</span></label>'
        f'<input id="sp-attribution" name="attribution" type="text" maxlength="80" placeholder="Public name (optional)" data-sp-attr></div>'
        f'</div>'
        f'<div class="sp-form-row2">'
        f'<div class="field"><label for="sp-contact">Where we confirm your reservation</label>'
        f'<input id="sp-contact" name="contact" type="text" maxlength="160" spellcheck="false" placeholder="Email or Telegram" data-sp-contact></div>'
        + U.button('<span class="spinner" aria-hidden="true" hidden></span><span data-sp-btn-lbl>Reserve Verification Pool</span>',
                   variant="default", size="lg", type_="submit", attrs="data-sp-submit")
        + '</div>'
        f'<p class="sp-safe-note" data-sp-safe-note><b>No payment now.</b> We confirm your reservation from Pacta (<code>pacta@dri.network</code>). '
        f'Deposit instructions come only after the Sponsor Safe is deployed and verified; never send sponsor funds to any other address. '
        f'Terms: {E(SPONSOR_TERMS_TEXT)}. See <a href="../privacy/#watch-pilot">Privacy</a>.</p>'
        f'<p class="form-message" data-slot="form-message" data-sp-err hidden></p>'
        f'<p class="wp-status" role="status" aria-live="polite" data-sp-status hidden></p>'
        f'</form>'
        f'<div class="wp-done" data-sp-done hidden tabindex="-1">'
        f'<span data-slot="badge" data-variant="success">Verification Pool Reserved</span>'
        f'<p data-sp-done-msg>Pool reservation recorded.</p>'
        f'</div></section>'
        f'<section class="memo-sec" id="sponsor-ledger" data-sponsor-ledger>'
        f'<h2>Public sponsor pool ledger</h2>'
        f'<p class="s">{ledger_lead}</p>'
        f'<div class="sp-self-check" data-sponsor-self-check>'
        f'<div class="sp-sc-head"><span class="step-k mono">SPONSOR SAFE SELF-CHECK</span>'
        f'<span data-slot="badge" data-variant="{"neutral" if live else "info"}">{"Base · verified" if live else "Opening soon"}</span></div>'
        f'<dl class="pf-metrics sp-sc-grid">'
        f'<div><dt>Safe address</dt><dd class="mono">{E(SPONSOR_POOL_ADDRESS) if live else nv}</dd></div>'
        f'<div><dt>Threshold</dt><dd class="mono">{E(obs.get("threshold", nv))}</dd></div>'
        f'<div><dt>Modules</dt><dd class="mono">{E(obs.get("modules", nv))}</dd></div>'
        f'<div><dt>Guard</dt><dd class="mono">{E(obs.get("guard", nv))}</dd></div>'
        f'<div><dt>Max held (policy)</dt><dd class="mono">$500 USDC</dd></div>'
        f'<div><dt>Status</dt><dd>{"Deposits open" if live else E(SPONSOR_OPENING)}</dd></div>'
        f'</dl></div>'
        f'<div class="table-scroll" role="region" aria-label="Public sponsor pool ledger" tabindex="0">'
        f'<table class="ix" data-sponsor-ledger-table>'
        f'<thead><tr><th>Pool ID</th><th>Target protocol</th><th>Tier</th><th>Deposit tx / amount</th><th>Status</th><th>Payout or refund tx</th></tr></thead>'
        f'<tbody><tr data-sponsor-ledger-empty><td colspan="6" class="s"><b>0 sponsor pools recorded.</b> No sponsor funds have been collected.</td></tr></tbody>'
        f'</table></div></section>'
    )


def bounties_page(idx, radar, bounties=None, claims=None, lb=None, claims3=None):
    """docs/bounties/index.html: Sponsor Verification Pools + Public Pool Ledger, Wave 3 active dossiers, and Wave 2 & Wave 1 archives."""
    d = load_bounties() if bounties is None else bounties
    claims = load_wave2_claims() if claims is None else claims
    claims3 = load_wave3_claims() if claims3 is None else claims3
    lb = load_leaderboard() if lb is None else lb
    prots_list = json.load(open(os.path.join(DOCS, "api", "v1", "protocols.json")))["protocols"]
    n_protocols = len(prots_list)
    n_rpc_observed = sum(1 for p_ in prots_list if not p_.get("easAttested"))
    w2_paid_n = sum(1 for p_ in lb["wave2Settlements"] if tx_ok(p_["payoutTxHash"]))
    pr = d["program"]
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    claude = f"claude mcp add --transport http pacta {MCP_URL}"
    slot_rows = "".join(f'<tr data-bounty-slot="{n}"><td class="num">#{n}</td><td class="num">$25 USDC</td><td>{E(BOUNTY_SLOTS[n])}</td>'
                        f'<td><a href="{E(BOUNTY_ISSUE_URLS[n])}" target="_blank" rel="noopener">Issue #{E(BOUNTY_ISSUE_URLS[n].rsplit("/", 1)[1])}{EXT}</a></td></tr>'
                        for n in (1, 2, 3, 4))
    proof = "".join(f"<li><b>{E(k)}.</b> {E(v)}</li>" for k, v in BOUNTY_PROOF)
    rules = "".join(f"<li><b>{E(k)}:</b> {E(v)}</li>" for k, v in BOUNTY_RULES)
    issues = "".join(f'<details class="bounty-issue" id="slot-{i["slot"]}" data-bounty-issue="{i["slot"]}"><summary>{E(i["title"])}</summary>'
                     f'<p class="s">GitHub: <a href="{E(BOUNTY_ISSUE_URLS[i["slot"]])}" target="_blank" rel="noopener">{E(BOUNTY_ISSUE_URLS[i["slot"]])}{EXT}</a> · labels: '
                     f'{E(", ".join(i["labels"]))}</p><div class="md">{wave1_md(i["body"])}</div></details>' for i in d["issues"])
    ld = {"@context": "https://schema.org", "@type": "WebPage",
          "name": "Pacta bounties · Wave 3 closed, in settlement · sponsor verification pools · Wave 2 & Wave 1 archives",
          "url": f"{BASE_URL}/bounties/",
          "isPartOf": {"@type": "WebSite", "name": "Pacta by Fractal Neurons", "url": f"{BASE_URL}/"},
          "about": "Human-researcher USDC bounties for DeFi protocol control-plane dossiers and sponsor-funded verification pools",
          "publisher": ORG_LD}
    ld_json = json.dumps(ld, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    body = f"""<body>
{topbar("../")}
<main id="main" class="memo-wrap">
<div class="crumbs"><a href="../">Pacta</a> / Bounties</div>
<article class="memo">
<header><span class="tier" data-bounty-pill>Wave 3 closed · in settlement · {len(W3_CLOSE["awards"])} × ${E(W3_CLOSE["awards"][0]["usdc"])} USDC awarded</span>
<p class="s" data-bounty-context>Wave 3 closed on {E(W3_CLOSE["closedOn"])} · Wave 2 ($1.00 micro-bounties) retired · Wave 1 Genesis (4/4 = $100 USDC) 100% settled on Base</p>
<h1>Wave 3 — 3-Year Protocol Trajectory &amp; Integrity Dossier</h1>
<p class="lede" data-bounty-lede>Wave 3 is closed and in settlement. Three dossiers won ${E(W3_CLOSE["awards"][0]["usdc"])} USDC each, three more receive a ${E(W3_CLOSE["honoraria"][0]["usdc"])} USDC honorarium, and up to four more can earn ${E(W3_CLOSE["signoff"]["usdc"])} USDC with a human sign-off within {W3_CLOSE["signoff"]["windowHours"]} hours. A payment shows as paid only once its Base transaction is public, and new checks are funded through the sponsor verification pools below.</p></header>
{sponsor_pool_section_html()}{wave3_section_html(claims3, n_protocols, lb, n_rpc_observed)}<section class="memo-sec" id="quickstart"><h2>1-line Remote MCP quickstart (free)</h2>
<div class="qs-snip"><span class="qs-l">Claude Code</span><code class="mono">{E(claude)}</code>{copy_btn(claude)}</div>
<p>Query <code>pacta_lookup_protocol</code>, <code>pacta_check_preflight</code> and <code>pacta_scan_control_plane</code> to check any protocol or contract for free, with no key and no wallet. Indexed protocols: <a href="../api/v1/protocols.json">protocol data</a>.</p></section>
<section class="memo-sec" id="completed-archives"><h2>Completed &amp; Retired Bounty Archives</h2>
<p class="s">Prior bounty waves are permanently closed to new submissions; their full on-chain Base USDC settlement ledgers remain archived below for public verification (<a href="../about/#official-addresses">official domains &amp; verified on-chain addresses</a>).</p></section>
<details class="archive-details" id="wave-2-archive" data-wave2-archive><summary><span>Archive: Wave 2 ($1.00 Micro-Bounties · {w2_paid_n}/{len(claims)} Slots Settled &amp; Retired) · {usdc(w2_paid_n * REWARD_ATOMIC)} USDC settled on Base</span></summary>
{wave2_section_html(claims, n_protocols, lb)}
</details>
<details class="archive-details" id="wave-1-archive" data-wave1-archive><summary><span>Archive: Wave 1 ($25.00 Genesis · Completed Early · Nov 17, 2026 · 4/4 Genesis Slots Settled) · $100.00 USDC settled on Base</span></summary>
<section class="memo-sec" id="wave-1"><h2>Wave 1 Genesis Archive · {E(BOUNTY_TITLE)}</h2>
<p class="s" data-wave1-snapshot><b>Historical Snapshot (Pinned at 53 Protocols on Nov 15)</b>: Completed Early · Nov 17, 2026 (4/4 Genesis Slots Settled). The Wave 1 terms below are archived verbatim from the 53-protocol launch snapshot at Nov 15, 2026; Wave 3 used the live <a href="../api/v1/protocols.json">protocol data</a>.</p>
<p>Find a live on-chain control-plane fact that contradicts a protocol's official documentation (<code>parameter_delta</code>). Four slots, <b>4 × $25 USDC = $100 USDC</b> in total, first valid merged PR per slot won. Organizer: {E(pr["organizer"])}. Completed early on Nov 17, 2026 (original window scheduled {bounty_hours(pr)}h from Nov 15).</p>
<h3>Wave 1 Genesis Settlement Ledger</h3>
{wave1_ledger_html(lb)}
<p class="s">Settled amounts appear only once a Base payout transaction hash is recorded in <code>bounties/leaderboard.json</code> (<code>tools/stamp_wave1_payouts.py</code>); each links to BaseScan.</p></section>
<section class="memo-sec" id="slots"><h2>Wave 1 slots (4 × $25 USDC · 4/4 Settled)</h2>
<table class="ix" data-bounty-slots><thead><tr><th>Slot</th><th>Reward</th><th>Scope</th><th>Issue</th></tr></thead><tbody>{slot_rows}</tbody></table>
<p>Total hard cap: <b>$100 USDC</b> across Slots #1–#4 (completed early on <b>Nov 17, 2026</b>; original scheduled window <code>{E(pr["sprintWindow"])}</code>, {bounty_hours(pr)}h).</p></section>
<section class="memo-sec" id="payout"><h2>How the Wave 1 reward is paid</h2>
<p data-bounty-payout>{E(BOUNTY_PAYOUT)}</p>
<p class="s">The Pacta treasury <code class="mono">{E(pr["treasuryAddress"])}</code> is an externally owned account (EOA) on {E(pr["settlementChain"])}; settlement happens after deterministic dual-RPC replay verification and maintainer merge.</p></section>
<section class="memo-sec" id="proof"><h2>Wave 1 required PR proof (all 6)</h2>
<ol>{proof}</ol>
<p>Open the PR to <code>Fractal-Neurons/pacta</code> with the <a href="{E(BOUNTY_TEMPLATE_URL)}" target="_blank" rel="noopener">bounty_mismatch.md PR template{EXT}</a> (<a href="{E(BOUNTY_COMPARE_URL)}" target="_blank" rel="noopener">pre-filled PR{EXT}</a>). Each PR commits exactly one JSON fixture at <code data-bounty-fixture>{E(BOUNTY_FIXTURE)}</code> (keys: <a href="{E(REPO)}/blob/main/bounties/submissions/README.md" target="_blank" rel="noopener">bounties/submissions/README.md{EXT}</a>). Check both offline before you submit: <code>python3 tools/verify_bounty_submission.py --json {E(BOUNTY_FIXTURE)}</code> and <code>python3 tools/verify_bounty_submission.py --body PR_BODY.md</code> (deterministic field checks; maintainers re-run the dual-RPC replay and the HTTP 200 docs check).</p>
<p><b>Apache-2.0:</b> by checking the grant box you grant Pacta by Fractal Neurons perpetual, irrevocable rights under Apache-2.0 to ingest, Base EAS-attest, publish on pacta.wtf, and commercialize the merged mismatch record.</p></section>
<section class="memo-sec" id="rules"><h2>Wave 1 anti-slop, fair-play &amp; safety rules</h2><ul>{rules}</ul></section>
<section class="memo-sec" id="issues"><h2>Wave 1 issue text (archived)</h2><p class="s">The four Wave 1 GitHub issues (#21–#24), word for word; index counts read as of Nov 15.</p>{issues}</section>
</details>
</article>
<div class="memo-foot"><span>Governance and documentation due-diligence dossiers only. Exploit-sensitive vulnerabilities are never published here; they go through Immunefi or Cantina bounty programmes.</span><a href="../protocols/">Indexed protocols{ARR}</a></div>
</main>
{footer(count_line, reg, "../")}
<script type="application/ld+json">{ld_json}</script>
</body></html>
"""
    return head("Bounties · Wave 3 closed, in settlement · sponsor verification pools · Pacta",
                f"Wave 3 closed on {W3_CLOSE['closedOn']} and is in settlement ({len(W3_CLOSE['awards'])} × ${W3_CLOSE['awards'][0]['usdc']} USDC awarded). Sponsor verification pools are opening soon (reservation or invoice only). Wave 2 ($1 micro-bounties) and Wave 1 (4 × $25) archives.",
                f"{BASE_URL}/bounties/", prefix="../",
                og_title="Pacta bounties · Wave 3 closed, in settlement") + "\n" + body


# ---- Wave 3 (2 x $20 USDC 3-Year Dossiers, OPEN) + Wave 2 ($1 micro-bounties, Completed & Retired) + Wave 1 Archive + /leaderboard/ ----
WAVE3_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bounty_wave3.json")
WAVE3 = json.load(open(WAVE3_SRC))
WAVE3_REWARD_USDC = WAVE3["rewardUsdc"]            # "20.00"
WAVE3_REWARD_ATOMIC = WAVE3["rewardAtomic"]        # 20_000_000
WAVE3_OPEN_SLOTS = WAVE3["openSlots"]              # 2
WAVE3_POOL_CAP_USDC = WAVE3["poolCapUsdc"]         # "40.00"
WAVE3_SETTLED_SLOTS = WAVE3["settledSlots"]        # 2 (#121, #127 paid on Base)
WAVE3_FUNDED_SLOTS = WAVE3["fundedUnencumberedSlots"]  # 0
WAVE3_FUNDED_USDC = WAVE3["fundedUnencumberedUsdc"]    # "0.00"
WAVE3_RESERVE_USDC = WAVE3["ringFencedReserveUsdc"]    # "0.05"
WAVE3_DIR = os.path.join(ROOT, *WAVE3["fixtureDir"].split("/"))
WAVE3_MASTER_ISSUE = os.path.join(ROOT, "bounties", "WAVE3-MASTER-ISSUE.md")
WAVE3_CHAINS_BY_ID = {int(k): v for k, v in WAVE3["chains"].items()}
WAVE3_NAME_RE = re.compile(r"^(" + "|".join(WAVE3_CHAINS_BY_ID.values()) + r")-([a-z0-9]+(?:-[a-z0-9]+)*)\.json$")
assert round(float(WAVE3_REWARD_USDC) * 10 ** WAVE3["settlement"]["decimals"]) == WAVE3_REWARD_ATOMIC
assert f"{WAVE3_REWARD_ATOMIC * WAVE3_OPEN_SLOTS / 10 ** 6:.2f}" == WAVE3_POOL_CAP_USDC
assert f"{WAVE3_REWARD_ATOMIC * WAVE3_FUNDED_SLOTS / 10 ** 6:.2f}" == WAVE3_FUNDED_USDC
assert WAVE3["settlement"]["chainId"] == 8453 and WAVE3["settlement"]["treasuryKind"] == "EOA"
WAVE3_PAYOUT = (f"Paid in USDC on Base Mainnet within {WAVE3['settlement']['windowDays']} days of maintainer merge and historical archive replay, "
                f"from the Pacta treasury ({WAVE3['settlement']['treasuryAddress']}, an externally owned account) directly to the base_payout_address "
                "committed in the merged bounties/wave-3 dossier. Funds are held on-chain in the EOA treasury and are not pre-escrowed in an automated contract.")

WAVE2_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bounty_wave2.json")
WAVE2 = json.load(open(WAVE2_SRC))
REWARD_USDC = WAVE2["rewardUsdc"]                  # "1.00"
REWARD_ATOMIC = WAVE2["rewardAtomic"]              # 1_000_000 (USDC has 6 decimals)
PROGRAM_CAP_SLOTS = WAVE2["programCapSlots"]       # 1,000-gap program (retired after Epoch 1 closeout)
CURRENT_EPOCH = WAVE2["currentEpoch"]
ACTIVE_EPOCH_SLOTS = WAVE2["activeEpochSlots"]
ACTIVE_EPOCH_CAP_USDC = WAVE2["activeEpochCapUsdc"]
PRIOR_EPOCH_SLOTS = WAVE2["priorEpochSlots"]
SETTLED_EPOCH_SLOTS = WAVE2["settledEpochSlots"]
FUNDED_UNENCUMBERED_SLOTS = WAVE2["fundedUnencumberedSlots"]
FUNDED_UNENCUMBERED_USDC = WAVE2["fundedUnencumberedUsdc"]
RING_FENCED_USDC, RING_FENCED_FOR = WAVE2["ringFencedUsdc"], WAVE2["ringFencedFor"]
PROGRAM_LABEL = WAVE2["program"]
USDC_BASE = WAVE2["settlement"]["tokenAddress"]
assert round(float(REWARD_USDC) * 10 ** WAVE2["settlement"]["decimals"]) == REWARD_ATOMIC
assert f"{REWARD_ATOMIC * ACTIVE_EPOCH_SLOTS / 10 ** 6:.2f}" == ACTIVE_EPOCH_CAP_USDC
assert 25 <= ACTIVE_EPOCH_SLOTS <= 100 and CURRENT_EPOCH >= 1 and 0 <= PRIOR_EPOCH_SLOTS
assert PRIOR_EPOCH_SLOTS + ACTIVE_EPOCH_SLOTS <= PROGRAM_CAP_SLOTS == 1000
assert 0 <= SETTLED_EPOCH_SLOTS and 0 <= FUNDED_UNENCUMBERED_SLOTS and SETTLED_EPOCH_SLOTS + FUNDED_UNENCUMBERED_SLOTS <= max(30, ACTIVE_EPOCH_SLOTS)
assert f"{REWARD_ATOMIC * FUNDED_UNENCUMBERED_SLOTS / 10 ** 6:.2f}" == FUNDED_UNENCUMBERED_USDC
EPOCH_REMAINING_USDC = f"{REWARD_ATOMIC * max(0, ACTIVE_EPOCH_SLOTS - SETTLED_EPOCH_SLOTS - FUNDED_UNENCUMBERED_SLOTS) / 10 ** 6:.2f}"
assert WAVE2["settlement"]["chainId"] == 8453 and USDC_BASE == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
assert WAVE2["settlement"]["treasuryKind"] == "EOA"
WAVE2_DIR = os.path.join(ROOT, *WAVE2["fixtureDir"].split("/"))
WAVE2_ISSUE_URL = WAVE2.get("wave2IssueUrl") or f"{REPO}/issues"
COMMUNITY_URL = WAVE3["communityUrl"]
COMMUNITY_QA_URL = WAVE3["communityQaUrl"]
assert COMMUNITY_URL == f"{REPO}/discussions" and COMMUNITY_QA_URL.startswith(COMMUNITY_URL + "/")
WAVE2_MASTER_ISSUE = os.path.join(ROOT, "bounties", "WAVE2-MASTER-ISSUE.md")
WAVE2_CHAINS_BY_ID = {int(k): v for k, v in WAVE2["chains"].items()}
WAVE2_NAME_RE = re.compile(r"^(" + "|".join(WAVE2_CHAINS_BY_ID.values()) + r")-([a-z0-9]+(?:-[a-z0-9]+)*)\.json$")
LEADERBOARD_SRC = os.path.join(ROOT, "bounties", "leaderboard.json")
HUNTER_BADGE_DIR = os.path.join(DOCS, "badges", "hunters")
HUNTER_FILE_RE = re.compile(r"^[A-Za-z0-9_-]{1,39}$")             # badge file name (strict; no dots, slashes or traversal)
GITHUB_USER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
FRAMEWORK_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,39}$")
TX_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
CHAIN_NAMES = {1: "Ethereum", 8453: "Base", 42161: "Arbitrum One", 10: "Optimism", 137: "Polygon PoS", 56: "BNB Chain", 43114: "Avalanche C-Chain"}
WAVE2_CATEGORY_TEXT = {
    "protocol_mismatch": "an unindexed protocol on Ethereum (1), Base (8453) or Arbitrum One (42161) with at least {tvl} of chain TVL, whose live "
                         "control plane (proxy admin, timelock delay, Safe threshold, guardian or role) contradicts its official documentation",
    "curated_vault_mismatch": "a curated vault or isolated market with at least {tvl} of vault TVL on Morpho (MetaMorpho), Euler V2 (EVK), Concrete, "
                              "Veda / BoringVault, Yearn V3, Pendle, Maple or Centrifuge on Ethereum, Base or Arbitrum One, where the on-chain curator(), "
                              "guardian(), owner(), timelock or role admin contradicts the HTTP-200 official documentation",
    "post_pin_drift": "live control-plane drift on any of Pacta's {n} indexed protocols since its pinned blockNumber (cite the pactaSlug and the prior pin)",
}
WAVE2_PAYOUT = (f"Paid in USDC on Base Mainnet in weekly batches, within {WAVE2['settlement']['windowDays']} days of maintainer merge, from the Pacta "
                f"treasury ({WAVE2['settlement']['treasuryAddress']}, an externally owned account) directly to the basePayoutAddress committed in the "
                "merged bounties/wave-2 fixture: no post-merge comment needed. Funds are not pre-escrowed in an automated contract; zero automatic "
                "on-chain payouts.")
# Inner geometry of the official mark (docs/logo.svg, comments / whitespace stripped): embedded in every hunter badge.
LOGO_SVG_INNER = ('<g fill="none" stroke-linecap="round">'
                  + "".join(f'<circle cx="{x}" cy="{y}" r="185" stroke="#000" stroke-width="38"/>'
                            f'<circle cx="{x}" cy="{y}" r="185" stroke="#fff" stroke-width="18"/>'
                            for x, y in ((240, 240), (760, 240), (240, 760), (760, 760)))
                  + '</g><polygon points="500,15 985,500 500,985 15,500" fill="#fff" stroke="#000" stroke-width="12" stroke-linejoin="miter"/>'
                  '<polygon points="500,125 875,500 500,875 125,500" fill="#000"/>'
                  '<path fill="#fff" fill-rule="evenodd" d="M380,335H535C610,335 655,378 655,442.5C655,507 610,550 535,550H458V665H380Z'
                  'M458,400V485H525C560,485 578,468 578,442.5C578,417 560,400 525,400Z"/>')


def usdc(atomic):
    return f"${atomic / 10 ** 6:,.2f}"


def tx_ok(h):
    """A real Base transaction hash: 0x + 64 hex, not all zero. Anything else never counts as settled."""
    return isinstance(h, str) and bool(TX_RE.match(h)) and int(h, 16) != 0


def tvl_label(cat):
    v = WAVE2["categories"][cat]["minTvlUsd"]
    return f"${v // 1_000_000}M"


def load_leaderboard(path=None):
    d = json.load(open(path or LEADERBOARD_SRC))
    assert d["schema"] == "pacta.bounty_leaderboard.v1"
    w1 = d["wave1Settlements"]
    assert [s["slot"] for s in w1] == [1, 2, 3, 4] and [s["issue"] for s in w1] == [21, 22, 23, 24]
    assert all(f"{REPO}/issues/{s['issue']}" == BOUNTY_ISSUE_URLS[s["slot"]] for s in w1)
    for s in w1:
        assert s["status"] in ("verified", "in_review"), s
        assert s["payoutTxHash"] is None or tx_ok(s["payoutTxHash"]), f"slot {s['slot']}: payoutTxHash must be null or a real 0x + 64-hex tx"
        assert s["payoutTxHash"] is None or s["status"] == "verified", f"slot {s['slot']}: only a verified slot can be settled"
        if s["status"] == "verified":
            assert GITHUB_USER_RE.match(s["hunter"]) and isinstance(s["pr"], int) and s["protocol"] and s["chainId"] in CHAIN_NAMES, s
            assert s["agentFramework"] is None or FRAMEWORK_RE.match(s["agentFramework"]), s
            assert s["rewardUsdc"] == "25.00"
    for p in d["wave2Settlements"]:
        assert WAVE2_NAME_RE.match(p["fixture"]) and tx_ok(p["payoutTxHash"]), p
    assert PRIOR_EPOCH_SLOTS + SETTLED_EPOCH_SLOTS <= len(d["wave2Settlements"]) <= 30, \
        "Wave 2 paid settlements must match completed Epoch 1 / closeout settlements"
    for p3 in d.get("wave3Settlements", []):
        assert WAVE3_NAME_RE.match(p3["fixture"]) and tx_ok(p3["payoutTxHash"]), p3
    assert len(d.get("wave3Settlements", [])) == WAVE3_SETTLED_SLOTS
    assert all(GITHUB_USER_RE.match(h) and isinstance(n, int) and n >= 0 for h, n in d["easAttestations"].items())
    for c in d.get("wave2Credits", []):
        assert set(c) == {"fixture", "pr", "pactaSlug", "record"} and WAVE2_NAME_RE.match(c["fixture"]) and isinstance(c["pr"], int), c
        assert SLUG_RE.fullmatch(c["pactaSlug"]) and SLUG_RE.fullmatch(c["record"]), c
    assert len({c["fixture"] for c in d.get("wave2Credits", [])}) == len(d.get("wave2Credits", []))
    return d


def load_wave2_claims(path=None):
    """Merged Wave 2 claims (bounties/wave-2/*.json), sorted by file name (Completed & Retired archive)."""
    d = path or WAVE2_DIR
    out = []
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not name.endswith(".json"):
            continue
        m = WAVE2_NAME_RE.match(name)
        f = json.load(open(os.path.join(d, name)))
        assert m and f.get("wave") == 2 and f.get("slug") == m.group(2) and CHAIN_NAMES.get(f.get("chainId")) is not None, name
        assert WAVE2_CHAINS_BY_ID[f["chainId"]] == m.group(1), name
        assert f.get("category") in WAVE2["categories"] and GITHUB_USER_RE.match(str(f.get("hunter"))), name
        assert f.get("agentFramework") is None or FRAMEWORK_RE.match(f["agentFramework"]), name
        out.append({**f, "_file": name})
    assert len(out) <= max(30, PRIOR_EPOCH_SLOTS + SETTLED_EPOCH_SLOTS + FUNDED_UNENCUMBERED_SLOTS), \
        "Wave 2 merged claims cannot exceed completed closeout capacity"
    assert len({(c["chainId"], c["contractAddress"].lower()) for c in out}) == len(out) and len({c["slug"] for c in out}) == len(out)
    return out


def load_wave3_claims(path=None):
    """Merged Wave 3 3-Year Dossiers (bounties/wave-3/*.json), sorted by file name."""
    d = path or WAVE3_DIR
    out = []
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not name.endswith(".json"):
            continue
        m = WAVE3_NAME_RE.match(name)
        f = json.load(open(os.path.join(d, name)))
        assert m and f.get("wave") == 3 and f.get("slug") == m.group(2) and f.get("chain") == m.group(1), name
        assert WAVE3_CHAINS_BY_ID.get(f.get("chain_id")) == m.group(1), name
        assert GITHUB_USER_RE.match(str(f.get("contributor_github"))), name
        out.append({**f, "_file": name})
    assert len(out) <= WAVE3_SETTLED_SLOTS + WAVE3_FUNDED_SLOTS, "Wave 3 merged dossiers cannot exceed funded unencumbered slots"
    assert len({(c["chain_id"], c["contract_address"].lower()) for c in out}) == len(out) and len({c["slug"] for c in out}) == len(out)
    return out


def hunter_stats(lb, claims, claims3=None):
    """Per-hunter aggregates from Wave 1 + Wave 2 + Wave 3. Settled USDC counts ONLY payouts with a real tx hash."""
    claims3 = load_wave3_claims() if claims3 is None else claims3
    paid2 = {p["fixture"]: p["payoutTxHash"] for p in lb["wave2Settlements"]}
    paid3 = {p["fixture"]: p["payoutTxHash"] for p in lb.get("wave3Settlements", [])}
    credits2 = {c["fixture"]: c for c in lb.get("wave2Credits", [])}
    credits3 = {c["fixture"]: c for c in lb.get("wave3Credits", [])}
    st = {}

    def add(handle, fw, proto_key, catch, settled_atomic, tx, credit=None):
        h = st.setdefault(handle.lower(), {"handle": handle, "frameworks": [], "catches": [], "protocols": set(), "proto_names": [],
                                           "settled": 0, "txs": [], "credits": [], "eas": lb["easAttestations"].get(handle, 0)})
        if fw and fw not in h["frameworks"]:
            h["frameworks"].append(fw)
        h["catches"].append(catch)
        h["protocols"].add(proto_key)
        if catch["protocol"] not in h["proto_names"]:
            h["proto_names"].append(catch["protocol"])
        if credit:
            h["credits"].append(credit)
        if tx:
            h["settled"] += settled_atomic
            h["txs"].append(tx)
    for s in lb["wave1Settlements"]:
        if s["status"] == "verified":
            tx = s["payoutTxHash"] if tx_ok(s["payoutTxHash"]) else None
            add(s["hunter"], s["agentFramework"], f"{s['chainId']}:{s['protocol'].lower()}",
                {"wave": 1, "label": f"Wave 1 · Slot #{s['slot']} · PR #{s['pr']}", "href": f"{REPO}/pull/{s['pr']}", "protocol": s["protocol"]},
                25 * 10 ** 6, tx)
    for i, c in enumerate(claims, 1):
        tx = paid2.get(c["_file"])
        add(c["hunter"], c.get("agentFramework"), f"{c['chainId']}:{c['slug']}",
            {"wave": 2, "label": f"Wave 2 · Slot #{i}", "href": f"{REPO}/blob/main/{WAVE2['fixtureDir']}/{c['_file']}", "protocol": c["protocol"]},
            REWARD_ATOMIC, tx if tx_ok(tx) else None, credits2.get(c["_file"]))
    for i, c3 in enumerate(claims3, 1):
        tx = paid3.get(c3["_file"])
        add(c3["contributor_github"], c3.get("agent_assist_framework") or "human-researcher", f"{c3['chain_id']}:{c3['slug']}",
            {"wave": 3, "label": f"Wave 3 · Dossier #{i}", "href": f"{REPO}/blob/main/{WAVE3['fixtureDir']}/{c3['_file']}", "protocol": c3["protocol_name"]},
            WAVE3_REWARD_ATOMIC, tx if tx_ok(tx) else None, credits3.get(c3["_file"]))
    rows = sorted(st.values(), key=lambda h: (-len(h["catches"]), -len(h["protocols"]), -h["eas"], -h["settled"], h["handle"].lower()))
    rank, prev = 0, None
    for i, h in enumerate(rows):                    # standard competition ranking: equal metrics share a rank
        key = (len(h["catches"]), len(h["protocols"]), h["eas"], h["settled"])
        rank = rank if key == prev else i + 1
        h["rank"], prev = rank, key
    return rows


def framework_stats(rows):
    fw = {}
    for h in rows:
        for name in h["frameworks"] or ["not stated"]:
            f = fw.setdefault(name, {"name": name, "hunters": 0, "catches": 0, "protocols": set(), "settled": 0})
            f["hunters"] += 1
            f["catches"] += len(h["catches"])
            f["protocols"] |= h["protocols"]
            f["settled"] += h["settled"]
    return sorted(fw.values(), key=lambda f: (f["name"] == "not stated", -f["catches"], -len(f["protocols"]), f["name"]))


def hunter_badge_dims(handle, catches):
    """(left text, right text, left width, right width) of a hunter badge; the leaderboard declares lw + rw as the <img> width."""
    left, right = "Pacta hunter", f"{handle} · {catches} verified"
    return left, right, 24 + round(len(left) * 6.6) + 8, round(len(right) * 6.6) + 14


def hunter_badge_width(handle, catches):
    _, _, lw, rw = hunter_badge_dims(handle, catches)
    return lw + rw


def hunter_badge_svg(handle, catches):
    """Deterministic static README badge for a hunter: the official Pacta mark + '<handle> · N verified'. Every dynamic string is
    XML-escaped and the handle must match HUNTER_FILE_RE (no traversal, no markup)."""
    from xml.sax.saxutils import escape, quoteattr
    import xml.etree.ElementTree as ET
    if not (isinstance(handle, str) and HUNTER_FILE_RE.fullmatch(handle)):
        raise ValueError(f"refusing hunter badge for handle {handle!r}")
    left, right, lw, rw = hunter_badge_dims(handle, catches)
    label = f"{left}: {right} control-plane catch{'es' if catches != 1 else ''}"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{lw + rw}" height="20" viewBox="0 0 {lw + rw} 20" role="img" aria-label={quoteattr(label)}>'
           f"<title>{escape(label)}</title>"
           f'<rect width="{lw}" height="20" fill="#f4f4f2"/><rect x="{lw}" width="{rw}" height="20" fill="#14161a"/>'
           f'<rect x="0.5" y="0.5" width="{lw + rw - 1}" height="19" fill="none" stroke="#14161a"/>'
           f'<svg x="4" y="2" width="16" height="16" viewBox="0 0 1000 1000">{LOGO_SVG_INNER}</svg>'
           f'<g font-family="Verdana,DejaVu Sans,Geneva,sans-serif" font-size="11">'
           f'<text x="24" y="14" fill="#14161a">{escape(left)}</text><text x="{lw + 7}" y="14" fill="#ffffff">{escape(right)}</text></g></svg>\n')
    ET.fromstring(svg)                               # valid XML or the build fails
    return svg


def hunter_badge_path(handle, base=None):
    """docs/badges/hunters/<handle>.svg, refusing any handle that is not a plain file name inside the badge directory."""
    base = os.path.realpath(base or HUNTER_BADGE_DIR)
    if not (isinstance(handle, str) and HUNTER_FILE_RE.fullmatch(handle)):
        raise ValueError(f"refusing hunter badge path for {handle!r}")
    p = os.path.realpath(os.path.join(base, handle + ".svg"))
    if os.path.dirname(p) != base:
        raise ValueError(f"hunter badge path escapes {base}: {p}")
    return p


def write_hunter_badges(rows, base=None):
    base = base or HUNTER_BADGE_DIR
    os.makedirs(base, exist_ok=True)
    keep = set()
    for h in rows:
        p = hunter_badge_path(h["handle"], base)
        with open(p, "w") as fh:
            fh.write(hunter_badge_svg(h["handle"], len(h["catches"])))
        keep.add(os.path.basename(p))
    for name in os.listdir(base):                    # deterministic directory: drop badges of hunters no longer listed
        if name.endswith(".svg") and name not in keep and HUNTER_FILE_RE.fullmatch(name[:-4]):
            os.remove(os.path.join(base, name))


def badge_markdown(handle):
    return f"[![Pacta hunter: {handle}]({BASE_URL}/badges/hunters/{handle}.svg)]({BASE_URL}/leaderboard/#{handle.lower()})"


def share_x_href(h):
    n = len(h["catches"])
    text = (f"Verified Base-EAS DeFi researcher credential on Pacta (@pacta_fractal): @{h['handle']} — {n} merged on-chain control-plane "
            f"catch{'es' if n != 1 else ''} across {len(h['protocols'])} protocol{'s' if len(h['protocols']) != 1 else ''} "
            f"(settled in USDC on Base Mainnet)")
    return "https://x.com/intent/tweet?" + urllib.parse.urlencode({"text": text, "url": f"{BASE_URL}/leaderboard/#{h['handle'].lower()}"})


def share_linkedin_href(h):
    return "https://www.linkedin.com/sharing/share-offsite/?" + urllib.parse.urlencode({"url": f"{BASE_URL}/leaderboard/#{h['handle'].lower()}"})


def settled_cell(atomic, txs, pending="$0.00 (pending settlement)"):
    if not txs:
        return f'<span class="s" data-settled="pending">{E(pending)}</span>'
    links = " ".join(f'<a href="https://basescan.org/tx/{E(t)}" target="_blank" rel="noopener" data-basescan-tx>tx {E(short(t, 6, 4))}{EXT}</a>'
                     for t in dict.fromkeys(txs))
    return f'<b data-settled="{atomic}">{usdc(atomic)} USDC</b> <span class="s">{links}</span>'


def wave1_ledger_html(lb):
    rows = []
    for s in lb["wave1Settlements"]:
        issue = f'<a href="{E(BOUNTY_ISSUE_URLS[s["slot"]])}" target="_blank" rel="noopener">Issue #{s["issue"]}{EXT}</a>'
        if s["status"] != "verified":
            rows.append(f'<tr data-w1-slot="{s["slot"]}"><td class="num">#{s["slot"]}</td><td>{issue}</td><td>—</td><td>—</td><td>—</td>'
                        f'<td class="num">${E(s["rewardUsdc"])} USDC</td><td>{E(s["statusNote"] or "In review")}</td><td>—</td></tr>')
            continue
        tx = s["payoutTxHash"] if tx_ok(s["payoutTxHash"]) else None
        status = "Settled on Base" if tx else "Verified · settlement pending"
        rows.append(f'<tr data-w1-slot="{s["slot"]}"><td class="num">#{s["slot"]}</td><td>{issue}</td>'
                    f'<td><a href="{E(REPO)}/pull/{s["pr"]}" target="_blank" rel="noopener">PR #{s["pr"]}{EXT}</a></td>'
                    f'<td><a href="https://github.com/{E(s["hunter"])}" target="_blank" rel="noopener">@{E(s["hunter"])}</a></td>'
                    f'<td>{E(s["protocol"])} <span class="s">({E(CHAIN_NAMES[s["chainId"]])})</span></td>'
                    f'<td class="num">${E(s["rewardUsdc"])} USDC</td><td>{E(status)}</td>'
                    f'<td>{settled_cell(25 * 10 ** 6, [tx] if tx else [])}</td></tr>')
    return ('<table class="ix" data-wave1-ledger><thead><tr><th>Slot</th><th>Issue</th><th>PR</th><th>Hunter</th><th>Protocol</th><th>Reward</th>'
            f'<th>Status</th><th>Settled (Base USDC)</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')


def _rpc_observed_count():
    prots_p = os.path.join(DOCS, "api", "v1", "protocols.json")
    if not os.path.exists(prots_p):
        return 0
    return sum(1 for p_ in json.load(open(prots_p))["protocols"] if not p_.get("easAttested"))


def wave3_master_issue_md(n_protocols, n_obs=None):
    """bounties/WAVE3-MASTER-ISSUE.md: deterministic Wave 3 GitHub Master Issue draft generated from tools/bounty_wave3.json."""
    s = WAVE3["settlement"]
    n_obs = _rpc_observed_count() if n_obs is None else n_obs
    n_eas = n_protocols - n_obs
    chains_md = ", ".join(f"`{v}` ({k})" for k, v in WAVE3["chains"].items())
    rules = "\n".join(f"- {r}." for r in WAVE3["rules"])
    return f"""# {WAVE3['title']}

> **Closed / in settlement:** {W3_CLOSE_SUMMARY} The rules below are archived; Wave 3 takes no new submissions.

**{WAVE3['program']}.** **Wave 3 offered {WAVE3_OPEN_SLOTS} human-researcher dossier slots (`{WAVE3_OPEN_SLOTS} × ${WAVE3_REWARD_USDC} USDC = ${WAVE3_POOL_CAP_USDC} USDC`).** Settled on {s['network']} from `{s['treasuryAddress']}` (an externally owned account, chainId {s['chainId']}, USDC `{s['tokenAddress']}`): **${WAVE3_REWARD_ATOMIC * WAVE3_SETTLED_SLOTS / 10 ** 6:.2f} USDC ({WAVE3_SETTLED_SLOTS} slots)**; unencumbered Wave 3 capacity now: **${WAVE3_FUNDED_USDC} USDC ({WAVE3_FUNDED_SLOTS} slots)** plus `${WAVE3_RESERVE_USDC}` operational buffer. Wave 2 (`$1.00` single-gap micro-bounties) and Wave 1 (`4 × $25.00 = $100.00 USDC` Genesis) are permanently completed and retired. Live board: https://pacta.wtf/bounties/#wave-3 · Researcher credentials & leaderboard: https://pacta.wtf/leaderboard/

## Eligible Targets (`>= USD 10M` TVL Across 7 EVM Chains + `{n_obs}` Unassessed On-Chain Records Unlocked)

- **Chains:** {chains_md}
- **TVL Floor:** `tvl_usd >= 10,000,000` (USD 10M+ verified on DefiLlama or official analytics)
- **Unassessed on-chain records unlocked:** All **{n_obs} unassessed on-chain records (`rpc_observed`, `easAttested: false`)** in the [protocol data](https://pacta.wtf/api/v1/protocols.json) are eligible alongside unindexed USD 10M+ protocols (only the {n_eas} already Base-EAS attested protocols are excluded as duplicates).

## Mandatory 3-Part Human-Researcher Dossier (`2023–2026`)

1. **Part 1 — 3-Year On-Chain Control-Plane Timeline (`historical_transitions`):** `>= 2` distinct chronological blocks (`strictly increasing` `block_number` + `block_date` + `tx_hash` + reproducible `cast`/RPC proof) reconstructing proxy implementation upgrades, multi-owner signer/threshold changes, or timelock mutations across `2023–2026` (or multi-block proof of 3-year immutability + controller verification).
2. **Part 2 — Historical Docs & DAO Governance Forensics (`docs_and_governance_forensics`):** `>= 2` dated archival sources (including at least one dated GitHub docs commit/blob/PR, `web.archive.org` snapshot, or Snapshot/Tally/Discourse governance proposal) proving historical gap windows and the **time taken to correct outdated documentation** (`mttr_days` or `unrepaired_open` duration).
3. **Part 3 — Repository & Engineering Reality Audit + Executive Risk Memo (`repo_audit` + `executive_risk_memo`):** 12-month smart-contract commits (`commits_12m_contracts`), non-contract commits (`commits_12m_frontend_or_other`), distinct human contributors (`human_contributors_12m`), `bus_factor`, `code_before_upgrade_verified` (`true`/`false`), and a substantive **`>= {WAVE3['minMemoChars']}`-character `executive_risk_memo`** (shallow 1-liner or repetitive bot spam is deterministically rejected).

**Submission & Attribution Metadata:** `contributor_github`, EIP-55 `base_payout_address`, `mcp_tool_receipt` from `{MCP_URL}`, `apache2_commercial_grant: true`, and `rules_accepted: [true, true, true, true]`.

## How to Validate & Submit

1. Query Pacta's free keyless MCP server (`claude mcp add --transport http pacta {MCP_URL}`) and save the tool output in `mcp_tool_receipt`.
2. Commit **one** newly added JSON dossier at `{WAVE3['fixtureDir']}/<chain>-<slug>.json` (full schema & valid example: `{WAVE3['fixtureDir']}/README.md`).
3. Validate locally before opening your PR: `python3 tools/verify_bounty_submission.py --wave 3 --json {WAVE3['fixtureDir']}/<chain>-<slug>.json`
4. Open a PR to `Fractal-Neurons/pacta`. CI (`verify-bounty-pr`) validates the single added JSON file with the base-branch validator; maintainers replay every historical block and archival commit before merging.

## Payout

{WAVE3_PAYOUT}

## Questions

Ask in Community Q&A (GitHub Discussions): {COMMUNITY_URL} · Builder & Bounty Q&A thread: {COMMUNITY_QA_URL}

## Rules

{rules}
"""


def write_wave3_master_issue(idx, path=None):
    prots_list = json.load(open(os.path.join(DOCS, "api", "v1", "protocols.json")))["protocols"]
    n = len(prots_list)
    n_obs = sum(1 for p_ in prots_list if not p_.get("easAttested"))
    with open(path or WAVE3_MASTER_ISSUE, "w") as fh:
        fh.write(wave3_master_issue_md(n, n_obs))


W3_CLOSE = WAVE3["closeout"]
W3_STATE = {"paid": "Paid on Base", "paying": "Awarded · payment in progress", "approved_awaiting_topup": "Awarded · approved, waiting for a Base USDC top-up",
            "awaiting_topup": "Awarded · waiting for a Base USDC top-up", "awaiting_signoff": "Waiting for a human sign-off comment"}
W3_CLOSE_SUMMARY = (f"Wave 3 closed on {W3_CLOSE['closedOn']} and is in settlement: {len(W3_CLOSE['awards'])} dossiers awarded "
                    f"${W3_CLOSE['awards'][0]['usdc']} USDC each (" + ", ".join(f"#{a['pr']} {a['protocol']}" for a in W3_CLOSE["awards"]) + "), "
                    f"{len(W3_CLOSE['honoraria'])} honoraria of ${W3_CLOSE['honoraria'][0]['usdc']} USDC with published credit and first call on the "
                    f"first sponsored pool (" + ", ".join(f"#{h['pr']} {h['protocol']}" for h in W3_CLOSE["honoraria"]) + "), and up to "
                    f"{len(W3_CLOSE['signoff']['prs'])} × ${W3_CLOSE['signoff']['usdc']} USDC for a human sign-off comment on the already-audited PR head "
                    f"within {W3_CLOSE['signoff']['windowHours']} hours (" + ", ".join(f"#{n}" for n in W3_CLOSE["signoff"]["prs"]) + "). "
                    "A payment counts as paid only once its Base transaction is public.")
assert WAVE3["status"] == "closed_in_settlement" and all(a["state"] in W3_STATE for a in W3_CLOSE["awards"] + W3_CLOSE["honoraria"])


def wave3_paid_prs(lb):
    """PR number -> payout tx for Wave 3 close-out payments that have a public Base transaction (bounties/leaderboard.json)."""
    return {int(p["pr"]): p["payoutTxHash"] for p in lb.get("wave3Settlements", []) if p.get("pr") and tx_ok(p.get("payoutTxHash", ""))}


def wave3_section_html(claims3, n_protocols, lb=None, n_obs=None):
    """Wave 3 on /bounties/: closed and in settlement. The close-out ledger (awards, honoraria, the sign-off window) comes from
    tools/bounty_wave3.json; a row reads "Paid on Base" only with a public Base transaction in bounties/leaderboard.json. The rules
    and the master issue stay readable as a collapsed archive, closed to new submissions."""
    lb = load_leaderboard() if lb is None else lb
    n_obs = _rpc_observed_count() if n_obs is None else n_obs
    n_eas = n_protocols - n_obs
    paid = wave3_paid_prs(lb)
    paid3 = {p["fixture"]: p["payoutTxHash"] for p in lb.get("wave3Settlements", []) if p.get("fixture") and tx_ok(p["payoutTxHash"])}
    chains_inline = ", ".join(f"{CHAIN_NAMES[int(k)]} ({v})" for k, v in WAVE3["chains"].items())

    assert all(a["pr"] in paid for a in W3_CLOSE["awards"] + W3_CLOSE["honoraria"] if a["state"] == "paid"), "a paid Wave 3 row needs its Base tx"
    receipts = {a["pr"]: a["receipt"] for a in W3_CLOSE["awards"] + W3_CLOSE["honoraria"]}
    receipts.update({int(k): v for k, v in W3_CLOSE["signoff"]["receipts"].items()})

    def pr_link(n):   # the PR's published close-out receipt (comment), else the PR itself
        return f'<a href="{E(receipts.get(n) or f"{REPO}/pull/{n}")}" target="_blank" rel="noopener">#{n}{EXT}</a>'

    def status_cell(pr, state):
        tx = paid.get(pr)
        if tx:
            return (f'<span data-slot="badge" data-variant="neutral">Paid on Base</span> '
                    f'<a href="https://basescan.org/tx/{E(tx)}" target="_blank" rel="noopener">{E(short(tx, 6, 4))}{EXT}</a>')
        return E(W3_STATE[state])

    rows = "".join(f'<tr data-wave3-award="{a["pr"]}"><td>{pr_link(a["pr"])}</td><td><b>{E(a["protocol"])}</b></td>'
                   f'<td class="num">${E(a["usdc"])} USDC award</td><td>{status_cell(a["pr"], a["state"])}</td></tr>' for a in W3_CLOSE["awards"])
    rows += "".join(f'<tr data-wave3-honorarium="{h["pr"]}"><td>{pr_link(h["pr"])}</td><td><b>{E(h["protocol"])}</b></td>'
                    f'<td class="num">${E(h["usdc"])} USDC honorarium</td><td>{status_cell(h["pr"], h["state"])}</td></tr>' for h in W3_CLOSE["honoraria"])
    so = W3_CLOSE["signoff"]
    rows += (f'<tr data-wave3-signoff><td>{" ".join(pr_link(n) for n in so["prs"])}</td><td>Already-audited PRs</td>'
             f'<td class="num">up to ${E(so["usdc"])} USDC each</td><td>{E(W3_STATE["awaiting_signoff"])} on the audited PR head, '
             f'within {so["windowHours"]} hours of the close-out</td></tr>')
    n_paid = len(paid)
    treasury = f'<code class="mono">{E(short(WAVE3["settlement"]["treasuryAddress"], 6, 4))}</code>'
    paid_links = " and ".join(f'#{n} (<a href="https://basescan.org/tx/{E(t)}" target="_blank" rel="noopener">tx {E(short(t, 6, 4))}{EXT}</a>)'
                              for n, t in sorted(paid.items()))
    capacity = (f'Paid on Base from the Wave 3 treasury {treasury}: {paid_links}, ${E(W3_CLOSE["awards"][0]["usdc"])} USDC each. '
                f'The other awards wait for a Base USDC top-up; no date is promised.' if paid else
                f'Held for these payouts: <b>${E(W3_CLOSE["heldUsdc"])} USDC</b> in the Base treasury {treasury}, which covers #121 and #127. '
                f'The other awards wait for a Base USDC top-up; no date is promised.')
    rows3 = "".join(
        f'<tr data-wave3-claim="{E(c["_file"])}"><td class="num">#{i}</td>'
        f'<td><a href="{E(REPO)}/blob/main/{E(WAVE3["fixtureDir"])}/{E(c["_file"])}" target="_blank" rel="noopener"><code>{E(c["_file"])}</code>{EXT}</a></td>'
        f'<td><b>{E(c["protocol_name"])}</b><div class="s">{E(c["chain"])} · {E(c["dossier_window"])}</div></td>'
        f'<td><a class="lb-handle" href="https://github.com/{E(c["contributor_github"])}" target="_blank" rel="noopener">@{E(c["contributor_github"])}</a></td>'
        f'<td>{settled_cell(WAVE3_REWARD_ATOMIC, [paid3[c["_file"]]] if c["_file"] in paid3 else [])}</td></tr>'
        for i, c in enumerate(claims3, 1)
    )
    merged = (f'<h4>Merged Wave 3 dossiers</h4><div class="table-scroll" role="region" aria-label="Merged Wave 3 dossiers" tabindex="0">'
              f'<table class="ix w2-table" data-wave3-claims><thead><tr><th>#</th><th>Dossier</th><th>Protocol / window</th><th>Researcher</th>'
              f'<th>Settled (Base USDC)</th></tr></thead><tbody>{rows3}</tbody></table></div>' if claims3 else "")
    master3 = md_html(wave3_master_issue_md(n_protocols, n_obs).split("\n", 2)[2])
    return f"""<section class="memo-sec" id="wave-3" data-wave3-active data-wave3-status="{E(WAVE3["status"])}">
<h2>Wave 3 close-out</h2>
<div class="w3-banner" data-wave3-closeout>
<div><b>Closed on {E(W3_CLOSE["closedOn"])} · in settlement</b> · {len(W3_CLOSE["awards"])} × ${E(W3_CLOSE["awards"][0]["usdc"])} USDC awarded · {len(W3_CLOSE["honoraria"])} × ${E(W3_CLOSE["honoraria"][0]["usdc"])} USDC honoraria · up to {len(so["prs"])} × ${E(so["usdc"])} USDC on sign-off · <b data-wave3-paid="{n_paid}">{n_paid} paid on Base so far</b></div>
<div class="s" data-wave3-capacity>{capacity}</div>
</div>
<div class="table-scroll" role="region" aria-label="Wave 3 settlement ledger" tabindex="0"><table class="ix w2-table" data-wave3-ledger>
<thead><tr><th>PR</th><th>Protocol</th><th>Amount</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="s">Each honorarium also carries published credit and first call on the first sponsored pool. A row reads paid only once its Base transaction is public. Each PR number links its published close-out receipt; the other {len(W3_CLOSE["closedUnpaid"])} Wave 3 PRs were closed without an award (<a href="{E(W3_CLOSE["closeoutUrl"])}" target="_blank" rel="noopener">close-out notice{EXT}</a>).</p>
{merged}
<details class="archive-details" id="wave-3-rules" data-wave3-rules><summary><span>Wave 3 rules and dossier format (archived · closed to new submissions)</span></summary>
<p><b>Eligible targets:</b> protocols with at least USD 10 million TVL across {E(chains_inline)}, including the {n_obs} unassessed on-chain records in the <a href="../api/v1/protocols.json">protocol data</a> (only the {n_eas} already Base-EAS attested protocols were excluded).</p>
<h3>The 3-part dossier (2023–2026)</h3>
<div class="w3-parts">
<article class="w3-part" data-wave3-part="1"><span class="w3-part-k">Part 1 · On-Chain Timeline</span><h4>3-Year Control-Plane Transitions</h4><p><code>historical_transitions</code> across ≥ 2 distinct chronological blocks + <code>tx_hash</code> + reproducible <code>cast</code>/RPC proofs covering proxy upgrades, signer/threshold rotations, and timelock mutations (or 3-year immutability proof).</p></article>
<article class="w3-part" data-wave3-part="2"><span class="w3-part-k">Part 2 · Archival Forensics</span><h4>Historical Docs, DAO Votes &amp; Repair Time</h4><p><code>docs_and_governance_forensics</code> citing dated GitHub docs commits, <code>web.archive.org</code> snapshots, and Snapshot/Tally/Discourse proposals proving historical gap windows and the time taken to correct outdated documentation.</p></article>
<article class="w3-part" data-wave3-part="3"><span class="w3-part-k">Part 3 · Engineering &amp; Memo</span><h4>12m Repo Audit + ≥ 400-Char Risk Memo</h4><p><code>repo_audit</code> (<code>github_org_repo</code>, 12m contract vs other commits, human contributors, <code>bus_factor</code>, pre-upgrade commit check) plus a clinical <code>executive_risk_memo</code> (≥ 400 chars; shallow bot spam rejected).</p></article>
</div>
<p class="s" data-wave3-meta><b>Submission &amp; attribution metadata:</b> <code>contributor_github</code>, EIP-55 <code>base_payout_address</code>, <code>mcp_tool_receipt</code> from <code>{E(MCP_URL)}</code>, <code>apache2_commercial_grant: true</code>, and <code>rules_accepted: [true, true, true, true]</code>.</p>
<ul><li>Format: one JSON dossier at <code data-wave3-fixture>{E(WAVE3["fixtureDir"])}/&lt;chain&gt;-&lt;slug&gt;.json</code> (schema &amp; example: <a href="{E(REPO)}/blob/main/{E(WAVE3["fixtureDir"])}/README.md" target="_blank" rel="noopener">{E(WAVE3["fixtureDir"])}/README.md{EXT}</a>), checked with <code>python3 tools/verify_bounty_submission.py --wave 3 --json {E(WAVE3["fixtureDir"])}/&lt;chain&gt;-&lt;slug&gt;.json</code>.</li>
<li data-wave3-payout>{E(WAVE3_PAYOUT)}</li></ul>
</details>
<details class="bounty-issue" id="wave-3-issue" data-wave3-issue-text><summary>{E(WAVE3["title"])} (archived)</summary><div class="md">{master3}</div></details>
<p data-community>Questions about the close-out? Ask in <a href="{E(COMMUNITY_URL)}" target="_blank" rel="noopener">Community Q&amp;A (Discussions){EXT}</a> (<a href="{E(COMMUNITY_QA_URL)}" target="_blank" rel="noopener">Builder &amp; Bounty Q&amp;A thread{EXT}</a>) · <a href="../leaderboard/">Hunter leaderboard &amp; verified researcher credentials{ARR}</a></p>
</section>
"""


def wave2_master_issue_md(n_protocols):
    """bounties/WAVE2-MASTER-ISSUE.md: archived Wave 2 GitHub issue #41 text (Completed & Retired)."""
    s = WAVE2["settlement"]
    cats = "\n".join(f"{i}. **{WAVE2['categories'][c]['label']} (`{c}`):** "
                     + WAVE2_CATEGORY_TEXT[c].format(tvl=tvl_label(c) if WAVE2["categories"][c]["minTvlUsd"] else "", n=n_protocols) + "."
                     for i, c in enumerate(WAVE2["categories"], 1))
    rules = "\n".join(f"- {r}." for r in WAVE2["rules"])
    return f"""# {WAVE2['title']}

> **Completed & Retired Archive:** Wave 2 (`$1.00 USDC` single-gap micro-bounties) is permanently closed and retired. Wave 3 (`2 × $20.00 USDC` 3-Year Protocol Trajectory & Integrity Dossiers) closed on {W3_CLOSE['closedOn']} and is in settlement: https://pacta.wtf/bounties/#wave-3

**{PROGRAM_LABEL} (Completed & Retired).** Epoch {CURRENT_EPOCH} (`{ACTIVE_EPOCH_SLOTS} × ${REWARD_USDC} USDC = ${ACTIVE_EPOCH_CAP_USDC} USDC`) is settled on {s['network']} (chainId {s['chainId']}, USDC `{USDC_BASE}`). Confirmed unencumbered Wave 2 micro-bounty capacity: **$0.00 USDC (0 slots)**; remaining treasury funds now back **Wave 3 (`2 × $20.00 USDC` 3-Year Protocol Trajectory & Integrity Dossiers)** at https://pacta.wtf/bounties/#wave-3 · Hunter leaderboard: https://pacta.wtf/leaderboard/

**Net-new only.** A finding qualified only if it was not already published in the [protocol data](https://pacta.wtf/api/v1/protocols.json) when the PR was opened, and `post_pin_drift` had to be read at a block strictly after Pacta's latest pinned block for that protocol.

## Historical Wave 2 Categories

{cats}

## Historical Submission Command

- `python3 tools/verify_bounty_submission.py --json {WAVE2['fixtureDir']}/<chain>-<slug>.json`

## Payout

{WAVE2_PAYOUT}

## Questions

Ask in Community Q&A (GitHub Discussions): {COMMUNITY_URL}. Builder & Bounty Q&A thread: {COMMUNITY_QA_URL}

## Rules

{rules}
"""


def write_wave2_master_issue(idx, path=None):
    n = len(json.load(open(os.path.join(DOCS, "api", "v1", "protocols.json")))["protocols"])
    with open(path or WAVE2_MASTER_ISSUE, "w") as fh:
        fh.write(wave2_master_issue_md(n))


def wave2_section_html(claims, n_protocols, lb=None):
    """Completed & Retired Wave 2 archive section on /bounties/. Joins merged claims to wave2Settlements by fixture."""
    lb = load_leaderboard() if lb is None else lb
    paid = {p["fixture"]: p["payoutTxHash"] for p in lb["wave2Settlements"] if tx_ok(p["payoutTxHash"])}
    claimed = len(claims)
    cats = "".join(f'<li data-wave2-category="{c}"><b>{E(WAVE2["categories"][c]["label"])}</b> (<code>{c}</code>'
                   + (f', ≥ {tvl_label(c)} TVL' if WAVE2["categories"][c]["minTvlUsd"] else "") + "): "
                   + E(WAVE2_CATEGORY_TEXT[c].format(tvl=tvl_label(c) if WAVE2["categories"][c]["minTvlUsd"] else "", n=n_protocols)) + ".</li>"
                   for c in WAVE2["categories"])
    rows = "".join(f'<tr data-wave2-claim="{E(c["_file"])}"><td class="num">#{i}</td><td><a href="{E(REPO)}/blob/main/{E(WAVE2["fixtureDir"])}/{E(c["_file"])}" '
                   f'target="_blank" rel="noopener"><code>{E(c["_file"])}</code>{EXT}</a></td><td>{E(c["protocol"])}<div class="s"><code>{E(c["category"])}</code></div></td>'
                   f'<td><a class="lb-handle" href="https://github.com/{E(c["hunter"])}" target="_blank" rel="noopener">@{E(c["hunter"])}</a>'
                   f'<div class="s">{E(c.get("agentFramework") or "framework not stated")}</div></td><td>{settled_cell(REWARD_ATOMIC, [paid[c["_file"]]] if c["_file"] in paid else [])}</td></tr>'
                   for i, c in enumerate(claims, 1))
    table = (f'<div class="table-scroll" role="region" aria-label="Wave 2 claimed slots table" tabindex="0"><table class="ix w2-table" data-wave2-claims><thead><tr><th>Slot</th><th>Fixture</th><th>Target / category</th><th>Hunter / agent framework</th>'
             f'<th>Settled (Base USDC)</th></tr></thead><tbody>{rows}</tbody></table></div>' if claims else '<p class="s" data-wave2-claims-empty>No Wave 2 slots claimed.</p>')
    m_issue = re.fullmatch(re.escape(REPO) + r"/issues/(\d+)", WAVE2_ISSUE_URL)
    issue_label = f"Master issue #{m_issue.group(1)}{EXT}" if m_issue else f"GitHub issues{EXT}"
    master = md_html(wave2_master_issue_md(n_protocols).split("\n", 2)[2])
    settled = sum(1 for c in claims if c["_file"] in paid)
    return f"""<section class="memo-sec" id="wave-2" data-wave2-retired><h2>Archive: Wave 2 ($1.00 Micro-Bounties · {settled}/{claimed} Slots Settled &amp; Retired) <span class="archive-pill">Completed &amp; Retired</span></h2>
<p class="w2-counter" data-wave2-counter="{claimed}" data-wave2-program="{claimed}"><b>{claimed} Wave 2 Micro-Bounty Claims Merged</b> · <b data-wave2-settled="{settled}">{settled} settled on Base ({usdc(settled * REWARD_ATOMIC)} USDC)</b> · <b>Program Completed &amp; Retired</b> (active bounties moved to <a href="#wave-3">Wave 3 — 2 × $20.00 USDC Dossiers</a>)</p>
<p class="s">Historical archive (<a href="{E(WAVE2_ISSUE_URL)}" target="_blank" rel="noopener" data-wave2-issue>{issue_label}</a>). Wave 2 accepted 3 categories across Ethereum, Base, and Arbitrum ({WAVE2["maxOpenPrsPerContributor"]} concurrent open CI-passing PRs per contributor):</p>
<ol>{cats}</ol>
<p class="s" data-wave2-payout>{E(WAVE2_PAYOUT)}</p>
<h3>Archived Wave 2 Settlement Ledger</h3>
{table}
<details class="bounty-issue" id="wave-2-issue" data-wave2-issue-text><summary>{E(WAVE2["title"])} (Archived)</summary><div class="md">{master}</div></details></section>
"""


EAS_SCHEMA_UID = "0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83"


def leaderboard_page(idx, lb, claims, claims3=None):
    rows = hunter_stats(lb, claims, claims3)
    fws = framework_stats(rows)
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    hrows = []
    cred_cards = []
    for h in rows:
        anchor_id = h["handle"].lower()
        hid = f"hunter-{anchor_id}"
        md = badge_markdown(h["handle"])
        catches = "".join(f'<li data-catch-wave="{c["wave"]}"><a href="{E(c["href"])}" target="_blank" rel="noopener">{E(c["label"])}{EXT}</a> '
                          f'<span class="s">{E(c["protocol"])}</span></li>' for c in h["catches"])
        hrows.append(f'<tr id="{E(hid)}" data-hunter="{E(h["handle"])}"><td class="num">{h["rank"]}</td>'
                     f'<td class="lb-hunter"><a class="lb-handle" href="https://github.com/{E(h["handle"])}" target="_blank" rel="noopener">@{E(h["handle"])}</a>'
                     f'<ul class="lb-catches">{catches}</ul></td>'
                     f'<td>{E(", ".join(h["frameworks"]) or "not stated")}</td><td class="num">{len(h["catches"])}</td><td class="num">{len(h["protocols"])}</td>'
                     f'<td class="num">{h["eas"]}</td><td>{settled_cell(h["settled"], h["txs"])}</td>'
                     f'<td><img class="cp-badge" src="../badges/hunters/{E(h["handle"])}.svg" alt="Pacta hunter: {E(h["handle"])}" '
                     f'width="{hunter_badge_width(h["handle"], len(h["catches"]))}" height="20">'
                     f'<div class="lb-share">{copy_btn(md, "Copy badge Markdown")}'
                     f'<a class="copy" href="{E(share_x_href(h))}" target="_blank" rel="noopener" data-share-x>Share on X{EXT}</a>'
                     f'<a class="copy" href="#{E(anchor_id)}">Credential{ARR}</a></div></td></tr>')

        tx_proofs = " ".join(
            f'<a class="cred-tx mono" href="https://basescan.org/tx/{E(t)}" target="_blank" rel="noopener" title="{E(t)}">tx {E(short(t, 6, 4))}{EXT}</a>'
            for t in dict.fromkeys(h["txs"])
        ) or '<span class="s">Settlement pending</span>'
        rec_links = " · ".join(
            f'<a href="../protocols/{E(cr["pactaSlug"])}/#{E(cr["record"])}">{E(cr["pactaSlug"])} (PR #{cr["pr"]}){ARR}</a>'
            for cr in h["credits"][:4]
        )
        eas_line = (
            f'<b>{h["eas"]} Base-EAS attestation{"s" if h["eas"] != 1 else ""}</b> · '
            f'<a href="https://base.easscan.org/schema/view/{EAS_SCHEMA_UID}" target="_blank" rel="noopener">Schema 0x7ff4…df83{EXT}</a>'
            + (f' · {rec_links}' if rec_links else "")
        )
        cred_url = f"{BASE_URL}/leaderboard/#{anchor_id}"
        cred_cards.append(
            f'<article class="cred-card" id="{E(anchor_id)}" data-credential-card="{E(h["handle"])}">'
            f'<div class="cred-top">'
            f'<div class="cred-id">'
            f'<span class="cred-pill">VERIFIED BASE-EAS PACTA RESEARCHER CREDENTIAL</span>'
            f'<h3><a href="https://github.com/{E(h["handle"])}" target="_blank" rel="noopener">@{E(h["handle"])}{EXT}</a> '
            f'<a class="cred-anchor mono" href="#{E(anchor_id)}">#{E(anchor_id)}</a></h3>'
            f'</div>'
            f'<img class="cred-badge" src="../badges/hunters/{E(h["handle"])}.svg" alt="Verified Pacta researcher badge for {E(h["handle"])}" '
            f'width="{hunter_badge_width(h["handle"], len(h["catches"]))}" height="20">'
            f'</div>'
            f'<dl class="cred-grid">'
            f'<div><dt>Merged Control-Plane Gaps</dt><dd><b>{len(h["catches"])} verified catch{"es" if len(h["catches"]) != 1 else ""}</b> · Rank #{h["rank"]}</dd></div>'
            f'<div><dt>Protocols Verified ({len(h["protocols"])})</dt><dd>{E(", ".join(h["proto_names"]))}</dd></div>'
            f'<div><dt>Base-EAS Proof</dt><dd>{eas_line}</dd></div>'
            f'<div><dt>Settled Base USDC</dt><dd><b>{usdc(h["settled"])} USDC</b> · {tx_proofs}</dd></div>'
            f'</dl>'
            f'<div class="cred-actions">'
            f'<a class="copy cred-li" href="{E(share_linkedin_href(h))}" target="_blank" rel="noopener" data-share-linkedin>Share Milestone on LinkedIn{EXT}</a>'
            f'<a class="copy" href="{E(share_x_href(h))}" target="_blank" rel="noopener" data-cred-share-x>Share on X{EXT}</a>'
            f'{copy_btn(cred_url, "Copy credential link", f"Copy credential URL for {h["handle"]}")}'
            f'</div></article>'
        )
    frows = "".join(f'<tr data-framework="{E(f["name"])}"><td>{E(f["name"])}</td><td class="num">{f["hunters"]}</td><td class="num">{f["catches"]}</td>'
                    f'<td class="num">{len(f["protocols"])}</td><td>{usdc(f["settled"]) + " USDC" if f["settled"] else "$0.00 (pending settlement)"}</td></tr>'
                    for f in fws)
    n_catches = sum(len(h["catches"]) for h in rows)
    n_hunters = len(rows)
    n_attested = site_numbers(idx)["eas_protocols"]
    reconcile_line = f"{n_catches} verified findings · {n_hunters} independent researchers · {n_attested} Base-EAS verified protocols"
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": "Pacta hunter leaderboard", "url": f"{BASE_URL}/leaderboard/",
          "isPartOf": {"@type": "WebSite", "name": "Pacta by Fractal Neurons", "url": f"{BASE_URL}/"},
          "about": "Verified on-chain control-plane mismatch catches by bounty hunters and agent frameworks", "publisher": ORG_LD}
    ld_json = json.dumps(ld, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    body = f"""<body>
{topbar("../")}
<main id="main" class="memo-wrap memo-wide">
<div class="crumbs"><a href="../">Pacta</a> / <a href="../bounties/">Bounties</a> / Leaderboard</div>
<article class="memo">
<header><span class="tier">Bounties · hunter leaderboard &amp; verified credentials</span><h1>Pacta hunter leaderboard</h1>
<p class="lb-stats" data-leaderboard-stats><b>{E(reconcile_line)}</b></p>
<p class="lede">Every verified on-chain control-plane mismatch merged through the <a href="../bounties/">Pacta bounties</a>, credited to its GitHub hunter and agent framework. Ranked by verified catches, then protocols covered, Base EAS attestations and settled Base USDC. Every merged researcher earns a permanent shareable credential at <code>/leaderboard/#&lt;hunter&gt;</code>.</p></header>
<section class="memo-sec" id="hunters"><h2>Hunters</h2>
<div class="table-scroll" role="region" aria-label="Hunter leaderboard table" tabindex="0"><table class="ix lb-table" data-leaderboard><thead><tr><th>Rank</th><th>Hunter</th><th>Agent framework</th><th>Verified catches</th><th>Protocols covered</th><th>Base EAS attestations</th><th>Settled Base USDC</th><th>README badge</th></tr></thead><tbody>{"".join(hrows)}</tbody></table></div>
<p class="s">{E(reconcile_line)}. Wave 3: <a href="../bounties/#wave-3">closed, in settlement (/bounties/#wave-3)</a> · Archives: <a href="../bounties/#wave-2">Wave 2</a>, <a href="../bounties/#wave-1">Wave 1</a>.</p></section>
<section class="memo-sec" id="credentials" data-researcher-credentials><h2>Verified Researcher Credentials</h2>
<p class="s">Permanent on-chain proof cards for every merged Pacta bounty researcher (anchor <code>https://pacta.wtf/leaderboard/#&lt;hunter&gt;</code>), backed by Base USDC settlement transactions and Base EAS schema <a href="https://base.easscan.org/schema/view/{EAS_SCHEMA_UID}" target="_blank" rel="noopener"><code>0x7ff4…df83</code>{EXT}</a>.</p>
<div class="cred-list">{"".join(cred_cards)}</div></section>
<section class="memo-sec" id="frameworks"><h2>Agent frameworks</h2>
<table class="ix" data-frameworks><thead><tr><th>Framework</th><th>Hunters</th><th>Verified catches</th><th>Protocols covered</th><th>Settled Base USDC</th></tr></thead><tbody>{frows}</tbody></table>
<p class="s">The framework is what the hunter declared (<code>agentFramework</code> in the Wave 2 fixture); "not stated" when none was given.</p></section>
<section class="memo-sec" id="badges"><h2>README badges</h2>
<p data-community>Questions or a catch to discuss: <a href="{E(COMMUNITY_URL)}" target="_blank" rel="noopener">Community Q&amp;A (Discussions){EXT}</a> · <a href="{E(COMMUNITY_QA_URL)}" target="_blank" rel="noopener">Builder &amp; Bounty Q&amp;A thread{EXT}</a></p>
<p>Each hunter has a static badge at <code>{E(BASE_URL)}/badges/hunters/&lt;handle&gt;.svg</code>, rebuilt with the site. <b>Copy badge Markdown</b> puts a linked badge in your clipboard for a GitHub README; <b>Share Milestone on LinkedIn</b> and <b>Share on X</b> share your verified <code>#&lt;hunter&gt;</code> credential card.</p></section>
</article>
<div class="memo-foot"><span>Governance and documentation mismatches only. Exploit-sensitive vulnerabilities are never published here; they go through Immunefi or Cantina bounty programmes.</span><a href="../bounties/">Bounties{ARR}</a></div>
</main>
{footer(count_line, reg, "../")}
<script type="application/ld+json">{ld_json}</script>
</body></html>
"""
    return head("Hunter leaderboard · Pacta bounties", "Verified on-chain control-plane catches by hunter and agent framework, with settled Base USDC and README badges.",
                f"{BASE_URL}/leaderboard/", prefix="../", og_title="Pacta hunter leaderboard") + "\n" + body


def mcp_page(idx):
    """docs/mcp/index.html (pacta.wtf/mcp/): a static landing page for people and tools that open /mcp on the site. The MCP
    endpoint itself is the Streamable-HTTP JSON-RPC server on the Worker (MCP_URL); this page only documents it."""
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    claude = f"claude mcp add --transport http pacta {MCP_URL}"
    cursor = json.dumps({"mcpServers": {"pacta": {"url": MCP_URL}}}, indent=2)
    tools = "".join(f"<li><code>{E(t)}</code></li>" for t in B2A.REMOTE_TOOLS)
    starter = "https://github.com/Fractal-Neurons/defi-control-plane-mcp"
    x402_rows = "".join(f'<tr><td class="nowrap"><code>POST {E(p)}</code></td><td class="nowrap num">${E(u)}</td><td>{E(w)}</td></tr>' for p, u, w in B2A.X402_ENDPOINTS)
    install = U.tabs("mcpq", [("mcp", "MCP", term(claude, "Claude Code", "Copy the Claude Code MCP install command")
                               + term(cursor, "Cursor (mcp.json)", "Copy the Cursor MCP configuration")),
                              ("curl", "cURL", term(REST_CURL, "cURL", "Copy the cURL quickstart")),
                              ("python", "Python", term(REST_PY, "Python (requests)", "Copy the Python requests quickstart")
                               + term(STATIC_PY, "Python (standard library, static JSON)", "Copy the Python standard-library quickstart"))], "Install")
    body = f"""<body>
{topbar("../", "mcp/")}
<main id="main" class="memo-wrap">
<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span><span>MCP</span></nav>
<article class="memo">
<header><span class="tier">Remote MCP · free · zero install</span><h1>Pacta MCP server</h1>
<p class="lede">The live Model Context Protocol endpoint is <code data-mcp-endpoint>{E(MCP_URL)}</code>: Streamable HTTP, JSON-RPC 2.0, stateless (no session), <b>no API key and no wallet</b>, {E(RATE_LIMIT)}. This page only documents it; point your MCP client at the endpoint above.</p></header>
<section class="memo-sec" id="install"><h2>Install</h2>
{install}
<p>Optional attribution: <code>caller_agent</code>, <code>requester_role</code> and <code>caller_purpose</code> (non-personal; omitted or invalid values never block a call — invalid values are silently dropped; see <a href="../SKILL.md">SKILL.md</a>).</p></section>
<section class="memo-sec" id="tools"><h2>Tools ({E(B2A.REMOTE_TOOLS_DOC)})</h2><ul>{tools}</ul>
<p>Indexed protocols: <a href="../api/v1/protocols.json">protocol data</a> · machine-readable server card: <a href="../.well-known/mcp.json">/.well-known/mcp.json</a> · REST twin and OpenAPI 3.1: <a href="{E(OPENAPI_URL)}" target="_blank" rel="noopener">openapi.json{EXT}</a></p>
<p class="s">The live check tool <code>pacta_check_preflight</code> rates the single contract address it is given, not the whole protocol (<a href="../methodology/#live-checker">methodology</a>).</p></section>
<section class="memo-sec" id="x402"><h2>Free tier &amp; pay per call (x402)</h2>
<p>{E(B2A.FREE_TIER_DOC)}</p>
<table class="stack"><thead><tr><th class="nowrap">Route (POST JSON)</th><th class="nowrap">Price</th><th>What it returns</th></tr></thead><tbody>{x402_rows}</tbody></table>
<p class="s">Origin: <code>{E(B2A.X402_PUBLIC)}</code> · x402 v1 (<code>X-PAYMENT</code>) or v2 (<code>PAYMENT-SIGNATURE</code>), USDC on Base to the Pacta treasury. A request without a payment header answers HTTP 402 with the exact requirements; discovery: <a href="{E(B2A.X402_PUBLIC)}/.well-known/x402">/.well-known/x402</a>. Payment never changes a classification.</p></section>
<section class="memo-sec" id="starter"><h2>Starter kit &amp; help</h2>
<p>Ready-to-copy client configs and stdlib examples: <a href="{E(starter)}" target="_blank" rel="noopener">Fractal-Neurons/defi-control-plane-mcp{EXT}</a>. Questions: <a href="{E(COMMUNITY_QA_URL)}" target="_blank" rel="noopener">Community Q&amp;A (Discussions){EXT}</a>.</p></section>
</article>
<div class="memo-foot"><span>Read-only onchain analysis. Not investment advice.</span><a href="../#scorecards">Browse the scorecards{ARR}</a></div>
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    return head("Pacta MCP server · free remote MCP endpoint", "Free remote MCP server for DeFi control-plane checks: Streamable HTTP, no API key, no wallet.",
                f"{BASE_URL}/mcp/", prefix="../", og_title="Pacta MCP server") + "\n" + body

def llms(idx, radar):
    c = counts(idx)
    a = idx["onchain_anchoring"]
    r = radar["refreshed_at"]
    lines = [
        "# Pacta by Fractal Neurons", "",
        DISAMBIGUATION, "",
        f"> {BRAND}: free pre-execution contract and governance safety API for AI agents (launch: $0, no API key, no wallet), plus block-pinned DeFi control-plane snapshots and timelock alerts. {coverage_line(idx)}.", "",
        "Pacta checks who can change the rules of DeFi protocols (proxy admins, timelock delays, Safe quorums, roles) and compares that with what the protocols document. Every record is a read-only on-chain observation pinned to a block number and canonical block hash on its chain (" + counts(idx)["chains"] + ").", "",
        "## Free API for agents (launch: $0, no API key, no wallet)",
        f"- Remote MCP (Streamable HTTP, zero install): {MCP_URL} · Claude Code: `claude mcp add --transport http pacta {MCP_URL}` · Cursor: `{{\"mcpServers\": {{\"pacta\": {{\"url\": \"{MCP_URL}\"}}}}}}`. Tools ({REMOTE_TOOLS_DOC}): {', '.join(B2A.REMOTE_TOOLS)}. Local stdio server: {STDIO_TOOLS_DOC}.",
        "- " + B2A.CALLER_FIELDS_DOC,
        "- " + B2A.FREE_TIER_DOC,
        "- " + B2A.X402_DOC,
        "- " + B2A.protocols_line(idx, load_pinned()),
        f"- One call: `{CURL} \"{API}/v1/check/preflight?chain=ethereum&address=0x...\"` returns a verdict (IMMUTABLE_NO_ADMIN, TIMELOCK_PROTECTED, ZERO_DELAY_TIMELOCK_RISK, MULTISIG_NO_TIMELOCK, INSTANT_EOA_ADMIN_RISK, UNDEPLOYED_OR_EOA, UNCLASSIFIED_CONTRACT_CONTROLLER), a 0-100 risk score, proxy / admin / timelock breakdown and pause / blacklist / upgrade capabilities, pinned to a block hash.",
        f"- [{B2A.LOOKUP_URL}?q=ethena]({B2A.LOOKUP_URL}?q=ethena): free protocol / token name lookup (MCP tool pacta_lookup_protocol). {B2A.LOOKUP_DOC}",
        f"- {B2A.REQUEST_DOC}",
        f"- [{BASE_URL}/bounties/]({BASE_URL}/bounties/): {B2A.BOUNTIES_DOC}",
        f"- [{BASE_URL}/bounties/#wave-3]({BASE_URL}/bounties/#wave-3): {B2A.WAVE3_DOC}",
        f"- [{BASE_URL}/bounties/#wave-2]({BASE_URL}/bounties/#wave-2): {B2A.WAVE2_DOC}",
        f"- [{BASE_URL}/leaderboard/]({BASE_URL}/leaderboard/): {B2A.LEADERBOARD_DOC}",
        f"- [{B2A.COMMUNITY_URL}]({B2A.COMMUNITY_URL}): {B2A.COMMUNITY_DOC}",
        f"- [{OPENAPI_URL}]({OPENAPI_URL}): OpenAPI 3.1 for ChatGPT Actions, LangChain and OpenAPI tools; every route takes GET query parameters or a POST JSON body. {RATE_LIMIT}; free during the launch (pricingMode free_launch), x402 v1 + v2 ready.",
        f"- [{BASE_URL}/protocols/]({BASE_URL}/protocols/): per-protocol control-plane safety records.",
        f"- [{BASE_URL}/integrations/vault-factories/]({BASE_URL}/integrations/vault-factories/): free building blocks for vault factories and curators (Morpho Vault V2, Euler EVK, Veda BoringVault, Lagoon, Upshift, Mellow): a Control-Plane & Role Map tab from /api/v1/protocols.json, status badges (/badges/<slug>.svg; live {API}/v1/badges/<slug>.svg), and PactaSentinelGuard.sol, a cap-increase tripwire that never blocks a decrease.", "",
        "## Agent feeds",
        f"- [{BASE_URL}/llms-full.txt]({BASE_URL}/llms-full.txt): complete single-file reference (feeds, MCP tools, x402, anchoring, every record, proposal and queued operation).",
        f"- [{BASE_URL}/api/v1/proposals.json]({BASE_URL}/api/v1/proposals.json): schema `pacta.governance_proposals_feed.v1`; live Aave / Euler / Morpho / Sky proposals mapped to block-pinned observations.",
        f"- [{BASE_URL}/.well-known/agent.json]({BASE_URL}/.well-known/agent.json) (A2A Agent Card) · [{BASE_URL}/.well-known/mcp.json]({BASE_URL}/.well-known/mcp.json) (MCP manifest) · [{BASE_URL}/SKILL.md]({BASE_URL}/SKILL.md) (portable agent skill).", "",
        "## Data",
        f"- [{BASE_URL}/api/v1/index.json]({BASE_URL}/api/v1/index.json): schema `{idx['schema']}`; `summary_metrics` (sprints_completed={c['sprints']}, records_indexed={c['records']}, parameter_deltas={c['delta']}, protective_deltas={c['protect']}, aligned_baselines={c['aligned']}); each entry has id, protocol, category, sprint, block_number, block_hash, classification, surface, target_contract, target_label, check_type, selector_or_slot, call_signature, call_args, repro_calldata, onchain_observed, documented_reference, observed/documented delay seconds, summary_doc, summary_sha256, base_eas_uid.",
        f"- [{BASE_URL}/api/v1/rpc-pinned.json]({BASE_URL}/api/v1/rpc-pinned.json): schema `{PINNED_SCHEMA}`; {len(load_pinned()['entries'])} RPC-pinned control-plane records on Ethereum and Base (block number + hash, cast reproduction). NOT EAS-attested: no sprint, summary document or Base EAS UID.",
        f"- [{BASE_URL}/api/v1/protocols.json]({BASE_URL}/api/v1/protocols.json): schema `pacta.protocols.v1`; every published protocol ({site_numbers(idx)['eas_protocols']} Base-EAS attested, {site_numbers(idx)['observed']} RPC-observed with documentationComparison not_assessed) with badge tier and URLs, Sprint ids and EAS UIDs, controller and every pinned surface (block number + hash).",
        f"- [{BASE_URL}/api/v1/radar.json]({BASE_URL}/api/v1/radar.json): queued timelock operations, refreshed at finalized block {r['block_number']} ({r['block_time_utc']})"
        + "".join(f" and {CHAINS[ch][0]} finalized block {p_['block_number']} ({p_['block_time_utc']})" for ch, p_ in radar_pins(radar)[1:]) + "; each operation carries pending / done / ready (delay elapsed, still unexecuted).",
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
        f"- Classifications: {CLASS_DEFINITIONS}.",
        f"- {VULN_ROUTE}",
        f"- {EDITORIAL_FIREWALL} {EDITORIAL_INDEPENDENCE} Independence policy: {BASE_URL}/methodology/#independence", "",
        "## Access",
        "- Free and real-time for everyone, including vault curators, allocators and AI risk agents: every indexed record, the timelock radar, the briefs, /api/v1/*.json and this file. No key, no delay, no paywall; curators never pay.", "",
        "## On-chain anchoring (Base, chain id 8453)",
        f"- PactaCommitmentRegistry: `{a['commitment_registry']}` (Sourcify verified); attester `pacta.base.eth` (`{a['attester_eoa']}`).",
        f"- EAS schema: `{a['eas_schema_uid']}`. {anchoring_text(c)}",
    ] + [f"- Multi-attest tx, Sprints {r_}: `{tx}`" for r_, tx in c["multi_txs"].items()] + [
        "- Per-sprint attestation UIDs: `onchain_anchoring.sprint_eas_attestations` in /api/v1/index.json; each record's `base_eas_uid`.", "",
        "## Engagements & Verification Pools (editorial firewall: payment never changes a classification)",
        f"- Free Post-Fix Re-Verification: Free factual re-verification within 7 days whenever a protocol merges a public docs or on-chain fix ({BASE_URL}/request/?tier=community).",
        f"- Sponsor Verification Pools ({BASE_URL}/bounties/#sponsor-pool): {SPONSOR_TERMS_TEXT} ({BASE_URL}/request/?tier=wholesale-150). {SPONSOR_OPENING}; refunds within 30 days are a signed policy, not an on-chain guarantee.",
        f"- Pre-Launch & Multi-Contract Suite Dossier: {CLEARANCE_PRICE} flat (24h SLA). Archive-RPC control-plane verification, upstream GitBook / docs reconciliation PR and Curator Diligence Dossier (PDF + JSON) for Morpho, Euler, Aave and Sky forum proposals. Request: {BASE_URL}/request/?tier=clearance",
        f"- Continuous Control-Plane Monitoring & Alerts: Free 30-day alert pilot (POST {PILOT_WATCH_API} or {BASE_URL}/scan/#watch-pilot) and {MONITORING_PRICE} Institutional Allocator Watch SLA ({BASE_URL}/request/?tier=continuous); the result can still read Docs differ.",
        f"- High-throughput API (> 60 requests / minute or a dedicated SLA): x402 metered endpoints, or an Enterprise API key priced on scope: {BASE_URL}/request/?tier=api_sla",
        f"- Settlement, Option A (recommended for protocol treasuries): a formal commercial invoice (PDF) with verified counterparty payment instructions, issued on scope confirmation; no upfront transfer is needed to open intake.",
        f"- Settlement, Option B (direct express): USDC on Base (`{USDC['Base']}`) or Ethereum (`{USDC['Ethereum']}`) to the Pacta treasury (direct settlement EOA) `{a['treasury_admin']}` (an externally owned account; the same address on both chains).",
        f"- Request: {BASE_URL}/request/ (builds a scope brief; opens a pre-filled GitHub intake issue or Gmail compose, or copies the brief). Prefill: `?tier=community|wholesale-150|clearance|continuous|api_sla&protocol=<slug>&forum=<https URL>&settlement=invoice|direct`.", "",
        "## x402 API (live for AI agents & programmatic callers)",
        f"- Free daily quota + pay-per-call x402 overflow: {B2A.FREE_DAILY_QUOTA} free preflight and wallet-exposure checks per caller per UTC day (`GET /v1/check/preflight`, `GET /v1/check/wallet-exposure`, MCP `pacta_check_preflight`, `pacta_scan_wallet_exposure`), then $0.01 per call over x402 (never a dead-end 429). Dedicated POST JSON x402 agent endpoints on `{API}` (`{B2A.X402_URL}`): `POST /v1/x402/verdict` ($0.02), `POST /v1/x402/dossier` ($0.05), `POST /v1/x402/wallet-exposure` ($0.05), `POST /v1/x402/calldata-sim` ($0.25), `POST /v1/x402/deep-scan` ($9.00); live scan routes (free_launch $0; x402_paid prices): `GET /v1/check/preflight` ($0.01), `GET /v1/check/wallet-exposure` ($0.01), `GET /v1/scan/control-plane` ($0.10), `GET /v1/scan/proposal-diff` ($0.15), `GET /v1/scan/timelock-op` ($0.25), `GET /v1/briefs/live-timelocks` ($0.10); free `/health`, `/.well-known/x402` (Bazaar discovery), `/v1/sample/control-plane`, `/v1/sample/preflight`. Wire: x402Versions [1, 2] (v1 network `base` with `X-PAYMENT` / `X-PAYMENT-RESPONSE`, v2 network `{B2A.X402_NETWORK_V2}` with `PAYMENT-REQUIRED` / `PAYMENT-SIGNATURE` / `PAYMENT-RESPONSE`; USDC on Base, payTo `{B2A.PAY_TO}`, maxTimeoutSeconds {B2A.X402_MAX_TIMEOUT_S}).",
        f"- Remote MCP: {MCP_URL} (free, no install). Local stdio server (from a clone of the repo; npm publication pending): set `PACTA_X402_URL={B2A.X402_URL}` to enable the scan tools; in x402_paid mode pay with `xPaymentHeader` (v1) or `paymentSignatureHeader` (v2). The MCP client does not re-check receipts on-chain (onchainReceiptVerified: false); the gateway does.",
        f"- Gateway settlement guard: {B2A.X402_GATEWAY_GUARD_NOTE}", "",
        "## Contact",
        f"- {CONTACT} · {REPO} · {FN} · security: {BASE_URL}/.well-known/security.txt", "",
    ]
    return "\n".join(lines)


def llms_html(idx, text):
    """docs/llms/index.html: the exact llms.txt text in a semantic HTML page (some chat URL fetchers only accept text/html)."""
    c = counts(idx)
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    alt = f'<link rel="alternate" type="text/plain" href="{BASE_URL}/llms.txt" title="llms.txt (plain text)">'
    ld = org_ld_script()
    body = f"""<body>
{topbar("../")}
<main id="main" class="memo-wrap">
<div class="crumbs"><a href="../">Pacta</a> / llms.txt</div>
<article class="memo">
<header><span class="tier">For agents</span><h1>llms.txt (HTML mirror)</h1>
<p class="lede">The same text as <a href="../llms.txt">/llms.txt</a> (plain text), rendered as HTML for fetchers that only read web pages. The complete single-file reference is <a href="../llms-full.txt">/llms-full.txt</a>.</p></header>
<pre class="llms" data-llms-mirror>{E(text)}</pre>
</article>
</main>
{footer(count_line, reg, "../")}
{ld}
</body></html>
"""
    return head("llms.txt · Pacta (HTML mirror)", "Pacta llms.txt as HTML: free pre-execution contract checks for AI agents, feeds, MCP and data.",
                f"{BASE_URL}/llms/", prefix="../", og_title="Pacta llms.txt", extra=alt) + "\n" + body


ROBOTS_TXT = "User-agent: *\nAllow: /\n\nSitemap: https://pacta.wtf/sitemap.xml\n"


def feed_items(idx, radar):
    """Feed entries, newest Sprint first, then the radar: (id, title, url, updated ISO-8601 UTC, summary text). Dates come from the
    data (index generated_at for Sprint attestations, the radar's finalized block time for timelock items), never the wall clock."""
    import datetime as _dt
    iso = lambda ts: _dt.datetime.fromtimestamp(int(ts), _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gen = idx["generated_at"]
    uids = idx["onchain_anchoring"]["sprint_eas_attestations"]
    by_sprint = {}
    for e in idx["entries"]:
        by_sprint.setdefault(int(e["sprint"]), []).append(e)
    out = []
    for n in sorted(by_sprint, reverse=True):
        es = by_sprint[n]
        names = sorted({e["protocol"] for e in es})
        cls = [e["classification"] for e in es]
        uid = uids.get(str(n))
        out.append((f"{BASE_URL}/#sprint-{n}", f"Sprint {n} Base EAS attestation: {len(es)} records, {len(names)} protocols",
                    f"https://base.easscan.org/attestation/view/{uid}" if uid else f"{BASE_URL}/api/v1/index.json", gen,
                    f"{', '.join(names)}. {cls.count('aligned_baseline')} aligned, {cls.count('protective_delta')} protective delta, "
                    f"{cls.count('parameter_delta')} parameter delta. Summary: {REPO}/blob/main/{es[0]['summary_doc']}"))
    for it in radar["items"]:
        r, ch = radar_pin(it, radar), radar_chain(it, radar)
        done = all(o.get("done") for o in it["operations"])
        out.append((f"{BASE_URL}/{it['brief'].strip('/')}/#radar", f"{it['protocol']} timelock: {'executed' if done else 'pending'} · {it['title']}",
                    f"{BASE_URL}/{it['brief'].strip('/')}/", iso(r["block_timestamp"]),
                    f"{it['summary']} Read at finalized {CHAINS[ch][0]} block #{r['block_number']:,}."))
    return out


def atom_feed(idx, radar):
    items = feed_items(idx, radar)
    upd = max(i[3] for i in items)
    X_ = lambda s: E(s)
    entries = "".join(f'  <entry>\n    <id>{X_(i)}</id>\n    <title>{X_(t)}</title>\n    <link href="{X_(u)}"/>\n    <updated>{d}</updated>\n'
                      f'    <summary>{X_(s)}</summary>\n  </entry>\n' for i, t, u, d, s in items)
    return ('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n'
            f'  <id>{BASE_URL}/feed.xml</id>\n  <title>Pacta: Sprint attestations and timelock radar</title>\n'
            f'  <subtitle>Block-pinned DeFi control-plane records (Base EAS) and queued timelock operations</subtitle>\n'
            f'  <link rel="self" href="{BASE_URL}/feed.xml"/>\n  <link href="{BASE_URL}/"/>\n  <updated>{upd}</updated>\n'
            f'  <author><name>Pacta by Fractal Neurons</name><uri>{BASE_URL}/</uri></author>\n{entries}</feed>\n')


def json_feed(idx, radar):
    items = feed_items(idx, radar)
    return json.dumps({"version": "https://jsonfeed.org/version/1.1", "title": "Pacta: Sprint attestations and timelock radar",
                       "home_page_url": f"{BASE_URL}/", "feed_url": f"{BASE_URL}/api/v1/feed.json",
                       "description": "Block-pinned DeFi control-plane records (Base EAS) and queued timelock operations",
                       "authors": [{"name": "Pacta by Fractal Neurons", "url": f"{BASE_URL}/"}], "language": "en",
                       "items": [{"id": i, "title": t, "url": u, "date_published": d, "content_text": s} for i, t, u, d, s in items]},
                      indent=1, ensure_ascii=False) + "\n"
# RFC 9309: "User-agent: *" + "Allow: /" already admits every crawler. No bot-name stanzas: an explicit Google-Extended
# stanza tripped a naive opt-out matcher in Gemini's url_context fetcher even when paired with Allow: /.


SITE_DATE_FALLBACK = "2026-11-15"


def site_date(idx, radar, pinned=None, onb=None):
    """The sitemap <lastmod>: the newest YYYY-MM-DD in the pinned data (index.json generated_at, the radar's finalized block
    time, rpc-pinned.json / onboarding.json generated_at), never the wall clock, so a rebuild after 00:00 UTC is byte-identical."""
    cands = [idx.get("generated_at"), (radar.get("refreshed_at") or {}).get("block_time_utc"),
             (pinned or {}).get("generated_at"), (onb or {}).get("generated_at")]
    days = [c[:10] for c in cands if isinstance(c, str) and re.match(r"^\d{4}-\d{2}-\d{2}", c)]
    return max(days) if days else SITE_DATE_FALLBACK


# Pricing cards (/#pricing and /request/, identical on both): key -> (price, price note, bullets, CTA label, featured)
PRICING = [
    ("community", "$0", "No key, no wallet", [
        "All {n} protocol scorecards and Base EAS proofs, free, with live re-check on demand",
        "100% free full Wallet & Safe exposure scan across Ethereum and Base",
        "Free factual re-verification within 7 days whenever a protocol merges a public docs or on-chain fix"], "Submit updated docs", False),
    ("wholesale-150", "$150 / protocol", "Multi-protocol sweep", [
        "For L2 ecosystems, grant councils and institutional vault curators",
        "Undelivered targets never charged; commercial invoice or Base USDC",
        "Single-protocol pools start at $50 USDC on /bounties/#sponsor-pool"], "Fund a pool", False),
    ("clearance", "$2,500–$5,000", "USDC · 24h SLA", [
        "Pre-launch or multi-contract suite diligence across proxies, Safes and timelocks",
        "$2,500 single chain (up to 8 contracts) · $5,000 multi-chain with a 90-day drift watch",
        "Docs reconciliation PR and a Base EAS attestation"], "Request a dossier", True),
    ("continuous", "$500–$2,500", "USDC per month", [
        "Institutional allocator & multi-vault control-plane watch SLA",
        "Refreshed dossier and attestation after governance proposals and signer rotations",
        "The result can still read Docs differ if docs and chain diverge"], "Start monitoring", False),
    ("api_sla", "Custom", "Priced on scope", [
        "For wallets, custodians and agents above 60 requests / minute",
        "Dedicated limits and support",
        "Same public data, same classifications"], "Request API access", False),
]


EDITORIAL_SHORT = ("Payment funds verification work. The published result follows the onchain and documentation evidence, and can "
                   "still read Docs differ.")


CONTACT_NOTE = "Pacta by Fractal Neurons · Official desk: pacta@dri.network"


FONT_FILE = "fonts/inter-latin-wght-normal.woff2"


def nav_href(home, key):
    if key.startswith("#"):
        return (home or "") + key if home else key
    return f"{home}{key}"


_NUMS = {}


def site_numbers(idx, cards=None, pinned=None):
    """M4: every count on the site, computed once from the data (scorecards = protocols; index.json entries = attested checks)."""
    key = (id(idx), id(pinned) if pinned is not None else None, id(cards) if cards is not None else None)
    if key in _NUMS:
        return _NUMS[key][1]
    pinned = load_pinned() if pinned is None else pinned
    cards = scorecards(idx, pinned) if cards is None else cards
    c = counts(idx)
    g = {k: sum(x["grade"] == k for x in cards) for k in ("delta", "protective", "aligned", "observed")}
    eas = sum(1 for x in cards if x["easAttested"])
    n = len(cards)
    assert n == sum(g.values()) == eas + g["observed"], (n, g, eas)
    assert g["observed"] == sum(1 for x in cards if not x["easAttested"]), "observed grade = RPC-observed protocols"
    res = {"protocols": n, "eas_protocols": eas, "observed": g["observed"], "delta": g["delta"], "protective": g["protective"],
           "aligned": g["aligned"], "checks": c["records"], "batches": c["eas_n"], "sprints": c["sprints"],
           "observed_records": len(pinned["entries"])}
    _NUMS[key] = ((idx, pinned, cards), res)   # keeps the keyed objects alive, so their id() can never be reused while cached
    return res


GRADE_UI = {"delta": ("Docs differ", "warning"), "protective": ("Protective", "info"), "aligned": ("Aligned", "neutral"),
            "observed": ("Observed", "outline")}


AWESOME_MCP_URL = "https://github.com/punkpeye/awesome-mcp-servers/pull/19455"


STATIC_PY = ("import json, urllib.request\n"
             f'cards = json.load(urllib.request.urlopen("{BASE_URL}/api/v1/scorecards.json"))\n'
             'print(len(cards["protocols"]), "protocols")')


def home_desc(n):
    """M1: the meta / OG / X description uses the subhead's own words (and keeps the social tags inside the first 1.2 KB)."""
    return f"Who can upgrade, pause or change {n} DeFi protocols: checked against their docs, attested onchain."


def receipt_data(idx):
    by = {e["id"]: e for e in idx["entries"]}
    out = []
    for slug, rid, label, docs, chain, dtok, ctok in RECEIPTS:
        e = by[rid]
        assert protocol_slug(e["protocol"]) == slug and e["classification"] == "parameter_delta", rid
        assert all(t in e["documented_reference"] for t in dtok) and all(t in e["onchain_observed"] for t in ctok), rid
        out.append({"slug": slug, "label": label, "docs": docs, "chain": chain, "e": e, "ch": chain_of(e)})
    return out


# R-V1 (v4.4): the contract a "Try:" example sends to the live check, when it is not the receipt record's own target. Stader's
# receipt is about the Manager Safe (3-of-6 vs 3-of-5 documented); a Safe has no proxy admin or owner() for the live check to read,
# so the check runs on the ETHx proxy (EIP-1967, admin behind the 7-day TimelockController), which the API matches to the same
# indexed protocol (catalogMatch stader-labs-ethx). YO's and Moonwell's record targets already expose their admin surfaces.
LIVE_CHECK_TARGET = {HERO_EXAMPLE[0]: (HERO_EXAMPLE[1], HERO_EXAMPLE[2])}


def try_chips(idx, prefix=""):
    """Hero examples (Button outline sm, labelled as examples): each loads its pinned receipt into the proof card and runs the live check."""
    chips = []
    for r in receipt_data(idx):
        e, ch = r["e"], r["ch"]
        lch, laddr = LIVE_CHECK_TARGET.get(r["slug"], (ch, e["target_contract"]))
        inner = receipt_inner_html(r["slug"], r["label"], lch, "GAP", "gap", prefix=prefix)
        sym = CHIP_TICKERS.get(r["slug"], "")
        chips.append(U.button(inner, variant="outline", size="sm", cls="receipt",
                              attrs=(f'data-receipt data-pf-chain="{lch}" data-pf-address="{laddr}" data-r-name="{E(r["label"])}" '
                                     f'data-r-docs="{E(r["docs"])}" data-r-chain="{E(r["chain"])}" data-r-block="{int(e["block_number"])}" '
                                     f'data-r-net="{CHAINS[ch][0]}" data-r-uid="{E(e.get("base_eas_uid") or "")}" data-r-href="{prefix}protocols/{r["slug"]}/" '
                                     f'data-pf-slug="{r["slug"]}" data-pf-disp="{E(r["label"])}" data-pf-sym="{E(sym)}" '
                                     f'data-pf-icon="{prefix}{proto_icon_rel(r["slug"])}" '
                                     f'aria-label="Try {E(r["label"])}: show its receipt and run a live check of {laddr}"')))
    return (f'<div class="try"><div class="try-row" role="group" aria-label="Example contracts"><span class="try-l">Try:</span>'
            f'<div class="try-chips">{"".join(chips)}</div></div></div>')


def proof_card(idx, prefix=""):
    """V6: the hero's right column is proof, not whitespace: one pinned receipt (docs say / chain says / finalized block / Base EAS UID)."""
    r = receipt_data(idx)[0]
    e, ch = r["e"], r["ch"]
    uid = e.get("base_eas_uid") or ""
    uid_html = (f'<a class="mono" data-pc-uid href="https://base.easscan.org/attestation/view/{E(uid)}" target="_blank" rel="noopener" '
                f'title="{E(uid)}">{E(short(uid, 10, 6))}</a>' if uid else '<span data-pc-uid>Pending batch attestation</span>')
    inner = (f'<div class="pc-head"><div><span class="eyebrow">Live receipt</span><p class="pc-name" data-pc-name>{E(r["label"])}</p></div>'
             + U.badge("Docs differ", "warning", cls="grade g-delta") + '</div>'
             f'<dl class="pc-rows"><div><dt>Docs say</dt><dd data-pc-docs>{E(r["docs"])}</dd></div>'
             f'<div><dt>Chain says</dt><dd class="pc-chain" data-pc-chain>{E(r["chain"])}</dd></div>'
             f'<div><dt>Finalized block</dt><dd><span class="mono" data-pc-block>{CHAINS[ch][0]} #{int(e["block_number"]):,}</span></dd></div>'
             f'<div><dt>Public attestation receipt</dt><dd>{uid_html}</dd></div></dl>'
             f'<div class="pc-foot"><span>Pinned to a finalized block, attested on Base</span>'
             f'<a data-pc-href href="{prefix}protocols/{r["slug"]}/">Full record{ARR}</a></div>')
    return U.card(inner, cls="proof-card", attrs='data-proof-card aria-live="polite" aria-label="Live receipt"')


def delta_line(s):
    """v4.5.1: one line reconciling the tiles: protocols whose docs and chain differ = adverse deltas + protective deltas (from the data)."""
    return (f'<p class="delta-line" data-delta-line>{s["delta"] + s["protective"]} of {s["protocols"]} protocols differ from their docs: '
            f'{s["delta"]} adverse, {s["protective"]} protective.</p>')


def stats_cards(idx, cards):
    s = site_numbers(idx, cards)
    items = [(s["protocols"], "Protocols scored", f'{s["eas_protocols"]} Base-EAS attested · {s["observed"]} RPC-observed'),
             (s["delta"], "Docs differ", "Adverse: chain looser than docs"),
             (s["protective"], "Protective", "Chain stricter than the docs"),
             (s["checks"], "Attested checks", f'Across {s["batches"]} Base EAS batch attestations')]
    return ('<div class="stats" data-proof>' + "".join(
        U.card(f'<b>{v}</b><span>{E(k)}</span><small>{E(sub)}</small>', cls="stat") for v, k, sub in items) + '</div>' + delta_line(s))


def fresh_pill(idx, radar=None):
    """v4.7 W4: deterministic freshness (no wall clock): the newest finalized block pinned per chain in index.json and the number
    of Base EAS batch attestations; on /radar/ the radar's own finalized pins (one per chain)."""
    if radar is not None:
        txt = ("Radar pinned at finalized blocks: " + " · ".join(f'{CHAINS[ch][0]} #{p_["block_number"]:,}' for ch, p_ in radar_pins(radar))
               + f' ({radar["refreshed_at"]["block_time_utc"]})')
    else:
        top = {}
        for e in idx["entries"]:
            top[chain_of(e)] = max(top.get(chain_of(e), 0), int(e["block_number"]))
        txt = ("Pinned blocks: " + " · ".join(f"{CHAINS[ch][0]} #{top[ch]:,}" for ch in CHAINS if ch in top)
               + f' · {counts(idx)["eas_n"]} Base EAS batches')
    return f'<p class="fresh" data-fresh><span class="dot" aria-hidden="true"></span><span>{E(txt)}</span></p>'


def radar_strip(radar, prefix=""):
    """v4.7 W1: one compact line under the hero numbers: the queued timelock operations by state, linking to the radar."""
    active = sum(len(it["operations"]) for it in radar["items"] if item_state(it) != "executed")
    chains = " and ".join(CHAINS[ch][0] for ch, _ in radar_pins(radar))
    return (f'<p class="tl-strip" data-tl-strip><span class="dot live" aria-hidden="true"></span><b>Timelock radar</b>'
            f'<span>{active} queued operations on {E(chains)}: {E(radar_counts_text(radar))}</span>'
            f'<a href="{prefix}#radar">See the queue{ARR}</a></p>')


def trust_strip(prefix=""):
    reg_v = json.load(open(os.path.join(ROOT, "packages", "mcp-server", "server.json"), encoding="utf-8"))["version"]
    links = [(f"Official MCP Registry (v{reg_v})", MCP_REGISTRY_URL, True), ("Glama MCP listing", GLAMA_URL, True),
             ("awesome-mcp-servers (merged #19455)", AWESOME_MCP_URL, True), ("Base Mainnet EAS schema", EAS_SCHEMA_VIEW, True),
             ("OpenAPI 3.1", f"{prefix}openapi.json", False)]
    return ('<p class="trust" data-trust><span>Listed and verifiable:</span>' + "".join(
        f'<a href="{E(h)}"{" target=" + chr(34) + "_blank" + chr(34) + " rel=" + chr(34) + "noopener" + chr(34) if ext else ""}>{E(t)}</a>'
        for t, h, ext in links) + '</p>')


def hero_section(idx, cards, radar):
    s = site_numbers(idx, cards)
    return f"""<section class="hero"><div class="wrap"><div class="hero-grid">
<div class="hero-main">
<span class="eyebrow">{E(HOME_EYEBROW)}</span>
<h1><span class="l">Protocol docs drift.</span><br><span class="l">The chain doesn’t.</span></h1>
<p class="lede">{E(HOME_SUB.format(n=s["protocols"]))}</p>
{hero_checker(try_chips(idx), label="Protocol or address", visible_label=True)}
<p class="hero-routes"><span>Building an agent? <a href="mcp/">Use the MCP server{ARR}</a></span><span>Run a protocol? <a href="for-protocols/">For protocol teams{ARR}</a></span></p>
</div>
{proof_card(idx)}
</div>
<div class="home-doors" aria-label="Three ways to use Pacta">
<a class="home-door" data-slot="card" href="scan/"><span class="hd-k">1 · Free Instant Scan</span><b>Scan any wallet or Safe</b><span class="hd-d">Check held DeFi positions, adverse gaps &amp; signer overlap in 3 seconds.</span><span class="hd-cta">Scan free{ARR}</span></a>
<a class="home-door" data-slot="card" href="bounties/#sponsor-pool"><span class="hd-k">2 · Community &amp; Curators</span><b>Fund a verification pool ($50+)</b><span class="hd-d">Sponsor a $50 live control-plane check or $150/protocol wholesale sweep.</span><span class="hd-cta">Fund a pool{ARR}</span></a>
<a class="home-door" data-slot="card" href="scan/#watch-pilot"><span class="hd-k">3 · Free 30-Day Pilot</span><b>Watch my positions</b><span class="hd-d">Get Email, @Telegram, or Webhook alerts before queued timelocks execute.</span><span class="hd-cta">Enable alerts{ARR}</span></a>
</div>
{stats_cards(idx, cards)}
<div class="hero-meta">{fresh_pill(idx)}{radar_strip(radar)}</div>
{trust_strip()}
</div></section>"""


def how_it_works(idx, cards, radar, prefix=""):
    """v4.7 W2: two audiences, one shadcn Tabs (role=tablist, roving tabindex, arrow keys / Home / End in app.js; every panel visible
    without JavaScript). Risk & diligence teams (default): the three steps, the rosette legend and the three next steps. AI agents &
    builders: the remote MCP config, the agent docs and a curl preflight plus a cast re-read of an indexed record."""
    steps = [("Read the docs", "We record what each protocol publishes about who can upgrade, pause or change its contracts, and how long "
                               "changes must wait."),
             ("Read the chain at a finalized block", "We read the live contracts at a finalized block on two independent RPC providers: "
                                                     "owners, multisig quorums, timelock delays and roles."),
             ("Attest the difference on Base", "Each result is attested on Base with EAS, so anyone can re-check it later with one "
                                               "command.")]
    lis = "".join(f'<li data-slot="card" class="step"><span class="step-n" aria-hidden="true">{i}</span><h3>{E(t)}</h3><p>{E(d)}</p></li>'
                  for i, (t, d) in enumerate(steps, 1))
    s_ = site_numbers(idx, cards)
    active = sum(len(it["operations"]) for it in radar["items"] if item_state(it) != "executed")
    risk = (f'<ol class="steps" aria-label="How Pacta works">{lis}</ol>{rosette_legend("hiw-legend")}'
            f'<div class="hiw-cta">' + U.button(f'Docs differ ({s_["delta"]})', href=f"{prefix}scorecards/?grade=delta", variant="outline")
            + U.button(f"Live timelock radar ({active} queued)", href=f"{prefix}radar/", variant="outline")
            + U.button("Scan Any Safe Free", href=f"{prefix}scan/", variant="default")
            + f'</div><p class="links"><a href="{prefix}methodology/">Read the methodology and the full glossary{ARR}</a></p>')
    by = {c["slug"]: c for c in cards}
    probe = by[RECEIPTS[0][0]]["probe"]
    verify = (f'{REST_CURL}\n\n# Re-read an indexed record yourself at its pinned block: {by[RECEIPTS[0][0]]["name"]}\n{cast_line(probe)}')
    cursor = json.dumps({"mcpServers": {"pacta": {"url": MCP_URL}}}, indent=2)
    pills = "".join(U.button(lbl, href=h, variant="outline", size="sm") for lbl, h in
                    (("SKILL.md", f"{prefix}SKILL.md"), ("llms.txt", f"{prefix}llms.txt"), ("OpenAPI 3.1", f"{prefix}openapi.json"),
                     ("MCP docs", f"{prefix}mcp/")))
    # v4.7.1: two columns from 1024 px (install | verify), so the two panels are close in height
    agents = (f'<p class="s">Remote MCP over Streamable HTTP and a REST API: {E(RATE_LIMIT)}, free, no API key, no wallet. '
              f'Remote tools: {E(REMOTE_TOOLS_DOC)}.</p>'
              + f'<div class="hiw-pills">{pills}</div><div class="hiw-agents"><div>'
              + term(f"claude mcp add --transport http pacta {MCP_URL}", "Claude Code", "Copy the Claude Code MCP install command")
              + term(cursor, "Cursor (mcp.json)", "Copy the Cursor MCP configuration") + '</div><div>'
              + term(verify, "Check a contract, then verify with cast", "Copy the curl preflight and the cast verification") + '</div></div>')
    tabs_ = U.tabs("hiw", [("risk", "For risk & diligence teams", risk), ("agents", "For AI agents & builders", agents)], "Choose your audience",
                   stable=True)
    return f"""<section class="sec" id="how-it-works"><div class="wrap">
<div class="sec-head"><h2>How it works</h2><p class="aside">Three steps for every protocol, and two ways to use the result.</p></div>
{tabs_}
</div></section>"""


FACTOR_LETTER = {"g": "S", "b": "M", "a": "W", "n": "—", "u": "—"}


def rosette_legend(id_="rosette-legend"):
    lg = "".join(f'<span class="lg"><span class="fdot r-{k}" aria-hidden="true">{FACTOR_LETTER[k]}</span>{w}</span>'
                 for k, w in (("g", "Strong"), ("b", "Moderate"), ("a", "Weak"), ("n", "Not determined")))
    return (f'<p class="legend" id="{id_}"><b>Control-strength graphic</b>{lg}<span>Longer, greener slices are stronger. Clockwise from the top: '
            f'upgradeability, timelock floor, signer quorum, emergency scope, docs-vs-chain parity.</span></p>')


BADGE_DEMO = "aave-v3-gho"   # an all-aligned, Base-EAS-attested protocol (the same example as /for-protocols/)


def badge_demo(prefix=""):
    """v4.5 G-P2-5: the real static badge of one aligned protocol and its one-line Markdown embed, inside the teams card."""
    label = LK.BADGE_TIERS["aligned"][0]
    width = (len(LK.BADGE_TITLE) + len(label)) * 7 + 24
    md = f"[![{LK.BADGE_TITLE}]({BASE_URL}/badges/{BADGE_DEMO}.svg)]({BASE_URL}/protocols/{BADGE_DEMO}/)"
    return (f'<p class="badge-preview"><img class="cp-badge" src="{prefix}badges/{BADGE_DEMO}.svg" alt="{E(LK.BADGE_TITLE)}: {E(label)}" '
            f'width="{width}" height="20"></p>' + term(md, "Badge Markdown", "Copy the Markdown badge embed"))


def agents_section(prefix=""):
    """M1: curators are the primary reader; agents and protocol teams get one card each and a route to their own page."""
    qs = (term(REST_PY, "Python (requests)", "Copy the Python requests quickstart")
          + term(STATIC_PY, "Python (standard library, static JSON)", "Copy the Python standard-library quickstart")
          + f'<p class="s" style="margin-top:12px"><a href="#hiw-t-agents" data-tab-open="hiw-t-agents">Claude Code, Cursor, curl and cast commands{ARR}</a></p>')
    agents = U.card(U.card_header("AI agents &amp; builders", f"Pre-execution contract checks over MCP or REST: {E(RATE_LIMIT)}, no key, no wallet.")
                    + f'<div data-slot="card-content">{qs}<p class="s" style="margin-top:12px">Remote MCP ({E(REMOTE_TOOLS_DOC)}) · {E(RATE_LIMIT)}.</p></div>'
                    + f'<div data-slot="card-footer" class="links"><a href="{prefix}mcp/">MCP docs{ARR}</a><a href="{prefix}openapi.json">OpenAPI 3.1</a>'
                      f'<a href="{prefix}SKILL.md">SKILL.md</a><a href="{prefix}agent.json">agent.json</a></div>', cls="agents-card")
    teams = U.card(U.card_header("Protocol &amp; security teams", "Keep your public docs and your onchain authority aligned.")
                   + '<div data-slot="card-content"><p class="s">Send a free doc-update notice, commission a 24h verification dossier, '
                     'and embed a live Base-EAS status badge in your docs. Paid work never changes a result.</p>' + badge_demo(prefix) + '</div>'
                   + '<div data-slot="card-footer">' + U.button("For protocol teams", href=f"{prefix}for-protocols/", variant="default")
                   + U.button("Embed a badge", href=f"{prefix}for-protocols/#embed", variant="outline") + '</div>', cls="teams-card")
    return f"""<section class="sec" id="audiences"><div class="wrap">
<div class="sec-head"><h2>Also built for agents and protocol teams</h2><p class="aside">The same data, two more ways in.</p></div>
<div class="aud">{agents}{teams}</div>
</div></section>"""


RADAR_STATE_ORDER = ("ready", "pending", "mixed", "unknown", "executed")


RADAR_STATE_WORD = {"ready": "ready", "pending": "pending", "mixed": "mixed", "unknown": "cancelled or unknown", "executed": "executed"}


# Three Clear Human Doors on /#pricing and /request/ (x402 per-call agent pricing lives strictly on /mcp/, llms.txt & /.well-known/x402)
SELF_SERVE_PLANS = [   # key, title, price, note, bullets, (cta, href, kind), badge, alt_link
    ("scan-free", "Scan & Verify Free", "$0", "No wallet, no key", [
        "All {n} scorecards ({n_eas} Base-EAS verified), free, with live re-check on demand",
        "100% free full Wallet & Safe exposure scan across Ethereum & Base holdings",
        "Free factual re-verification within 7 days whenever a protocol merges a public docs or on-chain fix"],
     ("Scan Free", "scan/", "pricing_scan_free"), None, ("MCP & x402 API", "mcp/", "pricing_mcp")),
    ("sponsor-pool", "Fund a Verification Pool", "$50+", "USDC Pool · $150/protocol Wholesale", [
        "$50 minimum pool with a $25 fixed verification fee; opening soon, reservation or invoice only",
        "$150 per protocol for a sweep of 20 or more protocols (undelivered targets never charged)",
        "Sponsors fund independent checking, never an Aligned rating; disclosed on scorecard"],
     ("Fund a Pool", "bounties/#sponsor-pool", "pricing_sponsor_pool"), "Community & Curators", ("Wholesale scope", "request/?tier=wholesale-150", "pricing_wholesale")),
    ("watch-positions", "Watch My Positions", "$0 Pilot", "Free 30-day pilot", [
        "Email, @Telegram, or HTTPS webhook alerts before queued timelocks & signer rotations execute",
        "30-day pilot with no payment now",
        "$500–$2,500 / month Institutional Allocator & Multi-Vault Watch SLA"],
     ("Start Pilot", "scan/#watch-pilot", "pricing_watch_pilot"), "Free 30-Day Pilot", ("Timelock radar", "radar/", "pricing_radar")),
]
ENTERPRISE_STRIP = [
    ("clearance", "Pre-launch & suite dossiers", "$2,500–$5,000"),
    ("wholesale-150", "Wholesale ecosystem sweep", "$150 / protocol"),
    ("continuous", "Continuous Control-Plane Monitoring", "$500–$2,500 / month"),
    ("community", "Free 7-day fix re-check", "$0"),
    ("api_sla", "API SLA", "custom"),
]


def pricing_cards(idx, home=""):
    nums = site_numbers(idx)
    n, n_eas = nums["protocols"], nums["eas_protocols"]
    out = []
    for key, title, price, note, bullets, (cta, href, kind), badge, (alt_lbl, alt_href, alt_cta) in SELF_SERVE_PLANS:
        lis = "".join(f"<li>{E(b.format(n=n, n_eas=n_eas))}</li>" for b in bullets)
        extra = f'<a class="plan-alt" href="{home}{alt_href}" data-cta="{alt_cta}">{E(alt_lbl)}{ARR}</a>'
        feat = key == "sponsor-pool"
        out.append(U.card((U.badge(E(badge), "info") if badge else "") + f'<h3 data-slot="card-title">{E(title)}</h3>'
                          f'<p class="price">{E(price)}<small>{E(note)}</small></p><ul>{lis}</ul><div class="plan-cta">'
                          + U.button(E(cta), href=f"{home}{href}", variant="default" if feat else "outline", attrs=f'data-cta="{kind}"')
                          + extra + '</div>', cls="plan" + (" feat" if feat else ""), attrs=f'data-plan="{key}"'))
    strip = "".join(f'<a href="{home}request/?tier={k}" data-tier="{k}" data-cta="pricing_{k.replace("-", "_")}"><b>{E(t)}</b><span>{E(p)}</span></a>'
                    for k, t, p in ENTERPRISE_STRIP)
    return (f'<div class="plans" data-pricing>{"".join(out)}</div>'
            f'<div class="ent-strip" data-enterprise-strip><span class="ent-l">Pre-launch, wholesale &amp; institutional scope</span>{strip}</div>'
            f'<p class="note">Paid work never changes a result: pools, sweeps, dossiers and monitoring can still read Docs differ when docs and chain diverge. '
            f'Programmatic AI agents: see <a href="{home}#hiw-t-agents" data-tab-open="hiw-t-agents">AI agent quickstart</a> or <a href="{home}mcp/#x402">metered x402 per-call API</a> ({B2A.FREE_DAILY_QUOTA} free checks/day).</p>')


HEX40 = re.compile(r"0x[0-9a-fA-F]{40}")


def clean_excerpt(text, limit=200):
    """First sentence of a record text without the two failure modes the auditor saw: a cut inside brackets ("(Sourcify match;")
    and a cut mid-word ("a process whi…"). Longer texts end at a word boundary (never inside a 0x value) with " …"."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    depth, end = 0, None
    for i, ch in enumerate(t):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch in ".;" and depth == 0 and i > 0 and not t[i - 1].isdigit():
            if i + 1 == len(t) or t[i + 1] == " ":
                end = i + 1
                break
            if t[i + 1] in "'\"’”" and (i + 2 == len(t) or t[i + 2] == " "):   # a sentence that ends inside a quotation
                end = i + 2
                break
    s = t[:end] if end else t
    if len(s) <= limit:
        return s
    cut = s[:limit]
    for m in HEX40.finditer(s):
        if m.start() < limit < m.end():
            cut = s[:m.start()]
    cut = cut[:cut.rfind(" ")] if " " in cut else cut
    cut = cut.rstrip(" ,;:(")
    while cut.count("(") > cut.count(")"):
        cut = cut[:cut.rfind("(")].rstrip(" ,;:")
    return cut + " …"


def live_check_tabs(chain, address, tid="live"):
    """T2: plain cURL / Python / MCP quickstarts for one contract; no custom User-Agent and no edge-error copy."""
    url = f"{API}/v1/check/preflight?chain={chain}&address={address}"
    py = ("import requests\n"
          f'r = requests.get("{API}/v1/check/preflight",\n'
          f'                 params={{"chain": "{chain}", "address": "{address}"}})\n'
          'print(r.json()["verdict"])')
    mcp = f'pacta_check_preflight({{"chain": "{chain}", "address": "{address}"}})'
    return U.tabs(tid, [("curl", "cURL", term(f'{CURL} "{url}"', "cURL", f"Copy the cURL live check for {address}")),
                        ("python", "Python", term(py, "Python (requests)", f"Copy the Python live check for {address}")),
                        ("mcp", "MCP", term(mcp, f"MCP tool call · {MCP_URL}", f"Copy the MCP tool call for {address}"))], "Live check")


REQUEST_API = f"{API}/v1/requests"


# U6: the request form posts this exact wire schema (additionalProperties false at the Worker). urgency_track per track:
URGENCY = {"community": "community_queue_free", "wholesale-150": "active_due_diligence", "clearance": "issuer_24h_clearance_5k",
           "continuous": "active_due_diligence", "api_sla": "api_high_volume_sla"}


REQUEST_TYPES = [("doc_or_data_discrepancy", "Review a docs-vs-chain difference"), ("missing_protocol", "Add a protocol"),
                 ("missing_check_surface", "Cover another contract or control"), ("unsupported_chain", "Support another chain"),
                 ("mcp_or_api_feature", "API or MCP feature")]


REQUESTER_ROLES = [("protocol_team", "Protocol team"), ("risk_curator_analyst", "Risk curator or analyst"),
                   ("institutional_allocator", "Institutional allocator"), ("defi_developer", "DeFi developer"),
                   ("security_researcher", "Security researcher"), ("individual_user", "Individual"), ("autonomous_agent", "Autonomous agent")]


PURPOSES = [("collateral_due_diligence", "Collateral due diligence"), ("governance_monitoring", "Governance monitoring"),
            ("security_audit", "Security audit"), ("pre_trade_safety", "Pre-trade safety"), ("yield_allocation", "Yield allocation"),
            ("integration_testing", "Integration testing"), ("general_research", "General research")]


def simple_page(slug, title, desc, h1, lede, sections, idx, current=None, og_title=None, wide=False):
    """About / Methodology / Privacy / Terms (M8) and the other static trust pages: prose column, same chrome."""
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    secs_html = "".join(f'<section class="memo-sec" id="{sid}"><h2>{E(h)}</h2>{body}</section>' for sid, h, body in sections)
    body = f"""<body>
{topbar("../", current)}
<main id="main" class="{"wrap" if wide else "memo-wrap"}">
<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span><span>{E(h1)}</span></nav>
<article class="memo legal">
<header><h1>{E(h1)}</h1><p class="lede">{lede}</p></header>
{secs_html}
</article>
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    return head(title, desc, f"{BASE_URL}/{slug}/", prefix="../", og_title=og_title or h1) + "\n" + body


def about_page(idx):
    s = site_numbers(idx)
    anc = idx["onchain_anchoring"]
    reg = anc["commitment_registry"]
    attester = anc["attester_eoa"]
    treasury = anc["treasury_admin"]
    eas_uid = anc["eas_schema_uid"]
    sections = [
        ("who", "Who is behind Pacta", f'<p>Pacta is built and operated by <a href="{FN}" target="_blank" rel="noopener">Fractal Neurons</a>. '
         f'The code is open source under the MIT licence at <a href="{REPO}" target="_blank" rel="noopener">github.com/Fractal-Neurons/pacta</a>, and '
         f'Pacta\'s onchain identity is <code>pacta.base.eth</code>.</p>'),
        ("what", "What Pacta does", f'<p>Pacta reads who can upgrade, pause or change {s["protocols"]} DeFi protocols on Ethereum and Base, and flags where '
         f'that differs from their documentation. Every finding is pinned to a finalized block, can be reproduced with one <code>cast</code> command, '
         f'and {s["checks"]} attested checks are anchored on Base with EAS in the PactaCommitmentRegistry '
         f'(<a href="https://basescan.org/address/{E(reg)}" target="_blank" rel="noopener">{E(short(reg))}</a>).</p>'
         f'<p>Risk curators and diligence teams use it to check collateral before allocating; agents call the same checks over MCP and REST; '
         f'protocol teams use it to keep their documentation and their onchain authority aligned.</p>'),
        ("official-addresses", "Official Domains & Verified On-Chain Addresses",
         f'<p>Verify every Pacta endpoint, attestation contract and operational account directly against this canonical manifest before interacting:</p>'
         f'<dl class="deflist" data-official-addresses>'
         f'<div><dt>Web Index</dt><dd><a href="{BASE_URL}/">{BASE_URL}</a></dd></div>'
         f'<div><dt>Edge API &amp; Remote MCP</dt><dd><a href="{API}/openapi.json" target="_blank" rel="noopener">{API}</a> · Streamable HTTP MCP <code>{API}/mcp</code></dd></div>'
         f'<div><dt>Open-Source Repository</dt><dd><a href="{REPO}" target="_blank" rel="noopener">{REPO}</a></dd></div>'
         f'<div><dt>Base EAS Attester &amp; Schema UID</dt><dd><code>pacta.base.eth</code> · Registry {hexref(reg)} · <a href="{E(anc["eas_schema_url"])}" target="_blank" rel="noopener">Schema {E(short(eas_uid, 6, 4))}{EXT}</a>{copy_btn(eas_uid, "Copy", "Copy Base EAS Schema UID")}</dd></div>'
         f'<div><dt>Outbound Researcher Bounty Treasury EOA</dt><dd>{hexref(attester)} · <code>pacta.base.eth</code> (externally owned account on Base Mainnet exclusively disbursing Pacta-funded Wave 1–3 researcher payouts)</dd></div>'
         f'<div><dt>Commercial Settlement EOA</dt><dd>{hexref(treasury)} (externally owned account on Base and Ethereum exclusively receiving direct commercial invoice and self-serve order settlements)</dd></div>'
         f'</dl>'
         f'<p class="s">Every transaction from or to the operational accounts above is permanently verifiable on BaseScan and Etherscan alongside Pacta&#x27;s public JSON ledgers at <a href="../api/v1/index.json">/api/v1/index.json</a> and <a href="../leaderboard/">/leaderboard/</a>; Pacta never solicits transfers over direct messages or unverified addresses.</p>'
         + (f'<p class="s" data-about-sponsor-custody>Community-funded Verification Pools on <a href="../bounties/#sponsor-pool">/bounties/</a> are held in a '
          f'dedicated multi-signer Base Safe, verified on Base and never mingled with the two operational EOAs above.</p>' if sponsor_pool_live() else
          f'<p class="s" data-about-sponsor-custody>Community-funded Verification Pools on <a href="../bounties/#sponsor-pool">/bounties/</a>: '
          f'{E(SPONSOR_OPENING)} until a dedicated Base Safe is deployed and verified. The intended policy is that pool funds will sit in that '
          f'multi-signer Safe, never mingled with the two operational EOAs above.</p>')),
        ("independence", "Independence and funding", f'<p>{E(EDITORIAL_FIREWALL)} {E(EDITORIAL_INDEPENDENCE)} Paid verification work for protocol teams funds the '
         f'engineering; the data, the API and the MCP server stay free for everyone.</p>'),
        ("contact", "Contact", f'<p>{E(CONTACT_NOTE)}. Security issues: see <a href="../.well-known/security.txt">security.txt</a>; exploit-sensitive '
         f'findings go through the affected protocol\'s bug bounty programme.</p>'),
    ]
    return simple_page("about", "About Pacta · Pacta by Fractal Neurons",
                       "Who is behind Pacta, what it does, how it stays independent and how to reach the team.", "About Pacta",
                       "Independent control-plane scorecards for DeFi, by Fractal Neurons.", sections, idx, og_title="About Pacta")


def live_checker_note(idx, s):
    """v4.5 G-P2-2: three sentences on the single-contract heuristic vs the multi-contract grade, and the catalog's delta counts."""
    n_pd = sum(e["classification"] == "parameter_delta" for e in idx["entries"])
    return (f'The live checker reads one contract address at the latest block and gives it a 0–100 heuristic score from its bytecode and '
            f'storage: who can upgrade or change it, through which controller, and how fast. A Docs-vs-chain status is different: it compares '
            f'everything a protocol documents about its control plane with every record Pacta has pinned for it, across many contracts. A '
            f'protocol can read Docs differ while one of its contracts scores 0, and an Aligned protocol can include a contract a multisig can change. '
            f'Across the catalog, {s["delta"]} of the {s["protocols"]} protocols carry at least one adverse docs-vs-chain difference ({n_pd} parameter-level differences across '
            f'{s["checks"]} attested checks), and {s["protective"]} carry protective differences where the chain is stricter than documented.')


def methodology_page(idx):
    """M3: one vocabulary, one legend. Every label the site uses is defined here."""
    import scorecard as SC
    s = site_numbers(idx)
    status_rows = [("Aligned", "neutral", "The published documentation matches the sampled onchain controls. It says the docs are accurate, not that the protocol is low-risk.", s["aligned"]),
                   ("Docs differ", "warning", "Docs and chain differ: the live controls are looser than, or different from, what the protocol documents.", s["delta"]),
                   ("Protective", "info", "Docs and chain differ in the safe direction: the live controls are stricter than documented.", s["protective"]),
                   ("Observed", "outline", "The onchain control plane is pinned at a finalized block over RPC; the documentation has not been compared yet.", s["observed"])]
    status = "".join(f'<tr><td>{U.badge(k, v, cls="grade")}</td><td>{E(d)}</td><td class="num">{n}</td></tr>' for k, v, d, n in status_rows)
    factor_def = {"upgrade": "Who can replace the contract code, and through what path (immutable, timelocked, multisig, single key).",
                  "timelock": "The shortest enforced delay before a privileged change can execute.",
                  "quorum": "The signer threshold of the multisigs that control the contracts.",
                  "emergency": "Who can pause, freeze or blacklist, and how broad that power is.",
                  "parity": "Whether the documented controls match the chain (uncompared for Observed protocols)."}
    factors = "".join(f'<tr><td><b>{E(lbl)}</b></td><td>{E(factor_def[k])}</td></tr>' for k, lbl in SC.FACTORS)
    states = "".join(f'<tr><td><span class="fdot r-{k}" aria-hidden="true">{FACTOR_LETTER[k]}</span>{E(SC.STATE_LABEL[k])}</td><td>{E(d)}</td></tr>'
                     for k, d in (("g", "Long green slice: the control meets a strong standard (for example a multi-day timelock)."),
                                  ("b", "Medium yellow slice: partial protection."),
                                  ("a", "Short red slice: weak or no protection."),
                                  ("n", "Hollow dashed slice: the published evidence does not decide it. Pacta never guesses."),
                                  ("u", "Hollow dashed slice: docs-vs-chain parity is not compared (Observed protocols).")))
    verdicts = [("No standard upgrade or admin authority detected", "Neutral. No proxy admin, owner or role with upgrade power was found at this address."),
                ("Changes wait behind a timelock", "Neutral. Privileged changes go through an enforced delay."),
                ("A multisig can change it with no delay", "Warning. A Safe can change the contract without a waiting period."),
                ("A single key can change it instantly", "Warning. One externally owned account controls it."),
                ("Timelock with a zero delay", "Warning. A timelock exists but enforces no delay."),
                ("Controller needs further review", "Warning. An unclassified contract controls it."),
                ("No contract code at this address", "Neutral. The address is an EOA or not deployed.")]
    vt = "".join(f'<tr><td>{E(a)}</td><td>{E(b)}</td></tr>' for a, b in verdicts)
    tbl = lambda cap, heads, rows: (f'<table class="tbl legend-table"><caption class="sr-only">{E(cap)}</caption><thead><tr>'
                                    + "".join(f'<th scope="col">{h}</th>' for h in heads) + f'</tr></thead><tbody>{rows}</tbody></table>')
    sections = [
        ("how", "How it works", '<ol><li><b>Read the docs.</b> Pacta records what each protocol publishes about who can upgrade, pause or change its '
         'contracts, and how long changes must wait.</li><li><b>Read the chain at a finalized block.</b> The same controls are read at a finalized '
         'block on two independent RPC providers.</li><li><b>Attest the difference on Base.</b> Each result is attested with EAS on Base, so anyone '
         'can re-check it later with <code>cast</code>.</li></ol>'),
        ("docs-vs-chain", "Docs vs chain", '<p>One status per protocol, used in every table, badge and feed:</p>'
         + tbl("Docs-vs-chain statuses", ["Status", "Meaning", "Protocols"], status)
         + '<p class="s">Record-level classifications in the JSON feeds map onto the same words: <code>parameter_delta</code> = Docs differ, '
           '<code>protective_delta</code> = Protective, <code>aligned_baseline</code> = Aligned, <code>rpc_observed</code> = Observed. The embeddable '
           'badges read "Aligned · Base EAS", "Parameter Delta" or "RPC-Observed" for the same three cases. A protocol reads Docs differ if any of its records '
           'does; "Reconciled" marks a difference that was fixed and re-attested as Aligned.</p>'),
        ("rosette", "The control-strength graphic", '<p>Five factors, clockwise from the top. Colour, slice length and a letter carry the same '
         'information, so the graphic never relies on colour alone; hover or focus a slice to read it.</p>'
         + tbl("Control-strength factors", ["Factor", "What it measures"], factors) + tbl("Control-strength states", ["State", "How it looks"], states)),
        ("live-checker", "The live contract check", f'<p>{live_checker_note(idx, s)}</p><p>The checker on the homepage and <code>/v1/check/preflight</code> read <b>one contract address</b> '
         'at the latest block. Its verdict and its 0–100 heuristic score rate that single address, not the whole protocol: a protocol can read Docs differ '
         'while one of its token contracts has no admin at all. Confidence says whether the address is an indexed, verified record or a bytecode '
         'heuristic.</p>' + tbl("Live check verdicts", ["Verdict", "Meaning"], vt)
         + '<p class="s">Amber is reserved for warnings everywhere on the site. Neutral and good results are never amber.</p>'),
        ("evidence", "Evidence and reproducibility", f'<p>Every record names its block number and block hash, the contract and the call. '
         f'{s["checks"]} attested checks are anchored in {s["batches"]} Base EAS batch attestations; the {s["observed"]} Observed protocols are '
         f'pinned over RPC and reproducible with <code>cast</code>, but not attested yet. Machine-readable: '
         f'<a href="../api/v1/scorecards.json">scorecards.json</a>, <a href="../api/v1/index.json">index.json</a>, '
         f'<a href="../api/v1/rpc-pinned.json">rpc-pinned.json</a>.</p>'),
        ("independence", "Independence policy", f'<p>{E(EDITORIAL_FIREWALL)} {E(EDITORIAL_INDEPENDENCE)}</p>'
         '<p>Paid verification work for protocol teams funds the engineering; the data, the API and the MCP server stay free for everyone.</p>'),
        ("corrections", "Corrections Log",
         '<p>Pacta logs parser, schema and record corrections transparently so institutional allocators and protocol teams can audit every change:</p>'
         '<ul class="corr-log" data-corrections-log>'
         '<li><b>2026-11-20 — Scorecard timelock parser (<code>tools/scorecard.py</code>):</b> broadened admin/executor delay extraction to capture prose executor delays (including Aave V3 / GHO&#x27;s 86,400s Executor Lvl1) and clarified hollow-slice copy from &ldquo;No enforced admin delay in the published records&rdquo; to &ldquo;Admin delay not extracted in structured record&rdquo;.</li>'
         '</ul>'),
        ("glossary", "Glossary", '<dl class="deflist"><div><dt>Control plane</dt><dd>The set of keys, multisigs, timelocks and roles that can change '
         'a protocol.</dd></div><div><dt>Finalized block</dt><dd>A block the chain will not reorganize; reads pinned to it are reproducible.</dd></div>'
         '<div><dt>EAS</dt><dd>Ethereum Attestation Service: Pacta signs each result onchain on Base.</dd></div><div><dt>Timelock</dt><dd>A '
         'contract that forces a delay between queuing and executing a change.</dd></div><div><dt>x402</dt><dd>An HTTP payment protocol for '
         'metered API calls; Pacta\'s free tier needs no payment.</dd></div><div><dt>MCP</dt><dd>Model Context Protocol: how AI agents call '
         'Pacta\'s tools.</dd></div></dl>'),
    ]
    return simple_page("methodology", "Methodology and glossary · Pacta",
                       "How Pacta compares protocol docs with onchain controls: statuses, the five-factor control-strength graphic, the live contract check and the evidence.",
                       "Methodology", "One vocabulary for every label on the site: what each status, control-strength slice and live-check verdict means.",
                       sections, idx, og_title="Pacta methodology")


def privacy_page(idx):
    sections = [
        ("summary", "Summary",
         '<p>Pacta has no user accounts. First-party telemetry stores aggregate counts only (zero raw IP addresses). '
         'On the public production domains (<code>pacta.wtf</code> and <code>pacta.fractalneurons.com</code>), Pacta also loads the X '
         '(Twitter) conversion measurement tag (<code>static.ads-twitter.com/uwt.js</code>, pixel <code>rjbqn</code>), which sets '
         'advertising attribution cookies unless blocked by your browser or content blocker.</p>'),
        ("analytics", "First-party page telemetry",
         '<p>Pages count anonymous, first-party aggregate page views through a small script on pacta.wtf '
         '(<code>b.js</code>): zero cookies, zero identifiers in browser storage, zero raw IP addresses stored, and nothing is sent by '
         '<code>b.js</code> when your browser sends Do Not Track (<code>navigator.doNotTrack = &quot;1&quot;</code>). A page view records '
         'only a closed-set page path, the referring site&#x27;s public host name, allowlisted campaign tags '
         '(<code>utm_source</code>, <code>utm_medium</code>, <code>utm_campaign</code>) and which Pacta domain served it.</p>'),
        ("x-pixel", "X (Twitter) Ads conversion measurement",
         '<p>To measure X campaign performance, public pages on <code class="nw">pacta.wtf</code> and <code class="nw">pacta.fractalneurons.com</code> load '
         'X&#x27;s Universal Website Tag (<code>https://static.ads-twitter.com/uwt.js</code>, pixel ID <code class="nw">rjbqn</code>). It records '
         'ad-attributed page visits (<code class="nw">config rjbqn</code>), live-checker or checkout intent (<code class="nw">tw-rjbqn-rjhie</code>, at most '
         'once per page load, with no wallet address or form text attached), and verified self-serve orders '
         '(<code class="nw">tw-rjbqn-rjhif</code>, sending only the USD order value and non-personal <code class="nw">orderId</code>; internal QA canary '
         'transactions and idempotent replays are excluded). Staging previews and localhost never load <code class="nw">uwt.js</code>.</p>'
         '<p><code class="nw">uwt.js</code> sets cookies and sends requests to <code class="nw">analytics.twitter.com</code> and <code class="nw">t.co</code> under '
         'X&#x27;s privacy policy. A small first-party <code class="nw">localStorage</code> entry (<code class="nw">pacta-x-purchased</code>) stores recent '
         '<code class="nw">orderId</code> strings in your browser solely so reloading a receipt never reports a duplicate purchase. To block X '
         'conversion measurement and cookies, enable tracker / third-party cookie blocking in your browser (Brave Shields, Firefox '
         'Enhanced Tracking Protection, Safari Intelligent Tracking Prevention, or uBlock Origin blocking '
         '<code class="nw">static.ads-twitter.com</code>, <code class="nw">analytics.twitter.com</code> and <code class="nw">t.co</code>) and review your X Ads '
         'personalization settings.</p>'),
        ("checkout", "Self-serve checkout", '<p>Verify on-chain &amp; unlock sends the product, the Base transaction hash, the target '
         'chain and address, the protocol or docs URL and, only if you enter one, a contact handle or webhook URL to Pacta&#x27;s API. The '
         'contact or webhook is kept privately for delivery and never published. A payment on Base is public on-chain, like any transfer. '
         'Pay on Base talks only to the wallet in your browser; Pacta never sees your keys.</p>'),
        ("checks", "Live checks", f'<p>When you press Check, the address and chain you entered are sent to Pacta\'s API at <code>{E(API)}</code>. '
         f'"Verify live on RPC" sends read-only JSON-RPC calls from your browser directly to public RPC providers (publicnode.com, drpc.org, '
         f'base.org), which see your IP address under their own policies.</p>'),
        ("watch-pilot", "Opted-in watch pilot & Sponsor Pool intake",
         '<p>When you opt in to the free 30-day watch pilot, which sends alerts when contract controls change (<code>POST /v1/pilot/watch</code>), or reserve a community '
         'Verification Pool (<code>POST /v1/pilot/sponsor-pool</code>), the target address or protocol and your chosen delivery destination '
         '(email, <code>@Telegram</code>, or <code>https://</code> webhook URL) are stored privately in <code>PactaLedgerDO</code> durable actor '
         'storage and write-only private KV. They are used only to deliver the alerts you ask for and opted-in setup replies '
         'from Pacta (<code>pacta@dri.network</code>), and are never exposed on public endpoints, sold, or used for cold marketing.</p>'),
        ("requests", "Requests you send", '<p>The request form sends the track, protocols, scope text and, only if you enter one, a contact '
         'handle to Pacta\'s API so the team can answer. Do not include personal or sensitive information beyond a contact handle. GitHub issues '
         'and emails you choose to send are handled by those services.</p>'),
        ("contact", "Contact", f'<p>{E(CONTACT_NOTE)}</p>'),
    ]
    return simple_page("privacy", "Privacy · Pacta",
                       "What the Pacta site and API collect: aggregate first-party telemetry without raw IPs, X Ads conversion measurement (uwt.js), and only what you submit.",
                       "Privacy", "What this site collects, how conversion measurement works, and how to block it.", sections, idx)


def terms_page(idx):
    sections = [
        ("use", "Use of the site and data", f'<p>Pacta publishes read-only analysis of public onchain state and public documentation. The '
         f'scorecards, records, feeds, API and MCP server are free to use, subject to the published rate limit ({E(RATE_LIMIT)}). The code is '
         f'MIT-licensed at <a href="{REPO}" target="_blank" rel="noopener">GitHub</a>.</p>'),
        ("advice", "Not investment advice", '<p>Nothing on Pacta is investment, legal or security advice. A status describes whether documentation '
         'matches onchain controls at a block; it is not a safety rating. Verify anything that matters with the reproduction commands.</p>'),
        ("warranty", "No warranty", '<p>Data is provided as is. Chains and documentation change; every record states the block it was read at.</p>'),
        ("paid", "Paid engagements", f'<p>Paid verification work is agreed per request: scope is confirmed first, then settled by commercial '
         f'invoice or USDC. {E(EDITORIAL_FIREWALL)} {E(EDITORIAL_INDEPENDENCE)}</p>'),
        ("disclosure", "Security disclosure", '<p>Exploit-sensitive findings are never published here. Report them through the affected protocol\'s '
         'bug bounty programme or <a href="../.well-known/security.txt">security.txt</a>.</p>'),
        ("contact", "Contact", f'<p>{E(CONTACT_NOTE)}</p>'),
    ]
    return simple_page("terms", "Terms of use · Pacta",   # v4.5 G-P2-8: a 113-character description
                       "Terms for Pacta's free data, API and MCP server, and for paid verification: what Pacta does and does not promise.",
                       "Terms of use", "Plain terms for the free data, the API and paid verification work.", sections, idx, og_title="Pacta terms of use")


def scorecards_page(idx):
    cards = scorecards(idx)
    n = len(cards)
    body = f"""<body>
{topbar("../", "scorecards/")}
<main id="main">
<div class="wrap" style="padding-top:32px"><nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span><span>Scorecards</span></nav></div>
{scorecards_section(cards, "../", full=True, heading="h1").replace('<section class="sec" id="scorecards">', '<section class="sec" id="scorecards" style="padding-top:0">', 1).replace("</h1>", "</h1>" + fresh_pill(idx), 1)}
</main>
{footer(coverage_line(idx), idx["onchain_anchoring"]["commitment_registry"], "../")}
</body></html>
"""
    return head("Protocol scorecards · Pacta", f"Docs vs chain for {n} DeFi protocols on Ethereum and Base, with a five-factor control-strength graphic.",
                f"{BASE_URL}/scorecards/", prefix="../", og_title="Protocol scorecards · Pacta",
                image=f"{BASE_URL}/cards/x-card-scorecards-1200x628.png", image_size=SOCIAL_SIZE) + "\n" + body


def radar_snapshot_line(radar):
    """B6: the one snapshot line on /radar/: each chain's finalized block (linked), the snapshot time and its relative age."""
    r = radar["refreshed_at"]
    blocks = " · ".join(f'{CHAINS[ch][0]} finalized block {xlink(ch, "block", p_["block_number"], "#" + format(p_["block_number"], ","))}'
                        for ch, p_ in radar_pins(radar))
    return (f'<p class="fresh radar-snap" data-fresh data-radar-snapshot><span class="dot" aria-hidden="true"></span>'
            f'<span>Snapshot: {blocks} · {E(r["block_time_utc"])}<span class="obs-age" data-age="{r["block_timestamp"]}"></span> · re-checked live in your browser</span></p>')


def radar_page(idx, radar):
    body = f"""<body>
{topbar("../", "radar/")}
<main id="main">
<div class="wrap" style="padding-top:32px"><nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span><span>Radar</span></nav></div>
{radar_section(radar, "../", full=True).replace('<section class="sec" id="radar"', '<section class="sec" style="padding-top:0" id="radar"', 1).replace("</h1>", "</h1>" + radar_snapshot_line(radar), 1).replace('<div class="radar-head">', watch_pilot_box("../", heading="Watch Queued Timelocks Free (30-Day Pilot)", id_attr="watch-pilot", compact=True) + '<div class="radar-head">', 1)}
</main>
{footer(coverage_line(idx), idx["onchain_anchoring"]["commitment_registry"], "../")}
</body></html>
"""
    return head("Queued timelock radar · Pacta", "Governance changes queued in DeFi timelocks on Ethereum and Base, read at finalized blocks and re-checked live.",
                f"{BASE_URL}/radar/", prefix="../", og_title="Pacta queued timelock radar") + "\n" + body


def pricing_redirect_page():
    """T5: /pricing/ lands on the pricing section of the homepage (static meta refresh; a link for no-refresh clients)."""
    t, d, img = "Pricing · Pacta", "Pacta pricing: $0 full wallet & protocol scan and free 7-day fix re-verification, $50 minimum community Verification Pools & $150/protocol sweeps of 20+, and a free 30-day alert pilot.", f"{BASE_URL}/og-preview.png"
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{E(t)}</title><meta name="description" content="{E(d)}">'
            f'<meta property="og:type" content="website"><meta property="og:site_name" content="Pacta by Fractal Neurons">'
            f'<meta property="og:title" content="{E(t)}"><meta property="og:description" content="{E(d)}"><meta property="og:url" content="{BASE_URL}/#pricing">'
            f'<meta property="og:image" content="{img}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(t)}"><meta name="twitter:description" content="{E(d)}">'
            f'<meta name="twitter:image" content="{img}"><meta name="twitter:site" content="{X_HANDLE}"><meta name="robots" content="{ROBOTS_META_404}">'
            f'<link rel="canonical" href="{BASE_URL}/#pricing"><meta http-equiv="refresh" content="0; url=../#pricing">'
            '<meta name="referrer" content="strict-origin-when-cross-origin">'
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}"><script src="../b.js" defer></script></head>'
            '<body><p><a href="../#pricing">Pacta pricing</a></p></body></html>\n')


def _effective_wallet_status(it, card):
    g = (card or {}).get("grade", "").lower()
    cl = (it or {}).get("classification", "")
    changed = ((it or {}).get("whatDiffers") or {}).get("changed") or []
    if g == "delta" or cl == "parameter_delta" or any(c.get("classification") == "parameter_delta" for c in changed):
        return "DELTA", "parameter_delta"
    if g == "protective" or cl == "protective_delta" or any(c.get("classification") == "protective_delta" for c in changed):
        return "PROTECTIVE", "protective_delta"
    if g == "aligned" or cl == "aligned_baseline" or (it or {}).get("easAttested"):
        return "ALIGNED", "aligned_baseline"
    return "OBSERVED", "rpc_observed"


def wallet_tokens_json(cards, lk):
    """Compact deterministic client catalog (/api/v1/wallet-tokens.json) for browser-direct Multicall3.aggregate3 fallback & instant demos."""
    cat = json.load(open(os.path.join(ROOT, "data", "wallet-multicall-catalog.json"), encoding="utf-8"))
    rec = json.load(open(os.path.join(ROOT, "data", "wallet-receipt-tokens.json"), encoding="utf-8"))
    cards_by_slug = {c["slug"]: c for c in cards}
    chains_out = {"ethereum": [], "base": []}
    referenced_slugs = set()
    for ch in ("ethereum", "base"):
        seen = set()
        for row in rec.get(ch, []):
            addr, slug, sym = row["address"], row["slug"], row.get("symbol", "")
            k = addr.lower()
            if k not in seen and slug in lk:
                seen.add(k)
                chains_out[ch].append([addr, slug, sym])
                referenced_slugs.add(slug)
        for row in cat.get(ch, []):
            addr, slug, sym = row["address"], row["slug"], row.get("symbol_hint", "")
            k = addr.lower()
            if k not in seen and slug in lk:
                seen.add(k)
                chains_out[ch].append([addr, slug, sym])
                referenced_slugs.add(slug)
    demos = {
        "demo_safe_eth_base": {
            "wallet": "0x5afE00003f5D8B29c4107E3A92d1b64E8C410305",
            "label": "Demo Multi-Vault Treasury Safe",
            "custody": {"isSafe": True, "chains": ["ethereum", "base"], "threshold": 3, "ownerCount": 5},
            "blocks": {"ethereum": {"number": 26451608}, "base": {"number": 59847352}},
            "holdings": [
                {"chain": "base", "address": "0xbeeF010f9cb27031ad51e3333f9aF9C6B1228183", "symbol": "steakUSDC", "slug": "steakhouse-usdc-metamorpho-base", "formattedBalance": "425,000"},
                {"chain": "ethereum", "address": "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0", "symbol": "wstETH", "slug": "lido-steth-dual-governance", "formattedBalance": "140.5"},
                {"chain": "base", "address": "0x0000000f2eB9f69274678c76222B35eEc7588a65", "symbol": "yoUSD", "slug": "yo-protocol", "formattedBalance": "85,000"},
                {"chain": "ethereum", "address": "0xA35b1B31Ce002FBF2058D22F30f95D405200A15b", "symbol": "ETHx", "slug": "stader-labs-ethx", "formattedBalance": "62.0"},
            ],
        },
        "demo_base_yield": {
            "wallet": "0xba5E00007C41D92e8A305F6b11c8E92D40A20845",
            "label": "Demo Base Yield Wallet",
            "custody": {"isSafe": False, "chains": [], "threshold": None, "ownerCount": None},
            "blocks": {"ethereum": None, "base": {"number": 59847352}},
            "holdings": [
                {"chain": "base", "address": "0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB", "symbol": "aBasUSDC", "slug": "aave-v3-base", "formattedBalance": "64,200"},
                {"chain": "base", "address": "0xEdc817A28E8B93B03976FBd4a3dDBc9f7D176c22", "symbol": "mUSDC", "slug": "moonwell-lending-base", "formattedBalance": "28,500"},
                {"chain": "base", "address": "0x1BCae9292b28b922C9ad2902C07bc25C4F9347E1", "symbol": "SEAM", "slug": "seamless-protocol-base", "formattedBalance": "19,400"},
            ],
        },
    }
    for d in demos.values():
        for h in d["holdings"]:
            referenced_slugs.add(h["slug"])
    protos = {}
    for slug in sorted(referenced_slugs):
        it = lk.get(slug)
        if not it:
            continue
        card = cards_by_slug.get(slug)
        st, cl = _effective_wallet_status(it, card)
        entry = {
            "name": it["name"],
            "status": st,
            "classification": cl,
            "easAttested": bool(it.get("easAttested")),
            "pinnedBlock": it.get("pinnedBlock"),
            "documentedDelaySeconds": it.get("documentedDelaySeconds"),
            "observedDelaySeconds": it.get("observedDelaySeconds"),
            "baseEasUids": list(it.get("baseEasUids") or []),
            "controllerAddress": it.get("controllerAddress"),
            "controllerKind": it.get("controllerKind"),
            "summary_short": (card or {}).get("summary_short") or "",
        }
        if st in ("DELTA", "PROTECTIVE") and it.get("whatDiffers"):
            entry["whatDiffers"] = it["whatDiffers"]
        protos[slug] = entry
    out = {
        "schema": "pacta.wallet_tokens.v1",
        "multicall3": cat["multicall3"],
        "counts": {"ethereum": len(chains_out["ethereum"]), "base": len(chains_out["base"]), "protocols": len(protos)},
        "ethereum": chains_out["ethereum"],
        "base": chains_out["base"],
        "protocols": protos,
        "demos": demos,
    }
    return json.dumps(out, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def _cur_grade(idx, it):
    """The scorecard grade of a curator matrix record (scorecards.json is the source of truth; the matrix label is a fallback)."""
    try:
        return card_for(idx, it["slug"])["grade"]
    except KeyError:
        return {"DELTA": "delta", "PROTECTIVE": "protective", "OBSERVED": "observed"}.get(str(it.get("grade", "")).upper(), "aligned")


def _curator_item_row(it, tone="aligned", idx=None):
    slug = it["slug"]
    if idx is not None and tone != "gap":
        it = dict(it, grade=_cur_grade(idx, it).upper())
    ch = (it.get("chains") or ["ethereum"])[0]
    ch_lbl = "Base" if ch == "base" else "Ethereum"
    blk = it.get("pinnedBlock")
    uid = (it.get("baseEasUids") or [""])[0]
    addr = it.get("primaryContract") or ""
    pill_lbl = "ADVERSE GAP" if tone == "gap" else ("PROTECTIVE" if it.get("grade") == "PROTECTIVE" else ("OBSERVED" if it.get("grade") == "OBSERVED" else "ALIGNED"))
    pill_tone = "gap" if tone == "gap" else ("protective" if it.get("grade") == "PROTECTIVE" else ("observed" if it.get("grade") == "OBSERVED" else "aligned"))
    eas_html = (f'<a class="cur-eas mono" href="https://base.easscan.org/attestation/view/{uid}" target="_blank" rel="noopener">'
                f'EAS {short(uid, 6, 4)}{EXT}</a>') if uid else '<span class="cur-eas mono muted">RPC-pinned</span>'
    scan_href = f'../scan/?chain={ch}&amp;address={addr}' if HEX40.fullmatch(addr) else '../scan/'
    blk_html = f'<span class="mono">{ch_lbl} #{int(blk):,}</span>' if isinstance(blk, int) else f'<span class="mono">{ch_lbl}</span>'
    return (
        f'<li class="cur-item" data-cur-grade="{E(it.get("grade", ""))}">'
        f'<div class="cur-item-top">'
        f'<span class="cur-item-id"><img class="pid-logo" src="../{proto_icon_rel(slug)}" alt="" width="20" height="20" loading="lazy" decoding="async">'
        f'<a class="cur-proto-a" href="../protocols/{slug}/">{E(it["name"])}</a>'
        f'<span class="pf-st-pill" data-tone="{pill_tone}">{pill_lbl}</span></span>'
        f'<span class="cur-item-links">{blk_html}{eas_html}'
        f'<a class="cur-scan-a" href="{scan_href}" title="Scan {E(it["name"])} or a wallet holding it">Scan{ARR}</a></span>'
        f'</div>'
        f'<p class="cur-item-sum">{E(it.get("summary_short") or "")}</p>'
        f'</li>'
    )


def curators_page(idx):
    """/curators/: clinical, zero-FUD Institutional Vault Curator & Collateral Exposure Matrix from data/curator-exposure-matrix.json."""
    mat = json.load(open(os.path.join(ROOT, "data", "curator-exposure-matrix.json"), encoding="utf-8"))
    totals = mat["dataset_totals"]
    curators = mat["curators_and_institutional_allocators"]
    count_line = coverage_line(idx)
    reg = idx["onchain_anchoring"]["commitment_registry"]
    crumbs = ('<nav class="crumbs" aria-label="Breadcrumb"><a href="../">Pacta</a><span aria-hidden="true">/</span>'
              '<span>Curator Exposure Matrix</span></nav>')

    tbl_rows = []
    cards_html = []
    for c in curators:
        cid = c["curator_id"]
        wc = c["wrapper_counts"]
        uc = c["underlying_182_eas_counts"]
        wrappers = c.get("direct_wrappers") or []
        u_gaps = c.get("underlying_adverse_gaps") or []
        u_al = c.get("underlying_aligned_protective") or []
        first_target = wrappers[0] if wrappers else (u_gaps[0] if u_gaps else None)
        first_ch = ((first_target.get("chains") or ["ethereum"])[0]) if first_target else "ethereum"
        first_addr = (first_target.get("primaryContract") or "") if first_target else ""
        scan_vault_href = f'../scan/?chain={first_ch}&address={first_addr}' if HEX40.fullmatch(first_addr) else '../scan/'
        pool_href = f'../bounties/?protocol={first_target["slug"]}#sponsor-pool' if first_target else '../bounties/#sponsor-pool'

        def grade_counts(items):
            g_ = [_cur_grade(idx, x) for x in items]
            return {k: g_.count(k) for k in ("aligned", "protective", "delta", "observed")}

        def count_pills(cnt, gaps_word):
            parts = [f'<span class="pf-st-pill" data-tone="aligned">{cnt["aligned"]} Aligned</span>'] if cnt["aligned"] else []
            parts += [f'<span class="pf-st-pill" data-tone="protective">{cnt["protective"]} Protective</span>'] if cnt["protective"] else []
            parts += [f'<span class="pf-st-pill" data-tone="gap">{cnt["delta"]} {gaps_word}</span>'] if cnt["delta"] else []
            parts += [f'<span class="pf-st-pill" data-tone="observed">{cnt["observed"]} Pinned</span>'] if cnt["observed"] else []
            return " ".join(parts)

        wcnt = grade_counts(wrappers)
        assert sum(wcnt.values()) == wc["total"], (cid, wcnt, wc)
        w_badges = (count_pills(wcnt, "Gap" if wcnt["delta"] == 1 else "Gaps") if wc["total"] > 0
                    else '<span class="pf-st-pill" data-tone="observed">Direct market curation</span>')
        ucnt = grade_counts(u_al)
        assert ucnt["aligned"] + ucnt["protective"] == uc["aligned_or_protective"] and len(u_gaps) == uc["adverse_gaps_delta"], (cid, ucnt, uc)
        ucnt["delta"] = uc["adverse_gaps_delta"]
        u_badges = count_pills(ucnt, "Adverse gaps" if ucnt["delta"] != 1 else "Adverse gap")
        name_link = f'<a class="cur-row-name" href="#{E(cid)}"><b>{E(c["curator_name"])}</b></a>'

        short_insight = clean_excerpt(c["curator_exposure_insight"], 145)
        tbl_rows.append(
            f'<tr data-curator-row="{E(cid)}">'
            f'<td data-label="Curator / Allocator">{entity_cell(c["curator_name"], name_link)}'
            f'<span class="cur-row-role">{E(c["role_archetype"])}</span></td>'
            f'<td data-label="Direct Wrapper Vaults"><div class="cur-pill-pair">{w_badges}</div></td>'
            f'<td data-label="Underlying Collateral Exposure"><div class="cur-pill-pair">{u_badges}</div></td>'
            f'<td class="hide-m" data-label="Verified Control-Plane Takeaway"><span class="cur-row-note">{E(short_insight)}</span></td>'
            f'<td class="r" data-label="Inspect"><div class="cur-row-acts">'
            f'<a class="cur-act-link" href="#{E(cid)}">View matrix</a>'
            f'<a class="cur-act-link" href="{E(scan_vault_href)}">Scan Vault{ARR}</a></div></td>'
            f'</tr>'
        )

        if wrappers:
            w_list = '<ul class="cur-list">' + "".join(_curator_item_row(w, "gap" if w.get("grade") == "DELTA" else "aligned", idx) for w in wrappers) + '</ul>'
        else:
            w_list = ('<p class="cur-empty">Curates isolated lending markets and collateral parameters directly on host protocols '
                      '(see underlying market &amp; collateral exposure alongside).</p>')

        gap_items = "".join(_curator_item_row(g, "gap", idx) for g in u_gaps)
        al_chips = "".join(
            f'<a class="cur-al-chip" href="../protocols/{a["slug"]}/">'
            f'<img class="pid-logo" src="../{proto_icon_rel(a["slug"])}" alt="" width="20" height="20" loading="lazy" decoding="async">'
            f'<span>{E(a["name"])}</span><span class="pf-st-pill" data-tone="{_cur_grade(idx, a)}">{_cur_grade(idx, a).capitalize()}</span></a>'
            for a in u_al
        )
        al_block = (f'<div class="cur-al-wrap"><span class="cur-sub-k mono">ALIGNED / PROTECTIVE UNDERLYING BASELINES ({len(u_al)})</span>'
                    f'<div class="cur-al-chips">{al_chips}</div></div>') if u_al else ""
        u_list = (('<ul class="cur-list">' + gap_items + '</ul>') if gap_items else '') + al_block

        edges = c.get("verified_contagion_edges") or []
        edge_html = (f'<p class="cur-edges mono"><b>Verified graph edges:</b> {E(" · ".join(edges))}</p>') if edges else ""
        xh = c.get("x_handle") or ""
        xh_html = f'<span class="cur-x mono">{E(xh)}</span>' if xh else ""

        cards_html.append(
            f'<article class="cur-card" id="{E(cid)}" data-curator-card="{E(cid)}">'
            f'<div class="cur-card-head">'
            f'<div class="cur-card-id"><div class="cur-title-row"><h3>{E(c["curator_name"])}</h3>{xh_html}</div>'
            f'<p class="cur-role">{E(c["role_archetype"])}</p></div>'
            f'<div class="cur-card-ctas">'
            + U.button("Scan Vault", href=scan_vault_href, variant="outline", size="sm", attrs=f'data-cta="cur_scan_{cid.replace("-", "_")[:14]}"')
            + U.button("Fund a Pool", href=pool_href, variant="default", size="sm", attrs=f'data-cta="cur_pool_{cid.replace("-", "_")[:14]}"')
            + '</div></div>'
            f'<div class="cur-insight"><p>{E(c["curator_exposure_insight"])}</p>{edge_html}</div>'
            f'<div class="cur-cols">'
            f'<div class="cur-col cur-col-wrap">'
            f'<div class="cur-col-head"><span class="step-k mono">LAYER 1 · DIRECT WRAPPER VAULTS</span>{w_badges}</div>'
            f'{w_list}</div>'
            f'<div class="cur-col cur-col-under">'
            f'<div class="cur-col-head"><span class="step-k mono">LAYER 2 · UNDERLYING MARKET &amp; COLLATERAL EXPOSURE</span>{u_badges}</div>'
            f'{u_list}</div>'
            f'</div></article>'
        )

    hero = (
        f'<section class="sec cur-hero" id="curators-top"><div class="wrap">{crumbs}'
        f'<div class="cur-hero-grid">'
        f'<div class="cur-hero-main">'
        f'<span data-slot="badge" data-variant="info">Institutional Vault Curator &amp; Collateral Matrix</span>'
        f'<h1>Wrapper vaults are often Aligned. Collateral risk sits one layer deeper.</h1>'
        f'<p class="lede">Pacta reconciles published security documentation against block-pinned Ethereum &amp; Base storage across '
        f'{totals["indexed_protocols"]} protocols ({totals["base_eas_attested_protocols"]} Base-EAS attested · '
        f'{totals["grades_breakdown"]["DELTA_adverse_gaps"]} verified adverse control-plane gaps). Inspect how direct MetaMorpho, '
        f'BoringVault, ERC-4626, and treasury wrappers compare against their downstream RWA, LST, and lending collateral markets.</p>'
        f'<div class="cur-hero-ctas">'
        + U.button("Scan Any Safe", href="../scan/", variant="default", size="lg", attrs='data-cta="curators_scan"')
        + U.button("Fund a Pool", href="../bounties/#sponsor-pool", variant="outline", size="lg", attrs='data-cta="curators_pool"')
        + '</div></div>'
        f'<div class="cur-stats" aria-label="Curator matrix totals">'
        f'<div class="cur-stat"><b>{len(curators)}</b><span>Curator &amp; Allocator Stacks</span></div>'
        f'<div class="cur-stat"><b>{totals["base_eas_attested_protocols"]}</b><span>Base-EAS Attested Protocols</span></div>'
        f'<div class="cur-stat"><b class="cur-amber">{totals["grades_breakdown"]["DELTA_adverse_gaps"]}</b><span>Verified Adverse Gaps</span></div>'
        f'<div class="cur-stat"><b>0</b><span>Paid Grades · Pure Evidence</span></div>'
        f'</div></div>'
        f'<div class="tbl-wrap cur-tbl-wrap" id="curator-matrix"><table class="tbl cur-tbl">'
        f'<thead><tr><th scope="col">Curator / Allocator Stack</th><th scope="col">Direct Wrapper Vaults</th>'
        f'<th scope="col">Underlying Collateral Exposure</th><th scope="col" class="hide-m">Verified Control-Plane Takeaway</th>'
        f'<th scope="col" class="r">Action</th></tr></thead>'
        f'<tbody>{"".join(tbl_rows)}</tbody></table></div>'
        f'</div></section>'
    )

    detail_sec = (
        f'<section class="sec" id="curator-stacks"><div class="wrap">'
        f'<div class="sec-head"><h2>Curator-by-curator wrapper vs. collateral breakdown</h2>'
        f'<p class="aside">Neutral/emerald pills denote Aligned or Protective records; amber pills strictly denote Docs differ: a documented parameter that differs from the one observed on chain.</p></div>'
        f'<div class="cur-stack-list">{"".join(cards_html)}</div>'
        f'</div></section>'
    )

    watch_sec = f'<section class="sec" style="padding-top:0"><div class="wrap">{watch_pilot_box("../", heading="Watch Curated Vaults & Underlying Collateral Free (30-Day Pilot)", id_attr="watch-pilot")}</div></section>'

    seal_banner = (
        f'<section class="sec" id="curator-seal"><div class="wrap">'
        f'<div class="cur-seal-box">'
        f'<div><span class="step-k mono">FOR VAULT CURATORS, RISK ADVISORS &amp; PROTOCOL TEAMS</span>'
        f'<h2>Wholesale Curator Sweeps &amp; Free 7-Day Fix Re-Verification</h2>'
        f'<p class="s">{E(EDITORIAL_FIREWALL)} {E(SEAL_GUARANTEE)} Commission a vault sweep at $150 per protocol for 20 or more protocols (undelivered targets never charged), fund a Verification Pool ($50 minimum pool, $25 fixed verification fee; opening soon, reservation or invoice only), or submit a merged docs fix for <a href="../seal/">free 7-day re-verification</a>.</p></div>'
        f'<div class="cur-seal-actions">'
        + U.button("Fund a Pool", href="../bounties/#sponsor-pool", variant="default", size="lg", attrs='data-cta="curators_btm_pool"')
        + U.button("Wholesale Sweep", href="../request/?tier=wholesale-150", variant="outline", size="lg", attrs='data-cta="curators_wholesale"')
        + '</div></div></div></section>'
    )

    body = f"""<body>
{topbar("../", "curators/")}
<main id="main">
{hero}
{watch_sec}
{detail_sec}
{seal_banner}
</main>
{footer(count_line, reg, "../")}
</body></html>
"""
    title = "DeFi Vault Curator & Collateral Exposure Matrix · Pacta"
    desc = ("Clinical control-plane comparison of Steakhouse, Gauntlet, Re7, MEV Capital, Veda, Upshift & institutional DeFi vault wrappers vs. underlying collateral markets.")
    return head(title, desc, f"{BASE_URL}/curators/", prefix="../",
                og_title="Wrapper vaults vs. underlying collateral: who can change the contracts behind your positions") + "\n" + body


def build_all():
    idx, radar = load()
    today = site_date(idx, radar, load_pinned(), load_onboarding())     # deterministic (Codex F3): no wall-clock date

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
    mcp_skill_p = os.path.join(ROOT, "packages", "mcp-server", "SKILL.md")
    if os.path.isdir(os.path.dirname(mcp_skill_p)):
        with open(mcp_skill_p, "w", encoding="utf-8") as fh_sk:
            fh_sk.write(open(os.path.join(DOCS, "SKILL.md"), encoding="utf-8").read())
    llms_text = llms(idx, radar)
    w("llms.txt", llms_text)
    w("llms/index.html", llms_html(idx, llms_text))
    sp = site_protocols(idx, pinned)
    LK.write_all(ROOT, DOCS, sp, onb, radar, BRIEF_PROTOCOL)   # api/v1/lookup.json + packages/mcp-server/src/lookup.mjs catalog
    w("scan/index.html", scan_page(idx))
    w("seal/index.html", seal_page(idx))
    w("webhook/index.html", watch_page(idx))      # free: the 30-day pilot + the RSS / Atom feed; automated paid delivery is not active
    for sku_ in CHECKOUT:                          # only live SKUs get a page (none in this build)
        if CHECKOUT[sku_].get("live", True):
            w(f"{CHECKOUT[sku_]['route']}/index.html", product_page(idx, sku_))
    w("miniapp/index.html", miniapp_page(idx))
    w(".well-known/farcaster.json", farcaster_manifest_json())
    ads_src = os.path.join(ROOT, "tools", "ads")
    if os.path.isdir(ads_src):
        ads_dst = os.path.join(DOCS, "assets", "ads")
        os.makedirs(ads_dst, exist_ok=True)
        for ad_f in sorted(os.listdir(ads_src)):
            if ad_f.endswith(".png"):
                with open(os.path.join(ads_src, ad_f), "rb") as f_in, open(os.path.join(ads_dst, ad_f), "wb") as f_out:
                    f_out.write(f_in.read())
    picons_src = os.path.join(ROOT, "tools", "protocol_icons")
    picons_dst = os.path.join(DOCS, "assets", "protocols")
    os.makedirs(picons_dst, exist_ok=True)
    if os.path.isdir(picons_src):
        for pf_ in sorted(os.listdir(picons_src)):
            if pf_.endswith((".webp", ".png", ".svg")):
                with open(os.path.join(picons_src, pf_), "rb") as f_in, open(os.path.join(picons_dst, pf_), "wb") as f_out:
                    f_out.write(f_in.read())
    for p_name, p_v in sp.items():
        p_slug = p_v["slug"]
        if not any(os.path.exists(os.path.join(picons_dst, f"{p_slug}.{ext}")) for ext in ("webp", "png", "svg")):
            with open(os.path.join(picons_dst, f"{p_slug}.svg"), "w", encoding="utf-8") as f_svg:
                f_svg.write(proto_monogram_svg(p_slug, p_name))
    GM.write(ROOT, DOCS)                          # api/v1/graph-manifest.json: durable protocol graph (from protocols/index/rpc-pinned.json)
    digest = load_forum_digest()                  # data/forum-digest.json (optional; missing = empty digest)
    w("api/v1/forum-digest.json", forum_digest_json(idx, digest, pinned))
    for name, v in sp.items():
        w(f"protocols/{v['slug']}/index.html", protocol_page(name, v["entries"], idx, radar, digest, v["slug"]))
    w("protocols/index.html", protocols_index_page(idx, sp))
    w("integrations/vault-factories/index.html", vault_factories_page(idx, sp))
    claims = load_wave2_claims()
    claims3 = load_wave3_claims()
    w("bounties/index.html", bounties_page(idx, radar, claims=claims, claims3=claims3))
    lb = load_leaderboard()
    w("leaderboard/index.html", leaderboard_page(idx, lb, claims, claims3))
    w("mcp/index.html", mcp_page(idx))
    w("for-protocols/index.html", for_protocols_page(idx))
    write_hunter_badges(hunter_stats(lb, claims, claims3))
    write_wave2_master_issue(idx)
    write_wave3_master_issue(idx)
    w("404.html", not_found_page(idx, sp))       # GitHub Pages serves it for any missing path
    w("scorecards/index.html", scorecards_page(idx))
    w("curators/index.html", curators_page(idx))
    w("radar/index.html", radar_page(idx, radar))
    w("about/index.html", about_page(idx))
    w("methodology/index.html", methodology_page(idx))
    w("privacy/index.html", privacy_page(idx))
    w("terms/index.html", terms_page(idx))
    w("pricing/index.html", pricing_redirect_page())   # T5: /pricing -> /#pricing
    w("robots.txt", ROBOTS_TXT)
    w("404-rescue.js", RESCUE_JS)                 # 404.html: stripped-"?" rescue (same origin, before b.js)
    w("theme.js", THEME_JS)                       # theme bootstrap (render-blocking, same origin): no inline JS anywhere
    w("app.js", minify_js(open(APP_SRC, encoding="utf-8").read()))   # readable source: tools/app.src.js
    sc_cards = scorecards(idx, pinned, sp)
    w("api/v1/scorecards.json", scorecards_json(sc_cards))
    w("api/v1/wallet-tokens.json", wallet_tokens_json(sc_cards, lookup_items()))
    w("api/v1/curator-exposure-matrix.json", open(os.path.join(ROOT, "data", "curator-exposure-matrix.json"), encoding="utf-8").read())
    # root discovery copies (byte-identical): agents that probe /agent.json, /mcp.json or /openapi.json get the canonical files
    for root_name, src_rel in (("agent.json", ".well-known/agent.json"), ("mcp.json", ".well-known/mcp.json"), ("openapi.json", "api/v1/openapi.json")):
        w(root_name, open(os.path.join(DOCS, src_rel), encoding="utf-8").read())
    w("feed.xml", atom_feed(idx, radar))
    w("api/v1/feed.json", json_feed(idx, radar))
    urls = ["/", "/request/", "/scan/", "/webhook/", "/seal/", "/miniapp/", "/curators/", "/.well-known/farcaster.json", "/llms.txt", "/api/v1/index.json", "/api/v1/radar.json"] + [f"/briefs/{k}/" for k in BRIEFS] + \
        [f"/briefs/{b['slug']}/" for b in load_onboarding()["briefs"]] + (["/api/v1/onboarding.json"] if load_onboarding()["briefs"] else []) + \
        ["/api/v1/proposals.json", "/api/v1/rpc-pinned.json", "/api/v1/lookup.json", "/api/v1/protocols.json", "/api/v1/graph-manifest.json", "/api/v1/wallet-tokens.json", "/api/v1/curator-exposure-matrix.json", "/integrations/vault-factories/", "/for-protocols/", "/llms/", "/llms-full.txt", "/SKILL.md", "/.well-known/agent.json", "/.well-known/mcp.json",
         "/demos/swapio-x402/", "/bounties/", "/leaderboard/", "/mcp/", "/protocols/", "/feed.xml", "/api/v1/feed.json",
         "/scorecards/", "/radar/", "/about/", "/methodology/", "/privacy/", "/terms/"] + [f"/protocols/{v['slug']}/" for v in sp.values()]
    w("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
      + "".join(f"  <url><loc>{BASE_URL}{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    w(".well-known/security.txt", f"Contact: mailto:{CONTACT}\nExpires: 2027-11-13T00:00:00.000Z\nPreferred-Languages: en\n"
      f"Canonical: {BASE_URL}/.well-known/security.txt\nPolicy: {BASE_URL}/for-protocols/#faq\n")
    w(".nojekyll", "")    # GitHub Pages: serve dot-directories such as /.well-known/
    c = counts(idx)
    print(f"built: {c['sprints']} sprints, {c['records']} records; radar block {radar['refreshed_at']['block_number']}; base {BASE_URL}")


STAGING_ROBOTS = "noindex, nofollow"
STAGING_MARK = ".pacta-staging"
SKIP_LINK = '<a class="skip" href="#main">Skip to content</a>'


STAGING_BANNER_STYLE = ("position:relative;z-index:2;padding:4px 16px;font:12px/1.5 system-ui,sans-serif;background:#15181d;color:#9aa0aa;"
                        "text-align:center;border-bottom:1px solid #23262c")


def staging_banner(base_path, styled=False):
    """N2 (v4.3): one subtle line at the top of every staging page (never on the canonical build) saying why the copy is noindex.
    styled=True (v4.5): pages without the site stylesheet (the hand-written demo) get the same look inline."""
    st = f' style="{STAGING_BANNER_STYLE}"' if styled else ""
    return (f'<div class="staging-banner" role="note" data-staging-banner{st}>Staging preview ({E(base_path or "")}/) · robots=noindex on this '
            f'test route; production pacta.wtf ships index, follow.</div>')
BASE_PATH_RE = re.compile(r"(?:/(?!\.{1,2}(?:/|$))[A-Za-z0-9._-]+)+")


def valid_base_path(bp):
    """A mount prefix such as /website-test or /a/release.v4: one or more segments, never a standalone "." or ".." segment
    (/.., /. and /website-test/../../evil would normalise outside the mount)."""
    return bool(BASE_PATH_RE.fullmatch(bp or ""))


def staging_target(out_dir, root=None, docs=None):
    """(resolved out_dir, problem or None). Symlinks are resolved first (os.path.realpath on out_dir, the repository root and
    docs/), so an alias can never make a staging build delete or overwrite the repository; a staging target may not equal, sit
    inside, or contain the repository root or docs/. Nothing is read or deleted before this check passes."""
    out = os.path.realpath(out_dir)
    for name, p in (("the repository root", os.path.realpath(root or ROOT)), ("docs/", os.path.realpath(docs or DOCS))):
        if out == p or out.startswith(p + os.sep) or p.startswith(out + os.sep):
            return out, f"--out-dir resolves to {out}, which is {name} or inside / above it"
    return out, None


def stage_site(out_dir, base_path):
    """--base-path / --out-dir (v4.2): turn a finished build in out_dir into a staging copy for a sub-path mount such as
    /website-test on a staging host. Page links and assets are relative, so they already work under any prefix; this
    prefixes the root-relative ones (404.html), records the mount on <html data-base-path> for app.js, marks every page
    noindex, nofollow, drops the first-party beacon (staging visits never reach production telemetry), adds the one-line staging
    banner after the skip link (N2) and disallows crawling. Canonical URLs keep pointing at pacta.wtf."""
    for root, _, files in os.walk(out_dir):
        for f in sorted(files):
            if not f.endswith(".html"):
                continue
            p = os.path.join(root, f)
            t = open(p, encoding="utf-8").read()
            if base_path:
                t = re.sub(r'((?:href|src|action)=")/(?!/)', lambda m: m.group(1) + base_path + "/", t)
                t = t.replace('<html lang="en">', f'<html lang="en" data-base-path="{base_path}">', 1)
            t, n = re.subn(r'<meta name="robots" content="[^"]*">', f'<meta name="robots" content="{STAGING_ROBOTS}">', t)
            if not n:
                t = t.replace('<meta charset="utf-8">', f'<meta charset="utf-8">\n<meta name="robots" content="{STAGING_ROBOTS}">', 1)
            t = re.sub(r'<script src="[^"]*b\.js" defer></script>\n?', "", t)
            styled = "styles.css" not in t   # a page without the site stylesheet carries the banner's look inline
            if SKIP_LINK in t:
                t = t.replace(SKIP_LINK, SKIP_LINK + "\n" + staging_banner(base_path, styled), 1)
            else:
                t = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + staging_banner(base_path, styled), t, count=1)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(t)
    with open(os.path.join(out_dir, "robots.txt"), "w") as fh:
        fh.write("User-agent: *\nDisallow: /\n")


def main(argv=None):
    """Default: the canonical pacta.wtf site in docs/. --base-path / --out-dir: a noindex staging copy (e.g.
    python3 tools/build_site.py --base-path /website-test --out-dir /var/www/website-test); docs/ is never touched."""
    import argparse
    import shutil
    ap = argparse.ArgumentParser(description="Build the Pacta static site")
    ap.add_argument("--base-path", default="", help="URL prefix the site is mounted under, e.g. /website-test (default: none)")
    ap.add_argument("--out-dir", default=None, help="output directory (default: docs/); any other directory gets a staging build")
    a = ap.parse_args(argv)
    global DOCS
    canon = os.path.realpath(DOCS)
    bp = a.base_path.rstrip("/")
    if bp and not valid_base_path(bp):
        ap.error("--base-path must look like /website-test (no '.' or '..' segments)")
    if not a.out_dir or os.path.realpath(a.out_dir) == canon:
        if bp:
            ap.error("--base-path needs --out-dir: the canonical docs/ build always has no base path")
        build_all()
        return
    out, problem = staging_target(a.out_dir)
    if problem:
        ap.error(problem + "; a staging build must live outside the repository")
    if os.path.isdir(out) and os.listdir(out) and not os.path.exists(os.path.join(out, STAGING_MARK)):
        ap.error(f"{out} is not empty and is not a previous staging build ({STAGING_MARK} missing); refusing to overwrite")
    if os.path.isdir(out):
        shutil.rmtree(out)
    shutil.copytree(canon, out)
    try:
        DOCS = out
        build_all()
    finally:
        DOCS = canon
    stage_site(out, bp)
    with open(os.path.join(out, STAGING_MARK), "w") as fh:
        fh.write(f"pacta staging build; base path {bp or '/'}; canonical pages are noindex here\n")
    print(f"staged: {out} (base path {bp or '/'}, noindex)")


if __name__ == "__main__":
    main()
