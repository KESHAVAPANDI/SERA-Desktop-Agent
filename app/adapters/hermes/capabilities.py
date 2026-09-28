"""
SERA 2.0 / Phase 4B.1 — Canonical Hermes Capability Inventory.

Defines the authoritative inventory of capabilities that the SERA execution substrate
can validate, execute, observe, and empirically verify.

This inventory is the single source of truth for:
- Hermes capability advertisement (bridge tool prompts)
- Plan validation and alias resolution (HermesPlanValidator)
- Execution dispatching and evidence collection (HermesExecutionCoordinator)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from app.adapters.hermes.schema import RiskLevel, TargetType


@dataclass
class HermesCapability:
    """Canonical specification of a SERA capability exposed to Hermes Agent."""
    name: str                                  # Canonical tool name recognized by ToolRegistry
    aliases: List[str]                         # Alternate names Hermes might propose
    target_type: TargetType                    # Semantic target entity class
    description: str                           # Clear description provided to Hermes
    arguments_schema: Dict[str, Any]           # Required/optional arguments
    is_destructive: bool = False               # Destructive operations require user confirmation
    expected_evidence: str = "VALUE_CHECK"     # Verification evidence category


CANONICAL_CAPABILITIES: List[HermesCapability] = [
    HermesCapability(
        name="youtube_search",
        aliases=["youtube_search", "search_youtube"],
        target_type=TargetType.SEARCH_RESULT,
        description="Search YouTube for videos/topics and extract item-level results into session. Arguments: {'query': str}",
        arguments_schema={"query": "str"},
        is_destructive=False,
        expected_evidence="SEARCH_RESULTS",
    ),
    HermesCapability(
        name="web_search",
        aliases=["web_search", "google_search"],
        target_type=TargetType.SEARCH_RESULT,
        description="Search the web for queries. Arguments: {'query': str}",
        arguments_schema={"query": "str"},
        is_destructive=False,
        expected_evidence="SEARCH_RESULTS",
    ),
    HermesCapability(
        name="browser_open",
        aliases=["browser_open", "browser_open_url", "open_url"],
        target_type=TargetType.WEBPAGE,
        description="Navigate to a URL or open a search result in the browser. Arguments: {'url': str}",
        arguments_schema={"url": "str"},
        is_destructive=False,
        expected_evidence="BROWSER_TAB",
    ),
    HermesCapability(
        name="open_new_tab",
        aliases=["open_new_tab"],
        target_type=TargetType.TAB,
        description="Open a URL in a new browser tab. Arguments: {'url': str}",
        arguments_schema={"url": "str"},
        is_destructive=False,
        expected_evidence="BROWSER_TAB",
    ),
    HermesCapability(
        name="focus_browser_tab",
        aliases=[
            "focus_browser_tab",
            "browser_switch_tab",
            "switch_tab",
            "switch_to_tab",
            "activate_tab",
        ],
        target_type=TargetType.TAB,
        description="Switch to an existing open browser tab by title or URL. Arguments: {'tab_identifier': str}",
        arguments_schema={"tab_identifier": "str"},
        is_destructive=False,
        expected_evidence="TAB_ACTIVE",
    ),
    HermesCapability(
        name="close_browser_tab",
        aliases=[
            "close_browser_tab",
            "browser_close_tab",
            "close_tab",
            "dismiss_tab",
        ],
        target_type=TargetType.TAB,
        description="Close a specific browser tab or active tab without terminating the browser process. Arguments: {'tab_identifier': str}",
        arguments_schema={"tab_identifier": "str"},
        is_destructive=False,
        expected_evidence="TAB_CLOSED",
    ),
    HermesCapability(
        name="open_application",
        aliases=["open_application", "launch_application", "start_application"],
        target_type=TargetType.APPLICATION,
        description="Launch or focus an application executable. Arguments: {'application': str}",
        arguments_schema={"application": "str"},
        is_destructive=False,
        expected_evidence="PROCESS_ID",
    ),
    HermesCapability(
        name="close_application",
        aliases=["close_application", "terminate_application", "kill_application", "kill_process"],
        target_type=TargetType.APPLICATION,
        description="Terminate an application or process (destructive, requires approval). Arguments: {'application': str}",
        arguments_schema={"application": "str"},
        is_destructive=True,
        expected_evidence="PROCESS_ID",
    ),
    HermesCapability(
        name="focus_desktop_window",
        aliases=[
            "focus_desktop_window",
            "bring_window_forward",
            "focus_window",
            "bring_to_front",
        ],
        target_type=TargetType.WINDOW,
        description="Bring an existing application window to the foreground. Arguments: {'window_name': str}",
        arguments_schema={"window_name": "str"},
        is_destructive=False,
        expected_evidence="WINDOW_HANDLE",
    ),
    HermesCapability(
        name="close_window",
        aliases=["close_window"],
        target_type=TargetType.WINDOW,
        description="Close a specific window (destructive). Arguments: {'window_name': str}",
        arguments_schema={"window_name": "str"},
        is_destructive=True,
        expected_evidence="WINDOW_HANDLE",
    ),
    HermesCapability(
        name="set_brightness",
        aliases=["set_brightness"],
        target_type=TargetType.SETTING,
        description="Set display brightness level (0-100). Arguments: {'brightness': int}",
        arguments_schema={"brightness": "int"},
        is_destructive=False,
        expected_evidence="VALUE_CHECK",
    ),
    HermesCapability(
        name="set_volume",
        aliases=["set_volume"],
        target_type=TargetType.SETTING,
        description="Set audio master volume (0-100). Arguments: {'volume': int}",
        arguments_schema={"volume": "int"},
        is_destructive=False,
        expected_evidence="VALUE_CHECK",
    ),
    HermesCapability(
        name="cancel_task",
        aliases=["cancel_task", "halt_task", "stop_task"],
        target_type=TargetType.SETTING,
        description="Halt the current executing task immediately.",
        arguments_schema={},
        is_destructive=False,
        expected_evidence="VALUE_CHECK",
    ),
]

# Quick lookup maps
CANONICAL_ACTION_MAP: Dict[str, str] = {}
CAPABILITY_BY_NAME: Dict[str, HermesCapability] = {}

for cap in CANONICAL_CAPABILITIES:
    CAPABILITY_BY_NAME[cap.name] = cap
    for alias in cap.aliases:
        CANONICAL_ACTION_MAP[alias.lower()] = cap.name


def resolve_canonical_action(action_name: str) -> Optional[str]:
    """Resolves any proposed action name or alias to canonical SERA tool name."""
    if not action_name:
        return None
    return CANONICAL_ACTION_MAP.get(action_name.strip().lower())


def get_hermes_tool_advertisements() -> List[Dict[str, Any]]:
    """Generates the authoritative list of tools advertised to the Hermes cognitive engine."""
    return [
        {
            "name": cap.name,
            "description": cap.description,
        }
        for cap in CANONICAL_CAPABILITIES
    ]
