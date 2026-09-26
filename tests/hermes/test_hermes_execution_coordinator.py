"""
SERA 2.0 / Phase 4B — Hermes Execution Coordinator Test Suite.

Validates the full Hermes-SERA execution loop across Categories A through G:
- Category A: Simple / complex boundary commands
- Category B: Reference-dependent tasks (grounded vs ungrounded)
- Category C: Browser multi-step flow
- Category D: Deterministic settings control
- Category E: Voice / fast-path cancellation
- Category F: Destructive action permission flow (APPROVE, DENY, CANCEL, EXPIRE)
- Category G: Failure boundaries and authoritative validation rejections

Test Classification:
All tests in this suite are classified as:
[SIMULATED INTEGRATION] using MockSimulationHermesClient and real SERA ToolRegistry + ContextStore.
"""

import asyncio
import pytest

from app.adapters.hermes.bridge import MockSimulationHermesClient, SeraHermesBridge
from app.adapters.hermes.coordinator import HermesExecutionCoordinator
from app.adapters.hermes.schema import (
    ApprovalDecision,
    ApprovalStatus,
    ExecutionHandoffStatus,
    RiskLevel,
    TargetType,
)
from app.adapters.hermes.validator import HermesPlanValidator
from app.core.context.store import ContextStore, SearchResultEntity, SearchResultType
from app.core.verification import EvidenceVerificationFabric
from app.tools import create_tool_registry


@pytest.fixture
def test_env():
    """Builds a hermetic test environment with SERA substrate components."""
    context_store = ContextStore()
    tools = create_tool_registry()
    evidence_fabric = EvidenceVerificationFabric()
    validator = HermesPlanValidator(context_store=context_store, tool_registry=tools)
    mock_backend = MockSimulationHermesClient()
    bridge = SeraHermesBridge(backend=mock_backend)

    coordinator = HermesExecutionCoordinator(
        bridge=bridge,
        context_store=context_store,
        tool_registry=tools,
        validator=validator,
        evidence_fabric=evidence_fabric,
    )
    return {
        "coordinator": coordinator,
        "bridge": bridge,
        "mock_backend": mock_backend,
        "context_store": context_store,
        "tools": tools,
    }


# =========================================================================
# Category A — Simple Complex-Boundary Commands
# =========================================================================
@pytest.mark.asyncio
async def test_category_a_open_application(test_env):
    """[SIMULATED INTEGRATION] Verify translation and execution of 'Bring Chrome forward'."""
    coord = test_env["coordinator"]
    res = await coord.execute_task("Bring Chrome forward")

    assert res.status == ExecutionHandoffStatus.COMPLETED
    assert res.steps_executed == 1
    assert res.telemetry.turns == 1
    assert res.step_history[0]["action"] == "open_application"
    assert res.step_history[0]["arguments"]["application"] == "chrome"
    assert res.step_history[0]["status"] == "VERIFIED_SUCCESS"


# =========================================================================
# Category B — Reference-Dependent Tasks
# =========================================================================
@pytest.mark.asyncio
async def test_category_b_open_result_with_valid_context(test_env):
    """[SIMULATED INTEGRATION] 'Open the first result' with active search session resolves entity."""
    coord = test_env["coordinator"]
    store = test_env["context_store"]

    # Pre-populate ContextStore with a search session
    session = store.create_search_session("Python tutorials", source="YouTube")
    store.add_search_results(session.session_id, [
        {"title": "Python for Beginners", "url": "https://www.youtube.com/watch?v=kqtD5dpn9C8"},
        {"title": "Advanced Python", "url": "https://www.youtube.com/watch?v=adv123"},
    ])

    test_env["mock_backend"].canned_responses["Open the first result"] = {
        "objective": "Open the first search result",
        "is_complete": True,
        "steps": [
            {
                "step_id": 1,
                "action": "browser_open",
                "arguments": {"ordinal": 1},
                "target_type": "SEARCH_RESULT",
                "target_reference": "1",
                "rationale": "Open first search result",
                "expected_evidence": "VALUE_CHECK",
            }
        ],
        "confidence": 0.98,
    }

    res = await coord.execute_task("Open the first result")
    assert res.status == ExecutionHandoffStatus.COMPLETED
    assert res.steps_executed == 1
    # Argument was grounded by HermesPlanValidator to the canonical URL
    assert res.step_history[0]["arguments"]["url"] == "https://www.youtube.com/watch?v=kqtD5dpn9C8"


@pytest.mark.asyncio
async def test_category_b_open_result_with_missing_context_rejects(test_env):
    """[SIMULATED INTEGRATION] 'Open the first result' without search session is rejected by SERA validator."""
    coord = test_env["coordinator"]

    test_env["mock_backend"].canned_responses["Open the first result"] = {
        "objective": "Open the first search result",
        "is_complete": True,
        "steps": [
            {
                "step_id": 1,
                "action": "browser_open",
                "arguments": {"ordinal": 1},
                "target_type": "SEARCH_RESULT",
                "target_reference": "1",
                "rationale": "Open first search result",
                "expected_evidence": "VALUE_CHECK",
            }
        ],
        "confidence": 0.98,
    }

    res = await coord.execute_task("Open the first result")
    assert res.status == ExecutionHandoffStatus.FAILED
    assert res.error == "UNRESOLVED_ENTITY"
    assert "No active search results in context" in res.response_text
    assert res.steps_executed == 0


# =========================================================================
# Category C — Browser Multi-Step (Search + Continuation)
# =========================================================================
@pytest.mark.asyncio
async def test_category_c_browser_multi_step_flow(test_env):
    """[SIMULATED INTEGRATION] Multi-step YouTube search followed by continuation opening result."""
    coord = test_env["coordinator"]

    res = await coord.execute_task("Search YouTube for Python tutorials and open the first result")

    assert res.status == ExecutionHandoffStatus.COMPLETED
    assert res.steps_executed == 2
    assert res.telemetry.turns in (2, 3)
    assert len(res.step_history) == 2

    # Turn 1: Search YouTube
    step1 = res.step_history[0]
    assert step1["action"] == "youtube_search"
    assert step1["status"] == "VERIFIED_SUCCESS"

    # Turn 2: Open first result URL
    step2 = res.step_history[1]
    assert step2["action"] == "browser_open"
    assert "youtube.com" in step2["arguments"]["url"]
    assert step2["status"] == "VERIFIED_SUCCESS"


# =========================================================================
# Category D — Settings
# =========================================================================
@pytest.mark.asyncio
async def test_category_d_brightness_setting(test_env):
    """[SIMULATED INTEGRATION] 'Make the screen dimmer' executed through SERA substrate."""
    coord = test_env["coordinator"]
    res = await coord.execute_task("Make the screen dimmer")

    assert res.status == ExecutionHandoffStatus.COMPLETED
    assert res.steps_executed == 1
    assert res.step_history[0]["action"] == "set_brightness"


# =========================================================================
# Category E — Cancellation
# =========================================================================
@pytest.mark.asyncio
async def test_category_e_cancellation_during_execution(test_env):
    """[SIMULATED INTEGRATION] Immediate task cancellation terminates execution without running tools."""
    coord = test_env["coordinator"]
    cancel_ev = asyncio.Event()
    cancel_ev.set()  # Cancelled before start

    res = await coord.execute_task("Bring Chrome forward", cancellation_event=cancel_ev)
    assert res.status == ExecutionHandoffStatus.CANCELLED
    assert res.steps_executed == 0


# =========================================================================
# Category F — Destructive Action Permission Flow
# =========================================================================
@pytest.mark.asyncio
async def test_category_f_destructive_action_pauses_for_approval(test_env):
    """[SIMULATED INTEGRATION] 'Close Notepad' pauses with PAUSED_APPROVAL when no auto-approval handler exists."""
    coord = test_env["coordinator"]
    res = await coord.execute_task("Close Notepad")

    assert res.status == ExecutionHandoffStatus.PAUSED_APPROVAL
    assert res.steps_executed == 0
    assert len(coord.pending_approvals) == 1
    perm_id = list(coord.pending_approvals.keys())[0]
    assert "perm_" in perm_id
    assert coord.pending_approvals[perm_id].risk_level == RiskLevel.DESTRUCTIVE


@pytest.mark.asyncio
async def test_category_f_destructive_action_approved(test_env):
    """[SIMULATED INTEGRATION] 'Close Notepad' succeeds when approval is granted."""
    coord = test_env["coordinator"]
    coord.mock_approval_mode = "APPROVE"

    from unittest.mock import AsyncMock
    close_tool = test_env["tools"].get("close_application")
    close_tool.execute = AsyncMock(return_value={
        "success": True,
        "verified": True,
        "application": "notepad",
        "message": "Closed Notepad.",
    })

    res = await coord.execute_task("Close Notepad")
    assert res.status == ExecutionHandoffStatus.COMPLETED
    assert res.steps_executed == 1
    assert res.telemetry.approval_interruptions == 1
    assert res.step_history[0]["action"] == "close_application"


@pytest.mark.asyncio
async def test_category_f_destructive_action_denied(test_env):
    """[SIMULATED INTEGRATION] 'Close Notepad' halts when user denies permission."""
    coord = test_env["coordinator"]
    coord.mock_approval_mode = "DENY"

    res = await coord.execute_task("Close Notepad")
    assert res.status == ExecutionHandoffStatus.FAILED
    assert res.error == "PERMISSION_DENIED"
    assert res.steps_executed == 0


@pytest.mark.asyncio
async def test_category_f_destructive_action_cancelled(test_env):
    """[SIMULATED INTEGRATION] 'Close Notepad' cancels when user cancels request."""
    coord = test_env["coordinator"]
    coord.mock_approval_mode = "CANCEL"

    res = await coord.execute_task("Close Notepad")
    assert res.status == ExecutionHandoffStatus.CANCELLED
    assert res.steps_executed == 0


@pytest.mark.asyncio
async def test_category_f_destructive_action_expired(test_env):
    """[SIMULATED INTEGRATION] 'Close Notepad' fails when permission request expires."""
    coord = test_env["coordinator"]
    coord.mock_approval_mode = "EXPIRE"

    res = await coord.execute_task("Close Notepad")
    assert res.status == ExecutionHandoffStatus.FAILED
    assert res.error == "APPROVAL_EXPIRED"
    assert res.steps_executed == 0


# =========================================================================
# Category G — Failure Boundaries & Validation Rejection
# =========================================================================
@pytest.mark.asyncio
async def test_category_g_unsupported_capability_rejection(test_env):
    """[SIMULATED INTEGRATION] Hallucinated/unsupported tool is strictly rejected by SERA validator."""
    coord = test_env["coordinator"]
    test_env["mock_backend"].canned_responses["Hack the server"] = {
        "objective": "Unauthorized tool test",
        "is_complete": True,
        "steps": [
            {
                "step_id": 1,
                "action": "hack_mainframe",
                "arguments": {"target": "mainframe"},
                "expected_evidence": "VALUE_CHECK",
            }
        ],
        "confidence": 0.9,
    }

    res = await coord.execute_task("Hack the server")
    assert res.status == ExecutionHandoffStatus.FAILED
    assert res.error == "UNSUPPORTED_CAPABILITY"
    assert res.steps_executed == 0


@pytest.mark.asyncio
async def test_category_g_ambiguous_target_rejection(test_env):
    """[SIMULATED INTEGRATION] Tool with missing target argument is rejected by SERA validator."""
    coord = test_env["coordinator"]
    test_env["mock_backend"].canned_responses["Open app"] = {
        "objective": "Launch app without name",
        "is_complete": True,
        "steps": [
            {
                "step_id": 1,
                "action": "open_application",
                "arguments": {},
                "expected_evidence": "WINDOW_HANDLE",
            }
        ],
        "confidence": 0.5,
    }

    res = await coord.execute_task("Open app")
    assert res.status == ExecutionHandoffStatus.FAILED
    assert res.error == "AMBIGUOUS_TARGET"
    assert res.steps_executed == 0
