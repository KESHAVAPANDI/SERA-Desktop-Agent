"""
SERA 2.0 — Comprehensive Test Suite for Phase 3A Stateful Graph Runtime Foundation.

Validates all 14 mandatory graph architecture requirements:
1. Simple successful execution (Perceive -> Normalize -> Route -> Execute -> Verify -> Respond -> Done)
2. Verification failure (Execute -> Verify -> Failure -> Retry/Replan)
3. Cancellation awareness (Cancellation at node boundaries, clean abort)
4. Bounded retries (Loop terminates within safety bounds)
5. Conditional transitions (Branching based on verification)
6. Multi-step state continuity (Step 1 state persists into Step 2)
7. Execution correlation (All events carry identical execution_id & task_id)
8. Deduplication / Zero duplicate lifecycle events
9. Simple command bypass (Fast-path bypasses LLM planner)
10. Observation vs. Verification separation
11. Model failure handling (Structured recovery without crashing runtime)
12. Tool failure handling (Tool exception converted to structured failure)
13. Timeout handling (Enforces hard execution safety budget)
14. State snapshot / serialization & deserialization
"""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.events import EventBus
from app.core.graph import (
    ErrorCategory,
    GraphDecision,
    GraphExecutionStatus,
    GraphNode,
    GraphObservation,
    GraphPlanStep,
    GraphState,
    GraphVerification,
    NodeResult,
    StatefulGraphRuntime,
    create_default_graph_runtime,
)
from app.core.verification import EvidenceRecord, EvidenceType, EvidenceVerificationFabric
from app.tools.base import Tool
from app.tools.registry import ToolRegistry


class DummySuccessTool(Tool):
    """Dummy tool returning immediate verified success."""
    def __init__(self, tool_name: str = "dummy_success"):
        self._name = tool_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Test tool returning success"

    @property
    def parameters(self) -> dict:
        return {}

    async def execute(self, **kwargs):
        return {
            "success": True,
            "application": kwargs.get("application", "chrome"),
            "verified": True,
            "dimensions": "1920x1080",
            "image": "mock_buffer",
        }


class DummyFailingTool(Tool):
    """Dummy tool returning failure."""
    def __init__(self, tool_name: str = "dummy_fail"):
        self._name = tool_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Test tool returning failure"

    @property
    def parameters(self) -> dict:
        return {}

    async def execute(self, **kwargs):
        return {"success": False, "error": "Simulated tool failure", "verified": False}


class DummyCrashTool(Tool):
    """Dummy tool raising an unexpected Python exception."""
    def __init__(self, tool_name: str = "dummy_crash"):
        self._name = tool_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Test tool raising exception"

    @property
    def parameters(self) -> dict:
        return {}

    async def execute(self, **kwargs):
        raise RuntimeError("Simulated internal driver crash")


class DummySlowTool(Tool):
    """Dummy tool sleeping to test timeouts and cancellation."""
    def __init__(self, tool_name: str = "dummy_slow"):
        self._name = tool_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Test tool with long sleep"

    @property
    def parameters(self) -> dict:
        return {}

    async def execute(self, **kwargs):
        await asyncio.sleep(10.0)
        return {"success": True}



class TestStatefulGraphRuntime(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.event_bus = EventBus()
        self.tools = ToolRegistry()
        self.tools.register(DummySuccessTool("open_application"))
        self.tools.register(DummySuccessTool("set_brightness"))
        self.tools.register(DummySuccessTool("capture_screen"))
        self.tools.register(DummyFailingTool("failing_tool"))
        self.tools.register(DummyCrashTool("crash_tool"))
        self.tools.register(DummySlowTool("slow_tool"))

        # Fabric with mocked process check
        self.fabric = EvidenceVerificationFabric()
        self.fabric.verify_process = MagicMock(return_value=EvidenceRecord(
            evidence_type=EvidenceType.PROCESS_RUNNING,
            verified=True,
            source="mock_kernel",
            details={"target_process": "chrome"},
        ))

        self.runtime = create_default_graph_runtime(
            tools=self.tools,
            event_bus=self.event_bus,
            fabric=self.fabric,
            max_retries_per_step=2,
        )

    # -------------------------------------------------------------
    # TEST 1: Simple Successful Execution
    # -------------------------------------------------------------
    async def test_01_simple_successful_execution(self):
        state = GraphState(raw_user_input="Open Chrome")
        result_state = await self.runtime.execute(state)

        self.assertEqual(result_state.status, GraphExecutionStatus.SUCCESS)
        self.assertTrue(result_state.verification.verified)
        self.assertEqual(result_state.current_phase, "COMPLETED")
        self.assertIn("opened Chrome", result_state.final_response)
        self.assertIn("PERCEIVE", result_state.node_timings)
        self.assertIn("NORMALIZE", result_state.node_timings)
        self.assertIn("ROUTE", result_state.node_timings)
        self.assertIn("EXECUTE", result_state.node_timings)
        self.assertIn("VERIFY", result_state.node_timings)
        self.assertIn("RESPOND", result_state.node_timings)

    # -------------------------------------------------------------
    # TEST 2: Verification Failure & Bounded Recovery
    # -------------------------------------------------------------
    async def test_02_verification_failure_triggers_recovery(self):
        # Configure tool to succeed locally, but fabric to fail verification
        self.tools.register(DummySuccessTool("unverifiable_tool"))
        fail_record = EvidenceRecord(
            evidence_type=EvidenceType.GENERIC,
            verified=False,
            source="test",
            failure_reason="Target side effect not detected",
        )
        self.fabric.verify_tool_execution = MagicMock(return_value=fail_record)

        engine = StatefulGraphRuntime(event_bus=self.event_bus, max_retries_per_step=2)
        from app.core.graph.nodes.execute import ExecuteNode
        from app.core.graph.nodes.observe import ObserveNode
        from app.core.graph.nodes.verify import VerifyNode
        from app.core.graph.nodes.decide import DecideNode
        from app.core.graph.nodes.recover import RecoverNode
        from app.core.graph.nodes.respond import RespondNode

        engine.register_node(ExecuteNode(self.tools))
        engine.register_node(ObserveNode())
        engine.register_node(VerifyNode(self.fabric))
        engine.register_node(DecideNode())
        engine.register_node(RecoverNode(backoff_seconds=0.01))
        engine.register_node(RespondNode())

        engine.add_edge("EXECUTE", "OBSERVE")
        engine.add_edge("OBSERVE", "VERIFY")
        engine.add_edge("VERIFY", "DECIDE")
        engine.add_edge("RECOVER", "EXECUTE")
        engine.set_start_node("EXECUTE")

        state = GraphState(raw_user_input="test")
        state.steps = [GraphPlanStep(step_id=1, goal="test", action="unverifiable_tool")]

        result_state = await engine.execute(state)

        # Should attempt retries up to max_retries_per_step and then FAIL
        self.assertEqual(result_state.status, GraphExecutionStatus.FAILED)
        self.assertEqual(result_state.retry_count, 2)
        self.assertIn("Target side effect not detected", str(result_state.last_error))

    # -------------------------------------------------------------
    # TEST 3: Cancellation Awareness
    # -------------------------------------------------------------
    async def test_03_cancellation_halts_graph_immediately(self):
        cancel_evt = asyncio.Event()

        state = GraphState(raw_user_input="Slow task")
        state.steps = [GraphPlanStep(step_id=1, goal="slow", action="slow_tool", timeout_seconds=15.0)]

        # Trigger cancellation after 50ms
        async def trigger_cancel():
            await asyncio.sleep(0.05)
            cancel_evt.set()

        asyncio.create_task(trigger_cancel())

        t0 = time.time()
        result_state = await self.runtime.execute(state, cancellation_event=cancel_evt)
        duration = time.time() - t0

        self.assertEqual(result_state.status, GraphExecutionStatus.CANCELLED)
        self.assertTrue(result_state.is_cancelled)
        self.assertLess(duration, 2.0, "Graph failed to interrupt immediately on cancellation")

    # -------------------------------------------------------------
    # TEST 4: Bounded Retries
    # -------------------------------------------------------------
    async def test_04_bounded_retries_terminates_gracefully(self):
        engine = StatefulGraphRuntime(event_bus=self.event_bus, max_loop_iterations=10)

        # Custom failing node that requests RETRY unconditionally
        class AlwaysRetryNode(GraphNode):
            def __init__(self):
                super().__init__("LOOPY")
                self.count = 0
            async def execute(self, state, cancellation_event=None):
                self.count += 1
                return NodeResult.continue_to("LOOPY", state)

        node = AlwaysRetryNode()
        engine.register_node(node)
        engine.set_start_node("LOOPY")

        state = GraphState(raw_user_input="infinite loop test")
        res_state = await engine.execute(state)

        self.assertEqual(res_state.status, GraphExecutionStatus.FAILED)
        self.assertEqual(node.count, 10)
        self.assertIn("maximum loop iterations", str(res_state.last_error))

    # -------------------------------------------------------------
    # TEST 5: Conditional Transitions
    # -------------------------------------------------------------
    async def test_05_conditional_transition_branching(self):
        engine = StatefulGraphRuntime(event_bus=self.event_bus)

        class BranchNode(GraphNode):
            def __init__(self):
                super().__init__("BRANCH")
            async def execute(self, state, cancellation_event=None):
                if state.context_state.get("condition") == "A":
                    return NodeResult.continue_to("NODE_A", state)
                return NodeResult.continue_to("NODE_B", state)

        class NodeA(GraphNode):
            def __init__(self):
                super().__init__("NODE_A")
            async def execute(self, state, cancellation_event=None):
                return NodeResult.done(state, final_response="Path A Chosen")

        class NodeB(GraphNode):
            def __init__(self):
                super().__init__("NODE_B")
            async def execute(self, state, cancellation_event=None):
                return NodeResult.done(state, final_response="Path B Chosen")

        engine.register_node(BranchNode())
        engine.register_node(NodeA())
        engine.register_node(NodeB())
        engine.set_start_node("BRANCH")

        state_a = GraphState(raw_user_input="test", context_state={"condition": "A"})
        res_a = await engine.execute(state_a)
        self.assertEqual(res_a.final_response, "Path A Chosen")

        state_b = GraphState(raw_user_input="test", context_state={"condition": "B"})
        res_b = await engine.execute(state_b)
        self.assertEqual(res_b.final_response, "Path B Chosen")

    # -------------------------------------------------------------
    # TEST 6: Multi-Step State Continuity
    # -------------------------------------------------------------
    async def test_06_multi_step_state_continuity(self):
        # 2-step compound plan
        state = GraphState(raw_user_input="Set brightness to 80% and open Chrome")
        state.steps = [
            GraphPlanStep(step_id=1, goal="brightness", action="set_brightness", arguments={"brightness": 80}),
            GraphPlanStep(step_id=2, goal="chrome", action="open_application", arguments={"application": "chrome"}),
        ]

        result_state = await self.runtime.execute(state)

        self.assertEqual(result_state.status, GraphExecutionStatus.SUCCESS)
        self.assertEqual(result_state.completed_steps, [1, 2])
        self.assertEqual(result_state.context_state.get("last_brightness"), 80)
        self.assertEqual(result_state.active_application, "chrome")
        self.assertEqual(result_state.task_progress, 1.0)

    # -------------------------------------------------------------
    # TEST 7: Execution Correlation
    # -------------------------------------------------------------
    async def test_07_event_correlation(self):
        received_events = []
        for ev in ["GRAPH_STARTED", "GRAPH_NODE_ENTERED", "GRAPH_NODE_COMPLETED", "GRAPH_TRANSITION", "GRAPH_COMPLETED"]:
            self.event_bus.subscribe(ev, lambda payload: received_events.append(payload))

        state = GraphState(raw_user_input="Set brightness to 50%")
        res_state = await self.runtime.execute(state)

        self.assertEqual(res_state.status, GraphExecutionStatus.SUCCESS)
        self.assertGreater(len(received_events), 4)

        # Every event must correlate to identical execution_id and task_id
        for ev in received_events:
            self.assertEqual(ev["execution_id"], res_state.execution_id)
            self.assertEqual(ev["task_id"], res_state.task_id)

    # -------------------------------------------------------------
    # TEST 8: Zero Duplicate Lifecycle Events
    # -------------------------------------------------------------
    async def test_08_no_duplicate_lifecycle_events(self):
        started_events = []
        completed_events = []
        self.event_bus.subscribe("GRAPH_STARTED", lambda p: started_events.append(p))
        self.event_bus.subscribe("GRAPH_COMPLETED", lambda p: completed_events.append(p))

        state = GraphState(raw_user_input="Open Chrome")
        await self.runtime.execute(state)

        self.assertEqual(len(started_events), 1, "Duplicate GRAPH_STARTED events emitted")
        self.assertEqual(len(completed_events), 1, "Duplicate GRAPH_COMPLETED events emitted")

    # -------------------------------------------------------------
    # TEST 9: Simple Command Fast-Path Bypass
    # -------------------------------------------------------------
    async def test_09_simple_command_fast_path_bypass(self):
        mock_router = MagicMock()
        mock_router.generate_with_fallback = AsyncMock()

        runtime = create_default_graph_runtime(
            tools=self.tools,
            router=mock_router,
            event_bus=self.event_bus,
            fabric=self.fabric,
        )

        state = GraphState(raw_user_input="Take a screenshot")
        res_state = await runtime.execute(state)

        self.assertEqual(res_state.status, GraphExecutionStatus.SUCCESS)
        self.assertEqual(res_state.selected_route, "FAST_PATH")
        # LLM reasoning router must NEVER be called for deterministic commands
        mock_router.generate_with_fallback.assert_not_called()

    # -------------------------------------------------------------
    # TEST 10: Observation vs. Verification Separation
    # -------------------------------------------------------------
    async def test_10_observation_vs_verification_separation(self):
        state = GraphState(raw_user_input="Open Chrome")
        res_state = await self.runtime.execute(state)

        self.assertIsNotNone(res_state.observation)
        self.assertIsNotNone(res_state.verification)

        # Observation contains raw output and observed state
        self.assertIsInstance(res_state.observation, GraphObservation)
        self.assertEqual(res_state.observation.action_name, "open_application")
        self.assertIn("application", res_state.observation.observed_state)

        # Verification contains empirical side-effect validation
        self.assertIsInstance(res_state.verification, GraphVerification)
        self.assertTrue(res_state.verification.verified)
        self.assertEqual(res_state.verification.source, "mock_kernel")

    # -------------------------------------------------------------
    # TEST 11: Model Failure Handling
    # -------------------------------------------------------------
    async def test_11_model_failure_handled_gracefully(self):
        mock_router = MagicMock()
        mock_router.generate_with_fallback = AsyncMock(side_effect=ConnectionError("Model provider rate limit 429"))

        runtime = create_default_graph_runtime(
            tools=self.tools,
            router=mock_router,
            event_bus=self.event_bus,
            fabric=self.fabric,
        )

        # Ambiguous query that invokes reasoning
        state = GraphState(raw_user_input="Compose an elaborate sonnet about quantum thermodynamics")
        res_state = await runtime.execute(state)

        self.assertEqual(res_state.status, GraphExecutionStatus.FAILED)
        self.assertIn("Model provider rate limit 429", str(res_state.last_error))

    # -------------------------------------------------------------
    # TEST 12: Tool Failure Handling
    # -------------------------------------------------------------
    async def test_12_tool_failure_handled_gracefully(self):
        state = GraphState(raw_user_input="Test crash")
        state.steps = [GraphPlanStep(step_id=1, goal="crash", action="crash_tool")]

        res_state = await self.runtime.execute(state)

        self.assertEqual(res_state.status, GraphExecutionStatus.FAILED)
        self.assertIn("Simulated internal driver crash", str(res_state.last_error))

    # -------------------------------------------------------------
    # TEST 13: Execution Timeout
    # -------------------------------------------------------------
    async def test_13_execution_timeout(self):
        state = GraphState(raw_user_input="Slow task")
        state.steps = [GraphPlanStep(step_id=1, goal="slow", action="slow_tool", timeout_seconds=20.0)]

        # Hard overall graph timeout of 0.1s
        res_state = await self.runtime.execute(state, timeout_seconds=0.1)

        self.assertEqual(res_state.status, GraphExecutionStatus.FAILED)
        self.assertEqual(res_state.completion_reason, "TIMEOUT")

    # -------------------------------------------------------------
    # TEST 14: State Snapshot & Deserialization
    # -------------------------------------------------------------
    def test_14_state_snapshot_serialization_and_restoration(self):
        state = GraphState(
            raw_user_input="Search YouTube for coding videos",
            normalized_user_input="search youtube for coding videos",
            current_objective="YouTube search",
            active_application="chrome",
            selected_route="FAST_PATH",
            steps=[
                GraphPlanStep(step_id=1, goal="search", action="youtube_search", arguments={"query": "coding"}),
            ],
            context_state={"last_brightness": 80},
        )
        state.observation = GraphObservation(action_name="youtube_search", raw_output={"count": 5}, summary="5 videos")
        state.verification = GraphVerification(verified=True, evidence_type="STRUCTURED_DATA", source="browser")
        state.record_node_timing("PERCEIVE", 0.45)

        # Snapshot
        snapshot_dict = self.runtime.snapshot(state)
        self.assertIsInstance(snapshot_dict, dict)
        self.assertEqual(snapshot_dict["execution_id"], state.execution_id)

        # Restore
        restored = self.runtime.restore(state.execution_id)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.execution_id, state.execution_id)
        self.assertEqual(restored.current_objective, "YouTube search")
        self.assertEqual(restored.active_application, "chrome")
        self.assertEqual(len(restored.steps), 1)
        self.assertEqual(restored.steps[0].action, "youtube_search")
        self.assertEqual(restored.context_state["last_brightness"], 80)
        self.assertEqual(restored.observation.summary, "5 videos")
        self.assertTrue(restored.verification.verified)
        self.assertEqual(restored.node_timings["PERCEIVE"], 0.45)


if __name__ == "__main__":
    unittest.main()
