"""Protocol scorecards (Website Edge v3): one canonical grade per protocol and a deterministic 5-factor control-plane rosette.

Every value is derived at build time from Pacta's published records only: index.json (Base-EAS-attested Sprint records) and
rpc-pinned.json (RPC-observed records), their onchain_observed evidence text and structured fields (observed_delay_seconds,
is_eip1967_proxy, safe_quorum), plus tools/graph_controller_facts.json. No value is entered by hand. A factor that the published
evidence does not decide is "Not determined" (a hollow slice), never a guess; slice 5 is "Uncompared" (hollow) for every
RPC-observed protocol, whose documentation Pacta has not assessed.

Grades (protocol level): DELTA (any parameter_delta record), UNRESOLVED (a protocol tools/scorecard_corrections.json marks
"unresolved": the chain state is pinned, but a breach of a documented commitment is not established; neither DELTA nor ALIGNED),
CHANGED RECENTLY ("recent_change": observed within 48 hours of an on-chain change, documents not yet updated; re-checked after
72 hours before it counts as a DELTA; neither DELTA nor ALIGNED),
PROTECTIVE (no parameter delta, at least one protective_delta), ALIGNED (every record an aligned baseline), OBSERVED (RPC-pinned only). A protocol whose record carries "reconciledFrom" provenance
(a former delta reconciled at a later attested block) is ALIGNED with the "Reconciled" sub-pill and a before / after trail."""
import re

GRADES = {"delta": ("DELTA", "Docs and chain differ"),
          "recent_change": ("CHANGED RECENTLY", "Changed on chain recently; documents not yet updated"),
          "docs_updated": ("DOCS UPDATED", "Documentation updated to match retained chain read; pending fresh chain read"),
          "unresolved": ("UNRESOLVED", "Observed on chain; document breach not established"),
          "protective": ("PROTECTIVE", "Chain stronger than documented"),
          "aligned": ("ALIGNED", "Docs and chain match"), "observed": ("OBSERVED", "Chain pinned; docs not assessed")}
FACTORS = [("upgrade", "Upgradeability"), ("timelock", "Timelock floor"), ("quorum", "Signer quorum"),
           ("emergency", "Emergency / freeze scope"), ("parity", "Docs-vs-chain parity")]
STATE_LABEL = {"g": "Strong", "b": "Moderate", "a": "Weak", "n": "Not determined", "u": "Uncompared"}
DAY = 86400

_NOF = re.compile(r"\b(\d{1,2})-of-(\d{1,2})\b")
# "getThreshold() = 3 of getOwners() = 6": the same K-of-N, written as the two Safe reads
_NOF_READS = re.compile(r"getThreshold\(\)\s*=\s*(\d{1,2})\s+of\s+getOwners\(\)\s*=\s*(\d{1,2})\b")
# a freeze / pause / blacklist power exercisable with no enforced delay (the record states it)
_ZERO_DELAY = re.compile(r"no delay of its own|\(0 ?s\)|needs no timelock|no enforced delay|with no delay|exposes no delay", re.I)


_DOC_NOF = re.compile(r"\b(\d{1,2})\s*(?:-of-|/|\s+of\s+)\s*(\d{1,2})\b")


_UNATTACHED = re.compile(r"\bowns neither\b|\bdoes not own\b|\bis not the [\w' ()-]*?owner\b|\bnot in the (?:\w+ )*path\b|\bnot wired\b", re.I)
_ZERO_GUARDIAN = re.compile(r"guardian\(\)\s*=\s*0x0{40}\b")
_CANCEL_ONLY = re.compile(r"CANCELLER_ROLE")
_FREEZE_WORDS = re.compile(r"\bpause|\bunpause|\bfreez|\bblacklist|PAUSE_ROLE|PAUSER_ROLE|pauseGuardian|EMERGENCY_ROLE|circuit breaker|emergency[- ]stop", re.I)
_NAMED_SAFE = re.compile(r"The ([A-Z][\w-]*) is a (?:\d{1,2}-of-\d{1,2} )?Safe\b")
# a sentence boundary inside a clause: ". " before a capital letter (never a decimal such as 111.1% or a version such as v1.3.0)
_SENTENCE = re.compile(r"(?<=[A-Za-z0-9)\]%])\.\s+(?=[A-Z0-9(])")


def _nofs(text):
    """Every K-of-N quorum in the text, written either as "3-of-6" or as "getThreshold() = 3 of getOwners() = 6"."""
    return sorted(list(_NOF.finditer(text)) + list(_NOF_READS.finditer(text)), key=lambda m: m.start())
_DELAY = re.compile(
    r"\b(?:(?:getMinDelay|delay|MINIMUM_DELAY|MIN_DELAY|minDelay|executionDelay|MIN_EXECUTION_DELAY|"
    r"TIMELOCK_PERIOD|timelockPeriod|timelockDelay|getMinimumDelay)(?:\(\))?\s*(?:returns\s*|=\s*|:\s*)"
    r"|getExecutorSettingsByAccessControl\(\d+\)\s*=\s*\([^;)]*?,\s*(?:delay\s*(?:=|:)\s*)?"
    r"|(?:Executor\s*Lvl?\s*\d+|Timelock(?:Controller)?|GovernorTimelock)\s*\([^;)]*?(?:,\s*|\bdelay\s*(?:=|:)\s*))"
    r"([\d,]+)\s*s\b"
)
_SINGLE = re.compile(r"no contract code|externally owned|\bEOA\b|\(no code\)|without code")
_GOVERNOR = re.compile(r"\bGovernor(?:Bravo|Alpha|Omega)?\b|\bDAO governance\b")
_PROXY = re.compile(r"EIP-1967 (?:admin|implementation) (?:slot )?(?:=|resolves|is)|ProxyAdmin|AdminUpgradeabilityProxy|BeaconProxy|UpgradeableBeacon|"
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
_ADDR_DELAY = re.compile(
    r"(?:(0x[0-9a-fA-F]{40})[^;0-9]{0,45}?(?:(?:getMinDelay|delay|minDelay|executionDelay|MIN_EXECUTION_DELAY)(?:\(\))?\s*(?:returns\s*|=\s*|:\s*)|minimum delay\s+)([\d,]+)\s*s?\b)"
    r"|(?:getExecutorSettingsByAccessControl\(\d+\)\s*=\s*\((?:[\w-]+\s+)?(0x[0-9a-fA-F]{40})\s*,\s*(?:delay\s*(?:=|:)\s*)?([\d,]+)\s*s\b)"
    r"|(?:(?:Executor\s*Lvl?\s*\d+|Timelock(?:Controller)?|GovernorTimelock)\s*\(\s*(0x[0-9a-fA-F]{40})\s*,\s*(?:delay\s*(?:=|:)\s*)?([\d,]+)\s*s\b)"
)
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
# v9 H1: "deprecated" (a README / docs status word) is not a pause / freeze surface and no longer matches
_EMERGENCY = re.compile(r"\bpause|\bblacklist|\bfreez|PAUSE_ROLE|ASSET_PROTECTION|\bguardian\b|pauseGuardian", re.I)
# v9 H2: a pause / freeze role with several members, e.g. "PAUSE_GUARDIAN_ROLE has 3 members (2-of-6 Safe 0x…, 0x…, 0x…)"
_MEMBERS = re.compile(r"\b([A-Z][A-Z0-9_]*_ROLE)\b[^;()]{0,40}?\bhas (\d+) members(?:\s*\(([^)]*)\))?"
                      r"|\b([A-Z][A-Z0-9_]*_ROLE)\b[^;()]{0,40}?getRoleMemberCount\([^)]*\)\s*(?:=|returns)\s*(\d+)")
_NUMWORD = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
# v10 H2.1: any pause / freeze role-holder list ("held by A and B", "granted to A, B", "holders: A, B", "pausers are A and B");
# addresses before the phrase (e.g. "On Vault 0x…, PAUSER_ROLE is held by …") are targets, never holders
_HOLDER_PHRASE = re.compile(r"\b(?:held by|assigned to|granted to|holders?\s*(?::|are|is)|pausers?\s+(?:are|is)|members?\s*(?::|are))\s+", re.I)
_LIST_SEP = re.compile(r",\s*(?:and\s+)?|\s+and\s+")
_ROLE = re.compile(r"\b([A-Z][A-Z0-9_]*_ROLE)\b")


def _top_level_split(tail):
    """Split a holder list on ", " / " and " outside parentheses."""
    out, depth, start, i = [], 0, 0, 0
    while i < len(tail):
        ch = tail[i]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif depth == 0:
            m = _LIST_SEP.match(tail, i)
            if m:
                out.append(tail[start:i])
                start = i = m.end()
                continue
        i += 1
    out.append(tail[start:])
    return [x.strip() for x in out if x.strip()]


def _holder_of(item):
    """The role-holder address of one list item: the first address outside parentheses, else the first inside."""
    bare = re.sub(r"\([^()]*\)", " ", item)
    a = _ADDR.findall(bare) or _ADDR.findall(item)
    return a[0].lower() if a else None


def role_holders(c):
    """(role, declared member count, [holder items]) for a pause / freeze clause naming >= 2 role holders, else None."""
    mm = _MEMBERS.search(c)
    if mm and int(mm.group(2) or mm.group(5)) > 1:
        return (mm.group(1) or mm.group(4), int(mm.group(2) or mm.group(5)),
                [x.strip() for x in (mm.group(3) or "").split(",") if x.strip()])
    hp = _HOLDER_PHRASE.search(c)
    if not hp:
        return None
    items, seen = [], []
    for it in _top_level_split(c[hp.end():]):
        h = _holder_of(it)
        if h is None:
            break                                     # the holder list ends at the first item that names no address
        if h not in seen:
            seen.append(h)
            items.append(it)
    if len(seen) < 2:
        return None
    roles = _ROLE.findall(c[:hp.start()])
    return (roles[-1] if roles else "Pause / freeze authority", len(seen), items)


UNRESOLVED_PARITY = "Observed onchain state pinned; a breach of a documented commitment is not established"
DOCS_UPDATED_PARITY = "Documentation updated to name the retained observation; a fresh finalized-block chain read is pending"
RECENT_CHANGE_PARITY = "Changed on chain within 48h of pin; re-checked after 72 hours before counting as a documentation gap"


def grade(classifications, easattested, reconciled=False, slug=None):
    if not easattested:
        return "observed"
    if slug is not None:
        import scorecard_corrections as CORR
        if CORR.status(slug) in CORR.NEUTRAL:      # "unresolved" / "recent_change": neither Delta nor Aligned
            return CORR.status(slug)
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


_NOT_PROXY = re.compile(r"not a proxy|non-proxy|no proxies")
# a proxy another contract in the record IS (a role holder, minter or helper), never a negated "no selector of upgradeTo(...)"
_HELPER_PROXY = re.compile(r"\b(?:ERC|EIP)-1967 prox|TransparentUpgradeableProxy|AdminUpgradeabilityProxy|\bUUPS prox|\bProxyAdmin\b")


def _target_not_proxy(r, t):
    """True when the record states its own target contract is not a proxy: "not a proxy" within the parenthetical or clause that
    follows the target address (e.g. "BIO token 0xcb15… (Ethereum, not a proxy; BioToken, verified source)")."""
    tc = str(r.get("target_contract") or "")
    i = t.lower().find(tc.lower()) if tc.startswith("0x") else -1
    if i < 0:
        return False
    return bool(_NOT_PROXY.search(t[i + len(tc): i + len(tc) + 120].split(":")[0].split(". ")[0]))


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


def factors(records, easattested, g, facts=(), parity_text=None, slug=None):
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
        if _COOLDOWN.search(str(_r.get("surface") or "")):
            continue
        for c in clauses(t):
            if _COOLDOWN.search(c):
                continue
            for m in _ADDR_DELAY.finditer(c):
                addr_s = m.group(1) or m.group(3) or m.group(5)
                sec_s = m.group(2) or m.group(4) or m.group(6)
                a, d = addr_s.lower(), int(sec_s.replace(",", ""))
                known[a] = min(d, known.get(a, d))
    for f in facts:
        if isinstance(f.get("timelock_min_delay"), int) and f.get("address"):
            known[f["address"].lower()] = f["timelock_min_delay"]
    # 1: upgradeability: every upgrade clause on its own; the weakest established path decides
    paths, undecided, prox, pending, admins, helper, notprox = [], 0, None, [], {}, None, None
    for rid, t, r in texts:
        prev = None
        if _target_not_proxy(r, t):
            # the record's own target is stated "not a proxy": a proxy it names (a role holder, minter or helper) is another
            # contract's upgrade path, never the target's, so it does not make the protocol "Upgradeable"
            helper = helper or ((rid, t) if _HELPER_PROXY.search(t) else None)
            notprox = notprox or (rid if _PROXY.search(t) else None)   # e.g. "no selector of upgradeTo(address)" on a plain token
            continue
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
    elif imm and helper and imm[0] == helper[0]:
        out["upgrade"] = ("g", "Target contract is not a proxy (non-upgradeable); a proxy named in the same record is a role holder or "
                               "helper, not the target", f"{imm[0]}: {_snip(imm[1], imm[2])}")
    elif imm and imm[0] == notprox:
        out["upgrade"] = ("g", "Not upgradeable: the target contract is not a proxy", f"{imm[0]}: {_snip(imm[1], imm[2])}")
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
        for c in clauses(t):
            if _COOLDOWN.search(c):
                continue
            off = t.find(c)
            for m in _DELAY.finditer(c):
                # a timelock the record itself says is not on the sampled path ("owns neither", "does not own MasterChef") sets no floor:
                # the path it was listed for has no enforced delay (v7 F4)
                ms, me = (off + m.start(), off + m.end()) if off >= 0 else (0, len(t))
                a_, b_ = t.rfind(". ", 0, ms), t.find(". ", me)
                sent = t[a_ + 2 if a_ >= 0 else 0: b_ if b_ >= 0 else len(t)]
                if _UNATTACHED.search(sent):
                    delays.append((0, f"{rid}: {_clip(sent)}"))
                    continue
                delays.append((int(m.group(1).replace(",", "")), f"{rid}: {_snip(c, m)}"))
        for c in clauses(t):                                      # a role that executes without the delay (e.g. RBACTimelock bypasser)
            if _BYPASS_EXEC.search(c):
                delays.append((0, f"{rid}: {_clip(c)}"))
    for f in facts:
        if isinstance(f.get("timelock_min_delay"), int):
            delays.append((f["timelock_min_delay"], f'controller fact: getMinDelay() = {f["timelock_min_delay"]}s'))
    if delays:
        d, ev = min(delays)
        st = "g" if d >= 2 * DAY else "b" if d >= 3600 else "a"   # Strong = a multi-day (>= 48h) floor, as on the upgrade factor
        out["timelock"] = (st, ("0s: an operator can execute approved proposals without waiting the timelock delay"
                                if d == 0 and "executeOperatorProposal" in ev and _BYPASS_EXEC.search(ev) else
                                "0s: a bypasser role can execute without waiting the timelock delay" if d == 0 and _BYPASS_EXEC.search(ev)
                                else "No enforced delay on at least one sampled control surface (0s)" if d == 0
                                else f"{_dur(d)} minimum enforced delay on sampled timelocked surfaces"), ev)
    else:
        out["timelock"] = ("n", "No enforced admin delay in the published records", None)   # v10 5c664b0c wording (Section 5)
    # 3: signer quorum (lowest threshold of any controlling Safe; a key without contract code counts as 1-of-1)
    quorum, wrapped, wrappers = [], set(), set()
    for rid, t, _r in texts:
        for w in _WRAPPER.finditer(t):
            if _TLWORD.search(w.group(3)) and (_NOF.search(w.group(3)) or re.search(r"Safe|[Mm]ultisig", w.group(3))):
                wrapped.add((rid, w.start()))
                wrappers.update(a.lower() for a in _ADDR.findall(w.group(2)))
        for m in _nofs(t):
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
    # a flagged record whose observed Safe threshold is below the threshold its documentation states (e.g. 4-of-6 against a
    # documented 6/8) is never rated Strong on quorum: the breached dimension caps at Moderate and names the documented value
    weaker = []
    for rid, t, r_ in texts:
        if r_.get("classification") != "parameter_delta":
            continue
        obs_k = [int(m.group(1)) for m in _nofs(t)]
        doc = [(int(a), int(b)) for a, b in _DOC_NOF.findall(str(r_.get("documented_reference") or "")) if 1 <= int(a) <= int(b)]
        if obs_k and doc and min(obs_k) < max(k_ for k_, _ in doc):
            weaker.append("{}-of-{}".format(*max(doc)))
    if quorum:
        k, lbl, ev = min(quorum, key=lambda q: (q[0], q[1]))
        st = "g" if k >= 3 else "b" if k == 2 else "a"
        if weaker and st == "g":
            st, lbl = "b", f"{lbl} (documented {weaker[0]})"
        out["quorum"] = (st, f"Lowest controlling quorum: {lbl}", ev)
    else:
        gov = next(((rid, t, m) for rid, t, _r in texts for m in [_GOVERNOR.search(t)] if m), None)
        out["quorum"] = (("g", "DAO Governor (token vote)", f"{gov[0]}: {_snip(gov[1], gov[2])}") if gov
                         else ("n", "No signer quorum in the published records", None))
    # 4: emergency / freeze scope: the holder named in the pause / freeze clause itself (a Safe fact by address counts)
    safes = {f["address"].lower(): f["safe_threshold"] for f in facts if f.get("safe_threshold") and f.get("address")}
    held, em, multi = [], None, []
    for rid, t, _r in texts:
        # v8 G1: a record that only establishes a timelock CANCELLER_ROLE (no pause / unpause / freeze / circuit-breaker binding anywhere
        # in it) establishes no pause / freeze holder, whichever of its clauses names a "Guardian"
        cancel_only = bool(_CANCEL_ONLY.search(t)) and not _FREEZE_WORDS.search(t)
        # v8 G4: the holder is bound within one sentence: clauses are split again on sentence boundaries, so a Safe quorum named in
        # a later sentence (e.g. a ProxyAdmin owner) is never borrowed by the pause / freeze holder of an earlier one
        cs = [u for c0 in clauses(t) for u in _SENTENCE.split(c0) if u.strip()]
        for i, c in enumerate(cs):
            if not _EMERGENCY.search(c):
                continue
            # a timelock CANCELLER_ROLE alone establishes neither a pause / freeze holder (v7 F3) nor pause / freeze presence (v9 H1)
            if cancel_only or (_CANCEL_ONLY.search(c) and not _FREEZE_WORDS.search(c)):
                continue
            # an unset guardian (guardian() = 0x0) establishes no pause / freeze holder (v7 F3)
            if _ZERO_GUARDIAN.search(c):
                em = em or (rid, c)
                continue
            em = em or (rid, c)
            if i + 1 < len(cs) and _THAT.match(cs[i + 1]):   # "…hasRole(FREEZER, 0x…) = true; that Safe is 2-of-5"
                c = f"{c}; {cs[i + 1]}"
            elif i + 1 < len(cs):
                # "owner() = Admin … Pauser Proxy …. The Admin is a Safe: getThreshold() = 3 of …": the next sentence describes the
                # same named holder, so its quorum binds; any other later sentence (e.g. a ProxyAdmin owner) never does
                nm = _NAMED_SAFE.match(cs[i + 1].strip())
                if nm and re.search(r"\b" + re.escape(nm.group(1)) + r"\b", c):
                    c = f"{c}; {cs[i + 1]}"
            # v9 H2: a multi-member pause / freeze role is rated on its members only when every member resolves to a >= 2-signer
            # Safe quorum or a timelock; one member's quorum never stands for co-members the published records do not resolve
            # (v10 H2.1: the same rule for every role-holder list, each holder bound only to its own list item)
            rh = role_holders(c)
            if rh:
                role, n_, items = rh
                res = []
                for it in items:
                    q = [int(a) for a, b in ((x.group(1), x.group(2)) for x in _nofs(it)) if 2 <= int(a) <= int(b)]
                    q += [safes[a.lower()] for a in _ADDR.findall(it) if safes.get(a.lower(), 0) >= 2]
                    if q:
                        res.append(next(f"{x.group(1)}-of-{x.group(2)} Safe" for x in _nofs(it)) if _nofs(it) else f"{min(q)}-of-N Safe")
                    elif re.search(r"[Tt]imelock", it):
                        res.append("timelock")
                if len(res) < n_:
                    u = n_ - len(res)
                    parts = [f"{_NUMWORD.get(res.count(x), res.count(x))} {x}" for x in dict.fromkeys(res)]
                    rest = f"{u} {'other ' if res else ''}role member{'s' if u > 1 else ''} not resolved in the published records"
                    multi.append((f"{role} held by {n_} addresses ({'; '.join(parts + [rest])})", f"{rid}: {_clip(c)}"))
                    continue
            ks = [(int(m.group(1)), f"{m.group(1)}-of-{m.group(2)}") for m in _nofs(c) if 1 <= int(m.group(1)) <= int(m.group(2))]
            ks += [(1, "a single key") for _ in _SINGLE.finditer(c)]
            ks += [(safes[a.lower()], f"{safes[a.lower()]}-of-N Safe") for a in _ADDR.findall(c) if a.lower() in safes]
            if ks:
                k, lbl = min(ks)
                # a flagged record whose freeze / pause / blacklist power has no enforced delay is never "Strong", whatever its quorum
                zero = _r.get("classification") == "parameter_delta" and bool(_ZERO_DELAY.search(c))
                held.append((k, lbl, f"{rid}: {_clip(c)}", zero))
    if held:
        imm = [h for h in held if h[3]]
        if imm:
            k, lbl, ev, _z = min(imm)
            out["emergency"] = ("a", f"Immediate: pause / freeze authority held by {lbl} with no enforced delay", ev)
        else:
            k, lbl, ev, _z = min(held)
            out["emergency"] = (("a", f"Pause / freeze authority held by {lbl}", ev) if k == 1 else
                                ("n", multi[0][0], multi[0][1]) if multi else
                                ("g", f"Pause / freeze authority scoped behind a multi-signer controller ({lbl})", ev))
    elif multi:
        out["emergency"] = ("n", multi[0][0], multi[0][1])
    elif em:
        out["emergency"] = ("n", "Pause / freeze authority present; its holder is not determined", f"{em[0]}: {_clip(em[1])}")
    else:
        out["emergency"] = ("n", "No pause / freeze authority in the published records", None)
    # 5: docs-vs-chain parity (the grade; never colored without a Base-EAS-attested documentation comparison)
    # an unresolved protocol is never coloured: the comparison does not establish a breach (hollow "n"), never weak, never strong
    out["parity"] = (("u", "Uncompared: documentation not assessed (Observed)", None) if not easattested else
                     ("n", parity_text or UNRESOLVED_PARITY, None) if g == "unresolved" else
                     ("n", parity_text or RECENT_CHANGE_PARITY, None) if g == "recent_change" else
                     ("n", parity_text or DOCS_UPDATED_PARITY, None) if g == "docs_updated" else
                     ("a", "Documentation differs from the chain (parameter delta)", None) if g == "delta" else
                     ("g", "Chain matches or is stronger than the documentation", None))
    if slug is not None:
        _rules_87(slug, records, out)
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
    return ((f"{name} control-strength graphic: " if name else "Control-strength graphic: ")
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


# ================================================================ Scorecard-87 (Business receipt 7462): rules R1-R5
# Five record-derived rules, applied only to the reviewed (slug, factor) slices below so that no other slice can move. Each rule reads
# the published records (surface + onchain_observed + observed_delay_seconds / safe_quorum / controller_kind) and returns
# (state, value, evidence); the value is a template filled from the records (no per-protocol prose). Sharper reviewed wording, when a
# slice has one, is a value-only entry in scorecard_corrections.json labelOverrides (never its state or evidence).
RULE_SLICES_87 = frozenset({
    ("across-protocol-hubpool", "upgrade"), ("angstrom", "upgrade"), ("anvil", "upgrade"), ("aura", "upgrade"),
    ("avalon-superearn", "timelock"), ("avalon-superearn", "upgrade"), ("axelar-network", "quorum"),
    ("balancer-v2-vault-timelock", "emergency"), ("bedrock-unibtc", "timelock"), ("bedrock-unibtc", "upgrade"),
    ("bedrock-unieth", "timelock"), ("bedrock-unieth", "upgrade"), ("beefy-finance-base", "quorum"), ("beefy-finance-base", "upgrade"),
    ("bmx-freestyle", "timelock"), ("bmx-freestyle", "upgrade"), ("cbridge", "quorum"), ("cbridge", "upgrade"),
    ("chamber-vaults", "timelock"), ("chamber-vaults", "upgrade"), ("cian-yield-layer", "upgrade"),
    ("coinbase-wrapped-staked-eth", "timelock"), ("convergence-fi", "timelock"), ("convergence-fi", "upgrade"), ("debridge", "quorum"),
    ("decentralized-euro", "upgrade"), ("eigenpie", "timelock"), ("eigenpie", "upgrade"), ("falcon-finance-usdf-susdf", "timelock"),
    ("flokifi-locker", "quorum"), ("hop-protocol", "upgrade"), ("inceptionlrt-isolated-restaking", "upgrade"),
    ("inverse-finance-firm", "emergency"), ("kine-finance", "timelock"), ("layerzero-v2", "quorum"), ("layerzero-v2", "timelock"),
    ("layerzero-v2", "upgrade"), ("lendflare", "timelock"), ("lendflare", "upgrade"), ("liquity-v2-bold", "upgrade"),
    ("m0-protocol-m", "upgrade"), ("makina", "upgrade"), ("maple-finance-v2-syrup", "timelock"), ("mcdex", "timelock"),
    ("mcdex", "upgrade"), ("meta-pool-eth", "timelock"), ("meta-pool-eth", "upgrade"), ("metric-v1", "upgrade"),
    ("mev-capital-weth-metamorpho", "emergency"), ("morph-bridge", "upgrade"), ("odyssey-finance", "timelock"),
    ("odyssey-finance", "upgrade"), ("origin-superoeth-base", "quorum"), ("pickle", "upgrade"), ("polygon-bridge", "timelock"),
    ("railgun", "timelock"), ("railgun", "upgrade"), ("resupply", "emergency"), ("safe-singleton-core", "upgrade"),
    ("saturn", "upgrade"), ("sonic-gateway", "timelock"), ("sonic-gateway", "upgrade"), ("stake-dao", "upgrade"),
    ("stargate-v2", "timelock"), ("steakhouse-financial-ethereum", "emergency"), ("steakhouse-prime-usdc-base", "emergency"),
    ("steakhouse-usdc-metamorpho-base", "emergency"), ("steer-protocol", "timelock"), ("steer-protocol", "upgrade"),
    ("superform-v2-base", "upgrade"), ("sushiswap-v3", "timelock"), ("sushiswap-v3", "upgrade"), ("taiko-bridge", "quorum"),
    ("taiko-bridge", "timelock"), ("team-finance", "timelock"), ("team-finance", "upgrade"), ("tether-usdt", "timelock"),
    ("threshold-network-tbtc", "upgrade"), ("unitus", "timelock"), ("unitus", "upgrade"), ("usdt0", "timelock"), ("usdt0", "upgrade"),
    ("world-chain-bridge", "timelock"), ("world-chain-bridge", "upgrade"), ("wormhole-core-ntt", "emergency"), ("yieldfi", "upgrade"),
    ("yuzu-money", "upgrade"),
})
assert len(RULE_SLICES_87) == 87

_R87_FORBIDDEN = re.compile(r"\b(?:immutable|renounced|EOA)\b", re.I)
_R87_NONPROXY = re.compile(r"\bnot a proxy\b|\bnon-proxy\b|non-EIP-1967")
_R87_ZEROSLOT = re.compile(r"EIP-1967 (?:implementation )?slots? (?:=|is|are)?\s*(?:0x0{1,40}\b|0x00\.\.\.00|0\b)|EIP-1967 slots 0x0|"
                           r"implementation and admin storage slots are both zero")
_R87_UPATH = re.compile(r"ProxyAdmin|EIP-1967 admin|admin slot|AdminUpgradeabilityProxy|\bUUPS\b|upgradeAndCall|_authorizeUpgrade|proxyOwner\(\)|"
                        r"proxies whose admins|\bproxy admins?\b")
_R87_TL_INLINE = re.compile(r"timelock \((\d+) ?(d|h|s) delay\)")
_R87_EXEC_DELAY = re.compile(r"execution delay ([\d,]+) s\b")
_R87_OFFSET = re.compile(r"EXECUTION_START_OFFSET\(\)\s*=\s*([\d,]+)\s*s\b")
_R87_MINDELAY = re.compile(r"getMinDelay\(\)\s*(?:=|of)\s*([\d,]+)\s*s\b")
_R87_UNTIMED = re.compile(r"without a timelock|\bno timelock\b|\bno delay\b|duration 0\b|getMinDelay\(\)\s*=\s*0\b|\(0 ?s delay\)")
_R87_NOCODE = re.compile(r"externally owned|no contract code|\(no code\)")
_R87_BURN = re.compile(r"0x0{36}dead\b|0x0{40}\b", re.I)
_R87_QUORUM = [re.compile(p) for p in (
    r"signerThreshold\(\)\s*=\s*(\d{1,2})\s+of\s+(\d{1,2})\b",
    r"\bthreshold\(\)\s*=\s*(\d{1,2})\s+of\s+(?:totalSigners\(\)\s*=\s*)?(\d{1,2})\b",
    r"getThreshold\(\)\s*=\s*(\d{1,2})\s+of\s+(?:getOwners\(\)\s*=\s*)?(\d{1,2})\b",
    r"minApprovals\s*(?:\(\)\s*=\s*)?(\d{1,2})\s+of\s+(\d{1,2})\b",
    r"\bat least (\d{1,2}) of (\d{1,2}) oracle",
    r"\b(\d{1,2}) of the (\d{1,2}) full-power voters\b",
    r"\b(\d{1,2})-of-(\d{1,2})\b")]
_R87_GUARD_CTX = re.compile(r"MetaMorpho|\bGovernor\w*\b[^.;]{0,40}guardian\(\)|guardian\(\) wrapper|guardian set|Guardian VAA|guardian-signed")
_R87_PAUSE_ENDED = re.compile(r"getPausedState\(\)\s*=\s*\(false\b")
_R87_EMERG = re.compile(r"\b[Ee]mergency\b[^.;]{0,40}\bguardian\b|\bguardian\b[^.;]{0,40}\b[Ee]mergency\b|[Ee]mergency guardian")


def _r87_text(r):
    return f'{r.get("surface") or ""}. {r.get("onchain_observed") or ""}'


def _r87_ev(rid, t, m=None):
    """'<record id>: <the clause that decided the slice>' (whole-word clipped); the on-chain clause first, the record heading last."""
    if m is not None:
        head_, _, obs_ = t.partition(". ")
        for c in clauses(obs_) + clauses(head_):
            if m.group(0) in c:
                return f"{rid}: {_clip(c)}"
    return f"{rid}: {_clip(t)}"


def _r87_path_ev(r, t):
    """'<record id>: <clause>' for an untimed path: the on-chain clause naming the upgrade path and its holder (never the record heading)."""
    obs = str(r.get("onchain_observed") or "")
    cs = clauses(obs) or [obs]
    for want in (lambda c: _R87_UPATH.search(c) and (_nofs(c) or _R87_NOCODE.search(c)), lambda c: _R87_UPATH.search(c), lambda c: _nofs(c)):
        c = next((c for c in cs if want(c)), None)
        if c:
            return f"{r['id']}: {_clip(c)}"
    return _r87_ev(r["id"], t)


def _r87_secs(n, unit="s"):
    return int(str(n).replace(",", "")) * {"d": DAY, "h": 3600, "s": 1}[unit]


def _r87_upgrade_delay(r, t, records):
    """The delay gating this record's upgrade path: an inline 'timelock (N d delay)', an execution delay, a getMinDelay() of the
    timelock that owns the admin, or the delay of the last contract in the ownership chain read from a same-page sibling record."""
    m = _R87_TL_INLINE.search(t)
    if m:
        return _r87_secs(m.group(1), m.group(2)), m
    m = _R87_EXEC_DELAY.search(t)
    if m:
        return _r87_secs(m.group(1)), m
    d = r.get("observed_delay_seconds")
    if isinstance(d, int) and re.search(r"ProxyAdmin|\bowns\b|owner\(\) = the timelock|upgradeAndCall|[Uu]pgrade", t) and not _COOLDOWN.search(
            str(r.get("surface") or "")):
        m = _R87_MINDELAY.search(t) or re.search(r"\d", t)
        return d, m
    # sibling join: "... whose owner() is Voting 0x..." -> that contract's execution offset / min delay in another record
    chain = re.findall(r"(?:whose owner\(\) is|owner\(\) =)\s+(?:the )?([A-Z]\w*) (0x[0-9a-fA-F]{40})", t)
    if chain:
        name, addr = chain[-1]
        for s in records:
            if s is r:
                continue
            st = _r87_text(s)
            if addr.lower() in st.lower() or st.lstrip(". ").startswith(name) or str(s.get("onchain_observed") or "").startswith(name + " "):
                m2 = _R87_OFFSET.search(st) or _R87_MINDELAY.search(st)
                if m2:
                    return _r87_secs(m2.group(1)), None
    return None, None


def _r87_holder(r, t):
    """Who holds the upgrade path when no delay gates it: a K-of-N Safe or an account with no contract code."""
    q = r.get("safe_quorum")
    if isinstance(q, str) and re.fullmatch(r"\d{1,2}-of-\d{1,2}", q):
        return q
    if r.get("controller_kind") == "eoa" or (_R87_NOCODE.search(t) and re.search(r"admin slot (?:holds|=) (?:externally|0x)", t)):
        return "nocode"
    for m in _nofs(t):
        if m.re is _NOF_READS:
            return f"{m.group(1)}-of-{m.group(2)}"
        return f"{m.group(1)}-of-{m.group(2)}"
    return None


def _r87_upgrade_paths(records):
    """Every record that establishes an upgrade path, scored: a delay on the path (3), a named holder (2), the proxy alone (1)."""
    out = []
    for i, r in enumerate(records):
        t = _r87_text(r)
        if not _R87_UPATH.search(t) or _R87_NONPROXY.search(t) and not re.search(r"\bUUPS\b|ProxyAdmin", t):
            continue
        d, m = _r87_upgrade_delay(r, t, records)
        h = _r87_holder(r, t) if d is None else None
        out.append((3 if d is not None else 2 if h else 1, -i, r, t, d, h, m))
    return sorted(out, key=lambda x: (x[0], x[1]), reverse=True)


def _r87_quorum(t):
    for p in _R87_QUORUM:
        m = p.search(t)
        if m and 1 <= int(m.group(1)) <= int(m.group(2)):
            return int(m.group(1)), int(m.group(2)), m
    return None


def _r87_label(r):
    lbl = re.sub(r"\s*\((?:Ethereum|Base)[^)]*\)$", "", str(r.get("target_label") or "")).strip()
    return lbl if lbl and not _R87_FORBIDDEN.search(lbl) else "target contract"


def _rule_upgrade(records, base_rid):
    paths = _r87_upgrade_paths(records)
    if paths and paths[0][0] >= 2:                                                       # R1: an established upgrade path
        _, _, r, t, d, h, m = paths[0]
        if d is not None:
            st = "g" if d >= 2 * DAY else "b" if d >= 3600 else "a"
            val = (f"Upgradeable behind a ≥48h delay ({_dur(d)})" if st == "g" else f"Upgradeable behind a 1h–47h delay ({_dur(d)})" if st == "b"
                   else "Upgradeable with no enforced delay (0s timelock)")
            return st, val, _r87_ev(r["id"], t, m)
        holder = "an account with no contract code" if h == "nocode" else f"a {h} Safe"
        return "a", f"Upgradeable with no enforced delay: upgrade admin held by {holder}", _r87_path_ev(r, t)
    base = next((r for r in records if r["id"] == base_rid), None)                        # R2: the sampled target is not a proxy
    for r in ([base] if base else []) + [r for r in records if r is not base]:
        t = _r87_text(r)
        z, np_ = _R87_ZEROSLOT.search(t), _R87_NONPROXY.search(t)
        if np_ or z:
            lbl = _r87_label(r)
            if np_ and not re.search(r"EIP-1967 (?:implementation )?slots? (?:=|is)", t):
                return "n", f"Sampled {lbl} is not a proxy (non-proxy bytecode; other protocol contracts not assessed)", _r87_ev(r["id"], t, np_)
            return "n", f"Sampled {lbl} has an empty EIP-1967 implementation slot (0x0); other upgrade paths not assessed", _r87_ev(r["id"], t, z or np_)
    return None


def _rule_timelock(records):
    paths = _r87_upgrade_paths(records)
    for score, _, r, t, d, h, m in paths:                                                 # R1: an untimed upgrade path is a 0s surface
        if score == 2:
            return "a", "No enforced delay on at least one sampled control surface (0s)", _r87_path_ev(r, t)
    for r in records:                                                                     # R4: explicit untimed execution
        t = _r87_text(r)
        m = _R87_UNTIMED.search(t)
        if m and not _COOLDOWN.search(str(r.get("surface") or "")):
            return "a", "No enforced delay on at least one sampled control surface (0s)", _r87_ev(r["id"], t, m)
    for r in records:                                                                     # R1: onlyOwner functions held by a multisig, no delay
        t = _r87_text(r)
        m = re.search(r"\bonlyOwner\b", t)
        if m and _r87_quorum(t) and not (_R87_TL_INLINE.search(t) or _R87_MINDELAY.search(t) or _R87_OFFSET.search(t) or _DELAY.search(t)
                                          or re.search(r"[Tt]imelock|delay", t)):
            return "a", "No enforced delay on at least one sampled control surface (0s)", _r87_ev(r["id"], t, m)
    timed = []                                                                            # R4: explicit enforced delays
    for i, r in enumerate(records):
        t = _r87_text(r)
        for p in (_R87_TL_INLINE, _R87_OFFSET):
            m = p.search(t)
            if m:
                timed.append((_r87_secs(m.group(1), m.group(2)) if p is _R87_TL_INLINE else _r87_secs(m.group(1)), i, r, t, m))
                break
    if timed:
        d, _, r, t, m = min(timed, key=lambda x: (x[0], x[1]))
        st = "g" if d >= 2 * DAY else "b" if d >= 3600 else "a"
        return st, f"{_dur(d)} minimum enforced delay on sampled timelocked surfaces", _r87_ev(r["id"], t, m)
    return None


def _rule_quorum(records):
    for r in records:                                                                     # R5: a burn address holds no quorum
        t = _r87_text(r)
        m = re.search(r"owner\(\)[^.;]{0,60}?(0x0{36}dead|0x0{40})\b", t, re.I)
        if m and not _r87_quorum(t):
            return "n", "No active signer quorum in the published records (owner() is a burn address)", _r87_ev(r["id"], t, m)
    best = None                                                                           # R1 / R4: a recorded multi-signer quorum
    for i, r in enumerate(records):
        t = _r87_text(r)
        q = _r87_quorum(str(r.get("onchain_observed") or "")) or _r87_quorum(str(r.get("surface") or ""))
        if q and (best is None or (q[0], i) < (best[0][0], best[1])):
            best = (q, i, r, t)
    if best:
        (k, n, m), _, r, t = best
        return ("g" if k >= 3 else "b" if k == 2 else "a"), f"Known controlling quorum: {k}-of-{n}", _r87_ev(r["id"], t, m)
    return None


def _rule_emergency(records, base_rid):
    r = next((x for x in records if x["id"] == base_rid), None)
    if r is None:
        return None
    t = _r87_text(r)
    m = _R87_PAUSE_ENDED.search(t)
    if m:                                                                                 # R3: an ended pause window is no pause power
        return "n", "Pause window ended before the pinned block (getPausedState() = false)", _r87_ev(r["id"], t, m)
    m = _R87_GUARD_CTX.search(t)
    if m:                                                                                 # R3: a non-pause guardian role
        return ("n", "A guardian role is recorded; no pause / freeze authority is established in the published records",
                _r87_ev(r["id"], t, m))
    m = _R87_EMERG.search(t)
    if m:                                                                                 # R1: the emergency guardian's own quorum
        holder = re.search(r"guardian\(\)\s*=\s*[\w ]*?(0x[0-9a-fA-F]{40})", t)
        for s in records:
            st_ = _r87_text(s)
            q = _r87_quorum(st_)
            if holder and holder.group(1).lower() in st_.lower() and q and q[0] >= 2:
                return ("g", f"Pause / freeze authority scoped behind a multi-signer controller ({q[0]}-of-{q[1]})", _r87_ev(r["id"], t, m))
    return None


def _rules_87(slug, records, out):
    """Apply R1-R5 to this protocol's reviewed slices only (RULE_SLICES_87); every other factor is left exactly as derived."""
    keys = [k for k, _ in FACTORS if (slug, k) in RULE_SLICES_87]
    for k in keys:
        base_rid = (out.get(k, (None, None, None))[2] or "").split(": ", 1)[0] or None
        res = (_rule_upgrade(records, base_rid) if k == "upgrade" else _rule_timelock(records) if k == "timelock"
               else _rule_quorum(records) if k == "quorum" else _rule_emergency(records, base_rid) if k == "emergency" else None)
        if res is not None:
            assert not _R87_FORBIDDEN.search(res[1]), (slug, k, res[1])
            out[k] = res
