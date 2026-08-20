import asyncio
import os
import psutil
from app.tools.base import Tool

KNOWN_WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "netflix": "https://www.netflix.com",
}


class OpenApplicationTool(Tool):

    @property
    def name(self) -> str:
        return "open_application"

    @property
    def description(self) -> str:
        return (
            "Open an application, executable, or URL on the Windows computer. "
            "Use this when the user asks SERA to open, launch, or start an app."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "application": {
                    "type": "string",
                    "description": "Name of the application, executable, or website to open (e.g. 'notepad', 'chrome', 'calculator', 'youtube').",
                }
            },
            "required": ["application"],
        }

    async def execute(self, application: str):
        application = application.strip()
        if not application:
            return {"success": False, "error": "Application name cannot be empty."}

        app_lower = application.lower()

        # Handle known websites by opening in default browser
        if app_lower in KNOWN_WEBSITES:
            url = KNOWN_WEBSITES[app_lower]
            try:
                process = await asyncio.create_subprocess_shell(
                    f'start "" "{url}"',
                    shell=True,
                )
                await process.wait()
                return {
                    "success": True,
                    "application": application,
                    "is_website": True,
                    "message": f"Opened {application.capitalize()} in web browser.",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to open website {application}: {str(e)}",
                }

        app_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "chrome": "chrome",
            "google chrome": "chrome",
            "edge": "msedge",
            "microsoft edge": "msedge",
            "vs code": "code",
            "vscode": "code",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "powershell": "powershell.exe",
            "spotify": "spotify",
            "task manager": "taskmgr.exe",
        }

        target = app_map.get(app_lower, application)

        try:
            process = await asyncio.create_subprocess_shell(
                f'start "" "{target}"',
                shell=True,
            )
            await process.wait()
            return {
                "success": True,
                "application": application,
                "message": f"Successfully launched {application}.",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to launch {application}: {str(e)}",
            }


class CloseApplicationTool(Tool):

    @property
    def name(self) -> str:
        return "close_application"

    @property
    def description(self) -> str:
        return (
            "Close or terminate a running application on the Windows computer. "
            "Use this when the user asks SERA to close, exit, or terminate an app."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "application": {
                    "type": "string",
                    "description": "Name or part of the name of the application to close (e.g. 'notepad', 'chrome', 'calc').",
                }
            },
            "required": ["application"],
        }

    async def execute(self, application: str):
        app_name = application.strip().lower()
        if not app_name:
            return {"success": False, "error": "Application name cannot be empty."}

        # Website vs Application Ambiguity Protection
        if app_name in KNOWN_WEBSITES:
            return {
                "success": False,
                "is_website": True,
                "error": f"'{application.capitalize()}' is a website/browser tab, not an independent Windows application. Please close the tab directly in your web browser.",
            }

        matched_pids = []
        app_clean = app_name.replace(".exe", "")

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                p_name = (proc.info["name"] or "").lower()
                if app_clean in p_name:
                    matched_pids.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not matched_pids:
            # Fallback to taskkill by name
            cmd = f'taskkill /F /IM "{app_clean}*" /T'
            res = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await res.communicate()
            if res.returncode == 0:
                return {"success": True, "message": f"Closed application matching '{application}'."}
            return {"success": False, "error": f"No running application found matching '{application}'."}

        closed_count = 0
        for proc in matched_pids:
            try:
                proc.terminate()
                closed_count += 1
            except Exception:
                try:
                    proc.kill()
                    closed_count += 1
                except Exception:
                    pass

        return {
            "success": True,
            "application": application,
            "processes_closed": closed_count,
            "message": f"Closed {closed_count} process(es) matching '{application}'.",
        }


class ListRunningApplicationsTool(Tool):

    @property
    def name(self) -> str:
        return "list_running_applications"

    @property
    def description(self) -> str:
        return (
            "List active applications and processes currently running on the Windows system."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "filter_user_apps": {
                    "type": "boolean",
                    "description": "If true, filters to common interactive user apps.",
                    "default": True,
                }
            },
        }

    async def execute(self, filter_user_apps: bool = True):
        seen_names = set()
        apps = []

        system_noise = {
            "svchost.exe", "conhost.exe", "runtimebroker.exe", "sihost.exe",
            "taskhostw.exe", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
            "lsass.exe", "fontdrvhost.exe", "dwm.exe", "explorer.exe", "spoolsv.exe",
            "wmiprvse.exe", "searchindexer.exe", "registry", "system idle process", "system"
        }

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = proc.info.get("name")
                if not name:
                    continue
                lower = name.lower()

                if filter_user_apps and lower in system_noise:
                    continue

                if lower not in seen_names:
                    seen_names.add(lower)
                    apps.append({
                        "name": name,
                        "pid": proc.info.get("pid"),
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        apps.sort(key=lambda x: x["name"].lower())

        return {
            "success": True,
            "count": len(apps),
            "applications": apps[:30],
        }
