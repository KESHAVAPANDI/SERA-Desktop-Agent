import asyncio
import ctypes
import ctypes.wintypes
import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

# Windows Hotkey Modifier Constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312


def parse_hotkey(hotkey_str: str) -> tuple[int, int]:
    """Parses a hotkey string like 'ctrl+space' into (modifiers, vk_code)."""
    parts = [p.strip().lower() for p in hotkey_str.replace("<", "").replace(">", "").split("+")]

    modifiers = MOD_NOREPEAT
    vk_code = 0x20  # Default to Space (VK_SPACE)

    vk_map = {
        "space": 0x20,
        "enter": 0x0D,
        "return": 0x0D,
        "tab": 0x09,
        "esc": 0x1B,
        "escape": 0x1B,
        "backspace": 0x08,
        "f1": 0x70,
        "f2": 0x71,
        "f3": 0x72,
        "f4": 0x73,
        "f5": 0x74,
        "f6": 0x75,
        "f7": 0x76,
        "f8": 0x77,
        "f9": 0x78,
        "f10": 0x79,
        "f11": 0x7A,
        "f12": 0x7B,
    }

    for part in parts:
        if part in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif part in ("alt", "menu"):
            modifiers |= MOD_ALT
        elif part in ("shift",):
            modifiers |= MOD_SHIFT
        elif part in ("win", "windows", "super", "cmd"):
            modifiers |= MOD_WIN
        elif part in vk_map:
            vk_code = vk_map[part]
        elif len(part) == 1:
            char = part.upper()
            vk_code = ord(char)

    return modifiers, vk_code


class GlobalHotkeyManager:
    """Global keyboard hotkey manager for Windows using native RegisterHotKey API with debounce."""

    def __init__(
        self,
        hotkey: str = "ctrl+space",
        on_trigger: Callable[[], None] | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        debounce_ms: int = 300,
    ):
        self.hotkey_str = hotkey
        self.on_trigger = on_trigger
        self.loop = loop
        self.debounce_seconds = max(0.05, debounce_ms / 1000.0)
        self._last_trigger_time: float = 0.0
        self._trigger_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False
        self._hotkey_id = 101
        self._thread_id: int | None = None

    def trigger_manually(self) -> bool:
        """Triggers the hotkey callback directly if not debounced. Returns True if executed."""
        if not self.on_trigger:
            return False

        with self._trigger_lock:
            now = time.perf_counter()
            if (now - self._last_trigger_time) < self.debounce_seconds:
                logger.debug(f"[GlobalHotkeyManager] Hotkey trigger ignored (debounced: {(now - self._last_trigger_time)*1000:.1f}ms < {self.debounce_seconds*1000:.0f}ms).")
                return False
            self._last_trigger_time = now

        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.on_trigger)
        else:
            try:
                self.on_trigger()
            except Exception as e:
                logger.error(f"[GlobalHotkeyManager] Error in manual trigger callback: {e}")
        return True

    def start(self) -> None:
        """Starts the global hotkey listener thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_listener, daemon=True, name="SERA-Hotkey-Listener")
        self._thread.start()

    def stop(self) -> None:
        """Stops the hotkey listener thread and unregisters the hotkey."""
        self._running = False
        if self._thread_id:
            # Post WM_QUIT to exit GetMessage loop
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run_listener(self) -> None:
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        modifiers, vk = parse_hotkey(self.hotkey_str)

        user32 = ctypes.windll.user32
        success = user32.RegisterHotKey(None, self._hotkey_id, modifiers, vk)

        if not success:
            logger.warning(
                f"[GlobalHotkeyManager] Could not register hotkey '{self.hotkey_str}' (it may be in use by another app)."
            )
        else:
            logger.info(f"[GlobalHotkeyManager] Global hotkey '{self.hotkey_str}' registered successfully.")

        try:
            msg = ctypes.wintypes.MSG()
            while self._running:
                # GetMessage blocks until a window message arrives
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res == 0 or res == -1:  # WM_QUIT or Error
                    break

                if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                    self.trigger_manually()

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        finally:
            user32.UnregisterHotKey(None, self._hotkey_id)
            logger.info("[GlobalHotkeyManager] Global hotkey unregistered.")
