"""
SERA 2.0 / Phase 4B — Live Hermes Agent Bridge (SeraHermesBridge).

Provides a clean, non-destructive architectural adapter between SERA and the official
Nous Research Hermes Agent runtime.
Translates user utterances + verified compact context into Hermes AgentPlans,
enforces multi-step continuation, cancellation semantics, timeout guards, and
safety-preserving fallback.

Architectural Rule:
"Hermes is an external agent harness that SERA integrates with. SERA does not implement Hermes."
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from app.adapters.hermes.schema import (
    AgentPlan,
    AgentStep,
    ApprovalDecision,
    ApprovalStatus,
    ExecutionHandoffStatus,
    HermesExecutionTelemetry,
    HermesMode,
    HermesTraceItem,
    PermissionRequirement,
    RiskLevel,
    TargetType,
)
from app.adapters.hermes.skills import SkillRegistry, HermesSkill
from app.adapters.hermes.memory import MemoryContract, MemoryRetrievalQuery, MemoryScope
from app.core.command import CommandCategory, CommandComplexity, CommandObject, PlanStepItem
from app.core.semantic.schema import CompactSemanticContext

logger = logging.getLogger("sera.hermes.bridge")


class HermesClientBackend:
    """Protocol for Hermes inference backend (Official Runtime, API Server, or Mock)."""

    async def execute_reasoning_loop(
        self,
        system_prompt: str,
        user_message: str,
        available_tools: List[Dict[str, Any]],
        cancel_event: asyncio.Event,
        trace_collector: List[HermesTraceItem],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def continue_reasoning_loop(
        self,
        system_prompt: str,
        original_objective: str,
        step_history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        cancel_event: asyncio.Event,
        trace_collector: List[HermesTraceItem],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class OfficialHermesClient(HermesClientBackend):
    """Executes reasoning loops against the REAL official Nous Research Hermes Agent.

    Invokes the official hermes CLI runner (`hermes -z` / oneshot mode)
    with the configured model provider (e.g. OpenRouter).
    Captures genuine token metrics, session IDs, finish reasons, and timings.
    """

    def __init__(
        self,
        hermes_bin: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.hermes_bin = hermes_bin or os.environ.get(
            "HERMES_EXECUTABLE_PATH",
            os.path.expandvars(r"%LOCALAPPDATA%\hermes\bin\hermes.exe"),
        )
        self.provider = provider or os.environ.get("HERMES_PROVIDER", "openrouter")
        self.model = model or os.environ.get("HERMES_MODEL", "meta-llama/llama-3.3-70b-instruct")
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.last_usage_data: Dict[str, Any] = {}
        self.last_latency: float = 0.0

    @classmethod
    def is_available(cls, bin_path: Optional[str] = None) -> bool:
        path = bin_path or os.environ.get(
            "HERMES_EXECUTABLE_PATH",
            os.path.expandvars(r"%LOCALAPPDATA%\hermes\bin\hermes.exe"),
        )
        return os.path.isfile(path)

    async def _run_hermes_process(
        self,
        full_prompt: str,
        task_label: str,
        cancel_event: asyncio.Event,
        trace_collector: List[HermesTraceItem],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        if cancel_event.is_set():
            trace_collector.append(HermesTraceItem(
                timestamp=time.time(),
                role="thought",
                content="Cancellation received prior to Hermes execution."
            ))
            return {"finish_reason": "cancelled", "objective": task_label, "steps": []}

        usage_file = tempfile.mktemp(suffix=".json")
        env = os.environ.copy()
        if self.api_key:
            env["OPENROUTER_API_KEY"] = self.api_key

        cmd = [
            self.hermes_bin,
            "-z", full_prompt,
            "--provider", self.provider,
            "-m", self.model,
            "--usage-file", usage_file,
        ]

        t0 = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except Exception as exc:
            trace_collector.append(HermesTraceItem(
                timestamp=time.time(),
                role="error",
                content=f"Failed to spawn official Hermes process: {exc}"
            ))
            raise RuntimeError(f"Official Hermes runtime execution failed: {exc}")

        wait_proc = asyncio.create_task(proc.communicate())
        wait_cancel = asyncio.create_task(cancel_event.wait())

        try:
            done, pending = await asyncio.wait(
                [wait_proc, wait_cancel],
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if cancel_event.is_set():
                try:
                    proc.terminate()
                    await asyncio.sleep(0.1)
                    if proc.returncode is None:
                        proc.kill()
                except Exception as e:
                    logger.warning(f"Error terminating Hermes process on cancellation: {e}")

                trace_collector.append(HermesTraceItem(
                    timestamp=time.time(),
                    role="thought",
                    content="Cancellation signaled during Hermes reasoning. Subprocess terminated."
                ))
                return {"finish_reason": "cancelled", "objective": task_label, "steps": []}

            if not done:
                try:
                    proc.terminate()
                except Exception:
                    pass
                trace_collector.append(HermesTraceItem(
                    timestamp=time.time(),
                    role="error",
                    content=f"Hermes execution timed out after {timeout}s"
                ))
                return {
                    "finish_reason": "timeout",
                    "objective": task_label,
                    "steps": [],
                    "needs_clarification": True,
                    "clarification_prompt": f"Hermes reasoning timed out after {timeout} seconds.",
                }

            stdout_bytes, stderr_bytes = await wait_proc
            stdout_str = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr_str = stderr_bytes.decode("utf-8", errors="replace").strip()

        finally:
            wait_cancel.cancel()
            if not wait_proc.done():
                wait_proc.cancel()

        duration = time.perf_counter() - t0
        self.last_latency = duration

        usage_data = {}
        if os.path.exists(usage_file):
            try:
                with open(usage_file, "r", encoding="utf-8") as f:
                    usage_data = json.load(f)
            except Exception:
                pass
            try:
                os.remove(usage_file)
            except Exception:
                pass

        self.last_usage_data = usage_data
        total_tokens = usage_data.get("total_tokens", 0)
        session_id = usage_data.get("session_id", "none")
        cost = usage_data.get("estimated_cost_usd", 0.0)

        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="assistant",
            content=f"[Official Hermes Telemetry: latency={duration:.2f}s, tokens={total_tokens}, cost=${cost:.6f}, session={session_id}]\n{stdout_str}"
        ))

        parsed = self._extract_json(stdout_str)
        if parsed:
            return parsed

        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="warning",
            content=f"Could not parse structured JSON from Hermes output: {stdout_str[:200]}"
        ))
        return {
            "objective": task_label,
            "steps": [],
            "needs_clarification": True,
            "clarification_prompt": "Could you please clarify your request?",
            "confidence": 0.5,
        }

    async def execute_reasoning_loop(
        self,
        system_prompt: str,
        user_message: str,
        available_tools: List[Dict[str, Any]],
        cancel_event: asyncio.Event,
        trace_collector: List[HermesTraceItem],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="system",
            content=f"Official Hermes runtime invoked ({self.hermes_bin}) [Provider: {self.provider}, Model: {self.model}]."
        ))
        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="user",
            content=user_message
        ))

        tools_desc = "\n".join(f"- {t['name']}: {t.get('description', '')}" for t in available_tools)
        full_prompt = (
            f"{system_prompt}\n\n"
            f"### AVAILABLE SERA CAPABILITIES:\n{tools_desc}\n\n"
            f"### USER UTTERANCE:\n\"{user_message}\"\n\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            "  \"objective\": \"Brief task summary\",\n"
            "  \"is_complete\": false,\n"
            "  \"steps\": [\n"
            "    {\"step_id\": 1, \"action\": \"tool_name\", \"arguments\": {\"arg\": \"val\"}, \"target_type\": \"APPLICATION|WINDOW|BROWSER|TAB|WEBPAGE|SEARCH_RESULT|SETTING\", \"target_reference\": \"reference\", \"rationale\": \"why\", \"expected_evidence\": \"WINDOW_HANDLE|PROCESS_ID|VALUE_CHECK\"}\n"
            "  ],\n"
            "  \"confidence\": 0.95,\n"
            "  \"needs_clarification\": false,\n"
            "  \"clarification_prompt\": null\n"
            "}\n"
            "If the user wants to cancel or stop, set steps=[] and objective=\"Cancel task\".\n"
            "If the request is ambiguous (e.g. referent missing like 'open that'), set needs_clarification=true and steps=[].\n"
            "Do not output markdown explanations outside the JSON."
        )

        return await self._run_hermes_process(full_prompt, user_message, cancel_event, trace_collector, timeout)

    async def continue_reasoning_loop(
        self,
        system_prompt: str,
        original_objective: str,
        step_history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        cancel_event: asyncio.Event,
        trace_collector: List[HermesTraceItem],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="system",
            content=f"Official Hermes runtime continuation invoked ({self.hermes_bin}) with {len(step_history)} completed steps."
        ))

        # Format completed steps history with verified evidence
        history_lines = []
        for h in step_history:
            status_str = h.get("status", "COMPLETED")
            action_str = h.get("action", "")
            args_str = json.dumps(h.get("arguments", {}))
            line = f"- Step {h.get('step_id')}: action=\"{action_str}\", arguments={args_str} -> Outcome: {status_str}"
            evidence = h.get("evidence")
            if evidence and isinstance(evidence, dict):
                if "results" in evidence:
                    results_preview = "\n    Captured Search Results:\n"
                    for r in evidence["results"][:5]:
                        results_preview += f"    {r.get('ordinal', '')}. {r.get('title', '')} ({r.get('url') or r.get('canonical_url', '')})\n"
                    line += "\n" + results_preview
            history_lines.append(line)
        history_block = "\n".join(history_lines)

        tools_desc = "\n".join(f"- {t['name']}: {t.get('description', '')}" for t in available_tools)
        full_prompt = (
            f"{system_prompt}\n\n"
            f"### ORIGINAL USER OBJECTIVE:\n\"{original_objective}\"\n\n"
            f"### EXECUTION HISTORY (COMPLETED STEPS & VERIFIED OUTCOMES):\n{history_block}\n\n"
            f"### AVAILABLE SERA CAPABILITIES:\n{tools_desc}\n\n"
            "TASK INSTRUCTIONS:\n"
            "Based on the original objective and the completed steps above, decide what to do next:\n"
            "1. If the objective is ALREADY FULLY SATISFIED by the completed steps, set \"is_complete\": true and \"steps\": [].\n"
            "2. If additional steps are required, set \"is_complete\": false and provide ONLY the NEXT concrete step(s) to execute.\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            "  \"objective\": \"Brief task summary or completion note\",\n"
            "  \"is_complete\": false,\n"
            "  \"steps\": [\n"
            "    {\n"
            "      \"step_id\": 2,\n"
            "      \"action\": \"tool_name\",\n"
            "      \"arguments\": {\"arg\": \"val\"},\n"
            "      \"target_type\": \"APPLICATION|WINDOW|BROWSER|TAB|WEBPAGE|SEARCH_RESULT|SETTING\",\n"
            "      \"target_reference\": \"reference or ordinal\",\n"
            "      \"rationale\": \"why\",\n"
            "      \"expected_evidence\": \"WINDOW_HANDLE|PROCESS_ID|VALUE_CHECK\"\n"
            "    }\n"
            "  ],\n"
            "  \"confidence\": 0.95\n"
            "}\n"
            "Do not output markdown explanations outside the JSON."
        )

        return await self._run_hermes_process(full_prompt, original_objective, cancel_event, trace_collector, timeout)

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        if "```" in text:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
        try:
            return json.loads(text)
        except Exception:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
        return None


class MockSimulationHermesClient(HermesClientBackend):
    """
    [MOCK / SIMULATION ONLY - FOR ADAPTER UNIT TESTING ONLY]

    This mock client is strictly used for testing error handling, timeouts, and network
    disconnects in unit tests without invoking real model APIs.
    IT MUST NEVER BE USED AS EVIDENCE OF REAL HERMES CAPABILITIES.
    """

    def __init__(
        self,
        canned_responses: Optional[Dict[str, Any]] = None,
        canned_continuations: Optional[Dict[str, Any]] = None,
    ):
        self.canned_responses = canned_responses or {}
        self.canned_continuations = canned_continuations or {}
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
            content=f"[MOCK/SIMULATION] Mock Hermes initialized with {len(available_tools)} tools."
        ))
        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="user",
            content=user_message
        ))

        if cancel_event.is_set():
            trace_collector.append(HermesTraceItem(
                timestamp=time.time(),
                role="thought",
                content="[MOCK/SIMULATION] Cancellation received prior to execution."
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
                        content="[MOCK/SIMULATION] Cancellation signaled during reasoning delay."
                    ))
                    return {"finish_reason": "cancelled", "objective": user_message, "steps": []}
                await asyncio.sleep(0.1)

        if self.should_fail:
            raise RuntimeError(self.failure_error)

        if user_message in self.canned_responses:
            res = self.canned_responses[user_message]
            trace_collector.append(HermesTraceItem(
                timestamp=time.time(),
                role="assistant",
                content=json.dumps(res)
            ))
            return res

        u_lower = user_message.lower().strip()
        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="thought",
            content=f"[MOCK/SIMULATION] Decomposing: {user_message}"
        ))

        if "youtube" in u_lower and ("search" in u_lower or "tutorial" in u_lower):
            return {
                "objective": "Search YouTube for Python tutorials and open results",
                "is_complete": False,
                "steps": [
                    {
                        "step_id": 1,
                        "action": "youtube_search",
                        "arguments": {"query": "Python tutorials"},
                        "target_type": "WEBPAGE",
                        "target_reference": "YouTube",
                        "rationale": "Search YouTube for relevant Python tutorials",
                        "expected_evidence": "VALUE_CHECK",
                    }
                ],
                "confidence": 0.98,
            }
        elif "chrome" in u_lower and ("open" in u_lower or "bring" in u_lower or "launch" in u_lower):
            return {
                "objective": "Bring Google Chrome window forward",
                "is_complete": True,
                "steps": [
                    {
                        "step_id": 1,
                        "action": "open_application",
                        "arguments": {"application": "chrome"},
                        "target_type": "APPLICATION",
                        "target_reference": "chrome",
                        "rationale": "Activate Chrome window",
                        "expected_evidence": "WINDOW_HANDLE",
                    }
                ],
                "confidence": 0.98,
            }
        elif "notepad" in u_lower and "close" in u_lower:
            return {
                "objective": "Close Notepad application",
                "is_complete": True,
                "steps": [
                    {
                        "step_id": 1,
                        "action": "close_application",
                        "arguments": {"application": "notepad"},
                        "target_type": "APPLICATION",
                        "target_reference": "notepad",
                        "rationale": "Terminate notepad process tree",
                        "expected_evidence": "PROCESS_ID",
                        "requires_confirmation": True,
                    }
                ],
                "confidence": 0.96,
            }
        elif "dimmer" in u_lower or "brightness" in u_lower:
            return {
                "objective": "Adjust display brightness",
                "is_complete": True,
                "steps": [
                    {
                        "step_id": 1,
                        "action": "set_brightness",
                        "arguments": {"brightness": 40},
                        "target_type": "SETTING",
                        "target_reference": "brightness",
                        "rationale": "Set display brightness to requested level",
                        "expected_evidence": "VALUE_CHECK",
                    }
                ],
                "confidence": 0.95,
            }
        elif "stop" in u_lower or "cancel" in u_lower:
            return {
                "objective": "Cancel current task",
                "steps": [],
                "finish_reason": "cancelled",
                "confidence": 1.0,
            }

        return {
            "objective": user_message,
            "steps": [],
            "needs_clarification": True,
            "clarification_prompt": "Could you please specify the desired action?",
            "confidence": 0.4,
        }

    async def continue_reasoning_loop(
        self,
        system_prompt: str,
        original_objective: str,
        step_history: List[Dict[str, Any]],
        available_tools: List[Dict[str, Any]],
        cancel_event: asyncio.Event,
        trace_collector: List[HermesTraceItem],
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        trace_collector.append(HermesTraceItem(
            timestamp=time.time(),
            role="system",
            content=f"[MOCK/SIMULATION] Mock Hermes continuation invoked with {len(step_history)} completed steps."
        ))
        if cancel_event.is_set():
            return {"finish_reason": "cancelled", "objective": original_objective, "steps": []}

        if self.should_timeout:
            await asyncio.sleep(timeout + 0.5)

        if self.should_fail:
            raise RuntimeError(self.failure_error)

        if original_objective in self.canned_continuations:
            return self.canned_continuations[original_objective]

        obj_lower = original_objective.lower().strip()
        last_step = step_history[-1] if step_history else {}
        last_action = last_step.get("action", "")

        # If last action was youtube_search, simulate step 2 opening the first result
        if "youtube" in obj_lower and ("first" in obj_lower or "result" in obj_lower):
            if last_action == "youtube_search":
                evidence = last_step.get("evidence") or {}
                results = evidence.get("results") or []
                first_url = results[0].get("url") if results else "https://www.youtube.com/watch?v=kqtD5dpn9C8"
                first_title = results[0].get("title") if results else "Python for Beginners"
                return {
                    "objective": "Open the first YouTube search result",
                    "is_complete": False,
                    "steps": [
                        {
                            "step_id": len(step_history) + 1,
                            "action": "browser_open",
                            "arguments": {"url": first_url, "title": first_title},
                            "target_type": "SEARCH_RESULT",
                            "target_reference": "1",
                            "rationale": "Open top search result video from YouTube search",
                            "expected_evidence": "VALUE_CHECK",
                        }
                    ],
                    "confidence": 0.96,
                }
            elif last_action == "browser_open":
                return {
                    "objective": "YouTube search and first result opened successfully",
                    "is_complete": True,
                    "steps": [],
                    "confidence": 1.0,
                }

        return {
            "objective": original_objective,
            "is_complete": True,
            "steps": [],
            "confidence": 0.95,
        }


# Backwards compatibility alias for existing unit tests
MockHermesClient = MockSimulationHermesClient


class SeraHermesBridge:
    """Thin, non-destructive adapter between SERA and Hermes Agent."""

    def __init__(
        self,
        backend: Optional[HermesClientBackend] = None,
        skill_registry: Optional[SkillRegistry] = None,
        memory_contract: Optional[MemoryContract] = None,
        mode: HermesMode = HermesMode.CURRENT,
    ):
        if backend is not None:
            self.backend = backend
        elif OfficialHermesClient.is_available():
            self.backend = OfficialHermesClient()
        else:
            self.backend = MockSimulationHermesClient()

        self.skills = skill_registry or SkillRegistry()
        self.memory = memory_contract or MemoryContract()
        self.mode = mode

        self._plans: Dict[str, AgentPlan] = {}
        self._traces: Dict[str, List[HermesTraceItem]] = {}
        self._cancel_events: Dict[str, asyncio.Event] = {}

    def _build_system_prompt(self, utterance: str, context: Dict[str, Any]) -> str:
        """Assembles skills, memories, and compact context for Hermes reasoning."""
        matched_skills = self.skills.match_and_load(utterance)
        skills_prompt = "\n".join(s.to_full_prompt() for s in matched_skills) if matched_skills else self.skills.list_metadata_prompts()

        mem_query = MemoryRetrievalQuery(query=utterance)
        memories = self.memory.query_memories(mem_query)
        mem_str = "\n".join(f"- [{m.scope.value}] {m.key}: {m.value}" for m in memories)

        return (
            "You are Hermes Agent reasoning harness operating under SERA Desktop Authority.\n"
            "Produce structured task plans. Never guess destructive actions from ambiguous input.\n\n"
            f"### AVAILABLE SKILLS:\n{skills_prompt}\n\n"
            f"### RELEVANT USER MEMORY & PREFERENCES:\n{mem_str}\n\n"
            f"### ACTIVE CONTEXT:\n"
            f"- Active App: {context.get('active_application')}\n"
            f"- Active Browser Tab: {context.get('active_tab')}\n"
            f"- Last Action: {context.get('last_action')}\n"
        )

    def _get_available_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": "youtube_search", "description": "Search YouTube for videos/topics and extract item-level results into session"},
            {"name": "browser_open", "description": "Navigate to a URL or open a search result in the browser"},
            {"name": "open_application", "description": "Launch or focus an application"},
            {"name": "close_application", "description": "Terminate an application (destructive)"},
            {"name": "bring_window_forward", "description": "Focus an existing window"},
            {"name": "set_brightness", "description": "Set display brightness level"},
            {"name": "set_volume", "description": "Set audio master volume"},
            {"name": "browser_switch_tab", "description": "Switch to existing browser tab"},
            {"name": "browser_close_tab", "description": "Close browser tab"},
            {"name": "cancel_task", "description": "Halt current task"},
        ]

    def _parse_steps(self, raw_steps: List[Dict[str, Any]], start_idx: int = 1) -> List[AgentStep]:
        steps: List[AgentStep] = []
        for s_idx, s_data in enumerate(raw_steps, start=start_idx):
            action = s_data.get("action", "")
            req_confirm = s_data.get("requires_confirmation", False)

            if "close" in action or "kill" in action or "delete" in action or "remove" in action:
                req_confirm = True
                risk = RiskLevel.DESTRUCTIVE
            elif "set" in action or "write" in action:
                risk = RiskLevel.BENIGN
            else:
                risk = RiskLevel.SAFE

            target_type_str = s_data.get("target_type")
            target_type = None
            if target_type_str:
                try:
                    target_type = TargetType(str(target_type_str).upper())
                except Exception:
                    pass

            target_ref = s_data.get("target_reference")
            perm = PermissionRequirement(
                action=action,
                target=str(s_data.get("arguments", {}).get("application") or s_data.get("arguments", {}).get("hwnd") or target_ref or ""),
                risk_level=risk,
                status=ApprovalStatus.PENDING_APPROVAL if req_confirm else ApprovalStatus.APPROVED,
            )

            steps.append(AgentStep(
                step_id=s_idx,
                action=action,
                arguments=s_data.get("arguments", {}),
                target_type=target_type,
                target_reference=target_ref,
                rationale=s_data.get("rationale"),
                target_entity_id=s_data.get("target_entity_id"),
                expected_evidence=s_data.get("expected_evidence", "VALUE_CHECK"),
                requires_confirmation=req_confirm,
                permission=perm,
            ))
        return steps

    async def submit_task(
        self,
        utterance: str,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        timeout: float = 30.0,
    ) -> AgentPlan:
        """Submits a user utterance to Hermes and returns a structured AgentPlan."""
        t_start = time.perf_counter()
        tid = task_id or f"hermes_{uuid.uuid4().hex[:8]}"
        cancel_ev = asyncio.Event()
        self._cancel_events[tid] = cancel_ev
        trace: List[HermesTraceItem] = []
        self._traces[tid] = trace

        ctx = context or {}
        system_prompt = self._build_system_prompt(utterance, ctx)
        available_tools = self._get_available_tools()

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
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            timeout_plan = AgentPlan(
                task_id=tid,
                objective=utterance,
                steps=[],
                confidence=0.0,
                needs_clarification=True,
                clarification_prompt=f"Hermes reasoning timed out after {timeout} seconds.",
                finish_reason="timeout",
                latency_ms=latency_ms,
            )
            self._plans[tid] = timeout_plan
            return timeout_plan
        except Exception as exc:
            logger.error(f"HERMES_BRIDGE_ERROR: Hermes inference failed for '{utterance}': {exc}")
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            error_plan = AgentPlan(
                task_id=tid,
                objective=utterance,
                steps=[],
                confidence=0.0,
                needs_clarification=True,
                clarification_prompt=f"Hermes encountered an error: {str(exc)}. Falling back to safe SERA behavior.",
                finish_reason="error",
                latency_ms=latency_ms,
            )
            self._plans[tid] = error_plan
            return error_plan

        steps = self._parse_steps(raw_res.get("steps", []))
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        plan = AgentPlan(
            task_id=tid,
            objective=raw_res.get("objective", utterance),
            assumptions=raw_res.get("assumptions", []),
            steps=steps,
            entities=raw_res.get("entities", []),
            confidence=raw_res.get("confidence", 1.0),
            is_complete=raw_res.get("is_complete", False),
            needs_clarification=raw_res.get("needs_clarification", False),
            clarification_prompt=raw_res.get("clarification_prompt"),
            raw_thought=raw_res.get("thought"),
            finish_reason=raw_res.get("finish_reason", "stop"),
            latency_ms=latency_ms,
        )

        self._plans[tid] = plan
        return plan

    async def continue_task(
        self,
        task_id: str,
        original_objective: str,
        step_history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> AgentPlan:
        """Requests Hermes to produce next step(s) based on verified step execution history."""
        t_start = time.perf_counter()
        cancel_ev = self._cancel_events.get(task_id) or asyncio.Event()
        self._cancel_events[task_id] = cancel_ev

        trace = self._traces.setdefault(task_id, [])
        ctx = context or {}
        system_prompt = self._build_system_prompt(original_objective, ctx)
        available_tools = self._get_available_tools()

        try:
            raw_res = await asyncio.wait_for(
                self.backend.continue_reasoning_loop(
                    system_prompt=system_prompt,
                    original_objective=original_objective,
                    step_history=step_history,
                    available_tools=available_tools,
                    cancel_event=cancel_ev,
                    trace_collector=trace,
                    timeout=timeout,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            timeout_plan = AgentPlan(
                task_id=task_id,
                objective=original_objective,
                steps=[],
                confidence=0.0,
                needs_clarification=True,
                clarification_prompt=f"Hermes continuation reasoning timed out after {timeout} seconds.",
                finish_reason="timeout",
                latency_ms=latency_ms,
            )
            self._plans[task_id] = timeout_plan
            return timeout_plan
        except Exception as exc:
            logger.error(f"HERMES_BRIDGE_ERROR: Hermes continuation failed for task {task_id}: {exc}")
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            error_plan = AgentPlan(
                task_id=task_id,
                objective=original_objective,
                steps=[],
                confidence=0.0,
                needs_clarification=True,
                clarification_prompt=f"Hermes continuation error: {str(exc)}.",
                finish_reason="error",
                latency_ms=latency_ms,
            )
            self._plans[task_id] = error_plan
            return error_plan

        next_start_idx = len(step_history) + 1
        steps = self._parse_steps(raw_res.get("steps", []), start_idx=next_start_idx)
        latency_ms = (time.perf_counter() - t_start) * 1000.0

        plan = AgentPlan(
            task_id=task_id,
            objective=raw_res.get("objective", original_objective),
            assumptions=raw_res.get("assumptions", []),
            steps=steps,
            entities=raw_res.get("entities", []),
            confidence=raw_res.get("confidence", 1.0),
            is_complete=raw_res.get("is_complete", False),
            needs_clarification=raw_res.get("needs_clarification", False),
            clarification_prompt=raw_res.get("clarification_prompt"),
            raw_thought=raw_res.get("thought"),
            finish_reason=raw_res.get("finish_reason", "stop"),
            latency_ms=latency_ms,
        )

        self._plans[task_id] = plan
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

    def get_cancel_event(self, task_id: str) -> Optional[asyncio.Event]:
        return self._cancel_events.get(task_id)

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
