"""Refresh docs/api/v1/radar.json: live state of the queued timelock operations shown on the homepage radar.

Read-only JSON-RPC (stdlib only), pinned to the current *finalized* Ethereum block and cross-checked on two
independent RPC endpoints; any disagreement aborts. The homepage "Last refreshed" badge and countdown ETAs are built
from this file, so they always state the exact block they were observed at.

  python3 tools/refresh_radar.py
"""

import json
import os
import time
import urllib.request

RPCS = ["https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "api", "v1", "radar.json")
SEL = {"getTimestamp": "0xd45c4435", "isOperationPending": "0x584b153e", "isOperationDone": "0x2ab0f529", "getMinDelay": "0xf27a0c92"}
OPS = [
    {"protocol": "Ethena", "title": "Ethena USDe — RLUSD & USAT collateral onboarding",
     "summary": "Two queued EthenaMinting.addSupportedAsset calls onboard RLUSD and USAT at 200M / 20M USDe-per-block caps (stablesDeltaLimit = 0 bps).",
     "timelock": "0xE8Dc0Fab349EA169283C48Ccfd09d797E6DB7c94", "ops": ["0x1fe5e3e892708310bbfcf50efc03a1b8e21e0d0042035d7e8315e0cd5f26d85b",
                                                                       "0x0ca0fcc4856b87f3df9a74532bd60db58d1310c27c17e7d9bfa8a56846f57a90"],
     "brief": "briefs/ethena-ops-0x0ca0-0x1fe5/"},
    {"protocol": "Treehouse", "title": "Treehouse TREE — UUPS upgrade adding Blacklistable",
     "summary": "Upgrades the TREE governance token (not tETH) and installs a 5-of-7 Safe as blacklister: a zero-delay transfer-freeze role after execution.",
     "timelock": "0x2225DAbFfC7F862c99477381E971E8B1FDaB467e", "ops": ["0x2f11dcc36860f09b9ef94585589ced1798cef603d133efecd017ce7e544c451f"],
     "brief": "briefs/treehouse-op-0x2f11/"},
    {"protocol": "ether.fi", "title": "ether.fi — LayerZero V2 delegate moved behind the 10-day timelock",
     "summary": "EtherfiL1SyncPoolETH.setDelegate(EtherFiTimelock): protective hardening of the OApp's messaging configuration.",
     "timelock": "0x9f26d4C958fD811A1F59B01B86Be7dFFc9d20761", "ops": ["0x244e3f6c3df722246c471cee58804dd34c7703fce9cee1eadc1c5a85f171359f"],
     "brief": "briefs/etherfi-op-0x244e/"},
]


def rpc(url, method, params):
    req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "pacta-site-radar/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        resp = json.loads(r.read())
    if resp.get("id") != 1 or "error" in resp:
        raise RuntimeError(f"{method}: {resp.get('error')}")
    return resp["result"]


def both(method, params):
    a, b = (rpc(u, method, params) for u in RPCS)
    if a != b:
        raise RuntimeError(f"RPC disagreement on {method}: {a!r} vs {b!r}")
    return a


def main():
    if rpc(RPCS[0], "eth_chainId", []) != "0x1" or rpc(RPCS[1], "eth_chainId", []) != "0x1":
        raise RuntimeError("not Ethereum mainnet")
    fin = both("eth_getBlockByNumber", ["finalized", False])
    pin = {"blockHash": fin["hash"], "requireCanonical": True}
    items = []
    for o in OPS:
        delay = int(both("eth_call", [{"to": o["timelock"], "data": SEL["getMinDelay"]}, pin]), 16)
        ops = []
        for op in o["ops"]:
            ts = int(both("eth_call", [{"to": o["timelock"], "data": SEL["getTimestamp"] + op[2:]}, pin]), 16)
            pending = int(both("eth_call", [{"to": o["timelock"], "data": SEL["isOperationPending"] + op[2:]}, pin]), 16) == 1
            done = int(both("eth_call", [{"to": o["timelock"], "data": SEL["isOperationDone"] + op[2:]}, pin]), 16) == 1
            ops.append({"op_id": op, "eta": ts if ts > 1 else None, "pending": pending, "done": done})
        items.append({**{k: o[k] for k in ("protocol", "title", "summary", "timelock", "brief")}, "min_delay_seconds": delay, "operations": ops,
                      "eta": min((x["eta"] for x in ops if x["eta"]), default=None)})
    out = {"schema": "pacta.radar.v1", "chain_id": 1, "refreshed_at": {
        "block_number": int(fin["number"], 16), "block_hash": fin["hash"], "block_timestamp": int(fin["timestamp"], 16),
        "block_time_utc": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(int(fin["timestamp"], 16))), "tag": "finalized",
        "rpcs_cross_checked": len(RPCS)}, "items": items}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")
    print(json.dumps(out["refreshed_at"]), [(i["protocol"], i["eta"], [x["pending"] for x in i["operations"]]) for i in items])


if __name__ == "__main__":
    main()
