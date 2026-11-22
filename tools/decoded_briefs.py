"""v4.6: the radar pre-execution briefs rendered from tools/briefs_decoded.json (schema pacta.decoded_briefs.v1); Sprint 27 adds the fifth, Sprint 28 the sixth.

tools/briefs_decoded.json is the decoder's output, committed byte-for-byte: scheduling logs, decoded calls, current vs new state,
verified sources (Sourcify), risk notes and `cast` reproduction commands. Every value in it was read at a finalized block
(Ethereum Mainnet or Base) on two independent public RPC endpoints that agreed. This module adds only the editorial frame
(headline, lede, badges, key-figure labels); every address, amount, block and transaction on the page comes from the JSON, and
every explorer link goes to the brief's own chain: Etherscan for chain id 1, Basescan for chain id 8453 (never Etherscan for a
Base brief). build_site.brief_page() adds the radar meta block, the post-ETA banner and the clearance callout around it.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from onboarding_scan import eip55  # noqa: E402  (pure keccak / EIP-55; never touches the network)

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "briefs_decoded.json")
SCHEMA = "pacta.decoded_briefs.v1"
CHAIN_BY_ID = {1: "ethereum", 8453: "base"}
ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}")
WAD = 10 ** 18

# Editorial frame only. Figures in the key-figure tiles are computed from the JSON in kpis() below.
EDITORIAL = {
    "umia-op-0x3d35": {
        "title": "Pacta Governance Radar · Pre-Execution Brief — Umia Op 0x3d35 on Base",
        "h1": "Umia on Base — One 9-Call Batch Upgrades <code>UmiaHub</code> and <code>UmiaMarketCore</code>",
        "lede": ("Pre-execution decode of one Base Mainnet timelock operation: two UUPS upgrades, three rotated periphery contracts, a new "
                 "spot migrator, an externally owned account as activeLiquidityKeeper and two new launch parameters, executable from "
                 "23 Nov 2026 10:30:40 UTC."),
        "badges": [("badge-cyan", "Pre-execution brief"), ("badge-amber", "Two core upgrades in one batch"),
                   ("badge-amber", "Keeper role to an EOA")],
        "state_title": "UmiaHub and UmiaMarketCore: current vs queued",
    },
    "lombard-ops-0xceee-0x2f2a-0x6404": {
        "title": "Pacta Governance Radar · Pre-Execution Brief — Lombard LBTC Ops 0xceee, 0x2f2a, 0x6404",
        "h1": "Lombard <code>LBTC</code> — Three Queued Proxy Upgrades Add a Per-Mint Deposit Fee",
        "lede": ("Pre-execution decode of three independent LombardTimeLock operations that upgrade AssetRouter, BTC.b (NativeLBTC) and "
                 "LBTC (StakedLBTC). The fee starts at 0, the three can execute in any order, and resuming paused LBTC transfers "
                 "no longer waits for the timelock."),
        "badges": [("badge-cyan", "Pre-execution brief"), ("badge-amber", "Order hazard: BTC.b before AssetRouter"),
                   ("badge-amber", "unpauseTransfers leaves the timelock")],
        "state_title": "Proxies: current vs queued implementation",
    },
    "beefy-base-op-0x3302": {
        "title": "Pacta Governance Radar · Pre-Execution Brief — Beefy CLM on Base Op 0x3302",
        "h1": "Beefy CLM <code>cowAeroBaseUSDC-VVV</code> on Base — Calm-Check Tolerance Widened to 25 Ticks",
        "lede": ("Pre-execution decode of one Base Mainnet timelock operation: setDeviation(25) widens how far the Aerodrome USDC/VVV "
                 "pool tick may sit from its TWAP before the strategy refuses to act. A parameter change, not a strategy upgrade."),
        "badges": [("badge-cyan", "Pre-execution brief"), ("badge-cyan", "Base Mainnet · chain id 8453"),
                   ("badge-amber", "Looser price-manipulation guard")],
        "state_title": "Strategy state at the pinned Base block",
    },
    "ethena-ops-0xb028-0xca05-0x108e-0x070a": {
        "title": "Pacta Governance Radar · Pre-Execution Brief — Ethena USDe Ops 0xb028, 0xca05, 0x108e, 0x070a",
        "h1": "Ethena <code>USDe</code> — Mint Caps Cut to 50M, USDm Delisted, Bridge Limits Reset, a Custodian Added",
        "lede": ("Pre-execution decode of four independent EthenaTimelockController operations on EthenaMinting and the USDe OFT "
                 "adapter (LayerZero). Three tighten or rebalance limits; one adds an externally owned account as a custodian."),
        "badges": [("badge-cyan", "Pre-execution brief"), ("badge-green", "Mint caps tightened"),
                   ("badge-amber", "New custodian is an EOA")],
        "state_title": "EthenaMinting and the USDe OFT adapter at the pin",
    },
    "yearn-v3-op-0x2a14": {
        "title": "Pacta Governance Radar · Pre-Execution Brief — Yearn V3 Op 0x2a14",
        "h1": "Yearn V3 — 8 Strategies Queued Across 6 Vaults with Max-Debt Caps",
        "lede": ("Pre-execution decode of one 16-call TimelockController batch: each of 8 inactive strategies is added outside the "
                 "default queue and given a max-debt cap, from 10,000 WETH to 10,000,000,000 USDC."),
        "badges": [("badge-cyan", "Pre-execution brief"), ("badge-amber", "yvFlexUSDC cap: in effect uncapped")],
        "state_title": "Vaults and strategies",
    },
    "etherfi-liquid-op-0xf0fb": {
        "title": "Pacta Governance Radar · Pre-Execution Brief — ether.fi Liquid Op 0xf0fb",
        "h1": "ether.fi Liquid — Strategist Merkle Roots Rotated on <code>liquidUSD</code>, <code>liquidETH</code> and <code>liquidBTC</code>",
        "lede": ("Pre-execution decode of one 5-call timelock batch on the Veda ManagerWithMerkleVerification contracts of three ether.fi "
                 "Liquid vaults: four live strategist roots are replaced and one is cleared. The roots' leaves are not onchain."),
        "badges": [("badge-cyan", "Pre-execution brief"), ("badge-amber", "Root leaves not onchain"),
                   ("badge-amber", "EOA strategist on liquidETH")],
        "state_title": "Managers, vaults and strategists at the pin",
    },
    "cap-op-0x3397": {
        "title": "Pacta Governance Radar · Pre-Execution Brief — Cap EigenServiceManager Op 0x3397",
        "h1": "Cap <code>EigenServiceManager</code> — Queued Upgrade Makes Slashes Pay Out After EigenLayer's Resolution Delay",
        "lede": ("Pre-execution decode of one Cap TimelockController operation: upgradeToAndCall moves Cap's EigenLayer service manager to a "
                 "new implementation where a slash only queues the payout, anyone completes it later, and rewards are USDC-only."),
        "badges": [("badge-cyan", "Pre-execution brief"), ("badge-amber", "Slash payouts become two-step"),
                   ("badge-amber", "Non-USDC rewards revert")],
        "state_title": "Proxy, implementations and roles at the pin",
    },
    "compound-v3-op-0x86b4": {
        "title": "Pacta Governance Radar · Pre-Execution Brief — Compound V3 Proposal 625 (Op 0x86b4)",
        "h1": "Compound V3 — Proposal 625 Withdraws All 25.94 WETH of Linea <code>cWETHv3</code> Reserves to the Ethereum Timelock",
        "lede": ("Pre-execution decode of one Compound Timelock transaction: a Linea message whose three calls, after a second 1-day timelock "
                 "on Linea, withdraw the Compound WETH market's entire reserve balance, unwrap it and bridge the ETH back to Ethereum."),
        "badges": [("badge-cyan", "Pre-execution brief"), ("badge-cyan", "Cross-chain: Ethereum to Linea"),
                   ("badge-amber", "Entire reserve balance")],
        "state_title": "Linea state at the pinned Linea block",
    },
    "lombard-op-0xd07f": {
        "title": "Pacta Governance Radar · Pre-Execution Brief — Lombard AssetRouter Op 0xd07f",
        "h1": "Lombard <code>AssetRouter</code> — 2,000-Sat Deposit Fees on <code>LBTC</code> and <code>BTC.b</code>, Minimum Request Doubled",
        "lede": ("Pre-execution decode of one 5-call LombardTimeLock batch on the upgraded AssetRouter: the router-wide minimum doubles to "
                 "4,000 sats, every LBTC and BTC.b proof mint pays a fixed 2,000-sat deposit fee, and LBTC's redeem charge moves from "
                 "non-Bitcoin redeems to redeems to Bitcoin."),
        "badges": [("badge-cyan", "Pre-execution brief"), ("badge-amber", "New fee on every proof mint"),
                   ("badge-amber", "Fee above the operator range")],
        "state_title": "AssetRouter parameters: current vs queued",
    },
    "lista-lending-op-0x21df": {
        "title": "Pacta Governance Radar · Pre-Execution Brief — Lista Lending Op 0x21df",
        "h1": "Lista Lending — Four Liquidator Upgrades Add an Emergency Pause; a 1-of-15 Safe Gets <code>PAUSER</code>",
        "lede": ("Pre-execution decode of one 16-call Lista TimeLock batch: the Liquidator, BrokerLiquidator, V3Liquidator and PublicLiquidator "
                 "proxies (UUPS) move to implementations that add OpenZeppelin Pausable, then PAUSER goes to a 1-of-15 Safe and to Lista's "
                 "EmergencySwitchHub, and MANAGER to the hub."),
        "badges": [("badge-cyan", "Pre-execution brief"), ("badge-amber", "Pause by 1 of 15 signers"),
                   ("badge-green", "Storage layout unchanged")],
        "state_title": "Liquidators, roles and the EmergencySwitchHub at the pin",
    },
}


def load():
    with open(SRC, encoding="utf-8") as fh:
        d = json.load(fh)
    assert d["schema"] == SCHEMA, d["schema"]
    c = d["counts"]
    assert len(d["briefs"]) == c["briefs"] and sum(len(b["operations"]) for b in d["briefs"]) == c["operations"]
    assert sum(len(o["calls"]) for b in d["briefs"] for o in b["operations"]) == c["calls"]
    assert set(EDITORIAL) == {b["slug"] for b in d["briefs"]}
    return {b["slug"]: b for b in d["briefs"]}


LINEA = ("Lineascan", "https://lineascan.build")     # Linea-side addresses in a cross-chain brief (never Etherscan for them)


def tl_delay(b):
    """The timelock's delay: getMinDelay() (OpenZeppelin TimelockController) or delay() (Compound Timelock)."""
    t = b["timelock"]
    return t["delay"] if t.get("kind") == "compound" else t["getMinDelay"]


def status_eta(x):
    return x["status"]["eta"] if "queuedTransactions" in x["status"] else x["status"]["getTimestamp"]


def check_against_radar(b, item, brief_protocol):
    """The decoded brief and its radar.json item describe the same timelock operations on the same chain."""
    assert item is not None, b["slug"]
    assert item["brief"] == b["brief"] and item["protocol_slug"] == b["protocol_slug"] == brief_protocol, b["slug"]
    assert item.get("chain_id", 1) == b["chain_id"] and item["timelock"].lower() == b["timelock"]["address"].lower(), b["slug"]
    assert [o["op_id"] for o in item["operations"]] == [o["op_id"] for o in b["operations"]], b["slug"]
    assert item["min_delay_seconds"] == tl_delay(b), b["slug"]
    assert (item.get("timelock_kind") == "compound") == (b["timelock"].get("kind") == "compound"), b["slug"]
    # a later radar refresh may find an operation executed (isOperationDone / ExecuteTransaction: eta cleared); otherwise the ETA is the decoded one
    assert all(o["eta"] == status_eta(x) or (o["done"] and o["eta"] is None)
               for o, x in zip(item["operations"], b["operations"])), b["slug"]


def millions(wei):
    """Exact USDe (18 decimals) amounts in millions: 200000000 * 10**18 -> 200M (never rounded)."""
    assert wei % (WAD * 10 ** 6) == 0, wei
    return f"{wei // (WAD * 10 ** 6):,}M"


def mstr(s):
    """'25,000,000' -> '25M' (exact millions only)."""
    assert s.endswith(",000,000"), s
    return s[:-8] + "M"


NUM_WORD = {1: "One", 2: "Two", 3: "Three", 4: "Four"}


def adj(s):
    """86400 -> '1-day (86,400 s)'; 21600 -> '6-hour (21,600 s)'."""
    n, u = (s // 86400, "day") if s % 86400 == 0 else (s // 3600, "hour")
    assert n * (86400 if u == "day" else 3600) == s, s
    return f"{n}-{u} ({s:,} s)"


def dur(s):
    if s % 86400 == 0:
        n, u = s // 86400, "day"
    else:
        assert s % 3600 == 0, s
        n, u = s // 3600, "hour"
    return f"{n} {u}{'' if n == 1 else 's'} ({s:,} s)"


def round2(s):
    """'5,010.57415989616055714' -> '5,010.57' (display only; the exact value is in the title attribute)."""
    whole, _, frac = s.partition(".")
    return whole + ("." + (frac + "00")[:2] if frac else "")


def op_state(o):
    st = o["status"]
    if "queuedTransactions" in st:   # Compound Timelock
        if st["executed"]:
            return "executed"
        if o["ready"]:
            return "ready: delay elapsed, still unexecuted"
        return "pending (queued)" if st["queuedTransactions"] else "not queued"
    if st["isOperationDone"]:
        return "executed"
    if st["isOperationReady"]:
        return "ready: delay elapsed, still unexecuted"
    return "pending" if st["isOperationPending"] else "not queued"


def render(b, item, bs):
    """(title, content HTML) for brief b; bs = the build_site module (E, short, hexref, term, EXPLORERS, CHAINS, U, EXT)."""
    E, short, EXT = bs.E, bs.short, bs.EXT
    ed = EDITORIAL[b["slug"]]
    ch = CHAIN_BY_ID[b["chain_id"]]
    chain_name = bs.CHAINS[ch][0]
    xname, xbase = bs.EXPLORERS[ch]
    pin = b["pinned_block"]
    tl = item["timelock"]                      # EIP-55 form from radar.json
    tl_l = tl.lower()
    tl_name = (b["timelock"]["verified"].get("sourcify") or {}).get("name") or b["timelock"].get("name", "Timelock")
    names = {tl_l: f"{tl_name} (this timelock)"}
    names.update(target_names(b))

    def xa(a, label=None):
        """Address on the brief's own chain explorer (Etherscan or Basescan), EIP-55 checksummed."""
        a = eip55(a)
        text = E(label) if label else f'<span class="addr">{E(short(a))}</span>'
        return f'<a href="{xbase}/address/{E(a)}" target="_blank" rel="noopener" title="{E(a)}">{text}{EXT}</a>'

    def xl(a, label=None):
        """An address on Linea (cross-chain briefs): Lineascan, EIP-55 checksummed."""
        a = eip55(a)
        text = E(label) if label else f'<span class="addr">{E(short(a))}</span>'
        return f'<a href="{LINEA[1]}/address/{E(a)}" target="_blank" rel="noopener" title="{E(a)} on Linea">{text}{EXT}</a>'

    def xtx(h):
        return f'<a href="{xbase}/tx/{E(h)}" target="_blank" rel="noopener" title="{E(h)}"><span class="addr">{E(short(h, 8, 6))}</span>{EXT}</a>'

    def xblock(n):
        return f'<a href="{xbase}/block/{n}" target="_blank" rel="noopener">#{n:,}{EXT}</a>'

    def arg(v, on=None):
        if isinstance(v, bool):
            return f"<code>{str(v).lower()}</code>"
        if isinstance(v, str) and ADDR_RE.fullmatch(v):
            return xl(v) if on == "linea" else xa(v)
        if isinstance(v, list):
            return "[" + ", ".join(arg(x) for x in v) + "]"
        return f"<code>{E(str(v))}</code>"

    ops = b["operations"]
    label = lambda o: (o.get("label") or b["radar_title"].split(" — ", 1)[-1])
    cap = lambda s: s[:1].upper() + s[1:]
    etas = sorted({o["eta_utc"] for o in ops})
    eta = etas[0] if len(etas) == 1 else (f"{etas[0][:-4]}–{etas[-1][11:]}" if etas[0][:10] == etas[-1][:10] else f"{etas[0]} to {etas[-1]}")
    facts = {"delay": dur(tl_delay(b)), "eta": eta}

    # header + key figures
    out = ['<header>', '  <div>' + "".join(f'<span class="badge {c}">{E(t)}</span>' for c, t in ed["badges"]) + '</div>',
           f'  <h1>{ed["h1"]}</h1>', f'  <p>{E(ed["lede"])}</p>', '</header>', '', '<div class="meta-grid">']
    for k, v, s, ok in kpis(b, facts):
        out.append(f'  <div class="kpi"><div class="k">{E(k)}</div><div class="v">{E(v)}</div><div class="{"s-ok" if ok else "s"}">{E(s)}</div></div>')
    out.append('</div>')

    # 1. what is queued
    n_ops = len(ops)
    out += ['', '<h2>1. What Is Queued</h2>', '<div class="card">',
            f'  <p>{NUM_WORD[n_ops]} operation{"s are" if n_ops > 1 else " is"} queued on {xa(tl, tl_name)}, the {E(chain_name)} timelock '
            f'with a {E(adj(tl_delay(b)))} minimum delay. Every value on this page was read at {E(chain_name)} finalized block '
            f'{xblock(pin["block_number"])} ({E(pin["block_time_utc"])}, block hash '
            f'<span class="addr" title="{E(pin["block_hash"])}">{E(short(pin["block_hash"], 10, 6))}</span>) on '
            f'{pin["rpcs_cross_checked"]} independent public RPC endpoints that agreed.</p>', '  <ul>']
    for o in ops:
        n = len(o["calls"])
        out.append(f'    <li><strong>{E(cap(label(o)))}</strong>: operation {bs.hexref(o["op_id"], 8, 4)} · {n} call{"s" if n > 1 else ""} · '
                   f'ETA {E(o["eta_utc"])} · {E(op_state(o))} at the pin.</li>')
    out.append('  </ul>')
    by_tx = {}
    for o in ops:
        by_tx.setdefault(o["scheduled"]["tx"], []).append(o)

    def sched(tx, s):
        fn = s["function"] if not s["function"].startswith("0x") else f"selector {s['function']}"
        return f'transaction {xtx(tx)} at block {xblock(s["block"])} ({E(fn)}, sent by {xa(s["from"])} to {xa(s["to"])})'
    if len(by_tx) == 1:
        tx, os_ = next(iter(by_tx.items()))
        out.append(f'  <p>{f"All {n_ops} operations were" if n_ops > 1 else "The operation was"} scheduled in {sched(tx, os_[0]["scheduled"])}.</p>')
    else:
        out.append('  <p>Scheduled in:</p>\n  <ul>')
        for tx, os_ in by_tx.items():
            ids = ", ".join(f'<span class="addr" title="{E(o["op_id"])}">{E(short(o["op_id"], 6, 4))}</span>' for o in os_)
            out.append(f'    <li>{ids}: {sched(tx, os_[0]["scheduled"])}</li>')
        out.append('  </ul>')
    out.append('</div>')

    # 2. decoded calls
    out += ['', '<h2>2. Decoded Calls</h2>']
    for o in ops:
        pred = ("proposal " + str(o["proposalId"])) if "proposalId" in o else \
            "predecessor " + ("none" if int(o["predecessor"], 16) == 0 else o["predecessor"])
        out += [f'<h3>{E(cap(label(o)))} · <span class="addr" title="{E(o["op_id"])}">{E(short(o["op_id"], 6, 4))}</span></h3>',
                '<div class="card">',
                f'  <p class="s">{len(o["calls"])} call{"s" if len(o["calls"]) > 1 else ""} · {E(pred)} · delay {o["delay"]:,} s · '
                f'ETA {E(o["eta_utc"])}</p>', '  <ol class="calls">']
        for c in o["calls"]:
            assert c["value"] == 0, (b["slug"], c)
            fname = c["function"].split("(", 1)[0]
            args = ", ".join(f'{E(k)} = {arg(v, c.get("argChains", {}).get(k))}' for k, v in c["args"].items())
            out.append(f'    <li><code>{E(fname)}</code>({args}) on {xa(c["target"], names.get(c["target"].lower()))}'
                       f'{call_effect(b, o, c, E)}</li>')
        out += ['  </ol>', '</div>']

    # 3. protocol state
    out += ['', f'<h2>3. {E(ed["state_title"])}</h2>']
    out += STATE[b["slug"]](b, item, bs, xa, E) if b["slug"] != "compound-v3-op-0x86b4" else state_compound(b, item, bs, xa, xl, E)

    # 4. risk notes
    out += ['', '<h2>4. Risk Notes</h2>', '<div class="card">', '  <ul>']
    out += [f'    <li>{E(n)}</li>' for n in b["risk_notes"]]
    out += ['  </ul>', '</div>']

    # 5. reproduce
    rpc = bs.CHAINS[ch][2]
    decodes = [c["cast_decode"] for o in ops for c in o["calls"]]
    out += ['', '<h2>5. Reproduce</h2>', '<div class="card">',
            f'  <p>Every value above can be re-read at block #{pin["block_number"]:,} with Foundry <code>cast</code> against any {E(chain_name)} '
            f'archive node (<code>{E(rpc)}</code>).</p>',
            bs.U.accordion_item(f'<span>{len(b["reproduce"])} <code>cast</code> commands at {E(chain_name)} block #{pin["block_number"]:,}</span>',
                                bs.term("\n".join(b["reproduce"]), title=f"Reproduce on any {chain_name} archive node",
                                        what=f"Copy the {len(b['reproduce'])} cast commands")),
            bs.U.accordion_item(f'<span>Decode the {len(decodes)} queued call{"s" if len(decodes) > 1 else ""} offline (<code>cast calldata-decode</code>)</span>',
                                bs.term("\n".join(decodes), title="Offline calldata decode", what=f"Copy the {len(decodes)} calldata-decode commands")),
            '</div>']
    return ed["title"], "\n".join(out) + "\n"


def target_names(b):
    d, n = b["decoded"], {}
    if "upgrades" in d:
        for u in d["upgrades"]:
            if u["proxyAdmin"]:
                n[u["proxyAdmin"]] = f'ProxyAdmin of {u["proxyName"]}'
            n[u["proxy"]] = u["proxyName"]
    if "l1" in d:
        n[d["l1"]["messageService"]["address"]] = "Linea L1 MessageService (LineaRollup)"
        n[d["l1"]["governor"]["address"]] = d["l1"]["governor"]["name"]
    if "strategy" in d:
        s = d["strategy"]
        n[s["strategy"]] = f'Beefy CLM strategy ({s["vaultSymbol"]})'
        n[s["vault"]] = s["vaultSymbol"]
    if "minting" in d:
        n[d["minting"]["address"]] = "EthenaMinting"
        n[d["oftAdapter"]["address"]] = "USDeOFTAdapter (LayerZero)"
        n.update({a: v["symbol"] for a, v in d["assets"].items()})
    if "hub" in d:
        n[d["hub"]["address"]] = "EmergencySwitchHub"
    if "router" in d:
        n[d["router"]["address"]] = d["router"]["name"]
        n.update({a: v["symbol"] for a, v in d["tokens"].items()})
    if "managers" in d:
        n.update({m: f'{v["vaultSymbol"]} manager' for m, v in d["managers"].items()})
        n.update({v["vault"]: v["vaultSymbol"] for v in d["managers"].values()})
    if "vaults" in d:
        n.update({a: v["symbol"] for a, v in d["vaults"].items()})
        n.update({s["strategy"]: s["strategyName"] for s in d["strategies"]})
    return {k.lower(): v for k, v in n.items()}


def call_effect(b, o, c, E):
    """One plain-language clause per decoded call, from the decoder's own annotations."""
    d = b["decoded"]
    if "umiaEffect" in c:
        return f" — {E(c['umiaEffect'])}"
    if "change" in c and "from" in c["change"]:
        ch = c["change"]
        return f' — {E(c.get("asset", "Global"))}: {E(ch["from"])} to {E(ch["to"])} {E(ch["unit"])}'
    if "change" in c and "isSupportedAsset" in c["change"]:
        ch = c["change"]["isSupportedAsset"]
        return f' — {E(c["asset"])} delisted (isSupportedAsset {str(ch["from"]).lower()} to {str(ch["to"]).lower()})'
    if "rateLimits" in c:
        return "".join(f' — LayerZero eid {r["dstEid"]}: limit {E(r["limit"]["from"])} to {E(r["limit"]["to"])} USDe per '
                       f'{r["window"]["to"]:,} s (window unchanged; {E(round2(r["amountInFlightAtPin"]))} in flight at the pin)'
                       for r in c["rateLimits"])
    if "custodian" in c:
        k = c["custodian"]
        return (f' — {E(k["kind"])} ({k["codeBytes"]} bytes of code); isCustodianAddress = '
                f'{str(k["isCustodianAddress"]).lower()} at the pin')
    if "lombardChange" in c:
        x = c["lombardChange"]
        who = f'{x["tokenSymbol"]} ' if x.get("tokenSymbol") else ""
        return f' — {E(who)}{E(x["parameter"])}: {x["from"]:,} to {x["to"]:,} {E(x["unit"])}'
    if "root" in c:
        r = c["root"]
        to = "zero (cleared)" if int(r["to"], 16) == 0 else f'{r["to"][:6]}…{r["to"][-4:]}'
        return f' — {E(c["vaultSymbol"])}: {E(c["strategistKind"])} strategist root {E(r["from"][:6])}…{E(r["from"][-4:])} to {E(to)}'
    if "newMaxDebtUnits" in c:
        return f' — max debt {E(c["newMaxDebtUnits"])}'
    if c["function"].startswith("add_strategy"):
        s = next(s for s in d["strategies"] if s["strategy"] == c["args"]["new_strategy"])
        return f' — {E(s["vaultSymbol"])}: {E(s["strategyName"])}, not added to the default queue'
    if c["function"].startswith("setDeviation"):
        return f' — maxTickDeviation {d["strategy"]["maxTickDeviation"]} to {d["newMaxTickDeviation"]} ticks'
    if "grant" in c:
        g = c["grant"]
        return f' — {E(g["roleName"])} to {E(g["accountName"])} (not held at the pin)' if not g["heldBefore"] else f' — {E(g["roleName"])} (already held)'
    if "upgradeOf" in c:
        u = next(u for u in d["upgrades"] if u["proxy"] == c["upgradeOf"])
        assert u["initCalldataBytes"] == 0 and c["args"]["data"] == "0x"
        return f' — {E(u["proxyName"])} (UUPS) to the queued implementation; adds Pausable; no initializer (empty data)'
    if c["function"].startswith("upgradeToAndCall"):
        u = next(u for u in d["upgrades"] if u["op_id"] == o["op_id"])
        assert u["initCalldataBytes"] == 0 and c["args"]["data"] == "0x"
        return f' — {E(u["proxyName"])} (UUPS) to the queued implementation; no initializer (empty data)'
    if c["function"].startswith("sendMessage") and "linea" in d:
        n_ = len(d["linea"]["calls"])
        return f' — a Linea message to the LineaBridgeReceiver carrying {n_} calls for the Linea Timelock (decoded in section 3); no fee, no value'
    if c["function"].startswith("upgradeAndCall"):
        u = next(u for u in d["upgrades"] if u["op_id"] == o["op_id"])
        assert u["initCalldataBytes"] == 0 and c["args"]["data"] == "0x"
        return f' — {E(u["proxyName"])} to the queued implementation; no initializer (empty data)'
    return ""


def kpis(b, F):
    """(label, value, sub-line, ok) for the four key-figure tiles; numbers from the JSON."""
    d, ops = b["decoded"], b["operations"]
    slug = b["slug"]
    if slug.startswith("umia-"):
        calls = [c for o in ops for c in o["calls"]]
        ups = sum(1 for c in calls if c["function"].startswith("upgradeToAndCall"))
        return [("Calls", f"{len(calls)} in one batch", f"{ups} upgradeToAndCall + {len(calls) - ups} setters", False),
                ("Timelock delay", F["delay"], f"ETA {F['eta']}", False),
                ("Unverified new code", "3 contracts", "Oracle, spot migrator, LBP factory", False),
                ("Keeper role", "EOA", "activeLiquidityKeeper · no code at the pin", False)]
    if slug == "lombard-op-0xd07f":
        ch = {c["lombardChange"]["parameter"] + (c["lombardChange"]["tokenSymbol"] or ""): c["lombardChange"] for o in ops for c in o["calls"]}
        lo, hi = d["router"]["depositFeeOperatorRange"]
        mn = ch["minRequestAmount"]
        return [("Deposit fee per proof mint", f'{ch["depositFeeLBTC"]["to"]:,} sats', f'LBTC and BTC.b · {ch["depositFeeLBTC"]["from"]:,} today', False),
                ("Minimum request", f'{mn["from"]:,} to {mn["to"]:,} sats', "Router-wide · set first in the batch", False),
                ("Timelock delay", F["delay"], f"ETA {F['eta']}", False),
                ("Operator fee range", f"{lo:,}–{hi:,} sats", "The queued fee is above it: timelock only", True)]
    if slug.startswith("lista-"):
        calls = [c for o in ops for c in o["calls"]]
        ps = d["safes"]["pauser"]
        return [("Calls", f"{len(calls)} in one batch", f"{len(d['upgrades'])} upgradeToAndCall + {len(d['grants'])} grantRole", False),
                ("Timelock delay", F["delay"], f"ETA {F['eta']}", False),
                ("Pause quorum", f"{ps['threshold']} of {ps['owners']}", "PAUSER Safe · unpause needs MANAGER", False),
                ("Storage", "Unchanged", "Pausable flag in an ERC-7201 slot", True)]
    if slug.startswith("cap-"):
        u = d["upgrades"][0]
        return [("Operation", "1 UUPS upgrade", "upgradeToAndCall · no initializer", False),
                ("Timelock delay", F["delay"], f"ETA {F['eta']}", False),
                ("Slash payout", "Queued", "completeSlash after EigenLayer's delay", False),
                ("Storage", "Append-only", f"ABI +{len(u['sourceDiff']['abiAdded'])} · -{len(u['sourceDiff']['abiRemoved'])}", True)]
    if slug.startswith("compound-"):
        ln = d["linea"]
        w = ln["calls"][0]
        return [("Reserves withdrawn", f"{w['amountEth'][:w['amountEth'].index('.') + 3]} WETH", "All reserves of Linea cWETHv3 at the pin", False),
                ("Ethereum Timelock delay", F["delay"], f"ETA {F['eta']}", False),
                ("Then on Linea", dur(ln["localTimelock"]["delay"]), "Linea Timelock before the calls run", False),
                ("Bridged back", f"{ln['calls'][2]['valueEth'][:ln['calls'][2]['valueEth'].index('.') + 3]} ETH", f"incl. {ln['calls'][2]['feeEth']} ETH fee", True)]
    if slug.startswith("lombard"):
        ar = d["assetRouter"]
        return [("Operations", f"{len(ops)} proxy upgrades", "Independent · predecessor 0x0", False),
                ("Timelock delay", F["delay"], f"ETA {F['eta']}", False),
                ("Deposit fee at execution", "0 sats", "Operator range 100–1,000 sats", False),
                ("Minimum request", f"{ar['depositMinAmount(BTC.b)']:,} sats", "Unchanged · now minRequestAmount", True)]
    if slug.startswith("beefy"):
        s = d["strategy"]
        return [("maxTickDeviation", f"{s['maxTickDeviation']} to {d['newMaxTickDeviation']} ticks", f"Pool tick spacing {s['poolTickSpacing']}", False),
                ("Timelock delay", F["delay"], f"ETA {F['eta']}", False),
                ("isCalm() at the pin", str(s["isCalm"]).lower(), f"Tick {s['currentTick']:,} · TWAP {s['twapTick']:,}", True),
                ("Code change", "None", "setDeviation(int56) only", True)]
    if slug.startswith("ethena"):
        new = ops[0]["calls"][0]["args"]["_globalMaxMintPerBlock"]
        limits = [r for o in ops for c in o["calls"] for r in c.get("rateLimits", [])]
        cust = next(c for o in ops for c in o["calls"] if "custodian" in c)
        assert len({r["limit"]["to"] for r in limits}) == 1
        return [("Mint cap per block", f"{millions(d['minting']['globalMaxMintPerBlock'])} to {millions(new)} USDe",
                 f"Global + 8 assets · redeem {millions(d['minting']['globalMaxRedeemPerBlock'])} unchanged", True),
                ("Collateral", "USDm delisted", "removeSupportedAsset(USDm)", False),
                ("Bridge rate limits", f"{mstr(limits[0]['limit']['to'])} USDe / hour", " · ".join(f"eid {r['dstEid']} was {mstr(r['limit']['from'])}" for r in limits), False),
                ("New custodian", cust["custodian"]["kind"], "Not yet a custodian · check the owner", False)]
    if slug.startswith("etherfi-liquid"):
        calls = [c for o in ops for c in o["calls"]]
        cleared = [c for c in calls if int(c["root"]["to"], 16) == 0]
        kinds = sorted({s["kind"] for a, s in d["strategists"].items() if a not in d["managers"]})
        return [("Calls", f"{len(calls)} in one batch", f"setManageRoot on {len(d['managers'])} vaults", False),
                ("Timelock delay", F["delay"], f"ETA {F['eta']}", False),
                ("Roots replaced", f"{len(calls)} of {len(calls)} live", f"{len(cleared)} set to zero ({cleared[0]['vaultSymbol']})", False),
                ("Strategists", " + ".join(kinds), "plus the liquidUSD manager itself", False)]
    v = d["vaults"]
    top = max(d["strategies"], key=lambda s: s["newMaxDebt"] / 10 ** v[s["vault"]]["decimals"])
    return [("Calls", f"{len(ops[0]['calls'])} in one batch", f"{len(d['strategies'])} add_strategy + {len(d['strategies'])} max-debt caps", False),
            ("Timelock delay", F["delay"], f"ETA {F['eta']}", False),
            ("Largest cap", top["newMaxDebtUnits"], f"{v[top['vault']]['symbol']} holds {round2(v[top['vault']]['totalAssets']).split('.')[0]} {v[top['vault']]['assetSymbol']}", False),
            ("Default queue", "Not added", "add_to_queue = false", True)]


def state_lombard(b, item, bs, xa, E):
    d, out = b["decoded"], []
    tl = item["timelock"].lower()
    for u in d["upgrades"]:
        assert u["proxyAdminOwner"].lower() == tl and u["initCalldataBytes"] == 0
        cur, new, sd = u["currentImplementation"], u["newImplementation"], u["sourceDiff"]
        files = " · ".join(f'{os.path.basename(f["file"])} +{f["linesAdded"]} / -{f["linesRemoved"]}' for f in sd["projectFilesChanged"])
        lib = f'{sd["libraryFilesChanged"]} OpenZeppelin library files changed, {len(sd["filesAdded"])} added'
        abi = lambda xs: ", ".join(f'<code>{E(x.split(" ", 1)[1].split("(", 1)[0])}</code>' for x in xs) or "none"
        out += [f'<h3>{E(u["proxyName"])}</h3>', '<dl class="memo-meta">',
                f'<dt>Proxy</dt><dd>{xa(u["proxy"])}</dd>',
                f'<dt>ProxyAdmin</dt><dd>{xa(u["proxyAdmin"])} · OpenZeppelin {E(u["proxyAdminVersion"])} · owned by this timelock</dd>',
                f'<dt>Implementation now</dt><dd>{xa(cur["address"])} · {E(cur["sourcify"]["name"])} · Sourcify {E(cur["sourcify"]["match"])}</dd>',
                f'<dt>Queued implementation</dt><dd>{xa(new["address"])} · {E(new["sourcify"]["name"])} · Sourcify {E(new["sourcify"]["match"])} '
                f'(verified {E(new["sourcify"]["verifiedAt"][:10])})</dd>',
                '<dt>Initializer</dt><dd>None: upgradeAndCall with empty data</dd>',
                f'<dt>Source diff</dt><dd>{E(files)}; {E(lib)}</dd>',
                f'<dt>ABI added</dt><dd>{abi(sd["abiAdded"])}</dd>',
                f'<dt>ABI removed</dt><dd>{abi(sd["abiRemoved"])}</dd>', '</dl>']
    ar = d["assetRouter"]
    assert ar["depositFee(BTC.b) before the upgrade"] == "reverts"
    out.append(f'<p>At the pin, AssetRouter <code>depositMinAmount(BTC.b)</code> = {ar["depositMinAmount(BTC.b)"]:,} sats and '
               f'<code>depositFee(BTC.b)</code> reverts: the function only exists after the AssetRouter upgrade, which is why the BTC.b '
               f'upgrade must not execute first (see Risk Notes).</p>')
    return out


def state_beefy(b, item, bs, xa, E):
    s, new = b["decoded"]["strategy"], b["decoded"]["newMaxTickDeviation"]
    tl = item["timelock"].lower()
    assert s["owner"].lower() == tl and s["beaconOwnerOwner"]["address"].lower() == tl and s["beaconImplementation"]["sourcify"] is None
    disp = ", ".join(f"<code>{E(k)}</code>" for k, ok in s["implementationDispatches"].items() if ok)
    return ['<dl class="memo-meta">',
            f'<dt>Strategy</dt><dd>{xa(s["strategy"])} · beacon proxy · owned by this timelock</dd>',
            f'<dt>Vault</dt><dd>{xa(s["vault"])} · {E(s["vaultName"])} (<code>{E(s["vaultSymbol"])}</code>) · owner {xa(s["vaultOwner"])}</dd>',
            f'<dt>Pool</dt><dd>{xa(s["pool"])} · {E(s["token0Symbol"])} / {E(s["token1Symbol"])} on Aerodrome · tick spacing {s["poolTickSpacing"]}</dd>',
            f'<dt>maxTickDeviation</dt><dd>{s["maxTickDeviation"]} ticks now; {new} ticks once the operation executes</dd>',
            f'<dt>TWAP interval</dt><dd>{s["twapInterval"]} s · position width {s["positionWidth"]}</dd>',
            f'<dt>isCalm()</dt><dd>{str(s["isCalm"]).lower()} at the pin: tick {s["currentTick"]:,}, TWAP tick {s["twapTick"]:,} '
            f'({abs(s["currentTick"] - s["twapTick"])} tick{"" if abs(s["currentTick"] - s["twapTick"]) == 1 else "s"} apart)</dd>',
            f'<dt>Paused</dt><dd>{str(s["paused"]).lower()}</dd>',
            f'<dt>Beacon</dt><dd>{xa(s["eip1967Beacon"])} · {E(s["beaconVerified"]["sourcify"]["name"])} · Sourcify {E(s["beaconVerified"]["sourcify"]["match"])}</dd>',
            f'<dt>Beacon implementation</dt><dd>{xa(s["beaconImplementation"]["address"])} · not verified on Sourcify; {disp} are in its dispatch table</dd>',
            f'<dt>Beacon owner</dt><dd>{xa(s["beaconOwner"])} · {E(s["beaconOwnerVerified"]["sourcify"]["name"])} '
            f'(Sourcify {E(s["beaconOwnerVerified"]["sourcify"]["match"])}), owned by this timelock: implementation swaps also wait '
            f'{item["min_delay_seconds"]:,} s</dd>', '</dl>']


def state_ethena(b, item, bs, xa, E):
    d, ops = b["decoded"], b["operations"]
    tl = item["timelock"].lower()
    m = d["minting"]
    assert m["owner"].lower() == tl and d["oftAdapter"]["owner"].lower() == tl
    new = {c["args"]["asset"].lower(): c["args"]["_maxMintPerBlock"] for c in ops[0]["calls"] if "asset" in c["args"]}
    delisted = {c["args"]["asset"].lower() for o in ops for c in o["calls"] if c["function"].startswith("removeSupportedAsset")}
    rows = [f'<tr><td>Global</td><td>{millions(m["globalMaxMintPerBlock"])}</td><td>{millions(ops[0]["calls"][0]["args"]["_globalMaxMintPerBlock"])}</td>'
            f'<td>{millions(m["globalMaxRedeemPerBlock"])}</td></tr>']
    for a, v in d["assets"].items():
        assert v["isSupportedAsset"] and v["isActive"]
        q = millions(new[a]) + ("; then delisted" if a in delisted else "")
        rows.append(f'<tr><td>{xa(a, v["symbol"])}</td><td>{millions(v["maxMintPerBlock"])}</td><td>{E(q)}</td><td>{millions(v["maxRedeemPerBlock"])}</td></tr>')
    limits = [r for o in ops for c in o["calls"] for r in c.get("rateLimits", [])]
    lrows = [f'<tr><td>{r["dstEid"]}</td><td>{E(r["limit"]["from"])}</td><td>{E(r["limit"]["to"])}</td>'
             f'<td title="{E(r["amountInFlightAtPin"])}">{E(round2(r["amountInFlightAtPin"]).split(".")[0])}</td></tr>' for r in limits]
    cust = next(c for o in ops for c in o["calls"] if "custodian" in c)
    return ['<div class="card">',
            f'  <p>{xa(m["address"], "EthenaMinting")} (Sourcify {E(m["verified"]["sourcify"]["match"])}) and the '
            f'{xa(d["oftAdapter"]["address"], "USDe OFT adapter")} (Sourcify {E(d["oftAdapter"]["verified"]["sourcify"]["match"])}) are both owned by '
            f'this timelock. USDe amounts per block:</p>',
            '  <table><thead><tr><th>Asset</th><th>Mint cap now</th><th>Queued</th><th>Redeem cap</th></tr></thead>',
            '  <tbody>' + "".join(rows) + '</tbody></table>',
            '  <p>USDe OFT adapter (LayerZero) rate limits, USDe per hour:</p>',
            '  <table><thead><tr><th>Route (eid)</th><th>Limit now</th><th>Queued</th><th>In flight at the pin</th></tr></thead>',
            '  <tbody>' + "".join(lrows) + '</tbody></table>',
            f'  <p>Queued custodian {xa(cust["args"]["custodian"])}: an {E(cust["custodian"]["kind"])} with {cust["custodian"]["codeBytes"]} bytes of code, '
            f'isCustodianAddress = {str(cust["custodian"]["isCustodianAddress"]).lower()} at the pin. Minted collateral is routed to custodian '
            f'addresses, so check who controls it before the ETA.</p>', '</div>']


def state_yearn(b, item, bs, xa, E):
    d = b["decoded"]
    v = d["vaults"]
    roles = {tuple(x["timelockHolds"]) for x in v.values()}
    assert len(roles) == 1 and {x["timelockRoles"] for x in v.values()} == {143}
    assert all(s["currentParams"]["activation"] == 0 and s["strategyAsset"] == v[s["vault"]]["asset"] and not s["addToQueue"] for s in d["strategies"])
    srows = [f'<tr><td><b>{E(s["vaultSymbol"])}</b><br>{E(s["strategyName"])} {xa(s["strategy"])}</td><td>{E(s["newMaxDebtUnits"])}</td>'
             f'<td title="{E(s["strategyTotalAssets"])}">{E(round2(s["strategyTotalAssets"]))}</td></tr>' for s in d["strategies"]]
    vrows = [f'<tr><td>{xa(a, x["symbol"])}</td><td>{E(x["assetSymbol"])} · v{E(x["apiVersion"])}</td>'
             f'<td title="{E(x["totalAssets"])}">{E(round2(x["totalAssets"]))}</td></tr>' for a, x in v.items()]
    return ['<div class="card">',
            f'  <p>None of the {len(d["strategies"])} strategies is active today (activation = 0), each uses its vault\'s asset, and none joins '
            f'the default withdrawal queue.</p>',
            '  <table><thead><tr><th>Vault · strategy</th><th>New max debt</th><th>In strategy now</th></tr></thead>',
            '  <tbody>' + "".join(srows) + '</tbody></table>',
            '  <table><thead><tr><th>Vault</th><th>Asset · API</th><th>Total assets</th></tr></thead>',
            '  <tbody>' + "".join(vrows) + '</tbody></table>',
            f'  <p>On every vault this timelock holds {", ".join(f"<code>{E(r)}</code>" for r in sorted(next(iter(roles))))} '
            f'(roles bitmask 143), so execution needs no other role. Funds move only when a DEBT_MANAGER, which this timelock is not, '
            f'calls update_debt up to the new max debt.</p>', '</div>']


def state_etherfi_liquid(b, item, bs, xa, E):
    d, ops = b["decoded"], b["operations"]
    tl = item["timelock"].lower()
    p = d["proposer"]
    assert p["proposerIsSafe"] and p["executorIsSafe"] and not p["executorOpen"]
    mrows = []
    for m, v in d["managers"].items():
        assert int(v["owner"], 16) == 0 and v["timelockCanSetRoot"] and not v["isPaused"]
        mrows.append(f'<tr><td>{xa(v["vault"], v["vaultSymbol"])}<br>{E(v["vaultName"])}</td><td title="{E(v["totalSupply"])}">{E(round2(v["totalSupply"]))}</td>'
                     f'<td>{xa(m)} · Sourcify {E(v["verified"]["sourcify"]["match"])}</td><td>{xa(v["authority"])}</td></tr>')
    root = lambda h: f'<span class="addr" title="{E(h)}">{"zero" if int(h, 16) == 0 else E(h[:10] + "…" + h[-4:])}</span>'
    crows = [f'<tr><td>{E(c["vaultSymbol"])}</td><td>{xa(c["args"]["strategist"])}<br>{E(c["strategistKind"])}</td>'
             f'<td>{root(c["root"]["from"])}</td><td>{root(c["root"]["to"])}</td></tr>' for o in ops for c in o["calls"]]
    return ['<div class="card">',
            f'  <p>Each vault is run by a Veda ManagerWithMerkleVerification contract whose owner() is the zero address; its authority lets '
            f'{xa(tl, "this timelock")} call setManageRoot. None of the three managers is paused at the pin. Vault shares outstanding:</p>',
            '  <table><thead><tr><th>Vault</th><th>Shares (totalSupply)</th><th>Manager</th><th>Authority</th></tr></thead>',
            '  <tbody>' + "".join(mrows) + '</tbody></table>',
            '  <p>Strategist roots, live at the pin and queued:</p>',
            '  <table><thead><tr><th>Vault</th><th>Strategist</th><th>Root now</th><th>Queued root</th></tr></thead>',
            '  <tbody>' + "".join(crows) + '</tbody></table>',
            f'  <p>The batch was scheduled by the {p["threshold"]}-of-{p["owners"]} Safe {xa(p["address"])} (Safe {E(p["version"])}), which is this '
            f'timelock\'s proposer, canceller and executor; the executor role is not open to everyone.</p>', '</div>']


def state_lombard_fees(b, item, bs, xa, E):
    d, ops = b["decoded"], b["operations"]
    tl = item["timelock"].lower()
    r, p = d["router"], d["proposer"]
    assert r["defaultAdmin"].lower() == tl and r["owner"].lower() == tl and r["timelockIsDefaultAdmin"] and not r["timelockIsOperator"]
    assert p["proposerIsTxTo"] and p["executorIsTxTo"] and not p["executorOpen"]
    rows = []
    for o in ops:
        for c in o["calls"]:
            x = c["lombardChange"]
            tok = xa(x["token"], x["tokenSymbol"]) if x.get("token") else "Router-wide"
            rows.append(f'<tr><td><code>{E(x["parameter"])}</code></td><td>{tok}</td><td>{x["from"]:,} sats</td><td>{x["to"]:,} sats</td>'
                        f'<td>{E(x["meaning"])}</td></tr>')
    impl = r["implementation"]
    lo, hi = r["depositFeeOperatorRange"]
    return ['<div class="card">',
            f'  <p>{xa(r["address"], "AssetRouter")} runs implementation {xa(impl["address"])} ({E(impl["sourcify"]["name"])}, Sourcify '
            f'{E(impl["sourcify"]["match"])}). Its owner() and defaultAdmin() are {xa(tl, "this timelock")} (defaultAdminDelay '
            f'{r["defaultAdminDelay"]} s); an OPERATOR_ROLE holder may only set deposit fees from {lo:,} to {hi:,} sats. Amounts are in '
            f'satoshis (8 decimals).</p>',
            '  <table><thead><tr><th>Parameter</th><th>Token</th><th>Now</th><th>Queued</th><th>What it charges or limits</th></tr></thead>',
            '  <tbody>' + "".join(rows) + '</tbody></table>',
            f'  <p>The batch was scheduled by the {p["threshold"]}-of-{p["owners"]} Safe {xa(p["address"])} (Safe {E(p["version"])}), which is '
            f'this timelock\'s proposer, canceller and executor; the executor role is not open to everyone.</p>', '</div>']


def state_cap(b, item, bs, xa, E):
    d = b["decoded"]
    tl = item["timelock"].lower()
    u = d["upgrades"][0]
    cur, new, sd, auth = u["currentImplementation"], u["newImplementation"], u["sourceDiff"], u["upgradeAuthority"]
    assert u["proxyKind"] == "UUPS" and int(u["eip1967AdminSlot"], 16) == 0 and u["initCalldataBytes"] == 0
    assert [m["address"] for m in auth["members"]] == [tl] and new["proxiableUUID"].lower() == "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    files = " · ".join(f'{os.path.basename(f["file"])} +{f["linesAdded"]} / -{f["linesRemoved"]}' for f in sd["projectFilesChanged"])
    libs = ", ".join(os.path.basename(f) for f in sd["filesAdded"]) or "none"
    abi = lambda xs: ", ".join(f'<code>{E(x.split(" ", 1)[1].split("(", 1)[0])}</code>' for x in xs) or "none"
    beh = d["behaviour"]
    rows = "".join(f'<tr><td><code>{E(k)}</code></td><td>{" · ".join(xa(m["address"], m["name"]) for m in v["members"])}</td></tr>'
                   for k, v in d["roles"].items())
    return [f'<h3>{E(u["proxyName"])}</h3>', '<dl class="memo-meta">',
            f'<dt>Proxy</dt><dd>{xa(u["proxy"])} · UUPS (ERC-1967 admin slot empty)</dd>',
            f'<dt>Upgrade authority</dt><dd>_authorizeUpgrade checks Cap AccessControl {xa(auth["accessControl"])} role <code>bytes4(0)</code> on this '
            f'proxy; its only member is {xa(tl, "this timelock")}</dd>',
            f'<dt>Implementation now</dt><dd>{xa(cur["address"])} · {E(cur["sourcify"]["name"])} · Sourcify {E(cur["sourcify"]["match"])}</dd>',
            f'<dt>Queued implementation</dt><dd>{xa(new["address"])} · {E(new["sourcify"]["name"])} · Sourcify {E(new["sourcify"]["match"])} '
            f'(verified {E(new["sourcify"]["verifiedAt"][:10])}) · proxiableUUID = the ERC-1967 implementation slot</dd>',
            '<dt>Initializer</dt><dd>None: upgradeToAndCall with empty data</dd>',
            f'<dt>Source diff</dt><dd>{E(files)}; OpenZeppelin files added: {E(libs)}</dd>',
            f'<dt>ABI added</dt><dd>{abi(sd["abiAdded"])}</dd>',
            f'<dt>ABI removed</dt><dd>{abi(sd["abiRemoved"])}</dd>',
            f'<dt>Storage</dt><dd>{E(sd["storage"])}</dd>', '</dl>',
            '<div class="card">',
            f'  <p><strong>slash</strong>: today it {E(beh["slash"]["before"])}; after the upgrade it {E(beh["slash"]["after"])}.</p>',
            f'  <p><strong>completeSlash</strong>: {E(beh["completeSlash"])}.</p>',
            f'  <p><strong>distributeRewards</strong>: {E(beh["distributeRewards"])}. {E(beh["delegationDistributeRewards"])}.</p>',
            f'  <p><strong>registerStrategy</strong>: {E(beh["registerStrategy"])}.</p>',
            '  <p>Who may call the role-gated functions on this contract at the pin:</p>',
            '  <table><thead><tr><th>Function</th><th>Role members</th></tr></thead>',
            '  <tbody>' + rows + '</tbody></table>', '</div>']


def state_compound(b, item, bs, xa, xl, E):
    d = b["decoded"]
    ln, tl = d["linea"], item["timelock"].lower()
    pin, r, lt, cm, ms = ln["pinned_block"], ln["receiver"], ln["localTimelock"], ln["comet"], ln["l2MessageService"]
    assert r["govTimelock"].lower() == tl and r["localTimelock"] == lt["address"] and lt["admin"] == r["address"] and cm["governor"] == lt["address"]
    assert cm["baseToken"] == ln["weth"]["address"] and int(cm["getReservesWei"]) == int(ln["calls"][0]["args"]["amount"])
    eth = lambda w: f'{int(w) // 10**18:,}.{int(w) % 10**18:018d}'.rstrip("0").rstrip(".")
    lblock = f'<a href="{LINEA[1]}/block/{pin["block_number"]}" target="_blank" rel="noopener">#{pin["block_number"]:,}{bs.EXT}</a>'
    calls = []
    for c in ln["calls"]:
        fn = c["signature"].split("(", 1)[0]
        args = ", ".join(f'{E(k)} = {xl(v) if ADDR_RE.fullmatch(str(v)) else "<code>" + E(str(v)) + "</code>"}' for k, v in c["args"].items())
        what = {0: lambda: f'withdraws {E(c["amountEth"])} WETH of reserves to the Linea Timelock',
                1: lambda: f'unwraps {E(c["amountEth"])} WETH to ETH in the Linea Timelock',
                2: lambda: f'sends {E(c["valueEth"])} ETH (value) to {xa(c["args"]["_to"], "the Ethereum Timelock")} with a {E(c["feeEth"])} ETH fee'}[c["index"]]()
        name = {cm["address"]: f'{cm["name"]} ({cm["symbol"]})', ln["weth"]["address"]: ln["weth"]["symbol"], ms["address"]: "L2 MessageService"}[c["target"]]
        calls.append(f'    <li><code translate="no">{E(fn)}</code>({args}) on {xl(c["target"], name)} — {what}</li>')   # Linea-side calls (not timelock calls)
    return ['<div class="card">',
            f'  <p>Read at Linea finalized block {lblock} ({E(pin["block_time_utc"])}, block hash <span class="addr" title="{E(pin["block_hash"])}">'
            f'{E(bs.short(pin["block_hash"], 10, 6))}</span>) on {pin["rpcs_cross_checked"]} independent public Linea RPC endpoints that agreed '
            f'(Lineascan links; reproduce with <code>$LINEA_RPC_URL</code>).</p>',
            f'  <p>{xl(r["address"], r["name"])} accepts a message only from its govTimelock, {xa(r["govTimelock"], "this Ethereum Timelock")}, and '
            f'queues every call on its localTimelock {xl(lt["address"], "Linea Timelock")} (delay {E(dur(lt["delay"]))}, grace period '
            f'{E(dur(lt["GRACE_PERIOD"]))}), whose admin is the receiver. The queued calls, in order:</p>', '  <ol class="calls">'] + calls + [
            '  </ol>', '  <table><thead><tr><th>At the Linea pin</th><th>Value</th></tr></thead><tbody>',
            f'  <tr><td>{E(cm["name"])} ({E(cm["symbol"])}) reserves, getReserves()</td><td>{E(eth(cm["getReservesWei"]))} WETH</td></tr>',
            f'  <tr><td>Supplied (totalSupply) / borrowed (totalBorrow)</td><td>{E(eth(cm["totalSupplyWei"]))} / {E(eth(cm["totalBorrowWei"]))} WETH</td></tr>',
            f'  <tr><td>WETH held by the market</td><td>{E(eth(cm["wethBalanceWei"]))} WETH</td></tr>',
            f'  <tr><td>targetReserves()</td><td>{E(eth(cm["targetReservesWei"]))} WETH</td></tr>',
            f'  <tr><td>Linea Timelock ETH balance</td><td>{E(eth(lt["ethBalanceWei"]))} ETH</td></tr>',
            f'  <tr><td>L2 MessageService minimumFeeInWei</td><td>{E(eth(ms["minimumFeeInWei"]))} ETH</td></tr>',
            f'  <tr><td>L2 MessageService rate limit (limitInWei / period)</td><td>{E(eth(ms["limitInWei"]))} ETH per {E(dur(ms["periodInSeconds"]))}; '
            f'{E(eth(ms["currentPeriodAmountInWei"]))} ETH used in the current period</td></tr>',
            '  </tbody></table>', '</div>']


def state_lista(b, item, bs, xa, E):
    d = b["decoded"]
    tl = item["timelock"].lower()
    hub, ps, ms, p, mf = d["hub"], d["safes"]["pauser"], d["safes"]["manager"], d["proposer"], d["marketFactory"]
    assert p["proposerIsTxTo"] and p["executorIsTxTo"] and not p["executorOpen"] and hub["defaultAdmin"] == [tl] and not hub["liquidatorsListed"]
    out = []
    abi = lambda xs: ", ".join(f'<code>{E(x.split(" ", 1)[1].split("(", 1)[0])}</code>' for x in xs) or "none"
    for u in d["upgrades"]:
        cur, new, sd = u["currentImplementation"], u["newImplementation"], u["sourceDiff"]
        assert u["proxyKind"] == "UUPS" and int(u["eip1967AdminSlot"], 16) == 0 and u["initCalldataBytes"] == 0 and u["upgradeAuthority"]["timelockHoldsDefaultAdmin"]
        files = " · ".join(f'{os.path.basename(f["file"])} +{f["linesAdded"]} / -{f["linesRemoved"]}' for f in sd["projectFilesChanged"])
        out += [f'<h3>{E(u["proxyName"])}</h3>', '<dl class="memo-meta">',
                f'<dt>Proxy</dt><dd>{xa(u["proxy"])} · UUPS (ERC-1967 admin slot empty)</dd>',
                f'<dt>Upgrade authority</dt><dd>_authorizeUpgrade requires DEFAULT_ADMIN_ROLE, held by {xa(tl, "this timelock")}</dd>',
                f'<dt>Implementation now</dt><dd>{xa(cur["address"])} · {E(cur["sourcify"]["name"])} · Sourcify {E(cur["sourcify"]["match"])}</dd>',
                f'<dt>Queued implementation</dt><dd>{xa(new["address"])} · {E(new["sourcify"]["name"])} · Sourcify {E(new["sourcify"]["match"])} '
                f'(verified {E(new["sourcify"]["verifiedAt"][:10])}) · proxiableUUID = the ERC-1967 implementation slot</dd>',
                '<dt>Initializer</dt><dd>None: upgradeToAndCall with empty data</dd>',
                f'<dt>Source diff</dt><dd>{E(files)}; OpenZeppelin files added: {E(", ".join(os.path.basename(f) for f in sd["filesAdded"]) or "none")}</dd>',
                f'<dt>ABI added</dt><dd>{abi(sd["abiAdded"])}</dd>',
                f'<dt>Paused entry points</dt><dd>{", ".join(f"<code>{E(f)}</code>" for f in u["pausedFunctions"])}</dd>',
                f'<dt>Storage</dt><dd>{E(sd["storage"])}</dd>', '</dl>']
    rows = (f'<tr><td><code>PAUSER</code></td><td>nobody</td><td>{xa(ps["address"])} (Safe, {ps["threshold"]} of {ps["owners"]}) · '
            f'{xa(hub["address"], "EmergencySwitchHub")}</td><td>pause()</td></tr>'
            f'<tr><td><code>MANAGER</code></td><td>{xa(ms["address"])} (Safe, {ms["threshold"]} of {ms["owners"]}) · {xa(mf["address"], mf["implementationName"])} '
            f'proxy</td><td>adds {xa(hub["address"], "EmergencySwitchHub")}</td><td>unpause() and the admin setters</td></tr>'
            f'<tr><td><code>DEFAULT_ADMIN_ROLE</code></td><td>{xa(tl, "this timelock")}</td><td>unchanged</td><td>upgrades; grants PAUSER and MANAGER</td></tr>')
    out += ['<div class="card">',
            '  <p>Roles on each of the four liquidators (the same holders on all four at the pin):</p>',
            '  <table><thead><tr><th>Role</th><th>Held at the pin</th><th>After the batch</th><th>Gates</th></tr></thead>',
            '  <tbody>' + rows + '</tbody></table>',
            f'  <p>{xa(hub["address"], "EmergencySwitchHub")} (implementation {xa(hub["implementation"]["address"])}, Sourcify '
            f'{E(hub["implementation"]["sourcifyMatch"])}): DEFAULT_ADMIN_ROLE is {xa(tl, "this timelock")}, MANAGER the {ms["threshold"]}-of-{ms["owners"]} '
            f'Safe, PAUSER the {ps["threshold"]}-of-{ps["owners"]} Safe, and the hub\'s PAUSER role admin is {E(hub["pauserRoleAdmin"])}. Its '
            f'getPausableContracts() lists {hub["pausableContracts"]} contracts at the pin, none of them one of these liquidators.</p>',
            f'  <p>The batch was scheduled by the {p["threshold"]}-of-{p["owners"]} Safe {xa(p["address"])} (Safe {E(p["version"])}), which is this '
            f'timelock\'s proposer, canceller and executor; the executor role is not open to everyone. The operation id was re-derived on chain with '
            f'hashOperationBatch (salt {E(d["opIdRederived"]["salt"][-4:])}).</p>', '</div>']
    return out


def state_umia(b, item, bs, xa, E):
    d = b["decoded"]
    u = d["umia"]
    cur = u["current"]
    calls = b["operations"][0]["calls"]
    rows = []
    for up in d["upgrades"]:
        c0, n0 = up["currentImplementation"], up["newImplementation"]
        rows.append(f'<dt>{E(up["proxyName"])} implementation</dt><dd>{xa(c0["address"])} · Sourcify {E(c0["sourcify"]["match"])} to queued '
                    f'{xa(n0["address"])} · {E(n0["sourcify"]["name"])} · Sourcify {E(n0["sourcify"]["match"])} '
                    f'(verified {E(n0["sourcify"]["verifiedAt"][:10])}) · no initializer</dd>')
    for g, i, k in (("conditionalMarketOracle()", 2, "oracle"), ("defaultGovernanceExecutor()", 3, "executor"), ("lbpStrategyFactory()", 8, "factory")):
        rows.append(f'<dt><code>{E(g)}</code></dt><dd>{xa(cur[g])} to queued {xa(calls[i]["args"][k])}</dd>')
    for g, i, k in (("spotMigrator()", 4, "spotMigrator"), ("activeLiquidityKeeper()", 5, "keeper")):
        rows.append(f'<dt><code>{E(g)}</code></dt><dd>reverts on the current implementation to queued {xa(calls[i]["args"][k])}</dd>')
    for g, i, k, unit in (("launchAnchorBps()", 6, "bps", "bps"), ("launchActiveHalfWidthTicks()", 7, "ticks", "ticks")):
        rows.append(f'<dt><code>{E(g)}</code></dt><dd>reverts on the current implementation to queued {calls[i]["args"][k]:,} {unit}</dd>')
    cr = u["credit"]
    return [f'<h3>UmiaHub {xa(u["hub"], "UmiaHub")} and UmiaMarketCore {xa(u["marketCore"], "UmiaMarketCore")}</h3>', '<dl class="memo-meta">', *rows, '</dl>',
            '<div class="card">',
            f'  <p class="s">Research credit: this queued operation was reported by <a href="https://github.com/{E(cr["github"])}" target="_blank" '
            f'rel="noopener">@{E(cr["github"])}{bs.EXT}</a> in the {E(cr["entry"])} entry <a href="{E(cr["prUrl"])}" target="_blank" rel="noopener">'
            f'Fractal-Neurons/pacta#{cr["pr"]}{bs.EXT}</a>. Pacta re-read every value on this page at the pinned block on two RPC endpoints.</p>',
            '</div>']


STATE = {"umia-op-0x3d35": state_umia, "lombard-ops-0xceee-0x2f2a-0x6404": state_lombard, "beefy-base-op-0x3302": state_beefy,
         "ethena-ops-0xb028-0xca05-0x108e-0x070a": state_ethena, "yearn-v3-op-0x2a14": state_yearn,
         "etherfi-liquid-op-0xf0fb": state_etherfi_liquid, "lombard-op-0xd07f": state_lombard_fees,
         "cap-op-0x3397": state_cap, "compound-v3-op-0x86b4": state_compound, "lista-lending-op-0x21df": state_lista}
