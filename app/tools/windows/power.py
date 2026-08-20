import asyncio
import os
from app.tools.base import Tool


class LockScreenTool(Tool):

    @property
    def name(self) -> str:
        return "lock_computer"

    @property
    def description(self) -> str:
        return "Lock the Windows PC immediately."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):
        try:
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return {"success": True, "message": "Workstation locked successfully."}
        except Exception as e:
            return {"success": False, "error": f"Failed to lock workstation: {str(e)}"}


class SleepPCTool(Tool):

    @property
    def name(self) -> str:
        return "sleep_computer"

    @property
    def description(self) -> str:
        return "Put the Windows PC to sleep / standby mode."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):
        try:
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            return {"success": True, "message": "Computer entering sleep mode."}
        except Exception as e:
            return {"success": False, "error": f"Failed to sleep computer: {str(e)}"}


class RestartPCTool(Tool):

    @property
    def name(self) -> str:
        return "restart_computer"

    @property
    def description(self) -> str:
        return (
            "Restart the Windows computer. "
            "WARNING: Requires explicit user confirmation before execution."
        )

    @property
    def requires_confirmation(self) -> bool:
        return True

    @property
    def confirmation_prompt(self) -> str:
        return "Are you sure you want me to restart your computer?"

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Force restart without waiting for applications.",
                    "default": False,
                }
            },
        }

    async def execute(self, force: bool = False):
        try:
            flag = "/f" if force else ""
            os.system(f"shutdown /r /t 5 {flag}")
            return {"success": True, "message": "Computer is restarting in 5 seconds."}
        except Exception as e:
            return {"success": False, "error": f"Failed to initiate restart: {str(e)}"}


class ShutdownPCTool(Tool):

    @property
    def name(self) -> str:
        return "shutdown_computer"

    @property
    def description(self) -> str:
        return (
            "Shut down the Windows computer. "
            "WARNING: Requires explicit user confirmation before execution."
        )

    @property
    def requires_confirmation(self) -> bool:
        return True

    @property
    def confirmation_prompt(self) -> str:
        return "Are you sure you want me to shut down your computer?"

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Force shutdown without waiting for applications.",
                    "default": False,
                }
            },
        }

    async def execute(self, force: bool = False):
        try:
            flag = "/f" if force else ""
            os.system(f"shutdown /s /t 5 {flag}")
            return {"success": True, "message": "Computer is shutting down in 5 seconds."}
        except Exception as e:
            return {"success": False, "error": f"Failed to initiate shutdown: {str(e)}"}
