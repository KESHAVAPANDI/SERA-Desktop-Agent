from app.tools.registry import ToolRegistry

from app.tools.windows.apps import (
    OpenApplicationTool,
    OpenFolderTool,
    OpenFileTool,
    CloseApplicationTool,
    ListRunningApplicationsTool,
)

from app.tools.windows.system import (
    GetSystemInfoTool,
    GetBatteryStatusTool,
    GetCurrentTimeTool,
    GetWiFiStatusTool,
)
from app.tools.windows.self_close import SeraSelfCloseTool

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
    LockComputerTool,
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

from app.tools.filesystem.files import (
    FindFilesTool,
    CreateFolderTool,
    CreateFileTool,
)
from app.tools.browser.web_search import WebSearchTool
from app.tools.browser.browser import (
    BrowserTool,
    CloseBrowserTabTool,
    FocusBrowserTabTool,
    OpenNewTabTool,
    ReadWebPageTool,
)
from app.tools.browser.youtube import YouTubeSearchTool
from app.tools.screen.capture import ScreenCaptureTool
from app.tools.screen.vision import AnalyzeScreenTool, InspectScreenTool


def create_tool_registry():
    registry = ToolRegistry()

    # Applications, Folders, Files
    registry.register(OpenApplicationTool())
    registry.register(OpenFolderTool())
    registry.register(OpenFileTool())
    registry.register(CloseApplicationTool())
    registry.register(ListRunningApplicationsTool())
    registry.register(FindFilesTool())
    registry.register(CreateFolderTool())
    registry.register(CreateFileTool())

    # Web & Browser
    registry.register(WebSearchTool())
    registry.register(BrowserTool())
    registry.register(OpenNewTabTool())
    registry.register(CloseBrowserTabTool())
    registry.register(FocusBrowserTabTool())
    registry.register(ReadWebPageTool())
    registry.register(YouTubeSearchTool())

    # Screen Capture & Vision
    registry.register(ScreenCaptureTool())
    registry.register(AnalyzeScreenTool())
    registry.register(InspectScreenTool())

    # System & Diagnostics
    registry.register(GetSystemInfoTool())
    registry.register(GetBatteryStatusTool())
    registry.register(GetCurrentTimeTool())
    registry.register(GetWiFiStatusTool())
    registry.register(SeraSelfCloseTool())

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
    registry.register(LockComputerTool())
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