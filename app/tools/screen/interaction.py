from app.tools.base import BaseTool

class ScreenInteractionTool(BaseTool):
    """Tool for mouse clicking and keyboard automation."""
    name = "screen_interaction"
    description = "Simulates mouse click or keyboard typing."

    def execute(self, action: str = "click", x: int = 0, y: int = 0, text: str = "", **kwargs):
        return {"success": True, "message": f"Executed screen action: {action}"}
