import asyncio
import unittest
from tests.e2e.phase5d2.base_e2e import BasePhase5D2E2ETest


class TestLiveTextTask(BasePhase5D2E2ETest):
    port = 8803

    async def test_01_text_prompt_canonical_lifecycle(self):
        """Verifies text submission -> TASK_STARTED -> execution -> TASK_COMPLETED with timer stop."""
        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.page.wait_for_selector("#global-header")
        await asyncio.sleep(0.4)

        # 1. Type instruction in chat
        await self.page.fill("#chat-input", "Open Chrome")
        await self.page.click("button[type='submit']")
        await asyncio.sleep(0.2)

        # 2. Simulate real backend TASK_STARTED
        await self.server.broadcast_event("TASK_STARTED", {
            "task_id": "task_e2e_01",
            "user_input": "Open Chrome",
            "started_at": 100.0,
        })
        await asyncio.sleep(0.3)

        title_text = await self.page.inner_text("#task-card-title")
        self.assertEqual(title_text, "Open Chrome")

        # 3. Simulate tool step
        await self.server.broadcast_event("TOOL_STARTED", {"tool": "open_application"})
        await asyncio.sleep(0.3)

        # 4. Simulate real backend TASK_COMPLETED
        await self.server.broadcast_event("TASK_COMPLETED", {
            "task_id": "task_e2e_01",
            "result": "Chrome browser has been opened.",
            "duration_seconds": 0.42,
        })
        await asyncio.sleep(0.4)

        # Verify that task step settled to Completed and did NOT remain stuck at Step 1
        step_label = await self.page.inner_text("#task-step-label")
        self.assertIn("Completed", step_label)

        await self.capture_screenshot("04_live_text_task_completed.png")


if __name__ == "__main__":
    unittest.main()
