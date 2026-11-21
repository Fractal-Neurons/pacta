#!/usr/bin/env python3
"""
pacta_x402_call.py — Local-only x402 EIP-3009 helper for Pacta Wave 4 bounties.

Security guarantees (standard-library Python 3, zero pip installs):
1. Runs a built-in cryptographic self-test (Keccak-256, secp256k1 address, EIP-712 signature) before any action.
2. Checks GitHub BEFORE signing (merged file + first 100 open PR titles/branches) so you do not pay on a taken slot.
3. Reads your fresh cents-only private key strictly from a local file (--key-file); never accepts a key
   on the command line, never prints or logs the key, and never sends the key over any network socket.
4. Signs only one fixed EIP-3009 TransferWithAuthorization ($0.02 verdict or $0.05 dossier) on Base USDC
   (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913) to Pacta's treasury wallet
   0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14, and sends the signed X-PAYMENT header to
   https://api.pacta.wtf/v1/x402/<route> (second official host: https://pacta.fractalneurons.com).
5. Signs exactly once per run. If the Worker answers HTTP 503 with "settled": true (the payment went through on Base but
   the Worker could not confirm it yet), the script replays the byte-identical request and X-PAYMENT header (same nonce,
   same signature) up to 4 times. The same authorization can never be charged twice.
6. Loads a key only from a regular, non-symlinked file readable by its owner alone (mode 0600), sends the signed request
   only to one of the two official hosts, never follows an HTTP redirect, and never forwards X-PAYMENT to another origin.
"""
from __future__ import annotations

import argparse
import re
import base64
import hashlib
import hmac
import json
import os
import secrets
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_HOST = "https://api.pacta.wtf"
# exactly the two official Pacta x402 hostnames (https only, default port, no path)
ALLOWED_HOSTS = frozenset({"api.pacta.wtf", "pacta.fractalneurons.com"})
PAY_TO = "0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BASE_CHAIN_ID = 8453
GITHUB_REPO = "Fractal-Neurons/pacta"

ROUTES = {
    "verdict": {"path": "/v1/x402/verdict", "price": "20000", "usd": "0.02"},
    "dossier": {"path": "/v1/x402/dossier", "price": "50000", "usd": "0.05"},
}

# Known test vectors verified against Foundry `cast`
_SELFTEST_KECCAK_EMPTY = "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
_SELFTEST_PK1_ADDR = "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
_SELFTEST_PK1_SIG = (
    "0xb282e580d9e940ed68d012564ae5c8e683fc4482e5fa6d4d1f3ceca7baf61ff5"
    "2792bd8e3fb3cd55eb76583ee0c26b5d169fa9743d310baac25a66211f1183451c"
)

# --- Pure-Python Keccak-256 (Ethereum pre-NIST padding 0x01) ---
_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROT = [
    [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
]
_M64 = (1 << 64) - 1


def _rol64(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & _M64 if n else x


def keccak256(data: bytes) -> bytes:
    rate = 136
    buf = bytearray(data)
    buf.append(0x01)
    while len(buf) % rate != 0:
        buf.append(0x00)
    buf[-1] |= 0x80
    st = [[0] * 5 for _ in range(5)]
    for off in range(0, len(buf), rate):
        for i in range(rate // 8):
            st[i % 5][i // 5] ^= int.from_bytes(buf[off + 8 * i : off + 8 * i + 8], "little")
        for rc in _RC:
            c = [st[x][0] ^ st[x][1] ^ st[x][2] ^ st[x][3] ^ st[x][4] for x in range(5)]
            d = [c[(x - 1) % 5] ^ _rol64(c[(x + 1) % 5], 1) for x in range(5)]
            for x in range(5):
                for y in range(5):
                    st[x][y] ^= d[x]
            b = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    b[y][(2 * x + 3 * y) % 5] = _rol64(st[x][y], _ROT[x][y])
            for x in range(5):
                for y in range(5):
                    st[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y] & _M64)
            st[0][0] ^= rc
    out = bytearray()
    for y in range(5):
        for x in range(5):
            out.extend(st[x][y].to_bytes(8, "little"))
            if len(out) >= 32:
                return bytes(out[:32])
    return bytes(out[:32])


# --- Pure-Python secp256k1 + RFC-6979 ECDSA (recoverable v=27/28, EIP-2 low-S, non-zero r/s guard) ---
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8


def _pt_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        if (y1 + y2) % _P == 0:
            return None
        lam = (3 * x1 * x1 * pow(2 * y1, _P - 2, _P)) % _P
    else:
        lam = ((y2 - y1) * pow(x2 - x1, _P - 2, _P)) % _P
    x3 = (lam * lam - x1 - x2) % _P
    y3 = (lam * (x1 - x3) - y1) % _P
    return (x3, y3)


def _pt_mul(k: int, pt=(_GX, _GY)):
    res = None
    addend = pt
    while k > 0:
        if k & 1:
            res = _pt_add(res, addend)
        addend = _pt_add(addend, addend)
        k >>= 1
    return res


def to_eip55(addr_hex: str) -> str:
    raw = addr_hex.lower().removeprefix("0x")
    if len(raw) != 40 or any(c not in "0123456789abcdef" for c in raw):
        raise ValueError(f"Invalid 20-byte EVM address: {addr_hex}")
    digest = keccak256(raw.encode("ascii")).hex()
    return "0x" + "".join(c.upper() if int(digest[i], 16) >= 8 else c for i, c in enumerate(raw))


def privkey_to_address(priv_int: int) -> str:
    if not (1 <= priv_int < _N):
        raise ValueError("Private key out of secp256k1 range")
    pt = _pt_mul(priv_int)
    if pt is None:
        raise RuntimeError("Invalid curve point")
    pub_uncompressed = pt[0].to_bytes(32, "big") + pt[1].to_bytes(32, "big")
    return to_eip55("0x" + keccak256(pub_uncompressed)[-20:].hex())


def _rfc6979_k(priv_int: int, msg32: bytes) -> int:
    x = priv_int.to_bytes(32, "big")
    h1 = (int.from_bytes(msg32, "big") % _N).to_bytes(32, "big")
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + x + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + x + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        v = hmac.new(k, v, hashlib.sha256).digest()
        cand = int.from_bytes(v, "big")
        if 1 <= cand < _N:
            return cand
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def sign_digest_recoverable(priv_int: int, digest32: bytes) -> str:
    z = int.from_bytes(digest32, "big")
    k = _rfc6979_k(priv_int, digest32)
    pt = _pt_mul(k)
    if pt is None:
        raise RuntimeError("ECDSA k*G produced point at infinity")
    rx, ry = pt
    r = rx % _N
    rec_id = (ry & 1) | (2 if rx >= _N else 0)
    s = (pow(k, _N - 2, _N) * (z + r * priv_int)) % _N
    if r == 0 or s == 0:
        raise RuntimeError("Refusing to output invalid ECDSA signature with r == 0 or s == 0")
    if s > _N // 2:
        s = _N - s
        rec_id ^= 1
    v = 27 + rec_id
    return "0x" + r.to_bytes(32, "big").hex() + s.to_bytes(32, "big").hex() + bytes([v]).hex()


def sign_eip3009_usdc_base(
    priv_int: int,
    from_addr: str,
    to_addr: str,
    value_str: str,
    valid_after: int,
    valid_before: int,
    nonce_hex: str,
) -> str:
    domain_typehash = keccak256(
        b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    )
    domain_sep = keccak256(
        domain_typehash
        + keccak256(b"USD Coin")
        + keccak256(b"2")
        + BASE_CHAIN_ID.to_bytes(32, "big")
        + bytes.fromhex(USDC_BASE[2:].lower()).rjust(32, b"\x00")
    )
    transfer_typehash = keccak256(
        b"TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)"
    )
    struct_hash = keccak256(
        transfer_typehash
        + bytes.fromhex(from_addr[2:].lower()).rjust(32, b"\x00")
        + bytes.fromhex(to_addr[2:].lower()).rjust(32, b"\x00")
        + int(value_str).to_bytes(32, "big")
        + int(valid_after).to_bytes(32, "big")
        + int(valid_before).to_bytes(32, "big")
        + bytes.fromhex(nonce_hex[2:].lower())
    )
    digest = keccak256(b"\x19\x01" + domain_sep + struct_hash)
    return sign_digest_recoverable(priv_int, digest)


def run_self_test() -> dict[str, object]:
    got_keccak = "0x" + keccak256(b"").hex()
    if got_keccak != _SELFTEST_KECCAK_EMPTY:
        raise SystemExit(f"SELF-TEST FAILED: keccak256('') = {got_keccak}, expected {_SELFTEST_KECCAK_EMPTY}")
    got_addr = privkey_to_address(1)
    if got_addr != _SELFTEST_PK1_ADDR:
        raise SystemExit(f"SELF-TEST FAILED: address(1) = {got_addr}, expected {_SELFTEST_PK1_ADDR}")
    got_sig = sign_eip3009_usdc_base(
        1, _SELFTEST_PK1_ADDR, PAY_TO, "20000", 1700000000, 1700000300, "0x" + "aa" * 32
    )
    if got_sig != _SELFTEST_PK1_SIG:
        raise SystemExit("SELF-TEST FAILED: EIP-712 TransferWithAuthorization signature mismatch")
    return {
        "self_test": "PASS",
        "keccak256_empty": got_keccak,
        "privkey_1_address": got_addr,
        "eip3009_signature_prefix": got_sig[:20] + "..." + got_sig[-6:],
    }


def load_local_key_file(path: str) -> int:
    if os.name == "posix":
        # verify the file actually opened (not a path-only check): no symlink, a regular file, owner-only permissions
        try:
            # O_NONBLOCK: a FIFO / device with no writer must never block the open before fstat can reject it
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        except OSError as e:
            raise SystemExit(f"ERROR: cannot open --key-file {path} as a regular, non-symlinked file ({e.strerror}).")
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            os.close(fd)
            raise SystemExit(f"ERROR: --key-file {path} must be a regular file.")
        if st.st_mode & 0o077:
            os.close(fd)
            raise SystemExit(
                f"ERROR: --key-file {path} is readable or writable by other users (mode {stat.S_IMODE(st.st_mode):04o}). "
                f"Run: chmod 600 {path}"
            )
        import fcntl  # POSIX-only stdlib module: clear O_NONBLOCK now that the file is a verified regular 0600 file
        fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) & ~os.O_NONBLOCK)
        with os.fdopen(fd, "r", encoding="utf-8") as fh:
            raw = fh.read().strip().removeprefix("0x")
    else:
        raw = open(path, "r", encoding="utf-8").read().strip().removeprefix("0x")
    if len(raw) != 64 or any(c not in "0123456789abcdefABCDEF" for c in raw):
        raise SystemExit("ERROR: --key-file must contain a 64-hex-character secp256k1 private key.")
    val = int(raw, 16)
    if not (1 <= val < _N):
        raise SystemExit("ERROR: private key integer out of secp256k1 range.")
    return val


def generate_fresh_wallet(path: str) -> str:
    if os.path.exists(path):
        raise SystemExit(f"ERROR: refusing to overwrite existing key file: {path}")
    priv_int = secrets.randbelow(_N - 1) + 1
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("0x" + priv_int.to_bytes(32, "big").hex() + "\n")
    return privkey_to_address(priv_int)


SETTLED_REPLAY_WAITS = (2.5, 4.0, 6.0, 10.0)   # up to 4 replays of the identical signed request (5 attempts in total)
SETTLED_ERRORS = ("settlement_unconfirmed", "settled_not_recorded")
SETTLED_EXHAUSTED_MSG = (
    "If the script ends with HTTP 503 and the answer says settled: true, your payment went through. "
    "Do not run it again. Use that transaction."
)


def _json_object(text: str) -> dict:
    try:
        obj = json.loads(text)
    except ValueError:
        return {}
    return obj if isinstance(obj, dict) else {}


_TX_RE = re.compile(r"\A0x[0-9a-fA-F]{64}\Z")   # whole string only: "$" would also accept a trailing newline


def _settled_tx(err_json: dict) -> str | None:
    tx = err_json.get("transaction")
    return tx if isinstance(tx, str) and _TX_RE.fullmatch(tx) else None


def _is_settled_503(code: int, err_json: dict) -> bool:
    """A 503 whose answer proves the payment already settled on Base: "settled" is exactly true, or "settled" is absent and
    a settled error name comes with a 0x + 64-hex transaction. "settled": false / null / "true" / 1 never replays."""
    if code != 503:
        return False
    if err_json.get("settled") is True:
        return True
    return "settled" not in err_json and err_json.get("error") in SETTLED_ERRORS and _settled_tx(err_json) is not None


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect for a signed payment request: a 301/302/303/307/308 surfaces as an HTTPError."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# dedicated opener for the signed request: no redirects (and no global urllib opener state)
_payment_opener = urllib.request.build_opener(_NoRedirectHandler())


def _pin_payment_header(http_req) -> None:
    """Keep X-PAYMENT out of any redirected request, whatever opener is used (stdlib never copies unredirected headers)."""
    pay = http_req.headers.pop("X-payment", None)
    if pay is not None:
        http_req.add_unredirected_header("X-PAYMENT", pay)


def send_signed_request(http_req, endpoint: str, basescan_hint: str, opener=None, sleep=None):
    """Send the already-signed request. A settled 503 is replayed with the SAME Request object (byte-identical body and
    X-PAYMENT header: no new nonce, no new signature) after 2.5 / 4 / 6 / 10 s. Every other HTTP error stops at once.
    Returns (raw_body, payment_response_header, status_code, settled_tx_from_a_503_or_None)."""
    opener = opener or _payment_opener.open
    sleep = sleep or time.sleep
    _pin_payment_header(http_req)
    settled_tx = None
    for attempt in range(len(SETTLED_REPLAY_WAITS) + 1):
        try:
            with opener(http_req, timeout=45) as resp:
                raw_body = resp.read().decode("utf-8")
                pay_hdr = resp.headers.get("X-PAYMENT-RESPONSE") or resp.headers.get("PAYMENT-RESPONSE") or ""
                return raw_body, pay_hdr, resp.status, settled_tx
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            err_json = _json_object(err_body)
            if not _is_settled_503(e.code, err_json):
                raise SystemExit(f"HTTP {e.code} from {endpoint}: {err_body}\n{basescan_hint}")
            settled_tx = _settled_tx(err_json) or settled_tx
            if attempt == len(SETTLED_REPLAY_WAITS):
                tx_line = f"Settled Base transaction: {settled_tx}\n" if settled_tx else ""
                raise SystemExit(
                    f"HTTP 503 from {endpoint} after {attempt + 1} attempts with the same signed payment: {err_body}\n"
                    f"{tx_line}{SETTLED_EXHAUSTED_MSG}"
                )
            wait = SETTLED_REPLAY_WAITS[attempt]
            print(
                f"[retry {attempt + 1}/{len(SETTLED_REPLAY_WAITS)}] payment settled on Base (tx {settled_tx or 'unknown'}); "
                f"waiting {wait}s for Worker receipt confirmation — no second charge...",
                file=sys.stderr,
            )
            sleep(wait)
        except Exception as e:
            raise SystemExit(f"Network/timeout error calling {endpoint}: {e}\n{basescan_hint}")
    raise SystemExit(f"unreachable retry state calling {endpoint}\n{basescan_hint}")


def check_slot_free_on_github(slot_id: str) -> None:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "pacta-x402-helper/1.0"}
    target_rel = f"bounties/wave-4/catalogue/{slot_id}.json"
    file_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{urllib.parse.quote(target_rel)}"
    req = urllib.request.Request(file_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                raise SystemExit(
                    f"SLOT TAKEN: {target_rel} is already merged on {GITHUB_REPO}. Stopped BEFORE signing ($0.00 spent)."
                )
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise SystemExit(f"ERROR checking GitHub file status (HTTP {e.code}); stopped before signing.")

    prs_url = f"https://api.github.com/repos/{GITHUB_REPO}/pulls?state=open&per_page=100"
    req_prs = urllib.request.Request(prs_url, headers=headers)
    try:
        with urllib.request.urlopen(req_prs, timeout=10) as resp:
            prs = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise SystemExit(f"ERROR checking open GitHub PRs ({e}); stopped before signing.")

    needle = slot_id.lower()
    matching = [
        f"PR #{pr['number']} ({pr['html_url']})"
        for pr in prs
        if needle in (pr.get("title") or "").lower() or needle in ((pr.get("head") or {}).get("ref") or "").lower()
    ]
    if matching:
        raise SystemExit(
            f"SLOT HAS OPEN PR(S) in first 100 open PRs: {', '.join(matching)}. Stopped BEFORE signing ($0.00 spent)."
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Local EIP-3009 x402 caller for Pacta Wave 4 bounties.")
    ap.add_argument("--self-test", action="store_true", help="Run built-in cryptographic self-test and exit.")
    ap.add_argument("--generate-wallet", metavar="KEY_FILE", help="Create a fresh 0600 wallet file and print ONLY its public Base address.")
    ap.add_argument("--print-address", metavar="KEY_FILE", help="Print ONLY the public EIP-55 address for an existing local key file.")
    ap.add_argument("--key-file", help="Path to local 0600 file holding your fresh cents-only private key.")
    ap.add_argument("--route", choices=["verdict", "dossier"], default="verdict")
    ap.add_argument("--host", default=DEFAULT_HOST, help=f"Official Pacta x402 host (default: {DEFAULT_HOST})")
    ap.add_argument("--slot", help="Catalogue slot_id to check on GitHub BEFORE signing.")
    ap.add_argument("--skip-slot-check", action="store_true", help="Skip GitHub slot availability pre-check.")
    ap.add_argument("--chain", choices=["ethereum", "base"], help="Target contract chain.")
    ap.add_argument("--address", help="Target 0x contract address.")
    ap.add_argument("--slug", help="Published Pacta protocol slug (for Watch / Documents Changed).")
    ap.add_argument("--dry-run", action="store_true", help="Check slot & print exact payment parameters without signing or calling.")
    ap.add_argument("--out", help="Write sanitized response + settlement receipt JSON to this file.")
    args = ap.parse_args()

    # Always run cryptographic self-test silently before any action; stop immediately on mismatch.
    st = run_self_test()
    if args.self_test:
        print(json.dumps(st, indent=2))
        return

    if args.generate_wallet:
        addr = generate_fresh_wallet(args.generate_wallet)
        print(json.dumps({"key_file": args.generate_wallet, "mode": "0600", "base_payout_address": addr}, indent=2))
        return

    if args.print_address:
        priv = load_local_key_file(args.print_address)
        print(privkey_to_address(priv))
        return

    try:
        hu = urllib.parse.urlsplit(args.host.strip())
        host_ok = (hu.scheme == "https" and (hu.hostname or "") in ALLOWED_HOSTS and hu.username is None and hu.password is None
                   and hu.port in (None, 443) and hu.path in ("", "/") and not hu.query and not hu.fragment)
    except ValueError:
        host_ok = False
    if not host_ok:
        raise SystemExit(f"ERROR: --host must be https://<one of {sorted(ALLOWED_HOSTS)}> (no port, path or credentials).")
    host = "https://" + hu.hostname

    if not args.key_file:
        raise SystemExit("ERROR: --key-file is required (or run --generate-wallet ./fresh-key.txt first).")

    if not args.slug and not (args.chain and args.address):
        raise SystemExit("ERROR: provide either (--chain and --address) or --slug.")

    if args.slot and not args.skip_slot_check:
        check_slot_free_on_github(args.slot)
        print(
            f"[precheck] No merged file and no match in the first 100 open PR titles/branches for '{args.slot}' on {GITHUB_REPO}.",
            file=sys.stderr,
        )

    priv_int = load_local_key_file(args.key_file)
    payer = privkey_to_address(priv_int)
    route_cfg = ROUTES[args.route]
    endpoint = host + route_cfg["path"]

    req_body: dict[str, str] = {}
    if args.slug:
        req_body["slug"] = args.slug
    if args.chain:
        req_body["chain"] = args.chain
    if args.address:
        req_body["address"] = to_eip55(args.address)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "self_test": "PASS",
                    "endpoint": endpoint,
                    "payer_and_payout_address": payer,
                    "pay_to": PAY_TO,
                    "usdc_base": USDC_BASE,
                    "amount_atomic": route_cfg["price"],
                    "amount_usd": route_cfg["usd"],
                    "request_body": req_body,
                },
                indent=2,
            )
        )
        return

    now = int(time.time())
    valid_after = now - 60
    valid_before = now + 300
    nonce_hex = "0x" + secrets.token_bytes(32).hex()
    sig_hex = sign_eip3009_usdc_base(priv_int, payer, PAY_TO, route_cfg["price"], valid_after, valid_before, nonce_hex)

    x_payment_obj = {
        "x402Version": 1,
        "scheme": "exact",
        "network": "base",
        "payload": {
            "signature": sig_hex,
            "authorization": {
                "from": payer,
                "to": PAY_TO,
                "value": route_cfg["price"],
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": nonce_hex,
            },
        },
    }
    x_payment_b64 = base64.b64encode(json.dumps(x_payment_obj, separators=(",", ":")).encode("utf-8")).decode("ascii")

    http_req = urllib.request.Request(
        endpoint,
        data=json.dumps(req_body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-PAYMENT": x_payment_b64,
            "User-Agent": "pacta-x402-helper/1.0",
        },
        method="POST",
    )
    basescan_hint = (
        f"IMPORTANT: Before retrying, check https://basescan.org/address/{payer}#tokentxns — "
        f"if ${route_cfg['usd']} USDC already transferred to {PAY_TO}, DO NOT PAY AGAIN; "
        f"that Base transaction hash is valid for your entry and our checker accepts it."
    )
    # The request (body + X-PAYMENT header) was signed exactly once above; a settled 503 replays this same object.
    raw_body, pay_hdr, status_code, settled_tx = send_signed_request(http_req, endpoint, basescan_hint)

    settlement = {}
    if pay_hdr:
        try:
            pad = pay_hdr + "=" * (-len(pay_hdr) % 4)
            settlement = json.loads(base64.b64decode(pad).decode("utf-8"))
        except Exception:
            settlement = {"raw_header": pay_hdr}
    if not settlement.get("transaction") and settled_tx:
        # the 200 came on a replay and carried no payment-response header: keep the transaction the settled 503 named
        settlement = {**settlement, "transaction": settled_tx, "source": "settled_503_before_replay"}

    parsed_resp = json.loads(raw_body)
    observed_only = {k: v for k, v in parsed_resp.items() if k not in ("grade", "riskScore", "oneLineVerdict")}

    result = {
        "http_status": status_code,
        "endpoint": endpoint,
        "payer_and_payout_address": payer,
        "pay_to": PAY_TO,
        "amount_usd": route_cfg["usd"],
        "payment_tx_hash": settlement.get("transaction"),
        "settlement_receipt": settlement,
        "observed_response": observed_only,
    }
    rendered = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
