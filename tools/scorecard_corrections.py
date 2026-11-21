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

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scorecard_corrections.json")
_DATA = None


def data():
    global _DATA
    if _DATA is None:
        _DATA = json.load(open(PATH, encoding="utf-8"))
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
NEUTRAL = ("unresolved", "recent_change")


def recent_change(slug):
    """Changed recently: observed within 48 hours of an on-chain change; re-checked after 72 hours before it counts as a Delta."""
    return status(slug) == "recent_change"


def neutral(slug):
    return status(slug) in NEUTRAL


def recent_change_rule():
    return data()["recentChangeRule"]["text"]


def finding_class(slug):
    """The class of one of the 56 historically flagged comparisons (clear_weaker / real_difference / bookkeeping / unresolved), or None."""
    for k, members in data()["findingClasses"]["members"].items():
        if slug in members:
            return k
    return None


def breakdown():
    """{"clearWeaker": 16, "needsExplanation": 17, "bookkeeping": 13, "unresolved": 10} from the registry's class members."""
    fc = data()["findingClasses"]
    return {fc["breakdownKeys"][k]: len(v) for k, v in fc["members"].items()}


def flagged_total():
    return sum(breakdown().values())


def breakdown_text(sep=", ", last=", and "):
    """'16 clear cases where the chain looks weaker than documented, 17 real differences needing explanation, 13 bookkeeping
    differences, and 10 unresolved' (plain words; never 'adverse')."""
    b = breakdown()
    parts = [f'{b["clearWeaker"]} clear cases where the chain looks weaker than documented',
             f'{b["needsExplanation"]} real differences needing explanation', f'{b["bookkeeping"]} bookkeeping differences',
             f'{b["unresolved"]} unresolved']
    return sep.join(parts[:-1]) + last + parts[-1]


def breakdown_short():
    """'16 weaker · 17 needing explanation · 13 bookkeeping · 10 unresolved'."""
    b = breakdown()
    return (f'{b["clearWeaker"]} weaker · {b["needsExplanation"]} needing explanation · {b["bookkeeping"]} bookkeeping · '
            f'{b["unresolved"]} unresolved')


def slug_of(name):
    """The site's slug rule for a protocol name (build_site.protocol_slug, imported lazily)."""
    import build_site
    return build_site.protocol_slug(name)


def apply_record_overrides(entries):
    """A copy of the record list with each correction's recordOverrides applied (field replacement, or "replace" substring pairs
    inside onchain_observed / documented_reference / surface). The input list is not modified."""
    over = {rid: o for c in data()["protocols"].values() for rid, o in (c.get("recordOverrides") or {}).items()}
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
        if c.get("status") not in ("unresolved", "recent_change", "delta"):
            errs.append(f"{s}: unknown status {c.get('status')!r}")
        if c.get("summaryShort") and len(c["summaryShort"]) > 90:
            errs.append(f"{s}: summaryShort over 90 characters")
        if not isinstance(c.get("pinnedBlock"), int):
            errs.append(f"{s}: pinnedBlock must be the historical block number")
        if re.search(r"across control surfaces", json.dumps(c)):
            errs.append(f"{s}: 'across control surfaces' overstates a sampled surface")
    members = [x for v in data()["findingClasses"]["members"].values() for x in v]
    if len(members) != len(set(members)):
        errs.append("findingClasses: a protocol is in more than one class")
    for s, c in data()["protocols"].items():
        if c.get("status") == "recent_change" and not c.get("recentChange"):
            errs.append(f"{s}: recent_change needs the recentChange observation note")
    return errs
