import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image

from app.tools.screen.capture import ScreenCaptureTool
from app.tools.screen.vision import AnalyzeScreenTool


class TestPhase5C2Screen(unittest.IsolatedAsyncioTestCase):
    """Unit tests for Phase 5C.2 Screen Capture & Vision Analysis tools."""

    async def test_01_screen_capture_execution(self):
        tool = ScreenCaptureTool()
        os.makedirs("scratch", exist_ok=True)
        test_img_path = os.path.abspath("scratch/test_unit_screenshot.png")

        # Create mock image
        img = Image.new("RGB", (1920, 1200), color="blue")
        img.save(test_img_path)

        with patch("uiautomation.GetRootControl") as mock_get_root:
            mock_root = MagicMock()
            mock_root.CaptureToImage.return_value = True
            mock_get_root.return_value = mock_root

            res = await tool.execute(save_path=test_img_path)
            self.assertTrue(res["success"])
            self.assertTrue(res["verified"])
            self.assertEqual(res["dimensions"], "1920x1200")
            self.assertEqual(res["width"], 1920)
            self.assertEqual(res["height"], 1200)

    async def test_02_analyze_screen_with_mock_vision(self):
        mock_vision = MagicMock()
        mock_vision.analyze = AsyncMock(return_value={
            "description": "Visual confirmation: A coding IDE window is open.",
            "provider": "Groq Qwen 3.6 27B",
        })

        tool = AnalyzeScreenTool(vision_engine=mock_vision)
        res = await tool.execute(question="What is on my screen?")
        self.assertTrue(res["success"])
        self.assertIn("IDE window", res["analysis"])


if __name__ == "__main__":
    unittest.main()
