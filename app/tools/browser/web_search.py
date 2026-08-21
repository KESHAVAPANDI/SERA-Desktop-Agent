import html
import logging
import re
import urllib.parse
import httpx
from app.tools.base import Tool

logger = logging.getLogger(__name__)


class WebSearchTool(Tool):

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the live web for current information, benchmarks, news, and facts. "
            "Returns structured search result snippets and source URLs."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g. 'RTX 5090 benchmarks', 'Python 3.13 release date').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (default: 5).",
                    "default": 5,
                }
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5):
        query = query.strip()
        if not query:
            return {"success": False, "error": "Search query cannot be empty."}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                results = []

                if resp.status_code == 200:
                    raw = resp.text
                    bodies = re.findall(r'<div class="result__body">([\s\S]*?)</div>\s*</div>', raw)
                    if not bodies:
                        bodies = re.findall(r'<a class="result__snippet[^>]*>([\s\S]*?)</a>', raw)

                    for b in bodies[:max_results]:
                        text = re.sub(r'<[^>]+>', '', b)
                        text = html.unescape(text).strip()
                        if text:
                            results.append({"snippet": text})

                if not results:
                    # Fallback to DuckDuckGo Instant Answer JSON API
                    api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json"
                    api_resp = await client.get(api_url, headers=headers)
                    if api_resp.status_code == 200:
                        data = api_resp.json()
                        abstract = data.get("AbstractText", "")
                        if abstract:
                            results.append({
                                "title": data.get("Heading", query),
                                "snippet": abstract,
                                "url": data.get("AbstractURL", ""),
                            })

                if results:
                    return {
                        "success": True,
                        "verified": True,
                        "query": query,
                        "count": len(results),
                        "results": results,
                    }
                else:
                    return {
                        "success": True,
                        "verified": False,
                        "query": query,
                        "count": 0,
                        "results": [],
                        "message": f"No direct search results found for '{query}'.",
                    }

        except Exception as e:
            logger.error(f"[WebSearchTool] Web search failed: {e}")
            return {
                "success": False,
                "verified": False,
                "query": query,
                "error": f"Web search request failed: {str(e)}",
            }
