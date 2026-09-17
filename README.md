# SERA — Personal Desktop AI Operating System

> **A computational consciousness designed for one user.**  
> Moving beyond conversational chatbots into an autonomous, voice-driven personal desktop operating system.

---

## 🌟 What is SERA?

**SERA** (**S**emantic **E**xecution & **R**untime **A**ssistant) is a personal desktop AI operating system for Windows. 

Unlike conventional AI tools that trap users in a rectangular chat window with message bubbles, SERA is engineered as an **autonomous computational presence** that resides over your operating system. It perceives your desktop, listens to intentional voice commands, executes multi-step system workflows with empirical verification, and manifests as dynamic, mathematical geometry hovering weightlessly over your active applications.

---

## ⚡ Why is SERA Different?

1. **Dual-Body Visual Paradigm:**
   * **Body 1 (Primary SERA Presence):** A 100% alpha-transparent, floating computational manifestation (inspired by the analytical transcendence of *Wisdom King / Raphael*). Zero panels, zero cards, zero sidebars, zero chat bubbles. The desktop behind SERA remains completely unobstructed.
   * **Body 2 (Secondary Command Center):** A high-density technical control surface (`http://127.0.0.1:8765`) for deep configuration, model routing, history replay, and diagnostics.
2. **Empirical Side-Effect Verification:**
   A task is **never** marked completed simply because an LLM claimed it or a shell command returned exit code 0. SERA actively verifies real-world side effects (scanning Windows process tables, confirming window handles, and verifying structured web search data).
3. **Dedicated Hold-to-Talk (`Ctrl+Space`):**
   Combines an intentional global keyboard hook with local wake-word detection ("SERA"), backed by streaming Google Gemini 3.5 Transcribe STT and real-time acoustic voice interruption.
4. **Model-Agnostic Resource-Aware Fabric:**
   Routes tasks dynamically across Gemini, Groq, Mistral, OpenRouter, and local Ollama based on real-time health, rolling latency averages, and quota headroom.

---

## 🏛️ High-Level System Architecture

```
                                  OPERATOR
                         (Voice, Hotkey, Text, API)
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                           PRIMARY SERA PRESENCE                               │
│        (100% Alpha Transparent WebGL Core · Kinetic Status Typography)        │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                              SERA CORE RUNTIME                                │
│                                                                               │
│   1. PERCEPTION ──────────▶ 2. INTENT CLASSIFIER ───▶ 3. RESOURCE ROUTER      │
│      • Gemini 3.5 STT          • Goal Deconstruction     • Health & Quota     │
│      • Whisper CUDA Fallback   • Ambiguity Resolution    • Latency Tracking   │
│      • Multimodal Screen                                 • Specialized Roles  │
│                                                               │               │
│   6. TTS & AUDIO CUES ◀─── 5. VERIFICATION GATE  ◀── 4. PLANNER & TOOLS       │
│      • Streaming Interruption  • OS Process Checks       • Windows Shell      │
│      • Spatial Audio Chimes    • Non-Zero Search Gates   • Web Search         │
│                                                          • MCP Client Hub     │
│                                       │                                       │
│                                       ▼                                       │
│                            7. PARTITIONED MEMORY                              │
│                               • 6 Scoped Tiers                                │
│                               • Local LanceDB Vector RAG                      │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                    │ Real-Time WebSocket Telemetry
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                          SECONDARY COMMAND CENTER                             │
│       (10-Tab Workstation · Living Shader Background · Workflow Replay)       │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚦 Implementation Status Ledger

To maintain absolute technical honesty, all capabilities are strictly classified by their verified state in the codebase:

### ✅ CURRENT STATUS (Actually Working & Verified)
* **Speech-to-Text (STT):** Google Gemini 3.5 Transcribe (`gemini-3.5-transcribe`) with automatic language detection, natural punctuation, and local Faster-Whisper CUDA fallback.
* **Hold-to-Talk Voice Loop:** Global `Ctrl+Space` hook with VAD gating and instant acoustic TTS interruption.
* **Empirical Application Automation:** Windows application launcher in `app/tools/windows/apps.py` with mandatory OS process ID and window title handle verification (verified with Chrome).
* **Empirical Web Search:** DuckDuckGo HTML parsing engine in `app/tools/browser/web_search.py` with multi-line title cleaning, sponsored ad filtering, strict data contracts, and live search previews (verified with 5-test vertical slice).
* **Primary SERA Presence (Body 1):** Three.js WebGL Wisdom King core with concentric mathematical rings, 12,000+ GPGPU curl particles, 9 animation states, single-line kinetic typography, and the Signature Computational Cellular Reconstruction completion sequence (`http://127.0.0.1:8765/presence`).
* **Multi-Provider LLM Fabric:** Adapters for Google Gemini, Groq, Mistral AI, OpenRouter, Cerebras, and Ollama.
* **Resource-Aware Router:** Model-level health isolation, volatile cooldowns, and latency moving averages.
* **Unified UI Gateway:** Asynchronous Python HTTP and WebSocket server listening on port 8765.

### ⚠️ IN DEVELOPMENT (Active Rework in Progress)
* **Secondary Command Center Reorganization:** Migrating the existing browser UI into the 10-tab technical surface (`LIVE`, `TASKS`, `WORKFLOWS`, `AGENTS`, `MEMORY`, `KNOWLEDGE`, `INTEGRATIONS`, `MODELS`, `HISTORY`, `SYSTEM`).
* **Dynamic Workflow Timeline:** Replacing the previous disconnected static drag-and-drop node graph with a dynamic event-generated task timeline.
* **Native Desktop Shell:** Wrapping the transparent presence canvas in a lightweight borderless Windows desktop window via `pywebview`.
* **Wake-Word Robustness:** Tuning local `openWakeWord` sensitivity to eliminate false positives in noisy environments.

### 📋 PLANNED (Architecturally Designed; Not Yet Implemented)
* **Model Context Protocol (MCP) Client:** Native JSON-RPC 2.0 client (`app/core/mcp_client.py`) connecting to Playwright, Chrome DevTools, Filesystem, and Git MCP servers.
* **Local Embedded RAG:** In-process LanceDB vector database with semantic chunking and verified line-number citations.
* **Autonomous Multi-Agent Swarm:** Dedicated sub-agents (Desktop, Browser, Vision, Research, Coding, Automation) coordinating under the SERA Core supervisor.

---

## 🔬 Core Subsystems

### 1. Dual-Body Visual System
* **Primary Presence:** Accessible at `http://127.0.0.1:8765/presence`. Manifests as a floating computational singularity with concentric rings rotating with differential angular speeds reflecting compute load. Displays single-line status updates (`LISTENING...`, `ANALYZING...`, `EXECUTING...`) and executes cellular reconstruction upon task completion.
* **Secondary Command Center:** Accessible at `http://127.0.0.1:8765`. High-density dark workstation built on Swiss typographical discipline, rich CSS tokens, and an organic living shader background.

### 2. Model Fabric & Roles
* **Reasoning:** High-parameter models (Groq Llama-3.3 70B, Mistral Large, Gemini Flash Thinking) for intent deconstruction and task planning.
* **Fast:** Low-latency models (Mistral Small, Gemini Flash Lite) for instant conversation and status updates.
* **Vision:** Multimodal models (Groq Qwen-2.5-VL, Gemini Flash) for desktop perception.
* **Tool Calling:** Mistral Codestral, Groq, and Gemini structured output endpoints.
* **STT & TTS:** Gemini 3.5 Transcribe / Faster-Whisper CUDA & streaming Fish/Kokoro audio.

### 3. Verification & Testing Philosophy
SERA rejects monolithic test suites and mock-only passes. All capabilities are validated via **Vertical Slices** (`tests/vertical_slices/`) requiring empirical real-world side effects:
* **Level 1 (Unit Pass):** Isolated parsing and logic validation.
* **Level 2 (Integration Pass):** Multi-component EventBus and WebSocket sync.
* **Level 3 (E2E Pass):** Real operating system or web execution.
* **Level 4 (Manual Acceptance):** Visual confirmation in Chrome and desktop.

---

## 🚀 Quick Start

### 1. Prerequisites
* **Operating System:** Windows 10 / 11 (64-bit).
* **Python:** Python 3.11, 3.12, or 3.14 (in virtual environment).
* **GPU (Optional):** NVIDIA CUDA-compatible GPU for local Faster-Whisper fallback.

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/KESHAVAPANDI/SERA-Desktop-Agent.git
cd SERA-Desktop-Agent

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and provide your API credentials:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
MISTRAL_API_KEY=your_mistral_api_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
```

### 4. Running SERA
```powershell
# Run SERA with unified Command Center and Primary Presence
python main.py

# Access the Primary Floating Presence:
http://127.0.0.1:8765/presence

# Access the Secondary Command Center:
http://127.0.0.1:8765
```

---

## 📚 Documentation Directory

Detailed engineering specifications and historical analyses are maintained in [`docs/`](./docs/):
* [**`docs/SERA_2_PRODUCT_VISION.md`**](./docs/SERA_2_PRODUCT_VISION.md) — The master product reimagining vision document.
* [**`docs/SERA_2_ARCHITECTURE.md`**](./docs/SERA_2_ARCHITECTURE.md) — Complete SERA 2.0 micro-kernel architecture.
* [**`docs/SERA_2_VISUAL_SYSTEM.md`**](./docs/SERA_2_VISUAL_SYSTEM.md) — WebGL shaders, GPGPU curl particles, and 9 state modes.
* [**`docs/SERA_2_CAPABILITY_MATRIX.md`**](./docs/SERA_2_CAPABILITY_MATRIX.md) — 16-dimension capability matrix and extension points.
* [**`docs/SERA_2_MCP_PLAN.md`**](./docs/SERA_2_MCP_PLAN.md) — Model Context Protocol client implementation plan.
* [**`docs/SERA_HISTORY.md`**](./docs/SERA_HISTORY.md) — Chronological development history from Phase 1 to SERA 2.0.
* [**`docs/DEVELOPMENT_APPROACH.md`**](./docs/DEVELOPMENT_APPROACH.md) — Vertical-slice philosophy and four pass levels.
* [**`docs/DECISIONS.md`**](./docs/DECISIONS.md) — Architectural decision records (ADRs).
* [**`docs/ARCHITECTURE_CURRENT.md`**](./docs/ARCHITECTURE_CURRENT.md) — Detailed description of the active codebase.
* [**`docs/ARCHITECTURE_SERA_2.md`**](./docs/ARCHITECTURE_SERA_2.md) — Future target architecture and dataflow.
* [**`docs/VISUAL_EVOLUTION.md`**](./docs/VISUAL_EVOLUTION.md) — Evolution from developer dashboards to computational consciousness.
* [**`docs/CAPABILITY_MATRIX.md`**](./docs/CAPABILITY_MATRIX.md) — Granular implementation status table.
* [**`docs/ROADMAP.md`**](./docs/ROADMAP.md) — NOW, NEXT, and LATER development horizons.
* [**`CHANGELOG.md`**](./CHANGELOG.md) — Chronological release notes.

---

## 👤 Authorship & Credits

* **Author:** Keshava Pandi A S
* **Creator:** Keshava Pandi A S
* **Developer:** Keshava Pandi A S

*Note: Antigravity is an AI development assistant/tool used by Keshava Pandi A S during development.*

---

## 📄 License
Internal proprietary research and development by Keshava Pandi A S. All rights reserved.

