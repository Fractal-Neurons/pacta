"""What differs: a compact, deterministic summary of a protocol's flagged records (parameter_delta / protective_delta).

Used by tools/build_site.py (the "What differs" callout on /protocols/<slug>/ and the homepage inspector) and by
tools/build_lookup.py (the lookup catalog, so the MCP server and the pacta-x402 Worker can return the same summary).

    what_differs(entries) -> {"changed": [...], "matched": [...]} or None when no record is flagged

changed: {"parameter", "observed", "documented", "recordId", "classification"} -- discrepant parameters first (the headline);
         parameter_delta records always precede protective_delta records, and a pair keeps its record's own surface label
matched: {"parameter", "value", "recordId"}                                   -- what agrees with the documentation

Only structured facts are paired: Safe thresholds ("k-of-n") and timelock delays (observed_delay_seconds vs
documented_delay_seconds). A flagged record with no structured pair still lists its surface with the shortest
verbatim observed / documented sentences, so nothing is invented.
"""

import re

FLAGGED = ("parameter_delta", "protective_delta")
THRESHOLD_RE = re.compile(r"\b(\d{1,2})\s*-?\s*of\s*-?\s*(\d{1,2})\b", re.I)
MAX_TEXT = 220


def thresholds(text):
    """Ordered, de-duplicated k-of-n thresholds named in a text (k <= n)."""
    out = []
    for k, n in THRESHOLD_RE.findall(text or ""):
        t = (int(k), int(n))
        if t[0] <= t[1] and t not in out:
            out.append(t)
    return out


def fmt_threshold(t):
    return f"{t[0]}-of-{t[1]}"


def fmt_delay(s):
    if not isinstance(s, (int, float)) or isinstance(s, bool):
        return None
    s = int(s)
    if s == 0:
        return "0 s (no delay)"
    for unit, size in (("d", 86400), ("h", 3600), ("min", 60)):
        if s % size == 0:
            return f"{s // size} {unit}"
    return f"{s} s"


def first_sentence(text):
    """The first sentence: up to the first '.' or ';' followed by a space (or the end). A ';' inside parentheses never ends it
    ("(token distribution; OBOL token): '…'" keeps its quote)."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    depth = 0
    for i, ch in enumerate(t):
        depth += (ch == "(") - (ch == ")") if ch in "()" else 0
        if ch in ".;" and (i + 1 == len(t) or t[i + 1] == " ") and not (ch == ";" and depth > 0) and i > 0:
            t = t[:i + 1]
            break
    return t if len(t) <= MAX_TEXT else t[:MAX_TEXT - 1].rstrip() + "…"


def _label(e, generic):
    """The record's own scope (its surface, else its target label); the bare generic label only when the record names neither,
    so a specific contract / role / path is never reduced to "Timelock delay" or "Safe threshold"."""
    return e.get("surface") or e.get("target_label") or generic


def what_differs(entries):
    # a looser-than-documented record (parameter_delta) leads; a protective_delta never becomes changed[0] ahead of it
    flagged = sorted((e for e in entries if e.get("classification") in FLAGGED),
                     key=lambda e: 0 if e.get("classification") == "parameter_delta" else 1)
    if not flagged:
        return None
    changed, matched = [], []
    for e in flagged:
        obs_t, doc_t = thresholds(e.get("onchain_observed")), thresholds(e.get("documented_reference"))
        paired = False
        for d in doc_t:
            if d in obs_t:
                matched.append({"parameter": _label(e, "Safe threshold"), "value": fmt_threshold(d), "recordId": e["id"]})
                continue
            o = next((x for x in obs_t if x[0] == d[0] and x not in doc_t), None) or next((x for x in obs_t if x[1] == d[1] and x not in doc_t), None)
            if o:
                changed.append({"parameter": _label(e, "Safe threshold"), "observed": fmt_threshold(o), "documented": fmt_threshold(d),
                                "recordId": e["id"], "classification": e["classification"]})
                paired = True
        od, dd = fmt_delay(e.get("observed_delay_seconds")), fmt_delay(e.get("documented_delay_seconds"))
        if od and dd:
            if e.get("observed_delay_seconds") == e.get("documented_delay_seconds"):
                matched.append({"parameter": _label(e, "Timelock delay"), "value": od, "recordId": e["id"]})
            else:
                changed.append({"parameter": _label(e, "Timelock delay"), "observed": od, "documented": dd, "recordId": e["id"],
                                "classification": e["classification"]})
                paired = True
        if not paired:
            changed.append({"parameter": e.get("surface") or e["id"], "observed": first_sentence(e.get("onchain_observed")),
                            "documented": first_sentence(e.get("documented_reference")), "recordId": e["id"], "classification": e["classification"]})
    for e in entries:
        if e.get("classification") == "aligned_baseline":
            matched.append({"parameter": e.get("surface") or e["id"], "value": "matches the documentation", "recordId": e["id"]})
    seen_c, changed_u = set(), []
    for c in changed:
        k = (c["parameter"], c["observed"], c["documented"])
        if k not in seen_c:
            seen_c.add(k)
            changed_u.append(c)
    changed = changed_u
    seen, uniq = set(), []
    for m in matched:
        k = (m["parameter"], m["value"])
        if k not in seen:
            seen.add(k)
            uniq.append(m)
    return {"changed": changed, "matched": uniq}
