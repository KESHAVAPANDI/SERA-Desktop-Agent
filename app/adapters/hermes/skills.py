"""
SERA 2.0 / Phase 4A — Progressive Skills Specification for Hermes.

Implements the agentskills.io-compatible progressive skill loading system.
Metadata is lightweight and always present; full procedural markdown is loaded
on-demand when the skill matches task preconditions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("sera.hermes.skills")


class HermesSkill(BaseModel):
    """Progressive Skill Definition conforming to agentskills.io."""
    name: str
    description: str
    triggers: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    required_permissions: List[str] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    instructions: str
    verification_expectations: str
    failure_handling: str
    is_loaded: bool = False

    def to_metadata_prompt(self) -> str:
        """Lightweight description for initial system prompt (< 100 tokens)."""
        tools_str = ", ".join(self.required_tools)
        return f"- {self.name}: {self.description} (Tools: {tools_str})"

    def to_full_prompt(self) -> str:
        """Full procedural context loaded only on demand."""
        return (
            f"### SKILL: {self.name}\n"
            f"**Description:** {self.description}\n"
            f"**Preconditions:** {', '.join(self.preconditions)}\n"
            f"**Required Tools:** {', '.join(self.required_tools)}\n\n"
            f"**Procedure:**\n{self.instructions}\n\n"
            f"**Verification Expectations:**\n{self.verification_expectations}\n\n"
            f"**Failure Handling:**\n{self.failure_handling}\n"
        )


class SkillRegistry:
    """Manages skill discovery, semantic matching, and on-demand context injection."""

    def __init__(self):
        self._skills: Dict[str, HermesSkill] = {}
        self._register_default_skills()

    def register_skill(self, skill: HermesSkill) -> None:
        self._skills[skill.name] = skill

    def get_skill(self, name: str) -> Optional[HermesSkill]:
        return self._skills.get(name)

    def list_metadata_prompts(self) -> str:
        """Returns consolidated metadata descriptions for all registered skills."""
        return "\n".join(s.to_metadata_prompt() for s in self._skills.values())

    def match_and_load(self, utterance: str) -> List[HermesSkill]:
        """Progressively matches user intent and loads full procedural instructions."""
        matched = []
        u_lower = utterance.lower()
        for skill in self._skills.values():
            if any(trigger.lower() in u_lower for trigger in skill.triggers):
                matched.append(skill)
        return matched

    def _register_default_skills(self) -> None:
        # 1. System Diagnostics Skill
        self.register_skill(
            HermesSkill(
                name="system_diagnostics",
                description="Performs comprehensive hardware, active window, and performance triage on Windows.",
                triggers=["diagnose", "system health", "diagnostics", "check performance", "why is pc slow"],
                required_tools=["list_running_applications", "get_system_power_status", "get_battery_info"],
                required_permissions=["READ_SYSTEM_STATE"],
                preconditions=["Windows interactive desktop session active"],
                instructions=(
                    "1. Enumerate active interactive user applications.\n"
                    "2. Query power and battery telemetry.\n"
                    "3. Identify CPU or memory resource hogs.\n"
                    "4. Summarize operational health in 2-3 concise sentences."
                ),
                verification_expectations="All diagnostic readings return success=True with concrete metrics.",
                failure_handling="If diagnostic query fails, report specific subsystem error without halting agent loop.",
            )
        )

        # 2. Browser Research Skill
        self.register_skill(
            HermesSkill(
                name="browser_research",
                description="Multi-step topic search, tab verification, and reference navigation.",
                triggers=["research", "search for videos", "look up", "find articles on", "youtube search"],
                required_tools=["browser_search", "browser_open", "focus_browser_tab"],
                required_permissions=["BROWSER_NAVIGATION"],
                preconditions=["Default web browser configured"],
                instructions=(
                    "1. Execute search query via browser_search.\n"
                    "2. Inspect returned SearchSession items.\n"
                    "3. Open the highest relevance result or solicit clarification if ambiguous.\n"
                    "4. Confirm active tab matches requested topic."
                ),
                verification_expectations="Active tab URL matches target domain and window title reflects search topic.",
                failure_handling="If search returns 0 results, propose alternative search terms or clarify topic.",
            )
        )
