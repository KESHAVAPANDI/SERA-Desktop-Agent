"""
Phase 5D.5 E2E Tests — Live Temporal Theater, Why-Model Endpoint & Guaranteed Assistant Response
"""

import unittest
import asyncio
import json
from app.ui.server import SERAUIServer
from app.core.runtime import SERARuntime


class TestPhase5D5LiveTheater(unittest.TestCase):
    def setUp(self):
        self.runtime = SERARuntime()
        self.server = SERAUIServer(host="127.0.0.1", port=8765, runtime=self.runtime)

    def test_why_model_endpoint(self):
        async def _run():
            code, headers, body = await self.server._process_http("GET", "/api/router/why-model?role=reasoning", {}, b"")
            self.assertIn("200 OK", code)
            data = json.loads(body.decode("utf-8"))
            self.assertEqual(data["role"], "reasoning")
            self.assertIn("explanation", data)
            self.assertIn("reasons", data["explanation"])

        asyncio.run(_run())

    def test_resource_cache_endpoint(self):
        async def _run():
            code, headers, body = await self.server._process_http("GET", "/api/resource-cache", {}, b"")
            self.assertIn("200 OK", code)
            data = json.loads(body.decode("utf-8"))
            self.assertIsInstance(data, dict)

        asyncio.run(_run())

    def test_canonical_task_lifecycle_events(self):
        async def _run():
            events_emitted = []

            def handle_event(evt_type, payload):
                events_emitted.append((evt_type, payload))

            self.runtime.register_event_listener(handle_event)

            res = await self.runtime.start_canonical_task("What is 2 + 2?", source="TEXT")
            self.assertIsNotNone(res)

            event_names = [e[0] for e in events_emitted]
            self.assertIn("TASK_STARTED", event_names)
            self.assertIn("AGENT_RESPONSE", event_names)
            self.assertIn("TASK_COMPLETED", event_names)

            agent_resps = [e[1] for e in events_emitted if e[0] == "AGENT_RESPONSE"]
            self.assertGreaterEqual(len(agent_resps), 1)
            resp = agent_resps[0]
            self.assertIn("task_id", resp)
            self.assertIn("turn_id", resp)
            self.assertIn("content", resp)
            self.assertEqual(resp["type"], "ASSISTANT_MESSAGE")
            self.assertEqual(resp["status"], "COMPLETED")

        asyncio.run(_run())

    def test_task_cancellation_endpoint(self):
        async def _run():
            t = asyncio.create_task(self.runtime.start_canonical_task("Long running analysis task", source="TEXT"))
            await asyncio.sleep(0.01)

            code, headers, body = await self.server._process_http("POST", "/api/task/cancel", {}, b"")
            self.assertIn("200 OK", code)
            data = json.loads(body.decode("utf-8"))
            self.assertTrue(data["success"])

            await t

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
