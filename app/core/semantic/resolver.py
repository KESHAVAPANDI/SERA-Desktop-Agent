"""
SERA 2.0 — Semantic Context Resolver.

Bridges CanonicalIntent from the Semantic Authority Gate to the Stateful Graph Runtime.
Translates semantic references, ordinals, and targets into concrete runtime entities:
- "browser" -> default / detected browser
- ordinal N -> actual URL / title from verified SearchSession
- contextual pronoun ("that", "it") -> active referent entity (NEVER defaults to result #1!)
- "close this tab" -> close_browser_tab (leaves Chrome process alive!)
- "put brightness back" -> restore_setting from structured hardware state history
- repeat -> replays verified ReplayableSemanticAction object

Conforms strictly to Phase 3A-F Sections 3, 5, 7, 8, 9, 10, 11, 12, 13, 18.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from app.core.command import (
    CommandCategory,
    CommandComplexity,
    CommandObject,
    PlanStepItem,
)
from app.core.context.entities import EntityType, SearchResultEntity
from app.core.context.store import ContextStore
from app.core.semantic.authority import SemanticAuthorityDecision, SemanticAuthoritySource

logger = logging.getLogger("sera.semantic.resolver")

# Standard default browser mappings
BROWSER_SYNONYMS = {"browser", "the browser", "web browser", "internet browser"}
DEFAULT_BROWSER = "chrome"


class SemanticContextResolver:
    """Translates an accepted SemanticAuthorityDecision into an executable CommandObject."""

    def __init__(self, context_store: Optional[ContextStore] = None):
        self.context_store = context_store

    @classmethod
    def resolve(
        cls,
        decision: SemanticAuthorityDecision,
        transcript: str,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        context_store: Optional[ContextStore] = None,
    ) -> CommandObject:
        """Converts authority decision + context into CommandObject for Graph Runtime."""
        ctx = context or {}
        store = context_store or ctx.get("context_store")
        inst = cls(context_store=store)
        return inst._resolve_internal(decision, transcript, ctx, task_id=task_id, store=store)

    def _resolve_internal(
        self,
        decision: SemanticAuthorityDecision,
        transcript: str,
        context: Dict[str, Any],
        task_id: Optional[str] = None,
        store: Optional[ContextStore] = None,
    ) -> CommandObject:
        t_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"

        # 1. Handle Clarification
        if decision.source == SemanticAuthoritySource.CLARIFICATION:
            return self._resolve_clarification(decision, transcript, t_id, cmd_id)

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
            return self._resolve_open_application(canonical, transcript, context, t_id, cmd_id, store)

        if intent_name == "close_application":
            return self._resolve_close_application(canonical, transcript, context, t_id, cmd_id, store)

        if intent_name == "switch_application":
            return self._resolve_switch_application(canonical, transcript, context, t_id, cmd_id, store)

        # 3. Handle Browser Tab Semantics (Sections 10 & 12)
        if intent_name in ("close_browser_tab", "close_tab"):
            return self._resolve_close_browser_tab(canonical, transcript, context, t_id, cmd_id, store)

        if intent_name in ("focus_browser_tab", "focus_tab"):
            return self._resolve_focus_browser_tab(canonical, transcript, context, t_id, cmd_id, store)

        if intent_name == "open_new_tab":
            return self._resolve_open_new_tab(canonical, transcript, context, t_id, cmd_id, store)

        # 4. Handle Hardware Setting Restoration (Section 18)
        if intent_name in ("restore_setting", "restore_previous_value"):
            return self._resolve_restore_setting(canonical, transcript, context, t_id, cmd_id, store)

        # 5. Handle Reference Semantics (Sections 7 & 8)
        if intent_name in ("open_reference", "open_search_result"):
            return self._resolve_open_reference(canonical, transcript, context, t_id, cmd_id, store)

        # 6. Handle Repetition Semantics (Section 9)
        if intent_name in ("repeat_last_task", "repeat_previous_action") or canonical.modifiers.repeat:
            return self._resolve_repeat(canonical, transcript, context, t_id, cmd_id, store)

        # 7. Handle Wake / Greeting
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

    def _resolve_clarification(
        self,
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

    def _resolve_open_application(
        self,
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
        store: Optional[ContextStore] = None,
    ) -> CommandObject:
        """Resolves target and modifiers for open_application."""
        raw_target = ""
        if canonical.target and canonical.target.value:
            raw_target = str(canonical.target.value).strip()

        # Handle contextual targets ("that", "it")
        if raw_target.lower() in ("that", "it", "this", "that app", "the app"):
            if store:
                ent = store.resolve_contextual_referent(raw_target, expected_type=EntityType.APPLICATION)
                raw_target = getattr(ent, "canonical_name", None) or getattr(ent, "title", None) or ""
            if not raw_target:
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

    def _resolve_close_application(
        self,
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
        store: Optional[ContextStore] = None,
    ) -> CommandObject:
        """Resolves target for close_application."""
        raw_target = ""
        if canonical.target and canonical.target.value:
            raw_target = str(canonical.target.value).strip()

        ref_type = str(canonical.reference.type or "").lower() if canonical.reference else ""
        ref_val = str(canonical.reference.value or "").lower() if canonical.reference else ""

        is_contextual = (
            raw_target.lower() in ("it", "that", "this", "that window", "the window", "this window")
            or ref_type == "active_window"
            or ref_val in ("it", "that", "window")
            or not raw_target
        )

        if is_contextual:
            if store:
                active_app_ent = store.get_active_application()
                app_to_close = active_app_ent.canonical_name if active_app_ent else ""
            else:
                app_to_close = ""
            if not app_to_close:
                app_to_close = context.get("active_application") or context.get("last_application") or ""
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

    def _resolve_switch_application(
        self,
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
        store: Optional[ContextStore] = None,
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
            required_tools=["focus_desktop_window"],
            execution_plan=[
                PlanStepItem(
                    step_id=1,
                    goal=f"Switch focus to {target_app}",
                    action="focus_desktop_window",
                    arguments={"window_name": target_app},
                    timeout_seconds=5.0,
                )
            ],
        )

    def _resolve_close_browser_tab(
        self,
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
        store: Optional[ContextStore] = None,
    ) -> CommandObject:
        """Resolves tab closure without terminating the browser process (Section 12)."""
        target_tab = None
        if canonical.target and canonical.target.value:
            target_tab = str(canonical.target.value).strip()

        # Handle contextual phrases ("this tab", "current tab", "it")
        if not target_tab or target_tab.lower() in ("this", "it", "that", "this tab", "current tab", "the tab"):
            target_tab = None  # None instructs close_tab to close the active foreground tab

        goal_desc = f"Close browser tab '{target_tab}'" if target_tab else "Close current browser tab"
        return CommandObject(
            command_id=cmd_id,
            task_id=task_id,
            intent="close_browser_tab",
            category=CommandCategory.BROWSER,
            complexity=CommandComplexity.ONE_TOOL,
            source_text=transcript,
            parameters={"tab_identifier": target_tab},
            entities={"target_tab": target_tab or "active_tab"},
            required_tools=["close_browser_tab"],
            execution_plan=[
                PlanStepItem(
                    step_id=1,
                    goal=goal_desc,
                    action="close_browser_tab",
                    arguments={"tab_identifier": target_tab},
                    timeout_seconds=5.0,
                    verification_type="tab_check",
                )
            ],
        )

    def _resolve_focus_browser_tab(
        self,
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
        store: Optional[ContextStore] = None,
    ) -> CommandObject:
        target_tab = str(canonical.target.value).strip() if (canonical.target and canonical.target.value) else "chrome"
        return CommandObject(
            command_id=cmd_id,
            task_id=task_id,
            intent="focus_browser_tab",
            category=CommandCategory.BROWSER,
            complexity=CommandComplexity.ONE_TOOL,
            source_text=transcript,
            parameters={"tab_identifier": target_tab},
            required_tools=["focus_browser_tab"],
            execution_plan=[
                PlanStepItem(
                    step_id=1,
                    goal=f"Focus browser tab '{target_tab}'",
                    action="focus_browser_tab",
                    arguments={"tab_identifier": target_tab},
                    timeout_seconds=5.0,
                )
            ],
        )

    def _resolve_open_new_tab(
        self,
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
        store: Optional[ContextStore] = None,
    ) -> CommandObject:
        target_url = str(canonical.target.value).strip() if (canonical.target and canonical.target.value) else "https://www.google.com"
        return CommandObject(
            command_id=cmd_id,
            task_id=task_id,
            intent="open_new_tab",
            category=CommandCategory.BROWSER,
            complexity=CommandComplexity.ONE_TOOL,
            source_text=transcript,
            parameters={"url": target_url},
            required_tools=["open_new_tab"],
            execution_plan=[
                PlanStepItem(
                    step_id=1,
                    goal=f"Open '{target_url}' in a new tab",
                    action="open_new_tab",
                    arguments={"url": target_url},
                    timeout_seconds=8.0,
                )
            ],
        )

    def _resolve_restore_setting(
        self,
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
        store: Optional[ContextStore] = None,
    ) -> CommandObject:
        """Restores a previous hardware setting value deterministically (Section 18)."""
        target_val = (canonical.target.value or "").lower() if (canonical.target and canonical.target.value) else ""
        setting_type = "brightness"
        if "volume" in target_val or "volume" in transcript.lower() or "sound" in transcript.lower():
            setting_type = "volume"
        elif "mute" in target_val or "mute" in transcript.lower():
            setting_type = "mute"

        prev_val = None
        if store:
            prev_val = store.get_previous_setting_value(setting_type)
        if prev_val is None:
            prev_val = context.get(f"last_{setting_type}")

        if prev_val is None:
            return CommandObject(
                command_id=cmd_id,
                task_id=task_id,
                intent="clarification",
                category=CommandCategory.SYSTEM,
                complexity=CommandComplexity.SIMPLE,
                source_text=transcript,
                raw_response=f"I don't have a previous {setting_type} level recorded to restore.",
            )

        tool_action = f"set_{setting_type}"
        return CommandObject(
            command_id=cmd_id,
            task_id=task_id,
            intent=f"restore_{setting_type}",
            category=CommandCategory.SYSTEM,
            complexity=CommandComplexity.ONE_TOOL,
            source_text=transcript,
            parameters={setting_type: prev_val},
            entities={"setting": setting_type, "value": prev_val},
            required_tools=[tool_action],
            execution_plan=[
                PlanStepItem(
                    step_id=1,
                    goal=f"Restore {setting_type} to previous level ({prev_val})",
                    action=tool_action,
                    arguments={setting_type: prev_val},
                    timeout_seconds=5.0,
                    verification_type="value_check",
                )
            ],
        )

    def _resolve_open_reference(
        self,
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
        store: Optional[ContextStore] = None,
    ) -> CommandObject:
        """Resolves reference to a concrete SearchResultEntity.
        CRITICAL RULE (Section 8): NEVER defaults to result #1 when ordinal is not specified!
        """
        # Verify if transcript actually contains an explicit ordinal expression
        # Prevents SLM from hallucinating ordinal=1 for pure anaphoric pronouns ("that", "it")
        transcript_clean = transcript.lower().strip()
        has_explicit_ordinal = bool(
            re.search(r"\b(?:first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last)\b", transcript_clean)
            or re.search(r"\b(?:result|item|video|link)\s+[1-9]\b", transcript_clean)
            or re.search(r"\b[1-9](?:st|nd|rd|th)?\s+(?:result|item|video|link)\b", transcript_clean)
            or re.search(r"^open\s+[1-9]\b", transcript_clean)
        )

        ordinal: Optional[int] = None
        if has_explicit_ordinal and canonical.reference and canonical.reference.ordinal is not None:
            ordinal = max(1, canonical.reference.ordinal)

        target_entity: Optional[SearchResultEntity] = None

        # 1. Try ContextStore resolution
        if store:
            target_entity = store.resolve_search_result(ordinal=ordinal)

        # 2. Try legacy dictionary resolution
        if not target_entity:
            search_results = context.get("search_results") or []
            if search_results and ordinal is not None and ordinal > 0:
                ord_idx = ordinal - 1
                if 0 <= ord_idx < len(search_results):
                    item = search_results[ord_idx]
                    target_entity = SearchResultEntity(
                        ordinal=ordinal,
                        title=item.get("title", f"Result {ordinal}"),
                        canonical_url=item.get("url") or item.get("canonical_url", ""),
                    )

        # 3. If no entity could be resolved: CLARIFY! NEVER DEFAULT TO 1! (Section 8)
        if not target_entity or not target_entity.canonical_url:
            logger.info("[SemanticContextResolver] Reference could not be resolved to verified entity. Demanding clarification.")
            search_results = context.get("search_results") or []
            if not search_results:
                msg = "There are no active search results from a previous search to open. Please ask me to search first."
            elif ordinal is not None:
                msg = f"I only found {len(search_results)} search results, so result #{ordinal} is not available."
            else:
                msg = "Which search result would you like me to open?"

            return CommandObject(
                command_id=cmd_id,
                task_id=task_id,
                intent="clarification",
                category=CommandCategory.CONTEXT,
                complexity=CommandComplexity.SIMPLE,
                source_text=transcript,
                raw_response=msg,
            )

        # 4. Success: construct execution plan using idempotent browser_open
        target_url = target_entity.canonical_url
        target_title = target_entity.title
        res_ordinal = target_entity.ordinal

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
                "index": res_ordinal - 1,
                "reference": f"result {res_ordinal}",
            },
            entities={
                "reference": f"result {res_ordinal}",
                "ordinal": res_ordinal - 1,
                "resolved_target": target_url,
                "entity_id": target_entity.entity_id,
            },
            required_tools=["browser_open"],
            execution_plan=[
                PlanStepItem(
                    step_id=1,
                    goal=f"Open search result #{res_ordinal}: {target_title}",
                    action="browser_open",
                    arguments={"url": target_url, "title": target_title, "new_tab": False},
                    timeout_seconds=10.0,
                    verification_type="url_check",
                )
            ],
        )

    def _resolve_repeat(
        self,
        canonical: Any,
        transcript: str,
        context: Dict[str, Any],
        task_id: str,
        cmd_id: str,
        store: Optional[ContextStore] = None,
    ) -> CommandObject:
        """Resolves repeat command by replaying verified action object (Section 9)."""
        # 1. Check ContextStore for ReplayableSemanticAction
        if store:
            last_act = store.get_last_replayable_action()
            if last_act and last_act.execution_plan_steps:
                cloned_plan = [
                    PlanStepItem(
                        step_id=idx + 1,
                        goal=s.get("goal", ""),
                        action=s.get("action", ""),
                        arguments=dict(s.get("arguments", {})),
                        timeout_seconds=s.get("timeout_seconds", 5.0),
                        verification_type=s.get("verification_type", "state_check"),
                    )
                    for idx, s in enumerate(last_act.execution_plan_steps)
                ]
                return CommandObject(
                    command_id=cmd_id,
                    task_id=task_id,
                    intent=f"repeat_{last_act.semantic_intent}",
                    category=CommandCategory.CONTEXT,
                    complexity=CommandComplexity.ONE_TOOL,
                    source_text=transcript,
                    parameters=dict(last_act.canonical_arguments),
                    required_tools=list(last_act.required_tools),
                    execution_plan=cloned_plan,
                )

        # 2. Fallback to last_command from context dict
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
