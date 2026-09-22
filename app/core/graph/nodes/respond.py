"""
SERA 2.0 — Respond Node.
Synthesizes clean, concise, single-sentence conversational completion responses.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.core.graph.control import NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphState


class RespondNode(GraphNode):
    """Synthesizes human-friendly response after verified execution."""

    def __init__(self):
        super().__init__("RESPOND")

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        cancelled = self.check_cancellation(state, cancellation_event)
        if cancelled:
            return cancelled

        # Preserve existing response if already populated
        if state.final_response:
            state.current_phase = "COMPLETED"
            state.sera_status = "IDLE"
            return NodeResult.done(state, final_response=state.final_response)

        action = state.last_verified_action or state.current_action or ""
        obs = state.observation.observed_state if state.observation else {}

        # Synthesize conversational response based on verified action
        if action == "set_brightness":
            val = obs.get("brightness") or state.context_state.get("last_brightness", 80)
            resp = f"I've set the brightness to {val} percent."
        elif action == "set_volume":
            val = obs.get("volume") or state.context_state.get("last_volume", 50)
            resp = f"I've set the volume to {val} percent."
        elif action == "capture_screen":
            dim = obs.get("dimensions", "")
            resp = f"Screenshot captured successfully ({dim})." if dim else "Screenshot captured successfully."
        elif action in ("open_application", "launch_application"):
            app_name = obs.get("application") or obs.get("name") or state.active_application or "the application"
            resp = f"I've opened {app_name.capitalize()}."
        elif action == "close_application":
            app_name = obs.get("application") or obs.get("name") or "the application"
            resp = f"I've closed {app_name.capitalize()}."
        elif action == "sera_self_close":
            resp = "Goodbye! Closing presence now."
        elif action in ("duckduckgo_search", "web_search"):
            count = len(obs.get("results", []))
            resp = f"I found {count} search results." if count else "Search completed."
        elif action == "youtube_search":
            resp = "I've searched YouTube and opened the results."
        else:
            resp = obs.get("message") or "Task completed."

        state.final_response = str(resp)
        state.current_phase = "COMPLETED"
        state.sera_status = "IDLE"
        return NodeResult.done(state, final_response=state.final_response)
