"""Loader for tools/scorecard_corrections.json: declarative scorecard wording, scope and status corrections.

One entry per protocol slug (status, headline, pinnedBlock, explanatorySentence, summaryShort, optional subPill / subtitle /
parityText / badgeTier / factorOverrides / recordOverrides / leadRecord). Shared by tools/control_diff.py, tools/scorecard.py,
tools/summary_short.py, tools/build_lookup.py and tools/build_site.py, so a correction is one JSON entry and a rebuild.

recordOverrides correct the published wording of a record (surface, target label, category, documented reference, or a substring of
the observed / documented text). tools/apply_scorecard_corrections.py writes them into docs/api/v1/index.json (the page, the JSON
feeds and the browser all read that file); the attested audits/ summary documents and every hash, block and UID are never touched.
apply_record_overrides is idempotent: applied to an already-corrected record it changes nothing."""
import copy
import json
import os
import re


def _json_file(*a, **k):
    """json.load on a file that is closed straight away (no ResourceWarning)."""
    with open(*a, **k) as fh:
        return json.load(fh)


PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scorecard_corrections.json")
_DATA = None


def data():
    global _DATA
    if _DATA is None:
        _DATA = _json_file(PATH, encoding="utf-8")
    return _DATA


def get(slug):
    """The correction entry for a protocol slug, or None."""
    return data()["protocols"].get(slug)


def status(slug):
    c = get(slug)
    return c.get("status") if c else None


def unresolved(slug):
    return status(slug) == "unresolved"


# the two neutral statuses: neither Delta nor Aligned, never the amber Parameter Delta badge, never the paid re-check prompt
NEUTRAL = ("unresolved", "recent_change", "docs_updated")


def recent_change(slug):
    """Changed recently: observed within 48 hours of an on-chain change; re-checked after 72 hours before it counts as a Delta."""
    return status(slug) == "recent_change"


def neutral(slug):
    return status(slug) in NEUTRAL


def lead_record(slug):
    """The record id a correction is about (its headline, pinned block and evidence bind to it), or None."""
    c = get(slug)
    return c.get("leadRecord") if c else None


def surface_class(e):
    """A record's classification as derived surfaces state it: 'observed_uncompared' when recordDisplay shows it as Observed /
    Uncompared (the attested index.json classification itself is never rewritten)."""
    return "observed_uncompared" if record_display(e.get("id")).get("badge") == "observed" else e.get("classification")


def record_display(record_id):
    """Display-only wording for one record card (e.g. {"documentedLabel": "Sister vault reference."}); never written to index.json."""
    for c in data()["protocols"].values():
        if record_id in (c.get("recordDisplay") or {}):
            return c["recordDisplay"][record_id]
    return {}


def recent_change_rule():
    return data()["recentChangeRule"]["text"]


def reviewed():
    """The single table of the 56 reviewed findings (tools/scorecard_corrections.json reviewedFindings, from the verifier's rulings):
    every count, tab, sentence and feed is computed from it."""
    return data()["reviewedFindings"]


def finding_class(slug):
    """A reviewed Delta's subcategory (clear_weaker / real_difference / bookkeeping), or None."""
    for k, members in reviewed()["deltaGroups"].items():
        if slug in members:
            return k
    return None


def reviewed_status(slug):
    """The public status the rulings give a reviewed finding (delta / recent_change / docs_updated / unresolved), or None."""
    return reviewed()["partition"].get(slug)


def breakdown():
    """{"reviewed": 56, "delta": 43, "clearWeaker": 16, "realDifference": 16, "bookkeeping": 11, "recentChange": 1, "docsUpdated": 1,
    "unresolved": 11}, counted from the partition and the Delta groups (and asserted against the rulings' own counts)."""
    rv = reviewed()
    part = rv["partition"]
    n = lambda st: sum(1 for v in part.values() if v == st)
    g = {k: len(v) for k, v in rv["deltaGroups"].items()}
    out = {"reviewed": len(part), "delta": n("delta"), "clearWeaker": g["clear_weaker"], "realDifference": g["real_difference"],
           "bookkeeping": g["bookkeeping"], "recentChange": n("recent_change"), "docsUpdated": n("docs_updated"), "unresolved": n("unresolved")}
    assert out["delta"] == sum(g.values()) == rv["counts"]["delta"] and out["unresolved"] == rv["counts"]["unresolved"], out
    return out


def flagged_total():
    return breakdown()["reviewed"]


def breakdown_text():
    """The one sentence on Home and Radar, verbatim from the rulings and asserted equal to the counts."""
    b, t = breakdown(), reviewed()["homeRadarSentence"]
    want = (f'Of {b["reviewed"]} reviewed findings, {b["delta"]} are Deltas ({b["clearWeaker"]} weaker protections, {b["realDifference"]} other '
            f'differences and {b["bookkeeping"]} bookkeeping changes), {b["recentChange"]} is Changed recently, {b["docsUpdated"]} is Docs updated '
            f'and {b["unresolved"]} are Unresolved; these statuses use retained chain observations.')
    assert t == want, (t, want)
    return t


def breakdown_short():
    """'16 weaker protections · 16 other differences · 11 bookkeeping'."""
    b = breakdown()
    return f'{b["clearWeaker"]} weaker protections · {b["realDifference"]} other differences · {b["bookkeeping"]} bookkeeping'


def slug_of(name):
    """The site's slug rule for a protocol name (build_site.protocol_slug, imported lazily)."""
    import build_site
    return build_site.protocol_slug(name)


def apply_record_overrides(entries):
    """A copy of the record list with each correction's recordOverrides applied (field replacement, or "replace" substring pairs
    inside onchain_observed / documented_reference / surface). The input list is not modified."""
    over = {rid: o for c in data()["protocols"].values() for rid, o in (c.get("recordOverrides") or {}).items()}
    over.update((data().get("labelOverrides") or {}).get("recordOverrides") or {})   # wording-35 r4 labels (no correction status)
    out = []
    for e in entries:
        o = dict(over.get(e.get("id")) or {})
        # a flagged record that carries its own one-line summary states the protocol's corrected line, never the superseded claim
        c = get(slug_of(e["protocol"])) if e.get("classification") == "parameter_delta" and "summary_short" in e else None
        if c and c.get("summaryShort") and e.get("summary_short") != c["summaryShort"]:
            o.setdefault("summary_short", c["summaryShort"])
        if not o:
            out.append(e)
            continue
        e = copy.deepcopy(e)
        for k, v in o.items():
            if k == "replace":
                for old, new in v:
                    hit = False
                    for f in ("onchain_observed", "documented_reference", "surface"):
                        if isinstance(e.get(f), str) and old in e[f] and not (old in new and new in e[f]):
                            e[f] = e[f].replace(old, new)
                            hit = True
                        elif isinstance(e.get(f), str) and new in e[f]:
                            hit = True                     # already corrected (idempotent)
                    assert hit, f"correction replace {old!r} not found in record {e['id']}"
            else:
                e[k] = v
        out.append(e)
    return out


def finding(slug):
    """The corrected one-line finding, '<headline> (#<block>)', or None."""
    c = get(slug)
    if not c or not c.get("headline"):
        return None
    return f'{c["headline"]} (#{c["pinnedBlock"]:,})'


def check():
    """Structural check of the registry (asserted by the build): known statuses, <= 90-character summaries, no stale wording."""
    errs = []
    for s, c in data()["protocols"].items():
        if c.get("status") not in ("unresolved", "recent_change", "docs_updated", "delta"):
            errs.append(f"{s}: unknown status {c.get('status')!r}")
        if c.get("summaryShort") and len(c["summaryShort"]) > 90:
            errs.append(f"{s}: summaryShort over 90 characters")
        if not isinstance(c.get("pinnedBlock"), int):
            errs.append(f"{s}: pinnedBlock must be the historical block number")
        if re.search(r"across control surfaces", json.dumps(c)):
            errs.append(f"{s}: 'across control surfaces' overstates a sampled surface")
    members = [x for v in reviewed()["deltaGroups"].values() for x in v]
    if len(members) != len(set(members)):
        errs.append("reviewedFindings: a protocol is in more than one Delta group")
    part = reviewed()["partition"]
    if sorted(members) != sorted(k for k, v in part.items() if v == "delta"):
        errs.append("reviewedFindings: the Delta groups are not the partition's Deltas")
    for s_, st in part.items():
        if st != "delta" and status(s_) != st:
            errs.append(f"{s_}: registry status {status(s_)!r} differs from the rulings' {st!r}")
        if st == "delta" and status(s_) not in (None, "delta"):
            errs.append(f"{s_}: the rulings keep it Delta, the registry says {status(s_)!r}")
    for s, c in data()["protocols"].items():
        if not c.get("leadRecord"):
            errs.append(f"{s}: every correction names its leadRecord")
        if c.get("status") == "recent_change" and not c.get("recentChange"):
            errs.append(f"{s}: recent_change needs the recentChange observation note")
    return errs
