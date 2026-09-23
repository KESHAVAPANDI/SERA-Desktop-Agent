"""
SERA 2.0 — Semantic Interpreter Output Validator.

Validates and sanitizes the structured output of the local SLM.
Never trusts raw model output without strict schema validation.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from pydantic import ValidationError

from app.core.semantic.schema import ActionFamily, CanonicalIntent

logger = logging.getLogger("sera.semantic.validator")

KNOWN_INTENTS = {
    "open_application", "close_application", "switch_application",
    "set_brightness", "adjust_brightness", "set_volume", "adjust_volume",
    "web_search", "youtube_search", "open_url", "open_reference",
    "take_screenshot", "analyze_screen", "compound_workflow",
    "repeat_last_task", "cancel_task", "system_status", "battery_status",
    "greeting", "gratitude", "farewell", "capabilities", "assistant_wake",
    "unknown"
}

VALID_ACTION_FAMILIES = {f.value for f in ActionFamily}


class SemanticValidator:
    """Strict validator and sanitizer for Semantic Interpreter outputs."""

    @staticmethod
    def clean_json_text(raw_text: str) -> str:
        """Strips markdown fences or accidental preamble/postscript from model output."""
        text = raw_text.strip()

        # 1. Remove markdown code block if present
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip()

        # 2. If text does not start with '{', handle assistant prefill continuation
        if not text.startswith("{"):
            candidate = "{\n" + text
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                # If trailing text after JSON, extract outermost matching braces from candidate
                c_match = re.search(r"(\{.*\})", candidate, re.DOTALL)
                if c_match:
                    try:
                        json.loads(c_match.group(1))
                        return c_match.group(1).strip()
                    except Exception:
                        pass

        # 3. Direct brace match if text already contains outer braces
        brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_match:
            return brace_match.group(1).strip()

        return text

    @classmethod
    def validate(cls, raw_output: str | Dict[str, Any]) -> Tuple[CanonicalIntent, bool, Optional[str]]:
        """Validates and constructs a CanonicalIntent object.
        
        Returns:
            (canonical_intent, is_valid, error_reason)
        """
        try:
            if isinstance(raw_output, str):
                cleaned_text = cls.clean_json_text(raw_output)
                if not cleaned_text:
                    return cls._create_failure_intent("Empty response from semantic model"), False, "Empty response"
                data = json.loads(cleaned_text)
            elif isinstance(raw_output, dict):
                data = raw_output
            else:
                return cls._create_failure_intent(f"Invalid input type: {type(raw_output)}"), False, "Invalid type"

            # Normalize family if lowercase
            if "action_family" in data and isinstance(data["action_family"], str):
                data["action_family"] = data["action_family"].upper()
                if data["action_family"] not in VALID_ACTION_FAMILIES:
                    data["action_family"] = ActionFamily.UNKNOWN.value

            # Validate against Pydantic schema
            intent_obj = CanonicalIntent.model_validate(data)

            # Check for unknown invented intents
            if intent_obj.intent not in KNOWN_INTENTS:
                # Do not reject immediately if reasonable, but flag lower confidence
                logger.warning(f"Semantic Interpreter produced unknown intent: {intent_obj.intent}")

            return intent_obj, True, None

        except json.JSONDecodeError as err:
            err_msg = f"Malformed JSON: {err}"
            logger.warning(err_msg)
            return cls._create_failure_intent(err_msg), False, err_msg
        except ValidationError as err:
            err_msg = f"Schema validation error: {err}"
            logger.warning(err_msg)
            return cls._create_failure_intent(err_msg), False, err_msg
        except Exception as err:
            err_msg = f"Unexpected validation error: {err}"
            logger.error(err_msg, exc_info=True)
            return cls._create_failure_intent(err_msg), False, err_msg

    @staticmethod
    def _create_failure_intent(reason: str) -> CanonicalIntent:
        """Produces a safe, structured failure intent."""
        return CanonicalIntent(
            intent="unknown",
            action_family=ActionFamily.UNKNOWN.value,
            confidence=0.0,
            needs_clarification=True,
            ambiguity_reason=reason,
        )
