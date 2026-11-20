#!/usr/bin/env python3
"""apply_sprint34_attestation.py - stamp the Sprint 34 Base EAS attestation and publish the staged Sprint 34 records.

    python3 tools/apply_sprint34_attestation.py --uid 0x<32-byte UID> --tx 0x<32-byte tx hash> [--core ../pacta-core] [--skip-tests]

Input: tools/staged/sprint-34-records.json (written by pacta-core packages/bulk-harvester/promote/s34_stage.py + s26_emit.py --sprint 34).
The UID must be the attestation of the staged summary under schema 0x7ff4..df83 (chainId 1, the Ethereum pin, verifiedCount = aligned +
protective records, driftCount = parameter-delta records, summarySha256 = the staged SHA-256); this script does not read the chain.

Sprint 34 converts published RPC-pinned protocols to Base-EAS records under the stop rule (no new RPC-observed row): conversions from
promote/s34_curated.py (staged "converts_rpc_pinned"; their RPC-pinned records are retired). No bounty PR is folded: BOUNTY_PRS is
empty, and bounties/leaderboard.json, tools/bounty_wave2.json and tools/bounty_wave3.json are not touched.

Everything else is the Sprint 28 / 29 apply (imported). Nothing is committed, pushed or deployed. Placeholder UIDs / tx hashes (one
repeated byte) need --allow-placeholder and are preview-only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_sprint29_attestation as S29  # noqa: E402  (configures and extends the Sprint 28 apply; re-pointed to Sprint 34 below)

A = S29.A
SPRINT = 34
A.SPRINT = S29.SPRINT = SPRINT
A.STAGED = os.path.join(HERE, "staged", f"sprint-{SPRINT}-records.json")
S29.NOTES = os.path.join(HERE, "staged", f"sprint-{SPRINT}-surface-notes.json")   # optional
A.NEW_BRIEFS = ()
# open community hunter PRs and the Sprint 34 NO_TOUCH list (#47, #81, #114-#117, #119-#136): these protocols gain no
# record while the PR is open
A.NO_TOUCH = ("optimism-bridge", "usd-ai", "fraxtal-bridge", "theo-network-thusd", "theo-network", "gami-labs", "gmx", "pancakeswap-amm-v3",
              "usdt0", "frankencoin", "frankencoin-zchf", "frankencoin-fcs", "decentralized-euro", "wildcat-protocol", "concentrator",
              "team-finance", "autofinance", "glif", "ankr", "ankr-eth-staking", "3f", "aera-v3", "nodedao", "derive-v3-options",
              "origami-finance", "world-chain-bridge")
# ---- TARGET-BEGIN (written by the staging run; predict_target() re-derives every number and must agree)
A.TARGET = {"sprints": 34, "records": 299, "eas_attestations": 34, "protocols": 313, "eas_protocols": 180, "rpc_protocols": 133, "briefs": 17,
            "badge_tiers": {"aligned": 119, "parameter_delta": 61, "rpc_observed": 133}, "base_records": 36,
            "rpc_by_chain": {"ethereum": 122, "base": 11}}
# ---- TARGET-END
A.ROW_NOTE = ("Backlog conversion under the stop rule (Base-EAS records only, no new RPC-observed row): twelve protocols moved "
              "from RPC-pinned to Base EAS, each a curated documentation-vs-chain record checked against verified source. Three new "
              "gaps: Taiko's emergency proposals execute on the DAO with 4 of 5 council approvals (docs: 6; standard 3, docs: 5); Hop's "
              "L1 ETH Bridge governance (Bonder whitelist) is a 1-day timelock run by a 2-of-3 key Safe, not the documented DAO; Hakka's "
              "multi-sig has an owner its keyholder list does not name. Nine aligned: the Gnosis bridge governors (8 of 15), Aegis, "
              "Tangent, LUSD Chicken Bonds, Angstrom, and the supply commitments of STO, RCH, GAMMA and PIKU; no bounty fold")
# no bounty fold in Sprint 34 (Wave 2 retired at 30 / 30; Wave 3 submissions under review): nothing is wired
S29.BOUNTY_PRS = ()


def wire_bounties(staged):
    """Sprint 34 folds no bounty PR: a staged bounty credit is refused; bounties/leaderboard.json, tools/bounty_wave2.json,
    tools/bounty_wave3.json and verify_site_v2.py's bounty checks are left as published."""
    if staged.get("bounty_credits"):
        A.fail(f"Sprint {SPRINT} folds no bounty PR, but the staging carries bounty credits {sorted(staged['bounty_credits'])}", 1)


S29.wire_bounties = A.wire_bounties = wire_bounties
# build_lookup TOKENS gains a "Sprint 34 promotion" block only when the staging names new-protocol tokens (an empty block would not parse)
_add_tokens = A.add_tokens
A.add_tokens = lambda staged: _add_tokens(staged) if staged.get("tokens") else None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if A.TARGET is None:
        A.fail("TARGET is not set: run the staging (s34_stage.py + s26_emit.py --sprint 34) and write the TARGET block first")
    if "--wave2-payouts" in argv:
        A.fail("--wave2-payouts given, but Sprint 34 folds no bounty PR (BOUNTY_PRS is empty)")
    return A.main(argv)


if __name__ == "__main__":
    sys.exit(main())
