# SERA 1.0 — Master UI/UX Specification v2.0
**The Temporal Aura Operating Interface & Visual System**

---

## 1. Design Vision & Interaction Philosophy
SERA is an **AI Desktop Operating Interface**, not a web dashboard. It balances quiet, focused standby states with dynamic, dimensional energy when executing tasks.

### 1.1 Core Visual Metaphor: Temporal Energy
- **Temporal Space:** Deep cosmic dark palette (`#08090D`, `#0D0F17`) with layered atmospheric depth blur and drifting temporal energy strands.
- **Dimensional Corridors:** Energy conduits connecting execution nodes rather than static 1px borders.
- **Event-Driven Motion:** Luminescence and energy pulses originate strictly from actual backend telemetry events.

### 1.2 The 8-Color Semantic System
```
┌────────────────────────────────────────────────────────┐
│ Color Palette       Role / Domain                      │
├────────────────────────────────────────────────────────┤
│ Cyan (#00E5FF)       Voice & Input Capture             │
│ Electric Blue (#007AFF) Router & Intent Classification │
│ Violet (#8B5CF6)     Reasoning & Core Orchestration    │
│ Purple (#D946EF)     Vision & Multimodal Perception    │
│ Amber (#F59E0B)      Desktop & Windows UI Tools        │
│ Emerald (#10B981)    Verification, Memory & RAG        │
│ Magenta (#EC4899)    Agent Studio & Delegation         │
│ Gold (#EAB308)       TTS & Audio Output Generation     │
│ Crimson (#EF4444)    BROKEN, Failed & Rate-Limited     │
└────────────────────────────────────────────────────────┘
```

---

## 2. Navigation Architecture & Global Header

### 2.1 Navigation Structure
Seven dedicated primary views:
1. **Live:** Central voice & conversation cockpit with reactive breathing aura.
2. **Workflow:** 3-layer dimensional freeform node canvas with temporal corridors and live runtime energy.
3. **Agents:** Agent Studio featuring animated character identities, active/planned badges, and task packet delegation.
4. **Providers:** Comprehensive provider control plane with dynamic quotas, model health, and workflow node jumping.
5. **Memory:** Truthful Neural Knowledge Core with clean empty states.
6. **History:** Execution archive with distinct Replay (visual) and Run Again (execution) actions.
7. **Debug / Settings:** Structured event telemetry, raw JSON drawer, and security policy matrix.

### 2.2 Global Status Header
Displays authoritative, truthful backend telemetry:
- **SERA Status:** `● IDLE` | `● LISTENING` | `● TRANSCRIBING` | `● THINKING` | `● EXECUTING` | `● SPEAKING`
- **Active Task:** Current step and progress bar or `No active task`.
- **Runtime:** `● ONLINE` | `○ OFFLINE`
- **Mic:** `● READY` | `○ MUTED`
- **Wake:** `○ NOT CONFIGURED` (truthful reporting when local weights are absent)
- **STT:** Configured primary (`NVIDIA Canary`) vs Actual active (`Faster-Whisper`)
- **System Metrics:** Live GPU utilization (%) and RAM consumption (GB).

---

## 3. Detailed View Specifications

### 3.1 Live Cockpit View
- **Central Aura:** Audio-reactive orb breathing gently in `IDLE`, glowing cyan in `LISTENING`, violet in `THINKING`, amber in `EXECUTING`, and gold in `SPEAKING`.
- **Hold-To-Talk Timer:** Precise millisecond stopwatch (`00:01.24`) visible when `Ctrl+Space` is held down.
- **Live Activity Rail:** Right-aligned rail streaming structured events in real time.
- **Auto-Navigation:** When a complex task (computer action, search, vision, multi-step) is initiated, the UI smoothly shifts focus to the **Workflow** view.

### 3.2 Temporal Aura Workflow Canvas
- **Layer 1 (Background):** Subtle drifting temporal strands and atmospheric particles.
- **Layer 2 (Canvas):** Freeform 2D DaVinci/Blender-style graph with pan, zoom, grid snap, center active, fit, and candidate reordering.
- **Layer 3 (Runtime Energy):** Animated energy pulses travelling through conduits on `MODEL_SELECTED`, `TOOL_STARTED`, `TOOL_COMPLETED`, and `VERIFICATION_COMPLETED`.

### 3.3 Agent Studio
- **Identities:**
  - SERA Core (Orchestrator)
  - Desktop Agent (UI Automation)
  - Vision Agent (Screen Perception)
  - Research Agent (Web & Search)
  - RAG Agent (`◌ PLANNED`)
  - MCP Agent (`◌ PLANNED`)
- **Visuals:** Animated character personas with distinct idle/thinking/executing states, animated task packet delegation lines, and an Agent Inspector drawer.

### 3.4 Provider Control Plane
- **Registry:** Groq, Gemini, Mistral, NVIDIA, Fish Audio, OpenRouter, Cerebras, Z.AI.
- **Model Health:** Granular model-level health tracking (Healthy, Rate Limited with cooldown, Degraded, Unavailable).
- **Dynamic Quotas:** Provider-specific metrics (RPM, TPM, RPD, Weekly, 5-Hour).
- **Interactivity:** Filter by role/health, add custom provider, and jump directly to associated workflow node.

### 3.5 Neural Knowledge Core (Memory)
- **Truthful Presentation:** No fabricated records. Pristine empty state when no embeddings are stored.
- **Actions:** Add Knowledge, Index Folder, Import Document.

### 3.6 History & Execution Archive
- **Session List:** Compact timeline with timestamp, query, duration, and status.
- **Execution Inspector:** Detailed transcript, step breakdown, model selection, tool latency, and verification results.
- **Actions:** **Replay Visualization** (visual trace only) vs **Run Again** (real live execution).

### 3.7 Debug & Security Console
- **Event Log:** Structured cards categorized by State, Model, Tool, Vision, Audio, and Network.
- **Controls:** Search, pause, clear, export JSON, and expandable raw payload drawer.
- **Security Matrix:** Interactive toggles for screen reading, UI automation, file modifications, and cloud routing.
