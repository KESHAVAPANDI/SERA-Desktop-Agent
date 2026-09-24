"""
SERA 2.0 — First-Class Contextual Entity Model.

Defines strongly-typed contextual entities with stable identities, timestamps,
and session-scoped boundaries. Eliminates string-based and command-centric context.
Conforms strictly to Phase 3A-F Sections 4, 5, 7, and 9.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EntityType(str, Enum):
    APPLICATION = "APPLICATION"
    WINDOW = "WINDOW"
    BROWSER = "BROWSER"
    BROWSER_TAB = "BROWSER_TAB"
    SEARCH_SESSION = "SEARCH_SESSION"
    SEARCH_RESULT = "SEARCH_RESULT"
    FILE = "FILE"
    FOLDER = "FOLDER"
    SCREEN_ELEMENT = "SCREEN_ELEMENT"
    SYSTEM_SETTING = "SYSTEM_SETTING"


class SearchResultType(str, Enum):
    VIDEO = "VIDEO"
    SHORT = "SHORT"
    CHANNEL = "CHANNEL"
    PLAYLIST = "PLAYLIST"
    WEB_PAGE = "WEB_PAGE"
    OTHER = "OTHER"


@dataclass
class BaseEntity:
    """Base class for all first-class contextual entities."""
    entity_id: str = field(default_factory=lambda: f"ent_{uuid.uuid4().hex[:10]}")
    entity_type: EntityType = EntityType.APPLICATION
    created_at: float = field(default_factory=time.time)
    observed_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "created_at": self.created_at,
            "observed_at": self.observed_at,
            "metadata": dict(self.metadata),
        }


@dataclass
class ApplicationEntity(BaseEntity):
    """Represents a local Windows desktop application."""
    app_name: str = ""
    canonical_name: str = ""
    executable_path: Optional[str] = None
    process_ids: List[int] = field(default_factory=list)
    window_handles: List[int] = field(default_factory=list)
    is_active: bool = False

    def __post_init__(self):
        self.entity_type = EntityType.APPLICATION
        if not self.canonical_name:
            self.canonical_name = self.app_name.lower().strip()

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "app_name": self.app_name,
            "canonical_name": self.canonical_name,
            "executable_path": self.executable_path,
            "process_ids": list(self.process_ids),
            "window_handles": list(self.window_handles),
            "is_active": self.is_active,
        })
        return d


@dataclass
class WindowEntity(BaseEntity):
    """Represents a specific top-level Windows application window."""
    hwnd: int = 0
    title: str = ""
    app_name: str = ""
    process_id: int = 0
    is_foreground: bool = False

    def __post_init__(self):
        self.entity_type = EntityType.WINDOW

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "hwnd": self.hwnd,
            "title": self.title,
            "app_name": self.app_name,
            "process_id": self.process_id,
            "is_foreground": self.is_foreground,
        })
        return d


@dataclass
class BrowserTabEntity(BaseEntity):
    """Represents an active or observed browser tab with canonical URL and domain."""
    browser_name: str = "chrome"
    title: str = ""
    canonical_url: str = ""
    domain: str = ""
    is_active: bool = False
    hwnd: Optional[int] = None
    tab_ordinal: int = 0

    def __post_init__(self):
        self.entity_type = EntityType.BROWSER_TAB
        if not self.domain and "://" in self.canonical_url:
            try:
                parts = self.canonical_url.split("://")[1].split("/")[0]
                self.domain = parts.lower()
            except Exception:
                self.domain = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "browser_name": self.browser_name,
            "title": self.title,
            "canonical_url": self.canonical_url,
            "domain": self.domain,
            "is_active": self.is_active,
            "hwnd": self.hwnd,
            "tab_ordinal": self.tab_ordinal,
        })
        return d


@dataclass
class SearchResultEntity(BaseEntity):
    """Item-level normalized representation of a search result."""
    session_id: str = ""
    ordinal: int = 1
    title: str = ""
    canonical_url: str = ""
    source: str = "YouTube"  # "YouTube", "Google", "DuckDuckGo"
    result_type: SearchResultType = SearchResultType.VIDEO
    description: str = ""
    duration_str: Optional[str] = None
    channel_name: Optional[str] = None

    def __post_init__(self):
        self.entity_type = EntityType.SEARCH_RESULT

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "session_id": self.session_id,
            "ordinal": self.ordinal,
            "title": self.title,
            "canonical_url": self.canonical_url,
            "url": self.canonical_url,  # backward compatibility alias
            "source": self.source,
            "result_type": self.result_type.value,
            "description": self.description,
            "duration_str": self.duration_str,
            "channel_name": self.channel_name,
        })
        return d


@dataclass
class SearchSession(BaseEntity):
    """Session-scoped container for search operations. Isolates search contexts."""
    session_id: str = field(default_factory=lambda: f"search_{uuid.uuid4().hex[:8]}")
    query: str = ""
    source: str = "YouTube"
    results: List[SearchResultEntity] = field(default_factory=list)
    active_result_id: Optional[str] = None
    last_resolved_result_id: Optional[str] = None

    def __post_init__(self):
        self.entity_type = EntityType.SEARCH_SESSION
        self.entity_id = self.session_id

    def get_result_by_ordinal(self, ordinal: int) -> Optional[SearchResultEntity]:
        """1-indexed lookup of verified result entity."""
        idx = ordinal - 1
        if 0 <= idx < len(self.results):
            return self.results[idx]
        return None

    def add_result(self, result: SearchResultEntity) -> None:
        """Adds a normalized result entity to this search session."""
        self.results.append(result)

    def get_result_by_id(self, entity_id: str) -> Optional[SearchResultEntity]:
        for r in self.results:
            if r.entity_id == entity_id:
                return r
        return None

    def get_result_by_url(self, url: str) -> Optional[SearchResultEntity]:
        u = url.rstrip("/").lower()
        for r in self.results:
            if r.canonical_url.rstrip("/").lower() == u:
                return r
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "query": self.query,
            "source": self.source,
            "created_at": self.created_at,
            "results": [r.to_dict() for r in self.results],
            "active_result_id": self.active_result_id,
            "last_resolved_result_id": self.last_resolved_result_id,
        }


@dataclass
class SystemSettingEntity(BaseEntity):
    """Tracks scalar hardware settings with strict history for deterministic reversal."""
    setting_type: str = "brightness"  # "brightness", "volume", "mute"
    current_value: Any = None
    previous_value: Any = None
    history: List[Any] = field(default_factory=list)
    unit: str = "%"

    def __post_init__(self):
        self.entity_type = EntityType.SYSTEM_SETTING

    def update_value(self, new_val: Any) -> None:
        if self.current_value is not None and self.current_value != new_val:
            self.previous_value = self.current_value
            self.history.append(self.current_value)
            if len(self.history) > 10:
                self.history.pop(0)
        self.current_value = new_val
        self.observed_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "setting_type": self.setting_type,
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "history": list(self.history),
            "unit": self.unit,
        })
        return d


@dataclass
class ReplayableSemanticAction:
    """Fully validated, replayable execution object representing a verified side effect."""
    action_id: str = field(default_factory=lambda: f"act_{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    semantic_intent: str = ""
    resolved_entity_id: Optional[str] = None
    canonical_arguments: Dict[str, Any] = field(default_factory=dict)
    execution_plan_steps: List[Dict[str, Any]] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    preconditions: Dict[str, Any] = field(default_factory=dict)
    verification_type: str = "state_check"
    is_idempotent: bool = True
    executed_at: float = field(default_factory=time.time)
    verified_outcome: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "task_id": self.task_id,
            "semantic_intent": self.semantic_intent,
            "resolved_entity_id": self.resolved_entity_id,
            "canonical_arguments": dict(self.canonical_arguments),
            "execution_plan_steps": list(self.execution_plan_steps),
            "required_tools": list(self.required_tools),
            "preconditions": dict(self.preconditions),
            "verification_type": self.verification_type,
            "is_idempotent": self.is_idempotent,
            "executed_at": self.executed_at,
            "verified_outcome": dict(self.verified_outcome),
        }
