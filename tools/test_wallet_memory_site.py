"""Wallet memory release, site copy: the /privacy/ summary sentence and the two section paragraphs (263, 1089 and 647
characters, word for word), the root search-engine verification files (exact bytes, also in every staging build), and the
MCP 0.1.8 registry and README copy.

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

SUMMARY_QUALIFIER = ("Two things go further and have their own sections below: if your agent uses the wallet memory tools, Pacta stores what it "
                     "saves under its wallet address; and a record of each API and MCP call, without wallet or IP address, goes to our "
                     "analytics provider, Keewano.")
WALLET_MEMORY = ("If your agent uses the remember tool, Pacta stores what it saves: contract addresses, block numbers and your notes, "
                 "together with your wallet address, the time of each save and the time of your latest recall. No other wallet can read it. "
                 "Pacta reads it to answer your own later calls, such as what changed since a block. We do not share it, sell it, score it "
                 "or trade on it. The forget tool erases one item or everything saved under your wallet at once. Backup copies kept by our "
                 "storage provider, Cloudflare, expire within 30 days. The data is encrypted at rest, and Cloudflare holds the keys. "
                 "Payments are separate. If your agent pays for a call, our payment record keeps the paying wallet's address, the "
                 "transaction, the amount and the time, and the payment itself stays on the public Base chain. The forget tool does not "
                 "remove a payment. A payment record does not hold what your agent saved. It holds a one-way fingerprint of the paid "
                 "request, kept so that a retry after a lost reply gets its answer without paying again and so that the payment cannot be "
                 "used for a different request.")
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
GSC = ("google9232d852c0706689.html", b"google-site-verification: google9232d852c0706689.html")
BING = ("BingSiteAuth.xml", b'<?xml version="1.0"?>\n<users>\n\t<user>E636BB57E9F39AD391DCAC0C3B6BEAB7</user>\n</users>\n')


def read(*p, mode="r"):
    with open(os.path.join(ROOT, *p), mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
        return fh.read()


class PrivacyParagraphs(unittest.TestCase):
    def test_exact_lengths(self):
        self.assertEqual(len(SUMMARY_QUALIFIER), 263)
        self.assertEqual(len(WALLET_MEMORY), 1089)
        self.assertEqual(len(CALL_ANALYTICS), 647)
        self.assertEqual(BS.PRIVACY_SUMMARY_QUALIFIER, SUMMARY_QUALIFIER)
        self.assertEqual(BS.PRIVACY_WALLET_MEMORY, WALLET_MEMORY)
        self.assertEqual(BS.PRIVACY_CALL_ANALYTICS, CALL_ANALYTICS)

    def test_summary_sentence_once_between_the_first_two_sentences(self):
        t = read("docs", "privacy", "index.html")
        self.assertEqual(len(re.findall(r"data-privacy-summary-gate2", t)), 1)
        m = re.findall(r'<section class="memo-sec" id="summary"><h2>Summary</h2><p>Pacta has no user accounts\. First-party telemetry '
                       r'stores aggregate counts only \(zero raw IP addresses\)\. <span data-privacy-summary-gate2>([^<]*)</span> On the '
                       r'public production domains ', t)
        self.assertEqual(len(m), 1)
        self.assertEqual(html.unescape(m[0]), SUMMARY_QUALIFIER)
        self.assertEqual(len(html.unescape(m[0])), 263)

    def test_rendered_once_each_in_its_own_section(self):
        t = read("docs", "privacy", "index.html")
        for attr, sid, h2, text in (("data-privacy-wallet-memory", "wallet-memory", "Wallet memory (remember and forget)", WALLET_MEMORY),
                                    ("data-privacy-call-analytics", "call-analytics", "Call analytics (Keewano)", CALL_ANALYTICS)):
            m = re.findall(rf'<section class="memo-sec" id="{sid}"><h2>([^<]*)</h2><p {attr}>([^<]*)</p></section>', t)
            self.assertEqual(len(m), 1, sid)
            self.assertEqual(html.unescape(m[0][0]), h2)
            self.assertEqual(html.unescape(m[0][1]), text)
            self.assertEqual(len(html.unescape(m[0][1])), len(text))
        # the new sections sit after the first-party telemetry and X sections, before checkout; nothing else on the page moved
        ids = re.findall(r'<section class="memo-sec" id="([^"]+)">', t)
        self.assertEqual(ids, ["summary", "analytics", "x-pixel", "wallet-memory", "call-analytics", "checkout", "checks", "watch-pilot", "requests", "contact"])

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


if __name__ == "__main__":
    unittest.main()
