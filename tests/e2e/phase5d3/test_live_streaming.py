import asyncio
import unittest
from tests.e2e.phase5d3.base_e2e import BasePhase5D3E2ETest


class TestLiveStreamingE2E(BasePhase5D3E2ETest):
    port = 8825

    async def test_01_token_streaming_and_settlement(self):
        """Validates that incremental tokens stream into the active assistant bubble with blinking caret and settle."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")

        # 1. Stream tokens incrementally
        tokens = ["SERA ", "is ", "analyzing ", "your ", "desktop ", "environment."]
        for t in tokens:
            await self.server.broadcast_event("STREAM_TOKEN", {"token": t})
            await asyncio.sleep(0.05)

        # Check streaming bubble active
        await self.page.wait_for_selector(".chat-bubble.sera.streaming-active", state="visible", timeout=5000)
        stream_text = await self.page.text_content(".chat-bubble.sera.streaming-active .stream-text")
        self.assertIn("SERA is analyzing", stream_text)

        # Caret is visible during streaming
        caret = self.page.locator(".streaming-caret")
        self.assertTrue(await caret.is_visible())

        # 2. Complete Agent Response
        await self.server.broadcast_event("AGENT_RESPONSE", {"text": "SERA is analyzing your desktop environment."})
        await asyncio.sleep(0.2)

        # Caret is removed and bubble becomes stable
        caret_count = await self.page.locator(".streaming-caret").count()
        self.assertEqual(caret_count, 0)

        final_text = await self.page.locator(".chat-bubble.sera").last.text_content()
        self.assertIn("desktop environment", final_text)

        await self.capture_screenshot("05_live_streaming_response.png")


if __name__ == "__main__":
    unittest.main()
