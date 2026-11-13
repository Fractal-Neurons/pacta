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
/// @notice Deterministic Base Mainnet (`chainId == 8453`) direct-EOA calldata builder for Sprints 1–9 public audit summaries.
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
    bytes32 public constant SPRINT_1_SUMMARY_SHA256 = 0xeb97180d687f9f8fb9a1ae341349bd74d3bc7ff95da0e4eb586e6ba4f540cffe;
    string public constant SPRINT_1_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/1";

    uint64 public constant SPRINT_2_BLOCK = 26400152;
    bytes32 public constant SPRINT_2_BLOCK_HASH = 0xa9a61622304ec55c5fec49abbcabec60069f66f28792cf841bdd7aef12ce63aa;
    bytes32 public constant SPRINT_2_SUMMARY_SHA256 = 0x9c2a186cf21dd97faf2a6afb9f810e1b9f6c8503dc5f7153435c0fa48811c966;
    string public constant SPRINT_2_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/2";

    uint64 public constant SPRINT_3_BLOCK = 26401070;
    bytes32 public constant SPRINT_3_BLOCK_HASH = 0xcf55f6a42ae610c1f8766b5c2fb676d91f178469fa10ef777eccbb76f6506234;
    bytes32 public constant SPRINT_3_SUMMARY_SHA256 = 0x02d6de1d05599e44d0634541a13d05764a90d6f860c8d8bcfde4b0e980d3c122;
    string public constant SPRINT_3_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/3";

    uint64 public constant SPRINT_4_BLOCK = 26401312;
    bytes32 public constant SPRINT_4_BLOCK_HASH = 0x95866ea3ef8f9a0567ce000bc8075f6dc5fb0f1e80cb4e9999ae624a2f0dc109;
    bytes32 public constant SPRINT_4_SUMMARY_SHA256 = 0x6adc370fdb6acbc14f38ab1b30cb90a0c1e5ce8c2457ad64177c82f548edc2fb;
    string public constant SPRINT_4_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/5";

    uint64 public constant SPRINT_5_BLOCK = 26401405;
    bytes32 public constant SPRINT_5_BLOCK_HASH = 0x26e155e1569d436406a52ecee31c94d8d8ef2ca4c45d82211a84c8c802be1510;
    bytes32 public constant SPRINT_5_SUMMARY_SHA256 = 0xfd13461161313f9bd5ae867e4076d5f07b787e05370bca7516dcbbc8ba8f63a2;
    string public constant SPRINT_5_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/7";

    uint64 public constant SPRINT_6_BLOCK = 26401540;
    bytes32 public constant SPRINT_6_BLOCK_HASH = 0x49324aaf84b0ffd4e21026c5345272788bff377f0f86fcdb74280cdfc32a9641;
    bytes32 public constant SPRINT_6_SUMMARY_SHA256 = 0xec0e3a3862cd528a35acc2992eccd798f8ce4bc8e7ea8c0311f56fa000df8471;
    string public constant SPRINT_6_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/10";

    uint64 public constant SPRINT_7_BLOCK = 26401638;
    bytes32 public constant SPRINT_7_BLOCK_HASH = 0xe62ad2969617ad07c23bec298c3d5e197ea7c3084f7f66c90d2eb51d04c6273e;
    bytes32 public constant SPRINT_7_SUMMARY_SHA256 = 0x326d36de4579d119b7cccc7ad36786933b50c2a0957082e28a73e6e6e6847f35;
    string public constant SPRINT_7_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/13";

    uint64 public constant SPRINT_8_BLOCK = 26401725;
    bytes32 public constant SPRINT_8_BLOCK_HASH = 0xec3820f0a9db32c01728e66f78dc1958e410269e1077fd1db53df4fbce2ad7a1;
    bytes32 public constant SPRINT_8_SUMMARY_SHA256 = 0x7f5605538db468ccb2f51a5822ea2dabf29fb36858f7ae301e36b1a57f6dd2d2;
    string public constant SPRINT_8_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/14";

    uint64 public constant SPRINT_9_BLOCK = 26402160;
    bytes32 public constant SPRINT_9_BLOCK_HASH = 0xd04a5e8aa3500c5b60d90c25a810ef28eb9d1bfffadf28f1da58a31ed90582dc;
    bytes32 public constant SPRINT_9_SUMMARY_SHA256 = 0x0a4b9cbd0c3f3eb1839a86753857a603237918200e1d9f90e757f70008472ef4;
    string public constant SPRINT_9_PR_URI = "https://github.com/Fractal-Neurons/pacta/pull/16";

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

    /// @notice Return the pinned, quarantine-safe public attestation data payload for Sprint `sprintId` (1..9).
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
        } else if (sprintId == 7) {
            return _encodeSprintAttestationData(7, ETH_MAINNET_CHAIN_ID, SPRINT_7_BLOCK, SPRINT_7_BLOCK_HASH, 3, 1, SPRINT_7_SUMMARY_SHA256, SPRINT_7_PR_URI);
        } else if (sprintId == 8) {
            return _encodeSprintAttestationData(8, ETH_MAINNET_CHAIN_ID, SPRINT_8_BLOCK, SPRINT_8_BLOCK_HASH, 3, 2, SPRINT_8_SUMMARY_SHA256, SPRINT_8_PR_URI);
        } else if (sprintId == 9) {
            return _encodeSprintAttestationData(9, ETH_MAINNET_CHAIN_ID, SPRINT_9_BLOCK, SPRINT_9_BLOCK_HASH, 4, 0, SPRINT_9_SUMMARY_SHA256, SPRINT_9_PR_URI);
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
