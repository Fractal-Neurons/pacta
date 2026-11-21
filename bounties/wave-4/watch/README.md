# Wave 4 — $2.00 USDC Control-Plane Watch Bounty (10 Open Awards on Base)

**Pool:** **10 awards of $2.00 USDC** on Base (`$20.00 USDC` held on-chain in Pacta's bounty wallet `0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09`). **Closes when all 10 awards are won, or on Sunday 29 November 2026 at 23:59 UTC, whichever comes first.** Any un-won Watch awards remaining at `29 November 2026, 23:59 UTC` roll over into extra `$1.00 USDC` Observed Catalogue slots (`2` Catalogue slots per un-won `$2.00` Watch award).

## Read First — Key Safety, Paid Call & Payout
- **Key safety:** Use a fresh wallet holding only cents, never your main wallet. Our helper script (`tools/pacta_x402_call.py`) runs its cryptographic self-test on every run, reads your key on your own machine, and never sends or prints it. Pacta will never ask for a private key or seed phrase.
- **One $0.02 paid call per entry:** Every entry needs one paid x402 `verdict` call of **$0.02 USDC** on Base to **`POST https://api.pacta.wtf/v1/x402/verdict`** (`https://pacta.fractalneurons.com` is the second official host; our checker verifies the payment on-chain). Payment goes to Pacta's treasury wallet **`0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`** on Base and must come **from the same Base wallet address that will receive your $2.00 USDC award**.
- **The $0.02 is not returned:** Your 2 cents pay for the API call and are never returned, even if someone else wins that event first or your entry fails our check. If the call returns an error or times out, check your wallet on BaseScan before retrying: if 2 cents already left your wallet to `0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`, do not pay again — that Base transaction hash is valid for your entry and our checker accepts it.
- **Getting 2 cents of USDC on Base:** If your fresh wallet has no USDC on Base, withdraw a small amount of USDC on the Base network from an exchange that supports Base (fees vary by exchange), or swap a few cents of Base ETH into Base USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`). Signing the x402 payment itself needs zero Base ETH gas.
- **Payout within 48 hours:** Each winning entry is paid **$2.00 USDC on Base** within **48 hours** after our check passes and the Pull Request merges.

## What Counts as a Qualifying On-Chain Change
Report a real on-chain control-plane change on any of the **567 watched contracts and controllers** in `bounties/wave-4/watched-addresses.json` (**Ethereum `chainId: 1` and Base `chainId: 8453` only**):
1. Happened in a finalized block **strictly after** that address's `pinned_block_number` in `bounties/wave-4/watched-addresses.json` — **any qualifying change after that address's pinned block that we have not yet published counts, not only changes from today**, **and**
2. Is **not already published** on the human Radar page (`https://pacta.wtf/radar/`) or in `https://pacta.wtf/api/v1/radar.json` or `https://pacta.wtf/api/v1/index.json` before your commit timestamp, **and**
3. Changes one of these four control-plane surfaces on the watched address:
   - **Proxy implementation upgrade** (EIP-1967 / Beacon / Diamond cut changing live implementation logic),
   - **Ownership or admin transfer** (`owner()`, `admin()`, `pendingAdmin`, or `DEFAULT_ADMIN_ROLE` / guardian role grant or revoke),
   - **Safe signer or threshold change** (`AddedOwner`, `RemovedOwner`, or `ChangedThreshold` on a watched Safe), or
   - **Timelock delay change or newly queued admin/upgrade operation** (`MinDelayChange` / `NewDelay`, or a newly scheduled `CallScheduled` / `QueueTransaction` targeting a watched contract).

Routine user deposits, swaps, borrows, reward distributions, or oracle price ticks do **not** qualify.

## Check Whether Someone Already Reported That Transaction Before Paying 2 Cents
Each unique on-chain change transaction (`event_tx_hash`) can win **at most one award**. Before running the `$0.02` call, take the first 8 hex characters after `0x` of `event_tx_hash` (`<tx8>`, lowercase, e.g. `1a2b3c4d`) and check open and merged Pull Requests:
```bash
gh pr list --repo Fractal-Neurons/pacta --state all --search "Wave 4 watch: <protocol_slug> 0x<tx8> in:title"
```
`tools/pacta_x402_call.py` is already published in this repository and follows the exact same steps as the Catalogue track (`--route verdict --chain <ethereum|base> --address <0xWatchedAddress>`).

## Fair-Play Rules
1. **Required Pull Request title:** Your Pull Request title must be **`Wave 4 watch: <protocol_slug> 0x<tx8>`**, where `<protocol_slug>` is taken verbatim from `bounties/wave-4/watched-addresses.json` — Pull Requests without that exact title fail our check.
2. **One award per `event_tx_hash`:** Won by **the timestamp of the first commit that passes every check**.
3. **One open Pull Request at a time** per GitHub account across Wave 4.
4. **At most 3 Watch awards** per GitHub account and per wallet cluster. Exchange withdrawal wallets do not link accounts; a cluster means entries using the same payout address or wallets that fund or transfer between each other.
5. **Account age:** Your GitHub account must be at least **6 months old** (created on or before `2026-05-21`).
6. **Pacta's own team and accounts cannot enter.**
7. **GitHub (`Fractal-Neurons/pacta`) only:** Never open issues, PRs, or comments in any third-party protocol repository.
8. **Right to refuse:** We refuse entries that break these rules and state why on the Pull Request.

## What to Submit
Open a Pull Request titled `Wave 4 watch: <protocol_slug> 0x<tx8>` adding one file at `bounties/wave-4/watch/<protocol_slug>-0x<tx8>.json` with:
- `protocol_slug`, `chain` (`"ethereum"` or `"base"`), and `watched_address` (checksummed EIP-55, from `watched-addresses.json`).
- `prior_pinned_block` (from `watched-addresses.json`), `event_block_number` (`> prior_pinned_block`, finalized), `event_block_hash`, and `event_tx_hash` (`0x` + 64 hex chars).
- `change_kind` (`"implementation_upgrade"`, `"admin_or_role_change"`, `"safe_signer_or_threshold_change"`, or `"timelock_delay_or_queued_op"`), `before_state`, and `after_state` (plain factual values only). We do not publish ratings of protocols, and nobody can pay to change a result.
- `payment_tx_hash` (settled Base USDC transaction from your `$0.02` `/v1/x402/verdict` call, unique to this entry).
- `contributor_github` and your checksummed 42-character `base_payout_address` (must match the payer of `payment_tx_hash`).

## Confirm Your Payout Address on GitHub
After opening your Pull Request, leave one comment from the same GitHub account:
`Payout address confirmed: 0xYourExact42CharacterAddress`
We verify all 42 characters against your PR file and your on-chain payment, and never read addresses from wallet history. Accepted Watch entries update `pacta.wtf` at the next site update.

---

## Watched Address List & Paid-Call Helper

- **Watched Address Manifest (567 entries: 501 Ethereum, 66 Base):** [`bounties/wave-4/watched-addresses.json`](https://github.com/Fractal-Neurons/pacta/blob/main/bounties/wave-4/watched-addresses.json)
- **Local `$0.02` EIP-3009 Paid-Call Helper (stdlib Python 3, self-tested on every run):** [`tools/pacta_x402_call.py`](https://github.com/Fractal-Neurons/pacta/blob/main/tools/pacta_x402_call.py)
  - **Verify helper SHA-256 before passing a key:** `eb873d21fc64b2c9f3f8f9b8eb057afcbf0e1f89aeb3477aea9b8e68120ab2cf` (`echo "eb873d21fc64b2c9f3f8f9b8eb057afcbf0e1f89aeb3477aea9b8e68120ab2cf  tools/pacta_x402_call.py" | sha256sum -c -`) (step-by-step instructions: [`bounties/wave-4/catalogue/README.md`](https://github.com/Fractal-Neurons/pacta/blob/main/bounties/wave-4/catalogue/README.md#how-to-make-the-002-paid-call-under-5-minutes-key-stays-local))

### Submission JSON Schema (`bounties/wave-4/watch/<protocol_slug>-0x<tx8>.json`)

```json
{
  "protocol_slug": "morpho-blue-core",
  "chain": "ethereum",
  "watched_address": "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb",
  "prior_pinned_block": 26425374,
  "event_block_number": 26465000,
  "event_block_hash": "0x1111111111111111111111111111111111111111111111111111111111111111",
  "event_tx_hash": "0x1a2b3c4d55555555555555555555555555555555555555555555555555555555",
  "change_kind": "admin_or_role_change",
  "before_state": "owner() = 0xcBa28b38103307Ec8dA98377ffF9816C164f9AFa",
  "after_state": "owner() = 0x2222222222222222222222222222222222222222",
  "payment_tx_hash": "0x4444444444444444444444444444444444444444444444444444444444444444",
  "contributor_github": "your-github-handle",
  "base_payout_address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
}
```
