#!/usr/bin/env python3
"""apply_sprint35_attestation.py - stamp the Sprint 35 Base EAS attestation and publish the staged Sprint 35 records.

    python3 tools/apply_sprint35_attestation.py --uid 0x<32-byte UID> --tx 0x<32-byte tx hash> [--core ../pacta-core] [--skip-tests]

Input: tools/staged/sprint-35-records.json (written by pacta-core packages/bulk-harvester/promote/s35_stage.py + s26_emit.py --sprint 35).
The UID must be the attestation of the staged summary under schema 0x7ff4..df83 (chainId 1, the Ethereum pin, verifiedCount = aligned +
protective records, driftCount = parameter-delta records, summarySha256 = the staged SHA-256); this script does not read the chain.

Sprint 35 converts published RPC-pinned protocols to Base-EAS records under the stop rule (no new RPC-observed row): conversions from
promote/s35_curated.py (staged "converts_rpc_pinned"; their RPC-pinned records are retired). No bounty PR is folded: BOUNTY_PRS is
empty, and bounties/leaderboard.json, tools/bounty_wave2.json and tools/bounty_wave3.json are not touched.

Everything else is the Sprint 28 / 29 apply (imported). Nothing is committed, pushed or deployed. Placeholder UIDs / tx hashes (one
repeated byte) need --allow-placeholder and are preview-only.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_sprint29_attestation as S29  # noqa: E402  (configures and extends the Sprint 28 apply; re-pointed to Sprint 35 below)

A = S29.A
SPRINT = 35
A.SPRINT = S29.SPRINT = SPRINT
A.STAGED = os.path.join(HERE, "staged", f"sprint-{SPRINT}-records.json")
S29.NOTES = os.path.join(HERE, "staged", f"sprint-{SPRINT}-surface-notes.json")   # optional
A.NEW_BRIEFS = ()
# open community hunter PRs and the Sprint 35 NO_TOUCH list (#47, #81, #114-#117, #119-#138): these protocols gain no
# record while the PR is open
A.NO_TOUCH = ("optimism-bridge", "usd-ai", "fraxtal-bridge", "theo-network-thusd", "theo-network", "gami-labs", "gmx", "pancakeswap-amm-v3",
              "usdt0", "frankencoin", "frankencoin-zchf", "frankencoin-fcs", "decentralized-euro", "wildcat-protocol", "concentrator",
              "team-finance", "autofinance", "glif", "ankr", "ankr-eth-staking", "3f", "aera-v3", "nodedao", "derive-v3-options",
              "origami-finance", "world-chain-bridge", "harvest-finance")
# ---- TARGET-BEGIN (written by the staging run; predict_target() re-derives every number and must agree)
A.TARGET = {"sprints": 35, "records": 301, "eas_attestations": 35, "protocols": 313, "eas_protocols": 182, "rpc_protocols": 131, "briefs": 17,
            "badge_tiers": {"aligned": 120, "parameter_delta": 62, "rpc_observed": 131}, "base_records": 37,
            "rpc_by_chain": {"ethereum": 121, "base": 10}}
# ---- TARGET-END
A.ROW_NOTE = ("Backlog conversion under the stop rule (Base-EAS records only, no new RPC-observed row): two protocols moved from "
              "RPC-pinned to Base EAS, each a curated documentation-vs-chain record checked against verified source. One new gap: "
              "Seamless's Community Guardian is documented as a 3/6 multi-sig, but the listed Guardian Safe on Base is 2-of-3. One "
              "aligned: SushiSwap V3's factory is owned by a V3Manager that the 3-of-5 Operations Multisig owns, matching the documented "
              "minimum of three signatures; no bounty fold")
# no bounty fold in Sprint 35 (Wave 2 retired at 30 / 30; Wave 3 submissions under review): nothing is wired
S29.BOUNTY_PRS = ()


def wire_bounties(staged):
    """Sprint 35 folds no bounty PR: a staged bounty credit is refused; bounties/leaderboard.json, tools/bounty_wave2.json,
    tools/bounty_wave3.json and verify_site_v2.py's bounty checks are left as published."""
    if staged.get("bounty_credits"):
        A.fail(f"Sprint {SPRINT} folds no bounty PR, but the staging carries bounty credits {sorted(staged['bounty_credits'])}", 1)


S29.wire_bounties = A.wire_bounties = wire_bounties
# build_lookup TOKENS gains a "Sprint 35 promotion" block only when the staging names new-protocol tokens (an empty block would not parse)
_add_tokens = A.add_tokens
A.add_tokens = lambda staged: _add_tokens(staged) if staged.get("tokens") else None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if A.TARGET is None:
        A.fail("TARGET is not set: run the staging (s35_stage.py + s26_emit.py --sprint 35) and write the TARGET block first")
    if "--wave2-payouts" in argv:
        A.fail("--wave2-payouts given, but Sprint 35 folds no bounty PR (BOUNTY_PRS is empty)")
    return A.main(argv)


if __name__ == "__main__":
    sys.exit(main())
