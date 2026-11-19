# Sprint 33 Protocol Commitment Summary — Block `26452373`

- **Ethereum Mainnet pin**: `26452373` (`0x193a195`), canonical block hash `0x63bfaa16f0019d8b37e757265d351bd135ad41e6ffa46207284198917123c55d`, timestamp `2026-11-19 23:18:47 UTC` (`1795130327`); the `finalized` head, both endpoints returning the same number and hash
- **Base Mainnet pin**: `59699598` (`0x38ef18e`), canonical block hash `0x2f1913093955cab789adde23d44cae9905a757de878fbe6e589477a88e66cb0f`, timestamp `2026-11-19 23:18:15 UTC` (`1795130295`); the `finalized` head, both endpoints returning the same number and hash
- **Scanner**: Pacta by Fractal Neurons (Pacta Protocol Commitments DRI), bulk harvester v2.1. Read-only `eth_call` / `eth_getStorageAt` / `eth_getCode` batched through Multicall3 at the pinned block, on two independent RPCs per chain with identical block hashes: `ethereum-rpc.publicnode.com` + `rpc.mevblocker.io` (Ethereum), `base-rpc.publicnode.com` + `mainnet.base.org` (Base). Documentation: HTTP-200 first-party snapshots named by their SHA-256; every quote below is an exact substring of its snapshot's text and every value is re-derived from the pinned reads by the validator (no model output is trusted). The 2 targets added after the pin (curated-s33-cbridge, curated-s33-debridge) were read at the same block numbers and hashes through two archive-capable endpoints per chain whose block hashes match the pin: `gateway.tenderly.co` + `eth.drpc.org` (Ethereum), `base-rpc.publicnode.com` + `mainnet.base.org` (Base).
- **Result**: `13` records for `13` protocols (`0` new; published protocols with a new record: cBridge, cVault Finance, deBridge, Index Coop, Orderly Bridge, Parallel Protocol V3, Peapods Finance, PoolTogether V3, SoSoValue Basis, SynFutures V3, The Idols, Yield Basis, Zama) — `12` aligned baselines, `0` protective deltas, `1` parameter delta. `verifiedCount = 12`. `driftCount = 1`, the same convention as Sprints 1–32 and `PactaSentinelGuard` (`driftCount != 0` means drift).
- **RPC-pinned promotions (not attested)**: `0` further new protocols are published as RPC-pinned control-plane records at the same pins (listed below); the `145` RPC-pinned protocols already published move to these pins with every stated fact unchanged. They carry no Base EAS UID. `13` published RPC-pinned protocols are documentation-compared for the first time and become Base-EAS protocols here (cBridge, cVault Finance, deBridge, Index Coop, Orderly Bridge, Parallel Protocol V3, Peapods Finance, PoolTogether V3, SoSoValue Basis, SynFutures V3, The Idols, Yield Basis, Zama); their RPC-pinned records are retired.
- **On-chain anchoring**: to be attested on Base Mainnet EAS (`0x4200000000000000000000000000000000000021`) under canonical schema `0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83` (`chainId = 1`, the Ethereum pin above); Base reads are taken at the Base pin.

## 1. cBridge — Pool Bridge signers: owner can resetSigners after 7-day notice; owner = 3-of-5 EOA governance

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **cBridge pool-based Bridge (Ethereum)** | `0x5427FEFA711Eff984124bFBB1AB6fbf5E3DA1820` | `owner()` | cBridge Bridge 0x5427FEFA711Eff984124bFBB1AB6fbf5E3DA1820 (Ethereum, not a proxy; verified source): withdraw() and relay() accept a message signed by the stored signer set, and resetSigners(signers, powers) replaces that set onlyOwner, gated only by block.timestamp > resetTime (notifyResetSigners() sets it to now + noticePeriod()); noticePeriod() = 604,800 s, resetTime() = unset (max) at this pin. owner() = 0xF380166F8490F24AF32Bf47D1aA217FBA62B6575, a SimpleGovernance (verified source): 6 voters, all accounts with no code, powers 10000, 10000, 10000, 10000, 10000, 1; QuorumThreshold params(1) = 60% and FastPassThreshold params(2) = 40% of total power, so 3 of the 5 full-power voters pass a proposal it executes. delayPeriod() = 21,600 s (large-transfer delay). This record does not allege any misuse. (Ethereum `#26452373`) |

Classification: **parameter delta** (1 record).
- 'It is only when nodes with more than ⅔ of the total stake are malicious, that the fund pool will be at risk.' (cbridge-docs.celer.network/print.html) (snapshot sha256 `79ae76ff137b0374fb05144229e22e9d7a405c345b7c4aca6f65ae436fbd36a6`)

## 2. cVault Finance — CORE supply: 10,000, no mint function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **CORE token** | `0x62359Ed7505Efc61FF1D56fEF82158CcaffA23D7` | `totalSupply()` | CORE token 0x62359Ed7505Efc61FF1D56fEF82158CcaffA23D7 (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 10,000. The runtime code holds no selector of mint(address,uint256), mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). Its only mint is the internal one at construction. The owner (an externally owned account) can still set the transfer checker and fee distributor; supply is not among its powers. (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- 'Theres absolutely no way to create new CORE tokens.' (raw.githubusercontent.com/cVault-finance/CORE-v1/master/README.md) (snapshot sha256 `f3118214cfaca9cd03b8bfad20b4692a3513536fcf84d88948ae3e4333a6b079`)

## 3. deBridge — SignatureVerifier: at least 8 of 12 oracle signatures required (2/3)

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **deBridge SignatureVerifier (Ethereum)** | `0x949b3B3c098348b879C9e4F15cecc8046d9C8A8c` | `minConfirmations()` | deBridge SignatureVerifier 0x949b3B3c098348b879C9e4F15cecc8046d9C8A8c (Ethereum; EIP-1967 proxy, implementation 0xfE7De3c1e1BD252C67667B56347cABFC6df08dF4, verified): DeBridgeGate 0x43dE2d77BF8027e25dBD179B491e8d64f38398aA signatureVerifier() identifies this proxy. Its submit(bytes32,bytes,uint8) requires at least minConfirmations() = 8 distinct valid signatures from the 12 oracle addresses (array length word at storage slot 152; entry 0 = 0x4bC16662A2cE381E7bb54Dc577c05619C5E67526); requiredOraclesCount() = 0. The caller-supplied _excessConfirmations argument, and the separate stored excessConfirmations() = 3 check that applies only when submissionsInBlock exceeds confirmationThreshold, can only raise, never lower, that requirement: at least 8 of 12 is the documented 2/3 minimum. (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- 'Validates ≥ 2⁄3 validator signatures before execution' (docs.debridge.com/dmp-details/dmp/deployed-contracts.md) (snapshot sha256 `8ce1f966fceaa7076f3d3271454031c765895a2252fe6cb0845b515bf8cf3b3f`)

## 4. Index Coop — INDEX supply: 10,000,000, no mint function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **INDEX token** | `0x0954906da0Bf32d5479e25f46056d22f08464cab` | `totalSupply()` | INDEX token 0x0954906da0Bf32d5479e25f46056d22f08464cab (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 10,000,000. The runtime code holds no selector of mint(address,uint256), mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). The whole supply is assigned in its constructor; no function creates tokens. (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- 'There is a maximum supply of 10 million $INDEX tokens.' (docs.indexcoop.com/index-coop-community-handbook/resources/governance/the-index-token.md) (snapshot sha256 `0601697fff7e105c3c17fbdacafebc886315f1fcc3330c428ba7e17ac3b3f85a`)

## 5. Orderly Bridge — ORDER supply: 1,000,000,000, no mint function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **ORDER token** | `0xABD4C63d2616A5201454168269031355f4764337` | `totalSupply()` | ORDER token 0xABD4C63d2616A5201454168269031355f4764337 (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 1,000,000,000. The runtime code holds no selector of mint(address,uint256), mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). Its only mint is the internal one at construction. (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- 'Maximum supply: 1,000,000,000' (orderly.network/docs/introduction/tokenomics/distribution-and-emission-schedule) (snapshot sha256 `f006d8a6b07276423a57e31d3b711114d41fc94d7fd91b48fbcc9a04b9caf9eb`)

## 6. Parallel Protocol V3 — PRL: 1,000,000,000, no mint function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **PRL token** | `0x6c0aeceeDc55c9d55d8B99216a670D85330941c3` | `totalSupply()` | PRL token 0x6c0aeceeDc55c9d55d8B99216a670D85330941c3 (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 1,000,000,000. The runtime code holds no selector of mint(address,uint256), mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). Its only mint is the internal one at construction (burns to 0x…dEaD do not reduce totalSupply). (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- 'PRL has no mint function, so its supply can only go down.' (docs.parallel.best/governance/parallel-governance-token-prl.md) (snapshot sha256 `ee48c3b6aac48bd477d4e8416ef1c0a283eddae96a7695042f54d51eaf5c4bb0`)

## 7. Peapods Finance — PEAS (Ethereum): 9,936,639.21, no mint function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **PEAS token** | `0x02f92800F57BCD74066F5709F1Daa1A4302Df875` | `totalSupply()` | PEAS token 0x02f92800F57BCD74066F5709F1Daa1A4302Df875 (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 9,936,639.21. The runtime code holds no selector of mint(address,uint256), mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). Its only mint is the internal one at construction; supply is below the initial 10,000,000 through burns. (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- 'making sure no additional PEAS are ever coming into circulation when expanding to additional chains' (docs.peapods.finance/links/contract-addresses.md) (snapshot sha256 `0aeb46a2d93e9b11620a2f10a5bdcfa336c246b83d34645f2c25da17bb01331c`)

## 8. PoolTogether V3 — POOL supply: 10,000,000; minter() is the zero address

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **POOL token** | `0x0cEC1A9154Ff802e7934Fc916Ed7Ca50bDE6844e` | `totalSupply()` | POOL token 0x0cEC1A9154Ff802e7934Fc916Ed7Ca50bDE6844e (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 10,000,000. The runtime code holds no selector of mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). mint() and setMinter() both require msg.sender == minter(), and minter() is the zero address, so no further POOL can be minted and no minter can be set. (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- 'The total supply of POOL tokens is 10 million' (docs.pooltogether.com/pooltogether/pool-token/pool-supply.md); '$POOL Ethereum 0x0cec1a9154ff802e7934fc916ed7ca50bde6844e' (docs.pooltogether.com/pooltogether/pool-token.md) (snapshot sha256 `00d74a3c4ad6c94031803e7b660d23d90b4a9220759804713af3ac91c5ac67dd`, `db7dfe892abf117f0f98beefa1a9aeb1e07f12bd7756648731723154646ff9b3`)

## 9. SoSoValue Basis — Base SOSO: mint/burn only by the canonical L2StandardBridge

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **SOSO token (Base)** | `0x624e2e7fDc8903165F64891672267AB0FCB98831` | `totalSupply()` | SOSO token (Base) 0x624e2e7fDc8903165F64891672267AB0FCB98831 (Base; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 73,536,304.93. The runtime code holds no selector of mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). OptimismMintableERC20: BRIDGE() = 0x4200000000000000000000000000000000000010 (Base's canonical L2StandardBridge) and REMOTE_TOKEN() = 0x76A0e27618462bDAC7a29104bdcfFf4E6BFCea2D, the Ethereum SOSO the page lists; mint and burn are onlyBridge, so Base supply moves only through the canonical bridge. (Base `#59699598`) |

Classification: **aligned baseline** (1 record).
- 'SOSO was originally deployed as an ERC-20 token on Ethereum and subsequently made available on Base through the official Base bridge.' (sosovalue-white-paper.gitbook.io/sosovalue-whitepaper/8.-tokennomics/8.3-soso-token-cross-chain-architecture.md) (snapshot sha256 `24abfcae210679e67507ec3f026f2b6ecef95781fbc2befcd26da887eaffda29`)

## 10. SynFutures V3 — $F supply: 10,000,000,000, no mint function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **SynFutures $F token** | `0x6e15A54B5EcAc17e58daDedDbe8506a7560252F9` | `totalSupply()` | SynFutures $F token 0x6e15A54B5EcAc17e58daDedDbe8506a7560252F9 (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 10,000,000,000. The runtime code holds no selector of mint(address,uint256), mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). Its only mint is the internal one at construction. (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- '**Maximum Supply:** 10,000,000,000' (docs.synfutures.com/llms-full.txt) (snapshot sha256 `f7cb6b06bd9bb1e39406b73eb4a8a820eb689ba6a5833606a3c1da810cad975a`)

## 11. The Idols — VIRTUE: 99,989,832.94, no mint function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **VIRTUE token** | `0x9416bA76e88D873050A06e5956A3EBF10386b863` | `totalSupply()` | VIRTUE token 0x9416bA76e88D873050A06e5956A3EBF10386b863 (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 99,989,832.94. The runtime code holds no selector of mint(address,uint256), mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). Its only mint is the internal one at construction (100,000,000); supply is lower through burns. (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- 'The $VIRTUE token is non-mintable and will have a maximum total supply of 100,000,000 tokens.' (docs.theidols.io/llms-full.txt) (snapshot sha256 `ca6393d95eaf9cffd990621bb1b8de224ca59d50087e3ef13208d704b95d65ac`)

## 12. Yield Basis — YB: owner() zero; reserve + supply = 1,000,000,000

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **YB token** | `0x01791F726B4103694969820be083196cC7c045fF` | `totalSupply()` | YB token 0x01791F726B4103694969820be083196cC7c045fF (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 760,625,378.82. The runtime code holds no selector of mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). reserve() = 239,374,621.18, and reserve() + totalSupply() = 1,000,000,000 exactly. owner() is the zero address; set_minter and transfer_ownership are owner-only and renounce_ownership() removed the deployer's minter role, so no minter can be added (existing minter memberships are not enumerable). (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- 'reserve + totalSupply equals 1,000,000,000. Nobody can add a new minter, because the token has no owner.' (docs.yieldbasis.com/user/governance/yb-token) (snapshot sha256 `37f493a9cf682e8441e7a4873d4b6234a9da7912820a947282438c96d7c95f48`)

## 13. Zama — ZAMA token: not a proxy, no upgrade function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **ZAMA token** | `0xA12CC123ba206d4031D1c7f6223D1C2Ec249f4f3` | `totalSupply()` | ZAMA token 0xA12CC123ba206d4031D1c7f6223D1C2Ec249f4f3 (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 11,391,483,307.90. The runtime code holds no selector of mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). This record checks the upgrade claim only: minting is role-gated in the token (documented as staking rewards). (Ethereum `#26452373`) |

Classification: **aligned baseline** (1 record).
- '**Some contracts cannot be upgraded**: $ZAMA token' (docs.zama.org/protocol/protocol-apps/governance/governance.md); '| Zama Token       | [`0xA12CC123ba206d4031D1c7f6223D1C2Ec249f4f3`]' (docs.zama.org/protocol/protocol-apps/addresses/mainnet/ethereum.md) (snapshot sha256 `8cdf0597a8ef7b9b2ab0e9e4e37ddb2179c3777942a742ead6bd56422322feb6`, `357cba64d963d735542fc88501c71dbe1c0fa9a4e79abee7ecdafcd020d9bf44`)

## 14. RPC-pinned promotions — 0 new protocols, documentation not compared

Each is published as an `rpc_observed` record (`docs/api/v1/rpc-pinned.json`): runtime bytecode, EIP-1967 slots and the first readable controller of the protocol's primary contract, at the pins above. No documentation parameter is compared, so none counts toward `verifiedCount` or `driftCount`.

| Protocol | Chain | Primary contract | Proxy | Controller |
| :--- | :--- | :--- | :--- | :--- |

## 15. Published RPC-pinned protocols moved to the Sprint 33 pins

- Extra Finance (Base): `0xBB505c54D71E9e599cB8435b4F0cEEc05fC71cbD` (Base) — bytecode keccak256 `0x2bda3204356bb12a5b68e82c0408773da0a9c311b37996552ee4e9e6756623e8`, EIP-1967 slots and controller unchanged at `#59699598`.
- Seamless Protocol (Base): `0x0E02EB705be325407707662C6f6d3466E939f3a0` (Base) — bytecode keccak256 `0x22818496ed85629596372dcbe81fbc48c729489bdf829e198040b0f06fc4f58f`, EIP-1967 slots and controller unchanged at `#59699598`.
- 3F: `0x54F862fa0612A8709F6Dec4A7B39AF015CD4E82E` (Ethereum) — bytecode keccak256 `0x4690b1cca8e819c6cf7d976ae8e296e41138d1a2d722c8d07b3394d431fc226e`, EIP-1967 slots and controller unchanged at `#26452373`.
- Aegis YUSD: `0x4274cD7277C7bb0806Bd5FE84b9aDAE466a8DA0a` (Ethereum) — bytecode keccak256 `0x673a34bc4b7ddbb2aaf2ff848f3fe7734a98331af20f2f0f55bca5dd131c39ff`, EIP-1967 slots and controller unchanged at `#26452373`.
- Aera V3: `0x29722cC9a1cACff4a15914F9bC274B46F3b90B4F` (Ethereum) — bytecode keccak256 `0xf4d329ab04c7cdbab16fe48996f83e05fbbdb9222305402bc9049c842ec5cfe7`, EIP-1967 slots and controller unchanged at `#26452373`.
- Anemoy Capital: `0x8c213ee79581Ff4984583C6a801e5263418C4b86` (Ethereum) — bytecode keccak256 `0x7d02f853cd5ee5a6aa0a08213618a6f3c3d594d4c030be909d0e894b6a37c749`, EIP-1967 slots and controller unchanged at `#26452373`.
- AO Bridge: `0xfE08D40Eee53d64936D3128838867c867602665c` (Ethereum) — bytecode keccak256 `0x53c0835906d5b2eed9f973e77d7c785956ea1d182c80679951ae09c4cfaa13c1`, EIP-1967 slots and controller unchanged at `#26452373`.
- Aster Bridge: `0x604DD02d620633Ae427888d41bfd15e38483736E` (Ethereum) — bytecode keccak256 `0x0959a24babb02d4d6c6ef27aaec9c34e824a2c55d24b13a8b3dae8401138e1c4`, EIP-1967 slots and controller unchanged at `#26452373`.
- AUTOfinance: `0x2218F90A98b0C070676f249EF44834686dAa4285` (Ethereum) — bytecode keccak256 `0x851c7bea863541332656d77df23c217c5013416390dcefce9992f95655446c1e`, EIP-1967 slots and controller unchanged at `#26452373`.
- Avalon Superearn: `0x5c8D0C48810FD37A0A824D074ee290E64f7A8Fa2` (Ethereum) — bytecode keccak256 `0xe5e3693157141608a301682c8c228c0277eac7efc0b98b57f874ca49752b5fd8`, EIP-1967 slots and controller unchanged at `#26452373`.
- BitFi Basis: `0xCdFb58c8C859Cb3F62ebe9Cf2767F9e036C7fb15` (Ethereum) — bytecode keccak256 `0x168f6bb27d4410c24923a1fa9ccad3e18530a1bdaa23935960b410be0aa1409c`, EIP-1967 slots and controller unchanged at `#26452373`.
- Concentrator: `0xb3Ad645dB386D7F6D753B2b9C3F4B853DA6890B8` (Ethereum) — bytecode keccak256 `0xce1d4da3ce85dfe2287a99b988ea0393a3d3c08472adbb065266e798585682f2`, EIP-1967 slots and controller unchanged at `#26452373`.
- Derive V3 Options: `0xB1D1eae60EEA9525032a6DCb4c1CE336a1dE71BE` (Ethereum) — bytecode keccak256 `0x4b19308ff101c086627922584dfdf6fb6f57828ecd7b0d5e84cea7cc36e2ca2b`, EIP-1967 slots and controller unchanged at `#26452373`.
- Frankencoin: `0xDb861830D9Ae2d1fCF99fA0cfd3973de382B0B5b` (Ethereum) — bytecode keccak256 `0x9dacc056e5f2d59b75a9c9ae8a3cd5134abf7bfb675462f50c12ab777603cc62`, EIP-1967 slots and controller unchanged at `#26452373`.
- Grvt Bridge: `0xAD29F2723fcdBcF665F210F25E06f97477e417cF` (Ethereum) — bytecode keccak256 `0x61f4a7aa2e0a3dcc40aa8314f37f612c0d4705c416a2bbe73430f130a25297c5`, EIP-1967 slots and controller unchanged at `#26452373`.
- Hyperlane: `0x6D265C7dD8d76F25155F1a7687C693FDC1220D12` (Ethereum) — bytecode keccak256 `0xa88000255e1f96de07122238840c31fd0b48f520430ff6dd78b7100dfc738358`, EIP-1967 slots and controller unchanged at `#26452373`.
- IDEX V1: `0xB705268213D593B8FD88d3FDEFF93AFF5CbDcfAE` (Ethereum) — bytecode keccak256 `0x41a6bbcc6ebf380d013e5bf81e1f04f14177e26857360fdb5fb0d96ab290b6a3`, EIP-1967 slots and controller unchanged at `#26452373`.
- K3 Capital: `0xdC47953c816531a8CA9E1D461AB53687d48EEA26` (Ethereum) — bytecode keccak256 `0xf44809e3d915cd908b4db54ad7e3de8d0923d8c68119d754ef9566c10573fd5e`, EIP-1967 slots and controller unchanged at `#26452373`.
- Lighter Bridge: `0x232CE3bd40fCd6f80f3d55A522d03f25Df784Ee2` (Ethereum) — bytecode keccak256 `0x509f7c0bd6c3e1d958030033e1e1e3ae1be166bbbefd2e8d8835fa72ba1a4236`, EIP-1967 slots and controller unchanged at `#26452373`.
- Origami Finance: `0x07c5500359161b81eb0DfFF83097d5025D3cF5A2` (Ethereum) — bytecode keccak256 `0x62d6e97082d84feec6a1fb354b9279aa8ceb6b7ffaf88d1bb82e9225bf1553e3`, EIP-1967 slots and controller unchanged at `#26452373`.
- PancakeSwap AMM V3: `0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865` (Ethereum) — bytecode keccak256 `0x8191d3ab1d55d3da9822199f28865415c99566b6f1aee4a4b16713f57930678c`, EIP-1967 slots and controller unchanged at `#26452373`.
- RockawayX: `0x953972ea0C1703c58F09FB6fD2477Fdcf0FEe074` (Ethereum) — bytecode keccak256 `0x864cc9ad53b338b82da1f7cab85ab0b3d5c8861acb422b6fec63cf36234f36a6`, EIP-1967 slots and controller unchanged at `#26452373`.
- Saturn: `0x23238f20b894f29041f48D88eE91131C395Aaa71` (Ethereum) — bytecode keccak256 `0x6d0ce32ba65bd273fcbdc767be5fd8924abd4ce0d6fb5c84ba39c28be05d2457`, EIP-1967 slots and controller unchanged at `#26452373`.
- Sierra Protocol: `0xe1b1252652A2FF0CC3A4214eE73d9FeD1FEa5b4f` (Ethereum) — bytecode keccak256 `0x1151e0ba784b3fe266ae02886e6435603745e3e3b288a9f5ad182737b0faa1ac`, EIP-1967 slots and controller unchanged at `#26452373`.
- Starknet Bridge: `0xCa14007Eff0dB1f8135f4C25B34De49AB0d42766` (Ethereum) — bytecode keccak256 `0x7ef33cd5b6004a6c025dee0df472999ec54227ba2a7ab0b612537ca5219ee275`, EIP-1967 slots and controller unchanged at `#26452373`.
- Team Finance: `0xCC4304A31d09258b0029eA7FE63d032f52e44EFe` (Ethereum) — bytecode keccak256 `0x17404120e429d743f170be02a42dd5018a3d340863ef7c7bf41db1baab1a1cd7`, EIP-1967 slots and controller unchanged at `#26452373`.
- Theo Network thUSD: `0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3` (Ethereum) — bytecode keccak256 `0xc8ff19e35002275bcbf9f8eede7c2030293c871666ff06c9eb19933826d81271`, EIP-1967 slots and controller unchanged at `#26452373`.
- Tornado Cash: `0x77777FeDdddFfC19Ff86DB637967013e6C6A116C` (Ethereum) — bytecode keccak256 `0x7bb3883a4af95ea24983177dbcb682a021f389b77835ed266bfa30bda271c77b`, EIP-1967 slots and controller unchanged at `#26452373`.
- UNCX Network V2: `0xaDB2437e6F65682B85F814fBc12FeC0508A7B1D0` (Ethereum) — bytecode keccak256 `0x9ef6c8d303308ae4c0cfd6466aff6fd25946facfdeb76992707386a34ae5879f`, EIP-1967 slots and controller unchanged at `#26452373`.
- USDT0: `0x6C96dE32CEa08842dcc4058c14d3aaAD7Fa41dee` (Ethereum) — bytecode keccak256 `0xe5e3693157141608a301682c8c228c0277eac7efc0b98b57f874ca49752b5fd8`, EIP-1967 slots and controller unchanged at `#26452373`.
- Veda: `0x5232bc0F5999f8dA604c42E1748A13a170F94A1B` (Ethereum) — bytecode keccak256 `0xf349ba5ac81eb0f8ad05e353e581928b157ebce878db155eaea6f4534cb5fe2b`, EIP-1967 slots and controller unchanged at `#26452373`.
- World Chain Bridge: `0x90BB48fe3310499Db36437dCAE642F721e32d094` (Ethereum) — bytecode keccak256 `0xfa8c9db6c6cab7108dea276f4cd09d575674eb0852c0fa3187e59e98ef977998`, EIP-1967 slots and controller unchanged at `#26452373`.
- xDAI Stake Bridge: `0x0Ae055097C6d159879521C384F1D2123D1f195e6` (Ethereum) — bytecode keccak256 `0xc142222c43ea630db16763d6dd8e619a9cecc3bf121785475841cdc9f94361b7`, EIP-1967 slots and controller unchanged at `#26452373`.
- ZEROBASE CeDeFi: `0xfAB99fCF605fD8f4593EDb70A43bA56542777777` (Ethereum) — bytecode keccak256 `0x5ea0a98719770123cf8cb56ed504a5975019e01868505874dc2fb31b034a7cfe`, EIP-1967 slots and controller unchanged at `#26452373`.
- ADI Bridge: `0x8B1484d57abBE239bB280661377363b03c89CaEa` (Ethereum) — bytecode keccak256 `0x864cc9ad53b338b82da1f7cab85ab0b3d5c8861acb422b6fec63cf36234f36a6`, EIP-1967 slots and controller unchanged at `#26452373`.
- Ankr: `0x8290333ceF9e6D528dD5618Fb97a76f268f3EDD4` (Ethereum) — bytecode keccak256 `0x0c0a59b206d3675604c0d605ecbf7ec2c7deedaee03fd40f9f94e4bd7e954798`, EIP-1967 slots and controller unchanged at `#26452373`.
- Anvil: `0xAEEAa594e7dc112D67b8547fe9767a02c15B5597` (Ethereum) — bytecode keccak256 `0x429a8e131784eb8288d76e76719f82390c239cc6c473298627c6524c61706197`, EIP-1967 slots and controller unchanged at `#26452373`.
- Arkis: `0xEA623eebd9c5bFd56067e36C89Db0C13e6c70ba8` (Ethereum) — bytecode keccak256 `0xddb2c9db76f64c21284e72e3ac43a2e9c263034b5b317504860a5adce96d91e7`, EIP-1967 slots and controller unchanged at `#26452373`.
- Aura: `0xC0c293ce456fF0ED870ADd98a0828Dd4d2903DBF` (Ethereum) — bytecode keccak256 `0x29fa14ed566cfc96628bfb573316782856bc583b0b3079fa524d13a38dd0d58b`, EIP-1967 slots and controller unchanged at `#26452373`.
- Avant avETH: `0x9469470C9878bf3d6d0604831d9A3A366156f7EE` (Ethereum) — bytecode keccak256 `0x9591b0f9a962e55ec9d4ab889638af7d31a3368e23618ee5599a609dcc1159fd`, EIP-1967 slots and controller unchanged at `#26452373`.
- Badger DAO: `0x3472A5A71965499acd81997a54BBA8D852C6E53d` (Ethereum) — bytecode keccak256 `0x2dda0f3a6bee3e5768e41adb77021f8f5653897a1c65a5f106265b17fa2c299b`, EIP-1967 slots and controller unchanged at `#26452373`.
- Blur Bids: `0x5283D291DBCF85356A21bA090E6db59121208b44` (Ethereum) — bytecode keccak256 `0xeb2957414f3daa1495aa331973f631de8ee6c87994fc4a612da20a97f4e14150`, EIP-1967 slots and controller unchanged at `#26452373`.
- Brickken: `0x0A638F07ACc6969abF392bB009f216D22aDEa36d` (Ethereum) — bytecode keccak256 `0xdf740b7eec2ee1e88020370781c03aab1b04dc55a1dc622b48cb7002ce87fb8e`, EIP-1967 slots and controller unchanged at `#26452373`.
- Chamber Vaults: `0xca1207647Ff814039530D7d35df0e1Dd2e91Fa84` (Ethereum) — bytecode keccak256 `0x1154b4431256a941501d558a4d3a3fd001a431840461ac32435cd878b90946ac`, EIP-1967 slots and controller unchanged at `#26452373`.
- Cronos zkEVM Bridge: `0x28Ff2E4dD1B58efEB0fC138602A28D5aE81e44e2` (Ethereum) — bytecode keccak256 `0xee8a105971995661291a9f284262a87abf2381b3cdc93b2c8fbeffe4cd636dd9`, EIP-1967 slots and controller unchanged at `#26452373`.
- D2 Finance: `0x07Dff4087b43c4A759f4Fc69511c26d51929dAF4` (Ethereum) — bytecode keccak256 `0x86b6dc26240e014376e03dac6bdfc333b63e56ee7506e1000786f8c33a6fb8c0`, EIP-1967 slots and controller unchanged at `#26452373`.
- DODO AMM: `0x43Dfc4159D86F3A37A5A4B3D4580b888ad7d4DDd` (Ethereum) — bytecode keccak256 `0xa3ed78c2deb7d2c3197c7f1f83847c7a2e806273099255078f11d84387b70ab9`, EIP-1967 slots and controller unchanged at `#26452373`.
- Drakewell USDdw: `0x2B5895b716311A1eaC8f93fB88C56aF9eC8C1A69` (Ethereum) — bytecode keccak256 `0xbb70cbce5814331e91f8533edb5153fbccaa65f6ab99f5baf5d9d766c4888309`, EIP-1967 slots and controller unchanged at `#26452373`.
- Easedefi.org: `0xEa5eDef1287AfDF9Eb8A46f9773AbFc10820c61c` (Ethereum) — bytecode keccak256 `0x614b8db3fa7d70d7f8369ff9cca21049df4bf56aef08bce338c66e82dfa1e1a1`, EIP-1967 slots and controller unchanged at `#26452373`.
- edgeX Bridge: `0xB0076DE78Dc50581770BBa1D211dDc0aD4F2a241` (Ethereum) — bytecode keccak256 `0xde5d6e9d24143b30c748d881d84f897a424b86c8a931badaa1ca8b4dd7e4051e`, EIP-1967 slots and controller unchanged at `#26452373`.
- Eigenpie: `0x20b70E4A1883b81429533FeD944d7957121c7CAB` (Ethereum) — bytecode keccak256 `0x02f54b576cbf2fd200517ffc5f9cdbd7c08314e9eb8002043e355001fa4e373f`, EIP-1967 slots and controller unchanged at `#26452373`.
- FermiSwap: `0xb1076fE3AB5e28005C7c323Bac5AC06a680d452e` (Ethereum) — bytecode keccak256 `0xba367f88fc2257711f741c9f6c4bca4b20e1030ab06635bbb903b0bf052d2638`, EIP-1967 slots and controller unchanged at `#26452373`.
- GETH: `0x3802c218221390025BCEABBaD5D8C59F40eB74B8` (Ethereum) — bytecode keccak256 `0xb5e0d7b2fb71f8589a2298f1e39888d6f7df1f3cf7338f44ce9f64337a724b1a`, EIP-1967 slots and controller unchanged at `#26452373`.
- Gondi V3: `0xf65B99CE6DC5F6c556172BCC0Ff27D3665a7d9A8` (Ethereum) — bytecode keccak256 `0x5a24688c56b5bd15d41e7fad9201ef8472da0b86cbda8ede7713b58ce6b09600`, EIP-1967 slots and controller unchanged at `#26452373`.
- Hakka Finance: `0x0E29e5AbbB5FD88e28b2d355774e73BD47dE3bcd` (Ethereum) — bytecode keccak256 `0x3cfb96debb564e364f4c21b2f07a940c6fcfc7557c0e33f948af2b2c937ad7c0`, EIP-1967 slots and controller unchanged at `#26452373`.
- Harvest Finance: `0xa0246c9032bC3A600820415aE600c6388619A14D` (Ethereum) — bytecode keccak256 `0x9c1795bb8a1ae198f6f98c74e4c0cebb6726da3b592ccda396ab78ee30c65fed`, EIP-1967 slots and controller unchanged at `#26452373`.
- Hop Protocol: `0xc5102fE9359FD9a28f877a67E36B0F050d81a3CC` (Ethereum) — bytecode keccak256 `0x4e5daef6a4c9a066d1d4f6c3e77a1eaefae7117c725cba2328ddb399d2260fe2`, EIP-1967 slots and controller unchanged at `#26452373`.
- Injective Bridge: `0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30` (Ethereum) — bytecode keccak256 `0x2860075dbbe8adda4739434d6accb0f815f6c16d66c1334920c2dde5cdf67f48`, EIP-1967 slots and controller unchanged at `#26452373`.
- Juicebox V1: `0x3abF2A4f8452cCC2CF7b4C1e4663147600646f66` (Ethereum) — bytecode keccak256 `0xf28bae363907eeebbed68f7f0b0efc447d495263f180b6ff3e161f81f75be328`, EIP-1967 slots and controller unchanged at `#26452373`.
- Ledgity Yield: `0x482dF7483a52496F4C65AB499966dfcdf4DDFDbc` (Ethereum) — bytecode keccak256 `0xe71d9a8dc2039e8ad5f38dc0f95409ec914ee7cba1c413374a11fba65d7941af`, EIP-1967 slots and controller unchanged at `#26452373`.
- Legion: `0xa0BeB0A8C765482c128a2986c063AF5C3171ff2F` (Ethereum) — bytecode keccak256 `0xf7924ec4706f7b92b773d73078c1f3d26580e4954d342f283018d7a713bb6186`, EIP-1967 slots and controller unchanged at `#26452373`.
- Metis Bridge: `0x9E32b13ce7f2E80A01932B42553652E053D6ed8e` (Ethereum) — bytecode keccak256 `0x9a833fe40ae2176ba5d50fbb57f2ad20f4189097772a9180c30bb9114526b55c`, EIP-1967 slots and controller unchanged at `#26452373`.
- Metronome Synth: `0x2Ebd53d035150f328bd754D6DC66B99B0eDB89aa` (Ethereum) — bytecode keccak256 `0xe2a3917cd8f22f7a6d01aedf941b9982b15af8484a9578939a24c93fd7b1fdff`, EIP-1967 slots and controller unchanged at `#26452373`.
- Monolith Market: `0x6D961c9DCF1AD73566822BA4B087892e3839B849` (Ethereum) — bytecode keccak256 `0x67cab37d1c7a97e5bd64e10a5e6283e14f2384165e1ba55ed4f0a51aaf8fcc96`, EIP-1967 slots and controller unchanged at `#26452373`.
- Morph Bridge: `0xDc71366EFFA760804DCFC3EDF87fa2A6f1623304` (Ethereum) — bytecode keccak256 `0x44107d7c70e67e04d35d77455d5755c94d4897196e4ea9a341c1a6d864a6d4d5`, EIP-1967 slots and controller unchanged at `#26452373`.
- Multichain: `0x9Fb9a33956351cf4fa040f65A13b835A3C8764E3` (Ethereum) — bytecode keccak256 `0x6a3d203c440e54090e1d8f2dfdb9aa32e0df4b7dd5bfd02d11889f3bd9534492`, EIP-1967 slots and controller unchanged at `#26452373`.
- Native Credit Pool: `0xe3D41d19564922C9952f692C5Dd0563030f5f2EF` (Ethereum) — bytecode keccak256 `0xde357882f2c0a539e8abef1c3c091bf56874c09a141eef9534dd62372e91e93c`, EIP-1967 slots and controller unchanged at `#26452373`.
- NodeDAO: `0xd7C049CD4ba216679ecC04Eb2767cC5E39812121` (Ethereum) — bytecode keccak256 `0x19d55c6b37ed536e4412158686e2df774d0e754dbb580b5f87923c7049d0ac0a`, EIP-1967 slots and controller unchanged at `#26452373`.
- OpenGDP Shared Security: `0x54e44DbB92dBA848ACe27F44c0CB4268981eF1CC` (Ethereum) — bytecode keccak256 `0xde741c264ec7f60e744da6731a699d17530b431a41d2e2ebe7476abc11261e92`, EIP-1967 slots and controller unchanged at `#26452373`.
- Paradex Bridge: `0xb32E10022FFBeDfE10bc818a1C7e67D9d87e0fa7` (Ethereum) — bytecode keccak256 `0xee8a105971995661291a9f284262a87abf2381b3cdc93b2c8fbeffe4cd636dd9`, EIP-1967 slots and controller unchanged at `#26452373`.
- Piku Finance: `0x2E4039E8E31475d65DC00293C366FDBfBBC02DC3` (Ethereum) — bytecode keccak256 `0x1be95a2ec43076d7ce5cd1d0d5261f9bb409e9022e46cc6495ffd1dd7bcf6f0c`, EIP-1967 slots and controller unchanged at `#26452373`.
- Pirex: `0xc55126051B22eBb829D00368f4B12Bde432de5Da` (Ethereum) — bytecode keccak256 `0x574a98b7bd30da9de3edfb7134b4e9dd5b4bbc011bb85a984aa06dae0e350f53`, EIP-1967 slots and controller unchanged at `#26452373`.
- Ribbon: `0x6123B0049F904d730dB3C36a31167D9d4121fA6B` (Ethereum) — bytecode keccak256 `0x06f86d51347023f4971c0638f8cb71cbd7b4de3b92a825904205dd2486591d59`, EIP-1967 slots and controller unchanged at `#26452373`.
- Ring Few: `0x7D86394139bf1122E82FDF45Bb4e3b038A4464DD` (Ethereum) — bytecode keccak256 `0x5126b02f7eec0470df7780456cdcee61bc47bf7bf574f213674c66393fd50ae9`, EIP-1967 slots and controller unchanged at `#26452373`.
- Royco V2: `0x7cC6fB28eC7b5e7afC3cB3986141797ffc27253C` (Ethereum) — bytecode keccak256 `0x18f95d772587f01e910a390c7b48d767fbfa7726584405e8277da572b72f9386`, EIP-1967 slots and controller unchanged at `#26452373`.
- Stafi: `0xef3A930e1FfFFAcd2fc13434aC81bD278B0ecC8d` (Ethereum) — bytecode keccak256 `0xcfb26d9dee1cbb07d16138dc589dff327bc820f608c7d6142789f9b2d94d9922`, EIP-1967 slots and controller unchanged at `#26452373`.
- StakeStone STONE: `0x1D88713b483A8E45cfF0e5CD7c2e15E5Fab4534d` (Ethereum) — bytecode keccak256 `0x7b5f00e12c193572cdda46010ef6bf30df8c68c1974d9aad61c8935ce091d9ca`, EIP-1967 slots and controller unchanged at `#26452373`.
- Steer Protocol: `0xCEBF1A54A9Ce703FC80967760b5A6cbDb4111099` (Ethereum) — bytecode keccak256 `0x1e71c4a5b01c61a4b1a4afa98257a085e472bfc63a362efa77be9a23e714cdc9`, EIP-1967 slots and controller unchanged at `#26452373`.
- SushiSwap V3: `0xc35DADB65012eC5796536bD9864eD8773aBc74C4` (Ethereum) — bytecode keccak256 `0x2908b9ac88489ac1ed7dbc2d6ff5c0832b56dc8f5408e4992b9c7c6a24bb337a`, EIP-1967 slots and controller unchanged at `#26452373`.
- Symbiosis: `0xd38BB40815d2B0c2d2c866e0c72c5728ffC76dd9` (Ethereum) — bytecode keccak256 `0x145131033c93e676112c82aa230328dfc8dd0ac596f59e4ed90ee5045adcdd20`, EIP-1967 slots and controller unchanged at `#26452373`.
- Synapse Cross Chain Bridge: `0x0f2D719407FdBeFF09D87557AbB7232601FD9F29` (Ethereum) — bytecode keccak256 `0x14b9c77780d7daf560bdab14dea33da9fa0bc59eb71b6a1d230de99b6ee0500f`, EIP-1967 slots and controller unchanged at `#26452373`.
- Syntropia: `0x1b2CB79a4564206f53Ba80b4d780F251b4Ae6765` (Ethereum) — bytecode keccak256 `0xdc8d9306a3726daedf8bb0db4da810ed5af2b6ab034e593737a83531a2e7d327`, EIP-1967 slots and controller unchanged at `#26452373`.
- Tangent Finance: `0x214C8A1023B30032a2Eded109146658C6D6F2781` (Ethereum) — bytecode keccak256 `0xf5dab7b6b40557238eaad60b7369bfb50c9329ff47046216a93497aa14cb9771`, EIP-1967 slots and controller unchanged at `#26452373`.
- UltraYield Vaults: `0x8ECC0B419dfe3AE197BC96f2a03636b5E1BE91db` (Ethereum) — bytecode keccak256 `0xe428fca70a96823c60ffaa430edc8cc501377a4709bdb3a070d024d616d81ff5`, EIP-1967 slots and controller unchanged at `#26452373`.
- Unslashed: `0xE0e05c43c097B0982Db6c9d626c4eb9e95C3b9ce` (Ethereum) — bytecode keccak256 `0x76b55d62d6e6d762eaa121e1cd4d14100f2d08c36d299b970d06a973dc86fb90`, EIP-1967 slots and controller unchanged at `#26452373`.
- Wildcat Protocol: `0xfEB516d9D946dD487A9346F6fee11f40C6945eE4` (Ethereum) — bytecode keccak256 `0x3622afdfc583101952ff6e608d76f9c897d2767297315962d97f8b3a2cc2df56`, EIP-1967 slots and controller unchanged at `#26452373`.
- XSY: `0xBA515304d8153c4b162dC79f867E152DF9c127eb` (Base) — bytecode keccak256 `0xa403fa29cda49311b973967ea91292c75ab23dd093a8444ae680d9099fac817a`, EIP-1967 slots and controller unchanged at `#59699598`.
- YieldFi: `0x19Ebd191f7A24ECE672ba13A302212b5eF7F35cb` (Ethereum) — bytecode keccak256 `0xcb948150f62f6105c4bab1c9fa409ee4a30c35405b1622d203d440a703ece90e`, EIP-1967 slots and controller unchanged at `#26452373`.
- Yuzu Money: `0x224e90591A2d63fb66E677D0561Ea4A6Ad1F098D` (Ethereum) — bytecode keccak256 `0xb516ec422f5c3709db0ba2ff716d5e06daaec61bf753989303aa3679d5163095`, EIP-1967 slots and controller unchanged at `#26452373`.
- Zora Bridge: `0x1111111111166b7FE7bd91427724B487980aFc69` (Base) — bytecode keccak256 `0xd8511363feac51319c3a08c4ad471f451c5c8d137878cbb0e0472fd976421cd5`, EIP-1967 slots and controller unchanged at `#59699598`.
- ZTLN-P: `0xfEd3D6557Dc46A1B25d0A6F666513Cb33835864B` (Ethereum) — bytecode keccak256 `0xf480c2a32f387d87861f5e505e80169f59eb402333618d51f49d70a724388374`, EIP-1967 slots and controller unchanged at `#26452373`.
- Angle: `0x31429d1856aD1377A8A0079410B297e1a9e214c2` (Ethereum) — bytecode keccak256 `0xb2b4462244cc70f518bca0e36112dc4932b72128f6ceeb7408c0ede78cb94a1d`, EIP-1967 slots and controller unchanged at `#26452373`.
- Angstrom: `0x0000000aa232009084Bd71A5797d089AA4Edfad4` (Ethereum) — bytecode keccak256 `0x528182e66a441545ea3ba1dede4e6063f23acd4ada4036c24b9fa2f254bc4ed1`, EIP-1967 slots and controller unchanged at `#26452373`.
- ApeX Pro: `0x52A8845DF664D76C69d2EEa607CD793565aF42B8` (Ethereum) — bytecode keccak256 `0xe223553d1494126fcfef118f62fdf0d99adeb4845469f967f193d468d79aa5a2`, EIP-1967 slots and controller unchanged at `#26452373`.
- Augur: `0x221657776846890989a759BA2973e427DfF5C9bB` (Ethereum) — bytecode keccak256 `0xa75cc1804fa75f619fa67eee93ddf254251f9690bd78af4a2f59e6bf6a195331`, EIP-1967 slots and controller unchanged at `#26452373`.
- Baseline Protocol: `0x9fDbDE76236998Dc2836FE67A9954eDE456A1D63` (Ethereum) — bytecode keccak256 `0xe3a0b45b4ce46850f120cc127182598eed3e806f86c25755fea84623b4573c8d`, EIP-1967 slots and controller unchanged at `#26452373`.
- Blast pre-launch Farm: `0x5F6AE08B8AeB7078cf2F96AFb089D7c9f51DA47d` (Ethereum) — bytecode keccak256 `0x82dee1d830a79106921dc73f0ebb4758243a04f29c5346ba4f82f58b81ffef72`, EIP-1967 slots and controller unchanged at `#26452373`.
- BMX Freestyle: `0x6D63921D8203044f6AbaD8F346d3AEa9A2719dDD` (Base) — bytecode keccak256 `0x4d9be648c5bf39973670d9f8b481d5d0b971e6a2db2deccc6b98cde21c5dd83e`, EIP-1967 slots and controller unchanged at `#59699598`.
- Clipper: `0xd8F1460044925d2D5c723C7054cd9247027415B7` (Ethereum) — bytecode keccak256 `0xe059da78dcedae60d32ef3865b8af77702c451736a2d129fe2e3cf8c8d91b6e0`, EIP-1967 slots and controller unchanged at `#26452373`.
- Convergence Fi: `0xB0Afc8363b8F36E0ccE5D54251e20720FfaeaeE7` (Ethereum) — bytecode keccak256 `0xc88eb359bcda37312f65801074d04313c015d1cef388769f2c9245265653e6fa`, EIP-1967 slots and controller unchanged at `#26452373`.
- CRETH2: `0x2ba592F78dB6436527729929AAf6c908497cB200` (Ethereum) — bytecode keccak256 `0x52b508080c903feaa0b873467c07dde6f8a88f6efc88b4dd898636433e0a42f0`, EIP-1967 slots and controller unchanged at `#26452373`.
- DeFIL: `0x09ce2B746C32528B7d864A1e3979Bd97d2f095AB` (Ethereum) — bytecode keccak256 `0x3b6ce2514862cb6b6d5d37979a693a0d4f7252ce4e5f4f132441aaa1a9c30ad4`, EIP-1967 slots and controller unchanged at `#26452373`.
- DELV Yield: `0x62F161BF3692E4015BefB05A03a94A40f520d1c0` (Ethereum) — bytecode keccak256 `0xf9a3a5f11360d59f975ee3b3a133cea72978503c3940d56d12f7abdb16d42d52`, EIP-1967 slots and controller unchanged at `#26452373`.
- DerivaDEX: `0x3A880652F47bFaa771908C07Dd8673A787dAEd3A` (Ethereum) — bytecode keccak256 `0x90459b94bf726acfb040ffb9f897868235160693e9bc9f2e2aa70d67f7bd6ca2`, EIP-1967 slots and controller unchanged at `#26452373`.
- DexFi Aggregator: `0x4C1a8a04577286Ce58d0723b1a90160F380E550A` (Ethereum) — bytecode keccak256 `0xed42fb03822a5d6d75695946a6eb1eb92cda4bc668f61635fdf710d5de8e83ef`, EIP-1967 slots and controller unchanged at `#26452373`.
- DxSale: `0xF063fE1aB7a291c5d06a86e14730b00BF24cB589` (Ethereum) — bytecode keccak256 `0x08d525afaf352be3b9eeb0eea7d588fcb7ea55e5e52829d107c97ded4fcd32e6`, EIP-1967 slots and controller unchanged at `#26452373`.
- ElfomoFi: `0x64f8bE47A011DF0fAB47319d5De258D18E93f4ef` (Base) — bytecode keccak256 `0x3911795ad7e9d471583ebe7aeb1021703890f7ca55a10b8ee8ca91e55ba70565`, EIP-1967 slots and controller unchanged at `#59699598`.
- Fake World Assets V2: `0xa0Df17B5aC76ABaBA36E1450E2cbCd18A620C845` (Ethereum) — bytecode keccak256 `0xd07b0280e4e25689956cff42290d843739714308e6fbe693017cede05c2c52fd`, EIP-1967 slots and controller unchanged at `#26452373`.
- Flexa: `0xfF20817765cB7f73d4bde2e66e067E58D11095C2` (Ethereum) — bytecode keccak256 `0xa0cfa14c1f8ef49585b024e29601a34bbeb675337a94833b2df167782cebbdf5`, EIP-1967 slots and controller unchanged at `#26452373`.
- FlokiFi Locker: `0xcf0C122c6b73ff809C693DB761e7BaeBe62b6a2E` (Ethereum) — bytecode keccak256 `0x62f6a27beef672562e73fb0f3dcc4efb0d16b16cf4daeddb5c9cd8e17f58d6f8`, EIP-1967 slots and controller unchanged at `#26452373`.
- friend.tech V1: `0x0bD4887f7D41B35CD75DFF9FfeE2856106f86670` (Base) — bytecode keccak256 `0x358aa3e7ee950f58863c601550d37477d36b1dd76c1ce15342ac6649acf9caa8`, EIP-1967 slots and controller unchanged at `#59699598`.
- Gamma: `0x6BeA7CFEF803D1e3d5f7C0103f7ded065644e197` (Ethereum) — bytecode keccak256 `0x35be488840b51a9788e28175818703d2764395e5e22fd5ebfda92d575b2020aa`, EIP-1967 slots and controller unchanged at `#26452373`.
- GLIF: `0xAeD7C2eD7Bb84396AfCB55fF72c8F8E87FFb68f3` (Base) — bytecode keccak256 `0x749f3b692400fa750c12cd525331ae1eda236ca25ac3033b739b8ff04abf3c1e`, EIP-1967 slots and controller unchanged at `#59699598`.
- Gro: `0x3Ec8798B81485A254928B70CDA1cf0A2BB0B74D7` (Ethereum) — bytecode keccak256 `0x3ab25059e82d964ea1bcb4653362e7f690d2a3256437df181fe0e7f62f0b0bb2`, EIP-1967 slots and controller unchanged at `#26452373`.
- Hegic: `0x584bC13c7D411c00c01A62e8019472dE68768430` (Ethereum) — bytecode keccak256 `0xdec18c0951427319cc61da2d7548a2a4f32d2ad07de25868f528e2753602bb61`, EIP-1967 slots and controller unchanged at `#26452373`.
- ICHI: `0x111111517e4929D3dcbdfa7CCe55d30d4B6BC4d6` (Ethereum) — bytecode keccak256 `0x33c88004b04cc3a91c6c2907e8399ce7ff2acd319c1476c49e299026878e98ad`, EIP-1967 slots and controller unchanged at `#26452373`.
- Interest Protocol: `0x2A54bA2964C8Cd459Dc568853F79813a60761B58` (Ethereum) — bytecode keccak256 `0x6273eddb91b574c664e91f6e38caf04527f5172f452b419a25f858c6a6f16265`, EIP-1967 slots and controller unchanged at `#26452373`.
- Kine Finance: `0xbB7D94a423f4978545ecf73161f0678e8AfD1a92` (Ethereum) — bytecode keccak256 `0x1240a7f0370dbc9f26bbc60420e4e1034b2008607b7fb39f0948d4fa31870d95`, EIP-1967 slots and controller unchanged at `#26452373`.
- King Protocol: `0x8F08B70456eb22f6109F57b8fafE862ED28E6040` (Ethereum) — bytecode keccak256 `0xf8c4135b5cd64765ef0eab5ea7559c47552279ee03eca8241f981cc597f5c777`, EIP-1967 slots and controller unchanged at `#26452373`.
- LandX Finance: `0x08A1C30BBB26425c1031ee9E43FA0B9960742539` (Ethereum) — bytecode keccak256 `0xb612e6bd581e8e2b7889e1ce264314531cea3c5503db7e8520c0f550d6ce4f96`, EIP-1967 slots and controller unchanged at `#26452373`.
- Lazy: `0xd53B68fB4eb907c3c1E348CD7d7bEDE34f763805` (Ethereum) — bytecode keccak256 `0x1fc427a9bc54ebdc7a32d32b519126d28cd2ef37ce526cca3a51e2ca9cee7150`, EIP-1967 slots and controller unchanged at `#26452373`.
- LendFlare: `0xB620Be8a1949AA9532e6a3510132864EF9Bc3F82` (Ethereum) — bytecode keccak256 `0xf62bd5d649a541bbef0e8aecef588c949b55a8103eccdb0c8bcd07fdf803dd69`, EIP-1967 slots and controller unchanged at `#26452373`.
- LUSD ChickenBonds: `0xB9D7DdDca9a4AC480991865EfEf82E01273F79C3` (Ethereum) — bytecode keccak256 `0x6640959990cc7cea35e6eb879bdbc5b131a512820345b4adc887c97c6d6396d9`, EIP-1967 slots and controller unchanged at `#26452373`.
- MortgageFi: `0x1bE87D273d47C3832Ab7853812E9A995A4DE9EEA` (Base) — bytecode keccak256 `0x185cf047b846a3513a3de1ebeba7c30fa0ccbe85f838a616ebccd8363e3b5973`, EIP-1967 slots and controller unchanged at `#59699598`.
- Nami: `0x0100000002935Dce071f4AFA607b961575672b4C` (Ethereum) — bytecode keccak256 `0x96259673a3d3296a129cce355d4b938bf40d7162e379c966116a22e224828023`, EIP-1967 slots and controller unchanged at `#26452373`.
- NFTX: `0x87d73E916D7057945c9BcD8cdd94e42A6F47f776` (Ethereum) — bytecode keccak256 `0x2dda0f3a6bee3e5768e41adb77021f8f5653897a1c65a5f106265b17fa2c299b`, EIP-1967 slots and controller unchanged at `#26452373`.
- Nucleus: `0x52E4d8989fa8b3E1C06696e7b16DEf5d7707A0d1` (Ethereum) — bytecode keccak256 `0xb2e2580f6bee3b141fb4c2cfca77558a0ac1bf0c77dc0ec41c2d6e85f18d7ab7`, EIP-1967 slots and controller unchanged at `#26452373`.
- Outcome Finance: `0x0b8de441B26E36f461b2748919ed71f50593A67b` (Ethereum) — bytecode keccak256 `0xa10d4eb25d8cec9207b66506981e4af2f9900f06311949d2fa7beed6f8a198f9`, EIP-1967 slots and controller unchanged at `#26452373`.
- Overtime: `0x90cE5720c17587D28E4Af120ae2d313B3BAD1722` (Ethereum) — bytecode keccak256 `0x2a2b42ae5730efe6b72757400473ea6427d7d8640d35cd3c04fbdf2f2d6d7925`, EIP-1967 slots and controller unchanged at `#26452373`.
- Punks Terminal: `0x000000000000A6fA31F5fC51c1640aAc76866750` (Ethereum) — bytecode keccak256 `0x5b8a9e982541c73da95a997139f197f575910a6037f34cb1e04d8567c019faf1`, EIP-1967 slots and controller unchanged at `#26452373`.
- Quickswap V4: `0xC5396866754799B9720125B104AE01d935Ab9C7b` (Base) — bytecode keccak256 `0x7822b724506fdf3f88058e04b74d0c754a8e09f5db1964fdc2ceb9977967b153`, EIP-1967 slots and controller unchanged at `#59699598`.
- Reflexer: `0x6243d8CEA23066d098a15582d81a598b4e8391F4` (Ethereum) — bytecode keccak256 `0x91b7369444e24b10e4d84904b059edc29aab786ca7c8061b5a501321c4a3cb5f`, EIP-1967 slots and controller unchanged at `#26452373`.
- Saffron Vaults: `0xb753428af26E81097e7fD17f40c88aaA3E04902c` (Ethereum) — bytecode keccak256 `0xd9f71ccdd211bba48b76ead02c0de837b0a34f07e693e367a32eff3860357a36`, EIP-1967 slots and controller unchanged at `#26452373`.
- SATO: `0x0000f07d2B5F1Ddf3244b8780F972f306EFd2888` (Ethereum) — bytecode keccak256 `0x0cb886792429db1b1f330dedc575160e709e659159b0b9477858b3965102cf42`, EIP-1967 slots and controller unchanged at `#26452373`.
- SMARDEX USDN: `0x656cB8C6d154Aad29d8771384089be5B5141f01a` (Ethereum) — bytecode keccak256 `0xfd1a8f7693ff598e9b2e993e7d30c57c12d773b948753d9edfd6761e8daeb4de`, EIP-1967 slots and controller unchanged at `#26452373`.
- SOFA.org: `0x57B96D4aF698605563A4653D882635da59Bf11AF` (Ethereum) — bytecode keccak256 `0x88056442963f4b4ba95bbdf2e92e6f4e89bfb34f82171e8837ecd7d4ffd1cc78`, EIP-1967 slots and controller unchanged at `#26452373`.
- Sommelier: `0xa670d7237398238DE01267472C6f13e5B8010FD1` (Ethereum) — bytecode keccak256 `0xe32339c16126933800abbc98e317903e5d17d0c0940813c63d51458593ef1d36`, EIP-1967 slots and controller unchanged at `#26452373`.
- Sport.fun: `0x16EE7ecAc70d1028E7712751E2Ee6BA808a7dd92` (Base) — bytecode keccak256 `0xe45965360fef796d68818c710054832bb0b9e09c72dc7783f6ebb633197bcddf`, EIP-1967 slots and controller unchanged at `#59699598`.
- StableHodl: `0x109D3042a3c682F94107b3818e93b3aDE2A47544` (Ethereum) — bytecode keccak256 `0xee8a105971995661291a9f284262a87abf2381b3cdc93b2c8fbeffe4cd636dd9`, EIP-1967 slots and controller unchanged at `#26452373`.
- Supernova CL: `0x44B7fBd4D87149eFa5347c451E74B9FD18E89c55` (Ethereum) — bytecode keccak256 `0x502e5730b9eb2b3afa6c7b8453c61c842dccac09c1a4cf4147ebb151e5184f3e`, EIP-1967 slots and controller unchanged at `#26452373`.
- Taiko Bridge: `0x10dea67478c5F8C5E2D90e5E9B26dBe60c54d800` (Ethereum) — bytecode keccak256 `0x26e751b9fd68f5207c6d2b35f2871bc22c1b05e9d20368c10257dc04ca67f46e`, EIP-1967 slots and controller unchanged at `#26452373`.
- TokenWorks: `0xA1a196b5BE89Be04a2c1dc71643689CE013c22e5` (Ethereum) — bytecode keccak256 `0xdbe822093f1c9e3d148657d5122e03958449aea91b271863b5cd42c5be206a86`, EIP-1967 slots and controller unchanged at `#26452373`.
- Unitus: `0x3B6564b5DA73A41d3A66e6558a98FD0e9E1e77ad` (Ethereum) — bytecode keccak256 `0xaf9c9da08abecebd75f6ed4d1aa7e423b553ce9ca8d2fd83c025e684b72f6534`, EIP-1967 slots and controller unchanged at `#26452373`.
- Wan Bridge: `0xfCeAAaEB8D564a9D0e71Ef36f027b9D162bC334e` (Ethereum) — bytecode keccak256 `0xd0cf0742bd64c1e960f924480430b6614def86d82463b5cb878836ff12274abe`, EIP-1967 slots and controller unchanged at `#26452373`.
- WOOFi Earn: `0x4691937a7508860F876c9c0a2a617E7d9E945D4B` (Ethereum) — bytecode keccak256 `0xee7b6a4b8c8f92fbca7423f575329f7935dd6c6e3b744490b702a238a41dd4e0`, EIP-1967 slots and controller unchanged at `#26452373`.
