"""Wallet memory release, site copy: the /privacy/ summary sentence and the two section paragraphs (263, 1089 and 647
characters, word for word), the root search-engine verification files (exact bytes, also in every staging build), the
MCP 0.1.8 registry and README copy, and the discovery copy (/, /mcp/, llms.txt, /llms/, llms-full.txt, smithery.yaml).

    python3 -m unittest tools/test_wallet_memory_site.py
"""
import html
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_site as BS  # noqa: E402
import build_b2a_feeds as B2A  # noqa: E402

SUMMARY_WALLET_ONLY = ("One thing goes further and has its own section below: if your agent uses the wallet memory tools, Pacta stores what it "
                       "saves under its wallet address.")
SUMMARY_QUALIFIER = ("Two things go further and have their own sections below: if your agent uses the wallet memory tools, Pacta stores what it "
                     "saves under its wallet address; and a record of each API and MCP call, without wallet or IP address, goes to our "
                     "analytics provider, Keewano.")
WALLET_MEMORY_PARAGRAPHS = BS.PRIVACY_WALLET_MEMORY_PARAGRAPHS
WALLET_MEMORY = "\n\n".join(WALLET_MEMORY_PARAGRAPHS)
CALL_ANALYTICS = ("To see how the service is used, we send a record of each call to our analytics provider, Keewano: which tool, which "
                  "chain, which listed protocol the call was about, the kind of client, the outcome and roughly how long it took. For memory "
                  "tools no protocol is sent. The record carries a label that stands for one caller for one day and is replaced at midnight "
                  "UTC. Payment requests and payments are recorded apart from that label: a request with the tool and the day, a payment "
                  "with the amount and the day. We do not send wallet addresses, IP addresses or anything a wallet has saved, and we keep no "
                  "key that would link one day's label to the next.")
LEAD = ("On-chain facts for agents that hold positions on Base and Ethereum. Ask who controls a contract, what a vault or market depends "
        "on (collateral, minter, price source, bridge verifier) and what is queued to change in its timelock. Every answer cites the "
        "contract and a block number. Save a position under your wallet and ask later what changed underneath it. No account.")
REGISTRY_DESCRIPTION = "Control, dependency and wallet-memory facts for agents on Ethereum and Base. MCP and x402."
# Discovery copy: the live remote MCP (POST /mcp tools/list, core f6877af3) and the Worker's WALLET_MEMORY_TRUST_NOTICE
REMOTE_TOOLS_16 = ["pacta_lookup_protocol", "who_controls", "pacta_check_preflight", "pacta_scan_wallet_exposure", "pacta_scan_control_plane",
                   "pacta_scan_timelock_op", "pacta_scan_proposal_diff", "pacta_get_live_timelocks", "pacta_verdict", "pacta_dossier",
                   "trace_dependencies", "remember", "what_changed_since", "forget", "pacta_submit_request", "request_feature"]
REMOTE_DOC = "11 read-only inspection tools + 3 wallet-memory tools + 2 opt-in request tools"
TRUST_NOTICE = ("Pacta keeps what your wallet saves (contract addresses, block numbers, your notes), with your wallet address and the time. "
                "No other wallet can read it. We do not sell, score or trade on it. One call ends every recall of it. What remains in backups "
                "and records, and who processes your notes, is in our privacy notice.")
HOME_AGENTS_TAB = ("Remote MCP over Streamable HTTP and a REST API: 60 requests / minute per caller; reads need no API key and no wallet. "
                   "16 remote tools: 11 read-only inspection tools (among them who_controls, 100 free calls a day, and trace_dependencies, free) "
                   "+ 3 wallet-memory tools (remember, what_changed_since and forget: free at 20 calls / minute and 100 / day per wallet, then "
                   "$0.001 USDC a call over x402; forget is always free) + 2 opt-in request tools.")
HOME_AGENTS_CARD = "Remote MCP (11 read-only + 3 wallet-memory + 2 request tools) · free daily tiers + wallet memory (20/min, 100/day per wallet)"
STALE = ("7 read-only", "1 opt-in coverage/feature request tool", "8 MCP tools", "Free during the launch", "Free read tools", "50/day live checks",
         "50 free preflight / ", "10 read-only inspection tools", "50 pre-flight and wallet-exposure checks", "Paid today: only the five",
         "wallet-exposure are free for 50", "and wallet-exposure checks include 50", "The Every scorecard")
# What wallet memory is for comes first (the two tool sentences of remember and what_changed_since)
PURPOSE = ("Save a position, an entry block or a rule under your wallet, tied to the contracts it depends on. Since a block or your last check: "
           "every control, minter, price source or bridge change under your saved positions or a list of contracts, including changes that are "
           "queued and have not run yet.")
TIER_50_100 = "include 50 free calls per day and wallet-exposure checks 100 ($0.01 USDC via x402 after)"
GSC = ("google9232d852c0706689.html", b"google-site-verification: google9232d852c0706689.html")
BING = ("BingSiteAuth.xml", b'<?xml version="1.0"?>\n<users>\n\t<user>E636BB57E9F39AD391DCAC0C3B6BEAB7</user>\n</users>\n')


def read(*p, mode="r"):
    with open(os.path.join(ROOT, *p), mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
        return fh.read()


class PrivacyParagraphs(unittest.TestCase):
    def test_exact_lengths(self):
        self.assertEqual(len(SUMMARY_WALLET_ONLY), 150)
        self.assertEqual(len(SUMMARY_QUALIFIER), 263)
        self.assertEqual(len(WALLET_MEMORY_PARAGRAPHS), 7)
        self.assertEqual(len(CALL_ANALYTICS), 647)
        self.assertEqual(BS.PRIVACY_SUMMARY_WALLET_ONLY, SUMMARY_WALLET_ONLY)
        self.assertEqual(BS.PRIVACY_SUMMARY_QUALIFIER, SUMMARY_QUALIFIER)
        self.assertEqual(BS.PRIVACY_WALLET_MEMORY, WALLET_MEMORY)
        self.assertEqual(BS.PRIVACY_CALL_ANALYTICS, CALL_ANALYTICS)

    def test_summary_sentence_once_between_the_first_two_sentences(self):
        t = read("docs", "privacy", "index.html")
        self.assertEqual(len(re.findall(r"data-privacy-summary-gate2", t)), 1)
        m = re.findall(r'<section class="memo-sec" id="summary"><h2>Summary</h2><p>Pacta has no user accounts\. First-party telemetry '
                       r'stores counts and the few details named below \(zero raw IP addresses\)\. <span data-privacy-summary-gate2>([^<]*)</span> On the '
                       r'public production domains ', t)
        self.assertEqual(len(m), 1)
        self.assertEqual(html.unescape(m[0]), SUMMARY_WALLET_ONLY)
        self.assertEqual(len(html.unescape(m[0])), 150)

    def test_rendered_once_each_in_its_own_section(self):
        t = read("docs", "privacy", "index.html")
        sec = re.findall(r'<section class="memo-sec" id="wallet-memory"><h2>([^<]*)</h2>(.*?)</section>', t, re.S)
        self.assertEqual(len(sec), 1, "wallet-memory")
        self.assertEqual(html.unescape(sec[0][0]), "Wallet memory (remember and forget)")
        ps = [html.unescape(x) for x in re.findall(r'<p data-privacy-wallet-memory>([^<]*)</p>', sec[0][1])]
        self.assertEqual(tuple(ps), WALLET_MEMORY_PARAGRAPHS)
        self.assertNotIn("[CHANGE", t)
        self.assertNotIn('id="call-analytics"', t)
        self.assertNotIn('data-privacy-call-analytics', t)
        self.assertNotIn('Keewano', t)
        m_pa = re.findall(r'<p data-privacy-provider-analytics>([^<]*)</p>', t)
        self.assertEqual(len(m_pa), 1)
        self.assertEqual(html.unescape(m_pa[0]), BS.PRIVACY_PROVIDER_ANALYTICS)
        # wallet-memory sits after the first-party telemetry and X sections, before checkout; call-analytics stays off while KEEWANO_ENABLED == "0"
        ids = re.findall(r'<section class="memo-sec" id="([^"]+)">', t)
        self.assertEqual(ids, ["summary", "analytics", "x-pixel", "wallet-memory", "checkout", "checks", "watch-pilot", "requests", "contact"])

    def test_privacy_page_is_a_rebuild_of_the_sources(self):
        self.assertEqual(read("docs", "privacy", "index.html"), BS.privacy_page(json.loads(read("docs", "api", "v1", "index.json"))))


class RootVerificationFiles(unittest.TestCase):
    def test_exact_bytes(self):
        for name, data in (GSC, BING):
            self.assertEqual(read("docs", name, mode="rb"), data, name)
        self.assertEqual(len(GSC[1]), 53)
        self.assertEqual(len(BING[1]), 86)

    def test_stage_site_leaves_the_gsc_file_alone(self):
        # stage_site rewrites *.html for a sub-path mount; the GSC file has no head, body or link, so every rule is a no-op on it
        import tempfile
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as d:
            with open(os.path.join(d, GSC[0]), "wb") as fh:
                fh.write(GSC[1])
            BS.stage_site(d, "/website-test")
            with open(os.path.join(d, GSC[0]), "rb") as fh:
                self.assertEqual(fh.read(), GSC[1])


class Mcp018Copy(unittest.TestCase):
    def test_registry_and_readmes(self):
        self.assertEqual(len(LEAD), 368)
        self.assertEqual(len(REGISTRY_DESCRIPTION), 90)
        for f in ("server.json", "server.remote.json"):
            doc = json.loads(read("packages", "mcp-server", f))
            self.assertEqual((doc["version"], doc["description"]), ("0.1.8", REGISTRY_DESCRIPTION), f)
        pkg = json.loads(read("packages", "mcp-server", "package.json"))
        self.assertEqual((pkg["version"], pkg["private"]), ("0.1.8", True))
        for f in (("README.md",), ("packages", "mcp-server", "README.md")):
            t = read(*f)
            self.assertEqual(t.count(LEAD), 1, f)
            self.assertNotIn("On-chain control facts for agents on Base and Ethereum.", t)
            self.assertNotIn("No scores.", t)



def text_of(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


class DiscoveryCopy(unittest.TestCase):
    def test_inventory_and_trust_notice(self):
        self.assertEqual(B2A.REMOTE_TOOLS, REMOTE_TOOLS_16)
        self.assertEqual((len(B2A.REMOTE_READ_ONLY_TOOLS), len(B2A.WALLET_MEMORY_TOOLS), len(B2A.REMOTE_TOOLS)), (11, 3, 16))
        self.assertEqual(B2A.WALLET_MEMORY_TOOLS, ["remember", "what_changed_since", "forget"])
        self.assertEqual((B2A.REMOTE_TOOLS_DOC, B2A.LLMS_REMOTE_TOOLS_DOC, B2A.LLMS_REMOTE_TOOLS), (REMOTE_DOC, REMOTE_DOC, REMOTE_TOOLS_16))
        self.assertEqual(B2A.STDIO_TOOLS_DOC, "14 read-only inspection tools + 2 opt-in request tools")
        self.assertEqual(len(TRUST_NOTICE), 316)
        self.assertEqual(B2A.WALLET_MEMORY_TRUST_NOTICE, TRUST_NOTICE)
        self.assertEqual([(p, u) for p, u, _ in B2A.X402_MEMORY_ENDPOINTS], [("/v1/x402/remember", "0.001"), ("/v1/x402/what-changed-since", "0.001")])
        self.assertEqual(len(B2A.X402_ENDPOINTS), 5)

    def test_mcp_page(self):
        t = read("docs", "mcp", "index.html")
        self.assertEqual(t, BS.mcp_page(json.loads(read("docs", "api", "v1", "index.json"))))
        self.assertEqual(t.count('data-mcp-tier>16 MCP tools · free read &amp; wallet memory</span>'), 1)
        m = re.search(r'<section class="memo-sec" id="tools"><h2>([^<]*)</h2><ul>(.*?)</ul>', t)
        self.assertEqual(html.unescape(m.group(1)), f"Tools ({REMOTE_DOC})")
        self.assertEqual(re.findall(r"<li><code>([a-z_]+)</code>", m.group(2)), REMOTE_TOOLS_16)
        rows = re.findall(r'<tr><td class="nowrap"><code>POST (/v1/x402/[a-z-]+)</code></td><td class="nowrap num">\$([0-9.]+)</td>',
                          re.search(r'<section class="memo-sec" id="x402">.*?</table>', t, re.S).group(0))
        self.assertEqual(rows, [("/v1/x402/verdict", "0.02"), ("/v1/x402/dossier", "0.05"), ("/v1/x402/wallet-exposure", "0.05"), ("/v1/x402/calldata-sim", "0.25"),
                                ("/v1/x402/deep-scan", "9.00"), ("/v1/x402/remember", "0.001"), ("/v1/x402/what-changed-since", "0.001")])
        memory = re.findall(r'<p class="lede" data-mcp-memory>(.*?)</p>', t)
        self.assertEqual(len(memory), 1)
        self.assertEqual(re.findall(r"<span data-trust-notice>([^<]*)</span>", memory[0]), [html.escape(TRUST_NOTICE)])
        self.assertIn('<a href="../privacy/">Privacy</a>', memory[0])
        self.assertTrue(text_of(memory[0]).startswith("Wallet memory (remember, what_changed_since, forget): " + PURPOSE
                                                      + " Free on MCP and POST /v1/memory/* at 20 calls per minute"), text_of(memory[0])[:300])
        for s in ("20 calls per minute and 100 calls per day per wallet", "$0.001 USDC each on Base", "60 calls per minute, no daily cap", "forget is always free",
                  "up to 200 items per wallet, notes up to 500 characters"):
            self.assertIn(s, text_of(memory[0]))
        lede = text_of(re.search(r'<p class="lede">(.*?)</p>', t).group(1))
        for s in ("who_controls (GET /v1/check), pacta_verdict, pacta_dossier and pacta_scan_wallet_exposure include 100 free calls per caller per UTC day",
                  "pacta_check_preflight includes 50", "trace_dependencies (GET /v1/trace-dependencies) are free ($0, no API key and no wallet)",
                  "the five deep /v1/x402/* routes ($0.02–$9.00 USDC) pay per call on Base"):
            self.assertIn(s, lede)

    def test_home_page(self):
        t = read("docs", "index.html")
        self.assertEqual([text_of(x) for x in re.findall(r'<p class="s" data-hiw-mcp>(.*?)</p>', t)], [HOME_AGENTS_TAB])
        self.assertEqual([text_of(x) for x in re.findall(r'<p class="s" style="margin-top:12px" data-agents-mcp>(.*?)</p>', t)], [HOME_AGENTS_CARD])
        self.assertEqual(len(re.findall(r'data-x402-route="', t)), 5)   # the x402 strip keeps its 5 routes
        self.assertIn("<li>50 free preflight and 100 free wallet-exposure checks a day, then $0.01 a call over x402</li>", t)

    def test_llms_texts(self):
        for f in (("docs", "llms.txt"), ("docs", "llms-full.txt")):
            lines = read(*f).splitlines()
            i = lines.index("- " + B2A.LLMS_WHO_CONTROLS_DOC)
            self.assertEqual(lines[i + 1:i + 3], ["- " + B2A.LLMS_TRACE_DEPENDENCIES_DOC, "- " + B2A.LLMS_WALLET_MEMORY_DOC], f)
            self.assertIn(", ".join(REMOTE_TOOLS_16) + " (who_controls also answers as pacta_who_controls_contract).", read(*f))
            x402 = next(k for k, l in enumerate(lines) if l.startswith("## x402 "))   # the paid memory doors sit in the x402 section
            end = next((k for k in range(x402 + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
            self.assertIn("- " + B2A.LLMS_X402_MEMORY_DOC, lines[x402 + 1:end], f)
            self.assertEqual(read(*f).count(TRUST_NOTICE), 1, f)
        self.assertTrue(B2A.LLMS_WALLET_MEMORY_DOC.endswith(" " + TRUST_NOTICE))
        self.assertEqual(B2A.WALLET_MEMORY_PURPOSE, PURPOSE)
        self.assertTrue(B2A.LLMS_WALLET_MEMORY_DOC.startswith("Wallet memory (remember, what_changed_since, forget): " + PURPOSE
                                                              + " Free over MCP and POST https://"))
        page = html.unescape(read("docs", "llms", "index.html"))
        for x in (B2A.LLMS_TRACE_DEPENDENCIES_DOC, B2A.LLMS_WALLET_MEMORY_DOC, B2A.LLMS_X402_MEMORY_DOC):
            self.assertIn(x, page)

    def test_smithery(self):
        t = read("smithery.yaml")
        self.assertIn("#      (16 tools: 11 read-only inspection tools led by pacta_lookup_protocol, who_controls and trace_dependencies + 3 wallet-memory tools\n"
                      "#      remember, what_changed_since, forget + 2 opt-in request tools request_feature, pacta_submit_request; free read and wallet-memory tiers,\n"
                      "#      no API key; $0.001 USDC paid memory overflow on Base; forget always free). Register it as an external\n", t)
        self.assertIn("Streamable HTTP at https://api.pacta.wtf/mcp", t)
        self.assertIn("Scans are free; pre-flight checks include 50 free calls per caller per UTC day, then $0.01 USDC per call via x402 on Base.", t)

    def test_shared_call_sites(self):
        self.assertIn("<p>16 MCP tools (" + REMOTE_DOC + ") over Streamable HTTP", read("docs", "404.html"))
        self.assertIn("pre-flight checks (<code>/v1/check/preflight</code>) include 50 free calls per day and wallet-exposure checks 100",
                      read("docs", "request", "index.html"))
        for f in (("docs", "mcp.json"), ("docs", ".well-known", "mcp.json")):
            doc = json.loads(read(*f))
            self.assertEqual((doc["transport"]["tools"], doc["toolSummary"]["remote"]), (REMOTE_TOOLS_16, REMOTE_DOC), f)
        for f in (("docs", "agent.json"), ("docs", ".well-known", "agent.json")):
            self.assertEqual(json.loads(read(*f))["pricing"]["note"], B2A.FREE_LAUNCH_NOTE, f)
        self.assertIn("/v1/check/wallet-exposure for 100", B2A.FREE_LAUNCH_NOTE)
        skill = read("docs", "SKILL.md")
        self.assertIn(", ".join(f"`{n}`" for n in REMOTE_TOOLS_16), skill)
        self.assertIn("/v1/check/wallet-exposure` (100 free calls per caller per UTC day", skill)

    def test_about_methodology_terms_free_tiers(self):
        for f in (("docs", "about", "index.html"), ("docs", "methodology", "index.html")):
            self.assertEqual(read(*f).count("pre-flight checks (<code>/v1/check/preflight</code>) " + TIER_50_100), 1, f)
        terms = read("docs", "terms", "index.html")
        self.assertEqual(terms.count("public documentation. Every scorecard, public JSON feed and remote MCP read tool stays free; "
                                     "pre-flight checks " + TIER_50_100), 1)

    def test_no_stale_remote_counts(self):
        for f in (("docs", "index.html"), ("docs", "mcp", "index.html"), ("docs", "llms.txt"), ("docs", "llms", "index.html"), ("docs", "llms-full.txt"),
                  ("smithery.yaml",), ("docs", "SKILL.md"), ("docs", "404.html"), ("docs", "request", "index.html"), ("docs", ".well-known", "mcp.json"),
                  ("docs", ".well-known", "agent.json"), ("docs", "about", "index.html"), ("docs", "methodology", "index.html"),
                  ("docs", "terms", "index.html")):
            t = read(*f)
            self.assertEqual([s for s in STALE if s in t], [], f)


if __name__ == "__main__":
    unittest.main()
