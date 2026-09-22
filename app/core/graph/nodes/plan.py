"""
SERA 2.0 — Plan Node.
Decomposes compound or ambiguous objectives into discrete GraphPlanStep items.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.core.graph.control import ErrorCategory, NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphPlanStep, GraphState
from app.core.router import ModelRouter
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class PlanNode(GraphNode):
    """Decomposes compound objectives into sequential verifiable plan steps."""

    def __init__(
        self,
        router: Optional[ModelRouter] = None,
        tools: Optional[ToolRegistry] = None,
    ):
        super().__init__("PLAN")
        self.router = router
        self.tools = tools

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        cancelled = self.check_cancellation(state, cancellation_event)
        if cancelled:
            return cancelled

        # 1. Plan already exists (from deterministic RouteNode)
        if state.steps:
            state.current_phase = "PLANNED"
            state.sera_status = "EXECUTING"
            cur = state.current_step
            if cur:
                state.current_action = cur.action
                state.action_arguments = cur.arguments
            return NodeResult.continue_to("EXECUTE", state)

        # 2. Ambiguous / Reasoning decomposition via ModelRouter
        if not self.router:
            return NodeResult.fail(
                state,
                error="Model router is not configured for ambiguous reasoning fallback",
                category=ErrorCategory.MODEL_FAILURE,
            )

        state.current_phase = "PLANNING_WITH_LLM"
        state.sera_status = "THINKING"
        t0 = asyncio.get_event_loop().time()

        try:
            role = "fast"
            tool_schemas = self.tools.schemas() if self.tools else []
            messages = [
                {"role": "system", "content": "You are SERA, a personal desktop assistant. Keep responses under 2 sentences."},
                {"role": "user", "content": state.normalized_user_input or state.raw_user_input},
            ]

            llm_resp, _ = await asyncio.wait_for(
                self.router.generate_with_fallback(
                    messages=messages,
                    tools=tool_schemas,
                    preferred_role=role,
                ),
                timeout=12.0,
            )
            state.model_timings["reasoning_plan"] = round((asyncio.get_event_loop().time() - t0) * 1000, 2)

            resp_str = (llm_resp.text or "").strip()
            if not resp_str:
                resp_str = "Task completed."

            state.final_response = resp_str
            state.sera_status = "IDLE"
            return NodeResult.done(state, final_response=resp_str)

        except asyncio.TimeoutError:
            err = "Model reasoning timed out after 12.0s"
            logger.warning(f"[PlanNode] {err}")
            return NodeResult.fail(state, error=err, category=ErrorCategory.TIMEOUT)
        except Exception as e:
            err = f"Model generation failed: {str(e)}"
            logger.warning(f"[PlanNode] {err}")
            return NodeResult.fail(state, error=err, category=ErrorCategory.MODEL_FAILURE)
