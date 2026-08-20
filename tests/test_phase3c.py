import asyncio
import time
import unittest
from unittest.mock import MagicMock, AsyncMock

from app.tools.desktop.executor import DesktopActionExecutor
from app.tools.desktop.models import (
    NativeUIControl,
    NativeWindowContext,
    SemanticActionRequest,
    SemanticActionResult,
)
from app.tools.desktop.target_resolver import TargetResolver, ResolutionResult
from app.tools.desktop.ui_inspector import WindowsUIInspector


class TestPhase3C(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.resolver = TargetResolver()
        self.controls = [
            NativeUIControl(
                id="ctrl_1",
                name="Start Debugging",
                type="button",
                control_type_name="ButtonControl",
                automation_id="btnStartDebug",
                enabled=True,
                visible=True,
            ),
            NativeUIControl(
                id="ctrl_2",
                name="File Name",
                type="edit",
                control_type_name="EditControl",
                automation_id="txtFileName",
                enabled=True,
                visible=True,
            ),
            NativeUIControl(
                id="ctrl_3",
                name="Save",
                type="button",
                automation_id="btnSaveToolbar",
                class_name="ToolbarButton",
                enabled=True,
                visible=True,
            ),
            NativeUIControl(
                id="ctrl_4",
                name="Save",
                type="button",
                automation_id="btnSaveMenu",
                class_name="MenuButton",
                enabled=True,
                visible=True,
            ),
            NativeUIControl(
                id="ctrl_5",
                name="Delete Project",
                type="button",
                enabled=False,
                visible=True,
            ),
        ]

    def test_target_resolver_high_confidence(self):
        """Test unique high-confidence resolution with exact name and type."""
        target = {"name": "Start Debugging", "type": "button"}
        res = self.resolver.resolve(target, self.controls)

        self.assertTrue(res.resolved)
        self.assertEqual(res.confidence, "high")
        self.assertEqual(res.control.id, "ctrl_1")
        self.assertGreaterEqual(res.score, 0.70)

    def test_target_resolver_ambiguity_detection(self):
        """Test that multiple identical buttons without context are flagged as ambiguous."""
        target = {"name": "Save", "type": "button"}
        res = self.resolver.resolve(target, self.controls)

        # Ambiguous between ctrl_3 and ctrl_4 -> should not be blindly resolved
        self.assertFalse(res.resolved)
        self.assertEqual(res.confidence, "medium")
        self.assertGreater(len(res.ambiguity_candidates), 1)

    def test_target_resolver_contextual_disambiguation(self):
        """Test that adding context ('Toolbar') successfully disambiguates competing candidates."""
        target = {"name": "Save", "type": "button", "context": "Toolbar"}
        res = self.resolver.resolve(target, self.controls)

        self.assertTrue(res.resolved)
        self.assertEqual(res.control.id, "ctrl_3")
        self.assertEqual(res.control.automation_id, "btnSaveToolbar")

    def test_target_resolver_disabled_control_penalty(self):
        """Test that disabled controls are penalized."""
        target = {"name": "Delete Project", "type": "button"}
        res = self.resolver.resolve(target, self.controls)

        self.assertFalse(res.resolved)
        self.assertLess(res.score, 0.70)

    async def test_action_executor_sensitive_field_protection(self):
        """Test blocking of sensitive fields (password, card, PIN)."""
        executor = DesktopActionExecutor(resolver=self.resolver)
        req = SemanticActionRequest(
            action="set_input_text",
            target={"name": "Password Input", "type": "password"},
            value="my_secret_pw",
        )
        res = await executor.execute_action(req)

        self.assertFalse(res.success)
        self.assertEqual(res.verification_method, "security_policy")
        self.assertIn("sensitive", res.message.lower())

    async def test_action_executor_ambiguity_guard(self):
        """Test that ambiguous targets are blocked from execution with informative error."""
        mock_inspector = MagicMock(spec=WindowsUIInspector)
        mock_inspector.get_active_window_context.return_value = NativeWindowContext(
            application="App",
            window_title="Main App",
            controls=self.controls,
            timestamp=time.time(),
        )

        executor = DesktopActionExecutor(inspector=mock_inspector, resolver=self.resolver)
        req = SemanticActionRequest(
            action="click_element",
            target={"name": "Save", "type": "button"},
        )
        res = await executor.execute_action(req)

        self.assertFalse(res.success)
        self.assertEqual(res.verification_method, "anti_ambiguity_guard")
        self.assertIn("Ambiguous target", res.message)

    async def test_action_executor_observe_act_verify_timing(self):
        """Test full Observe -> Act -> Verify execution and timing telemetry."""
        mock_inspector = MagicMock(spec=WindowsUIInspector)
        mock_inspector.get_active_window_context.return_value = NativeWindowContext(
            application="Notepad",
            window_title="Untitled - Notepad",
            controls=[self.controls[1]],  # "File Name" edit control
            timestamp=time.time(),
        )

        executor = DesktopActionExecutor(inspector=mock_inspector, resolver=self.resolver)
        req = SemanticActionRequest(
            action="set_input_text",
            target={"name": "File Name", "type": "edit"},
            value="document.txt",
        )

        telemetry = {}
        res = await executor.execute_action(req, telemetry=telemetry)

        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertEqual(res.verification_method, "value_change")
        self.assertIn("ui_inspection_ms", telemetry)
        self.assertIn("target_resolution_ms", telemetry)
        self.assertIn("action_execution_ms", telemetry)
        self.assertIn("verification_ms", telemetry)


if __name__ == "__main__":
    unittest.main()
