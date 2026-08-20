import json
import logging
import re
from typing import Any
from pydantic import BaseModel, Field

from app.core.router import ModelRouter
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class PlanStep(BaseModel):
    """An individual discrete step in a bounded task plan."""
    id: int = Field(description="1-based index of the step")
    goal: str = Field(description="Human-readable intent of this step")
    action: str = Field(description="Registered tool name to execute")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the tool")
    verification: str = Field(default="state_change", description="Verification method: active_window, value_change, focus_state, control_state_change, visual_check")
    expected_result: str = Field(default="", description="Expected outcome description")
    idempotent: bool = Field(default=True, description="Whether step is safe to retry without unintended side effects")
    completed: bool = Field(default=False, description="Whether step was executed and verified")


class TaskPlan(BaseModel):
    """A validated, bounded multi-step desktop execution plan."""
    task: str = Field(description="Original user task description")
    steps: list[PlanStep] = Field(default_factory=list, description="Sequence of steps (max 10)")
    is_valid: bool = Field(default=True, description="Whether plan passed validation")
    validation_error: str | None = Field(default=None, description="Validation failure details if invalid")


class TaskPlanner:
    """Decomposes user desktop requests into validated, bounded execution plans."""

    def __init__(
        self,
        tools: ToolRegistry,
        router: ModelRouter | None = None,
        max_steps: int = 10,
    ):
        self.tools = tools
        self.router = router
        self.max_steps = max_steps

    def is_multi_step_task(self, query: str) -> bool:
        return self.is_multi_step_request(query)

    def is_multi_step_request(self, query: str) -> bool:
        """Heuristic check to fast-filter multi-step computer tasks from single questions."""
        q_lower = query.lower().strip()
        patterns = [
            r"open .+ and (type|write|search|calculate|enter|focus)",
            r"launch .+ and (type|write|search|calculate|enter|focus)",
            r"calculate .+ in (calculator|calc)",
            r"open calculator and calculate",
            r"open (chrome|edge|browser) and search for",
            r"open (?:file )?explorer and (?:go to|navigate to)",
        ]
        return any(re.search(p, q_lower) for p in patterns)

    async def plan(self, user_request: str) -> TaskPlan:
        """Creates and validates an execution plan for a user request."""
        # 1. Check Fast-Path Deterministic Planners
        fast_plan = self._fast_path_plan(user_request)
        if fast_plan:
            valid, err = self.validate_plan(fast_plan)
            fast_plan.is_valid = valid
            fast_plan.validation_error = err
            return fast_plan

        # 2. LLM-Assisted Decomposition via Reasoning Provider
        if self.router and self.router.has_role("reasoning"):
            llm_plan = await self._llm_decompose(user_request)
            valid, err = self.validate_plan(llm_plan)
            llm_plan.is_valid = valid
            llm_plan.validation_error = err
            return llm_plan

        # Fallback empty plan
        return TaskPlan(
            task=user_request,
            steps=[],
            is_valid=False,
            validation_error="Unable to decompose task into valid steps.",
        )

    def validate_plan(self, plan: TaskPlan) -> tuple[bool, str | None]:
        """Validates that a plan conforms to safety bounds and registered tool schemas."""
        if not plan.steps:
            return False, "Plan contains no steps."

        if len(plan.steps) > self.max_steps:
            return False, f"Plan exceeds maximum step limit ({len(plan.steps)} > {self.max_steps})."

        for step in plan.steps:
            tool = self.tools.get(step.action)
            if not tool:
                return False, f"Action tool '{step.action}' is not registered in ToolRegistry."

            if not step.verification:
                return False, f"Step {step.id} has no verification method defined."

        return True, None

    def _fast_path_plan(self, query: str) -> TaskPlan | None:
        """Generates deterministic fast-path plans for common multi-step patterns."""
        clean_q = query.strip()

        # Pattern A: Notepad text entry ("Open Notepad and type Hello SERA")
        m_notepad = re.search(r"open notepad and (?:type|write|enter)\s+(.+)", clean_q, re.IGNORECASE)
        if m_notepad:
            text_to_type = m_notepad.group(1).strip(" '\"")
            return TaskPlan(
                task=query,
                steps=[
                    PlanStep(
                        id=1,
                        goal="Open Windows Notepad",
                        action="open_application",
                        arguments={"application": "notepad"},
                        verification="active_window",
                        expected_result="Notepad window open and active",
                        idempotent=True,
                    ),
                    PlanStep(
                        id=2,
                        goal="Enter text into Notepad editor",
                        action="set_ui_input_text",
                        arguments={"target_name": "Text editor", "text": text_to_type, "window_name": "Notepad"},
                        verification="value_change",
                        expected_result=f"Text '{text_to_type}' entered in editor",
                        idempotent=True,
                    ),
                ],
            )

        # Pattern B: Calculator calculation ("Open Calculator and calculate 125 * 8")
        m_calc = re.search(r"open calculator and calculate\s+([\d\s\+\-\*\/\.]+)", clean_q, re.IGNORECASE) or re.search(r"calculate\s+([\d\s\+\-\*\/\.]+)\s+in calculator", clean_q, re.IGNORECASE)
        if m_calc:
            expr = m_calc.group(1).replace(" ", "")
            steps = [
                PlanStep(
                    id=1,
                    goal="Open Windows Calculator",
                    action="open_application",
                    arguments={"application": "calculator"},
                    verification="active_window",
                    expected_result="Calculator window open and active",
                    idempotent=True,
                )
            ]
            step_id = 2
            for char in expr:
                if char.isdigit():
                    digit_names = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five", "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine"}
                    steps.append(
                        PlanStep(
                            id=step_id,
                            goal=f"Click digit {char}",
                            action="click_ui_element",
                            arguments={"target_name": digit_names.get(char, char), "control_type": "button", "window_name": "Calculator"},
                            verification="control_state_change",
                            expected_result=f"Digit {char} pressed",
                        )
                    )
                    step_id += 1
                elif char in ("+", "-", "*", "/"):
                    op_names = {"+": "Plus", "-": "Minus", "*": "Multiply", "/": "Divide"}
                    steps.append(
                        PlanStep(
                            id=step_id,
                            goal=f"Click operator {char}",
                            action="click_ui_element",
                            arguments={"target_name": op_names.get(char, "operator"), "control_type": "button", "window_name": "Calculator"},
                            verification="control_state_change",
                            expected_result=f"Operator {char} pressed",
                        )
                    )
                    step_id += 1

            # Equals step
            steps.append(
                PlanStep(
                    id=step_id,
                    goal="Click Equals for result",
                    action="click_ui_element",
                    arguments={"target_name": "Equals", "control_type": "button", "window_name": "Calculator"},
                    verification="control_state_change",
                    expected_result="Calculation evaluated",
                )
            )
            return TaskPlan(task=query, steps=steps)

        # Pattern C: Browser search ("Open Chrome and search for RTX 5090 benchmarks")
        m_browser = re.search(r"open (chrome|edge|browser) and search for\s+(.+)", clean_q, re.IGNORECASE)
        if m_browser:
            browser_app = m_browser.group(1).lower()
            search_query = m_browser.group(2).strip(" '\"")
            return TaskPlan(
                task=query,
                steps=[
                    PlanStep(
                        id=1,
                        goal=f"Open {browser_app.capitalize()}",
                        action="open_application",
                        arguments={"application": "msedge" if browser_app == "edge" else "chrome"},
                        verification="active_window",
                        expected_result=f"{browser_app.capitalize()} open and active",
                        idempotent=True,
                    ),
                    PlanStep(
                        id=2,
                        goal="Focus address bar",
                        action="click_ui_element",
                        arguments={"target_name": "Address and search bar", "control_type": "edit", "window_name": browser_app},
                        verification="focus_state",
                        expected_result="Address bar focused",
                        idempotent=True,
                    ),
                    PlanStep(
                        id=3,
                        goal="Enter search query",
                        action="set_ui_input_text",
                        arguments={"target_name": "Address and search bar", "text": search_query, "window_name": browser_app},
                        verification="value_change",
                        expected_result=f"Entered search query '{search_query}'",
                        idempotent=True,
                    ),
                ],
            )

        # Pattern D: File Explorer navigation ("Open File Explorer and go to C:\Users")
        m_explorer = re.search(r"open (?:file )?explorer and (?:go to|navigate to)\s+(.+)", clean_q, re.IGNORECASE)
        if m_explorer:
            path_target = m_explorer.group(1).strip(" '\"")
            return TaskPlan(
                task=query,
                steps=[
                    PlanStep(
                        id=1,
                        goal="Open File Explorer",
                        action="open_application",
                        arguments={"application": "explorer"},
                        verification="active_window",
                        expected_result="File Explorer open and active",
                        idempotent=True,
                    ),
                    PlanStep(
                        id=2,
                        goal="Navigate to path",
                        action="set_ui_input_text",
                        arguments={"target_name": "Address", "text": path_target, "window_name": "Explorer"},
                        verification="value_change",
                        expected_result=f"Path '{path_target}' entered in address bar",
                        idempotent=True,
                    ),
                ],
            )

        return None

    async def _llm_decompose(self, query: str) -> TaskPlan:
        """Decomposes complex requests using the reasoning model."""
        prompt = f"""Decompose the following user request into a step-by-step execution plan using ONLY registered tools:
Registered Tools:
- open_application(application: str)
- close_application(application: str)
- focus_desktop_window(window_name: str)
- inspect_desktop_ui()
- click_ui_element(target_name: str, control_type: str)
- set_ui_input_text(target_name: str, text: str)
- select_ui_tab(tab_name: str)

User Request: "{query}"

Output ONLY a JSON object:
{{
  "task": "{query}",
  "steps": [
    {{
      "id": 1,
      "goal": "...",
      "action": "...",
      "arguments": {{}},
      "verification": "active_window | value_change | focus_state | control_state_change | visual_check",
      "expected_result": "..."
    }}
  ]
}}"""
        try:
            target_role = "desktop" if self.router.has_role("desktop") else "reasoning"
            resp, _ = await self.router.generate_with_fallback(
                messages=[{"role": "user", "content": prompt}],
                preferred_role=target_role,
            )
            raw = (resp.text or "").strip()
            if "```json" in raw:
                raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in raw:
                raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

            data = json.loads(raw)
            steps = [PlanStep(**s) for s in data.get("steps", [])]
            return TaskPlan(task=query, steps=steps)
        except Exception as e:
            logger.warning(f"[TaskPlanner] LLM decomposition failed: {e}")
            return TaskPlan(task=query, steps=[], is_valid=False, validation_error=str(e))
