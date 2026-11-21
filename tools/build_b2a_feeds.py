"""Agent-first (B2A) machine feeds, generated deterministically from docs/api/v1/{index,radar,onboarding}.json.

Writes (called from tools/build_site.py; never hand-edited):
  docs/api/v1/proposals.json      schema pacta.governance_proposals_feed.v1: live Aave / Euler / Morpho / Sky governance
                                  proposals mapped to block-pinned control-plane observations
  docs/llms-full.txt              single-file reference corpus for LLM, coding and DeFi agents
  docs/.well-known/agent.json     A2A Agent Card (skills, feeds, Base EAS anchor, x402 payment descriptor)
  docs/.well-known/mcp.json       MCP discovery manifest for @pacta/mcp-server (io.github.Fractal-Neurons/pacta)
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
MCP_REMOTE_URL = X402_URL + "/mcp"                               # remote MCP (Streamable HTTP), zero install
OPENAPI_URL = X402_URL + "/openapi.json"
PRICING_MODE = "free_launch"                                     # live Worker default: $0, no key, no wallet; x402 behind a switch
RATE_LIMIT_PER_MIN = 60
REMOTE_READ_ONLY_TOOLS = ["pacta_lookup_protocol", "pacta_check_preflight", "pacta_scan_wallet_exposure", "pacta_scan_control_plane", "pacta_scan_timelock_op", "pacta_scan_proposal_diff", "pacta_get_live_timelocks"]
REQUEST_TOOL = "pacta_submit_request"                              # the one opt-in write tool (remote + stdio): queue / upvote a request
REMOTE_TOOLS = REMOTE_READ_ONLY_TOOLS + [REQUEST_TOOL]
REQUESTS_URL = "https://pacta-x402.pacta.workers.dev/v1/requests"
REMOTE_TOOLS_DOC = "7 read-only inspection tools + 1 opt-in coverage/feature request tool (pacta_submit_request)"
STDIO_TOOLS_DOC = "11 read-only inspection tools + 1 opt-in request tool"
BRAND = "Pacta by Fractal Neurons (https://pacta.wtf · pacta.base.eth)"
# Brand / RAG disambiguation (receipt/1817): never call this project by the two-word name of the dormant escrow project.
DISAMBIGUATION = ("Disambiguation: Pacta by Fractal Neurons (https://pacta.wtf, pacta.base.eth, io.github.Fractal-Neurons/pacta) is the EVM DeFi "
                  "control-plane, Safe multisig, and timelock verification registry — unrelated to pactaprotocol.org (commercial escrow) or RMI PACTA "
                  "(climate assessment).")
BOUNTIES_URL = "https://pacta.wtf/bounties/"
BOUNTIES_DOC = ("Bounties ($100): Pacta Chain-Feed Mismatch Challenge, 4 × $25 USDC = $100 USDC hard cap, 7-day sprint Nov 15 – Nov 22, 2026: "
                "a verified on-chain control-plane parameter_delta on an unindexed protocol, or live drift on an indexed one, submitted as a PR to "
                "Fractal-Neurons/pacta. Paid in USDC on Base Mainnet after maintainer merge (not pre-escrowed): " + BOUNTIES_URL)
_W2 = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bounty_wave2.json")))
_W3 = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bounty_wave3.json")))
_W2_TVL = {k: f"${v['minTvlUsd'] // 1_000_000}M" for k, v in _W2["categories"].items() if v["minTvlUsd"]}
LEADERBOARD_URL = "https://pacta.wtf/leaderboard/"
COMMUNITY_URL, COMMUNITY_QA_URL = _W3["communityUrl"], _W3["communityQaUrl"]
COMMUNITY_DOC = (f"Community hub (GitHub Discussions): announcements and builder / bounty Q&A at {COMMUNITY_URL}; questions about targets, "
                 f"dossiers or the MCP tools go to the Q&A thread {COMMUNITY_QA_URL}. Historical Wave 2 issue: {_W2['wave2IssueUrl']}")
WAVE3_DOC = (f"Bounties Wave 3 (OPEN): {_W3['program']} ({_W3['openSlots']} × ${_W3['rewardUsdc']} USDC = ${_W3['poolCapUsdc']} USDC open; "
             f"${_W3['fundedUnencumberedUsdc']} USDC ({_W3['fundedUnencumberedSlots']} slots) confirmed unencumbered on-chain now in {_W3['settlement']['treasuryAddress']}); "
             f"protocols >= ${_W3['minTvlUsd'] // 1_000_000}M TVL across 7 EVM chains ({', '.join(_W3['chains'].values())}), INCLUDING all pre-indexed rpc_observed "
             f"(easAttested: false) protocols in /api/v1/protocols.json; mandatory 3-part human-researcher dossier (historical_transitions 2023-2026, "
             f"docs_and_governance_forensics with MTTR, repo_audit + >= {_W3['minMemoChars']}-char executive_risk_memo) submitted at "
             f"{_W3['fixtureDir']}/<chain>-<slug>.json: {BOUNTIES_URL}#wave-3")
WAVE2_DOC = (f"Bounties Wave 2 (Completed & Retired Archive): {_W2['program']}, retired after Epoch {_W2['currentEpoch']} ({_W2['activeEpochSlots']} × ${_W2['rewardUsdc']} USDC "
             f"= ${_W2['activeEpochCapUsdc']} USDC settled on Base; active human-researcher bounties moved to Wave 3): {BOUNTIES_URL}#wave-2")
LEADERBOARD_DOC = ("Hunter leaderboard & verified researcher credentials: verified catches, protocols covered, Base EAS attestations, settled Base USDC "
                   "per hunter and agent framework, and permanent shareable credentials at /leaderboard/#<hunter> + /badges/hunters/<handle>.svg: " + LEADERBOARD_URL)
UA_DOC = ('HTTP clients: curl and python-requests work with their default User-Agent. For the Python standard library, send any '
          'User-Agent header (urllib.request.Request(url, headers={"User-Agent": "my-agent/1.0"})) or read the static JSON on pacta.wtf.')
REQUEST_DOC = ("Opt-in demand intake: when a result carries coverage_gap_hint (lookup miss, unindexed or unclassified pre-flight target, unsupported chain), "
               "ask the user, then call pacta_submit_request (or POST " + REQUESTS_URL + ") with request_type "
               "(missing_protocol | unsupported_chain | missing_check_surface | doc_or_data_discrepancy | mcp_or_api_feature), target_subject, "
               "requested_capability and urgency_track (community_queue_free | active_due_diligence | issuer_24h_clearance_5k | api_high_volume_sla), plus optional caller_agent / requester_role / caller_purpose. "
               "It returns request_id (REQ-2026-xxxxxxxx), status (queued | upvoted_existing), demand_votes and fast_track_url; an identical request "
               "upvotes the existing one. Free in every pricing mode, 5 per hour; never opens a GitHub issue. contact_handle only when the user "
               "explicitly asks for follow-up or an invoice: it is stored privately and never published.")
# Copy-paste MCP recipes (receipt/1818): Claude Code, OpenAI Agents SDK, LangChain (each <= 10 lines).
MCP_RECIPES = [
    ("Claude Code", "bash", "claude mcp add --transport http pacta https://pacta-x402.pacta.workers.dev/mcp"),
    ("OpenAI Agents SDK (Python)", "python", "\n".join([
        "from agents import Agent, Runner",
        "from agents.mcp import MCPServerStreamableHttp",
        "",
        "async def main():",
        "    async with MCPServerStreamableHttp(params={\"url\": \"https://pacta-x402.pacta.workers.dev/mcp\"}) as pacta:",
        "        agent = Agent(name=\"risk-agent\", mcp_servers=[pacta],",
        "                      instructions=\"Call pacta_lookup_protocol, then pacta_check_preflight, before any deposit.\")",
        "        print((await Runner.run(agent, \"Is it safe to deposit into Ethena sUSDe?\")).final_output)"])),
    ("LangChain (langchain-mcp-adapters)", "python", "\n".join([
        "from langchain_mcp_adapters.client import MultiServerMCPClient",
        "from langgraph.prebuilt import create_react_agent",
        "",
        "async def main(model):",
        "    client = MultiServerMCPClient({\"pacta\": {\"url\": \"https://pacta-x402.pacta.workers.dev/mcp\", \"transport\": \"streamable_http\"}})",
        "    agent = create_react_agent(model, await client.get_tools())",
        "    out = await agent.ainvoke({\"messages\": \"Who can upgrade the Ethena timelock, and how fast?\"})",
        "    print(out[\"messages\"][-1].content)"])),
]
STDIO_FROM_SOURCE = "node packages/mcp-server/bin/pacta-mcp.mjs"  # from a clone of the repository (npm publication pending)
FREE_LAUNCH_NOTE = (f"Free launch: every route answers HTTP 200 at $0 with no API key and no wallet ({RATE_LIMIT_PER_MIN} requests / minute per caller). "
                    "The x402 prices below apply only if the operator switches pricingMode to x402_paid.")
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
# Gateway-side guard (pacta-core packages/x402-edge-worker): the Worker re-reads every paid settlement on Base itself.
X402_GATEWAY_GUARD = {
    "onchainReceiptVerification": True, "appliesTo": "x402_paid settlements only", "chainId": 8453, "rpcMethod": "eth_getTransactionReceipt",
    "requires": "receipt status 0x1 and canonical USDC (Base) Transfer(payer -> payTo) logs summing to at least the route price",
    "asset": USDC_BASE, "payTo": PAY_TO, "replay": ("best-effort replay rejection: synchronous same-isolate in-flight + FIFO (4,096) sets block same-isolate "
               "concurrent/serial replays, and non-atomic eventually-consistent KV used_tx:<txHash> (30-day TTL) blocks "
               "post-propagation serial cross-isolate replays (402 replay_settlement_tx); concurrent cross-isolate races before "
               "KV write/propagation are not globally atomic without Durable Objects"),
    "failures": {"402": ["unconfirmed_or_reverted_settlement_tx", "insufficient_onchain_usdc_transfer", "replay_settlement_tx"],
                 "502": ["settlement_rpc_unavailable"]}}
X402_GATEWAY_GUARD_NOTE = (f"In x402_paid mode the gateway verifies every settlement on Base before releasing the product: eth_getTransactionReceipt "
                           f"must show status 0x1 and canonical USDC Transfer(payer -> payTo {PAY_TO}) logs summing to at least the route price, "
                           "and replays are rejected on a best-effort basis (402 replay_settlement_tx) via synchronous same-isolate state and "
                           "non-atomic eventually-consistent KV used_tx:<txHash>; concurrent cross-isolate races are not globally atomic "
                           "without Durable Objects. Otherwise the product is withheld: "
                           "402 unconfirmed_or_reverted_settlement_tx / insufficient_onchain_usdc_transfer, or 502 settlement_rpc_unavailable "
                           "when no Base RPC answers.")
TREASURY_USE = ("Pacta treasury (direct settlement EOA): Option B direct on-chain USDC settlement of commercial issuer clearance "
                "(Option A is a formal commercial invoice). An externally owned account, not a smart-contract wallet; not the x402 payTo.")
MCP_NAME = "io.github.Fractal-Neurons/pacta"
MCP_PACKAGE = "@pacta/mcp-server"
MCP_VERSION = "0.1.5"
CALLER_FIELDS_DOC = 'Free MCP tier: tools/call takes three OPTIONAL, non-personal attribution fields: caller_agent (a lowercase slug naming the calling agent, IDE or framework, e.g. claude-code, cursor, coinbase-agentkit; never a name, e-mail, IP, URL, address or secret), requester_role (autonomous_agent | defi_developer | risk_curator_analyst | security_researcher | protocol_team | institutional_allocator | individual_user) and caller_purpose (pre_trade_safety | collateral_due_diligence | yield_allocation | security_audit | governance_monitoring | integration_testing | general_research). Omitted, blank or invalid attribution fields never block a call (invalid values are silently dropped and never stored; unattributed MCP calls infer a known client slug from X-MCP-Client-Name / User-Agent or count as unspecified). Over REST they are optional query or body parameters. Location is never asked: only the Cloudflare edge country is counted; no IP is stored.'                                            # @pacta/mcp-server package.json version (SKILL.md is shipped in it)
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


RPC_ENV = {"ethereum": "$ETH_RPC_URL", "base": "$BASE_RPC_URL"}


def index_cast(e):
    rpc = f'--rpc-url "{RPC_ENV[e.get("chain", "ethereum")]}"'
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
        chains = {e.get("chain", "ethereum") for e in recs}
        assert len(chains) == 1, (x["records"], chains)                 # a cross-reference stays on one chain
        pin = max(recs, key=lambda e: e["block_number"])
        chain = chains.pop()
        summ = [f'{e["protocol"]} — {e["surface"]} [{e["classification"]}, Sprint {e["sprint"]}, block {e["block_number"]}]: {e["onchain_observed"]} '
                f'Documented: {e["documented_reference"]}' for e in recs]
        out.append({"proposal_id": f'{x["forum"]}-{x["topic_id"]}', "forum": x["forum"], "topic_id": x["topic_id"], "title": x["title"],
                    "forum_url": x["forum_url"], "relation": x["relation"], "chain": chain, "chain_id": {"ethereum": 1, "base": 8453}[chain],
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


def _catalog_counts():
    """Published protocol pages / briefs, read from the committed input feeds (the same sources build_lookup.py uses), so the
    agent docs never carry a stale count: protocols = index.json Sprint protocols + rpc-pinned.json protocols."""
    rd = lambda n: json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "api", "v1", n), encoding="utf-8"))
    eas = len({e["protocol"] for e in rd("index.json")["entries"]})
    rpc = len({e["slug"] for e in rd("rpc-pinned.json")["entries"]})
    return {"protocols": eas + rpc, "eas": eas, "rpc": rpc, "briefs": len(rd("onboarding.json")["briefs"]) + len(rd("radar.json")["items"])}


CAT = _catalog_counts()
FEEDS = [("/api/v1/index.json", "Block-pinned control-plane index (every record: target, call, block, block hash, classification, Base EAS UID)"),
         ("/api/v1/lookup.json", f"Protocol / token lookup catalog: {CAT['protocols']} protocols + {CAT['briefs']} briefs with slug, aliases, checksummed contracts, evidence basis and preflightArgs"),
         ("/api/v1/protocols.json", f"Every published protocol: badge tier + URLs, evidence basis ({CAT['eas']} EAS-attested / {CAT['rpc']} RPC-observed), Sprint ids, EAS UIDs, controller, pinned surfaces"),
         ("/api/v1/onboarding.json", "Onboarding verification scans: every check with call, calldata, raw result, decoded value; role maps"),
         ("/api/v1/proposals.json", "Live governance proposals (Aave, Euler, Morpho, Sky) mapped to block-pinned observations"),
         ("/api/v1/radar.json", "Queued timelock operations with on-chain ETAs at a finalized block"),
         ("/llms.txt", "Short index for language models"), ("/llms-full.txt", "This file: the complete agent reference"),
         ("/.well-known/agent.json", "A2A Agent Card"), ("/.well-known/mcp.json", "MCP discovery manifest"), ("/SKILL.md", "Portable agent skill")]
LOOKUP_URL = f"{X402_URL}/v1/protocols/lookup"
LOOKUP_DOC = (f"Name lookup first: if you only have a protocol or token name (e.g. Aave, Ethena, USDe, Moonwell, kUSD), call pacta_lookup_protocol "
              f"(or GET {LOOKUP_URL}?q=<name>) to resolve its verified record: canonical slug and page URL, checksummed primary contract and controller, "
              "classification with its evidence basis (eas_attested: Base-EAS-attested, documentation compared; rpc_observed: on-chain control plane "
              "pinned over JSON-RPC, documentationComparison not_assessed; briefs), and preflightArgs {chain, address} for pacta_check_preflight. "
              f"{CAT['protocols']} protocols + {CAT['briefs']} briefs, answered in memory with no RPC; free in every pricing mode; an empty query lists the catalog. "
              f"Catalog: {BASE}/api/v1/lookup.json.")
MCP_TOOLS = [("pacta_lookup_protocol", "free", "Resolve a protocol or token name, symbol, slug or 0x address to its verified record and preflightArgs {chain, address} (query, chain, kind, limit; no RPC)"),
             ("pacta_list_commitments", "free", "Filter indexed records (protocol, classification, sprint, limit)"),
             ("pacta_get_anchoring", "free", "Base EAS anchoring: PactaCommitmentRegistry, schema, sprint attestation UIDs"),
             ("pacta_list_proposals", "free", "Governance proposals feed (forum, topic_id, chain, limit, include_repro)"),
             ("pacta_x402_discover", "free", "x402 gateway status and discovery manifest (only when PACTA_X402_URL is set)"),
             ("pacta_check_preflight", "x402 $0.01", "Pre-execution check of a contract: verdict, 0-100 risk score, proxy / admin / timelock, capabilities (chain, address, block)"),
             ("pacta_scan_wallet_exposure", "x402 $0.01", "Read-only Multicall3 Ethereum + Base wallet or Safe exposure summary across indexed DeFi protocols (address, chain; shares 50/day free quota, zero wallet-address logging)"),
             ("pacta_scan_control_plane", "x402 $0.10", "Live control-plane scan of a contract (chain, address)"),
             ("pacta_scan_timelock_op", "x402 $0.25", "Live TimelockController operation state (timelock, opId)"),
             ("pacta_live_timelocks", "x402 $0.10", "Live state of tracked queued timelock operations"),
             ("pacta_scan_proposal_diff", "x402 $0.15", "Re-run a tracked governance proposal's pinned reads live, pinned-vs-live diffs (forum, topicId)"),
             ("pacta_submit_request", "free", "Opt-in (the only tool that writes): queue or upvote a coverage / feature request after a coverage_gap_hint, with the user's consent; forwards to POST /v1/requests (only when PACTA_X402_URL is set)")]
X402_ROUTES = [("/v1/check/preflight?chain=ethereum|base&address=0x…", "10000", "$0.01"),
               ("/v1/check/wallet-exposure?address=0x…&chain=ethereum|base|all", "10000", "$0.01"),
               ("/v1/scan/control-plane?chain=ethereum|base&address=0x…", "100000", "$0.10"),
               ("/v1/scan/timelock-op?chain=ethereum|base&timelock=0x…&opId=0x…", "250000", "$0.25"),
               ("/v1/scan/proposal-diff?forum=aave|euler|morpho|sky&topicId=<id>", "150000", "$0.15"),
               ("/v1/briefs/live-timelocks", "100000", "$0.10")]
SENTINEL = ("PactaSentinelTripwire.sol: an ownerless, immutable contract granted Morpho Vault V2 isSentinel. Vault owners register rules "
            "(predicate module + config, cap id, adapter, liquidity reader). trigger(ruleId) is permissionless but re-checks the broken invariant "
            "on-chain in the same transaction, then sets the absolute cap to 0 (committed even if deallocate or the EAS receipt revert), "
            "deallocates min(allocation, liquid assets), and sweepRemaining(ruleId) drains the rest as liquidity returns. Zero custody. "
            "Predicates: " + ", ".join(PREDICATES) + ". Status: built and tested (Foundry, 107 tests incl. invariants and fork tests); "
            "not audited, not deployed.")
MCP_STATUS = (f"publication_pending: @pacta/mcp-server is not yet published to npm or the MCP registry. Use the remote MCP server now "
              f"(no install): {MCP_REMOTE_URL}. The stdio server runs from a clone of the repository: {STDIO_FROM_SOURCE}.")


def protocols_line(idx, pinned):
    """The single protocol count sentence (homepage ledger, llms.txt, llms-full.txt): EAS-attested + RPC-pinned = indexed."""
    eas = len({e["protocol"] for e in idx["entries"]})
    rpc = len({e["protocol"] for e in (pinned or {}).get("entries", [])})
    return (f"{eas + rpc} indexed protocols: {eas} Base-EAS-attested protocols ({idx['summary_metrics']['records_indexed']} Sprint records across "
            f"{idx['summary_metrics']['sprints_completed']} Sprints) + {rpc} RPC-pinned protocols (not EAS-attested).")


def llms_full(idx, radar, prop, onb, pinned=None):
    a, m = idx["onchain_anchoring"], idx["summary_metrics"]
    L = ["# Pacta by Fractal Neurons — full agent reference (llms-full.txt)", "",
         DISAMBIGUATION, "",
         f"> {BRAND}: block-pinned DeFi control-plane observations for AI agents: who can change a protocol's rules (proxy admins, timelocks, "
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
         "## MCP server", f"- Name: {MCP_NAME} · package {MCP_PACKAGE} v{MCP_VERSION} · transport stdio.", f"- Status: {MCP_STATUS}",
         f"- Remote MCP (primary, zero install, Streamable HTTP): {MCP_REMOTE_URL} · Claude Code: `claude mcp add --transport http pacta {MCP_REMOTE_URL}` · "
         f"MCP client config: {{\"mcpServers\": {{\"pacta\": {{\"url\": \"{MCP_REMOTE_URL}\"}}}}}} · remote tools ({REMOTE_TOOLS_DOC}): {', '.join(REMOTE_TOOLS)}.",
         f"- Local stdio server (from a clone; npm publication pending): `{STDIO_FROM_SOURCE}`. OpenAPI 3.1: {OPENAPI_URL}.",
         f"- {CALLER_FIELDS_DOC}",
         f"- One call: `curl -s -A \"my-agent/1.0\" \"{X402_URL}/v1/check/preflight?chain=ethereum&address=0x...\"`. {UA_DOC} Every response carries "
         "`assessment` (coverage indexed_verified | unindexed_bytecode_heuristic, confidence high | medium | low, method, limits) next to the 0-100 "
         "`riskScore`, plus `catalogMatch` (slug, classification, Base EAS UIDs, pinned block, whatDiffers) when the address is an indexed protocol "
         "contract; if live RPC is unavailable for an indexed address, the answer is the pinned catalog record (`source: pinned_catalog_fallback`) "
         "instead of a 502.",
         f"- {protocols_line(idx, pinned)}",
         f"- {LOOKUP_DOC}",
         f"- {REQUEST_DOC}",
         f"- {BOUNTIES_DOC}",
         f"- {WAVE3_DOC}",
         f"- {WAVE2_DOC}",
         f"- {LEADERBOARD_DOC}",
         f"- {COMMUNITY_DOC}",
         f"- Vault factories and curators: {BASE}/integrations/vault-factories/ (Control-Plane & Role Map tab from {BASE}/api/v1/protocols.json, status badges {BASE}/badges/<slug>.svg and {X402_URL}/v1/badges/<slug>.svg, and PactaSentinelGuard.sol: refuses cap increases without a healthy Pacta attestation, never blocks a decrease).",
         f"- Stdio tools ({STDIO_TOOLS_DOC}):"] + [f"  - {n} ({p}): {d}" for n, p, d in MCP_TOOLS] + [
         f"- Paid tools are disabled unless PACTA_X402_URL is set (opt-in: PACTA_X402_URL={X402_URL}); the client refuses any 402 challenge (v1 body or v2 "
         "PAYMENT-REQUIRED header) whose payTo, asset or network differ from the values below, or whose amount exceeds $1.00 by default. Pay with "
         "xPaymentHeader (x402 v1) or paymentSignatureHeader (x402 v2).", "",
         "## x402 micropayments (optional; only for live scans of unindexed contracts)",
         f"- Network: Base (chain id 8453) · scheme exact · asset USDC {USDC_BASE} · payTo {PAY_TO} (attester EOA, pacta.base.eth).",
         f"- Pacta Treasury: {TREASURY} (an externally owned account; the PactaCommitmentRegistry treasury slot). {TREASURY_USE}",
         f"- Live gateway: {X402_URL} (Cloudflare Worker; pricingMode {PRICING_MODE}; x402Versions [1, 2]; PayAI facilitator; maxTimeoutSeconds {X402_MAX_TIMEOUT_S}).",
         f"- {FREE_LAUNCH_NOTE}",
         "- x402 v1: network base · amount field maxAmountRequired · challenge in the 402 JSON body · pay with X-PAYMENT · receipt X-PAYMENT-RESPONSE.",
         f"- x402 v2: network {X402_NETWORK_V2} · amount field amount · challenge in the PAYMENT-REQUIRED header (base64 JSON) · pay with PAYMENT-SIGNATURE · "
         f"receipt PAYMENT-RESPONSE · extensions.bazaar carries a JSON Schema draft 2020-12 schema ({JSON_SCHEMA_2020_12}).",
         f"- Bare probe: {X402_BARE_PROBE}",
         f"- Settlement: {X402_RECEIPT_NOTE}",
         f"- Gateway settlement guard: {X402_GATEWAY_GUARD_NOTE}",
         "- Paid routes (GET query or POST JSON body with the same names):"] + [f"  - GET {X402_URL}{r}: {atomic} atomic USDC ({usd})" for r, atomic, usd in X402_ROUTES] + [
         "- Free: " + ", ".join(f"GET {X402_URL}{p}" for p in X402_FREE) + " (/.well-known/x402 is the Bazaar discovery manifest, discoverable: true).", "",
         "## On-chain anchoring (Base, chain id 8453)",
         f"- PactaCommitmentRegistry {REGISTRY} (Sourcify verified); attester pacta.base.eth {a['attester_eoa']}.",
         f"- EAS schema {EAS_SCHEMA}: uint16 sprintId,uint64 chainId,uint64 blockNumber,bytes32 blockHash,uint8 verifiedCount,uint8 driftCount,bytes32 summarySha256,string prURI (as registered on Base).",
         ] + [f"- Sprint {k} attestation UID {v}" for k, v in sorted(a["sprint_eas_attestations"].items(), key=lambda kv: int(kv[0]))] + [
         "", "## Sentinel (Phase 2)", f"- {SENTINEL}", "",
         "## Governance proposals (from /api/v1/proposals.json)"]
    for p in prop["proposals"]:
        L += [f"### {p['proposal_id']}: {p['title']}", f"- {p['forum_url']} · {p['relation']}",
              f"- {p['chain']} block {p['pinned_block_number']} ({p['pinned_block_hash']}) · source {p['source_feed']} {', '.join(p['source_record_ids'])}"
              + (f" · brief {p['brief_url']}" if p["brief_url"] else ""),
              f"- Sentinel predicates: {', '.join(p['recommended_sentinel_predicates'])}"] + [f"- {s}" for s in p["control_plane_summary"]] + [""]
    L += ["## Queued timelock operations (from /api/v1/radar.json)",
          f"Refreshed at finalized block {radar['refreshed_at']['block_number']} ({radar['refreshed_at']['block_time_utc']})"
          + (f"; Base items at Base finalized block {radar['refreshed_at_base']['block_number']} ({radar['refreshed_at_base']['block_time_utc']})"
             if radar.get("refreshed_at_base") else "") + "."]
    for it in radar["items"]:
        ops = "; ".join(f"{o['op_id']} pending={str(o['pending']).lower()} eta={o['eta']}" for o in it["operations"])
        on = " · Base (chain id 8453)" if it.get("chain_id", 1) == 8453 else ""   # v4.6: multi-chain radar
        L.append(f"- {it['protocol']}: {it['title']}{on} · timelock {it['timelock']} ({it['min_delay_seconds']}s) · {ops}")
    L += ["", "## Indexed records (from /api/v1/index.json)"]
    for e in sorted(idx["entries"], key=lambda e: (-e["sprint"], e["id"])):
        L.append(f"- {e['id']} [{e['classification']}] {e['protocol']} — {e['surface']} · Sprint {e['sprint']} · block {e['block_number']} "
                 f"({e['block_hash']}) · target {e['target_contract']} · {e['onchain_observed']}")
    if pinned:
        L += ["", "## RPC-pinned records (from /api/v1/rpc-pinned.json; NOT EAS-attested)",
              "No sprint number, summary document or Base EAS UID: block-pinned public JSON-RPC reads, independently re-read at the same block.",
              "Classification rpc_observed: on-chain control plane pinned at an archive block height over JSON-RPC; documentation parameter "
              "comparison unassessed (documentation is linked for reference only)."]
        for e in sorted(pinned["entries"], key=lambda e: e["id"]):
            L.append(f"- {e['id']} [{e['classification']}] {e['protocol']} — {e['surface']} · {e['chain_label']} block {e['block_number']} "
                     f"({e['block_hash']}) · target {e['target_contract']} · {e['onchain_observed']} · page {BASE}/protocols/{e['slug']}/")
    L += ["", "## Scope",
          "- Observations of on-chain state at the stated blocks; not code audits, reserve attestations or investment advice.",
          "- Exploit-sensitive vulnerabilities are never published here; they go through Immunefi or Cantina bounty programmes.",
          "- Pacta reads governance forums and never posts on them.", ""]
    return "\n".join(L)


def agent_card(prop, onb, idx):
    return {
        "protocolVersion": "0.3.0",
        "name": "Pacta",
        "description": ("Free pre-execution contract and governance safety API for AI agents (launch: $0, no API key, no wallet): who can "
                        "upgrade, pause or blacklist a contract, how fast, pinned to a block hash. Plus block-pinned DeFi control-plane "
                        "records, live governance proposals and a timelock radar. Remote MCP and OpenAPI 3.1; x402 v1 + v2 ready."),
        "url": f"{BASE}/",
        "version": max(idx["generated_at"], onb["generated_at"])[:10].replace("-", "."),
        "provider": {"organization": "Fractal Neurons", "url": "https://fractalneurons.com"},
        "documentationUrl": f"{BASE}/llms-full.txt",
        "iconUrl": f"{BASE}/favicon.png",
        "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": False},
        "defaultInputModes": ["application/json", "text/plain"],
        "defaultOutputModes": ["application/json", "text/markdown"],
        "authentication": {"schemes": ["none"], "notes": "No API key, no account, no wallet during the free launch. If metered mode is switched on later, live scans use x402 instead of keys: v1 (HTTP 402 + X-PAYMENT) or v2 (PAYMENT-REQUIRED + PAYMENT-SIGNATURE)."},
        "skills": [
            {"id": "protocol-lookup", "name": "Protocol / token name lookup",
             "description": "Resolve a protocol or token name (Aave, Ethena, USDe, Moonwell, kUSD, ...) to Pacta's verified record and the checksummed contract to check next. Free, in memory, every pricing mode.",
             "tags": ["lookup", "discovery", "agent-safety", "free"], "inputModes": ["application/json"], "outputModes": ["application/json"],
             "examples": [f"GET {LOOKUP_URL}?q=ethena", "MCP tool pacta_lookup_protocol {\"query\": \"USDe\"}"]},
            {"id": "contract-preflight", "name": "Pre-execution contract check",
             "description": "Before approving, depositing into or calling a contract: who controls it (EOA, Safe, timelock, nobody), how fast it can change, and whether it can pause, blacklist or upgrade. Free, one call.",
             "tags": ["preflight", "agent-safety", "proxy", "timelock", "multisig", "free"], "inputModes": ["application/json"], "outputModes": ["application/json"],
             "examples": [f"GET {X402_URL}/v1/check/preflight?chain=base&address=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", "MCP tool pacta_check_preflight {\"chain\": \"ethereum\", \"address\": \"0x...\"}"]},
            {"id": "wallet-exposure", "name": "Wallet & Safe DeFi control-plane exposure scan",
             "description": "Read-only Multicall3 balanceOf + Safe custody scan across Ethereum & Base indexed DeFi protocols: portfolio risk score, shortest exit window, aligned vs flagged breakdown, and cross-position contagion.",
             "tags": ["wallet", "safe", "portfolio", "multicall3", "agent-safety", "free"], "inputModes": ["application/json"], "outputModes": ["application/json"],
             "examples": [f"GET {X402_URL}/v1/check/wallet-exposure?address=0x...", "MCP tool pacta_scan_wallet_exposure {\"address\": \"0x...\", \"chain\": \"all\"}"]},
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
            {"id": "coverage-request", "name": "Opt-in coverage / feature request",
             "description": "When a lookup misses or a pre-flight target is unindexed (coverage_gap_hint), queue or upvote a coverage / feature request with the user's consent: pacta_submit_request or POST /v1/requests. Free, 5 per hour, never opens a GitHub issue; contact details only on explicit request and never published.",
             "tags": ["demand", "coverage", "opt-in", "free"], "inputModes": ["application/json"], "outputModes": ["application/json"],
             "examples": ["MCP tool pacta_submit_request {\"request_type\": \"missing_protocol\", \"target_subject\": \"pendle-v2\", ...}", f"POST {REQUESTS_URL}"]},
            {"id": "verify-onchain", "name": "Reproduce a value",
             "description": "Replay any record with eth_call / cast at its pinned block and compare the canonical block hash.",
             "tags": ["verification", "eip-1898", "coding-agent"], "inputModes": ["text/plain"], "outputModes": ["text/plain"],
             "examples": ["cast call <target> \"getMinDelay()\" --block <N> --rpc-url $ETH_RPC_URL"]},
        ],
        "endpoints": {"feeds": {p: f"{BASE}{p}" for p, _ in FEEDS}, "mcp_manifest": f"{BASE}/.well-known/mcp.json", "skill": f"{BASE}/SKILL.md",
                      "x402_gateway": X402_URL, "mcp_remote": MCP_REMOTE_URL, "openapi": OPENAPI_URL, "preflight": f"{X402_URL}/v1/check/preflight",
                      "wallet_exposure": f"{X402_URL}/v1/check/wallet-exposure",
                      "lookup": LOOKUP_URL, "lookup_catalog": f"{BASE}/api/v1/lookup.json", "requests": REQUESTS_URL, "bounties": BOUNTIES_URL,
                      "curators": f"{BASE}/curators/", "protocols": f"{BASE}/protocols/"},
        "pricing": {"mode": PRICING_MODE, "priceUsd": "0.00", "apiKey": False, "wallet": False, "rateLimitPerMinute": RATE_LIMIT_PER_MIN,
                    "note": FREE_LAUNCH_NOTE},
        "x402": {"x402Version": 1, "x402Versions": [1, 2], "scheme": "exact", "network": "base", "networks": ["base", X402_NETWORK_V2],
                 "chainId": 8453, "asset": USDC_BASE, "payTo": PAY_TO, "maxTimeoutSeconds": X402_MAX_TIMEOUT_S, "pricingMode": PRICING_MODE,
                 "status": "live", "gatewayUrl": X402_URL, "discovery": f"{X402_URL}/.well-known/x402", "wire": X402_WIRE,
                 "bareProbe": X402_BARE_PROBE, "settlement": {"receiptHeaders": ["PAYMENT-RESPONSE", "X-PAYMENT-RESPONSE"],
                                                              "onchainReceiptVerified": False, "note": X402_RECEIPT_NOTE},
                 "onchainReceiptVerification": True, "settlementGuard": X402_GATEWAY_GUARD, "settlementGuardNote": X402_GATEWAY_GUARD_NOTE,
                 "free": [f"{X402_URL}{p}" for p in X402_FREE],
                 "routes": [{"path": r.split("?")[0], "url": X402_URL + r.split("?")[0], "methods": ["GET", "POST"],
                             "query": (r.split("?")[1] if "?" in r else ""), "maxAmountRequired": atomic, "amount": atomic, "priceUsd": usd,
                             "effectivePriceUsd": "0.00" if PRICING_MODE == "free_launch" else usd[1:]}
                            for r, atomic, usd in X402_ROUTES]},
        "anchoring": {"chainId": 8453, "registry": REGISTRY, "easSchema": EAS_SCHEMA, "attester": idx["onchain_anchoring"]["attester_eoa"],
                      "treasury": {"address": TREASURY, "label": "Pacta Treasury", "kind": "externally owned account", "use": TREASURY_USE}},
    }


def mcp_manifest(idx, onb):
    return {
        "name": MCP_NAME, "title": "Pacta by Fractal Neurons", "package": MCP_PACKAGE, "packageVersion": MCP_VERSION,
        "description": "Block-pinned DeFi control-plane commitments, Base EAS attestations and governance proposals for agents.",
        "version": max(idx["generated_at"], onb["generated_at"])[:10].replace("-", "."), "homepage": f"{BASE}/", "documentation": f"{BASE}/llms-full.txt",
        "status": MCP_STATUS,
        "transport": {"type": "streamable-http", "url": MCP_REMOTE_URL, "tools": REMOTE_TOOLS, "auth": "none", "pricingMode": PRICING_MODE},
        "transports": [{"type": "streamable-http", "url": MCP_REMOTE_URL, "tools": REMOTE_TOOLS, "install": "none"},
                       {"type": "stdio", "command": "node", "args": ["packages/mcp-server/bin/pacta-mcp.mjs"],
                        "install": "from a clone of the repository (npm publication pending)"}],
        "openapi": OPENAPI_URL,
        "lookup": {"tool": "pacta_lookup_protocol", "http": LOOKUP_URL, "catalog": f"{BASE}/api/v1/lookup.json", "free": True, "note": LOOKUP_DOC},
        "environment": [{"name": n, "required": False, "secret": False, "description": d} for n, d in MCP_ENV],
        "tools": [{"name": n, "access": "free" if p == "free" else PRICING_MODE, "price": None if p == "free" else p.split(" ")[1],
                   "effectivePriceUsd": "0.00", "readOnly": n != REQUEST_TOOL, "description": d} for n, p, d in MCP_TOOLS],
        "toolSummary": {"remote": REMOTE_TOOLS_DOC, "stdio": STDIO_TOOLS_DOC, "requestTool": REQUEST_TOOL, "requestsEndpoint": REQUESTS_URL},
        "disambiguation": DISAMBIGUATION,
        "feeds": {p: f"{BASE}{p}" for p, _ in FEEDS},
        "verification": {"chainId": 8453, "registry": REGISTRY, "easSchema": EAS_SCHEMA, "method": "eth_call with EIP-1898 {blockHash, requireCanonical: true}"},
        "x402": {"gatewayUrl": X402_URL, "discovery": f"{X402_URL}/.well-known/x402", "enableWith": f"PACTA_X402_URL={X402_URL}",
                 "optIn": True, "payTo": PAY_TO, "asset": USDC_BASE, "chainId": 8453, "x402Versions": [1, 2],
                 "networks": ["base", X402_NETWORK_V2], "maxTimeoutSeconds": X402_MAX_TIMEOUT_S, "wire": X402_WIRE,
                 "toolPaymentArguments": {"v1": "xPaymentHeader", "v2": "paymentSignatureHeader", "preference": "x402Version"},
                 "onchainReceiptVerified": False, "gatewayOnchainReceiptVerification": True, "gatewaySettlementGuard": X402_GATEWAY_GUARD_NOTE,
                 "paidRoutes": [{"path": r.split("?")[0], "amount": atomic, "priceUsd": usd} for r, atomic, usd in X402_ROUTES]},
    }


# The free agent tier and the pay-per-call x402 routes (the Worker's FREE_DAILY_PREFLIGHT_QUOTA / OVERFLOW_PRICE / X402_ROUTES).
X402_PUBLIC = "https://pacta.fractalneurons.com"
FREE_DAILY_QUOTA = 50
X402_ENDPOINTS = [("/v1/x402/verdict", "0.02", "Fast safety verdict: grade A-F, riskScore, upgrade / pause / blacklist / mint flags"),
                  ("/v1/x402/dossier", "0.05", "Control-plane dossier: Safe signers, threshold, cross-protocol signer overlap, Base EAS proof"),
                  ("/v1/x402/wallet-exposure", "0.05", "Multi-position wallet & Safe exposure graph: signer breakdown, cross-position contagion & exit matrix"),
                  ("/v1/x402/calldata-sim", "0.25", "Calldata sim: timelock / Safe calls decoded and rated before signing"),
                  ("/v1/x402/deep-scan", "9.00", "Deep scan cross-checked on two RPC operators + Base EAS ticket")]
FREE_TIER_DOC = (f"Free agent tier: {FREE_DAILY_QUOTA} pre-flight and wallet-exposure checks per caller per UTC day (REST /v1/check/preflight, /v1/check/wallet-exposure and MCP "
                 "pacta_check_preflight, pacta_scan_wallet_exposure together; X-Meter-Limit / X-Meter-Remaining / X-Meter-Reset headers), then $0.01 per call over x402 "
                 "(HTTP 402, USDC on Base; never a dead-end 429). Free responses carry an upgrade_x402 object listing the paid routes.")
X402_DOC = "Pay per call with x402 (USDC on Base, POST JSON, X-PAYMENT v1 or PAYMENT-SIGNATURE v2): " + "; ".join(
    f"{X402_PUBLIC}{p} ${usd} ({what})" for p, usd, what in X402_ENDPOINTS) + "."


def skill_md(prop, idx):
    m = idx["summary_metrics"]
    return f"""---
name: pacta-protocol-commitments
description: Run Pacta's free pre-execution check on any Ethereum or Base contract before an agent approves, deposits into or calls it (who can upgrade, pause or blacklist it, how fast), query the free block-pinned DeFi control-plane feeds, verify any value on an archive node, and map live Aave / Euler / Morpho / Sky governance proposals to on-chain state.
version: "{MCP_VERSION}"
homepage: {BASE}/
---

# Pacta by Fractal Neurons: protocol commitments skill

{DISAMBIGUATION}

Use this skill when a task involves DeFi collateral risk, governance or upgrade authority, timelocks, Safe quorums or roles,
or a live collateral onboarding proposal. Pacta publishes {m['records_indexed']} block-pinned records ({m['sprints_completed']} sprints) and
{len(prop['proposals'])} governance proposals mapped to on-chain state. Every inspection tool is read-only and free; one opt-in tool,
`pacta_submit_request`, queues a coverage / feature request with the user's consent.

## Free pre-execution API (launch: $0, no API key, no wallet)
- Remote MCP, zero install: `{MCP_REMOTE_URL}` (Streamable HTTP). Claude Code: `claude mcp add --transport http pacta {MCP_REMOTE_URL}`.
  Tools ({REMOTE_TOOLS_DOC}): {", ".join(f"`{t}`" for t in REMOTE_TOOLS)}.
- {LOOKUP_DOC}
- {REQUEST_DOC}
- {BOUNTIES_DOC}
- {CALLER_FIELDS_DOC}
- {FREE_TIER_DOC}
- {X402_DOC}
- One call: `curl -s -A "my-agent/1.0" "{X402_URL}/v1/check/preflight?chain=ethereum&address=0x..."` ({UA_DOC}) returns `verdict`, `riskScore` (0-100), proxy /
  implementation (EIP-1967, EIP-1822 or beacon), `controller` (eoa, multisig_safe, timelock, contract,
  access_control_enumerable, access_control or none), `canUpgradeZeroDelay`, `capabilities` (pause, blacklist, upgrade) and
  `pinnedBlock` + `pinnedBlockHash`. Verdicts: `IMMUTABLE_NO_ADMIN`, `TIMELOCK_PROTECTED`, `ZERO_DELAY_TIMELOCK_RISK` (0 s
  timelock: no exit window), `MULTISIG_NO_TIMELOCK`, `INSTANT_EOA_ADMIN_RISK`, `UNDEPLOYED_OR_EOA`,
  `UNCLASSIFIED_CONTRACT_CONTROLLER` (never treat it as safe).
- OpenAPI 3.1: `{OPENAPI_URL}`. Every route takes GET query parameters or a POST JSON body. {RATE_LIMIT_PER_MIN} requests / minute per caller.
- Protocol safety records: `{BASE}/protocols/`.

## MCP recipes (copy-paste)
""" + "\n\n".join(f"{t}:\n\n```{lang}\n{code}\n```" for t, lang, code in MCP_RECIPES) + f"""

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

## x402 (wired in; free during the launch)
- Live gateway: `{X402_URL}` (discovery `{X402_URL}/.well-known/x402`; free `/health`, `/v1/sample/control-plane`, `/v1/sample/preflight`).
- {FREE_LAUNCH_NOTE}
- The local stdio MCP server's scan tools are opt-in: set `PACTA_X402_URL={X402_URL}` to enable them.
- Base (8453), scheme `exact`, USDC `{USDC_BASE}`, payTo `{PAY_TO}`, `maxTimeoutSeconds` {X402_MAX_TIMEOUT_S}. Never sign for any other `payTo`.
- Routes and their x402_paid prices (GET query or POST JSON body with the same names; default client cap $1.00):
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


def render_all(idx, radar, onb, pinned=None):
    """Pure function: {relative path under docs/: file text}. No filesystem access (used by verify_site_v2.py). `pinned` is the
    parsed docs/api/v1/rpc-pinned.json (RPC-pinned records, not EAS-attested), listed in llms-full.txt in their own section."""
    prop = proposals(idx, onb)
    return {
        "api/v1/proposals.json": json.dumps(prop, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        "llms-full.txt": llms_full(idx, radar, prop, onb, pinned),
        ".well-known/agent.json": json.dumps(agent_card(prop, onb, idx), indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        ".well-known/mcp.json": json.dumps(mcp_manifest(idx, onb), indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        "SKILL.md": skill_md(prop, idx),
    }


def write_all(docs, idx, radar, onb, pinned=None):
    files = render_all(idx, radar, onb, pinned)
    for rel, text in files.items():
        p = os.path.join(docs, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            fh.write(text)
    return json.loads(files["api/v1/proposals.json"])
