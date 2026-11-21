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
from collections import Counter as Counter_  # noqa: E402
# the verifier's rulings wording, as copied verbatim into the registry (headline, pinned block, scope, evidence caption)
RULINGS_WORDING = {s: {"headline": c["headline"], "pinnedBlock": c["pinnedBlock"], "scope": c.get("explanatorySentence"),
                       "evidenceCaption": c.get("evidenceCaption")}
                   for s, c in CORR.data()["protocols"].items() if c.get("rulingsSource")}
UNRES = sorted(s for s, c in CORR.data()["protocols"].items() if c["status"] == "unresolved")


class Registry(unittest.TestCase):
    def test_the_registry_is_valid_and_index_json_carries_it(self):
        self.assertEqual(CORR.check(), [])
        r = subprocess.run([sys.executable, "-B", os.path.join(HERE, "apply_scorecard_corrections.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_eleven_unresolved_protocols(self):
        self.assertEqual(UNRES, ["concrete", "hakka-finance", "infinifi", "lagoon", "metamorpho-re7-weth-vs-re7-usdt", "odyssey-finance",
                                 "renzo-protocol-ezeth", "seamless-protocol-base", "taiko-bridge", "whales-market", "yo-protocol"])


class Grades(unittest.TestCase):
    def test_totals(self):
        from collections import Counter
        self.assertEqual(Counter(c["grade"] for c in CARDS.values()),
                         Counter({"aligned": 126, "protective": 7, "delta": 43, "recent_change": 1, "docs_updated": 1, "unresolved": 11, "observed": 127}))

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
        self.assertEqual(CARDS["tori-finance"]["grade"], "docs_updated")      # v6 A8: its own first-class status


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
        self.assertEqual(CORR.breakdown(), {"reviewed": 56, "delta": 43, "clearWeaker": 16, "realDifference": 16, "bookkeeping": 11,
                                            "recentChange": 1, "docsUpdated": 1, "unresolved": 11})
        self.assertEqual(j("api", "v1", "scorecards.json")["findingBreakdown"], CORR.breakdown())
        deltas = sorted(s for s, c in CARDS.items() if c.get("deltaSubcategory"))
        self.assertEqual(len(deltas), 43)
        self.assertTrue(all(CARDS[s]["grade"] == "delta" for s in deltas))

    def test_no_adverse_claim_on_home_radar_scorecards_scan_curators(self):
        for page in (("index.html",), ("radar", "index.html"), ("scorecards", "index.html"), ("scan", "index.html"),
                     ("curators", "index.html"), ("miniapp", "index.html")):
            t = open(os.path.join(ROOT, "docs", *page), encoding="utf-8").read()
            for bad in ("56 adverse", "Adverse: chain looser than docs", "verified adverse", "Verified Adverse", "ADVERSE DELTA", "ADVERSE GAP"):
                self.assertNotIn(bad, t, (page, bad))
        radar = open(os.path.join(ROOT, "docs", "radar", "index.html"), encoding="utf-8").read()
        self.assertIn(CORR.breakdown_text(), radar)


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


NEUTRAL7 = ["concrete", "lagoon", "renzo-protocol-ezeth", "whales-market", "metamorpho-re7-weth-vs-re7-usdt", "tori-finance", "yearn-v3"]


def page(slug):
    return open(os.path.join(ROOT, "docs", "protocols", slug, "index.html"), encoding="utf-8").read()


class V4(unittest.TestCase):
    def test_1_no_seal_prompt_on_neutral_pages(self):
        for s in NEUTRAL7:
            t = page(s)
            for bad in ('id="seal-cta"', "Fixed this gap?", "Book $99 seal", 'data-cta="seal_wd"'):
                self.assertNotIn(bad, t, (s, bad))
            self.assertIn('id="issuer-clearance"', t, s)                      # the free notice and dossier path remain
        self.assertIn('id="seal-cta"', page("usual-money-usd0-usd0"))           # a Delta page keeps the seal

    def test_2_record_cards_carry_the_scoped_wording(self):
        import html as H
        want = {"concrete-vault-owner-safe-1of2-s20": ("concrete", "ctDeltaWeETH: owner, VAULT_MANAGER and factory-manager roles share a 1-of-2 Safe; single-key full control or draining is not established"),
                "lagoon-vault-beacon-upgrade-delay-s29": ("lagoon", "Legacy cbBTC vault: immediate beacon upgrades; coverage by the documented 24-hour Opt-in delay is unverified"),
                "renzo-ezeth-deposit-queue-fee-s29": ("renzo-protocol-ezeth", "DepositQueue fee parameter: 10,000 bps; effective reward fee and onward distribution are not verified"),
                "renzo-ezeth-deposit-queue-fee": ("renzo-protocol-ezeth", "DepositQueue fee parameter at earlier block #26,401,725: 1,500 bps; effective reward fee and onward distribution are not verified"),
                "whales-market-upgradeability-s28": ("whales-market", "Sampled Whales Market proxy is upgradeable; coverage by the pre-market escrow immutability promise is unverified"),
                "metamorpho-re7-weth-guardian-parity": ("metamorpho-re7-weth-vs-re7-usdt", "Re7 WETH has no guardian; Re7 USDT has an Aragon guardian — no promise of matching configurations was verified"),
                "tori-trusd-timelock-admin-undocumented-timelock-s32": ("tori-finance", "trUSD TIMELOCK_ADMIN_ROLE: current documentation names the same 24-hour controller (0xcd3c…667b) as the retained observation"),
                "yearn-v3-ychad-safe-signers-s28": ("yearn-v3", "yChad governance Safe: 6-of-9 threshold retained; signer 0x6F2A…eAD6 rotated to 0x3839…a7F7 41h before pin (docs not yet updated)")}
        for rid, (s, h2) in want.items():
            t = page(s)
            card = t[t.index(f'<article class="memo-sec" id="{rid}">'):]
            card = card[:card.index("</article>")]
            self.assertIn(f"<h2>{H.escape(h2, quote=False)}</h2>", card, rid)
            self.assertNotIn('<span class="badge delta">', card, rid)            # never a Delta pill (both Renzo records included)
        for s, gone in (("lagoon", "Immediate beacon upgrades vs 24h wait"), ("renzo-protocol-ezeth", "100% vs 10%"), ("renzo-protocol-ezeth", "15% vs 10%"),
                        ("whales-market", "docs describe it as immutable"), ("metamorpho-re7-weth-vs-re7-usdt", "documented: Re7 USDT"),
                        ("tori-finance", "a second ToriTimelock, not the documented timelock"), ("tori-finance", "is the timelock the roles page names;"), ("yearn-v3", "documented signer 0x6F2A…eAD6 is no longer an owner")):
            self.assertNotIn(gone, page(s), (s, gone))
        self.assertIn("<b>Sister vault reference.</b>", page("metamorpho-re7-weth-vs-re7-usdt"))
        self.assertIn("21 November 2026", page("tori-finance"))

    def test_3_matched_lists_only_aligned_or_protective_records(self):
        idx = {e["id"]: e for e in j("api", "v1", "index.json")["entries"]}
        import re
        for s in CARDS:
            t = open(os.path.join(ROOT, "docs", "protocols", s, "index.html"), encoding="utf-8").read()
            box = re.search(r'data-what-differs>.*?</(?:section|div)>', t, re.S)
            if box and "Matched" in box.group(0):
                self.assertIn("data-wd-matched", box.group(0), s)
        self.assertNotIn("data-wd-matched", page("tori-finance"))
        self.assertNotIn('<p class="wd-l">Matched</p>', page("tori-finance"))
        for it in j("api", "v1", "lookup.json")["items"]:
            for m in ((it.get("whatDiffers") or {}).get("matched") or []):
                self.assertIn(idx[m["recordId"]]["classification"], ("aligned_baseline", "protective_delta"), (it.get("slug"), m))

    def test_4_evidence_and_x_feed_bind_to_the_lead_record(self):
        idx = {e["id"]: e for e in j("api", "v1", "index.json")["entries"]}
        feed = {i["slug"]: i for i in j("api", "v1", "x-feed.json")["items"] if i["kind"] != "radar_timelock"}
        reg = CORR.data()["protocols"]
        self.assertEqual(len(reg), 28)   # v7: cian-yield-layer and pickle carry scoped timelock rows; v8: bedrock-unibtc emergency
        for s, c in reg.items():
            r = idx[c["leadRecord"]]
            ev = CARDS[s]["evidence"]
            self.assertEqual((ev["recordId"], ev["block"], ev["blockHash"], ev["baseEasUid"]),
                             (r["id"], int(r["block_number"]), r["block_hash"], r.get("base_eas_uid")), s)
            self.assertEqual((feed[s]["recordId"], feed[s]["pinnedBlock"], feed[s]["blockHash"], feed[s]["easUid"]),
                             (r["id"], int(r["block_number"]), r["block_hash"], r.get("base_eas_uid")), s)
        self.assertEqual(CARDS["renzo-protocol-ezeth"]["evidence"]["block"], 26448221)
        self.assertEqual(CARDS["f-x-protocol-v2"]["evidence"]["recordId"], "f-x-protocol-v2-router-owner-safe-s29")

    def test_5_yearn_rotation_provenance_and_overdue_copy(self):
        rc = CARDS["yearn-v3"]["recentChange"]
        self.assertEqual((rc["rotationBlock"], rc["rotationTxHash"], rc["rotationTimestampIso"], rc["hoursBeforePin"], rc["recheckDueIso"], rc["recheckStatus"]),
                         (26428839, "0xf2ac69b26faa0ebcffcf6bdc8ea20263ca70331dc28336121a053b0d180b63ac", "2026-11-16T16:39:11Z", 41.22,
                          "2026-11-19T16:39:11Z", "pending_fresh_read"))
        self.assertEqual(CARDS["yearn-v3"]["subtitle"], "Changed on chain 41h before pin (16 Nov 2026); 72h window elapsed — pending fresh chain and docs re-read")
        self.assertEqual(CARDS["yearn-v3"]["grade"], "recent_change")
        self.assertIn("never reinstates Delta", j("api", "v1", "scorecards.json")["recentChangeRule"])
        meth = open(os.path.join(ROOT, "docs", "methodology", "index.html"), encoding="utf-8").read()
        self.assertIn("never reinstates Delta", meth)

    def test_6_no_lending_vault_proxy_anywhere(self):
        import glob
        hits = [f for f in glob.glob(os.path.join(ROOT, "docs", "**", "*"), recursive=True)
                if os.path.isfile(f) and f.endswith((".html", ".json", ".txt", ".xml", ".svg", ".js")) and
                "lending vault proxy" in open(f, encoding="utf-8", errors="ignore").read().lower()]
        self.assertEqual(hits, [])

    def test_7_clearance_states_free_self_correction(self):
        import html as H
        self.assertIn(H.escape(BS.CLEARANCE_SELF_CORRECTION, quote=False), page("usual-money-usd0-usd0"))
        self.assertIn("free of charge", BS.CLEARANCE_SELF_CORRECTION)

    def test_8_bounties_page_matches_base_apart_from_asset_keys(self):
        import re
        base = subprocess.check_output(["git", "-C", ROOT, "show", "d8a1d9d050aeecd055cc05b6bfedf2bab4b35a83:docs/bounties/index.html"], text=True)
        now = open(os.path.join(ROOT, "docs", "bounties", "index.html"), encoding="utf-8").read()
        strip = lambda t: re.sub(r'\?v=[0-9a-f]+', "?v=", t)
        self.assertEqual(strip(base), strip(now))


class V5(unittest.TestCase):
    def test_r1_yearn_feed_and_card_text(self):
        y = next(i for i in j("api", "v1", "x-feed.json")["items"] if i["slug"] == "yearn-v3")
        self.assertIn("72-hour window elapsed; fresh chain and docs recheck pending.", y["mainPostText"])
        self.assertIn("72-hour window elapsed; fresh chain and docs recheck pending", y["docsSay"])
        self.assertNotIn("Re-checked after 72 hours", y["mainPostText"] + y["docsSay"])
        self.assertEqual(y["pinnedBlock"], 26441165)
        self.assertNotIn("RoleManager", y["mainPostText"] + y["chainSays"])      # the #26,401,725 observation is never pinned at #26,441,165

    def test_r2_yearn_provenance_attribution(self):
        rc = CARDS["yearn-v3"]["recentChange"]
        self.assertIn(" supplied raw receipt and block-header captures from Tenderly, PublicNode and dRPC; ", rc["provenance"])
        self.assertTrue(rc["provenance"].endswith(" independently replayed them offline"))
        self.assertEqual((rc["operators"], rc["envelopeCount"], rc["rawEnvelopesSha256"]),
                         (["tenderly", "publicnode", "drpc"], 9, "13933bfb57584f0200dc8ededbb842a27a123c5eebe31b7cb1ab72fc54150b6b"))
        self.assertNotIn("mevblocker", json.dumps(rc))

    def test_r3_no_undocumented_timelock_claim_on_tori(self):
        import glob
        hits = [f for f in glob.glob(os.path.join(ROOT, "docs", "**", "*"), recursive=True)
                if os.path.isfile(f) and f.endswith((".html", ".json", ".txt", ".xml", ".js")) and
                "timelock the documentation does not name" in open(f, encoding="utf-8", errors="ignore").read()]
        self.assertEqual(hits, [])
        self.assertIn("At the retained pin, trUSD used a different 24-hour controller from the 19 November documentation snapshot; "
                      "the roles page retrieved 21 November now names that controller, pending a fresh chain read.", page("tori-finance"))

    def test_r4_evidence_and_feed_restate_the_cited_record(self):
        idx = {e["id"]: e for e in j("api", "v1", "index.json")["entries"]}
        n = 0
        for s, c in CARDS.items():
            if not c["easAttested"]:
                continue
            ev, r = c["evidence"], idx[c["evidence"]["recordId"]]
            self.assertEqual((ev["sprint"], ev["block"], ev["blockHash"], ev["baseEasUid"]),
                             (r["sprint"], int(r["block_number"]), r["block_hash"], r.get("base_eas_uid")), s)
            n += 1
        self.assertEqual(n, 189)
        for i in j("api", "v1", "x-feed.json")["items"]:
            if i["kind"] in ("radar_timelock", "rpc_observed"):
                continue
            r = idx[i["recordId"]]
            self.assertEqual((i["sprint"], i["pinnedBlock"], i["blockHash"], i["easUid"]),
                             (r["sprint"], int(r["block_number"]), r["block_hash"], r.get("base_eas_uid")), i["feedId"])
        beefy = next(i for i in j("api", "v1", "x-feed.json")["items"] if i["slug"] == "beefy-finance-base")
        self.assertEqual((beefy["sprint"], beefy["pinnedBlock"], beefy["recordId"]),
                         (22, 58315414, "beefy-finance-base-vault-owner-timelock-zero-delay-s22"))

RULINGS = CORR.reviewed()


def visible(t):
    """Visible text of a page: scripts, styles and tags (with their attributes) removed."""
    import re
    import html as H
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    return H.unescape(re.sub(r"<[^>]+>", " ", t))


class V6(unittest.TestCase):
    # ---- C13: one table drives every count, tab, pill, sentence and feed
    def test_c13_single_table(self):
        from collections import Counter
        self.assertEqual(dict(Counter(c["grade"] for c in CARDS.values())), RULINGS["fullCatalogueCounts"])
        for s, st in RULINGS["partition"].items():
            self.assertEqual(CARDS[s]["grade"], st, s)
        for k, members in RULINGS["deltaGroups"].items():
            self.assertTrue(all(CARDS[s].get("deltaSubcategory") == k for s in members), k)
        self.assertEqual(CORR.breakdown_text(), RULINGS["homeRadarSentence"])
        for page_ in (("index.html",), ("radar", "index.html"), ("scorecards", "index.html")):
            self.assertIn(CORR.breakdown_text(), visible(open(os.path.join(ROOT, "docs", *page_), encoding="utf-8").read()), page_)

    def test_c13_tabs_equal_row_counts(self):
        import re
        want = {"delta": 43, "recent_change": 1, "docs_updated": 1, "unresolved": 11, "protective": 7, "aligned": 126, "observed": 127}
        hub = open(os.path.join(ROOT, "docs", "protocols", "index.html"), encoding="utf-8").read()
        rows = Counter_(re.findall(r'<tr data-ptier="([a-z_]+)"', hub))
        tabs = {k: int(n) for k, n in re.findall(r'data-pfilter-status="([a-z_]+)"[^>]*>[^<]+ <span class="num">\((\d+)\)', hub) if k != "all"}
        self.assertEqual(tabs, want)
        self.assertEqual(dict(rows), want)
        for page_ in (("index.html",), ("scorecards", "index.html")):
            t = open(os.path.join(ROOT, "docs", *page_), encoding="utf-8").read()
            got = {k: int(n) for k, n in re.findall(r'data-sc-f="([a-z_]+)"[^>]*>[^<]+ <span class="num">\((\d+)\)', t) if k != "all"}
            self.assertEqual(got, want, page_)
        for label in ("Deltas (43)", "Changed recently (1)", "Docs updated (1)", "Unresolved (11)"):
            self.assertIn(label, visible(hub).replace("  ", " "))

    def test_c13_neutral_pages_carry_no_delta_or_seal(self):
        for s, st in RULINGS["partition"].items():
            if st == "delta":
                continue
            t = page(s)
            for bad in ('id="seal-cta"', "Fixed this gap?", "Book $99 seal", '<span class="badge delta">', 'class="grade g-delta"',
                        "Delta: docs and chain differ", "Control-plane badge: Parameter Delta"):
                self.assertNotIn(bad, t, (s, bad))
            svg = open(os.path.join(ROOT, "docs", "badges", f"{s}.svg"), encoding="utf-8").read()
            self.assertNotIn("Parameter Delta", svg, s)
        for s in ("yo-protocol", "infinifi", "hakka-finance", "taiko-bridge", "odyssey-finance", "seamless-protocol-base"):
            w = RULINGS_WORDING[s]
            self.assertEqual(CARDS[s]["finding"], f'{w["headline"]} (#{w["pinnedBlock"]:,})', s)
            self.assertIn("Verification scope", page(s))

    def test_c13_no_stale_counts(self):
        for page_ in (("index.html",), ("radar", "index.html"), ("scorecards", "index.html"), ("scan", "index.html"),
                      ("curators", "index.html"), ("methodology", "index.html"), ("miniapp", "index.html")):
            v = visible(open(os.path.join(ROOT, "docs", *page_), encoding="utf-8").read())
            for bad in ("17 real differences", "13 bookkeeping", "10 unresolved", "Unresolved (6)", "Deltas (49)", "49 Deltas"):
                self.assertNotIn(bad, v, (page_, bad))

    # ---- A1–A8
    def test_a1_gearbox(self):
        w = RULINGS_WORDING["gearbox-v3-v3-1"]
        self.assertEqual(CARDS["gearbox-v3-v3-1"]["finding"], f'{w["headline"]} (#26,403,523)')
        q = next(f for f in CARDS["gearbox-v3-v3-1"]["factors"] if f["key"] == "quorum")
        self.assertEqual(q["value"], "InstanceManager owner Safe: 4-of-21; separate Veto Guard Safe: 4-of-12 (Ethereum block 26,403,523).")
        t = page("gearbox-v3-v3-1")
        self.assertNotIn("lowest controlling quorum: 4-of-12", t.lower())
        for k in ("LegacyTimelock", "0x1E9ec044853611F4bCD4BBcFE7657508BD1c53D3", "0xbb803559B4D58b75E12dd74641AB955e8B0Df40E", "4-of-21"):
            self.assertIn(k, t)

    def test_a2_renzo_single_pin(self):
        t = page("renzo-protocol-ezeth")
        self.assertEqual(t.count("26,433,001") + t.count("26433001"), 0)
        self.assertIn("1,500 at Ethereum block 26,401,725", t)

    def test_a3_lagoon_rows(self):
        f = {x["key"]: x for x in CARDS["lagoon"]["factors"]}
        self.assertEqual(f["upgrade"]["value"], "Upgradeable · Immediate beacon upgrades via 3-of-6 Safe (0s delay on UpgradeableBeacon; coverage by "
                                                "documented 24h Opt-in ProxyDelay unverified)")
        self.assertEqual(f["quorum"]["value"], "3-of-6 Safe (UpgradeableBeacon owner)")
        self.assertNotEqual(f["upgrade"]["state"], "n")       # the generator now reads the BeaconProxy path itself
        self.assertNotEqual(f["quorum"]["state"], "n")        # and "getThreshold() = 3 of getOwners() = 6"

    def test_a4_beefy_both_pins(self):
        sc = CARDS["beefy-finance-base"]["scopeNote"]
        self.assertIn("58,315,414", sc)
        self.assertIn("58,885,628", sc)
        self.assertIn("3-of-6 dev multisig", sc)
        self.assertEqual(next(f for f in CARDS["beefy-finance-base"]["factors"] if f["key"] == "quorum")["value"],
                         "3-of-6 dev multisig (TimelockController proposer)")

    def test_a5_fx_both_safes(self):
        q = next(f for f in CARDS["f-x-protocol-v2"]["factors"] if f["key"] == "quorum")["value"]
        self.assertIn("ProtocolTreasury EmergencySafe: 3-of-4", q)
        self.assertIn("V2 Router operational Safe: 6-of-9", q)
        sc = CARDS["f-x-protocol-v2"]["scopeNote"]
        self.assertIn("6-of-9", sc)
        self.assertIn("3-of-4 EmergencySafe", sc)

    def test_a6_no_breached_dimension_rated_strong(self):
        st = lambda s, k: next(f for f in CARDS[s]["factors"] if f["key"] == k)
        e = st("treehouse-tree-teth", "emergency")
        self.assertEqual(e["state"], "a")
        self.assertEqual(e["value"], "Immediate · TREE transfer blacklister() is a 5-of-7 Safe with 0s enforced delay (five-day timelock retained on "
                                     "TREE and tETH owner paths)")
        # the breached dimension of each weaker-protection Delta (where it is a rosette factor) is never Strong
        breached = {"treehouse-tree-teth": "emergency", "usual-money-usd0-usd0": "timelock", "inverse-finance-firm": "quorum",
                    "zircuit-staking": "quorum", "benddao-ape-staking": "timelock", "pickle": "timelock", "cian-yield-layer": "timelock",
                    "40-acres-base": "upgrade", "circle-gateway": "upgrade", "maple-finance-v2-syrup": "upgrade"}
        for s, k in breached.items():
            self.assertIn(s, RULINGS["deltaGroups"]["clear_weaker"])
            self.assertNotEqual(st(s, k)["state"], "g", (s, k))

    def test_a7_yearn(self):
        w = RULINGS_WORDING["yearn-v3"]
        self.assertEqual(CARDS["yearn-v3"]["finding"], f'{w["headline"]} (#26,441,165)')
        self.assertEqual(CARDS["yearn-v3"]["scopeNote"], w["scope"])
        y = next(i for i in j("api", "v1", "x-feed.json")["items"] if i["slug"] == "yearn-v3")
        self.assertEqual(y["summaryShort"], CARDS["yearn-v3"]["summary_short"])

    def test_a8_tori_docs_updated_and_human_captions(self):
        import glob
        w = RULINGS_WORDING["tori-finance"]
        c = CARDS["tori-finance"]
        self.assertEqual((c["grade"], c["gradeLabel"]), ("docs_updated", "DOCS UPDATED"))
        self.assertEqual(c["finding"], f'{w["headline"]} (#26,451,608)')
        t = page("tori-finance")
        self.assertIn(w["evidenceCaption"], t)
        self.assertIn("Docs updated", t)
        self.assertNotIn("Resolved by a documentation change", t)
        for f in glob.glob(os.path.join(ROOT, "docs", "protocols", "*", "index.html")):
            v = visible(open(f, encoding="utf-8").read())
            self.assertNotIn("Evidence: tori-trusd", v, f)
            self.assertNotIn("undocumented-timelock", v, f)

    # ---- B9–B12
    def test_b9_b10_leads_are_clean(self):
        import re

        def unclosed(t):
            t = re.sub(r"(?<=\w)'(?=\w)|(?<=s)'(?=\s)", "", t)     # apostrophes in words and plural possessives are not quotes
            return t.count('"') % 2 == 1 or len(re.findall(r"(?<!\w)'|'(?!\w)", t)) % 2 == 1
        self.assertEqual(CARDS["bio-protocol"]["finding"], f'{RULINGS_WORDING["bio-protocol"]["headline"]} (#26,451,608)')
        self.assertEqual(CARDS["obol-network"]["finding"], f'{RULINGS_WORDING["obol-network"]["headline"]} (#26,433,001)')
        for s, c in CARDS.items():
            for txt in (c["finding"], c["summary_short"]):
                self.assertFalse(unclosed(txt), (s, txt))
                self.assertNotRegex(txt, r"docs say .* · chain says")
                self.assertIsNone(re.search(r"(?<![0-9A-Fa-fx])\d{18,}", txt), (s, txt))
            t = open(os.path.join(ROOT, "docs", "protocols", s, "index.html"), encoding="utf-8").read()
            i = t.find("data-what-differs")
            if i >= 0:
                lead = visible(t[i:t.find("</section>", i)])
                self.assertIsNone(re.search(r"(?<![0-9A-Fa-fx])\d{18,}", lead), s)

    def test_b11_no_markdown_or_tex_in_visible_html(self):
        import glob
        import re
        for f in glob.glob(os.path.join(ROOT, "docs", "**", "*.html"), recursive=True):
            v = visible(open(f, encoding="utf-8").read())
            self.assertIsNone(re.search(r"\*\*[^*\s][^*]*\*\*", v), f)
            self.assertNotIn("$5/9$", v, f)

    def test_b12_re7_prefix_and_dashes(self):
        v = visible(page("metamorpho-re7-weth-vs-re7-usdt"))
        self.assertEqual(v.count("Sister vault reference"), 1)
        self.assertNotIn("guardian—no", v)
        self.assertIn("Aragon guardian — no promise of matching configurations was verified", v)

    # ---- E16–E18
    def test_e16_home_showcase(self):
        home = open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8").read()
        self.assertIn('data-pc-name>Usual Money (USD0 / USD0++)<', home)
        self.assertIn("0xfd7ce0f2b980da6606c8cd755da45d99f9ae4826e6df1321ff52c2b0f8e6a6c2", home)
        self.assertNotIn('data-pf-slug="yo-protocol"', home)
        self.assertNotIn(">GAP<", home)

    def test_e17_ethena(self):
        w = RULINGS_WORDING["ethena-usde-susde"]
        self.assertEqual(CARDS["ethena-usde-susde"]["finding"], f'{w["headline"]} (#26,401,638)')
        home = open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8").read()
        self.assertNotIn(">Timelock delay:", home)
        self.assertNotIn("Timelock delay: docs", home)

    def test_e18_layout_and_footnote(self):
        import glob
        css = open(os.path.join(ROOT, "docs", "styles.css"), encoding="utf-8").read()
        home = open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8").read()
        self.assertIn('placeholder="Protocol or 0x…"', home)       # v8 G3 supersedes the v6 / v7 wording
        self.assertIn('.js #how-it-works [data-tabs-stable] > [data-slot="tabs-content"][data-inactive] { display: none; }', css)
        self.assertIn("overflow-wrap: break-word; word-break: normal;", css)
        self.assertNotIn("table.radar .meta { overflow-wrap: anywhere", css)
        self.assertIn('<span class="lb-lead"><span class="dot live"', open(os.path.join(ROOT, "docs", "radar", "index.html"), encoding="utf-8").read())
        self.assertIn(".memo-meta dd .sep { display: none; }", css)
        n_rated = 0
        for f in glob.glob(os.path.join(ROOT, "docs", "protocols", "*", "index.html")):
            s = f.split(os.sep)[-2]
            has = "parity is <i>uncompared</i> for RPC-observed protocols" in open(f, encoding="utf-8").read()
            self.assertEqual(has, CARDS[s]["grade"] == "observed", s)
            n_rated += CARDS[s]["grade"] != "observed"
        self.assertEqual(n_rated, 189)



class V7(unittest.TestCase):
    def test_f1_fx_display_title(self):
        import glob
        want = "V2 Router (Diamond) owner: docs put queued transactions behind a 3-day timelock (oracle updates excepted); owner() is the 6-of-9 Safe"
        t = page("f-x-protocol-v2")
        self.assertIn(f"<h2>{want}</h2>", t.replace("&#x27;", "'"))
        hits = [f for f in glob.glob(os.path.join(ROOT, "docs", "**", "*"), recursive=True)
                if os.path.isfile(f) and f.endswith((".html", ".json", ".txt")) and
                "docs put every transaction behind a 3-day timelock" in open(f, encoding="utf-8", errors="ignore").read()]
        self.assertEqual(hits, [])

    def test_f2_no_record_citations_or_ids_in_visible_prose(self):
        import glob
        import re
        import html as H
        ids = {e["id"] for e in j("api", "v1", "index.json")["entries"]} | {"tori-finance-control-plane"}
        id_re = re.compile(r"(?<![a-z0-9-])(" + "|".join(sorted(map(re.escape, ids), key=len, reverse=True)) + r")(?![a-z0-9-])")
        for f in glob.glob(os.path.join(ROOT, "docs", "**", "*.html"), recursive=True):
            t = re.sub(r"<script.*?</script>|<style.*?</style>|<code.*?</code>|<pre.*?</pre>", " ", open(f, encoding="utf-8").read(), flags=re.S)
            v = H.unescape(re.sub(r"<[^>]+>", " ", t))
            self.assertIsNone(re.search(r"\(record\s+[a-z0-9_-]+\)", v), f)
            self.assertIsNone(id_re.search(v), f)
        # the attested record text itself is unchanged (the citation is stripped only for display)
        cap = next(e for e in j("api", "v1", "index.json")["entries"] if "(record cap-1d-timelock-min-delay-s20)" in e["onchain_observed"])
        self.assertTrue(cap)

    def _f(self, s, k):
        return next(f for f in CARDS[s]["factors"] if f["key"] == k)

    def test_f3_no_strong_freeze_from_zero_guardian_or_canceller(self):
        e = self._f("metamorpho-re7-weth-vs-re7-usdt", "emergency")
        self.assertEqual((e["state"], e["value"], e["evidenceRecordId"]),
                         ("n", "Re7 WETH has no guardian set (0x0); Re7 USDT assigns an Aragon guardian", "metamorpho-re7-weth-guardian-parity"))
        e = self._f("seamless-protocol-base", "emergency")
        self.assertEqual((e["state"], e["value"], e["evidenceRecordId"]),
                         ("n", "2-of-3 Safe holds timelock CANCELLER_ROLE; pause / freeze binding not in the published records",
                          "seamless-community-guardian-safe-2-of-3-s35"))
        # across all 56 reviewed protocols, a Strong freeze rating never rests on an unset guardian or a CANCELLER_ROLE-only record
        import re
        idx = {x["id"]: x for x in j("api", "v1", "index.json")["entries"]}
        for s in RULINGS["partition"]:
            f = self._f(s, "emergency")
            if f["state"] == "g" and f.get("evidenceRecordId"):
                t = idx[f["evidenceRecordId"]]["onchain_observed"]
                self.assertIsNone(re.search(r"guardian\(\)\s*=\s*0x0{40}\b", t), s)
                self.assertFalse("CANCELLER_ROLE" in t and not re.search(r"pause|freez|blacklist", t, re.I), s)

    def test_f4_no_floor_from_an_unattached_timelock(self):
        t = self._f("cian-yield-layer", "timelock")
        self.assertEqual((t["state"], t["value"], t["evidenceRecordId"]),
                         ("a", "No timelock in the sampled ownership path (3-of-4 Safe direct; listed 1d TimeLock not wired)",
                          "cian-yield-layer-allocation-no-timelock-s31"))
        t = self._f("pickle", "timelock")
        self.assertEqual((t["state"], t["value"], t["evidenceRecordId"]),
                         ("a", "No timelock in the sampled MasterChef path (2-of-6 Safe direct; listed 24h Timelock does not own MasterChef)",
                          "pickle-masterchef-owner-safe-no-timelock-s32"))
        t = self._f("infinifi", "timelock")
        self.assertEqual((t["state"], t["value"], t["evidenceRecordId"], t["evidenceCaption"]),
                         ("b", "Long governance timelock: 7d; Short timelock: 1d (per-surface wiring unverified)", "infinifi-long-timelock-7d-s20",
                          "Long governance timelock delay: 7 days (Short timelock: 1 day) — Ethereum block #26,425,374"))
        # no reviewed protocol's positive timelock floor is cited from a record sentence saying the timelock is not on the path
        import re
        un = re.compile(r"\bowns neither\b|\bdoes not own\b|\bis not the [\w' ()-]*?owner\b|\bnot in the (?:\w+ )*path\b|\bnot wired\b", re.I)
        for s in RULINGS["partition"]:
            f = self._f(s, "timelock")
            if f["state"] in ("g", "b") and f.get("evidence"):
                self.assertIsNone(un.search(f["evidence"]), s)

    def test_f5_curator_matrix(self):
        from collections import Counter
        m = json.load(open(os.path.join(ROOT, "data", "curator-exposure-matrix.json"), encoding="utf-8"))
        rows = m["all_55_verified_adverse_gaps"]
        self.assertEqual(len(rows), 56)
        self.assertEqual(sorted(r["slug"] for r in rows), sorted(RULINGS["partition"]))
        self.assertEqual(Counter(r["grade"] for r in rows), Counter({"DELTA": 43, "UNRESOLVED": 11, "CHANGED RECENTLY": 1, "DOCS UPDATED": 1}))
        self.assertEqual(m["all_56_reviewed_comparisons"], rows)
        raw = json.dumps(m, ensure_ascii=False)
        cur = open(os.path.join(ROOT, "docs", "curators", "index.html"), encoding="utf-8").read()
        for txt in (raw, cur):
            self.assertNotIn("Seamless Base (DELTA", txt)
            self.assertNotIn("yearn-v3-op-0x2a14", txt)
        self.assertIn("Seamless Base (UNRESOLVED: 2-of-3 Guardian Safe; retained 3-of-6 docs not verified)", raw)

        def walk(x):
            if isinstance(x, dict):
                h = x.get("clinical_brief_hook")
                if isinstance(h, str) and x.get("grade") != "DELTA":
                    for bad in ("delta", "seal", "re-verification"):
                        self.assertNotIn(bad, h.lower(), x.get("slug"))
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(m)

    def test_f6_placeholder_and_radar_wrap(self):
        home = open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8").read()
        self.assertIn('placeholder="Protocol or 0x…"', home)            # v8 G3 supersedes the v7 wording
        radar = open(os.path.join(ROOT, "docs", "radar", "index.html"), encoding="utf-8").read()
        self.assertIn("EtherfiL1SyncPoolETH.<wbr>setDelegate(<wbr>EtherFiTimelock)", radar)
        self.assertNotIn("EtherFiTimelo<wbr>", radar)


class V8(unittest.TestCase):
    def _rec(self, rid):
        return next(e for e in j("api", "v1", "index.json")["entries"] if e["id"] == rid)

    def test_g1_seamless_record_alone_never_rates_freeze(self):
        import scorecard as SC
        f = next(x for x in SC.factors([self._rec("seamless-community-guardian-safe-2-of-3-s35")], True, "unresolved") if x["key"] == "emergency")
        self.assertEqual(f["state"], "n")                         # no controller facts, no post-hoc override
        e = next(x for x in CARDS["seamless-protocol-base"]["factors"] if x["key"] == "emergency")
        self.assertEqual((e["state"], e["value"]), ("n", "2-of-3 Safe holds timelock CANCELLER_ROLE; pause / freeze binding not in the published records"))

    def test_g2_infinifi_short_timelock_suffix(self):
        import glob
        rec = self._rec("infinifi-long-timelock-7d-s20")["onchain_observed"]
        self.assertIn("0x4B174afbeD7b98BA01F50E36109EEE5e6d327c32", rec)
        ev = next(x for x in CARDS["infinifi"]["factors"] if x["key"] == "timelock")["evidence"]
        self.assertIn("0x4B17…7c32", ev)
        self.assertTrue("0x4B174afbeD7b98BA01F50E36109EEE5e6d327c32".endswith("7c32"))
        hits = [f for f in glob.glob(os.path.join(ROOT, "docs", "**", "*"), recursive=True)
                if os.path.isfile(f) and f.endswith((".html", ".json", ".txt")) and "0x4B17…e88c" in open(f, encoding="utf-8", errors="ignore").read()]
        self.assertEqual(hits, [])

    def test_g3_hero_input_room(self):
        css = open(os.path.join(ROOT, "docs", "styles.css"), encoding="utf-8").read()
        home = open(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8").read()
        self.assertIn('placeholder="Protocol or 0x…"', home)
        self.assertIn(".hero .pf-toggle-lbl, .pd-sec-scan .pf-toggle-lbl { display: none; }", css)
        self.assertIn(".hero .pf-combo > input { padding-right: 46px; }", css)
        self.assertIn(".pd-sec-scan .pf-combo > input { padding-right: 40px; }", css)
        self.assertIn('aria-label="Browse', home)                 # the chevron button keeps its accessible name

    def test_g4_bedrock_pause_never_borrows_a_later_safe(self):
        import scorecard as SC
        f = next(x for x in SC.factors([self._rec("bedrock-unibtc-secure-mint-precondition-s30")], True, "delta") if x["key"] == "emergency")
        self.assertEqual(f["state"], "n")
        self.assertNotIn("3-of-5", f["value"])
        e = next(x for x in CARDS["bedrock-unibtc"]["factors"] if x["key"] == "emergency")
        self.assertEqual((e["state"], e["value"], e["evidenceRecordId"]),
                         ("n", "PAUSER_ROLE held by 0x9251…5aaB (EIP-7702 delegated account; delegation authority not in the published records)",
                          "bedrock-unibtc-secure-mint-precondition-s30"))
        self.assertIn("PAUSER_ROLE held by 0x9251…5aaB", page("bedrock-unibtc"))

    def test_g4_no_cross_sentence_pause_quorum_in_reviewed(self):
        # every Strong freeze rating among the 56 reviewed protocols cites one sentence (or a named-holder continuation) that names
        # both the pause / freeze power and the quorum it rates
        import scorecard as SC
        for s in RULINGS["partition"]:
            e = next(x for x in CARDS[s]["factors"] if x["key"] == "emergency")
            if e["state"] != "g":
                continue
            ev = e["evidence"].split(": ", 1)[1]
            self.assertTrue(SC._EMERGENCY.search(ev) and (SC._nofs(ev) or "-of-N Safe" in e["value"]), s)

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
