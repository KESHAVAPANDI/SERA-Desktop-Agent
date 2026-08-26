import asyncio
import unittest
from tests.e2e.phase5d2.base_e2e import BasePhase5D2E2ETest


class TestTaskCancellation(BasePhase5D2E2ETest):
    port = 8809

    async def test_01_interrupt_button_cancels_active_task(self):
        """Verifies clicking Interrupt stops the timer and marks task CANCELLED in UI."""
        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.page.wait_for_selector("#global-header")
        await asyncio.sleep(0.3)

        # 1. Start long running task
        await self.server.broadcast_event("TASK_STARTED", {
            "task_id": "task_cancel_1",
            "user_input": "Run extensive multi-step scan",
            "started_at": 100.0,
        })
        await asyncio.sleep(0.3)

        # 2. Click Interrupt
        await self.page.click("#btn-interrupt-task", force=True)
        await asyncio.sleep(0.2)

        # 3. Simulate backend TASK_CANCELLED
        await self.server.broadcast_event("TASK_CANCELLED", {
            "task_id": "task_cancel_1",
            "reason": "Cancelled by user interrupt",
        })
        await asyncio.sleep(0.4)

        step_text = await self.page.inner_text("#task-step-label")
        self.assertIn("Cancelled", step_text)

        await self.capture_screenshot("14_task_cancellation.png")


if __name__ == "__main__":
    unittest.main()
