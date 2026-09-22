"""
SERA 2.0 — Decide Node.
Governs graph lifecycle decisions (DONE, CONTINUE, RETRY, REPLAN, FAIL) based on verification evidence.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.core.graph.control import ErrorCategory, NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphState

logger = logging.getLogger(__name__)


class DecideNode(GraphNode):
    """Evaluates verification evidence and governs loop transitions."""

    def __init__(self):
        super().__init__("DECIDE")

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        cancelled = self.check_cancellation(state, cancellation_event)
        if cancelled:
            return cancelled

        is_verified = bool(state.verification and state.verification.verified)

        # ---------------------------------------------------------
        # BRANCH A: Verification Succeeded
        # ---------------------------------------------------------
        if is_verified:
            # Advance step and check if more steps remain in multi-step plan
            if state.steps and (state.current_step_index + 1 < len(state.steps)):
                state.advance_step()
                next_step = state.current_step
                if next_step:
                    state.current_action = next_step.action
                    state.action_arguments = next_step.arguments
                    state.task_progress = round(len(state.completed_steps) / len(state.steps), 2)
                    logger.info(f"[DecideNode] Step verified. Continuing to step {next_step.step_id}/{len(state.steps)}: {next_step.goal}")
                    return NodeResult.continue_to("EXECUTE", state)

            # Final step verified — transition to response synthesis
            if state.steps:
                state.task_progress = 1.0
                if state.current_step:
                    state.current_step.completed = True
                    if state.current_step.step_id not in state.completed_steps:
                        state.completed_steps.append(state.current_step.step_id)

            logger.info(f"[DecideNode] All steps verified. Transitioning to RESPOND.")
            return NodeResult.continue_to("RESPOND", state)

        # ---------------------------------------------------------
        # BRANCH B: Verification Failed -> Recovery Evaluation
        # ---------------------------------------------------------
        err_msg = state.last_error or "Verification check failed."
        logger.warning(f"[DecideNode] Verification failure: {err_msg}")

        # 1. Bounded Step Retry Check
        if state.retry_count < state.max_retries_per_step:
            state.retry_count += 1
            logger.info(f"[DecideNode] Initiating bounded retry {state.retry_count}/{state.max_retries_per_step}...")
            return NodeResult.continue_to("RECOVER", state)

        # 2. Bounded Replan Check
        if state.replan_count < state.max_replans and len(state.steps) > 1:
            state.replan_count += 1
            logger.info(f"[DecideNode] Step retries exhausted. Initiating replan {state.replan_count}/{state.max_replans}...")
            return NodeResult.replan(state, reason=err_msg)

        # 3. Terminal Failure
        logger.error(f"[DecideNode] Recovery attempts exhausted. Failing execution: {err_msg}")
        return NodeResult.fail(
            state,
            error=err_msg,
            category=ErrorCategory.VERIFICATION_FAILED,
        )
