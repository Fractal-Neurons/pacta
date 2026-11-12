# Sprint 4 Protocol Commitment Summary — Block `26401312`

- **Ethereum Mainnet Block**: `26401312` (`0x192da20`)
- **Canonical Block Hash**: `0x95866ea3ef8f9a0567ce000bc8075f6dc5fb0f1e80cb4e9999ae624a2f0dc109`
- **Block Timestamp**: `1794515987`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-dfc7ce3ca53e`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-cc0e35af1552`, `receipt_seq: 182`, static proof-bundle & decode review)

## 1. Mellow Protocol / Lido Earn (`earnETH` / `sdearnETH` `Vault` `0x65661941412cdB162C2232D299729c13C3D0227B`)
- **Curator Safe (`0xe5abcc40196174Ae0d12153dE286F0D8E401769d`)**: Live `getThreshold() = 3`, `getOwners().length = 5` (`3-of-5` Gnosis Safe) vs. `"3/6 multisig"` listed in `lidofinance/docs` (`earn/deployment-contracts.md` line 199).
- **Role Assignments on `Vault` (`0x65661941412cdB162C2232D299729c13C3D0227B`)**:
  - `ADMIN_DELEGATE_ROLE` (`0x02`) and `OPERATOR` (`0x04`) are held by `0xe5abcc40196174Ae0d12153dE286F0D8E401769d` (`3-of-5` Curator Safe) and `0xF696f7bEf8f9aC602424221F44b33c6B6B16A4d9` (`5-of-8` Mellow Lazy Vault Admin Safe) (`1` public parameter drift recorded).

## 2. Convex Finance (`Booster` `0xF403C135812408BFbE8713b5A23a04b3D48AAE31`)
- **`owner()`**: `0x3C5A1e09150B75ff251c1a7815A07182c3de2FBc` (`VoteProxy`), whose `owner()` is `0x59CFCD384746ec3035299D90782Be065e466800B` (`cvxLockerV2` / `CvxMining` governance contract), whose `owner()` is `0xa3C5A1e09150B75ff251c1a7815A07182c3de2FB` (`3-of-5` Convex DAO Multisig).
- **`feeManager()` & `poolManager()`**: `0xa3C5A1e09150B75ff251c1a7815A07182c3de2FB` (`3-of-5` Convex DAO Multisig) and `0x989AEb4d175e16225E39E87d0D97A3360524AD80` (`PoolManagerV4`).
