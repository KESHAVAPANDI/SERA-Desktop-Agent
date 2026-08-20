from typing import Any
from pydantic import BaseModel, Field


class NativeUIControl(BaseModel):
    """Represents a structured Windows UI Automation element."""
    id: str = Field(description="Stable local identifier for the control")
    name: str = Field(default="", description="Name, text label, or accessibility name")
    type: str = Field(default="control", description="Simplified control type: button, edit, tab, checkbox, menu, list, text, window")
    control_type_name: str = Field(default="", description="Native UI Automation ControlTypeName")
    class_name: str | None = Field(default=None, description="Win32 window/control class name")
    automation_id: str | None = Field(default=None, description="Developer automation identifier")
    enabled: bool = Field(default=True, description="Whether control is interactable/enabled")
    visible: bool = Field(default=True, description="Whether control is visible on screen")
    focused: bool = Field(default=False, description="Whether control currently has keyboard focus")
    bounds: dict[str, int] = Field(default_factory=dict, description="Bounding rectangle {x, y, width, height}")
    patterns: list[str] = Field(default_factory=list, description="Supported UI Automation patterns (e.g. Invoke, Value, Toggle)")


class NativeWindowContext(BaseModel):
    """Structured perception data describing the active window and its control tree."""
    application: str = Field(default="Unknown", description="Name of the application process")
    process_id: int | None = Field(default=None, description="Process ID (PID)")
    window_title: str = Field(default="", description="Title bar text of the window")
    class_name: str | None = Field(default=None, description="Window class name")
    is_active: bool = Field(default=True, description="Whether window is the foreground active window")
    controls: list[NativeUIControl] = Field(default_factory=list, description="Interactive and visible UI controls")
    timestamp: float = Field(default=0.0, description="Timestamp of inspection")


class SemanticActionRequest(BaseModel):
    """Structured semantic action request from LLM / agent."""
    action: str = Field(description="Action name: click_element, invoke_button, focus_window, set_input_text, select_tab, scroll_container")
    target: dict[str, Any] = Field(description="Target specification, e.g. {'name': 'Run', 'type': 'button'} or {'name': 'Notepad'}")
    value: str | None = Field(default=None, description="Optional text input or parameter value")


class SemanticActionResult(BaseModel):
    """Structured result of a semantic action after observation and verification."""
    success: bool = Field(description="Whether action executed and verified successfully")
    action: str = Field(description="Action that was attempted")
    target: str = Field(description="Human-readable description of target element")
    verified: bool = Field(description="Whether post-action UI state verification succeeded")
    verification_method: str = Field(default="ui_state_change", description="Method used to verify result")
    message: str = Field(description="User-facing summary message")
    reason: str | None = Field(default=None, description="Failure reason or diagnostics if failed")
