# Wave 4 — $1.00 USDC Observed Catalogue Bounty

**Pool:** **24 awards of $1.00 USDC** on Base (`$24.00 USDC` held on-chain in Pacta's bounty wallet `0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09`). More slots may be added and will be announced on this issue. **Closes when all open slots are filled, or on Sunday 29 November 2026 at 23:59 UTC, whichever comes first.**

## Read First — Key Safety, Paid Call & Payout
- **Key safety:** Use a fresh wallet holding only cents, never your main wallet. Our helper script reads your key on your own machine and never sends or prints it. Pacta will never ask for a private key or seed phrase.
- **One $0.02 paid call per entry:** Every entry needs one paid x402 `verdict` call of **$0.02 USDC** on Base to **`POST https://api.pacta.wtf/v1/x402/verdict`** (`https://pacta.fractalneurons.com` is the second official host; our checker verifies the payment on-chain). Payment goes to Pacta's treasury wallet **`0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`** on Base and must come **from the same Base wallet address that will receive your $1.00 USDC award**.
- **The $0.02 is not returned:** Your 2 cents pay for the API call and are never returned, even if someone else wins the slot first or your entry fails our check. **If the script ends with HTTP 503 and the answer says settled: true, your payment went through. Do not run it again. Use that transaction.** If the call returns any other error or times out, check your wallet on BaseScan before retrying: if 2 cents already left your wallet to `0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`, do not pay again — that Base transaction hash is valid for your entry and our checker accepts it.
- **Getting 2 cents of USDC on Base:** If your fresh wallet has no USDC on Base, withdraw a small amount of USDC on the Base network from an exchange that supports Base (fees vary by exchange), or swap a few cents of Base ETH into Base USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`). Signing the x402 payment itself needs zero Base ETH gas.
- **Payout within 48 hours:** Each winning entry is paid **$1.00 USDC on Base** within **48 hours** after our check passes and the Pull Request merges.

## Check That a Slot Is Free Before Paying 2 Cents
Only targets on the **closed Target List** below are eligible (**Ethereum and Base only**). Before making the paid call, check that `<slot_id>` has no merged file and no open Pull Request:
- Click the live PR search link next to `<slot_id>` in the target table, or run:
  ```bash
  gh pr list --repo Fractal-Neurons/pacta --state all --search "Wave 4 catalogue: <slot_id> in:title"
  ```
- Our local helper script checks whether `bounties/wave-4/catalogue/<slot_id>.json` is already merged and checks the first 100 open Pull Requests for `<slot_id>` in the title or branch before signing.

## Fair-Play Rules
1. **Required Pull Request title:** Your Pull Request title must be **`Wave 4 catalogue: <slot_id>`** — Pull Requests without that exact title fail our check.
2. **One award per slot:** Won by **the timestamp of the first commit that passes every check**.
3. **One open Pull Request at a time** per GitHub account across Wave 4.
4. **At most 3 awards** per GitHub account and per wallet cluster. Exchange withdrawal wallets do not link accounts; a cluster means entries using the same payout address or wallets that fund or transfer between each other.
5. **Account age:** Your GitHub account must be at least **6 months old** (created on or before `2026-05-21`).
6. **Payer must be the payout address:** The wallet that pays the x402 call must be the exact same `base_payout_address` that receives the award; pasting another wallet's payment transaction fails our check.
7. **Pacta's own team and accounts cannot enter.**
8. **GitHub (`Fractal-Neurons/pacta`) only:** Never open issues, PRs, or comments in any third-party protocol repository.
9. **Right to refuse:** We refuse entries that break these rules and state why on the Pull Request.

## What to Submit (Observed facts only)
We do not publish ratings of protocols, and nobody can pay to change a result. Entries record **pinned on-chain facts only**: no letter grade is accepted or published, and no claims about protocol documentation belong in this track. Accepted entries appear on `pacta.wtf` as **Observed** at the next site update.

Open a Pull Request titled `Wave 4 catalogue: <slot_id>` adding one file at `bounties/wave-4/catalogue/<slot_id>.json` with:
- `slot_id`, `chain` (`"ethereum"` or `"base"`), `protocol_name`, `contract_address`, and `official_source_url` from the closed list.
- `pinned_block_number` and `pinned_block_hash` for a finalized block.
- `observed_control_plane`: `is_proxy`, `implementation_address`, `controller_kind`, `controller_address`, plus `safe_threshold` and `safe_owners_count` if a Safe, or `timelock_min_delay_seconds` if a timelock.
- `payment_tx_hash`: the settled Base USDC transaction hash from your `$0.02` x402 `verdict` call (one entry per transaction).
- `contributor_github` and your checksummed 42-character `base_payout_address` (must match the payer of `payment_tx_hash`).

## Confirm Your Payout Address on GitHub
After opening your Pull Request, leave one comment from the same GitHub account:
`Payout address confirmed: 0xYourExact42CharacterAddress`
We verify all 42 characters against your PR file and your on-chain payment, and never read addresses from wallet history.

---

## Batch 1 Closed Target List (12 Open Slots — Ethereum & Base)

Batch 1 opens **12 slots** (`9` on Ethereum, `3` on Base; `$22.8M`–`$3,385.0M` TVL). Remaining slots from the 24-slot pool open in Batch 2 as Batch 1 slots fill.

| # | `slot_id` | Chain | Protocol & Surface | Target Contract (`EIP-55`) | TVL (Approx.) | Official Source URL | Check Open PRs Before Paying |
|---|---|---|---|---|---|---|---|
| 1 | `base-morpho-blue-singleton` | `base` | Morpho Blue on Base (Morpho Singleton) | `0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb` | $3,385.0M | [Official Docs/Repo](https://docs.morpho.org/addresses/) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+base-morpho-blue-singleton) |
| 2 | `ethereum-arbitrum-delayed-bridge` | `ethereum` | Arbitrum One Canonical Bridge (Delayed Bridge) | `0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a` | $2,776.7M | [Official Docs/Repo](https://docs.arbitrum.io/build-decentralized-apps/reference/contract-addresses) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+ethereum-arbitrum-delayed-bridge) |
| 3 | `ethereum-op-mainnet-portal` | `ethereum` | OP Mainnet Canonical Bridge (OptimismPortalProxy) | `0xbEb5Fc579115071764c7423A4f12eDde41f106Ed` | $750.6M | [Official Docs/Repo](https://raw.githubusercontent.com/ethereum-optimism/superchain-registry/main/superchain/configs/mainnet/op.toml) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+ethereum-op-mainnet-portal) |
| 4 | `ethereum-mantle-l1-bridge` | `ethereum` | Mantle Canonical Bridge (L1StandardBridge) | `0x95fC37A27a2f68e3A647CDc081F0A89bb47c3012` | $316.6M | [Official Docs/Repo](https://raw.githubusercontent.com/mantlenetworkio/networks/main/mainnet/addresses.json) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+ethereum-mantle-l1-bridge) |
| 5 | `base-uniswap-v3-factory` | `base` | Uniswap V3 on Base (UniswapV3Factory) | `0x33128a8fC17869897dcE68Ed026d694621f6FDfD` | $251.0M | [Official Docs/Repo](https://docs.uniswap.org/contracts/v3/reference/deployments/base-deployments) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+base-uniswap-v3-factory) |
| 6 | `ethereum-compound-v2-unitroller` | `ethereum` | Compound V2 (Unitroller / Comptroller) | `0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B` | $77.0M | [Official Docs/Repo](https://raw.githubusercontent.com/compound-finance/compound-protocol/master/networks/mainnet.json) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+ethereum-compound-v2-unitroller) |
| 7 | `base-uniswap-v2-factory` | `base` | Uniswap V2 on Base (UniswapV2Factory) | `0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6` | $56.6M | [Official Docs/Repo](https://docs.uniswap.org/contracts/v2/reference/smart-contracts/v2-deployments) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+base-uniswap-v2-factory) |
| 8 | `ethereum-linea-rollup` | `ethereum` | Linea Canonical Bridge (LineaRollup) | `0xd19d4B5d358258f05D7B411E21A1460D11B0876F` | $43.6M | [Official Docs/Repo](https://raw.githubusercontent.com/Consensys/doc.linea/main/docs/network/build/contracts.mdx) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+ethereum-linea-rollup) |
| 9 | `ethereum-ink-optimism-portal` | `ethereum` | Ink Canonical Bridge (OptimismPortalProxy) | `0x5d66C1782664115999C47c9fA5cd031f495D3e4F` | $39.3M | [Official Docs/Repo](https://raw.githubusercontent.com/ethereum-optimism/superchain-registry/main/superchain/configs/mainnet/ink.toml) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+ethereum-ink-optimism-portal) |
| 10 | `ethereum-unichain-optimism-portal` | `ethereum` | Unichain Canonical Bridge (OptimismPortalProxy) | `0x0bd48f6B86a26D3a217d0Fa6FfE2B491B956A7a2` | $33.1M | [Official Docs/Repo](https://raw.githubusercontent.com/ethereum-optimism/superchain-registry/main/superchain/configs/mainnet/unichain.toml) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+ethereum-unichain-optimism-portal) |
| 11 | `ethereum-scroll-l1-messenger` | `ethereum` | Scroll Canonical Bridge (L1ScrollMessengerProxy) | `0x6774Bcbd5ceCeF1336b5300fb5186a12DDD8b367` | $24.2M | [Official Docs/Repo](https://docs.scroll.io/en/developers/scroll-contracts/) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+ethereum-scroll-l1-messenger) |
| 12 | `ethereum-sui-bridge` | `ethereum` | Sui Canonical Bridge (SuiBridge) | `0xda3bD1fE1973470312db04551B65f401Bc8a92fD` | $22.8M | [Official Docs/Repo](https://docs.sui.io/concepts/tokenomics/sui-bridging) | [Check PRs](https://github.com/Fractal-Neurons/pacta/pulls?q=in%3Atitle+ethereum-sui-bridge) |

*TVL figures are approximate chain TVLs sourced from DeFiLlama (`https://api.llama.fi/protocols`) on 21 November 2026.*

---

## How to Make the $0.02 Paid Call (Under 5 Minutes, Key Stays Local)

Every Wave 4 **$1.00 USDC Observed Catalogue** entry requires one **$0.02 USDC** (`20,000` atomic units on Base) x402 call to **`POST https://api.pacta.wtf/v1/x402/verdict`** (`https://pacta.fractalneurons.com` is the second official Pacta host), paying Pacta's treasury wallet **`0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`** on Base from the same wallet address (`base_payout_address`) that will receive your `$1.00 USDC` award.

Our helper script (`pacta_x402_call.py`) uses **only standard-library Python 3** (zero `pip install` or `npm install` packages). On every run it verifies its built-in cryptographic self-test before doing anything else, checks GitHub **before** signing, reads your key strictly from a local `0600` file, and never prints or sends your private key.

---

## Step 1 — Start in a Clean Folder and Verify `--self-test`
Requires `python3` (`>= 3.10`):
```bash
mkdir pacta-catalogue-run && cd pacta-catalogue-run
curl -fsSLO https://raw.githubusercontent.com/Fractal-Neurons/pacta/main/tools/pacta_x402_call.py
echo "eb873d21fc64b2c9f3f8f9b8eb057afcbf0e1f89aeb3477aea9b8e68120ab2cf  pacta_x402_call.py" | sha256sum -c -   # macOS: shasum -a 256 -c -
python3 pacta_x402_call.py --self-test
```
Read `pacta_x402_call.py` before running it with a key, and verify `--self-test` prints `"self_test": "PASS"`.

## Step 2 — Create a Fresh Cents-Only Wallet Locally
Never use your main wallet. Generate a fresh `0600` key file on your own machine:
```bash
python3 pacta_x402_call.py --generate-wallet ./fresh-hunter-key.txt
```
This creates `./fresh-hunter-key.txt` (readable only by your OS user) and prints **only** your public `base_payout_address` (`0x...`).
Fund that `base_payout_address` with at least **$0.02 USDC on Base** (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`, chainId `8453`). You need **zero Base ETH** for the x402 call itself because EIP-3009 signing is gasless.

## Step 3 — Dry-Run & Check That Your Slot Is Free ($0.00 Spent)
Pick an open `<slot_id>`, `<chain>` (`ethereum` or `base`), and `<contract_address>` from the closed Target List, then run `--dry-run`:
```bash
python3 pacta_x402_call.py \
  --key-file ./fresh-hunter-key.txt \
  --route verdict \
  --slot <slot_id> \
  --chain <ethereum|base> \
  --address <0xTargetContractAddress> \
  --dry-run
```
Verify that:
- `[precheck]` confirms `bounties/wave-4/catalogue/<slot_id>.json` is not merged on `main` and `<slot_id>` does not appear in the title or branch of the first 100 open Pull Requests on `Fractal-Neurons/pacta` *(every valid Pull Request is required to be titled `Wave 4 catalogue: <slot_id>`)*,
- `endpoint` is `https://api.pacta.wtf/v1/x402/verdict`,
- `pay_to` is `0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`, and
- `amount_usd` is `"0.02"`.

## Step 4 — Execute the $0.02 Paid Call and Save Your Receipt
Remove `--dry-run` and save the output to `receipt.json`:
```bash
python3 pacta_x402_call.py \
  --key-file ./fresh-hunter-key.txt \
  --route verdict \
  --slot <slot_id> \
  --chain <ethereum|base> \
  --address <0xTargetContractAddress> \
  --out receipt.json
```
- **If the script ends with HTTP 503 and the answer says settled: true, your payment went through. Do not run it again. Use that transaction.**
- **If the call returns any other error or times out after signing:** Before retrying, check your wallet's Token Transfers on BaseScan (`https://basescan.org/address/<your_address>#tokentxns`). If **$0.02 USDC** already left your wallet to `0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14`, **do not pay again** — that Base transaction hash is valid for your entry and our checker accepts it.
- On `HTTP 200`, `receipt.json` contains `payment_tx_hash` (`0x...` settled Base USDC transaction) and `observed_response` (`block`, `capabilities`, `controllerSummary`).

Open your Pull Request titled **`Wave 4 catalogue: <slot_id>`** adding `bounties/wave-4/catalogue/<slot_id>.json`, and leave your confirmation comment:
`Payout address confirmed: 0xYourExact42CharacterAddress`

---

## Submission JSON Schema (`bounties/wave-4/catalogue/<slot_id>.json`)

```json
{
  "slot_id": "ethereum-arbitrum-delayed-bridge",
  "chain": "ethereum",
  "protocol_name": "Arbitrum One Canonical Bridge (Delayed Bridge)",
  "contract_address": "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a",
  "official_source_url": "https://docs.arbitrum.io/build-decentralized-apps/reference/contract-addresses",
  "pinned_block_number": 23849500,
  "pinned_block_hash": "0x1111111111111111111111111111111111111111111111111111111111111111",
  "observed_control_plane": {
    "is_proxy": true,
    "implementation_address": "0x2222222222222222222222222222222222222222",
    "controller_kind": "timelock",
    "controller_address": "0x3333333333333333333333333333333333333333",
    "safe_threshold": null,
    "safe_owners_count": null,
    "timelock_min_delay_seconds": 259200
  },
  "payment_tx_hash": "0x4444444444444444444444444444444444444444444444444444444444444444",
  "contributor_github": "your-github-handle",
  "base_payout_address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
}
```
