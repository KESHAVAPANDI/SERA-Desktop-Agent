import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.hotkey import GlobalHotkeyManager
from app.core.intent import LocalIntentRouter
from app.core.router import ModelRouter
from app.core.runtime import SERARuntime
from app.core.state import SERAState, SERAStatus
from app.models.llm.base import LLMProvider, LLMResponse
from app.speech.audio_cues import AudioCueManager
from app.speech.transcript_gate import TranscriptQualityGate
from app.tools.windows.apps import CloseApplicationTool, OpenApplicationTool
from app.utils.security import SecurityManager


class DummyProvider(LLMProvider):
    def __init__(self, should_fail_429: bool = False, response_text: str = "Hello from mock"):
        self.should_fail_429 = should_fail_429
        self.response_text = response_text
        self.call_count = 0

    def capabilities(self):
        return {"text": True, "tool_calling": True, "streaming": True}

    async def generate(self, messages, tools=None, images=None, **kwargs):
        self.call_count += 1
        if self.should_fail_429:
            raise RuntimeError("429 rate_limit_exceeded: TPM limit reached.")
        return LLMResponse(text=self.response_text, tool_calls=[], finish_reason="stop", provider="dummy", model="mock")

    async def stream(self, messages, tools=None, images=None, **kwargs):
        self.call_count += 1
        if self.should_fail_429:
            raise RuntimeError("429 rate_limit_exceeded: TPM limit reached.")
        yield self.response_text


class TestPhase41VoiceReliability(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.gate = TranscriptQualityGate()
        self.cue_manager = AudioCueManager(enabled=False)

    # -------------------------------------------------------------
    # 1. Hotkey Debounce & Rapid Press Tests
    # -------------------------------------------------------------
    def test_01_single_hotkey_triggers_one_event(self):
        count = 0
        def cb():
            nonlocal count
            count += 1

        mgr = GlobalHotkeyManager(on_trigger=cb, debounce_ms=300)
        res = mgr.trigger_manually()
        self.assertTrue(res)
        self.assertEqual(count, 1)

    def test_02_double_hotkey_within_debounce_window_is_debounced(self):
        count = 0
        def cb():
            nonlocal count
            count += 1

        mgr = GlobalHotkeyManager(on_trigger=cb, debounce_ms=300)
        res1 = mgr.trigger_manually()
        res2 = mgr.trigger_manually()  # Immediate second call
        self.assertTrue(res1)
        self.assertFalse(res2)
        self.assertEqual(count, 1)

    def test_03_five_rapid_hotkeys_produce_single_trigger(self):
        count = 0
        def cb():
            nonlocal count
            count += 1

        mgr = GlobalHotkeyManager(on_trigger=cb, debounce_ms=300)
        results = [mgr.trigger_manually() for _ in range(5)]
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 4)
        self.assertEqual(count, 1)

    # -------------------------------------------------------------
    # 2. Transcript Quality Gate Tests
    # -------------------------------------------------------------
    def test_04_reject_filler_um(self):
        dec = self.gate.evaluate("um")
        self.assertFalse(dec.accepted)
        self.assertTrue(dec.is_filler)

    def test_05_reject_noise_from(self):
        dec = self.gate.evaluate("from")
        self.assertFalse(dec.accepted)
        self.assertTrue(dec.is_filler)

    def test_06_reject_empty_and_whitespace(self):
        dec = self.gate.evaluate("   ")
        self.assertFalse(dec.accepted)

    def test_07_reject_high_no_speech_probability(self):
        dec = self.gate.evaluate("hello there", no_speech_prob=0.88)
        self.assertFalse(dec.accepted)

    def test_08_accept_valid_short_command_mute(self):
        dec = self.gate.evaluate("mute")
        self.assertTrue(dec.accepted)

    def test_09_accept_valid_command_open_chrome(self):
        dec = self.gate.evaluate("open chrome")
        self.assertTrue(dec.accepted)

    def test_10_accept_valid_question(self):
        dec = self.gate.evaluate("what time is it?")
        self.assertTrue(dec.accepted)

    # -------------------------------------------------------------
    # 3. State-Aware Hotkey & Cancellation Tests
    # -------------------------------------------------------------
    async def test_11_speaking_interruption(self):
        audio_mock = MagicMock()
        audio_mock.is_speaking = True
        state = SERAState()
        state.transition_to(SERAStatus.SPEAKING)

        runtime = SERARuntime.__new__(SERARuntime)
        runtime.state = state
        runtime.audio = audio_mock
        runtime.audio_cues = MagicMock()
        runtime.hotkey_event_count = 0
        runtime.turn_count = 0
        runtime.quality_gate = self.gate
        runtime._active_listen_task = None
        runtime._active_agent_task = None
        runtime._active_task = None
        runtime._loop = None
        runtime._last_printed_state = None
        runtime._process_voice_turn = AsyncMock()

        runtime.handle_hotkey_trigger()

        audio_mock.stop_speaking.assert_called_once()
        self.assertEqual(state.status, SERAStatus.LISTENING)

    async def test_12_thinking_interruption(self):
        state = SERAState()
        state.transition_to(SERAStatus.THINKING)

        active_task = MagicMock()
        active_task.done.return_value = False

        runtime = SERARuntime.__new__(SERARuntime)
        runtime.state = state
        runtime.audio = MagicMock()
        runtime.audio_cues = MagicMock()
        runtime.hotkey_event_count = 0
        runtime.turn_count = 0
        runtime.quality_gate = self.gate
        runtime._active_listen_task = None
        runtime._active_agent_task = active_task
        runtime._active_task = active_task
        runtime._loop = None
        runtime._last_printed_state = None
        runtime._process_voice_turn = AsyncMock()

        runtime.handle_hotkey_trigger()

        active_task.cancel.assert_called_once()
        self.assertEqual(state.status, SERAStatus.LISTENING)

    # -------------------------------------------------------------
    # 4. Quota Protection & 429 Fallback Handling
    # -------------------------------------------------------------
    async def test_13_groq_429_clean_fallback(self):
        primary_failing = DummyProvider(should_fail_429=True)
        fallback_success = DummyProvider(should_fail_429=False, response_text="Fallback Answer")

        router = ModelRouter(
            providers={
                "reasoning": primary_failing,
                "fallback": fallback_success,
            }
        )

        resp, role = await router.generate_with_fallback(
            messages=[{"role": "user", "content": "test query"}],
            preferred_role="reasoning",
        )

        self.assertEqual(resp.text, "Fallback Answer")
        self.assertEqual(role, "fallback")
        self.assertEqual(primary_failing.call_count, 1)
        self.assertEqual(fallback_success.call_count, 1)

    # -------------------------------------------------------------
    # 5. Local Intent Bypass
    # -------------------------------------------------------------
    def test_14_local_intent_bypasses_cloud_llm(self):
        router = LocalIntentRouter()
        match = router.detect("set brightness to 50%")
        self.assertIsNotNone(match)
        self.assertEqual(match["tool"], "set_brightness")
        self.assertEqual(match["arguments"], {"brightness": 50})

    # -------------------------------------------------------------
    # 6. Website vs Application Disambiguation
    # -------------------------------------------------------------
    async def test_15_close_youtube_website_disambiguation(self):
        tool = CloseApplicationTool()
        res = await tool.execute("youtube")
        self.assertFalse(res["success"])
        self.assertTrue(res.get("is_website", False))
        self.assertIn("website/browser tab", res["error"])

    async def test_16_open_youtube_opens_browser_url(self):
        tool = OpenApplicationTool()
        with patch("asyncio.create_subprocess_shell") as mock_sub:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock(return_value=0)
            mock_sub.return_value = mock_proc

            res = await tool.execute("youtube")
            self.assertTrue(res["success"])
            self.assertTrue(res.get("is_website", False))

    # -------------------------------------------------------------
    # 7. Security Confirmation Safety
    # -------------------------------------------------------------
    def test_17_destructive_actions_still_require_confirmation(self):
        sec = SecurityManager()
        dec_restart = sec.check("restart_computer")
        self.assertTrue(dec_restart.requires_confirmation)

        dec_shutdown = sec.check("shutdown_computer")
        self.assertTrue(dec_shutdown.requires_confirmation)

        dec_safe = sec.check("get_brightness")
        self.assertFalse(dec_safe.requires_confirmation)
        self.assertTrue(dec_safe.allowed)


if __name__ == "__main__":
    unittest.main()
