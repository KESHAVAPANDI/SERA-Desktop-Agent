import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

from app.core.hotkey import GlobalHotkeyManager
from app.core.runtime import SERARuntime
from app.core.state import SERAState, SERAStatus
from app.models.stt.base import STTProvider, STTResult
from app.models.stt.nvidia import NVIDIASTTProvider
from app.models.stt.whisper import FasterWhisperSTTProvider
from app.models.stt import PrimaryWithFallbackSTT
from app.speech.recorder import AudioRecorder
from app.speech.transcript_gate import TranscriptQualityGate
from app.speech.wakeword import OpenWakeWordDetector


class TestPhase42NVIDIASTT(unittest.IsolatedAsyncioTestCase):
    """Comprehensive test suite for SERA 1.0 Phase 4.2 NVIDIA STT, 5s Capture, Wake Word & Fallback."""

    def setUp(self):
        self.gate = TranscriptQualityGate()

    # -------------------------------------------------------------
    # 1. NVIDIA Provider Initialization & Request Construction
    # -------------------------------------------------------------
    def test_01_nvidia_provider_initialization(self):
        provider = NVIDIASTTProvider(api_key="test_key", model="nvidia/canary-qwen-2.5b")
        self.assertEqual(provider.api_key, "test_key")
        self.assertEqual(provider.model, "nvidia/canary-qwen-2.5b")
        self.assertEqual(provider.endpoint, NVIDIASTTProvider.DEFAULT_ENDPOINT)

    def test_02_audio_to_wav_conversion(self):
        provider = NVIDIASTTProvider(api_key="test_key")
        # 16kHz 1-second sine wave
        audio = np.sin(np.linspace(0, 100, 16000)).astype(np.float32)
        wav_bytes = provider._audio_to_wav_bytes(audio, sample_rate=16000)
        self.assertTrue(len(wav_bytes) > 1000)
        self.assertEqual(wav_bytes[:4], b"RIFF")
        self.assertEqual(wav_bytes[8:12], b"WAVE")

    @patch("httpx.AsyncClient.post")
    async def test_03_nvidia_transcription_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "text": "Open Google Chrome",
            "confidence": 0.98,
        }
        mock_post.return_value = mock_resp

        provider = NVIDIASTTProvider(api_key="test_key")
        audio = np.zeros(16000, dtype=np.float32)
        result = await provider.transcribe(audio, sample_rate=16000, language="en-US")

        self.assertIsInstance(result, STTResult)
        self.assertEqual(result.text, "Open Google Chrome")
        self.assertEqual(result.provider, "nvidia")
        self.assertEqual(result.model, "nvidia/canary-qwen-2.5b")
        self.assertEqual(result.language, "en-US")
        self.assertAlmostEqual(result.duration, 1.0, delta=0.1)

    # -------------------------------------------------------------
    # 2. Primary / Fallback Policy & Error Handling
    # -------------------------------------------------------------
    async def test_04_primary_fallback_to_whisper_on_error(self):
        failing_primary = MagicMock(spec=STTProvider)
        failing_primary.transcribe = AsyncMock(side_effect=RuntimeError("500 NVIDIA Service Unavailable"))
        failing_primary.model = "nvidia/canary-qwen-2.5b"

        fallback_whisper = MagicMock(spec=STTProvider)
        fallback_whisper.transcribe = AsyncMock(return_value=STTResult(
            text="Open Notepad",
            provider="faster_whisper",
            model="small",
            duration=5.0,
            confidence=0.92,
        ))
        fallback_whisper.model_size = "small"

        coordinator = PrimaryWithFallbackSTT(
            primary=failing_primary,
            fallback=fallback_whisper,
            primary_enabled=True,
        )

        audio = np.zeros(16000, dtype=np.float32)
        result = await coordinator.transcribe(audio)

        self.assertEqual(result.text, "Open Notepad")
        self.assertEqual(result.provider, "faster_whisper")
        failing_primary.transcribe.assert_called_once()
        fallback_whisper.transcribe.assert_called_once()

    @patch("httpx.AsyncClient.post")
    async def test_05_nvidia_429_triggers_fallback(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limit exceeded"
        mock_post.return_value = mock_resp

        nvidia_prov = NVIDIASTTProvider(api_key="test_key")
        fallback_prov = MagicMock(spec=STTProvider)
        fallback_prov.transcribe = AsyncMock(return_value=STTResult(
            text="Set brightness to 50%",
            provider="faster_whisper",
            model="small",
        ))

        coordinator = PrimaryWithFallbackSTT(primary=nvidia_prov, fallback=fallback_prov)
        audio = np.zeros(16000, dtype=np.float32)
        result = await coordinator.transcribe(audio)

        self.assertEqual(result.text, "Set brightness to 50%")
        self.assertEqual(result.provider, "faster_whisper")

    # -------------------------------------------------------------
    # 3. Fixed-Duration Audio Recorder
    # -------------------------------------------------------------
    @patch("sounddevice.InputStream")
    async def test_06_audio_recorder_fixed_duration(self, mock_stream):
        recorder = AudioRecorder(sample_rate=16000)
        # Mocking InputStream context manager
        stream_instance = MagicMock()
        mock_stream.return_value.__enter__.return_value = stream_instance

        audio = await recorder.record_for(seconds=0.05)
        self.assertIsInstance(audio, np.ndarray)

    def test_07_audio_recorder_cancellation(self):
        recorder = AudioRecorder(sample_rate=16000)
        self.assertFalse(recorder._cancel_flag)
        recorder.cancel()
        self.assertTrue(recorder._cancel_flag)

    # -------------------------------------------------------------
    # 4. Wake-Word Detector & Debounce
    # -------------------------------------------------------------
    def test_08_wakeword_trigger_and_debounce(self):
        triggered_count = 0
        def _cb():
            nonlocal triggered_count
            triggered_count += 1

        detector = OpenWakeWordDetector(phrase="SERA", debounce_ms=500)
        detector._on_detected = _cb

        # First trigger succeeds
        res1 = detector.trigger_manually()
        self.assertTrue(res1)
        self.assertEqual(triggered_count, 1)

        # Immediate second trigger is debounced
        res2 = detector.trigger_manually()
        self.assertFalse(res2)
        self.assertEqual(triggered_count, 1)

    def test_09_wakeword_suppression_while_paused(self):
        triggered_count = 0
        def _cb():
            nonlocal triggered_count
            triggered_count += 1

        detector = OpenWakeWordDetector(phrase="SERA", debounce_ms=100)
        detector._on_detected = _cb
        detector.pause()

        res = detector.trigger_manually()
        self.assertFalse(res)
        self.assertEqual(triggered_count, 0)

        detector.resume()
        res_after = detector.trigger_manually()
        self.assertTrue(res_after)
        self.assertEqual(triggered_count, 1)

    # -------------------------------------------------------------
    # 5. Runtime Unified Activation (Hotkey + Wake Word)
    # -------------------------------------------------------------
    async def test_10_unified_activation_from_idle(self):
        state = SERAState()
        state.transition_to(SERAStatus.IDLE)

        audio_mock = MagicMock()
        audio_mock.is_speaking = False
        audio_cues_mock = MagicMock()
        recorder_mock = MagicMock()
        recorder_mock.record_for = AsyncMock(return_value=np.zeros(16000, dtype=np.float32))

        stt_mock = MagicMock()
        stt_mock.transcribe = AsyncMock(return_value=STTResult(text="Open Chrome", provider="nvidia"))

        runtime = SERARuntime.__new__(SERARuntime)
        runtime.state = state
        runtime.audio = audio_mock
        runtime.audio_cues = audio_cues_mock
        runtime.recorder = recorder_mock
        runtime.stt = stt_mock
        runtime.quality_gate = self.gate
        runtime.hotkey_event_count = 0
        runtime.wakeword_event_count = 0
        runtime.turn_count = 0
        runtime.manual_debug_mode = False
        runtime.recording_duration = 5.0
        runtime.stt_language = "en-US"
        runtime._active_listen_task = None
        runtime._active_agent_task = None
        runtime._active_task = None
        runtime._loop = None
        runtime._last_printed_state = None
        runtime._process_voice_turn = AsyncMock()

        # Activation via Wake Word
        runtime.handle_wakeword_trigger()
        audio_cues_mock.play_listening_cue.assert_called_once()
        self.assertEqual(state.status, SERAStatus.LISTENING)

    async def test_11_interruption_via_wakeword_while_speaking(self):
        state = SERAState()
        state.transition_to(SERAStatus.SPEAKING)

        audio_mock = MagicMock()
        audio_mock.is_speaking = True
        audio_cues_mock = MagicMock()

        runtime = SERARuntime.__new__(SERARuntime)
        runtime.state = state
        runtime.audio = audio_mock
        runtime.audio_cues = audio_cues_mock
        runtime.recorder = MagicMock()
        runtime.stt = MagicMock()
        runtime.quality_gate = self.gate
        runtime.hotkey_event_count = 0
        runtime.wakeword_event_count = 0
        runtime.turn_count = 0
        runtime._active_listen_task = None
        runtime._active_agent_task = None
        runtime._active_task = None
        runtime._loop = None
        runtime._last_printed_state = None
        runtime._process_voice_turn = AsyncMock()

        # Say "SERA" while assistant is speaking
        runtime.handle_wakeword_trigger()

        audio_mock.stop_speaking.assert_called_once()
        audio_cues_mock.play_interrupted_cue.assert_called_once()
        self.assertEqual(state.status, SERAStatus.LISTENING)

    async def test_12_interruption_via_hotkey_while_thinking(self):
        state = SERAState()
        state.transition_to(SERAStatus.THINKING)

        active_agent_task = MagicMock()
        active_agent_task.done.return_value = False

        audio_cues_mock = MagicMock()

        runtime = SERARuntime.__new__(SERARuntime)
        runtime.state = state
        runtime.audio = MagicMock()
        runtime.audio_cues = audio_cues_mock
        runtime.recorder = MagicMock()
        runtime.stt = MagicMock()
        runtime.quality_gate = self.gate
        runtime.hotkey_event_count = 0
        runtime.wakeword_event_count = 0
        runtime.turn_count = 0
        runtime._active_listen_task = None
        runtime._active_agent_task = active_agent_task
        runtime._active_task = active_agent_task
        runtime._loop = None
        runtime._last_printed_state = None
        runtime._process_voice_turn = AsyncMock()

        # Press Ctrl+Space while thinking
        runtime.handle_hotkey_trigger()

        audio_cues_mock.play_interrupted_cue.assert_called_once()
        active_agent_task.cancel.assert_called_once()
        self.assertEqual(state.status, SERAStatus.LISTENING)

    # -------------------------------------------------------------
    # 6. Quality Gate on STTResult
    # -------------------------------------------------------------
    def test_13_quality_gate_evaluates_stt_result(self):
        valid_res = STTResult(text="what time is it?", provider="nvidia", confidence=0.95)
        dec1 = self.gate.evaluate(valid_res)
        self.assertTrue(dec1.accepted)

        noise_res = STTResult(text="um", provider="nvidia", confidence=0.1)
        dec2 = self.gate.evaluate(noise_res)
        self.assertFalse(dec2.accepted)
        self.assertTrue(dec2.is_filler)

        empty_res = STTResult(text="", provider="nvidia")
        dec3 = self.gate.evaluate(empty_res)
        self.assertFalse(dec3.accepted)

    def test_14_single_word_commands_remain_accepted(self):
        for cmd in ["mute", "unmute", "stop", "cancel", "time", "date", "battery"]:
            res = STTResult(text=cmd, provider="nvidia")
            dec = self.gate.evaluate(res)
            self.assertTrue(dec.accepted, f"Failed on command: {cmd}")


if __name__ == "__main__":
    unittest.main()
