import asyncio
import unittest
from tests.e2e.phase5d2.base_e2e import BasePhase5D2E2ETest


class TestWorkflowExecution(BasePhase5D2E2ETest):
    port = 8804

    async def test_01_execution_graph_materialization_and_return_to_live(self):
        """Verifies step-by-step materialization: STT -> Router -> Model -> Tool -> Completed Banner -> Return to Live."""
        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.page.wait_for_selector("#global-header")
        await self.page.click("#tab-workflow", force=True)
        await asyncio.sleep(0.4)

        # 1. Start Task -> Materializes STT & Router nodes
        await self.server.broadcast_event("TASK_STARTED", {
            "task_id": "task_exec_1",
            "user_input": "Open Chrome and search benchmarks",
            "started_at": 100.0,
        })
        await asyncio.sleep(0.3)

        has_stt = await self.page.evaluate("() => Boolean(document.getElementById('node_stt'))")
        has_router = await self.page.evaluate("() => Boolean(document.getElementById('node_router'))")
        self.assertTrue(has_stt, "Missing STT node in execution graph")
        self.assertTrue(has_router, "Missing Router node in execution graph")

        await self.capture_screenshot("05_workflow_exec_started.png")

        # 2. Model Selection -> Materializes Model Node
        await self.server.broadcast_event("MODEL_SELECTED", {
            "role": "reasoning",
            "provider": "groq",
            "model": "openai/gpt-oss-120b",
        })
        await asyncio.sleep(0.3)

        has_model = await self.page.evaluate("() => Boolean(document.getElementById('node_model_groq'))")
        self.assertTrue(has_model, "Missing dynamically materialized model node")

        # 3. Tool Execution -> Materializes Tool Node
        await self.server.broadcast_event("TOOL_STARTED", {"tool": "open_application"})
        await asyncio.sleep(0.3)

        has_tool = await self.page.evaluate("() => Boolean(document.getElementById('node_tool_open_application'))")
        self.assertTrue(has_tool, "Missing dynamically materialized tool node")

        await self.capture_screenshot("06_workflow_exec_progress.png")

        # 4. Task Completed -> All settled & Banner with Return to Live appears
        await self.server.broadcast_event("TASK_COMPLETED", {
            "task_id": "task_exec_1",
            "result": "Chrome search completed.",
            "duration_seconds": 0.58,
        })
        await asyncio.sleep(0.4)

        banner_visible = await self.page.evaluate("() => !document.getElementById('workflow-execution-banner').classList.contains('hidden')")
        self.assertTrue(banner_visible, "Execution completion banner failed to appear")

        await self.capture_screenshot("07_workflow_exec_completed_banner.png")

        # 5. Click RETURN TO LIVE button -> Navigates to Live view
        await self.page.evaluate("() => document.getElementById('btn-return-to-live').click()")
        await asyncio.sleep(0.4)

        is_live_active = await self.page.evaluate("() => document.getElementById('view-live').classList.contains('active')")
        self.assertTrue(is_live_active, "Failed to navigate back to LIVE on clicking RETURN TO LIVE")


if __name__ == "__main__":
    unittest.main()
