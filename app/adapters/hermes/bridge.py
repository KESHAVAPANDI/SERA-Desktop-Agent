"""
SERA 2.0 / Phase 4A — Thin Hermes Agent Bridge (SeraHermesBridge).

Provides a clean, non-destructive architectural adapter between SERA and Hermes.
Translates user utterances + verified compact context into Hermes AgentPlans,
enforcing cancellation semantics, timeout guards, and safety-preserving fallback.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from app.adapters.hermes.schema import (
    AgentPlan,
    AgentStep,
    HermesMode,
    HermesTraceItem,
    PermissionRequirement,
    RiskLevel,
    ApprovalStatus,
)
from app.adapters.hermes.skills import SkillRegistry, HermesSkill
from app.adapters.hermes.memory import MemoryContract, MemoryRetrievalQuery, MemoryScope
from app.core.command import CommandCategory, CommandComplexity, CommandObject, PlanStepItem
from app.core.semantic.schema import CompactSemanticContext

logger = logging.getLogger("sera.hermes.bridge")


class HermesClientBackend:
    """Protocol for Hermes inference backend (Local, API Server, or Mock)."""

    async def execute_reasoning_loop(
        self,
        system_prompt: str,
        user_message: str,
        available_tools: List[Dict[str, Any]],
        cancel_event: asyncio.Event,
        trace_collector: List[HermesTraceItem],
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class MockHermesClient(HermesClientBackend):
    """Deterministic mock client for testing failure boundaries, cancellations, and benchmarking."""

    def __init__(self, canned_responses: Optional[Dict[str, Any]] = None):
        self.canned_responses = canned_responses or {}
        self.should_timeout = False
        self.should_fail = False
        self.failure_error = "Hermes API connection refused"
        self.delay_seconds = 0.0

    async def execute_reasoning_loop(
        self,
        system_prompt: str,
        user_message: str,
        available_tools: List[Dict[str, Any]],
        cancel_event: asyncio.Event,
        trace_collector: List[HermesTraceItem],
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="system",
            content=f"System prompt initialized with {len(available_tools)} tools."
        ))
        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="user",
            content=user_message
        ))

        # Test cancellation before delay
        if cancel_event.is_set():
            trace_collector.append(HermesTraceItem(
                timestamp=time.time(),
                role="thought",
                content="Cancellation received prior to execution."
            ))
            return {"finish_reason": "cancelled", "objective": user_message, "steps": []}

        if self.should_timeout:
            await asyncio.sleep(timeout + 0.5)

        if self.delay_seconds > 0:
            for _ in range(int(self.delay_seconds * 10)):
                if cancel_event.is_set():
                    trace_collector.append(HermesTraceItem(
                        timestamp=time.time(),
                        role="thought",
                        content="Cancellation signaled during reasoning delay."
                    ))
                    return {"finish_reason": "cancelled", "objective": user_message, "steps": []}
                await asyncio.sleep(0.1)

        if self.should_fail:
            raise RuntimeError(self.failure_error)

        # Return custom or rule-based response
        if user_message in self.canned_responses:
            res = self.canned_responses[user_message]
            trace_collector.append(HermesTraceItem(
                timestamp=time.time(),
                role="assistant",
                content=json.dumps(res)
            ))
            return res

        # Standard rule-based decomposition
        u_lower = user_message.lower().strip()
        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="thought",
            content=f"Decomposing intent for: {user_message}"
        ))

        if "chrome" in u_lower and ("open" in u_lower or "bring" in u_lower or "launch" in u_lower):
            return {
                "objective": "Bring Google Chrome window forward",
                "steps": [
                    {
                        "step_id": 1,
                        "action": "open_application",
                        "arguments": {"application": "chrome"},
                        "rationale": "Activate Chrome window",
                        "expected_evidence": "WINDOW_HANDLE",
                    }
                ],
                "confidence": 0.98,
            }
        elif "notepad" in u_lower and "close" in u_lower:
            return {
                "objective": "Close Notepad application",
                "steps": [
                    {
                        "step_id": 1,
                        "action": "close_application",
                        "arguments": {"application": "notepad"},
                        "rationale": "Terminate notepad process tree",
                        "expected_evidence": "PROCESS_ID",
                        "requires_confirmation": True,
                    }
                ],
                "confidence": 0.96,
            }
        elif "dimmer" in u_lower or ("brightness" in u_lower and "decrease" in u_lower):
            return {
                "objective": "Decrease screen brightness",
                "steps": [
                    {
                        "step_id": 1,
                        "action": "set_brightness",
                        "arguments": {"brightness": 30},
                        "rationale": "Relative decrement based on context",
                        "expected_evidence": "VALUE_CHECK",
                    }
                ],
                "confidence": 0.94,
            }
        elif "stop" in u_lower or "cancel" in u_lower:
            return {
                "objective": "Cancel current task",
                "steps": [],
                "finish_reason": "cancelled",
                "confidence": 1.0,
            }
        elif u_lower in ["open that", "close it", "launch", "please open"]:
            return {
                "objective": "Ambiguous request",
                "needs_clarification": True,
                "clarification_prompt": f"What specific entity would you like me to act upon?",
                "steps": [],
                "confidence": 0.5,
            }

        return {
            "objective": user_message,
            "steps": [],
            "needs_clarification": True,
            "clarification_prompt": "Could you please specify the desired action?",
            "confidence": 0.4,
        }


class SeraHermesBridge:
    """Thin, non-destructive adapter between SERA and Hermes Agent."""

    def __init__(
        self,
        backend: Optional[HermesClientBackend] = None,
        skill_registry: Optional[SkillRegistry] = None,
        memory_contract: Optional[MemoryContract] = None,
        mode: HermesMode = HermesMode.CURRENT,
    ):
        self.backend = backend or MockHermesClient()
        self.skills = skill_registry or SkillRegistry()
        self.memory = memory_contract or MemoryContract()
        self.mode = mode

        self._plans: Dict[str, AgentPlan] = {}
        self._traces: Dict[str, List[HermesTraceItem]] = {}
        self._cancel_events: Dict[str, asyncio.Event] = {}

    async def submit_task(
        self,
        utterance: str,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        timeout: float = 10.0,
    ) -> AgentPlan:
        """Submits a user utterance to Hermes and returns a structured AgentPlan."""
        t_start = time.perf_counter()
        tid = task_id or f"hermes_{uuid.uuid4().hex[:8]}"
        cancel_ev = asyncio.Event()
        self._cancel_events[tid] = cancel_ev
        trace: List[HermesTraceItem] = []
        self._traces[tid] = trace

        ctx = context or {}

        # 1. Progressive Skill Matching & Loading
        matched_skills = self.skills.match_and_load(utterance)
        skills_prompt = "\n".join(s.to_full_prompt() for s in matched_skills) if matched_skills else self.skills.list_metadata_prompts()

        # 2. Context & Memory Assembly
        mem_query = MemoryRetrievalQuery(query=utterance)
        memories = self.memory.query_memories(mem_query)
        mem_str = "\n".join(f"- [{m.scope.value}] {m.key}: {m.value}" for m in memories)

        system_prompt = (
            "You are Hermes Agent reasoning harness operating under SERA Desktop Authority.\n"
            "Produce structured task plans. Never guess destructive actions from ambiguous input.\n\n"
            f"### AVAILABLE SKILLS:\n{skills_prompt}\n\n"
            f"### RELEVANT USER MEMORY & PREFERENCES:\n{mem_str}\n\n"
            f"### ACTIVE CONTEXT:\n"
            f"- Active App: {ctx.get('active_application')}\n"
            f"- Active Browser Tab: {ctx.get('active_tab')}\n"
            f"- Last Action: {ctx.get('last_action')}\n"
        )

        # 3. Tool schemas exposed to Hermes
        available_tools = [
            {"name": "open_application", "description": "Launch/focus an app"},
            {"name": "close_application", "description": "Terminate application process"},
            {"name": "close_window", "description": "Close window via WM_CLOSE"},
            {"name": "focus_browser_tab", "description": "Switch browser tab"},
            {"name": "close_browser_tab", "description": "Close browser tab"},
            {"name": "set_brightness", "description": "Set screen brightness"},
            {"name": "set_volume", "description": "Set system volume"},
            {"name": "cancel_task", "description": "Halt execution"},
        ]

        # 4. Invoke Hermes Backend with Cancellation and Timeout Safety
        try:
            raw_res = await asyncio.wait_for(
                self.backend.execute_reasoning_loop(
                    system_prompt=system_prompt,
                    user_message=utterance,
                    available_tools=available_tools,
                    cancel_event=cancel_ev,
                    trace_collector=trace,
                    timeout=timeout,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"HERMES_BRIDGE: Timeout ({timeout}s) exceeded for task {tid}")
            raw_res = {
                "objective": utterance,
                "finish_reason": "timeout",
                "needs_clarification": True,
                "clarification_prompt": "Reasoning timed out. What would you like me to do?",
                "steps": [],
                "confidence": 0.0,
            }
        except Exception as e:
            logger.error(f"HERMES_BRIDGE: Error in reasoning loop for task {tid}: {e}")
            raw_res = {
                "objective": utterance,
                "finish_reason": "error",
                "needs_clarification": True,
                "clarification_prompt": "Encountered an internal reasoning error. Please rephrase.",
                "steps": [],
                "confidence": 0.0,
            }

        # 5. Assemble Structured AgentPlan
        steps: List[AgentStep] = []
        for s_idx, s_data in enumerate(raw_res.get("steps", []), start=1):
            action = s_data.get("action", "")
            req_confirm = s_data.get("requires_confirmation", False)
            risk = RiskLevel.DESTRUCTIVE if "close" in action or "terminate" in action else RiskLevel.BENIGN
            
            perm = PermissionRequirement(
                action=action,
                target=str(s_data.get("arguments", {}).get("application") or s_data.get("arguments", {}).get("hwnd") or ""),
                risk_level=risk,
                status=ApprovalStatus.PENDING_APPROVAL if req_confirm else ApprovalStatus.APPROVED,
            )

            steps.append(AgentStep(
                step_id=s_idx,
                action=action,
                arguments=s_data.get("arguments", {}),
                rationale=s_data.get("rationale"),
                target_entity_id=s_data.get("target_entity_id"),
                expected_evidence=s_data.get("expected_evidence", "VALUE_CHECK"),
                requires_confirmation=req_confirm,
                permission=perm,
            ))

        latency_ms = (time.perf_counter() - t_start) * 1000.0

        plan = AgentPlan(
            task_id=tid,
            objective=raw_res.get("objective", utterance),
            assumptions=raw_res.get("assumptions", []),
            steps=steps,
            entities=raw_res.get("entities", []),
            confidence=raw_res.get("confidence", 1.0),
            needs_clarification=raw_res.get("needs_clarification", False),
            clarification_prompt=raw_res.get("clarification_prompt"),
            raw_thought=raw_res.get("thought"),
            finish_reason=raw_res.get("finish_reason", "stop"),
            latency_ms=latency_ms,
        )

        self._plans[tid] = plan
        return plan

    def cancel_task(self, task_id: str) -> bool:
        """Signals cancellation to an active Hermes task."""
        if task_id in self._cancel_events:
            self._cancel_events[task_id].set()
            if task_id in self._plans:
                self._plans[task_id].finish_reason = "cancelled"
            logger.info(f"HERMES_BRIDGE: Task {task_id} successfully cancelled.")
            return True
        return False

    def inspect_result(self, task_id: str) -> Optional[AgentPlan]:
        """Retrieves structured plan for inspection."""
        return self._plans.get(task_id)

    def inspect_trace(self, task_id: str) -> List[HermesTraceItem]:
        """Retrieves reasoning trace for inspection."""
        return self._traces.get(task_id, [])

    def convert_to_command_object(self, plan: AgentPlan, context: Dict[str, Any]) -> CommandObject:
        """Converts an AgentPlan into a SERA CommandObject for the Stateful Graph Runtime."""
        task_id = plan.task_id or f"task_{uuid.uuid4().hex[:8]}"
        command_id = f"cmd_{uuid.uuid4().hex[:8]}"

        if plan.needs_clarification or plan.finish_reason in ("cancelled", "error", "timeout"):
            return CommandObject(
                command_id=command_id,
                task_id=task_id,
                intent="clarification_needed" if plan.needs_clarification else "cancel_current_task",
                category=CommandCategory.SYSTEM,
                complexity=CommandComplexity.SIMPLE,
                source_text=plan.objective,
                parameters={"explanation": plan.clarification_prompt or "Task halted."},
                required_tools=[],
                execution_plan=[],
                raw_response=plan.clarification_prompt,
            )

        execution_steps: List[PlanStepItem] = []
        tools_needed: List[str] = []

        for step in plan.steps:
            tools_needed.append(step.action)
            execution_steps.append(PlanStepItem(
                step_id=step.step_id,
                goal=step.rationale or f"Execute {step.action}",
                action=step.action,
                arguments=step.arguments,
                timeout_seconds=step.timeout_seconds,
                verification_type=step.expected_evidence,
            ))

        primary_intent = plan.steps[0].action if plan.steps else "unknown"
        category = CommandCategory.APPLICATIONS if "app" in primary_intent else CommandCategory.SYSTEM

        return CommandObject(
            command_id=command_id,
            task_id=task_id,
            intent=primary_intent,
            category=category,
            complexity=CommandComplexity.MULTI_STEP if len(plan.steps) > 1 else CommandComplexity.ONE_TOOL,
            source_text=plan.objective,
            required_tools=tools_needed,
            execution_plan=execution_steps,
            confirmation_required=any(s.requires_confirmation for s in plan.steps),
        )
