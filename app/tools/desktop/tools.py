from typing import Any
from app.tools.base import Tool
from app.tools.desktop.executor import DesktopActionExecutor
from app.tools.desktop.models import SemanticActionRequest
from app.tools.desktop.ui_inspector import WindowsUIInspector


class InspectDesktopUITool(Tool):
    name = "inspect_desktop_ui"
    description = "Inspects the active application window, window title, and visible UI controls (buttons, inputs, tabs)."

    def __init__(self, inspector: WindowsUIInspector | None = None):
        self.inspector = inspector or WindowsUIInspector()

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "window_name": {
                    "type": "string",
                    "description": "Optional application or window title to inspect. If omitted, inspects active window.",
                }
            },
        }

    async def execute(self, window_name: str | None = None, **kwargs) -> dict[str, Any]:
        if window_name:
            ctx = self.inspector.find_window_context(window_name)
        else:
            ctx = self.inspector.get_active_window_context()

        if not ctx:
            return {"success": False, "error": "Could not locate active window or controls."}

        return {
            "success": True,
            "application": ctx.application,
            "window_title": ctx.window_title,
            "control_count": len(ctx.controls),
            "controls": [c.model_dump() for c in ctx.controls[:15]],
        }


class ClickUIElementTool(Tool):
    name = "click_ui_element"
    description = "Clicks or invokes a named button or interactive UI control in the active application window."

    def __init__(self, executor: DesktopActionExecutor | None = None):
        self.executor = executor or DesktopActionExecutor()

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target_name": {
                    "type": "string",
                    "description": "The visible text label, button name, or accessible name of the UI control to click.",
                },
                "control_type": {
                    "type": "string",
                    "description": "Optional type of control (e.g. 'button', 'tab', 'menu', 'checkbox'). Defaults to 'button'.",
                },
                "window_name": {
                    "type": "string",
                    "description": "Optional application or window title containing the control.",
                },
            },
            "required": ["target_name"],
        }

    async def execute(self, target_name: str, control_type: str = "button", window_name: str | None = None, **kwargs) -> dict[str, Any]:
        target_dict = {"name": target_name, "type": control_type}
        if window_name:
            target_dict["application"] = window_name
        req = SemanticActionRequest(
            action="click_element",
            target=target_dict,
        )
        res = await self.executor.execute_action(req)
        return res.model_dump()


class FocusWindowTool(Tool):
    name = "focus_desktop_window"
    description = "Brings a named application window to the foreground."

    def __init__(self, executor: DesktopActionExecutor | None = None):
        self.executor = executor or DesktopActionExecutor()

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "window_name": {
                    "type": "string",
                    "description": "Name of the application or title of the window to bring to the foreground (e.g. 'Notepad', 'Visual Studio Code').",
                }
            },
            "required": ["window_name"],
        }

    async def execute(self, window_name: str, **kwargs) -> dict[str, Any]:
        req = SemanticActionRequest(
            action="focus_window",
            target={"name": window_name},
        )
        res = await self.executor.execute_action(req)
        return res.model_dump()


class SetInputTextTool(Tool):
    name = "set_ui_input_text"
    description = "Enters text into an editable input or text field in the active application window."

    def __init__(self, executor: DesktopActionExecutor | None = None):
        self.executor = executor or DesktopActionExecutor()

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target_name": {
                    "type": "string",
                    "description": "Name, label, or placeholder of the input field.",
                },
                "text": {
                    "type": "string",
                    "description": "The text string to enter into the field.",
                },
                "window_name": {
                    "type": "string",
                    "description": "Optional application or window title containing the field.",
                },
            },
            "required": ["target_name", "text"],
        }

    async def execute(self, target_name: str, text: str, window_name: str | None = None, **kwargs) -> dict[str, Any]:
        target_dict = {"name": target_name, "type": "edit"}
        if window_name:
            target_dict["application"] = window_name
        req = SemanticActionRequest(
            action="set_input_text",
            target=target_dict,
            value=text,
        )
        res = await self.executor.execute_action(req)
        return res.model_dump()


class SelectTabTool(Tool):
    name = "select_ui_tab"
    description = "Selects a specific tab in the active application window."

    def __init__(self, executor: DesktopActionExecutor | None = None):
        self.executor = executor or DesktopActionExecutor()

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tab_name": {
                    "type": "string",
                    "description": "Name or title of the tab to switch to.",
                },
                "window_name": {
                    "type": "string",
                    "description": "Optional application or window title.",
                },
            },
            "required": ["tab_name"],
        }

    async def execute(self, tab_name: str, window_name: str | None = None, **kwargs) -> dict[str, Any]:
        target_dict = {"name": tab_name, "type": "tab"}
        if window_name:
            target_dict["application"] = window_name
        req = SemanticActionRequest(
            action="select_tab",
            target=target_dict,
        )
        res = await self.executor.execute_action(req)
        return res.model_dump()
