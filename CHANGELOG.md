# Changelog

All notable changes to the SERA project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0-phase3a-e] — 2026-09-24

### Added & Promoted
* **Controlled Qwen Semantic Authority Pilot:**
  * Promoted local `qwen3.5:4b` from shadow mode to the **Primary Semantic Interpretation Source** for authorized natural language categories:
    * **Application Semantics:** `open_application`, `close_application`, `switch_application` (*"Bring Chrome up."*, *"Could you get my browser running?"*).
    * **Reference Semantics:** `open_reference` (*"Take me to the first video you just found."*).
    * **Repetition / Continuation:** `repeat_last_task` (*"Repeat whatever you just did."*, *"Do it again."*).
    * **Contextual Entity Language:** *"Close that window."*, *"Open that."* (strictly requiring verified context; requests clarification when context is absent).
    * **Conversational Wrappers:** Polite requests, natural spoken phrasing, vocatives (*"Hey Sarah, could you fire up the browser for me?"*).
* **Semantic Authority Gate (`app/core/semantic/authority.py`):**
  * Implemented dedicated architectural decision boundary (`SemanticAuthorityGate`) evaluating CanonicalIntent against 10 rigorous acceptance rules.
  * Defines 4 operational sources: `QWEN`, `DETERMINISTIC`, `LEGACY_FALLBACK`, `CLARIFICATION`.
  * Preserves Deterministic Fast Path for exact numeric/scalar commands (`set_brightness`, `set_volume`, `mute`, system diagnostics, self-close), executing with 0.0ms model latency.
  * Guarantees legacy parser disagreement is never a veto for Qwen-eligible categories (e.g. *"Bring Chrome up."* succeeds via Qwen even if legacy parser classified it as `general_reasoning`).
  * Enforces shadow-only status for `compound_workflow`, coding, and general reasoning.
* **Semantic Context Resolver (`app/core/semantic/resolver.py`):**
  * Translates semantic entities and references into concrete runtime `CommandObject` execution plans without direct model execution or URL hallucination.
  * Resolves ordinal references to concrete URLs from verified `search_results`.
  * Clones previous plans for repetition intents.
  * Emits immediate conversational clarification (0 tools) for underspecified requests like *"Launch"*.
* **GraphState Telemetry:**
  * Extended `GraphState` with `semantic_decision` storing source, confidence, category, and fallback reasons for full observability and future Command Center visualization.
* **Empirical Verification:**
  * 24 automated unit tests in `tests/test_semantic_authority_gate.py` covering all 18 specified failure and edge cases.
  * 63 total passing tests across the entire semantic and graph integrity suite.
  * 15/15 successful live turns on local RTX 4050 GPU via `scratch/test_live_pilot.py`.

---

## [2.0.0-phase3a-c] — 2026-09-23

### Fixed & Enhanced
* **English-Constrained STT Policy:**
  * Configured Google Gemini STT (`gemini-3.5-transcribe`) with explicit audio transcription parameters (`language_codes=['en-US', 'en']`, `mode='VERBATIM'`, `temperature=0.0`) and non-Latin character detection logging to prevent multilingual translation hallucinations.
  * Hard-enforced English language decoding (`language="en"`) in Faster-Whisper fallback provider.
* **Canonical Semantic Normalization Boundary (`app/core/command.py`):**
  * Implemented multi-stage normalization cleanly stripping conversational addressing ("Hey Sarah, ...", "Sera, ...") and courtesy modals ("could you please...", "can you please...", "...for me", "...if you can") without corrupting target entity names.
  * Extracted repeat markers ("again", "once more") as structured semantic modifiers (`modifier="repeat"`), ensuring "Open Chrome again" resolves to `target="chrome"` rather than "chrome again".
* **Contextual Reference Resolution Gate:**
  * Inserted ordinal search result resolution ("open the first result", "click second one", "result 1", "play first video") resolving deterministically against verified `search_results` in `context_state` into `browser_open(url=...)`.
  * Added guard returning informative conversational feedback when no verified search results exist in session context, permanently preventing generic application parsing from interpreting "first result" as an executable application.
  * Expanded pronoun resolution ("close it", "close that") to map to the last verified active application or browser.
* **Terminal State Consistency & Single Event Source of Truth (`app/core/runtime.py`):**
  * Eliminated erroneous `TASK_COMPLETED` emissions following `BROKEN`/`FAILED` executions: failure turns now speak the conversational failure message, emit `AGENT_RESPONSE` with status `FAILED`, and terminate exclusively with `TASK_FAILED`.
  * Removed duplicate `MODEL_SELECTED` event trigger from `TASK_STARTED` in Electron Presence (`presence_desktop/src/App.js`).
  * Added deduplication guard in `PresenceEngine.js` preventing duplicate `Manifesting Task Structure` logs when consecutive identical objectives are received.
* **Deterministic Real Cancellation:**
  * Wired `asyncio.Event` cancellation primitive from `SERARuntime.cancel_task()` through `CommandPipeline` into `StatefulGraphRuntime`. Active nodes halt immediately without traversing subsequent nodes, emitting no false success events and terminating in `CANCELLED`.
* **Empirical Test Suite (`tests/test_phase3a_c_semantic_integrity.py`):**
  * Added 22 tests verifying English STT config, addressing & politeness normalization, repeat modifier extraction, ordinal reference resolution, terminal failure semantics, and deterministic cancellation (all 22 passing in 4.4s).

---

## [2.0.0-phase3a] — 2026-09-23

### Added
* **Stateful Graph Runtime Foundation (`app/core/graph/`):**
  * **Asynchronous Directed Execution Engine (`StatefulGraphRuntime`):** Replaced procedural command loops with a deterministic, stateful graph runtime supporting loops, retries, replanning, and specialist handoffs.
  * **Canonical State Model (`GraphState`):** Strongly-typed, centralized state container capturing Identity (`execution_id`, `task_id`), Input, Context, Routing, Plan (`GraphPlanStep`), Execution, Recovery, Outcome (`GraphExecutionStatus`), Presence, and Telemetry with lossless `to_dict()` and `from_dict()` serialization.
  * **Explicit Node Architecture:** Implemented modular nodes (`PerceiveNode`, `NormalizeNode`, `ContextNode`, `RouteNode`, `PlanNode`, `ExecuteNode`, `ObserveNode`, `VerifyNode`, `DecideNode`, `RecoverNode`, `RespondNode`) communicating strictly through structured graph state.
  * **Structured Control Primitives (`GraphDecision`):** Standardized control flow decisions (`CONTINUE`, `DONE`, `RETRY`, `REPLAN`, `HANDOFF`, `FAIL`, `CANCEL`) and error classifications (`TOOL_EXCEPTION`, `VERIFICATION_FAILED`, `TIMEOUT`, `USER_CANCELLED`, `MODEL_FAILURE`).
  * **First-Class Verification Gate (`VerifyNode`):** Mandated empirical side-effect verification through `EvidenceVerificationFabric` before any task is permitted to commit `DONE`, eliminating false passes.
  * **Atomic Tool Interruption & Cancellation:** Integrated real-time `asyncio.Event` monitoring inside `ExecuteNode` via `asyncio.wait(..., return_when=FIRST_COMPLETED)`, immediately terminating active tools without dangling background tasks or misleading events.
  * **Zero-Overhead Fast-Path Bypass:** Trivial deterministic commands traverse the minimal graph path with sub-millisecond dispatch (<0.2ms), maintaining SERA's instant desktop responsiveness.
  * **Unified EventBus Correlation:** All graph transitions emit correlated lifecycle events (`GRAPH_STARTED`, `GRAPH_NODE_ENTERED`, `GRAPH_NODE_COMPLETED`, `GRAPH_TRANSITION`, `GRAPH_COMPLETED`, `GRAPH_CANCELLED`, `GRAPH_FAILED`) maintaining consistent `execution_id` correlation without duplicate event emissions.
* **Empirical Graph Verification Test Suite (`tests/test_stateful_graph_runtime.py`):**
  * Added 14 comprehensive tests verifying simple execution, verification failure recovery, cancellation, bounded retries, conditional transitions, multi-step state continuity, event correlation, deduplication, fast-path bypass, observation vs verification separation, model failure handling, tool failure handling, timeout enforcement, and state snapshot restoration (all passing in 0.27s).

---

## [2.0.0-phase2c] — 2026-09-22

### Added
* **Master System Orchestrator (`sera.py`):**
  * Created unified root orchestrator launcher (`python sera.py`) managing the complete SERA lifecycle.
  * Verified HTTP health endpoint (`http://127.0.0.1:8765/api/health`) with exponential backoff.
  * **Empirical WebSocket Verification:** Connects to `ws://127.0.0.1:8765` and completes real handshake before launching Presence (zero false passes).
  * Robust signal handling (`SIGINT`, `SIGTERM`) with graceful teardown of all child processes (backend server and Electron presence) preventing orphaned background tasks.
* **Header-Only Native Window Dragging (`presence_desktop/`):**
  * Eliminated window drag drift by replacing asynchronous IPC mousemove delta calculations with native Windows DWM caption dragging (`-webkit-app-region: drag;` strictly on `.top-bar`).
  * Canvas, panel body, and input capsule are explicitly non-draggable (`-webkit-app-region: no-drag;`).
* **Complete Window Controls:**
  * Added dedicated non-draggable action buttons: Command Center (`CMD`), Minimize (`−`), and Close (`×`) with responsive hover states and Win32 IPC integration.

---

## [2.0.0-phase2b-behavior] — 2026-09-17

### Added
* **Primary Presence Behavior Engine (`presence_desktop/src/engine/PresenceBehaviorEngine.js`):**
  * **Dynamic Energy Budget (0.0 to 1.0):** Dynamically scales global activity across states (Dormant 0.0, Calm/Idle 0.25, Listening 0.52, Transcribing 0.68, Thinking 0.88, Executing 0.92, Speaking 0.72, Anomaly 0.98, Regeneration 1.0) to prevent visual overload.
  * **Visual Attention Model:** Per-layer focus dominance weights (`core`, `innerLattice`, `rings`, `glyphs`, `topology`, `filaments`, `particles`, `taskBridge`) highlighting focal operations while subordinating background elements.
  * **Organic Pacing ("No Constant Motion"):** Spontaneous micro-pauses (1–3s), non-linear phase drift, independent ring gear ratios, and randomized micro-bursts preventing deterministic repetition.
  * **Visual Memory System:** Persists spatial orientation seeds, primary branch angles, and target coordinates across state transitions.
  * **Multi-Band Audio Reactivity:** Web Audio analyser frequency decomposition into raw amplitude, bass, mid, and treble — modulating core physical displacement (bass) and filament wave propagation (treble) without global scale blowouts.
  * **Event-Driven Micro-Behavior:** Real-time event impulse triggers for `MODEL_SELECTED` (flash pulse), `TOOL_STARTED` (outward projection), `TOOL_COMPLETED` (return convergence), `FALLBACK` (glitch destabilization + alternate branch), `PROGRESS_UPDATE` (elastic completion progress), and `TASK_CANCELLED` (contraction).
  * **Computational Cellular Regeneration:** 7-stage reconstruction sequence upon task completion (fragmentation -> convergence -> lattice assembly -> edge reconnection -> stabilization -> core pulse -> calm baseline).
* **Behavior Engine Integration (`presence_desktop/src/engine/PresenceEngine.js` & `presence_desktop/src/App.js`):**
  * Connected all visual layers (GLSL core, HUD rings, glyph band, KNN 3D topology network, particle vector field, radial filaments, and task structures) to dynamic behavior outputs.
  * Added automated visual verification capturing 4 desktop state snapshots (`desktop_behavior_idle_variation.png`, `desktop_behavior_thinking_branches.png`, `desktop_behavior_execution_progress.png`, `desktop_behavior_regeneration.png`).

---

## [2.0.0-phase2] — 2026-09-17

### Added
* **Native Windows Primary Presence (`presence_desktop/`):**
  * True Windows desktop application overlay built on Electron 33 + Three.js WebGL 2.0 with 100% alpha-channel transparency (`transparent: true`, `frame: false`, `alwaysOnTop: true`, `backgroundColor: "#00000000"`).
  * System-wide global shortcut hook (`CommandOrControl+Space`) to summon and toggle input capsule from any active application.
  * Native repositioning via mouse drag, click-through toggle, and Windows system tray integration.
  * Direct bidirectional WebSocket link to the SERA Python runtime (`ws://127.0.0.1:8765`), consuming real-time EventBus events (`RUNTIME_STATE_CHANGED`, `ACTIVATION_STARTED`, `TASK_STARTED`, `TOOL_STARTED`, `TASK_COMPLETED`, `TASK_FAILED`).
  * Real-time microphone audio reactivity using Web Audio API analyser modulating core displacement and wave filaments.
* **8-Layer Computational Consciousness Visual Engine (`presence_desktop/src/engine/PresenceEngine.js`):**
  * **Layer 1 (Central Core):** Organic 3D Simplex noise GLSL displacement shader, white-hot center, dynamic inner rotating wireframe lattice, and 180-particle micro-singularity swarm.
  * **Layer 2 (Inner Energy):** Branching filaments and plasma streams with non-linear organic turbulence.
  * **Layer 3 (Computational Rings):** 5 segmented concentric rings with independent radii, angular speeds, sub-ticks, and gaps.
  * **Layer 4 (Information Band):** Procedural cybernetic glyph band with dynamic data symbols, mathematical marks, and orbital drift.
  * **Layer 5 (Geometric Topology Network):** Dynamic 3D K-nearest-neighbors graph continually forming, dissolving, and reconnecting edges.
  * **Layer 6 (Radial Filaments):** Tapered outward energy tendrils with audio-sensitive wave propagation.
  * **Layer 7 (Particle Field):** Volumetric 2,800-particle field responding to state vector fields (inward focus during listening, directional flow during execution, chaotic dispersal on anomaly, orbital reconvergence on completion).
  * **Layer 8 (Multi-Task Structural Engine):** 8 distinct task-specific computational structures:
    * *Greeting:* Subtle harmonic ripple ring with exponential decay.
    * *Time / Instant Query:* Celestial chronometer dial with 12 hour ticks, 60 sub-ticks, and high-speed vector needle.
    * *Browser:* Directional multi-segment conduit beam, flowing energy packets, and holographic destination reticle lock.
    * *Web Search:* 5-branch fractal research tree bifurcating into 10 glowing query result nodes.
    * *Vision / Screen Analysis:* Holographic rectangular frame, coordinate grid, and sweeping horizontal laser scanline.
    * *File Organization:* 36 discrete file particles clustering from chaotic cloud into structured 6x6 matrix.
    * *Code Construction:* 6 cascading vertical cybernetic code streams with syntax-tree crossbars.
    * *System Diagnostics:* 360-degree radar/lidar sweep line, 3 concentric range gauge rings, and 8 peripheral status beacons.
* **Empirical Snapshot Suite:**
  * Automated high-resolution window frame captures verifying alpha transparency and distinct task structures (`desktop_presence_live.png`, `desktop_presence_task.png`, `desktop_presence_diagnostics.png`, `desktop_presence_browser.png`).

---

## [2.0.0-phase2b] — 2026-09-17

### Added
* **Native Transparent Desktop Shell (`app/ui/desktop_presence.py`):**
  * Native desktop overlay launcher packaging `presence.html` using `pywebview` on Windows.
  * Borderless, frameless, and 100% alpha-transparent window presentation floating permanently above the desktop (`on_top=True`, `transparent=True`, `frameless=True`).
  * Display-aware window positioning with automatic work area computation for bottom-right screen docking (`compute_window_position`).
  * Win32 click-through toggle via `WS_EX_TRANSPARENT` and `WS_EX_LAYERED` extended window styles (`set_click_through`).
  * Bidirectional JavaScript-to-Python bridge (`DesktopPresenceAPI`) providing native window controls (`minimize`, `hide`, `show`, `close`, `toggle_on_top`) and bridge health verification (`ping`).
* **Desktop Presence Vertical Slice Test Suite (`tests/vertical_slices/presence/test_desktop_presence_shell.py`):**
  * 8 granular tests asserting default configuration compliance, custom docking geometry, position calculations, API bridge responses, dry-run lifecycles, pywebview window option contracts, server endpoint serving, and Evidence Verification Fabric disk asset validation.

---

## [2.0.0-phase2a] — 2026-09-17

### Added
* **Evidence Verification Fabric (`app/core/verification.py`):**
  * Core empirical verification engine establishing mandatory completion gates for all desktop and web actions.
  * Formalized `EvidenceType` (`PROCESS_RUNNING`, `WINDOW_HANDLE`, `STRUCTURED_DATA`, `FILE_SYSTEM`, `IMAGE_BUFFER`, `AUDIO_STREAM`, `GENERIC`).
  * Formalized `EvidenceRecord` data model capturing empirical verification status, source, telemetry details, and failure reasons.
  * Real Windows process table inspection via `psutil` verifying active PIDs and non-zombie statuses.
  * Web search structured data contract verification ensuring non-empty results and valid HTTP URLs.
  * Filesystem and screen capture buffer verification.
* **Command Pipeline Integration (`app/core/command_pipeline.py`):**
  * Integrated `EvidenceVerificationFabric` into `_execute_single_step`.
  * Emits `EVIDENCE_VERIFIED` event with empirical metadata.
  * Automatically transitions task to `BROKEN` and emits `TOOL_FAILED` / `TASK_FAILED` upon verification failure, completely eliminating false passes.
* **Vertical Slice Test Suite (`tests/vertical_slices/verification/test_evidence_fabric.py`):**
  * 12 granular, empirical tests asserting serialization, positive process detection, negative non-existent process detection, structured search data contracts, zero-result failure paths, and pipeline integration.

---

## [2.0.0-design] — 2026-09-17

### Added
* **Project Attribution:**
  * Author: Keshava Pandi A S
  * Creator: Keshava Pandi A S
  * Developer: Keshava Pandi A S
* **SERA 2.0 Architectural Specifications:**
  * `docs/SERA_2_PRODUCT_VISION.md`: Dual-body paradigm (floating transparent presence vs. technical command center).
  * `docs/SERA_2_ARCHITECTURE.md`: Decoupled micro-kernel, unified event bus, and Model Fabric.
  * `docs/SERA_2_VISUAL_SYSTEM.md`: Three.js WebGL shader specifications, concentric ring mathematics, GPGPU curl particles, and 9 state modes.
  * `docs/SERA_2_CAPABILITY_MATRIX.md`: 16-dimension capability audit with verification gates.
  * `docs/SERA_2_MCP_PLAN.md`: Native Model Context Protocol (MCP) client architecture and initial catalog.
* **Primary SERA Presence (Phase B Engine):**
  * Created `app/ui/static/presence.html`, `presence.css`, `presence_engine.js`, `status_morpher.js`, and `presence_controller.js`.
  * Implemented 100% alpha-transparent WebGL canvas with Wisdom King / Raphael computational core.
  * Implemented 9 interactive physics states: `IDLE`, `LISTENING`, `TRANSCRIBING`, `THINKING`, `EXECUTING`, `SPEAKING`, `BROKEN`, `CANCELLED`, `COMPLETED`.
  * Implemented signature **Computational Cellular Reconstruction** completion animation.
  * Added single-line kinetic status text morpher with blur/fade transitions.
  * Vendored offline `three.min.js` (603 KB) in `app/ui/static/js/vendor/`.
* **Empirical Web Search Engine:**
  * Implemented `parse_duckduckgo_html` in `app/tools/browser/web_search.py` with multi-line title cleaning, sponsored ad filtering, and strict data contracts (`title`, `url`, `snippet`, `source`).
  * Added live search preview event streaming to the UI.
  * Created comprehensive 5-test vertical slice in `tests/vertical_slices/web_search/test_web_search_suite.py`.
* **Google Gemini 3.5 Transcribe STT:**
  * Added dedicated `gemini-3.5-transcribe` integration in `app/models/stt/gemini.py`.
  * Preserved local Faster-Whisper CUDA FP16 as automatic offline fallback.
* **Real Application Launch Verification:**
  * Added process table lookup (`Get-Process`) and window title handle confirmation to `app/tools/windows/apps.py` to eliminate false passes.

---

## [1.5.0-phase5d5] — 2026-08-31

### Added
* **Adaptive Temporal Runtime:**
  * Resource-aware router with model-level health tracking and volatile cooldowns (`app/core/resource_cache.py`).
  * 3-column Architect Studio in `architect.js` for primary, fallback, and disabled model assignment.
  * Live embedded execution theater in `live.js` with structured tool badges and inline telemetry.
  * Multi-step bounded security manager enforcing 5-step loop limits and 10s action timeouts.

---

## [1.4.0-phase5d] — 2026-08-25

### Added
* **Temporal Aura Operating Interface:**
  * High-density dark workstation design system in `app/ui/static/css/`.
  * Asynchronous WebSocket gateway server on port 8765 in `app/ui/server.py`.
  * E2E test suites using Playwright for navigation and runtime UI synchronization.

---

## [1.3.0-phase5c2] — 2026-08-20

### Added
* **Hold-to-Talk Voice Architecture:**
  * Global Windows keyboard hook on `Ctrl+Space` for dedicated audio capture.
  * Wake-word yielding logic ensuring clean audio handoffs between background listeners and intentional speech.
  * Real-time acoustic interruption cutting off TTS playback upon user speech detection.

---

## [1.2.0-phase4] — 2026-08-10

### Added
* **Multi-Provider LLM Expansion:**
  * Integration of Mistral AI (Codestral, Mistral Small/Large), Groq (Llama-3.3-70B, Qwen-2.5), and OpenRouter.
  * Per-model health tracking and latency exponential moving average calculations.

---

## [1.1.0-phase2] — 2026-07-28

### Added
* **Local Speech & Tool Infrastructure:**
  * Local Faster-Whisper CUDA speech recognition.
  * Streaming TTS audio engine.
  * Windows system automation tools (PowerShell execution, volume control, window title queries).

---

## [1.0.0] — 2026-07-15

### Added
* **Core Agent Foundation:**
  * Initial `SERARuntime` event loop and `SERAState` state machine.
  * Async `EventBus` pub/sub infrastructure.
  * CLI voice agent entry point in `main.py`.
