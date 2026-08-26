import asyncio
import unittest
from tests.e2e.phase5d4.base_e2e import BasePhase5D4E2ETest


class TestLiveResponseDeliveryE2E(BasePhase5D4E2ETest):
    port = 8831

    async def test_01_guaranteed_assistant_response_settlement(self):
        """Validates that conversational turns produce guaranteed authoritative assistant messages and settle streaming carets."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")
        await self.wait_for_client_connected()
        await asyncio.sleep(0.3)

        # 1. User submits command
        await self.page.fill("#chat-input", "What are the latest RTX 5090 benchmarks?")
        await self.page.click("button[type='submit']")
        await asyncio.sleep(0.2)

        # 2. Simulate STREAM_TOKEN events
        await self.server.broadcast_event("STREAM_TOKEN", {"token": "RTX 5090 benchmarks show "})
        await self.server.broadcast_event("STREAM_TOKEN", {"token": "a 45% uplift over RTX 4090."})
        await asyncio.sleep(0.3)

        # Verify streaming bubble has text
        stream_bubble = self.page.locator(".chat-bubble.sera")
        self.assertTrue(await stream_bubble.count() >= 1)

        # 3. Authoritative AGENT_RESPONSE event
        await self.server.broadcast_event("AGENT_RESPONSE", {
            "task_id": "task_resp_1",
            "turn_id": "turn_1",
            "message_id": "msg_1",
            "type": "ASSISTANT_MESSAGE",
            "content": "RTX 5090 benchmarks show a 45% uplift over RTX 4090 with 32GB GDDR7 memory.",
            "status": "COMPLETED",
        })
        await asyncio.sleep(0.3)

        # Verify streaming caret is removed and bubble settled
        active_carets = await self.page.locator(".streaming-caret").count()
        self.assertEqual(active_carets, 0)

        last_msg = await self.page.locator(".chat-bubble.sera").last.text_content()
        self.assertIn("32GB GDDR7", last_msg)

        await self.capture_screenshot("01_live_response_settled.png")


if __name__ == "__main__":
    unittest.main()
