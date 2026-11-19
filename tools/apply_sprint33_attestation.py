#!/usr/bin/env python3
"""apply_sprint33_attestation.py - stamp the Sprint 33 Base EAS attestation and publish the staged Sprint 33 records.

    python3 tools/apply_sprint33_attestation.py --uid 0x<32-byte UID> --tx 0x<32-byte tx hash> [--core ../pacta-core] [--skip-tests]

Input: tools/staged/sprint-33-records.json (written by pacta-core packages/bulk-harvester/promote/s33_stage.py + s26_emit.py --sprint 33).
The UID must be the attestation of the staged summary under schema 0x7ff4..df83 (chainId 1, the Ethereum pin, verifiedCount = aligned +
protective records, driftCount = parameter-delta records, summarySha256 = the staged SHA-256); this script does not read the chain.

Sprint 33 converts published RPC-pinned protocols to Base-EAS records under the stop rule (no new RPC-observed row): conversions from
promote/s33_curated.py (staged "converts_rpc_pinned"; their RPC-pinned records are retired). No bounty PR is folded: BOUNTY_PRS is
empty, and bounties/leaderboard.json, tools/bounty_wave2.json and tools/bounty_wave3.json are not touched.

Everything else is the Sprint 28 / 29 apply (imported). Nothing is committed, pushed or deployed. Placeholder UIDs / tx hashes (one
repeated byte) need --allow-placeholder and are preview-only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_sprint29_attestation as S29  # noqa: E402  (configures and extends the Sprint 28 apply; re-pointed to Sprint 33 below)

A = S29.A
SPRINT = 33
A.SPRINT = S29.SPRINT = SPRINT
A.STAGED = os.path.join(HERE, "staged", f"sprint-{SPRINT}-records.json")
S29.NOTES = os.path.join(HERE, "staged", f"sprint-{SPRINT}-surface-notes.json")   # optional
A.NEW_BRIEFS = ()
# open community hunter PRs (#47, #81, #114-#117, #119-#129): these protocols gain no record while the PR is open
A.NO_TOUCH = ("optimism-bridge", "usd-ai", "fraxtal-bridge", "theo-network-thusd", "theo-network", "gami-labs", "gmx", "pancakeswap-amm-v3",
              "usdt0", "frankencoin", "frankencoin-fcs", "wildcat-protocol", "concentrator", "team-finance", "autofinance", "glif", "ankr")
# ---- TARGET-BEGIN (written by the staging run; predict_target() re-derives every number and must agree)
A.TARGET = {"sprints": 33, "records": 287, "eas_attestations": 33, "protocols": 313, "eas_protocols": 168, "rpc_protocols": 145, "briefs": 17,
            "badge_tiers": {"aligned": 110, "parameter_delta": 58, "rpc_observed": 145}, "base_records": 36,
            "rpc_by_chain": {"ethereum": 134, "base": 11}}
# ---- TARGET-END
A.ROW_NOTE = ("Backlog conversion under the stop rule (Base-EAS records only, no new RPC-observed row): thirteen protocols moved "
              "from RPC-pinned to Base EAS, each a curated documentation-vs-chain record checked against verified source and the "
              "runtime code: supply, minting or upgrade commitments on the documented token contracts (PoolTogether, SynFutures, "
              "Peapods, The Idols, Yield Basis, SoSoValue on Base, cVault, Parallel, Zama, Orderly, Index Coop), deBridge's 2/3 "
              "signature threshold, and a new gap: cBridge's pool signer set can be replaced by its owner governance (three keys, after "
              "a 7-day notice), while the docs put the fund pool at risk only beyond 2/3 of the SGN stake; no bounty fold")
# no bounty fold in Sprint 33 (Wave 2 retired at 30 / 30; Wave 3 submissions under review): nothing is wired
S29.BOUNTY_PRS = ()


def wire_bounties(staged):
    """Sprint 33 folds no bounty PR: a staged bounty credit is refused; bounties/leaderboard.json, tools/bounty_wave2.json,
    tools/bounty_wave3.json and verify_site_v2.py's bounty checks are left as published."""
    if staged.get("bounty_credits"):
        A.fail(f"Sprint {SPRINT} folds no bounty PR, but the staging carries bounty credits {sorted(staged['bounty_credits'])}", 1)


S29.wire_bounties = A.wire_bounties = wire_bounties
# build_lookup TOKENS gains a "Sprint 33 promotion" block only when the staging names new-protocol tokens (an empty block would not parse)
_add_tokens = A.add_tokens
A.add_tokens = lambda staged: _add_tokens(staged) if staged.get("tokens") else None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if A.TARGET is None:
        A.fail("TARGET is not set: run the staging (s33_stage.py + s26_emit.py --sprint 33) and write the TARGET block first")
    if "--wave2-payouts" in argv:
        A.fail("--wave2-payouts given, but Sprint 33 folds no bounty PR (BOUNTY_PRS is empty)")
    return A.main(argv)


if __name__ == "__main__":
    sys.exit(main())
