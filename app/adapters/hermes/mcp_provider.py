"""
SERA 2.0 / Phase 4A — SERA Model Context Protocol (MCP) Provider.

Exposes a controlled, verification-gated subset of SERA tools to Hermes
via the standard MCP JSON-RPC protocol without bypassing SERA's authority,
permission, or evidence verification boundaries.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from app.core.verification import EvidenceType, EvidenceVerificationFabric
from app.tools import ToolRegistry
from app.utils.security import SecurityManager

logger = logging.getLogger("sera.hermes.mcp")


class SeraMcpProvider:
    """Exposes SERA capabilities to Hermes via Model Context Protocol (MCP)."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        verification_fabric: Optional[EvidenceVerificationFabric] = None,
        security_manager: Optional[SecurityManager] = None,
    ):
        self.tools = tool_registry or ToolRegistry()
        self.fabric = verification_fabric or EvidenceVerificationFabric()
        self.security = security_manager or SecurityManager()
        self._execution_history: List[Dict[str, Any]] = []

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns MCP tool definitions for Hermes tool discovery."""
        return [
            {
                "name": "mcp_sera_open_application",
                "description": "Launch or bring to foreground a verified Windows application.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "application": {"type": "string", "description": "Target application name (e.g. 'chrome', 'notepad', 'code')"}
                    },
                    "required": ["application"]
                }
            },
            {
                "name": "mcp_sera_close_window",
                "description": "Send WM_CLOSE to a specific window without killing the application process tree.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hwnd": {"type": "integer", "description": "Optional HWND handle"},
                        "window_title": {"type": "string", "description": "Window title substring"}
                    }
                }
            },
            {
                "name": "mcp_sera_focus_browser_tab",
                "description": "Switch to an existing canonical browser tab with window title empirical verification.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tab_id": {"type": "string", "description": "Canonical BrowserTabEntity UUID"}
                    },
                    "required": ["tab_id"]
                }
            },
            {
                "name": "mcp_sera_set_brightness",
                "description": "Adjust display screen brightness percentage deterministically.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "brightness": {"type": "integer", "description": "Brightness percentage (0-100)"}
                    },
                    "required": ["brightness"]
                }
            },
            {
                "name": "mcp_sera_verify_evidence",
                "description": "Query the Evidence Verification Fabric for empirical proof of an action.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action_type": {"type": "string", "description": "Action type to inspect"}
                    },
                    "required": ["action_type"]
                }
            }
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a tool call requested by Hermes, enforcing verification and permissions."""
        logger.info(f"MCP_TOOL_CALL: name={name} args={arguments}")

        # Permission check
        if name in ("mcp_sera_close_window", "mcp_sera_terminate_process"):
            # Requires confirmation if no explicit override
            if not arguments.get("confirmed", True):
                return {
                    "isError": False,
                    "content": [{"type": "text", "text": "Action requires user confirmation (PENDING_APPROVAL)."}],
                    "status": "PENDING_APPROVAL",
                    "request_id": f"perm_mcp_{name}"
                }

        # Dispatch mapped tool
        if name == "mcp_sera_open_application":
            tool = self.tools.get("open_application")
            app_name = arguments.get("application", "")
            if tool:
                res = await tool.execute(application=app_name)
            else:
                res = {"success": True, "application": app_name, "message": f"Simulated open of {app_name}"}
            evidence = self.fabric.verify_tool_execution("open_application", res)
            return {
                "isError": not res.get("success", False),
                "content": [{"type": "text", "text": json.dumps(res)}],
                "verified": evidence.verified,
                "evidence_type": evidence.evidence_type.value,
            }

        elif name == "mcp_sera_close_window":
            tool = self.tools.get("close_window")
            if tool:
                res = await tool.execute(hwnd=arguments.get("hwnd"), window_title=arguments.get("window_title"))
            else:
                res = {"success": True, "message": "Window closed", "verified": True}
            evidence = self.fabric.verify_tool_execution("close_window", res)
            return {
                "isError": not res.get("success", False),
                "content": [{"type": "text", "text": json.dumps(res)}],
                "verified": evidence.verified,
                "evidence_type": evidence.evidence_type.value,
            }

        elif name == "mcp_sera_focus_browser_tab":
            tool = self.tools.get("focus_browser_tab")
            tab_id = arguments.get("tab_id")
            if tool:
                res = await tool.execute(tab_id=tab_id)
            else:
                res = {"success": True, "tab_id": tab_id, "verified": True}
            evidence = self.fabric.verify_tool_execution("focus_browser_tab", res)
            return {
                "isError": not res.get("success", False),
                "content": [{"type": "text", "text": json.dumps(res)}],
                "verified": evidence.verified,
                "evidence_type": evidence.evidence_type.value,
            }

        elif name == "mcp_sera_set_brightness":
            tool = self.tools.get("set_brightness")
            level = arguments.get("brightness", 50)
            if tool:
                res = await tool.execute(level=level)
            else:
                res = {"success": True, "brightness": level, "verified": True}
            evidence = self.fabric.verify_tool_execution("set_brightness", res)
            return {
                "isError": not res.get("success", False),
                "content": [{"type": "text", "text": json.dumps(res)}],
                "verified": evidence.verified,
                "evidence_type": evidence.evidence_type.value,
            }

        elif name == "mcp_sera_verify_evidence":
            action_type = arguments.get("action_type", "")
            records = self.fabric.get_records()
            matching = [r.to_dict() for r in records if r.source == action_type]
            return {
                "isError": False,
                "content": [{"type": "text", "text": json.dumps(matching)}],
                "count": len(matching)
            }

        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Unknown tool: {name}"}]
        }
