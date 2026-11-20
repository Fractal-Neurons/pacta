# AGENT_SUMMARY.md

**UNCERTAIN: two independent stop conditions are met — (1) 21 open non-draft Wave 3 dossier PRs from 13 researchers are competing for only 2 funded slots (stop condition: "3+ open PRs already attempting this fix"), and (2) the dossier schema requires two researcher-owned inputs I cannot obtain — `base_payout_address` (an EIP-55 Base wallet that receives the $20 USDC) and the `contributor_github` attribution/attestation identity.**

No code changes were made. `bounties/wave-3/` is untouched; the working tree is clean apart from the pre-existing untracked `BOUNTY_TASK.md` and this file.

---

## What the issue actually asks for

Issue #118 is not a code defect. It is a **data submission** bounty: add exactly one new JSON file at `bounties/wave-3/<chain>-<slug>.json` containing a 3-part due-diligence dossier on a `>= $10M` TVL DeFi protocol — a 3-year on-chain control-plane timeline, dated docs/governance forensics with a computed MTTR, a 12-month repository audit, a `>= 400`-char executive risk memo, and a Pacta MCP tool receipt.

## Orientation performed

- Read `README.md`, `bounties/wave-3/README.md` (full schema + worked example), and `bounties/WAVE3-MASTER-ISSUE.md`.
- Read the authoritative spec: `tools/verify_bounty_submission.py:739-1100` (`validate_wave3`, `FIELDS_WAVE3`, `WAVE3_*` constants) and its config `tools/bounty_wave3.json`.
- Read the CI gate `.github/workflows/verify-bounty-pr.yml`: a bounty PR must change **exactly one added file** (mode `100644`, `<= 64 KiB`) matching `bounties/wave-3/<chain>-<slug>.json`, validated with the **base-branch** validator so no PR code executes.
- Tests: the repo's test for this path is the validator's built-in `--self-test` (invoked by `verify_site_v2.py`). **It passes**, confirming no pre-existing breakage:

  ```
  $ PYTHONUTF8=1 python tools/verify_bounty_submission.py --self-test
  self-test ok     # exit 0
  ```

  Note for anyone re-running on Windows: `PYTHONUTF8=1` is required. Without it the self-test dies in pre-existing repo tooling with `UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d` while reading a UTF-8 `index.json` under the cp1252 default locale. This is a latent, pre-existing environment issue unrelated to this task — I did not change it, as it is outside the one-file CI gate.
- Confirmed capability to do the research: live network access verified to DefiLlama (`api.llama.fi` → 200), the GitHub API (→ 200), Ethereum JSON-RPC (`eth_blockNumber` → `0x193af61`), and the keyless Pacta MCP server at `https://pacta-x402.pacta.workers.dev/mcp` (`initialize` returned `pacta-mcp-remote` v0.2.0, 6 read-only tools). The MCP host named in `bounties/wave-3/README.md`, `https://mcp.pacta.wtf/mcp`, does **not** resolve (curl exit 6) — the working endpoint is the `pacta-x402.pacta.workers.dev` one from the issue body.

## Stop condition 1 — high competition (the decisive one)

| Measure | Value |
| --- | --- |
| Funded Wave 3 slots | **2** (`$40.00 USDC` total) |
| Open non-draft Wave 3 dossier PRs | **21** |
| Distinct competing researchers | **13** |
| Wave 3 dossiers merged so far | **0** (upstream `bounties/wave-3/` contains only `README.md`) |

Queried via the GitHub search API against `Fractal-Neurons/pacta`. The task's threshold is 3; the actual queue exceeds it sevenfold. Each PR targets a different protocol, so a new dossier would not be *technically* duplicative — but 21 submissions chasing 2 slots is precisely the "high competition" the stop condition is written to catch.

## Stop condition 2 — required inputs I cannot determine

Two schema fields are irreducibly the researcher's own identity and cannot be derived from the repo:

- **`base_payout_address`** — `validate_wave3` requires a mixed-case **EIP-55 checksummed** address that is not the zero address, not a precompile, not `contract_address`, and not the Pacta treasury. This is the wallet that receives the `$20.00 USDC`. A placeholder fails the EIP-55 checksum; any checksum-valid address I invented would either be unspendable or **direct real funds to a stranger's wallet**. I searched the repo, the full `bounties/` git history, `bounties/leaderboard.json`, and agent memory — no address is on record for this user.
- **`contributor_github`** — plausibly `tlv1231-py` from the `origin` fork URL, but this is the handle that signs `rules_accepted: [true, true, true, true]` and earns a permanent on-chain Base EAS researcher credential. Guessing an attestation identity is not mine to do.

Beyond validation, `rules_accepted` attests that *"every block height, transaction hash, cast/RPC output, and 12-month repo audit metric in this dossier is real and reproducible"*, and Wave 3 is scoped to **human-researcher** slots. That attestation, and the payout it is bound to, are the user's to sign. (The schema does contemplate agent assistance via the optional `agent_assist_framework: "claude-code"` disclosure field, so this is a point about who signs — not a claim that agent help is disallowed.)

## A real blocker found during feasibility checks

Part 1 proofs of the form `cast storage <addr> <slot> --block <N>` require an **archive** node. The obvious free endpoint rejects them:

```
$ curl -s -X POST --data '{"jsonrpc":"2.0","id":1,"method":"eth_getStorageAt",
    "params":["0xdAC17F958D2ee523a2206206994597C13D831ec7","0x0","0x10FB0A0"]}' \
    https://ethereum-rpc.publicnode.com
{"error":{"code":-32602,"message":"Archive requests require a personal token..."}}
```

This is surmountable — `cast receipt`, `cast tx`, and `cast logs` proofs need no archive state, and other keyless archive providers exist — so it is **not** on its own a reason to stop. Recording it because it shapes how Part 1 must be evidenced.

## Verification

- `PYTHONUTF8=1 python tools/verify_bounty_submission.py --self-test` → `self-test ok`, exit 0 (unchanged from the starting state).
- `git status --short` → only `?? BOUNTY_TASK.md` (pre-existing) and `?? AGENT_SUMMARY.md`.
- `git diff HEAD` → empty. No tracked file was modified.

## What a reviewer should know / how to proceed

The work is feasible and I got as far as confirming every external dependency is reachable. To finish it, I need two things from you:

1. Your **EIP-55 checksummed Base payout address**.
2. Confirmation of your **GitHub handle** (`tlv1231-py`?) and that you are willing to sign the Wave 3 researcher attestation.

Given 21 PRs against 2 slots and 0 merges, I'd also flag that the expected return here is low — roughly a 1-in-10 shot at $20 for a full multi-protocol forensic dossier. If you want it anyway, say the word and supply the two inputs; I'll pick an uncovered `rpc_observed` target from `docs/api/v1/protocols.json`, reconstruct the timeline against live RPC, pull the repo metrics from the GitHub API, capture a real MCP receipt, and validate locally before committing. Worth noting that the 21 competing PRs already claim protocols including Sushi V2, GMX, Harvest Finance, Derive V3, World Chain Bridge, Origami, NodeDAO, Aera V3, ankrETH, 3F, AUTOfinance, team-finance, Concentrator, wildcat-protocol, Frankencoin, USDT0, Fraxtal Bridge, and PancakeSwap V3 — a target would need to avoid those.
