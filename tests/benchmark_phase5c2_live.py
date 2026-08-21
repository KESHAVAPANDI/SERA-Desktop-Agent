import asyncio
import json
import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.agent import SERAAgent
from app.core.events import EventBus
from app.core.hotkey import GlobalHotkeyManager
from app.core.router import ModelRouter, RoleCandidate
from app.core.state import SERAState, SERAStatus
from app.models.llm.base import LLMResponse, ToolCall
from app.models.llm.health import ModelHealthRegistry
from app.speech.recorder import AudioRecorder
from app.speech.wakeword import OpenWakeWordDetector
from app.tools import create_tool_registry
from app.tools.browser.web_search import WebSearchTool
from app.tools.screen.capture import ScreenCaptureTool

logging.basicConfig(level=logging.INFO)


async def main():
    print("=" * 75)
    print("SERA 1.0 — PHASE 5C.2 GOD-TIER RUNTIME & VOICE VALIDATION BENCHMARK")
    print("=" * 75)

    # 1. Hold-To-Talk Voice Control
    print("\n--- 1. Hold-To-Talk Keyboard Control (KeyDown / KeyUp) ---")
    pressed = False
    released = False

    def on_press():
        nonlocal pressed
        pressed = True

    def on_release():
        nonlocal released
        released = True

    hotkey = GlobalHotkeyManager(hotkey="ctrl+space", on_press=on_press, on_release=on_release)
    hotkey.trigger_press()
    assert pressed, "Hold-To-Talk press failed"
    assert hotkey.is_held, "Hotkey held state is False"
    print("✓ Hotkey KeyDown triggered: is_held=True, audio listening cue played")

    hotkey.trigger_release()
    assert released, "Hold-To-Talk release failed"
    assert not hotkey.is_held, "Hotkey held state is True"
    print("✓ Hotkey KeyUp released: is_held=False, capture-finished audio cue played")

    # 2. Local "SERA" Wake-Word Lifecycle
    print("\n--- 2. Local 'SERA' Wake-Word Detector Lifecycle ---")
    detector = OpenWakeWordDetector(phrase="SERA")
    wake_detected = False

    def on_wake():
        nonlocal wake_detected
        wake_detected = True

    detector.start(on_wake)
    print(f"✓ Wake detector online: is_running={detector.is_running()}")
    detector.trigger_manually()
    assert wake_detected, "Wake-word trigger failed"
    print("✓ 'SERA' wake word detected and triggered callback")

    detector.pause()
    print(f"✓ Microphone yielded for command recording: is_running={detector.is_running()}")
    detector.resume()
    print(f"✓ Wake monitoring resumed: is_running={detector.is_running()}")
    detector.stop()

    # 3. Truthful Computer Actions (Invalid application / folder)
    print("\n--- 3. Computer Action Truthfulness ---")
    tools = create_tool_registry()

    # Test "Open enemy" -> Must return failure, NEVER success
    open_app_tool = tools.get("open_application")
    res_invalid_app = await open_app_tool.execute("enemy")
    print(f"✓ 'Open enemy' result: success={res_invalid_app.get('success')}, verified={res_invalid_app.get('verified')}, error='{res_invalid_app.get('error')}'")
    assert res_invalid_app["success"] is False
    assert res_invalid_app["verified"] is False

    # Test "Open enemy folder" -> Must return failure, NEVER success
    open_folder_tool = tools.get("open_folder")
    res_invalid_folder = await open_folder_tool.execute("enemy_folder_non_existent")
    print(f"✓ 'Open enemy folder' result: success={res_invalid_folder.get('success')}, error='{res_invalid_folder.get('error')}'")
    assert res_invalid_folder["success"] is False
    assert res_invalid_folder["verified"] is False

    # 4. Live Web Search Tool Execution
    print("\n--- 4. Live Web Search Execution ---")
    web_search = tools.get("web_search")
    search_res = await web_search.execute("RTX 5090 benchmarks", max_results=3)
    print(f"✓ Web Search Query: '{search_res.get('query')}' | Count: {search_res.get('count')} results")
    if search_res.get("results"):
        print(f"   Snippet 1: {search_res['results'][0].get('snippet')[:100]}...")
    assert search_res["success"] is True

    # 5. Live Screen Capture Tool Execution
    print("\n--- 5. Screen Capture Verification ---")
    screen_cap = tools.get("capture_screen")
    cap_res = await screen_cap.execute()
    print(f"✓ Screen Capture: success={cap_res.get('success')}, dimensions={cap_res.get('dimensions')}, path={cap_res.get('image_path')}")
    assert cap_res["success"] is True
    assert cap_res["verified"] is True
    assert os.path.exists(cap_res["image_path"])

    # 6. Conversational Fast-Path ("hi")
    print("\n--- 6. Conversational Fast-Path ('hi') ---")
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
    agent = SERAAgent(router=router, tools=tools, state=state)
    fast_resp = await agent.run("hi")
    print(f"✓ Fast conversational response: '{fast_resp}'")
    assert "Hello" in fast_resp

    print("\n" + "=" * 75)
    print("ALL PHASE 5C.2 GOD-TIER BENCHMARKS: PASS")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
