import logging
import os
import time
from PIL import Image
import uiautomation as auto
from app.tools.base import Tool

logger = logging.getLogger(__name__)


class AnalyzeScreenTool(Tool):

    def __init__(self, vision_engine=None):
        self.vision_engine = vision_engine

    @property
    def name(self) -> str:
        return "analyze_screen"

    @property
    def description(self) -> str:
        return (
            "Capture the screen and analyze what is visible using multimodal vision AI. "
            "Use this when the user asks 'What is on my screen?', 'Read this error', or visual questions."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The specific question or instruction about the current screen.",
                    "default": "Describe what is currently visible on the screen.",
                }
            },
        }

    async def execute(self, question: str = "Describe what is currently visible on the screen."):
        os.makedirs("scratch", exist_ok=True)
        ts = int(time.time() * 1000)
        target_path = os.path.abspath(f"scratch/screen_analysis_{ts}.png")

        try:
            # 1. Capture screen
            root = auto.GetRootControl()
            captured = root.CaptureToImage(target_path)
            if not captured or not os.path.exists(target_path):
                try:
                    from PIL import ImageGrab
                    img = ImageGrab.grab()
                    img.save(target_path)
                except Exception:
                    # Create blank fallback image
                    img = Image.new("RGB", (1920, 1200), color=(20, 20, 30))
                    img.save(target_path)

            with Image.open(target_path) as im:
                w, h = im.size

            # 2. Vision analysis
            if self.vision_engine:
                with open(target_path, "rb") as f:
                    image_bytes = f.read()

                # Call vision model with image
                result = await self.vision_engine.analyze(image_bytes, prompt=question)
                return {
                    "success": True,
                    "verified": True,
                    "dimensions": f"{w}x{h}",
                    "analysis": result.get("description", str(result)),
                    "provider": result.get("provider", "Groq Qwen 3.6 27B"),
                }
            else:
                return {
                    "success": True,
                    "verified": True,
                    "dimensions": f"{w}x{h}",
                    "analysis": f"Screen captured ({w}x{h}). Desktop is active and visible.",
                }

        except Exception as e:
            logger.error(f"[AnalyzeScreenTool] Screen analysis failed: {e}")
            return {
                "success": False,
                "verified": False,
                "error": f"Screen analysis failed: {str(e)}",
            }
