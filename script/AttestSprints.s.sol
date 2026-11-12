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
/// @notice Deterministic Base EAS schema registration and Sprints 1–6 public audit attestation helper
///         gated strictly to Tier 2 Pacta Attester EOA (0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09).
///         Attests only pinned public Sprint summary SHA-256 digests, block numbers, block hashes, and
///         allowlisted Fractal-Neurons/pacta PR URIs (zero quarantined findings or arbitrary caller strings).
contract AttestSprints {
    error OnlyPactaAttester();
    error InvalidSprintId();
    error ZeroSchemaUID();

    address public constant BASE_SCHEMA_REGISTRY = 0x4200000000000000000000000000000000000020;
    address public constant BASE_EAS = 0x4200000000000000000000000000000000000021;
    address public constant PACTA_ATTESTER_EOA = 0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09;

    /// @notice Exact 4-byte selectors verified against Base EAS contracts:
    ///         ISchemaRegistry.register(string,address,bool) = 0x60d7a278
    ///         IEAS.attest((bytes32,(address,uint64,bool,bytes32,bytes,uint256))) = 0xf17325e7
    bytes4 public constant SELECTOR_REGISTER_SCHEMA = ISchemaRegistry.register.selector;
    bytes4 public constant SELECTOR_ATTEST = IEAS.attest.selector;

    string public constant PACTA_EAS_SCHEMA =
        "uint16 sprintId,uint64 chainId,uint64 blockNumber,bytes32 blockHash,uint8 verifiedCount,uint8 driftCount,bytes32 summarySha256,string prURI";

    // Pinned Sprint 1–6 Public Summary Constants (Ethereum Mainnet chainId = 1)
    uint64 public constant ETH_MAINNET_CHAIN_ID = 1;

    uint64 public constant SPRINT_1_BLOCK = 26399876;
    bytes32 public constant SPRINT_1_BLOCK_HASH = 0x875e56f9e536e2ff3623fc60fa8ef287e91cd9780ab3582c31ef8c40763e4a97;
    bytes32 public constant SPRINT_1_SUMMARY_SHA256 = 0x62884edf21f6fc48bb96f9f39e4721b2238a2b360d4a90e13927f5c4285930ac;
    string public constant SPRINT_1_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/1";

    uint64 public constant SPRINT_2_BLOCK = 26400152;
    bytes32 public constant SPRINT_2_BLOCK_HASH = 0x5f38fa687a57007c62e8fd9f28b00a9b97fb9594c059ca1f2f95f97b044a3c7e;
    bytes32 public constant SPRINT_2_SUMMARY_SHA256 = 0x614235fb4808560338e894f1c033b9930a116a2650248d64cdf3d77b6410b367;
    string public constant SPRINT_2_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/2";

    uint64 public constant SPRINT_3_BLOCK = 26401070;
    bytes32 public constant SPRINT_3_BLOCK_HASH = 0xf3e40d9cd14bc3f463480660c910717a55b7010f67948421a9f189165d3b2191;
    bytes32 public constant SPRINT_3_SUMMARY_SHA256 = 0x9c02132d30514fc23e43ceac25d91d7973cdef78370996cc1e3820c517c64d4b;
    string public constant SPRINT_3_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/3";

    uint64 public constant SPRINT_4_BLOCK = 26401312;
    bytes32 public constant SPRINT_4_BLOCK_HASH = 0x1706679d24a9483b7444a428b517f086407cf6218b35e7dc5997b329b3fc5bb2;
    bytes32 public constant SPRINT_4_SUMMARY_SHA256 = 0xdde89d7b9bd5016b771d7e5b8433873256aa278caeeb30c7cf27098ff72a82ba;
    string public constant SPRINT_4_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/5";

    uint64 public constant SPRINT_5_BLOCK = 26401405;
    bytes32 public constant SPRINT_5_BLOCK_HASH = 0x413627fb0e52f093c4ffea753f64f8a224d86bb7f8eb90d73766c963f6f0fb48;
    bytes32 public constant SPRINT_5_SUMMARY_SHA256 = 0x5e25e1d3a77ca0ec952e68ce76676bbe175740b08e8c3b6b51fd9a77d936f5ba;
    string public constant SPRINT_5_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/7";

    uint64 public constant SPRINT_6_BLOCK = 26401540;
    bytes32 public constant SPRINT_6_BLOCK_HASH = 0x49324aaf84b0ffd4e21026c5345272788bff377f0f86fcdb74280cdfc32a9641;
    bytes32 public constant SPRINT_6_SUMMARY_SHA256 = 0x0bfd9b4a83c6b05d1ff52cdc6efb3b540c8d8ccc87a18b9dda24e3b204c73dc7;
    string public constant SPRINT_6_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/10";

    modifier onlyPactaAttester() {
        if (msg.sender != PACTA_ATTESTER_EOA) revert OnlyPactaAttester();
        _;
    }

    /// @notice Register the canonical Pacta EAS schema on Base SchemaRegistry (callable strictly by PACTA_ATTESTER_EOA).
    function registerSchema() external onlyPactaAttester returns (bytes32) {
        return ISchemaRegistry(BASE_SCHEMA_REGISTRY).register(PACTA_EAS_SCHEMA, address(0), false);
    }

    /// @notice Return the pinned, quarantine-safe public attestation payload for Sprint `sprintId` (1..6).
    function getPinnedSprintPayload(uint16 sprintId) public pure returns (bytes memory) {
        if (sprintId == 1) {
            return _encodeSprintAttestationData(1, ETH_MAINNET_CHAIN_ID, SPRINT_1_BLOCK, SPRINT_1_BLOCK_HASH, 6, 4, SPRINT_1_SUMMARY_SHA256, SPRINT_1_PR_URI);
        } else if (sprintId == 2) {
            return _encodeSprintAttestationData(2, ETH_MAINNET_CHAIN_ID, SPRINT_2_BLOCK, SPRINT_2_BLOCK_HASH, 6, 3, SPRINT_2_SUMMARY_SHA256, SPRINT_2_PR_URI);
        } else if (sprintId == 3) {
            return _encodeSprintAttestationData(3, ETH_MAINNET_CHAIN_ID, SPRINT_3_BLOCK, SPRINT_3_BLOCK_HASH, 5, 2, SPRINT_3_SUMMARY_SHA256, SPRINT_3_PR_URI);
        } else if (sprintId == 4) {
            return _encodeSprintAttestationData(4, ETH_MAINNET_CHAIN_ID, SPRINT_4_BLOCK, SPRINT_4_BLOCK_HASH, 4, 2, SPRINT_4_SUMMARY_SHA256, SPRINT_4_PR_URI);
        } else if (sprintId == 5) {
            return _encodeSprintAttestationData(5, ETH_MAINNET_CHAIN_ID, SPRINT_5_BLOCK, SPRINT_5_BLOCK_HASH, 5, 2, SPRINT_5_SUMMARY_SHA256, SPRINT_5_PR_URI);
        } else if (sprintId == 6) {
            return _encodeSprintAttestationData(6, ETH_MAINNET_CHAIN_ID, SPRINT_6_BLOCK, SPRINT_6_BLOCK_HASH, 4, 1, SPRINT_6_SUMMARY_SHA256, SPRINT_6_PR_URI);
        }
        revert InvalidSprintId();
    }

    /// @notice Publish a single pinned Sprint attestation (1..6) to Base EAS (callable strictly by PACTA_ATTESTER_EOA).
    function attestPinnedSprint(bytes32 schemaUID, uint16 sprintId) public onlyPactaAttester returns (bytes32) {
        if (schemaUID == bytes32(0)) revert ZeroSchemaUID();
        bytes memory payload = getPinnedSprintPayload(sprintId);
        IEAS.AttestationRequest memory req = IEAS.AttestationRequest({
            schema: schemaUID,
            data: IEAS.AttestationRequestData({
                recipient: PACTA_ATTESTER_EOA,
                expirationTime: 0,
                revocable: false,
                refUID: bytes32(0),
                data: payload,
                value: 0
            })
        });
        return IEAS(BASE_EAS).attest(req);
    }

    /// @notice Batch-publish all 6 pinned Sprints (1..6) to Base EAS (callable strictly by PACTA_ATTESTER_EOA).
    function run(bytes32 schemaUID) external onlyPactaAttester returns (bytes32[6] memory uids) {
        if (schemaUID == bytes32(0)) revert ZeroSchemaUID();
        for (uint16 s = 1; s <= 6; ++s) {
            uids[s - 1] = attestPinnedSprint(schemaUID, s);
        }
    }

    /// @dev Internal pure ABI encoder restricted to pinned Sprint constants (prevents arbitrary caller string injection).
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
