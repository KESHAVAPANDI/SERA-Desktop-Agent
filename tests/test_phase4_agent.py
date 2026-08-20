import asyncio
import time
import unittest
from unittest.mock import MagicMock, AsyncMock

from app.core.planner import TaskPlanner, TaskPlan, PlanStep
from app.core.state import SERAState, SERAStatus
from app.core.task_executor import MultiStepExecutor, TaskExecutionResult
from app.tools import create_tool_registry
from app.tools.desktop.ui_inspector import WindowsUIInspector


class TestPhase4Agent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.tools = create_tool_registry()
        self.state = SERAState()
        self.planner = TaskPlanner(tools=self.tools, max_steps=10)

    async def test_planner_notepad_fast_path(self):
        """Test deterministic fast-path planning for Notepad text entry."""
        query = "Open Notepad and type Hello SERA"
        self.assertTrue(self.planner.is_multi_step_task(query))

        plan = await self.planner.plan(query)
        self.assertTrue(plan.is_valid)
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].action, "open_application")
        self.assertEqual(plan.steps[0].arguments.get("application"), "notepad")
        self.assertEqual(plan.steps[1].action, "set_ui_input_text")
        self.assertEqual(plan.steps[1].arguments.get("text"), "Hello SERA")
        self.assertEqual(plan.steps[1].verification, "value_change")

    async def test_planner_calculator_fast_path(self):
        """Test deterministic fast-path planning for Calculator expression."""
        query = "Open Calculator and calculate 5 + 5"
        self.assertTrue(self.planner.is_multi_step_task(query))

        plan = await self.planner.plan(query)
        self.assertTrue(plan.is_valid)
        # open + 5 + plus + 5 + equals = 5 steps
        self.assertEqual(len(plan.steps), 5)
        self.assertEqual(plan.steps[0].action, "open_application")
        self.assertEqual(plan.steps[-1].arguments.get("target_name"), "Equals")

    def test_planner_rejects_excessive_steps(self):
        """Test that plans exceeding max_steps (10) are rejected."""
        steps = [
            PlanStep(id=i, goal=f"Step {i}", action="open_application", arguments={"application": "notepad"}, verification="active_window")
            for i in range(1, 12)
        ]
        plan = TaskPlan(task="Too many steps", steps=steps)
        valid, err = self.planner.validate_plan(plan)
        self.assertFalse(valid)
        self.assertIn("exceeds maximum step limit", err)

    def test_planner_rejects_unregistered_tool(self):
        """Test that plans referencing nonexistent tools are rejected."""
        steps = [
            PlanStep(id=1, goal="Bad tool", action="arbitrary_cmd_exec", arguments={}, verification="active_window")
        ]
        plan = TaskPlan(task="Invalid tool", steps=steps)
        valid, err = self.planner.validate_plan(plan)
        self.assertFalse(valid)
        self.assertIn("not registered", err)

    async def test_executor_successful_plan(self):
        """Test execution and verification of a valid plan."""
        mock_tools = MagicMock()
        mock_tools.execute = AsyncMock(return_value={"success": True, "verified": True})
        mock_inspector = MagicMock(spec=WindowsUIInspector)

        executor = MultiStepExecutor(
            tools=mock_tools,
            inspector=mock_inspector,
            state=self.state,
            max_steps=10,
        )

        plan = TaskPlan(
            task="Test task",
            steps=[
                PlanStep(id=1, goal="Step 1", action="click_ui_element", arguments={"target_name": "Run"}, verification="control_state_change"),
                PlanStep(id=2, goal="Step 2", action="set_ui_input_text", arguments={"target_name": "Edit", "text": "test"}, verification="value_change"),
            ],
        )

        res = await executor.execute(plan)
        self.assertTrue(res.success)
        self.assertEqual(res.steps_completed, 2)
        self.assertEqual(self.state.status, SERAStatus.TASK_COMPLETED)

    async def test_executor_cancellation(self):
        """Test immediate task cancellation via cancellation event."""
        mock_tools = MagicMock()
        mock_tools.execute = AsyncMock(return_value={"success": True, "verified": True})

        executor = MultiStepExecutor(
            tools=mock_tools,
            state=self.state,
            max_steps=10,
        )

        plan = TaskPlan(
            task="Cancelled task",
            steps=[
                PlanStep(id=1, goal="Step 1", action="click_ui_element", verification="control_state_change"),
                PlanStep(id=2, goal="Step 2", action="click_ui_element", verification="control_state_change"),
            ],
        )

        cancel_event = asyncio.Event()
        cancel_event.set()  # Pre-cancel

        res = await executor.execute(plan, cancellation_event=cancel_event)
        self.assertFalse(res.success)
        self.assertTrue(res.is_cancelled)
        self.assertEqual(self.state.status, SERAStatus.TASK_CANCELLED)

    async def test_executor_timeout(self):
        """Test hard timeout enforcement halts task safely."""
        mock_tools = MagicMock()
        async def slow_exec(*args, **kwargs):
            await asyncio.sleep(0.1)
            return {"success": True, "verified": True}
        mock_tools.execute = slow_exec

        executor = MultiStepExecutor(
            tools=mock_tools,
            state=self.state,
            max_task_time_seconds=0.05,  # 50ms timeout
        )

        plan = TaskPlan(
            task="Timed out task",
            steps=[
                PlanStep(id=1, goal="Step 1", action="click_ui_element", verification="control_state_change"),
                PlanStep(id=2, goal="Step 2", action="click_ui_element", verification="control_state_change"),
            ],
        )

        res = await executor.execute(plan)
        self.assertFalse(res.success)
        self.assertIn("timed out", res.summary_message.lower())
        self.assertEqual(self.state.status, SERAStatus.TASK_FAILED)

    async def test_executor_recovery_retry(self):
        """Test recovery retry when step initially fails then succeeds."""
        mock_tools = MagicMock()
        call_count = 0
        async def flaky_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"success": False, "reason": "UI element not found initially"}
            return {"success": True, "verified": True}
        mock_tools.execute = flaky_exec

        executor = MultiStepExecutor(
            tools=mock_tools,
            state=self.state,
            max_retries_per_step=2,
        )

        plan = TaskPlan(
            task="Recovery task",
            steps=[
                PlanStep(id=1, goal="Recoverable Step", action="click_ui_element", verification="control_state_change"),
            ],
        )

        res = await executor.execute(plan)
        self.assertTrue(res.success)
        self.assertEqual(res.steps_completed, 1)
        self.assertEqual(call_count, 2)


if __name__ == "__main__":
    unittest.main()
