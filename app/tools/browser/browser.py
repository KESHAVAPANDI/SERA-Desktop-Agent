import html
import logging
import os
import re
import httpx
from app.tools.base import Tool

logger = logging.getLogger(__name__)


class BrowserTool(Tool):

    @property
    def name(self) -> str:
        return "browser_open"

    @property
    def description(self) -> str:
        return "Open a URL or webpage in the default Windows web browser."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to open (e.g. 'https://www.google.com', 'https://github.com').",
                }
            },
            "required": ["url"],
        }

    async def execute(self, url: str):
        url = url.strip()
        if not url:
            return {"success": False, "error": "URL cannot be empty."}

        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        try:
            os.startfile(url)
            return {
                "success": True,
                "verified": True,
                "url": url,
                "message": f"Opened {url} in browser.",
            }
        except Exception as e:
            return {
                "success": False,
                "verified": False,
                "error": f"Failed to open {url}: {str(e)}",
            }


class ReadWebPageTool(Tool):

    @property
    def name(self) -> str:
        return "browser_read_page"

    @property
    def description(self) -> str:
        return "Fetch and read the text content of a public webpage URL."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the webpage to read.",
                }
            },
            "required": ["url"],
        }

    async def execute(self, url: str):
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return {"success": False, "error": f"HTTP error {resp.status_code} fetching {url}"}

                raw_html = resp.text
                # Remove scripts and styles
                clean = re.sub(r'<script[\s\S]*?</script>', '', raw_html, flags=re.IGNORECASE)
                clean = re.sub(r'<style[\s\S]*?</style>', '', clean, flags=re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', clean)
                text = html.unescape(text)
                text = re.sub(r'\s+', ' ', text).strip()

                return {
                    "success": True,
                    "url": url,
                    "content": text[:3000],  # Return first 3000 chars
                    "length": len(text),
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch webpage: {str(e)}",
            }
