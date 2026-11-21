"""Offline checks of the declarative scorecard corrections (tools/scorecard_corrections.json) against the built site (0 network
calls). Run after tools/build_site.py:  python3 tools/test_scorecard_corrections.py"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import scorecard_corrections as CORR  # noqa: E402
import control_diff as CD  # noqa: E402
import build_site as BS  # noqa: E402


def j(*p):
    return json.load(open(os.path.join(ROOT, "docs", *p), encoding="utf-8"))


CARDS = {c["slug"]: c for c in j("api", "v1", "scorecards.json")["protocols"]}
UNRES = sorted(s for s, c in CORR.data()["protocols"].items() if c["status"] == "unresolved")


class Registry(unittest.TestCase):
    def test_the_registry_is_valid_and_index_json_carries_it(self):
        self.assertEqual(CORR.check(), [])
        r = subprocess.run([sys.executable, "-B", os.path.join(HERE, "apply_scorecard_corrections.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_six_unresolved_protocols(self):
        self.assertEqual(UNRES, ["concrete", "lagoon", "metamorpho-re7-weth-vs-re7-usdt", "renzo-protocol-ezeth", "tori-finance", "whales-market"])


class Grades(unittest.TestCase):
    def test_totals(self):
        from collections import Counter
        self.assertEqual(Counter(c["grade"] for c in CARDS.values()),
                         Counter({"aligned": 126, "protective": 7, "delta": 49, "recent_change": 1, "unresolved": 6, "observed": 127}))

    def test_unresolved_is_neither_delta_nor_aligned(self):
        for s in UNRES:
            c = CARDS[s]
            self.assertEqual(c["grade"], "unresolved", s)
            parity = next(f for f in c["factors"] if f["key"] == "parity")
            self.assertEqual(parity["state"], "n", s)                     # hollow: never weak, never strong
            svg = open(os.path.join(ROOT, "docs", "badges", f"{s}.svg"), encoding="utf-8").read()
            self.assertNotIn("Parameter Delta", svg, s)
            self.assertNotIn("Aligned", svg, s)
            page = open(os.path.join(ROOT, "docs", "protocols", s, "index.html"), encoding="utf-8").read()
            self.assertNotIn('<span class="badge delta">', page, s)
            self.assertNotIn('data-cta="seal_wd"', page, s)
        self.assertIn("Docs updated · pending chain read", CARDS["tori-finance"].get("subPill", ""))


    def test_changed_recently_is_neither_delta_nor_aligned(self):
        c = CARDS["yearn-v3"]
        self.assertEqual((c["grade"], c["gradeLabel"]), ("recent_change", "CHANGED RECENTLY"))
        parity = next(f for f in c["factors"] if f["key"] == "parity")
        self.assertEqual(parity["state"], "n")
        self.assertIn("re-checked after 72 hours", parity["value"])
        svg = open(os.path.join(ROOT, "docs", "badges", "yearn-v3.svg"), encoding="utf-8").read()
        self.assertIn("Changed Recently · Re-Check Pending", svg)
        self.assertNotIn("Parameter Delta", svg)
        page = open(os.path.join(ROOT, "docs", "protocols", "yearn-v3", "index.html"), encoding="utf-8").read()
        self.assertNotIn('<span class="badge delta">', page)
        self.assertNotIn('data-cta="seal_wd"', page)
        self.assertIn("re-checked after 72 hours", page)
        meth = open(os.path.join(ROOT, "docs", "methodology", "index.html"), encoding="utf-8").read()
        self.assertIn(CORR.recent_change_rule(), meth)

    def test_neutral_protocols_never_show_a_delta_status_anywhere(self):
        wallet = j("api", "v1", "wallet-tokens.json")["protocols"]
        for s in UNRES + ["yearn-v3"]:
            if s in wallet:
                self.assertIn(wallet[s]["status"], ("UNRESOLVED", "CHANGED RECENTLY"), s)
            prot = next(p for p in j("api", "v1", "protocols.json")["protocols"] if p["slug"] == s)
            self.assertIn(prot["badge"]["tier"], ("unresolved", "docs_updated", "recent_change"), s)


class Breakdown(unittest.TestCase):
    def test_the_four_way_breakdown_of_the_56_flagged_comparisons(self):
        self.assertEqual(CORR.breakdown(), {"clearWeaker": 16, "needsExplanation": 17, "bookkeeping": 13, "unresolved": 10})
        self.assertEqual(j("api", "v1", "scorecards.json")["findingBreakdown"], CORR.breakdown())
        flagged = sorted(s for s, c in CARDS.items() if c.get("findingClass"))
        self.assertEqual(len(flagged), 56)
        self.assertTrue(all(CARDS[s]["grade"] in ("delta", "unresolved", "recent_change") for s in flagged))

    def test_no_adverse_claim_on_home_radar_scorecards_scan_curators(self):
        for page in (("index.html",), ("radar", "index.html"), ("scorecards", "index.html"), ("scan", "index.html"),
                     ("curators", "index.html"), ("miniapp", "index.html")):
            t = open(os.path.join(ROOT, "docs", *page), encoding="utf-8").read()
            for bad in ("56 adverse", "Adverse: chain looser than docs", "verified adverse", "Verified Adverse", "ADVERSE DELTA", "ADVERSE GAP"):
                self.assertNotIn(bad, t, (page, bad))
        radar = open(os.path.join(ROOT, "docs", "radar", "index.html"), encoding="utf-8").read()
        self.assertIn("16 clear cases where the chain looks weaker than documented", radar)


class Upgradeability(unittest.TestCase):
    def test_a_not_a_proxy_target_is_never_labelled_upgradeable(self):
        import scorecard as SC
        idx = j("api", "v1", "index.json")
        hit = {BS.protocol_slug(e["protocol"]) for e in idx["entries"] if SC._target_not_proxy(e, str(e.get("onchain_observed") or ""))}
        self.assertIn("bio-protocol", hit)
        for s in hit:
            up = next(f for f in CARDS[s]["factors"] if f["key"] == "upgrade")
            self.assertFalse(up["value"].startswith("Upgradeable"), (s, up["value"]))
        bio = next(f for f in CARDS["bio-protocol"]["factors"] if f["key"] == "upgrade")
        self.assertEqual(bio["value"], "BIO token contract is not a proxy (non-upgradeable); one MINTER_ROLE holder is an ERC-1967 Wormhole NttManager proxy")


class Polish(unittest.TestCase):
    def test_first_sentence_keeps_a_semicolon_inside_parentheses(self):
        t = "docs.obol.org (token distribution; OBOL token): 'The total supply is capped at 500 million tokens.' / more"
        self.assertIn("capped at 500 million tokens", CD.first_sentence(t))
        self.assertEqual(CD.first_sentence("A b; c d."), "A b;")
        obol = open(os.path.join(ROOT, "docs", "protocols", "obol-network", "index.html"), encoding="utf-8").read()
        self.assertIn("The total supply is capped at 500 million tokens.", obol)

    def test_upshift_lead_headline_sits_above_its_scope_sentence(self):
        page = open(os.path.join(ROOT, "docs", "protocols", "upshift", "index.html"), encoding="utf-8").read()
        lead = page.find("<strong>Vault ProxyAdmin multisig: docs state generally 4 of 6, the Safe is 2-of-3</strong> "
                         '<span class="wd-block mono">(#26,441,165)</span>')
        self.assertGreater(lead, 0)
        self.assertLess(lead, page.find('data-wd-scope>Upshift describes the ProxyAdmin Safe as generally 4-of-6'))


class Wording(unittest.TestCase):
    def test_no_aggregate_overstatement(self):
        self.assertNotIn("across control surfaces", json.dumps(j("api", "v1", "scorecards.json")))

    def test_headlines_lead_with_their_pinned_blocks(self):
        for s, c in CORR.data()["protocols"].items():
            if c.get("headline"):
                self.assertEqual(CARDS[s]["finding"], f'{c["headline"]} (#{c["pinnedBlock"]:,})', s)
                self.assertLessEqual(len(c["summaryShort"]), 90, s)
                self.assertEqual(CARDS[s]["summary_short"], c["summaryShort"], s)

    def test_40_acres_is_never_called_a_vault(self):
        page = open(os.path.join(ROOT, "docs", "protocols", "40-acres-base", "index.html"), encoding="utf-8").read()
        for bad in ("Lending vault proxy", "40 Acres vault proxy", "lending vault (UUPS)"):
            self.assertNotIn(bad, page)
            self.assertNotIn(bad, json.dumps(j("api", "v1", "lookup.json")))
        self.assertIn("AERO USDC Loan", page)

    def test_a_parameter_delta_always_leads_what_differs(self):
        sp = BS.site_protocols(j("api", "v1", "index.json"), BS.load_pinned())
        for v in sp.values():
            wd = CD.what_differs(v["entries"])
            if wd and any(c["classification"] == "parameter_delta" for c in wd["changed"]):
                self.assertEqual(wd["changed"][0]["classification"], "parameter_delta", v["slug"])


if __name__ == "__main__":
    unittest.main()
