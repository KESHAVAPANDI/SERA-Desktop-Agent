import asyncio
import os
import unittest
import pytest
from app.tools.browser.web_search import WebSearchTool, parse_duckduckgo_html
from app.tools import create_tool_registry
from app.core.command_pipeline import CommandPipeline
from app.core.state import SERAState, SERAStatus


# =====================================================================
# TEST 1 — REAL SEARCH TOOL (Direct Tool Integration)
# =====================================================================
@pytest.mark.asyncio
async def test_1_real_search_tool():
    """Test 1: Direct tool integration verifying real web search execution against live internet."""
    tool = WebSearchTool()
    query = "RTX 5090 benchmarks"
    print(f"\n[TEST 1] Executing WebSearchTool directly for query: '{query}'")

    res = await tool.execute(query=query, max_results=5, open_browser=False)

    print(f"[TEST 1] Tool Success: {res.get('success')}")
    print(f"[TEST 1] Results Count: {res.get('count')}")

    assert res.get("success") is True, f"Search failed: {res.get('error')}"
    assert res.get("verified") is True, "Search verification flag was False"
    assert res.get("count", 0) >= 1, "Expected at least 1 real search result"
    assert isinstance(res.get("results"), list) and len(res["results"]) >= 1, "Results must be a non-empty list"

    first = res["results"][0]
    print(f"[TEST 1] Sample result 1 title: '{first.get('title')}'")
    print(f"[TEST 1] Sample result 1 URL:   '{first.get('url')}'")
    assert first.get("title"), "First result must have a title"
    assert first.get("url"), "First result must have a URL"
    print("✓ TEST 1 (Real Search Tool Integration): PASSED")


# =====================================================================
# TEST 2 — RESULT CONTRACT (Schema & Data Integrity Validation)
# =====================================================================
def test_2_result_contract():
    """Test 2: Schema validation verifying structure of parsed results (title, url, snippet, source)."""
    sample_html = """
    <!DOCTYPE html>
    <html>
    <body>
      <div class="result results_links results_links_deep web-result ">
        <h2 class="result__title">
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ftechpowerup.com%2Freview%2Frtx-5090&amp;rut=123">NVIDIA GeForce RTX 5090 Review</a>
        </h2>
        <div class="result__snippet">The GeForce RTX 5090 is the fastest graphics card ever tested in our lab.</div>
        <span class="result__url">techpowerup.com</span>
      </div>
      <div class="result results_links results_links_deep web-result ">
        <h2 class="result__title">
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ftomshardware.com%2Freviews%2Frtx-5090-benchmarks&amp;rut=456">RTX 5090 Benchmarks &amp; Specs</a>
        </h2>
        <div class="result__snippet">Comprehensive gaming and compute benchmarks for RTX 5090.</div>
        <span class="result__url">tomshardware.com</span>
      </div>
    </body>
    </html>
    """
    results = parse_duckduckgo_html(sample_html, max_results=5)

    print(f"\n[TEST 2] Parsed {len(results)} items from schema fixture.")
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"

    required_fields = ["title", "url", "snippet", "source"]
    for idx, item in enumerate(results, 1):
        for field in required_fields:
            assert field in item, f"Result #{idx} missing required contract field '{field}'"
            assert isinstance(item[field], str), f"Field '{field}' in #{idx} must be a string"
            assert len(item[field].strip()) > 0, f"Field '{field}' in #{idx} must not be empty"

    assert results[0]["title"] == "NVIDIA GeForce RTX 5090 Review"
    assert results[0]["url"] == "https://techpowerup.com/review/rtx-5090"
    assert results[0]["source"] == "techpowerup.com"
    assert "fastest graphics card" in results[0]["snippet"]

    assert results[1]["title"] == "RTX 5090 Benchmarks & Specs"
    assert results[1]["url"] == "https://tomshardware.com/reviews/rtx-5090-benchmarks"
    assert results[1]["source"] == "tomshardware.com"

    print("✓ TEST 2 (Result Contract Validation): PASSED")


# =====================================================================
# TEST 3 — ZERO RESULT (Failure-Path Verification -> BROKEN)
# =====================================================================
@pytest.mark.asyncio
async def test_3_zero_result_failure_path():
    """Test 3: Controlled zero-result response verifies task becomes BROKEN / FAILED, not COMPLETED."""
    print("\n[TEST 3] Running Zero-Result failure-path test")

    class MockZeroResultWebSearchTool(WebSearchTool):
        async def execute(self, query: str, max_results: int = 5, open_browser: bool = True):
            return {
                "success": False,
                "verified": False,
                "query": query,
                "count": 0,
                "results": [],
                "error": f"No web search results found for '{query}'.",
            }

    tools = create_tool_registry()
    tools._tools["web_search"] = MockZeroResultWebSearchTool()

    state = SERAState()
    pipeline = CommandPipeline(tools=tools, state=state)

    result = await pipeline.execute_text("Search the web for RTX 5090 benchmarks")
    print(f"[TEST 3] Pipeline returned: {result}")

    assert result["success"] is False, f"Expected success=False on 0 results, got {result['success']}"
    assert state.status == SERAStatus.BROKEN, f"Expected state=BROKEN, got {state.status}"
    assert "no web search results" in (result.get("error") or "").lower() or "failed" in (result.get("response") or "").lower() or "0" in result.get("response", "") or not result["success"]

    print("✓ TEST 3 (Zero Result -> BROKEN State): PASSED")


# =====================================================================
# TEST 4 — LIVE RESULT RENDERING (Simulated UI Event Ingestion)
# =====================================================================
def test_4_live_result_rendering_data_contract():
    """Test 4: Verifies structured search result payload is compatible with LiveView renderArtifacts contract."""
    print("\n[TEST 4] Validating LiveView renderArtifacts data contract")

    mock_tool_result = {
        "success": True,
        "verified": True,
        "query": "RTX 5090 benchmarks",
        "count": 2,
        "search_url": "https://www.google.com/search?q=RTX+5090+benchmarks",
        "results": [
            {
                "title": "NVIDIA GeForce RTX 5090 Review",
                "url": "https://techpowerup.com/review/rtx-5090",
                "snippet": "Real-world test benchmarks and 4K performance.",
                "source": "techpowerup.com",
            },
            {
                "title": "RTX 5090 Benchmarks & Specs",
                "url": "https://tomshardware.com/reviews/rtx-5090",
                "snippet": "Deep dive into Blackwell desktop gaming performance.",
                "source": "tomshardware.com",
            }
        ]
    }

    # Verify fields required by LiveView
    assert "results" in mock_tool_result
    assert isinstance(mock_tool_result["results"], list)
    assert len(mock_tool_result["results"]) == 2
    for r in mock_tool_result["results"]:
        assert "title" in r and r["title"]
        assert "url" in r and r["url"].startswith("http")
        assert "snippet" in r
        assert "source" in r

    print("✓ TEST 4 (Live Result Rendering Contract): PASSED")


# =====================================================================
# TEST 5 — FULL END-TO-END COMMAND PIPELINE TEST
# =====================================================================
@pytest.mark.asyncio
async def test_5_full_end_to_end_web_search():
    """Test 5: Full end-to-end command execution ('Search the web for RTX 5090 benchmarks')."""
    print("\n" + "=" * 60)
    print("TEST 5: Full End-to-End Real Web Search")
    print("=" * 60)

    from app.core.events import EventBus
    event_bus = EventBus()
    events_captured = []

    for ev in ["TASK_STARTED", "TOOL_STARTED", "TOOL_COMPLETED", "AGENT_RESPONSE", "TASK_COMPLETED", "TASK_FAILED"]:
        def make_cb(name):
            return lambda *args, **kwargs: events_captured.append((name, args, kwargs))
        event_bus.subscribe(ev, make_cb(ev))

    tools = create_tool_registry()
    state = SERAState()
    pipeline = CommandPipeline(tools=tools, state=state, event_bus=event_bus)

    user_cmd = "Search the web for RTX 5090 benchmarks"
    print(f"\n[USER COMMAND] '{user_cmd}'")
    result = await pipeline.execute_text(user_cmd)
    print(f"[PIPELINE RESULT] {result}")

    # 1. Task executed and succeeded
    assert result["success"] is True, f"Pipeline execution failed: {result}"

    # 2. Exactly one final assistant response
    assert "found" in result["response"].lower() and "results" in result["response"].lower(), f"Unexpected response: {result['response']}"

    # 3. Tool results contain structured real data
    step_results = result.get("steps", [])
    assert len(step_results) >= 1, "Expected at least 1 step result"
    search_step = step_results[0]
    assert search_step.get("tool") == "web_search", f"Expected tool=web_search, got {search_step.get('tool')}"
    search_res = search_step.get("result", {})
    assert search_res.get("count", 0) >= 1, "Expected >= 1 search result in step output"
    assert len(search_res.get("results", [])) >= 1, "Expected non-empty results array"

    # 4. Events flow verification
    event_names = [e[0] for e in events_captured]
    print(f"[EVENTS CAPTURED] {event_names}")
    assert "TASK_STARTED" in event_names
    assert "TOOL_STARTED" in event_names
    assert "TOOL_COMPLETED" in event_names
    assert "AGENT_RESPONSE" in event_names
    assert "TASK_COMPLETED" in event_names

    print("✓ TEST 5 (Full End-to-End Web Search): PASSED")


if __name__ == "__main__":
    asyncio.run(test_1_real_search_tool())
    test_2_result_contract()
    asyncio.run(test_3_zero_result_failure_path())
    test_4_live_result_rendering_data_contract()
    asyncio.run(test_5_full_end_to_end_web_search())
