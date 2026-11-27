"""Pages for assistants (tools/fact_pages.py): the lists by one checked fact, the chain pages, the use pages, /listed/ and the links
block on every record page. Every count comes from the records at build time, a count in a page's first lines equals the rows
under it (and a changed count fails the check), a fact that is not determined keeps a protocol off a list, and the new text
carries no grade or judgement word.

    python3 -m unittest tools/test_fact_pages.py
"""
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_site as BS  # noqa: E402
import fact_pages as FP  # noqa: E402


def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def built():
    idx, radar = BS.load()
    return BS.wave(idx, radar), idx, radar


class Parse(unittest.TestCase):
    def test_durations(self):
        for tok, s in (("7d", 604800), ("1d 12h", 129600), ("1.5h", 5400), ("168h", 604800), ("300s", 300), ("10d", 864000)):
            self.assertEqual(FP.dur_seconds(tok), s, tok)
        for bad in ("7 days", "1h30m", ""):
            with self.assertRaises(AssertionError):
                FP.dur_seconds(bad)
        self.assertEqual([FP.say_dur(s) for s in (604800, 129600, 3600, 43200, 1800, 1)],
                         ["7 days", "1 day 12 hours", "1 hour", "12 hours", "30 minutes", "1 second"])

    def test_banned_words(self):
        self.assertEqual(FP.banned("<p>the best and safest; a risky score</p>"), ["best", "safest", "risky", "score"])
        self.assertEqual(FP.banned("<td>ProxyAdmin owned by a 3-of-5 Safe</td><td>Fail-safe recovery</td>"), [])


class Times(unittest.TestCase):
    def test_block_times_agree_and_cover_the_pins(self):
        _, _, radar = built()
        t = FP.block_times(ROOT, radar)
        pin = json.loads(read("docs", "api", "v1", "rpc-pinned.json"))
        for ch, h in pin["pinned_heads"].items():
            self.assertIn((ch, h["block_number"]), t)
        for ch in ("ethereum", "base"):
            seq = sorted((b, s) for (c, b), s in t.items() if c == ch)
            self.assertTrue(all(a[1] <= b[1] for a, b in zip(seq, seq[1:])), ch)

    def test_newest_day_needs_a_known_block(self):
        with self.assertRaises(AssertionError):
            FP.newest_day([("ethereum", 1)], {})


class Lists(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w, cls.idx, cls.radar = built()
        cls.n = len(BS.site_protocols(cls.idx))

    def test_pages(self):
        self.assertEqual(list(self.w["out"]), FP.PAGES)
        self.assertNotIn("control/immutable/", FP.PAGES)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "docs", "control", "immutable")))
        for rel, t in self.w["out"].items():
            self.assertEqual(t, read("docs", rel, "index.html"), rel)
            self.assertEqual(re.findall(r"<h1>([^<]*)</h1>", t), [BS.E(FP.TITLES[rel])], rel)
            self.assertEqual(re.findall(r"<title>([^<]*)</title>", t), [BS.E(FP.TITLES[rel])], rel)

    def test_partitions(self):
        L = self.w["L"]
        tl, ms, dv = L["control/timelock/"], L["control/multisig/"], L["docs-vs-chain/"]
        self.assertEqual(len(tl["rows"]) + len(tl["zero"]) + len(tl["nd"]), self.n)
        self.assertEqual(len(ms["rows"]) + len(ms["governor"]) + len(ms["nd"]), self.n)
        self.assertEqual(len(dv["compared"]) + len(dv["uncompared"]), self.n)
        self.assertEqual(len(dv["rows"]) + len(dv["nd"]) + len(dv["agree"]), len(dv["compared"]))
        for c in FP.CHAIN_PAGES:
            cv = L[f"chains/{c}/"]
            self.assertEqual(len(cv["both"]) + len(cv["one"]) + len(cv["neither"]), self.n, c)
        self.assertEqual(sum(len(L[f"chains/{c}/"]["rows"]) for c in FP.CHAIN_PAGES), len(cv["one"]) + 2 * len(cv["both"]))
        self.assertTrue(all(p["timelock"]["seconds"] > 0 for p in tl["rows"]))
        self.assertEqual([p["timelock"]["seconds"] for p in tl["rows"]], sorted(p["timelock"]["seconds"] for p in tl["rows"]))
        self.assertEqual([(p["quorum"]["k"], p["quorum"]["n"]) for p in ms["rows"]], sorted((p["quorum"]["k"], p["quorum"]["n"]) for p in ms["rows"]))

    def test_not_determined_is_never_listed(self):
        cards = {c["slug"]: c for c in BS.scorecards(self.idx)}
        L = self.w["L"]
        for rel, key in (("control/timelock/", "timelock"), ("control/multisig/", "quorum")):
            self.assertFalse([p["slug"] for p in L[rel]["rows"] if FP._factor(cards[p["slug"]], key)["state"] == "n"], rel)
        self.assertTrue(all(cards[p["slug"]]["grade"] == "delta" for p in L["docs-vs-chain/"]["rows"]))

    def test_rule_a_check_catches_a_changed_count(self):
        self.assertEqual(len(self.w["check"]), 5)
        self.assertTrue(all(line.endswith(": OK") for line in self.w["check"]))
        out = dict(self.w["out"])
        t = out["control/timelock/"]
        n = len(self.w["L"]["control/timelock/"]["rows"])
        out["control/timelock/"] = t.replace(f'<span data-n="rows">{n:,}</span>', f'<span data-n="rows">{n + 1:,}</span>', 1)
        self.assertNotEqual(out["control/timelock/"], t)
        with self.assertRaises(AssertionError):
            FP.check(out, self.w["L"], self.w["nums"])
        out = dict(self.w["out"])
        t = out["chains/base/"]
        first = t.split("<tbody data-rows>\n", 1)[1].split("</tr>\n", 1)[0] + "</tr>\n"   # one row twice: 38 rows under "37"
        out["chains/base/"] = t.replace("<tbody data-rows>\n", "<tbody data-rows>\n" + first, 1)
        with self.assertRaises(AssertionError):
            FP.check(out, self.w["L"], self.w["nums"])
        out = dict(self.w["out"])                                                  # the same count marked twice, the second one changed
        t = out["docs-vs-chain/"]
        mc = len(self.w["L"]["docs-vs-chain/"]["compared"])
        tag = f'<span data-n="compared">{mc:,}</span>'
        self.assertGreaterEqual(t.count(tag), 2)
        i = t.index(tag, t.index(tag) + 1)
        out["docs-vs-chain/"] = t[:i] + f'<span data-n="compared">{mc - 1:,}</span>' + t[i + len(tag):]
        self.assertEqual(FP.first_lines_counts(out["docs-vs-chain/"])[0]["compared"], -1)
        with self.assertRaises(AssertionError):
            FP.check(out, self.w["L"], self.w["nums"])

    def test_description_count_is_the_row_count(self):
        """W10: the count a description leads with (meta, og:, twitter:) is checked against the rows; one changed copy fails the build"""
        for rel in ("control/timelock/", "chains/ethereum/"):
            out = dict(self.w["out"])
            n = len(self.w["L"][rel]["rows"])
            t = out[rel]
            tag = f'<meta property="og:description" content="{n} DeFi protocols '
            self.assertEqual(t.count(tag), 1, rel)
            out[rel] = t.replace(tag, f'<meta property="og:description" content="{n + 1} DeFi protocols ', 1)
            with self.assertRaises(AssertionError):
                FP.check(out, self.w["L"], self.w["nums"])
        self.assertIn("Free within daily limits; the page lists what is paid per call.", FP.DESC["learn/check-before-deposit/"])
        self.assertIn(f'content="{BS.E(FP.DESC["learn/check-before-deposit/"])}"', self.w["out"]["learn/check-before-deposit/"])

    def test_soft_breaks_keep_the_text(self):
        for v in ('0x5f0DeE98360d8200b20812e174d139A1a633EDd2', 'AccessControlDefaultAdminRules',
                  '<a href="https://registry.modelcontextprotocol.io/v0/servers?search=io.github.Fractal-Neurons/pacta">https://registry.'
                  'modelcontextprotocol.io/v0/servers?search=io.github.Fractal-Neurons/pacta</a>', '&quot;0x99B5FA03a5ea4315725c43346e55a6A6fbd94098&quot;&#x27;',
                  'Ethereum #26,440,048', 'Subscription_decentralization'):
            w = FP._soft(v)
            self.assertEqual(w.replace("<wbr>", ""), v)                                     # the text and every tag unchanged
            self.assertFalse(re.search(r"<[^>]*<wbr>|&[#\w]*<wbr>", w), w)                  # never inside a tag or an entity
            for word in re.findall(r"[A-Za-z]+", re.sub(r"<[^>]+>", " ", v)):
                if not re.search(r"[a-z][A-Z]", word):
                    self.assertIn(word, w.replace("<wbr>", " ") + " " + w, word)          # a plain word is never split
        self.assertIn("<wbr>", FP._soft("0x5f0DeE98360d8200b20812e174d139A1a633EDd2"))
        self.assertNotIn("Subscripti<wbr>on", FP._soft("globalSubscriptionLimits(0x1B19C19393e2d034D8Ff31ff34c81252FcBbee92)"))
        for rel in FP.LIST_PAGES + ("chains/ethereum/", "chains/base/"):
            self.assertIn('<table class="stack w2-table" data-list-table>', self.w["out"][rel], rel)
            self.assertIn('<main id="main" class="memo-wrap memo-wide">', self.w["out"][rel], rel)
        self.assertIn('<table class="stack w2-table" data-listings>', self.w["out"]["listed/"])
        css = read("docs", "styles.css")
        self.assertIn(".w2-table th, .w2-table td { overflow-wrap: normal; word-break: normal; }", css)
        self.assertIn(".memo-wrap.memo-wide { max-width: var(--container-wide); }", css)
        self.assertIn("@media (min-width: 1024px) { .ftr-grid.ftr-cols5 { grid-template-columns: minmax(0, 1.4fr) repeat(5, minmax(0, 1fr)); } }", css)

    def test_documents_words_are_whole_quotes(self):
        rows = self.w["L"]["docs-vs-chain/"]["rows"]
        self.assertTrue(all(FP.quotes_closed(p["docs"]["documented"]) and FP.quotes_closed(p["docs"]["observed"]) for p in rows))
        for p in rows:
            self.assertLessEqual(len(p["docs"]["documented"]), FP.DOC_WORDS, p["slug"])
        t = self.w["out"]["docs-vs-chain/"]
        cells = re.findall(r'<td data-label="The documents say">(.*?)</td>', t)
        self.assertEqual(len(cells), len(rows))
        for c, p in zip(cells, rows):
            self.assertEqual("read the record</a>" in c, not p["docs"]["sourced"], p["slug"])
            self.assertEqual("it quotes no words" in c, not p["docs"]["quoted"], p["slug"])
            self.assertEqual("The rest is on" in c, p["docs"]["documented_cut"], p["slug"])
        self.assertNotIn("no row has left", t)
        self.assertNotIn("parameter delta", t.split('<article class="memo" data-page=', 1)[1])
        # the cutter: whole parts only, never inside a quotation; an apostrophe is not a quotation mark
        self.assertEqual(FP.doc_words("'a; b' (x.org/1) / 'c' (y.org)", 20), ("'a; b' (x.org/1)", True))
        self.assertTrue(FP.quotes_closed("'Puffer's multisig' (docs.puffer.fi)"))
        self.assertFalse(FP.quotes_closed("'Before any minting action occurs."))
        self.assertTrue(FP.quotes_closed("'l1Bridge: '0xb8901acB165ed027E32754E0FFe830802919727f'' (raw.githubusercontent.com/x)"))
        with self.assertRaises(AssertionError):
            FP.doc_words("'" + "word " * 100 + "'", 40)

    def test_use_page_dates(self):
        out = self.w["out"]
        for rel in [f"learn/{k}/" for k in FP.LEARN] + ["listed/"]:
            t = out[rel]
            got = re.findall(r'<time datetime="(\d{4}-\d\d-\d\d)" data-change-date>', t)
            reads = re.findall(r'<time datetime="(\d{4}-\d\d-\d\d)" data-reading-date>', t)
            newest = max(d for *_, d in FP.LISTINGS) if rel == "listed/" else None
            self.assertEqual(got, [max([FP.TEXT_PINS[rel][0]] + reads + ([newest] if newest else []))], rel)
            self.assertEqual(FP.text_fingerprint(t), FP.TEXT_PINS[rel][1], rel)
            self.assertEqual(bool(reads), rel != "listed/", rel)
        p, _, _, _, day = FP._example(BS, self.w["F"], FP.block_times(ROOT, self.radar))
        self.assertIn(f'its newest reading is from <time datetime="{day}" data-reading-date>{day}</time>', out["learn/who-can-upgrade/"])
        # a changed page text fails the build until its pin is set again; a changed example answer or date does not
        html_ = out["learn/who-can-upgrade/"].replace(re.search(r'<time datetime="[^"]+" data-change-date>[^<]*</time>', out["learn/who-can-upgrade/"]).group(0), FP.CHANGED)
        self.assertEqual(FP.changed("learn/who-can-upgrade/", html_, day)[0], out["learn/who-can-upgrade/"])
        with self.assertRaises(AssertionError):
            FP.changed("learn/who-can-upgrade/", html_.replace("One line, no key", "One line and no key"), day)
        ex = re.search(r"<span data-example>(.*?)</span>", html_).group(1)
        self.assertEqual(FP.changed("learn/who-can-upgrade/", html_.replace(ex, ex.replace("7 days", "8 days")), day)[1], FP.TEXT_PINS["learn/who-can-upgrade/"][0])

    def test_the_example_is_generated_from_the_record(self):
        import copy
        F, times = self.w["F"], FP.block_times(ROOT, self.radar)
        slug = BS.HERO_EXAMPLE[0]
        p, _, _, ex, _ = FP._example(BS, F, times)
        tl, q = p["timelock"], p["quorum"]
        self.assertIn(BS.E(ex), self.w["out"]["learn/who-can-upgrade/"])
        for part in (FP.say_dur(tl["seconds"]), f'block #{tl["block"]:,}', f'{q["k"]} of {q["n"]}', f'block #{q["block"]:,}',
                     FP.day_of(times[(tl["chain"], tl["block"])]), FP.day_of(times[(q["chain"], q["block"])])):
            self.assertIn(part, ex)
        G = copy.deepcopy(F)                                                         # a changed record changes the sentence
        G[slug]["timelock"]["seconds"], G[slug]["quorum"]["k"] = 86400, q["n"]
        ex2 = FP._example(BS, G, times)[3]
        self.assertIn("1 day", ex2)
        self.assertIn(f'{q["n"]} of {q["n"]}', ex2)
        G[slug]["timelock"]["kind"] = "nd"                                           # a fact no longer determined fails the build
        with self.assertRaises(AssertionError):
            FP._example(BS, G, times)

    def test_new_text_has_no_judgement_word(self):
        for rel, t in self.w["out"].items():
            art = t.split('<article class="memo" data-page=', 1)[1].split("</article>", 1)[0]
            self.assertEqual(FP.banned(art), [], rel)

    def test_use_pages_are_filled_from_the_site_lists(self):
        out, B = self.w["out"], BS.B2A
        for rel, t in out.items():
            self.assertNotIn("data-fill", t, rel)
        R = FP.prices(BS)
        self.assertEqual(list(R), list(B.REMOTE_TOOLS))
        t = out["learn/connect-mcp-agent/"]
        tb = t.split('data-tool-table>', 1)[1].split("</tbody>", 1)[0]
        self.assertEqual(re.findall(r'<tr><td data-label="Tool"><code>([^<]+)</code>', tb), list(B.REMOTE_TOOLS))
        self.assertIn(f"{B.WHO_CONTROLS_DAILY_QUOTA} a day", R["who_controls"][1])
        self.assertEqual(R["pacta_check_preflight"][1:], (f"{B.FREE_DAILY_QUOTA} a day", "$0.01 a call"))
        self.assertIn(f"${dict((r, u) for r, u, _ in B.X402_ENDPOINTS)['/v1/x402/dossier']} a call", R["pacta_dossier"][2])
        t = out["learn/check-before-deposit/"]
        self.assertIn(B.PAY_TO, t)
        self.assertIn(f"{B.WHO_CONTROLS_TOOL} is free for {B.WHO_CONTROLS_DAILY_QUOTA} calls a day", t)
        # the run is one protocol (the site's example, Stader Labs ETHx): calls 1 and 3 on the token, call 2 on the record's Safe
        safe = FP.lookup_item(BS, BS.HERO_EXAMPLE[0])["preflightArgs"]["address"]
        run = t.split('id="run"', 1)[1].split("</section>", 1)[0]
        self.assertIn(safe, run)
        self.assertIn(BS.HERO_EXAMPLE[2], run)
        self.assertNotIn("Ethena", run)
        # a tool missing from either list, or a route that is not in openapi.json, fails the build
        what = dict(FP.TOOL_WHAT)
        try:
            del FP.TOOL_WHAT["forget"]
            with self.assertRaises(AssertionError):
                FP.prices(BS)
        finally:
            FP.TOOL_WHAT.clear()
            FP.TOOL_WHAT.update(what)
        k = "docs/api/v1/openapi.json"
        oa = FP._json(BS, "docs", "api", "v1", "openapi.json")
        try:
            FP._CACHE[k] = {**oa, "paths": {p_: v for p_, v in oa["paths"].items() if p_ != "/v1/memory/forget"}}
            with self.assertRaises(AssertionError):
                FP.prices(BS)
        finally:
            FP._CACHE[k] = oa
        self.assertEqual(FP.prices(BS), R)

    def test_copy_markers_and_what_the_buttons_copy(self):
        markers = []
        for k in FP.LEARN:
            art = self.w["out"][f"learn/{k}/"].split('<article class="memo" data-page=', 1)[1].split("</article>", 1)[0]
            boxes = re.findall(r'data-copy-count="([^"]+)".*?<pre>(.*?)</pre>', art, re.S)
            markers += [m for m, _ in boxes]
            self.assertEqual(art.count('class="copy"'), len(boxes), k)
            for m, pre in boxes:                    # the site's copy hook counts copy_curl / copy_mcp_url by what is copied
                pre = BS.html.unescape(pre) if hasattr(BS, "html") else pre
                self.assertTrue(pre.startswith("curl ") or "/mcp" in pre, m)
        self.assertEqual(sorted(markers), sorted(FP.COPY_MARKERS))
        self.assertNotIn("data-copy-count", read("tools", "app.src.js"))

    def test_listed(self):
        t = self.w["out"]["listed/"]
        art = t.split('<article class="memo" data-page=', 1)[1].split("</article>", 1)[0]
        tb = art.split("data-listings>", 1)[1].split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        rows = re.findall(r"<tr>(.*?)</tr>", tb)
        self.assertEqual(len(rows), len(FP.LISTINGS))
        days = [re.sub(r"<[^>]+>", "", re.findall(r'<td data-label="Listed">(.*?)</td>', r)[0]) for r in rows]
        self.assertTrue(all(re.fullmatch(r"\d{4}-\d\d-\d\d", d) for d in days), days)
        self.assertEqual(days, sorted(days, reverse=True))
        self.assertIn("x402-list.com", rows[0])
        self.assertIn("our row is on the front page", rows[0])
        self.assertIn(f"<p data-listed-left-out>{len(FP.LISTINGS_LEFT_OUT)} more directories are left out", art)
        self.assertIn(FP.LISTED_DESC, BS.html.unescape(art) if hasattr(BS, "html") else art)
        self.assertNotIn("mailto:", art)

    def test_not_in_sitemap_or_feeds(self):
        for f in ("sitemap.xml", "feed.xml", os.path.join("api", "v1", "feed.json")):
            t = read("docs", f)
            self.assertFalse([r for r in FP.PAGES if f"{BS.BASE_URL}/{r}" in t], f)

    def test_llms_files_name_each_page_once(self):
        """W9: one Guides and lists section in llms.txt and llms-full.txt, from GUIDES (the page list), each page once, no figure"""
        self.assertEqual(sorted(g[0] for g in FP.GUIDES), sorted(FP.PAGES))
        for f, md in (("llms.txt", True), ("llms-full.txt", False)):
            t = read("docs", f)
            sec = "\n".join(FP.llms_lines(BS.BASE_URL, md)) + "\n\n"
            self.assertEqual(t.count(sec), 1, f)
            self.assertEqual(t.count("## Guides and lists"), 1, f)
            for rel in FP.PAGES:
                self.assertEqual(sum(f"{BS.BASE_URL}/{rel}" in line for line in t.split("\n")), 1, (f, rel))
        mirror = read("docs", "llms", "index.html")                                     # the /llms/ HTML mirror of llms.txt
        self.assertTrue(all(f"{BS.BASE_URL}/{rel}" in mirror for rel in FP.PAGES))
        for _, _, line in FP.GUIDES:
            self.assertFalse(re.search(r"\d", re.sub(r"\bx402\b|\b1 of 1\b", "", line)), line)

    def test_linked_from_home_footer_and_mcp(self):
        """W8: the home page block, the footer's Guides and lists column on every page with a footer, /mcp/ (the three use pages);
        no link to /learn/ itself"""
        rels = [g[0] for g in FP.GUIDES]
        home = read("docs", "index.html")
        blk = re.search(r'<nav class="home-guides" aria-label="Guides and lists" data-home-guides>(.*?)</nav>', home, re.S).group(1)
        self.assertEqual(re.findall(r'href="([^"]*)"', blk), rels)
        mcp = re.search(r"<p data-mcp-guides>(.*?)</p>", read("docs", "mcp", "index.html"), re.S).group(1)
        self.assertEqual(re.findall(r'href="([^"]*)"', mcp), ["../" + g[0] for g in FP.GUIDE_USE])
        self.assertEqual(re.findall(r'">([^<]+)</a>', mcp), [BS.E(FP.TITLES[g[0]]) for g in FP.GUIDE_USE])
        n = 0
        for dp, _, fs in os.walk(os.path.join(ROOT, "docs")):
            for fn in fs:
                if not fn.endswith(".html"):
                    continue
                t = open(os.path.join(dp, fn), encoding="utf-8").read()
                self.assertFalse(re.search(r'href="(?:(?:\.\./)*|/|https://pacta\.wtf/)learn/"', t), fn)
                if 'class="ftr"' not in t:
                    continue
                n += 1
                col = re.search(r'<div class="ftr-grid ftr-cols5">.*?<div><h2>Guides and lists</h2><ul>(.*?)</ul></div><div><h2>Company</h2>', t, re.S)
                self.assertTrue(col, os.path.join(dp, fn))
                hs = re.findall(r'href="([^"]*)"', col.group(1))
                self.assertEqual([h[len(h) - len(r):] for h, r in zip(hs, rels)], rels, os.path.join(dp, fn))
                self.assertEqual(re.findall(r'">([^<]+)</a>', col.group(1)), [BS.E(g[1]) for g in FP.GUIDES])
        self.assertGreater(n, 300)


class RecordLinks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w, cls.idx, _ = built()
        cls.F = cls.w["F"]

    def test_every_record_page(self):
        for slug, p in self.F.items():
            t = read("docs", "protocols", slug, "index.html")
            nav = re.search(r'<nav class="fact-links" aria-label="Lists this record is on" data-fact-links>(.*?)</nav>', t).group(1)
            self.assertEqual(nav, FP.record_links(BS, self.F, slug)[len('<nav class="fact-links" aria-label="Lists this record is on" data-fact-links>'):-6])
            self.assertLess(t.index('<p class="lede">'), t.index("data-fact-links"), slug)
            self.assertLess(t.index("data-fact-links"), t.index("</header>", t.index('<p class="lede">')), slug)
            for c in p["chains"]:
                self.assertIn(f'href="../../chains/{c}/"', nav)
            self.assertEqual('href="../../control/timelock/"' in nav, p["timelock"]["kind"] == "listed", slug)
            self.assertEqual('href="../../control/multisig/"' in nav, p["quorum"]["kind"] == "listed", slug)
            self.assertEqual('href="../../docs-vs-chain/"' in nav, p["docs"]["kind"] == "listed", slug)
            self.assertIn('href="../../learn/who-can-upgrade/">How to check this yourself</a>', nav)
            self.assertEqual(FP.banned(nav), [], slug)

    def test_others_like_this(self):
        for slug, p in self.F.items():
            for c in p["chains"]:
                b, os_ = FP.others(self.F, slug, c)
                self.assertLessEqual(len(os_), 5)
                self.assertNotIn(slug, [q["slug"] for q in os_])
                self.assertTrue(all(c in q["chains"] for q in os_))
                if b:
                    self.assertTrue(all(q["baskets"][:1] == [b] for q in os_), slug)
        self.assertEqual(len(FP.others(self.F, "stader-labs-ethx", "ethereum")[1]), 5)


if __name__ == "__main__":
    unittest.main()
