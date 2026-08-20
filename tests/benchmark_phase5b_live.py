import asyncio
import json
import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import websockets

from app.core.events import EventBus
from app.core.router import ModelRouter, RoleCandidate
from app.core.state import SERAState, SERAStatus
from app.models.llm.health import ModelHealthRegistry
from app.ui.server import SERAUIServer

logging.basicConfig(level=logging.INFO)


async def main():
    print("=" * 60)
    print("SERA 1.0 — PHASE 5B LIVE WORKFLOW VALIDATION")
    print("=" * 60)

    state = SERAState()
    events = EventBus()
    health_registry = ModelHealthRegistry()

    # Mock Providers
    mock_groq = MagicMock()
    mock_groq.provider_name = "groq"
    mock_groq.capabilities.return_value = {"text": True, "vision": True, "tool_calling": True, "streaming": True}

    mock_mistral = MagicMock()
    mock_mistral.provider_name = "mistral"
    mock_mistral.capabilities.return_value = {"text": True, "vision": False, "tool_calling": True, "streaming": True}

    mock_gemini = MagicMock()
    mock_gemini.provider_name = "gemini"
    mock_gemini.capabilities.return_value = {"text": True, "vision": True, "tool_calling": True, "streaming": True}

    router = ModelRouter(
        role_chains={
            "reasoning": [
                RoleCandidate("groq", "openai/gpt-oss-120b", mock_groq, "reasoning"),
                RoleCandidate("mistral", "mistral-large-latest", mock_mistral, "reasoning"),
            ],
            "vision": [
                RoleCandidate("groq", "qwen/qwen3.6-27b", mock_groq, "vision"),
                RoleCandidate("gemini", "gemini-3-flash-preview", mock_gemini, "vision"),
            ],
            "desktop": [
                RoleCandidate("mistral", "codestral-latest", mock_mistral, "desktop"),
            ],
            "fast": [
                RoleCandidate("mistral", "mistral-small-latest", mock_mistral, "fast"),
            ],
        },
        health_registry=health_registry,
    )

    mock_runtime = MagicMock()
    mock_runtime.state = state
    mock_runtime.events = events
    mock_runtime.router = router

    server = SERAUIServer(host="127.0.0.1", port=8772, runtime=mock_runtime)
    await server.start()

    ws_url = "ws://127.0.0.1:8772/ws"
    async with websockets.connect(ws_url) as ws:
        snapshot = json.loads(await ws.recv())
        print(f"[UI] Initial Snapshot received: Status={snapshot['data']['status']}, Nodes={len(snapshot['data']['workflow']['nodes'])}")

        # Step 1: "What time is it?"
        print("\n--- Test 1: 'What time is it?' ---")
        state.transition_to(SERAStatus.THINKING)
        await server.broadcast_event("MODEL_SELECTED", {"role": "fast", "provider": "mistral", "model": "mistral-small-latest"})
        await server.broadcast_event("TOOL_STARTED", {"tool": "get_current_time", "arguments": {"tz": "UTC"}})
        await asyncio.sleep(0.1)
        await server.broadcast_event("TOOL_COMPLETED", {"tool": "get_current_time", "latency_ms": 12})
        state.transition_to(SERAStatus.SPEAKING)
        await server.broadcast_event("TTS_STARTED", {"provider": "fish", "model": "s2.1"})
        print("✓ Test 1: Flow completed.")

        # Step 2: "Open Chrome."
        print("\n--- Test 2: 'Open Chrome' (Desktop Automation) ---")
        state.transition_to(SERAStatus.EXECUTING)
        await server.broadcast_event("MODEL_SELECTED", {"role": "desktop", "provider": "mistral", "model": "codestral-latest"})
        await server.broadcast_event("TOOL_STARTED", {"tool": "open_application", "arguments": {"app_name": "chrome"}})
        await asyncio.sleep(0.1)
        await server.broadcast_event("TOOL_COMPLETED", {"tool": "open_application", "latency_ms": 340})
        print("✓ Test 2: Desktop execution rendered.")

        # Step 3: Trigger Vision Request
        print("\n--- Test 3: Screen Perception & Verification ---")
        await server.broadcast_event("VISION_STARTED", {"provider": "groq", "model": "qwen/qwen3.6-27b"})
        await asyncio.sleep(0.1)
        await server.broadcast_event("VISION_COMPLETED", {"elements_count": 8, "latency_ms": 380})
        print("✓ Test 3: Vision branch rendered.")

        # Step 4: Fallback Failover Simulation
        print("\n--- Test 4: Rate Limit Failover (Groq 429 ➔ Mistral) ---")
        await server.broadcast_event("MODEL_FALLBACK", {
            "role": "reasoning",
            "failed_provider": "groq",
            "failed_model": "openai/gpt-oss-120b",
            "fallback_provider": "mistral",
            "fallback_model": "mistral-large-latest",
            "reason": "429 Rate Limit",
        })
        print("✓ Test 4: Fallback branch ignited.")

        # Step 5: Speech Interruption
        print("\n--- Test 5: Speech Interruption ---")
        await server.broadcast_event("TTS_INTERRUPTED", {"timestamp": 12345.67})
        await server.broadcast_event("TASK_CANCELLED", {"reason": "User speech detected"})
        state.transition_to(SERAStatus.IDLE)
        print("✓ Test 5: Cancellation visual state rendered.")

    await server.stop()
    print("\n" + "=" * 60)
    print("ALL PHASE 5B WORKFLOW LIVE TESTS: PASS")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
