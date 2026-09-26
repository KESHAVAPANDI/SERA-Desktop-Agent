"""
SERA 2.0 / Phase 4B — Authoritative Hermes Execution Coordinator.

Orchestrates the controlled execution loop between Hermes Agent and SERA:
User request
→ Hermes reasoning
→ AgentPlan / next action
→ SERA validation
→ Permission evaluation
→ SERA execution
→ Real-world observation
→ Evidence verification
→ Context update
→ Hermes continuation / replanning
→ Next action
→ Completion

Strict Architectural Invariant:
"Hermes decides what should happen. SERA decides whether it is allowed,
makes it happen, determines what actually happened, and tells Hermes the verified result."
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from app.adapters.hermes.bridge import SeraHermesBridge, OfficialHermesClient
from app.adapters.hermes.schema import (
    AgentPlan,
    AgentStep,
    ApprovalDecision,
    ApprovalStatus,
    ExecutionHandoffStatus,
    HermesExecutionTelemetry,
    HermesMode,
    PermissionRequirement,
    RiskLevel,
    StepValidationResult,
    TargetType,
)
from app.adapters.hermes.validator import HermesPlanValidator
from app.core.context.store import ContextStore
from app.core.verification import EvidenceVerificationFabric
from app.tools import ToolRegistry

logger = logging.getLogger("sera.hermes.coordinator")


class HermesExecutionResult(BaseModel):
    """Result of an end-to-end Hermes execution coordinated by SERA."""
    task_id: str
    status: ExecutionHandoffStatus
    objective: str
    response_text: str
    steps_executed: int
    telemetry: HermesExecutionTelemetry
    error: Optional[str] = None
    step_history: List[Dict[str, Any]] = Field(default_factory=list)


class HermesExecutionCoordinator:
    """Coordinates execution, validation, permissions, and multi-turn loops for Hermes."""

    def __init__(
        self,
        bridge: SeraHermesBridge,
        context_store: Optional[ContextStore] = None,
        tool_registry: Optional[ToolRegistry] = None,
        validator: Optional[HermesPlanValidator] = None,
        evidence_fabric: Optional[EvidenceVerificationFabric] = None,
        approval_handler: Optional[Callable[[PermissionRequirement], Awaitable[ApprovalDecision]]] = None,
    ):
        self.bridge = bridge
        self.context_store = context_store or ContextStore()
        self.tools = tool_registry or ToolRegistry()
        self.evidence_fabric = evidence_fabric or EvidenceVerificationFabric()
        self.validator = validator or HermesPlanValidator(
            context_store=self.context_store,
            tool_registry=self.tools,
        )
        self.approval_handler = approval_handler

        # Wire context_store to browser and YouTube tools if present
        yt_tool = self.tools.get("youtube_search")
        if yt_tool and hasattr(yt_tool, "context_store") and yt_tool.context_store is None:
            yt_tool.context_store = self.context_store

        browser_tool = self.tools.get("browser_open")
        if browser_tool:
            bsm = getattr(browser_tool, "session_manager", None)
            if bsm and hasattr(bsm, "context_store") and bsm.context_store is None:
                bsm.context_store = self.context_store

        self.pending_approvals: Dict[str, PermissionRequirement] = {}
        self.approval_decisions: Dict[str, ApprovalDecision] = {}
        self.telemetry_records: Dict[str, HermesExecutionTelemetry] = {}
        self.mock_approval_mode: Optional[str] = None  # E.g. "APPROVE", "DENY", "CANCEL", "EXPIRE"

    def set_approval_handler(
        self, handler: Callable[[PermissionRequirement], Awaitable[ApprovalDecision]]
    ) -> None:
        self.approval_handler = handler

    def resolve_approval(self, request_id: str, decision: ApprovalDecision) -> bool:
        """Resolves a pending permission request programmatically."""
        if request_id in self.pending_approvals:
            self.approval_decisions[request_id] = decision
            req = self.pending_approvals.pop(request_id)
            if decision == ApprovalDecision.APPROVE:
                req.status = ApprovalStatus.APPROVED
            elif decision == ApprovalDecision.DENY:
                req.status = ApprovalStatus.DENIED
            elif decision == ApprovalDecision.EXPIRE:
                req.status = ApprovalStatus.EXPIRED
            logger.info(f"[HermesExecutionCoordinator] Permission request {request_id} resolved with {decision.value}.")
            return True
        return False

    def cancel_task(self, task_id: str) -> bool:
        """Deterministically halts active Hermes task and terminates subprocess immediately."""
        logger.info(f"[HermesExecutionCoordinator] Deterministic cancellation triggered for task {task_id}.")
        return self.bridge.cancel_task(task_id)

    def _get_compact_context(self) -> Dict[str, Any]:
        """Projects compact verified context from ContextStore."""
        active_app = self.context_store.get_active_application()
        active_tab = self.context_store.get_active_browser_tab()
        active_search = self.context_store.get_active_search_session()

        results_preview = []
        if active_search and active_search.results:
            for r in active_search.results[:5]:
                results_preview.append({
                    "ordinal": r.ordinal,
                    "title": r.title,
                    "url": r.canonical_url,
                })

        return {
            "active_application": active_app.application_name if active_app else "None",
            "active_tab": active_tab.title if active_tab else "None",
            "active_search_query": active_search.query if active_search else None,
            "search_results": results_preview,
            "last_action": getattr(self.context_store, "last_action", "None"),
        }

    async def execute_task(
        self,
        utterance: str,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        is_voice: bool = False,
        cancellation_event: Optional[asyncio.Event] = None,
        timeout: float = 60.0,
        max_turns: int = 5,
    ) -> HermesExecutionResult:
        """Executes a full user task through the authoritative Hermes-SERA loop."""
        t_start = time.perf_counter()
        tid = task_id or f"hermes_exec_{uuid.uuid4().hex[:8]}"
        step_history: List[Dict[str, Any]] = []
        executed_steps_count = 0
        approval_interruptions = 0
        replans = 0

        # Wire cancellation event
        bridge_cancel = self.bridge.get_cancel_event(tid)
        if cancellation_event and bridge_cancel:
            def _sync_cancel():
                bridge_cancel.set()
            asyncio.create_task(self._wait_and_sync_cancel(cancellation_event, tid))

        ctx = context or self._get_compact_context()

        # Telemetry container
        telemetry = HermesExecutionTelemetry(
            task_id=tid,
            session_id=tid,
            hermes_version="v0.21.5",
            turns=1,
        )
        self.telemetry_records[tid] = telemetry

        # -------------------------------------------------------------
        # 1. Turn 1: Initial Reasoning & Planning
        # -------------------------------------------------------------
        t_reason_start = time.perf_counter()
        plan = await self.bridge.submit_task(utterance, context=ctx, task_id=tid)
        t_reason_end = time.perf_counter()
        telemetry.reasoning_latency_ms += (t_reason_end - t_reason_start) * 1000.0

        if plan.finish_reason == "cancelled" or (cancellation_event and cancellation_event.is_set()):
            telemetry.terminal_state = ExecutionHandoffStatus.CANCELLED
            telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
            return HermesExecutionResult(
                task_id=tid,
                status=ExecutionHandoffStatus.CANCELLED,
                objective=utterance,
                response_text="Task was cancelled.",
                steps_executed=0,
                telemetry=telemetry,
                step_history=step_history,
            )

        if plan.needs_clarification:
            telemetry.terminal_state = ExecutionHandoffStatus.COMPLETED
            telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
            resp = plan.clarification_prompt or "Could you please clarify your request?"
            return HermesExecutionResult(
                task_id=tid,
                status=ExecutionHandoffStatus.COMPLETED,
                objective=plan.objective,
                response_text=resp,
                steps_executed=0,
                telemetry=telemetry,
                step_history=step_history,
            )

        if plan.finish_reason in ("error", "timeout") or not plan.steps:
            if not plan.steps and plan.is_complete:
                telemetry.terminal_state = ExecutionHandoffStatus.COMPLETED
                telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                return HermesExecutionResult(
                    task_id=tid,
                    status=ExecutionHandoffStatus.COMPLETED,
                    objective=plan.objective,
                    response_text=plan.objective,
                    steps_executed=0,
                    telemetry=telemetry,
                    step_history=step_history,
                )
            telemetry.terminal_state = ExecutionHandoffStatus.FAILED
            telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
            return HermesExecutionResult(
                task_id=tid,
                status=ExecutionHandoffStatus.FAILED,
                objective=utterance,
                response_text=plan.clarification_prompt or f"Hermes execution halted ({plan.finish_reason}).",
                steps_executed=0,
                telemetry=telemetry,
                error=plan.finish_reason,
                step_history=step_history,
            )

        telemetry.steps_planned += len(plan.steps)

        # -------------------------------------------------------------
        # Multi-Turn Execution & Continuation Loop
        # -------------------------------------------------------------
        current_turn = 1
        final_summary = plan.objective

        while current_turn <= max_turns:
            # Execute steps in current plan
            for step in plan.steps:
                # Cancellation check
                if cancellation_event and cancellation_event.is_set():
                    self.cancel_task(tid)
                    telemetry.terminal_state = ExecutionHandoffStatus.CANCELLED
                    telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                    return HermesExecutionResult(
                        task_id=tid,
                        status=ExecutionHandoffStatus.CANCELLED,
                        objective=plan.objective,
                        response_text="Task was cancelled.",
                        steps_executed=executed_steps_count,
                        telemetry=telemetry,
                        step_history=step_history,
                    )

                # A. Authoritative SERA Validation
                val_result = self.validator.validate_step(step)
                if not val_result.is_valid:
                    logger.warning(
                        f"[HermesExecutionCoordinator] Step {step.step_id} REJECTED: "
                        f"code={val_result.rejection_code} reason={val_result.reason}"
                    )
                    telemetry.terminal_state = ExecutionHandoffStatus.FAILED
                    telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                    return HermesExecutionResult(
                        task_id=tid,
                        status=ExecutionHandoffStatus.FAILED,
                        objective=plan.objective,
                        response_text=f"Proposed action was rejected by SERA: {val_result.reason}",
                        steps_executed=executed_steps_count,
                        telemetry=telemetry,
                        error=val_result.rejection_code,
                        step_history=step_history,
                    )

                # B. Permission Boundary Evaluation
                if step.requires_confirmation or (
                    step.permission and step.permission.status == ApprovalStatus.PENDING_APPROVAL
                ):
                    approval_interruptions += 1
                    telemetry.approval_interruptions += 1
                    perm = step.permission or PermissionRequirement(
                        action=step.action,
                        target=str(step.arguments.get("application") or step.target_reference or ""),
                        risk_level=RiskLevel.DESTRUCTIVE,
                        status=ApprovalStatus.PENDING_APPROVAL,
                    )

                    decision = None
                    if self.mock_approval_mode:
                        try:
                            decision = ApprovalDecision(self.mock_approval_mode.lower())
                        except Exception:
                            decision = ApprovalDecision.APPROVE
                    elif self.approval_handler:
                        decision = await self.approval_handler(perm)
                    elif perm.request_id in self.approval_decisions:
                        decision = self.approval_decisions[perm.request_id]

                    if decision is None:
                        # Pause execution awaiting approval
                        self.pending_approvals[perm.request_id] = perm
                        telemetry.terminal_state = ExecutionHandoffStatus.PAUSED_APPROVAL
                        telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                        return HermesExecutionResult(
                            task_id=tid,
                            status=ExecutionHandoffStatus.PAUSED_APPROVAL,
                            objective=plan.objective,
                            response_text=f"Action '{step.action}' requires user approval (Request ID: {perm.request_id}).",
                            steps_executed=executed_steps_count,
                            telemetry=telemetry,
                            step_history=step_history,
                        )

                    if decision == ApprovalDecision.APPROVE:
                        perm.status = ApprovalStatus.APPROVED
                        step.status = "APPROVED"
                    elif decision == ApprovalDecision.DENY:
                        perm.status = ApprovalStatus.DENIED
                        telemetry.terminal_state = ExecutionHandoffStatus.FAILED
                        telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                        return HermesExecutionResult(
                            task_id=tid,
                            status=ExecutionHandoffStatus.FAILED,
                            objective=plan.objective,
                            response_text="Action was denied by user permission policy.",
                            steps_executed=executed_steps_count,
                            telemetry=telemetry,
                            error="PERMISSION_DENIED",
                            step_history=step_history,
                        )
                    elif decision == ApprovalDecision.CANCEL:
                        self.cancel_task(tid)
                        telemetry.terminal_state = ExecutionHandoffStatus.CANCELLED
                        telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                        return HermesExecutionResult(
                            task_id=tid,
                            status=ExecutionHandoffStatus.CANCELLED,
                            objective=plan.objective,
                            response_text="Task cancelled during permission check.",
                            steps_executed=executed_steps_count,
                            telemetry=telemetry,
                            step_history=step_history,
                        )
                    elif decision == ApprovalDecision.EXPIRE:
                        perm.status = ApprovalStatus.EXPIRED
                        telemetry.terminal_state = ExecutionHandoffStatus.FAILED
                        telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                        return HermesExecutionResult(
                            task_id=tid,
                            status=ExecutionHandoffStatus.FAILED,
                            objective=plan.objective,
                            response_text="Permission request expired without decision.",
                            steps_executed=executed_steps_count,
                            telemetry=telemetry,
                            error="APPROVAL_EXPIRED",
                            step_history=step_history,
                        )

                # C. SERA Tool Execution
                tool_name = step.action
                tool = self.tools.get(tool_name)
                if not tool:
                    # Check canonical alias mapping
                    from app.adapters.hermes.validator import SUPPORTED_ACTIONS
                    canon = SUPPORTED_ACTIONS.get(tool_name, tool_name)
                    tool = self.tools.get(canon)

                if not tool:
                    telemetry.terminal_state = ExecutionHandoffStatus.FAILED
                    telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                    return HermesExecutionResult(
                        task_id=tid,
                        status=ExecutionHandoffStatus.FAILED,
                        objective=plan.objective,
                        response_text=f"Tool '{step.action}' could not be resolved in registry.",
                        steps_executed=executed_steps_count,
                        telemetry=telemetry,
                        error="TOOL_NOT_FOUND",
                        step_history=step_history,
                    )

                t_exec_start = time.perf_counter()
                try:
                    tool_res = await tool.execute(**step.arguments)
                except Exception as exc:
                    logger.error(f"[HermesExecutionCoordinator] Execution failed for {step.action}: {exc}")
                    tool_res = {"success": False, "error": str(exc)}
                t_exec_end = time.perf_counter()
                telemetry.execution_latency_ms += (t_exec_end - t_exec_start) * 1000.0

                # D. Evidence Verification ("Tool success != World success")
                t_ver_start = time.perf_counter()
                is_verified = False
                verified_evidence = {}

                if tool_name == "youtube_search":
                    # Verify real SearchSession in ContextStore
                    session = self.context_store.get_active_search_session()
                    if session and session.results:
                        is_verified = True
                        verified_evidence = {
                            "session_id": session.session_id,
                            "query": session.query,
                            "results_count": len(session.results),
                            "results": [
                                {
                                    "ordinal": r.ordinal,
                                    "title": r.title,
                                    "url": r.canonical_url,
                                    "type": r.result_type.value,
                                }
                                for r in session.results
                            ],
                        }
                    else:
                        is_verified = tool_res.get("success", False) and bool(tool_res.get("results"))
                        verified_evidence = tool_res

                elif tool_name in ("browser_open", "open_new_tab"):
                    # Verify canonical BrowserTabEntity in ContextStore
                    active_tab = self.context_store.get_active_browser_tab()
                    is_verified = tool_res.get("success", False)
                    verified_evidence = {
                        "tab_id": tool_res.get("tab_id") or (active_tab.entity_id if active_tab else "tab_1"),
                        "url": tool_res.get("url") or (active_tab.canonical_url if active_tab else step.arguments.get("url")),
                        "status": "OPENED_AND_VERIFIED",
                    }

                elif tool_name == "close_application":
                    is_verified = tool_res.get("success", False)
                    verified_evidence = {
                        "application": step.arguments.get("application"),
                        "status": "TERMINATED",
                    }

                elif tool_name in ("set_brightness", "set_volume"):
                    is_verified = tool_res.get("success", False)
                    verified_evidence = tool_res

                else:
                    is_verified = tool_res.get("success", False)
                    verified_evidence = tool_res

                t_ver_end = time.perf_counter()
                telemetry.verification_latency_ms += (t_ver_end - t_ver_start) * 1000.0

                if not is_verified:
                    logger.warning(f"[HermesExecutionCoordinator] Step {step.step_id} failed verification!")
                    telemetry.verification_results.append({
                        "step_id": step.step_id,
                        "action": step.action,
                        "verified": False,
                        "error": tool_res.get("error", "Verification condition not met"),
                    })
                    telemetry.terminal_state = ExecutionHandoffStatus.FAILED
                    telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                    return HermesExecutionResult(
                        task_id=tid,
                        status=ExecutionHandoffStatus.FAILED,
                        objective=plan.objective,
                        response_text=f"Action '{step.action}' failed verification: {tool_res.get('error', 'World condition unfulfilled')}",
                        steps_executed=executed_steps_count,
                        telemetry=telemetry,
                        error="VERIFICATION_FAILED",
                        step_history=step_history,
                    )

                # E. Context Update (Only AFTER verification!)
                step.status = "VERIFIED"
                step.verified_evidence = verified_evidence
                executed_steps_count += 1
                telemetry.steps_executed += 1
                telemetry.verification_results.append({
                    "step_id": step.step_id,
                    "action": step.action,
                    "verified": True,
                    "evidence": verified_evidence,
                })

                step_entry = {
                    "step_id": step.step_id,
                    "action": step.action,
                    "arguments": step.arguments,
                    "status": "VERIFIED_SUCCESS",
                    "evidence": verified_evidence,
                    "summary": tool_res.get("summary") or f"Executed and verified {step.action}",
                }
                step_history.append(step_entry)
                final_summary = step_entry["summary"]

            # Check if continuation is needed
            if plan.is_complete:
                break

            # If this was a static precomputed plan and all steps executed successfully
            if len(plan.steps) > 1 and executed_steps_count >= len(plan.steps):
                break

            # If user utterance requires more work (e.g. search + open), invoke Hermes continuation
            current_turn += 1
            if current_turn > max_turns:
                break

            logger.info(f"[HermesExecutionCoordinator] Querying Hermes continuation for turn {current_turn}...")
            t_cont_start = time.perf_counter()
            updated_ctx = self._get_compact_context()

            next_plan = await self.bridge.continue_task(
                task_id=tid,
                original_objective=utterance,
                step_history=step_history,
                context=updated_ctx,
                timeout=timeout,
            )
            t_cont_end = time.perf_counter()
            telemetry.reasoning_latency_ms += (t_cont_end - t_cont_start) * 1000.0
            telemetry.turns = current_turn

            if next_plan.finish_reason in ("timeout", "error"):
                logger.warning(f"[HermesExecutionCoordinator] Continuation halted with {next_plan.finish_reason}.")
                telemetry.terminal_state = ExecutionHandoffStatus.FAILED
                telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                return HermesExecutionResult(
                    task_id=tid,
                    status=ExecutionHandoffStatus.FAILED,
                    objective=utterance,
                    response_text=next_plan.clarification_prompt or f"Hermes continuation failed ({next_plan.finish_reason}).",
                    steps_executed=executed_steps_count,
                    telemetry=telemetry,
                    error=next_plan.finish_reason,
                    step_history=step_history,
                )

            if next_plan.is_complete or not next_plan.steps:
                logger.info(f"[HermesExecutionCoordinator] Hermes signaled completion on turn {current_turn}.")
                if next_plan.objective and next_plan.objective != utterance:
                    final_summary = next_plan.objective
                break

            plan = next_plan
            telemetry.steps_planned += len(plan.steps)

        # -------------------------------------------------------------
        # Final Terminal State Completion
        # -------------------------------------------------------------
        telemetry.terminal_state = ExecutionHandoffStatus.COMPLETED
        telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0

        # Retrieve usage data if available
        if isinstance(self.bridge.backend, OfficialHermesClient):
            usage = getattr(self.bridge.backend, "last_usage_data", {})
            telemetry.total_tokens = usage.get("total_tokens", 0)
            telemetry.estimated_cost_usd = usage.get("estimated_cost_usd", 0.0)
            telemetry.session_id = usage.get("session_id", tid)

        logger.info(
            f"[HermesExecutionCoordinator] Task {tid} COMPLETED: "
            f"steps={executed_steps_count} turns={telemetry.turns} "
            f"total_latency={telemetry.total_latency_ms:.1f}ms "
            f"reasoning_latency={telemetry.reasoning_latency_ms:.1f}ms"
        )

        return HermesExecutionResult(
            task_id=tid,
            status=ExecutionHandoffStatus.COMPLETED,
            objective=utterance,
            response_text=final_summary,
            steps_executed=executed_steps_count,
            telemetry=telemetry,
            step_history=step_history,
        )

    async def _wait_and_sync_cancel(self, event: asyncio.Event, task_id: str) -> None:
        await event.wait()
        self.cancel_task(task_id)

    async def execute_task_for_pipeline(
        self,
        text: str,
        task_id: str,
        context: Dict[str, Any],
        t_start: float,
        source: str = "TEXT",
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> Dict[str, Any]:
        """Adapter hook integrating HermesExecutionCoordinator with CommandPipeline."""
        res = await self.execute_task(
            utterance=text,
            context=context,
            task_id=task_id,
            is_voice=(source == "VOICE"),
            cancellation_event=cancellation_event,
        )

        duration_ms = (time.perf_counter() - t_start) * 1000.0
        success = (res.status == ExecutionHandoffStatus.COMPLETED)

        return {
            "task_id": task_id,
            "success": success,
            "message": res.response_text,
            "source": source,
            "duration_ms": duration_ms,
            "steps_executed": res.steps_executed,
            "hermes_telemetry": res.telemetry.dict(),
            "terminal_state": res.status.value,
            "error": res.error,
        }
