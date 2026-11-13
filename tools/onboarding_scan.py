"""Scan the live onboarding-verification targets and write docs/api/v1/onboarding.json (read-only JSON-RPC, stdlib only).

Every value in the five onboarding briefs comes from this file's output; tools/build_site.py renders the briefs from it, so
prose and data cannot drift. Each check is an eth_call / eth_getStorageAt / eth_getCode / eth_getTransactionCount read
pinned to a canonical block with EIP-1898 {blockHash, requireCanonical: true}, executed on two independent RPC endpoints
per chain and compared byte for byte (any disagreement aborts). Role maps are replayed from event logs between the
contract's deployment block and the pinned block; the log range, event count and log RPC are recorded for replay.

  python3 tools/onboarding_scan.py            # ~5-15 min (paced eth_getLogs); writes docs/api/v1/onboarding.json
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "api", "v1", "onboarding.json")
CHAINS = {
    "base": {"chain_id": 8453, "blockscout": "https://base.blockscout.com", "rpcs": ["https://mainnet.base.org", "https://base-rpc.publicnode.com", "https://base.gateway.tenderly.co", "https://base.llamarpc.com"],
             "log_rpcs": ["https://mainnet.base.org", "https://base-rpc.publicnode.com"],
             "pin": (57050397, "0xd6d02efb420f81b3f0e095d78453362c4488afb9adc0f8e1c411bb265beb88a7"), "explorer": "https://basescan.org"},
    "eth": {"chain_id": 1, "blockscout": "https://eth.blockscout.com", "rpcs": ["https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io", "https://ethereum-rpc.publicnode.com", "https://eth.llamarpc.com"],
            "log_rpcs": ["https://gateway.tenderly.co/public/mainnet", "https://ethereum-rpc.publicnode.com"],
            "pin": (26408330, "0x8efc8256deb932e65b5117f040db264dc8200850636d90eecd5daccb99979f4d"), "explorer": "https://etherscan.io"},
}
EIP1967_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
EIP1967_ADMIN = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# --------------------------------------------------------------------------------------------- keccak-256 (stdlib) --
_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
       0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
       0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
       0x000000000000800A, 0x800000008000000A, 0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_R = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M = (1 << 64) - 1


def keccak(data: bytes) -> bytes:
    msg = bytearray(data) + b"\x01"
    while len(msg) % 136:
        msg.append(0)
    msg[-1] |= 0x80
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(msg), 136):
        for i in range(17):
            a[i % 5][i // 5] ^= int.from_bytes(msg[off + 8 * i:off + 8 * i + 8], "little")
        for rc in _RC:
            c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
            d = [c[(x - 1) % 5] ^ (((c[(x + 1) % 5] << 1) | (c[(x + 1) % 5] >> 63)) & _M) for x in range(5)]
            a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
            b = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    r = _R[x][y]
                    b[y][(2 * x + 3 * y) % 5] = ((a[x][y] << r) | (a[x][y] >> (64 - r))) & _M if r else a[x][y]
            a = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
            a[0][0] ^= rc
    return b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


def eip55(addr: str) -> str:
    body = addr[2:].lower()
    h = keccak(body.encode()).hex()
    return "0x" + "".join(ch.upper() if ch.isalpha() and int(h[i], 16) >= 8 else ch for i, ch in enumerate(body))


def selector(sig: str) -> str:
    return "0x" + keccak(sig.encode()).hex()[:8]


def topic(sig: str) -> str:
    return "0x" + keccak(sig.encode()).hex()


def word(arg) -> str:
    if isinstance(arg, int):
        return hex(arg)[2:].rjust(64, "0")
    return arg[2:].lower().rjust(64, "0")


# ------------------------------------------------------------------------------------------------------- JSON-RPC ---
class Rpc:
    def __init__(self, chain):
        self.c = CHAINS[chain]
        self.pin = {"blockHash": self.c["pin"][1], "requireCanonical": True}
        self.used = set()                      # endpoints that actually answered (and agreed) for this target

    @staticmethod
    def raw(url, method, params, tries=6):
        delay = 1.0
        for i in range(tries):
            req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": "pacta-onboarding-scan/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    resp = json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504, 525) and i < tries - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                raise
            if resp.get("id") != 1 or "error" in resp:
                raise RuntimeError(f"{method}: {resp.get('error')}")
            return resp["result"]
        raise RuntimeError(f"{method}: retries exhausted")

    def both(self, method, params):
        """Answer from the first two endpoints (in configured order) that respond; they must agree byte for byte.
        A JSON-RPC error (e.g. a revert) on a healthy endpoint is final, not a reason to shop for another endpoint."""
        got, errs = [], []
        for u in self.c["rpcs"]:
            try:
                got.append((u, self.raw(u, method, params, tries=3)))
            except (urllib.error.URLError, OSError) as ex:      # transport / HTTP-level failure: try the next endpoint
                errs.append(f"{u}: {ex}")
                continue
            if len(got) == 2:
                break
        if len(got) < 2:
            raise RuntimeError(f"{method}: fewer than two endpoints answered ({errs})")
        (u1, a), (u2, b) = got
        if a != b:
            raise RuntimeError(f"RPC disagreement on {method} {params}: {u1} {a!r} vs {u2} {b!r}")
        self.used.update((u1, u2))
        return a

    def logs(self, address, topics, frm, to, step=50000):
        """Paced, adaptive eth_getLogs over [frm, to] on the first log RPC that answers."""
        last = None
        for url in self.c["log_rpcs"]:
            try:
                out, s, st, waits = [], frm, step, 0
                while s <= to:
                    e = min(to, s + st - 1)
                    try:
                        out += self.raw(url, "eth_getLogs", [{"address": address, "fromBlock": hex(s), "toBlock": hex(e), "topics": [topics]}])
                        s, waits = e + 1, 0
                        time.sleep(0.2)
                    except RuntimeError as ex:          # range-limit style errors: shrink the window
                        if st <= 500:
                            raise
                        st = max(500, st // 5)
                        last = ex
                    except urllib.error.HTTPError as ex:  # rate limits that outlived raw()'s retries: wait, then continue
                        waits += 1
                        if ex.code not in (429, 503) or waits > 3:
                            raise
                        time.sleep(20)
                        last = ex
                return out, url
            except (RuntimeError, OSError) as ex:
                last = ex
        raise RuntimeError(f"eth_getLogs failed on every log RPC: {last}")

    def logs_via_explorer(self, address, topics, frm, to, max_pages=400):
        """Fallback when public eth_getLogs is rate-limited: page the Blockscout v2 address-log index, keep the wanted
        topics within [frm, to], then VERIFY every kept log against its transaction receipt on two RPC endpoints (same block,
        log index, topics and data; receipt block hash canonical). The explorer is only an index; the chain is the source."""
        base = f'{self.c["blockscout"]}/api/v2/addresses/{address}/logs'
        want, out, params, pages = {t.lower() for t in topics}, [], None, 0
        while pages < max_pages:
            url = base + ("?" + urllib.parse.urlencode(params) if params else "")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (pacta-onboarding-scan/1.0)", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                page = json.loads(r.read())
            pages += 1
            for it in page.get("items") or []:
                tps = [t for t in (it.get("topics") or []) if t]
                bn = int(it["block_number"])
                if tps and tps[0].lower() in want and frm <= bn <= to:
                    out.append({"blockNumber": hex(bn), "logIndex": hex(int(it["index"])), "transactionHash": it["transaction_hash"],
                                "topics": [t.lower() for t in tps], "data": it.get("data") or "0x"})
            params = page.get("next_page_params")
            if not params:
                break
            time.sleep(0.3)
        else:
            raise RuntimeError("explorer pagination exceeded max_pages")
        for lg in out:
            rc = self.both("eth_getTransactionReceipt", [lg["transactionHash"]])
            hit = [x for x in rc["logs"] if int(x["logIndex"], 16) == int(lg["logIndex"], 16)]
            if not hit or hit[0]["address"].lower() != address.lower() or [t.lower() for t in hit[0]["topics"]] != lg["topics"] \
                    or hit[0]["data"].lower() != lg["data"].lower() or int(rc["blockNumber"], 16) != int(lg["blockNumber"], 16):
                raise RuntimeError(f"explorer log does not match the receipt: {lg['transactionHash']} #{lg['logIndex']}")
            canon = self.both("eth_getBlockByNumber", [rc["blockNumber"], False])["hash"]
            if canon != rc["blockHash"]:
                raise RuntimeError(f"non-canonical receipt block for {lg['transactionHash']}")
        return out, f'{self.c["blockscout"]} (index) + receipt verification on {len(self.c["rpcs"])}-endpoint cross-check' 


# ----------------------------------------------------------------------------------------------------- decoders -----
def d_addr(raw):
    return eip55("0x" + raw[-40:])


def d_uint(raw):
    return int(raw, 16)


def d_bool(raw):
    return int(raw, 16) == 1


def d_string(raw):
    b = bytes.fromhex(raw[2:])
    off = int.from_bytes(b[:32], "big")
    n = int.from_bytes(b[off:off + 32], "big")
    return b[off + 32:off + 32 + n].decode("utf-8", "replace")


def d_addr_array(raw):
    b = bytes.fromhex(raw[2:])
    off = int.from_bytes(b[:32], "big")
    n = int.from_bytes(b[off:off + 32], "big")
    return [eip55("0x" + b[off + 32 + 32 * i + 12: off + 64 + 32 * i].hex()) for i in range(n)]


def d_words(raw):
    return [int(raw[2 + 64 * i: 66 + 64 * i], 16) for i in range((len(raw) - 2) // 64)]


def amount_cap(v):
    """Euler EVK AmountCap: 0 = no cap; else 10**(v & 63) * (v >> 6) / 100 (in asset units)."""
    return None if v == 0 else 10 ** (v & 63) * (v >> 6) // 100


DECODERS = {"address": d_addr, "uint": d_uint, "bool": d_bool, "string": d_string, "address[]": d_addr_array, "words": d_words,
            "raw": lambda r: r}


# ------------------------------------------------------------------------------------------------- the targets -----
def C(id_, label, to, sig, dec, args=()):
    return {"id": id_, "kind": "eth_call", "label": label, "to": to, "sig": sig, "args": list(args), "decode": dec}


def S(id_, label, to, slot):
    return {"id": id_, "kind": "eth_getStorageAt", "label": label, "to": to, "slot": slot, "decode": "address"}


def K(id_, label, to):
    return {"id": id_, "kind": "eth_getCode", "label": label, "to": to}


def N(id_, label, to):
    return {"id": id_, "kind": "eth_getTransactionCount", "label": label, "to": to}


KUSD_TL, KUSD_MINTER = "0x36A14976980B7Dd33136f6613545EB0A2C0a0D72", "0xaBDE1138aa1Ce88d1dF06422C0c3b05D70569803"
EFIX_MINTER = "0x8f8CD5cC7131BF24fE9BF674D58de6dC624dCCb1"
KUSD, EUSDC_K, EKUSD, ROUTER_K, FIXED_K, SAFE_K = ("0x5C2EfdF0D8D286959b42308966bc2B97f5680AA3", "0xe87c294E1139C31770727193e3Be0ccEd73d6AA3",
                                                   "0xD3800ceb6bBeB90101ed5d5A46017fE846c9509e", "0xB95407727d33fB2E444966fd0B7D0E7767Ce019E",
                                                   "0x8f27228f02E798c17B7d6b270F32F8EC6afDD2D3", "0x52d3E450Ba6c299b1b07298F1E87dD74732D4877")
EUSDC_E, ESCROW_E, ROUTER_E, ORACLE_E, SAFE_E, EFIXDI, EFIX, EFIX_OWNER = (
    "0xe276BB91E0C63C0BC6ABdd3Dc37DF324f90e3956", "0x008a506c6b6138F47B82f6a0b8Fc7FE375C102e9", "0x5F655525A46B968CF388865CeBC0c0B79A8F8a2b",
    "0x9CD219A773d94BBECdD1bb0ae413c45f72737788", "0x9040b4E9e1F8C96dC6dEF1a2d6f4105D8535EeD4", "0xf5CA55F3eA5BcD180Aea6Df9E05a0E63a66f5608",
    "0x400a8DE2bF8fc4A63000A7E77103eDAE897CB9a3", "0x7c54DCcD6FC5Db73b34F32aCa4d1631E054c7537")
CIRBTC = "0x72DFB2E44f59C5AD2bAFE84314E5b99a7cd5075E"
PAXGY, PAXGY_TL, PAXGY_AUTH, PAXGY_ACC, PAXGY_TELLER, PAXGY_TELLER_OLD, PAXGY_MANAGER, PAXGY_SAFE, PAXGY_RATE_EOA = (
    "0x6c6494Fd9962eB98B94ffA48F6679058F820700e", "0x0dcC87bC40E775A8207EB2E65b68CF51964cdf08", "0xC444dA4dF6aF6A9a3891a720C1712A4188D899dd",
    "0x397E38359F169748A02bc11f98d4F451fe88C1FD", "0x41AB5D8387e60E30aaCCF11357c306F6D875a6f7", "0x5c43AD60BEB32F88D14296fEf67eC0F329F3fe72",
    "0x353741abA79974a90f88594F6cBD1A9c54651015", "0x0000000000417626Ef34D62C4DC189b021603f2F", "0x1755397BEC366a1E1160D8ae0106C60e7e344B56")
USAT, USAT_MSIG, ETHENA_TL = "0x07041776f5007ACa2A54844F50503a18A72A8b68", "0x62B3a0F6ffC5Efd7692053a9040fE44F9aC8c5Cb", "0xE8Dc0Fab349EA169283C48Ccfd09d797E6DB7c94"
ZERO_ROLE = "0x" + "00" * 32
ETHENA_OPS = ["0x1fe5e3e892708310bbfcf50efc03a1b8e21e0d0042035d7e8315e0cd5f26d85b", "0x0ca0fcc4856b87f3df9a74532bd60db58d1310c27c17e7d9bfa8a56846f57a90"]

TARGETS = [
    {"slug": "kerne-kusd-base", "chain": "base", "asset": "kUSD (Kerne)", "venue": "Euler (Base) · isolated kUSD/USDC market",
     "forum": {"name": "Euler forum", "topic": 1862, "url": "https://forum.euler.finance/t/1862",
               "title": "kUSD/USDC isolated market on Euler Base: deployed, ungoverned, and an underwriting packet for curators"},
     "checks": [
         C("k_supply", "kUSD totalSupply()", KUSD, "totalSupply()", "uint"), C("k_dec", "kUSD decimals()", KUSD, "decimals()", "uint"),
         C("k_symbol", "kUSD symbol()", KUSD, "symbol()", "string"),
         C("k_ac", "kUSD supportsInterface(IAccessControl)", KUSD, "supportsInterface(bytes4)", "bool", ["0x7965db0b" + "00" * 28]),
         C("v_gov", "eUSDC vault governorAdmin()", EUSDC_K, "governorAdmin()", "address"),
         C("v_oracle", "eUSDC vault oracle()", EUSDC_K, "oracle()", "address"),
         C("v_caps", "eUSDC vault caps() (supplyCap, borrowCap)", EUSDC_K, "caps()", "words"),
         C("v_ltvb", "eUSDC LTVBorrow(ekUSD)", EUSDC_K, "LTVBorrow(address)", "uint", [EKUSD]),
         C("v_ltvl", "eUSDC LTVLiquidation(ekUSD)", EUSDC_K, "LTVLiquidation(address)", "uint", [EKUSD]),
         C("v_assets", "eUSDC totalAssets()", EUSDC_K, "totalAssets()", "uint"), C("v_borrows", "eUSDC totalBorrows()", EUSDC_K, "totalBorrows()", "uint"),
         C("c_gov", "ekUSD escrow governorAdmin()", EKUSD, "governorAdmin()", "address"), C("c_asset", "ekUSD escrow asset()", EKUSD, "asset()", "address"),
         C("c_assets", "ekUSD escrow totalAssets()", EKUSD, "totalAssets()", "uint"),
         C("r_gov", "EulerRouter governor()", ROUTER_K, "governor()", "address"),
         C("r_oracle", "EulerRouter getConfiguredOracle(kUSD, USDC)", ROUTER_K, "getConfiguredOracle(address,address)", "address", [KUSD, USDC_BASE]),
         C("o_quote", "FixedRateOracle getQuote(1e18 kUSD -> USDC)", FIXED_K, "getQuote(uint256,address,address)", "uint", [10 ** 18, KUSD, USDC_BASE]),
         C("s_threshold", "Kerne Safe getThreshold()", SAFE_K, "getThreshold()", "uint"), C("s_owners", "Kerne Safe getOwners()", SAFE_K, "getOwners()", "address[]"),
         C("s_admin", "kUSD hasRole(DEFAULT_ADMIN_ROLE, Kerne Safe)", KUSD, "hasRole(bytes32,address)", "bool", [ZERO_ROLE, SAFE_K]),
         C("k_admin_tl", "kUSD hasRole(DEFAULT_ADMIN_ROLE, admin timelock)", KUSD, "hasRole(bytes32,address)", "bool", [ZERO_ROLE, KUSD_TL]),
         C("tl_delay", "kUSD admin timelock getMinDelay()", KUSD_TL, "getMinDelay()", "uint"),
         C("tl_prop", "timelock hasRole(PROPOSER_ROLE, Kerne Safe)", KUSD_TL, "hasRole(bytes32,address)", "bool", ["0x" + keccak(b"PROPOSER_ROLE").hex(), SAFE_K]),
         C("tl_exec", "timelock hasRole(EXECUTOR_ROLE, Kerne Safe)", KUSD_TL, "hasRole(bytes32,address)", "bool", ["0x" + keccak(b"EXECUTOR_ROLE").hex(), SAFE_K]),
         C("tl_canc", "timelock hasRole(CANCELLER_ROLE, Kerne Safe)", KUSD_TL, "hasRole(bytes32,address)", "bool", ["0x" + keccak(b"CANCELLER_ROLE").hex(), SAFE_K]),
         C("k_minter", "kUSD hasRole(MINTER_ROLE, minter contract)", KUSD, "hasRole(bytes32,address)", "bool", ["0x" + keccak(b"MINTER_ROLE").hex(), KUSD_MINTER]),
         C("m_kusd", "minter contract kUSD()", KUSD_MINTER, "kUSD()", "address"), C("m_paused", "minter contract paused()", KUSD_MINTER, "paused()", "bool"),
         C("m_admin_tl", "minter hasRole(DEFAULT_ADMIN_ROLE, admin timelock)", KUSD_MINTER, "hasRole(bytes32,address)", "bool", [ZERO_ROLE, KUSD_TL]),
     ],
     "role_logs": [{"id": "kusd_roles", "label": "kUSD AccessControl role history", "address": KUSD, "kind": "access_control"},
                   {"id": "kusd_timelock", "label": "kUSD admin TimelockController role history", "address": KUSD_TL, "kind": "access_control"},
                   {"id": "kusd_minter", "label": "kUSD minter contract role history", "address": KUSD_MINTER, "kind": "access_control"}]},
    {"slug": "efix-efixdi-base", "chain": "base", "asset": "efixDI+ (EFIX)", "venue": "Euler (Base) · efixDI/USDC market (governedPerspective request)",
     "forum": {"name": "Euler forum", "topic": 1850, "url": "https://forum.euler.finance/t/1850",
               "title": "efixDI/USDC on Base — tokenized Brazilian DI fund, D+0 NAV redemption (governedPerspective whitelist)"},
     "checks": [
         C("v_gov", "eUSDC vault governorAdmin()", EUSDC_E, "governorAdmin()", "address"),
         C("v_oracle", "eUSDC vault oracle()", EUSDC_E, "oracle()", "address"),
         C("v_caps", "eUSDC vault caps() (supplyCap, borrowCap)", EUSDC_E, "caps()", "words"),
         C("v_ltvb", "eUSDC LTVBorrow(escrow)", EUSDC_E, "LTVBorrow(address)", "uint", [ESCROW_E]),
         C("v_ltvl", "eUSDC LTVLiquidation(escrow)", EUSDC_E, "LTVLiquidation(address)", "uint", [ESCROW_E]),
         C("v_fee", "eUSDC interestFee()", EUSDC_E, "interestFee()", "uint"),
         C("v_assets", "eUSDC totalAssets()", EUSDC_E, "totalAssets()", "uint"), C("v_borrows", "eUSDC totalBorrows()", EUSDC_E, "totalBorrows()", "uint"),
         C("c_gov", "escrow governorAdmin()", ESCROW_E, "governorAdmin()", "address"), C("c_asset", "escrow asset()", ESCROW_E, "asset()", "address"),
         C("r_gov", "EulerRouter governor()", ROUTER_E, "governor()", "address"),
         C("r_oracle", "EulerRouter getConfiguredOracle(efixDI+, USDC)", ROUTER_E, "getConfiguredOracle(address,address)", "address", [EFIXDI, USDC_BASE]),
         C("o_name", "NAV oracle name()", ORACLE_E, "name()", "string"),
         C("s_threshold", "Governor Safe getThreshold()", SAFE_E, "getThreshold()", "uint"), C("s_owners", "Governor Safe getOwners()", SAFE_E, "getOwners()", "address[]"),
         C("t_supply", "efixDI+ totalSupply()", EFIXDI, "totalSupply()", "uint"), C("t_paused", "efixDI+ paused()", EFIXDI, "paused()", "bool"),
         C("t_admin", "efixDI+ hasRole(DEFAULT_ADMIN_ROLE, Governor Safe)", EFIXDI, "hasRole(bytes32,address)", "bool", [ZERO_ROLE, SAFE_E]),
         C("t_minter", "efixDI+ hasRole(MINTER_ROLE, Safe signer account)", EFIXDI, "hasRole(bytes32,address)", "bool", ["0x" + keccak(b"MINTER_ROLE").hex(), EFIX_MINTER]),
         N("t_minter_nonce", "Safe signer account transaction count", EFIX_MINTER), K("t_minter_code", "Safe signer account eth_getCode", EFIX_MINTER),
         C("e_owner", "EFIX owner()", EFIX, "owner()", "address"),
         K("e_owner_code", "EFIX owner eth_getCode (EIP-7702 designator = 0xef0100 || delegate)", EFIX_OWNER),
         N("e_owner_nonce", "EFIX owner transaction count", EFIX_OWNER),
     ],
     "role_logs": {"id": "efixdi_roles", "label": "efixDI+ AccessControl role history", "address": EFIXDI, "kind": "access_control"}},
    {"slug": "circle-cirbtc-eth", "chain": "eth", "asset": "cirBTC (Circle)", "venue": "Aave V3 Core / V4 Core (Ethereum)",
     "forum": {"name": "Aave governance", "topic": 25128, "url": "https://governance.aave.com/t/25128",
               "title": "[ARFC] Onboard cirBTC on Aave v3 Core and Aave V4 Core"},
     "checks": [
         C("t_supply", "cirBTC totalSupply()", CIRBTC, "totalSupply()", "uint"), C("t_dec", "cirBTC decimals()", CIRBTC, "decimals()", "uint"),
         C("t_version", "cirBTC version()", CIRBTC, "version()", "string"), C("t_paused", "cirBTC paused()", CIRBTC, "paused()", "bool"),
         C("p_admin", "proxy admin()", CIRBTC, "admin()", "address"), C("p_impl", "proxy implementation()", CIRBTC, "implementation()", "address"),
         C("r_owner", "owner()", CIRBTC, "owner()", "address"), C("r_mm", "masterMinter()", CIRBTC, "masterMinter()", "address"),
         C("r_pauser", "pauser()", CIRBTC, "pauser()", "address"), C("r_bl", "blacklister()", CIRBTC, "blacklister()", "address"),
         C("r_rescuer", "rescuer()", CIRBTC, "rescuer()", "address"),
     ],
     "follow": [("p_admin", "admin"), ("r_owner", "owner"), ("r_pauser", "pauser"), ("r_bl", "blacklister"), ("r_mm", "masterMinter")],
     "follow_owner": ["r_mm"]},
    {"slug": "paxos-paxgy-eth", "chain": "eth", "asset": "PAXGy (Paxos Labs)", "venue": "Aave V4 Global Dollar Hub (Ethereum)",
     "forum": {"name": "Aave governance", "topic": 25499, "url": "https://governance.aave.com/t/25499",
               "title": "[ARFC] Onboard PAXGy to Aave V4 Global Dollar Hub"},
     "checks": [
         C("v_supply", "PAXGy totalSupply()", PAXGY, "totalSupply()", "uint"), C("v_dec", "PAXGy decimals()", PAXGY, "decimals()", "uint"),
         C("v_owner", "PAXGy owner()", PAXGY, "owner()", "address"), C("v_auth", "PAXGy authority()", PAXGY, "authority()", "address"),
         C("tl_delay", "Timelock getMinDelay()", PAXGY_TL, "getMinDelay()", "uint"),
         C("a_owner", "RolesAuthority owner()", PAXGY_AUTH, "owner()", "address"),
         C("acc_state", "Accountant accountantState()", PAXGY_ACC, "accountantState()", "words"),
         C("acc_rate", "Accountant getRate()", PAXGY_ACC, "getRate()", "uint"), C("acc_owner", "Accountant owner()", PAXGY_ACC, "owner()", "address"),
         C("te_paused", "Teller isPaused()", PAXGY_TELLER, "isPaused()", "bool"), C("te_owner", "Teller owner()", PAXGY_TELLER, "owner()", "address"),
         C("te_lock", "Teller shareLockPeriod()", PAXGY_TELLER, "shareLockPeriod()", "uint"),
         C("old_paused", "Previous teller isPaused()", PAXGY_TELLER_OLD, "isPaused()", "bool"),
         C("m_owner", "Manager owner()", PAXGY_MANAGER, "owner()", "address"),
         C("safe_threshold", "Operations Safe getThreshold()", PAXGY_SAFE, "getThreshold()", "uint"),
         C("safe_owners", "Operations Safe getOwners()", PAXGY_SAFE, "getOwners()", "address[]"),
         K("eoa_code", "Rate-updater account eth_getCode", PAXGY_RATE_EOA), N("eoa_nonce", "Rate-updater account transaction count", PAXGY_RATE_EOA),
     ],
     "role_logs": [{"id": "paxgy_authority", "label": "RolesAuthority capability history", "address": PAXGY_AUTH, "kind": "solmate_roles"},
                   {"id": "paxgy_timelock", "label": "TimelockController role history", "address": PAXGY_TL, "kind": "access_control"}]},
    {"slug": "tether-usat-eth", "chain": "eth", "asset": "USAT (Tether America / Anchorage)", "venue": "Aave (USAT assessments) · Ethereum canonical token",
     "forum": {"name": "Aave governance", "topic": 25927, "url": "https://governance.aave.com/t/25927",
               "title": "Tether America USD (USAT) on Aave Avalanche Assessments"},
     "checks": [
         C("t_supply", "USAT totalSupply()", USAT, "totalSupply()", "uint"), C("t_dec", "USAT decimals()", USAT, "decimals()", "uint"),
         S("p_impl", "EIP-1967 implementation slot", USAT, EIP1967_IMPL), S("p_admin", "EIP-1967 admin slot (ProxyAdmin)", USAT, EIP1967_ADMIN),
         C("t_owner", "USAT owner()", USAT, "owner()", "address"),
         C("m_required", "Controller multisig required()", USAT_MSIG, "required()", "uint"),
         C("m_owners", "Controller multisig getOwners()", USAT_MSIG, "getOwners()", "address[]"),
         K("m_code", "Controller multisig eth_getCode", USAT_MSIG),
         C("e_delay", "Ethena timelock getMinDelay()", ETHENA_TL, "getMinDelay()", "uint"),
         C("e_op1", "Ethena op 0x1fe5 isOperationPending()", ETHENA_TL, "isOperationPending(bytes32)", "bool", [ETHENA_OPS[0]]),
         C("e_op2", "Ethena op 0x0ca0 isOperationPending()", ETHENA_TL, "isOperationPending(bytes32)", "bool", [ETHENA_OPS[1]]),
         C("e_op2_eta", "Ethena op 0x0ca0 getTimestamp()", ETHENA_TL, "getTimestamp(bytes32)", "uint", [ETHENA_OPS[1]]),
     ],
     "follow_slot_owner": ["p_admin"]},
]


# ------------------------------------------------------------------------------------------------ execution -------
def normalize(ch):
    """EIP-55 every address in a check spec (target and address-typed arguments)."""
    ch = dict(ch, to=eip55(ch["to"]))
    if ch.get("args"):
        ch["args"] = [eip55(a) if isinstance(a, str) and len(a) == 42 and a.startswith("0x") else a for a in ch["args"]]
    return ch


def run_check(rpc, ch):
    ch = normalize(ch)
    out = {k: v for k, v in ch.items() if k != "decode"}
    if ch["kind"] == "eth_call":
        data = selector(ch["sig"]) + "".join(word(a) for a in ch["args"])
        raw = rpc.both("eth_call", [{"to": ch["to"], "data": data}, rpc.pin])
        out.update(calldata=data, raw=raw, value=DECODERS[ch["decode"]](raw))
    elif ch["kind"] == "eth_getStorageAt":
        raw = rpc.both("eth_getStorageAt", [ch["to"], ch["slot"], rpc.pin])
        out.update(raw=raw, value=d_addr(raw))
    elif ch["kind"] == "eth_getCode":
        raw = rpc.both("eth_getCode", [ch["to"], rpc.pin])
        out.update(code_bytes=(len(raw) - 2) // 2, value=raw if len(raw) <= 2 + 2 * 64 else raw[:2 + 2 * 32] + "…")
        if raw.startswith("0xef0100") and len(raw) == 2 + 46:
            out["eip7702_delegate"] = eip55("0x" + raw[8:])
    elif ch["kind"] == "eth_getTransactionCount":
        raw = rpc.both("eth_getTransactionCount", [ch["to"], rpc.pin])
        out.update(raw=raw, value=int(raw, 16))
    return out


def account_info(rpc, addr):
    code = rpc.both("eth_getCode", [addr, rpc.pin])
    nonce = int(rpc.both("eth_getTransactionCount", [addr, rpc.pin]), 16)
    info = {"address": eip55(addr), "code_bytes": (len(code) - 2) // 2, "nonce": nonce}
    if code.startswith("0xef0100") and len(code) == 48:
        info["eip7702_delegate"] = eip55("0x" + code[8:])
    return info


def classify(rpc, addr):
    """Who is this account at the pinned block: EOA (nonce, EIP-7702 delegate), Safe (threshold / owners) or other contract."""
    info = account_info(rpc, addr)
    if info["code_bytes"] and not info.get("eip7702_delegate"):
        try:
            th = d_uint(rpc.both("eth_call", [{"to": info["address"], "data": selector("getThreshold()")}, rpc.pin]))
            ow = d_addr_array(rpc.both("eth_call", [{"to": info["address"], "data": selector("getOwners()")}, rpc.pin]))
            info.update(kind="safe", threshold=th, owners=ow)
        except (RuntimeError, ValueError, IndexError):
            info["kind"] = "contract"
    else:
        info["kind"] = "eoa"
    return info


def enrich_holders(rpc, brief):
    """Classify every role holder in the brief's role maps (and the Safes the brief already reads)."""
    seen = {}
    for m in brief["role_maps"]:
        for r in m["roles"]:
            for h in r["holders"]:
                if h not in seen:
                    seen[h] = classify(rpc, h)
    safes = {c["to"]: c["value"] for c in brief["checks"] if c.get("sig") == "getOwners()"}
    for h, info in seen.items():
        info["owner_of_safes"] = sorted(sa for sa, owners in safes.items() if h in owners)
    brief["holders"] = seen
    return brief


def deploy_block(rpc, addr):
    lo, hi = 1, rpc.c["pin"][0]
    while lo < hi:
        m = (lo + hi) // 2
        if len(rpc.raw(rpc.c["rpcs"][0], "eth_getCode", [addr, hex(m)])) > 2:
            hi = m
        else:
            lo = m + 1
    return lo


AC_TOPICS = {topic("RoleGranted(bytes32,address,address)"): "granted", topic("RoleRevoked(bytes32,address,address)"): "revoked"}
SOL_TOPICS = {topic("UserRoleUpdated(address,uint8,bool)"): "user", topic("RoleCapabilityUpdated(uint8,address,bytes4,bool)"): "cap",
              topic("PublicCapabilityUpdated(address,bytes4,bool)"): "public", topic("OwnershipTransferred(address,address)"): "owner"}
ROLE_NAMES = {ZERO_ROLE: "DEFAULT_ADMIN_ROLE"} | {topic(n): n for n in (
    "MINTER_ROLE", "BURNER_ROLE", "PAUSER_ROLE", "UNPAUSER_ROLE", "UPGRADER_ROLE", "OPERATOR_ROLE", "MANAGER_ROLE", "ADMIN_ROLE",
    "PROPOSER_ROLE", "EXECUTOR_ROLE", "CANCELLER_ROLE", "TIMELOCK_ADMIN_ROLE", "BLACKLISTER_ROLE", "BLACKLIST_MANAGER_ROLE",
    "WHITELISTER_ROLE", "RESCUER_ROLE", "GATEKEEPER_ROLE", "FREEZER_ROLE", "MINT_ROLE", "BURN_ROLE", "PSM_ROLE", "KEEPER_ROLE",
    "ORACLE_ROLE", "GUARDIAN_ROLE", "SENTINEL_ROLE", "CURATOR_ROLE", "TREASURY_ROLE", "STRATEGIST_ROLE", "MINTER", "BURNER")}
SELECTOR_SIGS = ("manage(address,bytes,uint256)", "manage(address[],bytes[],uint256[])", "enter(address,address,uint256,address,uint256)",
                 "exit(address,address,uint256,address,uint256)", "pause()", "unpause()", "updateExchangeRate(uint96)",
                 "deposit(address,uint256,uint256)", "bulkDeposit(address,uint256,uint256,address)", "bulkWithdraw(address,uint256,uint256,address)",
                 "manageVaultWithMerkleVerification(bytes32[][],address[],address[],bytes[],uint256[])", "setManageRoot(address,bytes32)",
                 "depositAndBridge(address,uint256,uint256,(uint32,address,address,uint64,bytes))", "bridge(uint256,(uint32,address,address,uint64,bytes))")
SEL_LABEL = {selector(s): s for s in SELECTOR_SIGS}


def replay(rpc, spec):
    frm = deploy_block(rpc, spec["address"])
    to = rpc.c["pin"][0]
    topics = AC_TOPICS if spec["kind"] == "access_control" else SOL_TOPICS
    try:
        if os.environ.get("PACTA_LOGS_VIA") == "explorer":
            raise RuntimeError("explorer requested")
        logs, url = rpc.logs(spec["address"], list(topics), frm, to)
    except RuntimeError:
        logs, url = rpc.logs_via_explorer(spec["address"], list(topics), frm, to)
    logs.sort(key=lambda l: (int(l["blockNumber"], 16), int(l["logIndex"], 16)))
    res = {"id": spec["id"], "label": spec["label"], "address": eip55(spec["address"]), "kind": spec["kind"], "from_block": frm,
           "to_block": to, "events": len(logs), "log_rpc": url}
    if spec["kind"] == "access_control":
        held = {}
        for l in logs:
            role, acct = l["topics"][1], eip55("0x" + l["topics"][2][-40:])
            held.setdefault(role, set())
            (held[role].add if topics[l["topics"][0]] == "granted" else held[role].discard)(acct)
        res["roles"] = [{"role": r, "name": ROLE_NAMES.get(r), "holders": sorted(h)} for r, h in sorted(held.items()) if h]
    else:
        owner, users, caps, pubs = None, {}, {}, {}
        for l in logs:
            k, t = topics[l["topics"][0]], l["topics"]
            on = int(l["data"], 16) == 1 if l["data"] not in ("0x", "") else None
            if k == "owner":
                owner = eip55("0x" + t[2][-40:])
            elif k == "user":
                users[(eip55("0x" + t[1][-40:]), int(t[2], 16))] = on
            elif k == "cap":
                caps[(int(t[1], 16), eip55("0x" + t[2][-40:]), t[3][:10])] = on
            elif k == "public":
                pubs[(eip55("0x" + t[1][-40:]), t[2][:10])] = on
        roles = sorted({r for (_, r) in users} | {r for (r, _, _) in caps})
        res["owner_from_events"] = owner
        res["roles"] = [{"role": r, "holders": sorted(u for (u, rr), on in users.items() if on and rr == r),
                         "capabilities": [{"target": tg, "selector": s, "signature": SEL_LABEL.get(s)}
                                          for (rr, tg, s), on in sorted(caps.items()) if on and rr == r]} for r in roles]
        res["roles"] = [x for x in res["roles"] if x["holders"] or x["capabilities"]]
        res["public_capabilities"] = [{"target": tg, "selector": s, "signature": SEL_LABEL.get(s)} for (tg, s), on in sorted(pubs.items()) if on]
    return res


def scan_target(t):
    rpc = Rpc(t["chain"])
    checks = [run_check(rpc, ch) for ch in t["checks"]]
    by = {c["id"]: c for c in checks}
    accounts = {}
    for cid, role in t.get("follow", []):
        accounts[role] = account_info(rpc, by[cid]["value"])
    for cid in t.get("follow_owner", []):
        a = by[cid]["value"]
        o = d_addr(rpc.both("eth_call", [{"to": a, "data": selector("owner()")}, rpc.pin]))
        accounts[f"{cid}_owner"] = {**account_info(rpc, o), "of": eip55(a), "call": "owner()"}
    for cid in t.get("follow_slot_owner", []):
        a = by[cid]["value"]
        o = d_addr(rpc.both("eth_call", [{"to": a, "data": selector("owner()")}, rpc.pin]))
        accounts["proxy_admin"] = {**account_info(rpc, a), "owner": o}
    logs = t.get("role_logs") or []
    logs = [replay(rpc, s) for s in (logs if isinstance(logs, list) else [logs])]
    num, h = rpc.c["pin"]
    blk = rpc.both("eth_getBlockByNumber", [hex(num), False])
    if blk["hash"] != h:
        raise RuntimeError(f"{t['chain']} pin mismatch: {blk['hash']} != {h}")
    return enrich_holders(rpc, {k: v for k, v in t.items() if k not in ("checks", "role_logs", "follow", "follow_owner", "follow_slot_owner")} | {
        "chain_id": rpc.c["chain_id"], "explorer": rpc.c["explorer"],
        "pin": {"number": num, "hash": h, "timestamp": int(blk["timestamp"], 16)}, "rpcs_cross_checked": sorted(rpc.used),
        "checks": checks, "accounts": accounts, "role_maps": logs})


def enrich_existing():
    """--enrich: classify role holders in the existing onboarding.json without re-running the log replays."""
    d = json.load(open(OUT))
    for b in d["briefs"]:
        enrich_holders(Rpc(b["chain"]), b)
    with open(OUT, "w") as fh:
        json.dump(d, fh, indent=1)
        fh.write("\n")
    print("enriched", [(b["slug"], len(b["holders"])) for b in d["briefs"]])


def main():
    if sys.argv[1:] == ["--enrich"]:
        return enrich_existing()
    only = set(sys.argv[1:])
    prev = {}
    if os.path.exists(OUT):
        prev = {b["slug"]: b for b in json.load(open(OUT)).get("briefs", [])}
    briefs = []
    for t in TARGETS:
        if only and t["slug"] not in only:
            if t["slug"] in prev:
                briefs.append(prev[t["slug"]])
            continue
        print(f"scanning {t['slug']} ...", flush=True)
        briefs.append(scan_target(t))
    out = {"schema": "pacta.onboarding_briefs.v1", "generated_by": "tools/onboarding_scan.py",
           "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "method": "eth_call / eth_getStorageAt / eth_getCode / eth_getTransactionCount pinned with EIP-1898 {blockHash, requireCanonical:true}, "
                     "byte-compared across two RPC endpoints per chain; role maps replayed from event logs (deployment block -> pinned block).",
           "briefs": briefs}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")
    print("wrote", os.path.relpath(OUT), [(b["slug"], len(b["checks"]), [m["events"] for m in b["role_maps"]]) for b in briefs])


if __name__ == "__main__":
    main()
