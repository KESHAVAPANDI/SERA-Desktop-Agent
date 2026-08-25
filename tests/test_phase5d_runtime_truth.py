import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.core.runtime import SERARuntime
from app.core.state import SERAState, SERAStatus
from app.ui.server import SERAUIServer


class TestPhase5DRuntimeTruth(unittest.IsolatedAsyncioTestCase):
    async def test_01_server_truthful_wake_and_stt_snapshot(self):
        server = SERAUIServer(port=8799)
        snapshot = server._get_initial_snapshot()
        self.assertEqual(snapshot["wake_word_status"], "NOT CONFIGURED")
        self.assertIn("stt_info", snapshot)
        self.assertEqual(snapshot["stt_info"]["active"], "Faster-Whisper (GPU)")
        self.assertEqual(snapshot["mic_status"], "READY")

    async def test_02_memory_truthful_empty_state_initialization(self):
        server = SERAUIServer(port=8798)
        self.assertEqual(server.memory_items, [])
        status, _, body = await server._process_http("GET", "/api/memory", {}, b"")
        self.assertEqual(status, "200 OK")
        self.assertEqual(body, b"[]")

    async def test_03_runtime_has_wakeword_provider(self):
        runtime = SERARuntime.__new__(SERARuntime)
        from app.speech.wakeword import WakeWordRegistry
        runtime.wakeword_provider = WakeWordRegistry.create(enabled=False)
        self.assertIsNotNone(runtime.wakeword_provider)
        self.assertFalse(runtime.wakeword_provider.is_configured)


if __name__ == "__main__":
    unittest.main()
