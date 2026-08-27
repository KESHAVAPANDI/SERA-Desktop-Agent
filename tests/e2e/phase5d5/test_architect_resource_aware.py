"""
Phase 5D.5 E2E Tests — 3-Column Architect Studio, Resource-Aware Mode & Offline Simulation
"""

import unittest
import asyncio
import json
from app.ui.server import SERAUIServer
from app.core.runtime import SERARuntime


class TestPhase5D5Architect(unittest.TestCase):
    def setUp(self):
        self.server = SERAUIServer(host="127.0.0.1", port=8765, runtime=None)

    def test_architect_config_get_and_post(self):
        async def _run():
            # 1. GET Architect Config
            code, headers, body = await self.server._process_http("GET", "/api/architect/config", {}, b"")
            self.assertIn("200 OK", code)
            data = json.loads(body.decode("utf-8"))
            self.assertIn("roles", data)
            self.assertIn("execution_modes", data)

            # 2. POST update to RESOURCE_AWARE
            payload = {
                "execution_modes": {
                    "reasoning": "RESOURCE_AWARE",
                    "desktop": "RESOURCE_AWARE",
                    "fast": "PRIMARY_ONLY",
                },
                "roles": {
                    "reasoning": {
                        "candidates": [
                            {"provider": "Groq", "model": "openai/gpt-oss-120b"},
                            {"provider": "Mistral", "model": "mistral-large-2411"},
                        ]
                    }
                }
            }
            code, headers, body = await self.server._process_http("POST", "/api/architect/config", {}, json.dumps(payload).encode("utf-8"))
            self.assertIn("200 OK", code)
            res = json.loads(body.decode("utf-8"))
            self.assertTrue(res["success"])
            self.assertEqual(res["config"]["execution_modes"]["reasoning"], "RESOURCE_AWARE")

        asyncio.run(_run())

    def test_architect_simulation_low_quota(self):
        async def _run():
            # Simulate Low Quota preflight exclusion in RESOURCE_AWARE mode
            self.server.role_execution_modes["reasoning"] = "RESOURCE_AWARE"
            payload = {
                "role": "reasoning",
                "scenario": "low_quota",
                "simulate_outage": True,
            }
            code, headers, body = await self.server._process_http("POST", "/api/architect/test", {}, json.dumps(payload).encode("utf-8"))
            self.assertIn("200 OK", code)
            res = json.loads(body.decode("utf-8"))
            self.assertTrue(res["success"])
            self.assertEqual(res["mode"], "RESOURCE_AWARE")
            self.assertIn("reasons", res)
            self.assertTrue(any("Preflight" in r or "Selected" in r for r in res["reasons"]))

        asyncio.run(_run())

    def test_architect_simulation_normal(self):
        async def _run():
            # Simulate Normal operation
            self.server.role_execution_modes["reasoning"] = "RESOURCE_AWARE"
            payload = {
                "role": "reasoning",
                "scenario": "normal",
                "simulate_outage": False,
            }
            code, headers, body = await self.server._process_http("POST", "/api/architect/test", {}, json.dumps(payload).encode("utf-8"))
            self.assertIn("200 OK", code)
            res = json.loads(body.decode("utf-8"))
            self.assertTrue(res["success"])
            self.assertEqual(res["status"], "COMPLETED")

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
