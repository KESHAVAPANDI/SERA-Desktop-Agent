# SERA 1.0 UI Architecture Specification

## 1. System Overview & Client-Server Decoupling

The SERA UI is designed as a decoupled client layer operating over the SERA runtime core. The existing backend (STT, TTS, ModelRouter, Agent Engine, Windows UI Automation, TargetResolver, SecurityManager, and EventBus) remains completely independent and fully functional in headless CLI mode.

```
┌────────────────────────────────────────────────────────────┐
│                    SERA RUNTIME CORE                       │
│  [EventBus] ──► [SERAState] ──► [ModelRouter] ──► [Agent]  │
└─────────────────────────────┬──────────────────────────────┘
                              │ Real-time Events & State
                              ▼
┌────────────────────────────────────────────────────────────┐
│               UI BRIDGE & WEBSOCKET GATEWAY                │
│             (app/ui/server.py: 127.0.0.1:8765)              │
└─────────────────────────────┬──────────────────────────────┘
                              │ JSON Event Stream / REST IPC
                              ▼
┌────────────────────────────────────────────────────────────┐
│               SERA COMMAND CENTER (SPA UI)                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    GLOBAL HEADER                     │  │
│  │   [Status Orb] [Active Task] [GPU/Net] [View Tabs]   │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │                     VIEWPORT                         │  │
│  │  1. WORKFLOW  (Temporal Horizontal Execution Graph)  │  │
│  │  2. LIVE      (Futuristic Voice Orb & Unified Chat)  │  │
│  │  3. AGENTS    (Multi-Agent Hierarchy & Roles)        │  │
│  │  4. MEMORY    (Neural Memory Core & Knowledge RAG)   │  │
│  │  5. PROVIDERS (Provider Health, Quotas & Role Chains)│  │
│  │  6. HISTORY   (Timeline, Session Details & Replay)   │  │
│  │  7. DEBUG     (Real-time Telemetry & Event Streams)  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

---

## 2. Event-Driven Architecture & Synchronization

The UI client connects to the backend gateway over WebSocket (`ws://127.0.0.1:8765/ws`) and subscribes directly to runtime state changes.

### Supported Gateway Event Streams:
1. `RUNTIME_STATE_CHANGED`: Emitted on state transitions (`IDLE`, `LISTENING`, `TRANSCRIBING`, `THINKING`, `EXECUTING`, `SPEAKING`, `CONFIRMING`, `ERROR`).
2. `TRANSCRIPT_RECEIVED`: Emitted when STT yields final command text.
3. `ROUTER_DECISION`: Emitted with chosen role, candidate provider, and health status.
4. `MODEL_FALLBACK`: Emitted when candidate 429/402 triggers failover.
5. `TOOL_EXECUTION`: Emitted on semantic tool invoke, execution, and verification.
6. `VISION_PERCEPTION`: Emitted when screenshot perception hierarchy is engaged.
7. `AGENT_UPDATE`: Emitted when planner or multi-agent tasks spawn/complete.
8. `TELEMETRY_SAMPLE`: Emitted with live TTFT, TTFA, latency metrics, and quota updates.

---

## 3. Component Hierarchy

```
App
├── GlobalHeader
│   ├── BrandLogo
│   ├── StateIndicator (Aura Orb)
│   ├── ActiveTaskTicker
│   ├── HardwareGauges (GPU / System Memory)
│   └── NavigationBar (7 Main Views)
├── MainContainer
│   ├── WorkflowView (Interactive Horizontal Canvas)
│   ├── LiveView (Aura Voice Orb + Unified Stream Chat)
│   ├── AgentsView (Stylized Agent Nodes & Dynamic Flow)
│   ├── MemoryView (Memory Core + RAG Knowledge Clusters)
│   ├── ProvidersView (Provider Cards, Health & Quota Bars)
│   ├── HistoryView (Timeline, Session Cards & Replay Modal)
│   └── DebugView (Real-time Latency Waterfall & Event Log)
└── GlobalNotificationDrawer / ToastSystem
```

---

## 4. Headless & Production Independence

- **Zero Coupling**: If the UI server is not launched, SERA operates identically in headless CLI voice mode.
- **Bi-directional Control**: The UI can send text prompts, interrupt speech, reorder fallback candidates, and trigger verification actions over IPC without altering runtime business logic.
