import asyncio
import unittest
from tests.e2e.phase5d2.base_e2e import BasePhase5D2E2ETest
from app.utils.security import SecurityManager


class TestBrowserSearch(BasePhase5D2E2ETest):
    port = 8807

    async def test_01_web_search_and_browser_execution(self):
        """Verifies web search tools are permitted by SecurityManager and materialize in execution graph."""
        sm = SecurityManager()
        for tool in ["web_search", "browser_open", "browser_search", "browser_read"]:
            decision = sm.check(tool)
            self.assertTrue(decision.allowed, f"SecurityManager blocked {tool}")

        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.page.wait_for_selector("#global-header")
        await self.page.click("#tab-workflow", force=True)
        await asyncio.sleep(0.3)

        await self.server.broadcast_event("TASK_STARTED", {
            "task_id": "task_web_1",
            "user_input": "Search RTX 5090 benchmarks",
        })
        await self.server.broadcast_event("TOOL_STARTED", {"tool": "web_search"})
        await asyncio.sleep(0.4)

        has_search = await self.page.evaluate("() => Boolean(document.getElementById('node_tool_web_search'))")
        self.assertTrue(has_search, "Tool node for web_search failed to materialize")

        await self.capture_screenshot("11_browser_web_search.png")


if __name__ == "__main__":
    unittest.main()
