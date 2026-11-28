"""Pages for assistants: lists by one checked fact, a page per chain, three use pages, /listed/, and the links block on every
/protocols/<slug>/ page.

Every number on these pages is computed at build time from the published records (docs/api/v1/index.json and rpc-pinned.json),
through the five control facts build_site.scorecards() derives from them: the same facts each record page shows. A fact the
records do not decide ("n", not determined) keeps a protocol off a list, and the list says how many were left out for that
reason. check() fails the build when a count in a page's first lines is not the number of rows under it.

The pages:
  /control/timelock/       timelock floor: the shortest admin delay read on a protocol's sampled timelocked controls
  /control/multisig/       signer quorum: the lowest threshold of any multisig on any sampled control (a key with no code = 1 of 1)
  /docs-vs-chain/          the documentation comparison of the Base-EAS-attested records (where the two differ)
  /chains/ethereum/, /chains/base/   every protocol on the chain with the facts above
  /learn/who-can-upgrade/, /learn/check-before-deposit/, /learn/connect-mcp-agent/   routes, tool names, free limits and prices
                           from the site's own price and tool lists (tools/build_b2a_feeds.py, checked against docs/api/v1/
                           openapi.json at build time); every example answer generated from a record, with its block and date
  /listed/                 the listings Pacta is on (LISTINGS: each one checked over HTTP on 28 Nov 2026)
No list of protocols "with no upgrade path": no record field says a protocol has no proxy and no admin who can replace the code
(the upgrade fact only says a sampled contract is not a proxy), so that page is not built.

The pages carry no grade and no score; sitemap.xml, feed.xml and llms.txt do not list them (their entries are added separately).
"""
import datetime as dt
import glob
import hashlib
import html
import json
import os
import re
import urllib.parse

import control_diff as CD
import scorecard as SC

DAY = 86400
CHAIN_PAGES = ("ethereum", "base")
LIST_PAGES = ("control/timelock/", "control/multisig/", "docs-vs-chain/")
LEARN = {"who-can-upgrade": "How to check who can upgrade a DeFi contract",
         "check-before-deposit": "Check a protocol before your agent deposits",
         "connect-mcp-agent": "Add Pacta to Claude, Cursor or your own agent: one line, the first call, what is free and what costs"}
PAGES = (["control/timelock/", "control/multisig/", "docs-vs-chain/"] + [f"chains/{c}/" for c in CHAIN_PAGES]
         + [f"learn/{k}/" for k in LEARN] + ["listed/"])
TITLES = {"control/timelock/": "Protocols behind a timelock, by length of delay",
          "control/multisig/": "Protocols by the fewest signers needed on any control",
          "docs-vs-chain/": "Protocols whose documents differ from the chain",
          "listed/": "Where Pacta is listed",
          **{f"chains/{c}/": f"Who controls DeFi protocols on {c.capitalize()}" for c in CHAIN_PAGES},
          **{f"learn/{k}/": t for k, t in LEARN.items()}}
# The meta description of the pages without a count in it; a list or chain page's own description leads with its count ("75 DeFi
# protocols ..."), so llms.txt and llms-full.txt name those pages with the line below it in GUIDES, which holds no figure.
DESC = {"learn/who-can-upgrade/": "Find the proxy, its admin, the timelock and its delay, and the multisig behind a DeFi contract, read from "
                                  "the chain at a named block. One call, free within a daily limit, no key.",
        "learn/check-before-deposit/": "Three checks an agent can run before it moves funds into a DeFi protocol: who can change the "
                                       "contract, what it depends on, and what changed since the last look. Free within daily limits; "
                                       "the page lists what is paid per call.",
        "learn/connect-mcp-agent/": "Connect an agent to Pacta's MCP server in one line, make a first call, and see what is free and "
                                    "what an agent pays for per call over x402.",
        "listed/": "The directories and registries that list Pacta's MCP server and paid API, with a link to each listing."}
# Where the pages are linked from, and how the files made for assistants name them: ONE list, in this order. It feeds the block on
# the home page and the "Guides and lists" column of every page's footer (build_site.home / footer), the how-to links on /mcp/
# (the three use pages) and the "Guides and lists" section of llms.txt and llms-full.txt. Each entry: (path, link label, the line
# llms.txt and llms-full.txt give the page). No line holds a figure, so none can go stale between builds. No link goes to /learn/
# itself (it has no page of its own); verify_site_v2.py checks both.
GUIDES = (
    ("learn/who-can-upgrade/", "Who can upgrade", DESC["learn/who-can-upgrade/"]),
    ("learn/check-before-deposit/", "Check before deposit", DESC["learn/check-before-deposit/"]),
    ("learn/connect-mcp-agent/", "Add Pacta to an agent", DESC["learn/connect-mcp-agent/"]),
    ("control/timelock/", "Timelock delays", "The DeFi protocols that put a delay between a decision to change a contract and its effect, "
                                             "shortest delay first, each read from the chain at a named block."),
    ("control/multisig/", "Fewest signers", "DeFi protocols by the fewest signers needed on any sampled control: the lowest multisig "
                                            "threshold found, a single key counting as 1 of 1, each read from the chain at a named block."),
    ("docs-vs-chain/", "Documents vs chain", "The DeFi protocols whose published documents say one thing about who controls the contracts "
                                             "while the chain shows another, each difference with its block."),
    ("chains/ethereum/", "On Ethereum", "Every DeFi protocol Pacta has checked on Ethereum: how each can be upgraded, the timelock delay "
                                        "and the fewest signers needed, read from the chain."),
    ("chains/base/", "On Base", "Every DeFi protocol Pacta has checked on Base: how each can be upgraded, the timelock delay and the "
                                "fewest signers needed, read from the chain."),
    ("listed/", "Where Pacta is listed", DESC["listed/"]))
GUIDE_USE = [g for g in GUIDES if g[0].startswith("learn/")]


def guide_links(H, pre, guides=GUIDES):
    return [f'<a href="{pre}{rel}">{H.E(label)}</a>' for rel, label, _ in guides]


def home_guides(H, pre=""):
    """the block on the home page: the three use pages, then the lists and /listed/"""
    lists = [g for g in GUIDES if g not in GUIDE_USE]
    return ('<nav class="home-guides" aria-label="Guides and lists" data-home-guides>'
            f'<p class="s" style="margin-top:24px"><b>How to use Pacta:</b> {H.SEP.join(guide_links(H, pre, GUIDE_USE))}</p>'
            f'<p class="s" style="margin-top:8px"><b>Lists from the records:</b> {H.SEP.join(guide_links(H, pre, lists))}</p></nav>')


def mcp_guides(H, pre="../"):
    """the how-to links on /mcp/: the three use pages by their titles"""
    return ('<p data-mcp-guides>How-to pages: ' + H.SEP.join(f'<a href="{pre}{rel}">{H.E(TITLES[rel])}</a>' for rel, _, _ in GUIDE_USE)
            + '.</p>')


def llms_lines(base, md):
    """the "Guides and lists" section of llms.txt (md: markdown links) and llms-full.txt (plain addresses)"""
    return ["## Guides and lists"] + [f"- [{base}/{rel}]({base}/{rel}): {line}" if md else f"- {base}/{rel}: {line}" for rel, _, line in GUIDES]


# the use pages' copy buttons: which page and which button, never what was copied (the counting is not switched on here)
COPY_MARKERS = ("who-can-upgrade:call", "who-can-upgrade:connect", "check-before-deposit:call", "connect-mcp-agent:claude-code",
                "connect-mcp-agent:cursor")
assert sorted(g[0] for g in GUIDES) == sorted(PAGES) and len({g[1] for g in GUIDES}) == len(GUIDES)
assert not [g for g in GUIDES if re.search(r"\d", re.sub(r"\bx402\b|\b1 of 1\b", "", g[2]))], "a figure in an llms line"
BANNED = re.compile(r"\b(?:grade[sd]?|scores?|scored|safe|unsafe|safer|safest|risky|riskier|best|worst)\b", re.I)


def banned(html_):
    """Judgement words in the visible text of new markup. Not counted: "Safe" with a capital S, the multisig contract ("a 3-of-5
    Safe"), and "fail-safe", a mechanism named in a record's own surface title ("Fail-safe recovery: bridge declared dead ...")."""
    txt = re.sub(r"<[^>]+>", " ", html_)
    return [m.group(0) for m in BANNED.finditer(txt) if m.group(0) != "Safe" and not txt[max(0, m.start() - 5):m.start()].lower() == "fail-"]

_DUR = r"(\d+d(?: \d+h)?|\d+(?:\.\d+)?h|\d+s)"
_TL_ON = re.compile(r"^" + _DUR + r" minimum enforced delay on sampled (?:admin )?timelocked surfaces(?: \(.*\))?$")
_TL_ZERO = re.compile(r"^(?:No enforced delay on at least one sampled control surface \(0s|0s: |No timelock in the sampled )")
# a correction's floor sentence that starts at a 0s reading on a named control ("0s on TREE token blacklisting (...); ...") is a zero
# floor, unless the sentence leaves that reading itself in doubt: "unverified" in the reading's own clause, or in a later clause that
# is about anything other than whether a documented delay covers the control. "0s on the legacy cbBTC vault beacon upgrade path
# (3-of-6 Safe); whether the documented 24h Opt-in delay covers this vault is unverified" is a zero floor: the 0s is read from the
# chain, and what is open is the documents' coverage, not the reading (zero_on()).
_TL_ZERO_ON = re.compile(r"^0s on ")
_UNVERIFIED = re.compile(r"\bunverified\b")
_DOC_COVERS = re.compile(r"^whether the documented [^;]* covers [^;]* is unverified$")
# the upgrade path's own delay, in the upgrade fact's words: "Upgradeable behind a ≥48h delay (2d ...)" / "... with no enforced delay"
_UP_DELAY = re.compile(r"^Upgradeable behind a (?:≥48h|1h–47h) delay \(" + _DUR + r"\b")
_UP_NONE = re.compile(r"^Upgradeable with no enforced delay\b")
_DUR_ANY = re.compile(r"(?<![\w≥–.])" + _DUR + r"(?![\w–])")     # any duration in a sentence, not the class labels ≥48h and 1h–47h
_Q_NOF = re.compile(r"\b(\d{1,2})-of-(\d{1,2})\b")
_Q_CANON = re.compile(r"^Lowest controlling quorum: (?:\d{1,2}-of-\d{1,2}|a single key)$")


def dur_seconds(tok):
    """'7d' / '1d 12h' / '1.5h' / '168h' / '300s' (the duration a scorecard fact sentence starts with) -> seconds."""
    m = re.fullmatch(r"(\d+)d(?: (\d+)h)?|(\d+(?:\.\d+)?)h|(\d+)s", tok)
    assert m, tok
    s = (int(m.group(1)) * DAY + int(m.group(2) or 0) * 3600 if m.group(1) else
         round(float(m.group(3)) * 3600) if m.group(3) else int(m.group(4)))
    return s


def said_seconds(t):
    """say_dur's words back to seconds: '2 days', '1 day 12 hours', '6 hours', '30 minutes', '45 seconds'"""
    m = re.fullmatch(r"(\d+) days?(?: (\d+) hours?)?|(\d+(?:\.\d+)?) hours?|(\d+) minutes?|(\d+) seconds?", t)
    assert m, t
    return (int(m.group(1)) * DAY + int(m.group(2) or 0) * 3600 if m.group(1) else round(float(m.group(3)) * 3600) if m.group(3)
            else int(m.group(4)) * 60 if m.group(4) else int(m.group(5)))


def upgrade_delay(text):
    """the seconds the upgrade path waits, by the upgrade fact's own sentence; None where the sentence names no delay of its own"""
    m = _UP_DELAY.match(text)
    return dur_seconds(m.group(1)) if m else 0 if _UP_NONE.match(text) else None


def zero_on(value):
    """True for a "0s on <control>" floor sentence whose 0s reading stands: no "unverified" in its first clause, and in a later
    clause only where that clause asks whether a documented delay covers the control (_TL_ZERO_ON above)"""
    if not _TL_ZERO_ON.match(value):
        return False
    first, *later = [c.strip() for c in value.split(";")]
    return not _UNVERIFIED.search(first) and all(_DOC_COVERS.match(c) or not _UNVERIFIED.search(c) for c in later)


def timelock_kind(state, value, up):
    """(kind, seconds) of a protocol's timelock floor, the shortest delay on any sampled control, the upgrade path included
    (scorecard.factors()). kind: "listed" (a delay above zero), "zero" (a sampled control has none), "nd" (not determined) or
    "doubt" (no single delay for the sampled controls: not determined too). up: upgrade_delay() of the protocol's upgrade fact."""
    m = _TL_ON.match(value)
    if state == "n":
        # a correction can set the upgrade fact alone: when it says the upgrade path has no enforced delay, that sampled control has none
        return ("zero", 0) if up == 0 else ("nd", None)
    if m:
        s = dur_seconds(m.group(1))
        return ("listed" if s > 0 else "zero"), s
    if _TL_ZERO.match(value) or zero_on(value):
        return "zero", 0
    return "doubt", None


def say_dur(s):
    """7 days / 1 day 12 hours / 2 hours / 30 minutes / 45 seconds"""
    if s >= DAY:
        d, h = divmod(s // 3600, 24)
        return f"{d} day{'s' if d != 1 else ''}" + (f" {h} hour{'s' if h != 1 else ''}" if h else "")
    if s >= 3600:
        h = s / 3600
        return f"{h:g} hour{'s' if h != 1 else ''}"
    if s >= 60 and s % 60 == 0:
        return f"{s // 60} minute{'s' if s != 60 else ''}"
    return f"{s} second{'s' if s != 1 else ''}"


def block_times(root, radar=None):
    """{(chain, block): unix time} from the pinned data in the repository: the controller-fact pins (tools/
    graph_controller_facts.json), the radar's finalized pins, and the header lines of the audit summaries every Base-EAS-attested
    record names (audits/**/*.md: "Block Timestamp" or "... Mainnet pin ... timestamp ... (`T`)"). Two sources for one block must
    agree, and on each chain a later block never has an earlier time."""
    out = {}

    def put(ch, b, t, src):
        k = (ch, int(b))
        assert out.get(k, int(t)) == int(t), (k, out.get(k), t, src)
        out[k] = int(t)
    pins = json.load(open(os.path.join(root, "tools", "graph_controller_facts.json"), encoding="utf-8"))["pins"]
    for key, v in sorted(pins.items()):
        if v.get("timestamp"):
            put(key.split("@")[0], v["block_number"], v["timestamp"], key)
    for key, ch in (("refreshed_at", "ethereum"), ("refreshed_at_base", "base")):
        r = (radar or {}).get(key) or {}
        if r.get("block_number") and r.get("block_timestamp"):
            put(ch, r["block_number"], r["block_timestamp"], "radar " + key)
    for p in sorted(glob.glob(os.path.join(root, "audits", "**", "*.md"), recursive=True)):
        with open(p, encoding="utf-8", errors="replace") as fh:
            top = fh.read(6000)
        m1 = re.search(r"^- \*\*(Ethereum|Base) Mainnet Block\*\*: `(\d+)`", top, re.M)
        m2 = re.search(r"^- \*\*Block Timestamp\*\*: `(\d{10})`", top, re.M)
        if m1 and m2:
            put(m1.group(1).lower(), m1.group(2), m2.group(1), p)
        for m in re.finditer(r"^- \*\*(Ethereum|Base) Mainnet pin\*\*[^:\n]*: `(\d+)`[^\n]*?timestamp `[^`]*` \(`(\d{10})`\)", top, re.M):
            put(m.group(1).lower(), m.group(2), m.group(3), p)
    for ch in {k[0] for k in out}:
        seq = sorted((b, t) for (c, b), t in out.items() if c == ch)
        assert all(a[1] <= b[1] for a, b in zip(seq, seq[1:])), f"{ch}: block times out of order"
    return out


def day_of(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d")


def newest_day(blocks, times):
    """The date of the newest block among (chain, block) pairs: the newest block of each chain, then the later of those."""
    top = {}
    for ch, b in blocks:
        top[ch] = max(int(b), top.get(ch, 0))
    missing = [(ch, b) for ch, b in top.items() if (ch, b) not in times]
    assert not missing, f"no block time in the pinned data for {missing}"
    return day_of(max(times[(ch, b)] for ch, b in top.items()))


def _factor(card, key):
    return next(f for f in card["factors"] if f["key"] == key)


def _controller_pin(H, es, pred):
    """(chain, block) of the controller fact that decided a factor (a fact, not a record, was the evidence)."""
    cf = json.load(open(H.CONTROLLER_FACTS_SRC, encoding="utf-8"))
    hits = []
    for e in es:
        ch = H.chain_of(e)
        addrs = {e["target_contract"].lower()} | {str(e.get(k) or "").lower() for k in ("controller_address", "upstream_controller")}
        addrs.add(str((e.get("observed_delay_source") or {}).get("contract") or "").lower())
        for a in sorted(x for x in addrs if x.startswith("0x")):
            f = cf["contracts"].get(f"{ch}:{a[2:]}")
            if f and pred(f):
                pin = cf["pins"][f.get("pin") or ch]   # no pin = read at the chain's base pin (as graph_manifest.py reads it)
                hits.append((ch, int(pin["block_number"])))
    assert hits, "controller fact not found"
    return max(hits)


def protocol_facts(H, idx, sp, cards):
    """slug -> the facts the pages use, each with the record (or controller fact) and block it was read at."""
    out = {}
    for name, v in sp.items():
        slug, es = v["slug"], v["entries"]
        card = cards[slug]
        by_id = {e["id"]: e for e in es}

        def where(f, pred=None):
            rid = f.get("evidenceRecordId")
            if rid and rid in by_id:
                e = by_id[rid]
                return {"rid": rid, "surface": e["surface"], "chain": H.chain_of(e), "block": int(e["block_number"])}
            ch, b = _controller_pin(H, es, pred)
            return {"rid": None, "surface": None, "chain": ch, "block": b}
        p = {"slug": slug, "name": name, "chains": [c for c in H.CHAINS if any(H.chain_of(e) == c for e in es)],
             "category": es[0].get("category", ""), "newest": {}}
        for e in es:
            p["newest"][H.chain_of(e)] = max(int(e["block_number"]), p["newest"].get(H.chain_of(e), 0))
        p["baskets"] = [k for k in H.baskets_of(p["category"], p["chains"]) if k != "base"]
        up = _factor(card, "upgrade")
        p["upgrade"] = {"state": up["state"], "text": up["value"], "seconds": upgrade_delay(up["value"])}
        # timelock floor
        f = _factor(card, "timelock")
        k_, s = timelock_kind(f["state"], f["value"], p["upgrade"]["seconds"])
        if k_ == "listed":
            p["timelock"] = {"kind": "listed", "seconds": s, "text": f["value"], **where(f, lambda c, s=s: c.get("timelock_min_delay") == s)}
        elif k_ == "zero":
            p["timelock"] = {"kind": "zero", "seconds": 0, "text": f["value"]}
        else:
            p["timelock"] = {"kind": "nd", "text": f["value"], **({"doubt": True} if k_ == "doubt" else {})}   # not determined: out
        # signer quorum
        f = _factor(card, "quorum")
        v_ = f["value"]
        m = _Q_NOF.search(v_)
        single = v_.find("a single key")
        if f["state"] == "n":
            p["quorum"] = {"kind": "nd", "text": v_}
        elif v_.startswith("DAO Governor"):
            p["quorum"] = {"kind": "governor", "text": v_}
        elif m or single >= 0:
            k, n = (1, 1) if single >= 0 and (not m or single < m.start()) else (int(m.group(1)), int(m.group(2)))
            assert 1 <= k <= n, (slug, v_)
            p["quorum"] = {"kind": "listed", "k": k, "n": n, "text": v_, "canonical": bool(_Q_CANON.match(v_)),
                           **where(f, lambda c, k=k: c.get("safe_threshold") == k)}
        else:
            p["quorum"] = {"kind": "nd", "doubt": True, "text": v_}
        # documents against the chain
        par = _factor(card, "parity")
        if par["state"] == "u":
            p["docs"] = {"kind": "uncompared"}
        elif par["state"] == "n":
            p["docs"] = {"kind": "nd", "text": par["value"]}
        elif card["grade"] == "delta":
            wd = CD.what_differs(es) or {}
            ch_ = [c for c in wd.get("changed") or [] if c.get("classification") == "parameter_delta"] or (wd.get("changed") or [])
            assert ch_, slug
            c0 = ch_[0]
            e = by_id[c0["recordId"]]
            words, cut = doc_words(H.plain(e.get("documented_reference", "") or c0["documented"]))   # the documents' words
            p["docs"] = {"kind": "listed", "finding": card["finding"], "more": len(ch_) - 1,
                         "documented": words, "documented_cut": cut, "quoted": bool(quote_marks(words)), "sourced": bool(_SOURCE.search(words)),
                         "attested": bool(e.get("base_eas_uid")) and _summary_ok(H, e),
                         "observed": _excerpt(H, e.get("onchain_observed", ""), c0["observed"]),
                         "rid": e["id"], "surface": e["surface"], "chain": H.chain_of(e), "block": int(e["block_number"])}
            assert quotes_closed(p["docs"]["documented"]) and quotes_closed(p["docs"]["observed"]), ("a shown quote is not closed", slug)
        else:
            p["docs"] = {"kind": "agree"}
        out[slug] = p
    return out


_QCH = "'\"“”‘’"


def quote_marks(t):
    """(index, +1 opening / -1 closing) for each quotation mark in t; an apostrophe between two letters or digits ("Puffer's") is
    not a mark. Single and double quotes nest (a record quotes "'l1Bridge: '0x…''")."""
    ev = []
    for i, ch in enumerate(t):
        if ch not in _QCH:
            continue
        prev, nxt = (t[i - 1] if i else " "), (t[i + 1] if i + 1 < len(t) else " ")
        if ch in "“‘" and not (ch == "‘" and prev.isalnum()):
            ev.append((i, 1))
        elif ch in "'’" and prev.isalnum() and nxt.isalnum():
            continue
        elif ch in "”’":
            ev.append((i, -1))
        elif (prev.isspace() or prev in "([{:/-" or prev in _QCH) and not nxt.isspace():
            ev.append((i, 1))
        elif not prev.isspace():
            ev.append((i, -1))
    return ev


def quotes_closed(t):
    """every quotation mark opened in t is closed in t, in order"""
    d = 0
    for _, v in quote_marks(t):
        d += v
        if d < 0:
            return False
    return d == 0


DOC_WORDS = 360
_SOURCE = re.compile(r"(?:^|(?<=[\s(:'\"]))(?:[a-z0-9-]+\.)+[a-z]{2,}(?=[/\s)(:;,']|$)|\b[\w.-]+\.(?:md|txt|html)\b")


def doc_words(text, limit=DOC_WORDS):
    """The documents' words as the record quotes them (documented_reference): whole, or when longer than limit, cut only between
    two whole parts ("; ", " / " or ". " outside every quotation and bracket), so a shown quote always ends with its own mark and
    the source that follows it. Returns (text, cut)."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= limit:
        return t, False
    marks, dq, db, inside = dict(quote_marks(t)), 0, 0, []
    for i, ch in enumerate(t):
        if i in marks:
            dq = max(0, dq + marks[i])
        elif ch in "([":
            db += 1
        elif ch in ")]":
            db = max(0, db - 1)
        inside.append(dq or db)
    ends = [m.start() + (1 if m.group(0) == ". " else 0) for m in re.finditer(r"; | / |\. ", t) if m.start() <= limit and not inside[m.start()]]
    assert ends, ("no whole part of the documents' words fits", t[:120])
    return t[:ends[-1]].rstrip(" ;/"), True


def _summary_ok(H, e):
    """the record's summary_doc exists and its SHA-256 is the record's summary_sha256 (what the Base attestation carries)"""
    f = os.path.join(H.ROOT, e.get("summary_doc") or "")
    if not (e.get("summary_doc") and os.path.isfile(f)):
        return False
    with open(f, "rb") as fh:
        return "0x" + hashlib.sha256(fh.read()).hexdigest() == (e.get("summary_sha256") or "").lower()


def _excerpt(H, full, short_v):
    """The record page's "What differs" excerpt (build_site.what_differs_html): the short value when it is whole, else a whole-word
    excerpt of the record's own text."""
    full, short_v = H.plain(full), H.plain(short_v)
    if not short_v.endswith("…") and len(short_v) <= 60:
        return short_v
    return H.clean_excerpt(full or short_v)


def lists(F):
    """The rows of each list, sorted by its fact, and what was left out and why."""
    ps = sorted(F.values(), key=lambda p: p["name"].lower())
    tl = sorted([p for p in ps if p["timelock"]["kind"] == "listed"], key=lambda p: (p["timelock"]["seconds"], p["name"].lower()))
    ms = sorted([p for p in ps if p["quorum"]["kind"] == "listed"], key=lambda p: (p["quorum"]["k"], p["quorum"]["n"], p["name"].lower()))
    dv = [p for p in ps if p["docs"]["kind"] == "listed"]                       # one fact (they differ): by protocol name
    return {
        "control/timelock/": {"rows": tl, "total": len(ps),
                              "zero": [p for p in ps if p["timelock"]["kind"] == "zero"],
                              "nd": [p for p in ps if p["timelock"]["kind"] == "nd"]},
        "control/multisig/": {"rows": ms, "total": len(ps),
                              "governor": [p for p in ps if p["quorum"]["kind"] == "governor"],
                              "nd": [p for p in ps if p["quorum"]["kind"] == "nd"]},
        "docs-vs-chain/": {"rows": dv, "total": len(ps),
                           "compared": [p for p in ps if p["docs"]["kind"] != "uncompared"],
                           "uncompared": [p for p in ps if p["docs"]["kind"] == "uncompared"],
                           "nd": [p for p in ps if p["docs"]["kind"] == "nd"],
                           "agree": [p for p in ps if p["docs"]["kind"] == "agree"]},
        **{f"chains/{c}/": {"rows": [p for p in ps if c in p["chains"]], "chain": c, "total": len(ps),
                            "both": [p for p in ps if all(c_ in p["chains"] for c_ in CHAIN_PAGES)],
                            "one": [p for p in ps if sum(c_ in p["chains"] for c_ in CHAIN_PAGES) == 1],
                            "neither": [p for p in ps if not any(c_ in p["chains"] for c_ in CHAIN_PAGES)],
                            "other_chains": [p for p in ps if set(p["chains"]) - set(CHAIN_PAGES)]} for c in CHAIN_PAGES},
    }


def basket_label(H, k):
    return next(lbl for key, lbl, _, _ in H.BASKETS if key == k)


def others(F, slug, chain):
    """Up to five protocols on the same chain in the same basket (its first basket in the site's basket order), by name, the ones
    after it in name order (wrapping); a protocol with no basket gets five others on its chain."""
    p = F[slug]
    b = p["baskets"][0] if p["baskets"] else None
    group = sorted((q for q in F.values() if chain in q["chains"] and (b is None or (q["baskets"] and q["baskets"][0] == b))),
                   key=lambda q: q["name"].lower())
    i = next(n for n, q in enumerate(group) if q["slug"] == slug)
    rest = group[i + 1:] + group[:i]
    return b, rest[:5]


# ---- HTML ---------------------------------------------------------------------------------------------------------------------

def _n(v, key):
    """A number in the first lines, marked so the verifier can compare it with the rows."""
    return f'<span data-n="{key}">{v:,}</span>'


def _date(day):
    return f'<time datetime="{day}" data-change-date>{day}</time>'


def _reading(day):
    return f'<time datetime="{day}" data-reading-date>{day}</time>'


def _blk(H, chain, block):
    return f'{H.E(H.CHAINS[chain][0])} <span class="num">#{block:,}</span>'


def _rec(H, p, prefix, rid=None, text=None):
    href = f'{prefix}protocols/{p["slug"]}/' + (f"#{rid}" if rid else "")
    return f'<a href="{H.E(href)}">{H.E(text or p["name"])}</a>'


def page(H, idx, rel, desc, head_html, sections, crumbs=None, wide=False):
    """The chrome of these pages: the site's top bar and footer, one h1 (= the title tag), the first lines straight under it.
    wide: the site's wide container (memo-wide, as on /bounties/) for the long tables; the prose keeps its reading width."""
    depth = rel.count("/")
    pre = "../" * depth
    url = f"{H.BASE_URL}/{rel}"
    title = TITLES[rel]
    items = [("Pacta", f"{H.BASE_URL}/")] + (crumbs or []) + [(title, url)]
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList",
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}
    ld_json = json.dumps(ld, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    secs_html = "".join(f'<section class="memo-sec" id="{sid}"><h2>{H.E(h)}</h2>{body}</section>\n' for sid, h, body in sections)
    body = f"""<body>
{H.topbar(pre, None)}
<main id="main" class="memo-wrap{' memo-wide' if wide else ''}">
<article class="memo" data-page="{H.E(rel)}">
<header><h1>{H.E(title)}</h1>
{head_html}</header>
{secs_html}</article>
</main>
{H.footer(H.coverage_line(idx), idx["onchain_anchoring"]["commitment_registry"], pre)}
<script type="application/ld+json">{ld_json}</script>
</body></html>
"""
    return H.head(title, desc, url, prefix=pre, og_title=title) + "\n" + body


_SOFT_TOK = re.compile(r"[^\s<>]{17,}")
_SOFT_UNIT = re.compile(r"&#?\w+;|.", re.S)


def _soft_tok(t):
    """<wbr> inside one long token: after / . _ , = ? & : ; (not inside "://"), before (, at a lower-to-upper case change, and
    after every 10 characters of a run of letters and digits that holds a digit (an address or a hash, never a word); an entity
    (&amp;) is one unit and is never split."""
    units, out, run, dig = _SOFT_UNIT.findall(t), [], 0, False
    for i, u in enumerate(units):
        c = html.unescape(u)
        if i:
            pc = html.unescape(units[i - 1])
            brk = ((pc in "/._,=?&:;" and c != "/") or c == "(" or (pc.islower() and c.isupper())
                   or (run >= 10 and dig and c.isalnum()))
            if brk and i < len(units) - 1:
                out.append("<wbr>")
                run = 0
        if c.isalnum():
            run, dig = run + 1, (dig or c.isdigit()) if run else c.isdigit()
        else:
            run, dig = 0, False
        out.append(u)
    return "".join(out)


def _soft(v):
    """A table cell's HTML with soft wrap opportunities (<wbr>) inside its long tokens (contract calls, addresses, links), never
    inside a tag. The list tables are overflow-wrap: normal on wide screens (w2-table), so a word never breaks in the middle and a
    column is never narrower than its longest word; these breaks keep a 42-character address from widening its column instead.
    Below 640 px the stacked rows keep the site's overflow-wrap: anywhere. The text is unchanged (<wbr> is not a character)."""
    return "".join(p if p.startswith("<") else _SOFT_TOK.sub(lambda m: _soft_tok(m.group(0)), p) for p in re.split(r"(<[^>]+>)", v))


def _table(H, cols, rows, caption):
    th = "".join(f'<th scope="col">{H.E(c)}</th>' for c in cols)
    trs = "".join("<tr>" + "".join(f'<td data-label="{H.E(c)}">{_soft(v)}</td>' for c, v in zip(cols, r)) + "</tr>\n" for r in rows)
    return (f'<div class="tbl-wrap"><table class="stack w2-table" data-list-table><caption class="sr-only">{H.E(caption)}</caption>'
            f'<thead><tr>{th}</tr></thead>\n<tbody data-rows>\n{trs}</tbody></table></div>')


CORRECTION_TRACK = "community"                 # /request/?tier=community: the free document-update queue (label FREE_NOTIFY_CTA)
CALL_EXAMPLE = {"base": "moonwell-lending-base"}   # the call on /chains/base/: this record's own address (lookup.json preflightArgs)
_CACHE = {}


def _json(H, *rel):
    k = "/".join(rel)
    if k not in _CACHE:
        with open(os.path.join(H.ROOT, *rel), encoding="utf-8") as fh:
            _CACHE[k] = json.load(fh)
    return _CACHE[k]


def lookup_item(H, slug):
    return next(it for it in _json(H, "docs", "api", "v1", "lookup.json")["items"] if it.get("slug") == slug and it.get("kind") == "protocol")


def api_paths(H):
    return _json(H, "docs", "api", "v1", "openapi.json")["paths"]


def call_target(H, chain):
    """(slug, chain, address) of the one-contract example call: on Ethereum the site's example (ETHx), on Base a Base record's own
    address. The address must be one of the record's contracts in lookup.json."""
    if chain in CALL_EXAMPLE:
        it = lookup_item(H, CALL_EXAMPLE[chain])
        slug, addr = it["slug"], it["preflightArgs"]["address"]
        assert it["preflightArgs"]["chain"] == chain, it["slug"]
    else:
        slug, ch, addr = H.HERO_EXAMPLE
        assert ch == chain == "ethereum"
        it = lookup_item(H, slug)
    assert addr.lower() in {a.lower() for a in [it.get("primaryContract")] + list(it.get("relatedContracts") or []) if a}, (slug, addr)
    return slug, chain, addr, it["name"]


def _call(H, chain=None):
    B = H.B2A
    slug, ch, addr, name = call_target(H, chain or "ethereum")
    assert "/v1/check" in api_paths(H)
    url = f"{B.X402_URL}/v1/check?chain={ch}&address={addr}"
    return (f'<p>The call, for {H.E(name)} on {H.E(H.CHAINS[ch][0])}: <code>GET {H.E(url)}</code>, or the MCP tool '
            f'<code>{H.E(B.WHO_CONTROLS_TOOL)}</code> with the chain and the address. {B.WHO_CONTROLS_DAILY_QUOTA} calls a day are free, no key.</p>')


def read_next(H, pre, keys):
    lbl = {"control/timelock/": TITLES["control/timelock/"], "control/multisig/": TITLES["control/multisig/"],
           "docs-vs-chain/": TITLES["docs-vs-chain/"], "chains/ethereum/": "Protocols on Ethereum", "chains/base/": "Protocols on Base",
           **{f"learn/{k}/": t for k, t in LEARN.items()}, "listed/": TITLES["listed/"]}
    return "<ul>" + "".join(f'<li><a href="{pre}{k}">{H.E(lbl[k])}</a></li>' for k in keys) + "</ul>"


def tl_more(p):
    """"; <delay> on the upgrade path" where the upgrade path waits longer than the protocol's shortest delay, else "" """
    tl, u = p["timelock"], p["upgrade"]["seconds"]
    return f"; {say_dur(u)} on the upgrade path" if tl["kind"] != "nd" and u is not None and u > tl["seconds"] else ""


def tl_cell(p):
    """the Timelock delay cell: the protocol's shortest delay, then the upgrade path's delay where that path waits longer"""
    tl = p["timelock"]
    return (say_dur(tl["seconds"]) if tl["kind"] == "listed" else "none on a sampled control" if tl["kind"] == "zero"
            else "not determined") + tl_more(p)


def cells_disagree(up_txt, tl_txt):
    """Why a row's Upgradeability cell and Timelock delay cell disagree, or None. Read from the two cells' text alone: the upgrade
    path's delay (upgrade_delay()), and the timelock cell's shortest delay with its "; <delay> on the upgrade path"."""
    m = re.fullmatch(r"(?:(none on a sampled control)|(not determined)|(.+?))(?:; (.+) on the upgrade path)?", tl_txt)
    lo = 0 if m.group(1) else None if m.group(2) else said_seconds(m.group(3))
    more = said_seconds(m.group(4)) if m.group(4) else None
    u = upgrade_delay(up_txt)
    if more is not None and (lo is None or more != u or more <= lo):
        return "the timelock cell's upgrade-path delay is not the upgrade cell's, or not longer than the shortest delay"
    if u is not None and lo is None:
        return "the upgrade cell gives the upgrade path's delay, the timelock cell says not determined"
    if u is not None and u < lo:
        return "the upgrade path waits less than the timelock cell's shortest delay"
    if u is not None and u > lo and more != u:
        return "the upgrade path waits longer than the shortest delay, and the timelock cell does not say so"
    if "unverified" not in up_txt:            # a delay the upgrade sentence names in passing ("governance() is a 24h Timelock")
        for x in _DUR_ANY.finditer(up_txt):
            if lo is None or dur_seconds(x.group(1)) < lo:
                return f"the upgrade cell names {x.group(1)}, " + ("the timelock cell says not determined" if lo is None else "below the shortest delay")
    return None


def timelock_page(H, idx, L, times):
    d = L["control/timelock/"]
    rows, pre = d["rows"], "../../"
    n, z, k, m = len(rows), len(d["zero"]), len(d["nd"]), d["total"]
    day = newest_day([(p["timelock"]["chain"], p["timelock"]["block"]) for p in rows], times)
    lo, hi = rows[0]["timelock"]["seconds"], rows[-1]["timelock"]["seconds"]
    desc = (f"{n} DeFi protocols put a delay between a decision to change a contract and its effect. The list, shortest delay first, "
            "each read from the chain at a named block.")
    head_html = (f'<p class="lede" data-first-lines>{_n(n, "rows")} of the {_n(m, "total")} protocols we have checked put a delay (a timelock) '
                 'between a decision to change a contract and the change taking effect. Each protocol\'s delay is the shortest one read on '
                 f'its sampled timelocked controls; the list runs shortest delay first. The shortest delay is {H.E(say_dur(lo))}; the longest '
                 f'is {H.E(say_dur(hi))}. {_n(k, "nd")} protocols are left out because the delay could not be determined, and '
                 f'{_n(z, "zero")} because at least one of their sampled controls has a delay of zero seconds, that is no delay at all; a delay of '
                 f'zero is not a timelock. Read from the chain; newest reading {_date(day)}.</p>')
    trs = [[_rec(H, p, pre), H.E(", ".join(H.CHAINS[c][0] for c in p["chains"])),
            f'{H.E(say_dur(p["timelock"]["seconds"]))} <span class="num">({p["timelock"]["seconds"]:,} s)</span>{H.E(tl_more(p))}',
            _blk(H, p["timelock"]["chain"], p["timelock"]["block"]),
            _rec(H, p, pre, p["timelock"]["rid"], p["timelock"]["surface"]) if p["timelock"]["rid"] else "getMinDelay() of the timelock contract"]
           for p in rows]
    secs = [("list", f"{n} protocols, shortest delay first",
             _table(H, ["Protocol", "Chain", "Delay", "Read at block", "Record"], trs, "Protocols behind a timelock, shortest delay first")),
            ("meaning", "What the delay means",
             "<p>A timelock holds a decided change for a fixed time before it can run. During that time anyone can see what is coming. "
             "A longer delay gives users more time to react; it says nothing about whether a change is good.</p>" + _call(H)
             + f'<p>Changes queued right now: <a href="{pre}radar/">the radar of queued timelock operations</a>.</p>'),
            ("next", "Read next", read_next(H, pre, ["control/multisig/", "docs-vs-chain/", "chains/ethereum/", "chains/base/",
                                                     "learn/who-can-upgrade/", "learn/check-before-deposit/"]))]
    return page(H, idx, "control/timelock/", desc, head_html, secs, wide=True), {"rows": n, "stated": n, "left_out": {"not determined": k, "no delay on a sampled control": z}, "total": m, "date": day}


def multisig_page(H, idx, L, times):
    d = L["control/multisig/"]
    rows, pre = d["rows"], "../../"
    n, g, k, m = len(rows), len(d["governor"]), len(d["nd"]), d["total"]
    day = newest_day([(p["quorum"]["chain"], p["quorum"]["block"]) for p in rows], times)
    lo, hi = rows[0]["quorum"], max((p["quorum"] for p in rows), key=lambda q: (q["k"], q["n"]))
    desc = (f"{n} DeFi protocols by the fewest signers needed on any sampled control: the lowest multisig threshold found, a single key "
            "counting as 1 of 1, each read from the chain at a named block.")
    gov = (f', and {_n(g, "governor")} because {"it is" if g == 1 else "they are"} controlled by a token vote, not by signers' if g else "")
    head_html = (f'<p class="lede" data-first-lines>{_n(n, "rows")} of the {_n(m, "total")} protocols we have checked have a signer threshold on '
                 'at least one sampled control. The number is the lowest threshold of any multisig found on any sampled control (settings, '
                 'roles, pause, upgrades); a single key counts as 1 of 1. It does not say which control it is or that it can upgrade. '
                 f'The fewest signers needed is {lo["k"]} of {lo["n"]}; the most is {hi["k"]} of {hi["n"]}. The list runs fewest signers first. '
                 f'{_n(k, "nd")} protocols are left out because no signer threshold could be determined{gov}. Newest reading {_date(day)}.</p>')
    trs = []
    for p in rows:
        q = p["quorum"]
        cell = f'{q["k"]} of {q["n"]}' + ("" if q["canonical"] else f'<br><span class="s">{H.E(q["text"])}</span>')
        trs.append([_rec(H, p, pre), H.E(", ".join(H.CHAINS[c][0] for c in p["chains"])), cell,
                    _rec(H, p, pre, q["rid"], q["surface"]) if q["rid"] else "getThreshold() of the Safe; the record does not name the control",
                    _blk(H, q["chain"], q["block"])])
    secs = [("list", f"{n} protocols, fewest signers first",
             _table(H, ["Protocol", "Chain", "Fewest signers needed", "Read in the record", "Block"], trs,
                    "Protocols by the fewest signers needed on any control, fewest first")),
            ("meaning", "What the number means",
             '<p>A multisig spreads one key over several holders. "3 of 5" means any three of five holders can act together. The count says '
             'how many must agree; it does not say who they are or how they decide. A single key is one holder acting alone.</p>' + _call(H)),
            ("next", "Read next", read_next(H, pre, ["control/timelock/", "docs-vs-chain/", "chains/ethereum/", "chains/base/",
                                                     "learn/who-can-upgrade/"]))]
    return page(H, idx, "control/multisig/", desc, head_html, secs, wide=True), {"rows": n, "stated": n, "left_out": {"not determined": k, "token vote": g}, "total": m, "date": day}


def docs_page(H, idx, L, times):
    d = L["docs-vs-chain/"]
    rows, pre = d["rows"], "../"
    n, mc, u, k, ag, m = len(rows), len(d["compared"]), len(d["uncompared"]), len(d["nd"]), len(d["agree"]), d["total"]
    day = newest_day([(p["docs"]["chain"], p["docs"]["block"]) for p in rows], times)
    desc = (f"{n} DeFi protocols where the published documents say one thing about who controls the contracts and the chain shows another. "
            "Each difference with its block.")
    head_html = (f'<p class="lede" data-first-lines>For {_n(n, "rows")} of the {_n(mc, "compared")} protocols whose documents we compared with the '
                 'chain, the documents and the chain disagree on how the contracts are controlled. Each row names what the documents say, '
                 'what the chain shows, and the block it was read at. A difference can be an outdated document; the row states both sides '
                 f'and takes neither. Of the {_n(m, "total")} protocols we have checked, the documents of {_n(mc, "compared")} were compared with the chain '
                 f'and those of {_n(u, "uncompared")} were not; of the {_n(mc, "compared")} compared, {_n(n, "rows")} differ and are listed here, '
                 f'{_n(ag, "agree")} agree, and for {_n(k, "nd")} a difference is not determined, so they are left out. '
                 f'The list runs by protocol name, A to Z; newest reading {_date(day)}. A protocol leaves the list when a newer reading '
                 'of its record shows the two agree.</p>')
    trs = []
    for p in rows:
        dd = p["docs"]
        more = f'<br><span class="s">{dd["more"]} more on the record</span>' if dd["more"] else ""
        rec = f'{pre}protocols/{p["slug"]}/#{dd["rid"]}'
        notes = ([] if dd["quoted"] else ["The record's own summary of the documents; it quotes no words."]) \
            + ([f'The rest is on <a href="{rec}">the record</a>.'] if dd["documented_cut"] else []) \
            + ([] if dd["sourced"] else [f'The record gives no web address for these words: <a href="{rec}">read the record</a>.'])
        said = H.E(dd["documented"]) + (" …" if dd["documented_cut"] else "") + "".join(f'<br><span class="s">{x}</span>' for x in notes)
        trs.append([_rec(H, p, pre), H.E(H.CHAINS[dd["chain"]][0]),
                    said, H.E(dd["observed"]) + more, _blk(H, dd["chain"], dd["block"]),
                    _rec(H, p, pre, dd["rid"], dd["surface"])])
    assert CORRECTION_TRACK in H.TRACKS
    qn = sum(p["docs"]["quoted"] for p in rows)
    quo_t = ("Every row above quotes the documents' own words." if qn == n else
             f"{qn} of the {n} rows above quote the documents' own words; the other {n - qn} give the record's summary of them, marked in the row.")
    att = sum(p["docs"]["attested"] for p in rows)
    att_t = (("Each compared finding is attested on Base." if att == n else f"{att} of the {n} findings on this list are attested on Base.")
             + " The attestation carries the block it was read at and a fingerprint (SHA-256) of the summary that holds the quoted text; "
             "the text itself is in the public summary, not onchain.")
    secs = [("list", f"{n} protocols, A to Z",
             _table(H, ["Protocol", "Chain", "The documents say", "The chain shows", "Block", "Record"], trs,
                    "Protocols whose documents differ from the chain, by name")),
            ("how", "How a difference is found",
             "<p>Each record reads one control setting from the chain at a pinned block and records what the protocol's documents say about it. "
             f"{quo_t} Where the two differ, the record marks the difference. {att_t} "
             f'The <a href="{pre}methodology/">method page</a> gives the rules.</p>'
             f'<p>How a protocol team can have a row corrected: <a href="{pre}request/?tier={CORRECTION_TRACK}">{H.E(H.FREE_NOTIFY_CTA)}</a>, '
             'the free queue for updated documents.</p>' + _call(H)),
            ("next", "Read next", read_next(H, pre, ["control/timelock/", "control/multisig/", "chains/ethereum/", "chains/base/",
                                                     "learn/who-can-upgrade/"]))]
    return page(H, idx, "docs-vs-chain/", desc, head_html, secs, wide=True), {"rows": n, "stated": n, "left_out": {"documents not compared": u, "not determined": k, "agree": ag}, "compared": mc, "total": m, "date": day}


def chain_page(H, idx, L, times, chain):
    rel = f"chains/{chain}/"
    rows, pre, cname = L[rel]["rows"], "../../", H.CHAINS[chain][0]
    n = len(rows)
    a = sum(p["timelock"]["kind"] == "listed" for p in rows)
    b = sum(p["quorum"]["kind"] == "listed" for p in rows)
    dn = sum(p["docs"]["kind"] == "listed" for p in rows)
    day = newest_day([(chain, p["newest"][chain]) for p in rows], times)
    cv = L[rel]
    both, one, nei, m = len(cv["both"]), len(cv["one"]), len(cv["neither"]), cv["total"]
    names = " and ".join(H.CHAINS[c][0] for c in CHAIN_PAGES)
    lead = ("A protocol on more than one chain is listed on the page of each" if not cv["other_chains"]
            else f"A protocol on both {names} is listed on both pages")
    cover = (f'{lead}: {_n(both, "both")} of the {_n(m, "total")} protocols we have checked are on both {names}, '
             + (f'{_n(one, "one")} on only one of the two, and {_n(nei, "neither")} on neither, so on no chain page. ' if nei
                else f'and {_n(one, "one")} on only one of the two. '))
    desc = (f"{n} DeFi protocols on {cname}: how each can be upgraded, the timelock delay and the fewest signers needed, read from the chain.")
    head_html = (f'<p class="lede" data-first-lines>We have checked {_n(n, "rows")} protocols on {cname}. {_n(a, "timelock")} are behind a timelock, '
                 f'{_n(b, "multisig")} have a signer threshold on a sampled control, and for {_n(dn, "docs")} the documents differ from the chain. '
                 f'{cover}The list runs by protocol name, A to Z. Newest reading {_date(day)}.</p>')
    trs = []
    for p in rows:
        tl, q = p["timelock"], p["quorum"]
        tl_t = H.E(tl_cell(p))
        q_t = (f'{q["k"]} of {q["n"]}' if q["kind"] == "listed" else "token vote" if q["kind"] == "governor" else "not determined")
        dv = {"listed": "differ", "agree": "agree", "uncompared": "not compared", "nd": "not determined"}[p["docs"]["kind"]]
        trs.append([_rec(H, p, pre), H.E(p["upgrade"]["text"]), tl_t, q_t, dv, _blk(H, chain, p["newest"][chain])])
    other = [c for c in CHAIN_PAGES if c != chain]
    secs = [("list", f"{n} protocols on {cname}, A to Z",
             _table(H, ["Protocol", "Upgradeability", "Timelock delay", "Fewest signers needed", "Documents and chain", "Newest block"], trs,
                    f"Protocols on {cname}, by name")
             + '<p data-how-timelock>How the Timelock delay column picks: a protocol can have more than one timelock. The column gives the '
               'shortest delay read on any of its sampled controls, the upgrade path included, so one control with no delay makes it '
               '“none on a sampled control”. Where the upgrade path waits longer, the cell also gives the upgrade path\'s delay. The '
               'Upgradeability column is the upgrade path alone. “Not determined”: the published records do not settle the shortest '
               'delay.</p>'),
            ("next", "The lists", read_next(H, pre, ["control/timelock/", "control/multisig/", "docs-vs-chain/"] + [f"chains/{c}/" for c in other]
                                            + ["learn/who-can-upgrade/"]) + _call(H, chain))]
    return page(H, idx, rel, desc, head_html, secs, wide=True), {"rows": n, "stated": n, "timelock": a, "multisig": b, "docs": dn, "both": both, "one": one, "neither": nei, "total": m, "date": day}


def _example(H, F, times):
    """The use pages' real example: the hero record's protocol, two sentences generated from its facts, each with its block and date."""
    slug, chain, addr = H.HERO_EXAMPLE
    p = F[slug]
    tl, q = p["timelock"], p["quorum"]
    assert tl["kind"] == "listed" and q["kind"] == "listed", slug
    s1 = (f'{p["name"]}: on its sampled timelocked controls, a decided change waits at least {say_dur(tl["seconds"])} before it runs (read at {H.CHAINS[tl["chain"]][0]} '
          f'block #{tl["block"]:,} on {day_of(times[(tl["chain"], tl["block"])])}).')
    s2 = (f'The fewest signers needed on any sampled control is {q["k"]} of {q["n"]} (read at block #{q["block"]:,} on '
          f'{day_of(times[(q["chain"], q["block"])])}).')
    day = max(day_of(times[(tl["chain"], tl["block"])]), day_of(times[(q["chain"], q["block"])]))
    return p, chain, addr, s1 + " " + s2, day


def _ex(H, text):
    """a generated example answer: read from a record at build time (left out of the page-text fingerprint, see changed())"""
    return f'<span data-example>{H.E(text)}</span>'


# ---- prices, free limits, routes and tools: the site's own lists (tools/build_b2a_feeds.py, the Worker's price list as the site
# states it everywhere), each route checked against docs/api/v1/openapi.json; a tool missing from either side fails the build.

# what each remote MCP tool answers, one line each (checked against the tool code, 28 Nov 2026); the keys must be B2A.REMOTE_TOOLS
TOOL_WHAT = {
    "pacta_lookup_protocol": "Find a protocol, token or contract in Pacta's catalog by name, symbol, slug or 0x address",
    "who_controls": "Live proxy, admin, Safe signers and threshold, timelock delay, pause and mint facts on any Ethereum or Base contract",
    "pacta_check_preflight": "Pre-execution control-plane check and docs-vs-chain comparison for one contract",
    "pacta_scan_wallet_exposure": "DeFi protocol control-plane exposure across the positions held by a wallet or Safe",
    "pacta_scan_control_plane": "Raw proxy slots, Safe owners and threshold, and timelock reads for a contract",
    "pacta_scan_timelock_op": "Decode a timelock operation ID or calldata, and when it can run",
    "pacta_scan_proposal_diff": "Re-run the pinned contract reads of a tracked DAO governance proposal",
    "pacta_get_live_timelocks": "Queued timelock operations waiting now across the indexed protocols",
    "pacta_verdict": "Live control-plane scan plus summary fields at the latest block",
    "pacta_dossier": "Full control-plane dossier of a protocol across its controller Safes and timelocks",
    "trace_dependencies": "Collateral assets, minters, price sources and bridge verifiers a vault, market or token depends on",
    "remember": "Save a position, an entry block or a note under your wallet (up to 200 items)",
    "what_changed_since": "Control, minter, price-source, bridge or queued timelock changes since a block or your last check",
    "forget": "Erase one saved item, or everything saved under your wallet",
    "pacta_submit_request": "Queue a protocol coverage or document-update request",
    "request_feature": "Tell Pacta what tool or data your agent needs (read daily)",
}
# the tool's own words where the site's API description is not usable as a quote (its preflight text rates contracts)
PREFLIGHT_WORDS = ("Block-pinned proxy, Safe signer/threshold, timelock delay, and docs-vs-chain comparison for the contract before an agent "
                   "approves, deposits into or calls it.")


def prices(H):
    """{tool: (method and route, free a day, price after)} from the B2A constants; every route is a path of openapi.json"""
    B = H.B2A
    assert B.PRICING_MODE == "free_read" and B.WHO_CONTROLS_TOOL == "who_controls"
    x = {r: usd for r, usd, _ in B.X402_ENDPOINTS + B.X402_MEMORY_ENDPOINTS}
    met = {r.split("?")[0]: usd for r, _, usd in B.X402_ROUTES if r.split("?")[0] in B.METERED_PATHS}
    assert f"{B.WALLET_MEMORY_PER_MIN} calls / minute and {B.WALLET_MEMORY_DAILY_QUOTA} calls / day per wallet" in B.FREE_TIER_DOC
    assert f"({B.X402_MEMORY_PER_MIN} calls / minute)" in B.FREE_TIER_DOC and "who_controls has no paid overflow" in B.FREE_TIER_DOC
    rl = f"no daily limit ({B.RATE_LIMIT_PER_MIN} a minute)"
    # the two request routes: each limit as the service's API description gives it
    req, fr = api_paths(H)["/v1/requests"]["post"], api_paths(H)["/v1/feature-request"]["post"]
    per_h = re.search(r"\b(\d+) per hour per caller\b", req["summary"])
    assert per_h and f"More than {per_h.group(1)} requests per hour" in req["responses"]["429"]["description"] \
        and "(Retry-After)" in req["responses"]["429"]["description"], "openapi.json: the /v1/requests limit"
    per_d = re.search(r"\b(\d+) per caller per UTC day\b", fr["summary"])
    assert per_d and int(per_d.group(1)) == B.FEATURE_REQUEST_DAILY_LIMIT, "openapi.json and the site's feature-request limit differ"
    assert fr["responses"]["200"]["headers"]["X-Meter-Reset"]["description"].startswith("Unix seconds of the next UTC midnight"), \
        "openapi.json: the feature-request reset is no longer 00:00 UTC"
    mem_free = f"{B.WALLET_MEMORY_DAILY_QUOTA} a day per wallet ({B.WALLET_MEMORY_PER_MIN} a minute)"
    R = {"pacta_lookup_protocol": ("GET /v1/protocols/lookup", rl, "$0.00"),
         "who_controls": ("GET /v1/check", f"{B.WHO_CONTROLS_DAILY_QUOTA} a day", "none: free only, the count resets at 00:00 UTC"),
         "pacta_check_preflight": ("GET /v1/check/preflight", f"{B.FREE_DAILY_QUOTA} a day", f"{met['/v1/check/preflight']} a call"),
         "pacta_scan_wallet_exposure": ("GET /v1/check/wallet-exposure", f"{B.FREE_X402_DAILY_QUOTA} a day",
                                        f"{met['/v1/check/wallet-exposure']} a call (POST /v1/x402/wallet-exposure: ${x['/v1/x402/wallet-exposure']})"),
         "pacta_scan_control_plane": ("GET /v1/scan/control-plane", rl, "$0.00"),
         "pacta_scan_timelock_op": ("GET /v1/scan/timelock-op", rl, "$0.00"),
         "pacta_scan_proposal_diff": ("GET /v1/scan/proposal-diff", rl, "$0.00"),
         "pacta_get_live_timelocks": ("GET /v1/briefs/live-timelocks", rl, "$0.00"),
         "pacta_verdict": ("POST /v1/x402/verdict", f"{B.FREE_X402_DAILY_QUOTA} a day", f"${x['/v1/x402/verdict']} a call"),
         "pacta_dossier": ("POST /v1/x402/dossier", f"{B.FREE_X402_DAILY_QUOTA} a day", f"${x['/v1/x402/dossier']} a call"),
         "trace_dependencies": ("GET /v1/trace-dependencies", rl, "$0.00"),
         "remember": ("POST /v1/memory/remember", mem_free,
                      f"${x['/v1/x402/remember']} a call on POST /v1/x402/remember ({B.X402_MEMORY_PER_MIN} a minute, no daily cap)"),
         "what_changed_since": ("POST /v1/memory/what-changed-since", mem_free,
                                f"${x['/v1/x402/what-changed-since']} a call on POST /v1/x402/what-changed-since ({B.X402_MEMORY_PER_MIN} a minute, no daily cap)"),
         "forget": ("POST /v1/memory/forget", "free", "$0.00, always free"),
         "pacta_submit_request": ("POST /v1/requests", f"no daily limit ({int(per_h.group(1))} an hour)",
                                  "none: free only, a refused call gives the wait in seconds (Retry-After)"),
         "request_feature": ("POST /v1/feature-request", f"{int(per_d.group(1))} a day", "none: free only, the count resets at 00:00 UTC")}
    assert list(R) == list(B.REMOTE_TOOLS) and list(TOOL_WHAT) == list(B.REMOTE_TOOLS), "the tool list and the price list differ"
    paths = api_paths(H)
    for t, (route, _, after) in R.items():
        assert route.split(" ", 1)[1] in paths, (t, route)
        for r in re.findall(r"(?:POST|GET) (/v1/[\w/-]+)", after):
            assert r in paths, (t, r)
    return R


def http_only(H):
    """the paid HTTP routes no MCP tool answers (calldata-sim, deep-scan): (route, price)"""
    B = H.B2A
    used = {r for v in prices(H).values() for r in re.findall(r"/v1/x402/[\w-]+", v[0] + " " + v[2])}
    out = [(r, usd) for r, usd, _ in B.X402_ENDPOINTS if r not in used]
    assert all(r in api_paths(H) for r, _ in out)
    return out


def _ptable(H, cols, rows, caption, attr, soft=False):
    """soft: as the list tables (_table): never a break inside a word on wide screens, soft breaks inside long tokens"""
    th = "".join(f'<th scope="col">{H.E(c)}</th>' for c in cols)
    trs = "".join("<tr>" + "".join(f'<td data-label="{H.E(c)}">{_soft(v) if soft else v}</td>' for c, v in zip(cols, r)) + "</tr>\n"
                  for r in rows)
    return (f'<div class="tbl-wrap"><table class="stack{" w2-table" if soft else ""}" {attr}><caption class="sr-only">{H.E(caption)}</caption>'
            f'<thead><tr>{th}</tr></thead>\n<tbody>\n{trs}</tbody></table></div>')


def price_table(H, tools):
    R = prices(H)
    return _ptable(H, ["Call (MCP tool, HTTP route)", "Free a day, per caller", "Price after the free calls (USDC on Base, x402)"],
                   [[f'<code>{H.E(t)}</code> (<code>{H.E(R[t][0])}</code>)', H.E(R[t][1]), H.E(R[t][2])] for t in tools],
                   "What each check costs", "data-price-table")


def tool_table(H):
    R = prices(H)
    return _ptable(H, ["Tool", "What it answers", "Free a day", "Price after (HTTP x402 on Base)"],
                   [[f'<code>{H.E(t)}</code>', H.E(TOOL_WHAT[t]), H.E(R[t][1]), H.E(R[t][2])] for t in H.B2A.REMOTE_TOOLS],
                   "The tools of Pacta's MCP server", "data-tool-table")


def api_words(H, path, method="get", sentences=2):
    """the first sentences of a route's description in docs/api/v1/openapi.json, word for word"""
    d = api_paths(H)[path][method]["description"]
    w = " ".join(re.split(r"(?<=\.) ", d)[:sentences])
    assert w.endswith(".") and not banned(w), (path, w)
    return w


def _resp_fields(H, path):
    """every property path of a route's 200 answer in openapi.json (a.b for nested objects)"""
    oa = _json(H, "docs", "api", "v1", "openapi.json")

    def walk(o, pre):
        if not isinstance(o, dict):
            return
        if "$ref" in o:
            yield from walk(oa["components"]["schemas"][o["$ref"].split("/")[-1]], pre)
        for k, v in (o.get("properties") or {}).items():
            yield pre + k
            yield from walk(v, pre + k + ".")
        for k in ("items", "schema", "application/json", "content"):
            if isinstance(o.get(k), dict):
                yield from walk(o[k], pre)
        for k in ("allOf", "oneOf", "anyOf"):
            for v in o.get(k) or []:
                yield from walk(v, pre)
    return set(walk(api_paths(H)[path]["get"]["responses"]["200"], ""))


# "What comes back": the who_controls answer's fields by their names in the API description (each one checked at build time)
WHO_FIELDS = [(("chain", "address"), "the network (ethereum or base) and the contract address checked."),
              (("block.number", "block.hash", "block.providers"), "the block every read was pinned to, its hash, and the two RPC providers that read it."),
              (("upgradeable", "standardProxyDetected"), "whether a standard proxy slot or upgrade beacon is set: true, false, or null when custom upgrade code cannot be ruled out."),
              (("controllerType", "controllers"), "each controller found, with its kind, a Safe's threshold and owner count, and a timelock's delay."),
              (("upgradeDelaySeconds",), "the minimum delay in seconds when the upgrade admin is a timelock; null otherwise."),
              (("facts.upgrades", "facts.ownerAndRoles", "facts.pausing", "facts.supply"), "one plain line each on upgrades, owner and roles, pausing, and supply."),
              (("isPaused", "pauseIndicatorsObserved", "mintIndicatorsObserved", "canSupplyGrow"), "whether the contract is paused, and the pause and mint signals found."),
              (("pending_operations",), "timelock operations queued for the contract, and when they can run."),
              (("castCommands",), "Foundry cast commands that reproduce every read yourself.")]


def who_fields(H):
    have = _resp_fields(H, "/v1/check")
    miss = [f for names, _ in WHO_FIELDS for f in names if f not in have]
    assert not miss, ("fields not in the /v1/check answer of openapi.json", miss)
    return "<ul>" + "".join("<li>" + ", ".join(f"<code>{H.E(f)}</code>" for f in names) + f": {H.E(t)}</li>" for names, t in WHO_FIELDS) + "</ul>"


def mcp_lines(H):
    claude = next(c for lbl, _, c in H.B2A.MCP_RECIPES if lbl == "Claude Code")
    assert H.MCP_URL in claude
    return claude, json.dumps({"mcpServers": {"pacta": {"url": H.MCP_URL}}}, indent=2)


def learn_who(H, idx, F, times):
    rel, pre = "learn/who-can-upgrade/", "../../"
    B = H.B2A
    p, chain, addr, ex, day = _example(H, F, times)
    desc = DESC[rel]
    head_html = ('<p class="lede" data-first-lines>A contract that can be upgraded can be changed by whoever holds the upgrade key. To know who '
                 'that is you need three facts: is the contract behind a proxy, who is the proxy\'s admin, and is there a delay between a '
                 'decision and its effect (a timelock). For any contract on Ethereum or Base, Pacta reads these facts from the chain at a '
                 'finalized block and returns what the contract exposes in one answer. Where a contract uses its own upgrade code that '
                 'cannot be read this way, the answer says "not determined" instead of guessing.</p>'
                 f'<p class="s">Changed {CHANGED}. The example on this page was read from the chain; its newest reading is from {_reading(day)}.</p>')
    cname = H.CHAINS[chain][0]
    claude, _ = mcp_lines(H)
    secs = [("ask", "Ask it yourself",
             f'<p>One line, no key, {B.WHO_CONTROLS_DAILY_QUOTA} answers a day free:</p>'
             + H.term(f'curl -s "{B.X402_URL}/v1/check?chain={chain}&address={addr}"', "Ask with curl", "Copy the curl line",
                      marker="who-can-upgrade:call")),
            ("agent", "Ask it from an agent",
             "<p>Add the server once:</p>" + H.term(claude, "Add the MCP server", "Copy the MCP line", marker="who-can-upgrade:connect")
             + f'<p>Then ask in words: "Who controls {H.E(addr)} on {cname}?" The agent calls the tool <code>{H.E(B.WHO_CONTROLS_TOOL)}</code>.</p>'),
            ("answer", "What comes back", "<p>The fields of the answer, by their names in the API description:</p>" + who_fields(H)),
            ("example", "One real example",
             f'<p>{_ex(H, ex)} Full record: {_rec(H, p, pre, text="/protocols/" + p["slug"] + "/")}.</p>'),
            ("limits", "What it does not tell you",
             "<p>It tells you who can change the contract and how fast. It does not tell you whether they will, and it is not a rating.</p>"),
            ("questions", "Questions people ask",
             "<h3>What is a proxy admin?</h3><p>A proxy is a contract that passes every call on to a separate implementation contract, so the "
             "code behind one address can be replaced. The proxy admin is the account allowed to replace it.</p>"
             "<h3>What is a timelock?</h3><p>A timelock is a contract that holds a decided change for a fixed delay before it can run. While "
             "the change waits, anyone can see it.</p>"
             "<h3>What if the documents say something else than the chain?</h3><p>The record shows both: the value read from the chain at a "
             f'named block and the words of the documents. Where they differ, the protocol is on <a href="{pre}docs-vs-chain/">'
             f'{H.E(TITLES["docs-vs-chain/"])}</a>.</p>'),
            ("next", "Read next", read_next(H, pre, ["control/timelock/", "control/multisig/", f"chains/{chain}/", "learn/check-before-deposit/"]))]
    return page(H, idx, rel, desc, head_html, secs, crumbs=[]), {"example_read": day, "newest_input": day}


def worked_run(H, idx, F, times):
    """/learn/check-before-deposit/: one protocol, three calls, each answer the records hold (with its block and date), or said to
    be missing. Ethena USDe was asked for; its records decide no upgrade path, and the site's records hold no dependency links
    and no re-reading for it, so the run uses the site's example protocol (Stader Labs ETHx) throughout."""
    B = H.B2A
    slug, chain, addr = H.HERO_EXAMPLE
    p, it = F[slug], lookup_item(H, slug)
    safe = it["preflightArgs"]["address"]
    q, dd = p["quorum"], p["docs"]
    rec = next(e for e in idx["entries"] if e["id"] == q["rid"])
    assert rec["target_contract"].lower() == safe.lower() and safe.lower() != addr.lower(), slug
    assert addr.lower() in {a.lower() for a in it.get("relatedContracts") or []}, slug
    deps = _json(H, "tools", "graph_dependencies.json")["dependencies"]
    has_deps = any(addr.lower()[2:] == r.get("contract_hex") for d in deps for r in d.get("reads") or []) or \
        any(slug in (d.get("downstream_slug"), d.get("upstream_slug")) for d in deps)
    rereads = [r for e in idx["entries"] if e.get("protocol") == rec.get("protocol") for r in e.get("reverified") or []]
    _, _, _, ex, day = _example(H, F, times)
    qday = day_of(times[(q["chain"], q["block"])])
    cname = H.CHAINS[chain][0]
    a1 = ex
    a2 = (f'At {cname} block #{q["block"]:,} on {qday} the record read this Safe\'s signer threshold: {q["k"]} of {q["n"]}.'
          + (f' The documents say: {dd["documented"]}' if dd["kind"] == "listed" and dd["rid"] == q["rid"] else ""))
    days = [day, qday]
    assert not has_deps and not rereads, "the worked run says the records hold no dependency link and no re-reading: rewrite it"
    assert rec["block_number"] == q["block"], "call 3 starts at the block of the signer-threshold reading in the first answer"
    items = [
        (f'<code>{H.E(B.WHO_CONTROLS_TOOL)}</code> on the ETHx token contract <code>{H.E(addr)}</code>, the contract a depositor receives.',
         f'Pacta\'s record holds: {_ex(H, a1)}'),
        ('<code>trace_dependencies</code> on the same contract.',
         'The records on this site hold no dependency link for this contract, so no example answer is shown here.'),
        (f'<code>what_changed_since</code> on the ETHx contract since block {rec["block_number"]:,}, the block of the signer-threshold '
         'reading in the first answer.',
         'The answer depends on what happened on the chain after that block. The records on this site hold no later reading of this '
         'contract, so no example answer is shown here.'),
        (f'The one-call version, <code>pacta_check_preflight</code>, on the Stader Manager Safe <code>{H.E(safe)}</code>, because that '
         'is the contract whose signer threshold Pacta\'s record reads.', f'Pacta\'s record holds: {_ex(H, a2)}')]
    html_ = (f'<p>One protocol, {H.E(p["name"])}, four calls: the three checks and the one-call version. What follows each call is what '
             'Pacta\'s published records hold for it, with its block and date. A live call reads the chain now, so you should get an '
             'answer like this one, not necessarily the same.</p><ol>'
             + "".join(f"<li>{c} {a_}</li>" for c, a_ in items) + "</ol>")
    return html_, max(days), safe


def learn_deposit(H, idx, F, times):
    rel, pre = "learn/check-before-deposit/", "../../"
    B = H.B2A
    R = prices(H)
    p, chain, addr, ex, day = _example(H, F, times)
    run, run_day, safe = worked_run(H, idx, F, times)
    mem = H.B2A.X402_MEMORY_ENDPOINTS[0][1]
    desc = DESC[rel]
    head_html = ('<p class="lede" data-first-lines>Before an agent deposits, it should know three things about the contract it is about to '
                 'trust: who can change it, what it depends on, and whether anything changed since the agent last looked. Each is one call. '
                 f'No API key or account is needed: {B.WHO_CONTROLS_TOOL} is free for {B.WHO_CONTROLS_DAILY_QUOTA} calls a day, '
                 'trace_dependencies is free with no daily limit, preflight is free for '
                 f'{B.FREE_DAILY_QUOTA} calls a day (then {R["pacta_check_preflight"][2].split(" ")[0]} USDC per call on Base over x402), and '
                 'wallet memory (remember and what_changed_since) is free on MCP and /v1/memory/* '
                 f'({B.WALLET_MEMORY_DAILY_QUOTA} calls a day per wallet, or ${mem} USDC per call with no daily cap on /v1/x402/*).</p>'
                 f'<p class="s">Changed {CHANGED}. The worked run on this page was read from the chain; its newest reading is from {_reading(run_day)}.</p>')
    u = B.X402_URL
    secs = [("checks", "The three checks, in order",
             f'<ol><li>Who can change it: the MCP tool <code>{H.E(B.WHO_CONTROLS_TOOL)}</code>, or <code>GET {u}/v1/check?chain=ethereum&amp;address=0x…</code>. '
             'Stop here if the answer surprises you.</li>'
             f'<li>What it depends on: the MCP tool <code>trace_dependencies</code>, or <code>GET {u}/v1/trace-dependencies?chain=ethereum&amp;address=0x…</code>. '
             f'In the API description\'s own words: “{H.E(api_words(H, "/v1/trace-dependencies"))}”</li>'
             f'<li>What changed since last time: the MCP tool <code>what_changed_since</code>, or <code>POST {u}/v1/memory/what-changed-since</code> '
             '(given a list of contracts, a chain and a since_block, it needs no wallet), for an agent that saved its positions with '
             f'<code>remember</code> (the MCP tool, or <code>POST {u}/v1/memory/remember</code>).</li></ol>'
             f'<p data-one-call>Or one call for the whole picture: the MCP tool <code>pacta_check_preflight</code>, or '
             f'<code>GET {u}/v1/check/preflight?chain=ethereum&amp;address=0x…</code>. In the tool\'s own words: “{H.E(PREFLIGHT_WORDS)}”</p>'
             + H.term(f'curl -s "{u}/v1/check?chain={chain}&address={addr}"', "Check 1 with curl", "Copy the first check",
                      marker="check-before-deposit:call")),
            ("run", "A worked run", run),
            ("cost", "What it costs",
             price_table(H, ["who_controls", "trace_dependencies", "pacta_check_preflight", "remember", "what_changed_since", "forget"])
             + f'<p>Where a route charges over x402, payment is per call in USDC on Base to <code>{H.E(B.PAY_TO)}</code>. A call that needs '
             'payment answers HTTP 402 with the price and the payment requirements; the agent signs the Base USDC authorization and repeats '
             'the HTTP call with X-PAYMENT (v1) or PAYMENT-SIGNATURE (v2). No account, no API key.</p>'),
            ("limits", "What it does not do", "<p>It does not decide for the agent. It returns facts and where they were read.</p>"),
            ("next", "Read next", read_next(H, pre, ["learn/who-can-upgrade/", "learn/connect-mcp-agent/", "docs-vs-chain/"]))]
    assert "X-PAYMENT" in B.X402_DOC and "PAYMENT-SIGNATURE" in B.X402_DOC
    return page(H, idx, rel, desc, head_html, secs), {"example_read": run_day, "newest_input": run_day}


def learn_connect(H, idx, F, times):
    rel, pre = "learn/connect-mcp-agent/", "../../"
    B = H.B2A
    p, chain, addr, ex, day = _example(H, F, times)
    claude, cursor = mcp_lines(H)
    assert "Streamable HTTP" in B.MCP_STATUS
    desc = DESC[rel]
    head_html = ('<p class="lede" data-first-lines>Pacta is an MCP server and a web API that tells an agent who can upgrade, pause or change a '
                 'DeFi contract. Adding it takes one line. The tools are free within their limits and need no key; where a paid call '
                 'exists, the agent pays for it itself, per call. The table below says which.</p>'
                 f'<p class="s">Changed {CHANGED}. The example answer on this page was read from the chain; its newest reading is from {_reading(day)}.</p>')
    only = http_only(H)
    secs = [("add", "Add it",
             H.term(claude, "Claude Code", "Copy the Claude Code line", marker="connect-mcp-agent:claude-code")
             + H.term(cursor, "Cursor (mcp.json)", "Copy the Cursor lines", marker="connect-mcp-agent:cursor")
             + f'<p>Any MCP client: the address is <code>{H.E(H.MCP_URL)}</code>, transport Streamable HTTP.</p>'
             f'<p>No MCP: the same over the web API, described at <code>{H.E(H.OPENAPI_URL)}</code>.</p>'),
            ("first", "The first call",
             f'<p>Ask about the {H.E(p["name"])} token: "Who controls {H.E(addr)} on {H.E(H.CHAINS[chain][0])}?" You should get an answer like this one. '
             f'Pacta\'s record holds: {_ex(H, ex)}</p>'),
            ("tools", "The tools", tool_table(H)
             + "<p>Two paid HTTP routes have no MCP tool: " + " and ".join(f'<code>POST {H.E(r)}</code> (${H.E(usd)} a call)' for r, usd in only) + ".</p>"),
            ("pay", "How an agent pays",
             '<p>When a call goes over its free daily allowance, or calls a paid-only HTTP route, the API answers HTTP 402 Payment Required '
             f'with the exact USDC price on Base and the receiving address (<code>{H.E(B.PAY_TO)}</code>). An x402-capable agent signs a '
             'Base USDC transfer authorization locally, without creating an account or storing a card. It repeats the same HTTP request '
             'with the X-PAYMENT (v1) or PAYMENT-SIGNATURE (v2) header and receives the JSON answer.</p>'),
            ("listed", "Where it is listed", f'<p><a href="{pre}listed/">{H.E(TITLES["listed/"])}</a></p>'),
            ("next", "Read next", read_next(H, pre, ["learn/who-can-upgrade/", "learn/check-before-deposit/"]))]
    return page(H, idx, rel, desc, head_html, secs), {"example_read": day, "newest_input": day}


# The listings, each checked over HTTP on 28 Nov 2026 (00:08 UTC; the x402-list.com entry page at 01:32 UTC, "member since
# 2026-11-20"): (name, what it lists, link to our entry, note on the link, the day we were listed). Each link is our own entry,
# never a directory's front page (a sponsor row there is not part of the directory). A directory whose entry answered 404 or
# could not be checked is left out; LISTINGS_LEFT_OUT counts them.
LISTINGS = [
    ("x402-list.com", "x402 services", "https://x402-list.com/services/pacta-control-plane-verification", "our entry in the directory",
     "2026-11-20"),
    ("Official MCP Registry", "the remote MCP server {MCP_NAME} ({MCP_URL})",
     "https://registry.modelcontextprotocol.io/v0/servers?search={MCP_NAME}", "returns data, not a page", "2026-11-14"),
    ("Glama MCP directory", "the Pacta MCP server, its tools and their schema", "https://glama.ai/mcp/servers/Fractal-Neurons/pacta", None, "2026-11-14"),
    ("Base EAS explorer (base.easscan.org)", "the onchain schema and the batch attestations of Pacta's findings by pacta.base.eth",
     "https://base.easscan.org/schema/view/{EAS_SCHEMA}", None, "2026-11-12"),
    ("GitHub", "the public source repository, the evidence summaries, llms.txt and SKILL.md", "{REPO}", None, "2026-11-12"),
]
LISTINGS_LEFT_OUT = ("npmjs.com", "smithery.ai", "pulsemcp.com")   # 404, 404, not verified (28 Nov 2026)
LISTINGS_CHECKED = "2026-11-28"
LISTED_DESC = ("Pacta reads who can upgrade, pause or change DeFi contracts on Ethereum and Base, compares what a protocol's documents say "
               "with the chain, and attests the compared findings onchain on Base.")


def listings(H):
    v = {"MCP_NAME": H.B2A.MCP_NAME, "MCP_URL": H.MCP_URL, "EAS_SCHEMA": H.B2A.EAS_SCHEMA, "REPO": H.REPO}
    rows = [(n, w.format(**v), u.format(**v), note, d) for n, w, u, note, d in LISTINGS]
    assert all(u.startswith("https://") for _, _, u, _, _ in rows) and len({n for n, *_ in rows}) == len(rows)
    front = [u for _, _, u, _, _ in rows if urllib.parse.urlsplit(u).path in ("", "/")]
    assert not front, f"a listing links a directory's front page, not our entry: {front}"
    return sorted(sorted(rows, key=lambda r: r[0].lower()), key=lambda r: r[4], reverse=True)   # newest first, then A to Z


def listed_page(H, idx):
    rel, pre = "listed/", "../"
    rows = listings(H)
    newest = rows[0][4]
    desc = DESC[rel]
    head_html = ('<p class="lede" data-first-lines>Pacta\'s MCP server and its pay-per-call API are listed in the places below. Each link goes to '
                 'our entry there. If you run a directory of MCP servers, x402 services or DeFi tools and want '
                 'to list us, the facts you need are on this page.</p>'
                 f'<p class="s">Changed {CHANGED}.</p>')
    facts = [("Name", H.E(H.ORG_LD["name"])), ("Description", H.E(LISTED_DESC)),
             ("MCP address", f'<code>{H.E(H.MCP_URL)}</code>'), ("API description", f'<code>{H.E(H.OPENAPI_URL)}</code>'),
             ("Price list", f'<a href="{pre}#pricing">{H.E(H.BASE_URL)}/#pricing</a>'),
             ("Contact", H.E(H.CONTACT))]
    trs = [[H.E(n), H.E(w), f'<a href="{H.E(u)}" target="_blank" rel="noopener">{H.E(u)}</a>' + (f'<br><span class="s">{H.E(note)}</span>' if note else ""),
            f'<span class="nowrap">{H.E(d)}</span>'] for n, w, u, note, d in rows]
    k = len(LISTINGS_LEFT_OUT)
    secs = [("listings", f"{len(rows)} listings, newest first",
             _ptable(H, ["Listing", "What it lists", "Our entry", "Listed"], trs, "Where Pacta is listed, newest first", "data-listings", soft=True)
             + f'<p data-listed-left-out>{k} more director{"ies are" if k != 1 else "y is"} left out: our entry there answered 404 or could '
             f'not be verified when the list was checked on {LISTINGS_CHECKED}.</p>'),
            ("directories", "For directories",
             '<dl class="memo-meta">' + "".join(f"<dt>{k_}</dt><dd>{v}</dd>" for k_, v in facts) + "</dl>"),
            ("next", "Read next", read_next(H, pre, ["learn/connect-mcp-agent/", "learn/who-can-upgrade/"]))]
    return page(H, idx, rel, desc, head_html, secs), {"listings": len(rows), "left_out": k, "newest_listing": newest, "newest_input": newest}


# ---- the change date of the use pages and /listed/: the day the page's own text last changed. TEXT_PINS holds that day with a
# fingerprint of the text (the article without its generated example answers and dates); a changed text fails the build until
# its pin is set again. The page shows the later of that day and its newest input (the example's reading, the newest listing).
CHANGED = "@@CHANGED@@"
TEXT_PINS = {"learn/who-can-upgrade/": ("2026-11-28", "0b3943c787230351"),
             "learn/check-before-deposit/": ("2026-11-28", "34466fa5c8614468"),
             "learn/connect-mcp-agent/": ("2026-11-28", "44fb30a33c4e4f60"),
             "listed/": ("2026-11-28", "3f72448b274d13ba")}


def text_fingerprint(html_):
    art = html_.split('<article class="memo" data-page=', 1)[1].split("</article>", 1)[0]
    art = re.sub(r"<span data-example>.*?</span>", "", art, flags=re.S)
    art = re.sub(r"<time [^>]*>.*?</time>", "", art.replace(CHANGED, ""), flags=re.S)
    return hashlib.sha256(art.encode("utf-8")).hexdigest()[:16]


def changed(rel, html_, newest_input):
    fp = text_fingerprint(html_)
    pin = TEXT_PINS.get(rel)
    assert pin and pin[1] == fp, f"{rel}: the page text changed; set TEXT_PINS[{rel!r}] = (<the day of the change>, {fp!r})"
    day = max(d for d in (pin[0], newest_input) if d)
    assert html_.count(CHANGED) == 1, rel
    return html_.replace(CHANGED, _date(day)), day


def record_links(H, F, slug):
    """The links block straight under a record page's lede: up to its chain page and each list it is on, five others of the same
    chain and basket, and how to check it yourself."""
    p, pre = F[slug], "../../"
    L = [f'<a href="{pre}chains/{c}/">On {H.E(H.CHAINS[c][0])}</a>' for c in p["chains"] if c in CHAIN_PAGES]
    if p["timelock"]["kind"] == "listed":
        L.append(f'<a href="{pre}control/timelock/">Behind a timelock of {H.E(say_dur(p["timelock"]["seconds"]))}</a>')
    if p["quorum"]["kind"] == "listed":
        L.append(f'<a href="{pre}control/multisig/">Fewest signers needed on any control: {p["quorum"]["k"]} of {p["quorum"]["n"]}</a>')
    if p["docs"]["kind"] == "listed":
        L.append(f'<a href="{pre}docs-vs-chain/">Documents differ from the chain</a>')
    L.append(f'<a href="{pre}learn/who-can-upgrade/">How to check this yourself</a>')
    lines = [f'<p class="s" data-fact-lists>{H.SEP.join(L)}</p>']
    for c in p["chains"]:
        b, os_ = others(F, slug, c)
        if not os_:
            continue
        where = f"Others on {H.CHAINS[c][0]}" + (f" in {basket_label(H, b)}" if b else "")
        lines.append(f'<p class="s" data-others>{H.E(where)}: ' + ", ".join(f'<a href="../{q["slug"]}/">{H.E(q["name"])}</a>' for q in os_) + "</p>")
    return '<nav class="fact-links" aria-label="Lists this record is on" data-fact-links>' + "".join(lines) + "</nav>"


def build(H, idx, sp, cards, radar):
    """{relative path: html} for the new pages, the facts, and the per-page numbers for check()."""
    times = block_times(H.ROOT, radar)
    F = protocol_facts(H, idx, sp, cards)
    L = lists(F)
    out, nums = {}, {}
    for rel, fn in (("control/timelock/", timelock_page), ("control/multisig/", multisig_page), ("docs-vs-chain/", docs_page)):
        out[rel], nums[rel] = fn(H, idx, L, times)
    for c in CHAIN_PAGES:
        out[f"chains/{c}/"], nums[f"chains/{c}/"] = chain_page(H, idx, L, times, c)
    for rel, fn in (("learn/who-can-upgrade/", learn_who), ("learn/check-before-deposit/", learn_deposit),
                    ("learn/connect-mcp-agent/", learn_connect)):
        out[rel], nums[rel] = fn(H, idx, F, times)
    out["listed/"], nums["listed/"] = listed_page(H, idx)
    for rel in [f"learn/{k}/" for k in LEARN] + ["listed/"]:
        out[rel], nums[rel]["date"] = changed(rel, out[rel], nums[rel].pop("newest_input", None))
    assert list(out) == PAGES
    return out, F, L, nums


def first_lines_counts(html_):
    """The numbers marked in a page's first lines (data-n) and the rows of its list table."""
    m = re.search(r'<p class="lede" data-first-lines>(.*?)</p>', html_, re.S)
    ns = {}
    for k, v in (re.findall(r'<span data-n="([a-z]+)">([\d,]+)</span>', m.group(1)) if m else []):
        v = int(v.replace(",", ""))
        ns[k] = v if ns.get(k, v) == v else -1                                   # one key marked twice with two values: no count matches

    t = re.search(r"<tbody data-rows>(.*?)</tbody>", html_, re.S)
    return ns, (len(re.findall(r"<tr>", t.group(1))) if t else None)


def check(out, L, nums):
    """Rule a: a count in a page's first lines equals the rows under it (and the parts add up to the protocols checked). Returns the
    report lines; raises AssertionError on the first mismatch."""
    lines, bad = [], []
    for rel in LIST_PAGES + tuple(f"chains/{c}/" for c in CHAIN_PAGES):
        ns, rows = first_lines_counts(out[rel])
        ok = ns.get("rows") == rows == len(L[rel]["rows"])
        parts = ""
        if rel == "control/timelock/":
            ok &= ns["rows"] + ns["nd"] + ns["zero"] == ns["total"] == L[rel]["total"]
            parts = f'; {ns["rows"]} listed + {ns["nd"]} not determined + {ns["zero"]} with no delay on a sampled control = {ns["total"]} protocols'
        elif rel == "control/multisig/":
            ok &= ns["rows"] + ns["nd"] + ns.get("governor", 0) == ns["total"] == L[rel]["total"]
            parts = f'; {ns["rows"]} listed + {ns["nd"]} not determined + {ns.get("governor", 0)} token vote = {ns["total"]} protocols'
        elif rel == "docs-vs-chain/":
            d = L[rel]
            ok &= ns["compared"] == len(d["compared"]) and ns["uncompared"] == len(d["uncompared"]) and ns["nd"] == len(d["nd"]) \
                and ns["agree"] == len(d["agree"]) and ns["rows"] + ns["nd"] + ns["agree"] == ns["compared"] \
                and ns["compared"] + ns["uncompared"] == ns["total"] == d["total"]
            parts = (f'; {ns["rows"]} differ + {ns["nd"]} not determined + {ns["agree"]} agree = {ns["compared"]} compared; '
                     f'+ {ns["uncompared"]} not compared = {ns["total"]} protocols')
        else:
            t = re.search(r"<tbody data-rows>(.*?)</tbody>", out[rel], re.S).group(1)
            cells = [re.findall(r'<td data-label="([^"]+)">(.*?)</td>', r) for r in re.findall(r"<tr>(.*?)</tr>", t)]
            tl = sum(1 for r in cells if not _txt(dict(r)["Timelock delay"]).startswith(("none on a sampled control", "not determined")))
            ms = sum(1 for r in cells if re.fullmatch(r"\d+ of \d+", dict(r)["Fewest signers needed"]))
            dv = sum(1 for r in cells if dict(r)["Documents and chain"] == "differ")
            ok &= ns["timelock"] == tl == nums[rel]["timelock"] and ns["multisig"] == ms == nums[rel]["multisig"] and ns["docs"] == dv == nums[rel]["docs"]
            cv, rows_all = L[rel], sum(len(L[f"chains/{c}/"]["rows"]) for c in CHAIN_PAGES)
            nei = ns.get("neither", 0)
            ok &= len(CHAIN_PAGES) == 2 and ns["both"] == len(cv["both"]) and ns["one"] == len(cv["one"]) and nei == len(cv["neither"]) \
                and ns["both"] + ns["one"] + nei == ns["total"] == cv["total"] and rows_all == ns["one"] + 2 * ns["both"]
            parts = (f'; behind a timelock {ns["timelock"]} = {tl} rows, signer threshold {ns["multisig"]} = {ms} rows, '
                     f'documents differ {ns["docs"]} = {dv} rows; ' + " + ".join(str(len(L[f"chains/{c}/"]["rows"])) for c in CHAIN_PAGES)
                     + f' rows on the two chain pages = {ns["one"]} on one chain + 2 x {ns["both"]} on both; {ns["one"]} + {ns["both"]} + {nei} on neither = {ns["total"]} protocols')
        # the count a description leads with (meta description, og: and twitter: copies) is the number of rows too
        dn = [int(m.group(1)) if m else None for m in (re.match(r"(\d+) DeFi protocols ", html.unescape(c)) for c in re.findall(
            r'<meta (?:name|property)="(?:description|og:description|twitter:description)" content="([^"]*)"', out[rel]))]
        ok &= bool(dn) and set(dn) == {rows}
        parts += f'; description {"/".join(str(x) for x in sorted(set(dn), key=str))} = {rows} rows'
        lines.append(f'/{rel}: first lines {ns.get("rows")} = {rows} rows{parts}: {"OK" if ok else "MISMATCH"}')
        if not ok:
            bad.append(rel)
    # the two cells of a chain page row agree: the Upgradeability cell's delay and the Timelock delay cell (cells_disagree())
    for c in CHAIN_PAGES:
        t = re.search(r"<tbody data-rows>(.*?)</tbody>", out[f"chains/{c}/"], re.S).group(1)
        rows = [dict(re.findall(r'<td data-label="([^"]+)">(.*?)</td>', r)) for r in re.findall(r"<tr>(.*?)</tr>", t)]
        why = [(_txt(r["Protocol"]), w) for r in rows for w in [cells_disagree(_txt(r["Upgradeability"]), _txt(r["Timelock delay"]))] if w]
        more = sum("on the upgrade path" in _txt(r["Timelock delay"]) for r in rows)
        lines.append(f'/chains/{c}/: the Upgradeability and Timelock delay cells agree on {len(rows) - len(why)} of {len(rows)} rows '
                     f'({more} {"gives" if more == 1 else "give"} the upgrade path\'s longer delay): {"OK" if not why else "MISMATCH " + "; ".join(f"{n}: {w}" for n, w in why)}')
        if why:
            bad.append(f"chains/{c}/")
    assert not bad, "first-line counts differ from the rows, or two cells of a row disagree: " + "; ".join(lines)
    return lines


def _txt(cell):
    """a table cell's text: no tags (the soft breaks), no entities"""
    return html.unescape(re.sub(r"<[^>]+>", "", cell))
