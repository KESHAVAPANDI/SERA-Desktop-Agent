import asyncio
import os
import sys
import unittest
from playwright.async_api import async_playwright

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.ui.server import SERAUIServer


class BasePhase5D3E2ETest(unittest.IsolatedAsyncioTestCase):
    port = 8820

    @classmethod
    def setUpClass(cls):
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.screenshots_dir = os.path.join(PROJECT_ROOT, "artifacts", "e2e", "phase5d3")
        os.makedirs(cls.screenshots_dir, exist_ok=True)

    async def asyncSetUp(self):
        self.server = SERAUIServer(host="127.0.0.1", port=self.port)
        await self.server.start()

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context(viewport={"width": 1440, "height": 900})
        
        # Abort external font network waits so screenshots do not hang on offline/slow font networks
        await self.context.route("**/*fonts.google*/**", lambda route: route.abort())
        await self.context.route("**/*fonts.gstatic*/**", lambda route: route.abort())

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

    async def capture_screenshot(self, filename: str) -> str:
        shot_path = os.path.join(self.screenshots_dir, filename)
        await self.page.screenshot(path=shot_path, timeout=10000, animations="disabled")
        self.assertTrue(os.path.exists(shot_path), f"Screenshot {filename} failed to save")
        return shot_path
