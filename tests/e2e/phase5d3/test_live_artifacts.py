import asyncio
import unittest
from tests.e2e.phase5d3.base_e2e import BasePhase5D3E2ETest


class TestLiveArtifactsE2E(BasePhase5D3E2ETest):
    port = 8821

    async def test_01_inline_work_cards_and_artifacts(self):
        """Validates that tool actions render inline work cards, web search results, and screen capture previews."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")

        # 1. Trigger Web Search tool lifecycle event
        await self.server.broadcast_event("TOOL_STARTED", {
            "tool": "web_search",
            "arguments": {"query": "RTX 5090 benchmarks"},
            "call_id": "call_search_1",
        })

        await self.page.wait_for_selector("#call_search_1", state="visible", timeout=5000)
        card_text = await self.page.text_content("#call_search_1")
        self.assertIn("WEB SEARCH", card_text)
        self.assertIn("RTX 5090 benchmarks", card_text)

        # 2. Complete Web Search with Artifacts (results + sources)
        await self.server.broadcast_event("TOOL_COMPLETED", {
            "tool": "web_search",
            "call_id": "call_search_1",
            "latency_ms": 320,
            "result": {
                "results": [
                    {"title": "RTX 5090 Review", "url": "https://techpowerup.com/review/rtx-5090", "snippet": "32GB GDDR7 flagship benchmarks and raster performance.", "domain": "techpowerup.com"},
                    {"title": "NVIDIA GeForce RTX 5090 Tested", "url": "https://tomshardware.com/rtx-5090", "snippet": "Detailed power, ray tracing, and compute analysis.", "domain": "tomshardware.com"},
                ],
                "sources": ["TechPowerUp", "Tom's Hardware", "NVIDIA Official"],
            }
        })

        await self.page.wait_for_selector(".artifact-web-grid", state="visible", timeout=5000)
        await self.page.wait_for_selector(".artifact-sources-row", state="visible", timeout=5000)

        # 3. Trigger and complete Screen Capture artifact
        await self.server.broadcast_event("SCREEN_CAPTURE_STARTED", {"call_id": "call_screen_1"})
        await self.server.broadcast_event("SCREEN_CAPTURED", {
            "call_id": "call_screen_1",
            "width": 1920,
            "height": 1080,
            "resolution": "1920×1080",
        })

        await self.page.wait_for_selector(".artifact-screenshot-box", state="visible", timeout=5000)
        screen_badge = await self.page.text_content(".screenshot-meta-badge")
        self.assertIn("1920×1080", screen_badge)

        await self.capture_screenshot("01_live_artifacts_stream.png")


if __name__ == "__main__":
    unittest.main()
