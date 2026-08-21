import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

from app.core.hotkey import GlobalHotkeyManager
from app.core.events import EventBus
from app.core.state import SERAState, SERAStatus
from app.speech.recorder import AudioRecorder
from app.speech.wakeword import OpenWakeWordDetector


class TestPhase5C2RuntimeVoice(unittest.IsolatedAsyncioTestCase):
    """Unit tests for Phase 5C.2 Hold-To-Talk Voice Control, Wake-Word, and Mic Lifecycle."""

    def setUp(self):
        self.state = SERAState()
        self.events = EventBus()

    # 1. Hold-To-Talk Press and Release Sequence
    def test_01_hold_to_talk_press_and_release(self):
        press_called = False
        release_called = False

        def on_press():
            nonlocal press_called
            press_called = True

        def on_release():
            nonlocal release_called
            release_called = True

        manager = GlobalHotkeyManager(
            hotkey="ctrl+space",
            on_press=on_press,
            on_release=on_release,
        )

        self.assertFalse(manager.is_held)
        # Simulate KeyDown
        manager.trigger_press()
        self.assertTrue(manager.is_held)
        self.assertTrue(press_called)

        # Simulate KeyUp
        manager.trigger_release()
        self.assertFalse(manager.is_held)
        self.assertTrue(release_called)

    # 2. AudioRecorder Hold-To-Talk Dynamic Streaming Capture
    def test_02_recorder_start_and_stop_streaming(self):
        recorder = AudioRecorder(sample_rate=16000)
        self.assertFalse(recorder.is_recording)

        # Mock InputStream
        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream = MagicMock()
            mock_stream_cls.return_value = mock_stream

            started = recorder.start_recording()
            self.assertTrue(started)
            self.assertTrue(recorder.is_recording)

            # Push mock audio chunk
            mock_chunk = np.ones(1600, dtype=np.float32)
            recorder._active_chunks.append(mock_chunk)

            # Stop recording
            audio_out = recorder.stop_recording()
            self.assertFalse(recorder.is_recording)
            self.assertEqual(len(audio_out), 1600)

    # 3. Wake-Word 5-Second Fixed Capture Flow
    async def test_03_wakeword_fixed_capture_duration(self):
        recorder = AudioRecorder(sample_rate=16000)

        with patch("sounddevice.InputStream") as mock_stream_cls:
            mock_stream = MagicMock()
            mock_stream_cls.return_value = mock_stream

            # Simulate fast 0.05s recording
            audio = await recorder.record_for(0.05)
            self.assertIsInstance(audio, np.ndarray)

    # 4. Wake-Word Detection & Microphone Yielding
    def test_04_wakeword_yield_and_resume(self):
        detector = OpenWakeWordDetector(phrase="SERA")
        wake_called = False

        def on_wake():
            nonlocal wake_called
            wake_called = True

        detector.start(on_wake)
        self.assertTrue(detector.is_running())

        # Trigger wake word
        detector.trigger_manually()
        self.assertTrue(wake_called)

        # Yield mic (pause)
        detector.pause()
        self.assertFalse(detector.is_running())

        # Resume mic
        detector.resume()
        self.assertTrue(detector.is_running())
        detector.stop()


if __name__ == "__main__":
    unittest.main()
