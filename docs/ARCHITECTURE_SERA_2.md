# SERA 2.0 — Target Architecture Specification

> **Author:** Keshava Pandi A S  
> **Creator:** Keshava Pandi A S  
> **Developer:** Keshava Pandi A S  
> **Vision:** A Personal Desktop AI Operating System for One User.  
> **Execution Paradigm:** Dual-Body Visual Manifestation over an Asynchronous Unified Micro-Kernel.

---

## 1. The Unified Core Runtime Architecture

In SERA 2.0, the core runtime operates as an autonomous, event-driven engine. The user interface does not run its own "brain"; both the Primary Presence and the Secondary Command Center are lightweight display and control surfaces observing the same central kernel.

```
                                  OPERATOR
                         (Voice, Hotkey, Text, API)
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                                SERA 2.0 CORE                                  │
│                                                                               │
│  1. PERCEPTION ENGINE                                                         │
│     ├── STT: Gemini 3.5 Transcribe (Primary) / Faster-Whisper CUDA (Fallback) │
│     ├── Hotkey: Ctrl+Space (Hold-to-Talk) / Wake Word ("SERA")                │
│     └── Screen Perception: Multimodal Screen Inspection & OCR                 │
│                                   │                                           │
│                                   ▼                                           │
│  2. INTENT & CLASSIFICATION                                                   │
│     ├── Natural Language Intent Deconstruction                                │
│     └── Direct Execution vs. Multi-Step Task Disambiguation                   │
│                                   │                                           │
│                                   ▼                                           │
│  3. RESOURCE-AWARE ROUTER                                                     │
│     ├── Dynamic Selection: Quota, Health, Latency Rolling Avg, Cost, Context  │
│     └── Specialized Roles: Reasoning, Fast, Vision, Tool Calling, Embeddings  │
│                                   │                                           │
│                                   ▼                                           │
│  4. TASK PLANNER & OBJECTIVE DECOMPOSITION                                    │
│     ├── Explicit Objective Declaration                                        │
│     └── Sequential Step Synthesis (Step 1 -> Step 2 -> ... -> Verification)   │
│                                   │                                           │
│                                   ▼                                           │
│  5. AGENT / TOOL / MCP EXECUTION FABRIC                                       │
│     ├── Specialized Agents (Desktop, Browser, Vision, Research, Coding)       │
│     ├── Native Operating System Tools (Win32, PowerShell, Filesystem)         │
│     └── Model Context Protocol (MCP) Client Hub (Playwright, DevTools, Git)   │
│                                   │                                           │
│                                   ▼                                           │
│  6. EMPIRICAL VERIFICATION GATE                                               │
│     ├── OS Process Table & Window Handle Verification                         │
│     └── Structured Non-Zero Output Contracts (Never Fake Completion)          │
│                                   │                                           │
│                                   ▼                                           │
│  7. MEMORY & LOCAL RAG STORE                                                  │
│     ├── 6-Tier Memory (Conversation, Preference, Task, Project, Doc, Cache)   │
│     └── Embedded Vector Store (LanceDB) with Exact File & Line Citations      │
│                                   │                                           │
│                                   ▼                                           │
│  8. SPEECH SYNTHESIS & ACOUSTIC FEEDBACK                                      │
│     ├── Streaming Low-Latency TTS with Real-Time Energy Interruption          │
│     └── Spatial Audio Cues & State Transition Chimes                          │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                    │
                         UNIFIED EVENT BUS STREAM
            (State Changes, Task Objectives, Tool Results, Telemetry)
                                    │
             ┌──────────────────────┴──────────────────────┐
             ▼                                             ▼
┌─────────────────────────────┐             ┌─────────────────────────────┐
│   BODY 1: PRIMARY PRESENCE  │             │   BODY 2: COMMAND CENTER    │
│  • 100% Alpha Transparent   │             │  • 10-Tab Technical Surface │
│  • Wisdom King Core         │             │  • Living Shader Background │
│  • Concentric Rings         │             │  • Dynamic Timeline Graph   │
│  • GPGPU Curl Particles     │             │  • MCP & Integrations Vault │
│  • Single-Line Status Text  │             │  • Memory & RAG Inspector   │
│  • Cellular Reconstruction  │             │  • Telemetry & Diagnostics  │
└─────────────────────────────┘             └─────────────────────────────┘
```

---

## 2. Core Subsystems in Depth

### 2.1 Perception Engine
* **Acoustic Input:** Captures audio through a low-latency non-blocking buffer. Operates in two complementary modes:
  * **Intentional Hold-to-Talk:** Depressing `Ctrl+Space` captures speech with zero false positives. Releasing the hotkey triggers immediate transcription.
  * **Hands-Free Wake Word:** Background `openWakeWord` listener detecting "SERA".
* **Speech-to-Text (STT):** Transcribes audio using `gemini-3.5-transcribe` via the Google GenAI SDK. If network is offline, seamlessly shifts to local Faster-Whisper CUDA without dropping the audio buffer.
* **Visual Perception:** Captures screen buffers at up to 30 FPS when requested. Uses multimodal vision models to extract UI element locations and text content.

### 2.2 Intent & Planning Engine
* Deconstructs raw user requests into an **explicit, verifiable Objective**.
* Converts objectives into a directed execution plan.
* Rejects vague model actions: every step must specify the target tool, parameters, and expected post-condition.

### 2.3 Resource-Aware Model Fabric
* Treats LLM providers (Gemini, Groq, Mistral, OpenRouter, Ollama) as interchangeable compute pools.
* Selects candidate models dynamically using real-time telemetry:
  * Provider health (up/down status).
  * Rolling average response latency.
  * Remaining token and request quotas.
  * Context window requirements.
  * Estimated cost per invocation.
* Isolates rate-limited models temporarily without permanently altering user configuration.

### 2.4 Empirical Verification Gate
* The boundary between `EXECUTING` and `COMPLETED`.
* A task can only reach completion if its post-condition is verified:
  * `Open Chrome`: Verified by scanning the Windows process table for `chrome.exe` and confirming an active window handle exists.
  * `Search Web`: Verified by confirming that real search result objects (`title`, `url`, `snippet`, `source`) were extracted from DuckDuckGo/Brave.

### 2.5 Memory & Local RAG Subsystem
* Separates memory into 6 explicit domains:
  1. **Conversation Memory:** Sliding window buffer with background summarization.
  2. **Preference Memory:** Persistent user traits and hardware configuration (`config/preferences.json`).
  3. **Task History:** Permanent queryable ledger of all past tasks, steps, durations, and results.
  4. **Project Memory:** Workspace-specific conventions and code maps.
  5. **Document Knowledge:** Local vector indexing via embedded **LanceDB**.
  6. **Web Research Cache:** TTL-governed key-value cache of verified search results.

### 2.6 Model Context Protocol (MCP) Client
* Native JSON-RPC 2.0 client supporting `stdio` (local subprocesses) and `SSE` (remote streams).
* Automatically queries `tools/list` on startup, maps parameters into SERA's Tool Fabric, and exposes external capabilities (Playwright, Chrome DevTools, Filesystem, Git, Context7) under user-defined security permissions.

---

## 3. The Dual-Body Manifestation

### How Both Bodies Consume the Same Runtime
Both the Primary Presence (`/presence`) and the Command Center (`/`) connect to the same WebSocket server on port 8765. The server acts as a pure event relay:
* When a user speaks, the runtime emits `LISTENING_STARTED`.
* Body 1's rings contract and particles converge inward.
* Body 2's header indicator flashes `LISTENING`.
* When a tool starts, the runtime emits `TOOL_STARTED`.
* Body 1's particles radiate outward as filaments, and status text morphs to `EXECUTING: <tool>`.
* Body 2's Live tab renders an active step card and updates the timeline graph.
* When the task finishes, the runtime emits `TASK_COMPLETED`.
* Body 1 executes its Signature Computational Cellular Reconstruction sequence.
* Body 2 displays the final verified outcome and saves the task to History.

Neither interface maintains private task logic; the central runtime is the single source of truth.
