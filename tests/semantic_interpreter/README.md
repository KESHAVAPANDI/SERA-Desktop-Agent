# SERA 2.0 — Standalone Semantic Interpreter Benchmark

## Overview
This standalone benchmark suite evaluates local small language models (specifically **Qwen3.5-4B** via Ollama) as SERA's **Local Semantic Interpreter**.

The Semantic Interpreter translates natural-language user utterances + compact execution context into a strongly typed `CanonicalIntent` JSON payload.

## Scope & Constraints
- **Zero Tool Execution**: The benchmark harness never executes tools, touches Windows APIs, or triggers browser automations.
- **Semantic Generalization**: Phrasings are diverse across 9 semantic categories with 108 total test cases.
- **No Production Lookup Tables**: The production prompt contains general schema guidelines and intent taxonomy, never hand-curated lists of benchmark sentences.
- **Telemetry Measured**: Measures cold-start model load time, warm inference latency (p50, p95, avg), peak GPU VRAM (MB), peak system RAM (MB), and semantic accuracy.

## Running the Benchmark
Ensure Ollama is running locally with `qwen3.5:4b` downloaded:
```powershell
ollama pull qwen3.5:4b
ollama serve
```

Execute the benchmark runner:
```powershell
python tests/semantic_interpreter/benchmark_runner.py
```

The runner outputs a human-readable telemetry summary table and saves detailed test results to `tests/semantic_interpreter/benchmark_results.json`.
