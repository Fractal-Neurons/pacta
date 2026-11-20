#!/usr/bin/env python3
"""apply_sprint36_attestation.py - stamp the Sprint 36 Base EAS attestation and publish the staged Sprint 36 records.

    python3 tools/apply_sprint36_attestation.py --uid 0x<32-byte UID> --tx 0x<32-byte tx hash> [--core ../pacta-core] [--skip-tests]

Input: tools/staged/sprint-36-records.json (written by pacta-core packages/bulk-harvester/promote/s36_stage.py + s26_emit.py --sprint 36).
The UID must be the attestation of the staged summary under schema 0x7ff4..df83 (chainId 1, the Ethereum pin, verifiedCount = aligned +
protective records, driftCount = parameter-delta records, summarySha256 = the staged SHA-256); this script does not read the chain.

Sprint 36 converts published RPC-pinned protocols to Base-EAS records under the stop rule (no new RPC-observed row): conversions from
promote/s36_curated.py (staged "converts_rpc_pinned"; their RPC-pinned records are retired). No bounty PR is folded: BOUNTY_PRS is
empty, and bounties/leaderboard.json, tools/bounty_wave2.json and tools/bounty_wave3.json are not touched.

Everything else is the Sprint 28 / 29 apply (imported). Nothing is committed, pushed or deployed. Placeholder UIDs / tx hashes (one
repeated byte) need --allow-placeholder and are preview-only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_sprint29_attestation as S29  # noqa: E402  (configures and extends the Sprint 28 apply; re-pointed to Sprint 36 below)

A = S29.A
SPRINT = 36
A.SPRINT = S29.SPRINT = SPRINT
A.STAGED = os.path.join(HERE, "staged", f"sprint-{SPRINT}-records.json")
S29.NOTES = os.path.join(HERE, "staged", f"sprint-{SPRINT}-surface-notes.json")   # optional
A.NEW_BRIEFS = ()
# open community hunter PRs (the Sprint 36 NO_TOUCH list, 23 slugs): these protocols gain no
# record while the PR is open
A.NO_TOUCH = ("pancakeswap-amm-v3", "fraxtal-bridge", "usdt0", "frankencoin", "wildcat-protocol", "concentrator", "team-finance",
              "autofinance", "ipor-fusion", "gmx", "ankr", "3f", "aera-v3", "nodedao", "derive-v3-options", "origami-finance",
              "world-chain-bridge", "harvest-finance", "optimism-bridge", "usd-ai",
              "sushi-v2", "dodo-amm", "aster-bridge")
# ---- TARGET-BEGIN (written by the staging run; predict_target() re-derives every number and must agree)
A.TARGET = {"sprints": 36, "records": 304, "eas_attestations": 36, "protocols": 313, "eas_protocols": 184, "rpc_protocols": 129, "briefs": 17,
            "badge_tiers": {"aligned": 122, "parameter_delta": 62, "rpc_observed": 129}, "base_records": 38,
            "rpc_by_chain": {"ethereum": 119, "base": 10}}
# ---- TARGET-END
A.ROW_NOTE = ("Backlog conversion under the stop rule (Base-EAS records only, no new RPC-observed row): two protocols moved from "
              "RPC-pinned to Base EAS and one Base surface was added to Spark / Sky, each a curated documentation-vs-chain record checked "
              "against verified source. Aura's Protocol Multisig is 4-of-7 as documented for its non-delegated authority (its two "
              "Safe keeper modules, vetted and disclosed, act without the threshold within fixed scopes); Sommelier's Registry and "
              "PriceRouter are owned by a 3-day timelock whose proposer and executor is its multisig, as documented; Spark's Base sUSDC "
              "is the documented ERC-1967 UUPS proxy. The lookup gains verified "
              "contract aliases for flagship protocols; no bounty fold")
# no bounty fold in Sprint 36 (Wave 2 retired at 30 / 30; Wave 3 submissions under review): nothing is wired
S29.BOUNTY_PRS = ()


def wire_bounties(staged):
    """Sprint 36 folds no bounty PR: a staged bounty credit is refused; bounties/leaderboard.json, tools/bounty_wave2.json,
    tools/bounty_wave3.json and verify_site_v2.py's bounty checks are left as published."""
    if staged.get("bounty_credits"):
        A.fail(f"Sprint {SPRINT} folds no bounty PR, but the staging carries bounty credits {sorted(staged['bounty_credits'])}", 1)


S29.wire_bounties = A.wire_bounties = wire_bounties
# Node 18.19 (this host; CI runs Node 22): a `node --test` child that has passed every subtest can intermittently fail to exit, its
# main thread spinning, a V8 background-thread race made likelier by the larger generated lookup catalog (mcp.test.mjs: about 1 run in
# 5 with the Sprint 36 catalog, 0 / 20 with the Sprint 35 one; 0 / 30 with --single-threaded-gc). The suites run with that V8 flag
# (forwarded to every test child), one test file at a time; no assertion changes.
_run = A.run


def run(cmd, cwd, name, env=None):
    if len(cmd) > 1 and cmd[1] == "--test":
        cmd = [cmd[0], "--single-threaded-gc", "--test", "--test-concurrency=1", *cmd[2:]]
    return _run(cmd, cwd, name, env)


A.run = run
# build_lookup TOKENS gains a "Sprint 36 promotion" block only when the staging names new-protocol tokens (an empty block would not parse)
_add_tokens = A.add_tokens
A.add_tokens = lambda staged: _add_tokens(staged) if staged.get("tokens") else None

# Keep WALLET_CATALOG in worker.mjs and post-0cf32212 curator/scan count metadata synchronized on main (0cf32212 / 8361105).
import json
import re

_finish = A.finish
_sync_core = A.sync_core
_tests = A.tests


def sync_curator_and_scan_counts():
    bs_path = os.path.join(A.ROOT, "tools", "build_site.py")
    bs = A.read(bs_path)
    bs_new = re.sub(
        r"\(\d+ Base-EAS attested · (\d+) verified adverse control-plane gaps\)",
        f"({A.TARGET['eas_protocols']} Base-EAS attested · \\1 verified adverse control-plane gaps)",
        bs,
    )
    if bs_new != bs:
        A.write(bs_path, bs_new)

    cem_path = os.path.join(A.ROOT, "data", "curator-exposure-matrix.json")
    lk_path = os.path.join(A.ROOT, "docs", "api", "v1", "lookup.json")
    sc_path = os.path.join(A.ROOT, "docs", "api", "v1", "scorecards.json")
    gm_path = os.path.join(A.ROOT, "docs", "api", "v1", "graph-manifest.json")
    if not (os.path.isfile(cem_path) and os.path.isfile(lk_path) and os.path.isfile(sc_path)):
        return
    mat = json.loads(A.read(cem_path))
    lk_by = {x["slug"]: x for x in json.loads(A.read(lk_path))["items"] if x["kind"] == "protocol"}
    sc_by = {c["slug"]: c for c in json.loads(A.read(sc_path))["protocols"]}
    dt = mat.get("dataset_totals") or {}
    dt["indexed_protocols"] = A.TARGET["protocols"]
    dt["lookup_items_with_briefs"] = A.TARGET["protocols"] + A.TARGET["briefs"]
    dt["timelock_and_onboarding_briefs"] = A.TARGET["briefs"]
    dt["base_eas_attested_protocols"] = A.TARGET["eas_protocols"]
    gb = dt.get("grades_breakdown") or {}
    adv = gb.get("DELTA_adverse_gaps", 55)
    prot = gb.get("PROTECTIVE", 7)
    gb["ALIGNED"] = A.TARGET["badge_tiers"]["aligned"]
    gb["OBSERVED_rpc_pinned"] = A.TARGET["badge_tiers"]["rpc_observed"]
    gb["DELTA_adverse_gaps"] = adv
    gb["PROTECTIVE"] = prot
    if os.path.isfile(gm_path):
        gm = json.loads(A.read(gm_path))
        dt["graph_nodes"] = len(gm.get("nodes", []))
        dt["graph_edges"] = len(gm.get("edges", []))

    grade_map = {"aligned": "ALIGNED", "protective": "PROTECTIVE", "delta": "DELTA", "observed": "OBSERVED"}
    idx_entries = json.loads(A.read(A.INDEX))["entries"]
    latest_summary = {e["id"]: e.get("summary_short") for e in idx_entries}
    s36_summaries = {"sommelier": "Sommelier's Registry and PriceRouter are managed by its multisig, as documented"}

    for cur in mat.get("curators_and_institutional_allocators", []):
        for key in ("direct_wrappers", "underlying_aligned_protective", "underlying_adverse_gaps"):
            for row in cur.get(key, []):
                sl = row.get("slug")
                if sl in lk_by and sl in sc_by:
                    lki, sci = lk_by[sl], sc_by[sl]
                    was_obs = not row.get("easAttested", True)
                    row["easAttested"] = bool(lki["easAttested"])
                    row["grade"] = grade_map.get(sci.get("grade"), row.get("grade"))
                    row["chains"] = sci.get("chains") or [lki["chain"]]
                    row["pinnedBlock"] = lki["pinnedBlock"]
                    row["primaryContract"] = lki["primaryContract"]
                    row["targetLabel"] = lki["targetLabel"]
                    row["baseEasUids"] = lki.get("baseEasUids", [])
                    if was_obs and row["easAttested"] and sl in s36_summaries:
                        row["summary_short"] = s36_summaries[sl]
        dw = cur.get("direct_wrappers") or []
        if dw and "wrapper_counts" in cur:
            cur["wrapper_counts"] = {
                "total": len(dw),
                "aligned_or_protective": sum(1 for r in dw if r.get("grade") in ("ALIGNED", "PROTECTIVE")),
                "delta": sum(1 for r in dw if r.get("grade") == "DELTA"),
                "observed": sum(1 for r in dw if r.get("grade") == "OBSERVED"),
            }
    A.write(cem_path, json.dumps(mat, indent=2, ensure_ascii=False) + "\n")


def finish(core, node, skip_tests, stubs):
    sync_curator_and_scan_counts()
    # Wire sync_curator_and_scan_counts after graph_manifest too so graph_nodes/graph_edges stay exact before final build_twice
    orig_pin = A.pin_graph_manifest

    def pin_and_sync():
        res = orig_pin()
        sync_curator_and_scan_counts()
        A.build_twice()
        return A.pin_graph_manifest() if res != orig_pin() else res

    A.pin_graph_manifest = pin_and_sync
    try:
        return _finish(core, node, skip_tests, stubs)
    finally:
        A.pin_graph_manifest = orig_pin


def sync_core(core):
    _sync_core(core)
    wcat = os.path.join(core, "scripts", "sync-wallet-catalog.py")
    if os.path.isfile(wcat):
        A.run([sys.executable, "-B", "scripts/sync-wallet-catalog.py"], core, "pacta-core sync-wallet-catalog")


def tests(core, node):
    _tests(core, node)
    if core and os.path.isfile(os.path.join(core, "scripts", "sync-wallet-catalog.py")):
        A.run([sys.executable, "-B", "scripts/sync-wallet-catalog.py", "--check"], core, "sync-wallet-catalog --check")


A.finish = finish
A.sync_core = sync_core
A.tests = tests


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if A.TARGET is None:
        A.fail("TARGET is not set: run the staging (s36_stage.py + s26_emit.py --sprint 36) and write the TARGET block first")
    if "--wave2-payouts" in argv:
        A.fail("--wave2-payouts given, but Sprint 36 folds no bounty PR (BOUNTY_PRS is empty)")
    return A.main(argv)


if __name__ == "__main__":
    sys.exit(main())
