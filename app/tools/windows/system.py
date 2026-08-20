import asyncio
import datetime
import os
import psutil
import re
import subprocess
from app.tools.base import Tool


class GetSystemInfoTool(Tool):

    @property
    def name(self):
        return "get_system_info"

    @property
    def description(self):
        return (
            "Get comprehensive diagnostic information about the Windows computer, "
            "including CPU usage, RAM utilization, Disk usage, and system uptime."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):
        vmem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time

        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)

        return {
            "success": True,
            "cpu_percent": psutil.cpu_percent(interval=0.3),
            "cpu_cores": psutil.cpu_count(logical=True),
            "memory": {
                "percent": vmem.percent,
                "used_gb": round(vmem.used / (1024**3), 2),
                "total_gb": round(vmem.total / (1024**3), 2),
            },
            "disk_c": {
                "percent": disk.percent,
                "free_gb": round(disk.free / (1024**3), 2),
                "total_gb": round(disk.total / (1024**3), 2),
            },
            "uptime": f"{hours} hours, {minutes} minutes",
        }


class GetBatteryStatusTool(Tool):

    @property
    def name(self):
        return "get_battery_status"

    @property
    def description(self):
        return (
            "Get the current laptop battery percentage, charging state, and power source."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):
        battery = psutil.sensors_battery()
        if battery is None:
            return {
                "success": False,
                "error": "Battery sensor unavailable (likely a desktop PC without a battery).",
            }

        return {
            "success": True,
            "percentage": battery.percent,
            "charging": battery.power_plugged,
            "power_plugged": battery.power_plugged,
        }


class GetCurrentTimeTool(Tool):

    @property
    def name(self):
        return "get_current_time"

    @property
    def description(self):
        return "Get the current local date, time, and day of the week."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):
        now = datetime.datetime.now()
        return {
            "success": True,
            "datetime": now.isoformat(),
            "formatted": now.strftime("%A, %d %B %Y, %I:%M %p"),
        }


class GetWiFiStatusTool(Tool):

    @property
    def name(self):
        return "get_wifi_status"

    @property
    def description(self):
        return (
            "Check Wi-Fi network connection status, connected network SSID, signal quality, and radio state on Windows."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):
        try:
            res = await asyncio.create_subprocess_shell(
                "netsh wlan show interfaces",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await res.communicate()
            out_str = stdout.decode("utf-8", errors="ignore")

            if "There is no wireless interface on the system" in out_str:
                return {"success": True, "connected": False, "message": "No wireless interface detected."}

            ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", out_str, re.MULTILINE)
            state_match = re.search(r"^\s*State\s*:\s*(.+)$", out_str, re.MULTILINE)
            signal_match = re.search(r"^\s*Signal\s*:\s*(\d+)%", out_str, re.MULTILINE)

            state = state_match.group(1).strip() if state_match else "unknown"
            ssid = ssid_match.group(1).strip() if ssid_match else None
            signal = int(signal_match.group(1)) if signal_match else None

            is_connected = state.lower() == "connected"

            return {
                "success": True,
                "connected": is_connected,
                "ssid": ssid,
                "signal_percent": signal,
                "state": state,
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get Wi-Fi status: {str(e)}"}