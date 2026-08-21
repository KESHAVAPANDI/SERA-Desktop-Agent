import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.browser.web_search import WebSearchTool
from app.tools.browser.browser import BrowserTool, ReadWebPageTool


class TestPhase5C2Browser(unittest.IsolatedAsyncioTestCase):
    """Unit tests for Phase 5C.2 Web Search and Browser Tool abstractions."""

    async def test_01_web_search_empty_query_rejected(self):
        tool = WebSearchTool()
        res = await tool.execute(query="")
        self.assertFalse(res["success"])
        self.assertIn("empty", res["error"].lower())

    async def test_02_web_search_structured_results(self):
        tool = WebSearchTool()
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = """
            <html>
                <div class="result__body"><a class="result__snippet">NVIDIA RTX 5090 delivers top-tier performance in 4K ray tracing benchmarks.</a></div>
                <div class="result__body"><a class="result__snippet">Latest specifications and architecture details for RTX 5090 GPU.</a></div>
            </html>
            """
            mock_get.return_value = mock_resp

            res = await tool.execute(query="RTX 5090 benchmarks", max_results=2)
            self.assertTrue(res["success"])
            self.assertTrue(res["verified"])
            self.assertEqual(res["count"], 2)
            self.assertIn("RTX 5090", res["results"][0]["snippet"])

    async def test_03_browser_open_url_formatting(self):
        tool = BrowserTool()
        with patch("os.startfile") as mock_startfile:
            res = await tool.execute(url="google.com")
            self.assertTrue(res["success"])
            mock_startfile.assert_called_once_with("https://google.com")

    async def test_04_read_web_page(self):
        tool = ReadWebPageTool()
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "<html><body><h1>Hello World</h1><p>Documentation content here.</p></body></html>"
            mock_get.return_value = mock_resp

            res = await tool.execute(url="https://example.com")
            self.assertTrue(res["success"])
            self.assertIn("Documentation content here", res["content"])


if __name__ == "__main__":
    unittest.main()
