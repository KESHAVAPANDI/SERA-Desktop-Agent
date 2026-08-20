import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.runtime import SERARuntime
from app.core.state import SERAStatus
from app.core.streaming import SentenceBuffer, stream_sentences
from app.core.telemetry import LatencyMetrics
from app.models.llm.base import LLMResponse
from app.speech.audio_manager import AudioManager
from app.tools import create_tool_registry


class TestSentenceBuffer(unittest.TestCase):

    def test_sentence_buffering(self):
        buf = SentenceBuffer(min_words=3)
        tokens = ["Python ", "is ", "a ", "versatile ", "programming ", "language. ", "It ", "is ", "fast ", "to ", "learn!"]
        sentences = []
        for t in tokens:
            sentences.extend(buf.add_token(t))
        sentences.extend(buf.flush())

        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[0], "Python is a versatile programming language.")
        self.assertEqual(sentences[1], "It is fast to learn!")

    def test_clause_buffering(self):
        buf = SentenceBuffer(min_words=3, max_buffer_chars=50)
        tokens = ["When a program uses too much memory, ", "the OS begins swapping pages to disk."]
        sentences = []
        for t in tokens:
            sentences.extend(buf.add_token(t))
        sentences.extend(buf.flush())

        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[0], "When a program uses too much memory,")
        self.assertEqual(sentences[1], "the OS begins swapping pages to disk.")


class TestSERAPhase2C(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # Create mock audio manager
        self.mock_audio = MagicMock(spec=AudioManager)
        self.mock_audio.is_speaking = False
        self.mock_audio.is_listening = False
        self.mock_audio.listen_once.return_value = "Explain Python memory management."
        self.mock_audio.speak.side_effect = lambda text, on_playback_start=None: (
            on_playback_start() if on_playback_start else None
        )
        self.mock_audio.stop_speaking = MagicMock()

        async def mock_speak_stream(stream, metrics=None, on_playback_start=None):
            self.mock_audio.is_speaking = True
            if on_playback_start:
                on_playback_start()
            if metrics:
                metrics.first_audio_played_at = 100.0
            async for _ in stream:
                await asyncio.sleep(0.01)
            self.mock_audio.is_speaking = False

        self.mock_audio.speak_stream = AsyncMock(side_effect=mock_speak_stream)

        # Create mock model router with stream support
        mock_router = MagicMock()
        mock_router.has_role.return_value = True
        mock_router.select_role_for_task.return_value = "reasoning"
        mock_router.generate_with_fallback = AsyncMock(
            return_value=(
                LLMResponse(text="Memory is managed automatically.", tool_calls=[]),
                "reasoning",
            )
        )

        async def mock_generate_stream(*args, **kwargs):
            tokens = ["Python ", "manages ", "memory ", "automatically. ", "It ", "uses ", "reference ", "counting."]
            for t in tokens:
                await asyncio.sleep(0.01)
                yield t, "reasoning"

        mock_router.generate_stream_with_fallback = mock_generate_stream

        # Initialize runtime with mocked components
        self.runtime = SERARuntime(
            audio_manager=self.mock_audio,
            tools_registry=create_tool_registry(),
            model_router=mock_router,
        )
        self.runtime._loop = asyncio.get_running_loop()

    async def test_streaming_conversational_turn(self):
        """Verify conversational requests stream through SentenceBuffer and AudioManager.speak_stream."""
        metrics = LatencyMetrics(turn_id="test-123")
        response = await self.runtime.process_text("Explain Python memory management.", metrics=metrics)

        # Verify response text was collected
        self.assertEqual(response, "Python manages memory automatically. It uses reference counting.")
        # Verify speak_stream was invoked
        self.mock_audio.speak_stream.assert_called_once()
        # Verify TTFA metric was calculated
        self.assertIsNotNone(metrics.llm_first_token_at)

    async def test_local_intent_bypasses_streaming(self):
        """Verify deterministic local commands bypass streaming LLM and use direct speak()."""
        metrics = LatencyMetrics(turn_id="test-local")
        response = await self.runtime.process_text("Set my brightness to 50 percent", metrics=metrics)

        self.assertIn("Brightness has been set to 50%", response)
        # Verify speak was called for fast path
        self.mock_audio.speak.assert_called_once()
        # Verify speak_stream was NOT called
        self.mock_audio.speak_stream.assert_not_called()

    async def test_interruption_during_streaming(self):
        """Verify pressing hotkey during streaming speech immediately halts playback and transitions to LISTENING."""
        self.runtime.state.transition_to(SERAStatus.SPEAKING)
        self.mock_audio.is_speaking = True

        self.runtime.handle_hotkey_trigger()

        self.mock_audio.stop_speaking.assert_called_once()
        self.assertEqual(self.runtime.state.status, SERAStatus.LISTENING)

        if self.runtime._active_task:
            await self.runtime._active_task


if __name__ == "__main__":
    unittest.main()
