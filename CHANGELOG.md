# Changelog

All notable changes to the SERA project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
