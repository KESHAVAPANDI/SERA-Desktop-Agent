"""
SERA 2.0 — Canonical Semantic Contract & Schema.

Defines the strongly typed semantic representation emitted by the
Semantic Interpreter. Conforms strictly to the Phase 3A-D architectural specification.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ActionFamily(str, Enum):
    APPLICATION = "APPLICATION"
    SYSTEM = "SYSTEM"
    BROWSER = "BROWSER"
    SCREEN = "SCREEN"
    CONTEXT = "CONTEXT"
    COMPOUND = "COMPOUND"
    CONVERSATION = "CONVERSATION"
    UNKNOWN = "UNKNOWN"


class TargetType(str, Enum):
    APPLICATION = "application"
    WINDOW = "window"
    BROWSER = "browser"
    TAB = "tab"
    WEBPAGE = "webpage"
    SEARCH_RESULT = "search_result"
    SETTING = "setting"
    FILE = "file"
    URL = "url"
    QUERY = "query"
    ENTITY = "entity"
    CUSTOM = "custom"


class ReferenceType(str, Enum):
    SEARCH_RESULT = "search_result"
    ACTIVE_WINDOW = "active_window"
    PREVIOUS_ACTION = "previous_action"
    TARGET_ENTITY = "target_entity"
    NONE = "none"


class SemanticTarget(BaseModel):
    """Target entity or object of the action."""
    type: Optional[str] = None  # e.g., "application", "setting", "query", "url"
    value: Optional[Union[str, int, float]] = None  # e.g., "chrome", "brightness", "python tutorials"
    attributes: Dict[str, Any] = Field(default_factory=dict)


class SemanticReference(BaseModel):
    """Contextual or anaphoric reference (e.g. 'first result', 'it', 'that')."""
    type: Optional[str] = None  # e.g. "search_result", "active_window", "previous_action"
    scope: Optional[str] = None  # e.g. "previous_search_results", "desktop", "session"
    ordinal: Optional[int] = None  # 1-indexed: 1 for first, 2 for second, -1 for last
    value: Optional[Union[str, int, float]] = None  # descriptive token if literal (e.g. "top")


class SemanticModifiers(BaseModel):
    """Linguistic and execution modifiers qualifying the intent."""
    repeat: bool = False
    relative: bool = False
    direction: Optional[str] = None  # "up", "down", "restore", "max", "min"
    temporal: Optional[str] = None  # "again", "previous", "next"
    qualifiers: Dict[str, Any] = Field(default_factory=dict)


class SemanticContextResolution(BaseModel):
    """Status of contextual entity resolution."""
    resolved: bool = False
    context_entity_id: Optional[Union[str, int]] = None
    context_source: Optional[str] = None


class CanonicalIntent(BaseModel):
    """Canonical, strongly-typed semantic intent representation.
    
    The Semantic Interpreter converts (utterance + compact context + capabilities)
    into this schema. The Graph Runtime reads this to construct execution steps.
    """
    semantic_request_id: str = Field(default_factory=lambda: f"sem_{uuid.uuid4().hex[:8]}")
    intent: str  # Canonical intent name
    action_family: str = ActionFamily.UNKNOWN.value
    target: Optional[SemanticTarget] = None
    reference: Optional[SemanticReference] = None
    modifiers: SemanticModifiers = Field(default_factory=SemanticModifiers)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context_resolution: SemanticContextResolution = Field(default_factory=SemanticContextResolution)
    confidence: float = 1.0
    needs_clarification: bool = False
    ambiguity_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CompactSemanticContext(BaseModel):
    """Compact context passed to the Semantic Interpreter.
    
    Contains only language-relevant state. Never contains full GraphState,
    system logs, secrets, or file trees.
    """
    utterance: str
    active_application: Optional[str] = None
    active_browser: Optional[str] = None
    active_tab: Optional[str] = None
    current_url: Optional[str] = None
    last_verified_action: Optional[str] = None
    recent_verified_actions: List[Dict[str, Any]] = Field(default_factory=list)
    relevant_entities: List[Dict[str, Any]] = Field(default_factory=list)
    available_intents: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
