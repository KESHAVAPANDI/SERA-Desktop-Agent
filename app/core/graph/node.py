"""
SERA 2.0 — Graph Node Protocol and Base Class.

Every graph node must strictly adhere to this contract.
Nodes receive GraphState and return a structured NodeResult.
Nodes must not communicate by passing arbitrary unformatted prose.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import time
from typing import Optional

from app.core.graph.control import NodeResult
from app.core.graph.state import GraphState

logger = logging.getLogger(__name__)


class GraphNode(abc.ABC):
    """Abstract base class for all nodes in the stateful graph runtime."""

    def __init__(self, name: str):
        self.name = name.upper()

    @abc.abstractmethod
    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        """Executes node logic and returns structured NodeResult with updated state."""
        pass

    def check_cancellation(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> Optional[NodeResult]:
        """Convenience helper to check cancellation at node entry or checkpoints."""
        if cancellation_event and cancellation_event.is_set():
            return NodeResult.cancel(state, reason=f"Task cancelled before or during {self.name}")
        if state.is_cancelled:
            return NodeResult.cancel(state, reason=state.cancellation_reason or f"Task cancelled at {self.name}")
        return None
