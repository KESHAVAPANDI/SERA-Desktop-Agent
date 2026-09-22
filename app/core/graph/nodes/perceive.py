"""
SERA 2.0 — Perceive Node.
Ingests user input, validates payload, stamps creation telemetry.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.core.graph.control import ErrorCategory, NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphState


class PerceiveNode(GraphNode):
    """Initial graph node ingesting raw user input."""

    def __init__(self):
        super().__init__("PERCEIVE")

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        cancelled = self.check_cancellation(state, cancellation_event)
        if cancelled:
            return cancelled

        raw = (state.raw_user_input or "").strip()
        if not raw:
            return NodeResult.fail(
                state,
                error="Received empty user utterance",
                category=ErrorCategory.INTERNAL_ERROR,
            )

        state.current_phase = "PERCEIVED"
        state.sera_status = "THINKING"
        return NodeResult.continue_to("NORMALIZE", state)
