"""Agent-first (B2A) machine feeds, generated deterministically from docs/api/v1/{index,radar,onboarding}.json.

Writes (called from tools/build_site.py; never hand-edited):
  docs/api/v1/proposals.json      schema pacta.governance_proposals_feed.v1: live Aave / Euler / Morpho / Sky governance
                                  proposals mapped to block-pinned control-plane observations
  docs/llms-full.txt              single-file reference corpus for LLM, coding and DeFi agents
  docs/.well-known/agent.json     A2A Agent Card (skills, feeds, Base EAS anchor, x402 payment descriptor)
  docs/.well-known/mcp.json       MCP discovery manifest for @pacta/mcp-server (io.github.fractal-neurons/pacta)
  docs/SKILL.md                   portable agent skill (YAML frontmatter)

Determinism: no wall-clock input. Every timestamp is taken from the source feeds, every list is sorted by a stable key,
and JSON is written with sorted keys, so rebuilding from unchanged data is byte-identical (checked by verify_site_v2.py).
"""

import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import onboarding_render as OR  # noqa: E402

BASE = "https://pacta.wtf"
REGISTRY = "0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872"
EAS_SCHEMA = "0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83"
PAY_TO = "0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09"            # attester EOA pacta.base.eth, owner-approved x402 payTo
TREASURY = "0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14"          # Pacta Treasury (an EOA; never call it a Safe)
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
X402_URL = "https://pacta-x402.pacta.workers.dev"              # canonical live x402 edge Worker (Cloudflare; owner-deployed)
X402_FREE = ["/health", "/.well-known/x402", "/v1/sample/control-plane"]
X402_NETWORK_V2 = "eip155:8453"                                  # CAIP-2 Base mainnet (x402 v2); v1 uses "base"
X402_MAX_TIMEOUT_S = 60                                          # live Worker MAX_TIMEOUT_S (v1 and v2 requirements)
JSON_SCHEMA_2020_12 = "https://json-schema.org/draft/2020-12/schema"
# Live Worker wire contract (pacta-core packages/x402-edge-worker/worker.mjs): both protocol versions on every paid route.
X402_WIRE = {
    "v1": {"x402Version": 1, "network": "base", "amountField": "maxAmountRequired", "challenge": "402 JSON body",
           "paymentHeader": "X-PAYMENT", "receiptHeader": "X-PAYMENT-RESPONSE"},
    "v2": {"x402Version": 2, "network": X402_NETWORK_V2, "amountField": "amount", "challenge": "PAYMENT-REQUIRED header (base64 JSON)",
           "paymentHeader": "PAYMENT-SIGNATURE", "receiptHeader": "PAYMENT-RESPONSE", "bazaarSchema": JSON_SCHEMA_2020_12},
}
X402_BARE_PROBE = ("A bare GET (no query) or zero-byte POST with no payment header on any paid URL returns HTTP 402 at once: the v1 JSON body "
                   "(x402Version 1, network base, maxAmountRequired) plus the v2 PAYMENT-REQUIRED header (x402Version 2, network eip155:8453, "
                   "amount, extensions.bazaar with a JSON Schema draft 2020-12 schema).")
X402_RECEIPT_NOTE = ("A settled call returns 200 with both PAYMENT-RESPONSE and X-PAYMENT-RESPONSE (base64 {success, transaction, network, payer}). "
                     "That receipt is the facilitator's settlement assertion bound to the payer; the MCP client checks it against the signed "
                     "authorization but does not look the transaction up on Base (onchainReceiptVerified: false).")
MCP_NAME = "io.github.fractal-neurons/pacta"
MCP_PACKAGE = "@pacta/mcp-server"
MCP_VERSION = "0.1.0"                                            # @pacta/mcp-server package.json version (SKILL.md is shipped in it)
MCP_ENV = [("PACTA_INDEX_PATH", "Local snapshot of /api/v1/index.json (offline use)"),
           ("PACTA_PROPOSALS_PATH", "Local snapshot of /api/v1/proposals.json"),
           ("PACTA_SPEC_PATH", "Local spec JSON (anchoring overrides, local index fallback)"),
           ("PACTA_X402_URL", f"Enables paid x402 tools against this gateway URL; the live gateway is {X402_URL} (unset: free tools only)"),
           ("PACTA_X402_MAX_ATOMIC", "Per-call USDC cap in atomic units (default 1000000 = $1.00; hard ceiling 5000000)"),
           ("PACTA_X402_TIMEOUT_MS", "Timeout per outbound request in ms (default 8000)")]
FORUM_HOST = {"aave": "governance.aave.com", "euler": "forum.euler.finance", "morpho": "forum.morpho.org", "sky": "forum.skyeco.com"}
FORUM_OF = {"Aave governance": "aave", "Euler forum": "euler"}
CHAIN = {"eth": ("ethereum", 1), "base": ("base", 8453)}
PREDICATES = ("AdminUpgradePredicate", "OracleGovernanceSwapPredicate", "PausePrivilegeEscalationPredicate", "CapSupplyViolationPredicate")

# Live governance threads cross-referenced to verified index records. Title / URL are forum metadata; every chain value
# comes from the referenced index records. `relation` says how the thread relates to the record (never overstated).
CROSS_REF = [
    {"forum": "aave", "topic_id": 25721, "title": "[ARFC] Onboard syrupUSDC to Aave V4 on Arc",
     "forum_url": "https://governance.aave.com/t/arfc-onboard-syrupusdc-to-aave-v4-on-arc/25721",
     "records": ["maple-v2-syrup-ppm-admin"], "relation": "issuer_control_plane: the proposed collateral's issuer permission layer"},
    {"forum": "aave", "topic_id": 26304, "title": "[Direct-to-AIP] Ethena E-Mode Consolidation on Aave V3",
     "forum_url": "https://governance.aave.com/t/direct-to-aip-ethena-e-mode-consolidation-on-aave-v3/26304",
     "records": ["ethena-admin-timelock-and-dev-safe"], "relation": "issuer_control_plane: Ethena admin timelock and operating Safe"},
    {"forum": "aave", "topic_id": 25902, "title": "[Direct-To-AIP] Onboard PT-sUSDe-28JAN2027 to Aave V3 Plasma Instance",
     "forum_url": "https://governance.aave.com/t/direct-to-aip-onboard-pt-susde-28jan2027-to-aave-v3-plasma-instance/25902",
     "records": ["ethena-minting-rlusd-usat-onboarding-ops"], "relation": "issuer_control_plane: queued Ethena minting-collateral changes underlying sUSDe"},
    {"forum": "morpho", "topic_id": 2301, "title": "[RFC] A User-centric DeFi Collateral Transparency Framework - Phase 1",
     "forum_url": "https://forum.morpho.org/t/rfc-a-user-centric-defi-collateral-transparency-framework-phase-1/2301",
     "records": ["morpho-blue-singleton-owner", "metamorpho-re7-weth-guardian-parity"],
     "relation": "framework_reference: block-pinned Morpho Blue and MetaMorpho control-plane observations the framework discusses"},
    {"forum": "sky", "topic_id": 28390, "title": "[November 19, 2026] Proposed Changes to Spark for Upcoming Spell",
     "forum_url": "https://forum.skyeco.com/t/november-19-2026-proposed-changes-to-spark-for-upcoming-spell/28390",
     "records": ["spark-sky-gsm-pause-delay"], "relation": "governance_path: the GSM pause delay every Spark spell passes through"},
]


def plain(htm):
    t = re.sub(r"<button[^>]*>.*?</button>", "", htm)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"\s+", " ", t).strip()
    return t


def predicates_for(text):
    """Which PactaSentinelTripwire predicate modules can watch this surface (keyword rules on observed text; stable order)."""
    t = text.lower()
    out = []
    if re.search(r"timelock|getmindelay|delay\(|proxyadmin|eip-1967|implementation|admin\(\)|upgrade|threshold|safe|multisig|quorum", t):
        out.append(PREDICATES[0])
    if re.search(r"oracle|router|governor|price feed|getquote|rate provider", t):
        out.append(PREDICATES[1])
    if re.search(r"pause|role|minter|blacklist|guardian|owner\(\)|authority|capabilit", t):
        out.append(PREDICATES[2])
    if re.search(r"supply|cap\b|caps|mint|reserve|totalsupply|ltv|exchange rate", t):
        out.append(PREDICATES[3])
    return out or [PREDICATES[0]]


def index_cast(e):
    rpc = '--rpc-url "$ETH_RPC_URL"'
    if e["check_type"] == "eth_getStorageAt":
        first = f'cast storage {e["target_contract"]} {e["selector_or_slot"]} --block {e["block_number"]} {rpc}'
    else:
        args = " ".join(e.get("call_args") or [])
        first = f'cast call {e["target_contract"]} "{e.get("call_signature") or e["selector_or_slot"]}"{" " + args if args else ""} --block {e["block_number"]} {rpc}'
    return [first, f'cast block {e["block_number"]} --field hash {rpc}  # expect {e["block_hash"]}']


def proposals(idx, onb):
    byid = {e["id"]: e for e in idx["entries"]}
    out = []
    for b in onb["briefs"]:
        forum = FORUM_OF[b["forum"]["name"]]
        chain, cid = CHAIN[b["chain"]]
        text = " ".join(plain(x) for x in OR.findings(b))
        out.append({"proposal_id": f'{forum}-{b["forum"]["topic"]}', "forum": forum, "topic_id": b["forum"]["topic"], "title": b["forum"]["title"],
                    "forum_url": b["forum"]["url"], "relation": "direct_target: the asset or market this proposal asks to onboard",
                    "chain": chain, "chain_id": cid, "pinned_block_number": b["pin"]["number"], "pinned_block_hash": b["pin"]["hash"],
                    "source_feed": "/api/v1/onboarding.json", "source_record_ids": [b["slug"]], "brief_url": f'{BASE}/briefs/{b["slug"]}/',
                    "control_plane_summary": [plain(x) for x in OR.findings(b)],
                    "recommended_sentinel_predicates": predicates_for(text + " " + " ".join(c["label"] for c in b["checks"])),
                    "repro_commands": [f'cast block {b["pin"]["number"]} --field hash --rpc-url "{OR.RPC_ENV[b["chain"]]}"  # expect {b["pin"]["hash"]}']
                                      + [OR.cast_line(b, c) for c in b["checks"]]})
    briefs_by_record = {"ethena-minting-rlusd-usat-onboarding-ops": f"{BASE}/briefs/ethena-ops-0x0ca0-0x1fe5/"}
    for x in CROSS_REF:
        recs = [byid[r] for r in x["records"]]                         # KeyError = a mapping points at a missing record
        pin = max(recs, key=lambda e: e["block_number"])
        summ = [f'{e["protocol"]} — {e["surface"]} [{e["classification"]}, Sprint {e["sprint"]}, block {e["block_number"]}]: {e["onchain_observed"]} '
                f'Documented: {e["documented_reference"]}' for e in recs]
        out.append({"proposal_id": f'{x["forum"]}-{x["topic_id"]}', "forum": x["forum"], "topic_id": x["topic_id"], "title": x["title"],
                    "forum_url": x["forum_url"], "relation": x["relation"], "chain": "ethereum", "chain_id": 1,
                    "pinned_block_number": pin["block_number"], "pinned_block_hash": pin["block_hash"], "source_feed": "/api/v1/index.json",
                    "source_record_ids": x["records"], "brief_url": next((briefs_by_record[r] for r in x["records"] if r in briefs_by_record), None),
                    "record_urls": [f'{BASE}/#r-{r}' for r in x["records"]],
                    "control_plane_summary": summ,
                    "recommended_sentinel_predicates": predicates_for(" ".join(e["onchain_observed"] + " " + e["surface"] for e in recs)),
                    "repro_commands": [c for e in recs for c in index_cast(e)]})
    out.sort(key=lambda p: (p["forum"], p["topic_id"]))
    by_forum = {f: sum(1 for p in out if p["forum"] == f) for f in sorted(FORUM_HOST)}
    return {"schema": "pacta.governance_proposals_feed.v1", "generated_at": max(idx["generated_at"], onb["generated_at"]),
            "generated_by": "tools/build_b2a_feeds.py", "generated_from": ["/api/v1/onboarding.json", "/api/v1/index.json"],
            "note": "Observed on-chain state at the pinned block for each governance thread. Read-only; Pacta never posts on these forums.",
            "counts": {"total": len(out), "by_forum": by_forum}, "proposals": out}


FEEDS = [("/api/v1/index.json", "Block-pinned control-plane index (every record: target, call, block, block hash, classification, Base EAS UID)"),
         ("/api/v1/onboarding.json", "Onboarding verification scans: every check with call, calldata, raw result, decoded value; role maps"),
         ("/api/v1/proposals.json", "Live governance proposals (Aave, Euler, Morpho, Sky) mapped to block-pinned observations"),
         ("/api/v1/radar.json", "Queued timelock operations with on-chain ETAs at a finalized block"),
         ("/llms.txt", "Short index for language models"), ("/llms-full.txt", "This file: the complete agent reference"),
         ("/.well-known/agent.json", "A2A Agent Card"), ("/.well-known/mcp.json", "MCP discovery manifest"), ("/SKILL.md", "Portable agent skill")]
MCP_TOOLS = [("pacta_list_commitments", "free", "Filter indexed records (protocol, classification, sprint, limit)"),
             ("pacta_get_anchoring", "free", "Base EAS anchoring: PactaCommitmentRegistry, schema, sprint attestation UIDs"),
             ("pacta_list_proposals", "free", "Governance proposals feed (forum, topic_id, chain, limit, include_repro)"),
             ("pacta_x402_discover", "free", "x402 gateway status and discovery manifest (only when PACTA_X402_URL is set)"),
             ("pacta_scan_control_plane", "x402 $0.10", "Live control-plane scan of a contract (chain, address)"),
             ("pacta_scan_timelock_op", "x402 $0.25", "Live TimelockController operation state (timelock, opId)"),
             ("pacta_live_timelocks", "x402 $0.10", "Live state of tracked queued timelock operations"),
             ("pacta_scan_proposal_diff", "x402 $0.15", "Re-run a tracked governance proposal's pinned reads live, pinned-vs-live diffs (forum, topicId)")]
X402_ROUTES = [("/v1/scan/control-plane?chain=ethereum|base&address=0x…", "100000", "$0.10"),
               ("/v1/scan/timelock-op?chain=ethereum|base&timelock=0x…&opId=0x…", "250000", "$0.25"),
               ("/v1/scan/proposal-diff?forum=aave|euler|morpho|sky&topicId=<id>", "150000", "$0.15"),
               ("/v1/briefs/live-timelocks", "100000", "$0.10")]
SENTINEL = ("PactaSentinelTripwire.sol: an ownerless, immutable contract granted Morpho Vault V2 isSentinel. Vault owners register rules "
            "(predicate module + config, cap id, adapter, liquidity reader). trigger(ruleId) is permissionless but re-checks the broken invariant "
            "on-chain in the same transaction, then sets the absolute cap to 0 (committed even if deallocate or the EAS receipt revert), "
            "deallocates min(allocation, liquid assets), and sweepRemaining(ruleId) drains the rest as liquidity returns. Zero custody. "
            "Predicates: " + ", ".join(PREDICATES) + ". Status: built and tested (Foundry, 107 tests incl. invariants and fork tests); "
            "not audited, not deployed.")
MCP_STATUS = ("publication_pending: @pacta/mcp-server is not yet published to npm or the MCP registry; the install commands below apply "
              "once it is. Until then use the free HTTPS feeds directly.")


def llms_full(idx, radar, prop, onb):
    a, m = idx["onchain_anchoring"], idx["summary_metrics"]
    L = ["# Pacta — full agent reference (llms-full.txt)", "",
         "> Block-pinned DeFi control-plane observations for AI agents: who can change a protocol's rules (proxy admins, timelocks, "
         "Safe quorums, roles), what the docs say, and what is queued. All feeds are free, real-time and read-only; every value replays "
         "against any archive node with the given cast command.", "",
         f"Generated deterministically from the feeds below (data as of {max(idx['generated_at'], onb['generated_at'])}). "
         f"{m['sprints_completed']} sprints · {m['records_indexed']} indexed records · {len(radar['items'])} queued-operation groups · "
         f"{len(prop['proposals'])} governance proposals · {len(onb['briefs'])} onboarding briefs.", "",
         "## Feeds (all free, no key, no paywall)"] + [f"- {BASE}{p}: {d}" for p, d in FEEDS] + ["",
         "## How to verify any value",
         "1. Take the record's target, call signature and arguments, block number and block hash.",
         "2. Run the listed `cast call … --block N` (or eth_call with EIP-1898 {blockHash, requireCanonical: true}) on any archive node.",
         "3. Run `cast block N --field hash` and compare with the recorded block hash.", "",
         "## MCP server", f"- Name: {MCP_NAME} · package {MCP_PACKAGE} · transport stdio.", f"- Status: {MCP_STATUS}",
         f"- Install (after publication): `npx -y {MCP_PACKAGE}`; MCP client config: {{\"mcpServers\": {{\"pacta\": {{\"command\": \"npx\", \"args\": [\"-y\", \"{MCP_PACKAGE}\"]}}}}}}",
         "- Tools:"] + [f"  - {n} ({p}): {d}" for n, p, d in MCP_TOOLS] + [
         f"- Paid tools are disabled unless PACTA_X402_URL is set (opt-in: PACTA_X402_URL={X402_URL}); the client refuses any 402 challenge (v1 body or v2 "
         "PAYMENT-REQUIRED header) whose payTo, asset or network differ from the values below, or whose amount exceeds $1.00 by default. Pay with "
         "xPaymentHeader (x402 v1) or paymentSignatureHeader (x402 v2).", "",
         "## x402 micropayments (optional; only for live scans of unindexed contracts)",
         f"- Network: Base (chain id 8453) · scheme exact · asset USDC {USDC_BASE} · payTo {PAY_TO} (attester EOA, pacta.base.eth).",
         f"- Pacta Treasury: {TREASURY} (an externally owned account; the PactaCommitmentRegistry treasury slot).",
         f"- Live gateway: {X402_URL} (Cloudflare Worker; x402Versions [1, 2]; PayAI facilitator; maxTimeoutSeconds {X402_MAX_TIMEOUT_S}).",
         "- x402 v1: network base · amount field maxAmountRequired · challenge in the 402 JSON body · pay with X-PAYMENT · receipt X-PAYMENT-RESPONSE.",
         f"- x402 v2: network {X402_NETWORK_V2} · amount field amount · challenge in the PAYMENT-REQUIRED header (base64 JSON) · pay with PAYMENT-SIGNATURE · "
         f"receipt PAYMENT-RESPONSE · extensions.bazaar carries a JSON Schema draft 2020-12 schema ({JSON_SCHEMA_2020_12}).",
         f"- Bare probe: {X402_BARE_PROBE}",
         f"- Settlement: {X402_RECEIPT_NOTE}",
         "- Paid routes (GET query or POST JSON body with the same names):"] + [f"  - GET {X402_URL}{r}: {atomic} atomic USDC ({usd})" for r, atomic, usd in X402_ROUTES] + [
         "- Free: " + ", ".join(f"GET {X402_URL}{p}" for p in X402_FREE) + " (/.well-known/x402 is the Bazaar discovery manifest, discoverable: true).", "",
         "## On-chain anchoring (Base, chain id 8453)",
         f"- PactaCommitmentRegistry {REGISTRY} (Sourcify verified); attester pacta.base.eth {a['attester_eoa']}.",
         f"- EAS schema {EAS_SCHEMA}: uint16 sprintId, uint64 chainId, uint64 blockNumber, bytes32 blockHash, uint8 verifiedCount, uint8 driftCount, bytes32 summarySha256, string prURI.",
         ] + [f"- Sprint {k} attestation UID {v}" for k, v in sorted(a["sprint_eas_attestations"].items(), key=lambda kv: int(kv[0]))] + [
         "", "## Sentinel (Phase 2)", f"- {SENTINEL}", "",
         "## Governance proposals (from /api/v1/proposals.json)"]
    for p in prop["proposals"]:
        L += [f"### {p['proposal_id']}: {p['title']}", f"- {p['forum_url']} · {p['relation']}",
              f"- {p['chain']} block {p['pinned_block_number']} ({p['pinned_block_hash']}) · source {p['source_feed']} {', '.join(p['source_record_ids'])}"
              + (f" · brief {p['brief_url']}" if p["brief_url"] else ""),
              f"- Sentinel predicates: {', '.join(p['recommended_sentinel_predicates'])}"] + [f"- {s}" for s in p["control_plane_summary"]] + [""]
    L += ["## Queued timelock operations (from /api/v1/radar.json)",
          f"Refreshed at finalized block {radar['refreshed_at']['block_number']} ({radar['refreshed_at']['block_time_utc']})."]
    for it in radar["items"]:
        ops = "; ".join(f"{o['op_id']} pending={str(o['pending']).lower()} eta={o['eta']}" for o in it["operations"])
        L.append(f"- {it['protocol']}: {it['title']} · timelock {it['timelock']} ({it['min_delay_seconds']}s) · {ops}")
    L += ["", "## Indexed records (from /api/v1/index.json)"]
    for e in sorted(idx["entries"], key=lambda e: (-e["sprint"], e["id"])):
        L.append(f"- {e['id']} [{e['classification']}] {e['protocol']} — {e['surface']} · Sprint {e['sprint']} · block {e['block_number']} "
                 f"({e['block_hash']}) · target {e['target_contract']} · {e['onchain_observed']}")
    L += ["", "## Scope",
          "- Observations of on-chain state at the stated blocks; not code audits, reserve attestations or investment advice.",
          "- Exploit-sensitive vulnerabilities are never published here; they go through Immunefi or Cantina bounty programmes.",
          "- Pacta reads governance forums and never posts on them.", ""]
    return "\n".join(L)


def agent_card(prop, onb, idx):
    return {
        "protocolVersion": "0.3.0",
        "name": "Pacta",
        "description": ("Block-pinned DeFi control-plane intelligence for agents: proxy admins, timelocks, Safe quorums and roles behind "
                        "collateral, compared with documentation and live governance proposals. Free static JSON feeds; optional x402 "
                        "pay-per-call live scans on Base."),
        "url": f"{BASE}/",
        "version": max(idx["generated_at"], onb["generated_at"])[:10].replace("-", "."),
        "provider": {"organization": "Fractal Neurons", "url": "https://fractalneurons.com"},
        "documentationUrl": f"{BASE}/llms-full.txt",
        "iconUrl": f"{BASE}/favicon.png",
        "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": False},
        "defaultInputModes": ["application/json", "text/plain"],
        "defaultOutputModes": ["application/json", "text/markdown"],
        "authentication": {"schemes": ["none"], "notes": "Static feeds need no auth. Paid live scans use x402 instead of accounts or keys: v1 (HTTP 402 + X-PAYMENT) or v2 (PAYMENT-REQUIRED + PAYMENT-SIGNATURE)."},
        "skills": [
            {"id": "control-plane-lookup", "name": "Control-plane lookup",
             "description": "Who can upgrade, pause, mint or change delays for a DeFi protocol, at a canonical block, with a cast reproduction.",
             "tags": ["defi", "governance", "timelock", "proxy-admin", "risk"], "inputModes": ["application/json"], "outputModes": ["application/json"],
             "examples": ["Which address can upgrade Ethena's minting contract and with what delay?", f"Fetch {BASE}/api/v1/index.json and list parameter deltas."]},
            {"id": "collateral-diligence", "name": "Collateral onboarding diligence",
             "description": "For a live Aave / Euler / Morpho / Sky onboarding proposal, return the block-pinned control-plane observations and Sentinel predicates.",
             "tags": ["curator", "collateral", "aave", "euler", "morpho", "sky"], "inputModes": ["application/json"], "outputModes": ["application/json"],
             "examples": [f"Fetch {BASE}/api/v1/proposals.json and summarise {p['proposal_id']}." for p in prop["proposals"][:2]]},
            {"id": "timelock-radar", "name": "Queued timelock radar",
             "description": "Pending timelock operations and their on-chain ETAs.", "tags": ["timelock", "monitoring"],
             "inputModes": ["application/json"], "outputModes": ["application/json"], "examples": [f"Fetch {BASE}/api/v1/radar.json."]},
            {"id": "verify-onchain", "name": "Reproduce a value",
             "description": "Replay any record with eth_call / cast at its pinned block and compare the canonical block hash.",
             "tags": ["verification", "eip-1898", "coding-agent"], "inputModes": ["text/plain"], "outputModes": ["text/plain"],
             "examples": ["cast call <target> \"getMinDelay()\" --block <N> --rpc-url $ETH_RPC_URL"]},
        ],
        "endpoints": {"feeds": {p: f"{BASE}{p}" for p, _ in FEEDS}, "mcp_manifest": f"{BASE}/.well-known/mcp.json", "skill": f"{BASE}/SKILL.md",
                      "x402_gateway": X402_URL},
        "x402": {"x402Version": 1, "x402Versions": [1, 2], "scheme": "exact", "network": "base", "networks": ["base", X402_NETWORK_V2],
                 "chainId": 8453, "asset": USDC_BASE, "payTo": PAY_TO, "maxTimeoutSeconds": X402_MAX_TIMEOUT_S,
                 "status": "live", "gatewayUrl": X402_URL, "discovery": f"{X402_URL}/.well-known/x402", "wire": X402_WIRE,
                 "bareProbe": X402_BARE_PROBE, "settlement": {"receiptHeaders": ["PAYMENT-RESPONSE", "X-PAYMENT-RESPONSE"],
                                                              "onchainReceiptVerified": False, "note": X402_RECEIPT_NOTE},
                 "free": [f"{X402_URL}{p}" for p in X402_FREE],
                 "routes": [{"path": r.split("?")[0], "url": X402_URL + r.split("?")[0], "methods": ["GET", "POST"],
                             "query": (r.split("?")[1] if "?" in r else ""), "maxAmountRequired": atomic, "amount": atomic, "priceUsd": usd}
                            for r, atomic, usd in X402_ROUTES]},
        "anchoring": {"chainId": 8453, "registry": REGISTRY, "easSchema": EAS_SCHEMA, "attester": idx["onchain_anchoring"]["attester_eoa"],
                      "treasury": {"address": TREASURY, "label": "Pacta Treasury", "kind": "externally owned account"}},
    }


def mcp_manifest(idx, onb):
    return {
        "name": MCP_NAME, "title": "Pacta", "package": MCP_PACKAGE,
        "description": "Block-pinned DeFi control-plane commitments, Base EAS attestations and governance proposals for agents.",
        "version": max(idx["generated_at"], onb["generated_at"])[:10].replace("-", "."), "homepage": f"{BASE}/", "documentation": f"{BASE}/llms-full.txt",
        "status": MCP_STATUS,
        "transport": {"type": "stdio", "command": "npx", "args": ["-y", MCP_PACKAGE]},
        "environment": [{"name": n, "required": False, "secret": False, "description": d} for n, d in MCP_ENV],
        "tools": [{"name": n, "access": "free" if p == "free" else "x402", "price": None if p == "free" else p.split(" ")[1], "description": d} for n, p, d in MCP_TOOLS],
        "feeds": {p: f"{BASE}{p}" for p, _ in FEEDS},
        "verification": {"chainId": 8453, "registry": REGISTRY, "easSchema": EAS_SCHEMA, "method": "eth_call with EIP-1898 {blockHash, requireCanonical: true}"},
        "x402": {"gatewayUrl": X402_URL, "discovery": f"{X402_URL}/.well-known/x402", "enableWith": f"PACTA_X402_URL={X402_URL}",
                 "optIn": True, "payTo": PAY_TO, "asset": USDC_BASE, "chainId": 8453, "x402Versions": [1, 2],
                 "networks": ["base", X402_NETWORK_V2], "maxTimeoutSeconds": X402_MAX_TIMEOUT_S, "wire": X402_WIRE,
                 "toolPaymentArguments": {"v1": "xPaymentHeader", "v2": "paymentSignatureHeader", "preference": "x402Version"},
                 "onchainReceiptVerified": False,
                 "paidRoutes": [{"path": r.split("?")[0], "amount": atomic, "priceUsd": usd} for r, atomic, usd in X402_ROUTES]},
    }


def skill_md(prop, idx):
    m = idx["summary_metrics"]
    return f"""---
name: pacta-protocol-commitments
description: Query Pacta's free, block-pinned DeFi control-plane feeds (who can upgrade, pause, mint or change delays behind collateral), verify any value on an archive node, map live Aave / Euler / Morpho / Sky governance proposals to on-chain state, and optionally pay x402 Base USDC for live scans of unindexed contracts.
version: "{MCP_VERSION}"
homepage: {BASE}/
---

# Pacta protocol commitments

Use this skill when a task involves DeFi collateral risk, governance or upgrade authority, timelocks, Safe quorums or roles,
or a live collateral onboarding proposal. Pacta publishes {m['records_indexed']} block-pinned records ({m['sprints_completed']} sprints) and
{len(prop['proposals'])} governance proposals mapped to on-chain state. Everything is read-only and free.

## Feeds (no key, no paywall)
""" + "\n".join(f"- `{BASE}{p}`: {d}" for p, d in FEEDS) + f"""

## Verify before you trust
Every record carries a target contract, call signature and arguments, block number and canonical block hash:

```bash
cast call <target> "<signature>" <args> --block <N> --rpc-url "$ETH_RPC_URL"
cast block <N> --field hash --rpc-url "$ETH_RPC_URL"   # must equal the recorded block hash
```

Use EIP-1898 `{{"blockHash": "<hash>", "requireCanonical": true}}` when calling eth_call directly.

## MCP server ({MCP_NAME})
{MCP_STATUS}

""" + "\n".join(f"- `{n}` ({p}): {d}" for n, p, d in MCP_TOOLS) + """

Environment (all optional, none secret):
""" + "\n".join(f"- `{n}`: {d}" for n, d in MCP_ENV) + f"""

## x402 (optional, only for live scans of contracts not in the index)
- Live gateway: `{X402_URL}` (discovery `{X402_URL}/.well-known/x402`; free `/health` and `/v1/sample/control-plane`).
- The MCP paid tools are opt-in: set `PACTA_X402_URL={X402_URL}` to enable them.
- Base (8453), scheme `exact`, USDC `{USDC_BASE}`, payTo `{PAY_TO}`, `maxTimeoutSeconds` {X402_MAX_TIMEOUT_S}. Never sign for any other `payTo`.
- Paid routes (GET query or POST JSON body with the same names; default client cap $1.00):
""" + "\n".join(f"  - `{X402_URL}{r.split('?')[0]}` ({usd}, `{atomic}` atomic USDC)" + (f": `?{r.split('?')[1]}`" if "?" in r else "")
                for r, atomic, usd in X402_ROUTES) + f"""
- `x402Versions: [1, 2]`, `networks: ["base", "{X402_NETWORK_V2}"]`:
  - x402 v1: 402 JSON body (`x402Version: 1`, `network: "base"`, `maxAmountRequired`), pay with `X-PAYMENT`, receipt `X-PAYMENT-RESPONSE`.
  - x402 v2: `PAYMENT-REQUIRED` header (base64 JSON, `x402Version: 2`, `network: "{X402_NETWORK_V2}"`, `amount`, `extensions.bazaar` with a JSON Schema draft 2020-12 schema), pay with `PAYMENT-SIGNATURE`, receipt `PAYMENT-RESPONSE`.
- Bare probe: a bare `GET` (no query) or zero-byte `POST` with no payment header returns HTTP 402 with both challenges.
- MCP tools take `xPaymentHeader` (v1) or `paymentSignatureHeader` (v2); `x402Version` picks the challenge to answer.
- {X402_RECEIPT_NOTE}
- Pacta Treasury `{TREASURY}` is an EOA (externally owned account) that receives issuer clearance payments; it is not an x402 payTo.

## Anchoring (Base, chain id 8453)
- PactaCommitmentRegistry `{REGISTRY}`; EAS schema `{EAS_SCHEMA}`. Per-sprint attestation UIDs are in `/api/v1/index.json`.

## Sentinel
{SENTINEL}

## Rules
- Report observed values with their block; do not infer exploitability from a parameter delta.
- Pacta reads governance forums and never posts on them: there is no live forum posting.
- Exploit-sensitive findings go to Immunefi or Cantina, never to public channels.
"""


def render_all(idx, radar, onb):
    """Pure function: {relative path under docs/: file text}. No filesystem access (used by verify_site_v2.py)."""
    prop = proposals(idx, onb)
    return {
        "api/v1/proposals.json": json.dumps(prop, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        "llms-full.txt": llms_full(idx, radar, prop, onb),
        ".well-known/agent.json": json.dumps(agent_card(prop, onb, idx), indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        ".well-known/mcp.json": json.dumps(mcp_manifest(idx, onb), indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        "SKILL.md": skill_md(prop, idx),
    }


def write_all(docs, idx, radar, onb):
    files = render_all(idx, radar, onb)
    for rel, text in files.items():
        p = os.path.join(docs, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(text)
    return json.loads(files["api/v1/proposals.json"])
