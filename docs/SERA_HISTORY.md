# SERA History: Evolution of the Personal Desktop AI Operating System

This document provides a comprehensive, chronologically accurate record of the architectural, speech, model, tool, and visual evolution of SERA (**S**emantic **E**xecution & **R**untime **A**ssistant). Every milestone documented here corresponds to actual engineering phases, commits, and verified system behavior in the repository.

---

## Phase 1 — Core Runtime

### Initial Inception
SERA began as an experimental voice-first desktop companion on Windows. The core goal was to create a local-first agent capable of taking voice input, understanding high-level desktop intents, invoking local Windows automation scripts, and responding through acoustic speech synthesis.

### Architectural Components Established:
* **Runtime Core (`app/core/runtime.py`):** An asynchronous event loop orchestrating the entire lifecycle: audio capture -> transcription -> classification -> planning -> tool execution -> synthesis.
* **State Machine (`app/core/state.py`):** Formalized discrete system states: `IDLE`, `LISTENING`, `THINKING`, `EXECUTING`, `SPEAKING`, `ERROR`. Transitions were made deterministic to avoid race conditions between voice audio and task execution.
* **EventBus (`app/core/events.py`):** An internal publish-subscribe bus decoupling speech input, state updates, and tool invocations. Core event topics included `TASK_STARTED`, `TOOL_STARTED`, `TOOL_COMPLETED`, `AGENT_RESPONSE`, `TASK_COMPLETED`, and `STATE_CHANGED`.
* **Initial Speech Stack:**
  * STT: Local Whisper models via `faster-whisper` (FP16 on CUDA).
  * TTS: Basic streaming synthesis pipeline utilizing Fish Audio and local fallback engines.
* **Early Tools:** Basic PowerShell application launcher (`start <app>`), window title query via `pywin32`, and volume control.

---

## Phase 2 — Voice Architecture & Interruption

### The Voice Loop Challenge
Early testing revealed that conversational voice agents fail in real-world desktop environments if the user cannot interrupt the assistant while it speaks, or if background television/office noise triggers false activations.

### Key Innovations:
* **Hold-to-Talk Mechanism (`Ctrl+Space`):** While open-mic voice activity detection (VAD) was supported, an explicit global keyboard hook (`app/core/hotkey.py`) was introduced. Holding `Ctrl+Space` guarantees dedicated command capture, eliminating accidental ambient noise capture.
* **Wake-Word Yielding:** A local wake-word detector ("SERA") was trained and deployed using `openWakeWord`. When wake-word audio triggers, the runtime automatically yields background tasks, focuses the listening pipeline, and initiates audio buffer capture.
* **Acoustic Interruption:** Integrated a real-time energy VAD gate into the output audio streaming loop. The moment the user begins speaking while SERA is in the `SPEAKING` state, the TTS audio playback stream is immediately severed (`TTS_INTERRUPTED`), and the runtime transitions back to `LISTENING`.

---

## Phase 3 — Multi-Model Architecture & Role Specialization

### Decoupling from Single-LLM Lock-in
Relying on a single proprietary model proved brittle: models with strong reasoning were often too slow for rapid conversation, while fast text models frequently failed at structured tool calling.

### Role-Based Model Routing (`app/models/llm/`):
SERA established a provider-agnostic abstraction layer (`BaseLLMProvider`) and categorized system workloads into specialized roles:
1. **Reasoning Role:** High-parameter models (e.g., Groq Llama-3.3 70B, Mistral Large) tasked with complex multi-step planning, intent classification, and ambiguous query decomposition.
2. **Fast Role:** Low-latency, high-throughput models (e.g., Mistral Small, Gemini Flash Lite) for immediate conversational feedback and status generation.
3. **Vision Role:** Multimodal vision models (e.g., Groq Qwen-2.5-VL 72B, Gemini Flash) for parsing screenshots, recognizing UI elements, and extracting visual context.
4. **OCR & Embeddings:** Dedicated endpoints for high-density document reading and vector indexing.
5. **Fallback Chains:** Each role was assigned an ordered fallback array so that if the primary model failed or returned an error, the request automatically cascaded to the next provider.

---

## Phase 4 — Provider Expansion & Health Isolation

### Expanding Compute Pools
As model capabilities rapidly evolved across providers, SERA integrated native clients for:
* **Mistral AI:** Codestral (tool calling), Mistral Small/Large, Mistral Embed.
* **Groq:** Ultra-low latency inference for Llama-3.3-70B and Qwen models.
* **Google Gemini:** Gemini Flash and multimodal APIs.
* **OpenRouter:** Universal failover pool for diverse community models.
* **Local Ollama:** Completely offline fallback when internet connectivity is severed.

### Fine-Grained Model Health Isolation (`app/models/llm/health.py`):
In early implementations, if a provider returned HTTP 429 (rate limit), the entire provider was marked down. Phase 4 introduced **per-model health tracking**. If `llama-3.3-70b-versatile` hits a token limit on Groq, only that specific model enters a temporary cooldown; other models on the same provider continue operating normally. Latency tracking (`app/models/llm/latency.py`) was added to calculate rolling average response times.

---

## Phase 5 — UI Evolution: The Command Center

### From CLI to Web Workstation
As SERA expanded from a voice script to an operating system agent, a dedicated visual interface was needed. An asynchronous HTTP and WebSocket server (`app/ui/server.py`) was built into the runtime, listening at `http://127.0.0.1:8765`.

### Evolution of Command Center Views:
1. **LIVE:** Real-time conversation stream, audio visualizer orb, active tool execution badges, and contextual cancel button.
2. **WORKFLOW:** Visual execution graph representing the multi-step plan.
3. **ARCHITECT:** Studio interface allowing the operator to drag-and-drop candidate models into primary, fallback, and disabled tiers for each role.
4. **PROVIDERS:** Status dashboard displaying latency, error rates, and API keys for all configured backends.
5. **MEMORY:** Inspection view for short-term conversation context and persistent memory.
6. **HISTORY:** Chronological log of past sessions and commands.
7. **DEBUG / SECURITY:** System telemetry, log stream, and permission elevation controls.

---

## Phase 5D — Current Rework & The Vertical Slice Philosophy

### Diagnosis of Previous Shortcomings
Between Phase 5C and Phase 5D, several critical architectural bugs were uncovered:
* **The False PASS Problem:** Automated tests were asserting that `open_application("chrome")` succeeded simply because a subprocess command returned exit code 0. However, in reality, Chrome frequently failed to launch on Windows due to path resolution or sandboxing issues.
* **Web Search Hallucination:** Commands like "Search the web for RTX 5090 benchmarks" were completing with LLM-generated summaries without actually querying the web or returning structured URLs and snippets.
* **UI Clutter & Static Workflow Editors:** The Workflow tab had evolved into a static drag-and-drop node graph that had zero connection to real runtime events.

### Phase 5D Architectural Milestones:
* **Real-World Side-Effect Verification:** Every tool was re-engineered with empirical verification gates:
  * `open_application`: Must inspect the Windows process table and verify the window title exists before reporting `COMPLETED`. If not found, reports `BROKEN`.
  * `web_search`: Rewritten with real DuckDuckGo HTML scraping, multi-line title cleaning, sponsor/ad link filtering, and strict schema validation (`title`, `url`, `snippet`, `source`). Tasks return `BROKEN` if zero results are found.
* **Vertical-Slice Testing (`tests/vertical_slices/`):** Shifted away from monolithic test suites to focused, isolated vertical slices where each test executes the real tool against the real operating system.
* **Primary STT Modernization:** Replaced NVIDIA Canary-Qwen with **Google Gemini 3.5 Transcribe** (`gemini-3.5-transcribe`), achieving superior English accuracy and automatic language detection, with local **Faster-Whisper CUDA** as offline fallback.

---

## SERA 2.0 Direction — Complete Product Reimagining

### The Core Realization
A desktop AI operating system must **not** look like a developer dashboard or a web chatbot. Putting cards, panels, sidebars, and chat bubbles directly over the user's workspace creates visual clutter and distracts from the desktop itself.

### The Dual-Body Architectural Vision:
SERA 2.0 establishes two radically distinct visual bodies:

```
+─────────────────────────────────────────────────────────────────────────────+
|                                  SERA 2.0                                   |
+──────────────────────────────────────┬──────────────────────────────────────+
|    BODY 1: PRIMARY SERA PRESENCE     |   BODY 2: SECONDARY COMMAND CENTER   |
+──────────────────────────────────────┼──────────────────────────────────────+
| • 100% Alpha Transparent Overlay     | • High-Density Web Workstation       |
| • Zero panels, cards, or chat bubbles| • 10 primary operational sections    |
| • Raphael-inspired computational core| • Objective-first task visualization |
| • Concentric mathematical rings      | • Dynamic execution graph            |
| • GPGPU curl-noise particle swarm    | • MCP client registry                |
| • Single-line kinetic status morpher | • Local RAG & memory tiers           |
| • Cellular reconstruction completion | • System diagnostics & telemetry     |
+──────────────────────────────────────┴──────────────────────────────────────+
```

### Visual Metaphor: Wisdom King / Raphael
Inspired by the computational elegance of Raphael (the Ultimate Skill from *Tensura*), SERA's primary presence manifests as an **autonomous computational consciousness**:
* Concentric geometric rings with differential angular velocities reflecting CPU/GPU load.
* Luminous white singularity core with celestial cyan energy falloff (`#00F0FF`, `#0284C7`).
* Transient magenta accents (`#F43F5E`) marking state transitions and high-level analytical synthesis.
* **Signature Cellular Reconstruction:** Upon task completion, outward-projecting energy filaments fragment, converge inward, nucleate into micro-hexagonal cells, connect along circular tracks, and lock into stable resting geometry with a brilliant harmonic flash.
