import asyncio
import unittest
from tests.e2e.phase5d4.base_e2e import BasePhase5D4E2ETest


class TestWorkflowDynamicGraphE2E(BasePhase5D4E2ETest):
    port = 8833

    async def test_01_dynamic_node_materialization_sequence(self):
        """Validates that Workflow dynamically generates nodes as events occur without preloaded cards."""
        await self.page.goto(self.base_url)
        await self.page.wait_for_selector("#view-live", state="visible")
        await self.wait_for_client_connected()
        await asyncio.sleep(0.3)

        await self.page.click("#tab-workflow")
        await self.page.wait_for_selector("#view-workflow", state="visible")
        await asyncio.sleep(0.2)

        # 1. Initially minimal
        initial_nodes = await self.page.locator(".temporal-theater-node").count()
        self.assertEqual(initial_nodes, 0)

        # 2. TASK_STARTED materializes STT & Router
        task_id = "task_dyn_1"
        await self.server.broadcast_event("TASK_STARTED", {
            "task_id": task_id,
            "user_input": "Find nearest coffee shops",
            "source": "TEXT",
        })
        await asyncio.sleep(0.5)

        node_stt = self.page.locator("#node_stt")
        node_router = self.page.locator("#node_router")
        self.assertTrue(await node_stt.is_visible())
        self.assertTrue(await node_router.is_visible())

        # 3. MODEL_SELECTED materializes Reasoning Model Node
        await self.server.broadcast_event("MODEL_SELECTED", {
            "task_id": task_id,
            "role": "reasoning",
            "provider": "Groq",
            "model": "openai/gpt-oss-120b",
        })
        await asyncio.sleep(0.3)

        model_node = self.page.locator("#node_model_reasoning")
        self.assertTrue(await model_node.is_visible())

        # 4. TOOL_STARTED materializes Tool Node
        await self.server.broadcast_event("TOOL_STARTED", {
            "task_id": task_id,
            "tool": "web_search",
            "arguments": {"query": "coffee shops near me"},
        })
        await asyncio.sleep(0.3)

        tool_nodes = await self.page.locator("[id^='node_tool_']").count()
        self.assertGreaterEqual(tool_nodes, 1)

        # 5. TOOL_COMPLETED materializes Verify Node
        await self.server.broadcast_event("TOOL_COMPLETED", {
            "task_id": task_id,
            "tool": "web_search",
            "result": {"count": 3},
            "latency_ms": 140,
        })
        await asyncio.sleep(0.3)

        verify_node = self.page.locator("#node_verify")
        self.assertTrue(await verify_node.is_visible())

        # 6. AGENT_RESPONSE / TTS materializes TTS Node
        await self.server.broadcast_event("AGENT_RESPONSE", {
            "task_id": task_id,
            "content": "Found 3 coffee shops nearby.",
        })
        await asyncio.sleep(0.3)

        tts_node = self.page.locator("#node_tts")
        self.assertTrue(await tts_node.is_visible())

        await self.capture_screenshot("03_workflow_dynamic_nodes.png")


if __name__ == "__main__":
    unittest.main()
