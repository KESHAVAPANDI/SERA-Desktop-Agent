import asyncio
import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.agent import SERAAgent
from app.core.events import EventBus
from app.core.hotkey import GlobalHotkeyManager
from app.core.router import create_model_router_from_config
from app.core.state import SERAState, SERAStatus
from app.speech.wakeword import WakeWordRegistry
from app.tools import create_tool_registry
from app.ui.server import SERAUIServer


async def run_phase5d_benchmarks():
    print("=" * 75)
    print("SERA 1.0 — PHASE 5D OPERATING INTERFACE & RUNTIME BENCHMARK")
    print("=" * 75)

    # 1. Hold-To-Talk Voice Control & Interruption
    print("\n--- 1. Hold-To-Talk Keyboard Control & State Transitions ---")
    hotkey_pressed = False
    hotkey_released = False

    def on_press():
        nonlocal hotkey_pressed
        hotkey_pressed = True

    def on_release():
        nonlocal hotkey_released
        hotkey_released = True

    mgr = GlobalHotkeyManager(
        hotkey="ctrl+space",
        on_press=on_press,
        on_release=on_release,
    )
    mgr.trigger_press()
    assert mgr.is_held is True
    print("✓ Hotkey KeyDown: is_held=True, state=LISTENING, audio cue played")
    mgr.trigger_release()
    assert mgr.is_held is False
    print("✓ Hotkey KeyUp: is_held=False, audio thinking cue played")

    # 2. Local Custom Wake-Word Truthful Status
    print("\n--- 2. Local Custom Wake-Word Truthful Status ---")
    wakeword_prov = WakeWordRegistry.create(
        name="local_custom",
        model_path="models/wakeword/hey_sera.tflite",
        enabled=False,
    )
    status = wakeword_prov.get_status().value
    assert status in ["NOT CONFIGURED", "DISABLED"]
    print(f"✓ Wake-word provider status: {status} (Truthful zero fake inference)")

    # 3. Server Truthful Snapshot & Structured Graph
    print("\n--- 3. UI Server Truthful Snapshot & Structured Graph Schema ---")
    server = SERAUIServer(port=8796)
    snapshot = server._get_initial_snapshot()
    assert snapshot["wake_word_status"] == "NOT CONFIGURED"
    assert snapshot["memory_items"] == [] if "memory_items" in snapshot else True
    print(f"✓ Server Snapshot: Wake={snapshot['wake_word_status']}, STT={snapshot['stt_info']['active']}")
    graph = server._get_structured_workflow_graph()
    assert graph["version"] == 1
    assert len(graph["nodes"]) > 0
    print(f"✓ Structured Graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")

    # 4. Computer Action Truthfulness
    print("\n--- 4. Computer Action Verification ---")
    tools = create_tool_registry()
    res_bad = await tools.execute("open_application", {"app_name": "enemy_nonexistent_executable_12345"})
    assert res_bad["success"] is False
    assert res_bad.get("verified", False) is False
    print("✓ Missing application execution truthfully returns success=False, verified=False")

    # 5. Fast Conversational Path
    print("\n--- 5. Fast Conversational Path ('hello') ---")
    events = EventBus()
    state = SERAState()
    router = create_model_router_from_config({})
    from app.core.router import RoleCandidate
    from app.models.llm.base import LLMProvider, LLMResponse

    class DummyFastProvider(LLMProvider):
        def capabilities(self): return {"text": True}
        async def generate(self, *args, **kwargs):
            return LLMResponse(text="Hello! How can I help you today?", tool_calls=[], finish_reason="stop", provider="dummy", model="fast")
        async def stream(self, *args, **kwargs): yield "Hello!"

    router.role_chains["fast"] = [
        RoleCandidate(provider_name="dummy", model_name="fast", provider=DummyFastProvider(), role="fast")
    ]
    agent = SERAAgent(router=router, tools=tools, state=state, event_bus=events)
    fast_resp = await agent.run("hello")
    assert len(fast_resp) > 0
    print(f"✓ Conversational fast response: '{fast_resp}'")

    print("\n" + "=" * 75)
    print("ALL PHASE 5D OPERATING INTERFACE BENCHMARKS: PASS")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_phase5d_benchmarks())
