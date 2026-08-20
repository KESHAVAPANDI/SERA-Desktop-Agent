import asyncio
import time
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.router import ModelRouter
from app.core.runtime import SERARuntime
from app.core.telemetry import LatencyMetrics
from app.models.llm.base import LLMResponse, LLMProvider
from app.speech.audio_manager import AudioManager
from app.tools import create_tool_registry
from app.tools.desktop.executor import DesktopActionExecutor
from app.tools.desktop.matcher import SemanticTargetMatcher
from app.tools.desktop.models import (
    NativeUIControl,
    NativeWindowContext,
    SemanticActionRequest,
    SemanticActionResult,
)
from app.tools.desktop.perception_router import DesktopPerceptionRouter
from app.tools.desktop.ui_inspector import WindowsUIInspector
from app.vision.analyzer import ScreenPerceptionEngine
from app.vision.models import ScreenContext


class TestPhase3B(unittest.IsolatedAsyncioTestCase):

    def test_native_control_model(self):
        """Test NativeUIControl model creation and attributes."""
        ctrl = NativeUIControl(
            id="ctrl_1",
            name="Run",
            type="button",
            control_type_name="ButtonControl",
            class_name="Button",
            automation_id="btnRun",
            enabled=True,
            visible=True,
            focused=False,
            bounds={"x": 100, "y": 200, "width": 80, "height": 30},
        )
        self.assertEqual(ctrl.name, "Run")
        self.assertEqual(ctrl.type, "button")
        self.assertEqual(ctrl.bounds["width"], 80)

    def test_semantic_target_matcher(self):
        """Test fuzzy and exact matching of semantic targets to native controls."""
        matcher = SemanticTargetMatcher()
        controls = [
            NativeUIControl(
                id="c1",
                name="Start Debugging",
                type="button",
                control_type_name="ButtonControl",
                automation_id="btnDebug",
            ),
            NativeUIControl(
                id="c2",
                name="File Name",
                type="edit",
                control_type_name="EditControl",
                automation_id="txtFileName",
            ),
        ]

        # Exact match
        matched, score, reason = matcher.match({"name": "Start Debugging", "type": "button"}, controls)
        self.assertIsNotNone(matched)
        self.assertEqual(matched.id, "c1")
        self.assertGreaterEqual(score, 0.70)

        # Automation ID match
        matched_id, score_id, _ = matcher.match({"automation_id": "txtFileName"}, controls)
        self.assertIsNotNone(matched_id)
        self.assertEqual(matched_id.id, "c2")

        # Non-matching target
        matched_none, score_none, _ = matcher.match({"name": "CompletelyMissingButton"}, controls)
        self.assertIsNone(matched_none)
        self.assertLess(score_none, 0.40)

    async def test_action_executor_sensitive_field_protection(self):
        """Test that sensitive fields (password, card) are blocked from automated text entry."""
        executor = DesktopActionExecutor()
        req = SemanticActionRequest(
            action="set_input_text",
            target={"name": "User Password", "type": "password"},
            value="secret123",
        )
        res = await executor.execute_action(req)
        self.assertFalse(res.success)
        self.assertIn("sensitive", res.message.lower())

    async def test_action_executor_observe_act_verify(self):
        """Test Observe -> Act -> Verify lifecycle for safe semantic action."""
        mock_inspector = MagicMock(spec=WindowsUIInspector)
        mock_inspector.get_active_window_context.return_value = NativeWindowContext(
            application="Notepad",
            process_id=1234,
            window_title="Untitled - Notepad",
            controls=[
                NativeUIControl(id="1", name="File", type="menu"),
                NativeUIControl(id="2", name="Edit", type="menu"),
            ],
            timestamp=time.time(),
        )

        executor = DesktopActionExecutor(inspector=mock_inspector)
        req = SemanticActionRequest(
            action="click_element",
            target={"name": "File", "type": "menu"},
        )
        res = await executor.execute_action(req)
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertIn(res.verification_method, ("post_observation", "control_state_change"))

    async def test_desktop_perception_router_native_bypass(self):
        """Test that native UI info answers app/control query with ZERO cloud vision calls."""
        mock_inspector = MagicMock(spec=WindowsUIInspector)
        mock_inspector.get_active_window_context.return_value = NativeWindowContext(
            application="Visual Studio Code",
            window_title="main.py - Sera",
            controls=[
                NativeUIControl(id="1", name="Run", type="button"),
                NativeUIControl(id="2", name="Debug", type="button"),
            ],
            timestamp=time.time(),
        )

        mock_vision = MagicMock(spec=ScreenPerceptionEngine)
        router = DesktopPerceptionRouter(
            inspector=mock_inspector,
            vision_engine=mock_vision,
            prefer_native=True,
        )

        metrics = LatencyMetrics()
        spoken, method, ctx = await router.perceive("What application is open?", metrics=metrics)

        self.assertEqual(method, "native")
        self.assertIn("Visual Studio Code", spoken)
        # Vision engine should NEVER have been called
        mock_vision.analyze_screen.assert_not_called()

    async def test_desktop_perception_router_vision_fallback(self):
        """Test fallback to multi-model vision router when native UI is insufficient."""
        mock_inspector = MagicMock(spec=WindowsUIInspector)
        # Return empty/canvas window with no controls
        mock_inspector.get_active_window_context.return_value = NativeWindowContext(
            application="CustomCanvas",
            window_title="",
            controls=[],
            timestamp=time.time(),
        )

        mock_vision = MagicMock(spec=ScreenPerceptionEngine)
        mock_vision.router = MagicMock()
        mock_vision.router.providers = {"vision": "qwen"}
        mock_vision.analyze_screen = AsyncMock(
            return_value=(
                ScreenContext(
                    timestamp=time.time(),
                    screen_hash="h123",
                    width=1920,
                    height=1080,
                    application="CustomCanvas",
                    window_title="Canvas View",
                    summary="A custom graph canvas.",
                    visible_text=["Graph Node A"],
                    elements=[],
                ),
                "I see a custom graph canvas on your screen.",
            )
        )

        router = DesktopPerceptionRouter(
            inspector=mock_inspector,
            vision_engine=mock_vision,
            prefer_native=True,
        )

        spoken, method, ctx = await router.perceive("What is on my screen?")
        self.assertEqual(method, "vision_qwen")
        self.assertIn("custom graph canvas", spoken)
        mock_vision.analyze_screen.assert_called_once()

    def test_semantic_tools_registered(self):
        """Test that semantic desktop tools are registered and no raw mouse_click tools exist."""
        registry = create_tool_registry()
        tool_names = [t.name for t in registry.all()]

        self.assertIn("inspect_desktop_ui", tool_names)
        self.assertIn("click_ui_element", tool_names)
        self.assertIn("focus_desktop_window", tool_names)
        self.assertIn("set_ui_input_text", tool_names)
        self.assertIn("select_ui_tab", tool_names)

        # Confirm forbidden raw automation tools are NOT in the registry
        self.assertNotIn("mouse_click", tool_names)
        self.assertNotIn("mouse_move", tool_names)
        self.assertNotIn("keyboard_type", tool_names)


if __name__ == "__main__":
    unittest.main()
