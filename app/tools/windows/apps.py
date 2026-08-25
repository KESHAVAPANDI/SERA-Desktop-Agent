import asyncio
import os
import shutil
import subprocess
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
            "Open an application, executable, or website on the Windows computer. "
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

    async def execute(self, application: str = "", app_name: str = "", **kwargs):
        application = (application or app_name or kwargs.get("name", "")).strip()
        if not application:
            return {"success": False, "verified": False, "error": "Application name cannot be empty."}

        app_lower = application.lower()

        # Handle known websites by opening in default browser
        if app_lower in KNOWN_WEBSITES:
            url = KNOWN_WEBSITES[app_lower]
            try:
                os.startfile(url)
                return {
                    "success": True,
                    "verified": True,
                    "application": application,
                    "is_website": True,
                    "message": f"Opened {application.capitalize()} in web browser.",
                }
            except Exception as e:
                return {
                    "success": False,
                    "verified": False,
                    "error": f"Failed to open website {application}: {str(e)}",
                }

        app_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "vs code": "code.cmd",
            "vscode": "code.cmd",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "powershell": "powershell.exe",
            "spotify": "spotify.exe",
            "task manager": "taskmgr.exe",
        }

        target = app_map.get(app_lower, application)

        # Check if executable exists in PATH or standard locations
        resolved_path = shutil.which(target)
        if not resolved_path and not os.path.exists(target):
            # Check common Windows program paths
            common_dirs = [
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
                os.environ.get("LocalAppData", ""),
                os.environ.get("SystemRoot", "C:\\Windows"),
                os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32"),
            ]
            for c_dir in common_dirs:
                if not c_dir:
                    continue
                candidate = os.path.join(c_dir, target)
                if os.path.exists(candidate):
                    resolved_path = candidate
                    break

        # If not resolved and not in app_map or PATH, return truthful failure
        if not resolved_path and target not in app_map.values():
            return {
                "success": False,
                "verified": False,
                "error": f"Application or executable '{application}' could not be found.",
            }

        try:
            target_to_run = resolved_path or target
            subprocess.Popen(f'start "" "{target_to_run}"', shell=True)
            await asyncio.sleep(0.5)

            # Verification: Check if a matching process or window is running
            matched = False
            app_clean = target.lower().replace(".exe", "").replace(".cmd", "")
            for p in psutil.process_iter(["name"]):
                try:
                    p_name = (p.info["name"] or "").lower()
                    if app_clean in p_name:
                        matched = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return {
                "success": True,
                "verified": matched,
                "application": application,
                "message": f"Successfully launched {application}.",
            }
        except Exception as e:
            return {
                "success": False,
                "verified": False,
                "error": f"Failed to launch {application}: {str(e)}",
            }


class OpenFolderTool(Tool):

    @property
    def name(self) -> str:
        return "open_folder"

    @property
    def description(self) -> str:
        return (
            "Open a directory or folder in Windows File Explorer. "
            "Use this when the user asks SERA to open a folder (e.g. 'Downloads', 'Documents', 'Desktop', 'Projects')."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "folder_name": {
                    "type": "string",
                    "description": "Name or path of the folder to open (e.g. 'downloads', 'documents', 'desktop', 'pictures', or relative/absolute path).",
                }
            },
            "required": ["folder_name"],
        }

    async def execute(self, folder_name: str):
        folder_name = folder_name.strip()
        if not folder_name:
            return {"success": False, "verified": False, "error": "Folder name cannot be empty."}

        user_profile = os.environ.get("USERPROFILE", "C:\\Users\\Default")
        standard_folders = {
            "downloads": os.path.join(user_profile, "Downloads"),
            "download": os.path.join(user_profile, "Downloads"),
            "documents": os.path.join(user_profile, "Documents"),
            "document": os.path.join(user_profile, "Documents"),
            "desktop": os.path.join(user_profile, "Desktop"),
            "pictures": os.path.join(user_profile, "Pictures"),
            "photos": os.path.join(user_profile, "Pictures"),
            "videos": os.path.join(user_profile, "Videos"),
            "music": os.path.join(user_profile, "Music"),
            "home": user_profile,
        }

        folder_lower = folder_name.lower()
        target_path = standard_folders.get(folder_lower)

        if not target_path:
            # Check relative or absolute path
            if os.path.isabs(folder_name) and os.path.isdir(folder_name):
                target_path = folder_name
            else:
                # Check in current workspace and user profile subdirectories
                candidates = [
                    os.path.abspath(folder_name),
                    os.path.join(user_profile, folder_name),
                    os.path.join(user_profile, "Documents", folder_name),
                    os.path.join(user_profile, "Downloads", folder_name),
                    os.path.join(user_profile, "Desktop", folder_name),
                ]
                for cand in candidates:
                    if os.path.isdir(cand):
                        target_path = cand
                        break

        if not target_path or not os.path.isdir(target_path):
            return {
                "success": False,
                "verified": False,
                "error": f"Folder '{folder_name}' could not be found.",
            }

        try:
            os.startfile(target_path)
            return {
                "success": True,
                "verified": True,
                "folder_path": target_path,
                "message": f"Opened folder '{folder_name}' at {target_path}.",
            }
        except Exception as e:
            return {
                "success": False,
                "verified": False,
                "error": f"Failed to open folder '{folder_name}': {str(e)}",
            }


class OpenFileTool(Tool):

    @property
    def name(self) -> str:
        return "open_file"

    @property
    def description(self) -> str:
        return (
            "Open a specific file with its default Windows application (e.g. PDF, text file, image, spreadsheet)."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path or name of the file to open.",
                }
            },
            "required": ["file_path"],
        }

    async def execute(self, file_path: str):
        file_path = file_path.strip()
        if not file_path:
            return {"success": False, "verified": False, "error": "File path cannot be empty."}

        target = os.path.abspath(file_path)
        if not os.path.isfile(target):
            # Check user documents and downloads
            user_profile = os.environ.get("USERPROFILE", "")
            for base in [os.path.join(user_profile, "Documents"), os.path.join(user_profile, "Downloads"), os.path.join(user_profile, "Desktop")]:
                cand = os.path.join(base, file_path)
                if os.path.isfile(cand):
                    target = cand
                    break

        if not os.path.isfile(target):
            return {
                "success": False,
                "verified": False,
                "error": f"File '{file_path}' could not be found.",
            }

        try:
            os.startfile(target)
            return {
                "success": True,
                "verified": True,
                "file_path": target,
                "message": f"Opened file '{os.path.basename(target)}'.",
            }
        except Exception as e:
            return {
                "success": False,
                "verified": False,
                "error": f"Failed to open file '{file_path}': {str(e)}",
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
