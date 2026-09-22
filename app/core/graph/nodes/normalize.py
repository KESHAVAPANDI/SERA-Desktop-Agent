"""
SERA 2.0 — Normalize Node.
Normalizes addressing, vocatives, and courtesy prefixes while preserving self-close targets.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.core.command import normalize_conversational_utterance
from app.core.graph.control import NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphState


class NormalizeNode(GraphNode):
    """Normalizes natural conversational addressing, vocatives, and politeness markers."""

    def __init__(self):
        super().__init__("NORMALIZE")

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        cancelled = self.check_cancellation(state, cancellation_event)
        if cancelled:
            return cancelled

        cleaned, is_pure_address = normalize_conversational_utterance(state.raw_user_input)

        if is_pure_address:
            state.normalized_user_input = ""
            state.current_objective = "Acknowledge user presence"
            state.final_response = "Yes? I'm listening."
            state.sera_status = "LISTENING"
            return NodeResult.done(state, final_response="Yes? I'm listening.")

        state.normalized_user_input = cleaned or state.raw_user_input
        state.current_objective = state.normalized_user_input
        state.current_phase = "NORMALIZED"

        return NodeResult.continue_to("CONTEXT", state)
