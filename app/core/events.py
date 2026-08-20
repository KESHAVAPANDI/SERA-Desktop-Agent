import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class UserMessage:
    content: str


@dataclass
class AssistantMessage:
    content: str | None = None


@dataclass
class ToolCallEvent:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class ToolResultEvent:
    call_id: str
    tool_name: str
    result: Any


@dataclass
class AgentTurn:
    user: UserMessage
    assistant: AssistantMessage | None = None
    tool_calls: list[ToolCallEvent] = field(default_factory=list)
    tool_results: list[ToolResultEvent] = field(default_factory=list)


class EventBus:
    """Pub-Sub Event Bus for internal assistant event communication."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable):
        """Subscribes callback to event."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    async def emit_async(self, event_name: str, **kwargs):
        """Publishes event to all registered subscriber callbacks (handling both async and sync)."""
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    if inspect.iscoroutinefunction(callback):
                        await callback(**kwargs)
                    else:
                        callback(**kwargs)
                except Exception as e:
                    logger.error(f"Error executing async listener for {event_name}: {e}")

    def emit(self, event_name: str, **kwargs):
        """Synchronously publishes event to registered sync subscriber callbacks."""
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    if not inspect.iscoroutinefunction(callback):
                        callback(**kwargs)
                except Exception as e:
                    logger.error(f"Error executing sync listener for {event_name}: {e}")

    publish = emit