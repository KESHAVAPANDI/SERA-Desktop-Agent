from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Capability:
    """Defines a data-driven capability exposed dynamically to the human-facing SERA Live interface."""
    id: str
    label: str
    description: str
    icon: str
    category: str  # perception | web | desktop | system | knowledge
    tool_name: str
    action_type: str = "prompt"  # prompt | direct_tool
    risk_level: str = "safe"  # safe | confirmation_required
    required_permissions: list[str] = field(default_factory=list)
    show_when: list[str] = field(default_factory=lambda: ["IDLE", "ALWAYS"])
    prompt_template: str = ""
    priority: int = 50

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "tool_name": self.tool_name,
            "action_type": self.action_type,
            "risk_level": self.risk_level,
            "required_permissions": self.required_permissions,
            "show_when": self.show_when,
            "prompt_template": self.prompt_template or self.label,
            "priority": self.priority,
        }


class CapabilityRegistry:
    """Registry that manages and serves contextual capabilities for the Live UI."""

    def __init__(self):
        self._capabilities: dict[str, Capability] = {}
        self._register_default_capabilities()

    def register(self, capability: Capability):
        """Registers or updates a capability in the registry."""
        self._capabilities[capability.id] = capability

    def get(self, capability_id: str) -> Optional[Capability]:
        """Retrieves a capability by ID."""
        return self._capabilities.get(capability_id)

    def list_all(self) -> list[dict[str, Any]]:
        """Returns all registered capabilities as dictionaries."""
        return [c.to_dict() for c in sorted(self._capabilities.values(), key=lambda x: x.priority, reverse=True)]

    def get_contextual_capabilities(self, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Filters capabilities based on current runtime state and context (active tools, screen captured, etc.)."""
        context = context or {}
        state = context.get("state", "IDLE").upper()
        recent_tools = context.get("recent_tools", [])
        last_tool = recent_tools[-1] if recent_tools else None

        active_flags = {"ALWAYS"}
        if state in ("IDLE", "READY"):
            active_flags.add("IDLE")
        elif state in ("EXECUTING", "THINKING", "RUNNING"):
            active_flags.add("TASK_ACTIVE")

        if last_tool in ("capture_screen", "inspect_screen", "screen_reading"):
            active_flags.add("AFTER_CAPTURE")
        if last_tool in ("browser_open", "browser_search", "web_search", "browser_read"):
            active_flags.add("BROWSER_ACTIVE")

        matching = []
        for cap in self._capabilities.values():
            if any(flag in cap.show_when for flag in active_flags):
                matching.append(cap)

        # Sort by priority descending and return top 4-6 most relevant
        matching.sort(key=lambda x: x.priority, reverse=True)
        return [c.to_dict() for c in matching[:6]]

    def _register_default_capabilities(self):
        """Registers built-in default capabilities."""
        defaults = [
            Capability(
                id="capture_screen",
                label="Capture Screen",
                description="Grab current desktop display for inspection",
                icon="📸",
                category="perception",
                tool_name="capture_screen",
                show_when=["IDLE", "ALWAYS"],
                prompt_template="Take a screenshot of the current screen",
                priority=100,
                required_permissions=["screen_reading"],
            ),
            Capability(
                id="web_search",
                label="Web Search",
                description="Search the web with real-time sources",
                icon="🌐",
                category="web",
                tool_name="web_search",
                show_when=["IDLE", "ALWAYS"],
                prompt_template="Search the web for latest AI benchmarks",
                priority=90,
            ),
            Capability(
                id="launch_chrome",
                label="Launch Chrome",
                description="Open Google Chrome browser",
                icon="🖥️",
                category="desktop",
                tool_name="open_application",
                show_when=["IDLE"],
                prompt_template="Open Chrome application",
                priority=80,
            ),
            Capability(
                id="system_health",
                label="Health Audit",
                description="Audit hardware telemetry and runtime health",
                icon="⚡",
                category="system",
                tool_name="check_system_health",
                show_when=["IDLE", "ALWAYS"],
                prompt_template="Check current system health and hardware telemetry",
                priority=70,
            ),
            Capability(
                id="analyze_screen",
                label="Analyze Screen",
                description="Extract UI elements and visual structure from screenshot",
                icon="🔍",
                category="perception",
                tool_name="inspect_screen",
                show_when=["AFTER_CAPTURE"],
                prompt_template="Analyze what is on the screen and describe active windows",
                priority=110,
                required_permissions=["screen_reading"],
            ),
            Capability(
                id="read_page",
                label="Read Page",
                description="Extract main readable content from active browser tab",
                icon="📄",
                category="web",
                tool_name="browser_read",
                show_when=["BROWSER_ACTIVE"],
                prompt_template="Read the text content of the active web page",
                priority=105,
            ),
            Capability(
                id="find_files",
                label="Find Files",
                description="Inspect local project folder directory contents",
                icon="📁",
                category="desktop",
                tool_name="list_folder_contents",
                show_when=["IDLE"],
                prompt_template="List contents of the current workspace directory",
                priority=60,
            ),
        ]
        for d in defaults:
            self.register(d)
