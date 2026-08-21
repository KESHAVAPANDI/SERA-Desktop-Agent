import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.core.agent import SERAAgent
from app.core.events import EventBus
from app.core.router import ModelRouter, RoleCandidate
from app.core.state import SERAState, SERAStatus
from app.models.llm.base import LLMResponse, ToolCall
from app.models.llm.health import ModelHealthRegistry
from app.speech.wakeword import OpenWakeWordDetector
from app.tools.registry import ToolRegistry
from app.ui.server import SERAUIServer


class TestPhase5C1RuntimeRework(unittest.IsolatedAsyncioTestCase):
    """Unit tests for Phase 5C.1 Temporal Aura Rework: Runtime lifecycle, turn termination,
    tool deduplication, freeform canvas, and truthful UI presentation."""

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

        self.tools = ToolRegistry()
        # Register a mock open_application tool
        mock_open_app = MagicMock()
        mock_open_app.name = "open_application"
        mock_open_app.requires_confirmation = False
        mock_open_app.schema.return_value = {"name": "open_application", "description": "Opens an app", "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}}}
        mock_open_app.execute = AsyncMock(return_value={"success": True, "message": "Chrome launched"})
        self.tools.register(mock_open_app)

        self.agent = SERAAgent(
            router=self.router,
            tools=self.tools,
            state=self.state,
            event_bus=self.events,
            max_turn_timeout_seconds=5.0,
        )

    # 1. WakeWordDetector Lifecycle & Microphone Yielding
    def test_01_wakeword_mic_yielding_lifecycle(self):
        detector = OpenWakeWordDetector(phrase="SERA")
        callback_called = False

        def on_wake():
            nonlocal callback_called
            callback_called = True

        detector.start(on_wake)
        self.assertTrue(detector.is_running())

        # Trigger detection
        res = detector.trigger_manually()
        self.assertTrue(res)
        self.assertTrue(callback_called)

        # Pause detector (yield mic)
        detector.pause()
        self.assertFalse(detector.is_running())

        # Manual trigger ignored while paused
        callback_called = False
        res2 = detector.trigger_manually()
        self.assertFalse(res2)
        self.assertFalse(callback_called)

        # Resume detector
        detector.resume()
        self.assertTrue(detector.is_running())
        detector.stop()

    # 2. Conversational Fast Path ("hi" completes in 1 step with no tools)
    async def test_02_conversational_fast_path_termination(self):
        self.mock_mistral.generate = AsyncMock(return_value=LLMResponse(
            text="Hello! How can I help you today?",
            model="mistral-small-latest",
            provider="mistral",
            tool_calls=[],
        ))

        res = await self.agent.run("hi")
        self.assertIn("Hello", res)
        self.assertEqual(self.state.status, SERAStatus.THINKING)
        # Verify no tools were passed
        call_args = self.mock_mistral.generate.call_args[1]
        self.assertEqual(call_args.get("tools"), [])

    # 3. Deterministic Single-Step Task Termination ("Open Chrome" stops after success)
    async def test_03_deterministic_single_step_termination(self):
        self.mock_groq.generate = AsyncMock(return_value=LLMResponse(
            text=None,
            model="openai/gpt-oss-120b",
            provider="groq",
            tool_calls=[ToolCall(id="call_1", name="open_application", arguments={"app_name": "chrome"})],
        ))

        res = await self.agent.run("Open Chrome")
        self.assertEqual(res, "Opened Chrome.")
        # Verifies generate was only called once and did not loop
        self.assertEqual(self.mock_groq.generate.call_count, 1)

    # 4. Duplicate Tool Execution Protection in Multi-Round Loop
    async def test_04_duplicate_tool_call_blocked(self):
        # Round 1 returns open_application, and if it continues, round 2 returns the exact same tool call
        self.mock_groq.generate = AsyncMock(side_effect=[
            LLMResponse(
                text=None,
                model="openai/gpt-oss-120b",
                provider="groq",
                tool_calls=[ToolCall(id="call_1", name="open_application", arguments={"app_name": "chrome"})],
            ),
            LLMResponse(
                text=None,
                model="openai/gpt-oss-120b",
                provider="groq",
                tool_calls=[ToolCall(id="call_2", name="open_application", arguments={"app_name": "chrome"})],
            ),
        ])

        res = await self.agent.run("Open Chrome")
        self.assertEqual(res, "Opened Chrome.")
        # Verifies tool was executed only once
        self.assertEqual(self.tools.get("open_application").execute.call_count, 1)

    # 5. Task Safety Timeout & BROKEN State
    async def test_05_task_timeout_transitions_to_broken(self):
        async def slow_generate(*args, **kwargs):
            await asyncio.sleep(2.0)
            return LLMResponse(text="Done", model="test", provider="test")

        self.mock_groq.generate = slow_generate
        self.agent.max_turn_timeout_seconds = 0.2

        res = await self.agent.run("Complex task")
        self.assertEqual(self.state.status, SERAStatus.BROKEN)
        self.assertIn("timeout", res.lower())

    # 6. Truthful Provider Registry
    async def test_06_truthful_all_providers_summary(self):
        server = SERAUIServer(host="127.0.0.1", port=8794, runtime=None)
        await server.start()
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8794") as client:
                resp = await client.get("/api/providers")
                self.assertEqual(resp.status_code, 200)
                provs = resp.json()
                prov_names = {p["provider_name"] for p in provs}
                # Must contain all 8 registered providers
                for req in ["groq", "gemini", "mistral", "nvidia", "fish_audio", "openrouter", "cerebras", "zai"]:
                    self.assertIn(req, prov_names)

                # NVIDIA must be marked degraded/unavailable
                nvidia_prov = next(p for p in provs if p["provider_name"] == "nvidia")
                self.assertEqual(nvidia_prov["status"], "DEGRADED")
        finally:
            await server.stop()


if __name__ == "__main__":
    unittest.main()
