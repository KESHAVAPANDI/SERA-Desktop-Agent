"""
SERA 2.0 — Recover Node.
Executes recovery stabilization before bounded re-execution of a failed step.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.core.graph.control import NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphState

logger = logging.getLogger(__name__)


class RecoverNode(GraphNode):
    """Applies recovery stabilization and loops back to EXECUTE for a bounded retry."""

    def __init__(self, backoff_seconds: float = 0.1):
        super().__init__("RECOVER")
        self.backoff_seconds = backoff_seconds

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        cancelled = self.check_cancellation(state, cancellation_event)
        if cancelled:
            return cancelled

        state.current_phase = f"RECOVERING_RETRY_{state.retry_count}"
        state.sera_status = "RECOVERING"

        # Brief backoff delay for OS window/process stabilization
        if self.backoff_seconds > 0:
            await asyncio.sleep(self.backoff_seconds)

        # Check cancellation after sleep
        cancelled_after = self.check_cancellation(state, cancellation_event)
        if cancelled_after:
            return cancelled_after

        logger.info(f"[RecoverNode] State stabilized. Retrying action '{state.current_action}'...")
        return NodeResult.continue_to("EXECUTE", state)
