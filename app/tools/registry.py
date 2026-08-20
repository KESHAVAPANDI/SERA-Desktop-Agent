from typing import Any

from app.tools.base import Tool
from app.utils.security import SecurityManager


class ToolRegistry:

    def __init__(
        self,
        security: SecurityManager | None = None,
    ):
        self._tools: dict[str, Tool] = {}
        self.security = security or SecurityManager()

    def register(
        self,
        tool: Tool,
    ):
        if tool.name in self._tools:
            raise ValueError(
                f"Tool already registered: {tool.name}"
            )
        self._tools[tool.name] = tool

    def get(
        self,
        name: str,
    ) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(
        self,
    ) -> list[dict[str, Any]]:
        return [
            tool.schema()
            for tool in self._tools.values()
        ]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        is_confirmed: bool = False,
    ):
        arguments = arguments or {}
        tool = self.get(name)

        if tool is None:
            raise ValueError(f"Unknown tool: {name}")

        decision = self.security.check(name, is_confirmed=is_confirmed)

        if not decision.allowed:
            return {
                "success": False,
                "error": decision.reason,
            }

        if decision.requires_confirmation:
            return {
                "success": False,
                "requires_confirmation": True,
                "tool": name,
                "reason": decision.reason,
                "arguments": arguments,
            }

        return await tool.execute(**arguments)