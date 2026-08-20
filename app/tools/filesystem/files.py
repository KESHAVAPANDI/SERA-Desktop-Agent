import os
from app.tools.base import BaseTool

class FileOperationsTool(BaseTool):
    """Tool for reading and listing files."""
    name = "file_operations"
    description = "Lists files in directory or checks file existence."

    def execute(self, action: str = "list", path: str = ".", **kwargs):
        if action == "list":
            files = os.listdir(path)
            return {"success": True, "files": files}
        return {"success": False, "error": f"Unknown action: {action}"}
