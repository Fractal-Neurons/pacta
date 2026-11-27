"""/proof/moonwell-cbeth/: the Moonwell cbETH replay proof page. Its article is the approved text word for word (93 lines, pinned
by sha256 and length, with no draft banner), the page carries ROBOTS_META, and exactly four places link to it: the home page's
agents card, /mcp/'s Tools section (under the tool list and its Indexed protocols line), llms.txt (and its /llms/ mirror) and README.md, each with the approved line word for word
and nothing around it. Briefs, sitemap.xml, feed.xml and llms-full.txt do not.

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
LINE = ("Replay with public chain data: on Moonwell a wrong price source sat in the queue for 24.04 hours before it ran. "
        "Four commands to check it yourself.")
URL = "https://pacta.wtf/proof/moonwell-cbeth/"
MD = f"- [{LINE}]({URL})"
LINKED_FROM = {   # file -> the whole block: the approved line as the link text, nothing around it
    os.path.join("docs", "index.html"): f'<p class="s" data-moonwell-proof><a href="proof/moonwell-cbeth/">{LINE}</a></p>',
    os.path.join("docs", "mcp", "index.html"): f'<p data-moonwell-proof><a href="../proof/moonwell-cbeth/">{LINE}</a></p>',
    os.path.join("docs", "llms.txt"): MD,
    os.path.join("docs", "llms", "index.html"): MD,
    "README.md": MD,
}
UNLISTED_FROM = ["sitemap.xml", "feed.xml", "llms-full.txt"]


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


class Linked(unittest.TestCase):
    def test_the_approved_line(self):
        self.assertEqual(BS.PROOF_MOONWELL_LINE, LINE)
        self.assertEqual(len(LINE), 147)
        self.assertNotIn("<", LINE)
        self.assertNotIn("&", LINE)

    def test_each_place_has_the_line_and_the_link_once(self):
        for f, block in LINKED_FROM.items():
            t = read(f)
            self.assertEqual(t.count(block), 1, f)
            self.assertEqual(t.count(LINE), 1, f)
            self.assertEqual(t.count("moonwell-cbeth"), 1, f)

    def test_markdown_places_are_a_bare_list_item(self):
        for f in (os.path.join("docs", "llms.txt"), "README.md"):
            self.assertEqual([ln for ln in read(f).split("\n") if "moonwell-cbeth" in ln], [MD], f)

    def test_html_places_link_text_is_the_line(self):
        for f, href in ((os.path.join("docs", "index.html"), "proof/moonwell-cbeth/"), (os.path.join("docs", "mcp", "index.html"), "../proof/moonwell-cbeth/")):
            self.assertEqual(re.findall(r'<a href="([^"]*moonwell-cbeth[^"]*)">([^<]*)</a>', read(f)), [(href, LINE)], f)

    def between(self, f, start, end):
        t = read(f)
        i = t.index(start)
        self.assertLess(i, t.index(LINKED_FROM[f]), f)
        self.assertLess(t.index(LINKED_FROM[f]), t.index(end, i), f)

    def test_home_agents_card(self):
        home = os.path.join("docs", "index.html")
        self.between(home, '<section class="sec" id="audiences">', 'class="teams-card"')
        self.between(home, 'class="agents-card"', 'data-slot="card-footer"')
        t = read(home)
        card = t.index('class="agents-card"')
        self.assertIn("AI agents &amp; builders", t[card:t.index(LINKED_FROM[home])])
        content = t.index('data-slot="card-content">', card) + len('data-slot="card-content">')
        self.assertEqual(t.index(LINKED_FROM[home]), content)   # the card content opens with it

    def test_mcp_under_the_tool_list(self):
        """The tool list's own line changes whenever a tool is added, so one unchanged line (Indexed protocols) sits between."""
        mcp = os.path.join("docs", "mcp", "index.html")
        self.between(mcp, '<section class="memo-sec" id="tools">', "</section>")
        tools, ip, proof = read(mcp).split('<section class="memo-sec" id="tools">')[1].split("\n")[:3]
        self.assertTrue(tools.startswith("<h2>Tools (") and tools.endswith("</li></ul>"), tools[:40])
        self.assertTrue(ip.startswith("<p>Indexed protocols: "), ip[:40])
        self.assertEqual(proof, LINKED_FROM[mcp])

    def test_llms_and_readme_api_sections(self):
        self.between(os.path.join("docs", "llms.txt"), "\n## API & MCP for agents", "\n## Agent feeds")
        self.between(os.path.join("docs", "llms", "index.html"), "\n## API &amp; MCP for agents", "\n## Agent feeds")
        self.between("README.md", "\n## Pre-execution API, Remote MCP & x402 Endpoints", "\n### MCP recipes")


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
        self.assertEqual(sorted(hits), sorted([PAGE] + [f for f in LINKED_FROM if f.startswith("docs")]))


if __name__ == "__main__":
    unittest.main()
