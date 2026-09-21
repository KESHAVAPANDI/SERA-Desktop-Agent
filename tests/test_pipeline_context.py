"""Integration test: CommandPipeline multi-turn context execution.
Verifies 'Set brightness to 80%' followed by 'turn it back to 100%' executes deterministically.
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.command_pipeline import CommandPipeline
from app.core.state import SERAState
from app.core.events import EventBus
from app.tools import create_tool_registry


class TestPipelineContext(unittest.IsolatedAsyncioTestCase):

    async def test_brightness_continuation_flow(self):
        tools = create_tool_registry()

        # Mock the actual brightness hardware tool so it doesn't fail on headless systems
        bright_tool = tools.get("set_brightness")
        bright_tool.execute = AsyncMock(return_value={"success": True, "brightness": 80, "message": "Brightness set to 80%"})

        pipeline = CommandPipeline(tools=tools, state=SERAState(), event_bus=EventBus())

        # Turn 1
        res1 = await pipeline.execute_text("Set brightness to 80%")
        self.assertTrue(res1.get("success"))
        self.assertIn("80", res1.get("response"))
        self.assertEqual(pipeline.context_state.get("last_intent"), "set_brightness")

        # Turn 2: continuation without mentioning 'brightness'
        bright_tool.execute = AsyncMock(return_value={"success": True, "brightness": 100, "message": "Brightness set to 100%"})
        res2 = await pipeline.execute_text("turn it back to 100%")
        self.assertTrue(res2.get("success"), f"Turn 2 failed: {res2}")
        self.assertIn("100", res2.get("response"))
        self.assertEqual(pipeline.context_state.get("last_intent"), "set_brightness")
        bright_tool.execute.assert_called_once_with(brightness=100)

    async def test_self_close_execution_flow(self):
        tools = create_tool_registry()
        pipeline = CommandPipeline(tools=tools, state=SERAState(), event_bus=EventBus())

        close_tool = tools.get("sera_self_close")
        close_tool.execute = AsyncMock(return_value={"success": True, "verified": True, "message": "Presence closed"})

        res = await pipeline.execute_text("close yourself")
        self.assertTrue(res.get("success"))
        self.assertIn("safely closed", res.get("response").lower())
        close_tool.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
