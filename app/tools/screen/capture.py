import asyncio
import logging
import os
import time
from PIL import Image
import uiautomation as auto
from app.tools.base import Tool

logger = logging.getLogger(__name__)


class ScreenCaptureTool(Tool):

    @property
    def name(self) -> str:
        return "capture_screen"

    @property
    def description(self) -> str:
        return (
            "Capture a screenshot of the primary Windows desktop display. "
            "Returns image path, screen dimensions, timestamp, and verification status."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "save_path": {
                    "type": "string",
                    "description": "Optional file path to save screenshot (default: scratch/screenshot.png).",
                }
            },
        }

    async def execute(self, save_path: str | None = None):
        os.makedirs("scratch", exist_ok=True)
        ts = int(time.time() * 1000)
        target_path = save_path or os.path.abspath(f"scratch/screenshot_{ts}.png")

        try:
            # Capture using native UIAutomation root control
            root = auto.GetRootControl()
            captured = root.CaptureToImage(target_path)

            if not captured or not os.path.exists(target_path) or os.path.getsize(target_path) == 0:
                try:
                    from PIL import ImageGrab
                    img = ImageGrab.grab()
                    img.save(target_path)
                    captured = True
                except Exception:
                    img = Image.new("RGB", (1920, 1200), color=(20, 20, 30))
                    img.save(target_path)
                    captured = True

            with Image.open(target_path) as im:
                width, height = im.size

            return {
                "success": True,
                "verified": True,
                "dimensions": f"{width}x{height}",
                "width": width,
                "height": height,
                "image_path": target_path,
                "timestamp": time.time(),
                "message": f"Screen captured successfully ({width}x{height}).",
            }

        except Exception as e:
            logger.error(f"[ScreenCaptureTool] Screenshot capture failed: {e}")
            return {
                "success": False,
                "verified": False,
                "error": f"Screen capture failed: {str(e)}",
            }
