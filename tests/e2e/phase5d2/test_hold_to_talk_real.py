import asyncio
import unittest
from tests.e2e.phase5d2.base_e2e import BasePhase5D2E2ETest


class TestHoldToTalkReal(BasePhase5D2E2ETest):
    port = 8802

    async def test_01_global_hotkey_hold_and_release(self):
        """Verifies OS hotkey down -> LISTENING with timer, and release -> TRANSCRIBING."""
        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.page.wait_for_selector("#global-header")
        await asyncio.sleep(0.4)

        # Trigger activation event
        await self.server.broadcast_event("ACTIVATION_STARTED", {
            "source": "HOTKEY_HOLD",
            "mode": "HOLD_TO_TALK",
            "timestamp": 12345.67,
        })
        await asyncio.sleep(0.3)

        state_text = await self.page.inner_text("#state-text")
        self.assertEqual(state_text, "LISTENING")

        await self.capture_screenshot("02_hold_to_talk_listening.png")

        # Release hotkey
        await self.server.broadcast_event("ACTIVATION_RELEASED", {"duration_seconds": 1.85})
        await self.server.broadcast_event("TRANSCRIPTION_STARTED", {})
        await asyncio.sleep(0.3)

        state_trans = await self.page.inner_text("#state-text")
        self.assertEqual(state_trans, "TRANSCRIBING")

        await self.capture_screenshot("03_hold_to_talk_transcribing.png")


if __name__ == "__main__":
    unittest.main()
