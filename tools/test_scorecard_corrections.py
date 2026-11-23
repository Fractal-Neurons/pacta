"""Offline checks of the declarative scorecard corrections (tools/scorecard_corrections.json) against the built site (0 network
calls). Run after tools/build_site.py:  python3 tools/test_scorecard_corrections.py"""
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import scorecard_corrections as CORR  # noqa: E402
import control_diff as CD  # noqa: E402
import build_site as BS  # noqa: E402


def _read(*a, **k):
    with open(*a, **k) as fh:
        return fh.read()


def _load(*a, **k):
    with open(*a, **k) as fh:
        return json.load(fh)


def j(*p):
    return _load(os.path.join(ROOT, "docs", *p), encoding="utf-8")


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
            svg = _read(os.path.join(ROOT, "docs", "badges", f"{s}.svg"), encoding="utf-8")
            self.assertNotIn("Parameter Delta", svg, s)
            self.assertNotIn("Aligned", svg, s)
            page = _read(os.path.join(ROOT, "docs", "protocols", s, "index.html"), encoding="utf-8")
            self.assertNotIn('<span class="badge delta">', page, s)
            self.assertNotIn('data-cta="seal_wd"', page, s)
        self.assertEqual(CARDS["tori-finance"]["grade"], "docs_updated")      # v6 A8: its own first-class status


    def test_changed_recently_is_neither_delta_nor_aligned(self):
        c = CARDS["yearn-v3"]
        self.assertEqual((c["grade"], c["gradeLabel"]), ("recent_change", "CHANGED RECENTLY"))
        parity = next(f for f in c["factors"] if f["key"] == "parity")
        self.assertEqual(parity["state"], "n")
        self.assertIn("re-checked after 72 hours", parity["value"])
        svg = _read(os.path.join(ROOT, "docs", "badges", "yearn-v3.svg"), encoding="utf-8")
        self.assertIn("Changed Recently · Re-Check Pending", svg)
        self.assertNotIn("Parameter Delta", svg)
        page = _read(os.path.join(ROOT, "docs", "protocols", "yearn-v3", "index.html"), encoding="utf-8")
        self.assertNotIn('<span class="badge delta">', page)
        self.assertNotIn('data-cta="seal_wd"', page)
        self.assertIn("re-checked after 72 hours", page)
        meth = _read(os.path.join(ROOT, "docs", "methodology", "index.html"), encoding="utf-8")
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
            t = _read(os.path.join(ROOT, "docs", *page), encoding="utf-8")
            for bad in ("56 adverse", "Adverse: chain looser than docs", "verified adverse", "Verified Adverse", "ADVERSE DELTA", "ADVERSE GAP"):
                self.assertNotIn(bad, t, (page, bad))
        radar = _read(os.path.join(ROOT, "docs", "radar", "index.html"), encoding="utf-8")
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
        obol = _read(os.path.join(ROOT, "docs", "protocols", "obol-network", "index.html"), encoding="utf-8")
        self.assertIn("The total supply is capped at 500 million tokens.", obol)

    def test_upshift_lead_headline_sits_above_its_scope_sentence(self):
        page = _read(os.path.join(ROOT, "docs", "protocols", "upshift", "index.html"), encoding="utf-8")
        lead = page.find("<strong>Vault ProxyAdmin multisig: docs state generally 4 of 6, the Safe is 2-of-3</strong> "
                         '<span class="wd-block mono">(#26,441,165)</span>')
        self.assertGreater(lead, 0)
        self.assertLess(lead, page.find('data-wd-scope>Upshift describes the ProxyAdmin Safe as generally 4-of-6'))


NEUTRAL7 = ["concrete", "lagoon", "renzo-protocol-ezeth", "whales-market", "metamorpho-re7-weth-vs-re7-usdt", "tori-finance", "yearn-v3"]


def page(slug):
    return _read(os.path.join(ROOT, "docs", "protocols", slug, "index.html"), encoding="utf-8")


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
            t = _read(os.path.join(ROOT, "docs", "protocols", s, "index.html"), encoding="utf-8")
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
        meth = _read(os.path.join(ROOT, "docs", "methodology", "index.html"), encoding="utf-8")
        self.assertIn("never reinstates Delta", meth)

    def test_6_no_lending_vault_proxy_anywhere(self):
        import glob
        hits = [f for f in glob.glob(os.path.join(ROOT, "docs", "**", "*"), recursive=True)
                if os.path.isfile(f) and f.endswith((".html", ".json", ".txt", ".xml", ".svg", ".js")) and
                "lending vault proxy" in _read(f, encoding="utf-8", errors="ignore").lower()]
        self.assertEqual(hits, [])

    def test_7_clearance_states_free_self_correction(self):
        import html as H
        self.assertIn(H.escape(BS.CLEARANCE_SELF_CORRECTION, quote=False), page("usual-money-usd0-usd0"))
        self.assertIn("free of charge", BS.CLEARANCE_SELF_CORRECTION)

    def test_8_bounties_page_matches_base_apart_from_asset_keys(self):
        # merged candidate (Item 5): /bounties/ deliberately changes from the base: Wave 3 closed, 8 public Base payouts (2 sign-offs still open)
        now = _read(os.path.join(ROOT, "docs", "bounties", "index.html"), encoding="utf-8")
        self.assertEqual(now.count('<span data-slot="badge" data-variant="neutral">Paid on Base</span>'), 8)
        self.assertIn("Wave 3 closed 20 Nov 2026: $70.00 USDC paid on Base across 8 verified dossiers", now)
        self.assertNotIn("settled in full", now)
        for bad in ("[Wave 3:", "top-up", "in settlement", "verified adverse"):
            self.assertNotIn(bad, now)


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
                "timelock the documentation does not name" in _read(f, encoding="utf-8", errors="ignore")]
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
            self.assertIn(CORR.breakdown_text(), visible(_read(os.path.join(ROOT, "docs", *page_), encoding="utf-8")), page_)

    def test_c13_tabs_equal_row_counts(self):
        import re
        want = {"delta": 43, "recent_change": 1, "docs_updated": 1, "unresolved": 11, "protective": 7, "aligned": 126, "observed": 127}
        hub = _read(os.path.join(ROOT, "docs", "protocols", "index.html"), encoding="utf-8")
        rows = Counter_(re.findall(r'<tr data-ptier="([a-z_]+)"', hub))
        tabs = {k: int(n) for k, n in re.findall(r'data-pfilter-status="([a-z_]+)"[^>]*>[^<]+ <span class="num">\((\d+)\)', hub) if k != "all"}
        self.assertEqual(tabs, want)
        self.assertEqual(dict(rows), want)
        for page_ in (("index.html",), ("scorecards", "index.html")):
            t = _read(os.path.join(ROOT, "docs", *page_), encoding="utf-8")
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
            svg = _read(os.path.join(ROOT, "docs", "badges", f"{s}.svg"), encoding="utf-8")
            self.assertNotIn("Parameter Delta", svg, s)
        for s in ("yo-protocol", "infinifi", "hakka-finance", "taiko-bridge", "odyssey-finance", "seamless-protocol-base"):
            w = RULINGS_WORDING[s]
            self.assertEqual(CARDS[s]["finding"], f'{w["headline"]} (#{w["pinnedBlock"]:,})', s)
            self.assertIn("Verification scope", page(s))

    def test_c13_no_stale_counts(self):
        for page_ in (("index.html",), ("radar", "index.html"), ("scorecards", "index.html"), ("scan", "index.html"),
                      ("curators", "index.html"), ("methodology", "index.html"), ("miniapp", "index.html")):
            v = visible(_read(os.path.join(ROOT, "docs", *page_), encoding="utf-8"))
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
        # Scorecard-87 R1: the quorum is now derived from the dev-multisig record (no factor override)
        self.assertEqual(next(f for f in CARDS["beefy-finance-base"]["factors"] if f["key"] == "quorum")["value"],
                         "Known controlling quorum: 3-of-6 dev multisig")

    def test_a5_fx_both_safes(self):
        q = next(f for f in CARDS["f-x-protocol-v2"]["factors"] if f["key"] == "quorum")["value"]
        # Scorecard-87 R3 (SC87R2-02): both Safes, each with its own pinned block
        self.assertIn("3-of-4 ProtocolTreasury EmergencySafe (block #26,400,152)", q)
        self.assertIn("6-of-9 V2 Router / ProtocolTreasury OpsSafe (block #26,448,221)", q)
        sc = CARDS["f-x-protocol-v2"]["scopeNote"]
        self.assertIn("6-of-9", sc)
        self.assertIn("3-of-4 EmergencySafe", sc)

    def test_a6_no_breached_dimension_rated_strong(self):
        st = lambda s, k: next(f for f in CARDS[s]["factors"] if f["key"] == k)
        e = st("treehouse-tree-teth", "emergency")
        self.assertEqual(e["state"], "a")
        self.assertEqual(e["value"], "Immediate · TREE transfer blacklister() is a 5-of-7 Safe with 0s enforced delay (5d TimelockController retained on "
                                     "TREE and tETH owner paths)")   # Scorecard-87 R3 (SC87R2-02)
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
        import html as H_   # SC87-01: the caption's cited record is a link, so compare the visible text
        self.assertIn(w["evidenceCaption"], H_.unescape(re.sub(r"<[^>]+>", "", t)))
        self.assertIn("Docs updated", t)
        self.assertNotIn("Resolved by a documentation change", t)
        for f in glob.glob(os.path.join(ROOT, "docs", "protocols", "*", "index.html")):
            v = visible(_read(f, encoding="utf-8"))
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
            t = _read(os.path.join(ROOT, "docs", "protocols", s, "index.html"), encoding="utf-8")
            i = t.find("data-what-differs")
            if i >= 0:
                lead = visible(t[i:t.find("</section>", i)])
                self.assertIsNone(re.search(r"(?<![0-9A-Fa-fx])\d{18,}", lead), s)

    def test_b11_no_markdown_or_tex_in_visible_html(self):
        import glob
        import re
        for f in glob.glob(os.path.join(ROOT, "docs", "**", "*.html"), recursive=True):
            v = visible(_read(f, encoding="utf-8"))
            self.assertIsNone(re.search(r"\*\*[^*\s][^*]*\*\*", v), f)
            self.assertNotIn("$5/9$", v, f)

    def test_b12_re7_prefix_and_dashes(self):
        v = visible(page("metamorpho-re7-weth-vs-re7-usdt"))
        self.assertEqual(v.count("Sister vault reference"), 1)
        self.assertNotIn("guardian—no", v)
        self.assertIn("Aragon guardian — no promise of matching configurations was verified", v)

    # ---- E16–E18
    def test_e16_home_showcase(self):
        home = _read(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8")
        self.assertIn('data-pc-name>Usual Money (USD0 / USD0++)<', home)
        self.assertIn("0xfd7ce0f2b980da6606c8cd755da45d99f9ae4826e6df1321ff52c2b0f8e6a6c2", home)
        self.assertNotIn('data-pf-slug="yo-protocol"', home)
        self.assertNotIn(">GAP<", home)

    def test_e17_ethena(self):
        w = RULINGS_WORDING["ethena-usde-susde"]
        self.assertEqual(CARDS["ethena-usde-susde"]["finding"], f'{w["headline"]} (#26,401,638)')
        home = _read(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8")
        self.assertNotIn(">Timelock delay:", home)
        self.assertNotIn("Timelock delay: docs", home)

    def test_e18_layout_and_footnote(self):
        import glob
        css = _read(os.path.join(ROOT, "docs", "styles.css"), encoding="utf-8")
        home = _read(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8")
        self.assertIn('placeholder="Protocol or 0x…"', home)       # v8 G3 supersedes the v6 / v7 wording
        self.assertIn('.js #how-it-works [data-tabs-stable] > [data-slot="tabs-content"][data-inactive] { display: none; }', css)
        self.assertIn("overflow-wrap: break-word; word-break: normal;", css)
        self.assertNotIn("table.radar .meta { overflow-wrap: anywhere", css)
        self.assertIn('<span class="lb-lead"><span class="dot live"', _read(os.path.join(ROOT, "docs", "radar", "index.html"), encoding="utf-8"))
        self.assertIn(".memo-meta dd .sep { display: none; }", css)
        n_rated = 0
        for f in glob.glob(os.path.join(ROOT, "docs", "protocols", "*", "index.html")):
            s = f.split(os.sep)[-2]
            has = "parity is <i>uncompared</i> for Observed protocols" in _read(f, encoding="utf-8")   # merged candidate (Item 11): Observed
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
                "docs put every transaction behind a 3-day timelock" in _read(f, encoding="utf-8", errors="ignore")]
        self.assertEqual(hits, [])

    def test_f2_no_record_citations_or_ids_in_visible_prose(self):
        import glob
        import re
        import html as H
        ids = {e["id"] for e in j("api", "v1", "index.json")["entries"]} | {"tori-finance-control-plane"}
        id_re = re.compile(r"(?<![a-z0-9-])(" + "|".join(sorted(map(re.escape, ids), key=len, reverse=True)) + r")(?![a-z0-9-])")
        for f in glob.glob(os.path.join(ROOT, "docs", "**", "*.html"), recursive=True):
            t = re.sub(r"<script.*?</script>|<style.*?</style>|<code.*?</code>|<pre.*?</pre>", " ", _read(f, encoding="utf-8"), flags=re.S)
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
        m = _load(os.path.join(ROOT, "data", "curator-exposure-matrix.json"), encoding="utf-8")
        rows = m["all_55_verified_adverse_gaps"]
        self.assertEqual(len(rows), 56)
        self.assertEqual(sorted(r["slug"] for r in rows), sorted(RULINGS["partition"]))
        self.assertEqual(Counter(r["grade"] for r in rows), Counter({"DELTA": 43, "UNRESOLVED": 11, "CHANGED RECENTLY": 1, "DOCS UPDATED": 1}))
        self.assertEqual(m["all_56_reviewed_comparisons"], rows)
        raw = json.dumps(m, ensure_ascii=False)
        cur = _read(os.path.join(ROOT, "docs", "curators", "index.html"), encoding="utf-8")
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
        home = _read(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8")
        self.assertIn('placeholder="Protocol or 0x…"', home)            # v8 G3 supersedes the v7 wording
        radar = _read(os.path.join(ROOT, "docs", "radar", "index.html"), encoding="utf-8")
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
                if os.path.isfile(f) and f.endswith((".html", ".json", ".txt")) and "0x4B17…e88c" in _read(f, encoding="utf-8", errors="ignore")]
        self.assertEqual(hits, [])

    def test_g3_hero_input_room(self):
        css = _read(os.path.join(ROOT, "docs", "styles.css"), encoding="utf-8")
        home = _read(os.path.join(ROOT, "docs", "index.html"), encoding="utf-8")
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
            # a camelCase pause setter (setChainIdDepositsPaused()) names the pause power too (Scorecard-87, hop-protocol)
            pause_ = SC._EMERGENCY.search(ev) or re.search(r"\b[a-z]\w*Pause[ds]?\w*\(\)", ev)
            # a joined row (Scorecard-87 additionalEvidenceRecordIds) may read its quorum from the explicitly cited sibling record
            sib_ = " ".join(r_["onchain_observed"] for r_ in j("api", "v1", "index.json")["entries"] if r_["id"] in (e.get("additionalEvidenceRecordIds") or []))
            self.assertTrue(pause_ and (SC._nofs(ev) or SC._nofs(sib_) or "-of-N Safe" in e["value"]), s)

class V9(unittest.TestCase):
    INDEX = None

    def _rec(self, rid):
        if V9.INDEX is None:
            V9.INDEX = {e["id"]: e for e in j("api", "v1", "index.json")["entries"]}
        return V9.INDEX[rid]

    def _em(self, rid, g):
        import scorecard as SC
        return next(x for x in SC.factors([self._rec(rid)], True, g) if x["key"] == "emergency")

    def test_h1_deprecated_is_not_a_pause_surface(self):
        # "deprecated" README / docs sentences establish no pause / freeze authority (record-level and on the emitted card)
        for slug, rid in (("ekubo", "ekubo-core-immutable-starknet-owner-s32"),
                          ("inceptionlrt-isolated-restaking", "inception-vault-upgrades-timelock-3d-s32")):
            self.assertIn("deprecated", self._rec(rid)["onchain_observed"])
            for f in (self._em(rid, "aligned"), next(x for x in CARDS[slug]["factors"] if x["key"] == "emergency")):
                self.assertEqual((f["state"], f["value"]), ("n", "No pause / freeze authority in the published records"), slug)
                self.assertNotIn("Pause / freeze authority present", f["value"])
        # Tether's deprecated() getter sits beside its real pause / blacklist surface, which is kept
        import scorecard as SC
        self.assertTrue(SC._EMERGENCY.search("paused() = false") and SC._EMERGENCY.search("blacklist"))
        self.assertFalse(SC._EMERGENCY.search("The docs mark the V2 EVM deployment deprecated."))

    def test_h1_bare_seamless_canceller_role_establishes_no_presence(self):
        f = self._em("seamless-community-guardian-safe-2-of-3-s35", "unresolved")
        self.assertEqual((f["state"], f["value"], f["evidence"]), ("n", "No pause / freeze authority in the published records", None))
        e = next(x for x in CARDS["seamless-protocol-base"]["factors"] if x["key"] == "emergency")   # emitted override unchanged
        self.assertEqual((e["state"], e["value"], e["evidenceRecordId"]),
                         ("n", "2-of-3 Safe holds timelock CANCELLER_ROLE; pause / freeze binding not in the published records",
                          "seamless-community-guardian-safe-2-of-3-s35"))

    def test_h2_euler_multi_member_pause_role_is_not_strong(self):
        want = ("n", "PAUSE_GUARDIAN_ROLE held by 3 addresses (one 2-of-6 Safe; 2 other role members not resolved in the published records)")
        f = self._em("euler-v2-evk-factorygovernor-4d-timelock-s18", "aligned")
        self.assertEqual((f["state"], f["value"]), want)
        e = next(x for x in CARDS["euler-v2-evk"]["factors"] if x["key"] == "emergency")
        self.assertEqual((e["state"], e["value"]), want)
        for word in ("EOA", "single key", "single-key", "exploit"):
            self.assertNotIn(word, e["value"])

    def test_h2_no_strong_freeze_rests_on_unresolved_co_holders(self):
        # every Strong emergency row across all scorecards: no pause / freeze role-holder list in its cited record (a "has N members"
        # / getRoleMemberCount list, or "held by / granted to / assigned to / holders / pausers are A and B") leaves a holder without a
        # >= 2-signer Safe quorum or a timelock; addresses before the holder phrase are targets
        import re
        import scorecard as SC
        members = re.compile(r"\b[A-Z][A-Z0-9_]*_ROLE\b[^;()]{0,40}?\bhas (\d+) members(?:\s*\(([^)]*)\))?"
                             r"|getRoleMemberCount\([^)]*\)\s*(?:=|returns)\s*(\d+)")
        phrase = re.compile(r"\b(?:held by|assigned to|granted to|holders?\s*(?::|are|is)|pausers?\s+(?:are|is)|members?\s*(?::|are))\s+", re.I)
        bound = re.compile(r"\b([2-9]|1\d)-of-\d{1,2}\b|[Tt]imelock")
        addr = re.compile(r"0x[0-9a-fA-F]{40}")
        strong = [(s, x) for s, c in CARDS.items() for x in c["factors"] if x["key"] == "emergency" and x["state"] == "g"]
        self.assertEqual(len(CARDS), 316)
        self.assertEqual(len(strong), 13)   # Scorecard-87: hop-protocol emergency is reviewed down (M-group), 14 -> 13
        for s, x in strong:
            t = self._rec(x["evidenceRecordId"])["onchain_observed"]
            for sent in re.split(r";|(?<=[a-z0-9)])\.\s+(?=[A-Z])", t):
                if not SC._FREEZE_WORDS.search(sent):
                    continue
                m = members.search(sent)
                if m and int(m.group(1) or m.group(3)) > 1:
                    n = int(m.group(1) or m.group(3))
                    items = [i for i in (m.group(2) or "").split(",") if i.strip()]
                    self.assertEqual(len([i for i in items if bound.search(i)]), n, f"{s}: {n}-member pause role with unresolved members")
                p = phrase.search(sent)
                if p:
                    items = []
                    for it in re.split(r",\s*(?:and\s+)?|\s+and\s+", re.sub(r"\([^()]*\)", lambda q: q.group(0).replace(",", " ").replace(" and ", " "), sent[p.end():])):
                        if not addr.search(it):
                            break
                        items.append(it)
                    if len({addr.search(i).group(0).lower() for i in items}) > 1:
                        self.assertTrue(all(bound.search(i) for i in items), f"{s}: Strong freeze rests on unresolved co-holders: {sent[:120]}")


class V10(unittest.TestCase):
    A, B, V = "0x" + "1" * 40, "0x" + "2" * 40, "0x" + "9" * 40

    def _em(self, text):
        import scorecard as SC
        r = {"id": "synthetic-v10", "onchain_observed": text, "classification": "aligned_baseline"}
        return next(x for x in SC.factors([r], True, "aligned") if x["key"] == "emergency")

    def test_h21_members_list_with_an_unbound_member(self):
        f = self._em(f"PAUSER_ROLE has 2 members (2-of-3 Safe {self.A}, {self.B}).")
        self.assertEqual((f["state"], f["value"]), ("n", "PAUSER_ROLE held by 2 addresses (one 2-of-3 Safe; 1 other role member not resolved in the published records)"))

    def test_h21_held_by_list_with_an_unbound_holder(self):
        for t in (f"PAUSER_ROLE is held by 2-of-3 Safe {self.A} and {self.B}.", f"PAUSER_ROLE is granted to 2-of-3 Safe {self.A}, {self.B}.",
                  f"PAUSER_ROLE is assigned to 2-of-3 Safe {self.A} and {self.B}.", f"PAUSER_ROLE holders: 2-of-3 Safe {self.A}, {self.B}.",
                  f"The pausers are 2-of-3 Safe {self.A} and {self.B}."):
            f = self._em(t)
            self.assertEqual(f["state"], "n", t)
            self.assertIn("held by 2 addresses (one 2-of-3 Safe; 1 other role member not resolved in the published records)", f["value"], t)

    def test_h21_every_holder_bound_stays_strong(self):
        f = self._em(f"PAUSER_ROLE is held by 2-of-3 Safe {self.A} and 3-of-5 Safe {self.B}.")
        self.assertEqual((f["state"], f["value"]), ("g", "Pause / freeze authority scoped behind a multi-signer controller (2-of-3)"))
        self.assertEqual(self._em(f"PAUSER_ROLE holders: 2-of-3 Safe {self.A}, the TimelockController {self.B}.")["state"], "g")

    def test_h21_target_contract_is_not_a_co_holder(self):
        f = self._em(f"On Vault {self.V}, PAUSER_ROLE is held by 2-of-3 Safe {self.A}.")
        self.assertEqual((f["state"], f["value"]), ("g", "Pause / freeze authority scoped behind a multi-signer controller (2-of-3)"))


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
        page = _read(os.path.join(ROOT, "docs", "protocols", "40-acres-base", "index.html"), encoding="utf-8")
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



class ObolNeutralGovernance(unittest.TestCase):
    """Next site build Part 2: Obol keeps its Delta on the 500M cap; the archived v1.8 governance rows and the Timelock floor are neutral."""

    def test_obol_timelock_floor_and_two_rows_neutral_with_credit(self):
        sc = json.load(open(os.path.join(ROOT, "docs", "api", "v1", "scorecards.json"), encoding="utf-8"))
        ob = next(p for p in sc["protocols"] if p["slug"] == "obol-network")
        tl = next(f for f in ob["factors"] if f["key"] == "timelock")
        self.assertEqual(ob["grade"], "delta")
        self.assertEqual(tl["state"], "n")
        page = open(os.path.join(ROOT, "docs", "protocols", "obol-network", "index.html"), encoding="utf-8").read()
        for rid in ("obol-network-governance-timelock-delay-s24", "obol-network-governor-thresholds-s24"):
            sec = page[page.index(f'id="{rid}"'):]
            sec = sec[:sec.index("</article>")]
            self.assertIn('<span class="badge observed">Observed / Uncompared</span>', sec)
            self.assertNotIn("badge aligned", sec)
            self.assertIn("Current documentation (paused governance, not compared).", sec)
            self.assertIn("Governance within Obol is currently paused and undergoing a transition phase.", sec.replace("&#x27;", "'"))
        self.assertIn('data-research-wave="4"', page)
        self.assertIn("https://github.com/dankezo", page)
        self.assertIn("/pull/171", page)
        self.assertIn("Obol updated those governance pages in August 2026, before Sprint 24", page)
        low = page.lower()
        for bad in ("in response to pacta", "after pacta", "because of pacta", "following pacta", "prompted by"):
            self.assertNotIn(bad, low)
        self.assertNotIn("0xf8d0", low)

    def test_obol_uncompared_rows_never_matched_or_aligned_in_derived_surfaces(self):
        rows = ("obol-network-governance-timelock-delay-s24", "obol-network-governor-thresholds-s24")
        page = open(os.path.join(ROOT, "docs", "protocols", "obol-network", "index.html"), encoding="utf-8").read()
        wd = page[page.index("data-what-differs"):]
        wd = wd[:wd.index("</section>")]
        self.assertEqual(wd.count("<li data-wd-matched>"), 1)
        self.assertIn("stOBOL unstaking", wd)
        self.assertEqual(wd.count("<li data-wd-uncompared>"), 2)
        self.assertIn("governance paused in v1.11 documentation (not compared)", wd)
        lk = json.load(open(os.path.join(ROOT, "docs", "api", "v1", "lookup.json"), encoding="utf-8"))
        ob = next(i for i in lk["items"] if i["slug"] == "obol-network")
        self.assertIsNone(ob["documentedDelaySeconds"])
        self.assertEqual(ob["observedDelaySeconds"], 432000)
        self.assertFalse({m["recordId"] for m in ob["whatDiffers"]["matched"]} & set(rows))
        self.assertEqual({m["recordId"] for m in ob["whatDiffers"]["uncompared"]}, set(rows))
        pr = json.load(open(os.path.join(ROOT, "docs", "api", "v1", "protocols.json"), encoding="utf-8"))
        for doc in (ob, next(p for p in pr["protocols"] if p["slug"] == "obol-network")):
            cls = {s["id"]: s["classification"] for s in doc["surfaces"]}
            self.assertEqual({r: cls[r] for r in rows}, {r: "observed_uncompared" for r in rows})
        full = open(os.path.join(ROOT, "docs", "llms-full.txt"), encoding="utf-8").read()
        for r in rows:
            self.assertIn(f"- {r} [observed_uncompared] ", full)
            self.assertNotIn(f"- {r} [aligned_baseline] ", full)
        ix = json.load(open(os.path.join(ROOT, "docs", "api", "v1", "index.json"), encoding="utf-8"))
        self.assertEqual({e["classification"] for e in ix["entries"] if e["id"] in rows}, {"aligned_baseline"})   # attested data untouched


class Scorecard87(unittest.TestCase):
    """Business receipt 7462: one round, exactly 130 factor slices on 87 pages (87 rule-derived + 43 reviewed); everything else
    byte-identical to BASE (main 7cdc9a96; the scorecard commit b80f21eb was cut on f7ea61a7), apart from the x-feed rosette repair
    (REPAIRED / REDRAWN below), the request form's issuer track (URGENCY_MOVE), the button focus outline (FOCUS_MOVE) and the
    protocol combobox's Tab / focus-leave dismissal (COMBO_MOVES)."""
    BASE = "7cdc9a96bd59a2c0b77fb8a46dacc93c12cac814"
    CUT = ("f7ea61a757dc00749dee639105bda3e83b907408", "b80f21ebd9e478d68dd0f60cac9cd7e414b6cdcb")
    # service cleanup: the request form posts the Worker's renamed issuer track, the one moved line of tools/app.src.js and
    # docs/app.js; the app.js?v= stamp of every page moves with app.js (_unstamp). Nothing else of either file or any page moved.
    URGENCY_MOVE = ('clearance: "issuer_24h_clearance_5k"', 'clearance: "issuer_urgent_review"')
    # SC-FOCUS-01: docs/styles.css gains one rule after the button variants (a 2 px --ring outline on :focus-visible over a
    # page-colour gap); the styles.css?v= stamp of every page moves with it (_unstamp). Nothing else of the stylesheet moved.
    FOCUS_ANCHOR = '[data-slot="button"] svg, .btn svg { width: 16px; height: 16px; flex: none; }\n'
    FOCUS_MOVE = (FOCUS_ANCHOR, FOCUS_ANCHOR + '[data-slot="button"]:focus-visible, .btn:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px;'
                  ' box-shadow: 0 0 0 2px var(--background); }   /* SC-FOCUS-01: after the variant rules, several of which reset the box-shadow'
                  ' ring; the page-colour gap keeps the ring visible on the dark code blocks */\n')
    # SC-FOCUS-02: initCombo closes the protocol list on Tab / Shift+Tab from its search input and when focus leaves the combobox
    # (one keydown branch, one focusout listener) in tools/app.src.js and, minified, in docs/app.js. Nothing else of either file moved.
    _BKSP = 'else if (ev.key === "Backspace" && !input.value && selected.length) toggle(selected[selected.length - 1]);\n'
    _TAB = 'else if (ev.key === "Tab") { close(); }'
    _CLICK = 'document.addEventListener("click", function (ev) { if (!root.contains(ev.target)) close(); });\n'
    _LEAVE = ('root.addEventListener("focusout", function (ev) {\n', 'if (ev.relatedTarget && !root.contains(ev.relatedTarget)) close();\n',
              'else setTimeout(function () { if (!root.contains(document.activeElement)) close(); }, 0);\n', '});\n')
    COMBO_MOVES = {
        "tools/app.src.js": (
            ("      " + _BKSP + "    });\n",
             "      " + _BKSP + "      " + _TAB + "   // SC-FOCUS-02: no preventDefault; the list is hidden before Tab / Shift+Tab moves focus on\n"
             "    });\n"),
            ("    " + _CLICK,
             "    " + _CLICK + "    // SC-FOCUS-02: focus leaving the combobox (from the input or a chip Remove button) closes the list, so it never"
             " covers the next field\n    " + _LEAVE[0] + "      " + _LEAVE[1] + "      " + _LEAVE[2] + "    " + _LEAVE[3])),
        "docs/app.js": (
            (_BKSP + "});\n", _BKSP + _TAB + "\n});\n"),
            (_CLICK, _CLICK + "".join(_LEAVE))),
    }
    EXP = {e["slice_id"]: e for e in _load(os.path.join(HERE, "scorecard87_expected_136.json"), encoding="utf-8")["entries"]}
    FORBIDDEN = re.compile(r"\b(?:immutable|renounced|EOA)\b", re.I)

    @staticmethod
    def _unstamp(b):
        return re.sub(rb"((?:app\.js|styles\.css)\?v=)[0-9a-f]{8}\b", rb"\1", b)

    @classmethod
    def _git(cls, path, binary=False):
        r = subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "show", f"{cls.BASE}:{path}"], capture_output=True)
        if r.returncode:
            raise unittest.SkipTest(f"base commit {cls.BASE[:8]} not available")
        return r.stdout if binary else r.stdout.decode("utf-8")

    @classmethod
    def setUpClass(cls):
        base = json.loads(cls._git("docs/api/v1/scorecards.json"))["protocols"]
        cls.B = {(p["slug"], f["key"]): f for p in base for f in p["factors"]}
        cls.N = {(s, f["key"]): f for s, c in CARDS.items() for f in c["factors"]}
        cls.changed = {f"{s}:{k}" for (s, k) in cls.N if cls.N[(s, k)] != cls.B[(s, k)]}
        cls.pages = {e["slug"] for e in cls.EXP.values()}

    def test_exactly_the_130_slices_change(self):
        self.assertEqual(len(self.N), 1580)
        self.assertEqual(set(self.B), set(self.N))
        self.assertEqual(self.changed, set(self.EXP))
        self.assertEqual((len(self.EXP), len(self.pages), len(self.N) - len(self.changed)), (136, 87, 1444))
        self.assertEqual(sum(e["bucket"] == "B1_RULE" for e in self.EXP.values()), 87)

    def test_every_changed_slice_matches_the_reference(self):
        for sid, e in self.EXP.items():
            s, k = sid.rsplit(":", 1)
            f, a = self.N[(s, k)], e["after"]
            self.assertEqual((f["state"], f["value"], f["evidenceRecordId"], f["evidenceCaption"]),
                             (a["state"], a["value"], a["evidenceRecordId"], a["evidenceCaption"]), sid)
            self.assertEqual(f.get("additionalEvidenceRecordIds", []), a["additionalEvidenceRecordIds"], sid)
            self.assertEqual(f["evidence"].split(": ", 1)[0], a["evidenceRecordId"], sid)
            self.assertNotRegex(f["value"] + " " + f["evidenceCaption"], self.FORBIDDEN, sid)

    def test_rules_derive_state_and_evidence_before_any_override(self):
        # R1-R5 run on exactly the 87 rule slices; with every labelOverride for those slices removed, the raw factors already carry the
        # reference state and cited record and no forbidden word. Their overrides may only carry value / caption / additional ids.
        import copy
        import scorecard as SC
        b1 = {sid for sid, e in self.EXP.items() if e["bucket"] == "B1_RULE"}
        self.assertEqual({f"{s}:{k}" for s, k in SC.RULE_SLICES_87}, b1)
        data = CORR.data()
        lfo = data["labelOverrides"]["factorOverrides"]
        for sid in b1:
            s, k = sid.rsplit(":", 1)
            o = (lfo.get(s) or {}).get(k)
            if o is not None:
                self.assertTrue(set(o) <= {"value", "evidenceCaption", "additionalEvidenceRecordIds"}, (sid, set(o)))
            self.assertNotIn(k, ((data["protocols"].get(s) or {}).get("factorOverrides") or {}), sid)
        stripped = copy.deepcopy(data)
        for sid in b1:
            s, k = sid.rsplit(":", 1)
            stripped["labelOverrides"]["factorOverrides"].get(s, {}).pop(k, None)
        saved = CORR._DATA
        try:
            CORR._DATA = stripped
            raw = {(c["slug"], f["key"]): f for c in BS.scorecards(j("api", "v1", "index.json")) for f in c["factors"]}
        finally:
            CORR._DATA = saved
        for sid in sorted(b1):
            s, k = sid.rsplit(":", 1)
            a, f = self.EXP[sid]["after"], raw[(s, k)]
            self.assertEqual((f["state"], f["evidenceRecordId"]), (a["state"], a["evidenceRecordId"]), sid)
            self.assertNotRegex(f["value"], self.FORBIDDEN, sid)
        # and outside the gate the rules never run: every other slice of the stripped build equals f7ea61a7
        for key, f in raw.items():
            if f"{key[0]}:{key[1]}" not in self.EXP:
                self.assertEqual(f, self.B[key], key)

    # x-feed repair on 5392279b: the feed rosettes of the 229 clean protocols had stayed at BASE while their scorecards moved on, 117
    # entries on 111 items: 110 parity values ("(RPC-observed)" -> "(Observed)"), 6 emergency values (pause / freeze authority present,
    # holder not determined) and aave-v3-gho's timelock ("—" not determined -> "M" medium, 1d floor). Every rosette now follows its
    # scorecard; a card draws only the cue and state word of each entry (never the value), so aave-v3-gho.png is the one redrawn card.
    REPAIRED = {("parity", "value"): 110, ("emergency", "value"): 6, ("timelock", "state"): 1, ("timelock", "cue"): 1, ("timelock", "value"): 1}
    REDRAWN = {"aave-v3-gho"}

    def test_clean_pages_and_cards_byte_identical_and_every_feed_rosette_follows_its_scorecard(self):
        clean = sorted(set(CARDS) - self.pages)
        self.assertEqual(len(clean), 229)
        for s in clean:
            p = os.path.join("docs", "protocols", s, "index.html")
            self.assertEqual(self._unstamp(_read(os.path.join(ROOT, p), "rb")), self._unstamp(self._git(p, binary=True)), s)
            c = os.path.join("docs", "cards", f"{s}.png")
            if os.path.exists(os.path.join(ROOT, c)):
                (self.assertNotEqual if s in self.REDRAWN else self.assertEqual)(_read(os.path.join(ROOT, c), "rb"), self._git(c, binary=True), s)
        base_feed = {i["feedId"]: i for i in json.loads(self._git("docs/api/v1/x-feed.json"))["items"]}
        feed = {i["feedId"]: i for i in j("api", "v1", "x-feed.json")["items"]}
        self.assertEqual(set(base_feed), set(feed))
        cue = {"g": "S", "b": "M", "a": "W", "n": "—", "u": "—"}
        repaired, items = Counter_(), set()
        for fid, it in feed.items():
            # all five rosette entries of every item (316 protocols + the radar operations) follow its scorecard (parity included)
            s = it.get("protocolSlug") or it["slug"]
            self.assertEqual([(r["key"], r["label"], r["state"], r["cue"], r["value"]) for r in it["rosette"]],
                             [(f["key"], f["label"], f["state"], cue[f["state"]], f["value"]) for f in CARDS[s]["factors"]], fid)
            if it["slug"] not in self.pages:
                # a clean item keeps every other field of BASE
                b = base_feed[fid]
                self.assertEqual({k: v for k, v in it.items() if k != "rosette"}, {k: v for k, v in b.items() if k != "rosette"}, fid)
                for r, rb in zip(it["rosette"], b["rosette"]):
                    for k in ("state", "cue", "value"):
                        if r[k] != rb[k]:
                            repaired[(r["key"], k)] += 1
                            items.add(fid)
            else:
                if it["slug"] in ("layerzero-v2", "m0-protocol-m", "flokifi-locker"):
                    prose = " ".join(str(it.get(k, "")) for k in ("summaryShort", "docsSay", "chainSays", "mainPostText"))
                    self.assertNotRegex(prose, self.FORBIDDEN, fid)
        self.assertEqual(dict(repaired), self.REPAIRED)
        self.assertEqual(len(items), 111)

    def test_cards_rerendered_only_where_a_state_changed(self):
        import struct
        moved = {s for s in self.pages if any(self.N[(s, k)]["state"] != self.B[(s, k)]["state"] for k in ("upgrade", "timelock", "quorum", "emergency", "parity"))}
        out = subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "diff", "--name-only", self.BASE, "--", "docs/cards/"], capture_output=True, text=True)
        diff = {os.path.basename(p)[:-4] for p in out.stdout.split()}
        # R2: plus the changed protocols whose card text (docsSay / chainSays) changed in x-feed.json (m0-protocol-m)
        base_feed = {i["feedId"]: i for i in json.loads(self._git("docs/api/v1/x-feed.json"))["items"]}
        feed = j("api", "v1", "x-feed.json")["items"]
        texted = {i["slug"] for i in feed if any(i.get(k) != base_feed[i["feedId"]].get(k) for k in ("docsSay", "chainSays"))}
        self.assertTrue(texted <= self.pages, sorted(texted - self.pages))
        # x-feed repair: a clean protocol's card is redrawn only where a drawn rosette field (cue / state word) moved: aave-v3-gho alone
        redrawn = {i["slug"] for i in feed if i["slug"] not in self.pages
                   and any((r["state"], r["cue"]) != (rb["state"], rb["cue"]) for r, rb in zip(i["rosette"], base_feed[i["feedId"]]["rosette"]))}
        self.assertEqual(redrawn, self.REDRAWN)
        self.assertEqual(diff, moved | texted | redrawn, sorted(diff ^ (moved | texted | redrawn)))
        for s in diff:
            b = _read(os.path.join(ROOT, "docs", "cards", f"{s}.png"), "rb")
            self.assertEqual(b[:8], b"\x89PNG\r\n\x1a\n", s)
            self.assertEqual(struct.unpack(">II", b[16:24]), (1200, 675), s)

    @staticmethod
    def _png_rows(b):
        """stdlib PNG decode (8-bit RGB / RGBA, not interlaced): width, bytes per pixel and the unfiltered scanlines."""
        import struct
        import zlib
        assert b[:8] == b"\x89PNG\r\n\x1a\n"
        pos, idat, hdr = 8, [], None
        while pos < len(b):
            n, t = struct.unpack(">I4s", b[pos:pos + 8])
            if t == b"IHDR":
                hdr = struct.unpack(">IIBBBBB", b[pos + 8:pos + 8 + n])
            elif t == b"IDAT":
                idat.append(b[pos + 8:pos + 8 + n])
            pos += 12 + n
        w, h, depth, ctype, _c, _f, interlace = hdr
        assert depth == 8 and ctype in (2, 6) and interlace == 0, hdr
        bpp = 3 if ctype == 2 else 4
        raw, stride, rows, prev = zlib.decompress(b"".join(idat)), w * bpp, [], bytearray(w * bpp)
        for y in range(h):
            f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
            if f == 1:
                for i in range(bpp, stride):
                    line[i] = (line[i] + line[i - bpp]) & 255
            elif f == 2:
                line = bytearray((x + u) & 255 for x, u in zip(line, prev))
            elif f == 3:
                for i in range(stride):
                    line[i] = (line[i] + ((line[i - bpp] if i >= bpp else 0) + prev[i]) // 2) & 255
            elif f == 4:
                for i in range(stride):
                    a, u, c = (line[i - bpp] if i >= bpp else 0), prev[i], (prev[i - bpp] if i >= bpp else 0)
                    p = a + u - c
                    pa, pb, pc = abs(p - a), abs(p - u), abs(p - c)
                    line[i] = (line[i] + (a if pa <= pb and pa <= pc else u if pb <= pc else c)) & 255
            rows.append(bytes(line))
            prev = line
        return w, bpp, rows

    def test_redrawn_card_changes_only_its_timelock_cell(self):
        # aave-v3-gho.png against BASE: every changed pixel lies inside the timelock cell of the rosette (cue box + state word; card
        # layout: rosette top y1 - 150 = 489, five 204.8 px cells from x 88), and the cell does change
        new = _read(os.path.join(ROOT, "docs", "cards", "aave-v3-gho.png"), "rb")
        w, bpp, a = self._png_rows(new)
        w0, bpp0, b = self._png_rows(self._git("docs/cards/aave-v3-gho.png", binary=True))
        self.assertEqual((w, bpp, len(a)), (w0, bpp0, len(b)))
        ys = [y for y in range(len(a)) if a[y] != b[y]]
        xs = [x for y in ys for x in range(w) if a[y][x * bpp:(x + 1) * bpp] != b[y][x * bpp:(x + 1) * bpp]]
        self.assertTrue(ys)
        self.assertTrue(292 <= min(xs) and max(xs) < 498 and 489 <= ys[0] and ys[-1] < 545, (min(xs), ys[0], max(xs), ys[-1]))

    def test_attested_rows_js_css_and_mcp_untouched(self):
        paths = ["docs/api/v1/index.json", "docs/api/v1/rpc-pinned.json", "docs/api/v1/onboarding.json", "docs/api/v1/radar.json", "audits/",
                 "tools/pacta_x402_call.py", ".github/workflows/"]
        # packages/mcp-server/ equals BASE while the package is still 0.1.5; the 0.1.6 package is its own later push
        if _load(os.path.join(ROOT, "packages", "mcp-server", "package.json"), encoding="utf-8")["version"] == "0.1.5":
            paths.append("packages/mcp-server/")
        out = subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "diff", self.BASE, "--", *paths], capture_output=True)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, b"")
        # app.src.js / app.js: BASE with the request form's issuer track renamed (URGENCY_MOVE) and the protocol combobox's Tab /
        # focus-leave dismissal (COMBO_MOVES), byte for byte otherwise
        for p in ("tools/app.src.js", "docs/app.js"):
            base = self._git(p)
            self.assertEqual(base.count(self.URGENCY_MOVE[0]), 1, p)
            want = base.replace(*self.URGENCY_MOVE)
            for a, b in self.COMBO_MOVES[p]:
                self.assertEqual(want.count(a), 1, (p, a))
                want = want.replace(a, b)
            self.assertEqual(_read(os.path.join(ROOT, p), encoding="utf-8"), want, p)
        # styles.css: BASE plus the one focus rule after the button variants (FOCUS_MOVE), byte for byte otherwise
        base = self._git("docs/styles.css")
        self.assertEqual(base.count(self.FOCUS_MOVE[0]), 1)
        self.assertEqual(_read(os.path.join(ROOT, "docs", "styles.css"), encoding="utf-8"), base.replace(*self.FOCUS_MOVE))
        # the scorecard commit itself never touches packages/mcp-server/ (checked whenever f7ea61a7..b80f21eb is in the history)
        if all(subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "merge-base", "--is-ancestor", c, "HEAD"], capture_output=True).returncode == 0
               for c in self.CUT):
            out = subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "diff", f"{self.CUT[0]}..{self.CUT[1]}", "--", "packages/mcp-server/"],
                                 capture_output=True)
            self.assertEqual((out.returncode, out.stdout), (0, b""))

    def test_joined_rows_cite_their_siblings_on_one_evidence_tag(self):
        joined = {sid: e["after"]["additionalEvidenceRecordIds"] for sid, e in self.EXP.items() if e["after"]["additionalEvidenceRecordIds"]}
        self.assertEqual(len(joined), 19)
        for sid, ids in joined.items():
            s, k = sid.rsplit(":", 1)
            html = _read(os.path.join(ROOT, "docs", "protocols", s, "index.html"), encoding="utf-8")
            row = re.search(r'<div[^>]*data-factor="%s"[^>]*>.*?</div>' % k, html, re.S).group(0)
            ev = re.findall(r'<small class="ev"[^>]*>', row)
            self.assertEqual(len(ev), 1, sid)
            self.assertIn(f'data-record-id="{self.EXP[sid]["after"]["evidenceRecordId"]}"', ev[0], sid)
            self.assertIn(f'data-additional-record-ids="{",".join(ids)}"', ev[0], sid)
        others = sum(_read(os.path.join(ROOT, "docs", "protocols", s, "index.html"), encoding="utf-8").count("data-additional-record-ids")
                     for s in CARDS)
        self.assertEqual(others, len(joined))


    def test_sc87_01_citation_links_on_changed_cards_only(self):
        # every cited record of a changed card is a link to its row (#<record id>): one per segment of the caption head, the visible text
        # unchanged; one evidence tag (data-record-id only on it); the 229 clean pages carry no citation link at all
        import html as H
        for s in sorted(self.pages):
            page = _read(os.path.join(ROOT, "docs", "protocols", s, "index.html"), encoding="utf-8")
            for k in ("upgrade", "timelock", "quorum", "emergency", "parity"):
                f = self.N[(s, k)]
                if not f.get("evidenceRecordId"):
                    continue
                row = re.search(r'<div data-factor="%s"[^>]*>.*?</div>' % k, page, re.S).group(0)
                tag = re.search(r'<small class="ev"[^>]*>(.*?)</small>', row, re.S)
                ids = [f["evidenceRecordId"]] + list(f.get("additionalEvidenceRecordIds") or [])
                hrefs = re.findall(r'<a href="([^"]+)"', tag.group(1))
                self.assertEqual(hrefs, [f"/protocols/{s}/#{i}" for i in ids], (s, k))
                self.assertEqual(row.count("data-record-id="), 1, (s, k))
                for i in ids:
                    self.assertRegex(page, r'<article\b[^>]*\bid="%s"' % re.escape(i), (s, k, i))
                self.assertEqual(H.unescape(re.sub(r"<[^>]+>", "", tag.group(1))), "Evidence: " + f["evidenceCaption"], (s, k))
                self.assertIn("min-height:24px", tag.group(1))
        for s in sorted(set(CARDS) - self.pages):
            page = _read(os.path.join(ROOT, "docs", "protocols", s, "index.html"), encoding="utf-8")
            self.assertNotRegex(page, r'<small class="ev"[^>]*>Evidence: <a ', s)


    def test_cards_draw_reviewed_chainsays_without_truncation(self):
        # SC87R4-01: an aligned_baseline card draws its reviewed chainSays (never "Matches the docs" over it), and no drawn line ends in "…"
        import render_x_cards_raster as RX
        feed = [i for i in j("api", "v1", "x-feed.json")["items"] if i["slug"] in self.pages]
        custom = 0
        for it in feed:
            cs = (it.get("chainSays") or "").strip()
            if it["kind"] == "aligned_baseline" and cs.lower() not in ("", "the same, so docs and chain match"):
                custom += 1
                self.assertEqual(RX.card_rows(it)[1][1], RX.cap(cs), it["feedId"])
        self.assertEqual(custom, 22)
        by = {i["slug"]: i for i in feed}
        self.assertIn("Aragon identity not resolved in this read", RX.card_rows(by["steakhouse-prime-usdc-base"])[1][1])
        self.assertIn("direct pause not verified", RX.card_rows(by["railgun"])[1][1])
        fonts = os.environ.get("PACTA_CARD_FONT_DIR", "/home/pacta-gemini/workspace/shared-specs/ibm-plex-ttf")
        if not os.path.exists(os.path.join(fonts, "IBMPlexSans-Regular.ttf")):
            self.skipTest("IBM Plex fonts not available for the drawn-line check")
        F = RX.Fonts(fonts)
        drawn = {it["slug"]: RX.drawn_lines(it, F) for it in feed}
        self.assertEqual([(s, lab) for s, rows in drawn.items() for lab, ls in rows if ls and ls[-1].endswith("…")], [])
        self.assertIn("direct pause not verified", " ".join(drawn["railgun"][1][1]))
        self.assertIn("Aragon identity not resolved in this read", " ".join(drawn["steakhouse-prime-usdc-base"][1][1]))


if __name__ == "__main__":
    unittest.main()
