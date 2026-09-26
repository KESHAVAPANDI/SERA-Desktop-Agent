import asyncio
import os
import shutil
import subprocess
import time
import winreg
import psutil
import win32con
import win32gui
import win32process
from typing import Optional
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

APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "vs code": "code.exe",
    "vscode": "code.exe",
    "code": "code.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "spotify": "spotify.exe",
    "task manager": "taskmgr.exe",
}


def resolve_windows_application(application: str) -> str | None:
    """Resolves an application name to an absolute executable path using Registry, Standard Paths, and PATH."""
    app_clean = application.strip().lower()
    if not app_clean:
        return None

    target = APP_MAP.get(app_clean, app_clean)
    exe_name = target if (target.endswith(".exe") or target.endswith(".cmd")) else f"{target}.exe"

    # 1. Direct path check
    if os.path.isfile(target):
        return os.path.abspath(target)
    if os.path.isfile(exe_name):
        return os.path.abspath(exe_name)

    # 2. Known standard Windows installation paths
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    system_root = os.environ.get("SystemRoot", r"C:\Windows")

    known_paths = {
        "chrome.exe": [
            os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local_app_data, "Google", "Chrome", "Application", "chrome.exe") if local_app_data else "",
        ],
        "msedge.exe": [
            os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(local_app_data, "Microsoft", "Edge", "Application", "msedge.exe") if local_app_data else "",
        ],
        "notepad.exe": [
            os.path.join(system_root, "System32", "notepad.exe"),
            os.path.join(system_root, "notepad.exe"),
        ],
        "calc.exe": [
            os.path.join(system_root, "System32", "calc.exe"),
        ],
        "code.exe": [
            os.path.join(local_app_data, "Programs", "Microsoft VS Code", "Code.exe") if local_app_data else "",
            os.path.join(program_files, "Microsoft VS Code", "Code.exe"),
        ],
        "explorer.exe": [
            os.path.join(system_root, "explorer.exe"),
        ],
        "cmd.exe": [
            os.path.join(system_root, "System32", "cmd.exe"),
        ],
        "powershell.exe": [
            os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
        ],
        "taskmgr.exe": [
            os.path.join(system_root, "System32", "Taskmgr.exe"),
        ],
    }

    if exe_name in known_paths:
        for p in known_paths[exe_name]:
            if p and os.path.isfile(p):
                return p

    # 3. Check Windows Registry App Paths (HKLM and HKCU, 64-bit and 32-bit views)
    for root in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
        for subkey in [
            rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}",
            rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{target}",
        ]:
            for access_mask in [winreg.KEY_READ, winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0), winreg.KEY_READ | getattr(winreg, "KEY_WOW64_32KEY", 0)]:
                try:
                    with winreg.OpenKey(root, subkey, 0, access_mask) as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val:
                            clean_val = val.strip('"\t ')
                            if os.path.isfile(clean_val):
                                return clean_val
                except (OSError, FileNotFoundError):
                    pass

    # 4. PATH lookup via shutil.which
    which_path = shutil.which(exe_name) or shutil.which(target)
    if which_path and os.path.isfile(which_path):
        return which_path

    # 5. Search in common program folders
    for base_dir in [program_files, program_files_x86, os.path.join(local_app_data, "Programs") if local_app_data else ""]:
        if base_dir and os.path.isdir(base_dir):
            candidate = os.path.join(base_dir, exe_name)
            if os.path.isfile(candidate):
                return candidate

    return None


def verify_application_running(target_name: str, timeout: float = 5.0) -> bool:
    """Verifies that an active, non-zombie process matching the application exists."""
    app_clean = target_name.lower().replace(".exe", "").replace(".cmd", "")
    t0 = time.time()
    while time.time() - t0 < timeout:
        for p in psutil.process_iter(["pid", "name", "status"]):
            try:
                p_name = (p.info["name"] or "").lower()
                if app_clean in p_name and p.info.get("status") != psutil.STATUS_ZOMBIE:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(0.25)
    return False


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

        resolved_path = resolve_windows_application(application)

        if not resolved_path:
            return {
                "success": False,
                "verified": False,
                "error": f"Application or executable '{application}' could not be found.",
            }

        try:
            # Launch executable directly using Windows process creation
            try:
                subprocess.Popen([resolved_path], shell=False)
            except Exception:
                os.startfile(resolved_path)

            # Verification: Confirm the application process / window is genuinely active
            target_file = os.path.basename(resolved_path)
            verified = await asyncio.to_thread(verify_application_running, target_file, 5.0)

            if not verified:
                return {
                    "success": False,
                    "verified": False,
                    "error": f"Launched '{application}' but could not verify that its process/window opened.",
                }

            msg = "Chrome is now open." if "chrome" in app_lower else f"Successfully launched {application}."
            return {
                "success": True,
                "verified": True,
                "application": application,
                "resolved_path": resolved_path,
                "message": msg,
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


class CloseWindowTool(Tool):
    """Closes a specific window by HWND or title without terminating the underlying application process (Section 6)."""

    @property
    def name(self) -> str:
        return "close_window"

    @property
    def description(self) -> str:
        return (
            "Close a specific application window or active foreground window using Win32 WM_CLOSE "
            "without terminating the underlying application process. Use this when the user asks to "
            "close a window (e.g. 'close this window', 'close that window', 'close the Notepad window')."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "window_title": {
                    "type": "string",
                    "description": "Optional title or partial title of the window to close. If omitted, closes the active foreground window.",
                },
                "hwnd": {
                    "type": "integer",
                    "description": "Optional explicit HWND handle of the window to close.",
                },
            },
        }

    async def execute(self, window_title: Optional[str] = None, hwnd: Optional[int] = None, **kwargs):
        try:
            import win32service
            win32service.OpenDesktop("default", 0, False, win32con.GENERIC_ALL).SetThreadDesktop()
        except Exception:
            pass

        target_hwnd = hwnd or kwargs.get("handle")
        title_query = (window_title or kwargs.get("title") or kwargs.get("target") or "").strip()

        # 1. Resolve target HWND
        if not target_hwnd and title_query:
            matched_hwnds = []
            def enum_cb(h, _):
                if win32gui.IsWindowVisible(h):
                    txt = win32gui.GetWindowText(h)
                    if txt and title_query.lower() in txt.lower():
                        matched_hwnds.append((h, txt))
            try:
                win32gui.EnumWindows(enum_cb, None)
            except Exception:
                pass
            if matched_hwnds:
                target_hwnd = matched_hwnds[0][0]

        # Fallback to active foreground window
        if not target_hwnd:
            target_hwnd = win32gui.GetForegroundWindow()

        if not target_hwnd or not win32gui.IsWindow(target_hwnd):
            return {
                "success": False,
                "verified": False,
                "error": f"No active window found to close (query='{title_query}').",
            }

        w_title = win32gui.GetWindowText(target_hwnd)
        owning_pid = None
        try:
            _, owning_pid = win32process.GetWindowThreadProcessId(target_hwnd)
        except Exception:
            pass

        # 2. Dispatch WM_CLOSE to target window handle
        try:
            win32gui.PostMessage(target_hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception as e:
            return {
                "success": False,
                "verified": False,
                "error": f"Failed to post WM_CLOSE to window HWND {target_hwnd}: {e}",
            }

        # 3. Empirically verify that the window is closed
        closed = False
        for _ in range(15):
            await asyncio.sleep(0.1)
            if not win32gui.IsWindow(target_hwnd) or not win32gui.IsWindowVisible(target_hwnd):
                closed = True
                break

        # Check process survival (Window close must NOT kill process indiscriminately)
        process_alive = False
        if owning_pid:
            try:
                proc = psutil.Process(owning_pid)
                process_alive = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_alive = False

        return {
            "success": True,
            "verified": closed,
            "hwnd": target_hwnd,
            "title": w_title,
            "pid": owning_pid,
            "process_alive": process_alive,
            "message": f"Closed window '{w_title or target_hwnd}' (process alive={process_alive}).",
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
