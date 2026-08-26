import asyncio
import unittest
from tests.e2e.phase5d4.base_e2e import BasePhase5D4E2ETest


class TestLiveWorkflowTaskE2E(BasePhase5D4E2ETest):
    port = 8832

    async def test_01_task_overlay_and_workflow_deeplink(self):
        """Validates Live compact task overlay, current step indicator, and View Workflow deep-linking."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")
        await self.wait_for_client_connected()
        await asyncio.sleep(0.3)

        # 1. Start Task
        task_id = "task_e2e_overlay"
        await self.server.broadcast_event("TASK_STARTED", {
            "task_id": task_id,
            "user_input": "Inspect system health and download drivers",
            "started_at": 1000.0,
        })
        await asyncio.sleep(0.4)

        # Verify compact task overlay is visible
        overlay = self.page.locator("#live-task-overlay")
        self.assertTrue(await overlay.is_visible())

        title = await self.page.text_content("#task-overlay-title")
        self.assertIn("Inspect system health", title)

        # 2. Update tool step
        await self.server.broadcast_event("TOOL_STARTED", {
            "task_id": task_id,
            "tool": "web_search",
            "arguments": {"query": "NVIDIA RTX driver download"},
            "call_id": "call_overlay_1",
        })
        await asyncio.sleep(0.3)

        step_text = await self.page.text_content("#task-overlay-step")
        self.assertIn("Executing web_search", step_text)

        # 3. Click View Workflow button
        await self.page.click("#btn-overlay-workflow")
        await self.page.wait_for_selector("#view-workflow", state="visible")

        # Verify Workflow view is active
        workflow_active = await self.page.locator("#tab-workflow").get_attribute("class")
        self.assertIn("active", workflow_active)

        await self.capture_screenshot("02_live_task_overlay_workflow.png")


if __name__ == "__main__":
    unittest.main()
