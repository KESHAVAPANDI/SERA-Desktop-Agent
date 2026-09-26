"""
SERA 2.0 / Phase 4B — Live Real Hermes End-to-End Execution Benchmark.

Strict Architectural Rule:
[REAL HERMES + REAL SERA + REAL BROWSER + REAL VERIFICATION]

Demonstrates:
1. Official Nous Research Hermes Agent runtime receives the request.
2. Hermes reasons and produces real action (youtube_search).
3. SERA validates action and parameters against execution substrate.
4. SERA executes real YouTube search (extracts genuine item-level results).
5. SERA registers SearchSession & SearchResultEntities into ContextStore.
6. SERA verifies search result state.
7. Hermes receives updated verified context snapshot with real search results.
8. Hermes decides next action (browser_open on first result).
9. SERA validates target and resolves SearchResultEntity ordinal 1 to canonical URL.
10. SERA opens the target in browser.
11. SERA verifies browser reality.
12. Final state is COMPLETED with genuine evidence records.
"""

import asyncio
import json
import os
import sys
import time
import pytest

from app.adapters.hermes.bridge import OfficialHermesClient, SeraHermesBridge
from app.adapters.hermes.coordinator import HermesExecutionCoordinator
from app.adapters.hermes.schema import ExecutionHandoffStatus
from app.adapters.hermes.validator import HermesPlanValidator
from app.core.context.store import ContextStore
from app.core.verification import EvidenceVerificationFabric
from app.tools import create_tool_registry


@pytest.mark.asyncio
async def test_live_hermes_youtube_search_and_open_first_result():
    """
    [REAL HERMES + REAL SERA + REAL BROWSER + REAL VERIFICATION]
    End-to-end multi-step live execution benchmark.
    """
    # 1. Ensure Official Hermes is available
    assert OfficialHermesClient.is_available() is True, "Official Hermes binary not found on host!"

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        # Load from .env if present
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("OPENROUTER_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        os.environ["OPENROUTER_API_KEY"] = api_key
                        break

    assert api_key, "OPENROUTER_API_KEY is required for live Hermes benchmark."

    # 2. Build live execution substrate
    context_store = ContextStore()
    tools = create_tool_registry()
    evidence_fabric = EvidenceVerificationFabric()
    validator = HermesPlanValidator(context_store=context_store, tool_registry=tools)

    client = OfficialHermesClient(
        provider="openrouter",
        model="meta-llama/llama-3.3-70b-instruct",
        api_key=api_key,
    )
    bridge = SeraHermesBridge(backend=client)

    coordinator = HermesExecutionCoordinator(
        bridge=bridge,
        context_store=context_store,
        tool_registry=tools,
        validator=validator,
        evidence_fabric=evidence_fabric,
    )

    prompt = "Search YouTube for Python tutorials and open the first result"
    task_id = f"phase4b_live_{int(time.time())}"

    print(f"\n[PHASE 4B LIVE] Starting real task: '{prompt}' (Task ID: {task_id})")
    t0 = time.perf_counter()

    result = await coordinator.execute_task(
        utterance=prompt,
        task_id=task_id,
        timeout=90.0,
        max_turns=3,
    )

    total_duration = time.perf_counter() - t0
    print(f"[PHASE 4B LIVE] Finished in {total_duration:.2f}s with status: {result.status.value}")
    print(f"[PHASE 4B LIVE] Steps executed: {result.steps_executed}")
    print(f"[PHASE 4B LIVE] Telemetry: {result.telemetry}")

    # 3. Assert Real World Outcomes
    assert result.status == ExecutionHandoffStatus.COMPLETED, f"Task failed: {result.error}"
    assert result.steps_executed >= 2, f"Expected at least 2 steps, got {result.steps_executed}"

    # Step 1: Real YouTube Search
    step1 = result.step_history[0]
    assert step1["action"] == "youtube_search"
    assert step1["status"] == "VERIFIED_SUCCESS"

    session = context_store.get_active_search_session()
    assert session is not None, "ContextStore must contain active SearchSession"
    assert len(session.results) > 0, "Real YouTube search must return genuine results"
    first_result = session.results[0]
    print(f"[PHASE 4B LIVE] Top Search Result: '{first_result.title}' -> {first_result.canonical_url}")
    assert first_result.canonical_url.startswith("https://www.youtube.com/"), "Must be genuine YouTube URL"

    # Step 2: Open First Result
    step2 = result.step_history[1]
    assert step2["action"] == "browser_open"
    assert step2["status"] == "VERIFIED_SUCCESS"
    opened_url = step2["arguments"].get("url")
    print(f"[PHASE 4B LIVE] Opened URL: {opened_url}")
    assert opened_url == first_result.canonical_url, "Opened URL must strictly match verified Result #1 canonical URL"

    # 4. Save Benchmark Artifact
    benchmark_data = {
        "task_id": task_id,
        "classification": "REAL HERMES + REAL SERA + REAL BROWSER + REAL VERIFICATION",
        "prompt": prompt,
        "status": result.status.value,
        "turns": result.telemetry.turns,
        "steps_executed": result.steps_executed,
        "total_latency_ms": result.telemetry.total_latency_ms,
        "reasoning_latency_ms": result.telemetry.reasoning_latency_ms,
        "execution_latency_ms": result.telemetry.execution_latency_ms,
        "verification_latency_ms": result.telemetry.verification_latency_ms,
        "tokens": result.telemetry.total_tokens,
        "cost_usd": result.telemetry.estimated_cost_usd,
        "session_id": result.telemetry.session_id,
        "first_result_title": first_result.title,
        "first_result_url": first_result.canonical_url,
        "steps": result.step_history,
    }

    report_dir = os.path.join(os.getcwd(), "reports")
    os.makedirs(report_dir, exist_ok=True)
    bench_file = os.path.join(report_dir, "phase4b_live_hermes_benchmark.json")
    with open(bench_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    print(f"[PHASE 4B LIVE] Saved benchmark to: {bench_file}")


if __name__ == "__main__":
    asyncio.run(test_live_hermes_youtube_search_and_open_first_result())
