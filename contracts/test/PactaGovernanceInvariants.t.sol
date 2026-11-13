// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {PactaCommitmentRegistry} from "../PactaCommitmentRegistry.sol";
import {AttestSprints} from "../../script/AttestSprints.s.sol";

interface Vm {
    function chainId(uint256 newChainId) external;
    function createSelectFork(string calldata urlOrAlias, uint256 blockNumber) external returns (uint256);
    function envString(string calldata name) external view returns (string memory);
    function load(address target, bytes32 slot) external view returns (bytes32);
    function prank(address msgSender) external;
    function expectRevert(bytes4 revertData) external;
    function expectRevert(bytes calldata revertData) external;
}

interface ITimelockController {
    function getMinDelay() external view returns (uint256);
}

interface IRoleManager {
    function governance() external view returns (address);
    function pendingGovernance() external view returns (address);
    function getDaddy() external view returns (address);
    function getBrain() external view returns (address);
}

interface IGnosisSafe {
    function getThreshold() external view returns (uint256);
    function getOwners() external view returns (address[] memory);
}

interface IOwnable {
    function owner() external view returns (address);
}

/// @dev Illustrative mock Timelock target with an explicit post-execution delay-floor check pattern.
///      Demonstrates candidate-payload pre/post-state simulation in unit tests (not an authorization wrapper).
contract MockTimelockFloorGate {
    error UnauthorizedCaller();
    error DelayFloorViolated(uint256 postDelay, uint256 committedFloor);

    uint256 public minDelay;

    constructor(uint256 initialDelay) {
        minDelay = initialDelay;
    }

    function updateDelay(uint256 newDelay) external {
        if (msg.sender != address(this)) revert UnauthorizedCaller();
        minDelay = newDelay;
    }

    function simulateCandidateWithFloor(bytes calldata candidateCall, uint256 committedFloor) external {
        (bool ok, bytes memory ret) = address(this).call(candidateCall);
        if (!ok) {
            assembly {
                revert(add(ret, 32), mload(ret))
            }
        }
        if (minDelay < committedFloor) {
            revert DelayFloorViolated(minDelay, committedFloor);
        }
    }
}

/// @title PactaGovernanceInvariantsTest
/// @author Fractal Neurons — Pacta Protocol Commitments DRI (https://fractal-neurons.github.io/pacta/)
/// @notice Reference Foundry test suite separating three verification layers:
///         1. Deterministic offline unit tests for `PactaCommitmentRegistry` 2-tier role separation, batch bounds,
///            and `AttestSprints` Base EAS payload ABI decoding (`forge test --no-match-test testFork`).
///         2. Illustrative mock candidate-proposal floor gate (`testCandidateProposalDelayFloorGate`) exercising
///            both accepted (`>= 7d`) and rejected (`< 7d`) post-execution outcomes.
///         3. Historical block-pinned Mainnet archive smoke tests (`testFork*`, requiring `ETH_RPC_URL` and failing
///            closed when unset; run separately from offline GitHub Actions unit CI).
contract PactaGovernanceInvariantsTest {
    Vm private constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);

    bytes32 internal constant EIP1967_IMPLEMENTATION_SLOT =
        0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;
    bytes32 internal constant EIP1967_ADMIN_SLOT =
        0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103;

    address internal constant SAMPLE_TREASURY_SAFE = 0x1111111111111111111111111111111111111111;
    address internal constant UNPRIVILEGED_CALLER = 0x2222222222222222222222222222222222222222;
    address internal constant ROTATED_ATTESTER = 0x3333333333333333333333333333333333333333;
    address internal constant PACTA_ATTESTER = 0xcA4E2ff22B69A7284210c47BdeE21Aac1269da09;

    bytes32 internal constant SPRINT_7_SHA256 = 0x326d36de4579d119b7cccc7ad36786933b50c2a0957082e28a73e6e6e6847f35;
    bytes32 internal constant SPRINT_9_SHA256 = 0x0a4b9cbd0c3f3eb1839a86753857a603237918200e1d9f90e757f70008472ef4;
    bytes32 internal constant SPRINT_8_SHA256 = 0x7f5605538db468ccb2f51a5822ea2dabf29fb36858f7ae301e36b1a57f6dd2d2;

    /// @notice Verifies constructor zero-address, pinned-attester, and role-collision guards.
    function testRegistryConstructorGuards() public {
        vm.expectRevert(PactaCommitmentRegistry.ZeroAddress.selector);
        new PactaCommitmentRegistry(address(0), PACTA_ATTESTER);

        vm.expectRevert(PactaCommitmentRegistry.InvalidInitialAttester.selector);
        new PactaCommitmentRegistry(SAMPLE_TREASURY_SAFE, ROTATED_ATTESTER);

        vm.expectRevert(PactaCommitmentRegistry.RoleCollision.selector);
        new PactaCommitmentRegistry(PACTA_ATTESTER, PACTA_ATTESTER);
    }

    /// @notice Verifies strict Tier 1 vs Tier 2 separation, admin-denial paths, and rotation collision guards.
    function testRegistryRoleSeparationAndAdminDenials() public {
        PactaCommitmentRegistry registry = new PactaCommitmentRegistry(SAMPLE_TREASURY_SAFE, PACTA_ATTESTER);

        vm.prank(SAMPLE_TREASURY_SAFE);
        vm.expectRevert(PactaCommitmentRegistry.UnauthorizedAttester.selector);
        registry.recordVerification(
            8,
            1,
            26401725,
            0xec3820f0a9db32c01728e66f78dc1958e410269e1077fd1db53df4fbce2ad7a1,
            3,
            2,
            SPRINT_8_SHA256,
            14
        );

        vm.prank(PACTA_ATTESTER);
        vm.expectRevert(PactaCommitmentRegistry.UnauthorizedTreasurySafe.selector);
        registry.setAttester(ROTATED_ATTESTER);

        vm.prank(PACTA_ATTESTER);
        vm.expectRevert(PactaCommitmentRegistry.UnauthorizedTreasurySafe.selector);
        registry.setTreasurySafe(UNPRIVILEGED_CALLER);

        vm.prank(UNPRIVILEGED_CALLER);
        vm.expectRevert(PactaCommitmentRegistry.UnauthorizedTreasurySafe.selector);
        registry.setAttester(ROTATED_ATTESTER);

        vm.prank(SAMPLE_TREASURY_SAFE);
        vm.expectRevert(PactaCommitmentRegistry.RoleCollision.selector);
        registry.setAttester(SAMPLE_TREASURY_SAFE);

        vm.prank(SAMPLE_TREASURY_SAFE);
        vm.expectRevert(PactaCommitmentRegistry.RoleCollision.selector);
        registry.setTreasurySafe(PACTA_ATTESTER);

        vm.prank(SAMPLE_TREASURY_SAFE);
        registry.setAttester(ROTATED_ATTESTER);
        require(registry.attester() == ROTATED_ATTESTER, "Attester rotation failed");
    }

    /// @notice Verifies `recordVerificationBatch` empty/mismatch guards and complete Sprint 7 & 8 struct persistence.
    function testRegistryBatchRecordingAndBounds() public {
        PactaCommitmentRegistry registry = new PactaCommitmentRegistry(SAMPLE_TREASURY_SAFE, PACTA_ATTESTER);

        uint16[] memory emptyIds = new uint16[](0);
        uint64[] memory emptyU64 = new uint64[](0);
        bytes32[] memory emptyB32 = new bytes32[](0);
        uint8[] memory emptyU8 = new uint8[](0);
        uint32[] memory emptyU32 = new uint32[](0);

        vm.prank(PACTA_ATTESTER);
        vm.expectRevert(PactaCommitmentRegistry.EmptyBatch.selector);
        registry.recordVerificationBatch(
            emptyIds, emptyU64, emptyU64, emptyB32, emptyU8, emptyU8, emptyB32, emptyU32
        );

        uint16[] memory sprintIds = new uint16[](2);
        sprintIds[0] = 7;
        sprintIds[1] = 8;

        uint64[] memory chainIds = new uint64[](2);
        chainIds[0] = 1;
        chainIds[1] = 1;

        uint64[] memory blockNumbers = new uint64[](2);
        blockNumbers[0] = 26401638;
        blockNumbers[1] = 26401725;

        bytes32[] memory blockHashes = new bytes32[](2);
        blockHashes[0] = 0xe62ad2969617ad07c23bec298c3d5e197ea7c3084f7f66c90d2eb51d04c6273e;
        blockHashes[1] = 0xec3820f0a9db32c01728e66f78dc1958e410269e1077fd1db53df4fbce2ad7a1;

        uint8[] memory verifiedCounts = new uint8[](2);
        verifiedCounts[0] = 3;
        verifiedCounts[1] = 3;

        uint8[] memory driftCounts = new uint8[](2);
        driftCounts[0] = 1;
        driftCounts[1] = 2;

        bytes32[] memory summarySha256s = new bytes32[](2);
        summarySha256s[0] = SPRINT_7_SHA256;
        summarySha256s[1] = SPRINT_8_SHA256;

        uint32[] memory prNumbers = new uint32[](2);
        prNumbers[0] = 13;
        prNumbers[1] = 14;

        uint64[] memory shortU64 = new uint64[](1);
        bytes32[] memory shortB32 = new bytes32[](1);
        uint8[] memory shortU8 = new uint8[](1);
        uint32[] memory shortU32 = new uint32[](1);

        vm.prank(PACTA_ATTESTER);
        vm.expectRevert(PactaCommitmentRegistry.ArrayLengthMismatch.selector);
        registry.recordVerificationBatch(
            sprintIds, shortU64, blockNumbers, blockHashes, verifiedCounts, driftCounts, summarySha256s, prNumbers
        );

        vm.prank(PACTA_ATTESTER);
        vm.expectRevert(PactaCommitmentRegistry.ArrayLengthMismatch.selector);
        registry.recordVerificationBatch(
            sprintIds, chainIds, shortU64, blockHashes, verifiedCounts, driftCounts, summarySha256s, prNumbers
        );

        vm.prank(PACTA_ATTESTER);
        vm.expectRevert(PactaCommitmentRegistry.ArrayLengthMismatch.selector);
        registry.recordVerificationBatch(
            sprintIds, chainIds, blockNumbers, shortB32, verifiedCounts, driftCounts, summarySha256s, prNumbers
        );

        vm.prank(PACTA_ATTESTER);
        vm.expectRevert(PactaCommitmentRegistry.ArrayLengthMismatch.selector);
        registry.recordVerificationBatch(
            sprintIds, chainIds, blockNumbers, blockHashes, shortU8, driftCounts, summarySha256s, prNumbers
        );

        vm.prank(PACTA_ATTESTER);
        vm.expectRevert(PactaCommitmentRegistry.ArrayLengthMismatch.selector);
        registry.recordVerificationBatch(
            sprintIds, chainIds, blockNumbers, blockHashes, verifiedCounts, shortU8, summarySha256s, prNumbers
        );

        vm.prank(PACTA_ATTESTER);
        vm.expectRevert(PactaCommitmentRegistry.ArrayLengthMismatch.selector);
        registry.recordVerificationBatch(
            sprintIds, chainIds, blockNumbers, blockHashes, verifiedCounts, driftCounts, shortB32, prNumbers
        );

        vm.prank(PACTA_ATTESTER);
        vm.expectRevert(PactaCommitmentRegistry.ArrayLengthMismatch.selector);
        registry.recordVerificationBatch(
            sprintIds, chainIds, blockNumbers, blockHashes, verifiedCounts, driftCounts, summarySha256s, shortU32
        );

        vm.prank(PACTA_ATTESTER);
        registry.recordVerificationBatch(
            sprintIds, chainIds, blockNumbers, blockHashes, verifiedCounts, driftCounts, summarySha256s, prNumbers
        );

        (
            uint64 s7Chain,
            uint64 s7Block,
            bytes32 s7Hash,
            uint8 s7Verified,
            uint8 s7Drift,
            bytes32 s7Sha256,
            uint32 s7Pr
        ) = registry.sprintVerifications(7);
        require(s7Chain == 1 && s7Block == 26401638 && s7Pr == 13, "Sprint 7 metadata mismatch");
        require(s7Verified == 3 && s7Drift == 1, "Sprint 7 counts mismatch");
        require(s7Hash == blockHashes[0] && s7Sha256 == SPRINT_7_SHA256, "Sprint 7 digest mismatch");

        (
            uint64 s8Chain,
            uint64 s8Block,
            bytes32 s8Hash,
            uint8 s8Verified,
            uint8 s8Drift,
            bytes32 s8Sha256,
            uint32 s8Pr
        ) = registry.sprintVerifications(8);
        require(s8Chain == 1 && s8Block == 26401725 && s8Pr == 14, "Sprint 8 metadata mismatch");
        require(s8Verified == 3 && s8Drift == 2, "Sprint 8 counts mismatch");
        require(s8Hash == blockHashes[1] && s8Sha256 == SPRINT_8_SHA256, "Sprint 8 digest mismatch");
    }

    /// @notice Decodes all 12 `AttestSprints` payloads field-by-field and tests Base chain-ID enforcement.
    function testAttestSprintsDeterministicPayloads() public {
        AttestSprints builder = new AttestSprints();

        // Off-Base chainId must revert WrongChainId on transaction builders.
        vm.chainId(1);
        vm.expectRevert(abi.encodeWithSelector(AttestSprints.WrongChainId.selector, uint256(1), uint256(8453)));
        builder.buildRegisterSchemaTx();
        vm.expectRevert(abi.encodeWithSelector(AttestSprints.WrongChainId.selector, uint256(1), uint256(8453)));
        builder.buildAttestSprintTx(1);

        // On Base Mainnet (8453), register & attest builders return target + selector-prefixed calldata.
        vm.chainId(8453);
        (address regTo, uint256 regChain, bytes memory regData) = builder.buildRegisterSchemaTx();
        require(regTo == builder.BASE_SCHEMA_REGISTRY() && regChain == 8453, "Register target mismatch");
        require(bytes4(regData) == builder.SELECTOR_REGISTER_SCHEMA(), "Register selector mismatch");

        uint64[12] memory expBlocks = [
            builder.SPRINT_1_BLOCK(),
            builder.SPRINT_2_BLOCK(),
            builder.SPRINT_3_BLOCK(),
            builder.SPRINT_4_BLOCK(),
            builder.SPRINT_5_BLOCK(),
            builder.SPRINT_6_BLOCK(),
            builder.SPRINT_7_BLOCK(),
            builder.SPRINT_8_BLOCK(),
            builder.SPRINT_9_BLOCK(),
            builder.SPRINT_10_BLOCK(),
            builder.SPRINT_11_BLOCK(),
            builder.SPRINT_12_BLOCK()
        ];
        bytes32[12] memory expHashes = [
            builder.SPRINT_1_BLOCK_HASH(),
            builder.SPRINT_2_BLOCK_HASH(),
            builder.SPRINT_3_BLOCK_HASH(),
            builder.SPRINT_4_BLOCK_HASH(),
            builder.SPRINT_5_BLOCK_HASH(),
            builder.SPRINT_6_BLOCK_HASH(),
            builder.SPRINT_7_BLOCK_HASH(),
            builder.SPRINT_8_BLOCK_HASH(),
            builder.SPRINT_9_BLOCK_HASH(),
            builder.SPRINT_10_BLOCK_HASH(),
            builder.SPRINT_11_BLOCK_HASH(),
            builder.SPRINT_12_BLOCK_HASH()
        ];
        bytes32[12] memory expDigests = [
            builder.SPRINT_1_SUMMARY_SHA256(),
            builder.SPRINT_2_SUMMARY_SHA256(),
            builder.SPRINT_3_SUMMARY_SHA256(),
            builder.SPRINT_4_SUMMARY_SHA256(),
            builder.SPRINT_5_SUMMARY_SHA256(),
            builder.SPRINT_6_SUMMARY_SHA256(),
            builder.SPRINT_7_SUMMARY_SHA256(),
            builder.SPRINT_8_SUMMARY_SHA256(),
            builder.SPRINT_9_SUMMARY_SHA256(),
            builder.SPRINT_10_SUMMARY_SHA256(),
            builder.SPRINT_11_SUMMARY_SHA256(),
            builder.SPRINT_12_SUMMARY_SHA256()
        ];
        uint8[12] memory expVerified = [uint8(4), 4, 3, 4, 3, 4, 3, 3, 4, 4, 4, 4];
        uint8[12] memory expDrifts = [uint8(1), 1, 0, 1, 2, 1, 1, 2, 0, 1, 2, 1];
        string[12] memory expUris = [
            builder.SPRINT_1_PR_URI(),
            builder.SPRINT_2_PR_URI(),
            builder.SPRINT_3_PR_URI(),
            builder.SPRINT_4_PR_URI(),
            builder.SPRINT_5_PR_URI(),
            builder.SPRINT_6_PR_URI(),
            builder.SPRINT_7_PR_URI(),
            builder.SPRINT_8_PR_URI(),
            builder.SPRINT_9_PR_URI(),
            builder.SPRINT_10_PR_URI(),
            builder.SPRINT_11_PR_URI(),
            builder.SPRINT_12_PR_URI()
        ];

        for (uint16 id = 1; id <= 12; ++id) {
            (address attTo, uint256 attChain, bytes32 uid, bytes memory attCall) = builder.buildAttestSprintTx(id);
            require(attTo == builder.BASE_EAS() && attChain == 8453 && uid == builder.canonicalSchemaUID(), "EAS tx mismatch");
            require(bytes4(attCall) == builder.SELECTOR_ATTEST(), "EAS selector mismatch");

            (
                uint16 dId,
                uint64 dChain,
                uint64 dBlock,
                bytes32 dHash,
                uint8 dVerified,
                uint8 dDrift,
                bytes32 dSha,
                string memory dUri
            ) = abi.decode(
                builder.getPinnedSprintPayload(id),
                (uint16, uint64, uint64, bytes32, uint8, uint8, bytes32, string)
            );
            require(dId == id && dChain == 1, "Decoded sprint/chain mismatch");
            require(dBlock == expBlocks[id - 1] && dHash == expHashes[id - 1], "Decoded block/hash mismatch");
            require(dVerified == expVerified[id - 1] && dDrift == expDrifts[id - 1], "Decoded count mismatch");
            require(
                dSha == expDigests[id - 1] && keccak256(bytes(dUri)) == keccak256(bytes(expUris[id - 1])),
                "Decoded digest/URI mismatch"
            );
        }

        vm.expectRevert(AttestSprints.InvalidSprintId.selector);
        builder.getPinnedSprintPayload(13);
    }

    /// @notice Illustrative mock pattern testing both accepted (`>= 7d`) and rejected (`< 7d`) candidate delay updates.
    function testCandidateProposalDelayFloorGate() public {
        MockTimelockFloorGate gate = new MockTimelockFloorGate(7 days);
        uint256 floor = 7 days;

        // 1. Accepted candidate: 10-day delay preserves >= 7-day floor.
        gate.simulateCandidateWithFloor(abi.encodeCall(MockTimelockFloorGate.updateDelay, (10 days)), floor);
        require(gate.minDelay() == 10 days, "Expected 10-day delay update");

        // 2. Rejected candidate: lowering delay to 1 day below 7-day floor reverts DelayFloorViolated.
        vm.expectRevert(abi.encodeWithSelector(MockTimelockFloorGate.DelayFloorViolated.selector, 1 days, floor));
        gate.simulateCandidateWithFloor(abi.encodeCall(MockTimelockFloorGate.updateDelay, (1 days)), floor);
    }

    /// @notice Historical block-pinned Mainnet smoke test for sampled Yearn V3 RoleManager state at block 26401725.
    function testForkYearnV3SnapshotAt26401725() public {
        string memory rpcUrl = vm.envString("ETH_RPC_URL");
        vm.createSelectFork(rpcUrl, 26401725);
        require(block.chainid == 1 && block.number == 26401725, "Unexpected fork coordinate");

        address roleManagerAddr = 0xb3bd6B2E61753C311EFbCF0111f75D29706D9a41;
        require(roleManagerAddr.code.length > 0, "Missing RoleManager code");

        IRoleManager roleManager = IRoleManager(roleManagerAddr);
        address timelock = roleManager.governance();
        require(timelock == 0x88Ba032be87d5EF1fbE87336B7090767F367BF73, "Unexpected RoleManager governance");
        require(timelock.code.length > 0, "Missing TimelockController code");
        require(roleManager.pendingGovernance() == address(0), "Unexpected pendingGovernance");
        require(ITimelockController(timelock).getMinDelay() == 7 days, "Sampled Timelock delay != 7d");

        address daddy = roleManager.getDaddy();
        require(daddy == 0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52, "Unexpected Daddy Safe");
        require(IGnosisSafe(daddy).getThreshold() == 6, "Sampled Daddy Safe threshold != 6");
        require(IGnosisSafe(daddy).getOwners().length == 9, "Sampled Daddy Safe owners != 9");

        address brain = roleManager.getBrain();
        require(brain == 0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7, "Unexpected Brain Safe");
        require(IGnosisSafe(brain).getThreshold() == 3, "Sampled Brain Safe threshold != 3");
        require(IGnosisSafe(brain).getOwners().length == 6, "Sampled Brain Safe owners != 6");
    }

    /// @notice Historical block-pinned Mainnet smoke test for sampled Liquity V2 owner & EIP-1967 slots at block 26401540.
    function testForkLiquityV2SampledAlignmentAt26401540() public {
        string memory rpcUrl = vm.envString("ETH_RPC_URL");
        vm.createSelectFork(rpcUrl, 26401540);
        require(block.chainid == 1 && block.number == 26401540, "Unexpected fork coordinate");

        address boldToken = 0x6440f144b7e50D6a8439336510312d2F54beB01D;
        address governance = 0x807DEf5E7d057DF05C796F4bc75C3Fe82Bd6EeE1;
        address collateralRegistry = 0xf949982B91C8c61e952B3bA942cbbfaef5386684;

        require(
            boldToken.code.length > 0 && governance.code.length > 0 && collateralRegistry.code.length > 0,
            "Missing sampled Liquity V2 runtime code"
        );
        require(IOwnable(boldToken).owner() == address(0), "Sampled BOLD owner non-zero");
        require(IOwnable(governance).owner() == address(0), "Sampled Governance owner non-zero");

        bytes32 implWord = vm.load(collateralRegistry, EIP1967_IMPLEMENTATION_SLOT);
        bytes32 adminWord = vm.load(collateralRegistry, EIP1967_ADMIN_SLOT);
        require(implWord == bytes32(0) && adminWord == bytes32(0), "Sampled EIP-1967 slots non-zero");
    }
}
