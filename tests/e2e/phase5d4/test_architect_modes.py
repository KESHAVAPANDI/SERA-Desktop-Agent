import asyncio
import unittest
from tests.e2e.phase5d4.base_e2e import BasePhase5D4E2ETest


class TestArchitectModesE2E(BasePhase5D4E2ETest):
    port = 8835

    async def test_01_three_execution_modes_switching(self):
        """Validates that Architect supports Primary Only, Fallback Order, and Custom execution modes."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")
        await self.wait_for_client_connected()
        await asyncio.sleep(0.3)

        await self.page.click("#tab-architect")
        await self.page.wait_for_selector("#view-architect", state="visible")
        await asyncio.sleep(0.3)

        # 1. Click Reasoning node to open inspector drawer
        reasoning_node = self.page.locator(".architect-node[data-role='reasoning']").first
        await reasoning_node.click()
        await asyncio.sleep(0.3)

        drawer = self.page.locator("#architect-inspector-drawer")
        self.assertTrue(await drawer.is_visible())

        # 2. Switch to PRIMARY ONLY
        await self.page.click("#btn-role-mode-primary")
        await asyncio.sleep(0.2)

        explanation = await self.page.text_content("#mode-explanation-text")
        self.assertIn("Primary model only", explanation)

        # 3. Switch to FALLBACK ORDER
        await self.page.click("#btn-role-mode-fallback")
        await asyncio.sleep(0.2)

        explanation = await self.page.text_content("#mode-explanation-text")
        self.assertIn("fallback candidates in sequence", explanation)

        # 4. Switch to CUSTOM
        await self.page.click("#btn-role-mode-custom")
        await asyncio.sleep(0.2)

        explanation = await self.page.text_content("#mode-explanation-text")
        self.assertIn("Custom multi-model routing", explanation)

        # Verify dirty indicator is visible
        dirty_badge = self.page.locator("#architect-dirty-badge")
        self.assertTrue(await dirty_badge.is_visible())

        await self.capture_screenshot("05_architect_modes.png")


if __name__ == "__main__":
    unittest.main()
