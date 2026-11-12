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
/// @notice Deterministic Base EAS schema registration and Sprint 1–5 public audit attestation helper
///         for Tier 2 Pacta Attester EOA (0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09).
///         Contains strictly public, non-exploitable audit metadata (zero quarantined details).
contract AttestSprints {
    address public constant BASE_SCHEMA_REGISTRY = 0x4200000000000000000000000000000000000020;
    address public constant BASE_EAS = 0x4200000000000000000000000000000000000021;
    address public constant PACTA_ATTESTER_EOA = 0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09;

    string public constant PACTA_EAS_SCHEMA =
        "uint64 chainId,address targetContract,uint64 blockNumber,uint8 verifiedCount,uint8 driftCount,bytes32 proofSha256,string protocolName,string reportURI";

    /// @notice Encode EAS attestation payload for a verified Pacta Sprint audit.
    function encodeSprintAttestationData(
        uint64 chainId,
        address targetContract,
        uint64 blockNumber,
        uint8 verifiedCount,
        uint8 driftCount,
        bytes32 proofSha256,
        string memory protocolName,
        string memory reportURI
    ) public pure returns (bytes memory) {
        return abi.encode(
            chainId,
            targetContract,
            blockNumber,
            verifiedCount,
            driftCount,
            proofSha256,
            protocolName,
            reportURI
        );
    }
}
