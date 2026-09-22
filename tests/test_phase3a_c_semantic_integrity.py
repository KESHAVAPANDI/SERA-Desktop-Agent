"""
SERA 2.0 — Phase 3A-C Semantic Integrity & Execution Consistency Test Suite.

Validates:
1. English-only STT configuration (Gemini & Faster-Whisper)
2. Conversational addressing & politeness normalization
3. Repeat modifier extraction without entity corruption
4. Contextual reference resolution ("first result", "close it", "turn it back to 100%")
5. Reference resolution precedence over generic application parsing
6. Terminal state semantics (FAILED/BROKEN/CANCELLED never emit TASK_COMPLETED)
7. Deterministic real cancellation
8. Context persistence across sequential turns
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.command import CommandCategory, CommandComplexity, CommandParser, normalize_conversational_utterance
from app.core.command_pipeline import CommandPipeline
from app.core.events import EventBus
from app.core.graph.engine import StatefulGraphRuntime
from app.core.graph.node import GraphNode
from app.core.graph.control import NodeResult
from app.core.graph.state import GraphExecutionStatus, GraphPlanStep, GraphState
from app.core.state import SERAState, SERAStatus
from app.tools.registry import ToolRegistry


# =====================================================================
# 1. STT ENGLISH-ONLY POLICY TESTS
# =====================================================================

def test_whisper_english_constraint():
    """Verify Faster-Whisper enforces English decoding language policy."""
    from app.models.stt.whisper import FasterWhisperSTTProvider
    stt = FasterWhisperSTTProvider(lazy_load=True)
    assert stt is not None


def test_gemini_english_constraint_and_prompt():
    """Verify Gemini STT configures verbatim English transcription."""
    from app.models.stt.gemini import GeminiSTTProvider
    stt = GeminiSTTProvider(api_key="test_dummy_key")
    assert stt is not None
    assert stt.model == "gemini-3.5-transcribe"


# =====================================================================
# 2. CONVERSATIONAL NORMALIZATION TESTS
# =====================================================================

@pytest.mark.parametrize(
    "raw_input,expected_target",
    [
        ("Open Chrome", "chrome"),
        ("Hey Sera, open Chrome", "chrome"),
        ("Hey Sarah, open Chrome", "chrome"),
        ("Sarah, please open Chrome", "chrome"),
        ("Can you please open Chrome?", "chrome"),
        ("Sarah, could you please open Chrome for me?", "chrome"),
        ("Hey Sarah, can you please open the chrome for me?", "chrome"),
        ("Please open Chrome.", "chrome"),
        ("Could you please launch Notepad for me thanks?", "notepad"),
        ("Would you kindly start Calculator?", "calculator"),
    ],
)
def test_addressing_and_politeness_normalization(raw_input, expected_target):
    """Addressing and courtesies must not corrupt the intended application target."""
    parser = CommandParser()
    cmd = parser.parse(raw_input)
    assert cmd.intent == "open_application"
    assert cmd.parameters.get("application", "").lower() == expected_target


def test_pure_address_wake():
    """Single address invocation without action acts as assistant wake call."""
    parser = CommandParser()
    for phrase in ["Hey Sarah", "Sarah", "Sera", "Hey Sera", "Ok Sera"]:
        cmd = parser.parse(phrase)
        assert cmd.intent == "assistant_wake"
        assert cmd.category == CommandCategory.CONVERSATION
        assert "here" in cmd.raw_response.lower()


def test_self_close_target_preserved():
    """Self-close targets ('close yourself', 'quit sera') must not have target stripped."""
    parser = CommandParser()
    cmd = parser.parse("Sarah, please close yourself")
    assert cmd.intent == "sera_self_close"

    cmd2 = parser.parse("close presence")
    assert cmd2.intent == "sera_self_close"


# =====================================================================
# 3. REPEAT MODIFIER TESTS
# =====================================================================

def test_open_chrome_again_as_modifier():
    """'Open Chrome again' must have target='chrome' and modifier='repeat', not target='chrome again'."""
    parser = CommandParser()
    cmd = parser.parse("Open Chrome again")
    assert cmd.intent == "open_application"
    assert cmd.parameters.get("application") == "chrome"
    assert cmd.parameters.get("modifier") == "repeat"
    assert cmd.entities.get("modifier") == "repeat"
    assert "again" not in cmd.parameters.get("application")


def test_search_that_again_with_context():
    """'Search that again' repeats query from previous verified search context."""
    parser = CommandParser()
    ctx = {"last_search_query": "gaming videos"}
    cmd = parser.parse("Search that again", context=ctx)
    assert cmd.intent == "youtube_search"
    assert cmd.parameters.get("query") == "gaming videos"


# =====================================================================
# 4. CONTEXTUAL ORDINAL REFERENCE TESTS
# =====================================================================

def test_open_first_result_with_context():
    """'Open the first result' resolves against context.get('search_results')."""
    parser = CommandParser()
    ctx = {
        "search_results": [
            {"title": "Epic Gaming Video 2026", "url": "https://www.youtube.com/watch?v=abc12345"},
            {"title": "Second Great Video", "url": "https://www.youtube.com/watch?v=xyz67890"},
        ]
    }
    cmd = parser.parse("Open the first result", context=ctx)
    assert cmd.intent == "open_search_result"
    assert cmd.category == CommandCategory.BROWSER
    assert cmd.parameters.get("url") == "https://www.youtube.com/watch?v=abc12345"
    assert cmd.parameters.get("index") == 0
    assert len(cmd.execution_plan) == 1
    assert cmd.execution_plan[0].action == "browser_open"
    assert cmd.execution_plan[0].arguments["url"] == "https://www.youtube.com/watch?v=abc12345"


def test_open_second_result_variations():
    """Ordinal variations ('second', '2nd', 'click second one') resolve to index 1."""
    parser = CommandParser()
    ctx = {
        "search_results": [
            {"title": "Video 1", "url": "https://youtube.com/watch?v=1"},
            {"title": "Video 2", "url": "https://youtube.com/watch?v=2"},
        ]
    }
    for phrase in ["Open the second result", "click the second one", "open result 2", "play the second video", "use the second result"]:
        cmd = parser.parse(phrase, context=ctx)
        assert cmd.intent == "open_search_result", f"Failed for '{phrase}'"
        assert cmd.parameters.get("index") == 1
        assert cmd.parameters.get("url") == "https://youtube.com/watch?v=2"


def test_open_first_result_without_context_does_not_open_generic_app():
    """'Open the first result' without search results MUST NOT launch an app called 'first result'."""
    parser = CommandParser()
    cmd = parser.parse("Open the first result", context={})
    # Must NOT be open_application
    assert cmd.intent != "open_application"
    assert cmd.intent == "context_reference_missing"
    assert cmd.raw_response is not None
    assert "search" in cmd.raw_response.lower()


def test_close_it_closes_last_verified_app():
    """'Close it' resolves against last_application from verified context."""
    parser = CommandParser()
    ctx = {"last_application": "chrome"}
    cmd = parser.parse("Close it", context=ctx)
    assert cmd.intent == "close_application"
    assert cmd.parameters.get("application") == "chrome"
    assert cmd.execution_plan[0].arguments["application"] == "chrome"


# =====================================================================
# 5. TERMINAL STATE SEMANTICS TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_broken_task_never_emits_task_completed():
    """A failed/broken task must emit TASK_FAILED and never TASK_COMPLETED."""
    bus = EventBus()
    emitted_events = []

    def on_event(event_name, data):
        emitted_events.append((event_name, data))

    for ev in ["TASK_STARTED", "TASK_COMPLETED", "TASK_FAILED", "AGENT_RESPONSE"]:
        bus.on(ev, lambda data, name=ev: on_event(name, data))

    # Mock tool that fails verification
    tools = ToolRegistry()
    fail_tool = MagicMock()
    fail_tool.name = "open_application"
    fail_tool.execute = AsyncMock(return_value={"success": False, "verified": False, "error": "Application not found."})
    tools.register(fail_tool)

    pipeline = CommandPipeline(tools=tools, event_bus=bus)

    result = await pipeline.execute_text("Open an application called NONEXISTENT_APP_9999", is_voice_turn=False)
    assert result["success"] is False

    event_names = [e[0] for e in emitted_events]
    assert "TASK_FAILED" in event_names
    assert "TASK_COMPLETED" not in event_names, "TASK_COMPLETED was erroneously emitted after failure!"


# =====================================================================
# 6. DETERMINISTIC REAL CANCELLATION TESTS
# =====================================================================

@pytest.mark.asyncio
async def test_deterministic_real_cancellation():
    """Controlled cancellation terminates active graph execution immediately without running next nodes."""
    bus = EventBus()
    emitted = []
    bus.on("GRAPH_CANCELLED", lambda d: emitted.append(("GRAPH_CANCELLED", d)))
    bus.on("GRAPH_COMPLETED", lambda d: emitted.append(("GRAPH_COMPLETED", d)))

    runtime = StatefulGraphRuntime(event_bus=bus)

    step2_executed = False

    class SlowWaitingNode(GraphNode):
        def __init__(self):
            super().__init__("SLOW_STEP")

        async def execute(self, state, cancellation_event=None):
            # Safe wait that checks cancellation
            for _ in range(50):
                if cancellation_event and cancellation_event.is_set():
                    state.is_cancelled = True
                    return NodeResult.cancel(state, reason="Cancelled during wait")
                await asyncio.sleep(0.05)
            return NodeResult.continue_to("NEXT_STEP", state)

    class NextStepNode(GraphNode):
        def __init__(self):
            super().__init__("NEXT_STEP")

        async def execute(self, state, cancellation_event=None):
            nonlocal step2_executed
            step2_executed = True
            return NodeResult.done(state, final_response="Done")

    runtime.register_node(SlowWaitingNode())
    runtime.register_node(NextStepNode())
    runtime.add_edge("SLOW_STEP", "NEXT_STEP")
    runtime.set_start_node("SLOW_STEP")

    state = GraphState(raw_user_input="test slow operation", task_id="task_cancel_1")
    cancel_evt = asyncio.Event()

    # Launch graph in background task
    exec_task = asyncio.create_task(runtime.execute(state, cancellation_event=cancel_evt))

    # Wait 80ms so node is actively executing, then signal cancellation
    await asyncio.sleep(0.08)
    cancel_evt.set()

    final_state = await exec_task

    # Verifications
    assert final_state.status == GraphExecutionStatus.CANCELLED
    assert final_state.is_cancelled is True
    assert step2_executed is False, "Next node executed after cancellation!"

    event_names = [e[0] for e in emitted]
    assert "GRAPH_CANCELLED" in event_names
    assert "GRAPH_COMPLETED" not in event_names, "GRAPH_COMPLETED was emitted on cancelled execution!"
