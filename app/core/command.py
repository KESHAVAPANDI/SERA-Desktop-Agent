"""
SERA Command Specification & Multi-Layer Command Parser.
Defines normalized CommandObject, Complexity levels, Canonical Intent Registry,
and Layer 1 (Deterministic Fast-Path) / Layer 2 (Structured Semantic Extraction) Parser.
"""

import os
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CommandComplexity(str, Enum):
    SIMPLE = "SIMPLE"              # Direct conversational or local OS action (0 tools or 1 local tool)
    ONE_TOOL = "ONE_TOOL"          # Single discrete desktop/browser/screen tool
    MULTI_STEP = "MULTI_STEP"      # Compound multi-step deterministic workflow
    AMBIGUOUS = "AMBIGUOUS"        # Underspecified command requiring clarification or LLM inference


class CommandCategory(str, Enum):
    CONVERSATION = "CONVERSATION"
    SYSTEM = "SYSTEM"
    APPLICATIONS = "APPLICATIONS"
    FILES = "FILES"
    BROWSER = "BROWSER"
    SCREEN = "SCREEN"
    WINDOW = "WINDOW"
    POWER = "POWER"
    CONTEXT = "CONTEXT"
    COMPOUND = "COMPOUND"
    GENERAL = "GENERAL"


@dataclass
class PlanStepItem:
    step_id: int
    goal: str
    action: str
    arguments: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 5.0
    verification_type: str = "state_check"  # "window_check", "file_check", "url_check", "value_check", "none"


@dataclass
class CommandObject:
    command_id: str
    task_id: str
    intent: str
    category: CommandCategory
    complexity: CommandComplexity
    source_text: str
    entities: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    required_tools: list[str] = field(default_factory=list)
    confirmation_required: bool = False
    execution_plan: list[PlanStepItem] = field(default_factory=list)
    raw_response: str | None = None


class CommandParser:
    """Multi-layer command interpretation engine."""

    # -------------------------------------------------------------
    # GREETINGS & CONVERSATION
    # -------------------------------------------------------------
    GREETINGS = {
        "hi", "hello", "hey", "hey sera", "hello sera", "hi sera",
        "good morning", "good afternoon", "good evening", "howdy",
        "sup", "whats up", "what's up", "yo",
    }
    GRATITUDE = {
        "thanks", "thank you", "thanks sera", "thank you sera", "thx",
        "many thanks", "appreciate it", "much appreciated",
    }
    FAREWELLS = {
        "bye", "goodbye", "see you", "see ya", "good night", "exit", "quit",
    }
    CAPABILITY_QUERIES = {
        "what can you do", "help", "show capabilities", "what are your capabilities",
        "who are you", "what are you", "help me",
    }

    # -------------------------------------------------------------
    # CONTEXTUAL & REPEAT COMMANDS
    # -------------------------------------------------------------
    REPEAT_PATTERNS = [
        r"^repeat\s+(?:the\s+)?(?:last\s+)?(?:task|action|command|query)$",
        r"^do\s+(?:it|that)\s+again$",
        r"^run\s+(?:the\s+)?(?:last\s+)?(?:task|action|command)\s+again$",
        r"^again$",
        r"^one\s+more\s+time$",
    ]

    CANCEL_PATTERNS = [
        r"^cancel(?:\s+task|\s+current\s+task|\s+execution)?$",
        r"^stop(?:\s+task|\s+execution|\s+it)?$",
        r"^abort(?:\s+task|\s+it)?$",
    ]

    def parse(
        self,
        text: str,
        task_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> CommandObject:
        """Parses natural-language user utterance into a normalized CommandObject."""
        raw_text = text.strip()
        cleaned = raw_text.lower().strip().rstrip(".!?")
        cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"
        t_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        context = context or {}

        # =========================================================
        # 1. LAYER 1: CONVERSATION (Zero Tools, <10ms Response)
        # =========================================================
        if cleaned in self.GREETINGS or any(cleaned.startswith(f"{g} ") or cleaned.endswith(f" {g}") for g in ("hi", "hello", "hey")):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="greeting",
                category=CommandCategory.CONVERSATION,
                complexity=CommandComplexity.SIMPLE,
                source_text=raw_text,
                raw_response="Hello! I am SERA, your desktop AI assistant. How can I help you today?",
            )

        if cleaned in self.GRATITUDE or any(cleaned.startswith(f"{g} ") for g in ("thanks", "thank you")):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="gratitude",
                category=CommandCategory.CONVERSATION,
                complexity=CommandComplexity.SIMPLE,
                source_text=raw_text,
                raw_response="You're very welcome! Let me know if you need anything else.",
            )

        if cleaned in self.FAREWELLS:
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="farewell",
                category=CommandCategory.CONVERSATION,
                complexity=CommandComplexity.SIMPLE,
                source_text=raw_text,
                raw_response="Goodbye! Have a great day.",
            )

        if cleaned in self.CAPABILITY_QUERIES:
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="capabilities",
                category=CommandCategory.CONVERSATION,
                complexity=CommandComplexity.SIMPLE,
                source_text=raw_text,
                raw_response="I can control applications, manage files, search the web and YouTube, take and analyze screenshots, adjust volume and brightness, report system diagnostics, and execute multi-step workflows on your PC.",
            )

        # =========================================================
        # 2. LAYER 1: CONTEXTUAL COMMANDS ("Repeat last task", "Cancel", "Close it")
        # =========================================================
        if any(re.search(p, cleaned) for p in self.REPEAT_PATTERNS):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="repeat_last_task",
                category=CommandCategory.CONTEXT,
                complexity=CommandComplexity.SIMPLE,
                source_text=raw_text,
            )

        if any(re.search(p, cleaned) for p in self.CANCEL_PATTERNS):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="cancel_current_task",
                category=CommandCategory.CONTEXT,
                complexity=CommandComplexity.SIMPLE,
                source_text=raw_text,
            )

        if cleaned in ("close it", "close that", "kill it", "exit it", "dismiss it"):
            last_app = context.get("last_application") or context.get("last_opened_target") or "active_window"
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="close_application",
                category=CommandCategory.APPLICATIONS,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"application": last_app},
                required_tools=["close_application"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Close application '{last_app}'", action="close_application", arguments={"application": last_app}, timeout_seconds=5.0),
                ],
            )

        if cleaned in ("open it", "reopen it", "open it again"):
            last_target = context.get("last_application") or context.get("last_opened_target")
            if last_target:
                return CommandObject(
                    command_id=cmd_id,
                    task_id=t_id,
                    intent="open_application",
                    category=CommandCategory.APPLICATIONS,
                    complexity=CommandComplexity.ONE_TOOL,
                    source_text=raw_text,
                    parameters={"application": last_target},
                    required_tools=["open_application"],
                    execution_plan=[
                        PlanStepItem(step_id=1, goal=f"Open application '{last_target}'", action="open_application", arguments={"application": last_target}, timeout_seconds=5.0, verification_type="window_check"),
                    ],
                )

        # =========================================================
        # 3. LAYER 1: COMPOUND COMMANDS (Multi-Step Deterministic)
        # =========================================================
        # 3a. Open Chrome/Browser AND Search YouTube for <query>
        comp_yt_match = re.search(
            r"^(?:please\s+)?open\s+(?:chrome|google\s+chrome|browser|edge|youtube)?\s*(?:and|,)?\s*(?:search|search\s+in|search\s+on)?\s*youtube\s*(?:for)?\s*(.+)$",
            cleaned,
        )
        if comp_yt_match:
            yt_query = comp_yt_match.group(1).strip()
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="open_and_youtube_search",
                category=CommandCategory.COMPOUND,
                complexity=CommandComplexity.MULTI_STEP,
                source_text=raw_text,
                parameters={"application": "chrome", "query": yt_query},
                required_tools=["open_application", "youtube_search"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Open Chrome browser", action="open_application", arguments={"application": "chrome"}, timeout_seconds=5.0, verification_type="window_check"),
                    PlanStepItem(step_id=2, goal=f"Search YouTube for '{yt_query}'", action="youtube_search", arguments={"query": yt_query}, timeout_seconds=10.0, verification_type="url_check"),
                ],
            )

        # 3b. Open Chrome/Browser AND Search Web for <query>
        comp_web_match = re.search(
            r"^(?:please\s+)?open\s+(?:chrome|google\s+chrome|browser|edge)\s*(?:and|,)?\s*(?:search\s+(?:the\s+)?web\s+for|search\s+for|google)\s*(.+)$",
            cleaned,
        )
        if comp_web_match:
            web_query = comp_web_match.group(1).strip()
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="open_and_web_search",
                category=CommandCategory.COMPOUND,
                complexity=CommandComplexity.MULTI_STEP,
                source_text=raw_text,
                parameters={"application": "chrome", "query": web_query},
                required_tools=["open_application", "web_search"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Open Chrome browser", action="open_application", arguments={"application": "chrome"}, timeout_seconds=5.0, verification_type="window_check"),
                    PlanStepItem(step_id=2, goal=f"Search Web for '{web_query}'", action="web_search", arguments={"query": web_query}, timeout_seconds=12.0, verification_type="url_check"),
                ],
            )

        # 3c. Take a screenshot AND inspect/describe it
        comp_screen_match = re.search(
            r"^(?:take\s+a\s+screenshot|capture\s+screen)\s*(?:and|,)?\s*(?:inspect|describe|tell\s+me\s+what\s+is\s+visible|analyze|summarize)\s*(?:what\s+is\s+visible|what\'s\s+visible|it|the\s+screen)?$",
            cleaned,
        )
        if comp_screen_match:
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="screenshot_and_analyze",
                category=CommandCategory.COMPOUND,
                complexity=CommandComplexity.MULTI_STEP,
                source_text=raw_text,
                parameters={"query": raw_text},
                required_tools=["capture_screen", "inspect_screen"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Capture screen display", action="capture_screen", arguments={}, timeout_seconds=5.0, verification_type="file_check"),
                    PlanStepItem(step_id=2, goal="Inspect captured screen with vision engine", action="inspect_screen", arguments={"query": raw_text}, timeout_seconds=20.0),
                ],
            )

        # 3d. Open Downloads/Folder AND find latest PDF/file
        comp_find_match = re.search(
            r"^(?:open\s+(?:the\s+)?(\w+)\s+folder)\s*(?:and|,)?\s*(?:find|search\s+for)\s*(?:the\s+)?(?:latest\s+)?(\w+|\*\.\w+)?\s*(pdf|file|document|image)?$",
            cleaned,
        )
        if comp_find_match:
            folder = comp_find_match.group(1).strip()
            pattern = comp_find_match.group(2) or ("*.pdf" if "pdf" in cleaned else "*.*")
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="open_folder_and_find",
                category=CommandCategory.COMPOUND,
                complexity=CommandComplexity.MULTI_STEP,
                source_text=raw_text,
                parameters={"folder_name": folder, "pattern": pattern},
                required_tools=["open_folder", "find_files"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Open folder '{folder}' in File Explorer", action="open_folder", arguments={"folder_name": folder}, timeout_seconds=5.0, verification_type="window_check"),
                    PlanStepItem(step_id=2, goal=f"Find files matching '{pattern}' in {folder}", action="find_files", arguments={"folder": folder, "pattern": pattern}, timeout_seconds=5.0),
                ],
            )

        # =========================================================
        # 4. LAYER 1: SCREEN OPERATIONS
        # =========================================================
        # 4a. Region selection: capture screen region [x, y, w, h]
        region_match = re.search(r"capture\s+(?:screen\s+)?(?:region|area)\s*\[?\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)[,\s]+(\d+)\s*\]?", cleaned)
        if region_match:
            coords = [int(region_match.group(i)) for i in range(1, 5)]
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="capture_screen",
                category=CommandCategory.SCREEN,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"region": coords},
                required_tools=["capture_screen"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Capture screen region {coords}", action="capture_screen", arguments={"region": coords}, timeout_seconds=5.0, verification_type="file_check"),
                ],
            )

        # 4b. AI Target Region: capture <target> on screen
        ai_cap_match = re.search(r"^capture\s+(?:the\s+)?(.+?)\s+(?:on|of|from)\s+(?:the\s+)?(?:screen|desktop)$", raw_text, re.IGNORECASE)
        if ai_cap_match and not any(k in cleaned for k in ["what", "how", "why"]):
            target_desc = ai_cap_match.group(1).strip()
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="capture_screen",
                category=CommandCategory.SCREEN,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"ai_prompt": target_desc},
                required_tools=["capture_screen"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Capture AI target region '{target_desc}'", action="capture_screen", arguments={"ai_prompt": target_desc}, timeout_seconds=8.0, verification_type="file_check"),
                ],
            )

        # 4c. Entire Screen Capture
        screen_patterns = [
            r"^(?:please\s+)?(?:take|capture|grab|make|save)?\s*(?:a\s+)?(?:screen\s*shot|screenshot|screen\s*capture|screen\s*grab)(?:\s+please)?[\.!]?$",
            r"^(?:please\s+)?(?:capture|grab|record)\s+(?:my\s+|the\s+)?(?:screen|desktop)(?:\s+please)?[\.!]?$",
        ]
        if any(re.search(p, cleaned) for p in screen_patterns):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="capture_screen",
                category=CommandCategory.SCREEN,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={},
                required_tools=["capture_screen"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Capture full desktop display", action="capture_screen", arguments={}, timeout_seconds=5.0, verification_type="file_check"),
                ],
            )

        # 4d. Screen Analysis / Vision Perception ("What is on my screen?")
        screen_analyze_patterns = [
            r"(?:what\s+(?:is|do\s+you\s+see|can\s+you\s+see)\s+(?:currently\s+)?on\s+(?:my\s+|the\s+)?screen)",
            r"(?:what\'s\s+(?:currently\s+)?on\s+(?:my\s+|the\s+)?screen)",
            r"(?:read|analyze|describe|look\s+at|inspect|summarize)\s+(?:my\s+|the\s+)?screen",
            r"(?:what\s+is\s+shown\s+on\s+(?:my\s+|the\s+)?screen)",
            r"(?:explain|tell\s+me\s+about)\s+(?:what\s+is\s+on\s+)?(?:my\s+|the\s+)?screen",
        ]
        if any(re.search(p, cleaned) for p in screen_analyze_patterns):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="inspect_screen",
                category=CommandCategory.SCREEN,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"query": raw_text},
                required_tools=["inspect_screen"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Inspect and analyze active screen with perception vision", action="inspect_screen", arguments={"query": raw_text}, timeout_seconds=20.0),
                ],
            )

        # =========================================================
        # 5. LAYER 1: SYSTEM & HARDWARE CONTROLS
        # =========================================================
        # 5a. Time & Date
        if any(kw in cleaned for kw in ("what time is it", "what's the time", "current time", "what is the time", "tell me the time", "date today", "what is the date", "what day is it today")):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="get_current_time",
                category=CommandCategory.SYSTEM,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                required_tools=["get_current_time"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Retrieve current system time and date", action="get_current_time", arguments={}, timeout_seconds=5.0),
                ],
            )

        # 5b. System Info / Diagnostics (CPU / RAM / Disk)
        if any(kw in cleaned for kw in ("system info", "system information", "system diagnostic", "system status", "cpu usage", "ram usage", "memory usage", "disk usage", "system performance")):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="get_system_info",
                category=CommandCategory.SYSTEM,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                required_tools=["get_system_info"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Retrieve CPU, RAM, Disk and diagnostic telemetry", action="get_system_info", arguments={}, timeout_seconds=5.0),
                ],
            )

        # 5c. Battery Status
        if any(kw in cleaned for kw in ("battery status", "battery level", "battery percentage", "is my laptop charging", "check battery", "power state")):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="get_battery_status",
                category=CommandCategory.SYSTEM,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                required_tools=["get_battery_status"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Check laptop battery percentage and charging state", action="get_battery_status", arguments={}, timeout_seconds=5.0),
                ],
            )

        # 5d. Wi-Fi Status
        if any(kw in cleaned for kw in ("wifi status", "wi-fi status", "internet status", "am i connected to wifi", "check wifi", "network status", "connection status")):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="get_wifi_status",
                category=CommandCategory.SYSTEM,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                required_tools=["get_wifi_status"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Check current Wi-Fi network connection and SSID", action="get_wifi_status", arguments={}, timeout_seconds=5.0),
                ],
            )

        # 5e. Brightness
        bright_match = re.search(r"(?:brightness|screen brightness).*?(\d{1,3})\s*%?", cleaned)
        if bright_match:
            b_val = max(0, min(100, int(bright_match.group(1))))
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="set_brightness",
                category=CommandCategory.SYSTEM,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"brightness": b_val},
                required_tools=["set_brightness"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Set display brightness to {b_val}%", action="set_brightness", arguments={"brightness": b_val}, timeout_seconds=5.0, verification_type="value_check"),
                ],
            )

        # 5f. Volume
        vol_match = re.search(r"(?:volume|sound).*?(\d{1,3})\s*%?", cleaned)
        if vol_match:
            v_val = max(0, min(100, int(vol_match.group(1))))
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="set_volume",
                category=CommandCategory.SYSTEM,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"volume": v_val},
                required_tools=["set_volume"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Set system volume to {v_val}%", action="set_volume", arguments={"volume": v_val}, timeout_seconds=5.0, verification_type="value_check"),
                ],
            )

        # 5g. Mute / Unmute
        if "mute" in cleaned and "unmute" not in cleaned:
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="mute",
                category=CommandCategory.SYSTEM,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={},
                required_tools=["mute"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Mute system audio output", action="mute", arguments={}, timeout_seconds=5.0, verification_type="value_check"),
                ],
            )

        if "unmute" in cleaned:
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="unmute",
                category=CommandCategory.SYSTEM,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={},
                required_tools=["unmute"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Unmute system audio output", action="unmute", arguments={}, timeout_seconds=5.0, verification_type="value_check"),
                ],
            )

        # =========================================================
        # 6. LAYER 1: POWER CONTROLS (Safe Simulation / Local Execution)
        # =========================================================
        if any(kw in cleaned for kw in ("lock my pc", "lock the pc", "lock computer", "lock screen", "lock my computer")):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="lock_computer",
                category=CommandCategory.POWER,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                required_tools=["lock_screen"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Lock Windows workstation", action="lock_screen", arguments={}, timeout_seconds=5.0),
                ],
            )

        if any(kw in cleaned for kw in ("sleep my pc", "put computer to sleep", "sleep pc", "sleep")):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="sleep_computer",
                category=CommandCategory.POWER,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                required_tools=["sleep_pc"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="Suspend Windows to sleep mode", action="sleep_pc", arguments={}, timeout_seconds=5.0),
                ],
            )

        # =========================================================
        # 7. LAYER 1: BROWSER & WEB SEARCH
        # =========================================================
        # 7a. YouTube Search
        yt_patterns = [
            r"(?:search\s+(?:in|on|for)?\s*youtube\s*(?:for)?\s*)(.+)",
            r"(?:open\s+youtube\s+and\s+search\s*(?:for)?\s*)(.+)",
            r"(?:youtube\s+search\s*(?:for)?\s*)(.+)",
            r"(?:play\s+(.+)\s+(?:on|in)\s+youtube)",
            r"^youtube\s+(.+)$",
        ]
        for pat in yt_patterns:
            yt_m = re.search(pat, cleaned, re.IGNORECASE)
            if yt_m:
                q = yt_m.group(1).strip().rstrip(".!?")
                if q:
                    return CommandObject(
                        command_id=cmd_id,
                        task_id=t_id,
                        intent="youtube_search",
                        category=CommandCategory.BROWSER,
                        complexity=CommandComplexity.ONE_TOOL,
                        source_text=raw_text,
                        parameters={"query": q},
                        required_tools=["youtube_search"],
                        execution_plan=[
                            PlanStepItem(step_id=1, goal=f"Search YouTube for '{q}' and navigate to results", action="youtube_search", arguments={"query": q}, timeout_seconds=10.0, verification_type="url_check"),
                        ],
                    )

        # 7b. Web Search ("Search the web for RTX 5090 benchmarks")
        web_search_match = re.search(
            r"^(?:search\s+(?:the\s+)?web\s+(?:for)?\s*|google\s+|search\s+for\s+)(.+)$",
            cleaned,
        )
        if web_search_match and not any(k in cleaned for k in ["youtube", "file", "folder", "app"]):
            web_q = web_search_match.group(1).strip()
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="web_search",
                category=CommandCategory.BROWSER,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"query": web_q},
                required_tools=["web_search"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Searching the web for '{web_q}'", action="web_search", arguments={"query": web_q, "open_browser": True}, timeout_seconds=15.0, verification_type="search_results"),
                ],
            )

        # 7c. Open URL / Website ("open youtube.com", "open google.com", "open github.com")
        url_match = re.search(r"^(?:open|navigate\s+to|go\s+to)\s+(?:https?://)?([a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)$", cleaned)
        if url_match:
            url_target = url_match.group(1).strip()
            if not url_target.startswith("http://") and not url_target.startswith("https://"):
                url_target = f"https://{url_target}"
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="open_website",
                category=CommandCategory.BROWSER,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"url": url_target},
                required_tools=["browser_open"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Open URL '{url_target}' in web browser", action="browser_open", arguments={"url": url_target}, timeout_seconds=10.0, verification_type="url_check"),
                ],
            )

        # =========================================================
        # 8. LAYER 1: APPLICATIONS (Open / Close / List / Focus)
        # =========================================================
        # 8a. List Running Applications
        if any(kw in cleaned for kw in ("list running applications", "list running apps", "what applications are open", "what apps are running", "show open windows", "show running processes")):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="list_running_applications",
                category=CommandCategory.APPLICATIONS,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                required_tools=["list_running_applications"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal="List active applications and processes", action="list_running_applications", arguments={"filter_user_apps": True}, timeout_seconds=5.0),
                ],
            )

        # 8b. Close Application ("Close Chrome", "Exit Notepad", "Kill Spotify")
        close_match = re.search(r"^(?:close|exit|kill|terminate|stop)\s+(?:the\s+)?([a-zA-Z0-9_\-\.\s]+?)(?:\s+application|\s+app)?$", cleaned)
        if close_match and not any(k in cleaned for k in ["file", "folder", "tab", "task"]):
            app_to_close = close_match.group(1).strip()
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="close_application",
                category=CommandCategory.APPLICATIONS,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"application": app_to_close},
                required_tools=["close_application"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Close application '{app_to_close}'", action="close_application", arguments={"application": app_to_close}, timeout_seconds=5.0),
                ],
            )

        # 8c. Open Application ("Open Chrome", "Launch Notepad", "Start Calculator")
        open_app_match = re.search(r"^(?:open|launch|start|run)\s+(?:the\s+)?([a-zA-Z0-9_\-\.\s]+?)(?:\s+application|\s+app)?$", cleaned)
        if open_app_match and not any(k in cleaned for k in ["folder", "file", "directory", "tab", "website", "url", "youtube"]):
            app_to_open = open_app_match.group(1).strip()
            # Check if this target is actually a standard folder (e.g. "open downloads")
            if app_to_open.lower() in ("downloads", "download", "documents", "document", "desktop", "pictures", "photos", "videos", "music"):
                return CommandObject(
                    command_id=cmd_id,
                    task_id=t_id,
                    intent="open_folder",
                    category=CommandCategory.FILES,
                    complexity=CommandComplexity.ONE_TOOL,
                    source_text=raw_text,
                    parameters={"folder_name": app_to_open},
                    required_tools=["open_folder"],
                    execution_plan=[
                        PlanStepItem(step_id=1, goal=f"Open folder '{app_to_open}' in File Explorer", action="open_folder", arguments={"folder_name": app_to_open}, timeout_seconds=5.0, verification_type="window_check"),
                    ],
                )

            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="open_application",
                category=CommandCategory.APPLICATIONS,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"application": app_to_open},
                required_tools=["open_application"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Opening {app_to_open.capitalize()}...", action="open_application", arguments={"application": app_to_open}, timeout_seconds=8.0, verification_type="window_check"),
                ],
            )

        # =========================================================
        # 9. LAYER 1: FILES & FOLDERS (Open folder, find file, open file)
        # =========================================================
        # 9a. Open Folder ("Open folder X", "Open the Downloads folder", "Open Documents folder")
        folder_match = re.search(r"^(?:open|explore)\s+(?:the\s+)?(?:folder\s+|directory\s+)(.+)$|^(?:open|explore)\s+(?:the\s+)?(.+?)(?:\s+folder|\s+directory)$", cleaned)
        if folder_match:
            f_name = (folder_match.group(1) or folder_match.group(2)).strip()
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="open_folder",
                category=CommandCategory.FILES,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"folder_name": f_name},
                required_tools=["open_folder"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Open folder '{f_name}' in File Explorer", action="open_folder", arguments={"folder_name": f_name}, timeout_seconds=5.0, verification_type="window_check"),
                ],
            )

        # 9b. Find Files ("Find file resume.pdf", "Find the latest PDF", "Find files in Downloads")
        find_match = re.search(r"^(?:find|search\s+for|locate)\s+(?:the\s+)?(?:file|files|document)?\s*(.+?)(?:\s+in\s+(.+))?$", cleaned)
        if find_match and not any(k in cleaned for k in ["youtube", "web", "google"]):
            target_pattern = find_match.group(1).strip()
            target_dir = find_match.group(2).strip() if find_match.group(2) else "Downloads"
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="find_files",
                category=CommandCategory.FILES,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"folder": target_dir, "pattern": target_pattern},
                required_tools=["find_files"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Search for '{target_pattern}' in {target_dir}", action="find_files", arguments={"folder": target_dir, "pattern": target_pattern}, timeout_seconds=5.0),
                ],
            )

        # 9c. Open Specific File ("Open file report.pdf", "Open notes.txt")
        file_match = re.search(r"^(?:open|view)\s+(?:the\s+)?file\s+(.+)$", cleaned)
        if file_match:
            file_name = file_match.group(1).strip()
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="open_file",
                category=CommandCategory.FILES,
                complexity=CommandComplexity.ONE_TOOL,
                source_text=raw_text,
                parameters={"file_path": file_name},
                required_tools=["open_file"],
                execution_plan=[
                    PlanStepItem(step_id=1, goal=f"Open file '{file_name}' with default application", action="open_file", arguments={"file_path": file_name}, timeout_seconds=5.0, verification_type="file_check"),
                ],
            )

        # =========================================================
        # 10. LAYER 3: GENERAL AMBIGUOUS / COMPLEX LLM DELEGATION
        # =========================================================
        return CommandObject(
            command_id=cmd_id,
            task_id=t_id,
            intent="general_reasoning",
            category=CommandCategory.GENERAL,
            complexity=CommandComplexity.AMBIGUOUS,
            source_text=raw_text,
            parameters={"query": raw_text},
        )
