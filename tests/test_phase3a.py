import asyncio
import time
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from PIL import Image

from app.core.runtime import SERARuntime
from app.core.state import SERAStatus
from app.core.telemetry import LatencyMetrics
from app.models.llm.base import LLMResponse
from app.speech.audio_manager import AudioManager
from app.tools import create_tool_registry
from app.vision.analyzer import ScreenPerceptionEngine
from app.vision.capture import ScreenCapture
from app.vision.context import ScreenContextCache
from app.vision.models import ScreenContext, UIElement


class TestPhase3A(unittest.IsolatedAsyncioTestCase):

    def test_screen_capture_service(self):
        """Test image scaling, byte encoding, and MD5 hashing."""
        capture = ScreenCapture(max_width=800, image_quality=80)
        img, encoded, screen_hash, orig_w, orig_h = capture.capture_screen()

        self.assertIsInstance(img, Image.Image)
        self.assertIsInstance(encoded, bytes)
        self.assertIsInstance(screen_hash, str)
        self.assertEqual(len(screen_hash), 32)
        self.assertLessEqual(img.width, 800)

    def test_screen_context_cache(self):
        """Test cache storage, hash lookup, and TTL expiration."""
        cache = ScreenContextCache(enabled=True, ttl_seconds=0.1)
        ctx = ScreenContext(
            timestamp=time.time(),
            screen_hash="abc123hash",
            width=1920,
            height=1080,
            application="Visual Studio Code",
            window_title="main.py",
            summary="Writing Python code.",
            visible_text=["def main():"],
            elements=[UIElement(type="button", text="Run")],
        )

        cache.set("abc123hash", ctx)
        # Immediate lookup -> hit
        self.assertIsNotNone(cache.get("abc123hash"))
        # Different hash -> miss
        self.assertIsNone(cache.get("different_hash"))

        # Wait for expiration
        time.sleep(0.15)
        self.assertIsNone(cache.get("abc123hash"))

    def test_screen_context_voice_summary(self):
        """Test natural language summary formatting."""
        ctx = ScreenContext(
            timestamp=time.time(),
            screen_hash="test",
            width=1920,
            height=1080,
            application="Visual Studio Code",
            window_title="main.py",
            summary="An editor window with Python code.",
            visible_text=["Error: ConnectionResetError in socket"],
            elements=[],
        )

        error_summary = ctx.format_voice_summary("What error is on my screen?")
        self.assertIn("ConnectionResetError", error_summary)

        app_summary = ctx.format_voice_summary("What application is open?")
        self.assertIn("Visual Studio Code", app_summary)

    async def test_screen_perception_engine_with_cache(self):
        """Test perception engine with mock vision provider, verify cache hit."""
        mock_router = MagicMock()
        mock_router.generate_with_fallback = AsyncMock(
            return_value=(
                LLMResponse(
                    text="""```json
{
  "application": "Google Chrome",
  "window_title": "GitHub - SERA",
  "summary": "Browsing GitHub repository.",
  "visible_text": ["README.md", "Clone repository"],
  "elements": [{"type": "button", "text": "Code"}]
}
```""",
                    provider="gemini",
                ),
                "vision",
            )
        )

        mock_capture = MagicMock(spec=ScreenCapture)
        mock_capture.capture_screen.return_value = (
            Image.new("RGB", (100, 100)),
            b"fake_jpeg_bytes",
            "fixed_hash_123",
            1920,
            1080,
        )

        engine = ScreenPerceptionEngine(
            router=mock_router,
            capture_service=mock_capture,
            cache=ScreenContextCache(enabled=True, ttl_seconds=5.0),
        )

        # First call: Cache Miss
        metrics1 = LatencyMetrics()
        ctx1, resp1 = await engine.analyze_screen("What is on my screen?", metrics=metrics1)
        self.assertEqual(ctx1.application, "Google Chrome")
        self.assertIn("Google Chrome is active", resp1)
        self.assertFalse(metrics1.screen_context_cache_hit)
        mock_router.generate_with_fallback.assert_called_once()

        # Second call with same hash: Cache Hit
        metrics2 = LatencyMetrics()
        ctx2, resp2 = await engine.analyze_screen("What application is open?", metrics=metrics2)
        self.assertEqual(ctx2.application, "Google Chrome")
        self.assertTrue(metrics2.screen_context_cache_hit)
        # Vision model should NOT have been called again
        self.assertEqual(mock_router.generate_with_fallback.call_count, 1)

    async def test_runtime_vision_routing(self):
        """Test that vision questions are routed to ScreenPerceptionEngine and bypass action tools."""
        mock_audio = MagicMock(spec=AudioManager)
        mock_audio.is_speaking = False
        mock_audio.speak = MagicMock()

        mock_vision = MagicMock(spec=ScreenPerceptionEngine)
        mock_vision.is_vision_query.return_value = True
        mock_vision.analyze_screen = AsyncMock(
            return_value=(
                ScreenContext(
                    timestamp=time.time(),
                    screen_hash="hash",
                    width=1920,
                    height=1080,
                    application="VS Code",
                    window_title="app.py",
                    summary="Editing app.py",
                    visible_text=[],
                    elements=[],
                ),
                "You have VS Code open editing app.py.",
            )
        )

        runtime = SERARuntime(
            audio_manager=mock_audio,
            tools_registry=create_tool_registry(),
            model_router=MagicMock(),
            vision_engine=mock_vision,
        )

        response = await runtime.process_text("What is on my screen?")
        self.assertEqual(response, "You have VS Code open editing app.py.")
        mock_vision.analyze_screen.assert_called_once()
        mock_audio.speak.assert_called_once()


if __name__ == "__main__":
    unittest.main()
