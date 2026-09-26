"""
SERA 2.0 / Phase 4A — Hermes Agent Harness Contracts & Schemas.

Defines the execution handoff contract, structured plan representation,
and permission boundary separating Hermes reasoning from SERA execution.
Conforms strictly to Phase 4A architectural specifications.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class HermesMode(str, Enum):
    """Routing modes for Hermes Agent Harness evaluation."""
    CURRENT = "current"                  # Current SERA semantic authority gate & Qwen
    HERMES_SHADOW = "hermes_shadow"      # Run current path for execution; run Hermes in shadow mode for telemetry
    HERMES_EXPERIMENTAL = "hermes_exp"   # Hermes plans; SERA verifies permissions, executes, and verifies


class RiskLevel(str, Enum):
    """Action risk classification for the permission boundary."""
    SAFE = "safe"              # Read-only observation, window focus
    BENIGN = "benign"          # Settings adjustment, launching known applications
    DESTRUCTIVE = "destructive"# Closing windows/apps, killing processes, deleting files
    CRITICAL = "critical"      # System power (shutdown/reboot), file wiping


class ApprovalStatus(str, Enum):
    """Permission status for external action approval."""
    APPROVED = "approved"
    PENDING_APPROVAL = "pending_approval"
    DENIED = "denied"
    EXPIRED = "expired"


class PermissionRequirement(BaseModel):
    """External permission boundary request.
    
    Attaches to a stable request_id so UI (Command Center / Voice)
    can review and approve without guessing intent from conversational text.
    """
    request_id: str = Field(default_factory=lambda: f"perm_{uuid.uuid4().hex[:8]}")
    action: str
    target: str
    risk_level: RiskLevel = RiskLevel.SAFE
    status: ApprovalStatus = ApprovalStatus.APPROVED
    explanation: Optional[str] = None
    created_at: float = Field(default_factory=lambda: 0.0)


class TargetType(str, Enum):
    """Canonical SERA target entity classes."""
    APPLICATION = "APPLICATION"
    WINDOW = "WINDOW"
    BROWSER = "BROWSER"
    TAB = "TAB"
    WEBPAGE = "WEBPAGE"
    SEARCH_RESULT = "SEARCH_RESULT"
    SETTING = "SETTING"


class ExecutionHandoffStatus(str, Enum):
    """Terminal and progression states of the execution handoff."""
    INITIALIZED = "INITIALIZED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED_APPROVAL = "PAUSED_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ApprovalDecision(str, Enum):
    """User or channel approval decision on a pending permission request."""
    APPROVE = "approve"
    DENY = "deny"
    CANCEL = "cancel"
    EXPIRE = "expire"


class StepValidationResult(BaseModel):
    """Result of SERA's authoritative validation of a proposed Hermes step."""
    is_valid: bool
    rejection_code: Optional[str] = None  # e.g., INVALID_SCHEMA, UNSUPPORTED_CAPABILITY, UNRESOLVED_ENTITY, AMBIGUOUS_TARGET
    reason: Optional[str] = None
    resolved_target: Optional[Any] = None


class AgentStep(BaseModel):
    """Atomic execution step planned by Hermes."""
    step_id: int
    action: str  # Tool name (e.g., 'open_application', 'youtube_search', 'browser_open')
    target_type: Optional[TargetType] = None
    target_reference: Optional[str] = None  # E.g. 'chrome', '1', 'https://...'
    arguments: Dict[str, Any] = Field(default_factory=dict)
    rationale: Optional[str] = None
    target_entity_id: Optional[str] = None
    expected_evidence: str = "VALUE_CHECK"  # WINDOW_HANDLE, PROCESS_ID, VALUE_CHECK
    timeout_seconds: float = 8.0
    requires_confirmation: bool = False
    requires_clarification: bool = False
    permission: Optional[PermissionRequirement] = None
    status: str = "PENDING"  # PENDING, VALIDATED, EXECUTING, VERIFIED, FAILED, SKIPPED
    verified_evidence: Optional[Dict[str, Any]] = None


class AgentPlan(BaseModel):
    """Structured handoff plan produced by Hermes reasoning."""
    task_id: str
    objective: str
    assumptions: List[str] = Field(default_factory=list)
    steps: List[AgentStep] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 1.0
    is_complete: bool = False
    needs_clarification: bool = False
    clarification_prompt: Optional[str] = None
    raw_thought: Optional[str] = None
    finish_reason: str = "stop"  # stop, length, tool_calls, error, cancelled
    latency_ms: float = 0.0
    model: str = "hermes"


class HermesExecutionTelemetry(BaseModel):
    """Comprehensive telemetry for live Hermes execution runs (Phase 4B Section 18)."""
    task_id: str
    session_id: str = "none"
    hermes_version: str = "v0.21.5"
    model: str = "meta-llama/llama-3.3-70b-instruct"
    provider: str = "openrouter"
    turns: int = 1
    reasoning_latency_ms: float = 0.0
    execution_latency_ms: float = 0.0
    verification_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    steps_planned: int = 0
    steps_executed: int = 0
    approval_interruptions: int = 0
    verification_results: List[Dict[str, Any]] = Field(default_factory=list)
    replans: int = 0
    terminal_state: ExecutionHandoffStatus = ExecutionHandoffStatus.COMPLETED


class HermesTraceItem(BaseModel):
    """Diagnostic trace entry recording Hermes internal reasoning."""
    timestamp: float
    role: str  # system, user, assistant, tool, thought
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tokens: Optional[int] = None
