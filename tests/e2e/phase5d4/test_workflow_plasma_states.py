import asyncio
import unittest
from tests.e2e.phase5d4.base_e2e import BasePhase5D4E2ETest


class TestWorkflowPlasmaStatesE2E(BasePhase5D4E2ETest):
    port = 8834

    async def test_01_plasma_fallback_and_cancellation(self):
        """Validates fallback ignition, rate-limiting fracture, and cancellation collapse."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")
        await self.wait_for_client_connected()
        await asyncio.sleep(0.3)

        await self.page.click("#tab-workflow")
        await self.page.wait_for_selector("#view-workflow", state="visible")
        await asyncio.sleep(0.2)

        # 1. Start Task
        task_id = "task_plasma_fallback"
        await self.server.broadcast_event("TASK_STARTED", {
            "task_id": task_id,
            "user_input": "Summarize latest research paper",
        })
        await asyncio.sleep(0.5)

        # 2. Select Model
        await self.server.broadcast_event("MODEL_SELECTED", {
            "task_id": task_id,
            "role": "reasoning",
            "provider": "Groq",
            "model": "gpt-oss-120b",
        })
        await asyncio.sleep(0.3)

        # 3. Model Fallback due to Rate-Limiting
        await self.server.broadcast_event("MODEL_FALLBACK", {
            "task_id": task_id,
            "role": "reasoning",
            "provider": "Mistral",
            "model": "mistral-large-2411",
            "reason": "429 Rate limit exceeded on primary",
        })
        await asyncio.sleep(0.4)

        # Verify fallback node materialized
        fallback_node = self.page.locator("#node_model_reasoning_fallback")
        self.assertTrue(await fallback_node.is_visible())

        # Verify primary node has rate-limited fracture state
        primary_node = self.page.locator("#node_model_reasoning")
        primary_class = await primary_node.get_attribute("class")
        self.assertIn("rate-limited", primary_class)

        # 4. Cancel Task
        await self.server.broadcast_event("TASK_CANCELLED", {
            "task_id": task_id,
            "reason": "User interrupted",
        })
        await asyncio.sleep(0.4)

        # Verify theatre canvas marked cancelled
        container_class = await self.page.locator("#workflow-canvas").get_attribute("class")
        self.assertIn("cancelled", container_class)

        await self.capture_screenshot("04_workflow_plasma_states.png")


if __name__ == "__main__":
    unittest.main()
