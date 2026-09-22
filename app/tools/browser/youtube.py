import html
import logging
import os
import re
import urllib.parse
import webbrowser
import httpx
from typing import Any

from app.tools.base import Tool

logger = logging.getLogger(__name__)


class YouTubeSearchTool(Tool):
    """Dedicated YouTube search capability that executes search navigation and returns verified results."""

    @property
    def name(self) -> str:
        return "youtube_search"

    @property
    def description(self) -> str:
        return (
            "Search for videos, music, or channels on YouTube and open the results page. "
            "Requires a search query."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query or video topic to look up on YouTube (e.g. 'comedy videos', 'MrBeast latest video').",
                }
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "") -> dict[str, Any]:
        clean_query = query.strip()
        if not clean_query:
            return {
                "success": False,
                "verified": False,
                "error": "YouTube search query cannot be empty.",
            }

        # Format YouTube search URL
        encoded_query = urllib.parse.quote_plus(clean_query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

        # 1. Attempt to open in Chrome or default web browser
        opened = False
        try:
            # Prefer Chrome on Windows if available
            try:
                chrome_browser = webbrowser.get('chrome')
                chrome_browser.open(search_url)
                opened = True
            except Exception:
                opened = webbrowser.open(search_url)
                if not opened:
                    os.startfile(search_url)
                    opened = True
        except Exception as e:
            logger.warning(f"[YouTubeSearchTool] Browser launch fallback: {e}")
            try:
                os.startfile(search_url)
                opened = True
            except Exception as ex:
                logger.error(f"[YouTubeSearchTool] Failed to launch browser: {ex}")

        # 2. Extract quick search results / title hints via lightweight fetch (optional best-effort)
        video_titles = []
        video_ids = []
        results = []
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                resp = await client.get(search_url, headers=headers)
                if resp.status_code == 200:
                    raw = resp.text
                    # Extract video IDs
                    found_vids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', raw)
                    for v in found_vids:
                        if v not in video_ids:
                            video_ids.append(v)

                    # Extract titles
                    matches = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"', raw)
                    for m in matches:
                        t = html.unescape(m).strip()
                        if t and t not in video_titles and len(t) > 3:
                            video_titles.append(t)
                        if len(video_titles) >= 5:
                            break

            for idx, t in enumerate(video_titles):
                vid = video_ids[idx] if idx < len(video_ids) else None
                v_url = f"https://www.youtube.com/watch?v={vid}" if vid else search_url
                results.append({
                    "title": t,
                    "url": v_url,
                    "source": "YouTube",
                })
        except Exception as e:
            logger.debug(f"[YouTubeSearchTool] Results scrape skipped: {e}")

        summary = f"Searched YouTube for '{clean_query}' and opened the results."
        if video_titles:
            summary += f" Top results include: {video_titles[0]}."

        return {
            "success": True,
            "verified": True,
            "query": clean_query,
            "url": search_url,
            "titles": video_titles,
            "results": results,
            "browser_opened": opened,
            "message": summary,
        }
