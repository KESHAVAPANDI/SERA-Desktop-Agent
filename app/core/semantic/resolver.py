"""
SERA 2.0 — Semantic Context Resolver.

Bridges CanonicalIntent from the Semantic Authority Gate to the Stateful Graph Runtime.
Translates semantic references, ordinals, and targets into concrete runtime entities:
- "browser" -> default / detected browser
- ordinal 1 -> actual URL / title from verified search results
- "it" / "that window" -> active application from verified context
- repeat -> clones previous execution plan from last successful command
- clarification / missing target -> conversational CommandObject (0 tools, instant spoken answer)

Never invents raw URLs, PIDs, or unverified targets.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.core.command import (
    CommandCategory,
    CommandComplexity,
    CommandObject,
    PlanStepItem,
)
from app.core.semantic.authority import SemanticAuthorityDecision, SemanticAuthoritySource

logger = logging.getLogger("sera.semantic.resolver")

# Standard default browser mappings
BROWSER_SYNONYMS = {"browser", "the browser", "web browser", "internet browser"}
DEFAULT_BROWSER = "chrome"


class SemanticContextResolver:
    """Translates an accepted SemanticAuthorityDecision into an executable CommandObject."""

    @staticmethod
    def resolve(
        decision: SemanticAuthorityDecision,
        transcript: str,
        context: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> CommandObject:
        """Converts authority decision + context into CommandObject for Graph Runtime."""
        t_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"

        # 1. Handle Clarification
        if decision.source == SemanticAuthoritySource.CLARIFICATION:
            return SemanticContextResolver._resolve_clarification(decision, transcript, t_id, cmd_id)

        canonical = decision.canonical_intent
        if not canonical:
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="general_reasoning",
                category=CommandCategory.GENERAL,
                complexity=CommandComplexity.AMBIGUOUS,
                source_text=transcript,
                parameters={"query": transcript},
            )

        intent_name = (canonical.intent or "").strip().lower()

        # 2. Handle Application Semantics
        if intent_name == "open_application":
            return SemanticContextResolver._resolve_open_application(canonical, transcript, context, t_id, cmd_id)

        if intent_name == "close_application":
            return SemanticContextResolver._resolve_close_application(canonical, transcript, context, t_id, cmd_id)

        if intent_name == "switch_application":
            return SemanticContextResolver._resolve_switch_application(canonical, transcript, context, t_id, cmd_id)

        # 3. Handle Reference Semantics
        if intent_name in ("open_reference", "open_search_result"):
            return SemanticContextResolver._resolve_open_reference(canonical, transcript, context, t_id, cmd_id)

        # 4. Handle Repetition Semantics
        if intent_name in ("repeat_last_task", "repeat_previous_action") or canonical.modifiers.repeat:
            return SemanticContextResolver._resolve_repeat(canonical, transcript, context, t_id, cmd_id)

        # 5. Handle Wake / Greeting
        if intent_name in ("greeting", "assistant_wake"):
            return CommandObject(
                command_id=cmd_id,
                task_id=t_id,
                intent="assistant_wake",
                category=CommandCategory.CONVERSATION,
                complexity=CommandComplexity.SIMPLE,
                source_text=transcript,
                raw_response="Yes, I'm here. How can I help you?",
            )

        # Default fallback to general reasoning
        return CommandObject(
            command_id=cmd_id,
            task_id=t_id,
            intent="general_reasoning",
            category=CommandCategory.GENERAL,
            complexity=CommandComplexity.AMBIGUOUS,
            source_text=transcript,
            parameters={"query": transcript},
        )

    @staticmethod
    def _resolve_clarification(
        decision: SemanticAuthorityDecision,
        transcript: str,
        task_id: str,
        cmd_id: str,
    ) -> CommandObject:
        """Constructs conversational clarification CommandObject."""
        fb_reason = decision.fallback_reason or ""
        canonical = decision.canonical_intent

        if fb_reason == "MISSING_APPLICATION_TARGET" or transcript.strip().lower() in ("launch", "open", "start", "run"):
            msg = "What would you like me to launch?"
        elif fb_reason == "ACTIVE_APPLICATION_MISSING":
            msg = "Which application would you like me to close?"
        elif fb_reason == "TARGET_ENTITY_MISSING":
            msg = "What would you like me to open?"
        elif fb_reason == "CONTEXT_REFERENCE_MISSING":
            msg = "There are no active search results from a previous search to open. Please ask me to search first."
        elif fb_reason == "NO_PRIOR_TASK_TO_REPEAT":
            msg = "There is no previous task available to repeat."
        elif canonical and canonical.ambiguity_reason:
            msg = canonical.ambiguity_reason
        else:
            msg = "Could you please clarify what you would like me to do?"

        return CommandObject(
            command_id=cmd_id,
            task_id=task_id,
            intent="clarification",
            category=CommandCategory.CONVERSATION,
            complexity=CommandComplexity.SIMPLE,
            source_text=transcript,
            raw_response=msg,
        )

    @staticmethod
    def _resolve_open_application(
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
    ) -> CommandObject:
        """Resolves target and modifiers for open_application."""
        raw_target = ""
        if canonical.target and canonical.target.value:
            raw_target = str(canonical.target.value).strip()

        # Handle contextual targets ("that", "it")
        if raw_target.lower() in ("that", "it", "this", "that app", "the app"):
            raw_target = context.get("last_application") or context.get("last_opened_target") or ""

        # Normalize application target names and browser synonyms
        target_clean = raw_target.strip().lower()
        if target_clean in ("google chrome", "chrome browser", "chrome", "google-chrome"):
            app_to_open = "chrome"
        elif target_clean in BROWSER_SYNONYMS:
            app_to_open = context.get("active_browser") or DEFAULT_BROWSER
        else:
            app_to_open = raw_target

        if not app_to_open:
            return CommandObject(
                command_id=cmd_id,
                task_id=task_id,
                intent="clarification",
                category=CommandCategory.CONVERSATION,
                complexity=CommandComplexity.SIMPLE,
                source_text=transcript,
                raw_response="What would you like me to launch?",
            )

        params: Dict[str, Any] = {"application": app_to_open}
        entities: Dict[str, Any] = {"target": app_to_open}

        if canonical.modifiers.repeat:
            params["modifier"] = "repeat"
            entities["modifier"] = "repeat"

        goal_text = f"Opening {app_to_open.capitalize()}..."
        return CommandObject(
            command_id=cmd_id,
            task_id=task_id,
            intent="open_application",
            category=CommandCategory.APPLICATIONS,
            complexity=CommandComplexity.ONE_TOOL,
            source_text=transcript,
            parameters=params,
            entities=entities,
            required_tools=["open_application"],
            execution_plan=[
                PlanStepItem(
                    step_id=1,
                    goal=goal_text,
                    action="open_application",
                    arguments={"application": app_to_open},
                    timeout_seconds=8.0,
                    verification_type="window_check",
                )
            ],
        )

    @staticmethod
    def _resolve_close_application(
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
    ) -> CommandObject:
        """Resolves target for close_application."""
        raw_target = ""
        if canonical.target and canonical.target.value:
            raw_target = str(canonical.target.value).strip()

        ref_type = str(canonical.reference.type or "").lower() if canonical.reference else ""
        ref_val = str(canonical.reference.value or "").lower() if canonical.reference else ""

        # Check if target is contextual ("it", "that", active_window)
        is_contextual = (
            raw_target.lower() in ("it", "that", "this", "that window", "the window", "this window")
            or ref_type == "active_window"
            or ref_val in ("it", "that", "window")
            or not raw_target
        )

        if is_contextual:
            app_to_close = (
                context.get("active_application")
                or context.get("last_application")
                or context.get("last_opened_target")
                or ""
            )
        else:
            app_to_close = raw_target

        if not app_to_close:
            return CommandObject(
                command_id=cmd_id,
                task_id=task_id,
                intent="clarification",
                category=CommandCategory.CONVERSATION,
                complexity=CommandComplexity.SIMPLE,
                source_text=transcript,
                raw_response="Which application would you like me to close?",
            )

        # Normalize browser synonyms
        if app_to_close.lower() in BROWSER_SYNONYMS:
            app_to_close = context.get("active_browser") or DEFAULT_BROWSER

        return CommandObject(
            command_id=cmd_id,
            task_id=task_id,
            intent="close_application",
            category=CommandCategory.APPLICATIONS,
            complexity=CommandComplexity.ONE_TOOL,
            source_text=transcript,
            parameters={"application": app_to_close},
            entities={"target": app_to_close},
            required_tools=["close_application"],
            execution_plan=[
                PlanStepItem(
                    step_id=1,
                    goal=f"Close application '{app_to_close}'",
                    action="close_application",
                    arguments={"application": app_to_close},
                    timeout_seconds=5.0,
                )
            ],
        )

    @staticmethod
    def _resolve_switch_application(
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
    ) -> CommandObject:
        """Resolves target for switch_application."""
        raw_target = ""
        if canonical.target and canonical.target.value:
            raw_target = str(canonical.target.value).strip()

        if raw_target.lower() in BROWSER_SYNONYMS:
            target_app = context.get("active_browser") or DEFAULT_BROWSER
        else:
            target_app = raw_target

        return CommandObject(
            command_id=cmd_id,
            task_id=task_id,
            intent="switch_application",
            category=CommandCategory.APPLICATIONS,
            complexity=CommandComplexity.ONE_TOOL,
            source_text=transcript,
            parameters={"application": target_app},
            entities={"target": target_app},
            required_tools=["focus_window"],
            execution_plan=[
                PlanStepItem(
                    step_id=1,
                    goal=f"Switch focus to {target_app}",
                    action="focus_window",
                    arguments={"application": target_app},
                    timeout_seconds=5.0,
                )
            ],
        )

    @staticmethod
    def _resolve_open_reference(
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
    ) -> CommandObject:
        """Resolves reference ordinal to concrete search result item."""
        ordinal = 1
        if canonical.reference and canonical.reference.ordinal is not None:
            ordinal = max(1, canonical.reference.ordinal)

        ord_idx = ordinal - 1
        search_results = context.get("search_results") or []

        if not search_results or len(search_results) <= ord_idx:
            return CommandObject(
                command_id=cmd_id,
                task_id=task_id,
                intent="context_reference_missing",
                category=CommandCategory.CONTEXT,
                complexity=CommandComplexity.SIMPLE,
                source_text=transcript,
                raw_response="There are no active search results from a previous search to open. Please ask me to search first.",
            )

        target_item = search_results[ord_idx]
        target_url = target_item.get("url") or ""
        target_title = target_item.get("title") or f"Result {ordinal}"

        return CommandObject(
            command_id=cmd_id,
            task_id=task_id,
            intent="open_search_result",
            category=CommandCategory.BROWSER,
            complexity=CommandComplexity.ONE_TOOL,
            source_text=transcript,
            parameters={
                "url": target_url,
                "title": target_title,
                "index": ord_idx,
                "reference": f"result {ordinal}",
            },
            entities={
                "reference": f"result {ordinal}",
                "ordinal": ord_idx,
                "resolved_target": target_url,
            },
            required_tools=["browser_open"],
            execution_plan=[
                PlanStepItem(
                    step_id=1,
                    goal=f"Open search result #{ordinal}: {target_title}",
                    action="browser_open",
                    arguments={"url": target_url},
                    timeout_seconds=10.0,
                    verification_type="url_check",
                )
            ],
        )

    @staticmethod
    def _resolve_repeat(
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
    ) -> CommandObject:
        """Resolves repeat command by cloning previous successful plan."""
        last_cmd = context.get("last_command") or context.get("last_successful_command")
        if not last_cmd or not getattr(last_cmd, "execution_plan", None):
            return CommandObject(
                command_id=cmd_id,
                task_id=task_id,
                intent="clarification",
                category=CommandCategory.CONTEXT,
                complexity=CommandComplexity.SIMPLE,
                source_text=transcript,
                raw_response="There is no previous task available to repeat.",
            )

        cloned_plan = [
            PlanStepItem(
                step_id=idx + 1,
                goal=s.goal,
                action=s.action,
                arguments=dict(s.arguments),
                timeout_seconds=s.timeout_seconds,
                verification_type=s.verification_type,
            )
            for idx, s in enumerate(last_cmd.execution_plan)
        ]

        return CommandObject(
            command_id=cmd_id,
            task_id=task_id,
            intent=f"repeat_{last_cmd.intent}",
            category=last_cmd.category,
            complexity=last_cmd.complexity,
            source_text=transcript,
            parameters=dict(last_cmd.parameters),
            entities=dict(last_cmd.entities),
            required_tools=list(last_cmd.required_tools),
            execution_plan=cloned_plan,
        )
