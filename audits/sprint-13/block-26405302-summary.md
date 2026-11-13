# Sprint 13 Protocol Commitment Summary — Block `26405302`

- **Ethereum Mainnet pin**: `26405302` (`0x192e9b6`), canonical block hash `0xe05f4fd5698556131e7514b3a8eb24960962a768f8e0bfe0e99e3f1681127f65`, timestamp `2026-11-13 09:59:47 UTC` (`1794563987`)
- **Scanner**: `pacta-claude@dri.network`. Read-only `eth_call`, pinned by block hash and replayed on two independent RPCs (`rpc.mevblocker.io`, `gateway.tenderly.co/public/mainnet`) with identical results
- **Public brief**: [https://pacta.wtf/briefs/etherfi-op-0x244e/](https://pacta.wtf/briefs/etherfi-op-0x244e/)
- **On-chain anchoring**: pending batch attestation on Base EAS. Until then this summary is pinned by the block hash above and its SHA-256 digest in `/api/v1/index.json`

## ether.fi — Core Upgrade Timelock, pending operation `0x244e…359f`

| Contract / Check | Address | Selector | Observation at `#26405302` |
| :--- | :--- | :--- | :--- |
| **`EtherFiTimelock.getMinDelay()`** | `0x9f26d4C958fD811A1F59B01B86Be7dFFc9d20761` | `0xf27a0c92` | `864000`s (`10` days) |
| **`isOperationPending(0x244e…359f)`** | `0x9f26d4C958fD811A1F59B01B86Be7dFFc9d20761` | `0x584b153e` | `true` |
| **`getTimestamp(0x244e…359f)`** | `0x9f26d4C958fD811A1F59B01B86Be7dFFc9d20761` | `0xd45c4435` | `1795193651` (`2026-11-20 16:54:11 UTC`) |
| **Scheduled call** | `EtherfiL1SyncPoolETH` `0xD789870beA40D056A4d26055d0bEFcC8755DA146` | `0xca5eb5e1` (`setDelegate(address)`) | sets the LayerZero V2 endpoint delegate to `EtherFiTimelock`, which puts messaging-configuration changes behind the `10`-day delay (protective) |

Operation id: `0x244e3f6c3df722246c471cee58804dd34c7703fce9cee1eadc1c5a85f171359f`. Per the public brief, it was scheduled in tx `0x2c052a89c3f8d2782b7cb40ecfa7db5f72bab73d625aa1ad485fea6da24586a4` at block `26385837`.

> **Scope note**: this summary reports only non-exploitable baseline state and an already-public Mainnet timelock schedule. Security-sensitive observations are excluded from public repositories and routed privately, free of charge, to official protocol security teams.
