"""
Phase 3A-G — Architectural Stabilization Regression Suite.

Validates the 7 core architectural invariants established during Phase 3A-G:
1. Canonical Entity Ownership (BrowserSessionManager and ContextStore single ID lifecycle)
2. Semantic Taxonomy Distinction (APPLICATION vs WINDOW vs BROWSER vs TAB)
3. Empirical Tab Switching in focus_tab (Real tab switch and title verification)
4. Window vs Application Closing Semantics (WM_CLOSE vs Process Termination)
5. Interpretation vs Execution (Natural language settings interpretation + deterministic execution)
6. Safe Fallback Boundary (SLM offline -> zero destructive guessing of clauses/pronouns)
7. Truthful Voice Turn Lifecycle Synchronization (SPEAKING bound to audio playback start)
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.context.entities import (
    BrowserTabEntity,
    ApplicationEntity,
    SearchResultEntity,
    SystemSettingEntity,
)
from app.core.context.store import ContextStore
from app.core.semantic.schema import (
    CanonicalIntent,
    ActionFamily,
    TargetType,
    SemanticTarget,
    SemanticReference,
    SemanticModifiers,
)
from app.core.semantic.authority import (
    SemanticAuthorityGate,
    SemanticAuthoritySource,
    SemanticAuthorityDecision,
)
from app.core.semantic.resolver import SemanticContextResolver
from app.core.command import CommandParser, CommandCategory
from app.core.command_pipeline import CommandPipeline
from app.core.state import SERAState, SERAStatus
from app.core.events import EventBus
from app.core.verification import EvidenceVerificationFabric, EvidenceType, EvidenceRecord
from app.tools.browser.session import BrowserSessionManager
from app.tools.windows.apps import CloseWindowTool, CloseApplicationTool


# =====================================================================
# 1. CANONICAL ENTITY OWNERSHIP (Invariant 1)
# =====================================================================

@pytest.mark.asyncio
async def test_canonical_browser_tab_entity_ownership():
    """BrowserSessionManager and ContextStore must share a single canonical entity ID.
    Closing a tab must remove that exact ID from both stores without leaks.
    """
    store = ContextStore()
    bsm = BrowserSessionManager(context_store=store)

    # 1. Open tab through BrowserSessionManager
    res = await bsm.open_url("https://github.com", title="GitHub - Where the world builds software")
    tab_id = res["tab_id"]

    # Invariant: ID in BSM matches ID registered in ContextStore
    assert tab_id in bsm._tabs
    assert store.get_browser_tab(tab_id) is not None
    assert store.get_active_browser_tab().entity_id == tab_id
    assert store.get_entity(tab_id) is not None
    assert store.get_browser_tab(tab_id).canonical_url == "https://github.com"

    # 2. Close tab through BrowserSessionManager
    close_res = await bsm.close_tab(tab_id)
    assert close_res["success"] is True

    # Invariant: Exact entity is removed from both BSM and ContextStore
    assert tab_id not in bsm._tabs
    assert store.get_browser_tab(tab_id) is None
    assert store.get_entity(tab_id) is None
    assert store.get_active_browser_tab() is None


def test_idempotent_tab_registration_preserves_canonical_identity():
    """Registering an existing URL returns the identical tab entity without creating duplicate IDs."""
    store = ContextStore()
    t1 = store.register_browser_tab(title="Docs", canonical_url="https://docs.python.org")
    orig_id = t1.entity_id

    t2 = store.register_browser_tab(title="Docs Updated", canonical_url="https://docs.python.org")
    assert t2.entity_id == orig_id
    assert t2.title == "Docs Updated"
    assert len(store._browser_tabs) == 1


# =====================================================================
# 2. SEMANTIC TAXONOMY DISTINCTION (Invariant 2)
# =====================================================================

def test_target_taxonomy_preserves_tab_vs_window_vs_application():
    """Gate maps semantic taxonomy without auto-collapsing TAB to APPLICATION."""
    gate = SemanticAuthorityGate(pilot_enabled=True)

    # A. Tab target with close intent -> mapped to close_browser_tab (BROWSER family)
    tab_intent = CanonicalIntent(
        intent="close_application",
        action_family="APPLICATION",
        target=SemanticTarget(type=TargetType.TAB.value, value="youtube"),
        confidence=0.95,
    )
    dec_tab = gate.decide(tab_intent, transcript="Close this YouTube tab", context={})
    assert dec_tab.accepted is True
    assert dec_tab.canonical_intent.intent == "close_browser_tab"
    assert dec_tab.canonical_intent.action_family == ActionFamily.BROWSER
    assert dec_tab.category == "BROWSER"

    # B. Window target with close intent -> mapped to close_window (WINDOW family)
    win_intent = CanonicalIntent(
        intent="close_application",
        action_family="APPLICATION",
        target=SemanticTarget(type=TargetType.WINDOW.value, value="terminal"),
        confidence=0.95,
    )
    dec_win = gate.decide(win_intent, transcript="Close that window", context={"last_window": "terminal"})
    assert dec_win.accepted is True
    assert dec_win.canonical_intent.intent == "close_window"
    assert dec_win.category == "WINDOW"

    # C. Pure Application target -> preserved as close_application (APPLICATION family)
    app_intent = CanonicalIntent(
        intent="close_application",
        action_family="APPLICATION",
        target=SemanticTarget(type=TargetType.APPLICATION.value, value="notepad"),
        confidence=0.95,
    )
    dec_app = gate.decide(app_intent, transcript="Close Notepad", context={})
    assert dec_app.accepted is True
    assert dec_app.canonical_intent.intent == "close_application"
    assert dec_app.category == "APPLICATION"


# =====================================================================
# 3. EMPIRICAL TAB SWITCHING & VERIFICATION (Invariant 3)
# =====================================================================

@pytest.mark.asyncio
async def test_focus_tab_empirical_verification():
    """focus_tab verifies that the active browser window title actually matches requested tab."""
    store = ContextStore()
    bsm = BrowserSessionManager(context_store=store)

    res_yt = await bsm.open_url("https://youtube.com", title="YouTube - Home")
    tab_yt_id = res_yt["tab_id"]
    res_gh = await bsm.open_url("https://github.com", title="GitHub - Dashboard")
    tab_gh_id = res_gh["tab_id"]

    bsm.get_browser_windows = MagicMock(return_value=[1001])
    bsm.is_browser_process_alive = MagicMock(return_value=True)

    # Mock win32gui to simulate window title inspection
    with patch("app.tools.browser.session.win32gui") as mock_win32gui:
        mock_win32gui.IsWindow.return_value = True
        mock_win32gui.GetForegroundWindow.return_value = 1001

        # Scenario A: Title matches YouTube
        mock_win32gui.GetWindowText.return_value = "YouTube - Home - Google Chrome"
        success_res = await bsm.focus_tab(tab_yt_id)
        assert success_res["success"] is True
        assert bsm.get_active_tab().entity_id == tab_yt_id

        # Scenario B: Title does NOT match (failed tab switch)
        mock_win32gui.GetWindowText.return_value = "Unrelated Page - Google Chrome"
        failed_res = await bsm.focus_tab(tab_gh_id)
        assert failed_res["success"] is False


def test_verification_fabric_records_tab_and_window_actions():
    """EvidenceVerificationFabric supports close_window, focus_browser_tab, and close_browser_tab."""
    fabric = EvidenceVerificationFabric()

    rec_close = fabric.verify_tool_execution("close_window", {"success": True, "verified": True})
    assert rec_close.verified is True
    assert rec_close.evidence_type == EvidenceType.WINDOW_HANDLE
    assert rec_close.source == "close_window"

    rec_focus = fabric.verify_tool_execution("focus_browser_tab", {"success": True, "verified": True})
    assert rec_focus.verified is True
    assert rec_focus.evidence_type == EvidenceType.WINDOW_HANDLE
    assert rec_focus.source == "focus_browser_tab"

    rec_tab_close = fabric.verify_tool_execution("close_browser_tab", {"success": True, "verified": True})
    assert rec_tab_close.verified is True
    assert rec_tab_close.evidence_type == EvidenceType.WINDOW_HANDLE
    assert rec_tab_close.source == "close_browser_tab"


# =====================================================================
# 4. WINDOW VS APPLICATION CLOSING SEMANTICS (Invariant 4)
# =====================================================================

@pytest.mark.asyncio
async def test_close_window_sends_wm_close_without_terminating_process():
    """CloseWindowTool sends WM_CLOSE to HWND and verifies window destruction without killing process."""
    tool = CloseWindowTool()

    with patch("app.tools.windows.apps.win32gui") as mock_gui, \
         patch("app.tools.windows.apps.psutil") as mock_psutil:

        mock_gui.FindWindow.return_value = 54321
        mock_gui.GetForegroundWindow.return_value = 54321
        mock_gui.IsWindow.side_effect = [True, False]  # destroyed on second check
        mock_gui.IsWindowVisible.return_value = False
        mock_gui.GetWindowText.return_value = "Untitled - Notepad"

        mock_proc = MagicMock()
        mock_proc.is_running.return_value = True
        mock_proc.status.return_value = "running"
        mock_psutil.Process.return_value = mock_proc

        result = await tool.execute(hwnd=54321, window_title="Untitled - Notepad")
        assert result["success"] is True
        assert "Closed window" in result["message"]
        assert result["process_alive"] is True

        # Verify PostMessage was called with WM_CLOSE (0x0010)
        mock_gui.PostMessage.assert_called_once_with(54321, 0x0010, 0, 0)
        # Verify process was NOT killed
        mock_proc.terminate.assert_not_called()
        mock_proc.kill.assert_not_called()


@pytest.mark.asyncio
async def test_close_application_terminates_process():
    """CloseApplicationTool explicitly terminates the application process tree."""
    tool = CloseApplicationTool()

    with patch("app.tools.windows.apps.psutil.process_iter") as mock_iter:
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 8888, "name": "notepad.exe"}
        mock_proc.is_running.return_value = True
        mock_iter.return_value = [mock_proc]

        result = await tool.execute(application="notepad")
        assert result["success"] is True
        assert result["processes_closed"] == 1
        mock_proc.terminate.assert_called_once()


# =====================================================================
# 5. INTERPRETATION VS EXECUTION (Invariant 5)
# =====================================================================

def test_natural_settings_phrasing_resolved_to_deterministic_execution():
    """Natural phrasing ('revert brightness', 'make screen dimmer') resolves to deterministic tool calls."""
    store = ContextStore()
    store.record_setting_change("brightness", 75)
    store.record_setting_change("brightness", 30)  # previous was 75

    resolver = SemanticContextResolver()

    # A. "revert brightness" -> restores previous 75%
    intent_restore = CanonicalIntent(
        intent="restore_setting",
        action_family="SYSTEM",
        target=SemanticTarget(type="setting", value="brightness"),
        modifiers=SemanticModifiers(direction="restore"),
        confidence=0.96,
    )
    decision_restore = SemanticAuthorityDecision(
        source=SemanticAuthoritySource.QWEN,
        canonical_intent=intent_restore,
        accepted=True,
        category="SETTING",
    )
    cmd_restore = resolver.resolve(decision_restore, "put brightness back where it was", {}, "t1", context_store=store)
    assert cmd_restore.intent == "restore_brightness"
    assert cmd_restore.required_tools == ["set_brightness"]
    assert cmd_restore.execution_plan[0].arguments["brightness"] == 75

    # B. "make screen dimmer" -> relative decrement from current 50%
    intent_dim = CanonicalIntent(
        intent="adjust_brightness",
        action_family="SYSTEM",
        target=SemanticTarget(type="setting", value="brightness"),
        modifiers=SemanticModifiers(relative=True, direction="down"),
        confidence=0.95,
    )
    decision_dim = SemanticAuthorityDecision(
        source=SemanticAuthoritySource.QWEN,
        canonical_intent=intent_dim,
        accepted=True,
        category="SETTING",
    )
    cmd_dim = resolver.resolve(decision_dim, "make the screen dimmer", {"last_brightness": 50}, "t2", context_store=store)
    assert cmd_dim.intent == "set_brightness"
    assert cmd_dim.required_tools == ["set_brightness"]
    # 50 - 20 = 30%
    assert cmd_dim.execution_plan[0].arguments["brightness"] == 30


# =====================================================================
# 6. SAFE FALLBACK BOUNDARY (Invariant 6)
# =====================================================================

def test_safe_fallback_boundary_zero_destructive_guessing():
    """When SLM is offline or times out, fallback NEVER guesses destructive OS actions."""
    parser = CommandParser()
    gate = SemanticAuthorityGate(pilot_enabled=True)

    # A. "Open that" with empty context -> MUST CLARIFY, NEVER open arbitrary app or chrome
    dec_open_that = gate.decide(None, transcript="Open that", context={}, model_error="Connection refused")
    assert dec_open_that.source == SemanticAuthoritySource.CLARIFICATION
    assert dec_open_that.fallback_reason == "MISSING_CONTEXT_REFERENT"

    cmd_open_that = parser.parse("Open that", context={})
    assert cmd_open_that.intent == "clarification_needed"
    assert len(cmd_open_that.required_tools) == 0

    # B. "Stop what you are currently doing" -> MUST CANCEL TASK, NEVER kill application
    dec_cancel = gate.decide(None, transcript="Stop what you are currently doing", context={}, model_error="Timed out")
    assert dec_cancel.source == SemanticAuthoritySource.DETERMINISTIC
    assert dec_cancel.accepted is True
    assert dec_cancel.fallback_reason == "SAFE_DETERMINISTIC_CANCELLATION"

    cmd_cancel = parser.parse("Stop what you are currently doing", context={})
    assert cmd_cancel.intent == "cancel_current_task"
    assert len(cmd_cancel.required_tools) == 0

    # C. "Close that window" without context -> MUST CLARIFY or CLOSE WINDOW, NEVER kill process
    dec_close_win = gate.decide(None, transcript="Close that window", context={}, model_error="Connection refused")
    assert dec_close_win.source == SemanticAuthoritySource.CLARIFICATION

    # D. Bare verb "Launch" -> MUST CLARIFY, NEVER guess arbitrary app
    dec_launch = gate.decide(None, transcript="Launch", context={}, model_error="Connection refused")
    assert dec_launch.source == SemanticAuthoritySource.CLARIFICATION
    assert dec_launch.fallback_reason == "MISSING_APPLICATION_TARGET"


# =====================================================================
# 7. TRUTHFUL VOICE TURN LIFECYCLE (Invariant 7)
# =====================================================================

@pytest.mark.asyncio
async def test_truthful_voice_lifecycle_synchronized_with_audio_playback():
    """SPEAKING status and events must be strictly emitted on physical audio playback start."""
    from app.core.runtime import SERARuntime

    event_bus = EventBus()
    events_emitted = []

    for ev_name in ("RESPONSE_READY", "TTS_SYNTHESIS_STARTED", "AUDIO_PLAYBACK_STARTED", "AUDIO_PLAYBACK_FINISHED", "TASK_COMPLETED"):
        def make_cb(name):
            return lambda payload=None, **kwargs: events_emitted.append((name, payload or kwargs))
        event_bus.subscribe(ev_name, make_cb(ev_name))

    audio_mock = MagicMock()
    runtime = SERARuntime(event_bus=event_bus, audio_manager=audio_mock)

    # Mock STT to return transcription
    runtime.stt = MagicMock()
    runtime.stt.transcribe = AsyncMock(return_value="Bring Chrome up.")
    runtime.quality_gate = MagicMock()
    runtime.quality_gate.evaluate = MagicMock(return_value=MagicMock(accepted=True, confidence=0.98, reason="ok"))

    # Mock command_pipeline to return successful result
    runtime.command_pipeline.execute_text = AsyncMock(return_value={
        "success": True,
        "response": "Hello, I am ready.",
        "task_id": "test_voice_1",
    })

    # Hook speak to invoke on_playback_start
    def mock_speak(text, on_playback_start=None):
        assert runtime.state.status != SERAStatus.SPEAKING
        if on_playback_start:
            on_playback_start()
        assert runtime.state.status == SERAStatus.SPEAKING

    audio_mock.speak.side_effect = mock_speak

    # Simulate voice turn execution with 1 second of audio
    import numpy as np
    dummy_audio = np.zeros(16000, dtype=np.float32)
    await runtime._process_recorded_audio(dummy_audio, activation_time=time.time())

    event_types = [e[0] for e in events_emitted]

    # Verify lifecycle sequence:
    assert "RESPONSE_READY" in event_types
    assert "TTS_SYNTHESIS_STARTED" in event_types
    assert "AUDIO_PLAYBACK_STARTED" in event_types
    assert "AUDIO_PLAYBACK_FINISHED" in event_types
    assert "TASK_COMPLETED" in event_types

    assert runtime.state.status == SERAStatus.IDLE
