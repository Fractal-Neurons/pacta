"""Protocol scorecards (Website Edge v3): one canonical grade per protocol and a deterministic 5-factor control-plane rosette.

Every value is derived at build time from Pacta's published records only: index.json (Base-EAS-attested Sprint records) and
rpc-pinned.json (RPC-observed records), their onchain_observed evidence text and structured fields (observed_delay_seconds,
is_eip1967_proxy, safe_quorum), plus tools/graph_controller_facts.json. No value is entered by hand. A factor that the published
evidence does not decide is "Not determined" (a hollow slice), never a guess; slice 5 is "Uncompared" (hollow) for every
RPC-observed protocol, whose documentation Pacta has not assessed.

Grades (protocol level): DELTA (any parameter_delta record), UNRESOLVED (a protocol tools/scorecard_corrections.json marks
"unresolved": the chain state is pinned, but a breach of a documented commitment is not established; neither DELTA nor ALIGNED),
PROTECTIVE (no parameter delta, at least one protective_delta), ALIGNED (every record an aligned baseline), OBSERVED (RPC-pinned only). A protocol whose record carries "reconciledFrom" provenance
(a former delta reconciled at a later attested block) is ALIGNED with the "Reconciled" sub-pill and a before / after trail."""
import re

GRADES = {"delta": ("DELTA", "Docs and chain differ"), "unresolved": ("UNRESOLVED", "Observed on chain; document breach not established"),
          "protective": ("PROTECTIVE", "Chain stronger than documented"),
          "aligned": ("ALIGNED", "Docs and chain match"), "observed": ("OBSERVED", "Chain pinned; docs not assessed")}
FACTORS = [("upgrade", "Upgradeability"), ("timelock", "Timelock floor"), ("quorum", "Signer quorum"),
           ("emergency", "Emergency / freeze scope"), ("parity", "Docs-vs-chain parity")]
STATE_LABEL = {"g": "Strong", "b": "Moderate", "a": "Weak", "n": "Not determined", "u": "Uncompared"}
DAY = 86400

_NOF = re.compile(r"\b(\d{1,2})-of-(\d{1,2})\b")
_DELAY = re.compile(r"\b(?:getMinDelay\(\)|delay\(\)|MINIMUM_DELAY\(\)|MIN_DELAY\(\)|minDelay\(\)|executionDelay\(\)|TIMELOCK_PERIOD\(\)|"
                    r"timelockDelay\(\)|getMinimumDelay\(\))\s*(?:returns\s*|=\s*)([\d,]+)\s*s\b")
_SINGLE = re.compile(r"no contract code|externally owned|\bEOA\b|\(no code\)|without code")
_GOVERNOR = re.compile(r"\bGovernor(?:Bravo|Alpha|Omega)?\b|\bDAO governance\b")
_PROXY = re.compile(r"EIP-1967 (?:admin|implementation) (?:slot )?(?:=|resolves|is)|ProxyAdmin|AdminUpgradeabilityProxy|"
                    r"TransparentUpgradeableProxy|ERC-1967 prox|UUPS|zeppelinos\.proxy\.admin|upgradeTo")
_IMMUTABLE = re.compile(r"\bimmutable\b|ownership renounced|owner\(\) = 0x0\b|not a proxy|no proxies")   # zero EIP-1967 slots alone is not immutability
_BYPASS_EXEC = re.compile(r"(?:bypasserExecuteBatch|executeOperatorProposal)[^;]*\b(?:immediately|no delay)\b|"
                          r"\b(?:immediately|no delay)\b[^;]*(?:bypasserExecuteBatch|executeOperatorProposal)", re.I)
# an operator that can only execute proposals governance already approved (AxelarServiceGovernance.executeOperatorProposal reverts
# NotApproved otherwise) cannot originate a change: its key is an execution route (scored as the timelock floor), not a controlling quorum
_OPERATOR_EXEC = re.compile(r"executeOperatorProposal[^;]*\bapproved\b|\bapproved\b[^;]*executeOperatorProposal", re.I)
_GETTER_EQ = re.compile(r"\b(\w+)\(\)\s*=")          # "operator() =", "owner() =", "pauser() =": the relation a value belongs to


def _operator_key(text, pos):
    """True when the single-key match at pos belongs to the approved-proposal executor relation itself: inside a clause that
    states the executeOperatorProposal-approved route, the nearest getter assignment before the match is operator(). Any other
    holder in the same clause (owner() = EOA, pauser() = EOA, ...) keeps counting as a single key."""
    for a, b in clause_spans(text):
        if a <= pos < b:
            if not _OPERATOR_EXEC.search(text[a:b]):
                return False
            gs = list(_GETTER_EQ.finditer(text, a, pos))
            return bool(gs) and gs[-1].group(1) == "operator"
    return False
_COOLDOWN = re.compile(r"cooldown|unstak|withdraw|unbond|redemption|redeem|claim|lockup", re.I)   # user exit delays, not admin timelocks
_NODELAY = re.compile(r"no timelock")
_BYPASS = re.compile(r"\b1-of-\d{1,2}\b[^;]*?\b(?:shared between|co-owned by|jointly owned by)\b[^;]*?\bTimelock", re.I)
_SAME_TL = re.compile(r"\bthe same (?:Timelock|timelock|TimelockController)\b")
_TLWORD = re.compile(r"timelock", re.I)
_SAFE_DIRECT = re.compile(r"(?:owner\(\)|getAdmin\(\))\s*(?:=|is)\s*(?:the\s+)?(?:[\w-]+\s+){0,2}?Safe\b")
_ADDR = re.compile(r"0x[0-9a-fA-F]{40}")
_PROXY_ADMIN = re.compile(r"ProxyAdmin\s*\(?(0x[0-9a-fA-F]{40})")
_THAT = re.compile(r"(?:that|this|the same) (?:Safe|multisig|address)\b", re.I)
_ADDR_DELAY = re.compile(r"(0x[0-9a-fA-F]{40})[^;0-9]{0,40}?(?:(?:getMinDelay\(\)|delay\(\))\s*(?:returns\s*|=\s*)|minimum delay\s+)([\d,]+)\s*s?\b")
_W = r"(?:(?!0x[0-9a-fA-F]{40})[\w-]+\s+){0,3}?"   # up to 3 label words, never an address
# an address bound as the owner / admin / controller in the clause itself (never a context address)
_BOUND = re.compile(r"(?:owner\(\)|admin\(\)|getAdmin\(\)|governance\(\)|EIP-1967 admin(?: slot)?|admin slot[^=;]{0,60}?)\s*(?:=|is|returns|resolves? to|to)\s*"
                    r"(?:the\s+)?" + _W + r"\(?(0x[0-9a-fA-F]{40})"
                    r"|\b(?:owned by|governed by|behind|held by|resolves? to)\s+(?:the\s+)?" + _W + r"\(?(0x[0-9a-fA-F]{40})")
_ONLY = re.compile(r"\bonly(Admin|Owner)\b")
_SUBJECT_OWNS = re.compile(r"^(?:it owns|owner of)\b|\bit owns\b")   # the record's own subject owns the ProxyAdmin
_DEFINITE = re.compile(r"\b(?:held by|are|is|owned by|=)\s+the ((?:[A-Za-z]+ )?(?:Timelock|timelock)(?:Controller)?)\b")
_NAMED = re.compile(r"\b([A-Za-z]\w*)(?:\(\))?\s*(?:=\s*)?\(?(0x[0-9a-fA-F]{40})")
_WRAPPER = re.compile(r"\b1-of-(\d{1,2})\b([^;]*?)\b(?:shared between|co-owned by|jointly owned by)\b([^;]*)")
_EMERGENCY = re.compile(r"\bpause|\bblacklist|\bfreez|PAUSE_ROLE|ASSET_PROTECTION|\bdeprecate|\bguardian\b|pauseGuardian", re.I)


UNRESOLVED_PARITY = "Observed onchain state pinned; a breach of a documented commitment is not established"


def grade(classifications, easattested, reconciled=False, slug=None):
    if not easattested:
        return "observed"
    if slug is not None:
        import scorecard_corrections as CORR
        if CORR.unresolved(slug):
            return "unresolved"
    cl = set(classifications)
    if "parameter_delta" in cl:
        return "delta"
    if "protective_delta" in cl:
        return "protective"
    return "aligned"


def _snip(text, m, width=70):
    """A window around the match that starts and ends on whole words (never inside a 0x value or a word; V8)."""
    a, b = max(0, m.start() - width // 2), min(len(text), m.end() + width // 2)
    while a > 0 and not text[a - 1].isspace():
        a -= 1
    while b < len(text) and not text[b].isspace():
        b += 1
    return ("… " if a else "") + text[a:b].strip() + (" …" if b < len(text) else "")


def clauses(text):
    """Split evidence text into clauses on top-level ';' (a ';' inside parentheses stays in its clause)."""
    out, depth, cur = [], 0, []
    for ch in text:
        depth += (ch == "(") - (ch == ")") if ch in "()" else 0
        if ch == ";" and depth <= 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur).strip())
    return [c for c in out if c]


def clause_spans(text):
    """(start, end) offsets of the clauses() split (same top-level ';' rule), so a match can be located in its own clause."""
    spans, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        depth += (ch == "(") - (ch == ")") if ch in "()" else 0
        if ch == ";" and depth <= 0:
            spans.append((start, i))
            start = i + 1
    spans.append((start, len(text)))
    return spans


def _admin_delay(r):
    """A record's observed_delay_seconds when it is an admin / governance execution delay (never a user cooldown)."""
    d = r.get("observed_delay_seconds")
    if not isinstance(d, int):
        return None
    getter = (r.get("observed_delay_source") or {}).get("getter")
    if _COOLDOWN.search(getter or "") or (not getter and _COOLDOWN.search(str(r.get("surface") or ""))):
        return None
    return d


def _norm(name):
    return re.sub(r"[^a-z]", "", name.lower())


def _upgrade_path(c, t, known, prev):
    """The enforced delay (seconds) and its reason on one upgrade clause c of record text t, or None when the published evidence
    does not decide it. A delay counts only through a controller bound in the clause itself: an owner / admin / controller relation
    to an address, the record's own subject ("it owns the ProxyAdmin"), or a named definite reference ("the local timelock" ->
    localTimelock() = 0x…). A delay elsewhere in the record, or an address merely mentioned in the clause, never decides it."""
    if _BYPASS.search(c):
        return 0, "a 1-of-N executor co-owned by the timelock and a non-timelock signer bypasses the delay"
    if _NODELAY.search(c) or _SINGLE.search(c):
        return 0, "no timelock in front of upgrades"
    bound = [(m.group(1) or m.group(2)).lower() for m in _BOUND.finditer(c)]
    ds = [known[a] for a in bound if a in known]
    if ds:
        return min(ds), "timelock delay on the upgrade path"
    if prev is not None and _SAME_TL.search(c):
        return prev, "the same timelock"
    refs = []
    if _SUBJECT_OWNS.search(c):
        first = _ADDR.search(t)
        refs += [first.group(0).lower()] if first else []
    for m in _ONLY.finditer(c):   # "upgradeTo … is onlyAdmin" -> the record's own admin() = 0x… relation
        rel = re.search(r"\b" + m.group(1).lower() + r"\(\)\s*=\s*(?:the\s+)?" + _W + r"\(?(0x[0-9a-fA-F]{40})", t)
        refs += [rel.group(1).lower()] if rel else []
    for m in _DEFINITE.finditer(c):
        key = _norm(m.group(1))
        refs += [n.group(2).lower() for n in _NAMED.finditer(t) if _norm(n.group(1)) == key]
    ds = [known[a] for a in refs if a in known]
    if ds:
        return min(ds), "timelock delay on the upgrade path"
    if _SAFE_DIRECT.search(c) and not _TLWORD.search(c):
        return 0, "upgraded by a Safe directly (a Safe has no delay of its own)"
    return None


def factors(records, easattested, g, facts=(), parity_text=None):
    """The five factor states (g / b / a / n / u) with the evidence that decided each. records: the protocol's published records
    (index.json or rpc-pinned.json entries); facts: graph_controller_facts entries of its contracts (with "address").

    Every factor is bound to its own control surface: each record's evidence is split into clauses and a clause only decides the
    factor it is about. Upgradeability = the weakest established upgrade path (the delay gating that clause's proxy admin);
    timelock floor = the weakest established admin / governance execution delay, including those upgrade paths (user withdrawal /
    unstaking cooldowns never count); emergency scope = the holder named in the pause / freeze clause itself."""
    texts = [(r.get("id"), str(r.get("onchain_observed") or ""), r) for r in records]
    out = {}
    # known timelock delays by address (the published delay sources, in-text "0x… getMinDelay() = Ns" and controller facts)
    known = {}
    for r in records:
        src, d = (r.get("observed_delay_source") or {}).get("contract"), _admin_delay(r)
        if src and d is not None:
            known[src.lower()] = min(d, known.get(src.lower(), d))
    for _, t, _r in texts:
        for m in _ADDR_DELAY.finditer(t):
            a, d = m.group(1).lower(), int(m.group(2).replace(",", ""))
            known[a] = min(d, known.get(a, d))
    for f in facts:
        if isinstance(f.get("timelock_min_delay"), int) and f.get("address"):
            known[f["address"].lower()] = f["timelock_min_delay"]
    # 1: upgradeability: every upgrade clause on its own; the weakest established path decides
    paths, undecided, prox, pending, admins = [], 0, None, [], {}
    for rid, t, r in texts:
        prev = None
        for c in clauses(t):
            if not _PROXY.search(c):
                continue
            prox = prox or (rid, c)
            p = _upgrade_path(c, t, known, prev)
            if p is None:
                pending.append((rid, c))
                continue
            prev = p[0]
            paths.append((p[0], p[1], f"{rid}: {_clip(c)}"))
            for a in _PROXY_ADMIN.findall(c):
                admins[a.lower()] = min(p[0], admins.get(a.lower(), p[0]))
    for rid, c in pending:   # a ProxyAdmin whose gating delay another clause established
        ds = [admins[a.lower()] for a in _PROXY_ADMIN.findall(c) if a.lower() in admins]
        if ds:
            paths.append((min(ds), "the ProxyAdmin's owner delay", f"{rid}: {_clip(c)}"))
        else:
            undecided += 1
    if prox is None:
        flagged = next((r for r in records if r.get("is_eip1967_proxy")), None)
        if flagged is not None:
            prox, undecided = (flagged.get("id"), "is_eip1967_proxy = true"), 1
    imm = next(((rid, t, m) for rid, t, _r in texts for m in [_IMMUTABLE.search(t)] if m), None)
    more = f" ({undecided} other upgrade path{'s' if undecided != 1 else ''} not determined)" if paths and undecided else ""
    if paths:
        d, why, ev = min(paths, key=lambda p: (p[0], p[2]))
        if d >= 2 * DAY:
            out["upgrade"] = ("g", f"Upgradeable behind a ≥48h delay ({_dur(d)}){more}", ev)
        elif d >= 3600:
            out["upgrade"] = ("b", f"Upgradeable behind a 1h–47h delay ({_dur(d)}){more}", ev)
        else:
            out["upgrade"] = ("a", f"Upgradeable with no enforced delay: {why}{more}", ev)
    elif prox:
        out["upgrade"] = ("n", "Upgradeable; the delay gating the upgrade path is not in the published records", f"{prox[0]}: {_clip(prox[1])}")
    elif imm:
        out["upgrade"] = ("g", "Immutable or ownership renounced", f"{imm[0]}: {_snip(imm[1], imm[2])}")
    else:
        out["upgrade"] = ("n", "Upgrade path not in the published records", None)
    # 2: timelock floor: the weakest admin / governance execution delay on any control surface (upgrade paths included)
    delays = [(d, ev) for d, _, ev in paths]
    for r in records:
        d = _admin_delay(r)
        if d is not None:
            delays.append((d, f'{r.get("id")}: observed_delay_seconds = {d}'))
    for rid, t, _r in texts:
        if _COOLDOWN.search(str(_r.get("surface") or "")):        # a user withdrawal / unstaking delay is not an admin timelock
            continue
        for m in _DELAY.finditer(t):
            delays.append((int(m.group(1).replace(",", "")), f"{rid}: {_snip(t, m)}"))
        for c in clauses(t):                                      # a role that executes without the delay (e.g. RBACTimelock bypasser)
            if _BYPASS_EXEC.search(c):
                delays.append((0, f"{rid}: {_clip(c)}"))
    for f in facts:
        if isinstance(f.get("timelock_min_delay"), int):
            delays.append((f["timelock_min_delay"], f'controller fact: getMinDelay() = {f["timelock_min_delay"]}s'))
    if delays:
        d, ev = min(delays)
        st = "g" if d >= 2 * DAY else "b" if d >= 3600 else "a"
        out["timelock"] = (st, ("0s: an operator can execute approved proposals without waiting the timelock delay"
                                if d == 0 and "executeOperatorProposal" in ev and _BYPASS_EXEC.search(ev) else
                                "0s: a bypasser role can execute without waiting the timelock delay" if d == 0 and _BYPASS_EXEC.search(ev)
                                else "No enforced delay on at least one sampled control surface (0s)" if d == 0
                                else f"{_dur(d)} minimum enforced delay on sampled timelocked surfaces"), ev)
    else:
        out["timelock"] = ("n", "No enforced admin delay in the published records", None)
    # 3: signer quorum (lowest threshold of any controlling Safe; a key without contract code counts as 1-of-1)
    quorum, wrapped, wrappers = [], set(), set()
    for rid, t, _r in texts:
        for w in _WRAPPER.finditer(t):
            if _TLWORD.search(w.group(3)) and (_NOF.search(w.group(3)) or re.search(r"Safe|[Mm]ultisig", w.group(3))):
                wrapped.add((rid, w.start()))
                wrappers.update(a.lower() for a in _ADDR.findall(w.group(2)))
        for m in _NOF.finditer(t):
            k, nn = int(m.group(1)), int(m.group(2))
            if (rid, m.start()) in wrapped:
                continue
            if 1 <= k <= nn:
                quorum.append((k, f"{k}-of-{nn}" + (" (via a 1-of-N contract-executor wrapper co-owned with a timelock)" if wrapped else ""),
                               f"{rid}: {_snip(t, m)}"))
        for m in _SINGLE.finditer(t):
            if _operator_key(t, m.start()):
                continue                                  # the approved-proposal executor's own key (see _operator_key)
            quorum.append((1, "a single key", f"{rid}: {_snip(t, m)}"))
    for f in facts:
        if f.get("safe_threshold") and str(f.get("address", "")).lower() not in wrappers:
            quorum.append((f["safe_threshold"], f'{f["safe_threshold"]}-of-{f.get("safe_owners")}', "controller fact: Safe getThreshold()"))
    if quorum:
        k, lbl, ev = min(quorum, key=lambda q: (q[0], q[1]))
        st = "g" if k >= 3 else "b" if k == 2 else "a"
        out["quorum"] = (st, f"Lowest controlling quorum: {lbl}", ev)
    else:
        gov = next(((rid, t, m) for rid, t, _r in texts for m in [_GOVERNOR.search(t)] if m), None)
        out["quorum"] = (("g", "DAO Governor (token vote)", f"{gov[0]}: {_snip(gov[1], gov[2])}") if gov
                         else ("n", "No signer quorum in the published records", None))
    # 4: emergency / freeze scope: the holder named in the pause / freeze clause itself (a Safe fact by address counts)
    safes = {f["address"].lower(): f["safe_threshold"] for f in facts if f.get("safe_threshold") and f.get("address")}
    held, em = [], None
    for rid, t, _r in texts:
        cs = clauses(t)
        for i, c in enumerate(cs):
            if not _EMERGENCY.search(c):
                continue
            em = em or (rid, c)
            if i + 1 < len(cs) and _THAT.match(cs[i + 1]):   # "…hasRole(FREEZER, 0x…) = true; that Safe is 2-of-5"
                c = f"{c}; {cs[i + 1]}"
            ks = [(int(m.group(1)), f"{m.group(1)}-of-{m.group(2)}") for m in _NOF.finditer(c) if 1 <= int(m.group(1)) <= int(m.group(2))]
            ks += [(1, "a single key") for _ in _SINGLE.finditer(c)]
            ks += [(safes[a.lower()], f"{safes[a.lower()]}-of-N Safe") for a in _ADDR.findall(c) if a.lower() in safes]
            if ks:
                k, lbl = min(ks)
                held.append((k, lbl, f"{rid}: {_clip(c)}"))
    if held:
        k, lbl, ev = min(held)
        out["emergency"] = (("a", f"Pause / freeze authority held by {lbl}", ev) if k == 1 else
                            ("g", f"Pause / freeze authority scoped behind a multi-signer controller ({lbl})", ev))
    elif em:
        out["emergency"] = ("n", "Pause / freeze authority present; its holder is not determined", f"{em[0]}: {_clip(em[1])}")
    else:
        out["emergency"] = ("n", "No pause / freeze authority in the published records", None)
    # 5: docs-vs-chain parity (the grade; never colored without a Base-EAS-attested documentation comparison)
    # an unresolved protocol is never coloured: the comparison does not establish a breach (hollow "n"), never weak, never strong
    out["parity"] = (("u", "Uncompared: documentation not assessed (RPC-observed)", None) if not easattested else
                     ("n", parity_text or UNRESOLVED_PARITY, None) if g == "unresolved" else
                     ("a", "Documentation differs from the chain (parameter delta)", None) if g == "delta" else
                     ("g", "Chain matches or is stronger than the documentation", None))
    return [{"key": k, "label": lbl, "state": out[k][0], "value": out[k][1], "evidence": out[k][2]} for k, lbl in FACTORS]


def _clip(c, width=160):
    """Whole-word clip (V8): never mid-word, never inside a 0x value; the full text stays on the protocol page."""
    if len(c) <= width:
        return c
    cut = c[:width]
    if not c[width].isspace():
        cut = cut[:cut.rfind(" ")] if " " in cut else cut
    return cut.rstrip(" ,;:(") + " …"


def _dur(s):
    if s >= DAY and s % 3600 == 0:
        d, h = divmod(s // 3600, 24)
        return f"{d}d" + (f" {h}h" if h else "")
    if s >= 3600:
        return f"{s / 3600:g}h"
    return f"{s}s"


def aria(fs, name=None):
    return ((f"{name} control-plane rosette: " if name else "Control-plane rosette: ")
            + "; ".join(f'{f["label"]} {STATE_LABEL[f["state"]].lower()}' for f in fs))


# V5/A1: the slice length is a second, colour-independent cue (strong full, moderate 78 %, weak 56 %); not determined / uncompared
# is a hollow dashed full-length outline. The letters S / M / W / — sit next to every factor list.
RADIUS = {"g": 1.0, "b": 0.78, "a": 0.56, "n": 1.0, "u": 1.0}


def rosette_svg(fs, size=28, name=None, interactive=False):
    """Inline SVG: five 72-degree slices clockwise from 12 o'clock (factor order) inside a hairline ring. Ordered palette (strong
    green, moderate yellow, weak red) plus slice length; each slice names its factor and state in a <title> (hover). With
    interactive=True every slice is focusable and carries data-tip for the keyboard / hover Tooltip (app.js)."""
    import math
    c, r = size / 2, size / 2 - 1.5
    parts = [f'<circle class="r-ring" cx="{c:.1f}" cy="{c:.1f}" r="{r:.1f}"/>']
    for i, f in enumerate(fs):
        rr = r * RADIUS.get(f["state"], 1.0)
        a0, a1 = math.radians(-90 + 72 * i + 1.5), math.radians(-90 + 72 * (i + 1) - 1.5)
        x0, y0, x1, y1 = c + rr * math.cos(a0), c + rr * math.sin(a0), c + rr * math.cos(a1), c + rr * math.sin(a1)
        d = f"M{c:.1f} {c:.1f}L{x0:.1f} {y0:.1f}A{rr:.1f} {rr:.1f} 0 0 1 {x1:.1f} {y1:.1f}Z"
        lbl = f'{f["label"]}: {STATE_LABEL[f["state"]]}'
        extra = f' data-tip="{_esc(lbl)}"' if interactive else ""
        parts.append(f'<path class="r-{f["state"]}" d="{d}"{extra}><title>{_esc(lbl)}</title></path>' if interactive
                     else f'<path class="r-{f["state"]}" d="{d}"/>')
    # interactive: one keyboard stop (>= 24 px) whose Tooltip lists all five factors; each slice shows its own on hover
    tip = "\n".join(f'{f["label"]}: {STATE_LABEL[f["state"]]}' for f in fs)
    extra_svg = f' tabindex="0" data-tip="{_esc(tip)}"' if interactive else ""
    return (f'<svg class="rosette{" rosette-i" if interactive else ""}" width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" '
            f'aria-label="{_esc(aria(fs, name))}"{extra_svg}>{"".join(parts)}</svg>')


def _esc(s):
    return str(s).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
