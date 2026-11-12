// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title PactaCommitmentRegistry
/// @author Fractal Neurons — Pacta Protocol Commitments DRI (https://fractal-neurons.github.io/pacta/)
/// @notice Minimal on-chain commitment verification registry with strict 2-tier role separation and quarantine safety:
///         - Tier 1 (`treasurySafe`): Owner/admin Safe controlled by human founder (no hot keys on server).
///           Cannot publish attestations directly (`onlyAttester`), preventing operational/admin role conflation.
///         - Tier 2 (`attester`): Dedicated low-balance operational EOA (`0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09`)
///           authorized strictly to record block-pinned public sprint audit digests (zero value transfer or admin rights).
///         - Quarantine-Safe Schema: Emits and stores only numeric `sprintId`, `chainId`, `blockNumber`, `blockHash`,
///           `verifiedCount`, `driftCount`, `summarySha256`, and `githubPrNumber` (no arbitrary target addresses or
///           free-form URI strings that could leak `disclosure_only` findings on-chain).
/// @custom:security-contact pacta@dri.network
contract PactaCommitmentRegistry {
    struct SprintVerification {
        uint64 chainId;
        uint64 blockNumber;
        bytes32 blockHash;
        uint8 verifiedCount;
        uint8 driftCount;
        bytes32 summarySha256;
        uint32 githubPrNumber;
    }

    /// @notice Emitted when a block-pinned Sprint commitment audit summary is recorded on-chain.
    event CommitmentVerified(
        uint16 indexed sprintId,
        uint64 indexed chainId,
        uint64 indexed blockNumber,
        bytes32 blockHash,
        uint8 verifiedCount,
        uint8 driftCount,
        bytes32 summarySha256,
        uint32 githubPrNumber
    );

    event TreasurySafeTransferred(address indexed previousSafe, address indexed newSafe);
    event AttesterUpdated(address indexed previousAttester, address indexed newAttester);

    error UnauthorizedTreasurySafe();
    error UnauthorizedAttester();
    error ZeroAddress();
    error RoleCollision();
    error InvalidInitialAttester();
    error EmptyBatch();
    error ArrayLengthMismatch();
    error InvalidVerificationParameters();

    /// @notice Canonical initial Tier 2 Pacta Attester EOA.
    address public constant INITIAL_PACTA_ATTESTER = 0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09;

    /// @notice Canonical service portal URI for block explorer discovery.
    string public constant SERVICE_PORTAL_URI = "https://fractal-neurons.github.io/pacta/";

    /// @notice Canonical public audit repository prefix (append `/pull/<githubPrNumber>`).
    string public constant GITHUB_PR_PREFIX = "https://github.com/Fractal-Neurons/pacta/pull/";

    /// @notice Tier 1 Treasury & Admin Safe (human-controlled).
    address public treasurySafe;

    /// @notice Tier 2 Operational Attester EOA (pinned at deployment to INITIAL_PACTA_ATTESTER).
    address public attester;

    /// @notice Stored public verification records by Sprint ID.
    mapping(uint16 => SprintVerification) public sprintVerifications;

    modifier onlyTreasury() {
        if (msg.sender != treasurySafe) revert UnauthorizedTreasurySafe();
        _;
    }

    modifier onlyAttester() {
        if (msg.sender != attester) revert UnauthorizedAttester();
        _;
    }

    constructor(address initialTreasurySafe, address initialAttester) {
        if (initialTreasurySafe == address(0) || initialAttester == address(0)) revert ZeroAddress();
        if (initialAttester != INITIAL_PACTA_ATTESTER) revert InvalidInitialAttester();
        if (initialTreasurySafe == initialAttester) revert RoleCollision();
        treasurySafe = initialTreasurySafe;
        attester = initialAttester;
        emit TreasurySafeTransferred(address(0), initialTreasurySafe);
        emit AttesterUpdated(address(0), initialAttester);
    }

    /// @notice Record a single verified Sprint commitment summary receipt on-chain (callable strictly by Tier 2 `attester`).
    function recordVerification(
        uint16 sprintId,
        uint64 chainId,
        uint64 blockNumber,
        bytes32 blockHash,
        uint8 verifiedCount,
        uint8 driftCount,
        bytes32 summarySha256,
        uint32 githubPrNumber
    ) external onlyAttester {
        _record(sprintId, chainId, blockNumber, blockHash, verifiedCount, driftCount, summarySha256, githubPrNumber);
    }

    /// @notice Record a non-empty batch of verified Sprint commitment summary receipts in a single transaction.
    function recordVerificationBatch(
        uint16[] calldata sprintIds,
        uint64[] calldata chainIds,
        uint64[] calldata blockNumbers,
        bytes32[] calldata blockHashes,
        uint8[] calldata verifiedCounts,
        uint8[] calldata driftCounts,
        bytes32[] calldata summarySha256s,
        uint32[] calldata githubPrNumbers
    ) external onlyAttester {
        uint256 len = sprintIds.length;
        if (len == 0) revert EmptyBatch();
        if (
            chainIds.length != len ||
            blockNumbers.length != len ||
            blockHashes.length != len ||
            verifiedCounts.length != len ||
            driftCounts.length != len ||
            summarySha256s.length != len ||
            githubPrNumbers.length != len
        ) revert ArrayLengthMismatch();

        for (uint256 i = 0; i < len; ++i) {
            _record(
                sprintIds[i],
                chainIds[i],
                blockNumbers[i],
                blockHashes[i],
                verifiedCounts[i],
                driftCounts[i],
                summarySha256s[i],
                githubPrNumbers[i]
            );
        }
    }

    function _record(
        uint16 sprintId,
        uint64 chainId,
        uint64 blockNumber,
        bytes32 blockHash,
        uint8 verifiedCount,
        uint8 driftCount,
        bytes32 summarySha256,
        uint32 githubPrNumber
    ) internal {
        if (
            sprintId == 0 ||
            chainId == 0 ||
            blockNumber == 0 ||
            blockHash == bytes32(0) ||
            summarySha256 == bytes32(0) ||
            githubPrNumber == 0
        ) revert InvalidVerificationParameters();

        sprintVerifications[sprintId] = SprintVerification({
            chainId: chainId,
            blockNumber: blockNumber,
            blockHash: blockHash,
            verifiedCount: verifiedCount,
            driftCount: driftCount,
            summarySha256: summarySha256,
            githubPrNumber: githubPrNumber
        });

        emit CommitmentVerified(
            sprintId,
            chainId,
            blockNumber,
            blockHash,
            verifiedCount,
            driftCount,
            summarySha256,
            githubPrNumber
        );
    }

    /// @notice Rotate the Tier 2 Attester EOA (callable strictly by Tier 1 `treasurySafe`).
    function setAttester(address newAttester) external onlyTreasury {
        if (newAttester == address(0)) revert ZeroAddress();
        if (newAttester == treasurySafe) revert RoleCollision();
        emit AttesterUpdated(attester, newAttester);
        attester = newAttester;
    }

    /// @notice Transfer Tier 1 Treasury Safe ownership (callable strictly by current Tier 1 `treasurySafe`).
    function setTreasurySafe(address newTreasurySafe) external onlyTreasury {
        if (newTreasurySafe == address(0)) revert ZeroAddress();
        if (newTreasurySafe == attester) revert RoleCollision();
        emit TreasurySafeTransferred(treasurySafe, newTreasurySafe);
        treasurySafe = newTreasurySafe;
    }
}
