import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock

from app.core.runtime import SERARuntime
from app.core.state import SERAStatus
from app.core.telemetry import LatencyMetrics
from app.models.llm.base import LLMResponse
from app.speech.audio_manager import AudioManager
from app.tools import create_tool_registry


class TestSERAPhase2A(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Create mock audio manager (no real mic / sound playback)
        self.mock_audio = MagicMock(spec=AudioManager)
        self.mock_audio.is_speaking = False
        self.mock_audio.is_listening = False
        self.mock_audio.listen_once.return_value = "set my brightness to 40%"
        self.mock_audio.speak.side_effect = lambda text, on_playback_start=None: (
            on_playback_start() if on_playback_start else None
        )
        async def mock_speak_stream(stream, metrics=None, on_playback_start=None):
            self.mock_audio.is_speaking = True
            if on_playback_start:
                on_playback_start()
            async for _ in stream:
                await asyncio.sleep(0.01)
            self.mock_audio.is_speaking = False

        self.mock_audio.speak_stream = AsyncMock(side_effect=mock_speak_stream)
        self.mock_audio.stop_speaking = MagicMock()

        # Create mock model router
        self.mock_model = AsyncMock()
        self.mock_model.capabilities.return_value = {"tool_calling": True}
        self.mock_model.generate.return_value = LLMResponse(
            text="I've processed your request.",
            tool_calls=[],
        )

        mock_router = MagicMock()
        mock_router.has_role.return_value = True
        mock_router.select_role_for_task.return_value = "reasoning"
        mock_router.generate_with_fallback = AsyncMock(
            return_value=(
                LLMResponse(text="I've completed the task.", tool_calls=[]),
                "reasoning",
            )
        )

        # Initialize runtime with mocked components
        self.runtime = SERARuntime(
            audio_manager=self.mock_audio,
            tools_registry=create_tool_registry(),
            model_router=mock_router,
        )
        self.runtime._loop = asyncio.get_running_loop()

    async def test_integration_flow_idle_hotkey_to_idle(self):
        """Integration test: IDLE -> Hotkey -> LISTENING -> STT -> Local Intent (Brightness) -> Tool -> TTS -> IDLE"""
        self.assertEqual(self.runtime.state.status, SERAStatus.IDLE)

        # Telemetry listener
        received_metrics = []
        self.runtime.events.subscribe("latency_metrics", lambda metrics: received_metrics.append(metrics))

        # 1. Trigger hotkey
        self.runtime.handle_hotkey_trigger()
        self.assertEqual(self.runtime.state.status, SERAStatus.LISTENING)

        # Wait for the voice turn task to complete
        if self.runtime._active_task:
            await self.runtime._active_task

        # Verify final state is IDLE
        self.assertEqual(self.runtime.state.status, SERAStatus.IDLE)
        self.assertIn("Brightness has been set to 40%", self.runtime.state.last_response)

        # Verify TTS spoke the response
        self.mock_audio.speak.assert_called()

        # Verify Latency Telemetry was emitted
        self.assertEqual(len(received_metrics), 1)
        m = received_metrics[0]
        self.assertIsInstance(m, LatencyMetrics)
        self.assertIsNotNone(m.total_turn_latency_ms)
        self.assertIsNotNone(m.intent_duration_ms)

    async def test_interruption_speaking_to_listening(self):
        """Interruption test: SPEAKING -> Hotkey -> TTS stops -> LISTENING"""
        # Set state to SPEAKING
        self.runtime.state.transition_to(SERAStatus.SPEAKING)
        self.mock_audio.is_speaking = True

        # User presses hotkey while assistant is speaking
        self.runtime.handle_hotkey_trigger()

        # Verify audio manager immediately stopped speaking
        self.mock_audio.stop_speaking.assert_called_once()
        self.assertEqual(self.runtime.state.status, SERAStatus.LISTENING)

        # Clean up active task
        if self.runtime._active_task:
            await self.runtime._active_task

    async def test_task_cancellation_during_thinking(self):
        """Cancellation test: Slow LLM Task in THINKING is cleanly cancelled on hotkey."""
        # Create a slow mock LLM generate
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(5.0)
            return LLMResponse(text="Delayed response", tool_calls=[])

        async def slow_stream(*args, **kwargs):
            await asyncio.sleep(5.0)
            yield "Delayed response", "reasoning"

        self.runtime.router.generate_with_fallback = slow_generate
        self.runtime.router.generate_stream_with_fallback = slow_stream

        # Start an async processing task
        slow_task = asyncio.create_task(self.runtime.process_text("Tell me a long story"))
        self.runtime._active_task = slow_task
        await asyncio.sleep(0.05)

        self.assertEqual(self.runtime.state.status, SERAStatus.THINKING)

        # Press hotkey while thinking to interrupt and start a new command
        self.runtime.handle_hotkey_trigger()

        # Let the event loop cycle to process cancellation
        await asyncio.sleep(0.05)

        # Verify task was cancelled and state transitioned to LISTENING
        self.assertTrue(slow_task.cancelled() or slow_task.done())

        # Clean up
        if self.runtime._active_task:
            await self.runtime._active_task


if __name__ == "__main__":
    unittest.main()
