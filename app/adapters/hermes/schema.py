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


class AgentStep(BaseModel):
    """Atomic execution step planned by Hermes."""
    step_id: int
    action: str  # Tool name (e.g., 'open_application', 'set_brightness', 'close_browser_tab')
    arguments: Dict[str, Any] = Field(default_factory=dict)
    rationale: Optional[str] = None
    target_entity_id: Optional[str] = None
    expected_evidence: str = "VALUE_CHECK"  # WINDOW_HANDLE, PROCESS_ID, VALUE_CHECK
    timeout_seconds: float = 5.0
    requires_confirmation: bool = False
    permission: Optional[PermissionRequirement] = None


class AgentPlan(BaseModel):
    """Structured handoff plan produced by Hermes reasoning."""
    task_id: str
    objective: str
    assumptions: List[str] = Field(default_factory=list)
    steps: List[AgentStep] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 1.0
    needs_clarification: bool = False
    clarification_prompt: Optional[str] = None
    raw_thought: Optional[str] = None
    finish_reason: str = "stop"  # stop, length, tool_calls, error, cancelled
    latency_ms: float = 0.0
    model: str = "hermes"


class HermesTraceItem(BaseModel):
    """Diagnostic trace entry recording Hermes internal reasoning."""
    timestamp: float
    role: str  # system, user, assistant, tool, thought
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tokens: Optional[int] = None
