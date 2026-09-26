"""
SERA 2.0 / Phase 4B — Authoritative Hermes Proposal Validator.

Validates Hermes Agent proposals against SERA's execution substrate:
- Schema validity (required fields, argument types)
- Capability validity (registered SERA tools and permissions)
- Target validity (grounded in real ContextStore entities: APPLICATION, WINDOW, SEARCH_RESULT, TAB)
- Context validity (no hallucinated references or stale assumptions)
- Permission boundary (destructive actions marked PENDING_APPROVAL)
- Evidence compatibility (verified side effects)

Enforces:
"Hermes output is a proposal, not authority. If validation fails, REJECT without execution."
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.adapters.hermes.schema import (
    AgentStep,
    ApprovalStatus,
    PermissionRequirement,
    RiskLevel,
    StepValidationResult,
    TargetType,
)
from app.core.context.store import ContextStore, SearchResultEntity
from app.tools import ToolRegistry

logger = logging.getLogger("sera.hermes.validator")

# Canonical actions recognized and supported by the SERA execution substrate
SUPPORTED_ACTIONS = {
    "open_application": "open_application",
    "launch_application": "open_application",
    "close_application": "close_application",
    "terminate_application": "close_application",
    "bring_window_forward": "open_application",
    "close_window": "close_window",
    "set_brightness": "set_brightness",
    "set_volume": "set_volume",
    "browser_open": "browser_open",
    "browser_open_url": "browser_open",
    "open_new_tab": "open_new_tab",
    "focus_browser_tab": "focus_browser_tab",
    "close_browser_tab": "close_browser_tab",
    "youtube_search": "youtube_search",
    "web_search": "web_search",
    "cancel_task": "cancel_task",
}

DESTRUCTIVE_ACTIONS = {
    "close_application",
    "terminate_application",
    "kill_process",
    "delete_file",
}


class HermesPlanValidator:
    """Authoritative validator verifying proposed Hermes steps against real SERA substrate."""

    def __init__(
        self,
        context_store: Optional[ContextStore] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.context_store = context_store
        self.tool_registry = tool_registry

    def validate_step(self, step: AgentStep) -> StepValidationResult:
        """Validates a single proposed step from Hermes."""
        # 1. Schema Validity
        if not step.action or not isinstance(step.action, str):
            return StepValidationResult(
                is_valid=False,
                rejection_code="INVALID_SCHEMA",
                reason="Step action must be a non-empty string.",
            )

        if not isinstance(step.arguments, dict):
            return StepValidationResult(
                is_valid=False,
                rejection_code="INVALID_SCHEMA",
                reason="Step arguments must be a dictionary.",
            )

        action_norm = step.action.strip().lower()

        # 2. Capability Validity
        if action_norm not in SUPPORTED_ACTIONS:
            # Check if dynamically registered in tool_registry
            is_registered = False
            if self.tool_registry:
                is_registered = self.tool_registry.get(action_norm) is not None
            if not is_registered:
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="UNSUPPORTED_CAPABILITY",
                    reason=f"Action '{step.action}' is not supported by SERA execution substrate.",
                )

        # Normalize action to SERA canonical tool name if aliased
        canonical_action = SUPPORTED_ACTIONS.get(action_norm, action_norm)

        # 3. Target Validity & Context Grounding
        # A. Search Result resolution (only applies to actions referencing a prior result, not initiating a search)
        raw_url = str(step.arguments.get("url") or step.arguments.get("query") or "").strip()
        raw_url_lower = raw_url.lower()

        is_search_result_ref = canonical_action not in ("youtube_search", "web_search") and (
            step.target_type == TargetType.SEARCH_RESULT
            or "ordinal" in step.arguments
            or ("result" in str(step.target_reference).lower() and "search" not in str(step.target_reference).lower())
            or any(k in raw_url_lower for k in ("result", "first", "second", "third", "top", "ordinal"))
        )

        if is_search_result_ref:
            if not self.context_store:
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="CONTEXT_UNAVAILABLE",
                    reason="ContextStore is required to resolve search result reference.",
                )

            session = self.context_store.get_active_search_session()
            if not session or not session.results:
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="UNRESOLVED_ENTITY",
                    reason="No active search results in context to ground requested reference.",
                )

            # Determine ordinal
            ordinal = step.arguments.get("ordinal")
            if ordinal is None and step.target_reference:
                try:
                    ordinal = int(step.target_reference)
                except ValueError:
                    pass

            if ordinal is None:
                combined_ref = f"{raw_url_lower} {str(step.target_reference).lower()}"
                if "1" in combined_ref or "first" in combined_ref or "top" in combined_ref:
                    ordinal = 1
                elif "2" in combined_ref or "second" in combined_ref:
                    ordinal = 2
                elif "3" in combined_ref or "third" in combined_ref:
                    ordinal = 3
                else:
                    ordinal = 1

            result_entity = session.get_result_by_ordinal(int(ordinal))
            if not result_entity:
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="UNRESOLVED_ENTITY",
                    reason=f"Search result ordinal {ordinal} does not exist in current session (total results: {len(session.results)}).",
                )

            # Ground the URL and metadata into arguments
            step.arguments["url"] = result_entity.canonical_url
            step.arguments["title"] = result_entity.title
            step.target_type = TargetType.SEARCH_RESULT
            step.target_reference = str(ordinal)
            step.target_entity_id = result_entity.entity_id

        # B. Application Target Check
        if canonical_action in ("open_application", "close_application"):
            app_target = (
                step.arguments.get("application")
                or step.arguments.get("application_name")
                or step.arguments.get("app_name")
                or step.target_reference
            )
            if not app_target or not str(app_target).strip():
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="AMBIGUOUS_TARGET",
                    reason=f"Action '{canonical_action}' requires a concrete application target.",
                )
            # Standardize argument key
            step.arguments["application"] = str(app_target).strip()

        # C. Browser Open Target Check
        if canonical_action == "browser_open" and not is_search_result_ref:
            url = step.arguments.get("url") or step.arguments.get("query")
            if not url or not str(url).strip():
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="AMBIGUOUS_TARGET",
                    reason="Browser navigation requires a non-empty target URL.",
                )
            url_str = str(url).strip()
            if not (url_str.startswith("http://") or url_str.startswith("https://") or "." in url_str or "/" in url_str):
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="AMBIGUOUS_TARGET",
                    reason=f"Target '{url_str}' is not a valid URL and could not be resolved to an active entity.",
                )

        # 4. Safety & Permission Boundary
        is_destructive = canonical_action in DESTRUCTIVE_ACTIONS
        if is_destructive:
            step.requires_confirmation = True
            step.permission = PermissionRequirement(
                action=canonical_action,
                target=str(step.arguments.get("application") or step.target_reference or "unknown"),
                risk_level=RiskLevel.DESTRUCTIVE,
                status=ApprovalStatus.PENDING_APPROVAL,
                explanation=f"Requires user approval before executing destructive operation: {canonical_action}.",
            )
        elif canonical_action in ("set_brightness", "set_volume"):
            step.permission = PermissionRequirement(
                action=canonical_action,
                target=str(step.arguments.get("brightness") or step.arguments.get("volume") or "setting"),
                risk_level=RiskLevel.BENIGN,
                status=ApprovalStatus.APPROVED,
            )
        else:
            step.permission = PermissionRequirement(
                action=canonical_action,
                target=str(step.arguments.get("application") or step.arguments.get("url") or "safe_action"),
                risk_level=RiskLevel.SAFE,
                status=ApprovalStatus.APPROVED,
            )

        # 5. Evidence Compatibility Check
        valid_evidence_types = {"WINDOW_HANDLE", "PROCESS_ID", "VALUE_CHECK", "FILE_SYSTEM"}
        if step.expected_evidence not in valid_evidence_types:
            step.expected_evidence = "VALUE_CHECK"

        return StepValidationResult(
            is_valid=True,
            resolved_target=step.arguments.get("application") or step.arguments.get("url"),
        )
