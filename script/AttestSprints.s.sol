// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Minimal interface for Base EAS SchemaRegistry (0x4200000000000000000000000000000000000020)
interface ISchemaRegistry {
    function register(string calldata schema, address resolver, bool revocable) external returns (bytes32);
}

/// @notice Minimal interface for Base EAS (0x4200000000000000000000000000000000000021)
interface IEAS {
    struct AttestationRequestData {
        address recipient;
        uint64 expirationTime;
        bool revocable;
        bytes32 refUID;
        bytes data;
        uint256 value;
    }

    struct AttestationRequest {
        bytes32 schema;
        AttestationRequestData data;
    }

    function attest(AttestationRequest calldata request) external payable returns (bytes32);
}

/// @title AttestSprints
/// @notice Deterministic Base Mainnet (`chainId == 8453`) direct-EOA calldata builder for Sprints 1–6 public audit summaries.
///         Because EAS records `msg.sender` as the on-chain `attester`, transactions built by this helper are signed and
///         broadcast directly by Tier 2 `PACTA_ATTESTER_EOA` (`0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09`) to `BASE_SCHEMA_REGISTRY`
///         (`0x4200000000000000000000000000000000000020`) and `BASE_EAS` (`0x4200000000000000000000000000000000000021`), ensuring
///         `attester == PACTA_ATTESTER_EOA` on Base EAS. Schema and attestations are set `revocable = true` so `PACTA_ATTESTER_EOA`
///         can revoke/supersede any attestation if ever needed.
contract AttestSprints {
    error InvalidSprintId();
    error WrongChainId(uint256 actualChainId, uint256 expectedChainId);

    uint256 public constant BASE_MAINNET_CHAIN_ID = 8453;
    uint64 public constant ETH_MAINNET_CHAIN_ID = 1;

    address public constant BASE_SCHEMA_REGISTRY = 0x4200000000000000000000000000000000000020;
    address public constant BASE_EAS = 0x4200000000000000000000000000000000000021;
    address public constant PACTA_ATTESTER_EOA = 0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09;

    bytes4 public constant SELECTOR_REGISTER_SCHEMA = ISchemaRegistry.register.selector;
    bytes4 public constant SELECTOR_ATTEST = IEAS.attest.selector;

    string public constant PACTA_EAS_SCHEMA =
        "uint16 sprintId,uint64 chainId,uint64 blockNumber,bytes32 blockHash,uint8 verifiedCount,uint8 driftCount,bytes32 summarySha256,string prURI";

    // Canonical Ethereum Mainnet Block Numbers, Live-RPC Block Hashes, and Sanitized Summary SHA-256 Digests
    uint64 public constant SPRINT_1_BLOCK = 26399876;
    bytes32 public constant SPRINT_1_BLOCK_HASH = 0x8bf896b892683ff3267b88b367ab015a70cf5caf53542eb405f4f648f6bcde8a;
    bytes32 public constant SPRINT_1_SUMMARY_SHA256 = 0x4628df8585cf37a84d3a2084f778886e151e200e433c04a2aed47ad6f1f306b6;
    string public constant SPRINT_1_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/1";

    uint64 public constant SPRINT_2_BLOCK = 26400152;
    bytes32 public constant SPRINT_2_BLOCK_HASH = 0xa9a61622304ec55c5fec49abbcabec60069f66f28792cf841bdd7aef12ce63aa;
    bytes32 public constant SPRINT_2_SUMMARY_SHA256 = 0x257f475130f0602d3b0194457cd0ab0715f5dc4a8c76d25554bcb5ced72a211d;
    string public constant SPRINT_2_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/2";

    uint64 public constant SPRINT_3_BLOCK = 26401070;
    bytes32 public constant SPRINT_3_BLOCK_HASH = 0xcf55f6a42ae610c1f8766b5c2fb676d91f178469fa10ef777eccbb76f6506234;
    bytes32 public constant SPRINT_3_SUMMARY_SHA256 = 0x8ba8b87f8607fd2a890850568c7134db66717ef776165b9435ba4e8c8b2831c9;
    string public constant SPRINT_3_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/3";

    uint64 public constant SPRINT_4_BLOCK = 26401312;
    bytes32 public constant SPRINT_4_BLOCK_HASH = 0x95866ea3ef8f9a0567ce000bc8075f6dc5fb0f1e80cb4e9999ae624a2f0dc109;
    bytes32 public constant SPRINT_4_SUMMARY_SHA256 = 0xbbe35eeb93f9fe246c632d89c51ddee336daa332a5216535796800a5bae234a1;
    string public constant SPRINT_4_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/5";

    uint64 public constant SPRINT_5_BLOCK = 26401405;
    bytes32 public constant SPRINT_5_BLOCK_HASH = 0x26e155e1569d436406a52ecee31c94d8d8ef2ca4c45d82211a84c8c802be1510;
    bytes32 public constant SPRINT_5_SUMMARY_SHA256 = 0x091f660b0d23cd9275f6c88b564916876b6c6220390eb10a38db410c0c25d891;
    string public constant SPRINT_5_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/7";

    uint64 public constant SPRINT_6_BLOCK = 26401540;
    bytes32 public constant SPRINT_6_BLOCK_HASH = 0x49324aaf84b0ffd4e21026c5345272788bff377f0f86fcdb74280cdfc32a9641;
    bytes32 public constant SPRINT_6_SUMMARY_SHA256 = 0x12c1701a44b4d39f6adeb6f28bb5b391d04262a10652c975a912fccf989ac4c8;
    string public constant SPRINT_6_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/10";

    /// @notice Compute the canonical Base EAS Schema UID (`keccak256(abi.encodePacked(schema, resolver, revocable))`).
    function canonicalSchemaUID() public pure returns (bytes32) {
        return keccak256(abi.encodePacked(PACTA_EAS_SCHEMA, address(0), true));
    }

    /// @notice Enforce Base Mainnet (`chainId == 8453`) before building live transaction payloads.
    function requireBaseMainnet() public view {
        if (block.chainid != BASE_MAINNET_CHAIN_ID) {
            revert WrongChainId(block.chainid, BASE_MAINNET_CHAIN_ID);
        }
    }

    /// @notice Build direct-EOA unsigned transaction `(to, chainId, calldataBytes)` for `PACTA_ATTESTER_EOA` to register the schema on Base.
    function buildRegisterSchemaTx() external view returns (address to, uint256 chainId, bytes memory calldataBytes) {
        requireBaseMainnet();
        to = BASE_SCHEMA_REGISTRY;
        chainId = BASE_MAINNET_CHAIN_ID;
        calldataBytes = abi.encodeCall(ISchemaRegistry.register, (PACTA_EAS_SCHEMA, address(0), true));
    }

    /// @notice Return the pinned, quarantine-safe public attestation data payload for Sprint `sprintId` (1..6).
    function getPinnedSprintPayload(uint16 sprintId) public pure returns (bytes memory) {
        if (sprintId == 1) {
            return _encodeSprintAttestationData(1, ETH_MAINNET_CHAIN_ID, SPRINT_1_BLOCK, SPRINT_1_BLOCK_HASH, 4, 1, SPRINT_1_SUMMARY_SHA256, SPRINT_1_PR_URI);
        } else if (sprintId == 2) {
            return _encodeSprintAttestationData(2, ETH_MAINNET_CHAIN_ID, SPRINT_2_BLOCK, SPRINT_2_BLOCK_HASH, 4, 1, SPRINT_2_SUMMARY_SHA256, SPRINT_2_PR_URI);
        } else if (sprintId == 3) {
            return _encodeSprintAttestationData(3, ETH_MAINNET_CHAIN_ID, SPRINT_3_BLOCK, SPRINT_3_BLOCK_HASH, 3, 0, SPRINT_3_SUMMARY_SHA256, SPRINT_3_PR_URI);
        } else if (sprintId == 4) {
            return _encodeSprintAttestationData(4, ETH_MAINNET_CHAIN_ID, SPRINT_4_BLOCK, SPRINT_4_BLOCK_HASH, 4, 1, SPRINT_4_SUMMARY_SHA256, SPRINT_4_PR_URI);
        } else if (sprintId == 5) {
            return _encodeSprintAttestationData(5, ETH_MAINNET_CHAIN_ID, SPRINT_5_BLOCK, SPRINT_5_BLOCK_HASH, 3, 2, SPRINT_5_SUMMARY_SHA256, SPRINT_5_PR_URI);
        } else if (sprintId == 6) {
            return _encodeSprintAttestationData(6, ETH_MAINNET_CHAIN_ID, SPRINT_6_BLOCK, SPRINT_6_BLOCK_HASH, 4, 1, SPRINT_6_SUMMARY_SHA256, SPRINT_6_PR_URI);
        }
        revert InvalidSprintId();
    }

    /// @notice Build direct-EOA unsigned transaction `(to, chainId, schemaUID, calldataBytes)` for `PACTA_ATTESTER_EOA` to attest Sprint `sprintId` directly to `BASE_EAS`.
    function buildAttestSprintTx(uint16 sprintId) external view returns (address to, uint256 chainId, bytes32 schemaUID, bytes memory calldataBytes) {
        requireBaseMainnet();
        to = BASE_EAS;
        chainId = BASE_MAINNET_CHAIN_ID;
        schemaUID = canonicalSchemaUID();
        bytes memory payload = getPinnedSprintPayload(sprintId);
        IEAS.AttestationRequest memory req = IEAS.AttestationRequest({
            schema: schemaUID,
            data: IEAS.AttestationRequestData({
                recipient: PACTA_ATTESTER_EOA,
                expirationTime: 0,
                revocable: true,
                refUID: bytes32(0),
                data: payload,
                value: 0
            })
        });
        calldataBytes = abi.encodeCall(IEAS.attest, (req));
    }

    function _encodeSprintAttestationData(
        uint16 sprintId,
        uint64 chainId,
        uint64 blockNumber,
        bytes32 blockHash,
        uint8 verifiedCount,
        uint8 driftCount,
        bytes32 summarySha256,
        string memory prURI
    ) internal pure returns (bytes memory) {
        return abi.encode(
            sprintId,
            chainId,
            blockNumber,
            blockHash,
            verifiedCount,
            driftCount,
            summarySha256,
            prURI
        );
    }
}
