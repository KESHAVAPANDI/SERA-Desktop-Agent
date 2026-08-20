from app.tools.base import BaseTool

class ScreenCaptureTool(BaseTool):
    """Tool for taking screen captures."""
    name = "capture_screen"
    description = "Captures current primary display screenshot."

    def execute(self, output_path: str = "screenshot.png", **kwargs):
        # Screen capture logic placeholder
        return {"success": True, "output_path": output_path}
