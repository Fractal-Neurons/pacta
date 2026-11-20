# Sprint 34 Protocol Commitment Summary — Block `26453551`

- **Ethereum Mainnet pin**: `26453551` (`0x193a62f`), canonical block hash `0x51e9967ffd6a84012d0dad44204d523b8ac43928e69de2801d2e72dbf8767129`, timestamp `2026-11-20 03:15:35 UTC` (`1795144535`); the `finalized` head, both endpoints returning the same number and hash
- **Base Mainnet pin**: `59768717` (`0x38fff8d`), canonical block hash `0x20c204f69fb718a5dbc7976c1bfed0ceef78cf404c11072a1d962463fa07f04f`, timestamp `2026-11-20 03:08:39 UTC` (`1795144119`); the `finalized` head, both endpoints returning the same number and hash
- **Scanner**: Pacta by Fractal Neurons (Pacta Protocol Commitments DRI), bulk harvester v2.1. Read-only `eth_call` / `eth_getStorageAt` / `eth_getCode` batched through Multicall3 at the pinned block, on two independent RPCs per chain with identical block hashes: `ethereum-rpc.publicnode.com` + `rpc.mevblocker.io` (Ethereum), `base-rpc.publicnode.com` + `mainnet.base.org` (Base). Documentation: HTTP-200 first-party snapshots named by their SHA-256; every quote below is an exact substring of its snapshot's text and every value is re-derived from the pinned reads by the validator (no model output is trusted).
- **Result**: `12` records for `12` protocols (`0` new; published protocols with a new record: Aegis YUSD, Angstrom, Gamma, Hakka Finance, Hop Protocol, LUSD ChickenBonds, Piku Finance, SOFA.org, StakeStone STONE, Taiko Bridge, Tangent Finance, xDAI Stake Bridge) — `9` aligned baselines, `0` protective deltas, `3` parameter deltas. `verifiedCount = 9`. `driftCount = 3`, the same convention as Sprints 1–33 and `PactaSentinelGuard` (`driftCount != 0` means drift).
- **RPC-pinned promotions (not attested)**: `0` further new protocols are published as RPC-pinned control-plane records at the same pins (listed below); the `133` RPC-pinned protocols already published move to these pins with every stated fact unchanged. They carry no Base EAS UID. `12` published RPC-pinned protocols are documentation-compared for the first time and become Base-EAS protocols here (Aegis YUSD, Angstrom, Gamma, Hakka Finance, Hop Protocol, LUSD ChickenBonds, Piku Finance, SOFA.org, StakeStone STONE, Taiko Bridge, Tangent Finance, xDAI Stake Bridge); their RPC-pinned records are retired.
- **On-chain anchoring**: to be attested on Base Mainnet EAS (`0x4200000000000000000000000000000000000021`) under canonical schema `0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83` (`chainId = 1`, the Ethereum pin above); Base reads are taken at the Base pin.

## 1. Aegis YUSD — YUSD, JUSD, config and oracles owned by the documented Multisig; it is admin of minting and rewards

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **YUSD** | `0x4274cD7277C7bb0806Bd5FE84b9aDAE466a8DA0a` | `owner()` | owner() = Multisig 0x4Fe78eF65BD8EDDED480efaB030BA680646503c8 on YUSD 0x4274cD7277C7bb0806Bd5FE84b9aDAE466a8DA0a and on JUSD, AegisConfig, AegisOracle and AegisOracleJUSD (0xc86168d2424d28942EE0866F043c1206bc9E4900, 0x90cCF2C4b3DEe7aeac9AF5950a7C60f89AF1db00, 0x2B4Ad1d479561064cd1C311004Aca93d15041aEc, 0xfA449DC17194Fdaca1dd2237C828938f1917e0E7); hasRole(DEFAULT_ADMIN_ROLE, Multisig) = true on AegisMinting, AegisMintingJUSD and AegisRewards (0xc4df68e592245ca5202fe8b7c438d2b799820fc2, 0xBB0F32D176590faEdC7bc552b7EAD7A86809b520, 0x8aDCFAf1B64Cc514524B80565bCc732273dDEafD), the addresses owners.csv lists. The Multisig is a Safe: getThreshold() = 3 of getOwners() = 5; guard slot empty; getModulesPaginated() lists no module. (Ethereum `#26453551`) |

Classification: **aligned baseline** (1 record).
- 'Ethereum,0x4274cD7277C7bb0806Bd5FE84b9aDAE466a8DA0a,YUSD,setMinter,onlyOwner,0x4Fe78eF65BD8EDDED480efaB030BA680646503c8,Multisig' (raw.githubusercontent.com/Aegis-im/aegis-contracts/master/owners.csv) (snapshot sha256 `065cd7e746b28f41c199923f1d31d0c8ab03dd6ca375e040cd209afff33e71fa`)

## 2. Angstrom — Hook controller = documented ControllerV1; its owner = documented Timelock (5-day min delay)

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Angstrom Hook** | `0x0000000aa232009084Bd71A5797d089AA4Edfad4` | storage slot `0` | Angstrom Hook 0x0000000aa232009084Bd71A5797d089AA4Edfad4 (Ethereum, not a proxy; verified source): storage slot 0 (TopLevelAuth._controller, required by every onlyController configuration and token-pull function) = ControllerV1 0x1746484EA5e11C75e009252c102C8C33e0315fD4, whose ANGSTROM() = the hook and owner() = Timelock 0x60D41d9708BBEfd29000d1486C6406Ef23526c01, an OpenZeppelin TimelockController (verified) with getMinDelay() = 432,000 s that holds its own DEFAULT_ADMIN_ROLE: the three addresses of the deployments page's L1 table, in that control order. (Ethereum `#26453551`) |

Classification: **aligned baseline** (1 record).
- 'Angstrom Hook 0x0000000aa232009084Bd71A5797d089AA4Edfad4 ControllerV1 0x1746484EA5e11C75e009252c102C8C33e0315fD4 Timelock 0x60D41d9708BBEfd29000d1486C6406Ef23526c01' (docs.angstrom.xyz/contracts/deployments) (snapshot sha256 `3e3cb5b4349aae39cbd7871bcebb80c7934349385233b3397f1cf2dcc147c4da`)

## 3. Gamma — GAMMA supply: 100,000,000, no mint function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **GAMMA token** | `0x6BeA7CFEF803D1e3d5f7C0103f7ded065644e197` | `totalSupply()` | GAMMA token 0x6BeA7CFEF803D1e3d5f7C0103f7ded065644e197 (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 100,000,000. The runtime code holds no selector of mint(address,uint256), mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). The whole supply is minted in its constructor; the owner can only take snapshots and transfer ownership. (Ethereum `#26453551`) |

Classification: **aligned baseline** (1 record).
- 'Total Supply 100,000,000' (docs.gamma.xyz/gamma/learn/tokenomics.md) (snapshot sha256 `f40ab4a4ff591a9ed0341b94c20990e43687ce0a033e208e16b8d8aaf9c52990`)

## 4. Hakka Finance — Multi-sig: docs name 3 keyholders; the Safe is 2-of-4 with 1 unnamed owner

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Hakka Finance multi-sig (Safe)** | `0xF2B8f214Dc81b849ed3BDCAEdA6c8c39625c500A` | `getOwners()` | Hakka multi-sig 0xF2B8f214Dc81b849ed3BDCAEdA6c8c39625c500A (Ethereum Safe, the address the page gives): getThreshold() = 2 of getOwners() = 4; guard slot empty; getModulesPaginated() lists no module. Owners: 0x9033c3677E6C63FC252E9546AD5b5E7d66Fc0926, 0x1D075f1F543bB09Df4530F44ed21CA50303A65B2, 0xF9aCeFD1A4e4360eE3A534Cb3485Bce36F5F05A4, 0x784e010430a923Ce2a3Ff9846C4010694Bb7BEfb, all accounts with no code; the three documented keyholders are owners, and 0x9033c3677E6C63FC252E9546AD5b5E7d66Fc0926 is an owner the page does not name. With a threshold of 2, that key and any one documented keyholder can execute. HAKKA token 0x0E29e5AbbB5FD88e28b2d355774e73BD47dE3bcd owner() = this Safe. (Ethereum `#26453551`) |

Classification: **parameter delta** (1 record).
- 'The keyholders are as follows.' (hakkafinance.gitbook.io/hakka-wiki/governance/multi-sig.md) (snapshot sha256 `9e674bb3946ef1b4d4aa7af8129e87f30805149d0ccd0c3b300d7149f1fb685c`)

## 5. Hop Protocol — L1 ETH Bridge governance: 24h Timelock whose admin is a 2-of-3 key Safe

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Hop L1_ETH_Bridge (Ethereum)** | `0xb8901acB165ed027E32754E0FFe830802919727f` | `governance()` | Hop L1_ETH_Bridge 0xb8901acB165ed027E32754E0FFe830802919727f (Ethereum, not a proxy; verified source; the SDK's Ethereum ETH l1Bridge): addBonder(), removeBonder(), setGovernance(), setChallengePeriod(), setChainIdDepositsPaused() and rescueTransferRoot() are onlyGovernance, and governance() = 0x22e3F828b3f47dAcFACd875D20bd5cc0879C96e7, a Compound-style Timelock (verified) with delay() = 86,400 s, pendingAdmin() empty and admin() = Safe 0x1ec078551A5ac8F0f51fAc57Ffc48Ea7d9A86E9d: getThreshold() = 2 of getOwners() = 3; guard slot empty; getModulesPaginated() lists no module; all 3 owners are accounts with no code. Neither the DAO Governor 0xed8Bdb5895B8B7f9Fdb3C087628FD8410E853D48 nor the DAO Timelock 0xeeA8422a08258e73c139Fc32a25e10410c14bd7a (both on the governance links page) is in this path: 2 keys queue and execute any onlyGovernance call after 24 hours. (Ethereum `#26453551`) |

Classification: **parameter delta** (1 record).
- 'In summary, the Hop DAO controls every aspect of the protocol.' (docs.hop.exchange/governance/into-to-hop-dao); '0xeeA8422a08258e73c139Fc32a25e10410c14bd7a' (docs.hop.exchange/governance/important-links); 'l1Bridge: '0xb8901acB165ed027E32754E0FFe830802919727f'' (raw.githubusercontent.com/hop-protocol/hop/develop/packages/sdk/src/addresses/mainnet.ts) (snapshot sha256 `e410d6b10fc752f764df8a272f7b41574f4c5916b93a81f1f75469283090fcb5`, `1dfcc08a9413015645bfe715da1516de56edac90fd581a7c80b0cd2fc1f3a41a`, `f260cc4147af0c445dd8964492d570ec01d3d57f0bacc0cea4f51cf91aeea683`)

## 6. LUSD ChickenBonds — ChickenBondManager not a proxy, no owner; bLUSD and BondNFT owners renounced

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **bLUSD** | `0xB9D7DdDca9a4AC480991865EfEf82E01273F79C3` | `owner()` | ChickenBondManager 0x57619FE9C539f890b19c61812226F9703ce37137 (Ethereum; not a proxy: EIP-1967 implementation and admin slots empty; verified source): no owner() (the call reverts), no delegatecall or selfdestruct, and no upgrade path. Two functions are restricted to yearnGovernanceAddress() = 0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52 while migration is inactive: activateMigration(), the documented one-time wind-down (migration() = false at this pin), and sendFeeShare(uint256), which transfers LUSD from Yearn governance to the manager and deposits it to B.Protocol (a fee-share donation); no function is restricted to the Liquity team. bLUSD 0xB9D7DdDca9a4AC480991865EfEf82E01273F79C3 (not a proxy): owner() is the zero address (setAddresses already used, ownership renounced) and mint / burn require msg.sender == chickenBondManagerAddress() = the ChickenBondManager. BondNFT 0xa8384862219188a8f03c144953Cf21fc124029Ee: owner() is the zero address, chickenBondManager() = the ChickenBondManager. (Ethereum `#26453551`) |

Classification: **aligned baseline** (1 record).
- 'After deployment and initialization, no upgrade is possible.' (docs.chickenbonds.org/faq/technical-design.md); '0x57619FE9C539f890b19c61812226F9703ce37137' (docs.chickenbonds.org/llms-full.txt) (snapshot sha256 `cf68dddef3b697a5958d7e4af976854c8eb9007af0d48a36af31ed4b5517dd5d`, `e3929ce03df16e2b05cbd7b357f3729d1b8239e8215abdd4f470ba629ebfbda7`)

## 7. Piku Finance — PIKU supply: 500,000,000, no mint function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **PIKU token** | `0x2E4039E8E31475d65DC00293C366FDBfBBC02DC3` | `totalSupply()` | PIKU token 0x2E4039E8E31475d65DC00293C366FDBfBBC02DC3 (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 500,000,000. The runtime code holds no selector of mint(address,uint256), mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). The whole supply is minted to the admin in its constructor; no function creates tokens. (Ethereum `#26453551`) |

Classification: **aligned baseline** (1 record).
- '**Total Token Supply: 500,000,000 PIKU**' (docs.piku.co/piku/pikudao/piku.md) (snapshot sha256 `338d75fe79cbea825e5f9739a1f4b58d4d427489df39ad46666e0d01ecd0e572`)

## 8. SOFA.org — RCH: mint capped at MAX_SUPPLY = 37,000,000 (totalMinted)

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **RCH token** | `0x57B96D4aF698605563A4653D882635da59Bf11AF` | `totalSupply()` | RCH token 0x57B96D4aF698605563A4653D882635da59Bf11AF (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 27,709,422.00. The runtime code holds no selector of mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). MAX_SUPPLY() = 37,000,000 and totalMinted() = 30,647,695 (burns lower totalSupply, not totalMinted); mint() is onlyOwner and requires totalMinted + amount <= MAX_SUPPLY; owner() = 0x5a8cDDa6CA37B284b32eF8D513Ef71Ddac553270, a MerkleAirdrop contract. (Ethereum `#26453551`) |

Classification: **aligned baseline** (1 record).
- 'Total Supply: Capped at 37,000,000 $RCH.' (docs.sofa.org/en/tokenomics); 'RCH 0x57B96D4aF698605563A4653D882635da59Bf11AF' (docs.sofa.org/en/developer/contracts.html) (snapshot sha256 `b4a15c42163c88eb8269ca6f9e2288e73af604b42d615357f4ef9240623a46b0`, `682b116e31a008f607eefbbd4e6eba1abb1edd11a613b013875b85ab6b8c0b21`)

## 9. StakeStone STONE — STO (Ethereum) supply: 1,000,000,000, no mint function

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **STO token** | `0x1D88713b483A8E45cfF0e5CD7c2e15E5Fab4534d` | `totalSupply()` | STO token 0x1D88713b483A8E45cfF0e5CD7c2e15E5Fab4534d (Ethereum; not a proxy: EIP-1967 implementation, admin and beacon slots all empty; verified source): totalSupply() = 1,000,000,000. The runtime code holds no selector of mint(address,uint256), mint(uint256), upgradeTo(address), upgradeToAndCall(address,bytes). Its only mint is the internal one at construction. (Ethereum `#26453551`) |

Classification: **aligned baseline** (1 record).
- '**Maximum Token Supply** | 1,000,000,000' (docs.stakestone.io/stakestone/additionals/tokenomics.md) (snapshot sha256 `2f6c17103affdd1946c4e239ead6312c21d1d67c30a202a48938442f4413925e`)

## 10. Taiko Bridge — Emergency Multisig: minApprovals 4 of 5 signers (docs: 6); standard 3 (docs: 5)

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Taiko DAO Emergency Multisig plugin** | `0x2AffADEb2ef5e1F2a7F58964ee191F1e88317ECd` | `multisigSettings()` | Taiko DAO 0x9CDf589C941ee81D75F34d3755671d614f7cf261 (owner of controller.taiko.eth in the taiko-mono deployment log): hasPermission() grants EXECUTE_PERMISSION on the DAO to the OptimisticTokenVoting plugin 0x989E348275b659d36f8751ea1c10D146211650BE (and not to either council plugin), and PROPOSER_PERMISSION on that plugin to the Emergency Multisig 0x2AffADEb2ef5e1F2a7F58964ee191F1e88317ECd and the Multisig 0xD7dA1C25E915438720692bC55eb3a7170cA90321; all three return dao() = the DAO (EIP-1967 proxies, implementations 0x437E450452E8Bc142bd5317199296EcB187c514b, 0x8510d389236d7213eE9B9C38CAaBc0aD24853C25, 0x5B0Da2FB08754a5dDf32e28887D2F5437485f085, verified). EmergencyMultisig multisigSettings() = (onlyListed true, minApprovals 4, signerList 0x0F95E6968EC1B28c794CF1aD99609431de5179c2, proposalExpirationPeriod 1,209,600 s); the SignerList addresslistLength() = 5. Its execute() needs approvals >= minApprovals and calls createProposal(..., duration 0) on the destination plugin, which executes the actions on the DAO immediately when the duration is 0 (governanceSettings() minDuration = 0): 4 of the 5 listed signers make an emergency proposal executable. Multisig (standard) multisigSettings() = (onlyListed true, minApprovals 3, destinationProposalDuration 864,000 s, same signerList, proposalExpirationPeriod 1,209,600 s): 3 approvals move a standard proposal to the public veto stage (timelockPeriod 604,800 s, as documented). (Ethereum `#26453551`) |

Classification: **parameter delta** (1 record).
- 'The proposal must receive 6 approvals within 14 days from Security Council members to be executable.' (dao-docs.taiko.xyz/guides/making-an-emergency-proposal); 'The proposal must receive 5 approvals within 14 days from Security Council members to move to the public stage' (dao-docs.taiko.xyz/guides/making-a-standard-proposal); '- Owner (Taiko DAO): `0x9CDf589C941ee81D75F34d3755671d614f7cf261`' (raw.githubusercontent.com/taikoxyz/taiko-mono/main/packages/protocol/deployments/mainnet-contract-logs-L1.md) (snapshot sha256 `c95a8ec13bfc592d21b81892738fb7e0561a608bdb0828006394ade0c6695d95`, `db68fb8421a812983b5c9dd220ab89e09b0d6f44036de1dd5f75a6d6e4b443bc`, `5555074c5f7994a2e7928f705b2113d2f94e78537745cd2e736c890c714e45b0`)

## 11. Tangent Finance — Core contracts' owner() = the documented Admin (3-of-5 Safe)

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Tangent MarketCreator** | `0x214C8A1023B30032a2Eded109146658C6D6F2781` | `owner()` | owner() = Admin 0x461B62CB3A7e9Df8f800aE058AE92F855F2c27Ca on Control Tower 0xf3f7669dceed2f985815011c19ed68f667267215, USG 0xb1c2db5d6ca03fce73dbd304d320bf76c55ae1b1, IR Calculator 0xB4e1d3bBd2843263d58B4D648C599512cea6e88b, Rewards Accumulator 0x1461D76aA1C9c523398301D9174098c6D53ce639, Markets Creator 0x214C8A1023B30032a2Eded109146658C6D6F2781, Pauser Proxy 0x10b1f36452e27f08b0b5747f577ff816b0e6b5fa (core contracts on the contracts page). The Admin is a Safe: getThreshold() = 3 of getOwners() = 5; guard slot empty; getModulesPaginated() lists no module. (Ethereum `#26453551`) |

Classification: **aligned baseline** (1 record).
- '| Admin | 0x461B62CB3A7e9Df8f800aE058AE92F855F2c27Ca |' (docs.tangent.finance/docs/faq/contracts.md) (snapshot sha256 `cfbd11754a66ba5170d3cd25556eafd8a8a45630fefb3743c50b10f4b986e780`)

## 12. xDAI Stake Bridge — Bridge Governor Safe: 8-of-15, owners = the 15 documented governors

| Contract / Check | Address | Selector / slot | Observation |
| :--- | :--- | :--- | :--- |
| **Gnosis Bridge Governor Multisig (Ethereum)** | `0x42F38ec5A75acCEc50054671233dfAC9C0E7A3F6` | `getThreshold()` | Bridge Governor Multisig 0x42F38ec5A75acCEc50054671233dfAC9C0E7A3F6 (Ethereum Safe, the address the page gives): getThreshold() = 8 of getOwners() = 15; guard slot empty; getModulesPaginated() lists no module. Its 15 owners are exactly the 15 Ethereum governor addresses the page lists (none missing, none extra). The xDAI Bridge contract 0x4aa42145Aa6Ebf72e164C9bBC74fbD3788045016 (EternalStorageProxy, implementation 0x257bDD093Cab1Bd39eBF837dCB60f33d031d7d49) returns this Safe for both owner() and upgradeabilityOwner(). (Ethereum `#26453551`) |

Classification: **aligned baseline** (1 record).
- 'There are currently 15 Bridge Governors, of which 8-of-15 are required to pass a proposal.' (docs.gnosischain.com/bridges/management); '0x4aa42145Aa6Ebf72e164C9bBC74fbD3788045016' (docs.gnosischain.com/bridges/About%20Token%20Bridges/xdai-bridge) (snapshot sha256 `dd0bec6d5596ca6fd76953384f108b461fbd1651c9b15ea774a7b77bd13bd94e`, `463813f6a28e514cb893c658bd2f382fc47e6e500e47ff630003b090f69cb4f5`)

## 13. RPC-pinned promotions — 0 new protocols, documentation not compared

Each is published as an `rpc_observed` record (`docs/api/v1/rpc-pinned.json`): runtime bytecode, EIP-1967 slots and the first readable controller of the protocol's primary contract, at the pins above. No documentation parameter is compared, so none counts toward `verifiedCount` or `driftCount`.

| Protocol | Chain | Primary contract | Proxy | Controller |
| :--- | :--- | :--- | :--- | :--- |

## 14. Published RPC-pinned protocols moved to the Sprint 34 pins

- Extra Finance (Base): `0xBB505c54D71E9e599cB8435b4F0cEEc05fC71cbD` (Base) — bytecode keccak256 `0x2bda3204356bb12a5b68e82c0408773da0a9c311b37996552ee4e9e6756623e8`, EIP-1967 slots and controller unchanged at `#59768717`.
- Seamless Protocol (Base): `0x0E02EB705be325407707662C6f6d3466E939f3a0` (Base) — bytecode keccak256 `0x22818496ed85629596372dcbe81fbc48c729489bdf829e198040b0f06fc4f58f`, EIP-1967 slots and controller unchanged at `#59768717`.
- 3F: `0x54F862fa0612A8709F6Dec4A7B39AF015CD4E82E` (Ethereum) — bytecode keccak256 `0x4690b1cca8e819c6cf7d976ae8e296e41138d1a2d722c8d07b3394d431fc226e`, EIP-1967 slots and controller unchanged at `#26453551`.
- Aera V3: `0x29722cC9a1cACff4a15914F9bC274B46F3b90B4F` (Ethereum) — bytecode keccak256 `0xf4d329ab04c7cdbab16fe48996f83e05fbbdb9222305402bc9049c842ec5cfe7`, EIP-1967 slots and controller unchanged at `#26453551`.
- Anemoy Capital: `0x8c213ee79581Ff4984583C6a801e5263418C4b86` (Ethereum) — bytecode keccak256 `0x7d02f853cd5ee5a6aa0a08213618a6f3c3d594d4c030be909d0e894b6a37c749`, EIP-1967 slots and controller unchanged at `#26453551`.
- AO Bridge: `0xfE08D40Eee53d64936D3128838867c867602665c` (Ethereum) — bytecode keccak256 `0x53c0835906d5b2eed9f973e77d7c785956ea1d182c80679951ae09c4cfaa13c1`, EIP-1967 slots and controller unchanged at `#26453551`.
- Aster Bridge: `0x604DD02d620633Ae427888d41bfd15e38483736E` (Ethereum) — bytecode keccak256 `0x0959a24babb02d4d6c6ef27aaec9c34e824a2c55d24b13a8b3dae8401138e1c4`, EIP-1967 slots and controller unchanged at `#26453551`.
- AUTOfinance: `0x2218F90A98b0C070676f249EF44834686dAa4285` (Ethereum) — bytecode keccak256 `0x851c7bea863541332656d77df23c217c5013416390dcefce9992f95655446c1e`, EIP-1967 slots and controller unchanged at `#26453551`.
- Avalon Superearn: `0x5c8D0C48810FD37A0A824D074ee290E64f7A8Fa2` (Ethereum) — bytecode keccak256 `0xe5e3693157141608a301682c8c228c0277eac7efc0b98b57f874ca49752b5fd8`, EIP-1967 slots and controller unchanged at `#26453551`.
- BitFi Basis: `0xCdFb58c8C859Cb3F62ebe9Cf2767F9e036C7fb15` (Ethereum) — bytecode keccak256 `0x168f6bb27d4410c24923a1fa9ccad3e18530a1bdaa23935960b410be0aa1409c`, EIP-1967 slots and controller unchanged at `#26453551`.
- Concentrator: `0xb3Ad645dB386D7F6D753B2b9C3F4B853DA6890B8` (Ethereum) — bytecode keccak256 `0xce1d4da3ce85dfe2287a99b988ea0393a3d3c08472adbb065266e798585682f2`, EIP-1967 slots and controller unchanged at `#26453551`.
- Derive V3 Options: `0xB1D1eae60EEA9525032a6DCb4c1CE336a1dE71BE` (Ethereum) — bytecode keccak256 `0x4b19308ff101c086627922584dfdf6fb6f57828ecd7b0d5e84cea7cc36e2ca2b`, EIP-1967 slots and controller unchanged at `#26453551`.
- Frankencoin: `0xDb861830D9Ae2d1fCF99fA0cfd3973de382B0B5b` (Ethereum) — bytecode keccak256 `0x9dacc056e5f2d59b75a9c9ae8a3cd5134abf7bfb675462f50c12ab777603cc62`, EIP-1967 slots and controller unchanged at `#26453551`.
- Grvt Bridge: `0xAD29F2723fcdBcF665F210F25E06f97477e417cF` (Ethereum) — bytecode keccak256 `0x61f4a7aa2e0a3dcc40aa8314f37f612c0d4705c416a2bbe73430f130a25297c5`, EIP-1967 slots and controller unchanged at `#26453551`.
- Hyperlane: `0x6D265C7dD8d76F25155F1a7687C693FDC1220D12` (Ethereum) — bytecode keccak256 `0xa88000255e1f96de07122238840c31fd0b48f520430ff6dd78b7100dfc738358`, EIP-1967 slots and controller unchanged at `#26453551`.
- IDEX V1: `0xB705268213D593B8FD88d3FDEFF93AFF5CbDcfAE` (Ethereum) — bytecode keccak256 `0x41a6bbcc6ebf380d013e5bf81e1f04f14177e26857360fdb5fb0d96ab290b6a3`, EIP-1967 slots and controller unchanged at `#26453551`.
- K3 Capital: `0xdC47953c816531a8CA9E1D461AB53687d48EEA26` (Ethereum) — bytecode keccak256 `0xf44809e3d915cd908b4db54ad7e3de8d0923d8c68119d754ef9566c10573fd5e`, EIP-1967 slots and controller unchanged at `#26453551`.
- Lighter Bridge: `0x232CE3bd40fCd6f80f3d55A522d03f25Df784Ee2` (Ethereum) — bytecode keccak256 `0x509f7c0bd6c3e1d958030033e1e1e3ae1be166bbbefd2e8d8835fa72ba1a4236`, EIP-1967 slots and controller unchanged at `#26453551`.
- Origami Finance: `0x07c5500359161b81eb0DfFF83097d5025D3cF5A2` (Ethereum) — bytecode keccak256 `0x62d6e97082d84feec6a1fb354b9279aa8ceb6b7ffaf88d1bb82e9225bf1553e3`, EIP-1967 slots and controller unchanged at `#26453551`.
- PancakeSwap AMM V3: `0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865` (Ethereum) — bytecode keccak256 `0x8191d3ab1d55d3da9822199f28865415c99566b6f1aee4a4b16713f57930678c`, EIP-1967 slots and controller unchanged at `#26453551`.
- RockawayX: `0x953972ea0C1703c58F09FB6fD2477Fdcf0FEe074` (Ethereum) — bytecode keccak256 `0x864cc9ad53b338b82da1f7cab85ab0b3d5c8861acb422b6fec63cf36234f36a6`, EIP-1967 slots and controller unchanged at `#26453551`.
- Saturn: `0x23238f20b894f29041f48D88eE91131C395Aaa71` (Ethereum) — bytecode keccak256 `0x6d0ce32ba65bd273fcbdc767be5fd8924abd4ce0d6fb5c84ba39c28be05d2457`, EIP-1967 slots and controller unchanged at `#26453551`.
- Sierra Protocol: `0xe1b1252652A2FF0CC3A4214eE73d9FeD1FEa5b4f` (Ethereum) — bytecode keccak256 `0x1151e0ba784b3fe266ae02886e6435603745e3e3b288a9f5ad182737b0faa1ac`, EIP-1967 slots and controller unchanged at `#26453551`.
- Starknet Bridge: `0xCa14007Eff0dB1f8135f4C25B34De49AB0d42766` (Ethereum) — bytecode keccak256 `0x7ef33cd5b6004a6c025dee0df472999ec54227ba2a7ab0b612537ca5219ee275`, EIP-1967 slots and controller unchanged at `#26453551`.
- Team Finance: `0xCC4304A31d09258b0029eA7FE63d032f52e44EFe` (Ethereum) — bytecode keccak256 `0x17404120e429d743f170be02a42dd5018a3d340863ef7c7bf41db1baab1a1cd7`, EIP-1967 slots and controller unchanged at `#26453551`.
- Theo Network thUSD: `0xa3fE5c7596024E6811E14F029937D5bd8Ae485b3` (Ethereum) — bytecode keccak256 `0xc8ff19e35002275bcbf9f8eede7c2030293c871666ff06c9eb19933826d81271`, EIP-1967 slots and controller unchanged at `#26453551`.
- Tornado Cash: `0x77777FeDdddFfC19Ff86DB637967013e6C6A116C` (Ethereum) — bytecode keccak256 `0x7bb3883a4af95ea24983177dbcb682a021f389b77835ed266bfa30bda271c77b`, EIP-1967 slots and controller unchanged at `#26453551`.
- UNCX Network V2: `0xaDB2437e6F65682B85F814fBc12FeC0508A7B1D0` (Ethereum) — bytecode keccak256 `0x9ef6c8d303308ae4c0cfd6466aff6fd25946facfdeb76992707386a34ae5879f`, EIP-1967 slots and controller unchanged at `#26453551`.
- USDT0: `0x6C96dE32CEa08842dcc4058c14d3aaAD7Fa41dee` (Ethereum) — bytecode keccak256 `0xe5e3693157141608a301682c8c228c0277eac7efc0b98b57f874ca49752b5fd8`, EIP-1967 slots and controller unchanged at `#26453551`.
- Veda: `0x5232bc0F5999f8dA604c42E1748A13a170F94A1B` (Ethereum) — bytecode keccak256 `0xf349ba5ac81eb0f8ad05e353e581928b157ebce878db155eaea6f4534cb5fe2b`, EIP-1967 slots and controller unchanged at `#26453551`.
- World Chain Bridge: `0x90BB48fe3310499Db36437dCAE642F721e32d094` (Ethereum) — bytecode keccak256 `0xfa8c9db6c6cab7108dea276f4cd09d575674eb0852c0fa3187e59e98ef977998`, EIP-1967 slots and controller unchanged at `#26453551`.
- ZEROBASE CeDeFi: `0xfAB99fCF605fD8f4593EDb70A43bA56542777777` (Ethereum) — bytecode keccak256 `0x5ea0a98719770123cf8cb56ed504a5975019e01868505874dc2fb31b034a7cfe`, EIP-1967 slots and controller unchanged at `#26453551`.
- ADI Bridge: `0x8B1484d57abBE239bB280661377363b03c89CaEa` (Ethereum) — bytecode keccak256 `0x864cc9ad53b338b82da1f7cab85ab0b3d5c8861acb422b6fec63cf36234f36a6`, EIP-1967 slots and controller unchanged at `#26453551`.
- Ankr: `0x8290333ceF9e6D528dD5618Fb97a76f268f3EDD4` (Ethereum) — bytecode keccak256 `0x0c0a59b206d3675604c0d605ecbf7ec2c7deedaee03fd40f9f94e4bd7e954798`, EIP-1967 slots and controller unchanged at `#26453551`.
- Anvil: `0xAEEAa594e7dc112D67b8547fe9767a02c15B5597` (Ethereum) — bytecode keccak256 `0x429a8e131784eb8288d76e76719f82390c239cc6c473298627c6524c61706197`, EIP-1967 slots and controller unchanged at `#26453551`.
- Arkis: `0xEA623eebd9c5bFd56067e36C89Db0C13e6c70ba8` (Ethereum) — bytecode keccak256 `0xddb2c9db76f64c21284e72e3ac43a2e9c263034b5b317504860a5adce96d91e7`, EIP-1967 slots and controller unchanged at `#26453551`.
- Aura: `0xC0c293ce456fF0ED870ADd98a0828Dd4d2903DBF` (Ethereum) — bytecode keccak256 `0x29fa14ed566cfc96628bfb573316782856bc583b0b3079fa524d13a38dd0d58b`, EIP-1967 slots and controller unchanged at `#26453551`.
- Avant avETH: `0x9469470C9878bf3d6d0604831d9A3A366156f7EE` (Ethereum) — bytecode keccak256 `0x9591b0f9a962e55ec9d4ab889638af7d31a3368e23618ee5599a609dcc1159fd`, EIP-1967 slots and controller unchanged at `#26453551`.
- Badger DAO: `0x3472A5A71965499acd81997a54BBA8D852C6E53d` (Ethereum) — bytecode keccak256 `0x2dda0f3a6bee3e5768e41adb77021f8f5653897a1c65a5f106265b17fa2c299b`, EIP-1967 slots and controller unchanged at `#26453551`.
- Blur Bids: `0x5283D291DBCF85356A21bA090E6db59121208b44` (Ethereum) — bytecode keccak256 `0xeb2957414f3daa1495aa331973f631de8ee6c87994fc4a612da20a97f4e14150`, EIP-1967 slots and controller unchanged at `#26453551`.
- Brickken: `0x0A638F07ACc6969abF392bB009f216D22aDEa36d` (Ethereum) — bytecode keccak256 `0xdf740b7eec2ee1e88020370781c03aab1b04dc55a1dc622b48cb7002ce87fb8e`, EIP-1967 slots and controller unchanged at `#26453551`.
- Chamber Vaults: `0xca1207647Ff814039530D7d35df0e1Dd2e91Fa84` (Ethereum) — bytecode keccak256 `0x1154b4431256a941501d558a4d3a3fd001a431840461ac32435cd878b90946ac`, EIP-1967 slots and controller unchanged at `#26453551`.
- Cronos zkEVM Bridge: `0x28Ff2E4dD1B58efEB0fC138602A28D5aE81e44e2` (Ethereum) — bytecode keccak256 `0xee8a105971995661291a9f284262a87abf2381b3cdc93b2c8fbeffe4cd636dd9`, EIP-1967 slots and controller unchanged at `#26453551`.
- D2 Finance: `0x07Dff4087b43c4A759f4Fc69511c26d51929dAF4` (Ethereum) — bytecode keccak256 `0x86b6dc26240e014376e03dac6bdfc333b63e56ee7506e1000786f8c33a6fb8c0`, EIP-1967 slots and controller unchanged at `#26453551`.
- DODO AMM: `0x43Dfc4159D86F3A37A5A4B3D4580b888ad7d4DDd` (Ethereum) — bytecode keccak256 `0xa3ed78c2deb7d2c3197c7f1f83847c7a2e806273099255078f11d84387b70ab9`, EIP-1967 slots and controller unchanged at `#26453551`.
- Drakewell USDdw: `0x2B5895b716311A1eaC8f93fB88C56aF9eC8C1A69` (Ethereum) — bytecode keccak256 `0xbb70cbce5814331e91f8533edb5153fbccaa65f6ab99f5baf5d9d766c4888309`, EIP-1967 slots and controller unchanged at `#26453551`.
- Easedefi.org: `0xEa5eDef1287AfDF9Eb8A46f9773AbFc10820c61c` (Ethereum) — bytecode keccak256 `0x614b8db3fa7d70d7f8369ff9cca21049df4bf56aef08bce338c66e82dfa1e1a1`, EIP-1967 slots and controller unchanged at `#26453551`.
- edgeX Bridge: `0xB0076DE78Dc50581770BBa1D211dDc0aD4F2a241` (Ethereum) — bytecode keccak256 `0xde5d6e9d24143b30c748d881d84f897a424b86c8a931badaa1ca8b4dd7e4051e`, EIP-1967 slots and controller unchanged at `#26453551`.
- Eigenpie: `0x20b70E4A1883b81429533FeD944d7957121c7CAB` (Ethereum) — bytecode keccak256 `0x02f54b576cbf2fd200517ffc5f9cdbd7c08314e9eb8002043e355001fa4e373f`, EIP-1967 slots and controller unchanged at `#26453551`.
- FermiSwap: `0xb1076fE3AB5e28005C7c323Bac5AC06a680d452e` (Ethereum) — bytecode keccak256 `0xba367f88fc2257711f741c9f6c4bca4b20e1030ab06635bbb903b0bf052d2638`, EIP-1967 slots and controller unchanged at `#26453551`.
- GETH: `0x3802c218221390025BCEABBaD5D8C59F40eB74B8` (Ethereum) — bytecode keccak256 `0xb5e0d7b2fb71f8589a2298f1e39888d6f7df1f3cf7338f44ce9f64337a724b1a`, EIP-1967 slots and controller unchanged at `#26453551`.
- Gondi V3: `0xf65B99CE6DC5F6c556172BCC0Ff27D3665a7d9A8` (Ethereum) — bytecode keccak256 `0x5a24688c56b5bd15d41e7fad9201ef8472da0b86cbda8ede7713b58ce6b09600`, EIP-1967 slots and controller unchanged at `#26453551`.
- Harvest Finance: `0xa0246c9032bC3A600820415aE600c6388619A14D` (Ethereum) — bytecode keccak256 `0x9c1795bb8a1ae198f6f98c74e4c0cebb6726da3b592ccda396ab78ee30c65fed`, EIP-1967 slots and controller unchanged at `#26453551`.
- Injective Bridge: `0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30` (Ethereum) — bytecode keccak256 `0x2860075dbbe8adda4739434d6accb0f815f6c16d66c1334920c2dde5cdf67f48`, EIP-1967 slots and controller unchanged at `#26453551`.
- Juicebox V1: `0x3abF2A4f8452cCC2CF7b4C1e4663147600646f66` (Ethereum) — bytecode keccak256 `0xf28bae363907eeebbed68f7f0b0efc447d495263f180b6ff3e161f81f75be328`, EIP-1967 slots and controller unchanged at `#26453551`.
- Ledgity Yield: `0x482dF7483a52496F4C65AB499966dfcdf4DDFDbc` (Ethereum) — bytecode keccak256 `0xe71d9a8dc2039e8ad5f38dc0f95409ec914ee7cba1c413374a11fba65d7941af`, EIP-1967 slots and controller unchanged at `#26453551`.
- Legion: `0xa0BeB0A8C765482c128a2986c063AF5C3171ff2F` (Ethereum) — bytecode keccak256 `0xf7924ec4706f7b92b773d73078c1f3d26580e4954d342f283018d7a713bb6186`, EIP-1967 slots and controller unchanged at `#26453551`.
- Metis Bridge: `0x9E32b13ce7f2E80A01932B42553652E053D6ed8e` (Ethereum) — bytecode keccak256 `0x9a833fe40ae2176ba5d50fbb57f2ad20f4189097772a9180c30bb9114526b55c`, EIP-1967 slots and controller unchanged at `#26453551`.
- Metronome Synth: `0x2Ebd53d035150f328bd754D6DC66B99B0eDB89aa` (Ethereum) — bytecode keccak256 `0xe2a3917cd8f22f7a6d01aedf941b9982b15af8484a9578939a24c93fd7b1fdff`, EIP-1967 slots and controller unchanged at `#26453551`.
- Monolith Market: `0x6D961c9DCF1AD73566822BA4B087892e3839B849` (Ethereum) — bytecode keccak256 `0x67cab37d1c7a97e5bd64e10a5e6283e14f2384165e1ba55ed4f0a51aaf8fcc96`, EIP-1967 slots and controller unchanged at `#26453551`.
- Morph Bridge: `0xDc71366EFFA760804DCFC3EDF87fa2A6f1623304` (Ethereum) — bytecode keccak256 `0x44107d7c70e67e04d35d77455d5755c94d4897196e4ea9a341c1a6d864a6d4d5`, EIP-1967 slots and controller unchanged at `#26453551`.
- Multichain: `0x9Fb9a33956351cf4fa040f65A13b835A3C8764E3` (Ethereum) — bytecode keccak256 `0x6a3d203c440e54090e1d8f2dfdb9aa32e0df4b7dd5bfd02d11889f3bd9534492`, EIP-1967 slots and controller unchanged at `#26453551`.
- Native Credit Pool: `0xe3D41d19564922C9952f692C5Dd0563030f5f2EF` (Ethereum) — bytecode keccak256 `0xde357882f2c0a539e8abef1c3c091bf56874c09a141eef9534dd62372e91e93c`, EIP-1967 slots and controller unchanged at `#26453551`.
- NodeDAO: `0xd7C049CD4ba216679ecC04Eb2767cC5E39812121` (Ethereum) — bytecode keccak256 `0x19d55c6b37ed536e4412158686e2df774d0e754dbb580b5f87923c7049d0ac0a`, EIP-1967 slots and controller unchanged at `#26453551`.
- OpenGDP Shared Security: `0x54e44DbB92dBA848ACe27F44c0CB4268981eF1CC` (Ethereum) — bytecode keccak256 `0xde741c264ec7f60e744da6731a699d17530b431a41d2e2ebe7476abc11261e92`, EIP-1967 slots and controller unchanged at `#26453551`.
- Paradex Bridge: `0xb32E10022FFBeDfE10bc818a1C7e67D9d87e0fa7` (Ethereum) — bytecode keccak256 `0xee8a105971995661291a9f284262a87abf2381b3cdc93b2c8fbeffe4cd636dd9`, EIP-1967 slots and controller unchanged at `#26453551`.
- Pirex: `0xc55126051B22eBb829D00368f4B12Bde432de5Da` (Ethereum) — bytecode keccak256 `0x574a98b7bd30da9de3edfb7134b4e9dd5b4bbc011bb85a984aa06dae0e350f53`, EIP-1967 slots and controller unchanged at `#26453551`.
- Ribbon: `0x6123B0049F904d730dB3C36a31167D9d4121fA6B` (Ethereum) — bytecode keccak256 `0x06f86d51347023f4971c0638f8cb71cbd7b4de3b92a825904205dd2486591d59`, EIP-1967 slots and controller unchanged at `#26453551`.
- Ring Few: `0x7D86394139bf1122E82FDF45Bb4e3b038A4464DD` (Ethereum) — bytecode keccak256 `0x5126b02f7eec0470df7780456cdcee61bc47bf7bf574f213674c66393fd50ae9`, EIP-1967 slots and controller unchanged at `#26453551`.
- Royco V2: `0x7cC6fB28eC7b5e7afC3cB3986141797ffc27253C` (Ethereum) — bytecode keccak256 `0x18f95d772587f01e910a390c7b48d767fbfa7726584405e8277da572b72f9386`, EIP-1967 slots and controller unchanged at `#26453551`.
- Stafi: `0xef3A930e1FfFFAcd2fc13434aC81bD278B0ecC8d` (Ethereum) — bytecode keccak256 `0xcfb26d9dee1cbb07d16138dc589dff327bc820f608c7d6142789f9b2d94d9922`, EIP-1967 slots and controller unchanged at `#26453551`.
- Steer Protocol: `0xCEBF1A54A9Ce703FC80967760b5A6cbDb4111099` (Ethereum) — bytecode keccak256 `0x1e71c4a5b01c61a4b1a4afa98257a085e472bfc63a362efa77be9a23e714cdc9`, EIP-1967 slots and controller unchanged at `#26453551`.
- SushiSwap V3: `0xc35DADB65012eC5796536bD9864eD8773aBc74C4` (Ethereum) — bytecode keccak256 `0x2908b9ac88489ac1ed7dbc2d6ff5c0832b56dc8f5408e4992b9c7c6a24bb337a`, EIP-1967 slots and controller unchanged at `#26453551`.
- Symbiosis: `0xd38BB40815d2B0c2d2c866e0c72c5728ffC76dd9` (Ethereum) — bytecode keccak256 `0x145131033c93e676112c82aa230328dfc8dd0ac596f59e4ed90ee5045adcdd20`, EIP-1967 slots and controller unchanged at `#26453551`.
- Synapse Cross Chain Bridge: `0x0f2D719407FdBeFF09D87557AbB7232601FD9F29` (Ethereum) — bytecode keccak256 `0x14b9c77780d7daf560bdab14dea33da9fa0bc59eb71b6a1d230de99b6ee0500f`, EIP-1967 slots and controller unchanged at `#26453551`.
- Syntropia: `0x1b2CB79a4564206f53Ba80b4d780F251b4Ae6765` (Ethereum) — bytecode keccak256 `0xdc8d9306a3726daedf8bb0db4da810ed5af2b6ab034e593737a83531a2e7d327`, EIP-1967 slots and controller unchanged at `#26453551`.
- UltraYield Vaults: `0x8ECC0B419dfe3AE197BC96f2a03636b5E1BE91db` (Ethereum) — bytecode keccak256 `0xe428fca70a96823c60ffaa430edc8cc501377a4709bdb3a070d024d616d81ff5`, EIP-1967 slots and controller unchanged at `#26453551`.
- Unslashed: `0xE0e05c43c097B0982Db6c9d626c4eb9e95C3b9ce` (Ethereum) — bytecode keccak256 `0x76b55d62d6e6d762eaa121e1cd4d14100f2d08c36d299b970d06a973dc86fb90`, EIP-1967 slots and controller unchanged at `#26453551`.
- Wildcat Protocol: `0xfEB516d9D946dD487A9346F6fee11f40C6945eE4` (Ethereum) — bytecode keccak256 `0x3622afdfc583101952ff6e608d76f9c897d2767297315962d97f8b3a2cc2df56`, EIP-1967 slots and controller unchanged at `#26453551`.
- XSY: `0xBA515304d8153c4b162dC79f867E152DF9c127eb` (Base) — bytecode keccak256 `0xa403fa29cda49311b973967ea91292c75ab23dd093a8444ae680d9099fac817a`, EIP-1967 slots and controller unchanged at `#59768717`.
- YieldFi: `0x19Ebd191f7A24ECE672ba13A302212b5eF7F35cb` (Ethereum) — bytecode keccak256 `0xcb948150f62f6105c4bab1c9fa409ee4a30c35405b1622d203d440a703ece90e`, EIP-1967 slots and controller unchanged at `#26453551`.
- Yuzu Money: `0x224e90591A2d63fb66E677D0561Ea4A6Ad1F098D` (Ethereum) — bytecode keccak256 `0xb516ec422f5c3709db0ba2ff716d5e06daaec61bf753989303aa3679d5163095`, EIP-1967 slots and controller unchanged at `#26453551`.
- Zora Bridge: `0x1111111111166b7FE7bd91427724B487980aFc69` (Base) — bytecode keccak256 `0xd8511363feac51319c3a08c4ad471f451c5c8d137878cbb0e0472fd976421cd5`, EIP-1967 slots and controller unchanged at `#59768717`.
- ZTLN-P: `0xfEd3D6557Dc46A1B25d0A6F666513Cb33835864B` (Ethereum) — bytecode keccak256 `0xf480c2a32f387d87861f5e505e80169f59eb402333618d51f49d70a724388374`, EIP-1967 slots and controller unchanged at `#26453551`.
- Angle: `0x31429d1856aD1377A8A0079410B297e1a9e214c2` (Ethereum) — bytecode keccak256 `0xb2b4462244cc70f518bca0e36112dc4932b72128f6ceeb7408c0ede78cb94a1d`, EIP-1967 slots and controller unchanged at `#26453551`.
- ApeX Pro: `0x52A8845DF664D76C69d2EEa607CD793565aF42B8` (Ethereum) — bytecode keccak256 `0xe223553d1494126fcfef118f62fdf0d99adeb4845469f967f193d468d79aa5a2`, EIP-1967 slots and controller unchanged at `#26453551`.
- Augur: `0x221657776846890989a759BA2973e427DfF5C9bB` (Ethereum) — bytecode keccak256 `0xa75cc1804fa75f619fa67eee93ddf254251f9690bd78af4a2f59e6bf6a195331`, EIP-1967 slots and controller unchanged at `#26453551`.
- Baseline Protocol: `0x9fDbDE76236998Dc2836FE67A9954eDE456A1D63` (Ethereum) — bytecode keccak256 `0xe3a0b45b4ce46850f120cc127182598eed3e806f86c25755fea84623b4573c8d`, EIP-1967 slots and controller unchanged at `#26453551`.
- Blast pre-launch Farm: `0x5F6AE08B8AeB7078cf2F96AFb089D7c9f51DA47d` (Ethereum) — bytecode keccak256 `0x82dee1d830a79106921dc73f0ebb4758243a04f29c5346ba4f82f58b81ffef72`, EIP-1967 slots and controller unchanged at `#26453551`.
- BMX Freestyle: `0x6D63921D8203044f6AbaD8F346d3AEa9A2719dDD` (Base) — bytecode keccak256 `0x4d9be648c5bf39973670d9f8b481d5d0b971e6a2db2deccc6b98cde21c5dd83e`, EIP-1967 slots and controller unchanged at `#59768717`.
- Clipper: `0xd8F1460044925d2D5c723C7054cd9247027415B7` (Ethereum) — bytecode keccak256 `0xe059da78dcedae60d32ef3865b8af77702c451736a2d129fe2e3cf8c8d91b6e0`, EIP-1967 slots and controller unchanged at `#26453551`.
- Convergence Fi: `0xB0Afc8363b8F36E0ccE5D54251e20720FfaeaeE7` (Ethereum) — bytecode keccak256 `0xc88eb359bcda37312f65801074d04313c015d1cef388769f2c9245265653e6fa`, EIP-1967 slots and controller unchanged at `#26453551`.
- CRETH2: `0x2ba592F78dB6436527729929AAf6c908497cB200` (Ethereum) — bytecode keccak256 `0x52b508080c903feaa0b873467c07dde6f8a88f6efc88b4dd898636433e0a42f0`, EIP-1967 slots and controller unchanged at `#26453551`.
- DeFIL: `0x09ce2B746C32528B7d864A1e3979Bd97d2f095AB` (Ethereum) — bytecode keccak256 `0x3b6ce2514862cb6b6d5d37979a693a0d4f7252ce4e5f4f132441aaa1a9c30ad4`, EIP-1967 slots and controller unchanged at `#26453551`.
- DELV Yield: `0x62F161BF3692E4015BefB05A03a94A40f520d1c0` (Ethereum) — bytecode keccak256 `0xf9a3a5f11360d59f975ee3b3a133cea72978503c3940d56d12f7abdb16d42d52`, EIP-1967 slots and controller unchanged at `#26453551`.
- DerivaDEX: `0x3A880652F47bFaa771908C07Dd8673A787dAEd3A` (Ethereum) — bytecode keccak256 `0x90459b94bf726acfb040ffb9f897868235160693e9bc9f2e2aa70d67f7bd6ca2`, EIP-1967 slots and controller unchanged at `#26453551`.
- DexFi Aggregator: `0x4C1a8a04577286Ce58d0723b1a90160F380E550A` (Ethereum) — bytecode keccak256 `0xed42fb03822a5d6d75695946a6eb1eb92cda4bc668f61635fdf710d5de8e83ef`, EIP-1967 slots and controller unchanged at `#26453551`.
- DxSale: `0xF063fE1aB7a291c5d06a86e14730b00BF24cB589` (Ethereum) — bytecode keccak256 `0x08d525afaf352be3b9eeb0eea7d588fcb7ea55e5e52829d107c97ded4fcd32e6`, EIP-1967 slots and controller unchanged at `#26453551`.
- ElfomoFi: `0x64f8bE47A011DF0fAB47319d5De258D18E93f4ef` (Base) — bytecode keccak256 `0x3911795ad7e9d471583ebe7aeb1021703890f7ca55a10b8ee8ca91e55ba70565`, EIP-1967 slots and controller unchanged at `#59768717`.
- Fake World Assets V2: `0xa0Df17B5aC76ABaBA36E1450E2cbCd18A620C845` (Ethereum) — bytecode keccak256 `0xd07b0280e4e25689956cff42290d843739714308e6fbe693017cede05c2c52fd`, EIP-1967 slots and controller unchanged at `#26453551`.
- Flexa: `0xfF20817765cB7f73d4bde2e66e067E58D11095C2` (Ethereum) — bytecode keccak256 `0xa0cfa14c1f8ef49585b024e29601a34bbeb675337a94833b2df167782cebbdf5`, EIP-1967 slots and controller unchanged at `#26453551`.
- FlokiFi Locker: `0xcf0C122c6b73ff809C693DB761e7BaeBe62b6a2E` (Ethereum) — bytecode keccak256 `0x62f6a27beef672562e73fb0f3dcc4efb0d16b16cf4daeddb5c9cd8e17f58d6f8`, EIP-1967 slots and controller unchanged at `#26453551`.
- friend.tech V1: `0x0bD4887f7D41B35CD75DFF9FfeE2856106f86670` (Base) — bytecode keccak256 `0x358aa3e7ee950f58863c601550d37477d36b1dd76c1ce15342ac6649acf9caa8`, EIP-1967 slots and controller unchanged at `#59768717`.
- GLIF: `0xAeD7C2eD7Bb84396AfCB55fF72c8F8E87FFb68f3` (Base) — bytecode keccak256 `0x749f3b692400fa750c12cd525331ae1eda236ca25ac3033b739b8ff04abf3c1e`, EIP-1967 slots and controller unchanged at `#59768717`.
- Gro: `0x3Ec8798B81485A254928B70CDA1cf0A2BB0B74D7` (Ethereum) — bytecode keccak256 `0x3ab25059e82d964ea1bcb4653362e7f690d2a3256437df181fe0e7f62f0b0bb2`, EIP-1967 slots and controller unchanged at `#26453551`.
- Hegic: `0x584bC13c7D411c00c01A62e8019472dE68768430` (Ethereum) — bytecode keccak256 `0xdec18c0951427319cc61da2d7548a2a4f32d2ad07de25868f528e2753602bb61`, EIP-1967 slots and controller unchanged at `#26453551`.
- ICHI: `0x111111517e4929D3dcbdfa7CCe55d30d4B6BC4d6` (Ethereum) — bytecode keccak256 `0x33c88004b04cc3a91c6c2907e8399ce7ff2acd319c1476c49e299026878e98ad`, EIP-1967 slots and controller unchanged at `#26453551`.
- Interest Protocol: `0x2A54bA2964C8Cd459Dc568853F79813a60761B58` (Ethereum) — bytecode keccak256 `0x6273eddb91b574c664e91f6e38caf04527f5172f452b419a25f858c6a6f16265`, EIP-1967 slots and controller unchanged at `#26453551`.
- Kine Finance: `0xbB7D94a423f4978545ecf73161f0678e8AfD1a92` (Ethereum) — bytecode keccak256 `0x1240a7f0370dbc9f26bbc60420e4e1034b2008607b7fb39f0948d4fa31870d95`, EIP-1967 slots and controller unchanged at `#26453551`.
- King Protocol: `0x8F08B70456eb22f6109F57b8fafE862ED28E6040` (Ethereum) — bytecode keccak256 `0xf8c4135b5cd64765ef0eab5ea7559c47552279ee03eca8241f981cc597f5c777`, EIP-1967 slots and controller unchanged at `#26453551`.
- LandX Finance: `0x08A1C30BBB26425c1031ee9E43FA0B9960742539` (Ethereum) — bytecode keccak256 `0xb612e6bd581e8e2b7889e1ce264314531cea3c5503db7e8520c0f550d6ce4f96`, EIP-1967 slots and controller unchanged at `#26453551`.
- Lazy: `0xd53B68fB4eb907c3c1E348CD7d7bEDE34f763805` (Ethereum) — bytecode keccak256 `0x1fc427a9bc54ebdc7a32d32b519126d28cd2ef37ce526cca3a51e2ca9cee7150`, EIP-1967 slots and controller unchanged at `#26453551`.
- LendFlare: `0xB620Be8a1949AA9532e6a3510132864EF9Bc3F82` (Ethereum) — bytecode keccak256 `0xf62bd5d649a541bbef0e8aecef588c949b55a8103eccdb0c8bcd07fdf803dd69`, EIP-1967 slots and controller unchanged at `#26453551`.
- MortgageFi: `0x1bE87D273d47C3832Ab7853812E9A995A4DE9EEA` (Base) — bytecode keccak256 `0x185cf047b846a3513a3de1ebeba7c30fa0ccbe85f838a616ebccd8363e3b5973`, EIP-1967 slots and controller unchanged at `#59768717`.
- Nami: `0x0100000002935Dce071f4AFA607b961575672b4C` (Ethereum) — bytecode keccak256 `0x96259673a3d3296a129cce355d4b938bf40d7162e379c966116a22e224828023`, EIP-1967 slots and controller unchanged at `#26453551`.
- NFTX: `0x87d73E916D7057945c9BcD8cdd94e42A6F47f776` (Ethereum) — bytecode keccak256 `0x2dda0f3a6bee3e5768e41adb77021f8f5653897a1c65a5f106265b17fa2c299b`, EIP-1967 slots and controller unchanged at `#26453551`.
- Nucleus: `0x52E4d8989fa8b3E1C06696e7b16DEf5d7707A0d1` (Ethereum) — bytecode keccak256 `0xb2e2580f6bee3b141fb4c2cfca77558a0ac1bf0c77dc0ec41c2d6e85f18d7ab7`, EIP-1967 slots and controller unchanged at `#26453551`.
- Outcome Finance: `0x0b8de441B26E36f461b2748919ed71f50593A67b` (Ethereum) — bytecode keccak256 `0xa10d4eb25d8cec9207b66506981e4af2f9900f06311949d2fa7beed6f8a198f9`, EIP-1967 slots and controller unchanged at `#26453551`.
- Overtime: `0x90cE5720c17587D28E4Af120ae2d313B3BAD1722` (Ethereum) — bytecode keccak256 `0x2a2b42ae5730efe6b72757400473ea6427d7d8640d35cd3c04fbdf2f2d6d7925`, EIP-1967 slots and controller unchanged at `#26453551`.
- Punks Terminal: `0x000000000000A6fA31F5fC51c1640aAc76866750` (Ethereum) — bytecode keccak256 `0x5b8a9e982541c73da95a997139f197f575910a6037f34cb1e04d8567c019faf1`, EIP-1967 slots and controller unchanged at `#26453551`.
- Quickswap V4: `0xC5396866754799B9720125B104AE01d935Ab9C7b` (Base) — bytecode keccak256 `0x7822b724506fdf3f88058e04b74d0c754a8e09f5db1964fdc2ceb9977967b153`, EIP-1967 slots and controller unchanged at `#59768717`.
- Reflexer: `0x6243d8CEA23066d098a15582d81a598b4e8391F4` (Ethereum) — bytecode keccak256 `0x91b7369444e24b10e4d84904b059edc29aab786ca7c8061b5a501321c4a3cb5f`, EIP-1967 slots and controller unchanged at `#26453551`.
- Saffron Vaults: `0xb753428af26E81097e7fD17f40c88aaA3E04902c` (Ethereum) — bytecode keccak256 `0xd9f71ccdd211bba48b76ead02c0de837b0a34f07e693e367a32eff3860357a36`, EIP-1967 slots and controller unchanged at `#26453551`.
- SATO: `0x0000f07d2B5F1Ddf3244b8780F972f306EFd2888` (Ethereum) — bytecode keccak256 `0x0cb886792429db1b1f330dedc575160e709e659159b0b9477858b3965102cf42`, EIP-1967 slots and controller unchanged at `#26453551`.
- SMARDEX USDN: `0x656cB8C6d154Aad29d8771384089be5B5141f01a` (Ethereum) — bytecode keccak256 `0xfd1a8f7693ff598e9b2e993e7d30c57c12d773b948753d9edfd6761e8daeb4de`, EIP-1967 slots and controller unchanged at `#26453551`.
- Sommelier: `0xa670d7237398238DE01267472C6f13e5B8010FD1` (Ethereum) — bytecode keccak256 `0xe32339c16126933800abbc98e317903e5d17d0c0940813c63d51458593ef1d36`, EIP-1967 slots and controller unchanged at `#26453551`.
- Sport.fun: `0x16EE7ecAc70d1028E7712751E2Ee6BA808a7dd92` (Base) — bytecode keccak256 `0xe45965360fef796d68818c710054832bb0b9e09c72dc7783f6ebb633197bcddf`, EIP-1967 slots and controller unchanged at `#59768717`.
- StableHodl: `0x109D3042a3c682F94107b3818e93b3aDE2A47544` (Ethereum) — bytecode keccak256 `0xee8a105971995661291a9f284262a87abf2381b3cdc93b2c8fbeffe4cd636dd9`, EIP-1967 slots and controller unchanged at `#26453551`.
- Supernova CL: `0x44B7fBd4D87149eFa5347c451E74B9FD18E89c55` (Ethereum) — bytecode keccak256 `0x502e5730b9eb2b3afa6c7b8453c61c842dccac09c1a4cf4147ebb151e5184f3e`, EIP-1967 slots and controller unchanged at `#26453551`.
- TokenWorks: `0xA1a196b5BE89Be04a2c1dc71643689CE013c22e5` (Ethereum) — bytecode keccak256 `0xdbe822093f1c9e3d148657d5122e03958449aea91b271863b5cd42c5be206a86`, EIP-1967 slots and controller unchanged at `#26453551`.
- Unitus: `0x3B6564b5DA73A41d3A66e6558a98FD0e9E1e77ad` (Ethereum) — bytecode keccak256 `0xaf9c9da08abecebd75f6ed4d1aa7e423b553ce9ca8d2fd83c025e684b72f6534`, EIP-1967 slots and controller unchanged at `#26453551`.
- Wan Bridge: `0xfCeAAaEB8D564a9D0e71Ef36f027b9D162bC334e` (Ethereum) — bytecode keccak256 `0xd0cf0742bd64c1e960f924480430b6614def86d82463b5cb878836ff12274abe`, EIP-1967 slots and controller unchanged at `#26453551`.
- WOOFi Earn: `0x4691937a7508860F876c9c0a2a617E7d9E945D4B` (Ethereum) — bytecode keccak256 `0xee7b6a4b8c8f92fbca7423f575329f7935dd6c6e3b744490b702a238a41dd4e0`, EIP-1967 slots and controller unchanged at `#26453551`.
