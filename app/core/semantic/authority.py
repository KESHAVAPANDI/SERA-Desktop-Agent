"""
SERA 2.0 — Semantic Authority Gate.

Defines the explicit architectural authority decision boundary:
RAW TRANSCRIPT -> SEMANTIC INTERPRETER -> CanonicalIntent -> SEMANTIC AUTHORITY GATE
      |-- QWEN PRIMARY
      |-- DETERMINISTIC FAST PATH
      |-- LEGACY FALLBACK
      +-- CLARIFICATION

Enforces the 10 acceptance rules, pilot authority matrix, and context validation.
Conforms strictly to Phase 3A-E specification.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from app.core.semantic.schema import ActionFamily, CanonicalIntent

logger = logging.getLogger("sera.semantic.authority")


class SemanticAuthoritySource(str, Enum):
    QWEN = "QWEN"
    DETERMINISTIC = "DETERMINISTIC"
    LEGACY_FALLBACK = "LEGACY_FALLBACK"
    CLARIFICATION = "CLARIFICATION"


class SemanticAuthorityDecision(BaseModel):
    """Authoritative decision describing which semantic source SERA trusts."""
    source: SemanticAuthoritySource
    canonical_intent: Optional[CanonicalIntent] = None
    accepted: bool = False
    fallback_reason: Optional[str] = None
    confidence: float = 1.0
    category: str = "UNKNOWN"
    context_required: bool = False
    context_available: bool = False
    timestamp: float = Field(default_factory=time.time)
    semantic_request_id: str = Field(default_factory=lambda: f"auth_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class SemanticAuthorityGate:
    """Evaluates whether to grant primary semantic authority to Qwen, take the deterministic
    fast path, fall back to the legacy parser, or request conversational clarification.
    """

    # Category A: Application Semantics (Authoritative)
    APPLICATION_INTENTS: Set[str] = {
        "open_application",
        "close_application",
        "switch_application",
    }

    # Category B: Reference Semantics (Authoritative when context present)
    REFERENCE_INTENTS: Set[str] = {
        "open_reference",
        "open_search_result",
    }

    # Category C: Repetition / Continuation Semantics (Authoritative)
    REPETITION_INTENTS: Set[str] = {
        "repeat_last_task",
        "repeat_previous_action",
    }

    # Category D: Browser Tab Semantics (Authoritative)
    BROWSER_TAB_INTENTS: Set[str] = {
        "close_browser_tab",
        "focus_browser_tab",
        "open_new_tab",
    }

    # Category E: Hardware Setting Restoration Semantics (Authoritative)
    SETTING_INTENTS: Set[str] = {
        "restore_setting",
        "restore_previous_value",
    }

    # Categories that MUST REMAIN DETERMINISTIC (Section 5)
    DETERMINISTIC_INTENTS: Set[str] = {
        "set_brightness",
        "adjust_brightness",
        "set_volume",
        "adjust_volume",
        "mute",
        "unmute",
        "get_current_time",
        "get_system_info",
        "get_battery_status",
        "get_wifi_status",
        "lock_computer",
        "sleep_computer",
        "sera_self_close",
        "assistant_wake",
        "cancel_current_task",
    }

    # Categories that REMAIN SHADOW / EXPERIMENTAL (Section 6)
    SHADOW_ONLY_INTENTS: Set[str] = {
        "compound_workflow",
        "general_reasoning",
        "research",
        "coding",
    }

    # Generic contextual pronouns requiring verified context
    CONTEXTUAL_PRONOUNS: Set[str] = {
        "it",
        "that",
        "this",
        "that window",
        "this window",
        "the window",
        "that app",
        "the app",
        "that tab",
        "this tab",
        "the tab",
        "the previous one",
        "previous action",
        "the one at the top",
    }

    def __init__(self, pilot_enabled: bool = True):
        self.pilot_enabled = pilot_enabled

    def is_deterministic_fast_path(self, utterance: str) -> bool:
        """Determines if an utterance should bypass Qwen directly to the deterministic fast path.
        Applies to exact numeric/scalar settings (brightness, volume, mute, power, diagnostics).
        """
        raw = (utterance or "").strip().lower()
        if not raw:
            return False

        # Brightness exact percentage
        if re.search(r"(?:brightness|screen brightness).*?\d{1,3}\s*%", raw):
            return True
        if re.search(r"^(?:set|turn|change|put|make)\s+(?:the\s+)?brightness\s+(?:to\s+)?\d{1,3}\s*%?$", raw):
            return True

        # Volume exact percentage
        if re.search(r"(?:volume|sound).*?\d{1,3}\s*%", raw):
            return True
        if re.search(r"^(?:set|turn|change|put|make)\s+(?:the\s+)?volume\s+(?:to\s+)?\d{1,3}\s*%?$", raw):
            return True

        # Mute / Unmute
        if raw in ("mute", "unmute", "mute audio", "unmute audio", "mute sound", "unmute sound"):
            return True

        # System diagnostics / time / battery / wifi
        if any(raw.startswith(prefix) for prefix in ("what time is it", "get time", "current time", "battery status", "wifi status", "system info", "lock computer", "sleep computer")):
            return True

        # Native SERA Self-Close
        if re.search(r"^(?:close|exit|quit|terminate|shutdown|shut\s+down)\s+(?:yourself|sera|sarah|sara|presence|the\s+presence)$", raw) or raw in ("close yourself", "quit yourself", "exit yourself"):
            return True

        # Cancel task
        if raw in ("cancel", "cancel task", "stop", "abort"):
            return True

        return False

    def decide(
        self,
        canonical_intent: Optional[CanonicalIntent],
        transcript: str,
        context: Dict[str, Any],
        model_error: Optional[str] = None,
        latency_ms: float = 0.0,
    ) -> SemanticAuthorityDecision:
        """Evaluates CanonicalIntent against all 10 acceptance rules and returns authority decision."""
        req_id = canonical_intent.semantic_request_id if canonical_intent else f"auth_{uuid.uuid4().hex[:8]}"

        # 0. Check if pilot authority is enabled
        if not self.pilot_enabled:
            return SemanticAuthorityDecision(
                source=SemanticAuthoritySource.LEGACY_FALLBACK,
                canonical_intent=canonical_intent,
                accepted=False,
                fallback_reason="PILOT_DISABLED",
                category="SHADOW",
                semantic_request_id=req_id,
            )

        # Rule 1: Valid schema
        if canonical_intent is None or not isinstance(canonical_intent, CanonicalIntent):
            fallback_reason = "INVALID_SCHEMA"
            if model_error and "timed out" in model_error.lower():
                fallback_reason = "QWEN_TIMEOUT"
            elif model_error:
                fallback_reason = f"QWEN_ERROR: {model_error}"

            return SemanticAuthorityDecision(
                source=SemanticAuthoritySource.LEGACY_FALLBACK,
                canonical_intent=None,
                accepted=False,
                fallback_reason=fallback_reason,
                category="UNKNOWN",
                semantic_request_id=req_id,
            )

        # Section 17 & 31: Single bare action verb without a target demands clarification
        clean_tr = transcript.strip().rstrip(".!?").lower()
        if clean_tr in ("launch", "open", "start", "run"):
            return SemanticAuthorityDecision(
                source=SemanticAuthoritySource.CLARIFICATION,
                canonical_intent=canonical_intent,
                accepted=False,
                fallback_reason="MISSING_APPLICATION_TARGET",
                category="APPLICATION",
                context_required=False,
                context_available=False,
                semantic_request_id=req_id,
            )

        intent_name = (canonical_intent.intent or "").strip().lower()

        # Rule 2: Valid canonical intent name
        if not intent_name or intent_name == "unknown":
            reason = canonical_intent.ambiguity_reason or "UNKNOWN_INTENT"
            if "timed out" in reason.lower():
                src = SemanticAuthoritySource.LEGACY_FALLBACK
                fb_reason = "QWEN_TIMEOUT"
            elif canonical_intent.needs_clarification and not transcript.strip():
                src = SemanticAuthoritySource.CLARIFICATION
                fb_reason = "EMPTY_UTTERANCE"
            else:
                src = SemanticAuthoritySource.LEGACY_FALLBACK
                fb_reason = "QWEN_UNKNOWN_INTENT"

            return SemanticAuthorityDecision(
                source=src,
                canonical_intent=canonical_intent,
                accepted=False,
                fallback_reason=fb_reason,
                category="UNKNOWN",
                semantic_request_id=req_id,
            )

        # Check Deterministic Categories (Section 5)
        if intent_name in self.DETERMINISTIC_INTENTS:
            return SemanticAuthorityDecision(
                source=SemanticAuthoritySource.DETERMINISTIC,
                canonical_intent=canonical_intent,
                accepted=False,
                fallback_reason="DETERMINISTIC_CATEGORY",
                category="SYSTEM",
                semantic_request_id=req_id,
            )

        # Check Shadow-Only Categories (Section 6)
        if intent_name in self.SHADOW_ONLY_INTENTS or intent_name == "compound_workflow":
            return SemanticAuthorityDecision(
                source=SemanticAuthoritySource.LEGACY_FALLBACK,
                canonical_intent=canonical_intent,
                accepted=False,
                fallback_reason="SHADOW_ONLY_CATEGORY",
                category="COMPOUND",
                semantic_request_id=req_id,
            )

        # Rule 3: Intent belongs to enabled Qwen-authoritative category
        is_app = intent_name in self.APPLICATION_INTENTS
        is_ref = intent_name in self.REFERENCE_INTENTS
        is_rep = intent_name in self.REPETITION_INTENTS or canonical_intent.modifiers.repeat
        is_tab = intent_name in self.BROWSER_TAB_INTENTS
        is_setting = intent_name in self.SETTING_INTENTS
        is_greeting = intent_name in ("greeting", "assistant_wake")

        if not (is_app or is_ref or is_rep or is_tab or is_setting or is_greeting):
            return SemanticAuthorityDecision(
                source=SemanticAuthoritySource.LEGACY_FALLBACK,
                canonical_intent=canonical_intent,
                accepted=False,
                fallback_reason=f"UNAUTHORIZED_CATEGORY_{intent_name.upper()}",
                category="OTHER",
                semantic_request_id=req_id,
            )

        # Rule 8: Clarification state (if action requires certainty)
        if canonical_intent.needs_clarification:
            return SemanticAuthorityDecision(
                source=SemanticAuthoritySource.CLARIFICATION,
                canonical_intent=canonical_intent,
                accepted=False,
                fallback_reason="NEEDS_CLARIFICATION",
                category=canonical_intent.action_family,
                semantic_request_id=req_id,
            )

        # Rule 10: Internal Consistency & Target Check
        # Edge Case: "Launch" without a target must require clarification, not guess
        target_val = ""
        if canonical_intent.target and canonical_intent.target.value:
            target_val = str(canonical_intent.target.value).strip().lower()

        # Guard against self-close being captured as a normal OS application close
        if intent_name == "close_application" and target_val in ("yourself", "sera", "sarah", "sara", "presence", "the presence"):
            return SemanticAuthorityDecision(
                source=SemanticAuthoritySource.DETERMINISTIC,
                canonical_intent=canonical_intent,
                accepted=False,
                fallback_reason="DETERMINISTIC_CATEGORY",
                category="SYSTEM",
                semantic_request_id=req_id,
            )

        # Guard against tab closure being misclassified as OS application termination (Invariant 5)
        if intent_name == "close_application" and "tab" in clean_tr:
            canonical_intent.intent = "close_browser_tab"
            canonical_intent.action_family = "BROWSER"
            intent_name = "close_browser_tab"
            is_tab = True
            is_app = False

        ref_val = ""
        ref_type = ""
        ref_ordinal = None
        if canonical_intent.reference:
            ref_type = str(canonical_intent.reference.type or "").strip().lower()
            ref_val = str(canonical_intent.reference.value or "").strip().lower()
            ref_ordinal = canonical_intent.reference.ordinal

        if is_app and not target_val and not ref_val and not is_rep:
            # e.g., "Launch", "Open", "Start" without target or reference
            return SemanticAuthorityDecision(
                source=SemanticAuthoritySource.CLARIFICATION,
                canonical_intent=canonical_intent,
                accepted=False,
                fallback_reason="MISSING_APPLICATION_TARGET",
                category="APPLICATION",
                context_required=False,
                context_available=False,
                semantic_request_id=req_id,
            )

        # Rule 5: No hallucinated URL
        if target_val.startswith("http://") or target_val.startswith("https://") or ".com" in target_val:
            if target_val not in transcript.lower() and not any(target_val in str(v).lower() for v in context.values()):
                return SemanticAuthorityDecision(
                    source=SemanticAuthoritySource.LEGACY_FALLBACK,
                    canonical_intent=canonical_intent,
                    accepted=False,
                    fallback_reason="HALLUCINATED_URL",
                    category="BROWSER",
                    semantic_request_id=req_id,
                )

        # Rule 9: Context Availability Validation
        # Check Reference Semantics (Section 4.B & Section 10)
        if is_ref or ref_type == "search_result" or (is_app and ref_ordinal is not None):
            context_required = True
            search_results = context.get("search_results") or []
            ordinal_idx = (ref_ordinal - 1) if (ref_ordinal and ref_ordinal > 0) else 0

            if not search_results or len(search_results) <= ordinal_idx:
                logger.info(f"[SemanticAuthorityGate] Reference requested ordinal={ref_ordinal}, but verified search results missing/insufficient")
                return SemanticAuthorityDecision(
                    source=SemanticAuthoritySource.CLARIFICATION,
                    canonical_intent=canonical_intent,
                    accepted=False,
                    fallback_reason="CONTEXT_REFERENCE_MISSING",
                    category="REFERENCE",
                    context_required=True,
                    context_available=False,
                    semantic_request_id=req_id,
                )
            context_available = True
        else:
            context_required = False
            context_available = True

        # Check Contextual Entity Language ("close it", "open that", "close that window")
        is_contextual_target = target_val in self.CONTEXTUAL_PRONOUNS or ref_val in self.CONTEXTUAL_PRONOUNS or ref_type in ("active_window", "target_entity")

        if is_contextual_target:
            context_required = True
            if intent_name == "close_application":
                active_app = context.get("active_application") or context.get("last_application") or context.get("last_opened_target")
                if not active_app:
                    logger.info("[SemanticAuthorityGate] Contextual close requested, but active application context is empty")
                    return SemanticAuthorityDecision(
                        source=SemanticAuthoritySource.CLARIFICATION,
                        canonical_intent=canonical_intent,
                        accepted=False,
                        fallback_reason="ACTIVE_APPLICATION_MISSING",
                        category="APPLICATION",
                        context_required=True,
                        context_available=False,
                        semantic_request_id=req_id,
                    )
                context_available = True

            elif intent_name == "open_application":
                last_target = context.get("last_application") or context.get("last_opened_target")
                if not last_target:
                    logger.info("[SemanticAuthorityGate] 'Open that' requested, but no target entity in context")
                    return SemanticAuthorityDecision(
                        source=SemanticAuthoritySource.CLARIFICATION,
                        canonical_intent=canonical_intent,
                        accepted=False,
                        fallback_reason="TARGET_ENTITY_MISSING",
                        category="APPLICATION",
                        context_required=True,
                        context_available=False,
                        semantic_request_id=req_id,
                    )
                context_available = True

        # Check Repetition Context
        if is_rep and intent_name == "repeat_last_task":
            context_required = True
            has_prev = bool(context.get("last_command") or context.get("last_successful_command") or context.get("last_verified_action"))
            if not has_prev:
                logger.info("[SemanticAuthorityGate] Repetition requested, but no prior task in context")
                return SemanticAuthorityDecision(
                    source=SemanticAuthoritySource.CLARIFICATION,
                    canonical_intent=canonical_intent,
                    accepted=False,
                    fallback_reason="NO_PRIOR_TASK_TO_REPEAT",
                    category="CONTEXT",
                    context_required=True,
                    context_available=False,
                    semantic_request_id=req_id,
                )
            context_available = True

        # All 10 checks passed! Accept Qwen as Primary Semantic Authority
        category_label = (
            "APPLICATION" if is_app
            else ("REFERENCE" if is_ref
            else ("REPETITION" if is_rep
            else ("BROWSER" if is_tab
            else ("SETTING" if is_setting
            else "CONVERSATION"))))
        )

        return SemanticAuthorityDecision(
            source=SemanticAuthoritySource.QWEN,
            canonical_intent=canonical_intent,
            accepted=True,
            fallback_reason=None,
            confidence=canonical_intent.confidence,
            category=category_label,
            context_required=context_required,
            context_available=context_available,
            semantic_request_id=req_id,
        )
