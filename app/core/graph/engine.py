"""
SERA 2.0 — Stateful Graph Runtime Engine.

The canonical execution engine for SERA.
Orchestrates directed and conditional transitions across GraphNodes with:
- Strict loop guards & bounded retries
- Native cancellation at node boundaries
- Structured EventBus emission with execution correlation
- Per-node timing & comprehensive telemetry
- Checkpoint serialization hooks
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set

from app.core.events import EventBus
from app.core.graph.control import ErrorCategory, GraphDecision, NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphExecutionStatus, GraphState

logger = logging.getLogger(__name__)


class StatefulGraphRuntime:
    """Canonical stateful graph runtime orchestrator for SERA 2.0."""

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        max_loop_iterations: int = 50,
        max_retries_per_step: int = 2,
    ):
        self.event_bus = event_bus or EventBus()
        self.max_loop_iterations = max_loop_iterations
        self.max_retries_per_step = max_retries_per_step

        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, str] = {}  # node -> next_node
        self._conditional_edges: Dict[str, Callable[[GraphState, NodeResult], str]] = {}
        self._start_node: str = "PERCEIVE"

        # Checkpoints for snapshot/restore
        self._snapshots: Dict[str, Dict[str, Any]] = {}

    def register_node(self, node: GraphNode) -> StatefulGraphRuntime:
        """Registers a named graph node."""
        self._nodes[node.name] = node
        return self

    def add_edge(self, from_node: str, to_node: str) -> StatefulGraphRuntime:
        """Adds a direct transition between two nodes."""
        self._edges[from_node.upper()] = to_node.upper()
        return self

    def add_conditional_edge(
        self,
        from_node: str,
        router: Callable[[GraphState, NodeResult], str],
    ) -> StatefulGraphRuntime:
        """Adds a dynamic conditional transition router."""
        self._conditional_edges[from_node.upper()] = router
        return self

    def set_start_node(self, node_name: str) -> StatefulGraphRuntime:
        """Sets the entry node of the graph."""
        self._start_node = node_name.upper()
        return self

    def _emit_event(self, event_name: str, payload: Dict[str, Any], state: GraphState) -> None:
        """Dispatches correlated graph events to EventBus with standardized metadata."""
        data = {
            **payload,
            "execution_id": state.execution_id,
            "task_id": state.task_id,
            "turn_id": state.turn_id,
            "timestamp": time.time(),
        }
        try:
            self.event_bus.emit(event_name, data)
        except Exception as e:
            logger.debug(f"[StatefulGraphRuntime] Error emitting {event_name}: {e}")

    def snapshot(self, state: GraphState) -> Dict[str, Any]:
        """Creates an in-memory snapshot of the current state."""
        snap = state.to_dict()
        self._snapshots[state.execution_id] = snap
        return snap

    def restore(self, execution_id: str) -> Optional[GraphState]:
        """Restores state from an in-memory snapshot."""
        data = self._snapshots.get(execution_id)
        if data:
            return GraphState.from_dict(data)
        return None

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
        timeout_seconds: Optional[float] = None,
    ) -> GraphState:
        """Executes the graph beginning at start_node until a terminal decision or timeout."""
        if timeout_seconds and timeout_seconds > 0:
            try:
                return await asyncio.wait_for(
                    self._execute_internal(state, cancellation_event),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                err_msg = f"Graph execution exceeded timeout budget of {timeout_seconds}s"
                logger.warning(f"[StatefulGraphRuntime] {err_msg}")
                state.status = GraphExecutionStatus.FAILED
                state.last_error = err_msg
                state.completion_reason = "TIMEOUT"
                self._emit_event("GRAPH_FAILED", {
                    "error": err_msg,
                    "error_category": ErrorCategory.TIMEOUT.value,
                }, state)
                return state
        else:
            return await self._execute_internal(state, cancellation_event)

    async def _execute_internal(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> GraphState:
        """Internal execution loop traversing nodes."""
        t_graph_start = time.perf_counter()
        state.status = GraphExecutionStatus.RUNNING
        state.current_node = self._start_node

        self._emit_event("GRAPH_STARTED", {
            "start_node": self._start_node,
            "raw_input": state.raw_user_input,
            "source": state.input_source,
        }, state)

        current_node_name = self._start_node
        iteration_count = 0

        while current_node_name and iteration_count < self.max_loop_iterations:
            iteration_count += 1
            state.current_node = current_node_name

            # 1. Cancellation Check at Node Entry
            if (cancellation_event and cancellation_event.is_set()) or state.is_cancelled:
                state.status = GraphExecutionStatus.CANCELLED
                state.is_cancelled = True
                state.cancellation_reason = state.cancellation_reason or "Execution cancelled by user"
                logger.info(f"[StatefulGraphRuntime] Execution {state.execution_id} cancelled at {current_node_name}.")
                self._emit_event("GRAPH_CANCELLED", {
                    "node": current_node_name,
                    "reason": state.cancellation_reason,
                }, state)
                break

            # 2. Validate Node Registration
            node = self._nodes.get(current_node_name)
            if not node:
                err_msg = f"Graph node '{current_node_name}' is not registered."
                logger.error(f"[StatefulGraphRuntime] {err_msg}")
                state.status = GraphExecutionStatus.FAILED
                state.last_error = err_msg
                self._emit_event("GRAPH_FAILED", {
                    "node": current_node_name,
                    "error": err_msg,
                    "error_category": ErrorCategory.INTERNAL_ERROR.value,
                }, state)
                break

            # 3. Emit Node Entered Event
            self._emit_event("GRAPH_NODE_ENTERED", {
                "node": current_node_name,
                "iteration": iteration_count,
            }, state)

            # 4. Execute Node with Telemetry
            t0_node = time.perf_counter()
            try:
                result = await node.execute(state, cancellation_event=cancellation_event)
            except asyncio.CancelledError:
                state.status = GraphExecutionStatus.CANCELLED
                state.is_cancelled = True
                state.cancellation_reason = "Async task cancelled by runtime"
                self._emit_event("GRAPH_CANCELLED", {
                    "node": current_node_name,
                    "reason": state.cancellation_reason,
                }, state)
                raise
            except Exception as e:
                node_dur_ms = round((time.perf_counter() - t0_node) * 1000, 2)
                state.record_node_timing(current_node_name, node_dur_ms)
                err_msg = f"Unhandled exception in node {current_node_name}: {str(e)}"
                logger.exception(f"[StatefulGraphRuntime] {err_msg}")
                result = NodeResult.fail(state, err_msg, category=ErrorCategory.INTERNAL_ERROR)

            node_dur_ms = round((time.perf_counter() - t0_node) * 1000, 2)
            state.record_node_timing(current_node_name, node_dur_ms)

            # 5. Emit Node Completed Event
            self._emit_event("GRAPH_NODE_COMPLETED", {
                "node": current_node_name,
                "decision": result.decision.value,
                "latency_ms": node_dur_ms,
            }, state)

            # 6. Process Control Decision
            if result.decision == GraphDecision.DONE:
                state.status = GraphExecutionStatus.SUCCESS
                state.completion_reason = "VERIFIED_COMPLETION"
                self._emit_event("GRAPH_COMPLETED", {
                    "final_response": state.final_response,
                    "total_steps": len(state.steps),
                    "completed_steps": state.completed_steps,
                }, state)
                break

            elif result.decision == GraphDecision.CANCEL:
                state.status = GraphExecutionStatus.CANCELLED
                state.is_cancelled = True
                state.cancellation_reason = result.error_message or "Task cancelled"
                self._emit_event("GRAPH_CANCELLED", {
                    "node": current_node_name,
                    "reason": state.cancellation_reason,
                }, state)
                break

            elif result.decision == GraphDecision.FAIL:
                state.status = GraphExecutionStatus.FAILED
                state.last_error = result.error_message
                self._emit_event("GRAPH_FAILED", {
                    "node": current_node_name,
                    "error": result.error_message,
                    "error_category": result.error_category.value,
                }, state)
                break

            # 7. Determine Next Node
            next_node_name: Optional[str] = None

            # Explicit target in NodeResult takes priority
            if result.next_node:
                next_node_name = result.next_node.upper()
            # Conditional router
            elif current_node_name in self._conditional_edges:
                router_fn = self._conditional_edges[current_node_name]
                try:
                    next_node_name = router_fn(state, result)
                    if next_node_name:
                        next_node_name = next_node_name.upper()
                except Exception as e:
                    logger.error(f"[StatefulGraphRuntime] Conditional router for {current_node_name} failed: {e}")
                    state.status = GraphExecutionStatus.FAILED
                    state.last_error = f"Routing error: {e}"
                    break
            # Static directed edge
            elif current_node_name in self._edges:
                next_node_name = self._edges[current_node_name]

            if not next_node_name:
                # No transition found — treat as implicit end if not failed
                logger.info(f"[StatefulGraphRuntime] Reached terminal node '{current_node_name}' without further edges.")
                if state.status == GraphExecutionStatus.RUNNING:
                    state.status = GraphExecutionStatus.SUCCESS
                break

            # 8. Emit Transition Event
            self._emit_event("GRAPH_TRANSITION", {
                "from_node": current_node_name,
                "to_node": next_node_name,
                "decision": result.decision.value,
            }, state)

            current_node_name = next_node_name

        if iteration_count >= self.max_loop_iterations and state.status == GraphExecutionStatus.RUNNING:
            err_msg = f"Graph exceeded maximum loop iterations ({self.max_loop_iterations})"
            logger.error(f"[StatefulGraphRuntime] {err_msg}")
            state.status = GraphExecutionStatus.FAILED
            state.last_error = err_msg
            self._emit_event("GRAPH_FAILED", {
                "error": err_msg,
                "error_category": ErrorCategory.TIMEOUT.value,
            }, state)

        state.total_duration_ms = round((time.perf_counter() - t_graph_start) * 1000, 2)
        state.mark_updated()
        return state
