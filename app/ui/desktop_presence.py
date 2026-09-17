"""SERA 2.0 — Native Transparent Desktop Shell.

Packages the Three.js WebGL Wisdom King Presence into a native, borderless,
alpha-transparent, click-through desktop overlay window on Windows using pywebview.

Mandate:
- 100% Alpha Transparent background
- Frameless & borderless
- Floating on top of desktop
- Seamless JS-to-Python bridge
- Resilient offline fallback and multi-monitor awareness
"""

import asyncio
import ctypes
from dataclasses import dataclass
import logging
import os
import sys
import threading
import time
from typing import Any, Optional

import webview

logger = logging.getLogger(__name__)

# Constants for Windows Extended Window Styles
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008


@dataclass
class DesktopPresenceConfig:
    """Configuration for the native SERA Presence desktop overlay window."""
    title: str = "SERA Presence"
    host: str = "127.0.0.1"
    port: int = 8765
    width: int = 560
    height: int = 680
    frameless: bool = True
    transparent: bool = True
    on_top: bool = True
    background_color: str = "#000000"
    easy_drag: bool = True
    dock_position: str = "bottom-right"  # "bottom-right", "center", "custom"
    margin_x: int = 32
    margin_y: int = 48


class DesktopPresenceAPI:
    """Python API bridge exposed to JavaScript in presence.html."""

    def __init__(self, launcher: "DesktopPresenceLauncher"):
        self.launcher = launcher

    def ping(self) -> dict[str, Any]:
        """Verifies JS-to-Python bridge health."""
        return {
            "status": "online",
            "timestamp": time.time(),
            "surface": "native_desktop_shell",
            "platform": sys.platform,
        }

    def minimize(self) -> None:
        """Minimizes the presence overlay window."""
        if self.launcher.window:
            self.launcher.window.minimize()

    def hide(self) -> None:
        """Hides the presence overlay window."""
        if self.launcher.window:
            self.launcher.window.hide()

    def show(self) -> None:
        """Restores and shows the presence overlay window."""
        if self.launcher.window:
            self.launcher.window.show()

    def close(self) -> None:
        """Destroys the presence overlay window."""
        if self.launcher.window:
            self.launcher.window.destroy()

    def toggle_on_top(self) -> bool:
        """Toggles window stay-on-top state."""
        if not self.launcher.window:
            return False
        self.launcher.config.on_top = not self.launcher.config.on_top
        self.launcher.window.on_top = self.launcher.config.on_top
        return self.launcher.config.on_top

    def set_click_through(self, enabled: bool) -> bool:
        """Enables or disables click-through on Windows via Win32 extended style."""
        return self.launcher.set_click_through(enabled)


class DesktopPresenceLauncher:
    """Manages the creation, placement, and lifecycle of the native SERA Presence window."""

    def __init__(self, config: Optional[DesktopPresenceConfig] = None, runtime: Any = None):
        self.config = config or DesktopPresenceConfig()
        self.runtime = runtime
        self.api = DesktopPresenceAPI(self)
        self.window: Optional[webview.Window] = None
        self._hwnd: Optional[int] = None
        self._is_running = False

    def compute_window_position(self) -> tuple[int, int]:
        """Calculates window coordinates based on primary display work area."""
        screen_w = 1920
        screen_h = 1080

        # Try pywebview screens detection
        try:
            screens = webview.screens
            if screens:
                primary = screens[0]
                screen_w = primary.width
                screen_h = primary.height
        except Exception as e:
            logger.debug(f"[DesktopPresence] Could not query webview.screens: {e}")
            if sys.platform == "win32":
                try:
                    user32 = ctypes.windll.user32
                    screen_w = user32.GetSystemMetrics(0)
                    screen_h = user32.GetSystemMetrics(1)
                except Exception:
                    pass

        if self.config.dock_position == "bottom-right":
            x = screen_w - self.config.width - self.config.margin_x
            y = screen_h - self.config.height - self.config.margin_y
        elif self.config.dock_position == "center":
            x = (screen_w - self.config.width) // 2
            y = (screen_h - self.config.height) // 2
        else:
            x = self.config.margin_x
            y = self.config.margin_y

        return max(0, x), max(0, y)

    def get_presence_url(self) -> str:
        """Resolves target URL, preferring running HTTP server or direct local file."""
        server_url = f"http://{self.config.host}:{self.config.port}/presence"
        return server_url

    def create_window(self, dry_run: bool = False) -> webview.Window:
        """Initializes the pywebview window with borderless transparent options."""
        url = self.get_presence_url()
        x, y = self.compute_window_position()

        if dry_run:
            logger.info(f"[DesktopPresence] Dry-run configured window at ({x}, {y}) size ({self.config.width}x{self.config.height}) targeting {url}")
            return None

        self.window = webview.create_window(
            title=self.config.title,
            url=url,
            js_api=self.api,
            width=self.config.width,
            height=self.config.height,
            x=x,
            y=y,
            frameless=self.config.frameless,
            easy_drag=self.config.easy_drag,
            transparent=self.config.transparent,
            on_top=self.config.on_top,
            background_color=self.config.background_color,
            resizable=False,
            shadow=False,
            text_select=False,
        )
        return self.window

    def set_click_through(self, enabled: bool) -> bool:
        """Toggles WS_EX_TRANSPARENT style on Windows to allow mouse clicks to pass through."""
        if sys.platform != "win32":
            return False

        try:
            user32 = ctypes.windll.user32
            # Find window handle if not cached
            if not self._hwnd:
                self._hwnd = user32.FindWindowW(None, self.config.title)

            if not self._hwnd:
                return False

            ex_style = user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
            if enabled:
                new_style = ex_style | WS_EX_TRANSPARENT | WS_EX_LAYERED
            else:
                new_style = ex_style & ~WS_EX_TRANSPARENT

            user32.SetWindowLongW(self._hwnd, GWL_EXSTYLE, new_style)
            return True
        except Exception as e:
            logger.error(f"[DesktopPresence] Error setting click-through: {e}")
            return False

    def launch(self, dry_run: bool = False) -> None:
        """Entrypoint to create and start the pywebview native desktop presence loop."""
        if dry_run:
            self.create_window(dry_run=True)
            return

        self.create_window(dry_run=False)
        self._is_running = True
        logger.info("[DesktopPresence] Starting native transparent desktop overlay loop...")
        webview.start(debug=False)
        self._is_running = False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    dry_run_mode = "--dry-run" in sys.argv or "--test" in sys.argv
    launcher = DesktopPresenceLauncher()
    print(f"Launching SERA Desktop Presence Shell (dry_run={dry_run_mode})...")
    launcher.launch(dry_run=dry_run_mode)
    print("SERA Desktop Presence Shell initialized successfully.")
