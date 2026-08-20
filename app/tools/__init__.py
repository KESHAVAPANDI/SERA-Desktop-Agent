from app.tools.registry import ToolRegistry

from app.tools.windows.apps import (
    OpenApplicationTool,
    CloseApplicationTool,
    ListRunningApplicationsTool,
)

from app.tools.windows.system import (
    GetSystemInfoTool,
    GetBatteryStatusTool,
    GetCurrentTimeTool,
    GetWiFiStatusTool,
)

from app.tools.windows.audio import (
    GetVolumeTool,
    SetVolumeTool,
    MuteTool,
    UnmuteTool,
)

from app.tools.windows.display import (
    GetBrightnessTool,
    SetBrightnessTool,
)

from app.tools.windows.power import (
    LockScreenTool,
    SleepPCTool,
    RestartPCTool,
    ShutdownPCTool,
)

from app.tools.desktop.tools import (
    InspectDesktopUITool,
    ClickUIElementTool,
    FocusWindowTool,
    SetInputTextTool,
    SelectTabTool,
)


def create_tool_registry():
    registry = ToolRegistry()

    # Applications
    registry.register(OpenApplicationTool())
    registry.register(CloseApplicationTool())
    registry.register(ListRunningApplicationsTool())

    # System & Diagnostics
    registry.register(GetSystemInfoTool())
    registry.register(GetBatteryStatusTool())
    registry.register(GetCurrentTimeTool())
    registry.register(GetWiFiStatusTool())

    # Audio Controls
    registry.register(GetVolumeTool())
    registry.register(SetVolumeTool())
    registry.register(MuteTool())
    registry.register(UnmuteTool())

    # Display Controls
    registry.register(GetBrightnessTool())
    registry.register(SetBrightnessTool())

    # Power Controls (with safety confirmations where needed)
    registry.register(LockScreenTool())
    registry.register(SleepPCTool())
    registry.register(RestartPCTool())
    registry.register(ShutdownPCTool())

    # Semantic Desktop UI Automation
    registry.register(InspectDesktopUITool())
    registry.register(ClickUIElementTool())
    registry.register(FocusWindowTool())
    registry.register(SetInputTextTool())
    registry.register(SelectTabTool())

    return registry