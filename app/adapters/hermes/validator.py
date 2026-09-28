"""
SERA 2.0 / Phase 4B.1 — Authoritative Hermes Proposal Validator.

Validates Hermes Agent proposals against SERA's execution substrate:
- Schema validity (required fields, argument types)
- Capability validity (registered canonical SERA tools and permissions)
- Target validity (grounded in real ContextStore entities: APPLICATION, WINDOW, SEARCH_RESULT, TAB)
- Context validity (detects ambiguous pronouns / unresolvable referents -> MISSING_CONTEXT_REFERENT)
- Permission boundary (destructive actions marked PENDING_APPROVAL)
- Evidence compatibility (verified side effects)

Enforces:
"Hermes output is a proposal, not authority. If validation fails, REJECT without execution."
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from app.adapters.hermes.capabilities import (
    CANONICAL_ACTION_MAP,
    CAPABILITY_BY_NAME,
    resolve_canonical_action,
)
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
SUPPORTED_ACTIONS = CANONICAL_ACTION_MAP

DESTRUCTIVE_ACTIONS = {
    cap.name for cap in CAPABILITY_BY_NAME.values() if cap.is_destructive
} | {
    "close_application",
    "terminate_application",
    "kill_process",
    "delete_file",
    "close_window",
}

AMBIGUOUS_PRONOUNS: Set[str] = {
    "that",
    "it",
    "this",
    "the first one",
    "the previous one",
    "that window",
    "that tab",
    "first result",
    "the tab",
    "the window",
    "the app",
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

        action_raw = step.action.strip()
        action_norm = action_raw.lower()

        # 2. Capability Validity & Canonical Normalization
        canonical_action = resolve_canonical_action(action_norm)
        if not canonical_action:
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
            canonical_action = action_norm

        # Normalize step action to SERA canonical tool name
        step.action = canonical_action

        # 3. Target Validity & Context Grounding
        raw_url = str(step.arguments.get("url") or step.arguments.get("query") or "").strip()
        raw_url_lower = raw_url.lower()

        # A. Search Result resolution (references to prior search session items)
        is_search_result_ref = canonical_action not in ("youtube_search", "web_search") and (
            step.target_type == TargetType.SEARCH_RESULT
            or "ordinal" in step.arguments
            or ("result" in str(step.target_reference).lower() and "search" not in str(step.target_reference).lower())
            or any(k in raw_url_lower for k in ("result", "first", "second", "third", "top", "ordinal"))
            or (raw_url_lower in AMBIGUOUS_PRONOUNS and not (raw_url_lower.startswith("http://") or raw_url_lower.startswith("https://")))
        )

        if is_search_result_ref:
            if not self.context_store:
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="UNRESOLVED_ENTITY",
                    reason="ContextStore is required to resolve search result reference.",
                )

            session = self.context_store.get_active_search_session()
            if not session or not session.results:
                rej_code = "MISSING_CONTEXT_REFERENT" if raw_url_lower in AMBIGUOUS_PRONOUNS else "UNRESOLVED_ENTITY"
                return StepValidationResult(
                    is_valid=False,
                    rejection_code=rej_code,
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
                    rejection_code="MISSING_CONTEXT_REFERENT",
                    reason=f"Search result ordinal {ordinal} does not exist in current session (total results: {len(session.results)}).",
                )

            # Ground the URL and metadata into arguments
            step.arguments["url"] = result_entity.canonical_url
            step.arguments["title"] = result_entity.title
            step.target_type = TargetType.SEARCH_RESULT
            step.target_reference = str(ordinal)
            step.target_entity_id = result_entity.entity_id

        # B. Application Target Check
        elif canonical_action in ("open_application", "close_application"):
            app_target = (
                step.arguments.get("application")
                or step.arguments.get("application_name")
                or step.arguments.get("app_name")
                or step.target_reference
            )
            app_target_str = str(app_target).strip() if app_target else ""
            if not app_target_str:
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="AMBIGUOUS_TARGET",
                    reason=f"Action '{canonical_action}' requires a concrete application target.",
                )

            # Check for ambiguous pronoun without grounded target
            if app_target_str.lower() in AMBIGUOUS_PRONOUNS:
                active_app = None
                if self.context_store:
                    active_app = self.context_store.get_active_application()
                if not active_app:
                    return StepValidationResult(
                        is_valid=False,
                        rejection_code="MISSING_CONTEXT_REFERENT",
                        reason=f"Application referent '{app_target_str}' is ambiguous and no active application is present in context.",
                    )
                app_target_str = active_app

            # Standardize argument key and target type
            step.arguments["application"] = app_target_str
            step.target_type = TargetType.APPLICATION

        # C. Browser Open Target Check
        elif canonical_action == "browser_open" and not is_search_result_ref:
            url = step.arguments.get("url") or step.arguments.get("query")
            if not url or not str(url).strip():
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="AMBIGUOUS_TARGET",
                    reason="Browser navigation requires a non-empty target URL.",
                )
            url_str = str(url).strip()
            if url_str.lower() in AMBIGUOUS_PRONOUNS:
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="MISSING_CONTEXT_REFERENT",
                    reason=f"Referent '{url_str}' is ambiguous and no active target is available.",
                )
            if not (url_str.startswith("http://") or url_str.startswith("https://") or "." in url_str or "/" in url_str):
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="AMBIGUOUS_TARGET",
                    reason=f"Target '{url_str}' is not a valid URL and could not be resolved to an active entity.",
                )
            step.target_type = TargetType.WEBPAGE

        # D. Browser Tab Operations (focus_browser_tab / close_browser_tab)
        elif canonical_action in ("focus_browser_tab", "close_browser_tab"):
            tab_target = (
                step.arguments.get("tab_identifier")
                or step.arguments.get("tab")
                or step.arguments.get("title")
                or step.arguments.get("target")
                or step.target_reference
            )
            tab_str = str(tab_target).strip() if tab_target else ""
            step.target_type = TargetType.TAB

            if tab_str.lower() in AMBIGUOUS_PRONOUNS or not tab_str:
                active_tab = self.context_store.get_active_browser_tab() if self.context_store else None
                if active_tab:
                    tab_str = active_tab.title or active_tab.entity_id
                elif canonical_action == "close_browser_tab":
                    # Closing active tab by default
                    tab_str = ""
                else:
                    return StepValidationResult(
                        is_valid=False,
                        rejection_code="MISSING_CONTEXT_REFERENT",
                        reason=f"Browser tab referent '{tab_str or 'tab'}' could not be resolved from active context.",
                    )
            step.arguments["tab_identifier"] = tab_str

        # E. Desktop Window Operations (focus_desktop_window / close_window)
        elif canonical_action in ("focus_desktop_window", "close_window"):
            win_target = (
                step.arguments.get("window_name")
                or step.arguments.get("application")
                or step.arguments.get("app_name")
                or step.arguments.get("target")
                or step.target_reference
            )
            win_str = str(win_target).strip() if win_target else ""
            step.target_type = TargetType.WINDOW

            if win_str.lower() in AMBIGUOUS_PRONOUNS or not win_str:
                return StepValidationResult(
                    is_valid=False,
                    rejection_code="MISSING_CONTEXT_REFERENT",
                    reason=f"Window referent '{win_str or 'that'}' is ambiguous and cannot be resolved.",
                )
            step.arguments["window_name"] = win_str

        # 4. Safety & Permission Boundary
        is_destructive = canonical_action in DESTRUCTIVE_ACTIONS
        if is_destructive:
            step.requires_confirmation = True
            step.permission = PermissionRequirement(
                action=canonical_action,
                target=str(
                    step.arguments.get("application")
                    or step.arguments.get("window_name")
                    or step.arguments.get("tab_identifier")
                    or step.target_reference
                    or "unknown"
                ),
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
                target=str(
                    step.arguments.get("application")
                    or step.arguments.get("url")
                    or step.arguments.get("tab_identifier")
                    or step.arguments.get("window_name")
                    or "safe_action"
                ),
                risk_level=RiskLevel.SAFE,
                status=ApprovalStatus.APPROVED,
            )

        # 5. Evidence Compatibility Check
        cap_spec = CAPABILITY_BY_NAME.get(canonical_action)
        if cap_spec:
            step.expected_evidence = cap_spec.expected_evidence
        else:
            valid_evidence_types = {"WINDOW_HANDLE", "PROCESS_ID", "VALUE_CHECK", "FILE_SYSTEM", "SEARCH_RESULTS", "BROWSER_TAB", "TAB_ACTIVE", "TAB_CLOSED"}
            if step.expected_evidence not in valid_evidence_types:
                step.expected_evidence = "VALUE_CHECK"

        return StepValidationResult(
            is_valid=True,
            resolved_target=step.arguments.get("application") or step.arguments.get("url") or step.arguments.get("tab_identifier") or step.arguments.get("window_name"),
        )
