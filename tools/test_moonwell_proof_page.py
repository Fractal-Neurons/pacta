"""/proof/moonwell-cbeth/: the Moonwell cbETH replay proof page. Its article is the approved text word for word (93 lines, pinned
by sha256 and length, with no draft banner), the page carries ROBOTS_META, and nothing else on the site links to it.

    python3 -m unittest tools/test_moonwell_proof_page.py
"""
import hashlib
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_site as BS  # noqa: E402

PAGE = os.path.join("docs", "proof", "moonwell-cbeth", "index.html")
ARTICLE_SHA256 = "700b2a2d9d7712fdfbeaae7bf090b8cda9fc0639918901c167a35d586eaba414"   # the approved article, its 93 lines joined by "\n"
ARTICLE_CHARS = 8341
TITLE = "The change that broke a Moonwell market sat in the queue for 24 hours · Pacta"
HREFS = ["https://forum.moonwell.fi/t/mip-x43-cbeth-oracle-incident-summary/2068",
         "https://decrypt.co/358374/oracle-error-leaves-defi-lender-moonwell-1-8-million-bad-debt"]
BANNER = ["DRAFT", "box warn", "not published"]
UNLISTED_FROM = ["index.html", os.path.join("mcp", "index.html"), "sitemap.xml", "feed.xml", "llms.txt", "llms-full.txt"]


def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def article_of(page):
    head = '<main id="main" class="memo-wrap"><article class="memo">\n'
    assert page.count(head) == 1 and page.count("</article></main>") == 1
    return page[page.index(head) + len(head):page.index("</article></main>")]


class ArticleText(unittest.TestCase):
    def test_source_file_is_the_approved_text(self):
        a = read("data", "proof", "moonwell-cbeth-article.html")
        self.assertTrue(a.endswith("</small></p>\n"))
        body = a[:-1]
        self.assertEqual(hashlib.sha256(body.encode("utf-8")).hexdigest(), ARTICLE_SHA256)
        self.assertEqual(len(body), ARTICLE_CHARS)
        self.assertEqual(len(body.split("\n")), 93)
        self.assertTrue(body.startswith("<h1>The change that broke a Moonwell market sat in the queue for 24 hours</h1>\n"))
        self.assertTrue(body.split("\n")[-1].startswith("<p><small>Source: historical replay of 4 incidents, Pacta, 26 Nov 2026."))

    def test_built_article_is_the_file_byte_for_byte(self):
        self.assertEqual(article_of(read(PAGE)), read("data", "proof", "moonwell-cbeth-article.html"))

    def test_no_draft_banner(self):
        page = read(PAGE)
        for s in BANNER:
            self.assertNotIn(s, page, s)

    def test_only_the_two_source_links_in_the_article(self):
        art = article_of(read(PAGE))
        self.assertEqual(re.findall(r'<a href="([^"]+)">', art), HREFS)
        self.assertEqual(len(re.findall(r"<a\b", art)), 2)
        for tag in ("<button", "<form", "<input", "<script", "<img", "<iframe"):
            self.assertNotIn(tag, art, tag)


class PageChrome(unittest.TestCase):
    def test_title_robots_and_layout(self):
        page = read(PAGE)
        self.assertEqual(re.findall(r"<title>([^<]*)</title>", page), [TITLE])
        self.assertEqual(re.findall(r'<meta name="robots" content="([^"]*)">', page), [BS.ROBOTS_META])
        self.assertIn('<link rel="canonical" href="https://pacta.wtf/proof/moonwell-cbeth/">', page)
        self.assertIn('<main id="main" class="memo-wrap"><article class="memo">', page)
        self.assertEqual(page.count('<header class="topbar"'), 1)
        self.assertEqual(page.count('<footer class="ftr"'), 1)

    def test_layout_rules(self):
        css = BS.PROOF_MOONWELL_CSS
        self.assertEqual(read(PAGE).count(css), 1)
        for rule in (".memo .wrap{max-width:none;margin:12px 0 16px;padding:0;overflow-x:auto}",
                     ".memo .wrap table{display:table;max-width:none;overflow:visible;", ".memo .wrap th{text-transform:none;", ".memo .wrap table:has(th:nth-child(5)) :is(th,td){white-space:nowrap}",
                     ".memo .addr{word-break:break-all}", ".memo pre{margin:12px 0 0;padding:12px 14px;overflow-x:auto;white-space:pre;"):
            self.assertIn(rule, css)

    def test_phone_scroll_design(self):
        """Phones only: every new rule sits in the max-width 767px block, after all the earlier rules; the five-column table pins its
        Market column (opaque page colour, divider) and wraps its headers; each scroll box shades an edge only while content lies past it;
        nothing paints past the Market column's divider (no pseudo-element overlay, no animation), so no scrolled number is ever covered."""
        css = BS.PROOF_MOONWELL_CSS
        phone = "@media (max-width: 767px){"
        self.assertEqual(css.count(phone), 1)
        before, block = css.split(phone)
        self.assertNotIn("sticky", before)
        self.assertNotIn("local", before)
        five = ".memo .wrap table:has(th:nth-child(5)) "
        for rule in (five + ":is(th,td):first-child{position:sticky;left:0;z-index:2;padding-right:10px;background:var(--background);box-shadow:inset -1px 0 0 var(--border)}",
                     five + "th{white-space:normal;vertical-align:bottom}", ".memo pre{--mw-bg:var(--muted)}",
                     ".memo .wrap,.memo pre{--mw-bg:var(--background);"):
            self.assertIn(rule, block)
        self.assertEqual(block.count("no-repeat local"), 2)
        self.assertEqual(block.count("no-repeat scroll"), 2)
        self.assertEqual(re.findall(r"(\d+)px 100% no-repeat local", block), ["64", "64"])
        self.assertEqual(re.findall(r"(\d+)px 100% no-repeat scroll", block), ["32", "32"])
        self.assertTrue(css.endswith(five + ":is(th,td):nth-child(2){padding-left:6px}}</style>"))
        for overlay in ("::after", "::before", ":after", ":before", "@keyframes", "animation", "@supports", "content:"):
            self.assertNotIn(overlay, css)
        self.assertNotIn("<", css[len("<style>"):-len("</style>")])

    def test_page_is_a_rebuild_of_the_sources(self):
        self.assertEqual(read(PAGE), BS.proof_moonwell_page(json.loads(read("docs", "api", "v1", "index.json"))))


class Unlisted(unittest.TestCase):
    def test_named_surfaces_do_not_link_it(self):
        names = UNLISTED_FROM + [os.path.join("briefs", d, "index.html") for d in os.listdir(os.path.join(ROOT, "docs", "briefs"))
                                 if os.path.isfile(os.path.join(ROOT, "docs", "briefs", d, "index.html"))]
        names += [os.path.join("briefs", "index.html")] if os.path.isfile(os.path.join(ROOT, "docs", "briefs", "index.html")) else []
        self.assertGreater(len(names), len(UNLISTED_FROM))
        for n in names:
            self.assertNotIn("moonwell-cbeth", read("docs", n), n)

    def test_no_file_in_docs_names_it_but_the_page(self):
        hits = []
        for d, _, files in os.walk(os.path.join(ROOT, "docs")):
            for f in files:
                p = os.path.join(d, f)
                if os.path.splitext(f)[1] not in (".html", ".xml", ".txt", ".json", ".js", ".css", ".md", ".yaml", ".yml"):
                    continue
                with open(p, encoding="utf-8", errors="replace") as fh:
                    if "proof/moonwell-cbeth" in fh.read():
                        hits.append(os.path.relpath(p, ROOT))
        self.assertEqual(hits, [PAGE])


if __name__ == "__main__":
    unittest.main()
