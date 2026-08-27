# SERA 1.0 — Phase 5D.5 Comprehensive Diagnosis & Investigation

## 1. Executive Summary & Root Cause Analysis

Following manual runtime observations and trace analysis across the SERA 1.0 runtime, event bus, and UI layers, this diagnosis identifies the exact failure modes and architectural gaps targeted by Phase 5D.5:

```
[AGENT / RUNTIME]              [EVENT BUS / WEBSOCKET]             [LIVE UI & THEATER]
+--------------------------+    +---------------------------+     +--------------------------+
| - Voice turns missed     |    | - No uniform turn/task ID |     | - No embedded theater    |
|   AGENT_RESPONSE emit    | => | - Missing STREAM_START/   |  => |   on Live page           |
| - Blind sequential       |    |   COMPLETE contract       |     | - Unsettled carets       |
|   fallback on 429        |    | - Duplicate role select   |     | - Giant Architect graph  |
| - Token estimation       |    |   event noise             |     |   without Resource-Aware |
|   missing in preflight   |    |                           |     |   mode                   |
+--------------------------+    +---------------------------+     +--------------------------+
```

---

## 2. Deep-Dive Findings by Investigation Area

### 2.1 Why final assistant responses still do not reliably reach Live
1. **Voice Turns Asymmetry**: In `app/core/runtime.py`, `start_canonical_task()` emits `AGENT_RESPONSE` and `TASK_COMPLETED`, but `_process_voice_turn()` and `_process_turn()` called `process_text()` without emitting `AGENT_RESPONSE` or wrapping the voice turn in canonical task lifecycle events.
2. **Streaming Contract Breakage**: `agent.run_stream()` yielded raw tokens into `_stream_and_play_tts()`, but did not broadcast `STREAM_START`, `STREAM_TOKEN`, `STREAM_COMPLETE`, or `AGENT_RESPONSE` over the `EventBus` to WebSocket clients.
3. **Empty / Tool-Only Turns**: For tasks that executed desktop actions (e.g. "Open Chrome"), no conversational acknowledgment was emitted if the agent terminated without returning explicit conversational text, leaving the Live chat stream without a closing assistant message.

### 2.2 Why the runtime performs multiple role/model selection events for simple tasks
1. **Repeated Route Invocations**: `agent.run()` called `router.generate_with_fallback()` multiple times in tool-loop iterations and error fallbacks, emitting `MODEL_SELECTED` on every iteration even when using the same candidate.
2. **Lack of Fast Conversational Bypass**: Simple queries ("Hi", "Hello") sometimes cascaded into full multi-step planner checks before being caught by agent fast paths.

### 2.3 Why resource-aware selection is not preventing unnecessary sequential fallback
1. **No Preflight Resource Evaluation**: `ModelRouter` sequentially stepped through candidates `[0, 1, 2, ...]`, only reacting *after* receiving an HTTP 429/500 error from the provider.
2. **Missing Token Estimation & Header Tracking**: Provider responses returned remaining request and token headers (`x-ratelimit-remaining-tokens`), but these were discarded rather than cached in a centralized `ResourceStateCache`.
3. **Absence of `RESOURCE_AWARE` Mode**: Architect supported `PRIMARY_ONLY`, `FALLBACK_ORDER`, and `CUSTOM`, but had no mode allowing dynamic scoring based on current health, latency, token feasibility, and quota headroom.

### 2.4 How `task_id` flows between Live and Workflow
1. **Disjoint Identifiers**: Some runtime subsystems generated independent `turn_id` strings (e.g., `turn-1-abc`) while tasks used `task_12345`, leading to mismatched event handling in the UI.
2. **Missing Authoritative Contract**: Events did not strictly carry `{task_id, turn_id, event_id, timestamp}`, allowing late events from cancelled or completed tasks to trigger UI updates.

### 2.5 How the embedded Live workflow can reuse the existing dynamic Workflow renderer
1. **Unified Theater Engine**: Live page had no embedded canvas for active execution, forcing users to click away to View 2.
2. **Shared Component Architecture**: `WorkflowView` dynamic materialization and SVG plasma pipeline can be encapsulated into a reusable execution renderer mounted both inside `#live-embedded-theater` on the Live page and inside `#view-workflow` for full-screen inspection.

### 2.6 How Architect can be simplified without losing configuration capabilities
1. **Unused Giant Canvas**: The full-screen canvas in View 3 is overly complex for model selection configuration.
2. **Streamlined 3-Column List-Detail**:
   - **Left Column**: Clean role list (`REASONING`, `FAST`, `DESKTOP`, `VISION`, `OCR`, `EMBEDDINGS`, `STT`, `TTS`).
   - **Center Column**: Selected role configuration with 4 execution modes (`PRIMARY ONLY`, `FALLBACK ORDER`, `RESOURCE AWARE`, `CUSTOM`) and semantic priority list.
   - **Right Column**: Interactive routing preview & simulation runner ("Why this model?" and failure simulations).

---

## 3. Targeted Solution Architecture & Implementation Order

1. **Assistant Response & Streaming Contract**:
   - Standardize `STREAM_START` ➔ `STREAM_TOKEN`* ➔ `STREAM_COMPLETE` ➔ `AGENT_RESPONSE` (status: `COMPLETED`).
   - Emit `AGENT_RESPONSE` for all speech turns, text tasks, and action acknowledgements.
2. **Task Lifecycle Synchronization**:
   - Strict `{task_id, turn_id, event_id, timestamp}` metadata on all runtime events. Late event suppression in frontend.
3. **ResourceStateCache & Token Estimator**:
   - Capture HTTP rate-limit headers (Groq, Mistral, Cerebras, OpenRouter).
   - Compute `estimated_request_tokens = input_tokens + expected_output_tokens`.
   - Implement `candidate_score = capability_fit + health_score + quota_headroom + latency_score + reliability_score + preference - rate_limit_risk - cooldown_penalty`.
4. **Adaptive Resource-Aware Router**:
   - Preflight routing decision under ~50ms without blind sequential fallbacks.
   - Local intent fast-path for greetings ("Hi", "Hello") and system actions.
5. **Live Embedded Temporal Theater**:
   - Live page collapses conversation into `TASK IN PROGRESS` banner during active execution.
   - Embed pure black dynamic temporal canvas directly on Live page.
   - Single shared plasma rendering engine between Live and Workflow.
6. **Simplified Architect Surface & "Why This Model" Inspector**:
   - Clean 3-column layout with `RESOURCE AWARE` mode.
   - "Why This Model" explanation breakdown.
   - Safe offline simulation runner.
