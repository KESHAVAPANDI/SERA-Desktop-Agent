from typing import Dict, Any
from app.memory.short_term import ShortTermMemory

class ConversationContext:
    """Manages active conversation turn context and state metadata."""

    def __init__(self):
        self.memory = ShortTermMemory()
        self.current_state: Dict[str, Any] = {}

    def update_state(self, key: str, value: Any):
        """Updates transient turn context state."""
        self.current_state[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """Retrieves value from state."""
        return self.current_state.get(key, default)
