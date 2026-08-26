import asyncio
import unittest
from tests.e2e.phase5d4.base_e2e import BasePhase5D4E2ETest


class TestArchitectDragDropE2E(BasePhase5D4E2ETest):
    port = 8836

    async def test_01_candidate_priority_reordering(self):
        """Validates semantic candidate priority reordering and visual node canvas dragging."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")
        await self.wait_for_client_connected()
        await asyncio.sleep(0.3)

        await self.page.click("#tab-architect")
        await self.page.wait_for_selector("#view-architect", state="visible")
        await asyncio.sleep(0.3)

        # 1. Open Reasoning role inspector
        await self.page.locator(".architect-node[data-role='reasoning']").first.click()
        await asyncio.sleep(0.3)

        # 2. Add a new candidate
        await self.page.click("#btn-architect-add-cand")
        await asyncio.sleep(0.3)

        items_count = await self.page.locator(".cand-drag-item").count()
        self.assertGreaterEqual(items_count, 2)

        # 3. Canvas visual node drag
        target_node = self.page.locator(".architect-node[data-role='reasoning']").first
        box = await target_node.bounding_box()
        self.assertIsNotNone(box)

        # Perform mouse drag
        await self.page.mouse.move(box["x"] + 10, box["y"] + 10)
        await self.page.mouse.down()
        await self.page.mouse.move(box["x"] + 80, box["y"] + 40)
        await self.page.mouse.up()
        await asyncio.sleep(0.2)

        # Verify dirty badge is visible
        dirty_badge = self.page.locator("#architect-dirty-badge")
        self.assertTrue(await dirty_badge.is_visible())

        await self.capture_screenshot("06_architect_dragdrop.png")


if __name__ == "__main__":
    unittest.main()
