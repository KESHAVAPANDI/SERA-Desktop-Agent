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


TERMINAL_EVENTS = frozenset({"TASK_COMPLETED", "TASK_FAILED", "TASK_CANCELLED"})


class TerminalStateGovernor:
    """Enforces monotonic terminal state across task lifecycle (Section 27).

    Once a task reaches FAILED, CANCELLED, or COMPLETED, it cannot later emit
    a contradictory or duplicate terminal event for the same task_id.
    """

    def __init__(self, max_history: int = 1000):
        self._terminal_tasks: dict[str, str] = {}
        self._max_history = max_history

    def check_terminal_event(self, event_name: str, task_id: str | None) -> bool:
        """Returns True if event should be emitted, False if it violates monotonicity."""
        if not task_id or event_name not in TERMINAL_EVENTS:
            return True

        if task_id in self._terminal_tasks:
            prev_event = self._terminal_tasks[task_id]
            logger.warning(
                f"[TerminalStateGovernor] Monotonicity violation: task '{task_id}' "
                f"already terminated with '{prev_event}'. Dropping contradictory '{event_name}'."
            )
            return False

        if len(self._terminal_tasks) >= self._max_history:
            keys_to_remove = list(self._terminal_tasks.keys())[:200]
            for k in keys_to_remove:
                del self._terminal_tasks[k]

        self._terminal_tasks[task_id] = event_name
        return True


class EventBus:
    """Pub-Sub Event Bus for internal assistant event communication supporting both positional payloads and kwargs."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._governor = TerminalStateGovernor()

    def _extract_task_id(self, payload: Any, kwargs: dict) -> str | None:
        if isinstance(payload, dict):
            return payload.get("task_id")
        return kwargs.get("task_id")

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
        task_id = self._extract_task_id(payload, kwargs)
        if not self._governor.check_terminal_event(event_name, task_id):
            return

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
        task_id = self._extract_task_id(payload, kwargs)
        if not self._governor.check_terminal_event(event_name, task_id):
            return

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