"""build_lookup.py - the deterministic protocol / token lookup catalog (task-14e685be73f9).

One item per published record page: every /protocols/<slug>/ page (index.json Sprint protocols, Base-EAS-attested, plus
rpc-pinned.json Wave-2 protocols, RPC-observed only) and every /briefs/<slug>/ page (onboarding.json + radar.json).
Every value is read from docs/api/v1/{index,rpc-pinned,onboarding,radar}.json; only the token / product aliases (TOKENS)
are curated here, and a protocol without aliases fails the build.

Writes:
  docs/api/v1/lookup.json                       the catalog (schema pacta.protocol_lookup_catalog.v1)
  packages/mcp-server/src/lookup.mjs            the same items, between the CATALOG-BEGIN / CATALOG-END markers
pacta-core keeps packages/mcp-server/src/lookup.mjs byte-identical and embeds its LOOKUP block verbatim in
packages/x402-edge-worker/worker.mjs (scripts/sync-lookup-catalog.py), so the hosted gateway answers lookups in memory.

Scoped truthfulness: index.json protocols are evidenceBasis "eas_attested" (on-chain compared with the documentation,
Base EAS UIDs); rpc-pinned protocols are evidenceBasis "rpc_observed" with documentationComparison "not_assessed" and
are never labelled aligned or parameter_delta; briefs are block-pinned verification briefs.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from onboarding_scan import eip55  # noqa: E402  (pure keccak / EIP-55 helper; importing never touches the network)
import control_diff as CD  # noqa: E402  ("What differs": changed vs matched parameters of flagged records)
import re  # noqa: E402
import scorecard_corrections as CORR  # noqa: E402  recordDisplay (Observed / Uncompared rows)

ADDR_RE = re.compile(r"\b0x[0-9a-fA-F]{40}\b")
RELATED_MAX = 16


def _related(es, known, slug=None):
    """Other contracts the records name (ProxyAdmins, Safes, timelocks, tokens), EIP-55, in first-seen order, capped; so a
    pre-flight check of e.g. a token or its ProxyAdmin can cross-link the indexed protocol record. The protocol's verified
    ADDRESS_ALIASES (same-chain user-facing contracts) follow, outside the cap, so a lookup of any of them cross-links too."""
    out = []
    for e in es:
        for t in ("target_contract", "paired_contract", "controller_address", "onchain_observed", "upstream_controller"):
            v = e.get(t)
            for a in ADDR_RE.findall(v if isinstance(v, str) else ""):
                c = eip55(a.lower())
                if c.lower() not in known and c not in out:
                    out.append(c)
    out = out[:RELATED_MAX]
    for a in ADDRESS_ALIASES.get(slug, []) if slug else []:
        c = eip55(a.lower())
        if c.lower() not in known and c not in out:
            out.append(c)
    return out

BASE = "https://pacta.wtf"
CATALOG_SCHEMA = "pacta.protocol_lookup_catalog.v1"
CHAIN_IDS = {"ethereum": 1, "base": 8453}
ONB_CHAIN = {"eth": "ethereum", "base": "base"}
SOURCES = ["/api/v1/index.json", "/api/v1/rpc-pinned.json", "/api/v1/onboarding.json", "/api/v1/radar.json"]
# Searchable token / product symbols and aliases per record page (curated; everything else comes from the feeds).
TOKENS = {
    "aave-v3-gho": ["GHO", "AAVE"], "across-protocol-hubpool": ["ACX"], "aerodrome-finance-base": ["AERO", "veAERO"],
    "balancer-v2-vault-timelock": ["BAL", "veBAL"], "bedrock-unieth": ["uniETH"], "beefy-finance-base": ["BIFI"],
    "centrifuge-liquidity-pools-base": ["CFG"], "compound-v3-comet": ["COMP", "cUSDCv3", "Comet"], "convex-finance": ["CVX", "cvxCRV"],
    "curve-finance-crvusd": ["crvUSD", "CRV"], "eigenlayer-core": ["EIGEN"], "ethena-usde-susde": ["USDe", "sUSDe", "ENA"],
    "ether-fi-core-eeth-weeth": ["eETH", "weETH", "ETHFI"], "ether-fi-liquid-veda-boringvault": ["Liquid", "Veda", "BoringVault"],
    "euler-v2-evk": ["EUL", "EVK", "EVC"], "extra-finance-base": ["EXTRA"], "f-x-protocol-v2": ["fxUSD", "FXN"],
    "fluid-instadapp": ["FLUID", "INST"], "frax-ether-sfrxeth": ["frxETH", "sfrxETH", "FXS"], "gearbox-v3-v3-1": ["GEAR"],
    "inverse-finance-firm": ["DOLA", "INV", "FiRM"], "kelp-dao-rseth": ["rsETH"], "lido-steth-dual-governance": ["stETH", "wstETH", "LDO"],
    "liquity-v2-bold": ["BOLD", "LQTY"], "lombard-lbtc": ["LBTC"], "mantle-liquid-staking-meth-cmeth": ["mETH", "cmETH"],
    "maple-finance-v2-syrup": ["SYRUP", "syrupUSDC", "syrupUSDT"], "mellow-protocol-lido-earn": ["Mellow", "Lido Earn"],
    "metamorpho-re7-weth-vs-re7-usdt": ["Re7WETH", "Re7USDT", "MetaMorpho"], "moonwell-lending-base": ["WELL"], "morpho-blue-core": ["MORPHO"],
    "ondo-finance-ousg-flux-finance": ["OUSG", "ONDO", "Flux"], "origin-superoeth-base": ["superOETHb", "OETH", "OGN"],
    "pendle-finance-v2": ["PENDLE", "vePENDLE"], "puffer-finance-pufeth": ["pufETH", "PUFFER"], "renzo-protocol-ezeth": ["ezETH", "REZ"],
    "reserve-protocol-rtoken": ["eUSD", "RSR"], "resolv-usr-rlp": ["USR", "RLP", "wstUSR", "RESOLV"], "rocket-pool-reth": ["rETH", "RPL"],
    "safe-singleton-core": ["SAFE"], "seamless-protocol-base": ["SEAM"], "spark-sky": ["USDS", "sUSDS", "DAI", "SKY", "MKR", "SPK"],
    "stader-labs-ethx": ["ETHx", "SD"], "stakewise-v3-oseth": ["osETH", "SWISE"], "superform-v2-base": ["Superform", "SuperVaults"],
    "superstate-ustb-uscc": ["USTB", "USCC"], "swell-sweth-rsweth": ["swETH", "rswETH", "SWELL"], "symbiotic-core": ["Symbiotic"],
    "synthetix-v3-core": ["SNX", "sUSD"], "threshold-network-tbtc": ["tBTC", "T"], "treehouse-tree-teth": ["tETH", "TREE"],
    "uniswap-governance-timelock": ["UNI"],
    "usual-money-usd0-usd0": ["USD0", "USD0++", "USUAL"], "yearn-v3": ["YFI"],
    "falcon-finance-usdf-susdf": ["USDf", "sUSDf"], "m0-protocol-m": ["M", "M0", "MToken"], "solv-protocol-solvbtc": ["SolvBTC", "SOLV"], "steakhouse-usdc-metamorpho-base": ["steakUSDC", "Steakhouse", "MetaMorpho"],
    "nexus-mutual": ["NXM", "wNXM", "Nexus Mutual"], "enzyme-finance": ["MLN", "Enzyme"], "stargate-v2": ["STG", "Stargate"], "aerodrome-slipstream-base": ["AERO", "Slipstream"],
    "aave-v3-base": ["AAVE", "Aave Base"], "compound-v3-base": ["COMP", "cUSDCv3"], "liquid-collective-lseth": ["LsETH", "Liquid Collective"], "ethena-usdtb": ["USDtb", "USDTB"],
    "concrete": ["ctDeltaWeETH", "Concrete"], "cap": ["cUSD", "stcUSD", "CAP"], "infinifi": ["iUSD", "siUSD", "liUSD"], "stake-link": ["stLINK", "SDL"],
    "coinbase-wrapped-staked-eth": ["cbETH"], "ssv-network": ["SSV"], "grove-finance": ["GROVE", "stGROVE"], "re": ["reUSD", "reUSDe", "RE"],
    "stake-dao": ["SDT", "veSDT"], "resupply": ["RSUP", "sreUSD"], "yo-protocol": ["yoETH", "yoUSD", "YO"], "liquity-v1-lusd": ["LUSD", "LQTY"],
    "circle-usdc": ["USDC"], "tether-usdt": ["USDT"], "frax-usd-frxusd": ["frxUSD", "sfrxUSD"], "paypal-usd-pyusd": ["PYUSD"],
    "steakhouse-financial-ethereum": ["steakUSDT", "steakPYUSD", "steakUSDC", "Steakhouse"], "uniswap-v4": ["UNI", "Uniswap v4", "PoolManager"], "chainlink-ccip": ["CCIP", "LINK", "Chainlink"], "obol-network": ["OBOL", "stOBOL", "Obol"],
    "layerzero-v2": ["ZRO", "LayerZero", "EndpointV2"], "wormhole-core-ntt": ["Wormhole", "NTT", "Guardian"], "railgun": ["RAIL", "Railgun"], "axelar-network": ["AXL", "Axelar", "AxelarGateway", "InterchainTokenService"],
    # Sprint 26 promotion (bulk harvester v1.3)
    "3f": ["3F"], "3jane-lending": ["3Jane"], "aegis-yusd": ["YUSD"], "aera-v3": ["Aera"], "alchemix-v3": ["ALCX"],
    "anemoy-capital": ["JTRSY"], "ao-bridge": ["AO"], "arrakis-modular": ["Arrakis"], "aster-bridge": ["Aster"],
    "autofinance": ["AUTOfinance"], "avalon-superearn": ["AVL"], "bitfi-basis": ["bfBTC"], "cian-yield-layer": ["ylstETH"],
    "concentrator": ["CTR"], "cooler-loans": ["OHM"], "curve-dex-ethereum": ["Curve"], "derive-v3-options": ["DRV"], "frankencoin": ["FCS"],
    "grvt-bridge": ["GRVT"], "hyperlane": ["Hyperlane"], "idex-v1": ["IDEX"], "ipor-fusion": ["IPOR"], "k3-capital": ["K3"], "kpk": ["KPK"],
    "lighter-bridge": ["LIT"], "makina": ["Makina"], "noon": ["USN"], "origami-finance": ["SKY+"], "pancakeswap-amm-v3": ["PancakeSwap"],
    "polygon-bridge": ["Polygon"], "rockawayx": ["eY10K"], "saturn": ["USDat"], "shift-defi": ["sdUSDC-vault"],
    "sierra-protocol": ["xSOLY"], "sonic-gateway": ["Sonic"], "starknet-bridge": ["STRK"], "team-finance": ["SWAP"],
    "theo-network-thusd": ["thUSD"], "tori-finance": ["trUSD"], "tornado-cash": ["TORN"], "uncx-network-v2": ["UNCX"], "usdt0": ["USDT0"],
    "veda": ["Veda"], "vesper-v1": ["VSP"], "world-chain-bridge": ["World"], "xdai-stake-bridge": ["STAKE"], "yield-basis": ["YB"],
    "yieldnest": ["YND"], "zama": ["Zama"], "zerobase-cedefi": ["ZBT"],
    # Sprint 27 promotion (bulk harvester v1.3)
    "abracadabra-spell": ["SPELL"], "adi-bridge": ["ADI"], "ankr": ["Ankr"], "anvil": ["ANVL"], "arkis": ["Arkis"], "aura": ["Aura"],
    "avant-aveth": ["avETH"], "badger-dao": ["BADGER"], "bancor-v3": ["BNT"], "bio-protocol": ["BIO"], "blur-bids": ["BLUR"],
    "brickken": ["BKN"], "cbridge": ["CELR"], "chamber-vaults": ["DHT"], "cronos-zkevm-bridge": ["zkCRO"], "cvault-finance": ["CORE"],
    "d2-finance": ["DRV++"], "dodo-amm": ["DODO"], "dolomite": ["Dolomite"], "drakewell-usddw": ["JUSD"], "dydx-v3": ["DYDX"],
    "easedefi-org": ["EASE"], "eclipse-bridge": ["ES"], "edgex-bridge": ["EDGE"], "eigenpie": ["Eigenpie"], "equilibria": ["Equilibria"],
    "eth-strategy": ["STRAT"], "exactly": ["Exactly"], "fermiswap": ["FermiSwap"], "flying-tulip-lend": ["FT"], "geth": ["GETH"],
    "gondi-v3": ["Gondi"], "gravity-by-galxe-bridge": ["Gravity"], "hakka-finance": ["HAKKA"], "harvest-finance": ["FARM"],
    "hop-protocol": ["HOP"], "iaero-protocol": ["LIQ"], "inceptionlrt-isolated-restaking": ["InceptionLRT"], "index-coop": ["INDEX"],
    "injective-bridge": ["INJ"], "juicebox-v1": ["JBX"], "kuma-protocol": ["USK"], "ledgity-yield": ["LDY"], "legion": ["Legion"],
    "lista-lending": ["Lista"], "meta-pool-eth": ["mpETH"], "metis-bridge": ["Metis"], "metric-v1": ["Metric"], "metronome-synth": ["MET"],
    "monolith-market": ["Monolith"], "morph-bridge": ["Morph"], "morpheusai": ["MorpheusAI"], "multichain": ["anyMULTI"],
    "native-credit-pool": ["Native"], "nodedao": ["NodeDAO"], "nuva": ["NUVA"], "opengdp-shared-security": ["OpenGDP"],
    "orderly-bridge": ["ORDER"], "paradex-bridge": ["DIME"], "pickle": ["Pickle"], "piku-finance": ["PIKU"], "pirex": ["BTRFLY"],
    "pooltogether-v3": ["POOL"], "privacy-pools-v1": ["Privacy"], "ribbon": ["RBN"], "ring-few": ["Ring"], "royco-v2": ["Royco"],
    "sosovalue-basis": ["SOSO"], "spectra-metavaults": ["SPECTRA"], "stafi": ["FIS"], "stakestone-stone": ["STO"],
    "steer-protocol": ["Steer"], "strata-markets": ["srUSDe"], "sushiswap-v3": ["SushiSwap"], "symbiosis": ["SIS"],
    "synapse-cross-chain-bridge": ["SYN"], "syntropia": ["synUSD"], "tangent-finance": ["Tangent"], "the-idols": ["VIRTUE"],
    "ultrayield-vaults": ["sbUSD"], "umia": ["Umia"], "unslashed": ["USF"], "wildcat-protocol": ["Wildcat"], "xsy": ["UTY"],
    "yieldfi": ["yUSD"], "yuzu-money": ["yzCash"], "zircuit-staking": ["Zircuit"], "zora-bridge": ["ZORA"], "ztln-p": ["ZTLN"],
    # Sprint 28 promotion (bulk harvester v2.0)
    "40-acres-base": ["40Acres"], "angle": ["Angle"], "angstrom": ["Angstrom"], "apex-pro": ["APEX"], "apy-finance": ["APY"],
    "asymmetry-finance": ["ASF"], "augur": ["REPv2"], "baseline-protocol": ["Baseline"], "benddao-ape-staking": ["BEND"],
    "blast-pre-launch-farm": ["Blast"], "bmx-freestyle": ["BMX"], "clipper": ["SAIL"], "convergence-fi": ["Convergence"],
    "creth2": ["CREAM"], "debridge": ["deBridge"], "decentralized-euro": ["WFPS"], "defi-saver": ["DeFiSaver"], "defil": ["DFL"],
    "delv-yield": ["DELV"], "derivadex": ["DDX"], "dexfi-aggregator": ["DexFi"], "diem-relay": ["DIEM"], "dxsale": ["SALE"],
    "ekubo": ["Ekubo"], "elfomofi": ["ElfomoFi"], "fake-world-assets-v2": ["FWA"], "flaunch": ["flETH"], "flexa": ["AMP"],
    "flokifi-locker": ["FLOKI"], "friend-tech-v1": ["FRIEND"], "gamma": ["Gamma"], "glif": ["stICNT"], "goldfinch": ["GFI"], "gro": ["Gro"],
    "hashport": ["Hashport"], "hegic": ["Hegic"], "ichi": ["ICHI"], "idle": ["Idle"], "interest-protocol": ["USDI"], "jpy-defi": ["JPY"],
    "kine-finance": ["Kine"], "king-protocol": ["KING"], "kyberswap-classic": ["KNC"], "landx-finance": ["LNDX"], "lazy": ["lazyUSD"],
    "lendflare": ["LFT"], "lusd-chickenbonds": ["bLUSD"], "mcdex": ["MCB"], "mortgagefi": ["mf-e-usdc-weth"], "nami": ["Nami"],
    "nftx": ["NFTX"], "nucleus": ["bobaETH"], "outcome-finance": ["Outcome"], "overtime": ["OVER"], "panoptic-v2": ["PANOPTIC-NFT"],
    "parallel-protocol-v3": ["PRL"], "peapods-finance": ["PEAS"], "punks-terminal": ["Punks"], "quickswap-v4": ["Quickswap"],
    "reflexer": ["FLX"], "saffron-vaults": ["SFI"], "sato": ["SATO"], "smardex-usdn": ["SMARDEX"], "sofa-org": ["RCH"],
    "sommelier": ["somm"], "sport-fun": ["FUN"], "stablehodl": ["StableHodl"], "steakhouse-prime-usdc-base": ["steakUSDC"],
    "supernova-cl": ["Supernova"], "synfutures-v3": ["SynFutures"], "taiko-bridge": ["TAIKO"], "tokenworks": ["TokenWorks"],
    "trueo": ["TRUE"], "unitus": ["UTS"], "upshift": ["Upshift"], "vetro": ["VETRO"], "wan-bridge": ["Wan"], "whales-market": ["Whales"],
    "wintermute-confidential-wbtc-ethereum": ["armcWBTC"], "woofi-earn": ["WOO"],
    # Sprint 29 promotion (bulk harvester v2.0)
    "base-bridge": ["BaseBridge"], "lagoon": ["Lagoon"],
    # Sprint 30 promotion (bulk harvester v2.0)
    "bedrock-unibtc": ["Bedrock(uniBTC)"],
    # Sprint 32 promotion (bulk harvester v2.0)
    "circle-gateway": ["CircleGateway"],
    # Sprint 37 promotion (bulk harvester v2.0)
    "katana": ["KAT"], "mev-capital-weth-metamorpho": ["MCwETH"], "odyssey-finance": ["Odyssey"],
    # briefs
    "kerne-kusd-base": ["kUSD", "Kerne"], "efix-efixdi-base": ["efixDI+", "EFIXDI", "EFIX"], "circle-cirbtc-eth": ["cirBTC", "Circle"],
    "paxos-paxgy-eth": ["PAXGy", "Paxos"], "tether-usat-eth": ["USAT", "Tether"], "ethena-ops-0x0ca0-0x1fe5": ["USDe", "RLUSD", "USAT"],
    "etherfi-op-0x244e": ["eETH", "weETH"], "treehouse-op-0x2f11": ["TREE", "tETH"],
    "lombard-ops-0xceee-0x2f2a-0x6404": ["LBTC", "BTC.b"], "beefy-base-op-0x3302": ["cowAeroBaseUSDC-VVV", "VVV"],
    "ethena-ops-0xb028-0xca05-0x108e-0x070a": ["USDe", "USDm"], "yearn-v3-op-0x2a14": ["yvUSDC-1", "yvUSD", "yvWETH-1", "yvFlexUSDC"],
    "etherfi-liquid-op-0xf0fb": ["liquidUSD", "liquidETH", "liquidBTC"], "lombard-op-0xd07f": ["LBTC", "BTC.b", "AssetRouter"],
    "umia-op-0x3d35": ["Umia", "UmiaHub", "UmiaMarketCore"], "cap-op-0x3397": ["cUSD", "Cap", "EigenServiceManager"], "compound-v3-op-0x86b4": ["cWETHv3", "Comet", "Linea"],
    "lista-lending-op-0x21df": ["Lista", "Moolah", "Liquidator", "EmergencySwitchHub"],
}


def _addr(a):
    """Checksummed address; the feeds already publish EIP-55 forms, so any mismatch is a data error."""
    if a is None:
        return None
    c = eip55(a)
    assert a.lower() == c.lower() and a in (c, a.lower()), f"malformed or mis-checksummed address in feed: {a}"
    return c


# RPC-pinned protocols converted in place to EAS-attested keep the primary contract, its label and the controller their
# RPC-pinned page published (values copied from that record), so the protocol page, the lookup preflight and the durable graph
# (pacta-proto-* anchor, its pacta-ctrl-* nodes and governed_by_controller edges) never lose an anchor on conversion.
CONVERTED_CONTINUITY = {
    "frax-ether-sfrxeth": {"primaryContract": "0xbAFA44EFE7901E04E39Dad13167D089C559c1138", "targetLabel": "frxETHMinter",
                           "controllerAddress": "0x8306300ffd616049FD7e4b0354a64Da835c1A81C", "controllerKind": "multisig_safe"},
    "puffer-finance-pufeth": {"primaryContract": "0xD9A442856C234a39a81a089C06451EBAa4306a72", "targetLabel": "PufferVault (pufETH)",
                              "controllerAddress": "0x8c1686069474410E6243425f4a10177a94EBEE11", "controllerKind": "contract_controller"},
    # Sprint 21 conversions (values from the published RPC-pinned records)
    "aerodrome-finance-base": {"primaryContract": "0x420DD381b31aEf6683db6B902084cB0FFECe40Da", "targetLabel": "AerodromePoolFactory",
                               "controllerAddress": "0x16613524e02ad97eDfeF371bC883F2F5d6C480A5", "controllerKind": "contract_controller"},
    "balancer-v2-vault-timelock": {"primaryContract": "0xBA12222222228d8Ba445958a75a0704d566BF2C8", "targetLabel": "BalancerV2Vault",
                                   "controllerAddress": "0x6048A8c631Fb7e77EcA533Cf9C29784e482391e7", "controllerKind": "contract_controller"},
    # Sprint 22 conversions (values from the published RPC-pinned records)
    "across-protocol-hubpool": {"primaryContract": "0xc186fA914353c44b2E33eBE05f21846F1048bEda", "targetLabel": "AcrossHubPool",
                                "controllerAddress": "0xB524735356985D2f267FA010D681f061DfF03715", "controllerKind": "multisig_safe"},
    "beefy-finance-base": {"primaryContract": "0xfc69704cC3cAac545cC7577009Ea4AA04F1a61Eb", "targetLabel": "BeefyFeeConfig_Base",
                           "controllerAddress": "0x6FfaCA7C3B38Ec2d631D86e15f328ee6eF6C6226", "controllerKind": "multisig_safe"},
    # Sprint 23 conversions (values from the published RPC-pinned records)
    "uniswap-governance-timelock": {"primaryContract": "0x1F98431c8aD98523631AE4a59f267346ea31F984", "targetLabel": "UniswapV3Factory",
                                    "controllerAddress": "0xf2371551Fe3937Db7c750f4DfABe5c2fFFdcBf5A", "controllerKind": "contract_controller"},
    "reserve-protocol-rtoken": {"primaryContract": "0xA0d69E286B938e21CBf7E51D71F6A4c8918f482F", "targetLabel": "ReserveRToken_eUSD",
                                "controllerAddress": None, "controllerKind": "access_control"},
    # Sprint 24 conversions (values from the published RPC-pinned lookup items)
    "synthetix-v3-core": {"primaryContract": "0xffffffaEff0B96Ea8e4f94b2253f31abdD875847", "targetLabel": "SynthetixCoreProxy",
                          "controllerAddress": "0xEb3107117FEAd7de89Cd14D463D340A2E6917769", "controllerKind": "multisig_safe"},
    "centrifuge-liquidity-pools-base": {"primaryContract": "0x7Ed48C31f2fdC40d37407cBaBf0870B2b688368f", "targetLabel": "CentrifugeRoot_Base",
                                        "controllerAddress": None, "controllerKind": "access_control"},
    # Sprint 25 conversions: published primary contracts and controllers kept (the published graph only grows). Bedrock's label is
    # corrected by the Sprint 25 scan: the primary contract is the uniETH token proxy, whose owner() is the published Safe 0xAeE0..721A
    # (also the Staking / Restaking admin); its upgrade path (ProxyAdmin 0xa5F2..89C6, owned by a second Safe) is in the Sprint 25
    # upgrade-admin record. The Safe singleton has no controller (it is immutable).
    "bedrock-unieth": {"primaryContract": "0xF1376bceF0f78459C0Ed0ba5ddce976F1ddF51F4", "targetLabel": "uniETH token proxy (Universal ETH)",
                       "controllerAddress": "0xAeE017052DF6Ac002647229D58B786E380B9721A", "controllerKind": "multisig_safe"},
    "safe-singleton-core": {"primaryContract": "0x41675C099F32341bf84BFc5382aF534df5C7461a", "targetLabel": "SafeSingleton_v1_4_1",
                            "controllerAddress": None, "controllerKind": "immutable_or_role_governed"},
}
# Extra contract addresses a protocol answers to in pacta_lookup_protocol (an exact 0x query), each a same-chain user-facing contract
# verified on-chain: aave-v3-base: the Aave V3 Base Pool (PoolAddressesProvider 0xe20f..d64D getPool() and Pool.ADDRESSES_PROVIDER(),
# Sprint 24 evidence). The Sprint 36 additions were each read at the Sprint 36 pins (Ethereum #26,455,787; Base #59,903,224) on two
# providers: eth_getCode non-empty and a binding getter (symbol(), ADDRESSES_PROVIDER() / getPool(), sUSDe asset() = USDe,
# vePENDLE pendle() = PENDLE); evidence in the Sprint 36 alias-verification.json and its raw transcript.
ADDRESS_ALIASES = {
    "aave-v3-base": ["0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"],
    "stader-labs-ethx": ["0xA35b1B31Ce002FBF2058D22F30f95D405200A15b"],                     # ETHx
    "circle-gateway": ["0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"],                       # USDC (Ethereum)
    "aave-v3-gho": ["0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
                    "0x40D16FC0246aD3160Ccc09B8D0D3A2cD28aE6C2f", "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e"],  # Pool, AAVE, GHO, Provider
    "lido-steth-dual-governance": ["0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84", "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0",
                                   "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32"],                # stETH, wstETH, LDO
    "ethena-usde-susde": ["0x4c9EDD5852cd905f086C759E8383e09bff1E68B3", "0x9D39A5DE30e57443BfF2A8307A4256c8797A3497",
                          "0x57e114B691Db790C35207b2e685D4A43181e6061"],                         # USDe, sUSDe, ENA
    "pendle-finance-v2": ["0x888888888889758F76e7103c6CbF23ABbF58F946", "0x808507121B80c02388fAd14726482e061B8da827",
                          "0x4f30A9D41B80ecC5B94306AB4364951AE3170210"],                         # PendleRouterV4, PENDLE, vePENDLE
    "spark-sky": ["0xdC035D45d973E3EC169d2276DDab16f1e407384F", "0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD",
                  "0x6B175474E89094C44Da98b954EedeAC495271d0F", "0x56072C95FAA701256059aa122697B133aDEd9279",
                  "0xC13e21B648A5Ee794902342038FF3aDAB66BE987"],                                 # USDS, sUSDS, DAI, SKY, SparkLend Pool
    "ether-fi-core-eeth-weeth": ["0x35fA164735182de50811E8e2E824cFb9B6118ac2", "0xCd5fE23C85820F7B72D0926FC9b05b43E359b7ee",
                                 "0xFe0c30065B384F05761f15d0CC899D4F9F9Cc0eB"],                  # eETH, weETH, ETHFI
    "morpho-blue-core": ["0x58D97B57BB95320F9a05dC918Aef65434969c2B2"],                     # MORPHO
}


def _corrected_status(slug, pinned):
    """{"scorecardStatus": "unresolved" | "recent_change"} for a protocol tools/scorecard_corrections.json marks with a neutral
    status (unresolved: the comparison does not establish a documented breach; recent_change: observed within 48 hours of an
    on-chain change, re-checked after 72 hours), with the correction's sub-pill as a note when it has one; {} otherwise."""
    import scorecard_corrections as CORR
    c = CORR.get(slug) or {}
    if pinned or c.get("status") not in CORR.NEUTRAL:
        return {}
    return {"scorecardStatus": c["status"], **({"scorecardStatusNote": c["subPill"]} if c.get("subPill") else {})}


def _protocol_item(name, v):
    es, first = v["entries"], v["entries"][0]
    pinned = v["pinned"]
    chain = first.get("chain", "ethereum")
    classes = sorted({e["classification"] for e in es})
    if pinned:
        assert classes == ["rpc_observed"], (name, classes)
        ctrl, ctrl_kind = _addr(first.get("controller_address")), first.get("controller_kind")
        basis = {"classification": "rpc_observed", "evidenceBasis": "rpc_observed", "easAttested": False, "baseEasUids": [],
                 "documentationComparison": "not_assessed"}
    else:
        src = first.get("observed_delay_source") or {}
        ctrl = _addr(src.get("contract")) if src.get("contract") else None
        ctrl_kind = "timelock" if ctrl else None
        uids = sorted({e["base_eas_uid"] for e in es})
        assert all(u and u.startswith("0x") and len(u) == 66 for u in uids), name
        assert "rpc_observed" not in classes, name
        basis = {"classification": classes[0] if len(classes) == 1 else "mixed", "evidenceBasis": "eas_attested", "easAttested": True,
                 "baseEasUids": uids, "documentationComparison": "compared", "sprints": sorted({int(e["sprint"]) for e in es})}
    primary, label = _addr(first["target_contract"]), first["target_label"]
    keep = CONVERTED_CONTINUITY.get(v["slug"]) if not pinned else None
    if keep:
        primary, label, ctrl, ctrl_kind = (_addr(keep["primaryContract"]), keep["targetLabel"], _addr(keep["controllerAddress"]),
                                           keep["controllerKind"])
    return {"kind": "protocol", "slug": v["slug"], "name": name, "tokens": TOKENS[v["slug"]], "category": first["category"],
            "chain": chain, "chainId": CHAIN_IDS[chain], "primaryContract": primary, "targetLabel": label,
            "controllerAddress": ctrl, "controllerKind": ctrl_kind,
            "observedDelaySeconds": first.get("observed_delay_seconds"),
            # no documented delay when the documentation that stated it is shown as Observed / Uncompared (Obol: v1.11 governance paused)
            "documentedDelaySeconds": (None if any(CORR.record_display(e_["id"]).get("badge") == "observed" and e_.get("documented_delay_seconds")
                                                   for e_ in es) else first.get("documented_delay_seconds")),
            **basis,
            **_corrected_status(v["slug"], pinned),
            "surfaces": [{"id": e["id"], "surface": e["surface"], "classification": CORR.surface_class(e),
                          "targetContract": _addr(e["target_contract"]), "targetLabel": e["target_label"], "chain": e.get("chain", "ethereum"),
                          "blockNumber": int(e["block_number"])} for e in es],
            "pinnedBlock": max(int(e["block_number"]) for e in es),
            "relatedContracts": _related(es, {a.lower() for a in [primary, ctrl] + [e["target_contract"] for e in es] if isinstance(a, str)},
                                         v["slug"]),
            "whatDiffers": CD.what_differs(es),
            "url": f"{BASE}/protocols/{v['slug']}/", "preflightArgs": {"chain": chain, "address": primary},
            **({"aliasAddresses": [_addr(a) for a in ADDRESS_ALIASES[v["slug"]]]} if v["slug"] in ADDRESS_ALIASES else {})}


def _onboarding_item(b):
    chain = ONB_CHAIN[b["chain"]]
    supply = [c for c in b["checks"] if c.get("sig") == "totalSupply()"]
    assert supply, b["slug"]
    token = _addr(supply[0]["to"])
    return {"kind": "brief", "slug": b["slug"], "name": f'{b["asset"]} onboarding verification brief', "tokens": TOKENS[b["slug"]],
            "category": "Collateral onboarding verification brief", "chain": chain, "chainId": CHAIN_IDS[chain],
            "primaryContract": token, "targetLabel": b["asset"], "controllerAddress": None, "controllerKind": None,
            "observedDelaySeconds": None, "documentedDelaySeconds": None,
            "classification": "onboarding_delta_brief", "evidenceBasis": "pinned_rpc_brief", "easAttested": False, "baseEasUids": [],
            "venue": b["venue"], "forumUrl": b["forum"]["url"], "pinnedBlock": int(b["pin"]["number"]), "relatedProtocolSlug": None,
            "url": f"{BASE}/briefs/{b['slug']}/", "preflightArgs": {"chain": chain, "address": token}}


def _radar_item(it, related):
    slug = it["brief"].rstrip("/").split("/")[-1]
    tl = _addr(it["timelock"])
    chain = {v: k for k, v in CHAIN_IDS.items()}[it.get("chain_id", 1)]   # v4.6: Base radar items (chain_id 8453)
    return {"kind": "brief", "slug": slug, "name": it["title"], "tokens": TOKENS[slug], "category": "Timelock radar brief (queued operations)",
            "chain": chain, "chainId": CHAIN_IDS[chain], "primaryContract": tl, "targetLabel": f'{it["protocol"]} timelock',
            "controllerAddress": tl, "controllerKind": "timelock", "observedDelaySeconds": int(it["min_delay_seconds"]), "documentedDelaySeconds": None,
            "classification": "timelock_radar_brief", "evidenceBasis": "pinned_rpc_brief", "easAttested": False, "baseEasUids": [],
            "eta": int(it["eta"]) if it.get("eta") else None, "relatedProtocolSlug": related[slug],
            "url": f"{BASE}/briefs/{slug}/", "preflightArgs": {"chain": chain, "address": tl}}


def build_items(sp, onb, radar, brief_protocol):
    """sp = build_site.site_protocols(idx, pinned); brief_protocol = build_site.BRIEF_PROTOCOL."""
    protocols = sorted((_protocol_item(n, v) for n, v in sp.items()), key=lambda x: x["slug"])
    briefs = sorted([_onboarding_item(b) for b in onb["briefs"]] + [_radar_item(it, brief_protocol) for it in radar["items"] if it.get("brief")],
                    key=lambda x: x["slug"])
    items = protocols + briefs
    slugs = [x["slug"] for x in items]
    assert len(slugs) == len(set(slugs)), "duplicate slug"
    assert set(TOKENS) == set(slugs), f"TOKENS out of sync: missing {sorted(set(slugs) - set(TOKENS))} extra {sorted(set(TOKENS) - set(slugs))}"
    assert all(x["tokens"] for x in items)
    assert all(x["relatedProtocolSlug"] in {p["slug"] for p in protocols} for x in briefs if x["relatedProtocolSlug"])
    for x in items:
        for s in json.dumps(x, ensure_ascii=False):
            assert s not in "  ", x["slug"]
    return items


def totals(items):
    p = [x for x in items if x["kind"] == "protocol"]
    return {"protocols": len(p), "briefs": len(items) - len(p), "easAttestedProtocols": sum(x["easAttested"] for x in p),
            "rpcObservedProtocols": sum(x["evidenceBasis"] == "rpc_observed" for x in p), "items": len(items)}


def catalog_json(items):
    doc = {"schema": CATALOG_SCHEMA, "sources": [BASE + s for s in SOURCES], "totals": totals(items), "items": items,
           "search": {"http": "https://api.pacta.wtf/v1/protocols/lookup?q=<name, token or 0x address>",
                      "mcp": "pacta_lookup_protocol", "note": "Free discovery in every pricing mode; preflightArgs feed pacta_check_preflight directly."}}
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


BEGIN, END = "// ---- CATALOG-BEGIN (generated by tools/build_lookup.py; do not edit by hand)\n", "// ---- CATALOG-END\n"


def catalog_js(items):
    rows = "".join("  " + json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + ",\n" for x in items)
    # the Worker's static gate forbids the bare token "process" (no Node globals): verbatim quotes keep their value via \u0065
    rows = re.sub(r"\bprocess", r"proc\\u0065ss", rows)
    return BEGIN + "export const LOOKUP_CATALOG = lookupFreeze([\n" + rows + "]);\n" + END


def sync_module(path, items):
    """Rewrite the generated catalog between the markers of packages/mcp-server/src/lookup.mjs; True when it changed."""
    src = open(path, encoding="utf-8").read()
    a, b = src.index(BEGIN), src.index(END) + len(END)
    new = src[:a] + catalog_js(items) + src[b:]
    if new != src:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new)
    return new != src


def write_all(root, docs, sp, onb, radar, brief_protocol):
    items = build_items(sp, onb, radar, brief_protocol)
    t = totals(items)
    n_pin = sum(v["pinned"] for v in sp.values())          # counts follow the feeds; verify_site_v2.EXPECT pins the published numbers
    assert (t["protocols"], t["briefs"], t["easAttestedProtocols"], t["rpcObservedProtocols"]) == (
        len(sp), len(onb["briefs"]) + sum(1 for it in radar["items"] if it.get("brief")), len(sp) - n_pin, n_pin), t
    with open(os.path.join(docs, "api", "v1", "lookup.json"), "w", encoding="utf-8") as fh:
        fh.write(catalog_json(items))
    sync_module(os.path.join(root, "packages", "mcp-server", "src", "lookup.mjs"), items)
    write_badges(docs, items)
    with open(os.path.join(docs, "api", "v1", "protocols.json"), "w", encoding="utf-8") as fh:
        fh.write(protocols_json(sp, items))
    return items


# ---- control-plane status badges: byte-identical to badgeSvg() in packages/mcp-server/src/lookup.mjs (the worker's
# GET /v1/badges/<slug>.svg serves the same block); verify_site_v2.py compares all 53 through node.
BADGE_TITLE = "Pacta Control Plane"
# v4.5.1 R3-01: Aligned is neutral (gray-700, white text 10.3:1), never safety-green; amber stays reserved for Parameter Delta
BADGE_TIERS = {"aligned": ("Aligned · Base EAS", "#374151"), "parameter_delta": ("Delta", "#b45309"),
               "rpc_observed": ("Observed", "#475569"),
               # neutral slate tiers for a protocol whose comparison does not establish a documented breach
               # (tools/scorecard_corrections.json status "unresolved"): never the amber Parameter Delta, never Aligned
               "unresolved": ("Unresolved · Unverified Scope", "#475569"), "docs_updated": ("Docs Updated · Pending Re-Read", "#475569"),
               # info blue for status "recent_change": changed on chain within 48h of the pin, re-checked after 72h before any Delta
               "recent_change": ("Changed Recently · Re-Check Pending", "#0369a1")}


def badge_tier(item):
    if not item or item.get("kind") != "protocol":
        return None
    if item.get("evidenceBasis") == "rpc_observed":
        return "rpc_observed"
    if item.get("scorecardStatus") == "recent_change":      # info: changed on chain recently; documents not yet updated
        return "recent_change"
    if item.get("scorecardStatus") == "docs_updated":       # neutral: the documentation now names the retained observation
        return "docs_updated"
    if item.get("scorecardStatus") == "unresolved":         # neutral: a documented breach is not established
        return "docs_updated" if item.get("scorecardStatusNote") else "unresolved"
    return "aligned" if item.get("classification") == "aligned_baseline" else "parameter_delta"


def _num(x):
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def badge_svg(item):
    tier = badge_tier(item)
    right, color = BADGE_TIERS[tier]
    left, slug = BADGE_TITLE, item["slug"]
    lw, rw = len(left) * 7 + 12, len(right) * 7 + 12
    w = lw + rw
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{left}: {right}">'
            f'<title>{left}: {right} ({slug})</title>'
            f'<clipPath id="r"><rect width="{w}" height="20" rx="3" fill="#fff"/></clipPath>'
            f'<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#1f2937"/><rect x="{lw}" width="{rw}" height="20" fill="{color}"/></g>'
            f'<g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,Geneva,sans-serif" font-size="11">'
            f'<text x="{_num(lw / 2)}" y="14">{left}</text><text x="{_num(lw + rw / 2)}" y="14">{right}</text></g></svg>\n')


def write_badges(docs, items):
    d = os.path.join(docs, "badges")
    os.makedirs(d, exist_ok=True)
    want = {}
    for x in items:
        if x["kind"] == "protocol":
            want[x["slug"] + ".svg"] = badge_svg(x)
    for name in os.listdir(d):                      # stale badges of removed protocols never linger
        if name.endswith(".svg") and name not in want:
            os.remove(os.path.join(d, name))
    for name, svg in sorted(want.items()):
        with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
    return want


# ---- docs/api/v1/protocols.json: one record per /protocols/<slug>/ page with its badge tier, evidence basis and pinned
# surfaces (block number + hash). The same truthful split as the catalog: 33 eas_attested vs 20 rpc_observed.
PROTOCOLS_SCHEMA = "pacta.protocols.v1"
API = "https://api.pacta.wtf"
REGISTRY = "0x35D21Bb4Df6586FE7759b5e57263ffeB3e1fd872"
EAS_BASE = "0x4200000000000000000000000000000000000021"
EAS_SCHEMA_UID = "0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83"


def protocols_json(sp, items):
    by = {x["slug"]: x for x in items if x["kind"] == "protocol"}
    out = []
    for name, v in sp.items():
        x = by[v["slug"]]
        tier = badge_tier(x)
        surf = []
        for e in v["entries"]:
            surf.append({"id": e["id"], "surface": e["surface"], "classification": CORR.surface_class(e), "targetContract": _addr(e["target_contract"]),
                         "targetLabel": e["target_label"], "chain": e.get("chain", "ethereum"), "blockNumber": int(e["block_number"]),
                         "blockHash": e["block_hash"], "baseEasUid": e.get("base_eas_uid"), "sprint": e.get("sprint")})
        out.append({"slug": x["slug"], "name": name, "category": x["category"], "chain": x["chain"], "chainId": x["chainId"],
                    "url": x["url"], "evidenceBasis": x["evidenceBasis"], "easAttested": x["easAttested"],
                    "documentationComparison": x["documentationComparison"], "classification": x["classification"],
                    **{k: x[k] for k in ("scorecardStatus", "scorecardStatusNote") if k in x},
                    "sprints": x.get("sprints", []), "baseEasUids": x["baseEasUids"],
                    "badge": {"tier": tier, "label": BADGE_TIERS[tier][0], "svg": f"{BASE}/badges/{x['slug']}.svg", "live": f"{API}/v1/badges/{x['slug']}.svg"},
                    "primaryContract": x["primaryContract"], "targetLabel": x["targetLabel"], "controllerAddress": x["controllerAddress"],
                    "controllerKind": x["controllerKind"], "preflightArgs": x["preflightArgs"], "tokens": x["tokens"], "surfaces": surf,
                    "relatedContracts": x["relatedContracts"], **({"aliasAddresses": x["aliasAddresses"]} if "aliasAddresses" in x else {})})
    out.sort(key=lambda r: r["slug"])
    tiers = {}
    for r in out:
        tiers[r["badge"]["tier"]] = tiers.get(r["badge"]["tier"], 0) + 1
    doc = {"schema": PROTOCOLS_SCHEMA, "totals": {"protocols": len(out), "easAttested": sum(r["easAttested"] for r in out),
                                                  "rpcObserved": sum(r["evidenceBasis"] == "rpc_observed" for r in out),
                                                  "surfaces": sum(len(r["surfaces"]) for r in out), "badgeTiers": dict(sorted(tiers.items()))},
           "evidence": {"eas_attested": "Base-EAS-attested Sprint records: on-chain control plane compared with the protocol's documentation.",
                        "rpc_observed": "RPC-pinned records: on-chain control plane pinned at an archive block; documentation not assessed (documentationComparison: not_assessed); not EAS-attested."},
           "sentinelGuard": {"package": "packages/sentinel-guard (PactaSentinelGuard.sol)", "registry": REGISTRY, "eas": EAS_BASE, "schemaUid": EAS_SCHEMA_UID,
                             "bind": "bind(collateral, sprintId, easUid) with a Sprint id from `sprints` and its UID from `baseEasUids` (eas_attested protocols only; an unbound collateral can never have its cap increased)",
                             "guide": f"{BASE}/integrations/vault-factories/"},
           "protocols": out}
    t = doc["totals"]
    assert t["protocols"] == len(items_p := [x for x in items if x["kind"] == "protocol"]) == t["easAttested"] + t["rpcObserved"], t
    assert t["easAttested"] == sum(x["evidenceBasis"] == "eas_attested" for x in items_p), t
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
