import asyncio
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import httpx
import websockets

from app.core.events import EventBus
from app.core.router import ModelRouter, RoleCandidate
from app.core.state import SERAState, SERAStatus
from app.models.llm.health import ModelHealthRegistry
from app.ui.server import SERAUIServer


class TestPhase5C1Interaction(unittest.IsolatedAsyncioTestCase):
    """Unit tests for Phase 5C.1 Real Runtime Integration, Layout Persistence, and Freeform Canvas."""

    async def asyncSetUp(self):
        self.state = SERAState()
        self.events = EventBus()
        self.health_registry = ModelHealthRegistry()

        # Mock Providers
        self.mock_groq = MagicMock()
        self.mock_groq.provider_name = "groq"
        self.mock_groq.capabilities.return_value = {"text": True, "vision": True, "tool_calling": True, "streaming": True, "reasoning": True}

        self.mock_mistral = MagicMock()
        self.mock_mistral.provider_name = "mistral"
        self.mock_mistral.capabilities.return_value = {"text": True, "vision": False, "tool_calling": True, "streaming": True, "reasoning": True}

        self.router = ModelRouter(
            role_chains={
                "reasoning": [
                    RoleCandidate("groq", "openai/gpt-oss-120b", self.mock_groq, "reasoning"),
                    RoleCandidate("mistral", "mistral-large-latest", self.mock_mistral, "reasoning"),
                ],
                "fast": [
                    RoleCandidate("mistral", "mistral-small-latest", self.mock_mistral, "fast"),
                ],
            },
            health_registry=self.health_registry,
        )

        self.mock_runtime = MagicMock()
        self.mock_runtime.state = self.state
        self.mock_runtime.events = self.events
        self.mock_runtime.router = self.router

        self.server = SERAUIServer(
            host="127.0.0.1",
            port=8788,
            runtime=self.mock_runtime,
        )
        # Use a temporary workflow layout file
        self.server.workflow_layout_path = os.path.join(os.path.dirname(__file__), "test_layout.json")
        if os.path.exists(self.server.workflow_layout_path):
            os.remove(self.server.workflow_layout_path)

        await self.server.start()

    async def asyncTearDown(self):
        await self.server.stop()
        if os.path.exists(self.server.workflow_layout_path):
            os.remove(self.server.workflow_layout_path)

    # 1. Runtime Attached Snapshot Flag
    async def test_01_runtime_attached_in_state(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8788") as client:
            resp = await client.get("/api/state")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data.get("runtime_attached"))
            self.assertIn("workflow_layout", data)

    # 2. Workflow Visual Layout Persistence
    async def test_02_layout_get_and_post(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8788") as client:
            # Initial layout
            r_get = await client.get("/api/workflow/layout")
            self.assertEqual(r_get.status_code, 200)
            self.assertIn("workflow_layout", r_get.json())

            # Update layout coordinates (DaVinci-style freeform drag)
            payload = {
                "nodes": {
                    "node_stt": {"x": 128, "y": 256},
                    "node_reasoning_0": {"x": 720, "y": 384},
                }
            }
            r_post = await client.post("/api/workflow/layout", json=payload)
            self.assertEqual(r_post.status_code, 200)
            res = r_post.json()
            self.assertTrue(res["success"])
            self.assertEqual(res["workflow_layout"]["nodes"]["node_stt"]["x"], 128)

            # Check that dynamic graph overlays the custom coordinates
            graph = self.server._get_dynamic_workflow_graph()
            stt_node = next(n for n in graph["nodes"] if n["id"] == "node_stt")
            self.assertEqual(stt_node["x"], 128)
            self.assertEqual(stt_node["y"], 256)

    # 3. Decoupling: Visual Position vs Semantic Execution Order
    async def test_03_visual_drag_does_not_change_execution_priority(self):
        # Moving reasoning candidate to a new (x, y) coordinate
        self.server._save_workflow_layout({
            "node_reasoning_0": {"x": 950, "y": 800}
        })
        # Verify primary candidate remains Groq GPT-OSS
        candidates = self.server.runtime.router.get_role_candidates("reasoning")
        self.assertEqual(candidates[0].provider_name, "groq")
        self.assertEqual(candidates[0].model_name, "openai/gpt-oss-120b")

    # 4. Dual Activation Telemetry (Hotkey vs Wake Word)
    async def test_04_dual_activation_telemetry(self):
        ws_url = "ws://127.0.0.1:8788/ws"
        async with websockets.connect(ws_url) as ws:
            snap = json.loads(await ws.recv())
            self.assertEqual(snap["event"], "SNAPSHOT")

            # A. Hotkey Activation
            await self.server.broadcast_event("CAPTURE_COUNTDOWN", {
                "duration_seconds": 5.0,
                "activation_method": "HOTKEY",
            })
            msg_hotkey = json.loads(await ws.recv())
            self.assertEqual(msg_hotkey["data"]["activation_method"], "HOTKEY")
            self.assertEqual(msg_hotkey["data"]["duration_seconds"], 5.0)

            # B. Wake Word Activation
            await self.server.broadcast_event("CAPTURE_COUNTDOWN", {
                "duration_seconds": 5.0,
                "activation_method": "WAKE_WORD",
            })
            msg_wake = json.loads(await ws.recv())
            self.assertEqual(msg_wake["data"]["activation_method"], "WAKE_WORD")

    # 5. Standalone UI Server (No runtime attached)
    async def test_05_standalone_server_indicator(self):
        standalone_server = SERAUIServer(host="127.0.0.1", port=8789, runtime=None)
        await standalone_server.start()
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8789") as client:
                resp = await client.get("/api/state")
                self.assertEqual(resp.status_code, 200)
                self.assertFalse(resp.json().get("runtime_attached"))
        finally:
            await standalone_server.stop()


if __name__ == "__main__":
    unittest.main()
