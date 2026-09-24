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


@pytest.mark.asyncio
async def test_single_active_shadow_task_cancels_previous():
    """Verify launching a new turn cancels the previous in-flight shadow task to prevent queue accumulation."""
    from app.core.state import SERAState
    from app.core.events import EventBus

    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    # Create a simulated hanging shadow task for turn 1
    async def hanging_shadow(*args, **kwargs):
        await asyncio.sleep(10.0)
        return {}

    pipeline._record_semantic_shadow = hanging_shadow

    # Turn 1
    await pipeline.execute_text("Open Chrome")
    task_1 = pipeline._active_shadow_task
    assert task_1 is not None
    assert not task_1.done()

    # Turn 2: should cancel task_1 immediately
    await pipeline.execute_text("Launch Notepad")
    task_2 = pipeline._active_shadow_task
    assert task_2 is not None
    assert (hasattr(task_1, "cancelling") and task_1.cancelling() > 0) or task_1.cancelled() or task_1.done()
    assert task_2 != task_1

    # Clean up
    if task_2 and not task_2.done():
        task_2.cancel()


@pytest.mark.asyncio
async def test_shadow_timeout_does_not_break_live_execution():
    """Verify that a semantic interpreter timeout in shadow mode never fails the main live task."""
    from app.core.state import SERAState
    from app.core.events import EventBus

    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    # Simulate timeout in shadow interpreter
    pipeline.semantic_interpreter.interpret_async = AsyncMock(side_effect=asyncio.TimeoutError("Simulated timeout"))

    # Execute text: should execute legacy path successfully without raising
    result = await pipeline.execute_text("Open Chrome")
    assert result is not None
    assert result.get("success") is True or "chrome" in result.get("response", "").lower()
    # Ensure error from shadow mode didn't propagate as a task failure
    assert result.get("error") != "Simulated timeout"


@pytest.mark.asyncio
async def test_ollama_provider_passes_native_think_and_keep_alive():
    """Verify OllamaProvider explicitly passes think: false and keep_alive in chat payload."""
    from app.models.llm.ollama import OllamaProvider
    from unittest.mock import patch, MagicMock

    provider = OllamaProvider(model="qwen3.5:4b", keep_alive="10m")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {"content": '{"intent": "open_application"}'},
        "total_duration": 1500000000,
        "load_duration": 5000000,
        "prompt_eval_duration": 200000000,
        "eval_duration": 1200000000,
        "prompt_eval_count": 500,
        "eval_count": 50,
    }

    with patch.object(provider, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_get_client.return_value = mock_client

        content = await provider.generate_structured(
            messages=[{"role": "user", "content": "Open Chrome"}],
            think=False
        )

        assert content == '{"intent": "open_application"}'
        # Verify call arguments
        call_kwargs = mock_client.post.call_args.kwargs
        payload = call_kwargs["json"]
        assert payload["think"] is False
        assert payload["keep_alive"] == "10m"
        assert payload["format"] == "json"

        # Verify metadata extraction
        assert provider.last_metadata["total_duration_ms"] == 1500.0
        assert provider.last_metadata["load_duration_ms"] == 5.0
        assert provider.last_metadata["eval_count"] == 50
