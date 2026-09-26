"""
SERA 2.0 / Phase 4A — Memory Contract & Architecture Interface.

Defines the boundary between Hermes' internal cognitive memory and
SERA's authoritative user identity, project state, and session history.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryScope(str, Enum):
    IDENTITY = "identity"                  # Authoritative user identity (goals, style, persona)
    STABLE_PREFERENCE = "stable_pref"      # Long-term verified preferences (e.g. Chrome, dark mode)
    EVOLVING_HABIT = "evolving_habit"      # Dialectic/inferred working patterns
    PROJECT_STATE = "project_state"        # Active workspace, open files, repo branches
    SESSION_WORKING = "session_working"    # Current turn entity referents, active search sessions


class UserIdentityProfile(BaseModel):
    """Authoritative user identity owned strictly by SERA."""
    user_id: str = "primary_user"
    display_name: str = "User"
    goals: List[str] = Field(default_factory=lambda: ["Build high-performance AI desktop assistant"])
    working_style: str = "concise, direct, empirical, safety-first"
    stable_preferences: Dict[str, Any] = Field(default_factory=lambda: {
        "preferred_browser": "chrome",
        "default_search_engine": "youtube",
        "theme": "dark",
        "volume_default": 60,
    })
    evolving_preferences: Dict[str, Any] = Field(default_factory=dict)


class MemoryRetrievalQuery(BaseModel):
    """Query emitted by Hermes reasoning to retrieve relevant memories."""
    query: str
    scopes: List[MemoryScope] = Field(default_factory=lambda: [MemoryScope.STABLE_PREFERENCE, MemoryScope.SESSION_WORKING])
    max_results: int = 5


class MemoryItem(BaseModel):
    """Retrieved memory item returned from SERA to Hermes."""
    scope: MemoryScope
    key: str
    value: Any
    confidence: float = 1.0
    source: str = "sera_context"
    timestamp: float = Field(default_factory=time.time)


class MemoryContract:
    """Defines the memory interface bridging Hermes reasoning and SERA state.
    
    Architectural Contract:
    - SERA owns: Identity, stable preferences, permissions, and project state.
    - Hermes owns: Ephemeral reasoning scratchpads, semantic association, and retrieval queries.
    - Neither may unilaterally overwrite identity or stable preferences without SERA confirmation.
    """

    def __init__(self, identity_profile: Optional[UserIdentityProfile] = None):
        self.profile = identity_profile or UserIdentityProfile()
        self._session_items: Dict[str, MemoryItem] = {}

    def query_memories(self, query: MemoryRetrievalQuery) -> List[MemoryItem]:
        """Provides filtered memory items to Hermes prompt construction."""
        results: List[MemoryItem] = []

        if MemoryScope.IDENTITY in query.scopes:
            results.append(MemoryItem(
                scope=MemoryScope.IDENTITY,
                key="user_profile",
                value={
                    "name": self.profile.display_name,
                    "goals": self.profile.goals,
                    "working_style": self.profile.working_style,
                }
            ))

        if MemoryScope.STABLE_PREFERENCE in query.scopes:
            for k, v in self.profile.stable_preferences.items():
                results.append(MemoryItem(
                    scope=MemoryScope.STABLE_PREFERENCE,
                    key=k,
                    value=v,
                ))

        if MemoryScope.SESSION_WORKING in query.scopes:
            for item in self._session_items.values():
                results.append(item)

        return results[:query.max_results]

    def record_session_memory(self, key: str, value: Any, scope: MemoryScope = MemoryScope.SESSION_WORKING) -> None:
        self._session_items[key] = MemoryItem(scope=scope, key=key, value=value)
