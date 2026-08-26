import asyncio
import unittest
from tests.e2e.phase5d3.base_e2e import BasePhase5D3E2ETest


class TestLiveCapabilitiesE2E(BasePhase5D3E2ETest):
    port = 8823

    async def test_01_data_driven_contextual_capabilities(self):
        """Validates that capabilities are fetched dynamically from the CapabilityRegistry and filter by context."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")

        # 1. Initial idle capabilities loaded
        await self.page.wait_for_selector(".quick-chip-btn", state="visible", timeout=5000)
        chips = await self.page.locator(".quick-chip-btn").all_text_contents()
        self.assertTrue(any("Capture Screen" in c for c in chips))
        self.assertTrue(any("Web Search" in c for c in chips))

        # 2. Click a chip -> Appends user message and triggers task
        capture_btn = self.page.locator(".quick-chip-btn", has_text="Capture Screen")
        await capture_btn.click()

        await self.page.wait_for_selector(".chat-bubble.user", state="visible", timeout=5000)
        user_msg = await self.page.locator(".chat-bubble.user").last.text_content()
        self.assertIn("Take a screenshot", user_msg)

        # 3. Dynamic capabilities update via WS
        await self.server.broadcast_event("CAPABILITIES_LIST", {
            "capabilities": [
                {"id": "c1", "label": "Analyze Screen", "icon": "🔍", "prompt_template": "Analyze the active screen"},
                {"id": "c2", "label": "Search Current Page", "icon": "🔎", "prompt_template": "Search this page"},
            ]
        })
        await asyncio.sleep(0.2)

        new_chips = await self.page.locator(".quick-chip-btn").all_text_contents()
        self.assertTrue(any("Analyze Screen" in c for c in new_chips))
        self.assertTrue(any("Search Current Page" in c for c in new_chips))

        await self.capture_screenshot("03_live_capabilities_registry.png")


if __name__ == "__main__":
    unittest.main()
