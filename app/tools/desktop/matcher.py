import logging
from typing import Any
from app.tools.desktop.models import NativeUIControl

logger = logging.getLogger(__name__)


class SemanticTargetMatcher:
    """Matches semantic LLM targets to concrete native UI controls with confidence scoring."""

    def match(
        self,
        target: dict[str, Any],
        controls: list[NativeUIControl],
    ) -> tuple[NativeUIControl | None, float, str]:
        """Finds the best matching NativeUIControl for a target specification.

        Args:
            target: Target dictionary e.g. {"name": "Run", "type": "button", "automation_id": "btnRun"}
            controls: Available native controls from UI inspector

        Returns:
            (best_control, confidence_score_0_to_1, reason_description)
        """
        if not controls:
            return None, 0.0, "No native controls available in active window."

        target_name = (target.get("name") or "").strip().lower()
        target_type = (target.get("type") or "").strip().lower()
        target_auto_id = (target.get("automation_id") or "").strip().lower()

        best_control = None
        best_score = 0.0
        best_reason = "No match found."

        for ctrl in controls:
            score = 0.0
            reasons = []

            ctrl_name_lower = ctrl.name.lower()
            ctrl_type_lower = ctrl.type.lower()
            ctrl_auto_id_lower = (ctrl.automation_id or "").lower()

            # Automation ID matching
            if target_auto_id and target_auto_id == ctrl_auto_id_lower:
                score += 0.45
                reasons.append("Exact automation ID match")

            # Name matching
            if target_name:
                if ctrl_name_lower == target_name:
                    score += 0.50
                    reasons.append("Exact name match")
                elif target_name in ctrl_name_lower or ctrl_name_lower in target_name:
                    score += 0.30
                    reasons.append("Substring name match")

            # Type matching
            if target_type:
                if target_type == ctrl_type_lower:
                    score += 0.25
                    reasons.append(f"Matching control type '{ctrl.type}'")
                elif target_type in ("button", "action") and ctrl_type_lower == "button":
                    score += 0.20
                    reasons.append("Compatible button type")
                elif target_type in ("input", "field", "textbox", "edit") and ctrl_type_lower == "edit":
                    score += 0.20
                    reasons.append("Compatible edit type")

            # Prefer enabled and visible controls
            if ctrl.enabled and ctrl.visible:
                score += 0.05

            if score > best_score:
                best_score = score
                best_control = ctrl
                best_reason = ", ".join(reasons)

        # Normalize score to max 1.0
        normalized_score = min(1.0, round(best_score, 2))
        if normalized_score >= 0.40 and best_control:
            return best_control, normalized_score, f"Matched '{best_control.name}' ({best_reason})"

        return None, normalized_score, f"Confidence {normalized_score} below threshold (0.40). Native target insufficient."
