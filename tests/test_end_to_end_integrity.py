"""
Phase 3A-F — End-to-End Semantic, State, Routing, Execution & Response Integrity Tests.

Validates architectural invariants across the full user turn lifecycle:
- Invariant 1: Semantic Equivalence Classes (Wording variations converge to same canonical meaning)
- Invariant 2: Search Session Isolation (New search session cannot reuse entities from old session)
- Invariant 3: Entity Identity Continuity (Active referent preserved across 'open that' / 'open that again')
- Invariant 4: No Guessing / Explicit Clarification (Never defaults to result 1 or chrome)
- Invariant 5: Tab Closure Distinct from OS Process Termination
- Invariant 6: Application Requests Never Invoke Vision ("get Chrome back on my screen")
- Invariant 7: Idempotent Repeated Tab Opening (re-uses existing tab by default)
- Invariant 8: Monotonic Terminal State (Terminal events cannot be duplicated or contradicted)
- Invariant 9: No Raw Technical Exceptions in Spoken Responses
- Invariant 10: Repetition Replays Verified Semantic Actions
- Invariant 11: Deterministic System Setting Reversal / History
- Multi-Turn End-to-End Regression Chains (Section 35)
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.command import CommandCategory, CommandComplexity, CommandObject, CommandParser
from app.core.command_pipeline import CommandPipeline
from app.core.context.entities import (
    ApplicationEntity,
    BrowserTabEntity,
    EntityType,
    ReplayableSemanticAction,
    SearchResultEntity,
    SearchResultType,
    SearchSession,
    SystemSettingEntity,
)
from app.core.context.store import ContextStore
from app.core.events import EventBus
from app.core.graph import GraphExecutionStatus
from app.core.semantic import (
    CanonicalIntent,
    SemanticAuthorityDecision,
    SemanticAuthoritySource,
    SemanticContextResolver,
    SemanticReference,
    SemanticTarget,
)
from app.core.state import SERAState, SERAStatus
from app.vision.analyzer import ScreenPerceptionEngine


# =====================================================================
# INVARIANT 1: SEMANTIC EQUIVALENCE CLASSES (Section 3 & 34)
# =====================================================================

def test_invariant_1_wording_variations_converge_to_same_canonical_meaning():
    """Varying natural language expressions for opening/bringing Chrome must converge to open_application(chrome)."""
    parser = CommandParser()
    phrases = [
        "open Chrome",
        "bring Chrome up",
        "get Chrome running",
        "fire up the browser",
        "put Chrome back up",
        "can you bring my browser forward",
        "please get my browser on screen",
        "get Chrome back on my screen",
        "bring Chrome back on my screen",
    ]

    for phrase in phrases:
        cmd = parser.parse(phrase)
        assert cmd.intent in ("open_application", "switch_application"), f"Failed for phrase: '{phrase}' (got {cmd.intent})"
        target_app = (cmd.parameters.get("application") or "").lower()
        assert target_app in ("chrome", "browser", "the browser", "my browser"), f"Target mismatch for: '{phrase}' (got {target_app})"


# =====================================================================
# INVARIANT 2: SEARCH SESSION ISOLATION (Section 7 & 34)
# =====================================================================

def test_invariant_2_search_session_isolation():
    """A new search session creates isolated entity IDs and old results cannot leak into new session."""
    store = ContextStore()

    # Search A: Python tutorials
    session_a = store.create_search_session(query="python tutorials", source="youtube")
    r_a1 = SearchResultEntity(session_id=session_a.session_id, ordinal=1, title="Python 1", canonical_url="https://youtube.com/watch?v=py1")
    r_a2 = SearchResultEntity(session_id=session_a.session_id, ordinal=2, title="Python 2", canonical_url="https://youtube.com/watch?v=py2")
    session_a.add_result(r_a1)
    session_a.add_result(r_a2)

    # Resolve Result 2 in Search A
    res_a2 = store.resolve_search_result(ordinal=2)
    assert res_a2 is not None
    assert res_a2.canonical_url == "https://youtube.com/watch?v=py2"
    assert res_a2.session_id == session_a.session_id

    # Search B: Rust programming
    session_b = store.create_search_session(query="rust programming", source="youtube")
    r_b1 = SearchResultEntity(session_id=session_b.session_id, ordinal=1, title="Rust 1", canonical_url="https://youtube.com/watch?v=rust1")
    r_b2 = SearchResultEntity(session_id=session_b.session_id, ordinal=2, title="Rust 2", canonical_url="https://youtube.com/watch?v=rust2")
    session_b.add_result(r_b1)
    session_b.add_result(r_b2)

    # Old result 2 reference in new active session MUST resolve to Search B!
    res_b2 = store.resolve_search_result(ordinal=2)
    assert res_b2 is not None
    assert res_b2.canonical_url == "https://youtube.com/watch?v=rust2"
    assert res_b2.session_id == session_b.session_id
    assert res_b2.entity_id != res_a2.entity_id


# =====================================================================
# INVARIANT 3: ENTITY IDENTITY CONTINUITY (Section 7, 8 & 34)
# =====================================================================

def test_invariant_3_entity_identity_continuity():
    """Active referent entity remains identical across 'open that' and 'open that again'."""
    store = ContextStore()
    session = store.create_search_session(query="interstellar soundtrack", source="youtube")
    r1 = SearchResultEntity(session_id=session.session_id, ordinal=1, title="Track 1", canonical_url="https://youtube.com/watch?v=track1")
    r2 = SearchResultEntity(session_id=session.session_id, ordinal=2, title="Track 2", canonical_url="https://youtube.com/watch?v=track2")
    session.add_result(r1)
    session.add_result(r2)

    # 1. User says "open result 2"
    resolved_1 = store.resolve_search_result(ordinal=2)
    assert resolved_1 is not None
    assert resolved_1.entity_id == r2.entity_id

    # 2. User says "open that" (ordinal=None) -> Must resolve to Track 2, NOT Track 1!
    resolved_that = store.resolve_search_result(ordinal=None)
    assert resolved_that is not None
    assert resolved_that.entity_id == r2.entity_id
    assert resolved_that.canonical_url == "https://youtube.com/watch?v=track2"

    # 3. User says "open that again" -> Must resolve to Track 2 again!
    resolved_again = store.resolve_search_result(ordinal=None)
    assert resolved_again is not None
    assert resolved_again.entity_id == r2.entity_id


# =====================================================================
# INVARIANT 4: NO DEFAULTING TO RESULT #1 / EXPLICIT CLARIFICATION (Section 8 & 13)
# =====================================================================

def test_invariant_4_never_defaults_to_result_1():
    """Unknown references or empty search sessions MUST require clarification, never guess result 1."""
    store = ContextStore()
    # No search session created yet
    res = store.resolve_search_result(ordinal=None)
    assert res is None, "Must return None when referent is unknown (requiring clarification)"

    # Resolver test: open_reference with no active search
    decision = SemanticAuthorityDecision(
        source=SemanticAuthoritySource.QWEN,
        accepted=True,
        canonical_intent=CanonicalIntent(
            intent="open_reference",
            action_family="BROWSER",
            reference=SemanticReference(type="search_result", ordinal=None),
        ),
    )
    cmd = SemanticContextResolver.resolve(decision, "Open that", context={"context_store": store})
    assert cmd.intent == "clarification"
    assert len(cmd.required_tools) == 0
    assert "Which search result" in cmd.raw_response or "There are no active search results" in cmd.raw_response


def test_invariant_4_never_defaults_close_to_chrome():
    """'close it' without active window or application in context demands clarification, never closes Chrome."""
    parser = CommandParser()
    cmd = parser.parse("close it", context={})
    assert cmd.intent == "clarification_needed"
    assert cmd.complexity == CommandComplexity.AMBIGUOUS
    assert len(cmd.required_tools) == 0


# =====================================================================
# INVARIANT 5: TAB CLOSURE DISTINCT FROM PROCESS TERMINATION (Section 12)
# =====================================================================

def test_invariant_5_tab_closure_distinct_from_process_termination():
    """'Close this YouTube tab' produces close_browser_tab, NEVER close_application(chrome.exe)."""
    parser = CommandParser()
    cmd = parser.parse("close this YouTube tab")

    assert cmd.intent == "close_browser_tab"
    assert cmd.category == CommandCategory.BROWSER
    assert "close_browser_tab" in cmd.required_tools
    assert "close_application" not in cmd.required_tools

    # Test Qwen resolution
    decision = SemanticAuthorityDecision(
        source=SemanticAuthoritySource.QWEN,
        accepted=True,
        canonical_intent=CanonicalIntent(
            intent="close_browser_tab",
            action_family="BROWSER",
            target=SemanticTarget(type="tab", value="youtube"),
        ),
    )
    res_cmd = SemanticContextResolver.resolve(decision, "close this youtube tab")
    assert res_cmd.intent == "close_browser_tab"
    assert res_cmd.required_tools == ["close_browser_tab"]
    assert res_cmd.execution_plan[0].action == "close_browser_tab"


# =====================================================================
# INVARIANT 6: APPLICATION REQUESTS NEVER INVOKE VISION (Section 15 & 16)
# =====================================================================

def test_invariant_6_get_chrome_back_on_my_screen_never_invokes_vision():
    """'Get Chrome back on my screen' is an application request and is rejected by is_vision_query."""
    engine = ScreenPerceptionEngine.__new__(ScreenPerceptionEngine)

    app_phrases = [
        "get Chrome back on my screen",
        "bring Chrome back on my screen",
        "put Chrome on screen",
        "open Chrome on my screen",
        "switch to Chrome",
        "focus Chrome",
    ]
    for p in app_phrases:
        assert not engine.is_vision_query(p), f"Phrase '{p}' incorrectly matched vision!"

    vision_phrases = [
        "what am i looking at",
        "what is on my screen",
        "what's that error on my screen",
        "describe what is on my screen",
        "read the text on my screen",
    ]
    for vp in vision_phrases:
        assert engine.is_vision_query(vp), f"Vision phrase '{vp}' failed to match!"


# =====================================================================
# INVARIANT 7: IDEMPOTENT TAB OPENING (Section 11)
# =====================================================================

def test_invariant_7_repeated_tab_opening_is_idempotent():
    """Opening an already registered tab focuses/reuses it without creating duplicate tabs."""
    store = ContextStore()
    tab1 = store.register_browser_tab(title="Video A", canonical_url="https://youtube.com/watch?v=vidA")
    assert len(store._browser_tabs) == 1

    # Open again
    tab2 = store.register_browser_tab(title="Video A", canonical_url="https://youtube.com/watch?v=vidA")
    assert tab1.entity_id == tab2.entity_id
    assert len(store._browser_tabs) == 1, "Duplicate tab registered!"


# =====================================================================
# INVARIANT 8: MONOTONIC TERMINAL STATE (Section 27)
# =====================================================================

def test_invariant_8_monotonic_terminal_state():
    """Once a task reaches FAILED or COMPLETED, contradictory terminal events are rejected."""
    bus = EventBus()
    emitted = []
    bus.subscribe("TASK_COMPLETED", lambda p: emitted.append(("TASK_COMPLETED", p)))
    bus.subscribe("TASK_FAILED", lambda p: emitted.append(("TASK_FAILED", p)))

    task_id = "test_task_monotonic_1"

    # Emit FAILED first
    bus.emit("TASK_FAILED", {"task_id": task_id, "error": "Execution error"})
    assert len(emitted) == 1
    assert emitted[0][0] == "TASK_FAILED"

    # Attempt to emit COMPLETED for same task -> MUST BE DROPPED!
    bus.emit("TASK_COMPLETED", {"task_id": task_id, "result": "Success!"})
    assert len(emitted) == 1, "Monotonicity violated: TASK_COMPLETED emitted after TASK_FAILED!"


# =====================================================================
# INVARIANT 9: NO RAW TECHNICAL EXCEPTIONS IN SPOKEN RESPONSES (Section 28)
# =====================================================================

def test_invariant_9_no_raw_exceptions_in_spoken_responses():
    """Raw Python exceptions and tracebacks are sanitized into clean conversational responses."""
    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    raw_exception = "LLM generation failed: 'NoneType' object has no attribute 'strip'"
    sanitized = pipeline._finalize_result(
        task_id="t1",
        success=False,
        response_text=raw_exception,
        t_start=0.0,
        error=raw_exception,
    )

    spoken_resp = sanitized["response"]
    assert "'NoneType'" not in spoken_resp
    assert "attribute" not in spoken_resp
    assert "failed:" not in spoken_resp
    assert "issue" in spoken_resp or "problem" in spoken_resp or "try again" in spoken_resp


# =====================================================================
# INVARIANT 10: REPETITION REPLAYS VERIFIED ACTIONS (Section 9)
# =====================================================================

@pytest.mark.asyncio
async def test_invariant_10_repetition_replays_verified_action():
    """Repeating a task replays the stored ReplayableSemanticAction without lexical reconstruction."""
    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    # Pre-seed a verified replayable action
    action = ReplayableSemanticAction(
        action_id="act_test_replay",
        semantic_intent="set_brightness",
        canonical_arguments={"brightness": 45},
        execution_plan_steps=[
            {
                "step_id": 1,
                "goal": "Set brightness to 45%",
                "action": "set_brightness",
                "arguments": {"brightness": 45},
                "timeout_seconds": 5.0,
                "verification_type": "value_check",
            }
        ],
        required_tools=["set_brightness"],
        verified_outcome={"status": "SUCCESS"},
    )
    pipeline.context_store.record_action(action)

    # Mock graph execution
    executed_plan = None
    async def mock_execute(graph_state, cancellation_event=None):
        nonlocal executed_plan
        executed_plan = graph_state.steps
        graph_state.status = GraphExecutionStatus.SUCCESS
        graph_state.steps[0].completed = True
        return graph_state

    pipeline.graph_runtime.execute = AsyncMock(side_effect=mock_execute)

    result = await pipeline.execute_text("Do that again", source="TEXT")

    assert result["success"] is True
    assert executed_plan is not None
    assert len(executed_plan) == 1
    assert executed_plan[0].action == "set_brightness"
    assert executed_plan[0].arguments == {"brightness": 45}


# =====================================================================
# INVARIANT 11: DETERMINISTIC SETTING REVERSAL (Section 18 & 35)
# =====================================================================

@pytest.mark.asyncio
async def test_invariant_11_deterministic_setting_reversal():
    """State history correctly updates and restores previous brightness level."""
    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    executed_args = []
    async def mock_execute(graph_state, cancellation_event=None):
        for s in graph_state.steps:
            executed_args.append(dict(s.arguments))
            s.completed = True
        graph_state.status = GraphExecutionStatus.SUCCESS
        return graph_state

    pipeline.graph_runtime.execute = AsyncMock(side_effect=mock_execute)

    # Step 1: Set brightness 30
    await pipeline.execute_text("Set brightness to 30%", source="TEXT")
    assert pipeline.context_store.get_setting("brightness").current_value == 30

    # Step 2: Set brightness 80
    await pipeline.execute_text("Set brightness to 80%", source="TEXT")
    assert pipeline.context_store.get_setting("brightness").current_value == 80
    assert pipeline.context_store.get_previous_setting_value("brightness") == 30

    # Step 3: Put brightness back where it was
    res3 = await pipeline.execute_text("Put brightness back where it was", source="TEXT")
    assert res3["success"] is True
    assert executed_args[-1]["brightness"] == 30


# =====================================================================
# END-TO-END MULTI-TURN REGRESSION SCENARIO (Section 35)
# =====================================================================

@pytest.mark.asyncio
async def test_multi_turn_search_entity_and_tab_lifecycle():
    """Complete Section 35 Scenario:
    SEARCH A -> OPEN RESULT 2 -> OPEN THAT -> OPEN THAT AGAIN -> SEARCH B -> OPEN RESULT 2 -> OPEN THAT -> CLOSE CURRENT TAB -> FOCUS CHROME
    Verifies entity continuity and proper isolation at every transition.
    """
    pipeline = CommandPipeline(tools={}, state=SERAState(), event_bus=EventBus())

    executed_actions = []
    async def mock_execute(graph_state, cancellation_event=None):
        for s in graph_state.steps:
            executed_actions.append((s.action, dict(s.arguments)))
            s.completed = True
        graph_state.status = GraphExecutionStatus.SUCCESS
        return graph_state

    pipeline.graph_runtime.execute = AsyncMock(side_effect=mock_execute)

    # 1. SEARCH A
    session_a = pipeline.context_store.create_search_session("python async", "youtube")
    r_a1 = SearchResultEntity(session_id=session_a.session_id, ordinal=1, title="A1", canonical_url="https://youtube.com/a1")
    r_a2 = SearchResultEntity(session_id=session_a.session_id, ordinal=2, title="A2", canonical_url="https://youtube.com/a2")
    session_a.add_result(r_a1)
    session_a.add_result(r_a2)

    # 2. OPEN RESULT 2 (Search A)
    await pipeline.execute_text("Open result 2", source="TEXT")
    assert executed_actions[-1][0] == "browser_open"
    assert executed_actions[-1][1]["url"] == "https://youtube.com/a2"

    # Register tab for URL
    pipeline.context_store.register_browser_tab(title="A2 Tab", canonical_url="https://youtube.com/a2")

    # 3. OPEN THAT -> resolves to A2
    await pipeline.execute_text("Open that", source="TEXT")
    assert executed_actions[-1][1]["url"] == "https://youtube.com/a2"

    # 4. OPEN THAT AGAIN -> resolves to A2
    await pipeline.execute_text("Open that again", source="TEXT")
    assert executed_actions[-1][1]["url"] == "https://youtube.com/a2"

    # 5. SEARCH B
    session_b = pipeline.context_store.create_search_session("rust async", "youtube")
    r_b1 = SearchResultEntity(session_id=session_b.session_id, ordinal=1, title="B1", canonical_url="https://youtube.com/b1")
    r_b2 = SearchResultEntity(session_id=session_b.session_id, ordinal=2, title="B2", canonical_url="https://youtube.com/b2")
    session_b.add_result(r_b1)
    session_b.add_result(r_b2)

    # 6. OPEN RESULT 2 (Search B) -> MUST BE B2, not A2!
    await pipeline.execute_text("Open result 2", source="TEXT")
    assert executed_actions[-1][1]["url"] == "https://youtube.com/b2"

    # 7. OPEN THAT -> resolves to B2
    await pipeline.execute_text("Open that", source="TEXT")
    assert executed_actions[-1][1]["url"] == "https://youtube.com/b2"

    # 8. CLOSE CURRENT TAB -> closes tab, chrome remains open
    await pipeline.execute_text("Close this tab", source="TEXT")
    assert executed_actions[-1][0] == "close_browser_tab"

    # 9. FOCUS CHROME -> focuses application, does NOT invoke vision!
    await pipeline.execute_text("Get Chrome back on my screen", source="TEXT")
    assert executed_actions[-1][0] in ("open_application", "focus_desktop_window")
