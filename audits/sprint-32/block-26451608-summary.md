# Sprint 32 Protocol Commitment Summary — Block `26451608`

- **Ethereum Mainnet pin**: `26451608` (`0x1939e98`), canonical block hash `0x0266af5bcad519d93b3be78e41b76a62985e22fbe4feef043ac3225f6f217a17`, timestamp `2026-11-19 20:45:11 UTC` (`1795121111`); the `finalized` head, both endpoints returning the same number and hash
- **Base Mainnet pin**: `59653624` (`0x38e3df8`), canonical block hash `0x984d5efdee77a9e8ab0d5b8eb5bba2a230cdcadc268f35f6c77f4a629b13a305`, timestamp `2026-11-19 20:45:00 UTC` (`1795121100`); the `finalized` head, both endpoints returning the same number and hash
- **Scanner**: Pacta by Fractal Neurons (Pacta Protocol Commitments DRI), bulk harvester v2.1. Read-only `eth_call` / `eth_getStorageAt` / `eth_getCode` batched through Multicall3 at the pinned block, on two independent RPCs per chain with identical block hashes: `ethereum-rpc.publicnode.com` + `rpc.mevblocker.io` (Ethereum), `base-rpc.publicnode.com` + `mainnet.base.org` (Base). Documentation: HTTP-200 first-party snapshots named by their SHA-256; every quote below is an exact substring of its snapshot's text and every value is re-derived from the pinned reads by the validator (no model output is trusted). The merged bounty records' values were re-read by their own check (`bounty-check-s32.json`) at the same block numbers and hashes through `gateway.tenderly.co` + `eth.drpc.org` (Ethereum), `base-rpc.publicnode.com` + `mainnet.base.org` (Base).
- **Result**: `16` records for `16` protocols (`1` new; published protocols with a new record: Cap, Chainlink CCIP, Kelp DAO (rsETH), BendDAO APE Staking, Bio Protocol, dYdX V3, Ekubo, Hashport, InceptionLRT (Isolated Restaking), Lista Lending, Metric V1, MorpheusAI, Pickle, Superform Core v2 (Base), Tori Finance) — `11` aligned baselines, `0` protective deltas, `5` parameter deltas. `verifiedCount = 11`. `driftCount = 5`, the same convention as Sprints 1–31 and `PactaSentinelGuard` (`driftCount != 0` means drift).
- **RPC-pinned promotions (not attested)**: `0` further new protocols are published as RPC-pinned control-plane records at the same pins (listed below); the `158` RPC-pinned protocols already published move to these pins with every stated fact unchanged. They carry no Base EAS UID. `12` published RPC-pinned protocols are documentation-compared for the first time and become Base-EAS protocols here (BendDAO APE Staking, Bio Protocol, dYdX V3, Ekubo, Hashport, InceptionLRT (Isolated Restaking), Lista Lending, Metric V1, MorpheusAI, Pickle, Superform Core v2 (Base), Tori Finance); their RPC-pinned records are retired.
- **On-chain anchoring**: to be attested on Base Mainnet EAS (`0x4200000000000000000000000000000000000021`) under canonical schema `0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83` (`chainId = 1`, the Ethereum pin above); Base reads are taken at the Base pin.

## 1. Circle Gateway — GatewayWallet: EOA owner (UUPS upgrade, withdrawal delay) and EOA pauser over withdrawals

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Circle GatewayWallet** | `0x77777777Dcc4d5A8B6E418Fd04D8997ef11000eE` | `owner()` | Circle GatewayWallet 0x77777777Dcc4d5A8B6E418Fd04D8997ef11000eE (Ethereum; the address the Gateway contract-addresses page lists): UUPS EIP-1967 proxy, implementation 0xF7a6D9D7Df917c072ac8987A820c58aA27A0e798 (GatewayWallet, verified source). owner() = 0x2A6A86466F181721ec8ff946967b56f1AA4758c5 and pauser() = 0x9812d5F0a0832d9A0a78a1ba728fACd87bC35b19, both accounts with no code (externally owned) at this pin; denylister() = 0x7359fD9aA258992eb4B6d9572c6f6c74Cf719a94, also without code. In the verified source _authorizeUpgrade, updateWithdrawalDelay and updatePauser are onlyOwner, pause() is onlyPauser, and both initiateWithdrawal() and withdraw() are whenNotPaused; no timelock sits in either path. withdrawalDelay() = 50,400 blocks; paused() = false. This record does not allege any misuse of these powers. (Ethereum `#26451608`) |

Classification: **parameter delta** (1 record).
- 'Users have full control of their deposited assets. Funds can only move with their signature, and withdrawals are trustless.' (www.circle.com/gateway) (snapshot sha256 `2d3b509a2aba33c05e707490ef776e5d126925dd9612dc27dd553f882914a413`, `fa6bf978651c61758db332f9356ab7120034c1ab0b941f6793140f3e5b499acf`)

## 2. Cap — Timelock operation 0x740e26ef: executed since #26,425,374; getMinDelay() still 86,400 s

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Cap TimelockController** | `0xD8236031d8279d82E615aF2BFab5FC0127A329ab` | `isOperationDone(bytes32)` | Cap TimelockController 0xD8236031d8279d82E615aF2BFab5FC0127A329ab (Ethereum): isOperationDone(0x740e26ef00f5ac693593d62327a7b40ea59d2a88711c151fcc835bc0190b20ea) = true and isOperationPending = false at this pin; pending at Pacta's published pin #26,425,374 (record cap-1d-timelock-min-delay-s20). getMinDelay() = 86,400 s at both pins. (Ethereum `#26451608`) |

Classification: **aligned baseline** (1 record).
- 'The Timelock enforces a mandatory waiting period between when an operation is proposed and when it can be executed, giving participants time to react to parameter changes.' (docs.cap.app/concepts/access-controls) (snapshot sha256 `b89e2090b5b79b286dbc45587c345692fbde3f5b444160243da7e5bc93e2f8d9`)

## 3. Chainlink CCIP — RBACTimelock operation 0x67cdd78a: scheduled and executed since #26,433,001

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **CCIP RBACTimelock (Ethereum)** | `0x44835bBBA9D40DEDa9b64858095EcFB2693c9449` | `isOperationDone(bytes32)` | Chainlink CCIP RBACTimelock 0x44835bBBA9D40DEDa9b64858095EcFB2693c9449 (Ethereum): isOperationDone(0x67cdd78af74492609eb87e0b8b8c6afb4e4fe86d95b4c11ec5c0d4116350d829) = true at this pin; isOperation = false at Pacta's published pin #26,433,001 (record chainlink-ccip-timelock-proposers-s24). ERC20LockBox 0xEd3fc513F5888BD65E868ba77D25E8799FfFa18e (no code at #26,433,001) owner() = 0x44835bBBA9D40DEDa9b64858095EcFB2693c9449 at this pin. getMinDelay() = 10,800 s at both pins. (Ethereum `#26451608`) |

Classification: **aligned baseline** (1 record).
- 'This repo contains a set of contracts used for administering Chainlink contracts' (github.com/smartcontractkit/ccip-owner-contracts) (snapshot sha256 `0aa94b7609736b42afb1b3e8ea5b3076e1b7e8c2c3c7cf7ebacc06d8b5a7281b`)

## 4. Kelp DAO (rsETH) — RSETH_OFTAdapter owner(): a 6-of-11 Safe; another address at #26,406,106

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Kelp RSETH_OFTAdapter (Ethereum)** | `0x85d456B2DfF1fd8245387C0BfB64Dfb700e98Ef3` | `owner()` | Kelp RSETH_OFTAdapter 0x85d456B2DfF1fd8245387C0BfB64Dfb700e98Ef3 (Ethereum): owner() = 0xb3696a817D01C8623E66D156B6798291fa10a46d, a 6-of-11 Safe, at this pin and at Pacta's Sprint 30 pin #26,449,594; owner() = 0xCbcdd778AA25476F203814214dD3E9b9c46829A1 at the Sprint 14 pin #26,406,106 (record kelp-rseth-proxyadmin-10d-timelock-s14): the transfer falls between #26,406,106 and #26,449,594, not after #26,449,594. (Ethereum `#26451608`) |

Classification: **aligned baseline** (1 record).
- '| Ethereum RSETH_OFTAdapter    | 0x85d456B2DfF1fd8245387C0BfB64Dfb700e98Ef3     |' (raw.githubusercontent.com/Kelp-DAO/LRT-rsETH/main/README.md) (snapshot sha256 `a64f44a6b7f7a019abb7ce32c3c4b9d24fd478b73243c00d42e1620141e729a8`)

## 5. BendDAO APE Staking — BEND ProxyAdmin owner: BendDAO Timelock 7D, getMinDelay() 86,400 s

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **BendDAO Timelock 7D (owner of the Incentive ProxyAdmin)** | `0x4e4C314E2391A58775be6a15d7A05419ba7D2B6e` | `getMinDelay()` | BEND token 0x0d02755a5700414B26FF040e1dE35D337DF56218 (Ethereum): EIP-1967 proxy, implementation 0x02863C14603C3b157379999F567DDECE151e9153, admin slot = ProxyAdmin 0x859f6e05410893fe64BC84d92BdA773fF798cf66 (the docs' 'Incentive' Proxy Admin). ProxyAdmin owner() = 0x4e4C314E2391A58775be6a15d7A05419ba7D2B6e, the docs' 'BendDAO Timelock 7D', an OpenZeppelin TimelockController (verified source): getMinDelay() = 86,400 s at this pin; the security page lists it at 7 days. (Ethereum `#26451608`) |

Classification: **parameter delta** (1 record).
- '| Incentive | 7 Days Timelock | 0x859f6e05410893fe64BC84d92BdA773fF798cf66 |' (raw.githubusercontent.com/BendDAO/bend-gitbook-portal/HEAD/risk/security-and-audits.md) (snapshot sha256 `eb064c6538fde22fe17f2bf996606959713b8138999e7c1701707c3b73ac78fb`)

## 6. Bio Protocol — BIO mint(): MINTER_ROLE held by a 5-of-11 Safe and a bridge manager; no cap

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **BIO token (BioToken)** | `0xcb1592591996765Ec0eFc1f92599A19767ee5ffA` | `getRoleMember(bytes32,uint256)` | BIO token 0xcb1592591996765Ec0eFc1f92599A19767ee5ffA (Ethereum, not a proxy; BioToken, verified source): mint(to, amount) is onlyRole(MINTER_ROLE) and the token has no supply cap. getRoleMemberCount(MINTER_ROLE) = 2: 0xd9C6Ee1547Fd6d48F8872dD866473893Bbe8A1Ab, a 5-of-11 Safe, and 0x1783E7d1F498321D7E15044d769621E1beDc7F4C, an ERC-1967 proxy to a Wormhole NttManager (implementation 0x2bBaCb406d043D93997344F28a74A25069f3e9E3) that mints for inbound bridge transfers. The same Safe is the only DEFAULT_ADMIN_ROLE member, the admin of MINTER_ROLE. totalSupply() = 2,914,432,394 BIO. The page says new BIO requires deploying a new token contract; the current contract can mint. (Ethereum `#26451608`) |

Classification: **parameter delta** (1 record).
- 'The supply is uncapped, meaning new BIO can be minted for future protocol or network growth. This requires deploying a new token contract to replace the current BIO token.' (docs.bio.xyz/bio/introduction/bio-token/basic-token-information.md) (snapshot sha256 `09d986ced5fcdc1cc099d355e19d478f0aa3c00e4a06f7132fb2352072b0ef2e`)

## 7. dYdX V3 — ethDYDX owner: the Short Timelock Executor, getDelay() 172,800 s

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **dYdX Short Timelock Executor** | `0x64c7d40c07EFAbec2AafdC243bF59eaF2195c6dc` | `getDelay()` | ethDYDX 0x92D6C1e31e14520e676a687F0a93788B716BEff5 (Ethereum) owner() = 0x64c7d40c07EFAbec2AafdC243bF59eaF2195c6dc, an Executor (verified source): getDelay() = 172,800 s, MINIMUM_DELAY() = 86,400 s, MAXIMUM_DELAY() = 604,800 s, GRACE_PERIOD() = 604,800 s, the documented Short Timelock Executor column (the Long Timelock column is 7 / 5 / 21 days). (Ethereum `#26451608`) |

Classification: **aligned baseline** (1 record).
- 'Parameter Description Short Timelock Executor Merkle-Pauser Executor Long Timelock Executor Starkware Executor Timelock Delay* After a proposal passes and is queued, delay before the proposal is executed 2 days 0 days 7 days 2-9 days' (docs.dydx.community/dydx-governance/voting-and-governance/dip-proposal-lifecycle); 'Owner Can mint ethDYDX tokens after mint restriction Short Timelock' (docs.dydx.community/dydx-governance/voting-and-governance/governance-parameters) (snapshot sha256 `af73200d2ebb13f85548d0d71f1ba1539b73112f4e5b696d253d547a6e934da5`, `2b364ae407ed6f4cc77956045d51e5c8fff97cce6695ae9c0b645bdfd52ed64d`)

## 8. Ekubo — Core: not a proxy; owner() is the StarknetOwnerProxy driven by the Starknet Governor

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Ekubo Core (EVM V2)** | `0xe0e0e08A6A4b9Dc7bD67BCB7aadE5cF48157d444` | `owner()` | Ekubo Core 0xe0e0e08A6A4b9Dc7bD67BCB7aadE5cF48157d444 (Ethereum): EIP-1967 implementation, admin and beacon slots all empty; verified source (runtime exact match) has no delegatecall and no upgrade function, and its only onlyOwner functions are withdrawProtocolFees and the ownership transfers. owner() = 0x1E0EF4162e42C9bF820c307218c4E41cCcA6E9CC, StarknetOwnerProxy: immutable l2Owner() = 0x053499f7aa2706395060fe72d00388803fb2dcc111429891ad7b2d9dcea29acd (the Ekubo DAO Governor on Starknet), l2MessageBridge() = 0xc662c410C0ECf747543f5bA90660f6ABeBD9C8c4; it executes only calls consumed as L2 messages from that Governor. The docs mark the V2 EVM deployment deprecated. (Ethereum `#26451608`) |

Classification: **aligned baseline** (1 record).
- 'All smart contracts on Ethereum are immutable' (docs.ekubo.org/reference/contracts/evm-v2) (snapshot sha256 `24e4acb4f06fdc77becaaadc7439e409b8d0d7bcbcb942739656554a8489f8f4`)

## 9. Hashport — Diamond (EIP-2535): diamondCut owner-only; owner is a 5-of-9 Safe

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Hashport Router (Diamond)** | `0x367e59b559283C8506207d75B0c5D8C66c4Cd4B7` | `owner()` | Hashport Router diamond 0x367e59b559283C8506207d75B0c5D8C66c4Cd4B7 (Ethereum, EIP-2535): facetAddress(diamondCut 0x1f931c1c) = 0xe79c9Bb508f00ab7B03cf3043929639e86626EF9, the DiamondCutFacet of Deployment.md; in its verified source diamondCut() calls LibDiamond.enforceIsContractOwner() before adding, replacing or removing facets. owner() = 0x10AB2d9C085c816f43ccB0FB1b27d024224E36f1, a 5-of-9 Safe. (Ethereum `#26451608`) |

Classification: **aligned baseline** (1 record).
- 'Smart Contracts use [EIP-2535](https://eips.ethereum.org/EIPS/eip-2535).' (raw.githubusercontent.com/LimeChain/hashport-contracts/main/README.md); '`Hashport (Diamond)`: `0x367e59b559283C8506207d75B0c5D8C66c4Cd4B7`' (raw.githubusercontent.com/LimeChain/hashport-contracts/main/Deployment.md) (snapshot sha256 `54468cd3d2237bfffbad5ae6b53eae2ae88fe681ffaad939ce954fc4d96ad844`, `a810622abe16b404ca44134050d8a3f349b7b8ef4f7c98c5e320eb37d4fc2b7a`)

## 10. InceptionLRT (Isolated Restaking) — Vault upgrades: ProxyAdmins owned by InceptionTimeLock, getMinDelay() 259,200 s

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **InceptionTimeLock (owner of the vault ProxyAdmins)** | `0x650bD9Dee50E3eE15cbb49749ff6ABcf55A8FB1e` | `getMinDelay()` | InceptionTimeLock 0x650bD9Dee50E3eE15cbb49749ff6ABcf55A8FB1e (Ethereum), a TimelockController: getMinDelay() = 259,200 s. InstEthVault 0x814CC6B8fd2555845541FB843f37418b05977d8d (implementation 0x9Bb0F64c5A5e9120f55cde6B15683FF11Abc0eD4): ProxyAdmin 0xB81e55e7Ee6B286aF6abFEa4eFad83f7BA4D1f1e, owner() = the timelock; inLBTCVault_S 0xD496417a50DB34279631e0aF459493Cf9685F529 (implementation 0xb83ad67814BeD3478BB4239a5961391d836fCe4d): ProxyAdmin 0x177bFf0AD93B8132012F05081A10a0e574fa5F97, owner() = the timelock. The README lists InstEthVault under deprecated LSTs. Both vaults' own owner() is 0x8e6C8799B542E507bfDDCA1a424867e885D96e79, a 3-of-5 Safe, acting without the timelock on owner-only vault settings. (Ethereum `#26451608`) |

Classification: **aligned baseline** (1 record).
- 'The contracts are upgradeable and guarded with the [TimeLockController]' (raw.githubusercontent.com/inceptionlrt/smart-contracts/HEAD/projects/vaults/README.md) (snapshot sha256 `e45954842306bcde398b93dd8dcb1be96623473eb58d639cb6f1b314d7d2f370`)

## 11. Lista Lending — Moolah upgrade authority: sole DEFAULT_ADMIN_ROLE member is the Admin TimeLock, 86,400 s

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Lista Moolah (Ethereum)** | `0xf820fB4680712CD7263a0D3D024D5b5aEA82Fd70` | `getRoleMember(bytes32,uint256)` | Lista Moolah 0xf820fB4680712CD7263a0D3D024D5b5aEA82Fd70 (Ethereum): EIP-1967 proxy, implementation 0xD7C983093065E0169e955c44ab8370110231D3cf; in its verified source _authorizeUpgrade is onlyRole(DEFAULT_ADMIN_ROLE). getRoleMemberCount(DEFAULT_ADMIN_ROLE) = 1 and its member is 0xa18ae79AEDA3e711E0CD64cfe1Cd06402d400D61, the 'Admin TimeLock' of the Ethereum contract table: a TimelockController (verified source) with getMinDelay() = 86,400 s. (Ethereum `#26451608`) |

Classification: **aligned baseline** (1 record).
- 'Upgrade authority sits behind an OpenZeppelin `TimelockController`' (docs.bsc.lista.org/for-developer/lista-lending/contract-reference.md) (snapshot sha256 `358238b787b3daec6035ac9b7ebb5d3a709a951a8d7aeaef76d4b3b1fe088225`)

## 12. Metric V1 — Protocol fee share: setPoolProtocolFee by the owner, a 3-of-5 Safe, with no delay

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **MetricOmmPoolFactory** | `0x2a53833cc95548cf52c7b159110e22D3a9018f32` | `owner()` | MetricOmmPoolFactory 0x2a53833cc95548cf52c7b159110e22D3a9018f32 (Ethereum, not a proxy; verified source): setPoolProtocolFee and setPoolProtocolFeeBatch are requiresAuth, and Auth.isAuthorized admits owner() unconditionally (or a caller the authority 0x032a22958EE9277eCce675E04e8302B85224a1B0 allows); the new fee applies in the same call. owner() = 0xa082C768B1C40f5e980b75959D85cF245AFF0FAE, a 3-of-5 Safe. (Ethereum `#26451608`) |

Classification: **aligned baseline** (1 record).
- 'The curator and Metric can each change their share of the spread at any time and with no timelock' (docs.metric.xyz/use-metric/fees.md); 'The core, periphery and extension contracts below are deployed at the same addresses on every chain in this table.' (docs.metric.xyz/reference/supported-chains-and-deployments.md) (snapshot sha256 `fc8ebe9c6fda3420eb0b5f77839a6c7cf80f406c4320612ccee6e4ec88152239`, `7939380c54464d734af41a6166d36adec803978e31f87465bb73ff9e5e2d43f6`)

## 13. MorpheusAI — Ethereum multisig: 5-of-9, owner of the DepositPool

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Morpheus Ethereum multisig (Safe)** | `0x1FE04BC15Cf2c5A2d41a0b3a96725596676eBa1E` | `getThreshold()` | Morpheus Ethereum Safe 0x1FE04BC15Cf2c5A2d41a0b3a96725596676eBa1E (Ethereum): getThreshold() = 5 of 9 owners. DepositPool 0x47176B2Af9885dC6C4575d4eFd63895f7Aaa4790 (EIP-1967 proxy, implementation 0xdB10dAEF167eA2233Ba6811457dD24D676FbD670) owner() = this Safe. (Ethereum `#26451608`) |

Classification: **aligned baseline** (1 record).
- 'This setup requires 5 out of 9 key holders to sign transactions' (gitbook.mor.org/smart-contracts/multisig.md) (snapshot sha256 `ba1bd6149af97714d2058519b0653e7ad02d49a9468e7adfd2aecae4fd1d477d`)

## 14. Pickle — MasterChef admin: owner is a 2-of-6 Safe, the documented 24 h timelock is not in the path

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Pickle MasterChef** | `0xbD17B1ce622d73bD438b9E658acA5996dc394b0d` | `owner()` | Pickle MasterChef 0xbD17B1ce622d73bD438b9E658acA5996dc394b0d (Ethereum, not a proxy): its verified source makes add, set, setPicklePerBlock, setBonusEndBlock, setDevFundDivRate and the PICKLE mint path onlyOwner; MasterChef is owner() of the PICKLE token 0x429881672B9AE42b8EbA0E26cD9C73711b891Ca5. MasterChef owner() = 0x9d074E37d408542FD38be78848e8814AFB38db17, a 2-of-6 Safe (the page calls it a 2/5 multisig). The 24-hour Timelock the page links, 0x0040E05CE9A5fc9C0aBF89889f7b60c2fC278416 (delay() = 86,400 s, admin() = the same Safe), does not own MasterChef. (Ethereum `#26451608`) |

Classification: **parameter delta** (1 record).
- 'All key admin functions on the MasterChef contract, which controls the emission of PICKLEs to the Farms are controlled by a 24 hour timelock contract' (docs.pickle.finance/security/audits-and-timelock/timelocks-and-multisig) (snapshot sha256 `a7ed08696620889466d50dd713ab47dd095efce3c3ed1629cd1432a72028d189`)

## 15. Superform Core v2 (Base) — Primary manager change: 7-day timelock (604,800 s); interval changes 3 days

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Superform SuperVaultAggregator (Base)** | `0x10AC0b33e1C4501CF3ec1cB1AE51ebfdbd2d4698` | `UPKEEP_WITHDRAWAL_TIMELOCK()` | Superform SuperVaultAggregator 0x10AC0b33e1C4501CF3ec1cB1AE51ebfdbd2d4698 (Base, not a proxy; Sourcify-verified, runtime match): the primary-manager change proposal sets effectiveTime = block.timestamp + _MANAGER_CHANGE_TIMELOCK (7 days) and the min-update-interval proposal + _PARAMETER_CHANGE_TIMELOCK (3 days); the runtime code read at this pin holds the 604,800 s and 259,200 s constants once each. UPKEEP_WITHDRAWAL_TIMELOCK() = 86,400 s (the page's 24-hour upkeep withdrawal). SuperGovernor 0xB5396ef2bF8CA360cEB4166b77AFb2bed20e74d4 (same deployment page) holds its own 7-day TIMELOCK on fee changes. (Base `#59653624`) |

Classification: **aligned baseline** (1 record).
- '| Primary strategist updates | 7 days |' (docs.superform.xyz/security.md); 'These addresses are the same on both Ethereum and Base.' (docs.superform.xyz/deployment-addresses.md) (snapshot sha256 `fcc2da294a9bb02d80b4af043bd5aff76e4ed335083463f740b3455915e4f084`, `652bb98f9e2a4cfd97a4cdab956501ab77898072a40e4d82cbacc3ab6c73e4c2`)

## 16. Tori Finance — trUSD TIMELOCK_ADMIN_ROLE: a second ToriTimelock, not the documented timelock

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Tori trUSD** | `0xd0580192E98eA6CEB9c7b6191Ed2E27560911697` | `hasRole(bytes32,address)` | Tori trUSD 0xd0580192E98eA6CEB9c7b6191Ed2E27560911697 (Ethereum, EIP-1967 proxy, implementation 0xb1d133fE29255EB4Ac9B05d647d49cd7F05ff631): hasRole(TIMELOCK_ADMIN_ROLE 0x5f58e3a2316349923ce3780f8d587db2d72378aed66a8261c916544fa6846ca5, 0xcd3c66e73abF927EAAF1238aEB5F251b4f2f667b) = true and hasRole(TIMELOCK_ADMIN_ROLE, 0xA952453E39F77108Ee37C1b92de593F1C59A6ef4) = false at this pin; the reverse at Pacta's published pin #26,448,221 (record tori-finance-control-plane). 0xA952453E39F77108Ee37C1b92de593F1C59A6ef4 is the timelock the roles page names; 0xcd3c66e73abF927EAAF1238aEB5F251b4f2f667b is a second ToriTimelock (verified source; renounceRole disabled). Both have getMinDelay() = 86,400 s and the 3-of-5 Safe 0x0C6Bbfd2d5666d44bf28580eDEec0263692C8316 holds PROPOSER_ROLE on both: the delay is unchanged, but trUSD upgrades are now queued on a timelock the documentation does not name. (Ethereum `#26451608`) |

Classification: **parameter delta** (1 record).
- 'It holds the Timelock Admin role on the core contracts' (docs.tori.finance/security/roles.md) (snapshot sha256 `c103ebeafcddea4cc71afc2222bd48573ed1d1d8547ccff14b7088f974810c0c`)

## 17. RPC-pinned promotions — 0 new protocols, documentation not compared

Each is published as an `rpc_observed` record (`docs/api/v1/rpc-pinned.json`): runtime bytecode, EIP-1967 slots and the first readable controller of the protocol's primary contract, at the pins above. No documentation parameter is compared, so none counts toward `verifiedCount` or `driftCount`.

| Protocol | Chain | Primary contract | Proxy | Controller |
| :--- | :--- | :--- | :--- | :--- |

## 18. Published RPC-pinned protocols moved to the Sprint 32 pins

- Extra Finance (Base): `0xBB505c54D71E9e599cB8435b4F0cEEc05fC71cbD` (Base) — bytecode keccak256 `0x2bda3204356bb12a5b68e82c0408773da0a9c311b37996552ee4e9e6756623e8`, EIP-1967 slots and controller unchanged at `#59653624`.
- Seamless Protocol (Base): `0x0E02EB705be325407707662C6f6d3466E939f3a0` (Base) — bytecode keccak256 `0x22818496ed85629596372dcbe81fbc48c729489bdf829e198040b0f06fc4f58f`, EIP-1967 slots and controller unchanged at `#59653624`.
- 3F: `0x54F862fa0612A8709F6Dec4A7B39AF015CD4E82E` (Ethereum) — bytecode keccak256 `0x4690b1cca8e819c6cf7d976ae8e296e41138d1a2d722c8d07b3394d431fc226e`, EIP-1967 slots and controller unchanged at `#26451608`.
- Aegis YUSD: `0x4274cD7277C7bb0806Bd5FE84b9aDAE466a8DA0a` (Ethereum) — bytecode keccak256 `0x673a34bc4b7ddbb2aaf2ff848f3fe7734a98331af20f2f0f55bca5dd131c39ff`, EIP-1967 slots and controller unchanged at `#26451608`.
- Aera V3: `0x29722cC9a1cACff4a15914F9bC274B46F3b90B4F` (Ethereum) — bytecode keccak256 `0xf4d329ab04c7cdbab16fe48996f83e05fbbdb9222305402bc9049c842ec5cfe7`, EIP-1967 slots and controller unchanged at `#26451608`.
- Anemoy Capital: `0x8c213ee79581Ff4984583C6a801e5263418C4b86` (Ethereum) — bytecode keccak256 `0x7d02f853cd5ee5a6aa0a08213618a6f3c3d594d4c030be909d0e894b6a37c749`, EIP-1967 slots and controller unchanged at `#26451608`.
- AO Bridge: `0xfE08D40Eee53d64936D3128838867c867602665c` (Ethereum) — bytecode keccak256 `0x53c0835906d5b2eed9f973e77d7c785956ea1d182c80679951ae09c4cfaa13c1`, EIP-1967 slots and controller unchanged at `#26451608`.
- Aster Bridge: `0x604DD02d620633Ae427888d41bfd15e38483736E` (Ethereum) — bytecode keccak256 `0x0959a24babb02d4d6c6ef27aaec9c34e824a2c55d24b13a8b3dae8401138e1c4`, EIP-1967 slots and controller unchanged at `#26451608`.
- AUTOfinance: `0x2218F90A98b0C070676f249EF44834686dAa4285` (Ethereum) — bytecode keccak256 `0x851c7bea863541332656d77df23c217c5013416390dcefce9992f95655446c1e`, EIP-1967 slots and controller unchanged at `#26451608`.
- Avalon Superearn: `0x5c8D0C48810FD37A0A824D074ee290E64f7A8Fa2` (Ethereum) — bytecode keccak256 `0xe5e3693157141608a301682c8c228c0277eac7efc0b98b57f874ca49752b5fd8`, EIP-1967 slots and controller unchanged at `#26451608`.
- BitFi Basis: `0xCdFb58c8C859Cb3F62ebe9Cf2767F9e036C7fb15` (Ethereum) — bytecode keccak256 `0x168f6bb27d4410c24923a1fa9ccad3e18530a1bdaa23935960b410be0aa1409c`, EIP-1967 slots and controller unchanged at `#26451608`.
- Concentrator: `0xb3Ad645dB386D7F6D753B2b9C3F4B853DA6890B8` (Ethereum) — bytecode keccak256 `0xce1d4da3ce85dfe2287a99b988ea0393a3d3c08472adbb065266e798585682f2`, EIP-1967 slots and controller unchanged at `#26451608`.
- Derive V3 Options: `0xB1D1eae60EEA9525032a6DCb4c1CE336a1dE71BE` (Ethereum) — bytecode keccak256 `0x4b19308ff101c086627922584dfdf6fb6f57828ecd7b0d5e84cea7cc36e2ca2b`, EIP-1967 slots and controller unchanged at `#26451608`.
- Frankencoin: `0xDb861830D9Ae2d1fCF99fA0cfd3973de382B0B5b` (Ethereum) — bytecode keccak256 `0x9dacc056e5f2d59b75a9c9ae8a3cd5134abf7bfb675462f50c12ab777603cc62`, EIP-1967 slots and controller unchanged at `#26451608`.
- Grvt Bridge: `0xAD29F2723fcdBcF665F210F25E06f97477e417cF` (Ethereum) — bytecode keccak256 `0x61f4a7aa2e0a3dcc40aa8314f37f612c0d4705c416a2bbe73430f130a25297c5`, EIP-1967 slots and controller unchanged at `#26451608`.
- Hyperlane: `0x6D265C7dD8d76F25155F1a7687C693FDC1220D12` (Ethereum) — bytecode keccak256 `0xa88000255e1f96de07122238840c31fd0b48f520430ff6dd78b7100dfc738358`, EIP-1967 slots and controller unchanged at `#26451608`.
- IDEX V1: `0xB705268213D593B8FD88d3FDEFF93AFF5CbDcfAE` (Ethereum) — bytecode keccak256 `0x41a6bbcc6ebf380d013e5bf81e1f04f14177e26857360fdb5fb0d96ab290b6a3`, EIP-1967 slots and controller unchanged at `#26451608`.
- K3 Capital: `0xdC47953c816531a8CA9E1D461AB53687d48EEA26` (Ethereum) — bytecode keccak256 `0xf44809e3d915cd908b4db54ad7e3de8d0923d8c68119d754ef9566c10573fd5e`, EIP-1967 slots and controller unchanged at `#26451608`.
- Lighter Bridge: `0x232CE3bd40fCd6f80f3d55A522d03f25Df784Ee2` (Ethereum) — bytecode keccak256 `0x509f7c0bd6c3e1d958030033e1e1e3ae1be166bbbefd2e8d8835fa72ba1a4236`, EIP-1967 slots and controller unchanged at `#26451608`.
- Origami Finance: `0x07c5500359161b81eb0DfFF83097d5025D3cF5A2` (Ethereum) — bytecode keccak256 `0x62d6e97082d84feec6a1fb354b9279aa8ceb6b7ffaf88d1bb82e9225bf1553e3`, EIP-1967 slots and controller unchanged at `#26451608`.
- PancakeSwap AMM V3: `0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865` (Ethereum) — bytecode keccak256 `0x8191d3ab1d55d3da9822199f28865415c99566b6f1aee4a4b16713f57930678c`, EIP-1967 slots and controller unchanged at `#26451608`.
- RockawayX: `0x953972ea0C1703c58F09FB6fD2477Fdcf0FEe074` (Ethereum) — bytecode keccak256 `0x864cc9ad53b338b82da1f7cab85ab0b3d5c8861acb422b6fec63cf36234f36a6`, EIP-1967 slots and controller unchanged at `#26451608`.
- Saturn: `0x23238f20b894f29041f48D88eE91131C395Aaa71` (Ethereum) — bytecode keccak256 `0x6d0ce32ba65bd273fcbdc767be5fd8924abd4ce0d6fb5c84ba39c28be05d2457`, EIP-1967 slots and controller unchanged at `#26451608`.
- Sierra Protocol: `0xe1b1252652A2FF0CC3A4214eE73d9FeD1FEa5b4f` (Ethereum) — bytecode keccak256 `0x1151e0ba784b3fe266ae02886e6435603745e3e3b288a9f5ad182737b0faa1ac`, EIP-1967 slots and controller unchanged at `#26451608`.
- Starknet Bridge: `0xCa14007Eff0dB1f8135f4C25B34De49AB0d42766` (Ethereum) — bytecode keccak256 `0x7ef33cd5b6004a6c025dee0df472999ec54227ba2a7ab0b612537ca5219ee275`, EIP-1967 slots and controller unchanged at `#26451608`.
- Team Finance: `0xCC4304A31d09258b0029eA7FE63d032f52e44EFe` (Ethereum) — bytecode keccak256 `0x17404120e429d743f170be02a42dd5018a3d340863ef7c7bf41db1baab1a1cd7`, EIP-1967 slots and controller unchanged at `#26451608`.
- Theo Network thUSD: `0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3` (Ethereum) — bytecode keccak256 `0xc8ff19e35002275bcbf9f8eede7c2030293c871666ff06c9eb19933826d81271`, EIP-1967 slots and controller unchanged at `#26451608`.
- Tornado Cash: `0x77777FeDdddFfC19Ff86DB637967013e6C6A116C` (Ethereum) — bytecode keccak256 `0x7bb3883a4af95ea24983177dbcb682a021f389b77835ed266bfa30bda271c77b`, EIP-1967 slots and controller unchanged at `#26451608`.
- UNCX Network V2: `0xaDB2437e6F65682B85F814fBc12FeC0508A7B1D0` (Ethereum) — bytecode keccak256 `0x9ef6c8d303308ae4c0cfd6466aff6fd25946facfdeb76992707386a34ae5879f`, EIP-1967 slots and controller unchanged at `#26451608`.
- USDT0: `0x6C96dE32CEa08842dcc4058c14d3aaAD7Fa41dee` (Ethereum) — bytecode keccak256 `0xe5e3693157141608a301682c8c228c0277eac7efc0b98b57f874ca49752b5fd8`, EIP-1967 slots and controller unchanged at `#26451608`.
- Veda: `0x5232bc0F5999f8dA604c42E1748A13a170F94A1B` (Ethereum) — bytecode keccak256 `0xf349ba5ac81eb0f8ad05e353e581928b157ebce878db155eaea6f4534cb5fe2b`, EIP-1967 slots and controller unchanged at `#26451608`.
- World Chain Bridge: `0x90BB48fe3310499Db36437dCAE642F721e32d094` (Ethereum) — bytecode keccak256 `0xfa8c9db6c6cab7108dea276f4cd09d575674eb0852c0fa3187e59e98ef977998`, EIP-1967 slots and controller unchanged at `#26451608`.
- xDAI Stake Bridge: `0x0Ae055097C6d159879521C384F1D2123D1f195e6` (Ethereum) — bytecode keccak256 `0xc142222c43ea630db16763d6dd8e619a9cecc3bf121785475841cdc9f94361b7`, EIP-1967 slots and controller unchanged at `#26451608`.
- Yield Basis: `0x01791F726B4103694969820be083196cC7c045fF` (Ethereum) — bytecode keccak256 `0xb6dd52f54a35ee897ad6edc361c7dd1ce400f92031dc4b536514bf984f327777`, EIP-1967 slots and controller unchanged at `#26451608`.
- Zama: `0xA12CC123ba206d4031D1c7f6223D1C2Ec249f4f3` (Ethereum) — bytecode keccak256 `0xf172c8c96f8ba07e22f43c9bd9f1d3b96d1dbae326c61b388b4fbd7b517f9123`, EIP-1967 slots and controller unchanged at `#26451608`.
- ZEROBASE CeDeFi: `0xfAB99fCF605fD8f4593EDb70A43bA56542777777` (Ethereum) — bytecode keccak256 `0x5ea0a98719770123cf8cb56ed504a5975019e01868505874dc2fb31b034a7cfe`, EIP-1967 slots and controller unchanged at `#26451608`.
- ADI Bridge: `0x8B1484d57abBE239bB280661377363b03c89CaEa` (Ethereum) — bytecode keccak256 `0x864cc9ad53b338b82da1f7cab85ab0b3d5c8861acb422b6fec63cf36234f36a6`, EIP-1967 slots and controller unchanged at `#26451608`.
- Ankr: `0x8290333ceF9e6D528dD5618Fb97a76f268f3EDD4` (Ethereum) — bytecode keccak256 `0x0c0a59b206d3675604c0d605ecbf7ec2c7deedaee03fd40f9f94e4bd7e954798`, EIP-1967 slots and controller unchanged at `#26451608`.
- Anvil: `0xAEEAa594e7dc112D67b8547fe9767a02c15B5597` (Ethereum) — bytecode keccak256 `0x429a8e131784eb8288d76e76719f82390c239cc6c473298627c6524c61706197`, EIP-1967 slots and controller unchanged at `#26451608`.
- Arkis: `0xEA623eebd9c5bFd56067e36C89Db0C13e6c70ba8` (Ethereum) — bytecode keccak256 `0xddb2c9db76f64c21284e72e3ac43a2e9c263034b5b317504860a5adce96d91e7`, EIP-1967 slots and controller unchanged at `#26451608`.
- Aura: `0xC0c293ce456fF0ED870ADd98a0828Dd4d2903DBF` (Ethereum) — bytecode keccak256 `0x29fa14ed566cfc96628bfb573316782856bc583b0b3079fa524d13a38dd0d58b`, EIP-1967 slots and controller unchanged at `#26451608`.
- Avant avETH: `0x9469470C9878bf3d6d0604831d9A3A366156f7EE` (Ethereum) — bytecode keccak256 `0x9591b0f9a962e55ec9d4ab889638af7d31a3368e23618ee5599a609dcc1159fd`, EIP-1967 slots and controller unchanged at `#26451608`.
- Badger DAO: `0x3472A5A71965499acd81997a54BBA8D852C6E53d` (Ethereum) — bytecode keccak256 `0x2dda0f3a6bee3e5768e41adb77021f8f5653897a1c65a5f106265b17fa2c299b`, EIP-1967 slots and controller unchanged at `#26451608`.
- Blur Bids: `0x5283D291DBCF85356A21bA090E6db59121208b44` (Ethereum) — bytecode keccak256 `0xeb2957414f3daa1495aa331973f631de8ee6c87994fc4a612da20a97f4e14150`, EIP-1967 slots and controller unchanged at `#26451608`.
- Brickken: `0x0A638F07ACc6969abF392bB009f216D22aDEa36d` (Ethereum) — bytecode keccak256 `0xdf740b7eec2ee1e88020370781c03aab1b04dc55a1dc622b48cb7002ce87fb8e`, EIP-1967 slots and controller unchanged at `#26451608`.
- cBridge: `0x4F9254C83EB525f9FCf346490bbb3ed28a81C667` (Ethereum) — bytecode keccak256 `0x2f20f33e040f6be6f03b13a42e4c0b28a9834690ddfbf919a9a49b95007aadd3`, EIP-1967 slots and controller unchanged at `#26451608`.
- Chamber Vaults: `0xca1207647Ff814039530D7d35df0e1Dd2e91Fa84` (Ethereum) — bytecode keccak256 `0x1154b4431256a941501d558a4d3a3fd001a431840461ac32435cd878b90946ac`, EIP-1967 slots and controller unchanged at `#26451608`.
- Cronos zkEVM Bridge: `0x28Ff2E4dD1B58efEB0fC138602A28D5aE81e44e2` (Ethereum) — bytecode keccak256 `0xee8a105971995661291a9f284262a87abf2381b3cdc93b2c8fbeffe4cd636dd9`, EIP-1967 slots and controller unchanged at `#26451608`.
- cVault Finance: `0x62359Ed7505Efc61FF1D56fEF82158CcaffA23D7` (Ethereum) — bytecode keccak256 `0x35d8cb7adaa6c80bfac8896682d5aeb4d367bb2c199f42e1732957b245219caf`, EIP-1967 slots and controller unchanged at `#26451608`.
- D2 Finance: `0x07Dff4087b43c4A759f4Fc69511c26d51929dAF4` (Ethereum) — bytecode keccak256 `0x86b6dc26240e014376e03dac6bdfc333b63e56ee7506e1000786f8c33a6fb8c0`, EIP-1967 slots and controller unchanged at `#26451608`.
- DODO AMM: `0x43Dfc4159D86F3A37A5A4B3D4580b888ad7d4DDd` (Ethereum) — bytecode keccak256 `0xa3ed78c2deb7d2c3197c7f1f83847c7a2e806273099255078f11d84387b70ab9`, EIP-1967 slots and controller unchanged at `#26451608`.
- Drakewell USDdw: `0x2B5895b716311A1eaC8f93fB88C56aF9eC8C1A69` (Ethereum) — bytecode keccak256 `0xbb70cbce5814331e91f8533edb5153fbccaa65f6ab99f5baf5d9d766c4888309`, EIP-1967 slots and controller unchanged at `#26451608`.
- Easedefi.org: `0xEa5eDef1287AfDF9Eb8A46f9773AbFc10820c61c` (Ethereum) — bytecode keccak256 `0x614b8db3fa7d70d7f8369ff9cca21049df4bf56aef08bce338c66e82dfa1e1a1`, EIP-1967 slots and controller unchanged at `#26451608`.
- edgeX Bridge: `0xB0076DE78Dc50581770BBa1D211dDc0aD4F2a241` (Ethereum) — bytecode keccak256 `0xde5d6e9d24143b30c748d881d84f897a424b86c8a931badaa1ca8b4dd7e4051e`, EIP-1967 slots and controller unchanged at `#26451608`.
- Eigenpie: `0x20b70E4A1883b81429533FeD944d7957121c7CAB` (Ethereum) — bytecode keccak256 `0x02f54b576cbf2fd200517ffc5f9cdbd7c08314e9eb8002043e355001fa4e373f`, EIP-1967 slots and controller unchanged at `#26451608`.
- FermiSwap: `0xb1076fE3AB5e28005C7c323Bac5AC06a680d452e` (Ethereum) — bytecode keccak256 `0xba367f88fc2257711f741c9f6c4bca4b20e1030ab06635bbb903b0bf052d2638`, EIP-1967 slots and controller unchanged at `#26451608`.
- GETH: `0x3802c218221390025BCEABBaD5D8C59F40eB74B8` (Ethereum) — bytecode keccak256 `0xb5e0d7b2fb71f8589a2298f1e39888d6f7df1f3cf7338f44ce9f64337a724b1a`, EIP-1967 slots and controller unchanged at `#26451608`.
- Gondi V3: `0xf65B99CE6DC5F6c556172BCC0Ff27D3665a7d9A8` (Ethereum) — bytecode keccak256 `0x5a24688c56b5bd15d41e7fad9201ef8472da0b86cbda8ede7713b58ce6b09600`, EIP-1967 slots and controller unchanged at `#26451608`.
- Hakka Finance: `0x0E29e5AbbB5FD88e28b2d355774e73BD47dE3bcd` (Ethereum) — bytecode keccak256 `0x3cfb96debb564e364f4c21b2f07a940c6fcfc7557c0e33f948af2b2c937ad7c0`, EIP-1967 slots and controller unchanged at `#26451608`.
- Harvest Finance: `0xa0246c9032bC3A600820415aE600c6388619A14D` (Ethereum) — bytecode keccak256 `0x9c1795bb8a1ae198f6f98c74e4c0cebb6726da3b592ccda396ab78ee30c65fed`, EIP-1967 slots and controller unchanged at `#26451608`.
- Hop Protocol: `0xc5102fE9359FD9a28f877a67E36B0F050d81a3CC` (Ethereum) — bytecode keccak256 `0x4e5daef6a4c9a066d1d4f6c3e77a1eaefae7117c725cba2328ddb399d2260fe2`, EIP-1967 slots and controller unchanged at `#26451608`.
- Index Coop: `0x0954906da0Bf32d5479e25f46056d22f08464cab` (Ethereum) — bytecode keccak256 `0x72b69cf0962b8043d955eb54b5ec4dcdefed60b1c8ecd2581003bdd4e916559e`, EIP-1967 slots and controller unchanged at `#26451608`.
- Injective Bridge: `0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30` (Ethereum) — bytecode keccak256 `0x2860075dbbe8adda4739434d6accb0f815f6c16d66c1334920c2dde5cdf67f48`, EIP-1967 slots and controller unchanged at `#26451608`.
- Juicebox V1: `0x3abF2A4f8452cCC2CF7b4C1e4663147600646f66` (Ethereum) — bytecode keccak256 `0xf28bae363907eeebbed68f7f0b0efc447d495263f180b6ff3e161f81f75be328`, EIP-1967 slots and controller unchanged at `#26451608`.
- Ledgity Yield: `0x482dF7483a52496F4C65AB499966dfcdf4DDFDbc` (Ethereum) — bytecode keccak256 `0xe71d9a8dc2039e8ad5f38dc0f95409ec914ee7cba1c413374a11fba65d7941af`, EIP-1967 slots and controller unchanged at `#26451608`.
- Legion: `0xa0BeB0A8C765482c128a2986c063AF5C3171ff2F` (Ethereum) — bytecode keccak256 `0xf7924ec4706f7b92b773d73078c1f3d26580e4954d342f283018d7a713bb6186`, EIP-1967 slots and controller unchanged at `#26451608`.
- Metis Bridge: `0x9E32b13ce7f2E80A01932B42553652E053D6ed8e` (Ethereum) — bytecode keccak256 `0x9a833fe40ae2176ba5d50fbb57f2ad20f4189097772a9180c30bb9114526b55c`, EIP-1967 slots and controller unchanged at `#26451608`.
- Metronome Synth: `0x2Ebd53d035150f328bd754D6DC66B99B0eDB89aa` (Ethereum) — bytecode keccak256 `0xe2a3917cd8f22f7a6d01aedf941b9982b15af8484a9578939a24c93fd7b1fdff`, EIP-1967 slots and controller unchanged at `#26451608`.
- Monolith Market: `0x6D961c9DCF1AD73566822BA4B087892e3839B849` (Ethereum) — bytecode keccak256 `0x67cab37d1c7a97e5bd64e10a5e6283e14f2384165e1ba55ed4f0a51aaf8fcc96`, EIP-1967 slots and controller unchanged at `#26451608`.
- Morph Bridge: `0xDc71366EFFA760804DCFC3EDF87fa2A6f1623304` (Ethereum) — bytecode keccak256 `0x44107d7c70e67e04d35d77455d5755c94d4897196e4ea9a341c1a6d864a6d4d5`, EIP-1967 slots and controller unchanged at `#26451608`.
- Multichain: `0x9Fb9a33956351cf4fa040f65A13b835A3C8764E3` (Ethereum) — bytecode keccak256 `0x6a3d203c440e54090e1d8f2dfdb9aa32e0df4b7dd5bfd02d11889f3bd9534492`, EIP-1967 slots and controller unchanged at `#26451608`.
- Native Credit Pool: `0xe3D41d19564922C9952f692C5Dd0563030f5f2EF` (Ethereum) — bytecode keccak256 `0xde357882f2c0a539e8abef1c3c091bf56874c09a141eef9534dd62372e91e93c`, EIP-1967 slots and controller unchanged at `#26451608`.
- NodeDAO: `0xd7C049CD4ba216679ecC04Eb2767cC5E39812121` (Ethereum) — bytecode keccak256 `0x19d55c6b37ed536e4412158686e2df774d0e754dbb580b5f87923c7049d0ac0a`, EIP-1967 slots and controller unchanged at `#26451608`.
- OpenGDP Shared Security: `0x54e44DbB92dBA848ACe27F44c0CB4268981eF1CC` (Ethereum) — bytecode keccak256 `0xde741c264ec7f60e744da6731a699d17530b431a41d2e2ebe7476abc11261e92`, EIP-1967 slots and controller unchanged at `#26451608`.
- Orderly Bridge: `0xABD4C63d2616A5201454168269031355f4764337` (Ethereum) — bytecode keccak256 `0xb3151f817a0cbf213614631b397dd981aa4c3cd2c95a20a5ddf7f9ebdcbbff1c`, EIP-1967 slots and controller unchanged at `#26451608`.
- Paradex Bridge: `0xb32E10022FFBeDfE10bc818a1C7e67D9d87e0fa7` (Ethereum) — bytecode keccak256 `0xee8a105971995661291a9f284262a87abf2381b3cdc93b2c8fbeffe4cd636dd9`, EIP-1967 slots and controller unchanged at `#26451608`.
- Piku Finance: `0x2E4039E8E31475d65DC00293C366FDBfBBC02DC3` (Ethereum) — bytecode keccak256 `0x1be95a2ec43076d7ce5cd1d0d5261f9bb409e9022e46cc6495ffd1dd7bcf6f0c`, EIP-1967 slots and controller unchanged at `#26451608`.
- Pirex: `0xc55126051B22eBb829D00368f4B12Bde432de5Da` (Ethereum) — bytecode keccak256 `0x574a98b7bd30da9de3edfb7134b4e9dd5b4bbc011bb85a984aa06dae0e350f53`, EIP-1967 slots and controller unchanged at `#26451608`.
- PoolTogether V3: `0x0cEC1A9154Ff802e7934Fc916Ed7Ca50bDE6844e` (Ethereum) — bytecode keccak256 `0x308fc5e8970ed67ffebcc8dafff6333492ace6d3282ba6ef3b1092959a2da25c`, EIP-1967 slots and controller unchanged at `#26451608`.
- Ribbon: `0x6123B0049F904d730dB3C36a31167D9d4121fA6B` (Ethereum) — bytecode keccak256 `0x06f86d51347023f4971c0638f8cb71cbd7b4de3b92a825904205dd2486591d59`, EIP-1967 slots and controller unchanged at `#26451608`.
- Ring Few: `0x7D86394139bf1122E82FDF45Bb4e3b038A4464DD` (Ethereum) — bytecode keccak256 `0x5126b02f7eec0470df7780456cdcee61bc47bf7bf574f213674c66393fd50ae9`, EIP-1967 slots and controller unchanged at `#26451608`.
- Royco V2: `0x7cC6fB28eC7b5e7afC3cB3986141797ffc27253C` (Ethereum) — bytecode keccak256 `0x18f95d772587f01e910a390c7b48d767fbfa7726584405e8277da572b72f9386`, EIP-1967 slots and controller unchanged at `#26451608`.
- SoSoValue Basis: `0x624e2e7fDc8903165F64891672267AB0FCB98831` (Base) — bytecode keccak256 `0x48ac29a5246889375862706cb6369924947b6cf20bf05b904b04324c8536506a`, EIP-1967 slots and controller unchanged at `#59653624`.
- Stafi: `0xef3A930e1FfFFAcd2fc13434aC81bD278B0ecC8d` (Ethereum) — bytecode keccak256 `0xcfb26d9dee1cbb07d16138dc589dff327bc820f608c7d6142789f9b2d94d9922`, EIP-1967 slots and controller unchanged at `#26451608`.
- StakeStone STONE: `0x1D88713b483A8E45cfF0e5CD7c2e15E5Fab4534d` (Ethereum) — bytecode keccak256 `0x7b5f00e12c193572cdda46010ef6bf30df8c68c1974d9aad61c8935ce091d9ca`, EIP-1967 slots and controller unchanged at `#26451608`.
- Steer Protocol: `0xCEBF1A54A9Ce703FC80967760b5A6cbDb4111099` (Ethereum) — bytecode keccak256 `0x1e71c4a5b01c61a4b1a4afa98257a085e472bfc63a362efa77be9a23e714cdc9`, EIP-1967 slots and controller unchanged at `#26451608`.
- SushiSwap V3: `0xc35DADB65012eC5796536bD9864eD8773aBc74C4` (Ethereum) — bytecode keccak256 `0x2908b9ac88489ac1ed7dbc2d6ff5c0832b56dc8f5408e4992b9c7c6a24bb337a`, EIP-1967 slots and controller unchanged at `#26451608`.
- Symbiosis: `0xd38BB40815d2B0c2d2c866e0c72c5728ffC76dd9` (Ethereum) — bytecode keccak256 `0x145131033c93e676112c82aa230328dfc8dd0ac596f59e4ed90ee5045adcdd20`, EIP-1967 slots and controller unchanged at `#26451608`.
- Synapse Cross Chain Bridge: `0x0f2D719407FdBeFF09D87557AbB7232601FD9F29` (Ethereum) — bytecode keccak256 `0x14b9c77780d7daf560bdab14dea33da9fa0bc59eb71b6a1d230de99b6ee0500f`, EIP-1967 slots and controller unchanged at `#26451608`.
- Syntropia: `0x1b2CB79a4564206f53Ba80b4d780F251b4Ae6765` (Ethereum) — bytecode keccak256 `0xdc8d9306a3726daedf8bb0db4da810ed5af2b6ab034e593737a83531a2e7d327`, EIP-1967 slots and controller unchanged at `#26451608`.
- Tangent Finance: `0x214C8A1023B30032a2Eded109146658C6D6F2781` (Ethereum) — bytecode keccak256 `0xf5dab7b6b40557238eaad60b7369bfb50c9329ff47046216a93497aa14cb9771`, EIP-1967 slots and controller unchanged at `#26451608`.
- The Idols: `0x9416bA76e88D873050A06e5956A3EBF10386b863` (Ethereum) — bytecode keccak256 `0x1fc5a38d54c637a235d4a0fd7c57ec4ae5c3c148ec7a038d9715f89a1330cdce`, EIP-1967 slots and controller unchanged at `#26451608`.
- UltraYield Vaults: `0x8ECC0B419dfe3AE197BC96f2a03636b5E1BE91db` (Ethereum) — bytecode keccak256 `0xe428fca70a96823c60ffaa430edc8cc501377a4709bdb3a070d024d616d81ff5`, EIP-1967 slots and controller unchanged at `#26451608`.
- Unslashed: `0xE0e05c43c097B0982Db6c9d626c4eb9e95C3b9ce` (Ethereum) — bytecode keccak256 `0x76b55d62d6e6d762eaa121e1cd4d14100f2d08c36d299b970d06a973dc86fb90`, EIP-1967 slots and controller unchanged at `#26451608`.
- Wildcat Protocol: `0xfEB516d9D946dD487A9346F6fee11f40C6945eE4` (Ethereum) — bytecode keccak256 `0x3622afdfc583101952ff6e608d76f9c897d2767297315962d97f8b3a2cc2df56`, EIP-1967 slots and controller unchanged at `#26451608`.
- XSY: `0xBA515304d8153c4b162dC79f867E152DF9c127eb` (Base) — bytecode keccak256 `0xa403fa29cda49311b973967ea91292c75ab23dd093a8444ae680d9099fac817a`, EIP-1967 slots and controller unchanged at `#59653624`.
- YieldFi: `0x19Ebd191f7A24ECE672ba13A302212b5eF7F35cb` (Ethereum) — bytecode keccak256 `0xcb948150f62f6105c4bab1c9fa409ee4a30c35405b1622d203d440a703ece90e`, EIP-1967 slots and controller unchanged at `#26451608`.
- Yuzu Money: `0x224e90591A2d63fb66E677D0561Ea4A6Ad1F098D` (Ethereum) — bytecode keccak256 `0xb516ec422f5c3709db0ba2ff716d5e06daaec61bf753989303aa3679d5163095`, EIP-1967 slots and controller unchanged at `#26451608`.
- Zora Bridge: `0x1111111111166b7FE7bd91427724B487980aFc69` (Base) — bytecode keccak256 `0xd8511363feac51319c3a08c4ad471f451c5c8d137878cbb0e0472fd976421cd5`, EIP-1967 slots and controller unchanged at `#59653624`.
- ZTLN-P: `0xfEd3D6557Dc46A1B25d0A6F666513Cb33835864B` (Ethereum) — bytecode keccak256 `0xf480c2a32f387d87861f5e505e80169f59eb402333618d51f49d70a724388374`, EIP-1967 slots and controller unchanged at `#26451608`.
- Angle: `0x31429d1856aD1377A8A0079410B297e1a9e214c2` (Ethereum) — bytecode keccak256 `0xb2b4462244cc70f518bca0e36112dc4932b72128f6ceeb7408c0ede78cb94a1d`, EIP-1967 slots and controller unchanged at `#26451608`.
- Angstrom: `0x0000000aa232009084Bd71A5797d089AA4Edfad4` (Ethereum) — bytecode keccak256 `0x528182e66a441545ea3ba1dede4e6063f23acd4ada4036c24b9fa2f254bc4ed1`, EIP-1967 slots and controller unchanged at `#26451608`.
- ApeX Pro: `0x52A8845DF664D76C69d2EEa607CD793565aF42B8` (Ethereum) — bytecode keccak256 `0xe223553d1494126fcfef118f62fdf0d99adeb4845469f967f193d468d79aa5a2`, EIP-1967 slots and controller unchanged at `#26451608`.
- Augur: `0x221657776846890989a759BA2973e427DfF5C9bB` (Ethereum) — bytecode keccak256 `0xa75cc1804fa75f619fa67eee93ddf254251f9690bd78af4a2f59e6bf6a195331`, EIP-1967 slots and controller unchanged at `#26451608`.
- Baseline Protocol: `0x9fDbDE76236998Dc2836FE67A9954eDE456A1D63` (Ethereum) — bytecode keccak256 `0xe3a0b45b4ce46850f120cc127182598eed3e806f86c25755fea84623b4573c8d`, EIP-1967 slots and controller unchanged at `#26451608`.
- Blast pre-launch Farm: `0x5F6AE08B8AeB7078cf2F96AFb089D7c9f51DA47d` (Ethereum) — bytecode keccak256 `0x82dee1d830a79106921dc73f0ebb4758243a04f29c5346ba4f82f58b81ffef72`, EIP-1967 slots and controller unchanged at `#26451608`.
- BMX Freestyle: `0x6D63921D8203044f6AbaD8F346d3AEa9A2719dDD` (Base) — bytecode keccak256 `0x4d9be648c5bf39973670d9f8b481d5d0b971e6a2db2deccc6b98cde21c5dd83e`, EIP-1967 slots and controller unchanged at `#59653624`.
- Clipper: `0xd8F1460044925d2D5c723C7054cd9247027415B7` (Ethereum) — bytecode keccak256 `0xe059da78dcedae60d32ef3865b8af77702c451736a2d129fe2e3cf8c8d91b6e0`, EIP-1967 slots and controller unchanged at `#26451608`.
- Convergence Fi: `0xB0Afc8363b8F36E0ccE5D54251e20720FfaeaeE7` (Ethereum) — bytecode keccak256 `0xc88eb359bcda37312f65801074d04313c015d1cef388769f2c9245265653e6fa`, EIP-1967 slots and controller unchanged at `#26451608`.
- CRETH2: `0x2ba592F78dB6436527729929AAf6c908497cB200` (Ethereum) — bytecode keccak256 `0x52b508080c903feaa0b873467c07dde6f8a88f6efc88b4dd898636433e0a42f0`, EIP-1967 slots and controller unchanged at `#26451608`.
- deBridge: `0x43dE2d77BF8027e25dBD179B491e8d64f38398aA` (Ethereum) — bytecode keccak256 `0xfc1ea81db44e2de921b958dc92da921a18968ff3f3465bd475fb86dd1af03986`, EIP-1967 slots and controller unchanged at `#26451608`.
- DeFIL: `0x09ce2B746C32528B7d864A1e3979Bd97d2f095AB` (Ethereum) — bytecode keccak256 `0x3b6ce2514862cb6b6d5d37979a693a0d4f7252ce4e5f4f132441aaa1a9c30ad4`, EIP-1967 slots and controller unchanged at `#26451608`.
- DELV Yield: `0x62F161BF3692E4015BefB05A03a94A40f520d1c0` (Ethereum) — bytecode keccak256 `0xf9a3a5f11360d59f975ee3b3a133cea72978503c3940d56d12f7abdb16d42d52`, EIP-1967 slots and controller unchanged at `#26451608`.
- DerivaDEX: `0x3A880652F47bFaa771908C07Dd8673A787dAEd3A` (Ethereum) — bytecode keccak256 `0x90459b94bf726acfb040ffb9f897868235160693e9bc9f2e2aa70d67f7bd6ca2`, EIP-1967 slots and controller unchanged at `#26451608`.
- DexFi Aggregator: `0x4C1a8a04577286Ce58d0723b1a90160F380E550A` (Ethereum) — bytecode keccak256 `0xed42fb03822a5d6d75695946a6eb1eb92cda4bc668f61635fdf710d5de8e83ef`, EIP-1967 slots and controller unchanged at `#26451608`.
- DxSale: `0xF063fE1aB7a291c5d06a86e14730b00BF24cB589` (Ethereum) — bytecode keccak256 `0x08d525afaf352be3b9eeb0eea7d588fcb7ea55e5e52829d107c97ded4fcd32e6`, EIP-1967 slots and controller unchanged at `#26451608`.
- ElfomoFi: `0x64f8bE47A011DF0fAB47319d5De258D18E93f4ef` (Base) — bytecode keccak256 `0x3911795ad7e9d471583ebe7aeb1021703890f7ca55a10b8ee8ca91e55ba70565`, EIP-1967 slots and controller unchanged at `#59653624`.
- Fake World Assets V2: `0xa0Df17B5aC76ABaBA36E1450E2cbCd18A620C845` (Ethereum) — bytecode keccak256 `0xd07b0280e4e25689956cff42290d843739714308e6fbe693017cede05c2c52fd`, EIP-1967 slots and controller unchanged at `#26451608`.
- Flexa: `0xfF20817765cB7f73d4bde2e66e067E58D11095C2` (Ethereum) — bytecode keccak256 `0xa0cfa14c1f8ef49585b024e29601a34bbeb675337a94833b2df167782cebbdf5`, EIP-1967 slots and controller unchanged at `#26451608`.
- FlokiFi Locker: `0xcf0C122c6b73ff809C693DB761e7BaeBe62b6a2E` (Ethereum) — bytecode keccak256 `0x62f6a27beef672562e73fb0f3dcc4efb0d16b16cf4daeddb5c9cd8e17f58d6f8`, EIP-1967 slots and controller unchanged at `#26451608`.
- friend.tech V1: `0x0bD4887f7D41B35CD75DFF9FfeE2856106f86670` (Base) — bytecode keccak256 `0x358aa3e7ee950f58863c601550d37477d36b1dd76c1ce15342ac6649acf9caa8`, EIP-1967 slots and controller unchanged at `#59653624`.
- Gamma: `0x6BeA7CFEF803D1e3d5f7C0103f7ded065644e197` (Ethereum) — bytecode keccak256 `0x35be488840b51a9788e28175818703d2764395e5e22fd5ebfda92d575b2020aa`, EIP-1967 slots and controller unchanged at `#26451608`.
- GLIF: `0xAeD7C2eD7Bb84396AfCB55fF72c8F8E87FFb68f3` (Base) — bytecode keccak256 `0x749f3b692400fa750c12cd525331ae1eda236ca25ac3033b739b8ff04abf3c1e`, EIP-1967 slots and controller unchanged at `#59653624`.
- Gro: `0x3Ec8798B81485A254928B70CDA1cf0A2BB0B74D7` (Ethereum) — bytecode keccak256 `0x3ab25059e82d964ea1bcb4653362e7f690d2a3256437df181fe0e7f62f0b0bb2`, EIP-1967 slots and controller unchanged at `#26451608`.
- Hegic: `0x584bC13c7D411c00c01A62e8019472dE68768430` (Ethereum) — bytecode keccak256 `0xdec18c0951427319cc61da2d7548a2a4f32d2ad07de25868f528e2753602bb61`, EIP-1967 slots and controller unchanged at `#26451608`.
- ICHI: `0x111111517e4929D3dcbdfa7CCe55d30d4B6BC4d6` (Ethereum) — bytecode keccak256 `0x33c88004b04cc3a91c6c2907e8399ce7ff2acd319c1476c49e299026878e98ad`, EIP-1967 slots and controller unchanged at `#26451608`.
- Interest Protocol: `0x2A54bA2964C8Cd459Dc568853F79813a60761B58` (Ethereum) — bytecode keccak256 `0x6273eddb91b574c664e91f6e38caf04527f5172f452b419a25f858c6a6f16265`, EIP-1967 slots and controller unchanged at `#26451608`.
- Kine Finance: `0xbB7D94a423f4978545ecf73161f0678e8AfD1a92` (Ethereum) — bytecode keccak256 `0x1240a7f0370dbc9f26bbc60420e4e1034b2008607b7fb39f0948d4fa31870d95`, EIP-1967 slots and controller unchanged at `#26451608`.
- King Protocol: `0x8F08B70456eb22f6109F57b8fafE862ED28E6040` (Ethereum) — bytecode keccak256 `0xf8c4135b5cd64765ef0eab5ea7559c47552279ee03eca8241f981cc597f5c777`, EIP-1967 slots and controller unchanged at `#26451608`.
- LandX Finance: `0x08A1C30BBB26425c1031ee9E43FA0B9960742539` (Ethereum) — bytecode keccak256 `0xb612e6bd581e8e2b7889e1ce264314531cea3c5503db7e8520c0f550d6ce4f96`, EIP-1967 slots and controller unchanged at `#26451608`.
- Lazy: `0xd53B68fB4eb907c3c1E348CD7d7bEDE34f763805` (Ethereum) — bytecode keccak256 `0x1fc427a9bc54ebdc7a32d32b519126d28cd2ef37ce526cca3a51e2ca9cee7150`, EIP-1967 slots and controller unchanged at `#26451608`.
- LendFlare: `0xB620Be8a1949AA9532e6a3510132864EF9Bc3F82` (Ethereum) — bytecode keccak256 `0xf62bd5d649a541bbef0e8aecef588c949b55a8103eccdb0c8bcd07fdf803dd69`, EIP-1967 slots and controller unchanged at `#26451608`.
- LUSD ChickenBonds: `0xB9D7DdDca9a4AC480991865EfEf82E01273F79C3` (Ethereum) — bytecode keccak256 `0x6640959990cc7cea35e6eb879bdbc5b131a512820345b4adc887c97c6d6396d9`, EIP-1967 slots and controller unchanged at `#26451608`.
- MortgageFi: `0x1bE87D273d47C3832Ab7853812E9A995A4DE9EEA` (Base) — bytecode keccak256 `0x185cf047b846a3513a3de1ebeba7c30fa0ccbe85f838a616ebccd8363e3b5973`, EIP-1967 slots and controller unchanged at `#59653624`.
- Nami: `0x0100000002935Dce071f4AFA607b961575672b4C` (Ethereum) — bytecode keccak256 `0x96259673a3d3296a129cce355d4b938bf40d7162e379c966116a22e224828023`, EIP-1967 slots and controller unchanged at `#26451608`.
- NFTX: `0x87d73E916D7057945c9BcD8cdd94e42A6F47f776` (Ethereum) — bytecode keccak256 `0x2dda0f3a6bee3e5768e41adb77021f8f5653897a1c65a5f106265b17fa2c299b`, EIP-1967 slots and controller unchanged at `#26451608`.
- Nucleus: `0x52E4d8989fa8b3E1C06696e7b16DEf5d7707A0d1` (Ethereum) — bytecode keccak256 `0xb2e2580f6bee3b141fb4c2cfca77558a0ac1bf0c77dc0ec41c2d6e85f18d7ab7`, EIP-1967 slots and controller unchanged at `#26451608`.
- Outcome Finance: `0x0b8de441B26E36f461b2748919ed71f50593A67b` (Ethereum) — bytecode keccak256 `0xa10d4eb25d8cec9207b66506981e4af2f9900f06311949d2fa7beed6f8a198f9`, EIP-1967 slots and controller unchanged at `#26451608`.
- Overtime: `0x90cE5720c17587D28E4Af120ae2d313B3BAD1722` (Ethereum) — bytecode keccak256 `0x2a2b42ae5730efe6b72757400473ea6427d7d8640d35cd3c04fbdf2f2d6d7925`, EIP-1967 slots and controller unchanged at `#26451608`.
- Parallel Protocol V3: `0x6c0aeceeDc55c9d55d8B99216a670D85330941c3` (Ethereum) — bytecode keccak256 `0xe9660e0bc6bc7ea780091375b4d40a45d4afa77164cd837d3bc73eb237b40b6b`, EIP-1967 slots and controller unchanged at `#26451608`.
- Peapods Finance: `0x02f92800F57BCD74066F5709F1Daa1A4302Df875` (Ethereum) — bytecode keccak256 `0xc2df238df0d1f82b78333acfffa06600f20d55e6f2fa5b2ac05ce38526bd642c`, EIP-1967 slots and controller unchanged at `#26451608`.
- Punks Terminal: `0x000000000000A6fA31F5fC51c1640aAc76866750` (Ethereum) — bytecode keccak256 `0x5b8a9e982541c73da95a997139f197f575910a6037f34cb1e04d8567c019faf1`, EIP-1967 slots and controller unchanged at `#26451608`.
- Quickswap V4: `0xC5396866754799B9720125B104AE01d935Ab9C7b` (Base) — bytecode keccak256 `0x7822b724506fdf3f88058e04b74d0c754a8e09f5db1964fdc2ceb9977967b153`, EIP-1967 slots and controller unchanged at `#59653624`.
- Reflexer: `0x6243d8CEA23066d098a15582d81a598b4e8391F4` (Ethereum) — bytecode keccak256 `0x91b7369444e24b10e4d84904b059edc29aab786ca7c8061b5a501321c4a3cb5f`, EIP-1967 slots and controller unchanged at `#26451608`.
- Saffron Vaults: `0xb753428af26E81097e7fD17f40c88aaA3E04902c` (Ethereum) — bytecode keccak256 `0xd9f71ccdd211bba48b76ead02c0de837b0a34f07e693e367a32eff3860357a36`, EIP-1967 slots and controller unchanged at `#26451608`.
- SATO: `0x0000f07d2B5F1Ddf3244b8780F972f306EFd2888` (Ethereum) — bytecode keccak256 `0x0cb886792429db1b1f330dedc575160e709e659159b0b9477858b3965102cf42`, EIP-1967 slots and controller unchanged at `#26451608`.
- SMARDEX USDN: `0x656cB8C6d154Aad29d8771384089be5B5141f01a` (Ethereum) — bytecode keccak256 `0xfd1a8f7693ff598e9b2e993e7d30c57c12d773b948753d9edfd6761e8daeb4de`, EIP-1967 slots and controller unchanged at `#26451608`.
- SOFA.org: `0x57B96D4aF698605563A4653D882635da59Bf11AF` (Ethereum) — bytecode keccak256 `0x88056442963f4b4ba95bbdf2e92e6f4e89bfb34f82171e8837ecd7d4ffd1cc78`, EIP-1967 slots and controller unchanged at `#26451608`.
- Sommelier: `0xa670d7237398238DE01267472C6f13e5B8010FD1` (Ethereum) — bytecode keccak256 `0xe32339c16126933800abbc98e317903e5d17d0c0940813c63d51458593ef1d36`, EIP-1967 slots and controller unchanged at `#26451608`.
- Sport.fun: `0x16EE7ecAc70d1028E7712751E2Ee6BA808a7dd92` (Base) — bytecode keccak256 `0xe45965360fef796d68818c710054832bb0b9e09c72dc7783f6ebb633197bcddf`, EIP-1967 slots and controller unchanged at `#59653624`.
- StableHodl: `0x109D3042a3c682F94107b3818e93b3aDE2A47544` (Ethereum) — bytecode keccak256 `0xee8a105971995661291a9f284262a87abf2381b3cdc93b2c8fbeffe4cd636dd9`, EIP-1967 slots and controller unchanged at `#26451608`.
- Supernova CL: `0x44B7fBd4D87149eFa5347c451E74B9FD18E89c55` (Ethereum) — bytecode keccak256 `0x502e5730b9eb2b3afa6c7b8453c61c842dccac09c1a4cf4147ebb151e5184f3e`, EIP-1967 slots and controller unchanged at `#26451608`.
- SynFutures V3: `0x6e15A54B5EcAc17e58daDedDbe8506a7560252F9` (Ethereum) — bytecode keccak256 `0xb26a9e2b05c6cfb4165a2c2ea3fc8490f4b8dfbeb7e67cb1cc05687b7ed293de`, EIP-1967 slots and controller unchanged at `#26451608`.
- Taiko Bridge: `0x10dea67478c5F8C5E2D90e5E9B26dBe60c54d800` (Ethereum) — bytecode keccak256 `0x26e751b9fd68f5207c6d2b35f2871bc22c1b05e9d20368c10257dc04ca67f46e`, EIP-1967 slots and controller unchanged at `#26451608`.
- TokenWorks: `0xA1a196b5BE89Be04a2c1dc71643689CE013c22e5` (Ethereum) — bytecode keccak256 `0xdbe822093f1c9e3d148657d5122e03958449aea91b271863b5cd42c5be206a86`, EIP-1967 slots and controller unchanged at `#26451608`.
- Unitus: `0x3B6564b5DA73A41d3A66e6558a98FD0e9E1e77ad` (Ethereum) — bytecode keccak256 `0xaf9c9da08abecebd75f6ed4d1aa7e423b553ce9ca8d2fd83c025e684b72f6534`, EIP-1967 slots and controller unchanged at `#26451608`.
- Wan Bridge: `0xfCeAAaEB8D564a9D0e71Ef36f027b9D162bC334e` (Ethereum) — bytecode keccak256 `0xd0cf0742bd64c1e960f924480430b6614def86d82463b5cb878836ff12274abe`, EIP-1967 slots and controller unchanged at `#26451608`.
- WOOFi Earn: `0x4691937a7508860F876c9c0a2a617E7d9E945D4B` (Ethereum) — bytecode keccak256 `0xee7b6a4b8c8f92fbca7423f575329f7935dd6c6e3b744490b702a238a41dd4e0`, EIP-1967 slots and controller unchanged at `#26451608`.
