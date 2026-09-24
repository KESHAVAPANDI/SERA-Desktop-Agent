"""
SERA 2.0 — Local Semantic Interpreter Latency Profiler.
Measures all 10 stages of the semantic interpretation boundary:
1. Context construction
2. Prompt construction
3. HTTP request serialization
4. Ollama queue wait / roundtrip
5. Model load duration (from Ollama metadata)
6. Prompt eval duration (from Ollama metadata)
7. Token eval duration (from Ollama metadata)
8. Response transfer & HTTP completion
9. JSON parsing
10. Schema validation
Total end-to-end latency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
import time
from typing import Any, Dict, List, Optional

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import httpx

from app.core.semantic.prompt import build_semantic_prompt
from app.core.semantic.schema import CompactSemanticContext
from app.core.semantic.validator import SemanticValidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sera.semantic.profiler")


class LatencyProfiler:
    def __init__(self, model: str = "qwen3.5:4b", base_url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def profile_single_turn(
        self,
        utterance: str,
        context_dict: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Profiles a single interpretation turn with microsecond-level monotonic timestamps."""
        t_start = time.perf_counter()

        # 1. Context Construction
        t_ctx_start = time.perf_counter()
        compact_ctx = CompactSemanticContext(
            utterance=utterance,
            active_application=(context_dict or {}).get("active_application"),
            active_browser=(context_dict or {}).get("active_browser"),
            active_tab=(context_dict or {}).get("active_tab"),
            current_url=(context_dict or {}).get("current_url"),
            last_verified_action=(context_dict or {}).get("last_verified_action"),
            relevant_entities=(context_dict or {}).get("relevant_entities", []),
            recent_verified_actions=(context_dict or {}).get("recent_verified_actions", []),
        )
        ctx_payload = compact_ctx.to_dict()
        t_ctx_end = time.perf_counter()

        # 2. Prompt Construction
        t_prompt_start = time.perf_counter()
        messages = build_semantic_prompt(utterance, ctx_payload)
        t_prompt_end = time.perf_counter()

        # 3. HTTP Request Serialization
        t_http_start = time.perf_counter()
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "think": False,
            "keep_alive": "10m",
            "options": {
                "temperature": 0.0,
                "num_predict": 256,
            },
        }
        t_http_end = time.perf_counter()

        # 4. HTTP Post & Ollama Execution
        t_req_start = time.perf_counter()
        resp = await self.client.post("/api/chat", json=payload)
        t_req_end = time.perf_counter()

        if resp.status_code != 200:
            raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

        # 5. Response Transfer & JSON Deserialization
        t_deser_start = time.perf_counter()
        data = resp.json()
        raw_content = data.get("message", {}).get("content", "")
        t_deser_end = time.perf_counter()

        # 6. JSON Content Parsing & Schema Validation
        t_val_start = time.perf_counter()
        intent_obj, is_valid, err_reason = SemanticValidator.validate(raw_content)
        t_val_end = time.perf_counter()

        t_total = time.perf_counter() - t_start

        # Extract Ollama native duration metadata
        total_dur_ms = data.get("total_duration", 0) / 1e6
        load_dur_ms = data.get("load_duration", 0) / 1e6
        prompt_eval_dur_ms = data.get("prompt_eval_duration", 0) / 1e6
        eval_dur_ms = data.get("eval_duration", 0) / 1e6
        prompt_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        # Network/queue overhead = (wall request time) - (ollama total duration)
        net_queue_ms = max(0.0, (t_req_end - t_req_start) * 1000.0 - total_dur_ms)

        metrics = {
            "utterance": utterance,
            "intent": intent_obj.intent,
            "target": intent_obj.target.value if intent_obj.target else None,
            "is_valid": is_valid,
            "output_tokens": output_tokens,
            "prompt_tokens": prompt_tokens,
            # Stage Timings in milliseconds
            "stage_context_ms": (t_ctx_end - t_ctx_start) * 1000.0,
            "stage_prompt_ms": (t_prompt_end - t_prompt_start) * 1000.0,
            "stage_serialization_ms": (t_http_end - t_http_start) * 1000.0,
            "stage_net_queue_ms": net_queue_ms,
            "stage_ollama_load_ms": load_dur_ms,
            "stage_ollama_prompt_eval_ms": prompt_eval_dur_ms,
            "stage_ollama_eval_ms": eval_dur_ms,
            "stage_ollama_total_ms": total_dur_ms,
            "stage_response_deser_ms": (t_deser_end - t_deser_start) * 1000.0,
            "stage_validation_ms": (t_val_end - t_val_start) * 1000.0,
            "total_wall_ms": t_total * 1000.0,
        }
        return metrics

    async def run_profiling_suite(self) -> Dict[str, Any]:
        """Runs cold request, warm requests, and a 10-turn sequence."""
        logger.info(f"--- Starting Latency Profiling Suite for [{self.model}] ---")

        # 1. Cold Request
        logger.info("[1/4] Executing Cold Request...")
        cold_res = await self.profile_single_turn("Open Chrome")
        logger.info(
            f"Cold Request: Total={cold_res['total_wall_ms']:.1f}ms "
            f"(Load={cold_res['stage_ollama_load_ms']:.1f}ms, "
            f"PromptEval={cold_res['stage_ollama_prompt_eval_ms']:.1f}ms, "
            f"Eval={cold_res['stage_ollama_eval_ms']:.1f}ms)"
        )

        await asyncio.sleep(1.0)

        # 2. Warm Request 1
        logger.info("[2/4] Executing Warm Request 1...")
        warm1_res = await self.profile_single_turn("Could you bring Chrome back up for me?")
        logger.info(
            f"Warm Request 1: Total={warm1_res['total_wall_ms']:.1f}ms "
            f"(Load={warm1_res['stage_ollama_load_ms']:.1f}ms, "
            f"PromptEval={warm1_res['stage_ollama_prompt_eval_ms']:.1f}ms, "
            f"Eval={warm1_res['stage_ollama_eval_ms']:.1f}ms)"
        )

        await asyncio.sleep(1.0)

        # 3. Warm Request 2
        logger.info("[3/4] Executing Warm Request 2...")
        warm2_res = await self.profile_single_turn("Open the first result.", {
            "active_browser": "chrome",
            "last_verified_action": "youtube_search",
            "relevant_entities": [{"ordinal": 1, "title": "Top Result"}],
        })
        logger.info(
            f"Warm Request 2: Total={warm2_res['total_wall_ms']:.1f}ms "
            f"(Load={warm2_res['stage_ollama_load_ms']:.1f}ms, "
            f"PromptEval={warm2_res['stage_ollama_prompt_eval_ms']:.1f}ms, "
            f"Eval={warm2_res['stage_ollama_eval_ms']:.1f}ms)"
        )

        await asyncio.sleep(1.0)

        # 4. 10-Request Sequential Warm Sequence
        logger.info("[4/4] Executing 10-Request Warm Sequence...")
        sequence_utterances = [
            "Open Chrome.",
            "Launch Notepad.",
            "Bring up the browser.",
            "Could you open Spotify?",
            "Do that again.",
            "Open the second result.",
            "Close it.",
            "Set brightness to 80 percent.",
            "Repeat whatever you just did.",
            "Hey Sarah, can you open Chrome for me?",
        ]

        warm_sequence: List[Dict[str, Any]] = []
        for idx, u in enumerate(sequence_utterances, 1):
            res = await self.profile_single_turn(u)
            warm_sequence.append(res)
            logger.info(f"  Seq {idx:02d}/10: '{u}' -> {res['intent']} in {res['total_wall_ms']:.1f}ms")

        # Statistical Calculations on Warm Sequence
        totals = [r["total_wall_ms"] for r in warm_sequence]
        loads = [r["stage_ollama_load_ms"] for r in warm_sequence]
        prompt_evals = [r["stage_ollama_prompt_eval_ms"] for r in warm_sequence]
        evals = [r["stage_ollama_eval_ms"] for r in warm_sequence]
        net_queues = [r["stage_net_queue_ms"] for r in warm_sequence]

        def get_percentile(data: List[float], p: float) -> float:
            sorted_d = sorted(data)
            k = (len(sorted_d) - 1) * (p / 100.0)
            f = int(k)
            c = min(f + 1, len(sorted_d) - 1)
            return sorted_d[f] + (k - f) * (sorted_d[c] - sorted_d[f])

        report = {
            "model": self.model,
            "cold_request": cold_res,
            "warm_request_1": warm1_res,
            "warm_request_2": warm2_res,
            "warm_sequence_stats": {
                "count": len(totals),
                "total_wall_ms": {
                    "min": min(totals),
                    "max": max(totals),
                    "mean": statistics.mean(totals),
                    "p50": get_percentile(totals, 50),
                    "p95": get_percentile(totals, 95),
                },
                "stage_breakdowns_mean_ms": {
                    "context_build": statistics.mean([r["stage_context_ms"] for r in warm_sequence]),
                    "prompt_build": statistics.mean([r["stage_prompt_ms"] for r in warm_sequence]),
                    "serialization": statistics.mean([r["stage_serialization_ms"] for r in warm_sequence]),
                    "net_queue": statistics.mean(net_queues),
                    "ollama_load": statistics.mean(loads),
                    "ollama_prompt_eval": statistics.mean(prompt_evals),
                    "ollama_token_eval": statistics.mean(evals),
                    "response_deser": statistics.mean([r["stage_response_deser_ms"] for r in warm_sequence]),
                    "schema_validation": statistics.mean([r["stage_validation_ms"] for r in warm_sequence]),
                },
            },
            "warm_sequence_runs": warm_sequence,
        }

        print("\n" + "=" * 70)
        print(f"  SERA LATENCY PROFILING REPORT — MODEL: {self.model}")
        print("=" * 70)
        print(f"  Cold Request Wall Time:       {cold_res['total_wall_ms']:.1f} ms (Load: {cold_res['stage_ollama_load_ms']:.1f} ms)")
        print(f"  Warm Request 1:               {warm1_res['total_wall_ms']:.1f} ms")
        print(f"  Warm Request 2:               {warm2_res['total_wall_ms']:.1f} ms")
        print("-" * 70)
        print("  10-TURN WARM SEQUENCE STATISTICS:")
        print(f"    Mean Total Wall Latency:    {report['warm_sequence_stats']['total_wall_ms']['mean']:.1f} ms")
        print(f"    Median (p50):               {report['warm_sequence_stats']['total_wall_ms']['p50']:.1f} ms")
        print(f"    95th Percentile (p95):      {report['warm_sequence_stats']['total_wall_ms']['p95']:.1f} ms")
        print(f"    Min / Max:                  {report['warm_sequence_stats']['total_wall_ms']['min']:.1f} ms / {report['warm_sequence_stats']['total_wall_ms']['max']:.1f} ms")
        print("-" * 70)
        print("  MEAN STAGE BREAKDOWN (10 Warm Turns):")
        b = report["warm_sequence_stats"]["stage_breakdowns_mean_ms"]
        print(f"    1. Context Construction:    {b['context_build']:.3f} ms")
        print(f"    2. Prompt Construction:     {b['prompt_build']:.3f} ms")
        print(f"    3. Request Serialization:   {b['serialization']:.3f} ms")
        print(f"    4. Network / Queue Overhead:{b['net_queue']:.1f} ms")
        print(f"    5. Ollama Model Load:       {b['ollama_load']:.1f} ms")
        print(f"    6. Ollama Prompt Eval:      {b['ollama_prompt_eval']:.1f} ms")
        print(f"    7. Ollama Token Eval:       {b['ollama_token_eval']:.1f} ms")
        print(f"    8. Response Deserialization:{b['response_deser']:.3f} ms")
        print(f"    9. Schema Validation:       {b['schema_validation']:.3f} ms")
        print("=" * 70 + "\n")

        return report


async def main():
    parser = argparse.ArgumentParser(description="SERA Semantic Latency Profiler")
    parser.add_argument("--model", type=str, default="qwen3.5:4b", help="Model name (e.g. qwen3.5:4b or qwen3.5:2b)")
    parser.add_argument("--output", type=str, default="", help="Path to write JSON output report")
    args = parser.parse_args()

    profiler = LatencyProfiler(model=args.model)
    try:
        report = await profiler.run_profiling_suite()
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to {args.output}")
    finally:
        await profiler.close()


if __name__ == "__main__":
    asyncio.run(main())
