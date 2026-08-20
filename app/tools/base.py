from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description shown to the LLM."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON-schema-compatible parameter definition."""
        pass

    @property
    def requires_confirmation(self) -> bool:
        """Whether SERA must ask the user before execution."""
        return False

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool."""
        pass

    def schema(self) -> dict[str, Any]:
        """
        Convert this tool into a function/tool schema
        that can be passed to an LLM.
        """
        params = self.parameters
        if callable(params):
            params = params()

        name = self.name
        if callable(name):
            name = name()

        desc = self.description
        if callable(desc):
            desc = desc()

        return {
            "name": name,
            "description": desc,
            "parameters": params,
        }
