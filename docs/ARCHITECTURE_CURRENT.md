# SERA — Current Architecture (As-Built)

> **Author:** Keshava Pandi A S  
> **Creator:** Keshava Pandi A S  
> **Developer:** Keshava Pandi A S  
> **Document Status:** Empirical snapshot of the current active codebase.  
> **Classification Key:**  
> ✅ **IMPLEMENTED** — Fully operational, tested with real-world verification.  
> ⚠️ **PARTIAL** — Functional but currently undergoing rework or stabilization.  
> 📋 **PLANNED** — Defined in architecture specifications; implementation not yet complete.

---

## 1. Runtime Subsystem (`app/core/`) — ✅ IMPLEMENTED

```
┌────────────────────────────────────────────────────────┐
│                   SERARuntime Core                     │
│  - asyncio main loop orchestrating perception & tools  │
│  - Single active task handle with cancellation gates   │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
                ▼                        ▼
      ┌──────────────────┐     ┌──────────────────┐
      │  SERAState Store │     │     EventBus     │
      │  Deterministic   │     │  Async Pub/Sub   │
      │  State Machine   │     │  String Topics   │
      └──────────────────┘     └──────────────────┘
```

* **`SERARuntime` (`app/core/runtime.py`):** Central coordinator initializing hotkeys, microphone streams, wake-word listeners, and WebSocket server dispatch. Supports clean task cancellation via `cancel_task()`. Enforces strict terminal state semantics where failed/broken/cancelled tasks emit `TASK_FAILED`/`TASK_CANCELLED` and never emit `TASK_COMPLETED`.
* **`CommandPipeline` (`app/core/command_pipeline.py`):** Orchestrator coordinating canonical multi-stage utterance normalization, deterministic intent resolution, verified context persistence, and execution dispatch through the canonical `StatefulGraphRuntime`.
* **Semantic Normalization & Reference Resolution (Phase 3A-C):**
  * Multi-stage normalization: Addressing/vocatives ("Hey Sarah, ...") and politeness/courtesy modals ("can you please...", "...for me") are cleanly stripped without corrupting target entities.
  * Repeat modifiers: "again", "once more" are captured as semantic modifiers (`modifier="repeat"`) rather than becoming part of application names (e.g. "Open Chrome again" resolves to `action="open_application"`, `target="chrome"`, `modifier="repeat"`).
  * Contextual Ordinal References: "Open the first result", "click second one", "result 1" resolve deterministically against verified `search_results` in `context_state` into `browser_open(url=...)`. If no search results exist in context, the system provides polite conversational guidance rather than falling through to generic application launching.
* **`StatefulGraphRuntime` (`app/core/graph/`) — ✅ IMPLEMENTED (Phase 3A & 3A-C):**
  * Asynchronous directed execution graph engine orchestrating the canonical lifecycle: `PERCEIVE → NORMALIZE → CONTEXT → ROUTE → PLAN → EXECUTE → OBSERVE → VERIFY → DECIDE → RECOVER → RESPOND → DONE`.
  * Strongly-typed `GraphState` containing Identity (`execution_id`, `task_id`), Input, Context, Routing, Plan, Execution, Recovery, Outcome (`GraphExecutionStatus`), Presence, and Telemetry.
  * Node Contract: Receives `GraphState` and `asyncio.Event` cancellation primitive; produces updated state and structured `GraphDecision` (`CONTINUE`, `DONE`, `RETRY`, `REPLAN`, `HANDOFF`, `FAIL`, `CANCEL`).
  * First-Class Completion Gate: `VerifyNode` executes empirical inspection via `EvidenceVerificationFabric` before any task is permitted to commit `DONE`.
  * Real-Time Interruption & Deterministic Cancellation: `ExecuteNode` uses `asyncio.wait(..., return_when=FIRST_COMPLETED)` across tool execution and cancellation events, immediately halting tools and transitioning to `CANCELLED` with zero dangling tasks, running no subsequent nodes, and emitting no misleading success events.
  * Fast-Path Bypass: Trivial deterministic commands traverse the short path (`PERCEIVE → NORMALIZE → CONTEXT → ROUTE → EXECUTE → OBSERVE → VERIFY → DECIDE → RESPOND → DONE`) with sub-millisecond orchestration latency (<0.2ms).
* **`SERAState` (`app/core/state.py`):** Deterministic state machine tracking `SERAStatus` (`IDLE`, `LISTENING`, `THINKING`, `EXECUTING`, `SPEAKING`, `ERROR`). Thread-safe state change listeners broadcast to UI clients.
* **`EventBus` (`app/core/events.py`):** Async publish-subscribe bus emitting correlated execution events (`GRAPH_STARTED`, `GRAPH_NODE_ENTERED`, `GRAPH_NODE_COMPLETED`, `GRAPH_TRANSITION`, `GRAPH_COMPLETED`, `GRAPH_CANCELLED`, `GRAPH_FAILED`, `TASK_STARTED`, `TOOL_STARTED`, `TASK_COMPLETED`). Presence deduplication ensures task structures and model selections are materialized exactly once per transition.
* **Unified Local Semantic Interpreter Subsystem (`app/core/semantic/`) — 🔄 IN EVALUATION / SHADOW (Phase 3A-D):**
  * Local SLM (`qwen3.5:4b` via Ollama on localhost:11434) translating natural language & compact context into strongly typed `CanonicalIntent` Pydantic models.
  * Architectural Isolation: Interprets language only. Never executes actions, never controls Windows, never touches tools, never hallucinates URLs, never declares task completion.
  * Compact Context Strategy: Feeds only language-essential context (`active_application`, `active_browser`, `last_verified_action`, `relevant_entities`, `available_intents`); never feeds complete GraphState or system secrets.
  * Strict Schema Validation: `SemanticValidator` enforces valid intent names, normalizes action families, rejects hallucinated tools, and gracefully converts malformed responses into structured clarification requests.
  * Standalone Evaluation Harness (`tests/semantic_interpreter/`): 108 curated cases evaluating APPLICATION, SYSTEM, CONTEXTUAL, POLITENESS, NATURAL_SPEECH, COMPOUND, REFERENCE, REPETITION, and AMBIGUITY_NEGATIVE families, measuring p50/p95 latency and peak VRAM.
  * Shadow Mode Integration: Concurrently runs in `CommandPipeline` during real turns, logging `SEMANTIC_SHADOW` comparison telemetry alongside legacy deterministic parsing.
* **`GlobalHotkeyManager` (`app/core/hotkey_manager.py`):** Single authoritative system-wide keyboard hook on Windows capturing `Ctrl+Alt+Space` for Hold-to-Talk audio recording with dual-release and Win32 focus recovery.

---

## 2. Speech Subsystem (`app/speech/`, `app/models/stt/`) — ✅ IMPLEMENTED

* **English-Constrained STT Policy (Phase 3A-C):** Explicitly requests English transcription (`en-US`, `en`) with verbatim configuration to prevent unwanted multilingual hallucination (e.g. Hindi translation of English voice commands).
* **Primary STT (`app/models/stt/gemini.py`):** Google Gemini 3.5 Transcribe (`gemini-3.5-transcribe`) using direct Google GenAI SDK. Configured with verbatim audio transcription parameters and explicit English language constraints.
* **Fallback STT (`app/models/stt/whisper.py`):** Local `faster-whisper` running on CUDA FP16 (small model) with hard-enforced English language code decoding (`language="en"`) for offline resiliency.
* **Audio Manager (`app/speech/audio_manager.py`):** PyAudio non-blocking stream capture with VAD energy thresholding.
* **TTS (`app/speech/tts.py`):** Streaming TTS output with instant energy-based voice interruption cutoff.
* **Spatial Audio Cues (`app/speech/audio_cues.py`):** High-frequency chimes and acoustic feedback for state transitions (`listen_start`, `listen_stop`, `task_complete`, `task_fail`).

---

## 3. LLM & Model Subsystem (`app/models/llm/`) — ✅ IMPLEMENTED

* **Provider Abstractions:** Clean async implementations for:
  * Google Gemini (`gemini.py` — Flash 2.5, Flash Lite, Thinking models).
  * Groq (`groq.py` — Llama-3.3 70B, Qwen-2.5 32B/72B).
  * Mistral AI (`mistral.py` — Codestral, Mistral Small/Large).
  * OpenRouter (`openrouter.py` — Universal fallover).
  * Cerebras (`cerebras.py` — Ultra-low latency Llama-3.1).
  * Ollama (`ollama.py` — Local offline LLM execution).
* **OpenAI-Compatible Bridge (`openai_compatible.py`):** Universal client for any standard `/v1/chat/completions` endpoint.

---

## 4. Router Subsystem (`app/core/router.py`) — ✅ IMPLEMENTED

* **`ModelRouter`:** Maps specialized roles (`reasoning`, `fast`, `desktop`, `vision`, `ocr`, `embeddings`, `stt`, `tts`) to candidate provider chains.
* **`ResourceStateCache` (`app/core/resource_cache.py`):** Tracks model-level cooldowns, error rates, and quota exhaustion in volatile memory without altering persistent configuration.
* **Latency Tracker (`app/models/llm/latency.py`):** Exponential moving average response time calculation per provider/model.
* **Health Tracker (`app/models/llm/health.py`):** Per-model health status (`HEALTHY`, `DEGRADED`, `COOLING_DOWN`, `OFFLINE`).

---

## 5. Desktop Automation Tools (`app/tools/windows/`, `app/tools/desktop/`) — ✅ IMPLEMENTED

* **`WindowsApplicationTool` (`app/tools/windows/apps.py`):**
  * Launches Windows executables via PowerShell/ShellExecute.
  * **Empirical Verification Gate:** Must verify the target process ID exists (`Get-Process`) and the application window handle is registered before returning `success: True`. Returns `verified: False` and transitions state to `BROKEN` if launch fails.
* **System Controls (`app/tools/windows/system.py`, `power.py`):** Audio volume adjustment, display power states, process termination.
* **Filesystem Tools (`app/tools/filesystem/files.py`):** Workspace sandboxed file reading, writing, and directory listing.

---

## 6. Browser & Web Research Tools (`app/tools/browser/`) — ✅ IMPLEMENTED

* **`WebSearchTool` (`app/tools/browser/web_search.py`):**
  * Real DuckDuckGo HTML scraping engine with zero API key requirement.
  * **Ad & Sponsor Filtering:** Regex-based removal of commercial ads and sponsored links.
  * **Strict Data Contract:** Returns structured list of dicts with `title`, `url`, `snippet`, `source`.
  * **Empirical Verification Gate:** Fails with `count: 0` if zero search results are obtained. Emits live preview events to the UI before synthesis.
* **YouTube Navigation (`app/tools/browser/youtube.py`):** Specialized query constructor and direct video/search URL launching.

---

## 7. Vision & Perception (`app/vision/`, `app/tools/screen/`) — ⚠️ PARTIAL

* **Screen Capture (`app/tools/screen/capture.py`):** High-speed desktop screen capture via Windows desktop duplication / PIL.
* **Screen Perception Tool (`app/tools/screen/vision.py`):** Submits current desktop screenshot to multimodal LLM with user prompt.
* **Vision Analyzer (`app/vision/analyzer.py`):** Provides contextual OCR and visual UI element bounding box detection. Functional, but full UI automation based on visual bounding box clicking is in development.

---

## 8. User Interface Subsystems (`app/ui/`)

### 8.1 Primary SERA Presence (Body 1) — ✅ IMPLEMENTED (Phase B)
* **`presence.html` & `presence_engine.js`:**
  * 100% alpha-transparent WebGL canvas powered by Three.js.
  * Concentric mathematical rings, luminous white singularity core, and 12,000+ GPGPU curl-noise particles.
  * 9 physical animation states (Idle, Listening, Transcribing, Thinking, Executing, Speaking, Broken, Cancelled, Completed).
  * Signature Computational Cellular Reconstruction completion sequence.
  * Single-line kinetic status morpher with zero chat bubbles.
  * Served at `http://127.0.0.1:8765/presence`.

### 8.2 Command Center Server & Views (Body 2) — ⚠️ PARTIAL (Undergoing Reorganization)
* **Server (`app/ui/server.py`):** Native async Python HTTP/WebSocket server listening on port 8765. Broadcasts real-time events to all connected clients.
* **Current Views (`app/ui/static/js/views/`):**
  * `live.js`: Live execution events, audio visualizer, chat input.
  * `workflow.js`: Drag-and-drop node graph (being restructured into dynamic timeline).
  * `architect.js`: 3-column candidate configuration studio.
  * `providers.js`, `memory.js`, `history.js`, `security.js`, `debug.js`.

---

## 9. Persistence & Storage — ⚠️ PARTIAL

* **Configuration:** `config/config.yaml` stores provider API keys, default models, and system parameters.
* **Live History:** `scratch/live_history.json` stores the last 100 WebSocket events to survive browser refresh.
* **Workflow Layout:** `config/workflow_layout.json` stores 2D visual node coordinates.
* **Memory Tiers:** Rudimentary in-memory lists in `app/memory/`. Partitioned 6-tier persistent memory and local vector RAG are **PLANNED** for Phase F.

---

## 10. Telemetry & Security — ✅ IMPLEMENTED

* **Telemetry (`app/core/telemetry.py`):** Structured JSON event logging across execution traces.
* **Security Manager (`app/utils/security.py`):** Multi-step loop counters (5-step limits), timeout boundaries (10s max per action), and permission elevation gates for destructive system tools.
