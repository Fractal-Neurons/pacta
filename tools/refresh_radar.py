"""Refresh docs/api/v1/radar.json: live state of the queued timelock operations shown on the homepage radar.

Read-only JSON-RPC (stdlib only). Each chain is pinned to its current *finalized* block and every read is cross-checked on two
independent RPC endpoints; any disagreement aborts. Ethereum Mainnet items (chain_id 1) are read at `refreshed_at`, Base items
(chain_id 8453) at `refreshed_at_base`. The homepage "Last refreshed" line, the countdown ETAs and the explorer links (Etherscan
or Basescan) are built from this file, so they always state the exact block each item was observed at.

  python3 tools/refresh_radar.py                 # rewrite docs/api/v1/radar.json
  python3 tools/refresh_radar.py --out <path>    # write elsewhere (dry run)

Two timelock kinds are read (both on two endpoints that must agree):
  - OpenZeppelin TimelockController (default): getMinDelay(), getTimestamp(id), isOperationPending(id), isOperationDone(id).
  - Compound Timelock ("kind": "compound", e.g. the Compound governance Timelock): delay(), GRACE_PERIOD() and
    queuedTransactions(txHash). The ETA is re-read from the QueueTransaction log at the item's queue_block (its txHash must match),
    and an ExecuteTransaction / CancelTransaction log for the txHash between queue_block and the pin marks it executed / cancelled.
    pending = queuedTransactions(txHash); ready = queued and ETA <= pin time <= ETA + GRACE_PERIOD; done = an ExecuteTransaction log.

Item order: ready first, then pending by ETA, then anything else, executed last.
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "api", "v1", "radar.json")
# chain_id -> (key in radar.json, expected eth_chainId, two independent public RPC endpoints)
CHAINS = {1: ("refreshed_at", "0x1", ["https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet"]),
          8453: ("refreshed_at_base", "0x2105", ["https://gateway.tenderly.co/public/base", "https://base-rpc.publicnode.com"])}
SEL = {"getTimestamp": "0xd45c4435", "isOperationPending": "0x584b153e", "isOperationDone": "0x2ab0f529", "getMinDelay": "0xf27a0c92",
       # Compound Timelock (GovernorBravo's): delay(), GRACE_PERIOD(), queuedTransactions(bytes32)
       "delay": "0x6a42b8f8", "GRACE_PERIOD": "0xc1a287e2", "queuedTransactions": "0xf2b06537"}
# Compound Timelock events: QueueTransaction / ExecuteTransaction / CancelTransaction(bytes32 indexed txHash, address indexed target,
# uint value, string signature, bytes data, uint eta)
TOPIC = {"queue": "0x76e2796dc3a81d57b0e8504b647febcbeeb5f4af818e164f11eef8131a6a763f",
         "execute": "0xa560e3198060a2f10670c1ec5b403077ea6ae93ca8de1c32b451dc1a943cd6e7",
         "cancel": "0x2fffc091a501fd91bfbff27141450d3acb40fb8e6d8382b243ec7a812a3aaf87"}
LOG_SPAN = 5000   # eth_getLogs block range per request (public endpoints cap the range)
# ops: (op_id, label or None). Timelock addresses are EIP-55 (a wrong-checksum mixed-case address is skipped by the live re-check).
OPS = [
    {"protocol": "Treehouse", "protocol_slug": "treehouse-tree-teth", "chain_id": 1,
     "title": "Treehouse TREE — UUPS upgrade adding Blacklistable",
     "summary": "Upgrades the TREE governance token (not tETH) and installs a 5-of-7 Safe as blacklister: a zero-delay transfer-freeze role after execution.",
     "timelock": "0x2225DAbFfC7F862c99477381E971E8B1FDaB467e", "brief": "briefs/treehouse-op-0x2f11/",
     "ops": [("0x2f11dcc36860f09b9ef94585589ced1798cef603d133efecd017ce7e544c451f", None)]},
    {"protocol": "Lombard", "protocol_slug": "lombard-lbtc", "chain_id": 1,
     "title": "Lombard — AssetRouter, BTC.b and LBTC upgrades adding a fixed deposit fee",
     "summary": "Three ProxyAdmin.upgradeAndCall ops (no init call) upgrade AssetRouter, BTC.b (NativeLBTC) and LBTC (StakedLBTC): a per-token "
                "deposit fee is split off every proof mint to treasury (OPERATOR_ROLE may set 100-1,000 sats, the timelock anything up to half "
                "the minimum), a router-wide minRequestAmount replaces depositMinAmount, and unpauseTransfers moves from DEFAULT_ADMIN_ROLE to MANAGER_ROLE.",
     "timelock": "0x055E84e7FE8955E2781010B866f10Ef6E1E77e59", "brief": "briefs/lombard-ops-0xceee-0x2f2a-0x6404/",
     "ops": [("0xceeeff86865f11b6de2c57d4901d3ec3313edf08be6ea664989d386cb1ab18eb", "AssetRouter upgrade adding a fixed deposit fee"),
             ("0x2f2a342465e4d964eb240db7c573dff2f57e35b9bd3ea3798987aa327c02dd81", "BTC.b token upgrade that charges the deposit fee on mint"),
             ("0x6404e599d016a5a5d60957a22db6919eb7409f28d7d3880cf78ac1313f167fff", "LBTC token upgrade; unpausing transfers moves to the manager role")]},
    {"protocol": "Beefy Finance (Base)", "protocol_slug": "beefy-finance-base", "chain_id": 8453,
     "title": "Beefy CLM USDC-VVV on Aerodrome — calm-check tolerance widened from 9 to 25 ticks",
     "summary": "setDeviation(25) on the cowAeroBaseUSDC-VVV strategy (owned by the timelock): maxTickDeviation 9 -> 25 ticks, the tolerance "
                "between the pool tick and its 120 s TWAP before the strategy acts, on a tick-spacing-50 Aerodrome pool. No code change.",
     "timelock": "0x3B60F7f25b09E71356cdFFC6475c222A466a2AC9", "brief": "briefs/beefy-base-op-0x3302/",
     "ops": [("0x3302750e18a4bff9508c6e93386a406df9aa8d36992188e76a08ecc76bfce208", None)]},
    {"protocol": "Ethena", "protocol_slug": "ethena-usde-susde", "chain_id": 1,
     "title": "Ethena USDe — mint caps cut to 50M per block, USDm delisted, a custodian added",
     "summary": "Four ops: global and per-asset maxMintPerBlock 200M -> 50M USDe on 8 assets; removeSupportedAsset(USDm); addCustodianAddress "
                "for an EOA not yet a custodian; USDe OFT adapter setRateLimits to 25M per hour on LayerZero eids 30339 (was 10M) and 30383 (was 30M).",
     "timelock": "0xE8Dc0Fab349EA169283C48Ccfd09d797E6DB7c94", "brief": "briefs/ethena-ops-0xb028-0xca05-0x108e-0x070a/",
     "ops": [("0xb0289f92009409e09b8b87150e10486ab753b7c13d049702caca3221a622d81a", "mint caps cut from 200M to 50M per block"),
             ("0xca0563b0bebee6c971db36df24ef8c5802ad4007f7fb42bff2f553141c8ed835", "USDm removed as mint collateral"),
             ("0x108ea49a961a00e8992ad4aed2e1faea43b0a47982e0c62d63f9db03ddb4d0f4", "bridge rate limits set to 25M per hour on two routes"),
             ("0x070a0ab4df4b4d69e23ed817c62481d267dae887ed7f7b5fbc7cffa5ff64228d", "a new custodian address added")]},
    {"protocol": "ether.fi", "protocol_slug": "ether-fi-core-eeth-weeth", "chain_id": 1,
     "title": "ether.fi — LayerZero V2 delegate moved behind the 10-day timelock",
     "summary": "EtherfiL1SyncPoolETH.setDelegate(EtherFiTimelock): protective hardening of the OApp's messaging configuration.",
     "timelock": "0x9f26d4C958fD811A1F59B01B86Be7dFFc9d20761", "brief": "briefs/etherfi-op-0x244e/",
     "ops": [("0x244e3f6c3df722246c471cee58804dd34c7703fce9cee1eadc1c5a85f171359f", None)]},
    {"protocol": "Yearn V3", "protocol_slug": "yearn-v3", "chain_id": 1,
     "title": "Yearn V3 — 8 new strategies added to 6 vaults with max-debt caps",
     "summary": "One 16-call batch: add_strategy(strategy, add_to_queue=false) then update_max_debt_for_strategy on yvUSDC-1, yvUSD, yvWETH-1, "
                "yvWETH-2, yvFlexUSDC and yvFlexWETH (Flex siUSD and wstETH lenders / loopers, USDC-to-yvUSDS-1 depositors). Caps range from "
                "10,000 WETH to 10B USDC (yvFlexUSDC, effectively uncapped).",
     "timelock": "0x88Ba032be87d5EF1fbE87336B7090767F367BF73", "brief": "briefs/yearn-v3-op-0x2a14/",
     "ops": [("0x2a14e386ce3da63615778466602757ea8dc25e8157aaee660213827a15efb5cf", None)]},
    {"protocol": "Ethena", "protocol_slug": "ethena-usde-susde", "chain_id": 1,
     "title": "Ethena USDe — RLUSD & USAT collateral onboarding",
     "summary": "Two queued EthenaMinting.addSupportedAsset calls onboard RLUSD and USAT at 200M / 20M USDe-per-block caps (stablesDeltaLimit = 0 bps).",
     "timelock": "0xE8Dc0Fab349EA169283C48Ccfd09d797E6DB7c94", "brief": "briefs/ethena-ops-0x0ca0-0x1fe5/",
     "ops": [("0x1fe5e3e892708310bbfcf50efc03a1b8e21e0d0042035d7e8315e0cd5f26d85b", None),
             ("0x0ca0fcc4856b87f3df9a74532bd60db58d1310c27c17e7d9bfa8a56846f57a90", None)]},
    {"protocol": "ether.fi Liquid", "protocol_slug": "ether-fi-liquid-veda-boringvault", "chain_id": 1,
     "title": "ether.fi Liquid — strategist Merkle roots rotated on liquidUSD, liquidETH and liquidBTC",
     "summary": "One 5-call batch of setManageRoot on the Veda ManagerWithMerkleVerification contracts of three Liquid vaults: four live "
                "strategist roots replaced (a Safe on all three vaults, an EOA on liquidETH) and the liquidUSD manager's own root set to zero. "
                "The new roots' leaves are not onchain.",
     "timelock": "0xD829F278016b90FEc735F9A12Bf8b75E06102C89", "brief": "briefs/etherfi-liquid-op-0xf0fb/",
     "ops": [("0xf0fbfdb07f06c3a429b032811930fbb9b314ed8adc343b4d9ef3a60fe2975eea", None)]},
    {"protocol": "Cap", "protocol_slug": "cap", "chain_id": 1,
     "title": "Cap — EigenLayer service-manager upgrade: slashes paid out only after EigenLayer's resolution delay",
     "summary": "upgradeToAndCall (no initializer) on Cap's EigenServiceManager (UUPS): a slash now queues the payout, valued at slash "
                "time, and anyone completes it once EigenLayer's slash resolution delay has passed (completeSlash); rewards become "
                "USDC-only and USDC can no longer be registered as collateral. Storage is appended only (pendingSlashes).",
     "timelock": "0xD8236031d8279d82E615aF2BFab5FC0127A329ab", "brief": "briefs/cap-op-0x3397/",
     "ops": [("0x3397c542581a354278c3bfd01e0b9e853ec74e6c7a6ea1ec36e1d6e6cf7ab94a", None)]},
    {"protocol": "Compound V3", "protocol_slug": "compound-v3-comet", "chain_id": 1, "kind": "compound", "queue_block": 26443894,
     "title": "Compound V3 — all 25.94 WETH of reserves on Linea's cWETHv3 withdrawn and bridged to the Ethereum Timelock",
     "summary": "Proposal 625: the Ethereum Timelock sends one Linea message (L1 MessageService.sendMessage). On Linea the bridge "
                "receiver queues three calls behind the 1-day Linea Timelock: withdrawReserves of 25.942 WETH from Compound WETH "
                "(cWETHv3), WETH.withdraw, and L2 MessageService.sendMessage of 25.952 ETH (0.01 ETH fee) back to the Ethereum Timelock.",
     "timelock": "0x6d903f6003cca6255D85CcA4D3B5E5146dC33925", "brief": "briefs/compound-v3-op-0x86b4/",
     "ops": [("0x86b41fd84764a2e73ccd29c1e33c93497a70d7e84b7445804752980fa039fee0", None)]},
    {"protocol": "Lombard", "protocol_slug": "lombard-lbtc", "chain_id": 1,
     "title": "Lombard — LBTC and BTC.b deposit fees set to 2,000 sats; minimum request doubled",
     "summary": "One 5-call batch on the upgraded AssetRouter: minRequestAmount 2,000 -> 4,000 sats, a 2,000-sat deposit fee on every "
                "LBTC and BTC.b proof mint (half the new minimum, above the operator range), and LBTC's redeem charge moved from redeemFee "
                "(10,000 -> 0 sats) to toNativeCommission on redeems to Bitcoin (0 -> 10,000 sats).",
     "timelock": "0x055E84e7FE8955E2781010B866f10Ef6E1E77e59", "brief": "briefs/lombard-op-0xd07f/",
     "ops": [("0xd07fa5ecca21af2317c073b5e59ecddce3968f694270409f76771727ea02e50a", None)]},
    {"protocol": "Lista Lending", "protocol_slug": "lista-lending", "chain_id": 1,
     "title": "Lista Lending — four liquidator upgrades add an emergency pause; PAUSER to a 1-of-15 Safe and the EmergencySwitchHub",
     "summary": "One 16-call batch: upgradeToAndCall (no initializer) moves Lista's Liquidator, BrokerLiquidator, V3Liquidator and "
                "PublicLiquidator (UUPS) to implementations that add OpenZeppelin Pausable (storage layout unchanged), then grants PAUSER to "
                "a 1-of-15 Safe and the EmergencySwitchHub, and MANAGER to the hub. One signer can pause liquidations; unpause needs MANAGER.",
     "timelock": "0xa18ae79AEDA3e711E0CD64cfe1Cd06402d400D61", "brief": "briefs/lista-lending-op-0x21df/",
     "ops": [("0x21dffafc9876aca6c919e6897271e72805f3a4a986b3b7ac22d71950c7da7ebd", None)]},
    # Wave 4 Watch (hunter-caught live queued operations, 21-22 Nov 2026)
    {"protocol": "Umia", "protocol_slug": "umia", "chain_id": 8453,
     "title": "Umia — 9-call Base timelock batch upgrading UmiaHub and UmiaMarketCore",
     "summary": "One 9-call batch behind Umia's 48-hour Base timelock (executable 23 Nov 10:30 UTC): upgrades UmiaHub and UmiaMarketCore (UUPS), "
                "rotates three periphery contracts, adds a spotMigrator, and sets an EOA as activeLiquidityKeeper.",
     "timelock": "0xD0193fFAF565B6E530C1a6bbBb2FB13243f29177", "brief": "briefs/umia-op-0x3d35/",
     "ops": [("0x3d35aa49667160b739348b62ec2731b782669aaeb0a869328883bbd68c523788", None)]},
    {"protocol": "Inverse Finance", "protocol_slug": "inverse-finance-firm", "chain_id": 1, "kind": "compound", "queue_block": 26461811,
     "title": "Inverse Finance FiRM — 15-call governance proposal queued in Timelock",
     "summary": "One 15-call governance proposal queued behind Inverse's 48-hour Timelock (executable 23 Nov 06:53 UTC), including setDailyLimit, "
                "setStalenessThreshold and setMinDebt on the FiRM BorrowController. Reported via Wave 4 Watch (@VB-Blue, PR #166).",
     "timelock": "0x926dF14a23BE491164dCF93f4c468A50ef659D5B", "brief": None,
     "ops": [("0x88f3ea76863aafef1d82e0457d59e04c239aca7279272c54d5aa69d0138affaa", "DBR addMarket"),
             ("0x402eb0346f1e1653ff24139ac65416bdf0bdddf1ebdcbdef867f8a68c6d3a365", "Market setBorrowController"),
             ("0x64c48218552f11ac3d15ea16a3a4b56722bf7da2bcc7bda3b0ea0844e23f8c6f", "FiRM BorrowController setDailyLimit"),
             ("0xc1a72f9a18ca57b9d637f48d4b09b37f504898a815fca0b750c6157359beac62", "FiRM BorrowController setStalenessThreshold"),
             ("0xd09136c2466ad4852cfb0ea4005ddd68cd62782237a6faba27c9babe838e0e3d", "FiRM BorrowController setMinDebt"),
             ("0x7403e1649161094373d8ef1ac925e97a5b35c80a299174c7687c9032f4d5fa9c", "Oracle setFeed"),
             ("0x04b88542a16e17a53f1c60ba0a8cfdde6fe4b8e234e143c9a1bca6359e680d81", "Fed allowMarket"),
             ("0xd030676bb887626c1553b9645b20afef09cbd16e3ac395b667b993bec951a4cc", "Fed changeMarketCeiling"),
             ("0x9d4fe57e5bd66a9e298c3411398cc3c80ad9c8288dc413ff17ced7c1db6f8df6", "Market setCollateralFactorBps"),
             ("0xbbf44bc2242cb4327bf31a2cc2f4ff69ba7ac6ce6a4f7ced0862cf0287144c31", "Market setLiquidationFactorBps"),
             ("0x08ce4420bdbfb32428205847a3bec4a128f71aeac1395d0ce58db826db46f5f6", "Market setLiquidationIncentiveBps"),
             ("0x47d3a49ed31061320061342d5e8cdb974da4131612f140337a10d1f794be2d88", "Market setReplenismentIncentiveBps"),
             ("0xc57618a56878be344eecc3516c14f64c183ce310cc5bf15822950512c9d4bf80", "Controller setMarket (bool)"),
             ("0x938bf759b3e496894a0a69a3e4cd0958b7bd25275abdc80c1ae5a9214bedba2f", "Controller setMarket (caps)"),
             ("0x6a45e785eeafd77b74d65f15d113e76228723c5360773a599c6e25e6163e7379", "Registry approveMarket")]},
    {"protocol": "Ethena", "protocol_slug": "ethena-usde-susde", "chain_id": 1,
     "title": "Ethena — 4-call LayerZero EndpointV2 setConfig batch",
     "summary": "One 4-call batch on Ethena's 1-day timelock calling setConfig on LayerZero EndpointV2 (0x1a44…728c) for USDe/sUSDe cross-chain "
                "messaging. Reported via Wave 4 Watch (@oppo2357, PR #170).",
     "timelock": "0xE8Dc0Fab349EA169283C48Ccfd09d797E6DB7c94", "brief": None,
     "ops": [("0xa1ca841370380727e4cb104e298dd8e2e231cba25b4009cd1ba31d9b88faebb7", None)]},
]
RANK = {"ready": 0, "pending": 1, "mixed": 2, "unknown": 3, "executed": 4}


def rpc(url, method, params):
    req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "pacta-site-radar/1.1"})
    for attempt in range(6):   # public endpoints rate-limit bursts (HTTP 429): back off and retry the same read
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                resp = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 5:
                raise
            time.sleep(1.5 * (attempt + 1))
    if resp.get("id") != 1 or "error" in resp:
        raise RuntimeError(f"{method}: {resp.get('error')}")
    return resp["result"]


class Chain:
    """One chain pinned to a finalized block that both endpoints agree on (eth_chainId checked on both)."""

    def __init__(self, chain_id):
        self.key, want, self.rpcs = CHAINS[chain_id]
        for u in self.rpcs:
            if rpc(u, "eth_chainId", []) != want:
                raise RuntimeError(f"{u}: not chain {chain_id}")
        # consensus fields only (endpoints add their own extras, e.g. timestampMs); a lagging endpoint is met at the lower finalized block
        n = min(int(rpc(u, "eth_getBlockByNumber", ["finalized", False])["number"], 16) for u in self.rpcs)
        blocks = [rpc(u, "eth_getBlockByNumber", [hex(n), False]) for u in self.rpcs]
        fin = {k: blocks[0][k] for k in ("number", "hash", "timestamp")}
        if any({k: b[k] for k in fin} != fin for b in blocks):
            raise RuntimeError(f"RPC disagreement on finalized block {n}: {[{k: b[k] for k in fin} for b in blocks]}")
        self.pin = {"blockHash": fin["hash"], "requireCanonical": True}
        self.ts = int(fin["timestamp"], 16)
        self.meta = {"block_number": int(fin["number"], 16), "block_hash": fin["hash"], "block_timestamp": self.ts,
                     "block_time_utc": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(self.ts)), "tag": "finalized",
                     "rpcs_cross_checked": len(self.rpcs)}

    def both(self, method, params):
        a, b = (rpc(u, method, params) for u in self.rpcs)
        if a != b:
            raise RuntimeError(f"RPC disagreement on {method}: {a!r} vs {b!r}")
        return a

    def call(self, to, data):
        return int(self.both("eth_call", [{"to": to, "data": data}, self.pin]), 16)

    def logs(self, address, topics, frm, to=None):
        """eth_getLogs on both endpoints (consensus fields only), in LOG_SPAN chunks from block frm to the pin."""
        out, to = [], self.meta["block_number"] if to is None else to
        key = lambda x: (x["blockHash"], x["transactionHash"], x["logIndex"], x["address"].lower(), x["topics"], x["data"], x.get("removed", False))
        while frm <= to:
            end = min(frm + LOG_SPAN - 1, to)
            got = [sorted((key(x) for x in rpc(u, "eth_getLogs", [{"address": address, "topics": topics, "fromBlock": hex(frm), "toBlock": hex(end)}])),
                          key=lambda k: (k[0], k[2])) for u in self.rpcs]
            if got[0] != got[1]:
                raise RuntimeError(f"RPC disagreement on eth_getLogs {address} {frm}-{end}")
            out += [k for k in got[0] if not k[6]]
            frm = end + 1
        return out


def compound_ops(ch, o):
    """Compound Timelock: (delay, ops) at the pin. The ETA comes from the QueueTransaction log; its txHash must be the op id."""
    delay, grace = ch.call(o["timelock"], SEL["delay"]), ch.call(o["timelock"], SEL["GRACE_PERIOD"])
    ops = []
    for op, label in o["ops"]:
        q = ch.logs(o["timelock"], [TOPIC["queue"], op], o["queue_block"], o["queue_block"])
        if len(q) != 1:
            raise RuntimeError(f"{o['protocol']}: expected one QueueTransaction {op} at block {o['queue_block']}, got {len(q)}")
        eta = int(q[0][5][2 + 64 * 3: 2 + 64 * 4], 16)   # data = (value, signature offset, data offset, eta, ...)
        queued = ch.call(o["timelock"], SEL["queuedTransactions"] + op[2:]) == 1
        done = bool(ch.logs(o["timelock"], [TOPIC["execute"], op], o["queue_block"]))
        cancelled = bool(ch.logs(o["timelock"], [TOPIC["cancel"], op], o["queue_block"]))
        if done and cancelled:
            raise RuntimeError(f"{o['protocol']}: {op} both executed and cancelled")
        ops.append({"op_id": op, "eta": None if done else eta, "pending": queued, "done": done,
                    "ready": bool(queued and not done and eta <= ch.ts <= eta + grace), **({"label": label} if label else {})})
    return delay, ops


def state(ops):
    s = {"executed" if o["done"] else "ready" if o["ready"] else "pending" if o["pending"] else "unknown" for o in ops}
    return s.pop() if len(s) == 1 else "mixed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    out_path = ap.parse_args().out
    chains = {cid: Chain(cid) for cid in sorted({o["chain_id"] for o in OPS} | {1})}
    items = []
    for o in OPS:
        ch = chains[o["chain_id"]]
        if o.get("kind") == "compound":
            delay, ops = compound_ops(ch, o)
            items.append({**{k: o[k] for k in ("protocol", "protocol_slug", "chain_id", "title", "summary", "timelock", "brief")},
                          "timelock_kind": "compound", "min_delay_seconds": delay, "operations": ops,
                          "eta": min((x["eta"] for x in ops if x["eta"]), default=None)})
            continue
        delay = ch.call(o["timelock"], SEL["getMinDelay"])
        ops = []
        for op, label in o["ops"]:
            ts = ch.call(o["timelock"], SEL["getTimestamp"] + op[2:])
            pending = ch.call(o["timelock"], SEL["isOperationPending"] + op[2:]) == 1
            done = ch.call(o["timelock"], SEL["isOperationDone"] + op[2:]) == 1
            # ready: the delay has elapsed at the finalized block and the op is still unexecuted (execute() is now callable).
            # Never "executed" unless isOperationDone is true.
            ops.append({"op_id": op, "eta": ts if ts > 1 else None, "pending": pending, "done": done,
                        "ready": bool(pending and not done and ts > 1 and ch.ts >= ts), **({"label": label} if label else {})})
        items.append({**{k: o[k] for k in ("protocol", "protocol_slug", "chain_id", "title", "summary", "timelock", "brief")},
                      "min_delay_seconds": delay, "operations": ops, "eta": min((x["eta"] for x in ops if x["eta"]), default=None)})
    items.sort(key=lambda it: (RANK[state(it["operations"])], it["eta"] or 0))   # stable: ready, pending by ETA, …, executed last
    out = {"schema": "pacta.radar.v1", "chain_id": 1, **{ch.key: ch.meta for ch in chains.values()}, "items": items}
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print({ch.key: ch.meta["block_number"] for ch in chains.values()},
          [(i["protocol"], i["chain_id"], i["eta"], state(i["operations"])) for i in items])


if __name__ == "__main__":
    main()
