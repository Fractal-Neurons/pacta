# Wave 4 — $2.00 USDC Documents Changed Bounty (5 Open Awards on Base)

**Pool:** **5 awards of $2.00 USDC** on Base (`$10.00 USDC` held on-chain in Pacta's bounty wallet `0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09`). **Closes when all 5 awards are won, or on Sunday 29 November 2026 at 23:59 UTC, whichever comes first.** Any un-won Documents Changed awards remaining at `29 November 2026, 23:59 UTC` roll over into extra `$1.00 USDC` Observed Catalogue slots (`2` Catalogue slots per un-won `$2.00` award).

## Read First — Key Safety, Paid Call & Payout
- **Key safety:** Use a fresh wallet holding only cents, never your main wallet. Our helper script (`tools/pacta_x402_call.py`) runs its cryptographic self-test on every run, reads your key on your own machine, and never sends or prints it. Pacta will never ask for a private key or seed phrase.
- **One $0.05 paid call per entry:** Every entry needs one paid x402 `dossier` call of **$0.05 USDC** on Base to **`POST https://api.pacta.wtf/v1/x402/dossier`** (`https://pacta.fractalneurons.com` is the second official host; our checker verifies the payment on-chain). Payment goes to Pacta's treasury wallet **`0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`** on Base and must come **from the same Base wallet address that will receive your $2.00 USDC award**.
- **The $0.05 is not returned:** Your 5 cents pay for the API call and are never returned, even if someone else wins that protocol first or your entry fails our check. If the call returns an error or times out, check your wallet on BaseScan before retrying: if 5 cents already left your wallet to `0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`, do not pay again — that Base transaction hash is valid for your entry and our checker accepts it.
- **Getting 5 cents of USDC on Base:** If your fresh wallet has no USDC on Base, withdraw a small amount of USDC on the Base network from an exchange that supports Base (fees vary by exchange), or swap a few cents of Base ETH into Base USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`). Signing the x402 payment itself needs zero Base ETH gas.
- **Payout within 48 hours:** Each entry is pre-checked by script and **checked by a second reviewer** before merge; winning entries are paid **$2.00 USDC on Base** within **48 hours** of merge (not an instant automated payout).

## What Counts as a Qualifying Documentation Change
**A documentation change is not a fault. Many are improvements. We record what changed, we do not judge it.**

Pick any of the **160 reviewed protocols** in `bounties/wave-4/docs-changed-protocols.json` (**Ethereum `chainId: 1` and Base `chainId: 8453` only**; human pages at `https://pacta.wtf/scorecards/` and `https://pacta.wtf/protocols/<protocol_slug>/`). Show that the protocol's **current official public documentation** (its official documentation site or official GitHub documentation repository) **materially changed a specific control-plane commitment** compared with the `retained_documented_reference` in `bounties/wave-4/docs-changed-protocols.json`:
1. The change alters a **timelock delay**, **multisig signer count or threshold**, **upgrade or proxy-admin authority**, or **pause, guardian, or blacklist authority** on a recorded surface, **and**
2. The updated documentation is **live (`HTTP 200`)** at the official URL at review time and has **not already been published** on `https://pacta.wtf/protocols/<protocol_slug>/` or in `https://pacta.wtf/api/v1/index.json` before your commit timestamp. *(Any unpublished change since Pacta's retained documentation quote counts, not only edits made today.)*

Cosmetic rewrites, typo fixes, APR/fee marketing copy, or third-party blog posts and forum comments do **not** qualify.

## Check Whether a Protocol Already Has an Entry Before Paying 5 Cents
Each `<protocol_slug>` in `bounties/wave-4/docs-changed-protocols.json` can win **at most one award** in this track. Before running the `$0.05` call, check open and merged Pull Requests:
```bash
gh pr list --repo Fractal-Neurons/pacta --state all --search "Wave 4 docs-changed: <protocol_slug> in:title"
```
Then run `tools/pacta_x402_call.py` with `--route dossier --slug <protocol_slug>` (`--dry-run` first to confirm `endpoint` is `https://api.pacta.wtf/v1/x402/dossier`, `pay_to` is `0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`, and `amount_usd` is `"0.05"`).

## Fair-Play Rules
1. **Required Pull Request title:** Your Pull Request title must be **`Wave 4 docs-changed: <protocol_slug>`**, where `<protocol_slug>` is taken verbatim from `bounties/wave-4/docs-changed-protocols.json` — Pull Requests without that exact title fail our check.
2. **One award per `<protocol_slug>`:** Won by **the timestamp of the first commit that passes every check**.
3. **One open Pull Request at a time** per GitHub account across Wave 4.
4. **At most 3 Documents Changed awards** per GitHub account and per wallet cluster. Exchange withdrawal wallets do not link accounts; a cluster means entries using the same payout address or wallets that fund or transfer between each other.
5. **Account age:** Your GitHub account must be at least **6 months old** (created on or before `2026-05-21`).
6. **Pacta's own team and accounts cannot enter.**
7. **GitHub (`Fractal-Neurons/pacta`) only:** Never open issues, PRs, or comments in any third-party protocol repository.
8. **Right to refuse:** We refuse entries that break these rules and state why on the Pull Request.

## What to Submit
Open a Pull Request titled `Wave 4 docs-changed: <protocol_slug>` adding one file at `bounties/wave-4/docs-changed/<protocol_slug>.json` with:
- `protocol_slug` and `chain` (`"ethereum"` or `"base"`, from `docs-changed-protocols.json`).
- `surface` and `prior_documented_reference` (copied from the matching record in `docs-changed-protocols.json`).
- `current_official_docs_url` (`https://` official documentation page or official GitHub commit/blob URL returning `HTTP 200`), `current_verbatim_quote` (`<= 400` characters verbatim from that page), and `what_changed` (one plain, neutral factual sentence naming the old vs. new control-plane commitment). We do not publish ratings of protocols, and nobody can pay to change a result.
- `archive_url` *(optional, recommended)*: an archived copy of the page (`https://web.archive.org/...` link) is recommended and speeds our check, because documentation pages can change again before we look.
- `payment_tx_hash` (settled Base USDC transaction from your `$0.05` `/v1/x402/dossier` call, unique to this entry).
- `contributor_github` and your checksummed 42-character `base_payout_address` (must match the payer of `payment_tx_hash`).

## Confirm Your Payout Address on GitHub
After opening your Pull Request, leave one comment from the same GitHub account:
`Payout address confirmed: 0xYourExact42CharacterAddress`
We verify all 42 characters against your PR file and your on-chain payment, and never read addresses from wallet history. Accepted entries update `pacta.wtf` at the next site update.

---

## Reviewed Protocol List & Paid-Call Helper

- **Reviewed Protocols & Retained Quotes (160 protocols, 246 quoted records — Ethereum & Base):** [`bounties/wave-4/docs-changed-protocols.json`](https://github.com/Fractal-Neurons/pacta/blob/main/bounties/wave-4/docs-changed-protocols.json)
- **Local `$0.05` EIP-3009 Paid-Call Helper (`--route dossier`, stdlib Python 3, self-tested on every run):** [`tools/pacta_x402_call.py`](https://github.com/Fractal-Neurons/pacta/blob/main/tools/pacta_x402_call.py)
  - **Verify helper SHA-256 before passing a key:** `eb873d21fc64b2c9f3f8f9b8eb057afcbf0e1f89aeb3477aea9b8e68120ab2cf` (`echo "eb873d21fc64b2c9f3f8f9b8eb057afcbf0e1f89aeb3477aea9b8e68120ab2cf  tools/pacta_x402_call.py" | sha256sum -c -`)

### Quick Paid-Call Command (`$0.05` `/v1/x402/dossier`)

```bash
# Dry-run first ($0.00 spent):
python3 tools/pacta_x402_call.py --key-file ./fresh-hunter-key.txt --route dossier --slug <protocol_slug> --dry-run

# Execute $0.05 call and save receipt.json:
python3 tools/pacta_x402_call.py --key-file ./fresh-hunter-key.txt --route dossier --slug <protocol_slug> --out receipt.json
```

### Submission JSON Schema (`bounties/wave-4/docs-changed/<protocol_slug>.json`)

```json
{
  "protocol_slug": "beefy-finance-base",
  "chain": "base",
  "surface": "BeefyStrategyOwnerTimelock_Base",
  "prior_documented_reference": "docs.beefy.finance (contracts and timelocks): 'By default, a 6-hour timelock is configured for all strategy changes'",
  "current_official_docs_url": "https://docs.beefy.finance/safu-protocol/contracts-and-timelocks",
  "current_verbatim_quote": "Exact updated sentence from the current official documentation page (<= 400 chars)",
  "what_changed": "Official documentation updated strategy timelock description from X to Y.",
  "archive_url": "https://web.archive.org/web/20261121000000/https://docs.beefy.finance/safu-protocol/contracts-and-timelocks",
  "payment_tx_hash": "0x4444444444444444444444444444444444444444444444444444444444444444",
  "contributor_github": "your-github-handle",
  "base_payout_address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
}
```
