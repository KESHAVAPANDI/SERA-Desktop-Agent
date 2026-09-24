"""
SERA 2.0 — Context & Entity Package.

Provides ContextStore, first-class entities, session-scoped search contexts,
and backward-compatible ConversationContext.
"""

from typing import Any, Dict

from app.core.context.entities import (
    ApplicationEntity,
    BaseEntity,
    BrowserTabEntity,
    EntityType,
    ReplayableSemanticAction,
    SearchResultEntity,
    SearchResultType,
    SearchSession,
    SystemSettingEntity,
    WindowEntity,
)
from app.core.context.store import ContextStore
from app.memory.short_term import ShortTermMemory


class ConversationContext:
    """Manages active conversation turn context and state metadata.
    Backed by ContextStore for entity consistency and backward compatibility.
    """

    def __init__(self, store: ContextStore | None = None):
        self.memory = ShortTermMemory()
        self.store = store or ContextStore()
        self.current_state: Dict[str, Any] = {}

    def update_state(self, key: str, value: Any):
        """Updates transient turn context state."""
        self.current_state[key] = value
        self.store.update_from_legacy_dict({key: value})

    def get_state(self, key: str, default: Any = None) -> Any:
        """Retrieves value from state."""
        return self.current_state.get(key, default)


__all__ = [
    "ContextStore",
    "ConversationContext",
    "BaseEntity",
    "EntityType",
    "ApplicationEntity",
    "WindowEntity",
    "BrowserTabEntity",
    "SearchResultEntity",
    "SearchResultType",
    "SearchSession",
    "SystemSettingEntity",
    "ReplayableSemanticAction",
]
