import asyncio
import unittest
from tests.e2e.phase5d3.base_e2e import BasePhase5D3E2ETest


class TestLiveSyncE2E(BasePhase5D3E2ETest):
    port = 8824

    async def test_01_live_workflow_shared_task_lifecycle(self):
        """Validates that Live and Workflow share the same task_id, and navigating between them preserves context."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")

        # 1. Start a canonical task
        task_id = "task_sync_99"
        await self.server.broadcast_event("TASK_STARTED", {
            "task_id": task_id,
            "user_input": "Open Chrome and search AI models",
            "started_at": 1000.0,
        })
        await asyncio.sleep(0.2)

        # Check task card updated in Live
        task_title = await self.page.text_content("#task-card-title")
        self.assertIn("Open Chrome", task_title)

        # 2. Switch to Workflow tab
        await self.page.click("#tab-workflow")
        await self.page.wait_for_selector("#view-workflow", state="visible")
        
        # Verify workflow mode is EXECUTION
        exec_tab = self.page.locator("#btn-mode-execution")
        exec_class = await exec_tab.get_attribute("class")
        self.assertIn("active", exec_class)

        # 3. Complete Task
        await self.server.broadcast_event("TASK_COMPLETED", {
            "task_id": task_id,
            "result": "Chrome launched and search completed.",
            "duration_seconds": 2.1,
        })
        await asyncio.sleep(0.3)

        # 4. Return to Live
        ret_btn = self.page.locator("#btn-return-to-live")
        if await ret_btn.is_visible():
            await self.page.evaluate("() => document.getElementById('btn-return-to-live').click()")
        else:
            await self.page.click("#tab-live")

        await self.page.wait_for_selector("#view-live", state="visible")
        last_msg = await self.page.locator(".chat-bubble.sera").last.text_content()
        self.assertIn("Chrome launched and search completed", last_msg)

        await self.capture_screenshot("04_live_workflow_sync.png")


if __name__ == "__main__":
    unittest.main()
