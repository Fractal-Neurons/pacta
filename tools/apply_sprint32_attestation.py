#!/usr/bin/env python3
"""apply_sprint32_attestation.py - stamp the Sprint 32 Base EAS attestation and publish the staged Sprint 32 records.

    python3 tools/apply_sprint32_attestation.py --uid 0x<32-byte UID> --tx 0x<32-byte tx hash> --wave2-payouts <pr>=0x<tx>,...
        [--core ../pacta-core] [--skip-tests]

Input: tools/staged/sprint-32-records.json (written by pacta-core packages/bulk-harvester/promote/s32_stage.py + s26_emit.py --sprint 32).
The UID must be the attestation of the staged summary under schema 0x7ff4..df83 (chainId 1, the Ethereum pin, verifiedCount = aligned +
protective records, driftCount = parameter-delta records, summarySha256 = the staged SHA-256); this script does not read the chain.

Sprint 32 converts published RPC-pinned protocols to Base-EAS records under the stop rule (no new RPC-observed row): conversions from the
v2.1 re-score bundles and from promote/s32_curated.py (staged "converts_rpc_pinned"; their RPC-pinned records are retired). Wave 2
closes at 30 / 30: the five merged and paid closeout PRs (#106 Tori, #107 Circle Gateway, #110 Cap, #111 Chainlink CCIP, #113 Kelp) are
folded the Sprint 29 way (promote/bounty_s32.py, --wave2-payouts), Epoch 1 widens from 25 to 30 settled slots ($30.00), and the remaining
$40.05 USDC is ring-fenced for Wave 3 (bounties/leaderboard.json and tools/bounty_wave2.json; the build regenerates the retired Wave 2
master issue; tools/bounty_wave3.json and bounties/wave-3/ are not touched; wire_bounties below).

Everything else is the Sprint 28 / 29 apply (imported). Nothing is committed, pushed or deployed. Placeholder UIDs / tx hashes (one
repeated byte) need --allow-placeholder and are preview-only.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apply_sprint29_attestation as S29  # noqa: E402  (configures and extends the Sprint 28 apply; re-pointed to Sprint 32 below)

A = S29.A
SPRINT = 32
A.SPRINT = S29.SPRINT = SPRINT
A.STAGED = os.path.join(HERE, "staged", f"sprint-{SPRINT}-records.json")
S29.NOTES = os.path.join(HERE, "staged", f"sprint-{SPRINT}-surface-notes.json")   # optional
A.NEW_BRIEFS = ()
# open community hunter PRs (#47, #81, #114-#117, and Wave 3 dossier #119): these protocols gain no record while the PR is open
A.NO_TOUCH = ("optimism-bridge", "usd-ai", "fraxtal-bridge", "theo-network-thusd", "theo-network", "gami-labs", "gmx", "pancakeswap-amm-v3")
# ---- TARGET-BEGIN (written by the staging run; predict_target() re-derives every number and must agree)
A.TARGET = {"sprints": 32, "records": 274, "eas_attestations": 32, "protocols": 313, "eas_protocols": 155, "rpc_protocols": 158, "briefs": 17,
            "badge_tiers": {"aligned": 98, "parameter_delta": 57, "rpc_observed": 158}, "base_records": 35,
            "rpc_by_chain": {"ethereum": 146, "base": 12}}
# ---- TARGET-END
A.ROW_NOTE = ("Backlog conversion under the stop rule (Base-EAS records only, no new RPC-observed row): twelve protocols moved from "
              "RPC-pinned to Base EAS (eleven curated documentation-vs-chain records checked against verified source, and Tori Finance "
              "from Wave 2 PR #106); Circle Gateway (#107) attested as a new protocol; post-pin drift re-read for Cap (#110), Chainlink "
              "CCIP (#111) and Kelp DAO (#113); Wave 2 closed at 30 / 30, the rest ring-fenced for Wave 3; new gaps: BendDAO (its 7-day "
              "timelock reads one day), Pickle (MasterChef run by a Safe directly) and Bio Protocol (the current BIO contract mints) "
              "(312 → 313)")
# Wave 2 closeout (founder decision closeout_two): the 5 merged and paid PRs, 1.00 USDC each; Epoch 1 widens to 30 slots, all settled
S29.BOUNTY_PRS = (106, 107, 110, 111, 113)
S29.WAVE2_BEFORE = {"settledEpochSlots": 25, "fundedUnencumberedSlots": 0, "fundedUnencumberedUsdc": "0.00", "ringFencedUsdc": "45.05"}
S29.WAVE2_CAPACITY = {"settledEpochSlots": 30, "fundedUnencumberedSlots": 0, "fundedUnencumberedUsdc": "0.00", "ringFencedUsdc": "40.05"}
CFG_AFTER = {"activeEpochSlots": 30, "activeEpochCapUsdc": "30.00", "settledEpochSlots": 30, "fundedUnencumberedSlots": 0,
             "fundedUnencumberedUsdc": "0.00", "ringFencedUsdc": "40.05",
             "ringFencedFor": ("Wave 3 ($40.05 USDC total unencumbered in the Base treasury: 2 x $20.00 USDC Wave 3 dossier slots + a $0.05 "
                               "reserve; Wave 1 Genesis 4/4 = $100.00 USDC is 100% settled on Base)")}
CFG_BEFORE_KEYS = {"activeEpochSlots": 25, "activeEpochCapUsdc": "25.00", **S29.WAVE2_BEFORE}
# verify_site_v2.py: the stamp-tool simulation's settled total of veriton-dev (Wave 1 slot 1 stamped in the simulation) gains Wave 2 PR
# #106 (paid); the Wave 2 archive checks themselves follow tools/bounty_wave2.json and bounties/leaderboard.json (25..30 settlements)
VERIFY_PAIRS = [('st_rows["veriton-dev"]["settled"] == 25_000_000 + BS.REWARD_ATOMIC and',
                 'st_rows["veriton-dev"]["settled"] == 25_000_000 + 2 * BS.REWARD_ATOMIC and')]


def wire_bounties(staged):
    """The Wave 2 closeout on the Wave 3 tree (9d75acb7: the Wave 2 master issue is a regenerated Completed & Retired archive, the
    Wave 3 files are not touched): bounties/leaderboard.json easAttestations += this Sprint's credits, wave2Credits gains them,
    wave2Settlements gains the 5 payouts (--wave2-payouts) -> 30; tools/bounty_wave2.json moves to CFG_AFTER (title unchanged);
    verify_site_v2.py follows VERIFY_PAIRS. Fails closed on any other starting state; a re-run is a no-op."""
    credits = staged.get("bounty_credits") or {}
    new = sorted(({"fixture": os.path.basename(c["fixture"]), "pr": c["pr"], "pactaSlug": slug, "record": c["record"]}
                  for slug, cs_ in credits.items() for c in cs_ if c.get("wave") == 2), key=lambda c: c["pr"])
    if sorted(c["pr"] for c in new) != sorted(S29.BOUNTY_PRS):
        A.fail(f"staged bounty credits {sorted(c['pr'] for c in new)} differ from the Sprint {SPRINT} PRs {S29.BOUNTY_PRS}", 1)
    lb = json.loads(A.read(A.LEADERBOARD))
    have_w2 = lb.get("wave2Credits") or []
    stamped = all(c in have_w2 for c in new)
    before = [c for c in have_w2 if c["pr"] not in S29.BOUNTY_PRS]
    if not stamped and len(before) != len(have_w2):
        A.fail("bounties/leaderboard.json wave2Credits already carries part of the Sprint 32 credits", 1)
    if not stamped:
        eas = dict(lb.get("easAttestations") or {})
        for c in (c for cs_ in credits.values() for c in cs_):
            eas[c["hunter"]] = eas.get(c["hunter"], 0) + 1
        lb["easAttestations"] = {h: eas[h] for h in sorted(eas)}
        lb["wave2Credits"] = sorted(before + new, key=lambda c: c["pr"])
    fix = {c["pr"]: c["fixture"] for c in new}
    have_s = {x["fixture"]: x for x in lb["wave2Settlements"]}
    for pr in S29.BOUNTY_PRS:
        f, tx = fix[pr], S29.PAYOUTS[pr]
        if f in have_s:
            if have_s[f]["payoutTxHash"] != tx:
                A.fail(f"wave2Settlements {f}: published payout {have_s[f]['payoutTxHash']} differs from --wave2-payouts {tx}", 1)
            continue
        lb["wave2Settlements"].append({"fixture": f, "payoutTxHash": tx})
    lb["wave2Settlements"].sort(key=lambda x: x["fixture"])
    if len(lb["wave2Settlements"]) != CFG_AFTER["settledEpochSlots"]:
        A.fail(f"{len(lb['wave2Settlements'])} wave2Settlements vs the {CFG_AFTER['settledEpochSlots']} settled Wave 2 slots", 1)
    A.write(A.LEADERBOARD, json.dumps(lb, indent=2, ensure_ascii=False) + "\n")
    p = os.path.join(HERE, "bounty_wave2.json")
    cfg = json.loads(A.read(p))
    cur = {k: cfg[k] for k in CFG_BEFORE_KEYS}
    if cur == CFG_BEFORE_KEYS:
        cfg.update(CFG_AFTER)
        A.write(p, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    elif {k: cfg[k] for k in CFG_AFTER} != CFG_AFTER:
        A.fail(f"tools/bounty_wave2.json {cur} is neither the pre-Sprint-32 state nor the stamped one", 1)
    v = os.path.join(A.ROOT, "verify_site_v2.py")
    s_ = A.read(v)
    for old, new_ in VERIFY_PAIRS:
        if s_.count(old) == 1:
            s_ = s_.replace(old, new_)
        elif s_.count(new_) != 1:
            A.fail(f"verify_site_v2.py: neither {old[:70]!r} nor its Sprint 32 form is present once", 1)
    A.write(v, s_)
    return lb["easAttestations"]


S29.wire_bounties = A.wire_bounties = wire_bounties
# build_lookup TOKENS gains a "Sprint 32 promotion" block only when the staging names new-protocol tokens (an empty block would not parse)
_add_tokens = A.add_tokens
A.add_tokens = lambda staged: _add_tokens(staged) if staged.get("tokens") else None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if A.TARGET is None:
        A.fail("TARGET is not set: run the staging (s32_stage.py + s26_emit.py --sprint 32) and write the TARGET block first")
    if S29.BOUNTY_PRS:
        return S29.main(argv)                      # --wave2-payouts required and checked there
    if "--wave2-payouts" in argv:
        A.fail("--wave2-payouts given, but Sprint 32 folds no Wave 2 PR (BOUNTY_PRS is empty)")
    return A.main(argv)


if __name__ == "__main__":
    sys.exit(main())
