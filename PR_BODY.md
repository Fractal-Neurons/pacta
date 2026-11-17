## Fixture file

- Fixture: bounties/submissions/slot-1-stake-dao.json (exactly one JSON fixture per PR; keys in bounties/submissions/README.md)
  Check it with: python3 tools/verify_bounty_submission.py --json bounties/submissions/slot-1-stake-dao.json

## Bounty slot

- Slot: 1
- Issue: https://github.com/Fractal-Neurons/pacta/issues/21

## 1. chainId & contract address

- chainId: 1
- Contract address: 0xF930EBBd05eF8b25B1797b9b2109DDC9B0d43063
- Protocol: Stake DAO (Ethereum treasury Safe)
- TVL reference: https://defillama.com/protocol/stake-dao
- TVL note: DefiLlama currentChainTvls.Ethereum = $110,648,830 (>= $25M, Slot #1 threshold)
- Pacta slug: n/a

## 2. Pinned finalized block

- blockNumber: 26422051
- blockHash: 0x8eec7b2bd49efecd252ea631e8800a8159eae4c81b74f3c745e27537519ae7d0
- Prior Pacta pin: n/a

## 3. Deterministic dual-RPC cast proof

```bash
cast call 0xF930EBBd05eF8b25B1797b9b2109DDC9B0d43063 "getThreshold()" --block 26422051 --rpc-url https://ethereum-rpc.publicnode.com
cast call 0xF930EBBd05eF8b25B1797b9b2109DDC9B0d43063 "getThreshold()" --block 26422051 --rpc-url https://eth.drpc.org
cast storage 0xF930EBBd05eF8b25B1797b9b2109DDC9B0d43063 4 --block 26422051 --rpc-url https://ethereum-rpc.publicnode.com
cast storage 0xF930EBBd05eF8b25B1797b9b2109DDC9B0d43063 4 --block 26422051 --rpc-url https://eth.drpc.org
```

- RPC A output: getThreshold() = 0x0000000000000000000000000000000000000000000000000000000000000003 (3); eth_getStorageAt slot 3 (ownerCount) = 0x0000000000000000000000000000000000000000000000000000000000000005 (5); eth_getStorageAt slot 4 (threshold) = 0x0000000000000000000000000000000000000000000000000000000000000003 (3); getOwners() = [0xf2875cb91c35e0ddc9b76b15e2aae236d393efff, 0xe3268adb23043b3acc7083e96912aeeb4feb4df2, 0x07c2d0e24530199e2c9a15bfed4496d8e3798003, 0x4046b37ffc36b0c723d7fc64e0c763b698d81934, 0xeb9f416fa098697d95e70b20439f19097eb741ed]
- RPC B output: getThreshold() = 0x0000000000000000000000000000000000000000000000000000000000000003 (3); eth_getStorageAt slot 3 (ownerCount) = 0x0000000000000000000000000000000000000000000000000000000000000005 (5); eth_getStorageAt slot 4 (threshold) = 0x0000000000000000000000000000000000000000000000000000000000000003 (3); getOwners() = [0xf2875cb91c35e0ddc9b76b15e2aae236d393efff, 0xe3268adb23043b3acc7083e96912aeeb4feb4df2, 0x07c2d0e24530199e2c9a15bfed4496d8e3798003, 0x4046b37ffc36b0c723d7fc64e0c763b698d81934, 0xeb9f416fa098697d95e70b20439f19097eb741ed]

## 4. Live official documentation claim (HTTP 200)

- Docs URL: https://docs.stakedao.org/treasury
- Verbatim quote: "The Stake DAO treasury holds protocol-owned assets across multiple chains. All wallets use a 4-of-7 multisig structure." (the same page's table lists this Ethereum treasury address)

## 5. Pacta MCP output

```json
{
  "schema": "pacta.protocol_lookup.v1",
  "query": "Stake DAO",
  "totalMatches": 0,
  "count": 0,
  "results": [],
  "totalCatalog": {
    "protocols": 62,
    "briefs": 8
  },
  "catalog": "https://pacta.wtf/api/v1/lookup.json"
}
```

## 6. Apache-2.0 contribution & commercialization grant

- [x] I grant Pacta by Fractal Neurons perpetual, irrevocable rights under Apache-2.0 to ingest, Base EAS-attest, publish on pacta.wtf, and commercialize this merged mismatch record.

## Rules

- [x] This is my only open bounty PR (max 1 open PR per contributor across all slots).
- [x] Every RPC output above is real, pinned to the block above, and reproducible on 2 independent endpoints (no AI-generated or fabricated values).
- [x] I have not opened PRs, issues or comments in any third-party repository on Pacta's behalf.
- [x] This PR contains no exploit PoC: it reports a governance / documentation parameter mismatch only.
