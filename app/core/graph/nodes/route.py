"""
SERA 2.0 — Route Node.
Evaluates normalized user input against deterministic intent rules and classifies route.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.core.command import CommandComplexity, CommandParser
from app.core.graph.control import ErrorCategory, NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphPlanStep, GraphState


class RouteNode(GraphNode):
    """Classifies user utterance into FAST_PATH, MULTI_STEP, CONVERSATIONAL, or REASONING."""

    def __init__(self, parser: Optional[CommandParser] = None):
        super().__init__("ROUTE")
        self.parser = parser or CommandParser()

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        cancelled = self.check_cancellation(state, cancellation_event)
        if cancelled:
            return cancelled

        # 0. Pre-populated plan steps on state (explicit caller or test injection)
        if state.steps:
            if len(state.steps) == 1:
                state.selected_route = "FAST_PATH"
                state.current_action = state.steps[0].action
                state.action_arguments = state.steps[0].arguments
                return NodeResult.continue_to("EXECUTE", state)
            else:
                state.selected_route = "MULTI_STEP"
                return NodeResult.continue_to("PLAN", state)

        text = state.normalized_user_input or state.raw_user_input

        # Parse command with context
        cmd = self.parser.parse(text, task_id=state.task_id, context=state.context_state)
        state.context_state["last_intent"] = cmd.intent
        if cmd.parameters.get("brightness"):
            state.context_state["last_brightness"] = cmd.parameters["brightness"]
        if cmd.parameters.get("volume"):
            state.context_state["last_volume"] = cmd.parameters["volume"]

        # 1. Conversational Fast-Path (0 tools, direct answer)
        if cmd.raw_response is not None:
            state.selected_route = "CONVERSATIONAL"
            state.final_response = cmd.raw_response
            state.current_phase = "COMPLETED"
            state.sera_status = "IDLE"
            return NodeResult.done(state, final_response=cmd.raw_response)

        # 2. Explicit Cancellation Command
        if cmd.intent == "cancel_current_task":
            state.selected_route = "CANCELLATION"
            state.final_response = "Task cancelled."
            return NodeResult.cancel(state, reason="Cancelled by user command")

        # 3. Deterministic Execution Plan Available
        if cmd.execution_plan:
            state.steps = [
                GraphPlanStep(
                    step_id=item.step_id,
                    goal=item.goal,
                    action=item.action,
                    arguments=dict(item.arguments),
                    timeout_seconds=item.timeout_seconds,
                    verification_type=item.verification_type,
                )
                for item in cmd.execution_plan
            ]
            state.current_step_index = 0

            if len(cmd.execution_plan) == 1:
                state.selected_route = "FAST_PATH"
                state.routing_reason = f"Deterministic single tool intent: {cmd.intent}"
                state.current_action = state.steps[0].action
                state.action_arguments = state.steps[0].arguments
                return NodeResult.continue_to("EXECUTE", state)
            else:
                state.selected_route = "MULTI_STEP"
                state.routing_reason = f"Deterministic compound multi-step intent: {cmd.intent}"
                return NodeResult.continue_to("PLAN", state)

        # 4. Ambiguous / Reasoning Fallback
        state.selected_route = "REASONING"
        state.routing_reason = "Ambiguous natural language request requiring model reasoning"
        return NodeResult.continue_to("PLAN", state)
