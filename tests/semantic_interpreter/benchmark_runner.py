"""
SERA 2.0 — Standalone Semantic Interpreter Benchmark Runner.

Evaluates local SLM (Qwen3.5-4B via Ollama) on a comprehensive test suite of 100+ cases.
Measures semantic accuracy, category breakdowns, latency distributions (p50/p95),
and hardware resource usage (VRAM, RAM, CPU).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from typing import Any, Dict, List, Optional
import httpx
import psutil

from app.core.semantic.prompt import build_semantic_prompt
from app.core.semantic.validator import SemanticValidator
from tests.semantic_interpreter.evaluator import SemanticEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sera.semantic.benchmark")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL_NAME = os.environ.get("SEMANTIC_MODEL", "qwen3.5:4b")


def get_gpu_vram_mb() -> Optional[float]:
    """Queries nvidia-smi for current GPU memory used in MB."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2.0
        )
        if res.returncode == 0 and res.stdout.strip():
            lines = res.stdout.strip().split("\n")
            return float(lines[0])
    except Exception:
        pass
    return None


def get_system_ram_mb() -> float:
    """Returns total system RAM used in MB."""
    vm = psutil.virtual_memory()
    return float(vm.used / (1024 * 1024))


class SemanticBenchmarkRunner:
    """Executes standalone semantic benchmark against local Ollama instance."""

    def __init__(self, model: str = MODEL_NAME, base_url: str = OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)

    def check_health(self) -> bool:
        """Verifies Ollama is running and responsive."""
        try:
            resp = self.client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Cannot connect to Ollama at {self.base_url}: {e}")
            return False

    def list_models(self) -> List[str]:
        """Returns list of models installed in Ollama."""
        try:
            resp = self.client.get(f"{self.base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def call_ollama(self, messages: List[Dict[str, str]]) -> Tuple[str, float, int, int]:
        """Calls Ollama chat endpoint with deterministic parameters.
        
        Returns:
            (raw_response_text, latency_ms, prompt_eval_count, eval_count)
        """
        start = time.perf_counter()
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
                "top_p": 0.9,
            }
        }
        resp = self.client.post(f"{self.base_url}/api/chat", json=payload)
        latency_ms = (time.perf_counter() - start) * 1000.0

        if resp.status_code != 200:
            raise RuntimeError(f"Ollama API error {resp.status_code}: {resp.text}")

        data = resp.json()
        content = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        eval_tokens = data.get("eval_count", 0)

        return content, latency_ms, prompt_tokens, eval_tokens

    def run_benchmark(self, cases_path: Path, output_report_path: Optional[Path | str] = None) -> Dict[str, Any]:
        """Runs the entire benchmark and generates structured metrics."""
        with open(cases_path, "r", encoding="utf-8") as f:
            cases = json.load(f)

        logger.info(f"Loaded {len(cases)} benchmark cases from {cases_path}")

        # Check server health
        if not self.check_health():
            raise ConnectionError(f"Ollama is not running at {self.base_url}. Start Ollama first.")

        available_models = self.list_models()
        logger.info(f"Available Ollama models: {available_models}")

        # Check model availability
        matching = [m for m in available_models if self.model in m or m.startswith(self.model.split(":")[0])]
        if not matching:
            logger.warning(f"Target model '{self.model}' not found in installed models! Attempting inference anyway...")

        # Cold start measurement
        logger.info("Performing cold start probe...")
        cold_start_begin = time.perf_counter()
        cold_prompt = build_semantic_prompt("Open Chrome.", {})
        try:
            _, cold_latency_ms, _, _ = self.call_ollama(cold_prompt)
            cold_load_time_ms = (time.perf_counter() - cold_start_begin) * 1000.0
            logger.info(f"Cold start model probe complete in {cold_load_time_ms:.1f}ms (call: {cold_latency_ms:.1f}ms)")
        except Exception as e:
            logger.error(f"Cold start probe failed: {e}")
            raise

        results = []
        latencies: List[float] = []
        tokens_eval: List[int] = []
        category_stats: Dict[str, Dict[str, int]] = {}
        invalid_json_count = 0
        clarification_correct = 0
        clarification_total = 0
        reference_correct = 0
        reference_total = 0

        initial_vram = get_gpu_vram_mb()
        initial_ram = get_system_ram_mb()
        peak_vram = initial_vram or 0.0
        peak_ram = initial_ram

        logger.info(f"Starting execution of {len(cases)} cases...")

        for i, case in enumerate(cases, 1):
            c_id = case["id"]
            cat = case.get("category", "GENERAL")
            utterance = case["utterance"]
            context = case.get("context", {})
            expected = case["expected"]

            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "correct": 0}
            category_stats[cat]["total"] += 1

            if expected.get("needs_clarification"):
                clarification_total += 1
            if expected.get("reference"):
                reference_total += 1

            messages = build_semantic_prompt(utterance, context)

            try:
                raw_out, lat_ms, p_tok, e_tok = self.call_ollama(messages)
                latencies.append(lat_ms)
                tokens_eval.append(e_tok)

                intent_obj, is_valid, err_reason = SemanticValidator.validate(raw_out)
                if not is_valid:
                    invalid_json_count += 1

                is_match, comp_matches, failure_reason = SemanticEvaluator.evaluate_case(intent_obj, expected)

                if is_match:
                    category_stats[cat]["correct"] += 1
                    if expected.get("needs_clarification"):
                        clarification_correct += 1
                    if expected.get("reference"):
                        reference_correct += 1

                # Sample hardware resources
                current_vram = get_gpu_vram_mb()
                if current_vram and current_vram > peak_vram:
                    peak_vram = current_vram
                current_ram = get_system_ram_mb()
                if current_ram > peak_ram:
                    peak_ram = current_ram

                status_mark = "PASS" if is_match else "FAIL"
                logger.info(f"[{i:03d}/{len(cases):03d}] {status_mark} [{cat}] '{utterance}' -> {intent_obj.intent} ({lat_ms:.1f}ms)")
                if not is_match:
                    logger.warning(f"     Reason: {failure_reason}")

                results.append({
                    "id": c_id,
                    "category": cat,
                    "utterance": utterance,
                    "latency_ms": lat_ms,
                    "eval_tokens": e_tok,
                    "is_valid_json": is_valid,
                    "is_match": is_match,
                    "failure_reason": failure_reason,
                    "predicted": intent_obj.to_dict(),
                    "expected": expected
                })

            except Exception as e:
                logger.error(f"[{i:03d}/{len(cases):03d}] ERROR '{utterance}': {e}")
                results.append({
                    "id": c_id,
                    "category": cat,
                    "utterance": utterance,
                    "is_match": False,
                    "failure_reason": str(e),
                    "is_valid_json": False
                })

        # Calculate metrics
        latencies_sorted = sorted(latencies)
        total_eval = len(results)
        total_correct = sum(1 for r in results if r.get("is_match"))
        accuracy = (total_correct / total_eval) * 100.0 if total_eval > 0 else 0.0

        p50_lat = latencies_sorted[int(len(latencies_sorted) * 0.50)] if latencies_sorted else 0.0
        p95_lat = latencies_sorted[int(len(latencies_sorted) * 0.95)] if latencies_sorted else 0.0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
        min_lat = latencies_sorted[0] if latencies_sorted else 0.0
        max_lat = latencies_sorted[-1] if latencies_sorted else 0.0

        report = {
            "model": self.model,
            "timestamp": time.time(),
            "total_cases": total_eval,
            "correct": total_correct,
            "incorrect": total_eval - total_correct,
            "accuracy_percent": round(accuracy, 2),
            "invalid_json_count": invalid_json_count,
            "clarification_metrics": {
                "total": clarification_total,
                "correct": clarification_correct,
                "accuracy_percent": round((clarification_correct / clarification_total * 100.0), 2) if clarification_total > 0 else 0.0
            },
            "reference_metrics": {
                "total": reference_total,
                "correct": reference_correct,
                "accuracy_percent": round((reference_correct / reference_total * 100.0), 2) if reference_total > 0 else 0.0
            },
            "latency_ms": {
                "cold_load_time": round(cold_load_time_ms, 2),
                "avg": round(avg_lat, 2),
                "p50": round(p50_lat, 2),
                "p95": round(p95_lat, 2),
                "min": round(min_lat, 2),
                "max": round(max_lat, 2)
            },
            "resources": {
                "peak_vram_mb": round(peak_vram, 2),
                "peak_system_ram_mb": round(peak_ram, 2),
                "initial_vram_mb": round(initial_vram, 2) if initial_vram else None,
                "initial_ram_mb": round(initial_ram, 2)
            },
            "category_breakdown": category_stats,
            "results": results
        }

        # Print human-readable report
        print("\n" + "="*70)
        print("  SERA 2.0 SEMANTIC INTERPRETER BENCHMARK REPORT")
        print(f"  Model: {self.model} | Cases: {total_eval}")
        print("="*70)
        print(f"  Overall Accuracy:            {total_correct}/{total_eval} ({accuracy:.1f}%)")
        print(f"  Invalid JSON Outputs:        {invalid_json_count}")
        print(f"  Clarification Correct:       {clarification_correct}/{clarification_total}")
        print(f"  Reference Resolution Match:  {reference_correct}/{reference_total}")
        print("-"*70)
        print("  LATENCY (ms):")
        print(f"    Cold Start Load:           {cold_load_time_ms:.1f} ms")
        print(f"    Average Warm Latency:      {avg_lat:.1f} ms")
        print(f"    Median (p50):              {p50_lat:.1f} ms")
        print(f"    p95 Latency:               {p95_lat:.1f} ms")
        print(f"    Min / Max:                 {min_lat:.1f} ms / {max_lat:.1f} ms")
        print("-"*70)
        print("  HARDWARE RESOURCES:")
        if peak_vram:
            print(f"    Peak GPU VRAM:             {peak_vram:.1f} MB")
        print(f"    Peak System RAM:           {peak_ram:.1f} MB")
        print("-"*70)
        print("  CATEGORY BREAKDOWN:")
        for cat, stat in category_stats.items():
            c_pct = (stat['correct'] / stat['total'] * 100.0) if stat['total'] > 0 else 0.0
            print(f"    {cat:<25} {stat['correct']}/{stat['total']} ({c_pct:5.1f}%)")
        print("="*70 + "\n")

        # Save machine-readable JSON report
        out_report_path = Path(output_report_path) if output_report_path else (cases_path.parent / f"benchmark_results_{self.model.replace(':', '_')}.json")
        with open(out_report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Detailed machine-readable report written to {out_report_path}")

        return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SERA Semantic Benchmark Runner")
    parser.add_argument("--model", type=str, default=MODEL_NAME, help="Model to benchmark (e.g. qwen3.5:2b, qwen3.5:4b)")
    parser.add_argument("--cases", type=str, default=str(Path(__file__).parent / "benchmark_cases.json"), help="Cases JSON path")
    parser.add_argument("--output", type=str, default="", help="Output report JSON path")
    args = parser.parse_args()

    cases_file = Path(args.cases)
    out_file = Path(args.output) if args.output else None
    runner = SemanticBenchmarkRunner(model=args.model)
    runner.run_benchmark(cases_file, output_report_path=out_file)
