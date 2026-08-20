import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SERAStatus(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    SPEAKING = "SPEAKING"
    CONFIRMING_ACTION = "CONFIRMING_ACTION"
    # Task Lifecycle States (Phase 4)
    TASK_PLANNING = "TASK_PLANNING"
    TASK_EXECUTING = "TASK_EXECUTING"
    TASK_VERIFYING = "TASK_VERIFYING"
    TASK_RECOVERING = "TASK_RECOVERING"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_CANCELLED = "TASK_CANCELLED"
    ERROR = "ERROR"
    SHUTDOWN = "SHUTDOWN"


@dataclass
class SERAState:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: SERAStatus = SERAStatus.IDLE

    # Context & Active Task
    current_task: str | None = None
    last_user_message: str | None = None
    last_response: str | None = None

    # Model & Tool Tracking
    active_model_role: str | None = None
    active_tool_name: str | None = None
    last_tool_result: dict[str, Any] | None = None

    # Safety & Confirmation Flow
    pending_confirmation: dict[str, Any] | None = None

    # Conversation History
    conversation: list[dict[str, Any]] = field(default_factory=list)

    def transition_to(self, new_status: SERAStatus) -> None:
        """Updates the status of SERA."""
        self.status = new_status

    def set_pending_confirmation(self, tool_name: str, arguments: dict[str, Any], prompt: str) -> None:
        """Sets an action pending explicit confirmation."""
        self.status = SERAStatus.CONFIRMING_ACTION
        self.pending_confirmation = {
            "tool_name": tool_name,
            "arguments": arguments,
            "prompt": prompt,
        }

    def clear_confirmation(self) -> dict[str, Any] | None:
        """Clears and returns pending confirmation."""
        pending = self.pending_confirmation
        self.pending_confirmation = None
        return pending
