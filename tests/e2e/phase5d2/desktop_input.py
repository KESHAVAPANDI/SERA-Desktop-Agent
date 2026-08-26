import ctypes
import time
import sys

VK_CONTROL = 0x11
VK_SPACE = 0x20
KEYEVENTF_KEYUP = 0x0002

user32 = ctypes.windll.user32 if sys.platform == "win32" else None

def send_ctrl_space_down():
    if user32:
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_SPACE, 0, 0, 0)

def send_ctrl_space_up():
    if user32:
        user32.keybd_event(VK_SPACE, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

def press_and_hold_ctrl_space(duration_seconds: float = 1.0):
    send_ctrl_space_down()
    time.sleep(duration_seconds)
    send_ctrl_space_up()
