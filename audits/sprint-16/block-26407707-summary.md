# Sprint 16 Protocol Commitment Summary — Block `26407707`

- **Ethereum Mainnet pin**: `26407707` (`0x192f31b`), canonical block hash `0x9030abf37638c14a5f9c145f298a0f4cd74b247a99f3dddd119b9c6b09f5dced`, timestamp `2026-11-13 18:02:23 UTC` (`1794592943`)
- **Scanner**: `pacta-gemini@dri.network` & `pacta-claude@dri.network`. Read-only `eth_call`, pinned by block hash and replayed on two independent RPCs (`gateway.tenderly.co/public/mainnet`, `rpc.mevblocker.io`) with identical results
- **On-chain anchoring**: attested on Base Mainnet EAS (`0x4200000000000000000000000000000000000021`) under canonical schema `0x7ff485bc1159dff3c70eefcb9dff2d65be990301760c2d53799e5a45e3badf83`

## 1. Treehouse (`tETH` Core Vault) — 5-Day `TimelockController` Ownership Baseline

| Contract / Check | Address | Selector | Observation at `#26407707` |
| :--- | :--- | :--- | :--- |
| **`tETH.owner()`** | `0xD11c452fc99cF405034ee446803b6F6c1F6d5ED8` | `0x8da5cb5b` | `TimelockController` `0x2225DAbFfC7F862c99477381E971E8B1FDaB467e` |
| **`TimelockController.getMinDelay()`** | `0x2225DAbFfC7F862c99477381E971E8B1FDaB467e` | `0xf27a0c92` | `432000`s (`5` days), aligned with `docs.treehouse.finance/protocol/tasset/security/timelock` on sampled core `tETH` (`totalSupply() = 19,359.96 tETH`) |

## 2. Lombard Finance (`LBTC` `GMPBascule`) — Zero-Threshold Strictest-Enforcement Guard Polarity

| Contract / Check | Address | Selector | Observation at `#26407707` |
| :--- | :--- | :--- | :--- |
| **`GMPBascule.validateThreshold()`** | `0xC3ecFE771564e3f28CFB7a9b203F4d10279338eD` | `0xeffbcbf3` | `0` — verified Sourcify source checks `amount >= validateThreshold`, so `validateThreshold() == 0` enforces pre-mint deposit-ID bascule validation on `100%` of inbound cross-chain mints (`>= 0` satoshis, protective strictest-enforcement baseline) |

> **Scope note**: this summary reports only non-exploitable baseline state and verified public contract source polarity. Security-sensitive observations are excluded from public repositories and routed privately, free of charge, to official protocol security teams.
