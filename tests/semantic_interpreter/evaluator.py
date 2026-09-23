"""
SERA 2.0 — Semantic Interpreter Benchmark Evaluator.

Compares structured semantic predictions against ground truth canonical intents.
Does NOT rely on raw JSON string equality; evaluates semantic intent, entity targets,
contextual references, modifiers, parameters, and clarification requirements.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from app.core.semantic.schema import CanonicalIntent


class SemanticEvaluator:
    """Evaluates semantic accuracy between predicted CanonicalIntent and ground truth."""

    @staticmethod
    def normalize_str(s: Optional[str]) -> str:
        if not s:
            return ""
        return s.lower().strip().replace("-", " ").replace("_", " ")

    @classmethod
    def evaluate_case(
        cls,
        prediction: CanonicalIntent,
        expected: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, bool], str]:
        """Evaluates a single prediction against expected dictionary.
        
        Returns:
            (is_overall_match, component_matches, failure_reason)
        """
        matches = {
            "clarification": True,
            "intent": True,
            "target": True,
            "reference": True,
            "modifiers": True,
            "parameters": True,
        }
        reasons = []

        # 1. Ambiguity / Clarification check
        exp_clarification = expected.get("needs_clarification", False)
        if exp_clarification:
            # Expected ambiguous/needs clarification
            pred_clarification = prediction.needs_clarification or prediction.confidence < 0.5
            if not pred_clarification:
                matches["clarification"] = False
                reasons.append(f"Expected clarification, but model gave intent='{prediction.intent}' confidence={prediction.confidence}")
            return (len(reasons) == 0, matches, "; ".join(reasons))

        # If model requested clarification when unambiguous
        if prediction.needs_clarification:
            matches["clarification"] = False
            reasons.append(f"Model unexpectedly requested clarification: {prediction.ambiguity_reason}")
            return (False, matches, "; ".join(reasons))

        # 2. Intent check
        exp_intent = cls.normalize_str(expected.get("intent"))
        pred_intent = cls.normalize_str(prediction.intent)

        # Allow valid semantic equivalents
        intent_match = (
            pred_intent == exp_intent or
            (exp_intent == "open_application" and pred_intent in ("launch_application", "start_application")) or
            (exp_intent == "close_application" and pred_intent in ("terminate_application", "exit_application")) or
            (exp_intent == "set_brightness" and pred_intent == "adjust_brightness") or
            (exp_intent == "set_volume" and pred_intent == "adjust_volume") or
            (exp_intent == "open_reference" and pred_intent in ("open_search_result", "click_result", "select_result"))
        )
        if not intent_match:
            matches["intent"] = False
            reasons.append(f"Intent mismatch: predicted '{prediction.intent}', expected '{expected.get('intent')}'")

        # 3. Target check
        exp_target = expected.get("target")
        if exp_target:
            pred_target = prediction.target
            exp_val = cls.normalize_str(exp_target.get("value"))
            target_ok = False

            if pred_target and pred_target.value:
                pred_val = cls.normalize_str(pred_target.value)
                target_ok = (
                    exp_val == pred_val or
                    exp_val in pred_val or
                    pred_val in exp_val or
                    ("chrome" in exp_val and "chrome" in pred_val) or
                    ("code" in exp_val and "code" in pred_val) or
                    ("browser" in exp_val and pred_val in ("chrome", "browser")) or
                    ("youtube" in exp_val and "youtube" in pred_val)
                )
            elif exp_intent in ("battery_status", "system_status", "take_screenshot"):
                # Implicit target for specialized singleton intents
                target_ok = True
            elif prediction.parameters:
                # Check parameters for query/target
                param_strs = [str(pv).lower() for pv in prediction.parameters.values()]
                target_ok = any(exp_val in p for p in param_strs)

            if not target_ok:
                matches["target"] = False
                reasons.append(f"Target mismatch: expected '{exp_val}'")

        # 4. Reference check
        exp_ref = expected.get("reference")
        if exp_ref:
            pred_ref = prediction.reference
            if not pred_ref:
                matches["reference"] = False
                reasons.append(f"Missing reference: expected type='{exp_ref.get('type')}', ordinal={exp_ref.get('ordinal')}")
            else:
                exp_ord = exp_ref.get("ordinal")
                pred_ord = pred_ref.ordinal
                if exp_ord is not None and pred_ord != exp_ord:
                    # Allow top/first ordinal equivalence
                    if not (exp_ord == 1 and pred_ord in (1, None) and "top" in str(pred_ref.value).lower()):
                        matches["reference"] = False
                        reasons.append(f"Reference ordinal mismatch: predicted {pred_ord}, expected {exp_ord}")

        # 5. Modifiers check
        exp_mod = expected.get("modifiers", {})
        if exp_mod.get("repeat") and not prediction.modifiers.repeat:
            matches["modifiers"] = False
            reasons.append("Missing repeat modifier")
        if exp_mod.get("direction"):
            pred_dir = cls.normalize_str(prediction.modifiers.direction)
            exp_dir = cls.normalize_str(exp_mod.get("direction"))
            if pred_dir != exp_dir:
                matches["modifiers"] = False
                reasons.append(f"Modifier direction mismatch: predicted '{pred_dir}', expected '{exp_dir}'")

        # 6. Parameters check
        exp_params = expected.get("parameters", {})
        for k, v in exp_params.items():
            pred_val = prediction.parameters.get(k)
            # If value was placed in target attributes (e.g. level=80)
            if pred_val is None and k == "value" and prediction.target and prediction.target.attributes:
                pred_val = prediction.target.attributes.get("level") or prediction.target.attributes.get("value")

            # If value is integer, compare numeric
            if isinstance(v, (int, float)):
                try:
                    if pred_val is None or float(pred_val) != float(v):
                        matches["parameters"] = False
                        reasons.append(f"Parameter '{k}' mismatch: predicted {pred_val}, expected {v}")
                except (ValueError, TypeError):
                    matches["parameters"] = False
                    reasons.append(f"Parameter '{k}' missing or non-numeric: predicted {pred_val}, expected {v}")

        is_match = len(reasons) == 0
        return is_match, matches, "; ".join(reasons)
