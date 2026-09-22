"""
SERA 2.0 — Execute Node.
Invokes registered tools through the ToolRegistry with bounded timeout and safety guards.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.core.graph.control import ErrorCategory, NodeResult
from app.core.graph.node import GraphNode
from app.core.graph.state import GraphState
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ExecuteNode(GraphNode):
    """Executes the action defined in the active plan step through the ToolRegistry."""

    def __init__(self, tools: ToolRegistry):
        super().__init__("EXECUTE")
        self.tools = tools

    async def execute(
        self,
        state: GraphState,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> NodeResult:
        cancelled = self.check_cancellation(state, cancellation_event)
        if cancelled:
            return cancelled

        cur_step = state.current_step
        if cur_step:
            tool_name = cur_step.action
            tool_args = cur_step.arguments
            step_timeout = cur_step.timeout_seconds
        else:
            tool_name = state.current_action or ""
            tool_args = state.action_arguments or {}
            step_timeout = 10.0

        if not tool_name:
            return NodeResult.fail(
                state,
                error="ExecuteNode invoked without a defined tool action",
                category=ErrorCategory.INVALID_PLAN,
            )

        # 1. Lookup registered tool
        tool = self.tools.get(tool_name)
        if not tool:
            err = f"Tool '{tool_name}' is not registered in ToolRegistry"
            logger.error(f"[ExecuteNode] {err}")
            return NodeResult.fail(state, error=err, category=ErrorCategory.TOOL_EXCEPTION)

        # 2. Execute with bounded timeout and real-time cancellation monitoring
        state.current_phase = "EXECUTING"
        state.sera_status = "EXECUTING"
        t0 = time.perf_counter()

        try:
            tool_coro = tool.execute(**tool_args)
            if cancellation_event:
                tool_task = asyncio.create_task(tool_coro)
                cancel_wait_task = asyncio.create_task(cancellation_event.wait())
                done, pending = await asyncio.wait(
                    [tool_task, cancel_wait_task],
                    timeout=step_timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for p in pending:
                    p.cancel()
                    try:
                        await p
                    except (asyncio.CancelledError, Exception):
                        pass

                if cancellation_event.is_set():
                    state.is_cancelled = True
                    return NodeResult.cancel(state, reason="Execution cancelled during tool call")

                if not done:
                    raise asyncio.TimeoutError()

                tool_res = tool_task.result()
            else:
                tool_res = await asyncio.wait_for(tool_coro, timeout=step_timeout)

            dur_ms = round((time.perf_counter() - t0) * 1000, 2)
            state.tool_timings[tool_name] = dur_ms
            if cur_step:
                cur_step.latency_ms = dur_ms

            state.action_result = tool_res
            state.current_phase = "EXECUTED"

            # Check if cancellation was flagged during execution
            cancelled_after = self.check_cancellation(state, cancellation_event)
            if cancelled_after:
                return cancelled_after

            return NodeResult.continue_to("OBSERVE", state)

        except asyncio.CancelledError:
            if cancellation_event and cancellation_event.is_set():
                state.is_cancelled = True
                return NodeResult.cancel(state, reason="Execution cancelled during tool call")
            raise

        except asyncio.TimeoutError:
            dur_ms = round((time.perf_counter() - t0) * 1000, 2)
            state.tool_timings[tool_name] = dur_ms
            err = f"Tool '{tool_name}' timed out after {step_timeout}s"
            logger.warning(f"[ExecuteNode] {err}")
            state.last_error = err
            if cur_step:
                cur_step.failed = True
                cur_step.error = err
            return NodeResult.fail(state, error=err, category=ErrorCategory.TIMEOUT)

        except Exception as e:
            dur_ms = round((time.perf_counter() - t0) * 1000, 2)
            state.tool_timings[tool_name] = dur_ms
            err = f"Exception executing tool '{tool_name}': {str(e)}"
            logger.exception(f"[ExecuteNode] {err}")
            state.last_error = err
            if cur_step:
                cur_step.failed = True
                cur_step.error = err
            return NodeResult.fail(state, error=err, category=ErrorCategory.TOOL_EXCEPTION)
