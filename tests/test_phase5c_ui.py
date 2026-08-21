import asyncio
import json
import unittest
from unittest.mock import MagicMock

import httpx
import websockets

from app.core.events import EventBus
from app.core.router import ModelRouter, RoleCandidate
from app.core.state import SERAState, SERAStatus
from app.models.llm.health import ModelHealthRegistry
from app.ui.server import SERAUIServer


class TestPhase5CUI(unittest.IsolatedAsyncioTestCase):
    """Comprehensive test suite for Phase 5C Temporal Aura Command Center."""

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

        self.mock_gemini = MagicMock()
        self.mock_gemini.provider_name = "gemini"
        self.mock_gemini.capabilities.return_value = {"text": True, "vision": True, "tool_calling": True, "streaming": True}

        self.router = ModelRouter(
            role_chains={
                "reasoning": [
                    RoleCandidate("groq", "openai/gpt-oss-120b", self.mock_groq, "reasoning"),
                    RoleCandidate("mistral", "mistral-large-latest", self.mock_mistral, "reasoning"),
                ],
                "vision": [
                    RoleCandidate("groq", "qwen/qwen3.6-27b", self.mock_groq, "vision"),
                    RoleCandidate("gemini", "gemini-3-flash-preview", self.mock_gemini, "vision"),
                ],
                "desktop": [
                    RoleCandidate("mistral", "codestral-latest", self.mock_mistral, "desktop"),
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
            port=8775,
            runtime=self.mock_runtime,
        )
        await self.server.start()

    async def asyncTearDown(self):
        await self.server.stop()

    # 1. State Snapshot API
    async def test_01_state_snapshot_api(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8775") as client:
            resp = await client.get("/api/state")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "IDLE")
            self.assertIn("roles", data)
            self.assertIn("providers", data)
            self.assertIn("workflow", data)

    # 2. Broken State in Workflow Graph
    async def test_02_broken_state_in_workflow_graph(self):
        self.state.transition_to(SERAStatus.BROKEN)
        graph = self.server._get_dynamic_workflow_graph()
        self.assertEqual(graph["status"], "BROKEN")

    # 3. Three Execution Modes Configuration
    async def test_03_execution_modes_update(self):
        res = self.server._update_role_candidates("reasoning", [
            {"provider": "groq", "model": "openai/gpt-oss-120b"}
        ], mode="PRIMARY_ONLY")
        self.assertTrue(res["success"])
        self.assertEqual(self.server.role_execution_modes["reasoning"], "PRIMARY_ONLY")

        # Graph in PRIMARY_ONLY only contains 1 candidate
        graph = self.server._get_dynamic_workflow_graph()
        reasoning_nodes = [n for n in graph["nodes"] if n["role"] == "reasoning"]
        self.assertEqual(len(reasoning_nodes), 1)

    # 4. Custom Mode & Capability Validation
    async def test_04_capability_validation_in_role_update(self):
        # Mistral does not support vision
        res = self.server._update_role_candidates("vision", [
            {"provider": "mistral", "model": "mistral-small-latest"}
        ], mode="CUSTOM")
        self.assertFalse(res["success"])
        self.assertIn("does not support vision", res["error"])

    # 5. Active Task Edit Lock
    async def test_05_active_execution_safety_lock(self):
        self.state.transition_to(SERAStatus.EXECUTING)
        res = self.server._update_role_candidates("fast", [
            {"provider": "mistral", "model": "mistral-small-latest"}
        ])
        self.assertFalse(res["success"])
        self.assertIn("Safety guard", res["error"])

    # 6. Dynamic Quota Metrics Endpoint
    async def test_06_dynamic_quota_metrics_endpoint(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8775") as client:
            resp = await client.get("/api/providers")
            self.assertEqual(resp.status_code, 200)
            providers = resp.json()
            groq = next(p for p in providers if p["provider_name"] == "groq")
            gpt_model = next(m for m in groq["models"] if m["model_id"] == "openai/gpt-oss-120b")
            self.assertGreaterEqual(len(gpt_model["quota_metrics"]), 2)
            self.assertEqual(gpt_model["quota_metrics"][0]["label"], "Requests / Minute")

    # 7. Vercel-Style Provider Onboarding
    async def test_07_provider_onboarding_pipeline(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8775") as client:
            payload = {
                "provider_name": "deepseek",
                "display_name": "DeepSeek API",
                "base_url": "https://api.deepseek.com/v1",
                "api_key_env": "DEEPSEEK_API_KEY",
                "format": "openai_compatible",
            }
            resp = await client.post("/api/providers/add", json=payload)
            self.assertEqual(resp.status_code, 200)
            res = resp.json()
            self.assertTrue(res["success"])
            self.assertEqual(res["provider"]["provider_name"], "deepseek")

    # 8. Security Policies & Privacy Breakdown
    async def test_08_security_policies_endpoint(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8775") as client:
            resp = await client.get("/api/security")
            self.assertEqual(resp.status_code, 200)
            sec = resp.json()
            self.assertIn("permissions", sec)
            self.assertIn("privacy", sec)
            self.assertEqual(sec["permissions"]["screen_reading"]["status"], "ALLOWED")
            self.assertEqual(sec["permissions"]["shutdown_pc"]["status"], "CONFIRM_ALWAYS")

    # 9. Memory Core & Forget Action
    async def test_09_memory_core_and_forget_action(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8775") as client:
            resp = await client.get("/api/memory")
            self.assertEqual(resp.status_code, 200)
            items = resp.json()
            self.assertGreaterEqual(len(items), 3)

            # Forget an item
            del_id = items[0]["id"]
            resp_del = await client.post("/api/memory/forget", json={"id": del_id})
            self.assertEqual(resp_del.status_code, 200)
            self.assertTrue(resp_del.json()["success"])

            # Verify removed
            resp_after = await client.get("/api/memory")
            after_items = resp_after.json()
            self.assertFalse(any(i["id"] == del_id for i in after_items))

    # 10. History Sessions & Rerun Task
    async def test_10_history_sessions_and_rerun_task(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8775") as client:
            resp = await client.get("/api/history")
            self.assertEqual(resp.status_code, 200)
            sessions = resp.json()
            self.assertGreaterEqual(len(sessions), 2)
            self.assertIn("pipeline", sessions[0])

            # Rerun
            resp_rerun = await client.post("/api/history/rerun", json={"query": "Open Chrome"})
            self.assertEqual(resp_rerun.status_code, 200)
            self.assertTrue(resp_rerun.json()["success"])

    # 11. Telemetry Waterfall Breakdown
    async def test_11_telemetry_waterfall_endpoint(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8775") as client:
            resp = await client.get("/api/telemetry")
            self.assertEqual(resp.status_code, 200)
            telemetry = resp.json()
            self.assertIn("stages", telemetry)
            self.assertGreaterEqual(len(telemetry["stages"]), 4)

    # 12. WebSocket Real-Time Broadcast & Confirmation Event
    async def test_12_websocket_confirmation_and_events(self):
        ws_url = "ws://127.0.0.1:8775/ws"
        async with websockets.connect(ws_url) as ws:
            snap = json.loads(await ws.recv())
            self.assertEqual(snap["event"], "SNAPSHOT")

            # Broadcast confirmation request
            await self.server.broadcast_event("SECURITY_CONFIRMATION_REQUIRED", {
                "action_id": "act_99",
                "tool_name": "delete_file",
                "prompt": "Delete old backup file?",
                "arguments": {"path": "C:/temp/backup.zip"},
            })

            msg = json.loads(await ws.recv())
            self.assertEqual(msg["event"], "SECURITY_CONFIRMATION_REQUIRED")
            self.assertEqual(msg["data"]["tool_name"], "delete_file")

            # Client responds with confirmation
            await ws.send(json.dumps({"action": "CONFIRM_ACTION", "action_id": "act_99", "allowed": True}))
            res_msg = json.loads(await ws.recv())
            self.assertEqual(res_msg["event"], "ACTION_CONFIRMED")
            self.assertTrue(res_msg["data"]["allowed"])


if __name__ == "__main__":
    unittest.main()
