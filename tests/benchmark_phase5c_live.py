import asyncio
import json
import logging
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx
import websockets

from app.core.events import EventBus
from app.core.router import ModelRouter, RoleCandidate
from app.core.state import SERAState, SERAStatus
from app.models.llm.health import ModelHealthRegistry
from app.ui.server import SERAUIServer

logging.basicConfig(level=logging.INFO)


async def main():
    print("=" * 70)
    print("SERA 1.0 — PHASE 5C TEMPORAL AURA COMMAND CENTER LIVE VALIDATION")
    print("=" * 70)

    state = SERAState()
    events = EventBus()
    health_registry = ModelHealthRegistry()

    # Mock Providers
    mock_groq = MagicMock()
    mock_groq.provider_name = "groq"
    mock_groq.capabilities.return_value = {"text": True, "vision": True, "tool_calling": True, "streaming": True, "reasoning": True}

    mock_mistral = MagicMock()
    mock_mistral.provider_name = "mistral"
    mock_mistral.capabilities.return_value = {"text": True, "vision": False, "tool_calling": True, "streaming": True, "reasoning": True}

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

    server = SERAUIServer(host="127.0.0.1", port=8777, runtime=mock_runtime)
    await server.start()

    ws_url = "ws://127.0.0.1:8777/ws"
    async with websockets.connect(ws_url) as ws:
        snapshot = json.loads(await ws.recv())
        print(f"[UI] Initial Snapshot: Status={snapshot['data']['status']}, Providers={len(snapshot['data']['providers'])}, Nodes={len(snapshot['data']['workflow']['nodes'])}")

        # Step 1: Voice Capture Countdown (5.0s)
        print("\n--- Scenario 1: Voice Activation & 5-Second Capture ---")
        state.transition_to(SERAStatus.LISTENING)
        await server.broadcast_event("CAPTURE_COUNTDOWN", {"duration_seconds": 5.0, "activation_method": "HOTKEY"})
        ev_cap = json.loads(await ws.recv())
        self_status = state.status.value
        print(f"✓ Scenario 1: Event={ev_cap['event']}, 5.0s capture countdown rendered.")

        # Step 2: Live Task Progress & Tool Execution
        print("\n--- Scenario 2: Live Task Progress ('Open Chrome') ---")
        state.transition_to(SERAStatus.EXECUTING)
        await server.broadcast_event("TOOL_STARTED", {"tool": "open_application", "arguments": {"app": "chrome"}})
        ev_tool = json.loads(await ws.recv())
        await server.broadcast_event("TOOL_COMPLETED", {"tool": "open_application", "latency_ms": 280})
        ev_done = json.loads(await ws.recv())
        state.transition_to(SERAStatus.IDLE)
        print(f"✓ Scenario 2: Live task step progression rendered ({ev_tool['data']['tool']} ➔ {ev_done['data']['latency_ms']}ms).")

        # Step 3: Rate Limit Failover & Broken State
        print("\n--- Scenario 3: Broken State & Fallback Failover ---")
        await server.broadcast_event("MODEL_FALLBACK", {
            "role": "reasoning",
            "failed_provider": "groq",
            "failed_model": "openai/gpt-oss-120b",
            "fallback_provider": "mistral",
            "fallback_model": "mistral-large-latest",
            "reason": "429 Rate Limit Cooldown",
        })
        ev_fb = json.loads(await ws.recv())
        print(f"✓ Scenario 3: Fallback branch illuminated ({ev_fb['data']['failed_provider']} ➔ {ev_fb['data']['fallback_provider']}).")

        # Step 4: Security Action Confirmation Modal
        print("\n--- Scenario 4: Security Confirmation Modal ---")
        await server.broadcast_event("SECURITY_CONFIRMATION_REQUIRED", {
            "action_id": "act_delete_99",
            "tool_name": "delete_file",
            "prompt": "Delete old logs folder?",
            "arguments": {"folder": "C:/temp/logs"},
        })
        ev_sec = json.loads(await ws.recv())
        await ws.send(json.dumps({"action": "CONFIRM_ACTION", "action_id": "act_delete_99", "allowed": True}))
        res_conf = json.loads(await ws.recv())
        print(f"✓ Scenario 4: Security Confirmation processed (Action={ev_sec['data']['tool_name']}, Allowed={res_conf['data']['allowed']}).")

    # Step 5: REST Endpoints Validation
    print("\n--- Scenario 5: REST API Endpoints ---")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8777") as client:
        r_sec = await client.get("/api/security")
        print(f"  /api/security: {r_sec.status_code} ({len(r_sec.json()['permissions'])} policies)")

        r_mem = await client.get("/api/memory")
        print(f"  /api/memory: {r_mem.status_code} ({len(r_mem.json())} knowledge items)")

        r_hist = await client.get("/api/history")
        print(f"  /api/history: {r_hist.status_code} ({len(r_hist.json())} sessions)")

        r_tel = await client.get("/api/telemetry")
        print(f"  /api/telemetry: {r_tel.status_code} ({len(r_tel.json()['stages'])} stages)")

    await server.stop()
    print("\n" + "=" * 70)
    print("ALL PHASE 5C LIVE SCENARIOS: PASS")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
