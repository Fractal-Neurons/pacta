# Sprint 3 On-Chain Commitment Verification Summary (Block `26401070`)

- **Pinned Block**: Ethereum Mainnet `26401070` (`0xcf55f6a42ae610c1f8766b5c2fb676d91f178469fa10ef777eccbb76f6506234`)
- **Cross-RPC Verification**: Replayed identically across `gateway.tenderly.co` and `rpc.mevblocker.io` (`exit 0`)
- **Independent Verifier Gate**: Verified by `pacta-codex` (`task-cc0bbf599968`, `DONE`)

## 1. ether.fi Liquid / Veda BoringVault (`etherfi-protocol/smart-contracts#505`)
- **Verified `Accountant` & `RolesAuthority` Configuration (`EL1`)**:
  - `Liquid ETH AccountantWithRateProviders` (`0x0d05D94a5F1E76C18fbeB7A13d17C8a314088198`): `updateManagementFee(uint16)` (`0xc10af4c7`) ceiling `0.2e4` (`20%`); live fee within `0%–2%`.
  - `Liquid BTC AccountantWithRateProviders` (`0xEa23aC6D7D11f6b181d6B98174D334478ADAe6b0`): `updatePerformanceFee(uint16)` (`0x709ac1c3`) ceiling `50%`; live fee within documented bounds.
  - `RolesAuthority` (`0x485Bde66Bb668a51f2372E34e45B1c6226798122` ETH, `0x49F954c67ff235034b69b8a59fbe309A40256c8d` BTC): `role 8` held by 1-day Timelock (`0xD829F278016b90FEc735F9A12Bf8b75E06102C89`), `role 55` held by `2-of-4` Safe (`0x607d0C7e3578802Eb46D388cb86cfba8Ff657306`).
- **Quarantined Security Findings (`EL2` & `EL3` — `disclosure_only`)**: Withheld from public files and provided **at no cost (`$0`)** via `pacta@dri.network`.

## 2. Frax Finance (`frxGov` Comptroller Safes — `FraxFinance/docs#192`)
- **Main Comptroller Safe (`0xB1748C79709f4Ba2Dd82834B8c82D4a505003f27`)**: `3-of-5` Safe (`guard = 0x0`, `modules = []`), owner of AMO Minter (`0xcf37B62109b537fa0Cb9A90Af4CA72f6fb85E241`, `700M FRAX` mint cap).
- **`frxETH` Comptroller Safe (`0x8306300ffd616049FD7e4b0354a64Da835c1A81C`)**: `4-of-7` Safe (`guard = 0x0`, `modules = []`).
- **Fraxlend Comptroller Safe (`0x168200cF227D4543302686124ac28aE0eaf2cA0B`)**: `3-of-6` Safe (`guard = 0x0`, `modules = []`); block-`23041646` provenance trace (`FR1`) available **at no cost (`$0`)** via `pacta@dri.network`.

## 3. Euler V2 (`eIP-62` Frontier Vaults — `EU1`)
- **Aggregate `GovSetGovernorAdmin` Check (Block `26236508` / `26401070`)**: 49 `GovSetGovernorAdmin` events switching 40 Frontier vaults directly to `4-of-8` Safe `0xcAD001c30E96765aC90307669d578219D4fb1DCe` and 9 vaults to `2`-threshold Safe `0x7945...bb8e`. Individual vault addresses are redacted and provided **at no cost (`$0`)** via `pacta@dri.network`.
