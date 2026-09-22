"""SERA 2.0 — Focused Global Hotkey Authority Test Suite
Proves that an actual physical/injected Windows OS keypress (Ctrl+Alt+Space)
is accurately detected and reaches the SERA runtime on the FIRST press.
"""

import ctypes
import os
import sys
import time
import unittest
from unittest.mock import MagicMock

# Attach main test process/thread to the interactive input desktop before any windows are created
user32 = ctypes.windll.user32
try:
    h_desk = user32.OpenInputDesktop(0, False, 0x01FF)
    if h_desk:
        user32.SetThreadDesktop(h_desk)
except Exception:
    pass

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.hotkey import GlobalHotkeyManager, VK_CONTROL, VK_MENU, VK_SPACE
from app.core.events import EventBus
from app.core.runtime import SERARuntime


# Pre-compute scancodes for hardware key injection
SCAN_CTRL = user32.MapVirtualKeyW(VK_CONTROL, 0)
SCAN_MENU = user32.MapVirtualKeyW(VK_MENU, 0)
SCAN_SPACE = user32.MapVirtualKeyW(VK_SPACE, 0)
KEYEVENTF_KEYUP = 0x0002


def inject_key_down(vk_code: int, scan: int):
    user32.keybd_event(vk_code, scan, 0, 0)


def inject_key_up(vk_code: int, scan: int):
    user32.keybd_event(vk_code, scan, KEYEVENTF_KEYUP, 0)


def release_all_test_keys():
    """Ensure no test keys remain pressed in the OS keyboard buffer."""
    inject_key_up(VK_SPACE, SCAN_SPACE)
    inject_key_up(VK_MENU, SCAN_MENU)
    inject_key_up(VK_CONTROL, SCAN_CTRL)


class TestHotkeyAuthority(unittest.TestCase):

    def setUp(self):
        release_all_test_keys()
        time.sleep(0.05)

    def tearDown(self):
        release_all_test_keys()
        time.sleep(0.05)

    def test_global_hotkey_manager_real_keypress_activation(self):
        """Proves that a real OS keypress (Ctrl+Alt+Space) triggers on_press and on_release."""
        pressed_events = []
        released_events = []

        mgr = GlobalHotkeyManager(
            hotkey="ctrl+alt+space",
            on_press=lambda: pressed_events.append(time.time()),
            on_release=lambda: released_events.append(time.time()),
            poll_interval_ms=5.0,
        )

        mgr.start()
        self.assertTrue(mgr._running, "Hotkey manager must be in running state")
        self.assertIsNotNone(mgr._thread, "Listener thread must exist")
        self.assertTrue(mgr._thread.is_alive(), "Listener thread must be actively running")

        try:
            # Let listener poll loop settle
            time.sleep(0.08)
            self.assertFalse(mgr.is_held, "Must not start in held state")

            # 1. INJECT PHYSICAL KEY DOWN: Ctrl + Alt + Space
            inject_key_down(VK_CONTROL, SCAN_CTRL)
            inject_key_down(VK_MENU, SCAN_MENU)
            inject_key_down(VK_SPACE, SCAN_SPACE)

            # Wait for poll cycle
            time.sleep(0.2)
            self.assertTrue(mgr.is_held, "Manager must detect combo held on first press")
            self.assertGreaterEqual(len(pressed_events), 1, "on_press must be invoked on first physical keypress")

            # 2. INJECT PHYSICAL KEY UP: Space released
            inject_key_up(VK_SPACE, SCAN_SPACE)
            inject_key_up(VK_MENU, SCAN_MENU)
            inject_key_up(VK_CONTROL, SCAN_CTRL)

            time.sleep(0.1)
            self.assertFalse(mgr.is_held, "Manager must detect combo released")
            self.assertGreaterEqual(len(released_events), 1, "on_release must be invoked on release")

        finally:
            mgr.stop()
            self.assertFalse(mgr._running)

    def test_runtime_hotkey_authority_event_flow(self):
        """Proves that physical Ctrl+Alt+Space triggers SERARuntime activation events."""
        mock_audio = MagicMock()
        mock_stt = MagicMock()
        event_bus = EventBus()

        events_received = []
        event_bus.subscribe("ACTIVATION_STARTED", lambda d: events_received.append(("STARTED", d)))
        event_bus.subscribe("ACTIVATION_RELEASED", lambda d: events_received.append(("RELEASED", d)))

        runtime = SERARuntime(
            audio_manager=mock_audio,
            stt_pipeline=mock_stt,
            event_bus=event_bus,
        )
        runtime.recorder = MagicMock()

        # Verify combination is configured to ctrl+alt+space
        self.assertEqual(runtime.hotkey_manager.hotkey_str, "ctrl+alt+space")

        # Start hotkey listener
        runtime.hotkey_manager.start()
        self.assertTrue(runtime.hotkey_manager._thread.is_alive())

        try:
            time.sleep(0.08)
            self.assertEqual(runtime.hotkey_event_count, 0)

            # Inject FIRST PRESS
            inject_key_down(VK_CONTROL, SCAN_CTRL)
            inject_key_down(VK_MENU, SCAN_MENU)
            inject_key_down(VK_SPACE, SCAN_SPACE)

            time.sleep(0.25)
            self.assertEqual(runtime.hotkey_event_count, 1, "Runtime must register first hotkey event")
            self.assertTrue(any(ev[0] == "STARTED" for ev in events_received), "ACTIVATION_STARTED event must be emitted")

            # Inject RELEASE
            inject_key_up(VK_SPACE, SCAN_SPACE)
            inject_key_up(VK_MENU, SCAN_MENU)
            inject_key_up(VK_CONTROL, SCAN_CTRL)

            time.sleep(0.1)
            self.assertTrue(any(ev[0] == "RELEASED" for ev in events_received), "ACTIVATION_RELEASED event must be emitted")

        finally:
            runtime.hotkey_manager.stop()

    def test_backward_compatibility_ctrl_space(self):
        """Proves that GlobalHotkeyManager still supports legacy Ctrl+Space if explicitly configured."""
        pressed = []
        mgr = GlobalHotkeyManager(
            hotkey="ctrl+space",
            on_press=lambda: pressed.append(1),
            poll_interval_ms=5.0,
        )
        self.assertFalse(mgr.has_alt)
        mgr.start()
        try:
            time.sleep(0.08)
            inject_key_down(VK_CONTROL, SCAN_CTRL)
            inject_key_down(VK_SPACE, SCAN_SPACE)
            time.sleep(0.2)
            self.assertTrue(mgr.is_held)
            self.assertGreaterEqual(len(pressed), 1)

            inject_key_up(VK_SPACE, SCAN_SPACE)
            inject_key_up(VK_CONTROL, SCAN_CTRL)
            time.sleep(0.08)
            self.assertFalse(mgr.is_held)
        finally:
            mgr.stop()


if __name__ == "__main__":
    unittest.main()
