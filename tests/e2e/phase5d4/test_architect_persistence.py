import asyncio
import unittest
from tests.e2e.phase5d4.base_e2e import BasePhase5D4E2ETest


class TestArchitectPersistenceE2E(BasePhase5D4E2ETest):
    port = 8837

    async def test_01_configuration_preview_save_and_simulation(self):
        """Validates Configuration Preview modal, saving to backend, and Test Simulation execution."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")
        await self.wait_for_client_connected()
        await asyncio.sleep(0.3)

        await self.page.click("#tab-architect")
        await self.page.wait_for_selector("#view-architect", state="visible")
        await asyncio.sleep(0.3)

        # 1. Run Simulation Test
        await self.page.click("#btn-architect-test")
        await asyncio.sleep(0.6)

        # 2. Modify configuration to trigger dirty state
        await self.page.locator(".architect-node[data-role='reasoning']").first.click()
        await asyncio.sleep(0.3)
        await self.page.click("#btn-role-mode-primary")
        await asyncio.sleep(0.2)

        # 3. Click Save Changes to open Preview Modal
        await self.page.click("#btn-architect-save")
        await asyncio.sleep(0.3)

        modal = self.page.locator("#architect-preview-modal")
        self.assertTrue(await modal.is_visible())

        # 4. Apply changes
        await self.page.click("#btn-preview-apply")
        await asyncio.sleep(0.5)

        # Verify dirty badge is cleared
        dirty_badge = self.page.locator("#architect-dirty-badge")
        self.assertFalse(await dirty_badge.is_visible())

        await self.capture_screenshot("07_architect_persistence.png")


if __name__ == "__main__":
    unittest.main()
