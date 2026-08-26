# SERA 1.0 — PHASE 5D.3 LIVE EXPERIENCE DIAGNOSIS
**Deep Architecture, Event Flow & State Synchronization Assessment**

---

## 1. Current Live Architecture

The current Live View implementation (`app/ui/static/js/views/live.js` and `app/ui/static/index.html`) consists of:
- **Left Column**: Central Aura Orb, Hold-To-Talk countdown track, Authoritative Task Execution Card, and hardcoded quick action buttons.
- **Center Column**: Text chat feed (`#chat-stream`) and basic input form (`#chat-form`).
- **Right Column (Defect)**: Telemetry cards (Activity Rail, Provider Health Matrix, Memory Core Cache) which duplicate information belonging to `PROVIDERS` and `MEMORY` dedicated tabs, consuming 340px of screen real estate that should belong to conversational work streams.
- **Viewport Layout**: 3-column layout where the conversation feed is constrained and does not support inline progressive work rendering.

---

## 2. Current Event Flow

1. **User Action**:
   - Voice: `Ctrl+Space` triggers Windows OS hotkey ➔ `ACTIVATION_STARTED` ➔ `ACTIVATION_RELEASED` ➔ `TRANSCRIPTION_STARTED` ➔ `TRANSCRIPTION_COMPLETED`
   - Text: Typing prompt ➔ WebSocket `USER_PROMPT` action ➔ `runtime.start_canonical_task()`
2. **Backend Execution**:
   - `runtime.py` creates an `asyncio.Task`, records `self.active_task_info`, and emits:
     - `TASK_STARTED` (`task_id`, `user_input`, `started_at`)
     - `MODEL_SELECTED` (`role`, `provider`, `model`)
     - `TOOL_STARTED` / `TOOL_COMPLETED`
     - `AGENT_RESPONSE`
     - `TASK_COMPLETED` / `TASK_CANCELLED` / `TASK_FAILED`
3. **Frontend Routing (`app.js`)**:
   - Events are received over WebSocket, passed to `live.js`, `workflow.js`, `debug.js`.
   - **Critical Flow Defect**: In `app.js`, `TASK_STARTED`, `TOOL_STARTED`, and `SCREEN_CAPTURE_STARTED` contain `this.switchView("workflow")`, which forcibly kicks the user out of the Live view into the Workflow graph during task execution instead of rendering the work in-place.

---

## 3. Current Task State Flow

- `runtime.py` generates canonical `task_id` (`task_<timestamp>`) and maintains `active_task_info`.
- `TASK_STARTED` emits `task_id`, `user_input`, and `started_at`.
- `live.js` tracks `this.activeTaskId` and `this.startedAt`.
- **Gaps Identified**:
  - No `turn_id` or `work_item_id` tracking inside the conversation stream.
  - Stale events from an old task can overwrite UI state if a new task begins immediately after cancellation.
  - No streaming token buffer for real-time model text chunks.

---

## 4. Current Interrupt Flow

- **Flow**: User clicks `#btn-interrupt-task` ➔ sends WebSocket `INTERRUPT` + `POST /api/task/cancel` ➔ `runtime.cancel_task()` cancels active `asyncio.Task` and stops audio ➔ emits `TASK_CANCELLED`.
- **Gaps Identified**:
  - Button state is static (`Interrupt`) rather than context-aware (`CANCEL CAPTURE` during listening, `INTERRUPT` during thinking, `STOP TASK` during tool execution, `STOP SPEAKING` during TTS).
  - Button remains visible even when no task is active.
  - No inline cancellation notice in the conversation stream itself.

---

## 5. Current Capability Implementation

- **Current State**: Hardcoded HTML buttons in `index.html` with fixed attributes (`data-prompt="Take a screenshot..."`).
- **Gaps Identified**:
  - No backend `CapabilityRegistry`.
  - No context-awareness (e.g. suggesting "Analyze Screen" only after a capture, or "Read Page" when a browser is open).
  - No dynamic capability discovery or permission checking.

---

## 6. Current Conversation Rendering

- **Current State**: Static `appendMessage("user" | "sera", text)` that creates a single `<div>` with text.
- **Gaps Identified**:
  - No structured message types (`USER_MESSAGE`, `ASSISTANT_MESSAGE`, `THINKING`, `TOOL_ACTIVITY`, `WEB_SEARCH`, `SCREEN_CAPTURE`, `VISION_ANALYSIS`, `FILE_COLLECTION`, `SOURCE_COLLECTION`, `PROGRESS`, `CONFIRMATION`, `BROKEN`, `CANCELLED`).
  - No inline collapsible work cards or artifact previews (thumbnails, files, web result links).
  - No streaming token reveal animation.
  - No smart auto-scroll anchoring (breaks when user scrolls up to inspect history).

---

## 7. Current Workflow Synchronization

- **Current State**: Workflow and Live receive the same WebSocket events, but Workflow renders dynamic graph nodes while Live only updates a tiny 4-step progress bar on the task card.
- **Gaps Identified**:
  - Lack of a clean `[ View Workflow ]` button in Live that focuses Workflow on the active `task_id`.
  - Lack of workflow state preservation when returning to Live.

---

## 8. Exact Changes Required for Phase 5D.3

1. **Remove Right-Side Telemetry from Live View**:
   - Remove permanent Provider Health Matrix and Memory Cache from `index.html`.
   - Expand Live layout to 2-column: Left Voice & Aura Cockpit (`340px`), Right Full-Width Conversational Work Stream (`1fr`).
2. **Implement Unified Conversation Data & Event Stream (`live.js`)**:
   - Create class-based modular message/card architecture:
     - `UserMessageCard` (with input source: Voice `🎙` / Text `⌨`).
     - `AssistantMessageCard` (with real streaming token buffer, temporal glow cursor).
     - `InlineWorkCard` (supporting states `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `BROKEN`, `CANCELLED` and collapsible details).
     - `ArtifactCard` (`WEB_RESULT`, `SCREENSHOT`, `FILE`, `SOURCE_COLLECTION`, `VISION_RESULT`).
     - `SystemNoticeCard` (`TASK_CANCELLED`, `INITIALIZING`, `DISCONNECTED`).
3. **Backend Contextual Capability Registry (`app/core/capabilities.py` & `app/ui/server.py`)**:
   - Create `CapabilityRegistry` with metadata (`id`, `label`, `icon`, `category`, `tool_name`, `risk_level`, `required_permissions`, `show_when`, `priority`).
   - Add endpoint `GET /api/capabilities?context=<state>` returning prioritized contextual actions.
4. **Context-Aware Authoritative Interrupt UX**:
   - Dynamic button states: `CANCEL CAPTURE` (listening) | `INTERRUPT` (thinking) | `STOP TASK` (executing) | `STOP SPEAKING` (TTS) | Hidden/Disabled (idle).
   - Instant visual response with inline `Task cancelled by user` stream record.
5. **Eliminate Forced Auto-Navigation**:
   - Stop `app.js` from auto-switching views on `TASK_STARTED` / `TOOL_STARTED`.
   - Provide contextual `[ View in Workflow ➔ ]` links on complex inline work cards.
6. **Smart Scroll Anchoring**:
   - Detect user scroll position; auto-scroll only if anchored to bottom, otherwise show floating `[ New Activity ↓ ]` pill.
7. **Comprehensive E2E Headed Suite (`tests/e2e/phase5d3/`)**:
   - Create 5 new headed E2E test files validating artifacts, interrupt, capabilities, sync, and streaming.
