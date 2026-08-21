# SERA 1.0 — UI Architecture & Command Center Blueprint

## 1. System Overview

The SERA Command Center is a decoupled, asynchronous, real-time user interface designed around the **Temporal Aura** design system.

```
┌────────────────────────────────────────────────────────┐
│               SERA CLI / HEADLESS RUNTIME              │
│  State Machine • EventBus • ModelRouter • Tools • STT  │
└───────────────────────────┬────────────────────────────┘
                            │ (In-Memory Observers)
┌───────────────────────────▼────────────────────────────┐
│                    SERA UI SERVER                      │
│     Unified Async TCP Server (HTTP GET/POST + WS)      │
│          http://127.0.0.1:8765 / ws://.../ws           │
└───────────────────────────┬────────────────────────────┘
                            │ (WebSocket Events + REST)
┌───────────────────────────▼────────────────────────────┐
│                 TEMPORAL AURA CLIENT                   │
│   Vanilla JS SPA • SVG Bezier Graph • Real-time Aura   │
└────────────────────────────────────────────────────────┘
```

## 2. Decoupled Gateway Architecture

- **Zero-Block Guarantees**: The UI server communicates via non-blocking asynchronous event loops. If the UI client closes or disconnects, the voice runtime and desktop agent continue operating with zero latency overhead.
- **Bi-Directional WebSocket Stream**: Streams `RUNTIME_STATE_CHANGED`, `MODEL_SELECTED`, `MODEL_FALLBACK`, `TOOL_STARTED`, `TOOL_COMPLETED`, `VISION_STARTED`, `VISION_COMPLETED`, `TTS_STARTED`, `TASK_CANCELLED`, and `SECURITY_CONFIRMATION_REQUIRED`.
- **Unified REST API**:
  - `/api/state`: Instant snapshot of system state and hardware telemetry.
  - `/api/workflow`: Dynamic execution graph nodes and edges.
  - `/api/roles/update`: Validated candidate chains and execution mode updates.
  - `/api/providers`: Provider cards, model health, and dynamic quota metrics.
  - `/api/providers/add`: Vercel-style custom provider onboarding without leaking secrets.
  - `/api/security`: SecurityManager permission policies and privacy boundaries.
  - `/api/memory`: Categorical memory core retrieval and forgetting.
  - `/api/history`: Chronological interaction sessions.
  - `/api/telemetry`: Pipeline latency waterfall and event trace.

## 3. View Architecture Across 3 Domains

- **COMMAND**:
  - `LiveView`: Human-facing conversational interface, reactive Aura Orb, 5.0s recording countdown, current task progress card.
  - `WorkflowView`: Temporal execution graph, curved fallback branches, particle flow, and role candidate editor.
- **INTELLIGENCE**:
  - `AgentsView`: Multi-agent hierarchical executors (Planner, Desktop, Vision, Research).
  - `MemoryView`: Neural Knowledge Core with categories (Preferences, Semantic, Episodic, Projects, Documents).
- **SYSTEM**:
  - `ProvidersView`: Multi-provider acceleration dashboard, dynamic quotas, and provider onboarding.
  - `HistoryView`: Chronological session timeline with separate Replay and Run Again actions.
  - `DebugView`: Engineering latency waterfall and filtered EventBus console stream.
  - `SecurityView`: Security boundaries, permissions matrix, and action confirmation modals.
