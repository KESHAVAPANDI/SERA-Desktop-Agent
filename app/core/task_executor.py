import asyncio
import logging
import time
from typing import Any
from pydantic import BaseModel, Field

from app.core.events import EventBus
from app.core.planner import TaskPlan, PlanStep
from app.core.state import SERAState, SERAStatus
from app.core.telemetry import LatencyMetrics
from app.tools.desktop.executor import DesktopActionExecutor
from app.tools.desktop.models import SemanticActionRequest
from app.tools.desktop.target_resolver import TargetResolver
from app.tools.desktop.ui_inspector import WindowsUIInspector
from app.tools.registry import ToolRegistry
from app.vision.analyzer import ScreenPerceptionEngine

logger = logging.getLogger(__name__)


class TaskExecutionResult(BaseModel):
    """Structured outcome of a multi-step task execution."""
    success: bool = Field(description="Whether all plan steps succeeded and were verified")
    task: str = Field(description="Original user task")
    steps_completed: int = Field(default=0, description="Count of successfully verified steps")
    total_steps: int = Field(default=0, description="Total number of steps in plan")
    summary_message: str = Field(default="", description="Concise human-readable outcome summary")
    failure_reason: str | None = Field(default=None, description="Reason for failure or cancellation if any")
    is_cancelled: bool = Field(default=False, description="Whether task was interrupted by user")
    total_latency_ms: float = Field(default=0.0, description="Total runtime in milliseconds")


class MultiStepExecutor:
    """Bounded, observable, cancellable, and verifiable multi-step desktop execution engine."""

    def __init__(
        self,
        tools: ToolRegistry,
        inspector: WindowsUIInspector | None = None,
        resolver: TargetResolver | None = None,
        vision_engine: ScreenPerceptionEngine | None = None,
        state: SERAState | None = None,
        event_bus: EventBus | None = None,
        max_steps: int = 10,
        max_task_time_seconds: float = 30.0,
        max_retries_per_step: int = 2,
    ):
        self.tools = tools
        self.inspector = inspector or WindowsUIInspector()
        self.resolver = resolver or TargetResolver()
        self.desktop_executor = DesktopActionExecutor(inspector=self.inspector, resolver=self.resolver)
        self.vision_engine = vision_engine
        self.state = state or SERAState()
        self.event_bus = event_bus or EventBus()
        self.max_steps = max_steps
        self.max_task_time_seconds = max_task_time_seconds
        self.max_retries_per_step = max_retries_per_step

    async def execute(
        self,
        plan: TaskPlan,
        cancellation_event: asyncio.Event | None = None,
        metrics: LatencyMetrics | None = None,
    ) -> TaskExecutionResult:
        """Executes plan steps sequentially with Observe -> Act -> Verify -> Recover loop."""
        t_start = time.perf_counter()
        total_steps = len(plan.steps)

        if not plan.is_valid or total_steps == 0:
            if self.state:
                self.state.transition_to(SERAStatus.TASK_FAILED)
            return TaskExecutionResult(
                success=False,
                task=plan.task,
                steps_completed=0,
                total_steps=total_steps,
                summary_message="Invalid plan rejected before execution.",
                failure_reason=plan.validation_error or "Plan has no valid steps.",
            )

        if total_steps > self.max_steps:
            if self.state:
                self.state.transition_to(SERAStatus.TASK_FAILED)
            return TaskExecutionResult(
                success=False,
                task=plan.task,
                steps_completed=0,
                total_steps=total_steps,
                summary_message=f"Plan exceeded maximum step limit ({total_steps} > {self.max_steps}).",
                failure_reason="Step limit exceeded.",
            )

        steps_completed = 0

        for step in plan.steps:
            # 1. Cancellation Check
            if cancellation_event and cancellation_event.is_set():
                if self.state:
                    self.state.transition_to(SERAStatus.TASK_CANCELLED)
                return TaskExecutionResult(
                    success=False,
                    task=plan.task,
                    steps_completed=steps_completed,
                    total_steps=total_steps,
                    summary_message="Task cancelled by user.",
                    failure_reason="User interrupted task via hotkey.",
                    is_cancelled=True,
                    total_latency_ms=round((time.perf_counter() - t_start) * 1000, 2),
                )

            # 2. Timeout Check
            elapsed = time.perf_counter() - t_start
            if elapsed > self.max_task_time_seconds:
                if self.state:
                    self.state.transition_to(SERAStatus.TASK_FAILED)
                return TaskExecutionResult(
                    success=False,
                    task=plan.task,
                    steps_completed=steps_completed,
                    total_steps=total_steps,
                    summary_message=f"Task timed out after {round(elapsed, 1)} seconds.",
                    failure_reason="Hard execution timeout exceeded.",
                    total_latency_ms=round(elapsed * 1000, 2),
                )

            # 3. Execute Step with Retries & Recovery
            step_success = False
            retries = 0

            while not step_success and retries <= self.max_retries_per_step:
                if cancellation_event and cancellation_event.is_set():
                    if self.state:
                        self.state.transition_to(SERAStatus.TASK_CANCELLED)
                    return TaskExecutionResult(
                        success=False,
                        task=plan.task,
                        steps_completed=steps_completed,
                        total_steps=total_steps,
                        summary_message="Task cancelled by user.",
                        is_cancelled=True,
                    )

                if self.state:
                    self.state.transition_to(SERAStatus.TASK_EXECUTING)

                # Attempt step execution
                step_success, reason = await self._execute_single_step(step, cancellation_event)

                if step_success:
                    step.completed = True
                    steps_completed += 1
                    break

                # Recovery Strategy
                retries += 1
                if retries <= self.max_retries_per_step:
                    if self.state:
                        self.state.transition_to(SERAStatus.TASK_RECOVERING)
                    logger.info(f"[MultiStepExecutor] Step {step.id} failed ({reason}). Attempting recovery retry {retries}/{self.max_retries_per_step}...")
                    await self._attempt_recovery(step)

            if not step_success:
                if self.state:
                    self.state.transition_to(SERAStatus.TASK_FAILED)
                return TaskExecutionResult(
                    success=False,
                    task=plan.task,
                    steps_completed=steps_completed,
                    total_steps=total_steps,
                    summary_message=f"Task halted: Step {step.id} ('{step.goal}') failed.",
                    failure_reason=reason,
                    total_latency_ms=round((time.perf_counter() - t_start) * 1000, 2),
                )

        # All steps completed successfully
        total_time = round((time.perf_counter() - t_start) * 1000, 2)
        if self.state:
            self.state.transition_to(SERAStatus.TASK_COMPLETED)

        return TaskExecutionResult(
            success=True,
            task=plan.task,
            steps_completed=steps_completed,
            total_steps=total_steps,
            summary_message=f"Successfully completed {plan.task}.",
            total_latency_ms=total_time,
        )

    async def _execute_single_step(
        self,
        step: PlanStep,
        cancellation_event: asyncio.Event | None = None,
    ) -> tuple[bool, str | None]:
        """Executes and verifies a single plan step using Observe -> Act -> Verify."""
        try:
            # 1. Execute tool
            tool_res = await self.tools.execute(step.action, step.arguments)

            if isinstance(tool_res, dict) and not tool_res.get("success", True):
                return False, tool_res.get("reason") or tool_res.get("error") or tool_res.get("message") or "Tool returned failure."

            # 2. Post-Observe & Verify State
            if self.state:
                self.state.transition_to(SERAStatus.TASK_VERIFYING)

            verified, ver_reason = await self._verify_step(step, tool_res)
            return verified, ver_reason

        except Exception as e:
            return False, str(e)

    async def _verify_step(self, step: PlanStep, tool_result: Any) -> tuple[bool, str | None]:
        """Verifies state outcome against step verification strategy."""
        ver = step.verification

        if ver == "active_window":
            app_name = step.arguments.get("application") or step.arguments.get("window_name") or ""
            # Polling check: allow up to 1.5s for window to initialize
            for _ in range(6):
                ctx = self.inspector.get_active_window_context()
                if ctx and app_name.lower() in (ctx.application.lower() + " " + ctx.window_title.lower()):
                    return True, None
                found = self.inspector.find_window_context(app_name)
                if found and (found.window_title or found.controls):
                    return True, None
                await asyncio.sleep(0.2)

            if isinstance(tool_result, dict) and tool_result.get("success"):
                return True, None
            return False, f"Expected window '{app_name}' not active."

        elif ver in ("value_change", "control_state_change", "focus_state"):
            if isinstance(tool_result, dict):
                if tool_result.get("verified", False) or tool_result.get("success", False):
                    return True, None
                return False, tool_result.get("reason") or "State change verification failed."
            return True, None

        return True, None

    async def _attempt_recovery(self, step: PlanStep) -> None:
        """Executes recovery heuristics before retrying a step."""
        # 1. Re-observe active window
        await asyncio.sleep(0.3)
        self.inspector.get_active_window_context()

        # 2. If action is app open, wait extra time for window spawn
        if step.action == "open_application":
            await asyncio.sleep(0.5)

        # 3. Vision fallback if vision engine is available
        if self.vision_engine:
            try:
                await self.vision_engine.analyze_screen("Locate UI target for " + step.goal)
            except Exception:
                pass
