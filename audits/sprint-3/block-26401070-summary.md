# Sprint 3 Protocol Commitment Summary — Block `26401070`

- **Ethereum Mainnet Block**: `26401070` (`0x192d92e`)
- **Canonical Block Hash**: `0xcf55f6a42ae610c1f8766b5c2fb676d91f178469fa10ef777eccbb76f6506234`
- **Block Timestamp**: `1794513083`
- **Scanner Seat**: `pacta-claude@dri.network` (dual-RPC replay across `gateway.tenderly.co` and `rpc.mevblocker.io`, `exit 0`)
- **Independent Verifier Review**: `pacta-codex@dri.network` (`task-cc0bbf599968`, static proof-bundle & decode review)

## 1. ether.fi Liquid / Veda BoringVault
- **`AccountantWithRateProviders` (`0x0d05D94a5F1E76C18fbeB7A13d17C8a314088198`) & `RolesAuthority` (`0x4483321e3D3A34100C226259B7898602cC792E28`)**:
  - `doesRoleHaveCapability(9, 0x0d05D94a5F1E76C18fbeB7A13d17C8a314088198, 0xc10af4c7)` (`updateManagementFee(uint16)`) returns `true`.
  - Role `9` is held by `TimelockController` (`0x9F26d4C958fD811A1F59B01B86Be7dFFc9d20761`, `getMinDelay() = 259200` seconds / 3 days), proposed by `Liquid Scheduler Safe` (`0xCEA8039076E35a825854c5C2f85659430b06ec96`, `4-of-9`).

## 2. Morpho Blue Core & Prisma Finance
- **Morpho Blue Core (`0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb`)**: Sampled fee, owner, and LLTV parameters match public documentation at block `26401070`.
