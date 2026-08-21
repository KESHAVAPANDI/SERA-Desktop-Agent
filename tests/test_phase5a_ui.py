import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

import httpx
import websockets

from app.core.events import EventBus
from app.core.state import SERAState, SERAStatus
from app.ui.server import SERAUIServer


class TestPhase5AUI(unittest.IsolatedAsyncioTestCase):
    """Unit tests for Phase 5A UI/UX Foundation, Application Shell, and WebSocket Gateway."""

    async def asyncSetUp(self):
        self.state = SERAState()
        self.events = EventBus()
        self.mock_runtime = MagicMock()
        self.mock_runtime.state = self.state
        self.mock_runtime.events = self.events

        # Start UI Server on ephemeral test port 8769
        self.server = SERAUIServer(
            host="127.0.0.1",
            port=8769,
            runtime=self.mock_runtime,
        )
        await self.server.start()

    async def asyncTearDown(self):
        await self.server.stop()

    def test_01_static_assets_exist(self):
        static_dir = self.server.static_dir
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "index.html")))
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "css", "variables.css")))
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "css", "main.css")))
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "js", "app.js")))
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "js", "views", "workflow.js")))
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "js", "views", "live.js")))
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "js", "views", "agents.js")))
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "js", "views", "memory.js")))
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "js", "views", "providers.js")))
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "js", "views", "history.js")))
        self.assertTrue(os.path.isfile(os.path.join(static_dir, "js", "views", "debug.js")))

    async def test_02_http_server_serves_html_and_api(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8769") as client:
            # 1. Fetch index.html
            resp_html = await client.get("/")
            self.assertEqual(resp_html.status_code, 200)
            self.assertIn("SERA", resp_html.text)
            self.assertIn("tab-workflow", resp_html.text)
            self.assertIn("tab-live", resp_html.text)

            # 2. Fetch /api/state
            resp_state = await client.get("/api/state")
            self.assertEqual(resp_state.status_code, 200)
            data_state = resp_state.json()
            self.assertIn("status", data_state)
            self.assertEqual(data_state["status"], "IDLE")

            # 3. Fetch /api/providers
            resp_prov = await client.get("/api/providers")
            self.assertEqual(resp_prov.status_code, 200)
            data_prov = resp_prov.json()
            self.assertIsInstance(data_prov, list)
            prov_names = [p["provider_name"] for p in data_prov]
            self.assertIn("groq", prov_names)
            self.assertIn("mistral", prov_names)

    async def test_03_websocket_gateway_snapshot_and_broadcast(self):
        ws_url = "ws://127.0.0.1:8769/ws"
        async with websockets.connect(ws_url) as ws:
            # Receive initial SNAPSHOT
            raw_msg = await ws.recv()
            snapshot = json.loads(raw_msg)
            self.assertEqual(snapshot.get("event"), "SNAPSHOT")
            self.assertEqual(snapshot.get("data", {}).get("status"), "IDLE")

            # Trigger server broadcast
            await self.server.broadcast_event("RUNTIME_STATE_CHANGED", {"status": "THINKING", "task": "Searching RTX 5090"})

            # Receive broadcasted event
            raw_broadcast = await ws.recv()
            broadcast_msg = json.loads(raw_broadcast)
            self.assertEqual(broadcast_msg.get("event"), "RUNTIME_STATE_CHANGED")
            self.assertEqual(broadcast_msg.get("data", {}).get("status"), "THINKING")

    def test_04_backend_independence(self):
        # Verify state transitions remain completely independent
        self.state.transition_to(SERAStatus.LISTENING)
        self.assertEqual(self.state.status, SERAStatus.LISTENING)
        self.state.transition_to(SERAStatus.EXECUTING)
        self.assertEqual(self.state.status, SERAStatus.EXECUTING)


if __name__ == "__main__":
    unittest.main()
