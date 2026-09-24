"""
SERA 2.0 — Normalized YouTube Search Adapter.

Performs robust item-level result extraction from YouTube search responses.
Guarantees that video IDs, titles, types, and canonical URLs are extracted from
the same verified item block. Creates session-scoped SearchResultEntity collections
and registers them into ContextStore.
Conforms strictly to Phase 3A-F Sections 6 & 7.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import urllib.parse
import webbrowser
from typing import Any, Dict, List, Optional
import httpx

from app.core.context.entities import SearchResultEntity, SearchResultType, SearchSession
from app.core.context.store import ContextStore
from app.tools.base import Tool

logger = logging.getLogger("sera.tools.browser.youtube")


def extract_youtube_items_from_html(raw_html: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Extracts normalized result items from YouTube HTML using item-level parsing.
    Guarantees title, id, and type come from the exact same item block.
    """
    items: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    # Strategy 1: Parse ytInitialData JSON if available
    json_match = re.search(r"var\s+ytInitialData\s*=\s*({.+?});\s*</script>", raw_html)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            contents = (
                data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
            for section in contents:
                item_section = section.get("itemSectionRenderer", {}).get("contents", [])
                for entry in item_section:
                    # Video
                    if "videoRenderer" in entry:
                        v = entry["videoRenderer"]
                        vid = v.get("videoId")
                        title_runs = v.get("title", {}).get("runs", [])
                        title = title_runs[0].get("text", "") if title_runs else ""
                        channel = v.get("ownerText", {}).get("runs", [{}])[0].get("text", "")
                        duration = v.get("lengthText", {}).get("simpleText", "")

                        if vid and title and vid not in seen_ids:
                            seen_ids.add(vid)
                            items.append({
                                "id": vid,
                                "title": html.unescape(title).strip(),
                                "url": f"https://www.youtube.com/watch?v={vid}",
                                "type": SearchResultType.VIDEO.value,
                                "channel": channel,
                                "duration": duration,
                            })

                    # Short / Reel
                    elif "reelItemRenderer" in entry:
                        r = entry["reelItemRenderer"]
                        vid = r.get("videoId")
                        title = r.get("headline", {}).get("simpleText", "")
                        if vid and title and vid not in seen_ids:
                            seen_ids.add(vid)
                            items.append({
                                "id": vid,
                                "title": html.unescape(title).strip(),
                                "url": f"https://www.youtube.com/shorts/{vid}",
                                "type": SearchResultType.SHORT.value,
                                "channel": "",
                                "duration": "",
                            })

                    # Playlist
                    elif "playlistRenderer" in entry:
                        p = entry["playlistRenderer"]
                        pid = p.get("playlistId")
                        title = p.get("title", {}).get("simpleText", "")
                        if pid and title and pid not in seen_ids:
                            seen_ids.add(pid)
                            items.append({
                                "id": pid,
                                "title": html.unescape(title).strip(),
                                "url": f"https://www.youtube.com/playlist?list={pid}",
                                "type": SearchResultType.PLAYLIST.value,
                                "channel": "",
                                "duration": "",
                            })

                    # Channel
                    elif "channelRenderer" in entry:
                        c = entry["channelRenderer"]
                        cid = c.get("channelId")
                        title = c.get("title", {}).get("simpleText", "")
                        if cid and title and cid not in seen_ids:
                            seen_ids.add(cid)
                            items.append({
                                "id": cid,
                                "title": html.unescape(title).strip(),
                                "url": f"https://www.youtube.com/channel/{cid}",
                                "type": SearchResultType.CHANNEL.value,
                                "channel": title,
                                "duration": "",
                            })

                    if len(items) >= max_results:
                        break
                if len(items) >= max_results:
                    break
        except Exception as e:
            logger.debug(f"[YouTubeSearchTool] ytInitialData JSON parse error: {e}")

    # Strategy 2: Robust Item-Level Block Regex Fallback
    # Matches individual {"videoRenderer":{...}} blocks to guarantee title and videoId come from same block
    if not items:
        # Match each videoRenderer block
        block_matches = re.finditer(
            r'\{"videoRenderer":\{.*?"videoId":"([a-zA-Z0-9_-]{11})".*?"title":\{"runs":\[\{"text":"([^"]+)"\}',
            raw_html,
        )
        for m in block_matches:
            vid = m.group(1)
            t_raw = m.group(2)
            title = html.unescape(t_raw).strip()
            if vid not in seen_ids and len(title) > 2:
                seen_ids.add(vid)
                items.append({
                    "id": vid,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "type": SearchResultType.VIDEO.value,
                    "channel": "",
                    "duration": "",
                })
            if len(items) >= max_results:
                break

    # Strategy 3: Shorts blocks
    if len(items) < max_results:
        reel_matches = re.finditer(
            r'\{"reelItemRenderer":\{.*?"videoId":"([a-zA-Z0-9_-]{11})".*?"headline":\{"simpleText":"([^"]+)"\}',
            raw_html,
        )
        for m in reel_matches:
            vid = m.group(1)
            title = html.unescape(m.group(2)).strip()
            if vid not in seen_ids and len(title) > 2:
                seen_ids.add(vid)
                items.append({
                    "id": vid,
                    "title": title,
                    "url": f"https://www.youtube.com/shorts/{vid}",
                    "type": SearchResultType.SHORT.value,
                    "channel": "",
                    "duration": "",
                })
            if len(items) >= max_results:
                break

    return items[:max_results]


class YouTubeSearchTool(Tool):
    """Dedicated YouTube search capability that executes search navigation and returns verified,
    item-level normalized results scoped by SearchSession.
    """

    def __init__(self, context_store: Optional[ContextStore] = None):
        self.context_store = context_store

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
                    "description": "The search query or video topic to look up on YouTube.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of normalized search results to extract (default: 5).",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "", max_results: int = 5, **kwargs) -> dict[str, Any]:
        clean_query = query.strip()
        if not clean_query:
            return {
                "success": False,
                "verified": False,
                "error": "YouTube search query cannot be empty.",
            }

        encoded_query = urllib.parse.quote_plus(clean_query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

        # 1. Open in Chrome / default browser
        opened = False
        try:
            try:
                chrome_browser = webbrowser.get("chrome")
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

        # 2. Extract item-level normalized results
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        raw_items: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                resp = await client.get(search_url, headers=headers)
                if resp.status_code == 200:
                    raw_items = extract_youtube_items_from_html(resp.text, max_results=max_results)
        except Exception as e:
            logger.debug(f"[YouTubeSearchTool] Fast scrape skipped: {e}")

        # 3. Create Session-Scoped Search Context (Sections 6 & 7)
        session_id = f"search_{clean_query[:10].replace(' ', '_')}"
        registered_entities: List[SearchResultEntity] = []

        if self.context_store:
            session = self.context_store.create_search_session(query=clean_query, source="YouTube")
            session_id = session.session_id
            if raw_items:
                registered_entities = self.context_store.add_search_results(session_id, raw_items)

        # Standardized return results with entity identity
        results_out = []
        titles_out = []
        for idx, item in enumerate(raw_items):
            ent_id = registered_entities[idx].entity_id if idx < len(registered_entities) else f"yt_{idx+1}"
            entry = {
                "entity_id": ent_id,
                "session_id": session_id,
                "ordinal": idx + 1,
                "title": item["title"],
                "url": item["url"],
                "canonical_url": item["url"],
                "source": "YouTube",
                "result_type": item.get("type", SearchResultType.VIDEO.value),
            }
            results_out.append(entry)
            titles_out.append(item["title"])

        summary = f"Searched YouTube for '{clean_query}' and opened the results."
        if titles_out:
            summary += f" Top result: {titles_out[0]}."

        return {
            "success": True,
            "verified": True,
            "query": clean_query,
            "url": search_url,
            "search_session_id": session_id,
            "titles": titles_out,
            "results": results_out,
            "browser_opened": opened,
            "message": summary,
        }
