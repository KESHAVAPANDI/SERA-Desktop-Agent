import logging
import time
from typing import Any
import psutil
import win32gui
import win32process
import uiautomation as auto

from app.tools.desktop.models import NativeUIControl, NativeWindowContext

logger = logging.getLogger(__name__)


def simplify_control_type(control_type_name: str) -> str:
    """Converts verbose UIA ControlTypeName into normalized simplified type."""
    mapping = {
        "ButtonControl": "button",
        "EditControl": "edit",
        "TextControl": "text",
        "CheckBoxControl": "checkbox",
        "RadioButtonControl": "radio",
        "TabItemControl": "tab",
        "TabControl": "tab",
        "MenuItemControl": "menu",
        "MenuControl": "menu",
        "ListItemControl": "list_item",
        "ListControl": "list",
        "ComboBoxControl": "combobox",
        "HyperlinkControl": "link",
        "WindowControl": "window",
        "PaneControl": "pane",
        "ToolBarControl": "toolbar",
        "StatusBarControl": "statusbar",
        "TreeItemControl": "tree_item",
        "SliderControl": "slider",
        "DocumentControl": "edit",
        "SplitButtonControl": "button",
        "GroupControl": "group",
        "CustomControl": "custom",
    }
    return mapping.get(control_type_name, "control")


class WindowsUIInspector:
    """Inspects native Windows applications and UI Automation control hierarchies."""

    def __init__(self):
        pass

    def get_active_window_context(self, max_depth: int = 5) -> NativeWindowContext | None:
        """Inspects the foreground active window and its full child control hierarchy."""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or hwnd == 0:
            top_windows = self.get_all_windows_summary()
            if top_windows:
                return self.inspect_window_by_hwnd(top_windows[0][0], max_depth=max_depth)
            return None

        return self.inspect_window_by_hwnd(hwnd, max_depth=max_depth)

    def find_window_context(self, query: str, max_depth: int = 5) -> NativeWindowContext | None:
        """Finds a window by application name or title and inspects its full child control tree."""
        query_lower = query.lower().strip()
        all_windows = self.get_all_windows_summary()

        # 1. Match by HWND list and inspect matched window
        for hwnd, app_name, title in all_windows:
            if query_lower in app_name.lower() or query_lower in title.lower():
                ctx = self.inspect_window_by_hwnd(hwnd, max_depth=max_depth)
                if ctx and (ctx.controls or ctx.window_title):
                    return ctx

        # 2. Fallback search via UIA WindowControl directly
        try:
            uia_win = auto.WindowControl(searchDepth=2, SubName=query)
            if not uia_win.Exists(0.5, 0.2):
                uia_win = auto.WindowControl(searchDepth=2, ClassName=query)

            if uia_win.Exists(0, 0):
                return self._inspect_uia_control(uia_win, max_depth=max_depth)
        except Exception as e:
            logger.debug(f"[UIInspector] UIA direct search fallback error: {e}")

        return None

    def get_all_windows_summary(self) -> list[tuple[int, str, str]]:
        """Enumerates visible top-level windows returning list of (hwnd, app_name, title)."""
        summaries: list[tuple[int, str, str]] = []

        def enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title and title not in ("Default IME", "MSCTFIME UI", "Program Manager"):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    app_name = "Unknown"
                    try:
                        app_name = psutil.Process(pid).name().replace(".exe", "")
                    except Exception:
                        pass
                    summaries.append((hwnd, app_name, title))

        try:
            win32gui.EnumWindows(enum_cb, None)
        except Exception as e:
            logger.debug(f"[UIInspector] EnumWindows error: {e}")

        return summaries

    def inspect_window_by_hwnd(self, hwnd: int, max_depth: int = 5) -> NativeWindowContext | None:
        """Inspects a specific window handle, attaching UIA to extract all child controls."""
        try:
            title = win32gui.GetWindowText(hwnd).strip()
            cls_name = win32gui.GetClassName(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            app_name = "Unknown"
            try:
                app_name = psutil.Process(pid).name().replace(".exe", "")
            except Exception:
                pass

            # Attach UI Automation control from HWND
            control = auto.ControlFromHandle(hwnd)
            controls = self._extract_controls(control, max_depth=max_depth) if control else []

            return NativeWindowContext(
                application=app_name,
                process_id=pid,
                window_title=title,
                class_name=cls_name,
                is_active=True,
                controls=controls,
                timestamp=time.time(),
            )
        except Exception as e:
            logger.error(f"[UIInspector] Error inspecting HWND {hwnd}: {e}")
            return None

    def _inspect_uia_control(self, uia_control, max_depth: int = 5) -> NativeWindowContext:
        title = uia_control.Name or ""
        cls_name = uia_control.ClassName or ""
        pid = getattr(uia_control, "ProcessId", None)
        app_name = "Unknown"
        if pid:
            try:
                app_name = psutil.Process(pid).name().replace(".exe", "")
            except Exception:
                pass

        controls = self._extract_controls(uia_control, max_depth=max_depth)
        return NativeWindowContext(
            application=app_name,
            process_id=pid,
            window_title=title,
            class_name=cls_name,
            is_active=True,
            controls=controls,
            timestamp=time.time(),
        )

    def _extract_controls(self, root_control, max_depth: int = 5) -> list[NativeUIControl]:
        """Recursively extracts UI controls up to max_depth with full control attributes."""
        extracted: list[NativeUIControl] = []
        control_id_counter = 0

        def traverse(ctrl, current_depth: int):
            nonlocal control_id_counter
            if current_depth > max_depth or not ctrl:
                return

            try:
                name = ctrl.Name or ""
                ctrl_type = ctrl.ControlTypeName
                simplified_type = simplify_control_type(ctrl_type)
                rect = ctrl.BoundingRectangle
                auto_id = ctrl.AutomationId or ""

                # Extract buttons, edits, tabs, checkboxes, menus, lists, texts, items
                is_interactive = simplified_type in (
                    "button", "edit", "tab", "checkbox", "radio",
                    "menu", "list", "combobox", "link", "tree_item", "slider"
                )
                has_label = bool(name and len(name.strip()) > 0)

                if is_interactive or has_label:
                    control_id_counter += 1
                    bounds_dict = {
                        "x": rect.left if rect else 0,
                        "y": rect.top if rect else 0,
                        "width": (rect.right - rect.left) if rect else 0,
                        "height": (rect.bottom - rect.top) if rect else 0,
                    }

                    extracted.append(
                        NativeUIControl(
                            id=f"ctrl_{control_id_counter}",
                            name=name,
                            type=simplified_type,
                            control_type_name=ctrl_type,
                            class_name=ctrl.ClassName or "",
                            automation_id=auto_id,
                            enabled=ctrl.IsEnabled,
                            visible=True,
                            focused=ctrl.HasKeyboardFocus,
                            bounds=bounds_dict,
                            patterns=[],
                        )
                    )

                for child in ctrl.GetChildren():
                    traverse(child, current_depth + 1)

            except Exception:
                pass

        traverse(root_control, 1)
        return extracted
