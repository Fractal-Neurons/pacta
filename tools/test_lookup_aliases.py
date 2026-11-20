"""Offline test of the Sprint 36 lookup aliases (tools/build_lookup.py; 0 network calls): the catalog built from the published data, as
tools/build_site.py builds it, resolves each verified alias address to its protocol by an exact (chain, address) match over the same
fields the Worker's catalogAddressIndex() indexes (primaryContract, controllerAddress, surfaces[].targetContract, relatedContracts,
aliasAddresses), and protocols.json carries relatedContracts / aliasAddresses and every surface its chain.

    python3 -m pytest tools/test_lookup_aliases.py   (or: python3 tools/test_lookup_aliases.py)
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("TMPDIR", os.environ.get("TMPDIR", "/tmp"))

import build_site as BS  # noqa: E402
import build_lookup as LK  # noqa: E402


def _catalog():
    idx, radar = BS.load()
    sp = BS.site_protocols(idx, BS.load_pinned())
    items = LK.build_items(sp, BS.load_onboarding(), radar, BS.BRIEF_PROTOCOL)
    return sp, items


SP, ITEMS = _catalog()
PROTOCOLS = [x for x in ITEMS if x["kind"] == "protocol"]


def resolve(chain, address):
    """Slugs whose record names (chain, address), in the Worker's role order (primary, controller, surface, related)."""
    a, out = address.lower(), []
    for x in PROTOCOLS:
        if x["chain"] != chain:
            continue
        roles = ([x["primaryContract"]], [x["controllerAddress"]], [u["targetContract"] for u in x["surfaces"]],
                 x.get("relatedContracts", []) + x.get("aliasAddresses", []))
        for rank, addrs in enumerate(roles):
            if any(isinstance(v, str) and v.lower() == a for v in addrs):
                out.append((rank, x["slug"]))
                break
    return [s for _, s in sorted(out)]


class Aliases(unittest.TestCase):
    def test_every_alias_is_eip55_and_resolves_to_its_protocol_on_its_chain(self):
        by = {x["slug"]: x for x in PROTOCOLS}
        for slug, addrs in LK.ADDRESS_ALIASES.items():
            self.assertIn(slug, by)
            self.assertEqual(by[slug]["aliasAddresses"], addrs)
            for a in addrs:
                self.assertEqual(LK.eip55(a.lower()), a)
                self.assertIn(slug, resolve(by[slug]["chain"], a), (slug, a))

    def test_the_flagship_addresses_resolve(self):
        cases = {("ethereum", "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"): "aave-v3-gho",
                 ("ethereum", "0xA35b1B31Ce002FBF2058D22F30f95D405200A15b"): "stader-labs-ethx",
                 ("ethereum", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"): "circle-gateway",
                 ("base", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"): "circle-usdc",
                 ("ethereum", "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"): "lido-steth-dual-governance",
                 ("ethereum", "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"): "lido-steth-dual-governance",
                 ("ethereum", "0x4c9EDD5852cd905f086C759E8383e09bff1E68B3"): "ethena-usde-susde",
                 ("ethereum", "0x9D39A5DE30e57443BfF2A8307A4256c8797A3497"): "ethena-usde-susde"}
        for (chain, a), slug in cases.items():
            self.assertIn(slug, resolve(chain, a), (chain, a))

    def test_stader_invariants_hold(self):
        st = next(x for x in PROTOCOLS if x["slug"] == "stader-labs-ethx")
        self.assertIn("0xA35b1B31Ce002FBF2058D22F30f95D405200A15b", st["relatedContracts"])
        self.assertEqual(st["pinnedBlock"], 26403676)

    def test_protocols_json_carries_related_contracts_aliases_and_surface_chains(self):
        doc = json.loads(LK.protocols_json(SP, ITEMS))
        rows = {r["slug"]: r for r in doc["protocols"]}
        self.assertTrue(all("relatedContracts" in r for r in rows.values()))
        self.assertEqual(rows["aave-v3-gho"]["aliasAddresses"], LK.ADDRESS_ALIASES["aave-v3-gho"])
        self.assertTrue(all("chain" in u for x in PROTOCOLS for u in x["surfaces"]))


if __name__ == "__main__":
    unittest.main()
