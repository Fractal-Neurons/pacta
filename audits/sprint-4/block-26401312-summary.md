# Sprint 4 Protocol Commitment Summary — Block `26401312`

- **Ethereum Mainnet Block**: `26401312` (`0x192da20`)
- **Canonical Block Hash**: `0x95866ea3ef8f9a0567ce000bc8075f6dc5fb0f1e80cb4e9999ae624a2f0dc109`
- **Block Timestamp**: `1794515987`
- **Scanner Seat**: `pacta-claude@dri.network` (`task-dfc7ce3ca53e`, dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`) + leader dual-RPC archive replay (`pacta-gemini@dri.network`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-cc0e35af1552` initial static proof-bundle decode; repaired archive reads verified via scanner/leader dual-RPC replay, while offline verifier performs static EIP-55, selector & quarantine review without live RPC calls)

## 1. Mellow Protocol / Lido Earn (`earnETH` `0x6a37725ca7f4CE81c004c955f7280d5C704a249e` & `earnUSD` `0x014e6DA8F283C4aF65B2AA0f201438680A004452`)
- **Curator Safe (`0xe5abcc40196174Ae0d12153dE286F0D8E401769d`)**: Live `getThreshold() = 3`, `getOwners().length = 5` (`3-of-5` Gnosis Safe) vs. `"3/6 multisig"` listed in `lidofinance/docs` (`earn/deployment-contracts.md` line 199).
- **Admin Role & Signer Overlap**: `DEFAULT_ADMIN_ROLE` (`0x00`) on `earnETH` (`0x6a37725ca7f4CE81c004c955f7280d5C704a249e`) and `earnUSD` (`0x014e6DA8F283C4aF65B2AA0f201438680A004452`) is held by `Lazy Vault Admin Safe` (`0x0Dd73341d6158a72b4D224541f1094188f57076E`, `5-of-8` Gnosis Safe, with `Timelock` `0x363Ba8843d06BA5968f55C26aB055162eDd62189` `getMinDelay() = 0`s), where all 5 `Curator Safe` signers are also owners on the `5-of-8` `Lazy Vault Admin Safe` (`1` public parameter drift recorded).

## 2. Convex Finance (`Booster` `0xF403C135812408BFbE8713b5A23a04b3D48AAE31`)
- **`owner()` Chain**: `Booster.owner()` (`0x8da5cb5b`) resolves to `0x3cE6408F923326f81A7D7929952947748180f1E6`, whose `owner()` resolves to `0x256e1bbA846611C37CF89844a02435E6C098b86D`, whose `owner()` resolves to `0xa3C5A1e09150B75ff251c1a7815A07182c3de2FB` (`3-of-5` Convex DAO Multisig); `Booster.feeManager()` (`0xd0fb0203`) resolves to `0xa3C5A1e09150B75ff251c1a7815A07182c3de2FB`.

> **Scope & Evidence Limit**: Sampled read-only getter/slot observations at the pinned block compared against cited documentation; does not certify protocol-wide authority completeness, downstream mutation semantics, or exploitability.
