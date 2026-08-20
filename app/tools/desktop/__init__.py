from app.tools.desktop.models import (
    NativeUIControl,
    NativeWindowContext,
    SemanticActionRequest,
    SemanticActionResult,
)
from app.tools.desktop.ui_inspector import WindowsUIInspector
from app.tools.desktop.target_resolver import TargetResolver, ResolutionResult
from app.tools.desktop.matcher import SemanticTargetMatcher
from app.tools.desktop.executor import DesktopActionExecutor

__all__ = [
    "NativeUIControl",
    "NativeWindowContext",
    "SemanticActionRequest",
    "SemanticActionResult",
    "WindowsUIInspector",
    "TargetResolver",
    "ResolutionResult",
    "SemanticTargetMatcher",
    "DesktopActionExecutor",
]
