# SERA 1.0 — Phase 5D.4 Architectural Diagnosis & Deep Assessment
**Phase:** 5D.4: Temporal Execution Theater & Live / Workflow / Architect Separation  
**Status:** DIAGNOSIS COMPLETE  
**Date:** August 2026  

---

## 1. Executive Summary & Core Product Model

In Phase 5D.3, we established the full-width conversational stream, inline work cards, dynamic capability registry, contextual interrupt UX, and eliminated premature auto-switching to the Workflow view.

However, a critical product-level gap remains in the relationship between **LIVE**, **WORKFLOW**, and **ARCHITECT**:
1. **LIVE**: "What is SERA doing for me?" — Conversational surface, compact task overlay during active execution, interactive work results, guaranteed final assistant message.
2. **WORKFLOW**: "How is SERA doing this?" — Live temporal execution theater. A pure black canvas where nodes and high-energy plasma connections materialize dynamically during execution, without preloaded candidate cards.
3. **ARCHITECT**: "How have I configured SERA to work?" — Persistent editable configuration of the Temporal Framework (Primary Only, Fallback Order, Custom modes, semantic candidate priority drag vs visual positioning, configuration preview, test simulation).

---

## 2. Deep Root-Cause Analysis

### 2.1 Why Live Responses Can Fail to Appear
- **Root Cause**: In `app/core/runtime.py` and `app/ui/server.py`, the emission of `AGENT_RESPONSE` or `TASK_COMPLETED` was not guaranteed for all execution branches. 
  - For example, local fast-path commands (brightness, volume, launch app) printed results to the console or called `self.audio.speak()`, but did not always emit an authoritative `AGENT_RESPONSE` or structured `ASSISTANT_MESSAGE` payload containing `{ "task_id", "turn_id", "message_id", "type": "ASSISTANT_MESSAGE", "content", "status": "COMPLETED" }`.
  - In `live.js`, if streaming tokens arrived (`STREAM_TOKEN`), but `AGENT_RESPONSE` was missed, the stream bubble remained in `.streaming-active` with a blinking caret rather than settling into a completed assistant response.
- **Contract Solution**:
  - Implement a strict Assistant Response Event Contract:
    `USER_MESSAGE` ➔ `TASK_STARTED` ➔ `WORK_EVENTS` ➔ `STREAM_TOKEN` / `AGENT_RESPONSE` ➔ `TASK_COMPLETED` ➔ `ASSISTANT MESSAGE SETTLED`.
  - Every completed task produces an authoritative assistant response object. The frontend creates or updates the active message bubble and removes the streaming caret.

### 2.2 How Live Task State Is Currently Propagated
- **Current Flow**: `TASK_STARTED` sets `activeTaskId` and starts a local timer in `live.js`.
- **Defects**:
  - Live does not provide a compact task minimization overlay when a multi-step task runs. If long logs arrive, the conversation view gets cluttered.
  - The Live page lacked a clean, compact single current-step indicator (e.g. `CURRENT STEP: Searching the web...`, `CURRENT STEP: Opening Chrome...`).
- **Phase 5D.4 Design**:
  - Active execution renders a compact **Task In Progress Overlay** with single-line step indicator, progress bar, `[Expand Task]`, `[Stop Task]`, and `[View Workflow]`.
  - Conversation remains preserved and easily expandable.

### 2.3 How Workflow Currently Materializes Nodes & The Static/Dynamic Distinction
- **Current Defect**: `WorkflowView` in `workflow.js` previously fetched static graph data `/api/workflow` and pre-rendered all roles and all candidate models simultaneously in "RUNTIME" mode.
- **Phase 5D.4 Dynamic Execution Model**:
  - **WORKFLOW** starts minimal/empty on a pure black temporal canvas.
  - As runtime events arrive (`ACTIVATION_STARTED`, `TRANSCRIPTION_COMPLETED`, `TASK_STARTED`, `MODEL_SELECTED`, `TOOL_STARTED`, `SCREEN_CAPTURED`, `AGENT_RESPONSE`, `TTS_STARTED`, `TASK_COMPLETED`), nodes materialize in sequence:
    `STT` ➔ `Router` ➔ `Reasoning Model (e.g. GPT-OSS / Mistral)` ➔ `Tool / Web Search` ➔ `Results` ➔ `Verify` ➔ `TTS`.
  - Edges are created dynamically between materialized nodes.
  - When the task completes, energy settles smoothly.
  - When a task is cancelled, active plasma stops, energy retracts, and the active node collapses.
  - When a task fails or is broken, the connection fractures and particles scatter.

### 2.4 Luminous Plasma Execution Renderer
- **Visual Concept**:
  - High-energy luminous plasma channels replace dashed lines.
  - Multi-filament energy strands with bright central cores, soft bloom, and directional particle flow toward the downstream node.
  - Fallback ignition: If primary model fractures (`MODEL_FALLBACK` / `MODEL_RATE_LIMITED`), the primary node displays fracture/instability, the fallback branch ignites, and plasma flows to the fallback candidate.
  - Implemented via optimized Canvas / SVG rendering with hardware acceleration.

### 2.5 Separation of ARCHITECT Configuration Surface
- **Architect vs Workflow**:
  - `WORKFLOW`: Temporary runtime execution graph ("What is happening now?").
  - `ARCHITECT`: Persistent configuration graph ("How have I configured SERA to work?").
- **Architect Capabilities**:
  - 8 core roles: `STT`, `FAST`, `REASONING`, `DESKTOP`, `VISION`, `OCR`, `EMBEDDINGS`, `TTS` (extensible to `AGENTS`, `RAG`, `MCP`).
  - 3 execution modes per role: `PRIMARY ONLY`, `FALLBACK ORDER`, `CUSTOM`.
  - Decoupled dragging: Visual canvas dragging updates node positions; Semantic candidate dragging updates execution priority.
  - Unsaved changes dirty tracking (`[Discard]` / `[Save]`).
  - Pre-save Configuration Preview modal.
  - Safe simulation test run (`[Test Configuration]`).

### 2.6 Development Unrestricted Tool Mode (`SERA_DEV_UNRESTRICTED=true`)
- **Safety & Policy Gating**:
  - To allow automated and manual evaluation of actual agent capabilities without repetitive modal confirmation halts, provide `SERA_DEV_UNRESTRICTED=true`.
  - When active, `SecurityManager` allows registered safe tools (screen capture, web search, browser navigation, registered filesystem tools, desktop controls) without confirmation dialogs.
  - Security architecture is preserved; only registered SERA tools are permitted (no arbitrary shell injection).
  - UI displays a prominent amber indicator: `DEV MODE: UNRESTRICTED TOOLS`.

---

## 3. Implementation Blueprint

```
                                      +---------------------------------------------+
                                      |                 SERA UI 1.0                 |
                                      +---------------------------------------------+
                                                             |
                 +-------------------------------------------+------------------------------------------+
                 |                                           |                                          |
                 v                                           v                                          v
      +---------------------+                     +---------------------+                    +---------------------+
      |      (1) LIVE       |                     |    (2) WORKFLOW     |                    |    (3) ARCHITECT    |
      +---------------------+                     +---------------------+                    +---------------------+
      | - Human-facing chat |                     | - Temporal Theater  |                    | - System Config     |
      | - Compact Task HUD  |                     | - Dynamic Node Gen  |                    | - 3 Execution Modes |
      | - Inline Work Cards |                     | - Flowing Plasma    |                    | - Drag Reordering   |
      | - Guaranteed Settle |                     | - Pure Black Canvas |                    | - Save / Discard    |
      | - Context Actions   |                     | - Fracture/Fallback |                    | - Test Simulation   |
      +---------------------+                     +---------------------+                    +---------------------+
```
