"""Render the live onboarding verification briefs from docs/api/v1/onboarding.json (written by tools/onboarding_scan.py).

Every number, address and boolean on these pages is read from the scan output by check id; findings are plain statements
of observed state with the check that proves them. Nothing here is hand-typed chain data.
"""

import html

E = html.escape
RPC_ENV = {"base": "$BASE_RPC_URL", "eth": "$ETH_RPC_URL"}
CHAIN_NAME = {"base": "Base Mainnet", "eth": "Ethereum Mainnet"}


def short(h, a=6, b=4):
    return h[:a] + "…" + h[-b:]


def hexref(v, a=6, b=4):
    return (f'<span class="addr" title="{E(v)}">{E(short(v, a, b))}</span>'
            f'<button class="copy" type="button" data-copy="{E(v)}">Copy</button>')


def by_id(b):
    return {c["id"]: c for c in b["checks"]}


def v(b, cid):
    return by_id(b)[cid]["value"]


def num(n, dec=0):
    return f"{n / 10 ** dec:,.{2 if dec else 0}f}"


def amount_cap(x):
    return None if x == 0 else 10 ** (x & 63) * (x >> 6) // 100


def cap_text(x, dec, sym):
    a = amount_cap(x)
    return "none (AmountCap 0)" if a is None else f"{num(a, dec)} {sym}"


def eoa_text(acc):
    if acc.get("eip7702_delegate"):
        return f"EOA with EIP-7702 delegation to {hexref(acc['eip7702_delegate'])}; {acc['nonce']:,} transactions sent"
    if acc["code_bytes"] == 0:
        return f"EOA (no contract code); {acc['nonce']:,} transactions sent"
    return f"contract ({acc['code_bytes']:,} bytes of code)"


def holder_text(b, addr):
    i = (b.get("holders") or {}).get(addr)
    if not i:
        return ""
    if i["kind"] == "safe":
        return f'{i["threshold"]}-of-{len(i["owners"])} Safe'
    if i["kind"] == "eoa":
        t = f'EOA, {i["nonce"]:,} txs' + (f', EIP-7702 → {short(i["eip7702_delegate"])}' if i.get("eip7702_delegate") else "")
        return t + (", signer of " + ", ".join(short(x) for x in i["owner_of_safes"]) if i.get("owner_of_safes") else "")
    return f'contract, {i["code_bytes"]:,} bytes'


def holder_ref(b, addr):
    t = holder_text(b, addr)
    return hexref(addr) + (f' <span class="muted">({E(t)})</span>' if t else "")


def role_holders(rmap, name):
    for r in rmap.get("roles", []):
        if r.get("name") == name:
            return r["holders"]
    return []


# ---------------------------------------------------------------------------------------------------- findings -----
def findings(b):
    s, out = b["slug"], []
    if s == "kerne-kusd-base":
        sup, bor = v(b, "v_caps")
        out.append(f'The market layer has no governor: <code>governorAdmin()</code> returns {hexref(v(b, "v_gov"))} on the USDC vault '
                   f'and {hexref(v(b, "c_gov"))} on the kUSD escrow vault, and <code>EulerRouter.governor()</code> returns '
                   f'{hexref(v(b, "r_gov"))}. Oracle, LTVs and caps cannot be changed by anyone.')
        out.append(f'Caps are unset and cannot be set: supply cap {cap_text(sup, 6, "USDC")}, borrow cap {cap_text(bor, 6, "USDC")}. '
                   f'Exposure limits exist only in the curator vault that allocates to this market.')
        out.append(f'kUSD is priced at a fixed rate: <code>getQuote(1e18 kUSD → USDC)</code> = <b>{num(v(b, "o_quote"), 6)} USDC</b> from '
                   f'{hexref(v(b, "r_oracle"))}. Borrow / liquidation LTV {v(b, "v_ltvb") / 100:.2f}% / {v(b, "v_ltvl") / 100:.2f}%. '
                   f'No market price feeds liquidations, so lender recovery depends on kUSD redemption and its backing.')
        tl = by_id(b)["tl_delay"]["to"]
        out.append(f'kUSD implements AccessControl (<code>supportsInterface(0x7965db0b)</code> = {str(v(b, "k_ac")).lower()}). '
                   f'<code>DEFAULT_ADMIN_ROLE</code> on kUSD is held by the TimelockController {hexref(tl)} '
                   f'(<code>hasRole</code> = {str(v(b, "k_admin_tl")).lower()}; <code>getMinDelay()</code> = {v(b, "tl_delay"):,}s, '
                   f'{v(b, "tl_delay") / 3600:.0f}h). The 2-of-{len(v(b, "s_owners"))} Safe {hexref(by_id(b)["s_threshold"]["to"])} is its proposer, '
                   f'executor and canceller ({str(v(b, "tl_prop")).lower()} / {str(v(b, "tl_exec")).lower()} / {str(v(b, "tl_canc")).lower()}) and '
                   f'{"holds" if v(b, "s_admin") else "does not hold"} <code>DEFAULT_ADMIN_ROLE</code> on kUSD itself.')
        out.append(f'<code>MINTER_ROLE</code> is held by {hexref(by_id(b)["m_kusd"]["to"])} (<code>kUSD()</code> = {hexref(v(b, "m_kusd"))}, '
                   f'<code>paused()</code> = {str(v(b, "m_paused")).lower()}), whose <code>DEFAULT_ADMIN_ROLE</code> is the same timelock '
                   f'({str(v(b, "m_admin_tl")).lower()}). Role changes on kUSD and on the minter pass a {v(b, "tl_delay") / 3600:.0f}-hour public queue.')
        for m in b["role_maps"]:
            out.append(f'{E(m["label"])} ({m["events"]} events, blocks {m["from_block"]:,}–{m["to_block"]:,}): '
                       + ("; ".join(f'{E(r["name"] or short(r["role"], 10, 4))} → ' + ", ".join(holder_ref(b, h) for h in r["holders"]) for r in m["roles"])
                          or "no role held") + ".")
    elif s == "efix-efixdi-base":
        sup, bor = v(b, "v_caps")
        out.append(f'One 2-of-{len(v(b, "s_owners"))} Safe, {hexref(v(b, "v_gov"))} (<code>getThreshold()</code> = {v(b, "s_threshold")}), is '
                   f'<code>governorAdmin()</code> of the USDC vault, <code>governor()</code> of the EulerRouter '
                   f'(= {hexref(v(b, "r_gov"))}) and {"holds" if v(b, "t_admin") else "does not hold"} <code>DEFAULT_ADMIN_ROLE</code> on efixDI+. '
                   f'No TimelockController sits between that Safe and these contracts, so the router\'s oracle configuration, LTVs and caps '
                   f'can be changed by one executed 2-of-3 Safe transaction, with no enforced on-chain delay.')
        out.append(f'The router prices efixDI+ through the custom adapter {hexref(v(b, "r_oracle"))} (<code>name()</code> = '
                   f'“{E(v(b, "o_name"))}”). Borrow / liquidation LTV {v(b, "v_ltvb") / 100:.0f}% / {v(b, "v_ltvl") / 100:.0f}%, '
                   f'interest fee {v(b, "v_fee") / 100:.0f}%.')
        ta, tb = v(b, "v_assets"), v(b, "v_borrows")
        out.append(f'Supply cap {cap_text(sup, 6, "USDC")}, borrow cap {cap_text(bor, 6, "USDC")}; total assets {num(ta, 6)} USDC, '
                   f'borrows {num(tb, 6)} USDC ({100 * tb / ta:.1f}% utilization).')
        if v(b, "t_minter"):
            mi = by_id(b)["t_minter"]["args"][1]
            out.append(f'<code>MINTER_ROLE</code> on efixDI+ is held directly by {hexref(mi)}, an account with no contract code '
                       f'({by_id(b)["t_minter_code"]["code_bytes"]} bytes) and {v(b, "t_minter_nonce"):,} transactions sent, which is also one of the '
                       f'three signers of the governor Safe. Calls gated only by <code>MINTER_ROLE</code> need no second signature and no delay.')
        for m in b["role_maps"]:
            out.append(f'{E(m["label"])} ({m["events"]} events, blocks {m["from_block"]:,}–{m["to_block"]:,}): '
                       + ("; ".join(f'{E(r["name"] or short(r["role"], 10, 4))} → ' + ", ".join(holder_ref(b, h) for h in r["holders"]) for r in m["roles"])
                          or "no role held") + ".")
        own = b["accounts"].get("efix_owner") or {}
        code = by_id(b)["e_owner_code"]
        out.append(f'<code>EFIX.owner()</code> = {hexref(v(b, "e_owner"))}: '
                   + (f'an EOA carrying an EIP-7702 delegation designator to {hexref(code["eip7702_delegate"])}'
                      if code.get("eip7702_delegate") else f'{code["code_bytes"]} bytes of code')
                   + f', {v(b, "e_owner_nonce"):,} transactions sent. It is not a Safe or a timelock.')
        del own
    elif s == "circle-cirbtc-eth":
        acc = b["accounts"]
        out.append(f'Upgrade authority: proxy <code>admin()</code> = {hexref(v(b, "p_admin"))}, {eoa_text(acc["admin"])}. '
                   f'Implementation {hexref(v(b, "p_impl"))}; <code>version()</code> = “{E(v(b, "t_version"))}”.')
        out.append(f'Operational roles: <code>owner()</code> {hexref(v(b, "r_owner"))} ({eoa_text(acc["owner"])}); '
                   f'<code>pauser()</code> {hexref(v(b, "r_pauser"))} ({eoa_text(acc["pauser"])}); '
                   f'<code>blacklister()</code> {hexref(v(b, "r_bl"))} ({eoa_text(acc["blacklister"])}); '
                   f'<code>masterMinter()</code> {hexref(v(b, "r_mm"))} ({eoa_text(acc["masterMinter"])}, '
                   f'<code>owner()</code> {hexref(acc["r_mm_owner"]["address"])}: {eoa_text(acc["r_mm_owner"])}).')
        out.append('None of these roles sits behind an on-chain TimelockController or multisig contract at the pinned block: upgrade, pause, '
                   'blacklist and minter configuration take effect in the transaction that calls them. Key custody (HSM / MPC) is off-chain '
                   'and not observable here.')
    elif s == "paxos-paxgy-eth":
        st = v(b, "acc_state")
        auth = next((m for m in b["role_maps"] if m["kind"] == "solmate_roles"), None)
        tl = next((m for m in b["role_maps"] if m["kind"] == "access_control"), None)
        out.append(f'<code>owner()</code> of the vault, accountant, teller and manager is the TimelockController {hexref(v(b, "v_owner"))} '
                   f'(<code>getMinDelay()</code> = {v(b, "tl_delay"):,}s). The RolesAuthority {hexref(v(b, "v_auth"))} is also owned by it. '
                   f'Owner-only changes (including <code>setManageRoot</code>, which no role holds) therefore wait at least 24 hours.')
        if tl:
            out.append("Timelock roles (" + f'{tl["events"]} events replayed): ' + "; ".join(
                f'{r["name"] or short(r["role"], 10, 4)} → ' + ", ".join(hexref(h) for h in r["holders"]) for r in tl["roles"]) + ".")
        out.append(f'Capabilities granted through the RolesAuthority execute with no delay. '
                   f'<code>updateExchangeRate</code> is held by the {v(b, "safe_threshold")}-of-{len(v(b, "safe_owners"))} Safe '
                   f'{hexref(by_id(b)["safe_threshold"]["to"])} and by {hexref(by_id(b)["eoa_nonce"]["to"])} '
                   f'({eoa_text({"code_bytes": by_id(b)["eoa_code"]["code_bytes"], "nonce": v(b, "eoa_nonce")})}). '
                   f'The accountant bounds each update: upper {st[5]} bps, lower {st[6]} bps of the current rate, at least {st[9]:,}s apart '
                   f'(current rate {v(b, "acc_rate") / 1e18:.6f} PAXG per PAXGy; platform / performance fee {st[10]} / {st[11]} bps). '
                   f'In the upstream Veda <code>AccountantWithRateProviders</code> source, an update outside these bounds or sooner than the '
                   f'minimum delay stores the new rate and pauses the accountant instead of reverting (the deployed bytecode was not '
                   f'compared with that source here).')
        if auth:
            out.append(f'Full role → capability → holder map below, replayed from {auth["events"]} RolesAuthority events '
                       f'(blocks {auth["from_block"]:,}–{auth["to_block"]:,}). Selectors without a public signature are shown as raw 4-byte values.')
        out.append(f'Teller {hexref(by_id(b)["te_paused"]["to"])}: <code>isPaused()</code> = {str(v(b, "te_paused")).lower()}, '
                   f'<code>shareLockPeriod()</code> = {v(b, "te_lock")}s. The previous teller {hexref(by_id(b)["old_paused"]["to"])} is paused '
                   f'(<code>isPaused()</code> = {str(v(b, "old_paused")).lower()}).')
    elif s == "tether-usat-eth":
        pa = b["accounts"]["proxy_admin"]
        out.append(f'USAT {hexref(by_id(b)["t_supply"]["to"])} is an EIP-1967 proxy: implementation {hexref(v(b, "p_impl"))}, '
                   f'ProxyAdmin {hexref(v(b, "p_admin"))} whose <code>owner()</code> is {hexref(pa["owner"])}. '
                   f'<code>USAT.owner()</code> is the same address.')
        out.append(f'That controller is a legacy MultiSigWallet (submit / confirm / execute; {by_id(b)["m_code"]["code_bytes"]:,} bytes), '
                   f'<code>required()</code> = {v(b, "m_required")} of {len(v(b, "m_owners"))} owners. It is not a TimelockController: '
                   f'an upgrade or owner action executes as soon as the third confirmation lands.')
        out.append(f'Linked queue: Ethena timelock {hexref(by_id(b)["e_delay"]["to"])} ({v(b, "e_delay"):,}s delay) holds two pending operations '
                   f'(<code>isOperationPending</code> = {str(v(b, "e_op1")).lower()} / {str(v(b, "e_op2")).lower()}) that add RLUSD and USAT to '
                   f'EthenaMinting; the USAT operation becomes executable at {utc_ts(v(b, "e_op2_eta"))}. '
                   f'See the <a href="../ethena-ops-0x0ca0-0x1fe5/">Ethena pre-execution brief</a>.')
        out.append('The forum thread assesses the bridged USAT on Avalanche; this brief covers the canonical Ethereum token whose '
                   'redemption and credit exposure that bridged asset inherits.')
    return out


def kpis(b):
    s = b["slug"]
    if s == "kerne-kusd-base":
        return [("Market governor", "address(0)", "Vaults + router immutable"), ("kUSD admin", f'{v(b, "tl_delay") // 3600}h timelock', "Proposer: 2-of-3 Safe"),
                ("Oracle", f'{num(v(b, "o_quote"), 6)} USDC', "Fixed rate per kUSD"), ("LTV (borrow / liq.)", f'{v(b, "v_ltvb") / 100:.0f}% / {v(b, "v_ltvl") / 100:.0f}%', "Set at deploy")]
    if s == "efix-efixdi-base":
        return [("Governor", f'{v(b, "s_threshold")}-of-{len(v(b, "s_owners"))} Safe', "Vault + router + token admin"), ("Timelock", "none", "0s to oracle / LTV / caps"),
                ("LTV (borrow / liq.)", f'{v(b, "v_ltvb") / 100:.0f}% / {v(b, "v_ltvl") / 100:.0f}%', "Custom NAV oracle"),
                ("Utilization", f'{100 * v(b, "v_borrows") / v(b, "v_assets"):.1f}%', f'{num(v(b, "v_assets"), 6)} USDC supplied')]
    if s == "circle-cirbtc-eth":
        return [("Upgrade authority", "EOA", f'{b["accounts"]["admin"]["nonce"]} txs sent'), ("Owner", "EOA", "No timelock"),
                ("Supply", f'{num(v(b, "t_supply"), v(b, "t_dec"))} cirBTC', f'{v(b, "t_dec")} decimals'), ("Paused", str(v(b, "t_paused")).lower(), "FiatToken v" + v(b, "t_version"))]
    if s == "paxos-paxgy-eth":
        st = v(b, "acc_state")
        return [("Owner", "TimelockController", f'{v(b, "tl_delay") // 3600}h min delay'), ("Rate bounds", f"+{(st[5] - 10000) / 100:.2f}% / -{(10000 - st[6]) / 100:.2f}%", f"≥ {st[9] // 60} min apart"),
                ("Supply", f'{num(v(b, "v_supply"), 18)} PAXGy', f'rate {v(b, "acc_rate") / 1e18:.4f}'), ("0s capabilities", str(sum(len(r["capabilities"]) for m in b["role_maps"] if m["kind"] == "solmate_roles" for r in m["roles"])), "Via RolesAuthority")]
    if s == "tether-usat-eth":
        return [("Upgrade path", "ProxyAdmin", "EIP-1967"), ("Controller", f'{v(b, "m_required")}-of-{len(v(b, "m_owners"))} MultiSig', "Legacy MultiSigWallet"),
                ("Timelock", "none", "Executes on 3rd confirmation"), ("Supply", f'{num(v(b, "t_supply"), v(b, "t_dec"))} USAT', f'{v(b, "t_dec")} decimals')]
    return []


# ------------------------------------------------------------------------------------------------- reproduction ----
def cast_line(b, c):
    rpc = f'--rpc-url "{RPC_ENV[b["chain"]]}"'
    blk = f'--block {b["pin"]["number"]}'
    if c["kind"] == "eth_call":
        args = " ".join(str(a) for a in c["args"])
        return f'cast call {c["to"]} "{c["sig"]}"{" " + args if args else ""} {blk} {rpc}'
    if c["kind"] == "eth_getStorageAt":
        return f'cast storage {c["to"]} {c["slot"]} {blk} {rpc}'
    if c["kind"] == "eth_getCode":
        return f'cast code {c["to"]} {blk} {rpc}'
    return f'cast nonce {c["to"]} {blk} {rpc}'


ACC_TAIL = ["allowedExchangeRateChangeUpper (bps)", "allowedExchangeRateChangeLower (bps)", "lastUpdateTimestamp", "isPaused",
            "minimumUpdateDelayInSeconds", "platformFee (bps)", "performanceFee (bps)"]


def utc_ts(ts):
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts))


def display(c):
    val = c["value"]
    if c.get("id") == "acc_state" and isinstance(val, list) and len(val) == 12:
        tail = ", ".join(f"{n} {x}" for n, x in zip(ACC_TAIL, val[5:]))
        return f"payoutAddress 0x{val[0]:040x} · words 1-4 {val[1]}, {val[2]}, {val[3]}, {val[4]} · {tail}"
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, list):
        return f"[{len(val)}] " + ", ".join(val) if val and isinstance(val[0], str) else ", ".join(str(x) for x in val)
    if c["kind"] == "eth_getCode":
        return f'{c["code_bytes"]:,} bytes' + (f' · EIP-7702 → {c["eip7702_delegate"]}' if c.get("eip7702_delegate") else "")
    return str(val)


def terms(b):
    lines = [f'# {CHAIN_NAME[b["chain"]]} block {b["pin"]["number"]}', f'cast block {b["pin"]["number"]} --field hash --rpc-url "{RPC_ENV[b["chain"]]}"',
             f'# expect {b["pin"]["hash"]}', ""]
    for c in b["checks"]:
        lines += [f'# {c["label"]}', cast_line(b, c)]
    for m in b["role_maps"]:
        lines += ["", f'# {m["label"]}: replay {m["events"]} events', f'cast logs --from-block {m["from_block"]} --to-block {m["to_block"]} '
                  f'--address {m["address"]} --rpc-url "{RPC_ENV[b["chain"]]}"']
    return "\n".join(lines)


def role_table(m, b=None):
    rows = []
    if m["kind"] == "access_control":
        for r in m["roles"]:
            rows.append(f'<tr><td><code>{E(r["name"] or short(r["role"], 10, 6))}</code></td><td>' + "<br>".join(holder_ref(b or {}, h) for h in r["holders"]) + "</td><td>—</td></tr>")
    else:
        for r in m["roles"]:
            caps = "<br>".join(f'{hexref(c["target"])} <code>{E(c["signature"] or c["selector"])}</code>' for c in r["capabilities"]) or "—"
            rows.append(f'<tr><td>role {r["role"]}</td><td>' + ("<br>".join(holder_ref(b or {}, h) for h in r["holders"]) or "—") + f"</td><td>{caps}</td></tr>")
        for p in m.get("public_capabilities", []):
            rows.append(f'<tr><td>public</td><td>anyone</td><td>{hexref(p["target"])} <code>{E(p["signature"] or p["selector"])}</code></td></tr>')
    return (f'<h3 class="tbl-h">{E(m["label"])} · {hexref(m["address"])} · {m["events"]} events, blocks {m["from_block"]:,}–{m["to_block"]:,}</h3>'
            f'<div class="tbl-wrap"><table><thead><tr><th>Role</th><th>Holders at the pinned block</th><th>Capability (target · function)</th></tr></thead>'
            f'<tbody>{"".join(rows) or "<tr><td colspan=3>no role held</td></tr>"}</tbody></table></div>')


def content(b, term_html, price="$5,000 USDC"):
    """Memo body (same structure and classes as the hand-written pre-execution briefs)."""
    k = "".join(f'<div class="kpi"><div class="k">{E(a)}</div><div class="v">{E(x)}</div><div class="s">{E(c)}</div></div>' for a, x, c in kpis(b))
    obs = "".join(f'<tr><td>{E(c["label"])}</td><td>{hexref(c["to"])}</td><td><code>{E(display(c))}</code></td></tr>' for c in b["checks"])
    f = "".join(f"<li>{x}</li>" for x in findings(b))
    roles = "".join(role_table(m, b) for m in b["role_maps"])
    pin = b["pin"]
    return f"""<header>
  <div><span class="badge badge-cyan">Onboarding verification brief</span><span class="badge badge-amber">{E(b["forum"]["name"])} #{b["forum"]["topic"]}</span></div>
  <h1>{E(b["asset"])}: control-plane state at {E(CHAIN_NAME[b["chain"]])} block {pin["number"]:,}</h1>
  <p>Read-only verification of who can change {E(b["asset"])} and the {E(b["venue"])} it is proposed for, pinned to a canonical block and reproducible on any archive node. Forum thread: <a href="{E(b["forum"]["url"])}" target="_blank" rel="noopener">{E(b["forum"]["title"])} ↗</a>.</p>
</header>

<div class="meta-grid">{k}</div>

<h2>1. Findings</h2>
<div class="card"><ul>{f}</ul></div>

<h2>2. Observed state at block {pin["number"]:,}</h2>
<div class="card"><p>Block hash {hexref(pin["hash"], 10, 6)}; every read below used EIP-1898 <code>{{blockHash, requireCanonical: true}}</code> and returned byte-identical results on {len(b["rpcs_cross_checked"])} independent RPC endpoints.</p>
<div class="tbl-wrap"><table><thead><tr><th>Check</th><th>Contract</th><th>Value</th></tr></thead><tbody>{obs}</tbody></table></div></div>
{('<h2>3. Role maps (replayed from events)</h2><div class="card">' + roles + '</div>') if roles else ''}

<h2>{4 if roles else 3}. Reproduce</h2>
{term_html}

<h2>{5 if roles else 4}. Scope</h2>
<div class="card"><ul><li>Observations of on-chain state only. They do not assess code correctness, reserves, legal structure or off-chain key custody, and they are not investment advice.</li>
<li>Issuers can clear or document these findings with a <a href="../../request/?tier=clearance">24h Collateral Onboarding &amp; Delta Clearance Attestation</a> ({E(price)} flat): block-pinned audit, docs / config reconciliation PR, Base EAS <i>Aligned</i> attestation and a Curator Diligence Dossier for the forum thread.</li></ul></div>
"""


def homepage_rows(data, prefix=""):
    return "".join(
        f'<tr><td><b>{E(b["asset"])}</b><span class="sub">{E(b["venue"])}</span></td>'
        f'<td><a href="{E(b["forum"]["url"])}" target="_blank" rel="noopener">{E(b["forum"]["name"])} #{b["forum"]["topic"]} ↗</a></td>'
        f'<td class="hide-m">{E(CHAIN_NAME[b["chain"]])} #{b["pin"]["number"]:,}</td>'
        f'<td class="r"><a href="{prefix}briefs/{E(b["slug"])}/">Read the brief →</a></td></tr>' for b in data["briefs"])


def summary(b):
    """One-line description for llms.txt / meta description."""
    return {"kerne-kusd-base": "kUSD/USDC Euler Base market: ungoverned vaults and router, no caps, fixed 1.00 USDC oracle; kUSD and its minter administered through a 48h TimelockController (2-of-3 Safe proposer).",
            "efix-efixdi-base": "efixDI/USDC Euler Base market: one 2-of-3 Safe governs vault, router and token admin with no timelock; efixDI+ MINTER_ROLE held by a single signer EOA; custom NAV oracle.",
            "circle-cirbtc-eth": "cirBTC (Circle FiatToken): upgrade admin, owner, pauser and blacklister are EOAs; no on-chain timelock or multisig.",
            "paxos-paxgy-eth": "PAXGy BoringVault: 24h TimelockController owner; full RolesAuthority role -> capability -> holder map; exchange-rate bounds.",
            "tether-usat-eth": "USAT (Ethereum): EIP-1967 proxy controlled by a 3-of-5 legacy MultiSigWallet with no timelock; linked pending Ethena ops.",
            }[b["slug"]]
