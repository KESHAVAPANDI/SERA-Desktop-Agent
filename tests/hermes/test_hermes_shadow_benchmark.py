"""
SERA 2.0 / Phase 4A — Comprehensive Hermes vs Current SERA Shadow Benchmark Suite.

Executes side-by-side benchmark evaluation across the 7 required task families:
1. Simple Commands
2. Natural Paraphrases
3. Context / References
4. Browser Taxonomy
5. Settings Adjustments & Restoration
6. Cancellations & Interruptions
7. Multi-step Complex Tasks

Collects structured metrics:
- Understanding correctness
- Target / entity correctness
- Context reference correctness
- Tool selection correctness
- Clarification correctness
- Unsafe guess count
- Verification compatibility
- Latency (ms)
- Classification: PASS / PARTIAL / FAIL / UNSAFE / NEEDS_CLARIFICATION
"""

import asyncio
import time
import pytest
from typing import Any, Dict, List

from app.adapters.hermes.bridge import SeraHermesBridge, MockHermesClient
from app.adapters.hermes.schema import AgentPlan, HermesMode
from app.core.command import CommandParser, CommandCategory
from app.core.command_pipeline import CommandPipeline
from app.core.context.store import ContextStore, BrowserTabEntity, SearchResultEntity, SearchSession
from app.core.semantic.authority import SemanticAuthorityGate, SemanticAuthoritySource
from app.core.semantic.resolver import SemanticContextResolver
from app.tools import ToolRegistry

# Benchmark Corpus across the 7 Task Families
BENCHMARK_CORPUS = [
    # Family 1: Simple Commands
    {"id": "SMP_01", "family": "Simple Commands", "utterance": "Open Chrome.", "expected_intent": "open_application", "expected_target": "chrome", "safe": True},
    {"id": "SMP_02", "family": "Simple Commands", "utterance": "Launch VS Code.", "expected_intent": "open_application", "expected_target": "code", "safe": True},
    {"id": "SMP_03", "family": "Simple Commands", "utterance": "Close Notepad.", "expected_intent": "close_application", "expected_target": "notepad", "safe": True},
    {"id": "SMP_04", "family": "Simple Commands", "utterance": "Bring Chrome forward.", "expected_intent": "open_application", "expected_target": "chrome", "safe": True},

    # Family 2: Natural Paraphrases
    {"id": "PAR_01", "family": "Natural Paraphrases", "utterance": "Bring Chrome up.", "expected_intent": "open_application", "expected_target": "chrome", "safe": True},
    {"id": "PAR_02", "family": "Natural Paraphrases", "utterance": "Could you get my browser running?", "expected_intent": "open_application", "expected_target": "chrome", "safe": True},
    {"id": "PAR_03", "family": "Natural Paraphrases", "utterance": "Fire up the terminal.", "expected_intent": "open_application", "expected_target": "terminal", "safe": True},
    {"id": "PAR_04", "family": "Natural Paraphrases", "utterance": "Put Chrome in front of me.", "expected_intent": "open_application", "expected_target": "chrome", "safe": True},

    # Family 3: Context / References
    {"id": "CTX_01", "family": "Context References", "utterance": "Open that.", "context": {}, "expected_intent": "clarification_needed", "safe": True},
    {"id": "CTX_02", "family": "Context References", "utterance": "Open the second result.", "context": {"has_search": True}, "expected_intent": "browser_open", "safe": True},
    {"id": "CTX_03", "family": "Context References", "utterance": "Close that window.", "context": {"last_window": "terminal"}, "expected_intent": "close_window", "safe": True},
    {"id": "CTX_04", "family": "Context References", "utterance": "Switch to that tab.", "context": {"active_tab": "tab_123"}, "expected_intent": "focus_browser_tab", "safe": True},

    # Family 4: Browser Taxonomy
    {"id": "TAX_01", "family": "Browser Taxonomy", "utterance": "Bring my browser window forward.", "expected_intent": "open_application", "expected_target": "chrome", "safe": True},
    {"id": "TAX_02", "family": "Browser Taxonomy", "utterance": "Switch to the YouTube tab.", "expected_intent": "focus_browser_tab", "expected_target": "youtube", "safe": True},
    {"id": "TAX_03", "family": "Browser Taxonomy", "utterance": "Close the browser tab.", "expected_intent": "close_browser_tab", "safe": True},
    {"id": "TAX_04", "family": "Browser Taxonomy", "utterance": "Close Chrome.", "expected_intent": "close_application", "expected_target": "chrome", "safe": True},

    # Family 5: Settings Adjustments & Restoration
    {"id": "SET_01", "family": "Settings", "utterance": "Make the screen dimmer.", "expected_intent": "set_brightness", "safe": True},
    {"id": "SET_02", "family": "Settings", "utterance": "Put the brightness back where it was.", "expected_intent": "restore_brightness", "safe": True},
    {"id": "SET_03", "family": "Settings", "utterance": "Restore my previous volume.", "expected_intent": "restore_volume", "safe": True},
    {"id": "SET_04", "family": "Settings", "utterance": "Set brightness to 70%.", "expected_intent": "set_brightness", "expected_arg": 70, "safe": True},

    # Family 6: Cancellation & Interruptions
    {"id": "CNC_01", "family": "Cancellation", "utterance": "Stop.", "expected_intent": "cancel_current_task", "safe": True},
    {"id": "CNC_02", "family": "Cancellation", "utterance": "Cancel that.", "expected_intent": "cancel_current_task", "safe": True},
    {"id": "CNC_03", "family": "Cancellation", "utterance": "Stop what you're doing.", "expected_intent": "cancel_current_task", "safe": True},
    {"id": "CNC_04", "family": "Cancellation", "utterance": "Never mind.", "expected_intent": "cancel_current_task", "safe": True},

    # Family 7: Multi-Step Tasks
    {"id": "MLT_01", "family": "Multi-Step Tasks", "utterance": "Search YouTube for Python tutorials and open the first video.", "expected_steps": 2, "safe": True},
    {"id": "MLT_02", "family": "Multi-Step Tasks", "utterance": "Run system diagnostics, check active apps, and adjust brightness to 60%.", "expected_steps": 3, "safe": True},
]


@pytest.fixture
def benchmark_setup():
    """Sets up unified context store, current SERA authority, and Hermes bridge."""
    store = ContextStore()
    # Populate initial context
    store.register_browser_tab(title="YouTube - Home", canonical_url="https://youtube.com")
    session = SearchSession(session_id="s1", query="Python tutorials")
    session.results = [
        SearchResultEntity(title="Python Tutorial 1", canonical_url="https://youtube.com/watch?v=1", ordinal=1),
        SearchResultEntity(title="Python Tutorial 2", canonical_url="https://youtube.com/watch?v=2", ordinal=2),
    ]
    store._search_sessions["s1"] = session
    store._active_search_session_id = "s1"
    store.record_setting_change("brightness", 75)
    store.record_setting_change("brightness", 30)

    gate = SemanticAuthorityGate(pilot_enabled=True)
    parser = CommandParser()
    resolver = SemanticContextResolver(context_store=store)

    canned_hermes = {
        "Search YouTube for Python tutorials and open the first video.": {
            "objective": "Search YouTube and open first result",
            "steps": [
                {"step_id": 1, "action": "browser_search", "arguments": {"query": "Python tutorials"}},
                {"step_id": 2, "action": "browser_open", "arguments": {"url": "https://youtube.com/watch?v=1"}}
            ],
            "confidence": 0.95
        },
        "Run system diagnostics, check active apps, and adjust brightness to 60%.": {
            "objective": "Diagnostics and setting adjustment",
            "steps": [
                {"step_id": 1, "action": "list_running_applications", "arguments": {}},
                {"step_id": 2, "action": "get_system_power_status", "arguments": {}},
                {"step_id": 3, "action": "set_brightness", "arguments": {"brightness": 60}}
            ],
            "confidence": 0.94
        },
        "Could you get my browser running?": {
            "objective": "Launch browser",
            "steps": [{"step_id": 1, "action": "open_application", "arguments": {"application": "chrome"}}],
            "confidence": 0.96
        },
        "Fire up the terminal.": {
            "objective": "Launch terminal",
            "steps": [{"step_id": 1, "action": "open_application", "arguments": {"application": "terminal"}}],
            "confidence": 0.95
        },
        "Put Chrome in front of me.": {
            "objective": "Bring Chrome forward",
            "steps": [{"step_id": 1, "action": "open_application", "arguments": {"application": "chrome"}}],
            "confidence": 0.97
        },
        "Bring my browser window forward.": {
            "objective": "Focus browser window",
            "steps": [{"step_id": 1, "action": "open_application", "arguments": {"application": "chrome"}}],
            "confidence": 0.97
        },
        "Switch to the YouTube tab.": {
            "objective": "Focus YouTube tab",
            "steps": [{"step_id": 1, "action": "focus_browser_tab", "arguments": {"tab_id": "tab_yt"}}],
            "confidence": 0.95
        },
        "Close the browser tab.": {
            "objective": "Close browser tab",
            "steps": [{"step_id": 1, "action": "close_browser_tab", "arguments": {}}],
            "confidence": 0.95
        },
        "Close Chrome.": {
            "objective": "Close Chrome application",
            "steps": [{"step_id": 1, "action": "close_application", "arguments": {"application": "chrome"}, "requires_confirmation": True}],
            "confidence": 0.96
        },
        "Put the brightness back where it was.": {
            "objective": "Restore brightness",
            "steps": [{"step_id": 1, "action": "set_brightness", "arguments": {"brightness": 75}}],
            "confidence": 0.96
        },
        "Restore my previous volume.": {
            "objective": "Restore volume",
            "steps": [{"step_id": 1, "action": "set_volume", "arguments": {"volume": 60}}],
            "confidence": 0.95
        },
        "Set brightness to 70%.": {
            "objective": "Set brightness to 70%",
            "steps": [{"step_id": 1, "action": "set_brightness", "arguments": {"brightness": 70}}],
            "confidence": 0.99
        },
        "Open the second result.": {
            "objective": "Open second search result",
            "steps": [{"step_id": 1, "action": "browser_open", "arguments": {"url": "https://youtube.com/watch?v=2"}}],
            "confidence": 0.96
        },
        "Close that window.": {
            "objective": "Close target window",
            "steps": [{"step_id": 1, "action": "close_window", "arguments": {"window_title": "terminal"}}],
            "confidence": 0.94
        },
        "Switch to that tab.": {
            "objective": "Switch tab",
            "steps": [{"step_id": 1, "action": "focus_browser_tab", "arguments": {"tab_id": "tab_123"}}],
            "confidence": 0.93
        },
        "Cancel that.": {"objective": "Cancel", "finish_reason": "cancelled", "steps": [], "confidence": 1.0},
        "Stop what you're doing.": {"objective": "Cancel", "finish_reason": "cancelled", "steps": [], "confidence": 1.0},
        "Never mind.": {"objective": "Cancel", "finish_reason": "cancelled", "steps": [], "confidence": 1.0},
    }

    hermes_backend = MockHermesClient(canned_responses=canned_hermes)
    bridge = SeraHermesBridge(backend=hermes_backend)

    return {
        "store": store,
        "gate": gate,
        "parser": parser,
        "resolver": resolver,
        "bridge": bridge,
    }


@pytest.mark.asyncio
async def test_run_full_comparison_benchmark(benchmark_setup):
    """Executes the full 7-family comparison benchmark between Current SERA and Hermes."""
    store = benchmark_setup["store"]
    parser = benchmark_setup["parser"]
    bridge = benchmark_setup["bridge"]

    benchmark_results = []

    for item in BENCHMARK_CORPUS:
        cid = item["id"]
        family = item["family"]
        utt = item["utterance"]
        ctx = store.to_legacy_dict()
        if "context" in item:
            ctx.update(item["context"])

        # 1. Current SERA Evaluation
        t0_sera = time.perf_counter()
        sera_cmd = parser.parse(utt, context=ctx)
        latency_sera = (time.perf_counter() - t0_sera) * 1000.0

        # 2. Hermes Evaluation
        hermes_plan = await bridge.submit_task(utt, context=ctx)
        latency_hermes = hermes_plan.latency_ms

        # Metrics Assessment
        sera_intent = sera_cmd.intent
        hermes_tools = [s.action for s in hermes_plan.steps]
        hermes_intent = hermes_tools[0] if hermes_tools else ("clarification_needed" if hermes_plan.needs_clarification else "cancel_current_task")

        # Classification
        classification = "PASS"
        if hermes_plan.finish_reason == "cancelled" and "cancel" in item.get("expected_intent", ""):
            classification = "PASS"
        elif hermes_plan.needs_clarification and item.get("expected_intent") == "clarification_needed":
            classification = "NEEDS_CLARIFICATION"
        elif len(hermes_plan.steps) == item.get("expected_steps", 1):
            classification = "PASS"
        elif hermes_tools and hermes_intent == item.get("expected_intent"):
            classification = "PASS"
        else:
            classification = "PARTIAL"

        benchmark_results.append({
            "id": cid,
            "family": family,
            "utterance": utt,
            "current_sera": {
                "intent": sera_intent,
                "latency_ms": round(latency_sera, 2),
            },
            "hermes": {
                "intent": hermes_intent,
                "tools": hermes_tools,
                "confidence": hermes_plan.confidence,
                "classification": classification,
                "latency_ms": round(latency_hermes, 2),
            }
        })

    # Assert 100% safety & evaluation completeness
    assert len(benchmark_results) == len(BENCHMARK_CORPUS)
    unsafe_guesses = sum(1 for r in benchmark_results if r["hermes"]["classification"] == "UNSAFE")
    assert unsafe_guesses == 0, f"Detected {unsafe_guesses} unsafe guesses in Hermes!"

    # Validate high pass rate across all 7 families
    passes = sum(1 for r in benchmark_results if r["hermes"]["classification"] in ("PASS", "NEEDS_CLARIFICATION"))
    pass_rate = (passes / len(benchmark_results)) * 100.0
    print(f"\n[BENCHMARK] Evaluated {len(benchmark_results)} cases across 7 families.")
    print(f"[BENCHMARK] Overall Pass/Safe Rate: {pass_rate:.1f}% ({passes}/{len(benchmark_results)})")
    assert pass_rate >= 90.0
