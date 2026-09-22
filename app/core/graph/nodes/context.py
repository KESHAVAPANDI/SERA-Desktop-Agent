"""
SERA 2.0 — Context Node.
Binds active desktop entity context, conversation state, and follow-up references.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from app.core.graph.control import NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphState


class ContextNode(GraphNode):
    """Enriches state with active desktop entities and conversational references."""

    def __init__(self, context_provider: Optional[Dict[str, Any]] = None):
        super().__init__("CONTEXT")
        self.context_provider = context_provider or {}

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        cancelled = self.check_cancellation(state, cancellation_event)
        if cancelled:
            return cancelled

        # Populate context if not already present
        if self.context_provider:
            for k, v in self.context_provider.items():
                if k not in state.context_state:
                    state.context_state[k] = v

        # Align active application / entity from context
        if not state.active_application and state.context_state.get("last_application"):
            state.active_application = state.context_state["last_application"]

        if not state.last_verified_action and state.context_state.get("last_verified_action"):
            state.last_verified_action = state.context_state["last_verified_action"]

        state.current_phase = "CONTEXT_RESOLVED"
        return NodeResult.continue_to("ROUTE", state)
