"""
SERA Command Pipeline — Core Deterministic Desktop Execution Engine.
Executes normalized CommandObjects with strict step timeouts, total task deadlines,
tool argument validation, process/file/window verification, context resolution,
deduplication guards, and guaranteed single response delivery.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any

from app.core.command import CommandCategory, CommandComplexity, CommandObject, CommandParser, PlanStepItem
from app.core.context import ContextStore, ReplayableSemanticAction
from app.core.events import EventBus
from app.core.graph import (
    GraphExecutionStatus,
    GraphPlanStep,
    GraphState,
    create_default_graph_runtime,
)
from app.core.router import ModelRouter
from app.core.semantic import (
    CanonicalIntent,
    SemanticAuthorityDecision,
    SemanticAuthorityGate,
    SemanticAuthoritySource,
    SemanticContextResolver,
    SemanticInterpreter,
)
from app.core.state import SERAState, SERAStatus
from app.core.verification import EvidenceVerificationFabric, EvidenceRecord, EvidenceType
from app.tools import ToolRegistry
from app.utils.security import SecurityManager

logger = logging.getLogger(__name__)


class CommandPipeline:
    """Deterministic, resilient desktop command execution pipeline."""

    def __init__(
        self,
        tools: ToolRegistry,
        router: ModelRouter | None = None,
        state: SERAState | None = None,
        event_bus: EventBus | None = None,
        security_manager: SecurityManager | None = None,
        context_store: ContextStore | None = None,
    ):
        self.tools = tools
        self.router = router
        self.state = state or SERAState()
        self.event_bus = event_bus or EventBus()
        self.security = security_manager or SecurityManager()
        self.parser = CommandParser()
        self.evidence_fabric = EvidenceVerificationFabric()

        # Context & History Memory (Entity-Centric ContextStore)
        self.context_store = context_store or ContextStore()
        self.last_successful_command: CommandObject | None = None
        self.last_application: str | None = None
        self.last_folder: str | None = None
        self.last_file: str | None = None
        self.context_state: dict[str, Any] = {}

        # Execution Deduplication Cache
        self._executed_signatures: set[str] = set()
        self.active_cancellation_event: asyncio.Event = asyncio.Event()

        # Semantic Interpreter & Authority Gate (Phase 3A-E Pilot)
        self.semantic_interpreter = SemanticInterpreter()
        self.authority_gate = SemanticAuthorityGate(pilot_enabled=True)
        self.context_resolver = SemanticContextResolver(context_store=self.context_store)
        self.last_semantic_decision: dict[str, Any] | None = None
        self.last_semantic_shadow: dict[str, Any] | None = None
        self.last_canonical_intent: dict[str, Any] | None = None
        self.shadow_records: list[dict[str, Any]] = []
        self._active_shadow_task: asyncio.Task[Any] | None = None

        # Canonical Phase 3A Stateful Graph Runtime Foundation
        self.graph_runtime = create_default_graph_runtime(
            tools=self.tools,
            router=self.router,
            event_bus=self.event_bus,
            fabric=self.evidence_fabric,
            context_provider=self.context_state,
        )

    def cancel_current_task(self) -> None:
        """Flags the active task cancellation event."""
        if hasattr(self, "active_cancellation_event") and self.active_cancellation_event:
            self.active_cancellation_event.set()

    async def execute_text(
        self,
        text: str,
        task_id: str | None = None,
        source: str = "TEXT",
        metrics: Any = None,
        is_voice_turn: bool = False,
    ) -> dict[str, Any]:
        """Entrypoint to parse, validate, execute, and verify a user command utterance."""
        t_start = time.time()
        task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        self._current_is_voice_turn = is_voice_turn

        # 1. State: RECEIVED -> CLASSIFYING
        self.state.transition_to(SERAStatus.THINKING)
        self.state.last_user_message = text
        if not is_voice_turn:
            self._emit_event("TASK_STARTED", {"task_id": task_id, "user_input": text, "source": source})

        # Update context map (Entity-Centric ContextStore projection + working execution context)
        store_ctx = self.context_store.to_legacy_dict()
        ctx = {
            **store_ctx,
            **self.context_state,
            "last_application": self.last_application or store_ctx.get("last_application"),
            "last_folder": self.last_folder,
            "last_file": self.last_file,
            "last_intent": self.context_state.get("last_intent") or (self.last_successful_command.intent if self.last_successful_command else None),
            "last_tool": self.context_state.get("last_tool"),
            "last_command": self.last_successful_command,
            "context_store": self.context_store,
        }

        # -------------------------------------------------------------
        # 2. SEMANTIC AUTHORITY EVALUATION (Phase 3A-E Pilot)
        # -------------------------------------------------------------
        is_fast_path = self.authority_gate.is_deterministic_fast_path(text)

        if is_fast_path:
            # Deterministic Fast Path: bypass Qwen directly for exact scalar/system commands
            cmd = self.parser.parse(text, task_id=task_id, context=ctx)
            fast_decision = SemanticAuthorityDecision(
                source=SemanticAuthoritySource.DETERMINISTIC,
                accepted=True,
                category="SYSTEM",
                confidence=1.0,
                fallback_reason=None,
            )
            self.last_semantic_decision = fast_decision.to_dict()
            logger.info(
                f"SEMANTIC_DECISION: transcript=\"{text}\" qwen=none "
                f"authority=DETERMINISTIC fallback=none accepted=true latency=0.0ms "
                f"category=SYSTEM"
            )
            # Concurrently run shadow interpreter for telemetry tracking
            if self._active_shadow_task and not self._active_shadow_task.done():
                self._active_shadow_task.cancel()
            self._active_shadow_task = asyncio.create_task(self._record_semantic_shadow(text, ctx, cmd))
        else:
            # Candidate for Qwen Semantic Interpretation
            compact_ctx = self.semantic_interpreter.extract_compact_context(extra_context=ctx)
            t_sem_start = time.perf_counter()
            sem_error = None
            try:
                qwen_intent = await self.semantic_interpreter.interpret_async(text, compact_ctx)
            except asyncio.TimeoutError:
                qwen_intent = None
                sem_error = "Semantic model timed out"
            except Exception as e:
                qwen_intent = None
                sem_error = str(e)
            sem_latency_ms = (time.perf_counter() - t_sem_start) * 1000.0

            # Evaluate decision through Authority Gate
            decision = self.authority_gate.decide(
                canonical_intent=qwen_intent,
                transcript=text,
                context=ctx,
                model_error=sem_error,
                latency_ms=sem_latency_ms,
            )
            self.last_semantic_decision = decision.to_dict()
            self.last_canonical_intent = qwen_intent.to_dict() if qwen_intent else None

            qwen_desc = f"intent={qwen_intent.intent}" if qwen_intent else "none"
            fb_desc = decision.fallback_reason or "none"
            logger.info(
                f"SEMANTIC_DECISION: transcript=\"{text}\" qwen={qwen_desc} "
                f"authority={decision.source.value} fallback={fb_desc} "
                f"accepted={decision.accepted} latency={sem_latency_ms:.1f}ms "
                f"category={decision.category}"
            )

            if decision.source == SemanticAuthoritySource.QWEN:
                # Qwen Primary Authority: Resolve context to CommandObject
                cmd = self.context_resolver.resolve(decision, text, ctx, task_id=task_id, context_store=self.context_store)
                logger.info(f"[CommandPipeline] Qwen Primary accepted: intent='{cmd.intent}' category='{cmd.category.value}' tools={cmd.required_tools}")

            elif decision.source == SemanticAuthoritySource.CLARIFICATION:
                # Clarification Authority: Conversational CommandObject (0 tools)
                cmd = self.context_resolver.resolve(decision, text, ctx, task_id=task_id, context_store=self.context_store)
                logger.info(f"[CommandPipeline] Clarification required: '{cmd.raw_response}'")

            else:
                # Legacy Fallback / Deterministic: Parse with legacy parser
                cmd = self.parser.parse(text, task_id=task_id, context=ctx)
                logger.info(f"[CommandPipeline] Legacy fallback: intent='{cmd.intent}' category='{cmd.category.value}'")

            # Maintain single active shadow task for telemetry / background tracking
            if self._active_shadow_task and not self._active_shadow_task.done():
                self._active_shadow_task.cancel()
            self._active_shadow_task = asyncio.create_task(self._record_semantic_shadow(text, ctx, cmd))

        # 3. Handle Special Case: Repeat Last Task (Replay verified semantic action per Section 9)
        if (cmd.intent in ("repeat_last_task", "repeat_action") or cmd.parameters.get("modifier") == "repeat") and not cmd.execution_plan:
            replayable = self.context_store.get_replayable_action()
            if replayable and replayable.execution_plan_steps:
                logger.info(f"[CommandPipeline] Replaying verified semantic action: intent='{replayable.semantic_intent}', tools={replayable.required_tools}")
                cmd.execution_plan = [
                    PlanStepItem(
                        step_id=s.get("step_id", idx + 1),
                        goal=s.get("goal", f"Repeat step {idx + 1}"),
                        action=s.get("action", ""),
                        arguments=dict(s.get("arguments", {})),
                        timeout_seconds=s.get("timeout_seconds", 8.0),
                        verification_type=s.get("verification_type", "state_check"),
                    )
                    for idx, s in enumerate(replayable.execution_plan_steps)
                ]
                cmd.required_tools = list(replayable.required_tools)
                cmd.complexity = CommandComplexity.ONE_TOOL if len(cmd.execution_plan) == 1 else CommandComplexity.MULTI_STEP
                cmd.intent = f"repeat_{replayable.semantic_intent}"
            elif self.last_successful_command and self.last_successful_command.execution_plan:
                logger.info(f"[CommandPipeline] Repeating previous plan: {self.last_successful_command.intent}")
                cloned_plan = [
                    PlanStepItem(
                        step_id=idx + 1,
                        goal=s.goal,
                        action=s.action,
                        arguments=dict(s.arguments),
                        timeout_seconds=s.timeout_seconds,
                        verification_type=s.verification_type,
                    )
                    for idx, s in enumerate(self.last_successful_command.execution_plan)
                ]
                cmd.execution_plan = cloned_plan
                cmd.required_tools = list(self.last_successful_command.required_tools)
                cmd.complexity = self.last_successful_command.complexity
                cmd.intent = f"repeat_{self.last_successful_command.intent}"
            else:
                resp_text = "There is no previous task available to repeat."
                return self._finalize_result(task_id, False, resp_text, t_start, error="No previous task to repeat")

        # 4. Handle Direct Conversational Fast-Path (0 Tools or Clarification)
        if cmd.raw_response is not None:
            return self._finalize_result(task_id, True, cmd.raw_response, t_start)

        # 5. Handle Cancellation Command
        if cmd.intent == "cancel_current_task":
            self.state.transition_to(SERAStatus.IDLE)
            self._emit_event("TASK_CANCELLED", {"task_id": task_id, "reason": "Cancelled by user command"})
            return self._finalize_result(task_id, True, "Task cancelled.", t_start)

        self._current_source = source

        # 6. Total Task Timeout Budget
        if cmd.complexity == CommandComplexity.SIMPLE:
            task_timeout = 10.0
        elif cmd.complexity in (CommandComplexity.ONE_TOOL, CommandComplexity.MULTI_STEP):
            task_timeout = 30.0 if "inspect_screen" not in cmd.required_tools else 60.0
        else:
            task_timeout = 45.0

        self.active_cancellation_event = asyncio.Event()

        try:
            return await asyncio.wait_for(
                self._execute_command_internal(cmd, task_id, t_start, metrics, cancellation_event=self.active_cancellation_event),
                timeout=task_timeout,
            )
        except asyncio.TimeoutError:
            err_msg = f"Task exceeded safety deadline of {task_timeout}s."
            logger.warning(f"[CommandPipeline] {err_msg}")
            self.state.transition_to(SERAStatus.BROKEN)
            self._emit_event("TASK_FAILED", {"task_id": task_id, "error": err_msg})
            spoken_err = "That request took a little too long to finish. Let's try that again."
            return self._finalize_result(task_id, False, spoken_err, t_start, error=err_msg)

    async def _execute_command_internal(
        self,
        cmd: CommandObject,
        task_id: str,
        t_start: float,
        metrics: Any = None,
        cancellation_event: asyncio.Event | None = None,
    ) -> dict[str, Any]:
        """Executes the execution plan using the canonical StatefulGraphRuntime."""

        # -------------------------------------------------------------
        # BRANCH A: Deterministic Execution Plan (Stateful Graph Runtime)
        # -------------------------------------------------------------
        if cmd.execution_plan:
            self.state.transition_to(SERAStatus.TASK_EXECUTING)

            graph_state = GraphState(
                raw_user_input=cmd.source_text,
                task_id=task_id,
                input_source=getattr(self, "_current_source", "TEXT"),
                context_state=dict(self.context_state),
                canonical_intent=getattr(self, "last_canonical_intent", None),
                semantic_shadow=getattr(self, "last_semantic_shadow", None),
                semantic_decision=getattr(self, "last_semantic_decision", None),
                steps=[
                    GraphPlanStep(
                        step_id=s.step_id,
                        goal=s.goal,
                        action=s.action,
                        arguments=dict(s.arguments),
                        timeout_seconds=s.timeout_seconds,
                        verification_type=s.verification_type,
                    )
                    for s in cmd.execution_plan
                ],
            )

            res_state = await self.graph_runtime.execute(
                graph_state,
                cancellation_event=cancellation_event,
            )

            # Sync context state from GraphState
            self.context_state.update(res_state.context_state)
            if res_state.active_application:
                self.last_application = res_state.active_application
            if res_state.last_verified_action:
                self.last_verified_action = res_state.last_verified_action

            step_results = [
                {
                    "success": s.completed,
                    "tool": s.action,
                    "result": res_state.observation.observed_state if (res_state.observation and res_state.current_action == s.action) else {},
                    "latency_ms": s.latency_ms,
                    "error": s.error,
                }
                for s in res_state.steps
            ]

            if res_state.status == GraphExecutionStatus.CANCELLED:
                self.state.transition_to(SERAStatus.IDLE)
                return self._finalize_result(task_id, False, "Task cancelled.", t_start, error="Cancelled by user", step_results=step_results)

            if res_state.status != GraphExecutionStatus.SUCCESS:
                err = res_state.last_error or f"Step failed."
                self.state.transition_to(SERAStatus.BROKEN)
                self._emit_event("TASK_FAILED", {"task_id": task_id, "error": err, "status": "BROKEN"})
                spoken_err = self._synthesize_conversational_error(cmd.intent, err, cmd.parameters)
                return self._finalize_result(task_id, False, spoken_err, t_start, error=err, step_results=step_results)

            # Capture entity context from steps and record verified replayable action
            for step in cmd.execution_plan:
                if step.action == "open_application" and step.arguments.get("application"):
                    self.last_application = step.arguments.get("application").lower()
                    self.context_store.record_active_application(self.last_application)
                elif step.action in ("browser_open", "youtube_search", "web_search"):
                    self.last_application = "chrome"
                    self.context_store.record_active_application("chrome")
                    if step.arguments.get("query"):
                        self.context_state["last_search_query"] = step.arguments.get("query")
                    if step.action == "browser_open" and step.arguments.get("url"):
                        opened_url = step.arguments.get("url")
                        matched = self.context_store.record_opened_url(opened_url)
                        if not matched and cmd.parameters.get("index") is not None:
                            self.context_store.record_opened_result_by_ordinal(cmd.parameters["index"] + 1)
                elif step.action == "open_folder" and step.arguments.get("folder_name"):
                    self.last_folder = step.arguments.get("folder_name").capitalize()
                elif step.action == "open_file" and step.arguments.get("file_path"):
                    self.last_file = step.arguments.get("file_path")
                elif step.action == "set_brightness":
                    self.context_state["last_intent"] = "set_brightness"
                    self.context_state["last_tool"] = "set_brightness"
                    self.context_state["last_brightness"] = step.arguments.get("brightness")
                    if step.arguments.get("brightness") is not None:
                        self.context_store.record_setting_change("brightness", step.arguments.get("brightness"))
                elif step.action == "set_volume":
                    self.context_state["last_intent"] = "set_volume"
                    self.context_state["last_tool"] = "set_volume"
                    self.context_state["last_volume"] = step.arguments.get("volume")
                    if step.arguments.get("volume") is not None:
                        self.context_store.record_setting_change("volume", step.arguments.get("volume"))
                elif step.action == "close_browser_tab":
                    tab_id = step.arguments.get("tab_identifier") or "current"
                    self.context_store.remove_tab(tab_id)

            # Record verified replayable semantic action (Section 9)
            if cmd.execution_plan:
                first_step = cmd.execution_plan[0]
                resolved_ent = cmd.entities.get("resolved_entity") or cmd.entities.get("target")
                entity_id = getattr(resolved_ent, "entity_id", None) if resolved_ent else None
                entity_type = getattr(resolved_ent, "entity_type", None) if resolved_ent else None
                replayable = ReplayableSemanticAction(
                    action_id=f"act_{uuid.uuid4().hex[:8]}",
                    task_id=task_id,
                    semantic_intent=cmd.intent,
                    resolved_entity_id=entity_id,
                    canonical_arguments=dict(first_step.arguments),
                    execution_plan_steps=[
                        {
                            "step_id": s.step_id,
                            "goal": s.goal,
                            "action": s.action,
                            "arguments": dict(s.arguments),
                            "timeout_seconds": s.timeout_seconds,
                            "verification_type": s.verification_type,
                        }
                        for s in cmd.execution_plan
                    ],
                    required_tools=list(cmd.required_tools),
                    verification_type=first_step.verification_type,
                    is_idempotent=True,
                    verified_outcome={"status": "SUCCESS"},
                )
                self.context_store.record_action(replayable)

            # Synthesize Clean Single Response
            final_spoken_response = self._synthesize_plan_response(cmd, step_results) or res_state.final_response

            # Record in context memory on success
            self.last_successful_command = cmd
            self.context_state["last_intent"] = cmd.intent
            self.state.transition_to(SERAStatus.TASK_COMPLETED)
            return self._finalize_result(task_id, True, final_spoken_response, t_start, step_results=step_results)

        # -------------------------------------------------------------
        # BRANCH B: Ambiguous / Complex Fallback -> Bounded LLM Agent
        # -------------------------------------------------------------
        logger.info(f"[CommandPipeline] Routing ambiguous/unstructured request to LLM: '{cmd.source_text}'")
        self.state.transition_to(SERAStatus.THINKING)
        self._emit_event("MODEL_SELECTED", {
            "task_id": task_id,
            "role": "fast",
            "provider": "Groq",
            "model": "gpt-oss-120b",
        })

        if not self.router:
            fallback_msg = "Command could not be resolved deterministically."
            return self._finalize_result(task_id, False, fallback_msg, t_start, error=fallback_msg)

        try:
            llm_resp, _ = await asyncio.wait_for(
                self.router.generate_with_fallback(
                    messages=[
                        {"role": "system", "content": "You are SERA, a personal desktop assistant. Keep responses under 2 sentences."},
                        {"role": "user", "content": cmd.source_text},
                    ],
                    tools=self.tools.schemas(),
                    preferred_role="fast",
                ),
                timeout=12.0,
            )
            resp_str = llm_resp.text.strip() or "Task completed."
            return self._finalize_result(task_id, True, resp_str, t_start)
        except Exception as e:
            err_msg = f"LLM generation failed: {str(e)}"
            logger.error(f"[CommandPipeline] {err_msg}", exc_info=True)
            conversational_msg = "I ran into an issue while processing that request. Please try again."
            return self._finalize_result(task_id, False, conversational_msg, t_start, error=err_msg)

    async def _execute_single_step(
        self,
        step: PlanStepItem,
        task_id: str,
        step_idx: int,
        total_steps: int,
    ) -> dict[str, Any]:
        """Executes a single plan step with timeout, argument validation, and deduplication guard."""
        tool_name = step.action
        tool_args = step.arguments

        # Deduplication signature
        sig = f"{task_id}:{step_idx}:{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
        if sig in self._executed_signatures:
            logger.warning(f"[CommandPipeline] Skipping duplicate execution of signature: {sig}")
            return {"success": True, "tool": tool_name, "deduplicated": True, "result": {}, "message": "Already executed in this step."}
        self._executed_signatures.add(sig)

        # 1. Validate Tool Registration
        tool = self.tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool '{tool_name}' is not registered in ToolRegistry."}

        # 2. Emit UI Start Events
        if tool_name == "capture_screen":
            self._emit_event("SCREEN_CAPTURE_STARTED", {"task_id": task_id, "tool": tool_name, "arguments": tool_args})
        elif tool_name == "inspect_screen":
            self._emit_event("VISION_STARTED", {"task_id": task_id, "tool": tool_name, "arguments": tool_args})
        else:
            self._emit_event("TOOL_STARTED", {"task_id": task_id, "tool_name": tool_name, "arguments": tool_args, "step": step_idx, "total_steps": total_steps})

        t0_step = time.time()
        try:
            # Execute with per-step bounded timeout
            tool_res = await asyncio.wait_for(
                tool.execute(**tool_args),
                timeout=step.timeout_seconds,
            )
            step_latency_ms = round((time.time() - t0_step) * 1000, 1)

            is_success = isinstance(tool_res, dict) and tool_res.get("success", False)
            if not isinstance(tool_res, dict):
                is_success = bool(tool_res)

            # Phase 2A: Evidence Verification Fabric Check
            evidence = self.evidence_fabric.verify_tool_execution(tool_name, tool_res)
            if not evidence.verified:
                is_success = False

            if not is_success:
                tool_err = tool_res.get("error") if isinstance(tool_res, dict) else None
                err_text = tool_err or evidence.failure_reason or f"Execution of {tool_name} failed."
                self._emit_event("TOOL_FAILED", {"task_id": task_id, "tool_name": tool_name, "error": err_text, "evidence": evidence.to_dict()})
                return {"success": False, "tool": tool_name, "error": err_text, "latency_ms": step_latency_ms, "evidence": evidence.to_dict()}

            # Emit Verified Evidence Event
            self._emit_event("EVIDENCE_VERIFIED", {
                "task_id": task_id,
                "tool_name": tool_name,
                "evidence": evidence.to_dict(),
            })

            # Emit Completion Events
            if tool_name == "capture_screen":
                self._emit_event("SCREEN_CAPTURED", {
                    **(tool_res if isinstance(tool_res, dict) else {}),
                    "task_id": task_id,
                    "tool": tool_name,
                    "latency_ms": step_latency_ms,
                    "evidence": evidence.to_dict(),
                })
            elif tool_name == "inspect_screen":
                self._emit_event("VISION_COMPLETED", {
                    "task_id": task_id,
                    "tool": tool_name,
                    "result": tool_res.get("response") or tool_res.get("result") or tool_res,
                    "latency_ms": step_latency_ms,
                    "evidence": evidence.to_dict(),
                })
            else:
                self._emit_event("TOOL_COMPLETED", {
                    "task_id": task_id,
                    "tool_name": tool_name,
                    "result": tool_res,
                    "latency_ms": step_latency_ms,
                    "evidence": evidence.to_dict(),
                })

            return {"success": True, "tool": tool_name, "result": tool_res, "latency_ms": step_latency_ms, "evidence": evidence.to_dict()}

        except asyncio.TimeoutError:
            err = f"Step '{step.goal}' timed out after {step.timeout_seconds}s."
            self._emit_event("TOOL_FAILED", {"task_id": task_id, "tool_name": tool_name, "error": err})
            return {"success": False, "tool": tool_name, "error": err}
        except Exception as e:
            err = f"Error executing {tool_name}: {str(e)}"
            self._emit_event("TOOL_FAILED", {"task_id": task_id, "tool_name": tool_name, "error": err})
            return {"success": False, "tool": tool_name, "error": err}

    def _synthesize_plan_response(self, cmd: CommandObject, step_results: list[dict[str, Any]]) -> str:
        """Generates exactly ONE concise, truthful assistant response sentence."""
        intent = cmd.intent
        last_step_res = step_results[-1].get("result") if step_results else {}

        # Screen Capture
        if intent == "capture_screen":
            dim = last_step_res.get("dimensions") or "1920x1200" if isinstance(last_step_res, dict) else ""
            return f"Screenshot captured successfully ({dim})." if dim else "Screenshot captured successfully."

        # Screen Vision Perception
        if intent in ("inspect_screen", "screenshot_and_analyze"):
            for res in reversed(step_results):
                r_dict = res.get("result", {})
                if isinstance(r_dict, dict) and (r_dict.get("response") or r_dict.get("description") or r_dict.get("result")):
                    return str(r_dict.get("response") or r_dict.get("description") or r_dict.get("result"))
                elif isinstance(r_dict, str) and r_dict.strip():
                    return r_dict.strip()
            return "Screen analyzed."

        # YouTube Search
        if intent in ("youtube_search", "open_and_youtube_search"):
            q = cmd.parameters.get("query", "")
            return f"Searched YouTube for '{q}' and opened the results."

    def _synthesize_conversational_error(self, intent: str, technical_error: str, parameters: dict | None = None) -> str:
        """Shields the user and Primary Presence from raw exceptions, process exit codes, and Win32 errors."""
        params = parameters or {}
        t_err = (technical_error or "").lower()

        if "timeout" in t_err or "deadline" in t_err:
            return "That request took a little too long to finish. Let's try that again."

        if intent == "open_application":
            app = params.get("application", "that application")
            return f"I couldn't find or open {app}."

        if intent == "close_application":
            app = params.get("application", "that application")
            return f"I wasn't able to close {app}."

        if intent == "set_brightness":
            return "I wasn't able to adjust the brightness on this display."

        if intent in ("set_volume", "mute", "unmute"):
            return "I couldn't change the audio volume right now."

        if intent in ("web_search", "youtube_search"):
            return "I had trouble searching right now. Please check your internet connection."

        if intent in ("find_files", "open_folder", "open_file"):
            return "I couldn't locate that file or folder on your computer."

        if intent in ("screen_capture_only", "inspect_screen", "analyze_screen"):
            return "I had trouble capturing your screen just now."

        if intent == "sera_self_close":
            return "I wasn't able to close the presence window automatically."

        return "I ran into a problem taking care of that. Could you ask me again?"

    def _synthesize_plan_response(self, cmd: CommandObject, step_results: list[dict[str, Any]]) -> str:
        """Synthesizes an intelligent, concise, conversational response for multi-step or single-step plans."""
        intent = cmd.intent
        last_step_res = step_results[-1].get("result") if step_results else {}

        # Screen Capture & Vision
        if intent == "screen_capture_only":
            return "I've captured your screen for you."

        if intent in ("screen_capture_and_inspect", "inspect_screen"):
            if isinstance(last_step_res, dict) and last_step_res.get("summary"):
                return str(last_step_res.get("summary"))
            return "Here is what I see on your screen."

        # YouTube Search
        if intent in ("youtube_search", "open_and_youtube_search"):
            q = cmd.parameters.get("query", "")
            return f"I've searched YouTube for '{q}'."

        # Web Search
        if intent in ("web_search", "open_and_web_search"):
            q = cmd.parameters.get("query", "")
            count = last_step_res.get("count", 0) if isinstance(last_step_res, dict) else (len(last_step_res.get("results", [])) if isinstance(last_step_res, dict) else 0)
            if count > 0:
                return f"I found {count} results for {q}."
            return f"Here's what I found for '{q}'."

        # Open Application
        if intent == "open_application":
            app = cmd.parameters.get("application", "").strip()
            if app.lower() in ("chrome", "google chrome"):
                return "I've opened Chrome for you."
            return f"I've opened {app.capitalize()}."

        # Close Application
        if intent == "close_application":
            app = cmd.parameters.get("application", "")
            return f"I've closed {app.capitalize()}."

        # Switch Application
        if intent == "switch_application":
            app = cmd.parameters.get("application", "")
            return f"I've switched focus to {app.capitalize()}."

        # Open Search Result / Reference
        if intent in ("open_search_result", "open_reference"):
            title = cmd.parameters.get("title") or "the selected result"
            return f"I've opened {title} for you."

        # Repeat Previous Action
        if intent.startswith("repeat_"):
            return "I've repeated the previous action for you."

        # Open Folder
        if intent in ("open_folder", "open_folder_and_find"):
            folder = cmd.parameters.get("folder_name", "")
            if intent == "open_folder_and_find":
                pat = cmd.parameters.get("pattern", "")
                return f"I've opened your {folder.capitalize()} folder and searched for '{pat}'."
            return f"I've opened your {folder.capitalize()} folder."

        # Find Files
        if intent == "find_files":
            pat = cmd.parameters.get("pattern", "")
            folder = cmd.parameters.get("folder", "Downloads")
            count = last_step_res.get("count", 0) if isinstance(last_step_res, dict) else 0
            if count > 0:
                latest = last_step_res.get("latest_file", {}).get("name") if isinstance(last_step_res, dict) else ""
                if latest:
                    return f"I found '{latest}' in your {folder} folder."
                return f"I found {count} file{'s' if count != 1 else ''} matching '{pat}' in your {folder} folder."
            return f"I couldn't find any files matching '{pat}' in your {folder} folder."

        # Open File
        if intent == "open_file":
            fp = cmd.parameters.get("file_path", "")
            return f"I've opened '{os.path.basename(fp)}'."

        # System: Time
        if intent == "get_current_time":
            if isinstance(last_step_res, dict) and last_step_res.get("time"):
                return f"It's {last_step_res.get('time')} on {last_step_res.get('date')}."
            return "The current time has been retrieved."

        # System: System Info
        if intent == "get_system_info":
            if isinstance(last_step_res, dict):
                cpu = last_step_res.get("cpu_percent", "N/A")
                ram = last_step_res.get("memory", {}).get("percent", "N/A")
                return f"Your CPU is at {cpu} percent, and memory is at {ram} percent."
            return "All system diagnostics look healthy."

        # System: Battery
        if intent == "get_battery_status":
            if isinstance(last_step_res, dict) and last_step_res.get("percentage") is not None:
                pct = last_step_res.get("percentage")
                plugged = "charging" if last_step_res.get("charging") else "on battery power"
                return f"Your battery is at {pct} percent and currently {plugged}."
            return "Your battery status is steady."

        # System: Wi-Fi
        if intent == "get_wifi_status":
            if isinstance(last_step_res, dict):
                ssid = last_step_res.get("ssid")
                if ssid and ssid != "Not connected":
                    return f"You're connected to {ssid}."
                return "Your Wi-Fi is currently disconnected."
            return "Your network status is steady."

        # System: Brightness / Volume / Mute
        if intent == "set_brightness":
            return f"I've set the brightness to {cmd.parameters.get('brightness')} percent."
        if intent == "set_volume":
            return f"I've set the volume to {cmd.parameters.get('volume')} percent."
        if intent == "mute":
            return "I've muted your audio."
        if intent == "unmute":
            return "I've unmuted your audio."

        # Self Close
        if intent == "sera_self_close":
            return "Goodbye! Closing presence now."

        # Power
        if intent == "lock_computer":
            return "I've locked your computer."
        if intent == "sleep_computer":
            return "Putting your computer to sleep."

        # List Running Applications
        if intent == "list_running_applications":
            count = last_step_res.get("count", 0) if isinstance(last_step_res, dict) else 0
            return f"You currently have {count} active applications running."

        # Assistant Attention / Wake
        if intent == "assistant_wake":
            return "Yes, I'm here. How can I help you?"

        # Close Browser Tab (Section 12)
        if intent == "close_browser_tab":
            tab_name = cmd.parameters.get("tab") or cmd.parameters.get("tab_identifier") or ""
            if tab_name and tab_name != "current":
                return f"I've closed the {tab_name} tab for you."
            return "I've closed the current browser tab for you."

        # Focus Browser Tab
        if intent == "focus_browser_tab":
            tab_name = cmd.parameters.get("tab") or ""
            if tab_name:
                return f"I've brought the {tab_name} tab to the front."
            return "I've switched to that browser tab."

        # Setting restoration (Section 18)
        if (intent in ("set_brightness", "restore_setting") or "brightness" in intent) and cmd.parameters.get("is_restore"):
            val = cmd.parameters.get("brightness")
            return f"I've restored the brightness back to {val} percent."

        if (intent in ("set_volume", "restore_setting") or "volume" in intent) and cmd.parameters.get("is_restore"):
            val = cmd.parameters.get("volume")
            return f"I've restored the volume back to {val} percent."

        # General
        if isinstance(last_step_res, dict) and last_step_res.get("message"):
            return str(last_step_res.get("message"))
        return "I've taken care of that for you."

    def _finalize_result(
        self,
        task_id: str,
        success: bool,
        response_text: str,
        t_start: float,
        error: str | None = None,
        step_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Ensures terminal state, updates state machine, and broadcasts single response event."""
        duration = round(time.time() - t_start, 2)

        # Ensure raw technical exceptions never leak into spoken/user-facing response (Section 28)
        lower_resp = (response_text or "").lower()
        if any(marker in lower_resp for marker in ("traceback", "exception:", "error:", "'nonetype'", "object has no attribute", "timed out after", "connectionrefused")):
            response_text = "I ran into an issue while processing that request. Please try again."

        self.state.last_response = response_text
        is_voice = getattr(self, "_current_is_voice_turn", False)

        if not is_voice:
            # 1. Emit Authoritative Single Response Payload for standalone calls
            self._emit_event("AGENT_RESPONSE", {
                "task_id": task_id,
                "turn_id": task_id,
                "type": "ASSISTANT_MESSAGE",
                "content": response_text,
                "status": "COMPLETED" if success else "BROKEN",
            })

            # 2. Emit Terminal State Event
            if success:
                self.state.transition_to(SERAStatus.IDLE)
                self._emit_event("TASK_COMPLETED", {
                    "task_id": task_id,
                    "status": "COMPLETED",
                    "result": response_text,
                    "duration_seconds": duration,
                    "steps": step_results or [],
                })
            else:
                self.state.transition_to(SERAStatus.BROKEN)
                self._emit_event("TASK_FAILED", {
                    "task_id": task_id,
                    "status": "BROKEN",
                    "error": error or response_text,
                    "duration_seconds": duration,
                })
        else:
            # Under voice turns, SERARuntime manages AGENT_RESPONSE -> SPEAKING -> TTS -> TASK_COMPLETED -> IDLE
            if not success:
                self.state.transition_to(SERAStatus.BROKEN)
                self._emit_event("TASK_FAILED", {
                    "task_id": task_id,
                    "status": "BROKEN",
                    "error": error or response_text,
                    "duration_seconds": duration,
                })

        print(f"\n[SERA RESPONSE] ({duration}s) {response_text}")

        return {
            "success": success,
            "task_id": task_id,
            "response": response_text,
            "error": error,
            "duration_seconds": duration,
            "steps": step_results or [],
        }

    def _emit_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Safely dispatches event to EventBus."""
        if hasattr(self.event_bus, "emit"):
            try:
                self.event_bus.emit(event_name, payload)
            except Exception as e:
                logger.debug(f"[CommandPipeline] EventBus emit error: {e}")

    async def _record_semantic_shadow(
        self, text: str, ctx: dict[str, Any], legacy_cmd: CommandObject
    ) -> dict[str, Any]:
        """Evaluates utterance with SemanticInterpreter in shadow mode and logs comparison."""
        try:
            compact_ctx = self.semantic_interpreter.extract_compact_context(extra_context=ctx)
            qwen_intent = await self.semantic_interpreter.interpret_async(text, compact_ctx)

            legacy_target = (
                legacy_cmd.entities.get("application")
                or legacy_cmd.entities.get("target")
                or legacy_cmd.parameters.get("query")
                or legacy_cmd.parameters.get("setting")
                or ""
            )
            qwen_target = qwen_intent.target.value if qwen_intent.target else ""

            # Check intent agreement
            intent_match = (
                legacy_cmd.intent == qwen_intent.intent
                or (legacy_cmd.intent == "assistant_wake" and qwen_intent.intent in ("assistant_wake", "greeting"))
                or (legacy_cmd.intent == "repeat_last_task" and (qwen_intent.intent == "repeat_last_task" or qwen_intent.modifiers.repeat))
                or (legacy_cmd.intent.startswith("open_") and qwen_intent.intent.startswith("open_"))
                or (legacy_cmd.intent.startswith("close_") and qwen_intent.intent.startswith("close_"))
                or (legacy_cmd.intent.startswith("set_") and qwen_intent.intent.startswith("set_"))
            )

            # Check target agreement
            target_match = True
            if legacy_target and qwen_target:
                target_match = (
                    legacy_target.lower() in qwen_target.lower()
                    or qwen_target.lower() in legacy_target.lower()
                )
            elif bool(legacy_target) != bool(qwen_target):
                target_match = False

            agreement = intent_match and target_match

            comparison = {
                "transcript": text,
                "legacy": {
                    "intent": legacy_cmd.intent,
                    "category": legacy_cmd.category.value,
                    "target": legacy_target,
                },
                "qwen": qwen_intent.to_dict(),
                "agreement": agreement,
                "intent_match": intent_match,
                "target_match": target_match,
                "timestamp": time.time(),
            }
            self.last_semantic_shadow = comparison
            self.last_canonical_intent = qwen_intent.to_dict()
            self.shadow_records.append(comparison)

            logger.info(
                f"SEMANTIC_SHADOW: transcript=\"{text}\" "
                f"legacy=intent={legacy_cmd.intent},target={legacy_target} "
                f"qwen=intent={qwen_intent.intent},target={qwen_target},modifier_repeat={qwen_intent.modifiers.repeat} "
                f"agreement={agreement}"
            )
            return comparison
        except asyncio.CancelledError:
            logger.debug(f"[CommandPipeline] Semantic shadow evaluation cancelled for: '{text}'")
            return {}
        except Exception as e:
            logger.debug(f"[CommandPipeline] Semantic shadow evaluation skipped/failed: {e}")
            return {}

