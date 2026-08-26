import asyncio
import unittest
from tests.e2e.phase5d3.base_e2e import BasePhase5D3E2ETest


class TestLiveInterruptE2E(BasePhase5D3E2ETest):
    port = 8822

    async def test_01_context_aware_interrupt_states_and_cancellation(self):
        """Validates that the interrupt button updates text and classes dynamically and cancels running tasks."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")

        # 1. Idle state: button is disabled/idle
        btn = self.page.locator("#btn-interrupt-task")
        btn_class = await btn.get_attribute("class")
        self.assertIn("btn-interrupt-idle", btn_class)

        # 2. Listening state: "Cancel Capture"
        await self.server.broadcast_event("ACTIVATION_STARTED", {"source": "HOTKEY_HOLD", "mode": "HOLD_TO_TALK"})
        await asyncio.sleep(0.2)
        text = await btn.text_content()
        self.assertIn("Cancel Capture", text)

        # 3. Executing state: "Stop Task"
        await self.server.broadcast_event("TASK_STARTED", {"task_id": "task_int_1", "user_input": "Long running test task"})
        await asyncio.sleep(0.2)
        text = await btn.text_content()
        self.assertIn("Stop Task", text)

        # 4. Click Interrupt -> Triggers cancellation and adds inline notice
        await btn.click(force=True)
        await asyncio.sleep(0.2)
        
        # Broadcast TASK_CANCELLED
        await self.server.broadcast_event("TASK_CANCELLED", {"task_id": "task_int_1", "duration_seconds": 1.2})
        await self.page.wait_for_selector(".system-notice-cancelled", state="visible", timeout=5000)
        notice_text = await self.page.text_content(".system-notice-cancelled")
        self.assertIn("Task cancelled by user", notice_text)

        await self.capture_screenshot("02_live_contextual_interrupt.png")


if __name__ == "__main__":
    unittest.main()
