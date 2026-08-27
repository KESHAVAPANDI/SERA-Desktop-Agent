# SERA 1.0 — Phase 5D.5 Architecture Documentation
## Adaptive Temporal Runtime + Live Execution Theater

### 1. Architectural Overview
Phase 5D.5 reconciles the real backend runtime with the frontend 3-Surface Architecture (**LIVE**, **WORKFLOW**, **ARCHITECT**), eliminating blind failovers, silent completion drops, and monolithic graph confusion.

```
+------------------------------------------------------------------------------------+
|                                    SERA RUNTIME                                    |
|                                                                                    |
|  +--------------------+     +------------------------+     +--------------------+  |
|  | Speech & Hotkey    | --> | Preflight Model Router | --> | Agent Execution    |  |
|  | Voice / Text Turns |     | (ResourceStateCache)   |     | Desktop & Search   |  |
|  +--------------------+     +------------------------+     +--------------------+  |
|                                         |                                          |
|                                         v                                          |
|                               +--------------------+                               |
|                               | Real Provider HTTP |                               |
|                               | Rate-Limit Headers |                               |
|                               +--------------------+                               |
+------------------------------------------------------------------------------------+
                                          |
                     WebSocket / EventBus Broadcast Stream
                                          v
+------------------------------------------------------------------------------------+
|                              FRONTEND 3-SURFACE ARCHITECTURE                       |
|                                                                                    |
|  1. LIVE VIEW:                                                                     |
|     - Chat auto-minimizes during execution: [⚡ TASK IN PROGRESS]                  |
|     - Pure-Black Embedded Mini-Theater SVG Canvas                                 |
|     - Interactive "Why This Model?" badge                                          |
|     - Guaranteed Assistant Response settlement                                     |
|                                                                                    |
|  2. WORKFLOW VIEW:                                                                 |
|     - Dedicated full-screen temporal execution theater                             |
|     - Shared task_id, node topology & plasma edge rendering                         |
|                                                                                    |
|  3. ARCHITECT STUDIO:                                                              |
|     - Clean 3-Column Studio (Roles | Role Config & Candidates | Live Preview)      |
|     - 4 Execution Modes: PRIMARY_ONLY, FALLBACK_ORDER, RESOURCE_AWARE, CUSTOM       |
|     - Draggable candidate priority ranking & Offline simulation suite             |
+------------------------------------------------------------------------------------+
```

---

### 2. Core Components

#### A. ResourceStateCache (`app/core/resource_cache.py`)
- Tracks per-provider, per-model telemetry in real time:
  - `remaining_tokens`, `remaining_requests`
  - `reset_times` (`s`, `ms`, ISO strings)
  - HTTP 429 backoff cooldown timestamps (`cooldown_until`)
  - Exponentially smoothed latency and failure rates
- Intercepts provider response headers across `Groq`, `Mistral`, `Cerebras`, `OpenRouter`, and `Gemini`.
- Preflight evaluation: Disqualifies candidates before making network calls when `remaining_tokens < estimated_request_tokens`.

#### B. 4 Architect Execution Modes (`app/core/router.py`)
1. **`PRIMARY_ONLY`**: Direct routing to primary model.
2. **`FALLBACK_ORDER`**: Sequential fallback to next candidate on 429/network failure.
3. **`RESOURCE_AWARE`** (Default): Preflight scoring evaluating quota headroom, rate limits, and latency to pick optimal healthy candidate under 0.2ms.
4. **`CUSTOM`**: Custom routing rules and priority overrides.

#### C. Guaranteed Assistant Response Contract (`app/core/runtime.py` & `app/core/agent.py`)
- Standardized turn response contract ensuring all turns produce settled assistant messages:
  - Streaming: `STREAM_START` $\to$ `STREAM_TOKEN*` $\to$ `STREAM_COMPLETE` $\to$ settled bubble.
  - Non-streaming: `AGENT_RESPONSE` (status: `COMPLETED`) $\to$ settled bubble.
  - Actions without natural responses produce explicit voice/text acknowledgement (e.g., *"Chrome is now open."*).

#### D. Live Embedded Execution Theater (`app/ui/static/js/views/live.js`)
- Transforms the active Live view into a compact task execution cockpit:
  - Minimizes chat history into a glowing progress overlay.
  - Renders a pure-black mini temporal SVG canvas with active pulsing nodes (`STT ~~~~> ROUTER ~~~~> MODEL ~~~~> TOOL`).
  - Displays interactive `#live-current-model-badge` displaying the "Why This Model?" breakdown modal.
  - Provides controls: `[Expand Chat]`, `[View Workflow]`, `[Stop Task]`.

---

### 3. Verification & Test Matrix
- **Unit & Router Tests**: `tests/test_phase5d5_resource_router.py` (5/5 PASSED).
- **Architect Resource-Aware E2E**: `tests/e2e/phase5d5/test_architect_resource_aware.py` (3/3 PASSED).
- **Live Embedded Theater E2E**: `tests/e2e/phase5d5/test_live_theater.py` (4/4 PASSED).
- **Full Phase 5 Regression**: 33/33 PASSED across Phase 5D.2, 5D.3, 5D.4, 5D.5.
- **Phase 4 & 5C Regression**: 25/25 PASSED.
