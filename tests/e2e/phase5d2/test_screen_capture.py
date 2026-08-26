import asyncio
import unittest
from tests.e2e.phase5d2.base_e2e import BasePhase5D2E2ETest
from app.utils.security import SecurityManager


class TestScreenCapture(BasePhase5D2E2ETest):
    port = 8806

    async def test_01_security_policy_authorizes_capture_screen(self):
        """Verifies SecurityManager permits capture_screen and perception events materialize in UI."""
        # 1. Verify backend SecurityManager check
        sm = SecurityManager()
        decision = sm.check("capture_screen")
        self.assertTrue(decision.allowed, "Security policy blocked capture_screen")
        self.assertFalse(decision.requires_confirmation)

        # 2. Verify UI perception event rendering
        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.page.wait_for_selector("#global-header")
        await self.page.click("#tab-workflow", force=True)
        await asyncio.sleep(0.3)

        await self.server.broadcast_event("TASK_STARTED", {
            "task_id": "task_screen_1",
            "user_input": "Take a screenshot",
        })
        await self.server.broadcast_event("SCREEN_CAPTURE_STARTED", {})
        await asyncio.sleep(0.4)

        has_vision = await self.page.evaluate("() => Boolean(document.getElementById('node_vision'))")
        self.assertTrue(has_vision, "Perception node failed to materialize on SCREEN_CAPTURE_STARTED")

        await self.capture_screenshot("10_screen_capture_pipeline.png")


if __name__ == "__main__":
    unittest.main()
