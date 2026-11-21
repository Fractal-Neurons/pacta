#!/usr/bin/env python3
"""Offline structural CI gate for Pacta Wave 4 bounty PRs (bounties/wave-4/**).

Runs inside GitHub Actions on fork PRs with zero network calls and zero secrets.
Full on-chain Base USDC settlement, finalized block/storage/getter replay, account-age,
and wallet-cluster checks run in the Codex-gated maintainer verifier before merge/payout.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from pacta_x402_call import to_eip55  # noqa: E402

HEX32_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
GH_HANDLE_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
FORBIDDEN_GRADE_KEYS = {"grade", "riskScore", "oneLineVerdict", "letter_grade"}


def _check_eip55(val: object, field: str, errs: list[str], allow_null: bool = False) -> None:
    if val is None and allow_null:
        return
    if not isinstance(val, str) or not ADDR_RE.match(val):
        errs.append(f"{field}: must be a 42-character 0x EVM address")
        return
    if to_eip55(val) != val:
        errs.append(f"{field}: must be EIP-55 checksummed ({to_eip55(val)})")


def validate_catalogue(path: Path, data: dict) -> list[str]:
    errs: list[str] = []
    for bad in FORBIDDEN_GRADE_KEYS:
        if bad in data or (isinstance(data.get("observed_control_plane"), dict) and bad in data["observed_control_plane"]):
            errs.append(f"{bad}: forbidden field — Pacta never sells or publishes grades in Catalogue entries")

    req_keys = {
        "slot_id",
        "chain",
        "protocol_name",
        "contract_address",
        "official_source_url",
        "pinned_block_number",
        "pinned_block_hash",
        "observed_control_plane",
        "payment_tx_hash",
        "contributor_github",
        "base_payout_address",
    }
    missing = sorted(req_keys - set(data.keys()))
    if missing:
        errs.append(f"missing required fields: {', '.join(missing)}")
        return errs

    slot_id = data.get("slot_id")
    if not isinstance(slot_id, str) or path.name != f"{slot_id}.json":
        errs.append(f"slot_id '{slot_id}' must match filename '{path.stem}'")

    # Load closed target batches
    known_targets: dict[str, dict] = {}
    for tf in sorted((ROOT / "bounties" / "wave-4").glob("catalogue-targets-*.json")):
        obj = json.loads(tf.read_text(encoding="utf-8"))
        for t in obj.get("targets", []):
            known_targets[t["slot_id"]] = t

    if slot_id not in known_targets:
        errs.append(f"slot_id '{slot_id}' is not in an open Wave 4 closed target batch")
    else:
        tgt = known_targets[slot_id]
        if data.get("chain") != tgt["chain"]:
            errs.append(f"chain must equal '{tgt['chain']}' for slot '{slot_id}'")
        if isinstance(data.get("contract_address"), str) and data["contract_address"].lower() != tgt["contract_address"].lower():
            errs.append(f"contract_address must equal closed-list address {tgt['contract_address']}")

    _check_eip55(data.get("contract_address"), "contract_address", errs)
    _check_eip55(data.get("base_payout_address"), "base_payout_address", errs)

    bn = data.get("pinned_block_number")
    if not isinstance(bn, int) or isinstance(bn, bool) or bn <= 0:
        errs.append("pinned_block_number: must be a positive integer")
    if not isinstance(data.get("pinned_block_hash"), str) or not HEX32_RE.match(data["pinned_block_hash"]):
        errs.append("pinned_block_hash: must be 0x + 64 hex chars")
    if not isinstance(data.get("payment_tx_hash"), str) or not HEX32_RE.match(data["payment_tx_hash"]):
        errs.append("payment_tx_hash: must be 0x + 64 hex chars")
    if not isinstance(data.get("contributor_github"), str) or not GH_HANDLE_RE.match(data["contributor_github"]):
        errs.append("contributor_github: invalid GitHub handle")

    ocp = data.get("observed_control_plane")
    if not isinstance(ocp, dict):
        errs.append("observed_control_plane: must be an object")
    else:
        if not isinstance(ocp.get("is_proxy"), bool):
            errs.append("observed_control_plane.is_proxy: must be boolean")
        _check_eip55(ocp.get("implementation_address"), "observed_control_plane.implementation_address", errs, allow_null=True)
        if ocp.get("controller_kind") not in {"timelock", "safe", "eoa", "contract", "immutable_or_renounced"}:
            errs.append("observed_control_plane.controller_kind: invalid kind")
        _check_eip55(ocp.get("controller_address"), "observed_control_plane.controller_address", errs, allow_null=True)

    return errs


def validate_watch(path: Path, data: dict) -> list[str]:
    errs: list[str] = []
    for bad in FORBIDDEN_GRADE_KEYS:
        if bad in data:
            errs.append(f"{bad}: forbidden field — Pacta never sells or publishes grades in Watch entries")

    req_keys = {
        "protocol_slug",
        "chain",
        "watched_address",
        "prior_pinned_block",
        "event_block_number",
        "event_block_hash",
        "event_tx_hash",
        "change_kind",
        "before_state",
        "after_state",
        "payment_tx_hash",
        "contributor_github",
        "base_payout_address",
    }
    missing = sorted(req_keys - set(data.keys()))
    if missing:
        errs.append(f"missing required fields: {', '.join(missing)}")
        return errs

    protocol_slug = data.get("protocol_slug")
    event_tx_hash = data.get("event_tx_hash")
    if not isinstance(protocol_slug, str) or not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", protocol_slug):
        errs.append("protocol_slug: must be lowercase kebab-case")

    if isinstance(event_tx_hash, str) and HEX32_RE.match(event_tx_hash) and isinstance(protocol_slug, str):
        tx8 = event_tx_hash[2:10].lower()
        expected_filename = f"{protocol_slug}-0x{tx8}.json"
        if path.name != expected_filename:
            errs.append(f"filename '{path.name}' must equal '{expected_filename}'")
    elif path.suffix != ".json":
        errs.append(f"file must have .json extension, got '{path.name}'")

    manifest_file = ROOT / "bounties" / "wave-4" / "watched-addresses.json"
    if not manifest_file.exists():
        errs.append("watched-addresses.json manifest not found")
        return errs
    try:
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except Exception as e:
        errs.append(f"failed to parse watched-addresses.json: {e}")
        return errs

    watched_addresses = manifest_data.get("addresses", [])
    slug = data.get("protocol_slug")
    chain = data.get("chain")
    watched_addr = data.get("watched_address")
    prior_block = data.get("prior_pinned_block")

    matching_slug = [a for a in watched_addresses if a.get("protocol_slug") == slug]
    if not matching_slug:
        errs.append(f"protocol_slug '{slug}' is not in watched-addresses.json")
    else:
        matching_target = None
        for a in matching_slug:
            if (
                a.get("chain") == chain
                and isinstance(watched_addr, str)
                and a.get("address", "").lower() == watched_addr.lower()
            ):
                matching_target = a
                break
        if matching_target is None:
            errs.append(
                f"watched_address '{watched_addr}' on chain '{chain}' is not a registered watched address for '{slug}'"
            )
        else:
            if prior_block != matching_target.get("pinned_block_number"):
                errs.append(
                    f"prior_pinned_block must equal {matching_target.get('pinned_block_number')} for {slug} ({watched_addr})"
                )

    _check_eip55(data.get("watched_address"), "watched_address", errs)
    _check_eip55(data.get("base_payout_address"), "base_payout_address", errs)

    if not isinstance(prior_block, int) or isinstance(prior_block, bool) or prior_block <= 0:
        errs.append("prior_pinned_block: must be a positive integer")

    event_block = data.get("event_block_number")
    if not isinstance(event_block, int) or isinstance(event_block, bool) or event_block <= 0:
        errs.append("event_block_number: must be a positive integer")
    elif isinstance(prior_block, int) and not isinstance(prior_block, bool) and event_block <= prior_block:
        errs.append(
            f"event_block_number ({event_block}) must be strictly greater than prior_pinned_block ({prior_block})"
        )

    if not isinstance(data.get("event_block_hash"), str) or not HEX32_RE.match(data["event_block_hash"]):
        errs.append("event_block_hash: must be 0x + 64 hex chars")
    if not isinstance(data.get("event_tx_hash"), str) or not HEX32_RE.match(data["event_tx_hash"]):
        errs.append("event_tx_hash: must be 0x + 64 hex chars")

    allowed_change_kinds = {
        "implementation_upgrade",
        "admin_or_role_change",
        "safe_signer_or_threshold_change",
        "timelock_delay_or_queued_op",
    }
    if data.get("change_kind") not in allowed_change_kinds:
        errs.append(f"change_kind: must be one of {sorted(allowed_change_kinds)}")

    if not isinstance(data.get("before_state"), str) or not data["before_state"].strip():
        errs.append("before_state: must be a non-empty string")
    if not isinstance(data.get("after_state"), str) or not data["after_state"].strip():
        errs.append("after_state: must be a non-empty string")

    if data.get("chain") not in {"ethereum", "base"}:
        errs.append("chain: must be 'ethereum' or 'base'")
    if not isinstance(data.get("payment_tx_hash"), str) or not HEX32_RE.match(data["payment_tx_hash"]):
        errs.append("payment_tx_hash: must be 0x + 64 hex chars")
    if not isinstance(data.get("contributor_github"), str) or not GH_HANDLE_RE.match(data["contributor_github"]):
        errs.append("contributor_github: invalid GitHub handle")

    return errs


def validate_generic_wave4(data: dict) -> list[str]:
    errs: list[str] = []
    if not isinstance(data.get("payment_tx_hash"), str) or not HEX32_RE.match(data["payment_tx_hash"]):
        errs.append("payment_tx_hash: must be 0x + 64 hex chars")
    _check_eip55(data.get("base_payout_address"), "base_payout_address", errs)
    if not isinstance(data.get("contributor_github"), str) or not GH_HANDLE_RE.match(data["contributor_github"]):
        errs.append("contributor_github: invalid GitHub handle")
    return errs


def run_self_test() -> None:
    sample = {
        "slot_id": "ethereum-arbitrum-delayed-bridge",
        "chain": "ethereum",
        "protocol_name": "Arbitrum One Canonical Bridge (Delayed Bridge)",
        "contract_address": "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a",
        "official_source_url": "https://docs.arbitrum.io/build-decentralized-apps/reference/contract-addresses",
        "pinned_block_number": 23849500,
        "pinned_block_hash": "0x" + "11" * 32,
        "observed_control_plane": {
            "is_proxy": True,
            "implementation_address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
            "controller_kind": "timelock",
            "controller_address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
            "safe_threshold": None,
            "safe_owners_count": None,
            "timelock_min_delay_seconds": 259200,
        },
        "payment_tx_hash": "0x" + "44" * 32,
        "contributor_github": "alice-researcher",
        "base_payout_address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
    }
    assert validate_catalogue(Path("bounties/wave-4/catalogue/ethereum-arbitrum-delayed-bridge.json"), sample) == []
    bad = dict(sample, grade="A")
    assert validate_catalogue(Path("bounties/wave-4/catalogue/ethereum-arbitrum-delayed-bridge.json"), bad) != []

    watch_sample = {
        "protocol_slug": "morpho-blue-core",
        "chain": "ethereum",
        "watched_address": "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb",
        "prior_pinned_block": 26401070,
        "event_block_number": 26465000,
        "event_block_hash": "0x" + "11" * 32,
        "event_tx_hash": "0x1a2b3c4d" + "55" * 28,
        "change_kind": "admin_or_role_change",
        "before_state": "owner() = 0xcBa28b38103307Ec8dA98377ffF9816C164f9AFa",
        "after_state": "owner() = 0x2222222222222222222222222222222222222222",
        "payment_tx_hash": "0x" + "44" * 32,
        "contributor_github": "alice-researcher",
        "base_payout_address": "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf",
    }
    watch_path = Path("bounties/wave-4/watch/morpho-blue-core-0x1a2b3c4d.json")
    assert validate_watch(watch_path, watch_sample) == []

    bad_grade = dict(watch_sample, grade="A")
    assert validate_watch(watch_path, bad_grade) != []

    bad_block = dict(watch_sample, event_block_number=26401070)
    assert validate_watch(watch_path, bad_block) != []

    bad_kind = dict(watch_sample, change_kind="invalid_kind")
    assert validate_watch(watch_path, bad_kind) != []

    bad_filename = Path("bounties/wave-4/watch/wrong-filename.json")
    assert validate_watch(bad_filename, watch_sample) != []

    bad_prior = dict(watch_sample, prior_pinned_block=12345)
    assert validate_watch(watch_path, bad_prior) != []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="Wave 4 JSON file path")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        run_self_test()
        print("verify_wave4_structural self-test: PASS")
        return
    if not args.json:
        raise SystemExit("Provide --json <file> or --self-test")
    p = Path(args.json)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"invalid JSON: {e}")
        sys.exit(1)
    if not isinstance(data, dict):
        print("top-level JSON value must be an object")
        sys.exit(1)
    norm = str(p).replace(os.sep, "/")
    if "/wave-4/catalogue/" in norm or norm.startswith("bounties/wave-4/catalogue/"):
        errs = validate_catalogue(p, data)
    elif "/wave-4/watch/" in norm or norm.startswith("bounties/wave-4/watch/"):
        errs = validate_watch(p, data)
    else:
        errs = validate_generic_wave4(data)
    if errs:
        for e in errs:
            print(e)
        sys.exit(1)
    print(f"OK: {norm}")


if __name__ == "__main__":
    main()
