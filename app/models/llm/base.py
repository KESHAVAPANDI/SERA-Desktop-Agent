from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    text: str | None = None

    tool_calls: list[ToolCall] = field(
        default_factory=list
    )

    finish_reason: str | None = None

    provider: str | None = None

    model: str | None = None

    raw_response: Any = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class LLMProvider(ABC):

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        **kwargs,
    ) -> LLMResponse:
        pass

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        images: list[bytes] | None = None,
        **kwargs,
    ):
        pass

    @abstractmethod
    def capabilities(self) -> dict[str, bool]:
        pass