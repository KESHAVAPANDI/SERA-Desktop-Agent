"""
Automated validation of Shadow Mode Semantic Interpretation (Phase 3A-D).
Verifies that CommandPipeline executes the legacy parser while concurrently running
Qwen3.5-4B in shadow mode, logging SEMANTIC_SHADOW agreement telemetry.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.core.command_pipeline import CommandPipeline
from app.core.command import CommandObject, CommandCategory, CommandComplexity
from app.core.semantic.schema import CanonicalIntent, SemanticTarget, SemanticModifiers
from app.core.graph.state import GraphState


@pytest.mark.asyncio
async def test_semantic_shadow_mode_execution(caplog):
    """Test that _record_semantic_shadow logs comparison and stores shadow telemetry."""
    from app.core.state import SERAState
    from app.core.events import EventBus

    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    mock_intent = CanonicalIntent(
        intent="open_application",
        action_family="APPLICATION",
        target=SemanticTarget(type="application", value="chrome"),
        modifiers=SemanticModifiers(repeat=True),
        confidence=0.96
    )

    pipeline.semantic_interpreter.interpret_async = AsyncMock(return_value=mock_intent)

    legacy_cmd = CommandObject(
        command_id="cmd_1",
        task_id="task_1",
        source_text="Could you bring Chrome back up for me?",
        intent="open_application",
        category=CommandCategory.APPLICATIONS,
        complexity=CommandComplexity.SIMPLE,
        entities={"application": "chrome"}
    )

    with caplog.at_level("INFO"):
        comparison = await pipeline._record_semantic_shadow(
            "Could you bring Chrome back up for me?",
            ctx={"last_application": "chrome"},
            legacy_cmd=legacy_cmd
        )

    assert comparison["agreement"] is True
    assert comparison["intent_match"] is True
    assert comparison["target_match"] is True
    assert comparison["legacy"]["intent"] == "open_application"
    assert comparison["qwen"]["intent"] == "open_application"
    assert comparison["qwen"]["modifiers"]["repeat"] is True
    assert pipeline.last_semantic_shadow == comparison
    assert pipeline.last_canonical_intent == mock_intent.to_dict()

    # Verify log output matches the requested format
    assert "SEMANTIC_SHADOW:" in caplog.text
    assert 'transcript="Could you bring Chrome back up for me?"' in caplog.text
    assert "legacy=intent=open_application,target=chrome" in caplog.text
    assert "qwen=intent=open_application,target=chrome" in caplog.text
    assert "agreement=True" in caplog.text


def test_graph_state_serializes_semantic_fields():
    """Verify GraphState accurately serializes and deserializes canonical_intent & semantic_shadow."""
    shadow_data = {
        "transcript": "Open Chrome",
        "agreement": True,
        "legacy": {"intent": "open_application"},
        "qwen": {"intent": "open_application"}
    }
    canonical_data = {
        "intent": "open_application",
        "action_family": "APPLICATION",
        "target": {"type": "application", "value": "chrome"}
    }

    state = GraphState(
        raw_user_input="Open Chrome",
        task_id="test_task_123",
        canonical_intent=canonical_data,
        semantic_shadow=shadow_data
    )

    d = state.to_dict()
    assert d["canonical_intent"] == canonical_data
    assert d["semantic_shadow"] == shadow_data

    reconstituted = GraphState.from_dict(d)
    assert reconstituted.canonical_intent == canonical_data
    assert reconstituted.semantic_shadow == shadow_data
