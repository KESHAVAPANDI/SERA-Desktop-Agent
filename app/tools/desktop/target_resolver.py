import logging
from typing import Any
from pydantic import BaseModel, Field
from app.tools.desktop.models import NativeUIControl

logger = logging.getLogger(__name__)


class ResolutionResult(BaseModel):
    """Structured result of semantic target resolution."""
    resolved: bool = Field(description="Whether a valid target control was resolved")
    control: NativeUIControl | None = Field(default=None, description="The resolved native UI control")
    confidence: str = Field(default="low", description="Confidence tier: high, medium, or low")
    score: float = Field(default=0.0, description="Normalized match score 0.0-1.0")
    matched_name: str = Field(default="", description="Name of the matched control")
    control_type: str = Field(default="", description="Type of the matched control")
    ambiguity_candidates: list[str] = Field(default_factory=list, description="Names of competing ambiguous controls")
    reason: str = Field(default="", description="Explanation of match rationale or ambiguity")


class TargetResolver:
    """Robust semantic target resolver with multi-factor scoring and confidence tiering."""

    def resolve(
        self,
        target: dict[str, Any],
        controls: list[NativeUIControl],
    ) -> ResolutionResult:
        """Resolves a semantic target specification against a list of native UI controls.

        Args:
            target: Target dict e.g. {"name": "5", "type": "button", "context": "Calculator", "automation_id": "num5Button"}
            controls: Available controls from UI inspection
        """
        if not controls:
            return ResolutionResult(
                resolved=False,
                confidence="low",
                score=0.0,
                reason="No native controls available in active window.",
            )

        target_name = (target.get("name") or "").strip().lower()
        target_type = (target.get("type") or "").strip().lower()
        target_auto_id = (target.get("automation_id") or "").strip().lower()
        target_context = (target.get("context") or "").strip().lower()

        scored_candidates: list[tuple[NativeUIControl, float, list[str]]] = []

        for ctrl in controls:
            score = 0.0
            reasons = []

            ctrl_name_raw = ctrl.name or ""
            ctrl_name_lower = ctrl_name_raw.lower()
            ctrl_type_lower = (ctrl.type or "").lower()
            ctrl_auto_id_lower = (ctrl.automation_id or "").lower()
            ctrl_class_lower = (ctrl.class_name or "").lower()

            # 1. Exact Name match
            if target_name:
                if ctrl_name_raw == target.get("name"):
                    score += 0.50
                    reasons.append("Exact case-sensitive name match")
                elif ctrl_name_lower == target_name:
                    score += 0.45
                    reasons.append("Normalized name match")
                elif target_name in ctrl_name_lower:
                    score += 0.25
                    reasons.append("Substring name match")

            # 2. Automation ID match
            if target_auto_id:
                if ctrl_auto_id_lower == target_auto_id:
                    score += 0.40
                    reasons.append("Exact automation ID match")
                elif target_auto_id in ctrl_auto_id_lower:
                    score += 0.20
                    reasons.append("Partial automation ID match")

            # 3. Control Type match
            if target_type:
                if ctrl_type_lower == target_type:
                    score += 0.25
                    reasons.append(f"Matching control type '{ctrl.type}'")
                elif target_type in ("button", "action") and ctrl_type_lower in ("button", "menu"):
                    score += 0.15
                    reasons.append("Compatible action type")
                elif target_type in ("input", "field", "textbox", "edit") and ctrl_type_lower in ("edit", "text"):
                    score += 0.15
                    reasons.append("Compatible edit type")

            # 4. Contextual Hint match (parent/container/label)
            if target_context:
                if target_context in ctrl_name_lower or target_context in ctrl_auto_id_lower or target_context in ctrl_class_lower:
                    score += 0.20
                    reasons.append(f"Context hint '{target_context}' verified")

            # 5. Enabled & Visible bonus / penalty
            if ctrl.enabled and ctrl.visible:
                score += 0.05
            elif not ctrl.enabled:
                score -= 0.35
                reasons.append("Penalized: control disabled")

            if score > 0.15:
                scored_candidates.append((ctrl, round(min(1.0, max(0.0, score)), 2), reasons))

        if not scored_candidates:
            return ResolutionResult(
                resolved=False,
                confidence="low",
                score=0.0,
                reason=f"No matching active control found for target '{target_name}'.",
            )

        # Sort candidates descending by score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_ctrl, top_score, top_reasons = scored_candidates[0]

        # Disabled control guard
        if not top_ctrl.enabled:
            return ResolutionResult(
                resolved=False,
                control=top_ctrl,
                confidence="low",
                score=top_score,
                matched_name=top_ctrl.name,
                control_type=top_ctrl.type,
                reason="Target control is currently disabled and cannot be interacted with.",
            )

        # Check for ambiguity among top candidates
        ambiguous_names = []
        if len(scored_candidates) > 1:
            second_ctrl, second_score, _ = scored_candidates[1]
            if top_score >= 0.50 and (top_score - second_score) < 0.10:
                ambiguous_names = [f"{c[0].name} ({c[0].id})" for c in scored_candidates[:3] if (top_score - c[1]) < 0.15]

        # Determine Confidence Tier
        if ambiguous_names:
            confidence = "medium"
            reason = f"Ambiguous match between: {', '.join(ambiguous_names)}"
        elif top_score >= 0.70:
            confidence = "high"
            reason = f"Unique high-confidence match: {', '.join(top_reasons)}"
        elif top_score >= 0.40:
            confidence = "medium"
            reason = f"Moderate match: {', '.join(top_reasons)}"
        else:
            confidence = "low"
            reason = f"Score {top_score} below minimum threshold (0.40)"

        is_resolved = (confidence == "high") or (confidence == "medium" and not ambiguous_names)

        return ResolutionResult(
            resolved=is_resolved,
            control=top_ctrl if is_resolved else None,
            confidence=confidence,
            score=top_score,
            matched_name=top_ctrl.name,
            control_type=top_ctrl.type,
            ambiguity_candidates=ambiguous_names,
            reason=reason,
        )
