# On-Chain Access-Control Verification: v2 `ProtocolTreasury` `DEFAULT_ADMIN_ROLE` Retention (`FX3`)

- **Protocol**: f(x) Protocol (`AladdinDAO/fx-protocol-contracts`)
- **Pinned Block**: Ethereum Mainnet Block `26400152` (`0xa9a61622304ec55c5fec49abbcabec60069f66f28792cf841bdd7aef12ce63aa`)
- **Auditor**: Pacta — Protocol Commitments DRI ([Fractal Neurons](https://fractalneurons.com)) · `pacta@dri.network`
- **Category**: Governance & Access-Control Drift (`confirmed_material`)

---

## 1. Summary

In f(x) Protocol v2, the core pool managers (`LongPoolManager` `0x250893CA4Ba5d05626C785e8da758026928FCD24` and `ShortPoolManager` `0xaCDc0AB51178d0Ae8F70c1EAd7d3cF5421FDd66D`) enforce a clear separation of powers:
- The `Timelock` (`0x68863fb8855b04509a835082478D6E3D0bE4E61a`) holds `DEFAULT_ADMIN_ROLE` (`0x0000000000000000000000000000000000000000000000000000000000000000`).
- The 3-of-4 `EmergencySafe` (`0x28c921adAC4c1072658eB01a28DA06b5F651eF62`) is scoped exclusively to `EMERGENCY_ROLE` (`keccak256("EMERGENCY_ROLE")` = `0xbf233dd2aafeb4d50879c4aa5c81e96d92f6e6945c906a58f9f2d1c1631b4b26`) and does **not** hold `DEFAULT_ADMIN_ROLE`.

However, on all **four live v2 `ProtocolTreasury` proxies** (implementation `0x0DC918f6294321bf2fb81996FFa03bD00b4739A6`), `DEFAULT_ADMIN_ROLE` is currently held directly by both the 6-of-9 `OpsSafe` (`0x26B2ec4E02ebe2F54583af25b647b1D619e67BbF`) and the 3-of-4 `EmergencySafe` (`0x28c921adAC4c1072658eB01a28DA06b5F651eF62`), while the `Timelock` (`0x68863fb8855b04509a835082478D6E3D0bE4E61a`) holds `0` (`false`).

Because `ProtocolTreasury` inherits `PermissionedSwap.withdraw(address baseToken, address recipient)` gated by `onlyRole(DEFAULT_ADMIN_ROLE)` (`contracts/periphery/swap/PermissionedSwap.sol`), holding `DEFAULT_ADMIN_ROLE` on these four proxies grants direct role-administration (`grantRole`/`revokeRole` over `HARVESTER_ROLE` and `SETTLEMENT_ROLE`), strategy updates, and `PermissionedSwap.withdraw(...)` execution to the 3-of-4 `EmergencySafe` without Timelock delay.

---

## 2. Affected v2 `ProtocolTreasury` Contracts (Block `26400152`)

| Pool / Collateral | `ProtocolTreasury` Proxy | Implementation | `hasRole(0x00..00, OpsSafe)` | `hasRole(0x00..00, EmergencySafe)` | `hasRole(0x00..00, Timelock)` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **wstETH** | `0x32356FE312Eba9B7D6A157ad28D1ca91b571CdA6` | `0x0DC918f6294321bf2fb81996FFa03bD00b4739A6` | `true` (`1`) | `true` (`1`) | `false` (`0`) |
| **WBTC** | `0xb178197E88D58Da21bE22A408E850d1e6Dc09A38` | `0x0DC918f6294321bf2fb81996FFa03bD00b4739A6` | `true` (`1`) | `true` (`1`) | `false` (`0`) |
| **sfrxETH** | `0x6D9e81c5b7C4b37d0Fe9E8CDA776e057f4040868` | `0x0DC918f6294321bf2fb81996FFa03bD00b4739A6` | `true` (`1`) | `true` (`1`) | `false` (`0`) |
| **weETH** | `0x87d5e4cAaF4358A4337C10859c7107c7AEF4f8Ce` | `0x0DC918f6294321bf2fb81996FFa03bD00b4739A6` | `true` (`1`) | `true` (`1`) | `false` (`0`) |

---

## 3. Deterministic Reproduction (`cast`)

```bash
# Pinned block: 26400152
RPC_URL="https://eth.drpc.org"
BLOCK=26400152
ADMIN_ROLE="0x0000000000000000000000000000000000000000000000000000000000000000"
EMERGENCY_ROLE="0xbf233dd2aafeb4d50879c4aa5c81e96d92f6e6945c906a58f9f2d1c1631b4b26"

OPS_SAFE="0x26B2ec4E02ebe2F54583af25b647b1D619e67BbF"
EMERGENCY_SAFE="0x28c921adAC4c1072658eB01a28DA06b5F651eF62"
TIMELOCK="0x68863fb8855b04509a835082478D6E3D0bE4E61a"

# 1. Contrast: LongPoolManager (0x250893CA4Ba5d05626C785e8da758026928FCD24)
# Timelock holds DEFAULT_ADMIN_ROLE (true); EmergencySafe holds only EMERGENCY_ROLE (true) and NOT DEFAULT_ADMIN_ROLE (false)
cast call 0x250893CA4Ba5d05626C785e8da758026928FCD24 "hasRole(bytes32,address)(bool)" $ADMIN_ROLE $TIMELOCK --block $BLOCK --rpc-url $RPC_URL
cast call 0x250893CA4Ba5d05626C785e8da758026928FCD24 "hasRole(bytes32,address)(bool)" $ADMIN_ROLE $EMERGENCY_SAFE --block $BLOCK --rpc-url $RPC_URL
cast call 0x250893CA4Ba5d05626C785e8da758026928FCD24 "hasRole(bytes32,address)(bool)" $EMERGENCY_ROLE $EMERGENCY_SAFE --block $BLOCK --rpc-url $RPC_URL

# 2. Verify all 4 v2 ProtocolTreasury proxies
for TREASURY in \
  0x32356FE312Eba9B7D6A157ad28D1ca91b571CdA6 \
  0xb178197E88D58Da21bE22A408E850d1e6Dc09A38 \
  0x6D9e81c5b7C4b37d0Fe9E8CDA776e057f4040868 \
  0x87d5e4cAaF4358A4337C10859c7107c7AEF4f8Ce; do
  echo "=== ProtocolTreasury: $TREASURY ==="
  echo -n "OpsSafe DEFAULT_ADMIN_ROLE:       "
  cast call $TREASURY "hasRole(bytes32,address)(bool)" $ADMIN_ROLE $OPS_SAFE --block $BLOCK --rpc-url $RPC_URL
  echo -n "EmergencySafe DEFAULT_ADMIN_ROLE: "
  cast call $TREASURY "hasRole(bytes32,address)(bool)" $ADMIN_ROLE $EMERGENCY_SAFE --block $BLOCK --rpc-url $RPC_URL
  echo -n "Timelock DEFAULT_ADMIN_ROLE:      "
  cast call $TREASURY "hasRole(bytes32,address)(bool)" $ADMIN_ROLE $TIMELOCK --block $BLOCK --rpc-url $RPC_URL
done
```

---

## 4. Recommended Remediation

To align the four v2 `ProtocolTreasury` proxies with `LongPoolManager` and `ShortPoolManager`:
1. Grant `DEFAULT_ADMIN_ROLE` (`0x00..00`) to `Timelock` (`0x68863fb8855b04509a835082478D6E3D0bE4E61a`) where timelocked admin governance is intended.
2. Revoke `DEFAULT_ADMIN_ROLE` (`0x00..00`) from `EmergencySafe` (`0x28c921adAC4c1072658eB01a28DA06b5F651eF62`) across all four `ProtocolTreasury` proxies (`0x3235...CdA6`, `0xb178...9A38`, `0x6D9e...0868`, `0x87d5...f8Ce`), scoping emergency signers strictly to `EMERGENCY_ROLE` on pool managers.
