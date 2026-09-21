"""Test server health check readiness and event deduplication."""

import asyncio
import json
import os
import sys
import unittest
import urllib.request
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.ui.server import SERAUIServer
from app.core.events import EventBus
from app.core.state import SERAState


class TestServerHealth(unittest.IsolatedAsyncioTestCase):

    async def test_health_and_deduplication(self):
        server = SERAUIServer(host="127.0.0.1", port=8769, runtime=None)
        server.is_initializing_runtime = True
        await server.start()

        # 1. Test 503 while initializing
        status, headers, body = await server._process_http("GET", "/api/health", {}, b"")
        self.assertIn("503", status)
        data = json.loads(body.decode("utf-8"))
        self.assertFalse(data.get("ready"))

        # 2. Mock runtime with active hotkey manager
        mock_runtime = MagicMock()
        mock_runtime.is_ready = True
        mock_runtime.hotkey_manager = MagicMock()
        mock_runtime.hotkey_manager._running = True
        mock_runtime.state = SERAState()
        mock_runtime.events = EventBus()

        server.runtime = mock_runtime
        server.is_initializing_runtime = False

        # 3. Test 200 when ready
        status, headers, body = await server._process_http("GET", "/api/health", {}, b"")
        self.assertIn("200", status)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data.get("ready"))
        self.assertTrue(data.get("hotkey_running"))

        # 4. Test listener deduplication guard
        server._setup_event_listeners()
        listeners_count_1 = len(mock_runtime.events._listeners.get("ACTIVATION_STARTED", []))
        self.assertEqual(listeners_count_1, 1)

        # Calling again must not add duplicate listeners
        server._setup_event_listeners()
        listeners_count_2 = len(mock_runtime.events._listeners.get("ACTIVATION_STARTED", []))
        self.assertEqual(listeners_count_2, 1)

        await server.stop()


if __name__ == "__main__":
    unittest.main()
