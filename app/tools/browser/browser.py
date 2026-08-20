import webbrowser
from app.tools.base import BaseTool

class BrowserTool(BaseTool):
    """Tool for opening URLs and web searches in default browser."""
    name = "open_browser"
    description = "Opens a web URL in default browser."

    def execute(self, url: str = "https://www.google.com", **kwargs):
        webbrowser.open(url)
        return {"success": True, "message": f"Opened {url}"}
