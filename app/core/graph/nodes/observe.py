"""
SERA 2.0 — Observe Node.
Extracts empirical observations from action results and environment state.
Strictly separates Action from Observation from Verification.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from app.core.graph.control import NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphObservation, GraphState


class ObserveNode(GraphNode):
    """Translates tool output and environment telemetry into structured GraphObservation."""

    def __init__(self):
        super().__init__("OBSERVE")

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
        raw_res = state.action_result

        observed_dict: Dict[str, Any] = {}
        summary_text = ""

        if isinstance(raw_res, dict):
            observed_dict = dict(raw_res)
            # Extract key observations
            if "application" in observed_dict:
                state.active_application = str(observed_dict["application"]).lower()
            elif "name" in observed_dict and action_name == "open_application":
                state.active_application = str(observed_dict["name"]).lower()

            step_args = (cur_step.arguments if cur_step else state.action_arguments) or {}
            if "brightness" in observed_dict:
                state.context_state["last_brightness"] = observed_dict["brightness"]
            elif "brightness" in step_args:
                state.context_state["last_brightness"] = step_args["brightness"]

            if "volume" in observed_dict:
                state.context_state["last_volume"] = observed_dict["volume"]
            elif "volume" in step_args:
                state.context_state["last_volume"] = step_args["volume"]

            if "dimensions" in observed_dict:
                summary_text = f"Screen buffer dimensions: {observed_dict['dimensions']}"
            elif "results" in observed_dict and isinstance(observed_dict["results"], list):
                summary_text = f"Found {len(observed_dict['results'])} structured results"
            elif "message" in observed_dict:
                summary_text = str(observed_dict["message"])
            else:
                summary_text = f"{action_name} executed with status {observed_dict.get('success', False)}"
        else:
            summary_text = str(raw_res) if raw_res is not None else "No output payload returned"
            observed_dict = {"raw": summary_text}

        state.observation = GraphObservation(
            action_name=action_name,
            raw_output=raw_res,
            observed_state=observed_dict,
            summary=summary_text,
        )
        state.current_phase = "OBSERVED"

        return NodeResult.continue_to("VERIFY", state)
