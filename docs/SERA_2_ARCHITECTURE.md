# SERA 2.0 — System Architecture Specification

> **Author:** Keshava Pandi A S  
> **Creator:** Keshava Pandi A S  
> **Developer:** Keshava Pandi A S  
> **Version:** 2.0.0-PROPOSED  
> **Core Subsystems:** Runtime Engine, Model Fabric, Tool Fabric, MCP Client, Memory & RAG, Event Bus, Dual Visual Bodies  
> **Architectural Paradigm:** Event-Driven Asynchronous Micro-Kernel with Decoupled Surfaces

---

## 1. High-Level Architectural Topology

SERA 2.0 operates as a local-first, low-latency micro-kernel. The backend orchestrates voice capture, LLM routing, real-world tool execution, and memory, while broadcasting synchronized telemetry to both visual bodies via WebSocket event streaming.

```
                                  ┌────────────────────────┐
                                  │   OPERATOR INPUTS      │
                                  │ Voice (Mic) / Hotkey   │
                                  │ WebUI Text / API       │
                                  └───────────┬────────────┘
                                              │
                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                   SERA 2.0 CORE RUNTIME                                  │
│                                                                                          │
│  ┌───────────────────────┐   ┌────────────────────────┐   ┌───────────────────────────┐  │
│  │   Perception Engine   │   │     Command Pipeline   │   │       Model Fabric        │  │
│  │  - Gemini 3.5 STT     │──▶│  - State Machine       │──▶│  - Fast: Groq / Cerebras  │  │
│  │  - Whisper Fallback   │   │  - Intent Classifier   │   │  - Reasoning: Gemini/Mist │  │
│  │  - Screen Capture     │   │  - Task Planner        │   │  - Vision / OCR / Embed   │  │
│  │  - Audio Cues / TTS   │   │  - Step Verifier       │   │  - Quota & Health Monitor │  │
│  └───────────────────────┘   └───────────┬────────────┘   └───────────────────────────┘  │
│                                          │                                               │
│                                          ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                                  Tool & MCP Fabric                                 │  │
│  │  ┌───────────────────────┐  ┌──────────────────────┐  ┌─────────────────────────┐  │  │
│  │  │ Windows OS Automation │  │ Web Research Layer   │  │ MCP Client Hub (JSON-RPC│  │  │
│  │  │ - Process/Win Verified│  │ - Ad-Filtered Search │  │ - Playwright / DevTools │  │  │
│  │  │ - Filesystem / Shell  │  │ - Real Fetch / Reader│  │ - Filesystem / Context7 │  │  │
│  │  └───────────────────────┘  └──────────────────────┘  └─────────────────────────┘  │  │
│  └───────────────────────────────────────┬────────────────────────────────────────────┘  │
│                                          │                                               │
│                                          ▼                                               │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                           Unified Event Bus & State Store                          │  │
│  │   TASK_STARTED | TOOL_STARTED | TOOL_COMPLETED | STATE_CHANGED | AGENT_TELEMETRY   │  │
│  └───────────────────────────────────────┬────────────────────────────────────────────┘  │
└──────────────────────────────────────────┼───────────────────────────────────────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    │  Async WebSocket & HTTP Server (Port 8765)  │
                    └──────────────┬──────────────────────────────┘
                                   │ Real-time JSON Event Stream
                ┌──────────────────┴──────────────────┐
                ▼                                     ▼
   ┌─────────────────────────┐           ┌──────────────────────────┐
   │  BODY 1: PRIMARY SERA   │           │   BODY 2: SECONDARY      │
   │  PRESENCE               │           │   COMMAND CENTER         │
   │  - Transparent Overlay  │           │  - 10-Tab Workstation    │
   │  - WebGL / Three.js     │           │  - Living Noise/Flow BG  │
   │  - Concentric Rings     │           │  - Workflow Step Graph   │
   │  - GPGPU Curl Particles │           │  - MCP & Integrations    │
   │  - Single-line Status   │           │  - Memory & Local RAG    │
   └─────────────────────────┘           └──────────────────────────┘
```

---

## 2. Decoupled Visual Bodies: Process Model

To achieve a truly transparent, non-obstructive desktop presence while maintaining a high-density technical command center, the visual layer is decoupled into two runtime surfaces:

| Attribute | Body 1: Primary SERA Presence | Body 2: Secondary Command Center |
| :--- | :--- | :--- |
| **Window Type** | Frameless, borderless transparent viewport | Full standard browser tab or desktop application |
| **Technology** | HTML5 Canvas + WebGL + Three.js / GLSL Shaders | Modular Vanilla ES6 + CSS Design System |
| **Alpha / Opacity** | `transparent` window with `alpha: true` WebGL | Opaque dark surface (`#070A12`) with subtle animated shader canvas |
| **Interaction** | Click-through enabled during IDLE; interactive on hover/click | Standard high-density dashboard controls |
| **Launch Modes** | Embedded Webview (PyQt6 / pywebview / Chrome app-mode) | Browser URL: `http://127.0.0.1:8765` |
| **Responsibility** | Immediate state, listening, speaking, micro-progress | Deep inspection, task history, MCP config, RAG indexing |

### Body 1 Transparent Window Implementation Options:
1. **Lightweight Dedicated Webview (Recommended):**  
   Using Python `pywebview` or a dedicated transparent Chrome window (`--app=http://127.0.0.1:8765/presence --transparent --disable-gpu-compositing`).
2. **In-Browser Presence Mode:**  
   When running purely within Chrome, Body 1 renders as an ultra-minimal floating modal/canvas above a darkened backdrop, toggleable via `F2` or header shortcut, or dockable to a compact floating side-window.

---

## 3. Codebase Audit: Reusable Components vs. Rework/Removal

### 3.1 Components to Keep & Reuse (High Value / Proven)
1. **`app/core/events.py` (`EventBus`):**
   - Clean async event dispatcher with string subscriptions.
   - Core events (`TASK_STARTED`, `TOOL_STARTED`, `TOOL_COMPLETED`, `AGENT_RESPONSE`, `TASK_COMPLETED`, `TASK_FAILED`, `STATE_CHANGED`).
2. **`app/tools/windows/application.py`:**
   - Recently validated and bulletproofed with real Windows process and window verification.
3. **`app/tools/browser/web_search.py`:**
   - Ad-filtered, multi-line cleaned DuckDuckGo HTML parser returning strict contracts (`title`, `url`, `snippet`, `source`).
4. **`app/speech/stt.py` & `app/speech/audio_manager.py`:**
   - Dedicated Gemini 3.5 Transcribe STT engine with Faster-Whisper local CUDA fallback.
   - Microphone capture, hotkey listener (`Ctrl+Space`), and VAD transcript gating.
5. **`app/models/llm/`:**
   - High-performance provider wrappers: Gemini, Groq, Mistral, OpenRouter, Cerebras, Ollama, OpenAI-compatible.
   - `latency.py` and `health.py` tracking.

### 3.2 Code to Remove, Isolate, or Completely Rework
1. **Monolithic Live Dashboard (`app/ui/static/js/views/live.js`):**
   - *Current Flaw:* Merges chat bubbles, model cards, execution log widgets, and audio visualizations into one cluttered column.
   - *Rework:* Split completely into:
     - `presence.js`: Pure WebGL Wisdom King core, GPGPU particles, concentric rings, and single-line status morpher.
     - New `live.js`: Human-facing live objective stream, active perception viewport, structured artifact card, and verified task results.
2. **Static Freeform Workflow Editor (`app/ui/static/js/views/workflow.js`):**
   - *Current Flaw:* A disconnected drag-and-drop node graph saved to a separate JSON layout, completely detached from actual execution events.
   - *Rework:* Transform into a **Dynamic Execution Workflow Theater** where nodes are created automatically from actual runtime events: `Objective -> Step 1 -> Step 2 ... -> Completion Signature`.
3. **Redundant Settings Views:**
   - *Current Flaw:* `providers.js`, `architect.js`, `security.js`, and `debug.js` display overlapping configuration controls.
   - *Rework:* Consolidate into the unified `SYSTEM` section with sub-panels (Providers, MCP, RAG, Audio, Desktop, Security, Diagnostics) and a dedicated `INTEGRATIONS` environment-variable view.
4. **Rudimentary Memory:**
   - *Current Flaw:* `long_term.py` and `short_term.py` are basic in-memory lists without persistence, semantic indexing, or domain partitioning.
   - *Rework:* Architect 6 distinct memory tiers with vector store integration hooks.

---

## 4. Model Fabric & Dynamic Resource-Aware Routing

SERA 2.0 maintains a strict **Model-Agnostic Architecture**. LLM providers are commodity compute nodes; SERA's reasoning engine routes requests according to role requirements, real-time latency, and remaining quota.

```
                          ROLE REQUEST (e.g. REASONING)
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │    RESOURCE-AWARE ROUTER      │
                       │  Evaluates:                   │
                       │  - Provider Health (Up/Down)  │
                       │  - Latency Rolling Average    │
                       │  - Quota / Token Remaining    │
                       │  - Context Window Size        │
                       │  - Cost Metric                │
                       └───────────────┬───────────────┘
                                       │
               ┌───────────────────────┼───────────────────────┐
               ▼                       ▼                       ▼
      [ Primary Provider ]    [ Secondary Fallback ]   [ Local Offline Fallback ]
      e.g. Gemini 2.5 Flash   e.g. Groq Llama-3.3 70B  e.g. Ollama Qwen-2.5 14B
```

### Supported Provider Pools
1. **Free / High-Efficiency Providers:**
   - Google Gemini (Gemini 2.5 Flash / Flash Lite / Gemini 3.5 Transcribe).
   - Groq (Llama-3.3-70b-versatile, Qwen-2.5-32b).
   - Mistral AI (Mistral Small / Nemo / Codestral).
   - Cloudflare Workers AI / OpenRouter (Free community pools).
   - Local Ollama (Offline fallback).
2. **Paid / Deep Infrastructure (Optional):**
   - DeepSeek (Reasoning R1 / V3 as optional paid infrastructure).
   - OpenAI / Anthropic (BYOK via Integrations).
3. **Explicit Exclusions:**
   - GitHub Models (Service retired July 2026; permanently excluded).

---

## 5. Web Research Layer

SERA 2.0 treats Web Research as an empirical pipeline, not an LLM hallucination:

```
User Query: "Search the web for RTX 5090 benchmarks"
   │
   ▼
[ Web Research Tool Router ]
   │
   ├── 1. Primary Engine: DuckDuckGo / Brave Search API
   │      - Strip URL redirects & sponsor tracking
   │      - Filter out commercial ad snippets
   │      - Extract Title, Canonical URL, Snippet, Published Date
   │
   ├── 2. Verification Gate:
   │      - If count == 0: Return Failure / Broken state (Never fake completion!)
   │      - If count > 0: Structured JSON payload emitted
   │
   ├── 3. Deep Fetch Engine (Optional Deep Research):
   │      - Playwright MCP / Fetch MCP / Firecrawl
   │      - Fetch markdown / DOM readability extract
   │
   └── 4. Live Preview Stream:
          - Broadcast structured result cards to Live UI before final synthesis.
```

---

## 6. Memory & Local RAG Architecture

SERA separates memory into 6 explicit domains:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SERA MEMORY SUBSYSTEM                           │
├──────────────────────────┬─────────────────────────────────────────────┤
│ Domain                   │ Storage Engine & Lifecycle                  │
├──────────────────────────┼─────────────────────────────────────────────┤
│ 1. Conversation Memory   │ Sliding window context + summary buffer     │
│ 2. Preference Memory     │ Key-value user traits & explicit rules      │
│ 3. Task History          │ SQLite / JSONL event ledger with verif. log │
│ 4. Project Memory        │ Per-workspace conventions & file mappings   │
│ 5. Document Knowledge    │ Vector embeddings (LanceDB / Qdrant)        │
│ 6. Web Research Cache    │ TTL-cached queries & raw extracts           │
└──────────────────────────┴─────────────────────────────────────────────┘
```

### Local RAG Pipeline:
1. **Document Ingestion:** PDF, Markdown, Python, Code files.
2. **Chunking:** Semantic boundary-aware chunking (Markdown headers, AST code chunks, sliding overlap).
3. **Local Embedding:** Gemini Embeddings or local HuggingFace `all-MiniLM-L6-v2` / `bge-small-en`.
4. **Vector Store:** Embedded local LanceDB or ChromaDB requiring zero server daemon.
5. **Reranking & Citation:** Cosine similarity + reciprocal rank fusion (RRF); every answer cites exact file paths and line numbers.

---

## 7. Multi-Agent Extensibility Points

While autonomous multi-agent swarms are not fully unleashed in Phase 1, SERA 2.0 defines clean abstract interfaces (`BaseAgent`) for future specialization:

```python
class BaseAgent(ABC):
    name: str
    role: str
    capabilities: list[str]
    tools: list[str]
    
    @abstractmethod
    async def step(self, objective: str, context: AgentContext) -> AgentAction: ...
```

Planned Agent Specializations:
- **SERA Core:** High-level supervisor, intent deconstruction, user communication.
- **Desktop Agent:** Windows GUI manipulation, window focus, keyboard/mouse macros.
- **Browser Agent:** Playwright automation, web scraping, form submission.
- **Vision Agent:** Desktop screenshot OCR, bounding box detection, visual QA.
- **Research Agent:** Deep multi-source web synthesis, citation verification.
- **Coding Agent:** File edits, testing execution, git diff generation.
- **Knowledge Agent:** RAG vector search, document indexing, memory retrieval.
- **Automation Agent:** Scheduled triggers, background monitoring cron jobs.

---

## 8. Stateful Graph Runtime Architecture (Phase 3A Foundation)

SERA 2.0 establishes an asynchronous, directed, stateful execution graph runtime (`app/core/graph/`) beneath the `CommandPipeline`. Rather than treating execution as procedural command dispatching, SERA operates as a persistent computational system governed by formal state transitions, empirical verification completion gates, and resilient recovery loops.

```
                  ┌──────────────┐
                  │   PERCEIVE   │ (Speech / Text / API Ingestion)
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │  NORMALIZE   │ (Conversational normalization & vocative stripping)
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │   CONTEXT    │ (Active app, window, entities, recent actions)
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │    ROUTE     │ (Deterministic Fast-Path vs. Multi-Step vs. Reasoning)
                  └──────┬───────┘
                         │
         ┌───────────────┴───────────────┐
         ▼ (Deterministic Fast-Path)     ▼ (Complex / Multi-Step)
         │                         ┌───────────┐
         │                         │   PLAN    │ (Step decomposition & Model Fabric)
         │                         └─────┬─────┘
         │                               ▼
         │                         ┌───────────┐
         │                         │SPECIALIST │ (Desktop / Browser / Vision Seam)
         │                         └─────┬─────┘
         └───────────────┬───────────────┘
                         ▼
                  ┌──────────────┐
                  │   EXECUTE    │ (Tool invocation with real-time cancellation gate)
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │   OBSERVE    │ (Structured OS/browser state capture)
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │    VERIFY    │ (EvidenceVerificationFabric empirical gate)
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │ UPDATE STATE │ (GraphState synchronization & telemetry)
                  └──────┬───────┘
                         ▼
                  ┌──────────────┐
                  │    DECIDE    │
                  └──┬───┬───┬───┘
          ┌──────────┘   │   └──────────┐
          ▼              ▼              ▼
       [ DONE ]     [ CONTINUE ]    [ RECOVER ]
          │              │          (Retry / Replan / Handoff)
          ▼              └──────────────┘
    ┌───────────┐
    │  RESPOND  │ (Shielded conversational response synthesis)
    └───────────┘
```

### 8.1 Why the Graph Runtime Exists
1. **Looping & Multi-Step Continuity:** Previous procedural loops held intermediate execution in fragile local variables. The graph runtime maintains execution state across arbitrary step sequences.
2. **First-Class Verification Gate:** A node cannot simply declare success because an API returned HTTP 200 or an exit code was 0. `VerifyNode` evaluates an empirical `EvidenceRecord` (processes, window handles, non-empty structured data) before permitting the task to advance or complete.
3. **Structured Interruption & Cancellation:** Long-running tools and loops race against an atomic `asyncio.Event` cancellation primitive via `asyncio.wait(..., return_when=FIRST_COMPLETED)`. Cancellation stops downstream tool calls, TTS playback, and misleading task-completion events instantly.
4. **Resilient Recovery Model:** System exceptions are caught and classified into structured categories (`TOOL_EXCEPTION`, `VERIFICATION_FAILED`, `TIMEOUT`, `USER_CANCELLED`, `MODEL_FAILURE`). The graph evaluates bounded retries with exponential backoff before failing or replanning.

### 8.2 Canonical Graph State Model (`GraphState`)
All nodes communicate strictly through the typed `GraphState` structure (`app/core/graph/state.py`) rather than loose prose:
- **Identity:** `execution_id`, `task_id`, `turn_id`, `created_at`, `updated_at`.
- **Input:** `raw_user_input`, `normalized_user_input`, `input_source`, `speech_metadata`.
- **Context:** `active_application`, `active_window`, `active_browser`, `active_tab`, `current_url`, `last_verified_action`, `context_state`.
- **Routing:** `selected_route`, `selected_specialist`, `selected_model_role`, `routing_reason`.
- **Plan:** `plan_id`, `steps` (`GraphPlanStep`), `current_step_index`, `retry_count`.
- **Execution:** `current_node`, `current_action`, `action_arguments`, `action_result`, `observation` (`GraphObservation`), `verification` (`EvidenceRecord`).
- **Recovery:** `last_error`, `error_category`, `is_recoverable`, `replan_count`.
- **Outcome:** `status` (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `CANCELLED`, `BROKEN`), `final_response`, `completion_reason`.
- **Presence:** `presence_state`, `active_objective`, `task_progress`.
- **Telemetry:** `node_timings`, `model_timings`, `tool_timings`, `total_duration_ms`.

### 8.3 Node Contract & Control Semantics
Every node implements the `GraphNode` abstract base class:
```python
async def execute(self, state: GraphState, cancellation_event: asyncio.Event | None = None) -> GraphDecision:
```
The node mutates `state` directly and returns a typed `GraphDecision`:
- `CONTINUE`: Advance to the next scheduled step or node.
- `DONE`: Transition to completion (`RESPOND` → end).
- `RETRY`: Re-execute the current step within bounded retry limits.
- `REPLAN`: Invoke reasoning to compute an alternate execution plan.
- `HANDOFF`: Delegate execution to an external specialist.
- `FAIL`: Controlled failure with structured diagnostic evidence.
- `CANCEL`: Immediate clean abort requested by the user.

### 8.4 Relationship to Core Subsystems
- **Model Fabric Integration:** The graph requests capabilities by semantic role (`REASONING`, `FAST`, `VISION`, `CODING`) through `ModelRouter`. It never hardcodes providers, preserving SERA's provider-agnostic resiliency.
- **EventBus Integration:** All transitions emit unified lifecycle events (`GRAPH_STARTED`, `GRAPH_NODE_ENTERED`, `GRAPH_NODE_COMPLETED`, `GRAPH_TRANSITION`, `GRAPH_COMPLETED`, `GRAPH_CANCELLED`, `GRAPH_FAILED`) carrying identical `execution_id`, `task_id`, and `turn_id` correlation parameters.
- **Primary Presence Integration:** The Presence remains a decoupled renderer of runtime truth. Presence states (`LISTENING`, `THINKING`, `EXECUTING`, `COMPLETED`, `BROKEN`, `CANCELLED`) are driven by graph state transitions without embedding execution logic inside Electron.
- **Specialist Handoff Boundary:** Establishes the seam for future autonomous agents (Desktop, Browser, Vision, Coding). The supervisor graph hands execution off to a specialist via shared state, awaiting a structured result before resuming graph progression.

### 8.5 What Phase 3A Intentionally Does NOT Implement
- **Autonomous Multi-Agent Swarms:** Swarm coordination and free-agent negotiations are deferred to Phase 3B/Phase G.
- **Lock-in Mode UI & Continuous Loop:** The architectural support for repeated session executions is enabled, but the Lock-in UI surface is scheduled for Phase 3B.
- **6-Domain Persistent Memory & Vector RAG:** Checkpoint hooks and serialization are implemented, but persistent LanceDB vector storage belongs to Phase F.
- **3D Visual Engine Redesign:** The Three.js WebGL 2.0 Presence engine and glass panel are preserved without regression.

