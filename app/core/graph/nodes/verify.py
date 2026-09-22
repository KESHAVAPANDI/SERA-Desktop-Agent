"""
SERA 2.0 — Verify Node.
First-class verification gate asserting empirical real-world side effects.
Zero false completions without validated evidence records.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.core.graph.control import NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphState, GraphVerification
from app.core.verification import EvidenceVerificationFabric

logger = logging.getLogger(__name__)


class VerifyNode(GraphNode):
    """Enforces empirical side-effect verification before task completion."""

    def __init__(self, fabric: Optional[EvidenceVerificationFabric] = None):
        super().__init__("VERIFY")
        self.fabric = fabric or EvidenceVerificationFabric()

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        cancelled = self.check_cancellation(state, cancellation_event)
        if cancelled:
            return cancelled

        cur_step = state.current_step
        action_name = cur_step.action if cur_step else (state.current_action or "unknown")

        t0 = time.perf_counter()

        # 1. Run empirical verification through EvidenceVerificationFabric
        evidence_rec = self.fabric.verify_tool_execution(action_name, state.action_result)

        dur_ms = round((time.perf_counter() - t0) * 1000, 2)
        state.verification_timings[action_name] = dur_ms

        verif = GraphVerification(
            verified=evidence_rec.verified,
            evidence_type=evidence_rec.evidence_type.value if hasattr(evidence_rec.evidence_type, "value") else str(evidence_rec.evidence_type),
            source=evidence_rec.source,
            details=dict(evidence_rec.details),
            failure_reason=evidence_rec.failure_reason,
        )

        state.verification = verif
        state.evidence = verif.to_dict()

        if verif.verified:
            state.current_phase = "VERIFIED"
            state.last_verified_action = action_name
            state.context_state["last_verified_action"] = action_name
            if cur_step:
                cur_step.completed = True
                cur_step.failed = False
                cur_step.error = None
        else:
            state.current_phase = "VERIFICATION_FAILED"
            tool_err = state.action_result.get("error") if isinstance(state.action_result, dict) else None
            state.last_error = tool_err or verif.failure_reason or f"Verification failed for {action_name}"
            if cur_step:
                cur_step.failed = True
                cur_step.error = state.last_error

        return NodeResult.continue_to("DECIDE", state)
