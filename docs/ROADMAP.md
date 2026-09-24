# SERA Project Roadmap

> **Author:** Keshava Pandi A S  
> **Creator:** Keshava Pandi A S  
> **Developer:** Keshava Pandi A S  

This living document outlines development priorities organized into three horizons: **NOW** (immediate focus), **NEXT** (upcoming architecture phases), and **LATER** (long-term strategic capabilities).

---

## 1. NOW — Core Reliability & Visual Presence (Current Phase)

* **[x] Primary STT Modernization:** Google Gemini 3.5 Transcribe integrated as primary STT engine with local Faster-Whisper CUDA fallback.
* **[x] Real-World Verification Gates:** Elimination of false passes on Windows application launches (real process and window checks).
* **[x] Empirical Web Search Engine:** DuckDuckGo HTML scraping with ad/sponsor filtering, strict data contracts, and live preview cards.
* **[x] Vertical-Slice Testing Infrastructure:** Granular, fast-executing test suites in `tests/vertical_slices/`.
* **[x] SERA 2.0 Product Architecture:** Formalization of the 5 foundational architecture specifications in `docs/`.
* **[x] Primary SERA Presence (Phase B Engine):** Three.js WebGL Wisdom King core with concentric mathematical rings, GPGPU curl particles, 9 animation states, and kinetic status typography at `/presence`.
* **[x] Evidence Verification Fabric (Phase 2A):** Universal side-effect verification engine (`app/core/verification.py`) enforcing mandatory completion gates across OS processes, web queries, and filesystem operations with zero false passes.
* **[x] Native Transparent Desktop Shell (Phase 2B):** Packaging `presence.html` into a lightweight, borderless, click-through desktop overlay window using `pywebview` on Windows (`app/ui/desktop_presence.py`).
* **[x] Primary SERA Presence Rebuild (Phase 2):** Dedicated native Windows desktop overlay (`presence_desktop/`) using Electron 33 + Three.js WebGL 2.0 with true DWM alpha transparency, global shortcut (`Ctrl+Space`), 8-layer computational consciousness engine, and 8 distinct task-specific structural visualizations.
* **[x] Primary Presence Behavior Engine (Phase 2B):** Continuous non-deterministic simulation engine (`PresenceBehaviorEngine.js`) driven by dynamic energy budget, visual attention model, organic pacing, visual memory, multi-band audio, micro-event reactions, and 7-phase computational cellular regeneration.
* **[x] Stateful Graph Runtime Foundation (Phase 3A):** Canonical asynchronous directed execution graph engine (`app/core/graph/`) with strongly-typed `GraphState`, explicit node contracts, conditional branching, bounded loops/retries, real-time `asyncio.Event` cancellation, first-class `EvidenceVerificationFabric` completion gates, and event correlation across the runtime.
* **[x] Controlled Qwen Semantic Authority Pilot (Phase 3A-E):** Promotion of local Qwen3.5-4B Semantic Interpreter to primary semantic interpretation source for application, reference, repetition, and conversational language via `SemanticAuthorityGate` and `SemanticContextResolver`, while preserving deterministic fast path, safe legacy fallback, and Stateful Graph Runtime execution authority.
* **[x] End-to-End Semantic, State, Routing, Execution & Response Integrity (Phase 3A-F):** Comprehensive architectural overhaul establishing Entity-Centric ContextStore with session-scoped search isolation, stateful browser subsystem with idempotent tab reuse and tab closure distinct from process termination, semantics-first specialist vision routing, strict terminal state monotonicity, and TTS playback synchronization.
* **[ ] Command Center Reorganization (Phase C):** Rebuilding `http://127.0.0.1:8765` into the 10 organized operational sections (`LIVE`, `TASKS`, `WORKFLOWS`, `AGENTS`, `MEMORY`, `KNOWLEDGE`, `INTEGRATIONS`, `MODELS`, `HISTORY`, `SYSTEM`).

---

## 2. NEXT — Extensibility, Memory & Multi-Agent (Upcoming Phases)

* **Phase D: Dynamic Execution Timeline:**
  * Rebuild the Workflow view to render real execution events dynamically (Objective -> Step 1 -> Step 2 ... -> Completion Signature), completely replacing the static drag-and-drop node graph.
  * Integrate the Signature Computational Cellular Reconstruction visual into the Command Center.
* **Phase E: Model Context Protocol (MCP) Fabric:**
  * Build native async JSON-RPC 2.0 client in `app/core/mcp_client.py` supporting `stdio` and `SSE` transports.
  * Implement the environment-variable style "Add Integration" experience in the Command Center with live ping verification and secret token masking.
  * Connect initial MCP catalog: Playwright MCP (browser navigation), Chrome DevTools MCP (active tab companion), Filesystem MCP, and Fetch MCP.
* **Phase F: Partitioned Memory & Local RAG:**
  * Segment memory into 6 explicit domains (Conversation, Preferences, Task History, Projects, Documents, Web Cache).
  * Embed in-process **LanceDB** vector store with semantic document chunking, reciprocal rank fusion (RRF), and mandatory line-number source citations.
* **Phase G: Multi-Agent Specialization:**
  * Formalize `BaseAgent` abstract class.
  * Deploy specialized autonomous sub-agents: Desktop Agent, Browser Agent, Vision Agent, Research Agent, Coding Agent, Knowledge Agent, Automation Agent.

---

## 3. LATER — Advanced Autonomous OS Capabilities (Future Horizon)

* **Deep Visual Perception & Autonomous UI Driving:**
  * Real-time 30 FPS screen perception with local object detection for fine UI buttons, form inputs, and window controls.
  * Hybrid coordinate + accessibility tree targeting for complex desktop applications (e.g. Adobe Suite, Blender, Visual Studio).
* **Multi-Modal Desktop Memory & Chronological Timeline:**
  * Local continuous desktop timeline indexing (OCR on active windows, active files, and project contexts) enabling queries like *"What was the commit hash I was reviewing yesterday afternoon?"*
* **Autonomous Task Scheduling & Background Daemons:**
  * Local cron scheduler executing complex multi-step automations in the background without user intervention.
* **Self-Healing Code & Workflow Repair:**
  * Autonomous regression testing and self-correcting tool chains that dynamically recover from API shifts or desktop errors.
