"""
SERA 2.0 — Stateful Browser Execution Tools.

Exposes discrete tools for opening URLs idempotently, opening new tabs,
focusing specific tabs, and closing browser tabs without terminating the browser process.
Conforms strictly to Phase 3A-F Sections 10, 11, 12.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Optional
import httpx

from app.tools.base import Tool
from app.tools.browser.session import BrowserSessionManager

logger = logging.getLogger("sera.tools.browser")


class BrowserTool(Tool):
    """Opens a URL or webpage in the browser, reusing existing open tabs idempotently by default."""

    def __init__(self, session_manager: Optional[BrowserSessionManager] = None):
        self.session_manager = session_manager or BrowserSessionManager()

    @property
    def name(self) -> str:
        return "browser_open"

    @property
    def description(self) -> str:
        return (
            "Open a URL or webpage in the web browser. If the page is already open, "
            "focuses the existing tab idempotently instead of creating a duplicate."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to open (e.g. 'https://www.youtube.com', 'https://github.com').",
                },
                "title": {
                    "type": "string",
                    "description": "Optional title of the page or video to assist in idempotent tab matching.",
                },
                "new_tab": {
                    "type": "boolean",
                    "description": "Force opening in a new tab even if already open (default: False).",
                    "default": False,
                },
            },
            "required": ["url"],
        }

    async def execute(self, url: str, title: Optional[str] = None, new_tab: bool = False, **kwargs) -> dict[str, Any]:
        return await self.session_manager.open_url(url=url, title=title, new_tab=new_tab)


class OpenNewTabTool(Tool):
    """Explicitly opens a URL in a new browser tab."""

    def __init__(self, session_manager: Optional[BrowserSessionManager] = None):
        self.session_manager = session_manager or BrowserSessionManager()

    @property
    def name(self) -> str:
        return "open_new_tab"

    @property
    def description(self) -> str:
        return "Explicitly opens a URL in a new browser tab."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to open in a new tab.",
                }
            },
            "required": ["url"],
        }

    async def execute(self, url: str, **kwargs) -> dict[str, Any]:
        return await self.session_manager.open_url(url=url, new_tab=True)


class CloseBrowserTabTool(Tool):
    """Closes a specific browser tab or the current active tab without terminating the browser process."""

    def __init__(self, session_manager: Optional[BrowserSessionManager] = None):
        self.session_manager = session_manager or BrowserSessionManager()

    @property
    def name(self) -> str:
        return "close_browser_tab"

    @property
    def description(self) -> str:
        return (
            "Close a specific browser tab or the active browser tab without terminating "
            "the browser process. Use this when the user asks to close a tab or website."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tab_identifier": {
                    "type": "string",
                    "description": "Optional title, domain, or identifier of the tab to close (e.g. 'YouTube', 'GitHub'). If omitted, closes the active tab.",
                }
            },
        }

    async def execute(self, tab_identifier: Optional[str] = None, **kwargs) -> dict[str, Any]:
        target = tab_identifier or kwargs.get("tab_name") or kwargs.get("target")
        return await self.session_manager.close_tab(tab_identifier=target)


class FocusBrowserTabTool(Tool):
    """Switches focus to an open browser tab."""

    def __init__(self, session_manager: Optional[BrowserSessionManager] = None):
        self.session_manager = session_manager or BrowserSessionManager()

    @property
    def name(self) -> str:
        return "focus_browser_tab"

    @property
    def description(self) -> str:
        return "Switches to an existing open browser tab by title or URL."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tab_identifier": {
                    "type": "string",
                    "description": "Title or URL of the tab to focus.",
                }
            },
            "required": ["tab_identifier"],
        }

    async def execute(self, tab_identifier: str, **kwargs) -> dict[str, Any]:
        return await self.session_manager.focus_tab(tab_id_or_title=tab_identifier)


class ReadWebPageTool(Tool):
    """Fetches and reads the text content of a public webpage URL."""

    @property
    def name(self) -> str:
        return "browser_read_page"

    @property
    def description(self) -> str:
        return "Fetch and read the text content of a public webpage URL."

    @property
    def parameters(self) -> dict[str, Any]:
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

    async def execute(self, url: str) -> dict[str, Any]:
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return {"success": False, "error": f"HTTP error {resp.status_code} fetching {url}"}

                raw_html = resp.text
                clean = re.sub(r"<script[\s\S]*?</script>", "", raw_html, flags=re.IGNORECASE)
                clean = re.sub(r"<style[\s\S]*?</style>", "", clean, flags=re.IGNORECASE)
                text = re.sub(r"<[^>]+>", " ", clean)
                text = html.unescape(text)
                text = re.sub(r"\s+", " ", text).strip()

                return {
                    "success": True,
                    "url": url,
                    "content": text[:3000],
                    "length": len(text),
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to fetch webpage: {str(e)}",
            }
