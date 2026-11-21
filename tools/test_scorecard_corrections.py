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
                         Counter({"aligned": 126, "protective": 7, "delta": 50, "unresolved": 6, "observed": 127}))

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
