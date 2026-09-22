import asyncio
import ctypes
import logging
import threading
import time
from typing import Callable

from app.speech.audio_cues import get_audio_cues

logger = logging.getLogger(__name__)

# Virtual Key Codes
VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_MENU = 0x12       # Alt
VK_LMENU = 0xA4      # Left Alt
VK_RMENU = 0xA5      # Right Alt
VK_SPACE = 0x20
VK_SHIFT = 0x10


class GlobalHotkeyManager:
    """Windows Hold-To-Talk global keyboard manager with millisecond-accurate KeyDown and KeyUp detection."""

    def __init__(
        self,
        hotkey: str = "ctrl+alt+space",
        on_press: Callable[[], None] | None = None,
        on_release: Callable[[], None] | None = None,
        on_trigger: Callable[[], None] | None = None,  # Backward compatibility
        loop: asyncio.AbstractEventLoop | None = None,
        poll_interval_ms: float = 5.0,
        debounce_ms: int = 300,
    ):
        self.hotkey_str = hotkey.lower()
        self.has_alt = "alt" in self.hotkey_str
        self.has_ctrl = "ctrl" in self.hotkey_str or "control" in self.hotkey_str
        self.has_space = "space" in self.hotkey_str
        self.on_press = on_press or on_trigger
        self.on_release = on_release
        self.loop = loop
        self.poll_interval = max(0.005, poll_interval_ms / 1000.0)
        self.debounce_ms = debounce_ms

        self._running = False
        self._is_held = False
        self._last_trigger_time: float | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._audio_cues = get_audio_cues(enabled=True)

    @property
    def is_held(self) -> bool:
        """Returns True if the hotkey is currently held down."""
        return self._is_held

    def trigger_manually(self) -> bool:
        """Triggers manual hotkey invocation with debounce for testing."""
        now = time.monotonic()
        debounce_sec = self.debounce_ms / 1000.0
        if self._last_trigger_time is not None and (now - self._last_trigger_time) < debounce_sec:
            logger.debug(f"[GlobalHotkeyManager] Hotkey debounced ({now - self._last_trigger_time:.3f}s < {debounce_sec:.3f}s)")
            return False

        self._last_trigger_time = now
        if self.on_press:
            self._dispatch(self.on_press)
        return True

    def trigger_press(self) -> bool:
        """Manually triggers KeyDown (Hold-to-Talk begin)."""
        with self._lock:
            if self._is_held:
                return False
            self._is_held = True

        self._audio_cues.play_listening_cue()
        self._dispatch(self.on_press)
        return True

    def trigger_release(self) -> bool:
        """Manually triggers KeyUp (Hold-to-Talk release)."""
        with self._lock:
            if not self._is_held:
                return False
            self._is_held = False

        self._audio_cues.play_thinking_cue()
        self._dispatch(self.on_release)
        return True

    def start(self) -> None:
        """Starts the global hold-to-talk listener thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_poll_loop,
            daemon=True,
            name="SERA-HoldToTalk-Listener",
        )
        self._thread.start()
        logger.info(f"[GlobalHotkeyManager] Hold-To-Talk listener started for '{self.hotkey_str}'.")

    def stop(self) -> None:
        """Stops the hold-to-talk listener thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        logger.info("[GlobalHotkeyManager] Hold-To-Talk listener stopped.")

    def _dispatch(self, callback: Callable[[], None] | None) -> None:
        if not callback:
            return

        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(callback)
        else:
            try:
                callback()
            except Exception as e:
                logger.error(f"[GlobalHotkeyManager] Error executing callback: {e}")

    def _run_poll_loop(self) -> None:
        user32 = ctypes.windll.user32

        # Ensure listener thread is attached to the active interactive input desktop
        try:
            h_desk = user32.OpenInputDesktop(0, False, 0x01FF)
            if h_desk:
                user32.SetThreadDesktop(h_desk)
        except Exception as e:
            logger.debug(f"[GlobalHotkeyManager] Desktop attach note: {e}")

        get_async_key_state = user32.GetAsyncKeyState

        # Flush initial key state to clear any stale pressed bits before starting detection
        get_async_key_state(VK_CONTROL)
        get_async_key_state(VK_LCONTROL)
        get_async_key_state(VK_RCONTROL)
        get_async_key_state(VK_MENU)
        get_async_key_state(VK_LMENU)
        get_async_key_state(VK_RMENU)
        get_async_key_state(VK_SPACE)

        combo_label = self.hotkey_str.upper()

        while self._running:
            try:
                # 0x8000 indicates key is currently pressed down
                ctrl_down = bool(
                    get_async_key_state(VK_CONTROL) & 0x8000
                    or get_async_key_state(VK_LCONTROL) & 0x8000
                    or get_async_key_state(VK_RCONTROL) & 0x8000
                )
                alt_down = bool(
                    get_async_key_state(VK_MENU) & 0x8000
                    or get_async_key_state(VK_LMENU) & 0x8000
                    or get_async_key_state(VK_RMENU) & 0x8000
                )
                space_down = bool(get_async_key_state(VK_SPACE) & 0x8000)

                if self.has_alt:
                    is_combo_down = ctrl_down and alt_down and space_down
                else:
                    is_combo_down = ctrl_down and space_down

                if is_combo_down and not self._is_held:
                    # Key Down Event
                    with self._lock:
                        self._is_held = True
                    logger.info(f"[GlobalHotkeyManager] Hotkey {combo_label} PRESSED (Hold-To-Talk).")
                    self._audio_cues.play_listening_cue()
                    self._dispatch(self.on_press)

                elif not is_combo_down and self._is_held:
                    # Key Up Event
                    with self._lock:
                        self._is_held = False
                    logger.info(f"[GlobalHotkeyManager] Hotkey {combo_label} RELEASED (Stop recording).")
                    self._audio_cues.play_thinking_cue()
                    self._dispatch(self.on_release)

            except Exception as e:
                logger.debug(f"[GlobalHotkeyManager] Error in poll loop: {e}")

            time.sleep(self.poll_interval)
