# SERA 1.0 — Temporal Aura Master UI & Command Center Specification

## 1. Design Philosophy & Temporal Aura Visual Language

SERA is an intelligent desktop AI operating system and command center. The visual interface is built upon the **Temporal Aura** design language—inspired by dimensional energy fields, layered flowing timelines, and cinematic science-fiction aesthetics without replicating any third-party proprietary designs.

### Core Visual Principles
1. **Temporal**: Left-to-Right horizontal timelines, layered fallback branches, dynamic recovery paths, and dimensional depth.
2. **Aura**: State-driven energy glows, audio-reactive acoustic rings, harmonic breathing pulses, and soft particle streams. Glow is never decorative noise; it strictly communicates real-time system state.
3. **Intelligence**: Crisp typography, high data density with zero clutter, structured cards, and transparent pipeline visibility.
4. **Motion**: Purposeful state-dependent animations. No continuous fake animations when idle; animations ignite only on real runtime transitions.

---

## 2. Global Shell & Central State Aura

Every view in the SERA Command Center shares a persistent header and state monitoring infrastructure.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ◈ SERA    ● LISTENING [4.2s]    Current Task: Search RTX 5090    [GPU: 18%  RAM: 3.4GB]   🔒 CLOUD │
│                                                                                                  │
│ [COMMAND: (1) LIVE  (2) WORKFLOW]  [INTEL: (3) AGENTS  (4) MEMORY]  [SYSTEM: (5) PROV  (6) HIST  (7) DBG  (8) SEC] │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Visual State Aura Signatures
- **IDLE**: Subtle harmonic cyan breathing halo (`4s` cycle). Low energy.
- **LISTENING**: Acoustic expanding cyan/amber rings with 5.0-second countdown progress ring.
- **TRANSCRIBING**: Inward particle convergence with high-speed lateral shimmer.
- **THINKING**: Concentrated dual orbital energy rings (violet & cyan) revolving during LLM generation.
- **EXECUTING**: Directional emerald energy flow traveling through the active workflow path.
- **SPEAKING**: Sound-reactive amplitude visualizer responding to Fish Audio TTS speech.
- **CONFIRMING**: Amber pulsating warning aura for dangerous system action authorization.
- **BROKEN**: Fractured crimson aura with broken temporal strand indicators and explicit failure diagnostics.
- **CANCELLED**: Rapid collapse of active particles back into the core on hotkey or voice interruption.

---

## 3. Dual Voice Activation Architecture & 5-Second Capture

SERA unifies two distinct activation pathways into a single execution engine:
1. **Global Hotkey**: `Ctrl + Space` (300ms thread-safe debounce).
2. **Local Wake Word**: `"SERA"` (openWakeWord local detector).

### 5-Second Fixed Capture Flow
```
[Ctrl+Space] or ["SERA"] ──► LISTENING (5.0s Countdown Ring) ──► TRANSCRIBING ──► ROUTER
```
- A circular radial meter tracks the 5.0s recording window.
- Visual countdown display: `05.0s` ➔ `04.0s` ➔ `00.0s`.
- Automatic instant transition to `TRANSCRIBING` at `00.0s` with zero extra keystrokes required.

---

## 4. Navigation Architecture & View Organization

The Command Center organizes 8 first-class views across 3 primary operational domains:

### A. COMMAND
1. **LIVE (`1`)**: Human-facing conversational interface with central Aura Orb, 5s recording visualizer, unified typed/voice chat stream, and Current Task progress panel.
2. **WORKFLOW (`2`)**: Defining horizontal temporal execution graph, active path glow, fallback branches, BROKEN state visualization, and Temporal Tree candidate editor.

### B. INTELLIGENCE
3. **AGENTS (`3`)**: Multi-agent hierarchy visualizer showing Planner, Desktop Agent, Vision Specialist, and Research Agent workflows (extensible for future Browser, RAG, and MCP agents).
4. **MEMORY (`4`)**: Neural Knowledge Core displaying categorical memory clusters (Preferences, Semantic, Episodic, Projects, Documents) with provenance metadata and Edit/Forget controls.

### C. SYSTEM
5. **PROVIDERS (`5`)**: Model infrastructure dashboard featuring dynamic quota meters, model-level health tracking, candidate chain positions, and Vercel-style provider onboarding modal.
6. **HISTORY (`6`)**: Chronological session timeline with turn-by-turn pipeline telemetry, and explicit separation between **Replay Visualization** and **Run Again**.
7. **DEBUG (`7`)**: Engineering telemetry console with live pipeline Latency Waterfall and EventBus stream with category filters.
8. **SECURITY (`8`)**: Permissions matrix (Screen Reading, UI Automation, File System, Shutdown), Action Confirmation modals, and Local vs Cloud processing privacy indicator.

---

## 5. Temporal Aura Workflow Engine

### Horizontal Execution Pipeline
```
[INPUT / STT] ──► [ROUTER] ──► [COGNITION / ROLE] ──► [TOOLS / ACTIONS] ──► [OBSERVE / VERIFY] ──► [STREAMING TTS]
```

### Three Execution Modes Per Role
Every role (`reasoning`, `fast`, `desktop`, `vision`, `ocr`, `embeddings`, `stt`, `tts`) supports:
1. **PRIMARY ONLY**: Only the primary model executes. If unavailable/rate-limited, failover is blocked and the node transitions to `BROKEN`.
2. **FALLBACK ORDER**: Deterministic sequential failover down the candidate chain (`Primary` ➔ `Fallback #1` ➔ `Fallback #2`).
3. **CUSTOM**: User-configured temporal flow with capability validation.

### Broken Visual State & Recovery
- When a candidate receives an HTTP 429/402 or failure:
  - The node displays a fractured crimson border with failure reason (e.g. `429 TPM LIMIT • Cooldown: 12s`).
  - If a fallback candidate exists, the fallback branch illuminates in glowing amber energy.
  - If no candidate succeeds, the execution path terminates in `BROKEN`.

---

## 6. Dynamic Quota Engine & Provider Management

Providers expose vastly different quota metrics. SERA dynamically renders the metrics each provider natively reports without fabricating estimates:

### Quota Display Patterns
- **Groq Style**: Rate-based metrics (`Requests/Min: 28/30`, `Tokens/Min: 7.8K/8K`, `Requests/Day`, `Tokens/Day`).
- **Gemini Style**: Window-based percentages (`Weekly Limit: 86% Remaining`, `5-Hour Limit: 100% Remaining`).
- **Unreported Providers**: Explicitly marked as `Quota: Unknown / Not Reported`.

### Vercel-Style Provider Onboarding Pipeline
```
[+ ADD PROVIDER] ──► [Test Connection] ──► [Discover Models] ──► [Capability Check] ──► [Role Suggestion] ──► [Save]
```
- Masked secret storage: API keys are referenced via environment variables (e.g. `MY_PROVIDER_API_KEY`) and never logged, sent over WebSockets, or exposed in the UI.

---

## 7. Security & Action Authorization

- **Real-Time Permission Matrix**: Live visualization of `SecurityManager` rules (`Screen Reading: Allowed`, `File Deletion: Confirm Always`, `Shutdown: Confirm Always`, `Credentials: Blocked`).
- **Interactive Action Confirmation Modal**: Dangerous system or desktop actions pause execution and present interactive `[ALLOW ONCE]` / `[DENY]` controls.
- **Privacy Indicator**: Transparent indicator displaying whether processing is `LOCAL` (e.g. Faster-Whisper, Native UIA) or `CLOUD` (e.g. Groq, Gemini, Fish Audio).

---

## 8. REST & WebSocket Gateway Data Contracts

### Core Endpoints
- `GET /api/state`: Current runtime status, active task, telemetry, hardware gauges.
- `GET /api/workflow`: Dynamic execution graph nodes, edges, roles, and health.
- `POST /api/roles/update`: Validated candidate chain update (rejects changes during `EXECUTING`).
- `GET /api/providers`: Provider cards, model capabilities, dynamic quota metrics, health status.
- `POST /api/providers/add`: Test connection, discover models, and register custom provider.
- `GET /api/security`: SecurityManager permission policies and privacy status.
- `GET /api/memory`: Memory core items, categories, confidence, and provenance.
- `GET /api/history`: Chronological interaction sessions and turn execution traces.
- `WS /ws`: Bi-directional real-time event streaming (`RUNTIME_STATE_CHANGED`, `ROUTER_DECISION`, `MODEL_FALLBACK`, `TOOL_STARTED`, `TOOL_COMPLETED`, `VISION_STARTED`, `VISION_COMPLETED`, `TTS_STARTED`, `TASK_CANCELLED`, `ROLE_UPDATED`, `SECURITY_CONFIRMATION_REQUIRED`).

---

## 9. Performance & Accessibility Standards

- **Virtualization & Delta Updates**: Only update modified nodes/cards on incoming WebSocket events rather than re-rendering the full DOM.
- **Responsive Layout**: Optimized for 1920x1200 (16:10), with full scaling support for 1080p, 1440p, and 4K.
- **Accessibility**: Multi-modal status communication combining color, iconography, text badges, and keyboard shortcuts (`1–8`, `Ctrl+Space`, `Esc`).
