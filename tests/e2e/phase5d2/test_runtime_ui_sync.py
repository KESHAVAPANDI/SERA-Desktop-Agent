import asyncio
import unittest
from tests.e2e.phase5d2.base_e2e import BasePhase5D2E2ETest


class TestRuntimeUISync(BasePhase5D2E2ETest):
    port = 8801

    async def test_01_build_id_and_header_telemetry_freshness(self):
        """Verifies Build 5D.2 ID, truthful header telemetry, and screenshot capture."""
        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.page.wait_for_selector("#global-header")
        await asyncio.sleep(0.4)

        # 1. Check Build ID in window and DOM
        build_id = await self.page.evaluate("() => window.SERA_BUILD_ID")
        self.assertEqual(build_id, "5D.2", "Browser served stale build without 5D.2 ID")

        badge_text = await self.page.inner_text("#sera-build-badge")
        self.assertIn("BUILD 5D.2", badge_text)

        # 2. Check Header Telemetry
        wake_text = await self.page.inner_text("#wake-status-text")
        self.assertEqual(wake_text, "WAKE: NOT CONFIGURED")

        stt_text = await self.page.inner_text("#stt-status-text")
        self.assertEqual(stt_text, "STT: FASTER-WHISPER")

        # 3. Capture screenshot
        await self.capture_screenshot("01_runtime_ui_sync.png")


if __name__ == "__main__":
    unittest.main()
