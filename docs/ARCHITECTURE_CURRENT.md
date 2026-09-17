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

* **`SERARuntime` (`app/core/runtime.py`):** Central coordinator initializing hotkeys, microphone streams, wake-word listeners, and WebSocket server dispatch. Supports clean cancellation via `cancel_task()`.
* **`SERAState` (`app/core/state.py`):** Deterministic state machine tracking `SERAStatus` (`IDLE`, `LISTENING`, `THINKING`, `EXECUTING`, `SPEAKING`, `ERROR`). Thread-safe state change listeners broadcast to UI clients.
* **`EventBus` (`app/core/events.py`):** Async publish-subscribe bus with topics: `TASK_STARTED`, `TOOL_STARTED`, `TOOL_COMPLETED`, `AGENT_RESPONSE`, `TASK_COMPLETED`, `TASK_FAILED`, `STATE_CHANGED`.
* **`HotkeyListener` (`app/core/hotkey.py`):** Global keyboard hook on Windows capturing `Ctrl+Space` for Hold-to-Talk audio recording.

---

## 2. Speech Subsystem (`app/speech/`, `app/models/stt/`) — ✅ IMPLEMENTED

* **Primary STT (`app/models/stt/gemini.py`):** Google Gemini 3.5 Transcribe (`gemini-3.5-transcribe`) using direct Google GenAI SDK. Streams 16-bit PCM WAV audio; handles punctuation, capitalization, and language detection.
* **Fallback STT (`app/speech/stt.py`):** Local `faster-whisper` running on CUDA FP16 (small model) for complete offline resiliency.
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
