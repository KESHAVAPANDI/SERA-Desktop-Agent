"""
SERA 2.0 — Graph Control Semantics & Decision Primitives.

Defines the structured decisions and outcomes that nodes produce.
Nodes communicate through structured decisions and GraphState rather than arbitrary strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.graph.state import GraphState


class GraphDecision(str, Enum):
    """Authoritative control decisions produced by graph nodes."""
    CONTINUE = "CONTINUE"
    DONE = "DONE"
    RETRY = "RETRY"
    REPLAN = "REPLAN"
    HANDOFF = "HANDOFF"
    FAIL = "FAIL"
    CANCEL = "CANCEL"


class ErrorCategory(str, Enum):
    """Categorized execution failures for recovery classification."""
    NONE = "NONE"
    TOOL_EXCEPTION = "TOOL_EXCEPTION"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    TIMEOUT = "TIMEOUT"
    USER_CANCELLED = "USER_CANCELLED"
    MODEL_RATE_LIMIT = "MODEL_RATE_LIMIT"
    MODEL_FAILURE = "MODEL_FAILURE"
    SECURITY_BLOCKED = "SECURITY_BLOCKED"
    INVALID_PLAN = "INVALID_PLAN"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass
class NodeResult:
    """The structured output of any graph node execution."""
    decision: GraphDecision
    state: GraphState
    next_node: Optional[str] = None
    error_category: ErrorCategory = ErrorCategory.NONE
    error_message: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def continue_to(cls, next_node: str, state: GraphState, payload: Optional[Dict[str, Any]] = None) -> NodeResult:
        """Transitions forward to a specific named node."""
        return cls(
            decision=GraphDecision.CONTINUE,
            next_node=next_node,
            state=state,
            payload=payload or {},
        )

    @classmethod
    def done(cls, state: GraphState, final_response: str = "", payload: Optional[Dict[str, Any]] = None) -> NodeResult:
        """Signals verified task completion."""
        state.final_response = final_response or state.final_response
        return cls(
            decision=GraphDecision.DONE,
            state=state,
            payload=payload or {},
        )

    @classmethod
    def retry(cls, state: GraphState, reason: str, next_node: Optional[str] = None) -> NodeResult:
        """Signals a retry of the current step."""
        return cls(
            decision=GraphDecision.RETRY,
            next_node=next_node,
            state=state,
            error_category=ErrorCategory.VERIFICATION_FAILED,
            error_message=reason,
        )

    @classmethod
    def replan(cls, state: GraphState, reason: str) -> NodeResult:
        """Signals that the remaining plan should be re-evaluated."""
        return cls(
            decision=GraphDecision.REPLAN,
            next_node="PLAN",
            state=state,
            error_category=ErrorCategory.VERIFICATION_FAILED,
            error_message=reason,
        )

    @classmethod
    def fail(cls, state: GraphState, error: str, category: ErrorCategory = ErrorCategory.INTERNAL_ERROR) -> NodeResult:
        """Signals terminal task failure."""
        state.last_error = error
        return cls(
            decision=GraphDecision.FAIL,
            state=state,
            error_category=category,
            error_message=error,
        )

    @classmethod
    def cancel(cls, state: GraphState, reason: str = "User cancelled task") -> NodeResult:
        """Signals immediate task cancellation."""
        state.is_cancelled = True
        state.cancellation_reason = reason
        return cls(
            decision=GraphDecision.CANCEL,
            state=state,
            error_category=ErrorCategory.USER_CANCELLED,
            error_message=reason,
        )
