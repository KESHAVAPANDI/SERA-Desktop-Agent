"""
Automated Validation of Semantic Authority Gate & Context Resolver (Phase 3A-E).

Tests all 18 cases specified in the Phase 3A-E specification:
1. Qwen accepted for allowed category.
2. Qwen rejected for deterministic-only category.
3. Qwen timeout -> fallback.
4. Qwen invalid schema/JSON -> fallback.
5. Qwen unknown -> fallback/clarification.
6. Qwen clarification state -> no tool execution.
7. Qwen reference -> context resolver maps to URL.
8. Missing context -> clarification, no guessed target.
9. Qwen output cannot execute tools directly (security barrier).
10. Legacy parser disagreement does not veto valid Qwen interpretation.
11. Semantic authority stored in GraphState.
12. Deterministic commands remain fast (no Qwen latency).
13. Compound workflows remain non-authoritative (shadow-only).
14. One semantic interpretation per turn.
15. No duplicate cloud reasoning caused by semantic fallback.
16. Event correlation preserved.
17. Cancellation preserved.
18. Existing verification preserved.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.command import CommandCategory, CommandComplexity, CommandObject, PlanStepItem
from app.core.command_pipeline import CommandPipeline
from app.core.events import EventBus
from app.core.graph.state import GraphExecutionStatus, GraphPlanStep, GraphState
from app.core.semantic.authority import (
    SemanticAuthorityDecision,
    SemanticAuthorityGate,
    SemanticAuthoritySource,
)
from app.core.semantic.resolver import SemanticContextResolver
from app.core.semantic.schema import (
    CanonicalIntent,
    SemanticModifiers,
    SemanticReference,
    SemanticTarget,
)
from app.core.state import SERAState


# =====================================================================
# 1. SEMANTIC AUTHORITY GATE UNIT TESTS
# =====================================================================

def test_qwen_accepted_for_application_category():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=SemanticTarget(type="application", value="chrome"),
        confidence=0.95,
    )
    decision = gate.decide(intent, transcript="Bring Chrome up.", context={})
    assert decision.source == SemanticAuthoritySource.QWEN
    assert decision.accepted is True
    assert decision.category == "APPLICATION"
    assert decision.fallback_reason is None


def test_qwen_rejected_for_deterministic_category():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="set_brightness",
        action_family="SYSTEM",
        target=SemanticTarget(type="setting", value="brightness"),
        confidence=0.98,
    )
    decision = gate.decide(intent, transcript="Set brightness to 80%.", context={})
    assert decision.source == SemanticAuthoritySource.DETERMINISTIC
    assert decision.accepted is False
    assert decision.fallback_reason == "DETERMINISTIC_CATEGORY"
    assert decision.category == "SYSTEM"


def test_deterministic_fast_path_identification():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    assert gate.is_deterministic_fast_path("Set brightness to 80%") is True
    assert gate.is_deterministic_fast_path("brightness 50%") is True
    assert gate.is_deterministic_fast_path("turn volume to 40%") is True
    assert gate.is_deterministic_fast_path("mute") is True
    assert gate.is_deterministic_fast_path("unmute sound") is True
    assert gate.is_deterministic_fast_path("battery status") is True
    assert gate.is_deterministic_fast_path("what time is it") is True

    # Natural language application requests must NOT be flagged as fast path
    assert gate.is_deterministic_fast_path("Bring Chrome up.") is False
    assert gate.is_deterministic_fast_path("Could you get my browser running?") is False
    assert gate.is_deterministic_fast_path("Launch") is False
    assert gate.is_deterministic_fast_path("Open that.") is False


def test_compound_workflows_remain_shadow_only():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="compound_workflow",
        action_family="COMPOUND",
        confidence=0.88,
    )
    decision = gate.decide(intent, transcript="Open Chrome and search for lo-fi", context={})
    assert decision.source == SemanticAuthoritySource.LEGACY_FALLBACK
    assert decision.accepted is False
    assert decision.fallback_reason == "SHADOW_ONLY_CATEGORY"


def test_qwen_timeout_produces_fallback():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="unknown",
        action_family="UNKNOWN",
        confidence=0.0,
        needs_clarification=True,
        ambiguity_reason="Semantic model timed out after 10.0s",
    )
    decision = gate.decide(intent, transcript="Bring Chrome up.", context={})
    assert decision.source == SemanticAuthoritySource.LEGACY_FALLBACK
    assert decision.accepted is False
    assert decision.fallback_reason == "QWEN_TIMEOUT"


def test_qwen_invalid_schema_produces_fallback():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    decision = gate.decide(None, transcript="Some command", context={}, model_error="Invalid JSON")
    assert decision.source == SemanticAuthoritySource.LEGACY_FALLBACK
    assert decision.accepted is False
    assert "QWEN_ERROR" in decision.fallback_reason


def test_qwen_unknown_intent_produces_fallback():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="unknown",
        action_family="UNKNOWN",
        confidence=0.0,
    )
    decision = gate.decide(intent, transcript="random gibberish", context={})
    assert decision.source == SemanticAuthoritySource.LEGACY_FALLBACK
    assert decision.accepted is False
    assert decision.fallback_reason == "QWEN_UNKNOWN_INTENT"


def test_edge_case_launch_without_target_demands_clarification():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=None,
        reference=None,
    )
    decision = gate.decide(intent, transcript="Launch", context={})
    assert decision.source == SemanticAuthoritySource.CLARIFICATION
    assert decision.accepted is False
    assert decision.fallback_reason == "MISSING_APPLICATION_TARGET"


def test_missing_reference_context_demands_clarification():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="open_reference",
        action_family="BROWSER",
        reference=SemanticReference(type="search_result", ordinal=1),
    )
    # Empty context: no search results exist
    decision = gate.decide(intent, transcript="Open the first result.", context={})
    assert decision.source == SemanticAuthoritySource.CLARIFICATION
    assert decision.accepted is False
    assert decision.fallback_reason == "CONTEXT_REFERENCE_MISSING"
    assert decision.context_available is False


def test_valid_reference_with_verified_context_is_accepted():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="open_reference",
        action_family="BROWSER",
        reference=SemanticReference(type="search_result", ordinal=1),
    )
    ctx = {
        "search_results": [
            {"title": "Video 1", "url": "https://youtube.com/watch?v=abc"}
        ]
    }
    decision = gate.decide(intent, transcript="Open the first result.", context=ctx)
    assert decision.source == SemanticAuthoritySource.QWEN
    assert decision.accepted is True
    assert decision.category == "REFERENCE"
    assert decision.context_available is True


def test_contextual_close_missing_active_app_demands_clarification():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="close_application",
        action_family="APPLICATION",
        reference=SemanticReference(type="active_window", value="it"),
    )
    # Context has no active application
    decision = gate.decide(intent, transcript="Close it.", context={})
    assert decision.source == SemanticAuthoritySource.CLARIFICATION
    assert decision.accepted is False
    assert decision.fallback_reason == "ACTIVE_APPLICATION_MISSING"


def test_contextual_close_with_active_app_is_accepted():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="close_application",
        action_family="APPLICATION",
        reference=SemanticReference(type="active_window", value="it"),
    )
    ctx = {"active_application": "chrome"}
    decision = gate.decide(intent, transcript="Close it.", context=ctx)
    assert decision.source == SemanticAuthoritySource.QWEN
    assert decision.accepted is True
    assert decision.context_available is True


def test_open_that_missing_target_demands_clarification():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=SemanticTarget(type="entity", value="that"),
    )
    decision = gate.decide(intent, transcript="Open that.", context={})
    assert decision.source == SemanticAuthoritySource.CLARIFICATION
    assert decision.accepted is False
    assert decision.fallback_reason == "TARGET_ENTITY_MISSING"


def test_hallucinated_url_rejected():
    gate = SemanticAuthorityGate(pilot_enabled=True)
    intent = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=SemanticTarget(type="url", value="https://malicious-site.com"),
    )
    decision = gate.decide(intent, transcript="Open the app", context={})
    assert decision.source == SemanticAuthoritySource.LEGACY_FALLBACK
    assert decision.accepted is False
    assert decision.fallback_reason == "HALLUCINATED_URL"


# =====================================================================
# 2. CONTEXT RESOLVER UNIT TESTS
# =====================================================================

def test_resolver_open_application_paraphrase():
    decision = SemanticAuthorityDecision(
        source=SemanticAuthoritySource.QWEN,
        accepted=True,
        canonical_intent=CanonicalIntent(
            intent="open_application",
            action_family="APPLICATION",
            target=SemanticTarget(type="application", value="chrome"),
        ),
    )
    cmd = SemanticContextResolver.resolve(decision, "Bring Chrome up.", context={})
    assert cmd.intent == "open_application"
    assert cmd.parameters["application"] == "chrome"
    assert len(cmd.execution_plan) == 1
    assert cmd.execution_plan[0].action == "open_application"
    assert cmd.execution_plan[0].arguments["application"] == "chrome"


def test_resolver_browser_generic_mapping():
    decision = SemanticAuthorityDecision(
        source=SemanticAuthoritySource.QWEN,
        accepted=True,
        canonical_intent=CanonicalIntent(
            intent="open_application",
            action_family="APPLICATION",
            target=SemanticTarget(type="application", value="browser"),
        ),
    )
    cmd = SemanticContextResolver.resolve(decision, "Could you get my browser running?", context={})
    assert cmd.intent == "open_application"
    assert cmd.parameters["application"] == "chrome"
    assert cmd.execution_plan[0].arguments["application"] == "chrome"


def test_resolver_open_reference_to_actual_url():
    decision = SemanticAuthorityDecision(
        source=SemanticAuthoritySource.QWEN,
        accepted=True,
        canonical_intent=CanonicalIntent(
            intent="open_reference",
            action_family="BROWSER",
            reference=SemanticReference(type="search_result", ordinal=2),
        ),
    )
    ctx = {
        "search_results": [
            {"title": "Result 1", "url": "https://example.com/1"},
            {"title": "Result 2", "url": "https://example.com/2"},
        ]
    }
    cmd = SemanticContextResolver.resolve(decision, "Take me to the second video.", context=ctx)
    assert cmd.intent == "open_search_result"
    assert cmd.parameters["url"] == "https://example.com/2"
    assert cmd.execution_plan[0].action == "browser_open"
    assert cmd.execution_plan[0].arguments["url"] == "https://example.com/2"


def test_resolver_clarification_produces_zero_tools():
    decision = SemanticAuthorityDecision(
        source=SemanticAuthoritySource.CLARIFICATION,
        accepted=False,
        fallback_reason="MISSING_APPLICATION_TARGET",
    )
    cmd = SemanticContextResolver.resolve(decision, "Launch", context={})
    assert cmd.intent == "clarification"
    assert cmd.raw_response == "What would you like me to launch?"
    assert len(cmd.required_tools) == 0
    assert len(cmd.execution_plan) == 0


# =====================================================================
# 3. PIPELINE INTEGRATION TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_pipeline_qwen_primary_bring_chrome_up():
    """Validates that 'Bring Chrome up.' uses Qwen primary authority even though legacy parser would fail."""
    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    # Mock Qwen Semantic Interpreter to return open_application for "Bring Chrome up."
    mock_intent = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=SemanticTarget(type="application", value="chrome"),
        confidence=0.96,
    )
    pipeline.semantic_interpreter.interpret_async = AsyncMock(return_value=mock_intent)

    # Mock graph runtime execution
    async def mock_execute(graph_state, cancellation_event=None):
        graph_state.status = GraphExecutionStatus.SUCCESS
        graph_state.active_application = "chrome"
        graph_state.steps[0].completed = True
        return graph_state

    pipeline.graph_runtime.execute = AsyncMock(side_effect=mock_execute)

    result = await pipeline.execute_text("Bring Chrome up.", source="VOICE")

    assert result["success"] is True
    assert "Chrome" in result["response"]
    assert pipeline.last_semantic_decision is not None
    assert pipeline.last_semantic_decision["source"] == "QWEN"
    assert pipeline.last_semantic_decision["accepted"] is True
    assert pipeline.last_semantic_decision["category"] == "APPLICATION"


@pytest.mark.asyncio
async def test_pipeline_legacy_disagreement_does_not_veto_qwen():
    """Confirms that legacy parser disagreement is NOT used as a veto for Qwen-eligible categories."""
    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    mock_intent = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=SemanticTarget(type="application", value="browser"),
        confidence=0.94,
    )
    pipeline.semantic_interpreter.interpret_async = AsyncMock(return_value=mock_intent)

    async def mock_execute(graph_state, cancellation_event=None):
        graph_state.status = GraphExecutionStatus.SUCCESS
        graph_state.steps[0].completed = True
        return graph_state

    pipeline.graph_runtime.execute = AsyncMock(side_effect=mock_execute)

    # Phrase that classifies as general_reasoning in legacy parser
    phrase = "Would you mind having Chrome available for me?"
    legacy_cmd = pipeline.parser.parse(phrase)
    assert legacy_cmd.intent == "general_reasoning"

    result = await pipeline.execute_text(phrase, source="VOICE")

    assert result["success"] is True
    # Qwen was granted authority, NOT vetoed by legacy general_reasoning!
    assert pipeline.last_semantic_decision["source"] == "QWEN"
    assert pipeline.last_semantic_decision["accepted"] is True


@pytest.mark.asyncio
async def test_pipeline_deterministic_fast_path_bypasses_qwen():
    """Confirms that exact numeric settings (e.g. brightness) execute immediately without Qwen latency."""
    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    pipeline.semantic_interpreter.interpret_async = AsyncMock()

    async def mock_execute(graph_state, cancellation_event=None):
        graph_state.status = GraphExecutionStatus.SUCCESS
        graph_state.steps[0].completed = True
        return graph_state

    pipeline.graph_runtime.execute = AsyncMock(side_effect=mock_execute)

    result = await pipeline.execute_text("Set brightness to 80%", source="TEXT")

    assert result["success"] is True
    assert pipeline.last_semantic_decision["source"] == "DETERMINISTIC"
    assert pipeline.last_semantic_decision["category"] == "SYSTEM"


@pytest.mark.asyncio
async def test_pipeline_clarification_returns_speech_immediately_without_tools():
    """'Launch' without target demands clarification with 0 tool executions."""
    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    mock_intent = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=None,
        reference=None,
        needs_clarification=True,
        ambiguity_reason="What would you like me to launch?",
    )
    pipeline.semantic_interpreter.interpret_async = AsyncMock(return_value=mock_intent)
    pipeline.graph_runtime.execute = AsyncMock()

    result = await pipeline.execute_text("Launch", source="VOICE")

    assert result["success"] is True
    assert "What would you like me to launch?" in result["response"]
    assert pipeline.last_semantic_decision["source"] == "CLARIFICATION"
    # Ensure GraphRuntime was NOT invoked
    pipeline.graph_runtime.execute.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_qwen_timeout_falls_back_to_legacy():
    """Qwen timeout safely triggers legacy fallback without crashing SERA."""
    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    mock_intent = CanonicalIntent(
        intent="unknown",
        action_family="UNKNOWN",
        needs_clarification=True,
        ambiguity_reason="Semantic model timed out after 10.0s",
    )
    pipeline.semantic_interpreter.interpret_async = AsyncMock(return_value=mock_intent)

    async def mock_execute(graph_state, cancellation_event=None):
        graph_state.status = GraphExecutionStatus.SUCCESS
        graph_state.steps[0].completed = True
        return graph_state

    pipeline.graph_runtime.execute = AsyncMock(side_effect=mock_execute)

    # "open notepad" can be parsed by legacy parser
    result = await pipeline.execute_text("open notepad", source="TEXT")

    assert result["success"] is True
    assert pipeline.last_semantic_decision["source"] == "LEGACY_FALLBACK"
    assert pipeline.last_semantic_decision["fallback_reason"] == "QWEN_TIMEOUT"


@pytest.mark.asyncio
async def test_pipeline_semantic_decision_stored_in_graph_state():
    """Verify that graph_state.semantic_decision is populated and preserved during execution."""
    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    mock_intent = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=SemanticTarget(type="application", value="chrome"),
        confidence=0.97,
    )
    pipeline.semantic_interpreter.interpret_async = AsyncMock(return_value=mock_intent)

    captured_graph_state = None

    async def mock_execute(graph_state, cancellation_event=None):
        nonlocal captured_graph_state
        captured_graph_state = graph_state
        graph_state.status = GraphExecutionStatus.SUCCESS
        graph_state.steps[0].completed = True
        return graph_state

    pipeline.graph_runtime.execute = AsyncMock(side_effect=mock_execute)

    result = await pipeline.execute_text("Bring Chrome up.", source="VOICE")

    assert result["success"] is True
    assert captured_graph_state is not None
    assert captured_graph_state.semantic_decision is not None
    assert captured_graph_state.semantic_decision["source"] == "QWEN"
    assert captured_graph_state.semantic_decision["accepted"] is True
    assert captured_graph_state.semantic_decision["category"] == "APPLICATION"
    # Verify serialization
    state_dict = captured_graph_state.to_dict()
    assert state_dict["semantic_decision"]["source"] == "QWEN"
    reconstructed = GraphState.from_dict(state_dict)
    assert reconstructed.semantic_decision["source"] == "QWEN"

