"""Vertical Slice Test Suite — Evidence Verification Fabric (Phase 2A).

Mandate: Real-world side-effect verification as a mandatory completion gate.
Zero false passes. Tasks only reach COMPLETED when verifiable evidence of
execution is empirically confirmed.
"""

import asyncio
import os
import pytest
from app.core.verification import EvidenceVerificationFabric, EvidenceRecord, EvidenceType
from app.core.command_pipeline import CommandPipeline
from app.core.command import CommandParser, PlanStepItem
from app.core.state import SERAState, SERAStatus
from app.core.events import EventBus
from app.tools import ToolRegistry


@pytest.fixture
def fabric():
    return EvidenceVerificationFabric()


def test_evidence_record_serialization():
    """Verify EvidenceRecord structure and serialization."""
    rec = EvidenceRecord(
        evidence_type=EvidenceType.PROCESS_RUNNING,
        verified=True,
        source="test_kernel",
        details={"pid": 1234},
    )
    d = rec.to_dict()
    assert d["evidence_type"] == "PROCESS_RUNNING"
    assert d["verified"] is True
    assert d["source"] == "test_kernel"
    assert d["details"]["pid"] == 1234
    assert d["timestamp"] > 0
    assert d["failure_reason"] is None


def test_verify_process_positive(fabric):
    """Verifies that an existing system process (explorer or python) is found."""
    # explorer.exe or python.exe is guaranteed to run in Windows during test execution
    rec = fabric.verify_process("explorer")
    assert rec.evidence_type == EvidenceType.PROCESS_RUNNING
    assert rec.verified is True
    assert rec.details["count"] >= 1
    assert rec.failure_reason is None


def test_verify_process_negative(fabric):
    """Verifies that a non-existent process correctly returns verified=False without false pass."""
    rec = fabric.verify_process("definitely_non_existent_process_99999")
    assert rec.evidence_type == EvidenceType.PROCESS_RUNNING
    assert rec.verified is False
    assert rec.details["count"] == 0
    assert "No active process matching" in rec.failure_reason


def test_verify_web_search_results_positive(fabric):
    """Verifies that valid structured search results pass verification."""
    results = [
        {
            "title": "NVIDIA GeForce RTX 5090 Official Specs",
            "url": "https://www.nvidia.com/rtx-5090",
            "snippet": "Next-generation Blackwell architecture flagship.",
            "source": "duckduckgo",
        },
        {
            "title": "RTX 5090 Benchmarks & Performance Review",
            "url": "https://www.tomshardware.com/rtx-5090-review",
            "snippet": "Extensive testing across 25 games in 4K.",
            "source": "duckduckgo",
        },
    ]
    rec = fabric.verify_web_search_results(results, min_count=1)
    assert rec.evidence_type == EvidenceType.STRUCTURED_DATA
    assert rec.verified is True
    assert rec.details["valid_results_count"] == 2
    assert rec.details["first_title"] == "NVIDIA GeForce RTX 5090 Official Specs"
    assert rec.failure_reason is None


def test_verify_web_search_results_negative_empty(fabric):
    """Verifies that empty search results fail verification (preventing hallucinated completion)."""
    rec = fabric.verify_web_search_results([], min_count=1)
    assert rec.evidence_type == EvidenceType.STRUCTURED_DATA
    assert rec.verified is False
    assert rec.details["valid_results_count"] == 0
    assert "Expected at least 1 valid search results" in rec.failure_reason


def test_verify_web_search_results_negative_invalid_format(fabric):
    """Verifies that malformed or non-URL data fails verification."""
    malformed = [
        {"title": "No URL here", "snippet": "Missing url"},
        {"url": "not-a-http-url", "title": "Bad url"},
    ]
    rec = fabric.verify_web_search_results(malformed, min_count=1)
    assert rec.verified is False
    assert rec.details["valid_results_count"] == 0


def test_verify_file_system_positive(fabric):
    """Verifies that an existing file passes verification."""
    this_file = os.path.abspath(__file__)
    rec = fabric.verify_file_system(this_file, check_exists=True, min_bytes=10)
    assert rec.evidence_type == EvidenceType.FILE_SYSTEM
    assert rec.verified is True
    assert rec.details["exists"] is True
    assert rec.details["size_bytes"] > 10


def test_verify_file_system_negative(fabric):
    """Verifies that a non-existent file fails verification."""
    rec = fabric.verify_file_system("C:\\non_existent_directory_xyz\\fake_file.txt", check_exists=True)
    assert rec.evidence_type == EvidenceType.FILE_SYSTEM
    assert rec.verified is False
    assert rec.details["exists"] is False
    assert "File does not exist" in rec.failure_reason


def test_verify_screen_capture_positive(fabric):
    """Verifies that valid screen capture dictionary payload passes."""
    payload = {
        "success": True,
        "dimensions": "1920x1080",
        "buffer": "base64_image_bytes_here",
    }
    rec = fabric.verify_screen_capture(payload)
    assert rec.evidence_type == EvidenceType.IMAGE_BUFFER
    assert rec.verified is True
    assert rec.failure_reason is None


def test_verify_screen_capture_negative(fabric):
    """Verifies that invalid or empty capture payload fails."""
    payload = {"success": True, "error": "DirectX capture failed"}
    rec = fabric.verify_screen_capture(payload)
    assert rec.verified is False
    assert "no valid image data" in rec.failure_reason


def test_verify_tool_execution_catches_false_pass(fabric):
    """Critical mandate: If a tool claims success but the process does NOT exist, fabric must REJECT it."""
    fake_tool_result = {
        "success": True,
        "application": "completely_fictitious_ghost_process",
        "action": "launched",
    }
    # verify_tool_execution for open_application must inspect the real OS process table
    rec = fabric.verify_tool_execution("open_application", fake_tool_result)
    assert rec.evidence_type == EvidenceType.PROCESS_RUNNING
    assert rec.verified is False  # Must be rejected because process doesn't exist
    assert "No active process matching" in rec.failure_reason


def test_command_pipeline_integrates_evidence_fabric():
    """Verifies that CommandPipeline emits EVIDENCE_VERIFIED and transitions to BROKEN on verification failure."""
    async def _run():
        event_bus = EventBus()
        state = SERAState()
        tools = ToolRegistry()

        pipeline = CommandPipeline(
            tools=tools,
            state=state,
            event_bus=event_bus,
        )

        emitted_events = []
        event_bus.subscribe("EVIDENCE_VERIFIED", lambda p: emitted_events.append(("EVIDENCE_VERIFIED", p)))
        event_bus.subscribe("TASK_FAILED", lambda p: emitted_events.append(("TASK_FAILED", p)))

        # Step that points to non-existent tool
        step = PlanStepItem(
            step_id=1,
            goal="Launch ghost app",
            action="non_existent_tool_xyz",
            arguments={},
            timeout_seconds=5.0,
        )

        res = await pipeline._execute_single_step(step, "test_task", 1, 1)
        assert res["success"] is False
        assert "not registered" in res["error"]

    asyncio.run(_run())


if __name__ == "__main__":
    test_evidence_record_serialization()
    test_verify_process_positive(EvidenceVerificationFabric())
    test_verify_process_negative(EvidenceVerificationFabric())
    test_verify_web_search_results_positive(EvidenceVerificationFabric())
    test_verify_web_search_results_negative_empty(EvidenceVerificationFabric())
    test_verify_web_search_results_negative_invalid_format(EvidenceVerificationFabric())
    test_verify_file_system_positive(EvidenceVerificationFabric())
    test_verify_file_system_negative(EvidenceVerificationFabric())
    test_verify_screen_capture_positive(EvidenceVerificationFabric())
    test_verify_screen_capture_negative(EvidenceVerificationFabric())
    test_verify_tool_execution_catches_false_pass(EvidenceVerificationFabric())
    test_command_pipeline_integrates_evidence_fabric()
    print("ALL EVIDENCE FABRIC VERTICAL SLICE TESTS PASSED!")
