"""
SERA 2.0 / Phase 4A — Hermes Bridge Unit & Contract Tests.

Validates the thin Hermes adapter, cancellation semantics, failure boundaries,
timeout guards, permission boundaries, and conversion to CommandObjects.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.adapters.hermes.schema import (
    AgentPlan,
    AgentStep,
    HermesMode,
    PermissionRequirement,
    RiskLevel,
    ApprovalStatus,
)
from app.adapters.hermes.bridge import (
    SeraHermesBridge,
    MockHermesClient,
)
from app.core.command import CommandObject, CommandCategory, CommandComplexity


@pytest.mark.asyncio
async def test_hermes_bridge_submit_simple_task():
    """Bridge submits a user request and receives a structured AgentPlan."""
    mock_backend = MockHermesClient()
    bridge = SeraHermesBridge(backend=mock_backend)

    plan = await bridge.submit_task("Open Chrome", context={"active_application": "desktop"})
    assert isinstance(plan, AgentPlan)
    assert plan.finish_reason == "stop"
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "open_application"
    assert plan.steps[0].arguments == {"application": "chrome"}
    assert plan.steps[0].expected_evidence == "WINDOW_HANDLE"
    assert plan.latency_ms > 0.0


@pytest.mark.asyncio
async def test_hermes_bridge_destructive_action_permission_boundary():
    """Destructive actions like closing an application generate a PENDING_APPROVAL requirement."""
    mock_backend = MockHermesClient()
    bridge = SeraHermesBridge(backend=mock_backend)

    plan = await bridge.submit_task("Close Notepad", context={})
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.action == "close_application"
    assert step.requires_confirmation is True
    assert step.permission is not None
    assert step.permission.status == ApprovalStatus.PENDING_APPROVAL
    assert step.permission.risk_level == RiskLevel.DESTRUCTIVE
    assert "perm_" in step.permission.request_id


@pytest.mark.asyncio
async def test_hermes_bridge_cancellation_semantics():
    """Cancelling an active task halts execution immediately and sets finish_reason='cancelled'."""
    mock_backend = MockHermesClient()
    mock_backend.delay_seconds = 2.0  # Simulate reasoning latency
    bridge = SeraHermesBridge(backend=mock_backend)

    task_id = "test_cancel_task_123"

    # Start task in background
    submit_coro = asyncio.create_task(bridge.submit_task("Bring Chrome forward", task_id=task_id))
    await asyncio.sleep(0.1)

    # Cancel task
    cancelled = bridge.cancel_task(task_id)
    assert cancelled is True

    plan = await submit_coro
    assert plan.finish_reason == "cancelled"
    assert len(plan.steps) == 0

    trace = bridge.inspect_trace(task_id)
    assert any("Cancellation" in t.content for t in trace)


@pytest.mark.asyncio
async def test_hermes_bridge_timeout_handling():
    """Bridge catches timeouts and returns a clean clarification plan without crashing."""
    mock_backend = MockHermesClient()
    mock_backend.should_timeout = True
    bridge = SeraHermesBridge(backend=mock_backend)

    plan = await bridge.submit_task("Complex multi-step reasoning", timeout=0.2)
    assert plan.finish_reason == "timeout"
    assert plan.needs_clarification is True
    assert "timed out" in plan.clarification_prompt.lower()
    assert len(plan.steps) == 0


@pytest.mark.asyncio
async def test_hermes_bridge_offline_error_boundary():
    """When Hermes backend raises an unhandled error, bridge falls back safely with 0 tool executions."""
    mock_backend = MockHermesClient()
    mock_backend.should_fail = True
    mock_backend.failure_error = "Ollama/Hermes connection refused at 127.0.0.1:11434"
    bridge = SeraHermesBridge(backend=mock_backend)

    plan = await bridge.submit_task("Open Chrome")
    assert plan.finish_reason == "error"
    assert plan.needs_clarification is True
    assert len(plan.steps) == 0


@pytest.mark.asyncio
async def test_hermes_bridge_ambiguous_input_demands_clarification():
    """Ambiguous pronouns or bare verbs without context must demand clarification."""
    mock_backend = MockHermesClient()
    bridge = SeraHermesBridge(backend=mock_backend)

    for ambiguous in ("Open that", "Close it", "Launch", "Please open"):
        plan = await bridge.submit_task(ambiguous, context={})
        assert plan.needs_clarification is True
        assert len(plan.steps) == 0
        assert plan.clarification_prompt is not None


def test_convert_agent_plan_to_command_object():
    """Converting an AgentPlan yields a valid SERA CommandObject."""
    bridge = SeraHermesBridge()
    plan = AgentPlan(
        task_id="t_convert",
        objective="Set brightness to 30%",
        steps=[
            AgentStep(
                step_id=1,
                action="set_brightness",
                arguments={"brightness": 30},
                rationale="Lower brightness",
                expected_evidence="VALUE_CHECK",
            )
        ],
    )

    cmd = bridge.convert_to_command_object(plan, context={})
    assert isinstance(cmd, CommandObject)
    assert cmd.intent == "set_brightness"
    assert cmd.category == CommandCategory.SYSTEM
    assert len(cmd.execution_plan) == 1
    assert cmd.execution_plan[0].action == "set_brightness"
    assert cmd.execution_plan[0].arguments == {"brightness": 30}
    assert cmd.execution_plan[0].verification_type == "VALUE_CHECK"
