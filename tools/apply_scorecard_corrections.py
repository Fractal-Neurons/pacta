#!/usr/bin/env python3
"""Write the recordOverrides of tools/scorecard_corrections.json into docs/api/v1/index.json (idempotent).

    python3 tools/apply_scorecard_corrections.py            # rewrite the corrected records in place
    python3 tools/apply_scorecard_corrections.py --check    # exit 1 when index.json lacks a correction

It also writes idx["scorecard_status_overrides"] = {record id: {"status": "unresolved" | "recent_change", "label": ...}} for the
flagged records of a protocol the registry marks with a neutral status (Unresolved / Changed recently), so the browser (which reads only index.json) shows the neutral status, never "Parameter
delta". Only the corrected wording fields of the named records change (surface, target_label, category, documented_reference, or the given
substrings of onchain_observed / documented_reference). Block numbers, block hashes, classifications, summary documents, summary
SHA-256 digests and Base EAS UIDs are never touched, and audits/ is never written."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scorecard_corrections as CORR  # noqa: E402

INDEX = os.path.join(HERE, "..", "docs", "api", "v1", "index.json")
FIXED = ("id", "protocol", "sprint", "block_number", "block_hash", "classification", "summary_doc", "summary_sha256", "base_eas_uid",
         "target_contract", "observed_delay_seconds", "documented_delay_seconds")


def main(argv):
    raw = open(INDEX, encoding="utf-8").read()
    idx = json.loads(raw)
    new = CORR.apply_record_overrides(idx["entries"])
    for a, b in zip(idx["entries"], new):
        assert all(a.get(k) == b.get(k) for k in FIXED), f"a correction may not change attested fields: {a['id']}"
    changed = [b["id"] for a, b in zip(idx["entries"], new) if a != b]
    ov = {}
    for e in new:
        c = CORR.get(CORR.slug_of(e["protocol"])) or {}
        if c.get("status") in CORR.NEUTRAL and e["classification"] == "parameter_delta":
            ov[e["id"]] = {"status": c["status"],
                           "label": c.get("statusLabel") or c.get("subPill") or {"unresolved": "Unresolved", "recent_change": "Changed recently",
                                                                                  "docs_updated": "Docs updated"}[c["status"]]}
    ov = dict(sorted(ov.items()))
    if idx.get("scorecard_status_overrides") != ov:
        changed.append("scorecard_status_overrides")
    # the corrected headline / block / scope of every flagged record of a corrected protocol (the browser's "What differs" box)
    wo = {}
    for e in new:
        c = CORR.get(CORR.slug_of(e["protocol"])) or {}
        if (c.get("headline") or c.get("explanatorySentence")) and e["classification"] in ("parameter_delta", "protective_delta"):
            wo[e["id"]] = {"headline": c.get("headline"), "pinnedBlock": c["pinnedBlock"], "scope": c.get("explanatorySentence"),
                           "unresolved": c.get("status") == "unresolved", "recentChange": c.get("status") == "recent_change",
                           "docsUpdated": c.get("status") == "docs_updated"}
    wo = dict(sorted(wo.items()))
    if idx.get("scorecard_wording_overrides") != wo:
        changed.append("scorecard_wording_overrides")
    if "--check" in argv:
        if changed:
            print("index.json lacks corrections for", changed)
            return 1
        print("index.json carries every scorecard correction")
        return 0
    idx["entries"] = new
    idx["scorecard_status_source"] = "tools/scorecard_corrections.json"
    idx["scorecard_status_overrides"] = ov
    idx["scorecard_wording_overrides"] = wo
    out = json.dumps(idx, indent=2, ensure_ascii=False) + "\n"
    if raw.endswith("\n") and json.dumps(json.loads(raw), indent=2, ensure_ascii=False) + "\n" != raw:
        raise SystemExit("index.json is not in the canonical indent-2 form; refusing to reformat it")
    open(INDEX, "w", encoding="utf-8").write(out)
    print("corrected records:", changed or "none (already applied)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
