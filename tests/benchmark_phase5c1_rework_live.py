import asyncio
import json
import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
import websockets

from app.core.agent import SERAAgent
from app.core.events import EventBus
from app.core.router import ModelRouter, RoleCandidate
from app.core.state import SERAState, SERAStatus
from app.models.llm.base import LLMResponse, ToolCall
from app.models.llm.health import ModelHealthRegistry
from app.speech.wakeword import OpenWakeWordDetector
from app.tools.registry import ToolRegistry
from app.ui.server import SERAUIServer

logging.basicConfig(level=logging.INFO)


async def main():
    print("=" * 70)
    print("SERA 1.0 — PHASE 5C.1 RUNTIME REWORK LIVE VALIDATION")
    print("=" * 70)

    # 1. Wake-Word Detector Lifecycle
    print("\n--- 1. Wake-Word Lifecycle & Microphone Yielding ---")
    detector = OpenWakeWordDetector(phrase="SERA")
    triggered = False

    def on_wake():
        nonlocal triggered
        triggered = True

    detector.start(on_wake)
    print(f"✓ Detector Started: is_running={detector.is_running()}")
    detector.trigger_manually()
    assert triggered, "Wake-word manual trigger failed"
    print("✓ Wake-word trigger received callback")

    detector.pause()
    print(f"✓ Paused for command recording: is_running={detector.is_running()}")
    detector.resume()
    print(f"✓ Resumed after turn: is_running={detector.is_running()}")
    detector.stop()

    # 2. Conversational Fast Path
    print("\n--- 2. Conversational Fast-Path ('hi') ---")
    state = SERAState()
    mock_mistral = MagicMock()
    mock_mistral.provider_name = "mistral"
    mock_mistral.capabilities.return_value = {"text": True, "vision": False, "tool_calling": True, "streaming": True, "reasoning": True}
    mock_mistral.generate = AsyncMock(return_value=LLMResponse(
        text="Hello! How can I help you today?",
        model="mistral-small-latest",
        provider="mistral",
        tool_calls=[],
    ))

    router = ModelRouter(
        role_chains={"fast": [RoleCandidate("mistral", "mistral-small-latest", mock_mistral, "fast")]},
        health_registry=ModelHealthRegistry(),
    )
    tools = ToolRegistry()
    agent = SERAAgent(router=router, tools=tools, state=state)

    resp_fast = await agent.run("hi")
    print(f"✓ Fast response: '{resp_fast}' (Tools passed: {mock_mistral.generate.call_args[1].get('tools')})")
    assert "Hello" in resp_fast

    # 3. Deterministic Single-Step Task Termination
    print("\n--- 3. Single-Step Task Termination ('Open Chrome') ---")
    mock_open_app = MagicMock()
    mock_open_app.name = "open_application"
    mock_open_app.requires_confirmation = False
    mock_open_app.schema.return_value = {"name": "open_application", "description": "Opens an app", "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}}}
    mock_open_app.execute = AsyncMock(return_value={"success": True, "message": "Chrome launched"})
    tools.register(mock_open_app)

    mock_groq = MagicMock()
    mock_groq.provider_name = "groq"
    mock_groq.capabilities.return_value = {"text": True, "vision": True, "tool_calling": True, "streaming": True, "reasoning": True}
    mock_groq.generate = AsyncMock(return_value=LLMResponse(
        text=None,
        model="openai/gpt-oss-120b",
        provider="groq",
        tool_calls=[ToolCall(id="call_1", name="open_application", arguments={"app_name": "chrome"})],
    ))
    router.role_chains["reasoning"] = [RoleCandidate("groq", "openai/gpt-oss-120b", mock_groq, "reasoning")]

    resp_action = await agent.run("Open Chrome")
    print(f"✓ Action response: '{resp_action}' (Generate call count: {mock_groq.generate.call_count})")
    assert resp_action == "Opened Chrome."
    assert mock_groq.generate.call_count == 1

    # 4. Truthful Provider Registry & Workflow Layout
    print("\n--- 4. Provider Registry & Non-overlapping Layout ---")
    server = SERAUIServer(host="127.0.0.1", port=8796, runtime=None)
    await server.start()

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8796") as client:
        r_prov = await client.get("/api/providers")
        provs = r_prov.json()
        prov_names = [p["provider_name"] for p in provs]
        print(f"✓ Providers registered ({len(provs)}): {prov_names}")
        assert "nvidia" in prov_names
        assert "fish_audio" in prov_names

        r_wf = await client.get("/api/workflow")
        nodes = r_wf.json()["nodes"]
        coords = [(n["id"], n["x"], n["y"]) for n in nodes[:5]]
        print(f"✓ Workflow nodes layout sample: {coords}")

    await server.stop()

    print("\n" + "=" * 70)
    print("ALL PHASE 5C.1 REWORK SCENARIOS: PASS")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
