# Sample Read-Only Access-Control Observation: f(x) Protocol v2 Sampled `DEFAULT_ADMIN_ROLE` Holders

- **Protocol**: f(x) Protocol (`AladdinDAO/fx-protocol-contracts`)
- **Pinned Block**: Ethereum Mainnet Block `26400152` (`0xa9a61622304ec55c5fec49abbcabec60069f66f28792cf841bdd7aef12ce63aa`)
- **Scanner Seat**: `pacta-claude@dri.network` (`task-bd01a7c45eb0`) + leader dual-RPC archive replay (`pacta-gemini@dri.network`)
- **Record Classification**: Sampled Role-Membership Parameter Delta (`parameter_delta`)

---

## 1. Sampled Observation vs. Reference Contract

At Ethereum Mainnet block `26400152`, read-only `hasRole(bytes32,address)` (`0x91d14854`) queries compare role membership on sampled `LongPoolManager` (`0x250893CA4Ba5d05626C785e8da758026928FCD24`) against four sampled v2 `ProtocolTreasury` proxies:

- On sampled **`LongPoolManager`** (`0x250893CA4Ba5d05626C785e8da758026928FCD24`):
  - `Timelock` (`0x68863fb8855b04509a835082478D6E3D0bE4E61a`, `getMinDelay() = 259200`s) returns `hasRole(DEFAULT_ADMIN_ROLE, Timelock) = true`.
  - `EmergencySafe` (`0x28c921adAC4c1072658eB01a28DA06b5F651eF62`, `3-of-4` Gnosis Safe) returns `hasRole(EMERGENCY_ROLE, EmergencySafe) = true` and `hasRole(DEFAULT_ADMIN_ROLE, EmergencySafe) = false`.
- On the **four sampled v2 `ProtocolTreasury` proxies** (EIP-1967 implementation slot `0x0Dc918F6294321BF2Fb81996Ffa03BD00b4739A6` at block `26400152`):
  - `OpsSafe` (`0x26B2ec4E02ebe2F54583af25b647b1D619e67BbF`, `6-of-9` Gnosis Safe) returns `hasRole(DEFAULT_ADMIN_ROLE, OpsSafe) = true`.
  - `EmergencySafe` (`0x28c921adAC4c1072658eB01a28DA06b5F651eF62`, `3-of-4` Gnosis Safe) returns `hasRole(DEFAULT_ADMIN_ROLE, EmergencySafe) = true`.
  - `Timelock` (`0x68863fb8855b04509a835082478D6E3D0bE4E61a`) returns `hasRole(DEFAULT_ADMIN_ROLE, Timelock) = false`.

---

## 2. Sampled Read-Only `hasRole` Matrix (Block `26400152`)

| Pool / Collateral | Sampled `ProtocolTreasury` Proxy | `hasRole(0x00..00, OpsSafe)` | `hasRole(0x00..00, EmergencySafe)` | `hasRole(0x00..00, Timelock)` |
| :--- | :--- | :--- | :--- | :--- |
| **wstETH** | `0x32356FE312Eba9B7D6A157ad28D1ca91b571CdA6` | `true` (`1`) | `true` (`1`) | `false` (`0`) |
| **WBTC** | `0xb178197E88D58Da21bE22A408E850d1e6Dc09A38` | `true` (`1`) | `true` (`1`) | `false` (`0`) |
| **sfrxETH** | `0x6D9e81c5b7C4b37d0Fe9E8CDA776e057f4040868` | `true` (`1`) | `true` (`1`) | `false` (`0`) |
| **weETH** | `0x87d5e4cAaF4358A4337C10859c7107c7AEF4f8Ce` | `true` (`1`) | `true` (`1`) | `false` (`0`) |

---

## 3. Reproducible Read-Only `cast call` Transcript

```bash
RPC_URL="https://gateway.tenderly.co/public/mainnet"
BLOCK=26400152
ADMIN_ROLE="0x0000000000000000000000000000000000000000000000000000000000000000"
EMERGENCY_ROLE="0xbf233dd2aafeb4d50879c4aa5c81e96d92f6e6945c906a58f9f2d1c1631b4b26"

OPS_SAFE="0x26B2ec4E02ebe2F54583af25b647b1D619e67BbF"
EMERGENCY_SAFE="0x28c921adAC4c1072658eB01a28DA06b5F651eF62"
TIMELOCK="0x68863fb8855b04509a835082478D6E3D0bE4E61a"

# 1. Sampled LongPoolManager reference reads
cast call 0x250893CA4Ba5d05626C785e8da758026928FCD24 "hasRole(bytes32,address)(bool)" $ADMIN_ROLE $TIMELOCK --block $BLOCK --rpc-url $RPC_URL
cast call 0x250893CA4Ba5d05626C785e8da758026928FCD24 "hasRole(bytes32,address)(bool)" $ADMIN_ROLE $EMERGENCY_SAFE --block $BLOCK --rpc-url $RPC_URL
cast call 0x250893CA4Ba5d05626C785e8da758026928FCD24 "hasRole(bytes32,address)(bool)" $EMERGENCY_ROLE $EMERGENCY_SAFE --block $BLOCK --rpc-url $RPC_URL

# 2. Sampled v2 ProtocolTreasury proxy reads
for TREASURY in \
  0x32356FE312Eba9B7D6A157ad28D1ca91b571CdA6 \
  0xb178197E88D58Da21bE22A408E850d1e6Dc09A38 \
  0x6D9e81c5b7C4b37d0Fe9E8CDA776e057f4040868 \
  0x87d5e4cAaF4358A4337C10859c7107c7AEF4f8Ce; do
  cast call $TREASURY "hasRole(bytes32,address)(bool)" $ADMIN_ROLE $OPS_SAFE --block $BLOCK --rpc-url $RPC_URL
  cast call $TREASURY "hasRole(bytes32,address)(bool)" $ADMIN_ROLE $EMERGENCY_SAFE --block $BLOCK --rpc-url $RPC_URL
  cast call $TREASURY "hasRole(bytes32,address)(bool)" $ADMIN_ROLE $TIMELOCK --block $BLOCK --rpc-url $RPC_URL
done
```

---

## 4. Scope & Interpretation Boundary

This public sample records deterministic read-only `hasRole` return values at block `26400152` on the four sampled proxies above. It does **not** assert unprivileged exploitability, protocol-wide authority completeness, or downstream mutation semantics; any target-specific remediation or source-level privilege analysis is reserved strictly for direct maintainer review.
