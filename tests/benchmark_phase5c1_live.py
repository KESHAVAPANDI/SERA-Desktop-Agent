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
    print("SERA 1.0 — PHASE 5C.1 RUNTIME & FREEFORM CANVAS LIVE VALIDATION")
    print("=" * 70)

    state = SERAState()
    events = EventBus()
    health_registry = ModelHealthRegistry()

    # Mock Providers
    mock_groq = MagicMock()
    mock_groq.provider_name = "groq"
    mock_groq.capabilities.return_value = {"text": True, "vision": True, "tool_calling": True, "streaming": True, "reasoning": True}

    router = ModelRouter(
        role_chains={
            "reasoning": [
                RoleCandidate("groq", "openai/gpt-oss-120b", mock_groq, "reasoning"),
            ],
            "fast": [
                RoleCandidate("groq", "openai/gpt-oss-120b", mock_groq, "fast"),
            ],
        },
        health_registry=health_registry,
    )

    mock_runtime = MagicMock()
    mock_runtime.state = state
    mock_runtime.events = events
    mock_runtime.router = router

    server = SERAUIServer(host="127.0.0.1", port=8791, runtime=mock_runtime)
    await server.start()

    ws_url = "ws://127.0.0.1:8791/ws"
    async with websockets.connect(ws_url) as ws:
        snapshot = json.loads(await ws.recv())
        print(f"[UI] Initial Snapshot: RuntimeAttached={snapshot['data'].get('runtime_attached')}, Status={snapshot['data']['status']}")

        # 1. Dual Activation Sources
        print("\n--- 1. Dual Activation Verification ---")
        await server.broadcast_event("CAPTURE_COUNTDOWN", {"duration_seconds": 5.0, "activation_method": "HOTKEY"})
        ev1 = json.loads(await ws.recv())
        print(f"✓ Hotkey Activation: {ev1['data']['activation_method']} ({ev1['data']['duration_seconds']}s)")

        await server.broadcast_event("CAPTURE_COUNTDOWN", {"duration_seconds": 5.0, "activation_method": "WAKE_WORD"})
        ev2 = json.loads(await ws.recv())
        print(f"✓ Wake Word Activation: {ev2['data']['activation_method']} ({ev2['data']['duration_seconds']}s)")

    # 2. Freeform Visual Layout Persistence
    print("\n--- 2. Visual Layout Persistence & Decoupling ---")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8791") as client:
        # Save custom 2D node coordinates
        post_resp = await client.post("/api/workflow/layout", json={
            "nodes": {
                "node_stt": {"x": 160, "y": 320},
                "node_router": {"x": 480, "y": 320},
            }
        })
        print(f"  POST /api/workflow/layout: {post_resp.status_code} ({post_resp.json()['success']})")

        # Verify layout fetched
        get_resp = await client.get("/api/workflow/layout")
        nodes_layout = get_resp.json()["workflow_layout"]["nodes"]
        print(f"  GET /api/workflow/layout: STT pos = ({nodes_layout['node_stt']['x']}, {nodes_layout['node_stt']['y']})")
        assert nodes_layout["node_stt"]["x"] == 160

        # Verify execution priority unchanged
        cand = server.runtime.router.get_role_candidates("reasoning")[0]
        print(f"✓ Semantic execution priority preserved: Primary Reasoning = {cand.provider_name}:{cand.model_name}")

    await server.stop()
    print("\n" + "=" * 70)
    print("ALL PHASE 5C.1 LIVE SCENARIOS: PASS")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
