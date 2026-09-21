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
    """Pub-Sub Event Bus for internal assistant event communication supporting both positional payloads and kwargs."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable):
        """Subscribes callback to event."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def on(self, event_name: str, callback: Callable):
        """Alias for subscribe."""
        self.subscribe(event_name, callback)

    async def emit_async(self, event_name: str, payload: Any = None, **kwargs):
        """Publishes event to all registered subscriber callbacks (handling both async and sync)."""
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    if inspect.iscoroutinefunction(callback):
                        if payload is not None and not kwargs:
                            await callback(payload)
                        elif payload is not None and isinstance(payload, dict):
                            await callback(**{**payload, **kwargs})
                        else:
                            await callback(**kwargs)
                    else:
                        if payload is not None and not kwargs:
                            callback(payload)
                        elif payload is not None and isinstance(payload, dict):
                            callback(**{**payload, **kwargs})
                        else:
                            callback(**kwargs)
                except Exception as e:
                    logger.debug(f"Error executing async listener for {event_name}: {e}")

    def emit(self, event_name: str, payload: Any = None, **kwargs):
        """Synchronously publishes event to registered sync subscriber callbacks."""
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    if not inspect.iscoroutinefunction(callback):
                        if payload is not None and not kwargs:
                            callback(payload)
                        elif payload is not None and isinstance(payload, dict):
                            callback(**{**payload, **kwargs})
                        else:
                            callback(**kwargs)
                except Exception as e:
                    logger.debug(f"Error executing sync listener for {event_name}: {e}")

    publish = emit