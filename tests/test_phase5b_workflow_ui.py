import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock

import httpx
import websockets

from app.core.events import EventBus
from app.core.router import ModelRouter, RoleCandidate
from app.core.state import SERAState, SERAStatus
from app.models.llm.health import ModelHealthRegistry, ProviderHealthStatus
from app.ui.server import SERAUIServer


class TestPhase5BWorkflowUI(unittest.IsolatedAsyncioTestCase):
    """Comprehensive test suite for Phase 5B Temporal Aura Workflow View and Role Candidate Editor."""

    async def asyncSetUp(self):
        self.state = SERAState()
        self.events = EventBus()
        self.health_registry = ModelHealthRegistry()

        # Mock Providers
        self.mock_groq = MagicMock()
        self.mock_groq.provider_name = "groq"
        self.mock_groq.capabilities.return_value = {"text": True, "vision": True, "tool_calling": True, "streaming": True}

        self.mock_mistral = MagicMock()
        self.mock_mistral.provider_name = "mistral"
        self.mock_mistral.capabilities.return_value = {"text": True, "vision": False, "tool_calling": True, "streaming": True}

        self.mock_gemini = MagicMock()
        self.mock_gemini.provider_name = "gemini"
        self.mock_gemini.capabilities.return_value = {"text": True, "vision": True, "tool_calling": True, "streaming": True}

        self.mock_openrouter = MagicMock()
        self.mock_openrouter.provider_name = "openrouter"
        self.mock_openrouter.capabilities.return_value = {"text": True, "vision": True, "tool_calling": True, "streaming": True}

        # Mock ModelRouter with production candidate chains
        self.router = ModelRouter(
            role_chains={
                "reasoning": [
                    RoleCandidate("groq", "openai/gpt-oss-120b", self.mock_groq, "reasoning"),
                    RoleCandidate("mistral", "mistral-large-latest", self.mock_mistral, "reasoning"),
                ],
                "vision": [
                    RoleCandidate("groq", "qwen/qwen3.6-27b", self.mock_groq, "vision"),
                    RoleCandidate("gemini", "gemini-3-flash-preview", self.mock_gemini, "vision"),
                    RoleCandidate("openrouter", "openrouter/free", self.mock_openrouter, "vision"),
                ],
                "desktop": [
                    RoleCandidate("mistral", "codestral-latest", self.mock_mistral, "desktop"),
                    RoleCandidate("groq", "openai/gpt-oss-120b", self.mock_groq, "desktop"),
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

        # Start UI Server on ephemeral test port 8770
        self.server = SERAUIServer(
            host="127.0.0.1",
            port=8770,
            runtime=self.mock_runtime,
        )
        await self.server.start()

    async def asyncTearDown(self):
        await self.server.stop()

    # 1. Graph Loads
    async def test_01_workflow_graph_loads_via_api(self):
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8770") as client:
            resp = await client.get("/api/workflow")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("nodes", data)
            self.assertIn("edges", data)
            self.assertIn("roles", data)
            self.assertGreaterEqual(len(data["nodes"]), 6)
            self.assertGreaterEqual(len(data["edges"]), 5)

    # 2. Runtime State Renders Correctly
    async def test_02_runtime_state_in_workflow_graph(self):
        self.state.transition_to(SERAStatus.THINKING)
        graph = self.server._get_dynamic_workflow_graph()
        self.assertEqual(graph["status"], "THINKING")

        reasoning_node = next(n for n in graph["nodes"] if n["id"] == "node_reasoning_0")
        self.assertEqual(reasoning_node["status"], "ACTIVE")

    # 3. Node Statuses Update on Execution
    async def test_03_node_statuses_update_on_executing(self):
        self.state.transition_to(SERAStatus.EXECUTING)
        graph = self.server._get_dynamic_workflow_graph()
        tools_node = next(n for n in graph["nodes"] if n["id"] == "node_tools")
        self.assertEqual(tools_node["status"], "ACTIVE")

    # 4. Fallback Event Broadcast
    async def test_04_fallback_event_activates_fallback_path(self):
        ws_url = "ws://127.0.0.1:8770/ws"
        async with websockets.connect(ws_url) as ws:
            await ws.recv() # Initial snapshot

            # Broadcast fallback event
            await self.server.broadcast_event("MODEL_FALLBACK", {
                "role": "reasoning",
                "failed_provider": "groq",
                "failed_model": "openai/gpt-oss-120b",
                "fallback_provider": "mistral",
                "fallback_model": "mistral-large-latest",
                "reason": "429 Rate Limit",
            })

            raw_msg = await ws.recv()
            msg = json.loads(raw_msg)
            self.assertEqual(msg["event"], "MODEL_FALLBACK")
            self.assertEqual(msg["data"]["fallback_provider"], "mistral")

    # 5. Rate-Limited Node Status
    async def test_05_rate_limited_node_status(self):
        self.health_registry.record_failure("groq", "openai/gpt-oss-120b", "429 Too Many Requests", status_code=429, retry_after=30.0)
        graph = self.server._get_dynamic_workflow_graph()
        groq_reasoning_node = next(n for n in graph["nodes"] if n["id"] == "node_reasoning_0")
        self.assertEqual(groq_reasoning_node["status"], "RATE_LIMITED")

    # 6. Vision Branch Representation
    async def test_06_vision_branch_representation(self):
        graph = self.server._get_dynamic_workflow_graph()
        vision_nodes = [n for n in graph["nodes"] if n["role"] == "vision"]
        self.assertEqual(len(vision_nodes), 3) # Primary + 2 fallbacks
        self.assertTrue(vision_nodes[0]["is_primary"])
        self.assertFalse(vision_nodes[1]["is_primary"])
        self.assertEqual(vision_nodes[1]["fallback_rank"], 1)

    # 7. Tool Execution Event Representation
    async def test_07_tool_execution_broadcast(self):
        ws_url = "ws://127.0.0.1:8770/ws"
        async with websockets.connect(ws_url) as ws:
            await ws.recv() # snapshot
            await self.server.broadcast_event("TOOL_COMPLETED", {"tool": "click_ui_element", "latency_ms": 142})
            raw_msg = await ws.recv()
            msg = json.loads(raw_msg)
            self.assertEqual(msg["event"], "TOOL_COMPLETED")
            self.assertEqual(msg["data"]["latency_ms"], 142)

    # 8. Task Completion Representation
    async def test_08_task_completion_status(self):
        self.state.transition_to(SERAStatus.SPEAKING)
        graph = self.server._get_dynamic_workflow_graph()
        tts_node = next(n for n in graph["nodes"] if n["id"] == "node_tts")
        self.assertEqual(tts_node["status"], "ACTIVE")

    # 9. Task Cancellation Event
    async def test_09_cancellation_broadcast(self):
        ws_url = "ws://127.0.0.1:8770/ws"
        async with websockets.connect(ws_url) as ws:
            await ws.recv()
            await self.server.broadcast_event("TASK_CANCELLED", {"reason": "User interrupted"})
            raw_msg = await ws.recv()
            msg = json.loads(raw_msg)
            self.assertEqual(msg["event"], "TASK_CANCELLED")

    # 10. Role Candidate Update via WebSocket
    async def test_10_update_role_via_websocket(self):
        ws_url = "ws://127.0.0.1:8770/ws"
        async with websockets.connect(ws_url) as ws:
            await ws.recv() # snapshot

            # Reorder vision candidates: Gemini first, then Groq
            new_vision_cands = [
                {"provider": "gemini", "model": "gemini-3-flash-preview"},
                {"provider": "groq", "model": "qwen/qwen3.6-27b"},
            ]
            await ws.send(json.dumps({"action": "UPDATE_ROLE", "role": "vision", "candidates": new_vision_cands}))

            # Result event
            res_raw = await ws.recv()
            res_msg = json.loads(res_raw)
            self.assertEqual(res_msg["event"], "ROLE_UPDATE_RESULT")
            self.assertTrue(res_msg["data"]["success"])

            # Verify router candidate chain was updated
            updated_cands = self.router.get_role_candidates("vision")
            self.assertEqual(updated_cands[0].provider_name, "gemini")
            self.assertEqual(updated_cands[1].provider_name, "groq")

    # 11. Invalid Role Configuration Rejected
    async def test_11_invalid_role_configuration_rejected(self):
        res = self.server._update_role_candidates("non_existent_role", [{"provider": "groq", "model": "test"}])
        self.assertFalse(res["success"])
        self.assertIn("Invalid role", res["error"])

    # 12. Candidate Chain Duplicate Validation
    async def test_12_candidate_duplicate_rejected(self):
        dup_cands = [
            {"provider": "groq", "model": "qwen/qwen3.6-27b"},
            {"provider": "groq", "model": "qwen/qwen3.6-27b"},
        ]
        res = self.server._update_role_candidates("vision", dup_cands)
        self.assertFalse(res["success"])
        self.assertIn("Duplicate candidate", res["error"])

    # 13. Candidate Capability Requirement Validation
    async def test_13_candidate_capability_validated(self):
        # Mistral does not have vision in mock
        incompatible_cands = [
            {"provider": "mistral", "model": "mistral-small-latest"},
        ]
        res = self.server._update_role_candidates("vision", incompatible_cands)
        self.assertFalse(res["success"])
        self.assertIn("does not support vision", res["error"])

    # 14. Safety Guard during Active Execution
    async def test_14_safety_guard_blocks_updates_during_execution(self):
        self.state.transition_to(SERAStatus.EXECUTING)
        res = self.server._update_role_candidates("reasoning", [
            {"provider": "mistral", "model": "mistral-large-latest"}
        ])
        self.assertFalse(res["success"])
        self.assertIn("Safety guard", res["error"])

    # 15. WebSocket Disconnect / Reconnect Resilience
    async def test_15_websocket_reconnect_resilience(self):
        ws_url = "ws://127.0.0.1:8770/ws"
        async with websockets.connect(ws_url) as ws1:
            await ws1.recv()
            self.assertEqual(len(self.server.clients), 1)

        # Disconnected (allow event loop cycle for disconnect cleanup)
        await asyncio.sleep(0.05)
        self.assertEqual(len(self.server.clients), 0)

        # Reconnect
        async with websockets.connect(ws_url) as ws2:
            raw = await ws2.recv()
            msg = json.loads(raw)
            self.assertEqual(msg["event"], "SNAPSHOT")
            self.assertEqual(len(self.server.clients), 1)


if __name__ == "__main__":
    unittest.main()
