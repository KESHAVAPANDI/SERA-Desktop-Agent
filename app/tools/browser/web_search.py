import html
import logging
import os
import re
import subprocess
import urllib.parse
import httpx
from app.tools.base import Tool
from app.tools.windows.apps import resolve_windows_application

logger = logging.getLogger(__name__)


def parse_duckduckgo_html(raw_html: str, max_results: int = 5) -> list[dict[str, str]]:
    """Parses real structured search results (title, url, snippet, source) from DuckDuckGo HTML."""
    results = []
    title_matches = list(re.finditer(r'<h2 class="result__title">\s*<a\b[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>\s*</h2>', raw_html))
    
    for idx, m in enumerate(title_matches):
        raw_url = m.group(1)
        raw_title = m.group(2)

        # Skip sponsored/ad links
        if "ad_provider=" in raw_url or "ad_type=" in raw_url or "/y.js?" in raw_url:
            continue

        title = html.unescape(re.sub(r'<[^>]+>', '', raw_title)).strip()
        # Clean multi-line garbage if any
        title = re.sub(r'\s+', ' ', title).strip()

        # Unwrap DDG redirect url
        url = raw_url
        if "uddg=" in raw_url:
            match_uddg = re.search(r'uddg=([^&]+)', raw_url)
            if match_uddg:
                url = urllib.parse.unquote(match_uddg.group(1))
        elif raw_url.startswith("//"):
            url = "https:" + raw_url

        if "duckduckgo.com/y.js" in url or "bing.com/aclick" in url:
            continue

        # Extract snippet from following content
        start_pos = m.end()
        end_pos = title_matches[idx + 1].start() if idx + 1 < len(title_matches) else (start_pos + 3000)
        segment = raw_html[start_pos:end_pos]

        snip_m = re.search(r'<a class="result__snippet"[^>]*>([\s\S]*?)</a>|<div class="result__snippet"[^>]*>([\s\S]*?)</div>', segment)
        snippet = ""
        if snip_m:
            snippet_raw = snip_m.group(1) or snip_m.group(2)
            snippet = html.unescape(re.sub(r'<[^>]+>', '', snippet_raw)).strip()
            snippet = re.sub(r'\s+', ' ', snippet).strip()

        domain = ""
        try:
            domain = urllib.parse.urlparse(url).netloc.replace("www.", "")
        except Exception:
            pass

        if not domain:
            domain_m = re.search(r'<span class="result__url[^>]*>([\s\S]*?)</span>', segment)
            if domain_m:
                domain = html.unescape(re.sub(r'<[^>]+>', '', domain_m.group(1))).strip()

        if title and (url.startswith("http://") or url.startswith("https://")):
            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": domain or "Web",
            })
            if len(results) >= max_results:
                break

    return results


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
                },
                "open_browser": {
                    "type": "boolean",
                    "description": "Whether to also open the search results page in Chrome / web browser.",
                    "default": True,
                }
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5, open_browser: bool = True):
        query = query.strip()
        if not query:
            return {"success": False, "verified": False, "count": 0, "results": [], "error": "Search query cannot be empty."}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        results = []
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"

        # 1. Fetch from DuckDuckGo HTML endpoint
        try:
            ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(ddg_url, headers=headers)
                if resp.status_code == 200:
                    results = parse_duckduckgo_html(resp.text, max_results=max_results)
        except Exception as e:
            logger.debug(f"[WebSearchTool] DDG HTML fetch error: {e}")

        # 2. Fallback to DuckDuckGo Instant Answer JSON API
        if not results:
            try:
                api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json"
                async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                    api_resp = await client.get(api_url, headers=headers)
                    if api_resp.status_code == 200:
                        data = api_resp.json()
                        abstract = data.get("AbstractText", "")
                        if abstract:
                            results.append({
                                "title": data.get("Heading", query),
                                "url": data.get("AbstractURL", search_url),
                                "snippet": abstract,
                                "source": data.get("AbstractSource", "DuckDuckGo"),
                            })
                        for topic in data.get("RelatedTopics", []):
                            if isinstance(topic, dict) and "Text" in topic and "FirstURL" in topic:
                                results.append({
                                    "title": topic.get("Text", "").split(" - ")[0],
                                    "url": topic["FirstURL"],
                                    "snippet": topic.get("Text", ""),
                                    "source": "DuckDuckGo",
                                })
                                if len(results) >= max_results:
                                    break
            except Exception as e:
                logger.debug(f"[WebSearchTool] DDG API fallback error: {e}")

        # 3. Open Chrome / Browser to the search results page if requested
        if open_browser and results:
            try:
                chrome_path = resolve_windows_application("chrome")
                if chrome_path and os.path.isfile(chrome_path):
                    subprocess.Popen([chrome_path, search_url], shell=False)
                else:
                    os.startfile(search_url)
            except Exception as e:
                logger.debug(f"[WebSearchTool] Browser navigation exception: {e}")

        # 4. Strict Side-Effect Verification
        if results and len(results) > 0 and all(r.get("title") and r.get("url") for r in results):
            return {
                "success": True,
                "verified": True,
                "query": query,
                "count": len(results),
                "results": results,
                "search_url": search_url,
                "message": f"Found {len(results)} search results for '{query}'.",
            }
        else:
            return {
                "success": False,
                "verified": False,
                "query": query,
                "count": 0,
                "results": [],
                "error": f"No web search results found for '{query}'.",
            }
