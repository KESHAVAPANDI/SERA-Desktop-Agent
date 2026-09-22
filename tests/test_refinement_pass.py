"""Tests for Phase 2C/2D Refinement Pass:
1. Conversational Addressing Normalization ("Sarah, close yourself", "Hey Sera, turn brightness to 50%", "Sarah")
2. Conversational Error Shielding (internal errors are never spoken)
3. Event Deduplication on Voice Turns
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.command import CommandParser, normalize_conversational_utterance
from app.core.command_pipeline import CommandPipeline
from app.core.state import SERAState
from app.core.events import EventBus
from app.tools import create_tool_registry


class TestRefinementPass(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.parser = CommandParser()

    def test_01_addressing_normalization_self_close(self):
        """Verify addressing variants of self-close route directly to sera_self_close."""
        variants = [
            "Sarah, close yourself",
            "Sera, close yourself",
            "Hey Sarah, close yourself",
            "Hey Sera, close yourself",
            "Please close yourself",
            "Close yourself, please",
            "Close yourself, Sarah",
            "Sarah, please close yourself",
            "Could you please close yourself",
        ]
        for phrase in variants:
            cmd = self.parser.parse(phrase)
            self.assertEqual(
                cmd.intent,
                "sera_self_close",
                f"Failed for '{phrase}': got intent '{cmd.intent}' instead of 'sera_self_close'",
            )
            self.assertIn("sera_self_close", cmd.required_tools)
            self.assertEqual(cmd.source_text, phrase)

    def test_02_addressing_normalization_system_controls(self):
        """Verify natural addressing works seamlessly with brightness, volume, and app commands."""
        # Brightness
        cmd1 = self.parser.parse("Hey Sera, turn brightness to 60%")
        self.assertEqual(cmd1.intent, "set_brightness")
        self.assertEqual(cmd1.parameters.get("brightness"), 60)

        cmd2 = self.parser.parse("Sarah, please set brightness to 40%")
        self.assertEqual(cmd2.intent, "set_brightness")
        self.assertEqual(cmd2.parameters.get("brightness"), 40)

        # Volume
        cmd3 = self.parser.parse("Could you please set volume to 75%")
        self.assertEqual(cmd3.intent, "set_volume")
        self.assertEqual(cmd3.parameters.get("volume"), 75)

        # Application
        cmd4 = self.parser.parse("Sarah, please open Chrome")
        self.assertEqual(cmd4.intent, "open_application")
        self.assertEqual(cmd4.parameters.get("application"), "chrome")

    def test_03_pure_address_call(self):
        """Verify calling Sarah/Sera alone returns conversational acknowledgement."""
        calls = ["Sarah", "Sera", "Hey Sarah", "Hey Sera", "Ok Sera"]
        for call in calls:
            cmd = self.parser.parse(call)
            self.assertEqual(cmd.intent, "assistant_wake")
            self.assertIn("here", cmd.raw_response.lower())

    async def test_04_conversational_error_shielding(self):
        """Verify internal technical errors (Win32, stack traces) are shielded from spoken response."""
        tools = create_tool_registry()
        mock_bright = tools.get("set_brightness")
        # Simulate low-level Win32 hardware failure
        raw_tech_err = "Win32 error 127: The specified procedure could not be found in user32.dll"
        mock_bright.execute = AsyncMock(return_value={"success": False, "error": raw_tech_err})

        pipeline = CommandPipeline(tools=tools, state=SERAState(), event_bus=EventBus())
        res = await pipeline.execute_text("set brightness to 50%")

        self.assertFalse(res.get("success"))
        # Raw error is preserved for diagnostics
        self.assertEqual(res.get("error"), raw_tech_err)
        # Spoken response is natural companion phrasing
        spoken = res.get("response")
        self.assertNotIn("127", spoken)
        self.assertNotIn("Win32", spoken)
        self.assertNotIn("user32.dll", spoken)
        self.assertIn("brightness", spoken.lower())

    async def test_05_voice_turn_event_deduplication(self):
        """Verify is_voice_turn=True suppresses duplicate AGENT_RESPONSE and TASK_COMPLETED."""
        tools = create_tool_registry()
        events = EventBus()
        captured_events = []

        for ev_name in ["TASK_STARTED", "AGENT_RESPONSE", "TASK_COMPLETED", "TASK_FAILED"]:
            events.subscribe(ev_name, lambda p, name=ev_name: captured_events.append(name))

        pipeline = CommandPipeline(tools=tools, state=SERAState(), event_bus=events)

        # Voice turn: pipeline should NOT emit AGENT_RESPONSE or TASK_COMPLETED
        res = await pipeline.execute_text("what time is it", is_voice_turn=True)
        self.assertTrue(res.get("success"))

        self.assertNotIn("AGENT_RESPONSE", captured_events)
        self.assertNotIn("TASK_COMPLETED", captured_events)
        self.assertNotIn("TASK_STARTED", captured_events)


if __name__ == "__main__":
    unittest.main()
