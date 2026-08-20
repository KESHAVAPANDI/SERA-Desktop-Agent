# SERA 1.0 UI Navigation & View Scaffolding Specification

## 1. Top-Level Navigation Architecture

The SERA Command Center features 7 first-class primary views accessible from the persistent global header. The **WORKFLOW** view serves as the primary home screen.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  [✦ SERA]  (● IDLE)  |  Task: Ready  |  [GPU: 14%  RAM: 3.2GB]  |  (1) WORKFLOW   (2) LIVE │
│                                                                   (3) AGENTS     (4) MEMORY │
│                                                                   (5) PROVIDERS  (6) HISTORY│
│                                                                   (7) DEBUG                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. View Breakdown & Functional Roles

### 1. WORKFLOW (Primary Home View)
- **Role**: Horizontal temporal execution graph visualizer.
- **Interactions**:
  - Live execution trace (active path lights up, inactive branches subdue).
  - Branching visualization (Primary → 429 Failover → Fallback).
  - Canvas pan and zoom.
  - Node click opens detailed execution inspector drawer.

### 2. LIVE (Voice & Chat Interface)
- **Role**: Central SERA conversational sphere and unified stream.
- **Interactions**:
  - Central reactive Aura Orb responding dynamically to runtime states (`IDLE`, `LISTENING`, `THINKING`, `SPEAKING`, `ERROR`).
  - Unified typed input box + voice capture telemetry.
  - "Inspect Turn Execution" shortcut jumping directly to the Workflow Graph.

### 3. AGENTS (Multi-Agent Visualization)
- **Role**: Hierarchical stylized visualization of specialized agents.
- **Agents**: Planner, Researcher, Vision Specialist, Desktop Executor, Memory Engine, Verifier, Synthesizer.
- **Interactions**: Active task delegation paths and status cards.

### 4. MEMORY (Neural Knowledge Core)
- **Role**: Visual knowledge repository and RAG search breakdown.
- **Structure**: Central Memory Core surrounded by satellite regions (Preferences, Projects, Facts, Documents).
- **Interactions**: Search filter, category pills, confidence badges.

### 5. PROVIDERS (Health, Quota & Candidate Chains)
- **Role**: Comprehensive model infrastructure dashboard.
- **Interactions**:
  - Expandable provider cards (Groq, Mistral, Gemini, OpenRouter, Cerebras, Z.AI, NVIDIA, Fish).
  - Live quota meters (Requests, Tokens, RPM, Reset countdowns).
  - Health status badges (`HEALTHY`, `RATE_LIMITED`, `UNAVAILABLE`, `AUTH_ERROR`).
  - Active role candidate chains.

### 6. HISTORY (Session Timeline & Replay)
- **Role**: First-class chronological interaction log.
- **Structure**: Grouped daily sessions with turn summaries, duration, and models used.
- **Actions**:
  - **Replay Visualization**: Visually steps through the historical workflow graph.
  - **Run Again**: Re-submits the task to the live runtime.
  - Global search & multi-facet filters.

### 7. DEBUG (Developer Telemetry Console)
- **Role**: Deep telemetry inspection for real-time observability.
- **Sections**:
  - Real-time latency waterfall (STT → Router → LLM TTFT → Tool → TTS TTFA).
  - EventBus trace stream.
  - Provider health state matrix.

---

## 3. Keyboard Navigation & Shortcuts

- `1` through `7`: Quick jump to views 1-7.
- `Ctrl + Space`: Activate voice command capture (native global hotkey).
- `Esc`: Close open drawers, modals, or cancel active execution.
- `Space`: (in Replay mode) Play/Pause execution graph replay.
