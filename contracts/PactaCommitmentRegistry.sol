// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title PactaCommitmentRegistry
/// @author Fractal Neurons — Pacta Protocol Commitments DRI (https://fractal-neurons.github.io/pacta/)
/// @notice Minimal on-chain commitment verification registry & attestation emitter with strict 2-tier role separation:
///         - Tier 1 (`treasurySafe`): Owner/admin Safe controlled by human founder (no hot keys on server).
///         - Tier 2 (`attester`): Dedicated low-balance operational EOA (`0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09`)
///           authorized only to publish block-pinned commitment audit receipts.
/// @custom:security-contact pacta@dri.network
contract PactaCommitmentRegistry {
    /// @notice Emitted when a block-pinned commitment audit is recorded on-chain.
    /// @param targetContract Primary protocol contract or governance Safe audited.
    /// @param blockNumber Pinned mainnet/L2 block number at which proofs were verified.
    /// @param verifiedCount Number of commitments verified in the bundle.
    /// @param driftCount Number of non-sensitive commitment drifts recorded in the public summary.
    /// @param proofSha256 SHA-256 digest of the deterministic replay bundle / audit summary.
    /// @param reportURI Canonical URI to the public audit summary on https://fractal-neurons.github.io/pacta/ or GitHub.
    event CommitmentVerified(
        address indexed targetContract,
        uint256 indexed blockNumber,
        uint8 verifiedCount,
        uint8 driftCount,
        bytes32 proofSha256,
        string reportURI
    );

    event TreasurySafeTransferred(address indexed previousSafe, address indexed newSafe);
    event AttesterUpdated(address indexed previousAttester, address indexed newAttester);

    error UnauthorizedTreasurySafe();
    error UnauthorizedAttester();
    error ZeroAddress();

    /// @notice Tier 1 Treasury & Admin Safe (human-controlled).
    address public treasurySafe;

    /// @notice Tier 2 Operational Attester EOA (0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09).
    address public attester;

    /// @notice Canonical service portal URI for block explorer discovery.
    string public constant SERVICE_PORTAL_URI = "https://fractal-neurons.github.io/pacta/";

    /// @notice Canonical scan request intake URI.
    string public constant SCAN_INTAKE_URI = "https://github.com/Fractal-Neurons/pacta/issues/new?template=request-scan.yml";

    modifier onlyTreasurySafe() {
        if (msg.sender != treasurySafe) revert UnauthorizedTreasurySafe();
        _;
    }

    modifier onlyAttesterOrTreasury() {
        if (msg.sender != attester && msg.sender != treasurySafe) revert UnauthorizedAttester();
        _;
    }

    constructor(address initialTreasurySafe, address initialAttester) {
        if (initialTreasurySafe == address(0) || initialAttester == address(0)) revert ZeroAddress();
        treasurySafe = initialTreasurySafe;
        attester = initialAttester;
        emit TreasurySafeTransferred(address(0), initialTreasurySafe);
        emit AttesterUpdated(address(0), initialAttester);
    }

    /// @notice Record a single verified commitment audit receipt on-chain.
    function recordVerification(
        address targetContract,
        uint256 blockNumber,
        uint8 verifiedCount,
        uint8 driftCount,
        bytes32 proofSha256,
        string calldata reportURI
    ) external onlyAttesterOrTreasury {
        emit CommitmentVerified(targetContract, blockNumber, verifiedCount, driftCount, proofSha256, reportURI);
    }

    /// @notice Record a batch of verified commitment audit receipts in a single transaction.
    function recordVerificationBatch(
        address[] calldata targetContracts,
        uint256[] calldata blockNumbers,
        uint8[] calldata verifiedCounts,
        uint8[] calldata driftCounts,
        bytes32[] calldata proofSha256s,
        string[] calldata reportURIs
    ) external onlyAttesterOrTreasury {
        uint256 len = targetContracts.length;
        for (uint256 i = 0; i < len; ++i) {
            emit CommitmentVerified(
                targetContracts[i],
                blockNumbers[i],
                verifiedCounts[i],
                driftCounts[i],
                proofSha256s[i],
                reportURIs[i]
            );
        }
    }

    /// @notice Rotate the Tier 2 Attester EOA (callable only by Tier 1 Treasury Safe).
    function setAttester(address newAttester) external onlyTreasurySafe {
        if (newAttester == address(0)) revert ZeroAddress();
        emit AttesterUpdated(attester, newAttester);
        attester = newAttester;
    }

    /// @notice Transfer Tier 1 Treasury Safe ownership (callable only by current Tier 1 Treasury Safe).
    function setTreasurySafe(address newTreasurySafe) external onlyTreasurySafe {
        if (newTreasurySafe == address(0)) revert ZeroAddress();
        emit TreasurySafeTransferred(treasurySafe, newTreasurySafe);
        treasurySafe = newTreasurySafe;
    }
}
