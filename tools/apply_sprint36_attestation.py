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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if A.TARGET is None:
        A.fail("TARGET is not set: run the staging (s36_stage.py + s26_emit.py --sprint 36) and write the TARGET block first")
    if "--wave2-payouts" in argv:
        A.fail("--wave2-payouts given, but Sprint 36 folds no bounty PR (BOUNTY_PRS is empty)")
    return A.main(argv)


if __name__ == "__main__":
    sys.exit(main())
