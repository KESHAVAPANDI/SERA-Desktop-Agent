"""
Generates the 100 benchmark test cases for the Semantic Interpreter evaluation.
Follows Phase 3A-D specifications across all mandatory semantic categories:
- APPLICATION (12)
- SYSTEM (14)
- CONTEXTUAL (14)
- POLITENESS (12)
- NATURAL_SPEECH (12)
- COMPOUND (10)
- REFERENCE (10)
- REPETITION (10)
- AMBIGUITY / NEGATIVE (14)
Total: 108 cases (>= 100 target).
"""

import json
from pathlib import Path

CASES = [
    # =========================================================================
    # 1. APPLICATION (12 cases)
    # =========================================================================
    {
        "id": "app_01",
        "category": "APPLICATION",
        "utterance": "Open Chrome.",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "app_02",
        "category": "APPLICATION",
        "utterance": "Launch Chrome.",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "app_03",
        "category": "APPLICATION",
        "utterance": "Bring Chrome up.",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "app_04",
        "category": "APPLICATION",
        "utterance": "Start Google Chrome.",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "app_05",
        "category": "APPLICATION",
        "utterance": "Can you get Chrome running?",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "app_06",
        "category": "APPLICATION",
        "utterance": "Could you open my browser?",
        "context": {"active_browser": "chrome"},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "browser"},
            "needs_clarification": False
        }
    },
    {
        "id": "app_07",
        "category": "APPLICATION",
        "utterance": "Open the browser again.",
        "context": {"last_verified_action": "open_application", "relevant_entities": [{"type": "application", "name": "chrome"}]},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "browser"},
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "app_08",
        "category": "APPLICATION",
        "utterance": "Close Notepad.",
        "context": {"active_application": "notepad"},
        "expected": {
            "intent": "close_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "notepad"},
            "needs_clarification": False
        }
    },
    {
        "id": "app_09",
        "category": "APPLICATION",
        "utterance": "Shut down Spotify.",
        "context": {},
        "expected": {
            "intent": "close_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "spotify"},
            "needs_clarification": False
        }
    },
    {
        "id": "app_10",
        "category": "APPLICATION",
        "utterance": "Switch to VS Code.",
        "context": {},
        "expected": {
            "intent": "switch_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "vscode"},
            "needs_clarification": False
        }
    },
    {
        "id": "app_11",
        "category": "APPLICATION",
        "utterance": "Bring Calculator to the front.",
        "context": {},
        "expected": {
            "intent": "switch_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "calculator"},
            "needs_clarification": False
        }
    },
    {
        "id": "app_12",
        "category": "APPLICATION",
        "utterance": "Launch File Explorer.",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "explorer"},
            "needs_clarification": False
        }
    },

    # =========================================================================
    # 2. SYSTEM SETTINGS (14 cases)
    # =========================================================================
    {
        "id": "sys_01",
        "category": "SYSTEM",
        "utterance": "Set the brightness to 80 percent.",
        "context": {},
        "expected": {
            "intent": "set_brightness",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "brightness"},
            "parameters": {"value": 80},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_02",
        "category": "SYSTEM",
        "utterance": "Make the screen brightness eighty.",
        "context": {},
        "expected": {
            "intent": "set_brightness",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "brightness"},
            "parameters": {"value": 80},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_03",
        "category": "SYSTEM",
        "utterance": "Turn my brightness down to 40.",
        "context": {},
        "expected": {
            "intent": "set_brightness",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "brightness"},
            "parameters": {"value": 40},
            "modifiers": {"direction": "down"},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_04",
        "category": "SYSTEM",
        "utterance": "Put the brightness back at full.",
        "context": {},
        "expected": {
            "intent": "set_brightness",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "brightness"},
            "parameters": {"value": 100},
            "modifiers": {"direction": "max"},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_05",
        "category": "SYSTEM",
        "utterance": "Return the brightness to 100.",
        "context": {},
        "expected": {
            "intent": "set_brightness",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "brightness"},
            "parameters": {"value": 100},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_06",
        "category": "SYSTEM",
        "utterance": "Put the display brightness back where it was.",
        "context": {"relevant_entities": [{"type": "setting", "name": "brightness", "previous_value": 75}]},
        "expected": {
            "intent": "set_brightness",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "brightness"},
            "modifiers": {"direction": "restore"},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_07",
        "category": "SYSTEM",
        "utterance": "Can you restore the brightness to full?",
        "context": {},
        "expected": {
            "intent": "set_brightness",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "brightness"},
            "parameters": {"value": 100},
            "modifiers": {"direction": "max"},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_08",
        "category": "SYSTEM",
        "utterance": "Set volume to 50 percent.",
        "context": {},
        "expected": {
            "intent": "set_volume",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "volume"},
            "parameters": {"value": 50},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_09",
        "category": "SYSTEM",
        "utterance": "Turn the sound up a bit.",
        "context": {},
        "expected": {
            "intent": "adjust_volume",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "volume"},
            "modifiers": {"relative": True, "direction": "up"},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_10",
        "category": "SYSTEM",
        "utterance": "Mute the audio.",
        "context": {},
        "expected": {
            "intent": "set_volume",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "volume"},
            "parameters": {"value": 0},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_11",
        "category": "SYSTEM",
        "utterance": "How much battery do I have left?",
        "context": {},
        "expected": {
            "intent": "battery_status",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "battery"},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_12",
        "category": "SYSTEM",
        "utterance": "Show me system resources and CPU usage.",
        "context": {},
        "expected": {
            "intent": "system_status",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "system"},
            "needs_clarification": False
        }
    },
    {
        "id": "sys_13",
        "category": "SYSTEM",
        "utterance": "Take a screenshot.",
        "context": {},
        "expected": {
            "intent": "take_screenshot",
            "action_family": "SCREEN",
            "needs_clarification": False
        }
    },
    {
        "id": "sys_14",
        "category": "SYSTEM",
        "utterance": "Capture the screen and tell me what is open.",
        "context": {},
        "expected": {
            "intent": "analyze_screen",
            "action_family": "SCREEN",
            "needs_clarification": False
        }
    },

    # =========================================================================
    # 3. CONTEXTUAL & ANAPHORA (14 cases)
    # =========================================================================
    {
        "id": "ctx_01",
        "category": "CONTEXTUAL",
        "utterance": "Open the first result.",
        "context": {
            "active_browser": "chrome",
            "last_verified_action": "youtube_search",
            "relevant_entities": [
                {"type": "search_result", "ordinal": 1, "title": "Top Tech 2026"},
                {"type": "search_result", "ordinal": 2, "title": "Tech Review"}
            ]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_02",
        "category": "CONTEXTUAL",
        "utterance": "Open the second one.",
        "context": {
            "active_browser": "chrome",
            "last_verified_action": "web_search",
            "relevant_entities": [
                {"type": "search_result", "ordinal": 1},
                {"type": "search_result", "ordinal": 2}
            ]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 2},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_03",
        "category": "CONTEXTUAL",
        "utterance": "Show me that result.",
        "context": {
            "last_verified_action": "web_search",
            "relevant_entities": [{"type": "search_result", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_04",
        "category": "CONTEXTUAL",
        "utterance": "Click on the first video.",
        "context": {
            "active_browser": "chrome",
            "last_verified_action": "youtube_search",
            "relevant_entities": [{"type": "video", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_05",
        "category": "CONTEXTUAL",
        "utterance": "Use the result we just found.",
        "context": {
            "last_verified_action": "web_search",
            "relevant_entities": [{"type": "search_result", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_06",
        "category": "CONTEXTUAL",
        "utterance": "Open that.",
        "context": {
            "last_verified_action": "web_search",
            "relevant_entities": [{"type": "search_result", "ordinal": 1, "title": "Target Result"}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "CONTEXT",
            "reference": {"type": "target_entity", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_07",
        "category": "CONTEXTUAL",
        "utterance": "Close it.",
        "context": {
            "active_application": "notepad",
            "active_window": "Untitled - Notepad"
        },
        "expected": {
            "intent": "close_application",
            "action_family": "APPLICATION",
            "reference": {"type": "active_window"},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_08",
        "category": "CONTEXTUAL",
        "utterance": "Close that window.",
        "context": {
            "active_application": "chrome",
            "active_window": "Google Chrome"
        },
        "expected": {
            "intent": "close_application",
            "action_family": "APPLICATION",
            "reference": {"type": "active_window"},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_09",
        "category": "CONTEXTUAL",
        "utterance": "Do that again.",
        "context": {
            "last_verified_action": "open_application"
        },
        "expected": {
            "intent": "repeat_last_task",
            "action_family": "CONTEXT",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_10",
        "category": "CONTEXTUAL",
        "utterance": "Repeat the previous action.",
        "context": {
            "last_verified_action": "youtube_search"
        },
        "expected": {
            "intent": "repeat_last_task",
            "action_family": "CONTEXT",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_11",
        "category": "CONTEXTUAL",
        "utterance": "Stop what you are doing.",
        "context": {"last_verified_action": "running_task"},
        "expected": {
            "intent": "cancel_task",
            "action_family": "CONTEXT",
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_12",
        "category": "CONTEXTUAL",
        "utterance": "Cancel the current task.",
        "context": {"last_verified_action": "running_task"},
        "expected": {
            "intent": "cancel_task",
            "action_family": "CONTEXT",
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_13",
        "category": "CONTEXTUAL",
        "utterance": "Open the last result.",
        "context": {
            "last_verified_action": "web_search",
            "relevant_entities": [
                {"type": "search_result", "ordinal": 1},
                {"type": "search_result", "ordinal": 2},
                {"type": "search_result", "ordinal": 3}
            ]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": -1},
            "needs_clarification": False
        }
    },
    {
        "id": "ctx_14",
        "category": "CONTEXTUAL",
        "utterance": "Go back to that thing we just opened.",
        "context": {
            "last_verified_action": "open_application",
            "recent_verified_actions": [{"action": "open_application", "target": "chrome"}]
        },
        "expected": {
            "intent": "switch_application",
            "action_family": "APPLICATION",
            "reference": {"type": "previous_action"},
            "needs_clarification": False
        }
    },

    # =========================================================================
    # 4. POLITENESS & CONVERSATIONAL WRAPPERS (12 cases)
    # =========================================================================
    {
        "id": "pol_01",
        "category": "POLITENESS",
        "utterance": "Hey Sera, open Chrome.",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "pol_02",
        "category": "POLITENESS",
        "utterance": "Sarah, could you open Chrome please?",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "pol_03",
        "category": "POLITENESS",
        "utterance": "Can you please open Chrome for me?",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "pol_04",
        "category": "POLITENESS",
        "utterance": "Would you mind opening Chrome?",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "pol_05",
        "category": "POLITENESS",
        "utterance": "Could you bring Chrome up for me?",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "pol_06",
        "category": "POLITENESS",
        "utterance": "Good morning Sera, how are you?",
        "context": {},
        "expected": {
            "intent": "greeting",
            "action_family": "CONVERSATION",
            "needs_clarification": False
        }
    },
    {
        "id": "pol_07",
        "category": "POLITENESS",
        "utterance": "Thank you so much Sarah.",
        "context": {},
        "expected": {
            "intent": "gratitude",
            "action_family": "CONVERSATION",
            "needs_clarification": False
        }
    },
    {
        "id": "pol_08",
        "category": "POLITENESS",
        "utterance": "Sera, what can you do?",
        "context": {},
        "expected": {
            "intent": "capabilities",
            "action_family": "CONVERSATION",
            "needs_clarification": False
        }
    },
    {
        "id": "pol_09",
        "category": "POLITENESS",
        "utterance": "Please close Chrome for me if you don't mind.",
        "context": {},
        "expected": {
            "intent": "close_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "pol_10",
        "category": "POLITENESS",
        "utterance": "Hey Sarah, could you set brightness to 60?",
        "context": {},
        "expected": {
            "intent": "set_brightness",
            "action_family": "SYSTEM",
            "target": {"type": "setting", "value": "brightness"},
            "parameters": {"value": 60},
            "needs_clarification": False
        }
    },
    {
        "id": "pol_11",
        "category": "POLITENESS",
        "utterance": "Would you kindly search YouTube for lo-fi hip hop?",
        "context": {},
        "expected": {
            "intent": "youtube_search",
            "action_family": "BROWSER",
            "target": {"type": "query", "value": "lo-fi hip hop"},
            "needs_clarification": False
        }
    },
    {
        "id": "pol_12",
        "category": "POLITENESS",
        "utterance": "Thanks Sera, see you later.",
        "context": {},
        "expected": {
            "intent": "farewell",
            "action_family": "CONVERSATION",
            "needs_clarification": False
        }
    },

    # =========================================================================
    # 5. NATURAL SPEECH & IDIOMATIC PHRASING (12 cases)
    # =========================================================================
    {
        "id": "nat_01",
        "category": "NATURAL_SPEECH",
        "utterance": "Okay, let's get Chrome going.",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_02",
        "category": "NATURAL_SPEECH",
        "utterance": "Can you pull up YouTube?",
        "context": {},
        "expected": {
            "intent": "open_url",
            "action_family": "BROWSER",
            "target": {"type": "url", "value": "youtube"},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_03",
        "category": "NATURAL_SPEECH",
        "utterance": "Bring up the browser.",
        "context": {"active_browser": "chrome"},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "browser"},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_04",
        "category": "NATURAL_SPEECH",
        "utterance": "Get the last search result.",
        "context": {
            "relevant_entities": [
                {"type": "search_result", "ordinal": 1},
                {"type": "search_result", "ordinal": 2}
            ]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": -1},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_05",
        "category": "NATURAL_SPEECH",
        "utterance": "Get my Chrome window up.",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_06",
        "category": "NATURAL_SPEECH",
        "utterance": "Could you fire up the browser?",
        "context": {},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "browser"},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_07",
        "category": "NATURAL_SPEECH",
        "utterance": "Bring the browser back.",
        "context": {"relevant_entities": [{"type": "application", "name": "chrome"}]},
        "expected": {
            "intent": "switch_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "browser"},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_08",
        "category": "NATURAL_SPEECH",
        "utterance": "Take me back to the top result.",
        "context": {
            "last_verified_action": "web_search",
            "relevant_entities": [{"type": "search_result", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_09",
        "category": "NATURAL_SPEECH",
        "utterance": "Use the first thing you found.",
        "context": {
            "last_verified_action": "web_search",
            "relevant_entities": [{"type": "search_result", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_10",
        "category": "NATURAL_SPEECH",
        "utterance": "Go with the first video.",
        "context": {
            "last_verified_action": "youtube_search",
            "relevant_entities": [{"type": "video", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_11",
        "category": "NATURAL_SPEECH",
        "utterance": "Kill the Spotify window.",
        "context": {},
        "expected": {
            "intent": "close_application",
            "action_family": "APPLICATION",
            "target": {"type": "application", "value": "spotify"},
            "needs_clarification": False
        }
    },
    {
        "id": "nat_12",
        "category": "NATURAL_SPEECH",
        "utterance": "Look up python programming on Google.",
        "context": {},
        "expected": {
            "intent": "web_search",
            "action_family": "BROWSER",
            "target": {"type": "query", "value": "python programming"},
            "needs_clarification": False
        }
    },

    # =========================================================================
    # 6. COMPOUND WORKFLOWS (10 cases)
    # =========================================================================
    {
        "id": "cmp_01",
        "category": "COMPOUND",
        "utterance": "Open Chrome and search YouTube for gaming videos.",
        "context": {},
        "expected": {
            "intent": "compound_workflow",
            "action_family": "COMPOUND",
            "target": {"type": "query", "value": "gaming videos"},
            "parameters": {"application": "chrome", "platform": "youtube"},
            "needs_clarification": False
        }
    },
    {
        "id": "cmp_02",
        "category": "COMPOUND",
        "utterance": "Bring up YouTube and look for gaming videos.",
        "context": {},
        "expected": {
            "intent": "compound_workflow",
            "action_family": "COMPOUND",
            "target": {"type": "query", "value": "gaming videos"},
            "parameters": {"platform": "youtube"},
            "needs_clarification": False
        }
    },
    {
        "id": "cmp_03",
        "category": "COMPOUND",
        "utterance": "Open the browser, head to YouTube, and find gaming videos.",
        "context": {},
        "expected": {
            "intent": "compound_workflow",
            "action_family": "COMPOUND",
            "target": {"type": "query", "value": "gaming videos"},
            "parameters": {"application": "browser", "platform": "youtube"},
            "needs_clarification": False
        }
    },
    {
        "id": "cmp_04",
        "category": "COMPOUND",
        "utterance": "Can you search YouTube for gaming videos after opening the browser?",
        "context": {},
        "expected": {
            "intent": "compound_workflow",
            "action_family": "COMPOUND",
            "target": {"type": "query", "value": "gaming videos"},
            "parameters": {"application": "browser", "platform": "youtube"},
            "needs_clarification": False
        }
    },
    {
        "id": "cmp_05",
        "category": "COMPOUND",
        "utterance": "Launch Chrome and find recipes on Google.",
        "context": {},
        "expected": {
            "intent": "compound_workflow",
            "action_family": "COMPOUND",
            "target": {"type": "query", "value": "recipes"},
            "parameters": {"application": "chrome"},
            "needs_clarification": False
        }
    },
    {
        "id": "cmp_06",
        "category": "COMPOUND",
        "utterance": "Open Notepad and type a note.",
        "context": {},
        "expected": {
            "intent": "compound_workflow",
            "action_family": "COMPOUND",
            "target": {"type": "application", "value": "notepad"},
            "needs_clarification": False
        }
    },
    {
        "id": "cmp_07",
        "category": "COMPOUND",
        "utterance": "Take a screenshot and analyze what is on screen.",
        "context": {},
        "expected": {
            "intent": "analyze_screen",
            "action_family": "SCREEN",
            "needs_clarification": False
        }
    },
    {
        "id": "cmp_08",
        "category": "COMPOUND",
        "utterance": "Search Google for weather in Seattle and open the first link.",
        "context": {},
        "expected": {
            "intent": "compound_workflow",
            "action_family": "COMPOUND",
            "target": {"type": "query", "value": "weather in Seattle"},
            "needs_clarification": False
        }
    },
    {
        "id": "cmp_09",
        "category": "COMPOUND",
        "utterance": "Set brightness to 50 and volume to 20.",
        "context": {},
        "expected": {
            "intent": "compound_workflow",
            "action_family": "COMPOUND",
            "parameters": {"brightness": 50, "volume": 20},
            "needs_clarification": False
        }
    },
    {
        "id": "cmp_10",
        "category": "COMPOUND",
        "utterance": "Close Chrome and switch to VS Code.",
        "context": {},
        "expected": {
            "intent": "compound_workflow",
            "action_family": "COMPOUND",
            "parameters": {"close": "chrome", "switch": "vscode"},
            "needs_clarification": False
        }
    },

    # =========================================================================
    # 7. REFERENCES & ORDINALS (10 cases)
    # =========================================================================
    {
        "id": "ref_01",
        "category": "REFERENCE",
        "utterance": "Open the first result.",
        "context": {
            "relevant_entities": [{"type": "search_result", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "ref_02",
        "category": "REFERENCE",
        "utterance": "Take me to the second result.",
        "context": {
            "relevant_entities": [
                {"type": "search_result", "ordinal": 1},
                {"type": "search_result", "ordinal": 2}
            ]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 2},
            "needs_clarification": False
        }
    },
    {
        "id": "ref_03",
        "category": "REFERENCE",
        "utterance": "Open the one at the top.",
        "context": {
            "relevant_entities": [{"type": "search_result", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "ref_04",
        "category": "REFERENCE",
        "utterance": "Show me the third result.",
        "context": {
            "relevant_entities": [
                {"type": "search_result", "ordinal": 1},
                {"type": "search_result", "ordinal": 2},
                {"type": "search_result", "ordinal": 3}
            ]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 3},
            "needs_clarification": False
        }
    },
    {
        "id": "ref_05",
        "category": "REFERENCE",
        "utterance": "Show me the first video.",
        "context": {
            "relevant_entities": [{"type": "video", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "ref_06",
        "category": "REFERENCE",
        "utterance": "Click that result.",
        "context": {
            "relevant_entities": [{"type": "search_result", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },
    {
        "id": "ref_07",
        "category": "REFERENCE",
        "utterance": "Close the page you just opened.",
        "context": {
            "last_verified_action": "open_url",
            "active_browser": "chrome"
        },
        "expected": {
            "intent": "close_application",
            "action_family": "BROWSER",
            "reference": {"type": "active_window"},
            "needs_clarification": False
        }
    },
    {
        "id": "ref_08",
        "category": "REFERENCE",
        "utterance": "Open result number 4.",
        "context": {
            "relevant_entities": [
                {"type": "search_result", "ordinal": 1},
                {"type": "search_result", "ordinal": 2},
                {"type": "search_result", "ordinal": 3},
                {"type": "search_result", "ordinal": 4}
            ]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 4},
            "needs_clarification": False
        }
    },
    {
        "id": "ref_09",
        "category": "REFERENCE",
        "utterance": "Select the second item on the list.",
        "context": {
            "relevant_entities": [{"type": "search_result", "ordinal": 2}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 2},
            "needs_clarification": False
        }
    },
    {
        "id": "ref_10",
        "category": "REFERENCE",
        "utterance": "Play the top video.",
        "context": {
            "relevant_entities": [{"type": "video", "ordinal": 1}]
        },
        "expected": {
            "intent": "open_reference",
            "action_family": "BROWSER",
            "reference": {"type": "search_result", "scope": "previous_search_results", "ordinal": 1},
            "needs_clarification": False
        }
    },

    # =========================================================================
    # 8. REPETITION & MODIFIERS (10 cases)
    # =========================================================================
    {
        "id": "rep_01",
        "category": "REPETITION",
        "utterance": "Do it again.",
        "context": {"last_verified_action": "open_application"},
        "expected": {
            "intent": "repeat_last_task",
            "action_family": "CONTEXT",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "rep_02",
        "category": "REPETITION",
        "utterance": "Repeat that.",
        "context": {"last_verified_action": "web_search"},
        "expected": {
            "intent": "repeat_last_task",
            "action_family": "CONTEXT",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "rep_03",
        "category": "REPETITION",
        "utterance": "Run the previous action again.",
        "context": {"last_verified_action": "take_screenshot"},
        "expected": {
            "intent": "repeat_last_task",
            "action_family": "CONTEXT",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "rep_04",
        "category": "REPETITION",
        "utterance": "Open it one more time.",
        "context": {"last_verified_action": "open_application", "active_application": "chrome"},
        "expected": {
            "intent": "open_application",
            "action_family": "APPLICATION",
            "reference": {"type": "active_window"},
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "rep_05",
        "category": "REPETITION",
        "utterance": "Search that again.",
        "context": {"last_verified_action": "web_search", "relevant_entities": [{"type": "query", "value": "quantum computing"}]},
        "expected": {
            "intent": "web_search",
            "action_family": "BROWSER",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "rep_06",
        "category": "REPETITION",
        "utterance": "Repeat whatever you just did.",
        "context": {"last_verified_action": "set_brightness"},
        "expected": {
            "intent": "repeat_last_task",
            "action_family": "CONTEXT",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "rep_07",
        "category": "REPETITION",
        "utterance": "Do whatever you just did one more time.",
        "context": {"last_verified_action": "take_screenshot"},
        "expected": {
            "intent": "repeat_last_task",
            "action_family": "CONTEXT",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "rep_08",
        "category": "REPETITION",
        "utterance": "Once more please.",
        "context": {"last_verified_action": "open_application"},
        "expected": {
            "intent": "repeat_last_task",
            "action_family": "CONTEXT",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "rep_09",
        "category": "REPETITION",
        "utterance": "Try that query again.",
        "context": {"last_verified_action": "youtube_search"},
        "expected": {
            "intent": "youtube_search",
            "action_family": "BROWSER",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },
    {
        "id": "rep_10",
        "category": "REPETITION",
        "utterance": "Do it one more time.",
        "context": {"last_verified_action": "adjust_volume"},
        "expected": {
            "intent": "repeat_last_task",
            "action_family": "CONTEXT",
            "modifiers": {"repeat": True},
            "needs_clarification": False
        }
    },

    # =========================================================================
    # 9. AMBIGUITY & NEGATIVE TESTS (14 cases)
    # =========================================================================
    {
        "id": "amb_01",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Open that.",
        "context": {},  # No contextual target
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_02",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Close it.",
        "context": {},  # No active entity or window
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_03",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Do the usual thing.",
        "context": {},  # No reliable previous action
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_04",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Open the one.",
        "context": {},  # No known candidates
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_05",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Do it.",
        "context": {},  # No context
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_06",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Get it.",
        "context": {},  # No context
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_07",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Change it.",
        "context": {},  # No setting or entity
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_08",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Close that.",
        "context": {},  # No active window
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_09",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Make it better.",
        "context": {},  # Underspecified
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_10",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Fix that thing.",
        "context": {},  # Underspecified
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_11",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Click the button.",
        "context": {},  # Underspecified button with no UI coordinates or screen context
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_12",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Switch to it.",
        "context": {},  # No active candidate
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_13",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Set the thing to fifty.",
        "context": {},  # Unknown setting
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    },
    {
        "id": "amb_14",
        "category": "AMBIGUITY_NEGATIVE",
        "utterance": "Open result number 10.",
        "context": {
            "relevant_entities": [
                {"type": "search_result", "ordinal": 1},
                {"type": "search_result", "ordinal": 2}
            ]  # Only 2 results exist
        },
        "expected": {
            "needs_clarification": True,
            "confidence": 0.3
        }
    }
]

def main():
    target_dir = Path(__file__).parent
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / "benchmark_cases.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(CASES, f, indent=2)
    print(f"Generated {len(CASES)} benchmark cases at {out_file}")

if __name__ == "__main__":
    main()
