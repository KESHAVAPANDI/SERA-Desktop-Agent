"""Verification suite for Phase 2C/2D Correction Pass fixes:
1. Hotkey First-Press Readiness & Health Check
2. Self Close Routing & Tool
3. Event Deduplication
4. Audio Levels Streaming Calculation
5. Immediate Context Hotfix ("Set brightness to 80%" -> "turn it back to 100%")
"""

import asyncio
import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.command import CommandParser, CommandCategory
from app.core.command_pipeline import CommandPipeline
from app.tools import create_tool_registry
from app.tools.windows.self_close import SeraSelfCloseTool
from app.speech.audio_manager import AudioManager
import numpy as np


class TestCorrectionPass(unittest.TestCase):

    def setUp(self):
        self.parser = CommandParser()

    def test_01_self_close_intent(self):
        """Verify 'close yourself' routes to dedicated sera_self_close tool, NOT close_application."""
        phrases = [
            "close yourself",
            "exit yourself",
            "quit yourself",
            "shutdown yourself",
            "close sera",
            "quit sera",
            "close presence",
        ]
        for phrase in phrases:
            cmd = self.parser.parse(phrase)
            self.assertEqual(cmd.intent, "sera_self_close", f"Failed for '{phrase}': got {cmd.intent}")
            self.assertIn("sera_self_close", cmd.required_tools)
            self.assertNotIn("close_application", cmd.required_tools)
            self.assertEqual(cmd.execution_plan[0].action, "sera_self_close")

    def test_02_immediate_context_hotfix(self):
        """Verify 'Set brightness to 80%' followed by 'turn it back to 100%' resolves directly to set_brightness."""
        # Turn 1: Set brightness to 80%
        cmd1 = self.parser.parse("Set brightness to 80%")
        self.assertEqual(cmd1.intent, "set_brightness")
        self.assertEqual(cmd1.parameters.get("brightness"), 80)

        # Context after Turn 1
        ctx = {
            "last_intent": "set_brightness",
            "last_tool": "set_brightness",
            "last_brightness": 80,
            "last_command": cmd1,
        }

        # Turn 2: "turn it back to 100%"
        cmd2 = self.parser.parse("turn it back to 100%", context=ctx)
        self.assertEqual(cmd2.intent, "set_brightness", f"Got intent: {cmd2.intent}")
        self.assertEqual(cmd2.parameters.get("brightness"), 100)
        self.assertEqual(cmd2.execution_plan[0].action, "set_brightness")
        self.assertEqual(cmd2.execution_plan[0].arguments, {"brightness": 100})

        # Turn 2 variant: "set it to 50%"
        cmd3 = self.parser.parse("set it to 50%", context=ctx)
        self.assertEqual(cmd3.intent, "set_brightness")
        self.assertEqual(cmd3.parameters.get("brightness"), 50)

    def test_03_immediate_context_volume(self):
        """Verify volume continuation works identically."""
        ctx_vol = {
            "last_intent": "set_volume",
            "last_tool": "set_volume",
            "last_volume": 40,
        }
        cmd = self.parser.parse("turn it back to 75%", context=ctx_vol)
        self.assertEqual(cmd.intent, "set_volume")
        self.assertEqual(cmd.parameters.get("volume"), 75)
        self.assertEqual(cmd.execution_plan[0].arguments, {"volume": 75})

    def test_04_tool_registry_contains_self_close(self):
        """Verify SeraSelfCloseTool is properly registered."""
        registry = create_tool_registry()
        tool = registry.get("sera_self_close")
        self.assertIsNotNone(tool)
        self.assertIsInstance(tool, SeraSelfCloseTool)

    def test_05_audio_level_streaming_calculation(self):
        """Verify AudioManager._compute_chunk_levels returns valid multi-band levels from PCM data."""
        # Generate 1-second 440Hz sine wave PCM data
        rate = 16000
        t = np.linspace(0, 1.0, rate, endpoint=False)
        sine = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

        mgr = AudioManager.__new__(AudioManager)
        levels = mgr._compute_chunk_levels(sine, rate, 0.2)

        self.assertIn("rawAmp", levels)
        self.assertIn("bass", levels)
        self.assertIn("mid", levels)
        self.assertIn("treble", levels)
        self.assertGreater(levels["rawAmp"], 0.0)
        self.assertLessEqual(levels["rawAmp"], 1.0)
        self.assertGreater(levels["mid"], 0.0)


if __name__ == "__main__":
    unittest.main()
