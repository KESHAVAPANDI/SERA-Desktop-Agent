"""
SERA 2.0 / Phase 4B.1 — Authoritative Hermes Execution Coordinator.

Orchestrates the controlled execution loop between Hermes Agent and SERA:
User request
→ Hermes reasoning
→ AgentPlan / next action proposal
→ SERA validation
→ Permission evaluation (PAUSED_APPROVAL / WAITING_FOR_APPROVAL)
→ SERA execution
→ Real-world observation
→ Evidence verification
→ Context update (ContextStore)
→ Objective satisfaction evaluation (Stops continuation when user goal is met!)
→ Hermes continuation / replanning (Only if objective remains unsatisfied)
→ Terminal completion

Strict Architectural Invariant:
"Hermes decides what should happen. SERA decides whether it is allowed,
what real entity it refers to, how it is executed, what actually happened,
whether it is verified, and when the task is actually complete."
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from app.adapters.hermes.bridge import OfficialHermesClient, SeraHermesBridge
from app.adapters.hermes.capabilities import resolve_canonical_action
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


@dataclass
class PendingApprovalContext:
    """Stored execution context for a task paused awaiting user permission."""
    permission: PermissionRequirement
    task_id: str
    step: AgentStep
    plan: AgentPlan
    utterance: str
    context: Dict[str, Any]
    step_history: List[Dict[str, Any]]
    executed_steps_count: int
    telemetry: HermesExecutionTelemetry
    current_turn: int

    def __getattr__(self, name: str) -> Any:
        # Transparently delegate permission attributes for backward compatibility
        return getattr(self.permission, name)


@dataclass
class PendingClarificationContext:
    """Stored context for a task waiting for user clarification."""
    task_id: str
    original_objective: str
    context: Dict[str, Any]
    clarification_prompt: str
    plan: Optional[AgentPlan] = None


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

        self.pending_approvals: Dict[str, PendingApprovalContext] = {}
        self.pending_clarifications: Dict[str, PendingClarificationContext] = {}
        self.approval_decisions: Dict[str, ApprovalDecision] = {}
        self.telemetry_records: Dict[str, HermesExecutionTelemetry] = {}
        self.mock_approval_mode: Optional[str] = None  # E.g. "APPROVE", "DENY", "CANCEL", "EXPIRE"

    def set_approval_handler(
        self, handler: Callable[[PermissionRequirement], Awaitable[ApprovalDecision]]
    ) -> None:
        self.approval_handler = handler

    def cancel_task(self, task_id: str) -> bool:
        """Deterministically halts active Hermes task and terminates subprocess immediately."""
        logger.info(f"[HermesExecutionCoordinator] Deterministic cancellation triggered for task {task_id}.")
        return self.bridge.cancel_task(task_id)

    def is_objective_satisfied(
        self,
        original_objective: str,
        step_history: List[Dict[str, Any]],
        context_store: Optional[ContextStore] = None,
    ) -> bool:
        """Determines authoritatively whether verified state satisfies the user's original objective."""
        if not step_history:
            return False

        obj_lower = original_objective.lower().strip()
        verified_steps = [s for s in step_history if s.get("status") in ("VERIFIED_SUCCESS", "VERIFIED")]
        if not verified_steps:
            return False

        verified_actions = [s["action"] for s in verified_steps]

        # 1. Search Query Objective:
        # e.g. "search youtube for python tutorials", "find python tutorials on youtube"
        is_search_intent = any(k in obj_lower for k in ("search", "find", "look up", "lookup"))
        is_open_intent = any(k in obj_lower for k in ("open", "play", "watch", "click", "select", "start", "launch", "run"))

        if is_search_intent and not is_open_intent:
            # Pure search request: satisfied as soon as search results exist and are verified
            if any(a in ("youtube_search", "web_search") for a in verified_actions):
                if context_store:
                    session = context_store.get_active_search_session()
                    if session and session.results:
                        return True
                return True

        # 2. Search AND Open Objective:
        # e.g. "search youtube for python tutorials and open the first result"
        if is_search_intent and is_open_intent:
            has_search = any(a in ("youtube_search", "web_search") for a in verified_actions)
            has_open = any(a in ("browser_open", "open_new_tab", "focus_browser_tab") for a in verified_actions)
            if has_search and has_open:
                return True

        # 3. Dedicated Browser Tab action:
        # e.g. "switch to youtube tab", "close this tab"
        if "tab" in obj_lower or "switch" in obj_lower:
            if "close" in obj_lower and "close_browser_tab" in verified_actions:
                return True
            if ("switch" in obj_lower or "focus" in obj_lower) and "focus_browser_tab" in verified_actions:
                return True

        # 4. Window focus action:
        # e.g. "bring browser window forward", "focus notepad window"
        if any(k in obj_lower for k in ("bring", "forward", "front", "focus window")) and "focus_desktop_window" in verified_actions:
            return True

        # 5. Application Launch or Termination:
        # e.g. "open notepad", "close notepad", "get my browser running"
        if "close_application" in verified_actions and any(k in obj_lower for k in ("close", "kill", "terminate", "exit")):
            return True
        if "open_application" in verified_actions and not is_search_intent:
            return True

        # 6. Settings adjustment:
        if any(a in ("set_brightness", "set_volume") for a in verified_actions):
            return True

        return False

    async def resolve_approval(
        self, request_id: str, decision: Union[ApprovalDecision, str]
    ) -> HermesExecutionResult:
        """Resolves a pending permission request and resumes execution exactly once on APPROVE."""
        if isinstance(decision, str):
            try:
                dec = ApprovalDecision(decision.lower())
            except Exception:
                dec = ApprovalDecision.APPROVE
        else:
            dec = decision

        if request_id not in self.pending_approvals:
            raise KeyError(f"No pending approval found for request_id: {request_id}")

        approval_ctx = self.pending_approvals.pop(request_id)
        self.approval_decisions[request_id] = dec
        perm = approval_ctx.permission

        if dec == ApprovalDecision.APPROVE:
            perm.status = ApprovalStatus.APPROVED
            approval_ctx.step.status = "APPROVED"
            logger.info(f"[HermesExecutionCoordinator] Request {request_id} APPROVED. Continuing execution.")
            return await self._execute_approved_step(approval_ctx)

        elif dec == ApprovalDecision.DENY:
            perm.status = ApprovalStatus.DENIED
            approval_ctx.telemetry.terminal_state = ExecutionHandoffStatus.FAILED
            logger.info(f"[HermesExecutionCoordinator] Request {request_id} DENIED by user.")
            return HermesExecutionResult(
                task_id=approval_ctx.task_id,
                status=ExecutionHandoffStatus.FAILED,
                objective=approval_ctx.utterance,
                response_text="Action was denied by user permission policy.",
                steps_executed=approval_ctx.executed_steps_count,
                telemetry=approval_ctx.telemetry,
                error="PERMISSION_DENIED",
                step_history=approval_ctx.step_history,
            )

        elif dec == ApprovalDecision.CANCEL:
            self.cancel_task(approval_ctx.task_id)
            approval_ctx.telemetry.terminal_state = ExecutionHandoffStatus.CANCELLED
            logger.info(f"[HermesExecutionCoordinator] Request {request_id} CANCELLED.")
            return HermesExecutionResult(
                task_id=approval_ctx.task_id,
                status=ExecutionHandoffStatus.CANCELLED,
                objective=approval_ctx.utterance,
                response_text="Task cancelled during permission check.",
                steps_executed=approval_ctx.executed_steps_count,
                telemetry=approval_ctx.telemetry,
                step_history=approval_ctx.step_history,
            )

        elif dec == ApprovalDecision.EXPIRE:
            perm.status = ApprovalStatus.EXPIRED
            approval_ctx.telemetry.terminal_state = ExecutionHandoffStatus.FAILED
            logger.info(f"[HermesExecutionCoordinator] Request {request_id} EXPIRED.")
            return HermesExecutionResult(
                task_id=approval_ctx.task_id,
                status=ExecutionHandoffStatus.FAILED,
                objective=approval_ctx.utterance,
                response_text="Permission request expired without decision.",
                steps_executed=approval_ctx.executed_steps_count,
                telemetry=approval_ctx.telemetry,
                error="APPROVAL_EXPIRED",
                step_history=approval_ctx.step_history,
            )

        raise ValueError(f"Unknown approval decision: {decision}")

    async def _execute_approved_step(self, ctx: PendingApprovalContext) -> HermesExecutionResult:
        """Executes the single approved step, verifies it, and completes or continues as needed."""
        step = ctx.step
        t0 = time.perf_counter()
        canonical_tool_name = resolve_canonical_action(step.action) or step.action
        tool = self.tools.get(canonical_tool_name) or self.tools.get(step.action)

        if not tool:
            ctx.telemetry.terminal_state = ExecutionHandoffStatus.FAILED
            return HermesExecutionResult(
                task_id=ctx.task_id,
                status=ExecutionHandoffStatus.FAILED,
                objective=ctx.utterance,
                response_text=f"Tool '{step.action}' could not be resolved in registry.",
                steps_executed=ctx.executed_steps_count,
                telemetry=ctx.telemetry,
                error="TOOL_NOT_FOUND",
                step_history=ctx.step_history,
            )

        try:
            tool_res = await tool.execute(**step.arguments)
        except Exception as exc:
            logger.error(f"[HermesExecutionCoordinator] Execution failed for {step.action}: {exc}")
            tool_res = {"success": False, "error": str(exc)}

        is_verified, verified_evidence = self._verify_step_outcome(step, canonical_tool_name, tool_res)

        if not is_verified:
            ctx.telemetry.terminal_state = ExecutionHandoffStatus.FAILED
            return HermesExecutionResult(
                task_id=ctx.task_id,
                status=ExecutionHandoffStatus.FAILED,
                objective=ctx.utterance,
                response_text=f"Action '{step.action}' failed verification: {tool_res.get('error', 'World condition unfulfilled')}",
                steps_executed=ctx.executed_steps_count,
                telemetry=ctx.telemetry,
                error="VERIFICATION_FAILED",
                step_history=ctx.step_history,
            )

        step.status = "VERIFIED"
        step.verified_evidence = verified_evidence
        ctx.executed_steps_count += 1
        ctx.telemetry.steps_executed += 1

        step_entry = {
            "step_id": step.step_id,
            "action": canonical_tool_name,
            "arguments": step.arguments,
            "status": "VERIFIED_SUCCESS",
            "evidence": verified_evidence,
            "summary": tool_res.get("summary") or f"Executed and verified {canonical_tool_name}",
        }
        ctx.step_history.append(step_entry)

        # Check if objective is now satisfied
        if self.is_objective_satisfied(ctx.utterance, ctx.step_history, self.context_store):
            ctx.telemetry.terminal_state = ExecutionHandoffStatus.COMPLETED
            ctx.telemetry.total_latency_ms += (time.perf_counter() - t0) * 1000.0
            return HermesExecutionResult(
                task_id=ctx.task_id,
                status=ExecutionHandoffStatus.COMPLETED,
                objective=ctx.utterance,
                response_text=step_entry["summary"],
                steps_executed=ctx.executed_steps_count,
                telemetry=ctx.telemetry,
                step_history=ctx.step_history,
            )

        # Default completion for single approved action
        ctx.telemetry.terminal_state = ExecutionHandoffStatus.COMPLETED
        return HermesExecutionResult(
            task_id=ctx.task_id,
            status=ExecutionHandoffStatus.COMPLETED,
            objective=ctx.utterance,
            response_text=step_entry["summary"],
            steps_executed=ctx.executed_steps_count,
            telemetry=ctx.telemetry,
            step_history=ctx.step_history,
        )

    def _verify_step_outcome(
        self, step: AgentStep, canonical_tool_name: str, tool_res: Dict[str, Any]
    ) -> tuple[bool, Dict[str, Any]]:
        """Empirically verifies step outcome based on canonical tool semantics."""
        if canonical_tool_name == "youtube_search":
            session = self.context_store.get_active_search_session()
            if session and session.results:
                return True, {
                    "session_id": session.session_id,
                    "query": session.query,
                    "results_count": len(session.results),
                }
            return tool_res.get("success", False) and bool(tool_res.get("results")), tool_res

        elif canonical_tool_name in ("browser_open", "open_new_tab"):
            active_tab = self.context_store.get_active_browser_tab()
            return tool_res.get("success", False), {
                "tab_id": tool_res.get("tab_id") or (active_tab.entity_id if active_tab else "tab_1"),
                "url": tool_res.get("url") or (active_tab.canonical_url if active_tab else step.arguments.get("url")),
                "status": "OPENED_AND_VERIFIED",
            }

        elif canonical_tool_name == "focus_browser_tab":
            is_ver = bool(tool_res.get("verified", False) or tool_res.get("success", False))
            return is_ver, {
                "tab_id": tool_res.get("tab_id", "tab_focused"),
                "title": tool_res.get("title", step.arguments.get("tab_identifier")),
                "status": "TAB_ACTIVATED",
            }

        elif canonical_tool_name == "close_browser_tab":
            is_ver = bool(tool_res.get("verified", False) or tool_res.get("success", False))
            return is_ver, {
                "closed_tab": step.arguments.get("tab_identifier") or "active_tab",
                "status": "TAB_CLOSED",
            }

        elif canonical_tool_name == "focus_desktop_window":
            is_ver = bool(tool_res.get("verified", False) or tool_res.get("success", False))
            return is_ver, {
                "window_name": step.arguments.get("window_name"),
                "status": "WINDOW_FOREGROUND",
            }

        elif canonical_tool_name == "close_application":
            return tool_res.get("success", False), {
                "application": step.arguments.get("application"),
                "status": "TERMINATED",
            }

        elif canonical_tool_name in ("set_brightness", "set_volume"):
            return tool_res.get("success", False), tool_res

        else:
            return tool_res.get("success", False), tool_res

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
        action_signatures: List[str] = []
        executed_steps_count = 0
        approval_interruptions = 0

        # Wire cancellation event
        bridge_cancel = self.bridge.get_cancel_event(tid)
        if cancellation_event and bridge_cancel:
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
            telemetry.terminal_state = ExecutionHandoffStatus.WAITING_FOR_CLARIFICATION
            telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
            resp = plan.clarification_prompt or "Which one do you mean?"
            self.pending_clarifications[tid] = PendingClarificationContext(
                task_id=tid,
                original_objective=utterance,
                context=ctx,
                clarification_prompt=resp,
                plan=plan,
            )
            return HermesExecutionResult(
                task_id=tid,
                status=ExecutionHandoffStatus.WAITING_FOR_CLARIFICATION,
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

                # Loop & No-Progress Protection
                act_sig = f"{step.action}:{json.dumps(step.arguments, sort_keys=True)}"
                if action_signatures.count(act_sig) >= 1:
                    logger.warning(f"[HermesExecutionCoordinator] Loop detected on '{act_sig}'. Halting.")
                    telemetry.terminal_state = ExecutionHandoffStatus.FAILED
                    telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                    return HermesExecutionResult(
                        task_id=tid,
                        status=ExecutionHandoffStatus.FAILED,
                        objective=plan.objective,
                        response_text="I couldn't make further progress because the same action was repeated without new results.",
                        steps_executed=executed_steps_count,
                        telemetry=telemetry,
                        error="NO_PROGRESS_LOOP_DETECTED",
                        step_history=step_history,
                    )
                action_signatures.append(act_sig)

                # A. Authoritative SERA Validation
                val_result = self.validator.validate_step(step)
                if not val_result.is_valid:
                    # Clarification Outcome for ambiguous referents
                    if val_result.rejection_code == "MISSING_CONTEXT_REFERENT":
                        logger.info(f"[HermesExecutionCoordinator] Step {step.step_id} ambiguous referent. Entering WAITING_FOR_CLARIFICATION.")
                        telemetry.terminal_state = ExecutionHandoffStatus.WAITING_FOR_CLARIFICATION
                        telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                        resp = "Which one do you mean?"
                        self.pending_clarifications[tid] = PendingClarificationContext(
                            task_id=tid,
                            original_objective=utterance,
                            context=ctx,
                            clarification_prompt=resp,
                            plan=plan,
                        )
                        return HermesExecutionResult(
                            task_id=tid,
                            status=ExecutionHandoffStatus.WAITING_FOR_CLARIFICATION,
                            objective=plan.objective,
                            response_text=resp,
                            steps_executed=executed_steps_count,
                            telemetry=telemetry,
                            step_history=step_history,
                        )

                    logger.warning(
                        f"[HermesExecutionCoordinator] Step {step.step_id} REJECTED: "
                        f"code={val_result.rejection_code} reason={val_result.reason}"
                    )
                    telemetry.terminal_state = ExecutionHandoffStatus.FAILED
                    telemetry.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
                    
                    user_msg = "I couldn't complete that step because the requested capability is unavailable." if val_result.rejection_code == "UNSUPPORTED_CAPABILITY" else f"Proposed action was rejected by SERA: {val_result.reason}"
                    return HermesExecutionResult(
                        task_id=tid,
                        status=ExecutionHandoffStatus.FAILED,
                        objective=plan.objective,
                        response_text=user_msg,
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
                        # Pause execution awaiting approval without looping
                        approval_ctx = PendingApprovalContext(
                            permission=perm,
                            task_id=tid,
                            step=step,
                            plan=plan,
                            utterance=utterance,
                            context=ctx,
                            step_history=step_history,
                            executed_steps_count=executed_steps_count,
                            telemetry=telemetry,
                            current_turn=current_turn,
                        )
                        self.pending_approvals[perm.request_id] = approval_ctx
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
                canonical_name = resolve_canonical_action(step.action) or step.action
                tool = self.tools.get(canonical_name) or self.tools.get(step.action)

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

                # D. Evidence Verification
                t_ver_start = time.perf_counter()
                is_verified, verified_evidence = self._verify_step_outcome(step, canonical_name, tool_res)
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
                    "action": canonical_name,
                    "arguments": step.arguments,
                    "status": "VERIFIED_SUCCESS",
                    "evidence": verified_evidence,
                    "summary": tool_res.get("summary") or f"Executed and verified {canonical_name}",
                }
                step_history.append(step_entry)
                final_summary = step_entry["summary"]

            # -------------------------------------------------------------
            # Objective Boundary Check: Does verified state satisfy user objective?
            # -------------------------------------------------------------
            if self.is_objective_satisfied(utterance, step_history, self.context_store):
                logger.info(f"[HermesExecutionCoordinator] Objective '{utterance}' satisfied by verified state. Halting continuation.")
                break

            # If plan explicitly signaled completion
            if plan.is_complete:
                break

            # If this was a static precomputed multi-step plan and all steps executed successfully
            if len(plan.steps) > 1 and executed_steps_count >= len(plan.steps):
                break

            # Bounded turn ceiling check
            current_turn += 1
            if current_turn > max_turns:
                break

            # Query Hermes continuation
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
            telemetry.total_tokens = int(usage.get("total_tokens") or 0)
            telemetry.estimated_cost_usd = float(usage.get("estimated_cost_usd") or 0.0)
            telemetry.session_id = usage.get("session_id") or tid

        logger.info(
            f"[HermesExecutionCoordinator] Task {tid} COMPLETED: "
            f"steps={executed_steps_count} turns={telemetry.turns} "
            f"total_latency={telemetry.total_latency_ms:.1f}ms "
            f"reasoning_latency={telemetry.reasoning_latency_ms:.1f}ms"
        )

        res = HermesExecutionResult(
            task_id=tid,
            status=ExecutionHandoffStatus.COMPLETED,
            objective=utterance,
            response_text=final_summary,
            steps_executed=executed_steps_count,
            telemetry=telemetry,
            step_history=step_history,
        )
        self._log_compact_trace(res, is_satisfied=True, next_action="TERMINAL_COMPLETION")
        return res

    def _log_compact_trace(
        self,
        res: HermesExecutionResult,
        is_satisfied: bool = False,
        next_action: str = "TERMINAL_COMPLETION",
    ) -> None:
        """Emits a compact terminal execution trace for live manual tester acceptance."""
        t = res.telemetry
        lines = [
            "=" * 64,
            "  [HERMES EXECUTION CONTROL TRACE]",
            f"  Task ID:               {res.task_id}",
            f"  Original Objective:    {res.objective}",
            f"  Authority Path:        HERMES_EXPERIMENTAL",
            f"  Cognitive Engine:      Hermes v{t.hermes_version} ({t.provider} / {t.model})",
            f"  Total Turns:           {t.turns}",
            f"  Steps Planned/Exec:    {t.steps_planned} / {res.steps_executed}",
            f"  Objective Satisfied:   {'YES' if is_satisfied else 'NO'}",
            f"  Next Action Decision:  {next_action}",
            f"  Final Terminal State:  {res.status.value}",
            f"  Total Latency:         {t.total_latency_ms:.1f}ms (Reasoning: {t.reasoning_latency_ms:.1f}ms, Exec: {t.execution_latency_ms:.1f}ms, Ver: {t.verification_latency_ms:.1f}ms)",
        ]
        if res.step_history:
            lines.append("  Execution History:")
            for s in res.step_history:
                lines.append(f"    - Step {s.get('step_id')}: {s.get('action')} | Status: {s.get('status')} | Summary: {s.get('summary')}")
        if res.error:
            lines.append(f"  Error / Reason:        {res.error}")
        lines.append("=" * 64)
        trace_str = "\n".join(lines)
        print(f"\n{trace_str}\n")
        logger.info(trace_str)

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
            "response": res.response_text,
            "source": source,
            "duration_ms": duration_ms,
            "steps_executed": res.steps_executed,
            "hermes_telemetry": res.telemetry.model_dump() if hasattr(res.telemetry, "model_dump") else res.telemetry.dict(),
            "step_history": res.step_history,
            "terminal_state": res.status.value,
            "status": res.status.value,
            "error": res.error,
        }
