import asyncio
import unittest
from tests.e2e.phase5d2.base_e2e import BasePhase5D2E2ETest


class TestNavigation(BasePhase5D2E2ETest):
    port = 8808

    async def test_01_primary_and_more_dropdown_navigation(self):
        """Verifies primary tabs (LIVE, WORKFLOW, AGENTS, PROVIDERS) and MORE dropdown views (MEMORY, HISTORY, DEBUG, SECURITY)."""
        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.page.wait_for_selector("#global-header")
        await asyncio.sleep(0.3)

        # 1. Primary Tabs
        views = [
            ("tab-live", "view-live"),
            ("tab-workflow", "view-workflow"),
            ("tab-agents", "view-agents"),
            ("tab-providers", "view-providers"),
        ]

        for tab_id, view_id in views:
            await self.page.click(f"#{tab_id}", force=True)
            await asyncio.sleep(0.2)
            is_active = await self.page.evaluate(f"() => document.getElementById('{view_id}').classList.contains('active')")
            self.assertTrue(is_active, f"Failed to activate view {view_id} via tab #{tab_id}")

        await self.capture_screenshot("12_navigation_providers_tab.png")

        # 2. MORE Dropdown Views
        dropdown_views = [
            ("tab-memory", "view-memory"),
            ("tab-history", "view-history"),
            ("tab-debug", "view-debug"),
            ("tab-security", "view-security"),
        ]

        for item_id, view_id in dropdown_views:
            await self.page.evaluate(f"() => document.getElementById('{item_id}').click()")
            await asyncio.sleep(0.2)
            is_active = await self.page.evaluate(f"() => document.getElementById('{view_id}').classList.contains('active')")
            self.assertTrue(is_active, f"Failed to activate dropdown view {view_id} via #{item_id}")

        await self.capture_screenshot("13_navigation_more_dropdown.png")


if __name__ == "__main__":
    unittest.main()
