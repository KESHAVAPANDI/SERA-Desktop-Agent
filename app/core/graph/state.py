"""
SERA 2.0 — Canonical Graph State Model.

Establishes the authoritative state container for the stateful graph runtime.
No state is scattered across globals or hidden procedural loop variables.
Supports complete serialization and snapshotting for future checkpointing and recovery.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GraphExecutionStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BROKEN = "BROKEN"


@dataclass
class GraphPlanStep:
    """Discrete executable plan step within GraphState."""
    step_id: int
    goal: str
    action: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 10.0
    verification_type: str = "state_check"
    completed: bool = False
    failed: bool = False
    error: Optional[str] = None
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "goal": self.goal,
            "action": self.action,
            "arguments": dict(self.arguments),
            "timeout_seconds": self.timeout_seconds,
            "verification_type": self.verification_type,
            "completed": self.completed,
            "failed": self.failed,
            "error": self.error,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GraphPlanStep:
        return cls(
            step_id=data.get("step_id", 1),
            goal=data.get("goal", ""),
            action=data.get("action", ""),
            arguments=data.get("arguments", {}),
            timeout_seconds=data.get("timeout_seconds", 10.0),
            verification_type=data.get("verification_type", "state_check"),
            completed=data.get("completed", False),
            failed=data.get("failed", False),
            error=data.get("error"),
            latency_ms=data.get("latency_ms", 0.0),
        )


@dataclass
class GraphObservation:
    """Represents an empirical observation of the environment following an action."""
    action_name: str
    raw_output: Any
    observed_state: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_name": self.action_name,
            "raw_output": self.raw_output if isinstance(self.raw_output, (dict, list, str, int, float, bool, type(None))) else str(self.raw_output),
            "observed_state": dict(self.observed_state),
            "summary": self.summary,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GraphObservation:
        return cls(
            action_name=data.get("action_name", ""),
            raw_output=data.get("raw_output"),
            observed_state=data.get("observed_state", {}),
            summary=data.get("summary", ""),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class GraphVerification:
    """Represents the verification gate evaluating an observation against expected outcomes."""
    verified: bool
    evidence_type: str = "GENERIC"
    source: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    failure_reason: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified": self.verified,
            "evidence_type": self.evidence_type,
            "source": self.source,
            "details": dict(self.details),
            "failure_reason": self.failure_reason,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GraphVerification:
        return cls(
            verified=data.get("verified", False),
            evidence_type=data.get("evidence_type", "GENERIC"),
            source=data.get("source", ""),
            details=data.get("details", {}),
            failure_reason=data.get("failure_reason"),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class GraphState:
    """Authoritative, strongly-typed state for the SERA Stateful Graph Runtime."""

    # 1. IDENTITY
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:10]}")
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    turn_id: str = field(default_factory=lambda: f"turn_{uuid.uuid4().hex[:8]}")
    parent_execution_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # 2. INPUT
    raw_user_input: str = ""
    normalized_user_input: str = ""
    input_source: str = "TEXT"  # "TEXT", "VOICE", "HOTKEY", "WAKE_WORD"
    speech_metadata: Dict[str, Any] = field(default_factory=dict)

    # 3. CONTEXT
    conversation_context: List[Dict[str, Any]] = field(default_factory=list)
    current_objective: str = ""
    active_application: Optional[str] = None
    active_window: Optional[str] = None
    active_browser: Optional[str] = None
    active_browser_tab: Optional[str] = None
    current_url: Optional[str] = None
    pending_reference: Optional[str] = None
    last_verified_action: Optional[str] = None
    context_state: Dict[str, Any] = field(default_factory=dict)

    # 4. ROUTING
    selected_route: str = "FAST_PATH"  # "FAST_PATH", "MULTI_STEP", "REASONING", "CONVERSATIONAL"
    selected_specialist: Optional[str] = None  # "desktop", "browser", "vision", etc.
    selected_model_role: Optional[str] = None  # "fast", "reasoning", etc.
    selected_provider: Optional[str] = None
    selected_model: Optional[str] = None
    routing_reason: Optional[str] = None

    # 5. PLAN
    plan_id: Optional[str] = None
    steps: List[GraphPlanStep] = field(default_factory=list)
    current_step_index: int = 0
    completed_steps: List[int] = field(default_factory=list)
    failed_steps: List[int] = field(default_factory=list)
    plan_retry_count: int = 0
    replan_count: int = 0
    max_replans: int = 2

    # 6. EXECUTION
    current_node: str = "PERCEIVE"
    current_phase: str = "INITIALIZING"
    current_action: Optional[str] = None
    action_arguments: Dict[str, Any] = field(default_factory=dict)
    action_result: Any = None
    observation: Optional[GraphObservation] = None
    verification: Optional[GraphVerification] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)

    # 7. RECOVERY
    last_error: Optional[str] = None
    is_recoverable: bool = True
    retry_count: int = 0
    max_retries_per_step: int = 2
    handoff_status: Optional[str] = None
    is_cancelled: bool = False
    cancellation_reason: Optional[str] = None

    # 8. OUTCOME
    status: GraphExecutionStatus = GraphExecutionStatus.IDLE
    final_response: str = ""
    completion_reason: Optional[str] = None

    # 9. PRESENCE
    sera_status: str = "IDLE"
    attention_target: Optional[str] = None
    task_progress: float = 0.0  # 0.0 to 1.0

    # 10. TELEMETRY
    node_timings: Dict[str, float] = field(default_factory=dict)
    model_timings: Dict[str, float] = field(default_factory=dict)
    tool_timings: Dict[str, float] = field(default_factory=dict)
    verification_timings: Dict[str, float] = field(default_factory=dict)
    total_duration_ms: float = 0.0

    @property
    def current_step(self) -> Optional[GraphPlanStep]:
        """Returns the current active plan step if within bounds."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    @property
    def remaining_steps(self) -> List[GraphPlanStep]:
        """Returns the list of remaining unexecuted steps."""
        if self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index:]
        return []

    def advance_step(self) -> bool:
        """Advances current_step_index to the next step. Returns True if more steps remain."""
        if self.current_step:
            self.current_step.completed = True
            if self.current_step.step_id not in self.completed_steps:
                self.completed_steps.append(self.current_step.step_id)
        self.current_step_index += 1
        self.retry_count = 0  # reset per-step retry count
        self.updated_at = time.time()
        return self.current_step_index < len(self.steps)

    def mark_updated(self) -> None:
        """Updates the updated_at timestamp."""
        self.updated_at = time.time()

    def record_node_timing(self, node_name: str, duration_ms: float) -> None:
        """Records latency for a specific node execution."""
        self.node_timings[node_name] = round(duration_ms, 2)
        self.mark_updated()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes GraphState to a clean, JSON-compatible dictionary."""
        return {
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "turn_id": self.turn_id,
            "parent_execution_id": self.parent_execution_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "raw_user_input": self.raw_user_input,
            "normalized_user_input": self.normalized_user_input,
            "input_source": self.input_source,
            "speech_metadata": dict(self.speech_metadata),
            "conversation_context": list(self.conversation_context),
            "current_objective": self.current_objective,
            "active_application": self.active_application,
            "active_window": self.active_window,
            "active_browser": self.active_browser,
            "active_browser_tab": self.active_browser_tab,
            "current_url": self.current_url,
            "pending_reference": self.pending_reference,
            "last_verified_action": self.last_verified_action,
            "context_state": dict(self.context_state),
            "selected_route": self.selected_route,
            "selected_specialist": self.selected_specialist,
            "selected_model_role": self.selected_model_role,
            "selected_provider": self.selected_provider,
            "selected_model": self.selected_model,
            "routing_reason": self.routing_reason,
            "plan_id": self.plan_id,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_index": self.current_step_index,
            "completed_steps": list(self.completed_steps),
            "failed_steps": list(self.failed_steps),
            "plan_retry_count": self.plan_retry_count,
            "replan_count": self.replan_count,
            "max_replans": self.max_replans,
            "current_node": self.current_node,
            "current_phase": self.current_phase,
            "current_action": self.current_action,
            "action_arguments": dict(self.action_arguments),
            "action_result": self.action_result if isinstance(self.action_result, (dict, list, str, int, float, bool, type(None))) else str(self.action_result),
            "observation": self.observation.to_dict() if self.observation else None,
            "verification": self.verification.to_dict() if self.verification else None,
            "evidence": dict(self.evidence),
            "artifacts": list(self.artifacts),
            "last_error": self.last_error,
            "is_recoverable": self.is_recoverable,
            "retry_count": self.retry_count,
            "max_retries_per_step": self.max_retries_per_step,
            "handoff_status": self.handoff_status,
            "is_cancelled": self.is_cancelled,
            "cancellation_reason": self.cancellation_reason,
            "status": self.status.value,
            "final_response": self.final_response,
            "completion_reason": self.completion_reason,
            "sera_status": self.sera_status,
            "attention_target": self.attention_target,
            "task_progress": self.task_progress,
            "node_timings": dict(self.node_timings),
            "model_timings": dict(self.model_timings),
            "tool_timings": dict(self.tool_timings),
            "verification_timings": dict(self.verification_timings),
            "total_duration_ms": self.total_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GraphState:
        """Restores a GraphState instance from a serialized dictionary."""
        status_val = data.get("status", "IDLE")
        status = GraphExecutionStatus(status_val) if status_val in GraphExecutionStatus._value2member_map_ else GraphExecutionStatus.IDLE

        obs_data = data.get("observation")
        observation = GraphObservation.from_dict(obs_data) if obs_data else None

        verif_data = data.get("verification")
        verification = GraphVerification.from_dict(verif_data) if verif_data else None

        steps_data = data.get("steps", [])
        steps = [GraphPlanStep.from_dict(s) for s in steps_data]

        return cls(
            execution_id=data.get("execution_id", f"exec_{uuid.uuid4().hex[:10]}"),
            task_id=data.get("task_id", f"task_{uuid.uuid4().hex[:8]}"),
            turn_id=data.get("turn_id", f"turn_{uuid.uuid4().hex[:8]}"),
            parent_execution_id=data.get("parent_execution_id"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            raw_user_input=data.get("raw_user_input", ""),
            normalized_user_input=data.get("normalized_user_input", ""),
            input_source=data.get("input_source", "TEXT"),
            speech_metadata=data.get("speech_metadata", {}),
            conversation_context=data.get("conversation_context", []),
            current_objective=data.get("current_objective", ""),
            active_application=data.get("active_application"),
            active_window=data.get("active_window"),
            active_browser=data.get("active_browser"),
            active_browser_tab=data.get("active_browser_tab"),
            current_url=data.get("current_url"),
            pending_reference=data.get("pending_reference"),
            last_verified_action=data.get("last_verified_action"),
            context_state=data.get("context_state", {}),
            selected_route=data.get("selected_route", "FAST_PATH"),
            selected_specialist=data.get("selected_specialist"),
            selected_model_role=data.get("selected_model_role"),
            selected_provider=data.get("selected_provider"),
            selected_model=data.get("selected_model"),
            routing_reason=data.get("routing_reason"),
            plan_id=data.get("plan_id"),
            steps=steps,
            current_step_index=data.get("current_step_index", 0),
            completed_steps=data.get("completed_steps", []),
            failed_steps=data.get("failed_steps", []),
            plan_retry_count=data.get("plan_retry_count", 0),
            replan_count=data.get("replan_count", 0),
            max_replans=data.get("max_replans", 2),
            current_node=data.get("current_node", "PERCEIVE"),
            current_phase=data.get("current_phase", "INITIALIZING"),
            current_action=data.get("current_action"),
            action_arguments=data.get("action_arguments", {}),
            action_result=data.get("action_result"),
            observation=observation,
            verification=verification,
            evidence=data.get("evidence", {}),
            artifacts=data.get("artifacts", []),
            last_error=data.get("last_error"),
            is_recoverable=data.get("is_recoverable", True),
            retry_count=data.get("retry_count", 0),
            max_retries_per_step=data.get("max_retries_per_step", 2),
            handoff_status=data.get("handoff_status"),
            is_cancelled=data.get("is_cancelled", False),
            cancellation_reason=data.get("cancellation_reason"),
            status=status,
            final_response=data.get("final_response", ""),
            completion_reason=data.get("completion_reason"),
            sera_status=data.get("sera_status", "IDLE"),
            attention_target=data.get("attention_target"),
            task_progress=data.get("task_progress", 0.0),
            node_timings=data.get("node_timings", {}),
            model_timings=data.get("model_timings", {}),
            tool_timings=data.get("tool_timings", {}),
            verification_timings=data.get("verification_timings", {}),
            total_duration_ms=data.get("total_duration_ms", 0.0),
        )
