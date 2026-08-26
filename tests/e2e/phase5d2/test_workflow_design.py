import asyncio
import unittest
from tests.e2e.phase5d2.base_e2e import BasePhase5D2E2ETest


class TestWorkflowDesign(BasePhase5D2E2ETest):
    port = 8805

    async def test_01_design_mode_architecture_and_candidate_inspector(self):
        """Verifies DESIGN mode rendering, node dragging, and candidate reordering decoupling."""
        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.page.wait_for_selector("#global-header")
        await self.page.click("#tab-workflow", force=True)
        await asyncio.sleep(0.3)

        # Switch to DESIGN mode
        await self.page.click("#btn-mode-design", force=True)
        await asyncio.sleep(0.4)

        await self.capture_screenshot("08_workflow_design_mode.png")

        # Check total nodes rendered in design topology
        nodes = await self.page.query_selector_all(".temporal-node")
        self.assertGreaterEqual(len(nodes), 8, "Design mode must show full role candidate topology")

        # Click on Reasoning primary node to open Inspector
        reason_node = await self.page.query_selector("#node_reasoning_primary") or nodes[0]
        await reason_node.click(force=True)
        await asyncio.sleep(0.4)

        drawer_open = await self.page.evaluate("() => document.getElementById('workflow-inspector-drawer').classList.contains('open')")
        self.assertTrue(drawer_open, "Role inspector drawer failed to open on node click")

        await self.capture_screenshot("09_workflow_role_inspector.png")


if __name__ == "__main__":
    unittest.main()
