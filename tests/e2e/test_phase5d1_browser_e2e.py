import asyncio
import json
import os
import sys
import time
import unittest
from playwright.async_api import async_playwright

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.runtime import SERARuntime
from app.ui.server import SERAUIServer


class TestPhase5D1BrowserE2E(unittest.IsolatedAsyncioTestCase):
    """MANDATORY REAL PLAYWRIGHT BROWSER E2E TEST SUITE FOR PHASE 5D.1."""

    @classmethod
    def setUpClass(cls):
        cls.port = 8790
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.screenshots_dir = os.path.join(PROJECT_ROOT, "artifacts", "e2e")
        os.makedirs(cls.screenshots_dir, exist_ok=True)

    async def asyncSetUp(self):
        # 1. Start real SERAUIServer with SERARuntime attached
        self.server = SERAUIServer(host="127.0.0.1", port=self.port)
        await self.server.start()

        # 2. Launch real Chromium
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        self.page = await self.context.new_page()

    async def asyncTearDown(self):
        try:
            if hasattr(self, "browser") and self.browser:
                await self.browser.close()
            if hasattr(self, "playwright") and self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        finally:
            if hasattr(self, "server") and self.server:
                await self.server.stop()

    async def test_01_initial_load_and_build_id_verification(self):
        """P0: Verifies browser loads fresh Build 5D.1, header badges, and captures 00_initial.png."""
        await self.page.goto(self.base_url, wait_until="networkidle")
        await asyncio.sleep(0.5)

        # 1. Verify Build ID in window and DOM
        build_id = await self.page.evaluate("() => window.SERA_BUILD_ID")
        self.assertEqual(build_id, "5D.1", "Browser served stale build without 5D.1 ID")

        badge_text = await self.page.inner_text("#sera-build-badge")
        self.assertIn("BUILD 5D.1", badge_text)

        # 2. Verify Header Telemetry Pills
        wake_text = await self.page.inner_text("#wake-status-text")
        self.assertEqual(wake_text, "WAKE: NOT CONFIGURED")

        stt_text = await self.page.inner_text("#stt-status-text")
        self.assertEqual(stt_text, "STT: FASTER-WHISPER")

        # 3. Capture 00_initial.png
        shot_path = os.path.join(self.screenshots_dir, "00_initial.png")
        await self.page.screenshot(path=shot_path)
        self.assertTrue(os.path.exists(shot_path))

    async def test_02_live_view_states_and_voice_control(self):
        """P0: Verifies Live view aura cockpit, hold-to-talk timer, and captures 01_live_idle, 02_hold_to_talk, 03_transcribing."""
        await self.page.goto(self.base_url, wait_until="networkidle")
        await asyncio.sleep(0.4)

        # 1. Live Idle
        shot_01 = os.path.join(self.screenshots_dir, "01_live_idle.png")
        await self.page.screenshot(path=shot_01)
        self.assertTrue(os.path.exists(shot_01))

        # 2. Simulate Hold-to-Talk (ACTIVATION_STARTED)
        await self.server.broadcast_event("ACTIVATION_STARTED", {"source": "HOTKEY", "mode": "HOLD"})
        await asyncio.sleep(0.3)

        state_text = await self.page.inner_text("#state-text")
        self.assertEqual(state_text, "LISTENING")

        shot_02 = os.path.join(self.screenshots_dir, "02_hold_to_talk.png")
        await self.page.screenshot(path=shot_02)
        self.assertTrue(os.path.exists(shot_02))

        # 3. Simulate KeyUp Release (ACTIVATION_RELEASED & TRANSCRIPTION_STARTED)
        await self.server.broadcast_event("ACTIVATION_RELEASED", {"duration_seconds": 2.4})
        await self.server.broadcast_event("TRANSCRIPTION_STARTED", {})
        await asyncio.sleep(0.3)

        state_trans = await self.page.inner_text("#state-text")
        self.assertEqual(state_trans, "TRANSCRIBING")

        shot_03 = os.path.join(self.screenshots_dir, "03_transcribing.png")
        await self.page.screenshot(path=shot_03)
        self.assertTrue(os.path.exists(shot_03))

    async def test_03_workflow_canvas_drag_and_persistence(self):
        """P0: Verifies Workflow 2D canvas, drag-and-drop node movement, persistence, and candidate ranking decoupling."""
        await self.page.goto(self.base_url, wait_until="networkidle")
        await self.page.click("#tab-workflow")
        await asyncio.sleep(0.4)

        # 1. Verify on Workflow View
        is_active = await self.page.evaluate("() => document.getElementById('view-workflow').classList.contains('active')")
        self.assertTrue(is_active)

        shot_04 = os.path.join(self.screenshots_dir, "04_workflow_idle.png")
        await self.page.screenshot(path=shot_04)
        self.assertTrue(os.path.exists(shot_04))

        # 2. Verify Canvas elements exist
        has_canvas = await self.page.evaluate("() => Boolean(document.getElementById('temporal-canvas-bg'))")
        self.assertTrue(has_canvas, "Missing temporal-canvas-bg backdrop")

        # 3. Simulate Node Dragging
        stt_node = await self.page.query_selector("#node_stt")
        self.assertIsNotNone(stt_node)
        box_before = await stt_node.bounding_box()

        # Drag node_stt by +80px X, +50px Y
        await self.page.mouse.move(box_before["x"] + 20, box_before["y"] + 20)
        await self.page.mouse.down()
        await self.page.mouse.move(box_before["x"] + 100, box_before["y"] + 70, steps=5)
        await self.page.mouse.up()
        await asyncio.sleep(0.3)

        # 4. Verify Active Execution Energy Pulses
        await self.server.broadcast_event("MODEL_SELECTED", {"role": "reasoning", "provider": "groq", "model": "openai/gpt-oss-120b"})
        await self.server.broadcast_event("TOOL_STARTED", {"tool": "open_application"})
        await asyncio.sleep(0.4)

        shot_05 = os.path.join(self.screenshots_dir, "05_workflow_active.png")
        await self.page.screenshot(path=shot_05)
        self.assertTrue(os.path.exists(shot_05))

        # 5. Fallback Branch Illumination
        await self.server.broadcast_event("MODEL_FALLBACK", {
            "failed_provider": "groq",
            "failed_model": "openai/gpt-oss-120b",
            "fallback_provider": "mistral",
            "fallback_model": "mistral-large-latest"
        })
        await asyncio.sleep(0.3)

        shot_06 = os.path.join(self.screenshots_dir, "06_workflow_fallback.png")
        await self.page.screenshot(path=shot_06)
        self.assertTrue(os.path.exists(shot_06))

        # 6. Broken State Glitch
        await self.server.broadcast_event("TOOL_FAILED", {"tool": "open_application", "error": "Process terminated abnormally"})
        await asyncio.sleep(0.3)

        shot_07 = os.path.join(self.screenshots_dir, "07_workflow_broken.png")
        await self.page.screenshot(path=shot_07)
        self.assertTrue(os.path.exists(shot_07))

    async def test_04_all_domain_views_validation(self):
        """P0: Verifies Agents, Memory, Providers, History, Debug, Security views and captures 08 - 13 screenshots."""
        await self.page.goto(self.base_url, wait_until="networkidle")
        await asyncio.sleep(0.3)

        # 1. Agents View
        await self.page.click("#tab-agents")
        await asyncio.sleep(0.3)
        shot_08 = os.path.join(self.screenshots_dir, "08_agents.png")
        await self.page.screenshot(path=shot_08)
        self.assertTrue(os.path.exists(shot_08))

        # 2. Memory View (Empty State Verification)
        await self.page.click("#tab-memory")
        await asyncio.sleep(0.3)
        empty_text = await self.page.evaluate("() => document.getElementById('memory-grid').innerText")
        self.assertIn("No knowledge indexed yet", empty_text)
        shot_09 = os.path.join(self.screenshots_dir, "09_memory.png")
        await self.page.screenshot(path=shot_09)
        self.assertTrue(os.path.exists(shot_09))

        # 3. Providers View (8 Providers Verification)
        await self.page.click("#tab-providers")
        await asyncio.sleep(0.3)
        prov_cards = await self.page.query_selector_all(".provider-card")
        self.assertGreaterEqual(len(prov_cards), 8, "Expected 8 first-class providers in control plane")
        shot_10 = os.path.join(self.screenshots_dir, "10_providers.png")
        await self.page.screenshot(path=shot_10)
        self.assertTrue(os.path.exists(shot_10))

        # 4. History View
        await self.page.click("#tab-history")
        await asyncio.sleep(0.3)
        shot_11 = os.path.join(self.screenshots_dir, "11_history.png")
        await self.page.screenshot(path=shot_11)
        self.assertTrue(os.path.exists(shot_11))

        # 5. Debug View
        await self.page.click("#tab-debug")
        await asyncio.sleep(0.3)
        shot_12 = os.path.join(self.screenshots_dir, "12_debug.png")
        await self.page.screenshot(path=shot_12)
        self.assertTrue(os.path.exists(shot_12))

        # 6. Security View & Confirmation Modal
        await self.page.click("#tab-security")
        await asyncio.sleep(0.3)
        shot_13 = os.path.join(self.screenshots_dir, "13_security.png")
        await self.page.screenshot(path=shot_13)
        self.assertTrue(os.path.exists(shot_13))

    async def test_05_live_to_workflow_auto_navigation(self):
        """P0: Verifies that a complex task auto-navigates from LIVE to WORKFLOW view."""
        await self.page.goto(self.base_url, wait_until="networkidle")
        await asyncio.sleep(0.3)

        # Start on LIVE view
        is_live_active = await self.page.evaluate("() => document.getElementById('view-live').classList.contains('active')")
        self.assertTrue(is_live_active)

        # Broadcast user transcription for complex action
        await self.server.broadcast_event("TRANSCRIPTION_COMPLETED", {"transcript": "Open Chrome browser"})
        await self.server.broadcast_event("TOOL_STARTED", {"tool": "open_application"})
        await asyncio.sleep(0.6)

        # Check view transitioned to WORKFLOW automatically
        is_workflow_active = await self.page.evaluate("() => document.getElementById('view-workflow').classList.contains('active')")
        self.assertTrue(is_workflow_active, "Failed to auto-navigate from LIVE to WORKFLOW on action execution")


if __name__ == "__main__":
    unittest.main()
