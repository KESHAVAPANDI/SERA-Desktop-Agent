"""
SERA 2.0 / Phase 4B.1 — Test Suite for Hermes Live Acceptance Corrections & Execution Control.

Covers:
- Category A: Clarification as terminal turn outcome ("Open that" with no referent -> WAITING_FOR_CLARIFICATION)
- Category B: Destructive action approval pause & single-step execution ("Close Notepad" -> PAUSED_APPROVAL -> APPROVE -> COMPLETED)
- Category C: Approval denial, cancellation, and expiration (DENY -> FAILED, CANCEL -> CANCELLED, EXPIRE -> FAILED)
- Category D: Multi-step objective boundaries ("Search YouTube... and open first result" -> search + open -> stops, NO runaway videos)
- Category E: Pure search objective boundaries ("Search YouTube..." -> search -> stops, NO video opened)
- Category F: Browser tab switching (browser_switch_tab -> focus_browser_tab, TargetType.TAB, verified)
- Category G: Browser tab closing (browser_close_tab -> close_browser_tab, TargetType.TAB, verified)
- Category H: Window focus verification (bring_window_forward -> focus_desktop_window, TargetType.WINDOW)
- Category I: Deterministic cancellation during reasoning/continuation
- Category J: Unsupported capability rejection without infinite retry
- Category K: No-progress loop detection protection
- Category L: Startup mode and Command Center runtime truth consistency
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, patch

from app.adapters.hermes.bridge import MockSimulationHermesClient, SeraHermesBridge
from app.adapters.hermes.coordinator import HermesExecutionCoordinator
from app.adapters.hermes.schema import (
    AgentStep,
    ApprovalDecision,
    ExecutionHandoffStatus,
    HermesMode,
    RiskLevel,
    TargetType,
    resolve_hermes_mode,
)
from app.core.context.store import ContextStore, SearchResultEntity, SearchSession
from app.tools import create_tool_registry


@pytest.fixture
def test_env():
    """Builds an isolated test harness with mock Hermes client and real SERA tools."""
    mock_client = MockSimulationHermesClient()
    bridge = SeraHermesBridge(backend=mock_client, mode=HermesMode.HERMES_EXPERIMENTAL)
    context_store = ContextStore()
    tools = create_tool_registry()

    coordinator = HermesExecutionCoordinator(
        bridge=bridge,
        context_store=context_store,
        tool_registry=tools,
    )

    return {
        "client": mock_client,
        "bridge": bridge,
        "context_store": context_store,
        "tools": tools,
        "coordinator": coordinator,
    }


# =========================================================================
# Category A: Clarification as Terminal Turn Outcome
# =========================================================================
@pytest.mark.asyncio
async def test_category_a_open_that_with_no_referent_waits_for_clarification(test_env):
    """[SIMULATED INTEGRATION] 'Open that' with no verified referent enters WAITING_FOR_CLARIFICATION without spinning."""
    coord = test_env["coordinator"]
    client = test_env["client"]

    client.canned_responses["Open that"] = {
        "objective": "Open requested target",
        "steps": [
            {
                "step_id": 1,
                "action": "open_application",
                "arguments": {"application": "that"},
                "target_reference": "that",
            }
        ],
        "is_complete": False,
    }

    # When context is empty, "that" has no grounded referent
    res = await coord.execute_task("Open that")

    assert res.status == ExecutionHandoffStatus.WAITING_FOR_CLARIFICATION
    assert res.steps_executed == 0
    assert "Which one do you mean?" in res.response_text
    assert len(coord.pending_clarifications) == 1
    assert res.telemetry.turns == 1


# =========================================================================
# Category B: Approval Flow — Pausing and Single-Step Resumption
# =========================================================================
@pytest.mark.asyncio
async def test_category_b_destructive_action_pauses_and_executes_once_on_approval(test_env):
    """[SIMULATED INTEGRATION] 'Close Notepad' pauses with PAUSED_APPROVAL, and resolve_approval(APPROVE) runs exactly once."""
    coord = test_env["coordinator"]
    client = test_env["client"]

    client.canned_responses["Close Notepad"] = {
        "objective": "Close application Notepad",
        "steps": [
            {
                "step_id": 1,
                "action": "close_application",
                "arguments": {"application": "notepad"},
                "requires_confirmation": True,
            }
        ],
        "is_complete": True,
    }

    close_tool = test_env["tools"].get("close_application")
    mock_exec = AsyncMock(return_value={
        "success": True,
        "verified": True,
        "application": "notepad",
        "message": "Terminated application 'notepad'.",
    })
    close_tool.execute = mock_exec

    # Step 1: Execute task -> should pause cleanly
    res = await coord.execute_task("Close Notepad")
    assert res.status in (ExecutionHandoffStatus.PAUSED_APPROVAL, ExecutionHandoffStatus.WAITING_FOR_APPROVAL)
    assert res.steps_executed == 0
    assert len(coord.pending_approvals) == 1

    req_id = list(coord.pending_approvals.keys())[0]
    ctx = coord.pending_approvals[req_id]
    assert ctx.action == "close_application"
    assert ctx.risk_level == RiskLevel.DESTRUCTIVE
    mock_exec.assert_not_called()

    # Step 2: Programmatic approval resolution
    res_approved = await coord.resolve_approval(req_id, ApprovalDecision.APPROVE)

    assert res_approved.status == ExecutionHandoffStatus.COMPLETED
    assert res_approved.steps_executed == 1
    mock_exec.assert_called_once()
    assert len(coord.pending_approvals) == 0


# =========================================================================
# Category C: Approval Flow — Denied, Cancelled, Expired
# =========================================================================
@pytest.mark.asyncio
async def test_category_c_destructive_action_denied(test_env):
    """[SIMULATED INTEGRATION] Denying approval halts task in FAILED state with PERMISSION_DENIED and no execution."""
    coord = test_env["coordinator"]
    client = test_env["client"]

    client.canned_responses["Close Notepad"] = {
        "objective": "Close application Notepad",
        "steps": [
            {
                "step_id": 1,
                "action": "close_application",
                "arguments": {"application": "notepad"},
                "requires_confirmation": True,
            }
        ],
        "is_complete": True,
    }

    close_tool = test_env["tools"].get("close_application")
    close_tool.execute = AsyncMock()

    res = await coord.execute_task("Close Notepad")
    req_id = list(coord.pending_approvals.keys())[0]

    res_denied = await coord.resolve_approval(req_id, ApprovalDecision.DENY)
    assert res_denied.status == ExecutionHandoffStatus.FAILED
    assert res_denied.error == "PERMISSION_DENIED"
    assert "denied by user permission policy" in res_denied.response_text
    close_tool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_category_c_destructive_action_cancelled(test_env):
    """[SIMULATED INTEGRATION] Cancelling approval transitions to CANCELLED without tool execution."""
    coord = test_env["coordinator"]
    client = test_env["client"]

    client.canned_responses["Close Notepad"] = {
        "objective": "Close application Notepad",
        "steps": [
            {
                "step_id": 1,
                "action": "close_application",
                "arguments": {"application": "notepad"},
                "requires_confirmation": True,
            }
        ],
        "is_complete": True,
    }

    close_tool = test_env["tools"].get("close_application")
    close_tool.execute = AsyncMock()

    res = await coord.execute_task("Close Notepad")
    req_id = list(coord.pending_approvals.keys())[0]

    res_cancelled = await coord.resolve_approval(req_id, ApprovalDecision.CANCEL)
    assert res_cancelled.status == ExecutionHandoffStatus.CANCELLED
    assert "Task cancelled" in res_cancelled.response_text
    close_tool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_category_c_destructive_action_expired(test_env):
    """[SIMULATED INTEGRATION] Expiring approval transitions to FAILED with APPROVAL_EXPIRED."""
    coord = test_env["coordinator"]
    client = test_env["client"]

    client.canned_responses["Close Notepad"] = {
        "objective": "Close application Notepad",
        "steps": [
            {
                "step_id": 1,
                "action": "close_application",
                "arguments": {"application": "notepad"},
                "requires_confirmation": True,
            }
        ],
        "is_complete": True,
    }

    res = await coord.execute_task("Close Notepad")
    req_id = list(coord.pending_approvals.keys())[0]

    res_expired = await coord.resolve_approval(req_id, ApprovalDecision.EXPIRE)
    assert res_expired.status == ExecutionHandoffStatus.FAILED
    assert res_expired.error == "APPROVAL_EXPIRED"


# =========================================================================
# Category D: Multi-Step Objective Boundaries (Search + Open First Result)
# =========================================================================
@pytest.mark.asyncio
async def test_category_d_search_and_open_first_result_stops_after_single_open(test_env):
    """[SIMULATED INTEGRATION] 'Search YouTube for Python tutorials and open the first result'
    executes search, opens result #1, verifies, and STOPS without opening result #2.
    """
    coord = test_env["coordinator"]
    client = test_env["client"]

    client.canned_responses["Search YouTube for Python tutorials and open the first result."] = {
        "objective": "Search YouTube for Python tutorials and open the first result.",
        "steps": [
            {
                "action": "youtube_search",
                "arguments": {"query": "Python tutorials"},
                "expected_evidence": "SEARCH_RESULTS",
            }
        ],
        "is_complete": False,
    }

    client.canned_continuation_response = {
        "objective": "Open first search result",
        "steps": [
            {
                "action": "browser_open",
                "arguments": {"url": "https://www.youtube.com/watch?v=python1"},
                "target_type": "SEARCH_RESULT",
                "target_reference": "1",
            }
        ],
        "is_complete": True,
    }

    browser_open_count = 0
    real_browser_tool = test_env["tools"].get("browser_open")

    async def mock_browser_open(**kwargs):
        nonlocal browser_open_count
        browser_open_count += 1
        return {"success": True, "verified": True, "tab_id": "tab_python", "url": kwargs.get("url")}

    real_browser_tool.execute = mock_browser_open

    res = await coord.execute_task("Search YouTube for Python tutorials and open the first result.")

    assert res.status == ExecutionHandoffStatus.COMPLETED
    assert res.steps_executed == 2
    assert browser_open_count == 1  # Opened EXACTLY 1 video, did not continue to video 2 or 3!
    assert res.step_history[0]["action"] == "youtube_search"
    assert res.step_history[1]["action"] == "browser_open"


# =========================================================================
# Category E: Pure Search Objective Boundaries
# =========================================================================
@pytest.mark.asyncio
async def test_category_e_pure_search_stops_without_opening_results(test_env):
    """[SIMULATED INTEGRATION] 'Search YouTube for Python tutorials' satisfies objective upon verified search
    and MUST NOT continue to open any video results.
    """
    coord = test_env["coordinator"]
    client = test_env["client"]

    client.canned_responses["Search YouTube for Python tutorials."] = {
        "objective": "Search YouTube for Python tutorials.",
        "steps": [
            {
                "action": "youtube_search",
                "arguments": {"query": "Python tutorials"},
                "expected_evidence": "SEARCH_RESULTS",
            }
        ],
        "is_complete": False,  # Even if Hermes sets is_complete=False, SERA objective check stops it!
    }

    browser_tool = test_env["tools"].get("browser_open")
    browser_tool.execute = AsyncMock()

    res = await coord.execute_task("Search YouTube for Python tutorials.")

    assert res.status == ExecutionHandoffStatus.COMPLETED
    assert res.steps_executed == 1
    assert res.step_history[0]["action"] == "youtube_search"
    browser_tool.execute.assert_not_called()


# =========================================================================
# Category F: Browser Tab Switching
# =========================================================================
@pytest.mark.asyncio
async def test_category_f_browser_switch_tab_normalizes_and_verifies(test_env):
    """[SIMULATED INTEGRATION] 'browser_switch_tab' is recognized by capability inventory,
    normalizes to 'focus_browser_tab', targets TargetType.TAB, and verifies.
    """
    coord = test_env["coordinator"]
    validator = coord.validator

    # 1. Validator Contract check
    step = AgentStep(
        step_id=1,
        action="browser_switch_tab",
        arguments={"tab_identifier": "YouTube"},
    )
    val_res = validator.validate_step(step)
    assert val_res.is_valid is True
    assert step.action == "focus_browser_tab"
    assert step.target_type == TargetType.TAB

    # 2. Execution check
    focus_tool = test_env["tools"].get("focus_browser_tab")
    focus_tool.execute = AsyncMock(return_value={
        "success": True,
        "verified": True,
        "tab_id": "tab_yt",
        "title": "YouTube",
        "message": "Switched to tab 'YouTube'.",
    })

    client = test_env["client"]
    client.canned_responses["Switch to the YouTube tab."] = {
        "objective": "Switch to the YouTube tab.",
        "steps": [
            {
                "action": "browser_switch_tab",
                "arguments": {"tab_identifier": "YouTube"},
            }
        ],
        "is_complete": True,
    }

    res = await coord.execute_task("Switch to the YouTube tab.")
    assert res.status == ExecutionHandoffStatus.COMPLETED
    assert res.steps_executed == 1
    assert res.step_history[0]["action"] == "focus_browser_tab"


# =========================================================================
# Category G: Browser Tab Closing
# =========================================================================
@pytest.mark.asyncio
async def test_category_g_browser_close_tab_normalizes_and_verifies(test_env):
    """[SIMULATED INTEGRATION] 'browser_close_tab' is recognized, normalizes to 'close_browser_tab',
    targets TargetType.TAB, and verifies tab closure without process kill.
    """
    coord = test_env["coordinator"]
    validator = coord.validator

    step = AgentStep(
        step_id=1,
        action="browser_close_tab",
        arguments={"tab_identifier": "this"},
    )
    val_res = validator.validate_step(step)
    assert val_res.is_valid is True
    assert step.action == "close_browser_tab"
    assert step.target_type == TargetType.TAB

    close_tab_tool = test_env["tools"].get("close_browser_tab")
    close_tab_tool.execute = AsyncMock(return_value={
        "success": True,
        "verified": True,
        "tab_id": "tab_1",
        "message": "Closed tab.",
    })

    client = test_env["client"]
    client.canned_responses["Close this tab."] = {
        "objective": "Close this tab.",
        "steps": [
            {
                "action": "browser_close_tab",
                "arguments": {"tab_identifier": "this"},
            }
        ],
        "is_complete": True,
    }

    res = await coord.execute_task("Close this tab.")
    assert res.status == ExecutionHandoffStatus.COMPLETED
    assert res.steps_executed == 1
    assert res.step_history[0]["action"] == "close_browser_tab"


# =========================================================================
# Category H: Window Focus Verification
# =========================================================================
@pytest.mark.asyncio
async def test_category_h_window_focus_targets_window_not_tab(test_env):
    """[SIMULATED INTEGRATION] 'bring_window_forward' normalizes to 'focus_desktop_window',
    preserves TargetType.WINDOW (does not silently convert to TAB), and verifies.
    """
    coord = test_env["coordinator"]
    validator = coord.validator

    step = AgentStep(
        step_id=1,
        action="bring_window_forward",
        arguments={"window_name": "Google Chrome"},
    )
    val_res = validator.validate_step(step)
    assert val_res.is_valid is True
    assert step.action == "focus_desktop_window"
    assert step.target_type == TargetType.WINDOW

    focus_win_tool = test_env["tools"].get("focus_desktop_window")
    focus_win_tool.execute = AsyncMock(return_value={
        "success": True,
        "verified": True,
        "window_name": "Google Chrome",
        "message": "Brought 'Google Chrome' to foreground.",
    })

    client = test_env["client"]
    client.canned_responses["Bring the browser window forward."] = {
        "objective": "Bring the browser window forward.",
        "steps": [
            {
                "action": "bring_window_forward",
                "arguments": {"window_name": "Google Chrome"},
            }
        ],
        "is_complete": True,
    }

    res = await coord.execute_task("Bring the browser window forward.")
    assert res.status == ExecutionHandoffStatus.COMPLETED
    assert res.steps_executed == 1
    assert res.step_history[0]["action"] == "focus_desktop_window"


# =========================================================================
# Category I: Cancellation During Reasoning
# =========================================================================
@pytest.mark.asyncio
async def test_category_i_cancellation_halts_task_immediately(test_env):
    """[SIMULATED INTEGRATION] Triggering cancellation_event immediately halts task in CANCELLED state."""
    coord = test_env["coordinator"]
    cancel_ev = asyncio.Event()
    cancel_ev.set()

    res = await coord.execute_task("Open Notepad", cancellation_event=cancel_ev)
    assert res.status == ExecutionHandoffStatus.CANCELLED
    assert res.steps_executed == 0


# =========================================================================
# Category J: Unsupported Capability Rejection
# =========================================================================
@pytest.mark.asyncio
async def test_category_j_unsupported_capability_rejected_without_infinite_retry(test_env):
    """[SIMULATED INTEGRATION] Proposing an unregistered/unsupported action halts with clean error
    and does not enter an infinite retry loop.
    """
    coord = test_env["coordinator"]
    client = test_env["client"]

    client.canned_responses["Reformat drive."] = {
        "objective": "Reformat drive.",
        "steps": [
            {
                "action": "reformat_hard_drive",
                "arguments": {"drive": "C:"},
            }
        ],
        "is_complete": False,
    }

    res = await coord.execute_task("Reformat drive.")
    assert res.status == ExecutionHandoffStatus.FAILED
    assert res.error == "UNSUPPORTED_CAPABILITY"
    assert "unavailable" in res.response_text or "rejected" in res.response_text
    assert res.steps_executed == 0


# =========================================================================
# Category K: No-Progress Protection
# =========================================================================
@pytest.mark.asyncio
async def test_category_k_no_progress_loop_detection(test_env):
    """[SIMULATED INTEGRATION] Repeating the exact same step with identical arguments triggers loop detection."""
    coord = test_env["coordinator"]
    client = test_env["client"]

    client.canned_responses["Do redundant action."] = {
        "objective": "Do redundant action.",
        "steps": [
            {
                "action": "set_brightness",
                "arguments": {"brightness": 50},
            },
            {
                "action": "set_brightness",
                "arguments": {"brightness": 50},
            },
        ],
        "is_complete": False,
    }

    bright_tool = test_env["tools"].get("set_brightness")
    bright_tool.execute = AsyncMock(return_value={"success": True, "verified": True, "brightness": 50})

    res = await coord.execute_task("Do redundant action.")
    assert res.status == ExecutionHandoffStatus.FAILED
    assert res.error == "NO_PROGRESS_LOOP_DETECTED"
    assert res.steps_executed == 1


# =========================================================================
# Category L: Startup Mode and Command Center Truth
# =========================================================================
def test_category_l_startup_mode_consistency():
    """[UNIT] Verifies that resolve_hermes_mode() consistently resolves HERMES_EXPERIMENTAL when configured."""
    with patch.dict(os.environ, {"SERA_HERMES_MODE": "hermes_exp"}):
        mode = resolve_hermes_mode()
        assert mode == HermesMode.HERMES_EXPERIMENTAL

    with patch.dict(os.environ, {"SERA_HERMES_MODE": "hermes_shadow"}):
        mode = resolve_hermes_mode()
        assert mode == HermesMode.HERMES_SHADOW

    with patch.dict(os.environ, {"SERA_HERMES_MODE": "current"}):
        mode = resolve_hermes_mode()
        assert mode == HermesMode.CURRENT
