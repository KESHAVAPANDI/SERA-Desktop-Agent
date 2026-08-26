# SERA 1.0 — Phase 5D.2 Root Cause Analysis & Architecture Diagnosis
**Document Version:** 1.0  
**Date:** 2026-08-25  
**Scope:** Runtime/UI Synchronization, Global Hotkey Event Flow, Task Model & Cancellation, Security Manager Policies, Two-Mode Workflow Graph.

---

## 1. Executive Summary & Root Cause Findings

Manual inspection and live desktop testing revealed 6 root-cause architectural issues in the previous Phase 5D.1 implementation:

### 1. `capture_screen`, `browser_open`, `web_search` Rejected by `SecurityManager`
- **Location:** `app/utils/security.py` lines 16–59 (`self.safe_tools`).
- **Cause:** `self.safe_tools` did not include `capture_screen`, `screen_reading`, `browser_open`, `browser_search`, `browser_read`, `browser_click`, `browser_type`, `browser_scroll`, `browser_close`, `web_search`, `open_folder`, `open_file`, or `list_folder_contents`.
- **Result:** `SecurityManager.check()` returned `allowed=False` with error `"Tool '<tool_name>' is not approved by the security policy."`
- **Resolution:** Add `SCREEN_CAPTURE`, `BROWSER_CONTROL`, `WEB_SEARCH`, and file read tools to `self.safe_tools` (with destructive operations remaining in `self.confirmation_tools`).

### 2. Global Hotkey Activation Events Dropped by UI Gateway
- **Location:** `app/ui/server.py` lines 112–128 (`_setup_event_listeners`).
- **Cause:** The event list subscribed by `SERAUIServer` only included model/tool events, but omitted `ACTIVATION_STARTED`, `ACTIVATION_RELEASED`, `WAKE_WORD_DETECTED`, `TRANSCRIPTION_STARTED`, `TRANSCRIPTION_COMPLETED`, `AGENT_RESPONSE`, `SCREEN_CAPTURE_STARTED`, `SCREEN_CAPTURED`, and `TASK_STARTED`.
- **Result:** When the user pressed `Ctrl+Space` in Windows, Python logged `[ACTIVATION HOTKEY_HOLD]` in the console, but the browser UI never received the WebSocket notification to switch to `LISTENING`.
- **Resolution:** Bridge all `EventBus` events to WebSocket broadcast, ensuring thread-safe scheduling onto the server event loop.

### 3. Text Prompt Live Execution Divergence & Fake Timers
- **Location:** `app/ui/server.py` line 283 (`USER_PROMPT`) and `app/ui/static/js/views/live.js` line 48 (`this.startTask()`).
- **Cause:** 
  1. `USER_PROMPT` called `self.runtime.agent.run()` directly without creating a canonical `Task` instance or managing task lifecycle.
  2. `live.js` started a local fake client-side interval `this.taskTimerInterval = setInterval(...)` and hardcoded `Step 1 / 4` without server-driven progress events.
- **Result:** The UI remained stuck on "Step 1" with an infinite client timer, while the backend agent executed independently in the terminal.
- **Resolution:** Implement a canonical backend task model with `task_id`, `started_at`, `status`, `current_step`, `total_steps`, and `current_node`. Expose `GET /api/task/{task_id}`, `POST /api/task/{task_id}/cancel`, and `GET /api/tasks/active`. Make `LiveView` a thin client consuming server-sent timestamps.

### 4. Fake / Ineffective Interrupt Button
- **Location:** `app/ui/server.py` lines 287–292 (`INTERRUPT`).
- **Cause:** When the user clicked "Interrupt", the server merely interrupted audio playback and transitioned state to `CANCELLED`, but never cancelled the underlying `asyncio.Task` running the agent/tool execution.
- **Result:** The agent kept running background tools (e.g. Chrome, PowerShell) despite the user clicking interrupt.
- **Resolution:** Maintain active `asyncio.Task` reference for the current `task_id` and explicitly invoke `active_task.cancel()` on `POST /api/task/{task_id}/cancel`, broadcasting `TASK_CANCELLED`.

### 5. Workflow Graph Mode Mixing (Need for Execution vs Design Split)
- **Location:** `app/ui/static/js/views/workflow.js`.
- **Cause:** The workflow canvas attempted to render all 19 static model candidates before any task started, rather than materializing the live execution trace dynamically.
- **Resolution:** Architect TWO dedicated modes:
  - **Execution Mode (`[EXECUTION]`):** Dynamically materializes nodes chronologically as real runtime events occur (`STT` -> `Router` -> `Model` -> `Tool` -> `Verification` -> `TTS`). On completion, displays `TASK COMPLETED` and a clear `[RETURN TO LIVE]` button.
  - **Design Mode (`[DESIGN]`):** Persistent full model topology for role inspection, candidate priority reordering, and fallback mode configuration with independent spatial layout persistence.

### 6. Navigation Complexity
- **Location:** `app/ui/static/index.html` header tabs.
- **Cause:** 8 equal-weight tabs created visual noise.
- **Resolution:** Simplify navbar into Primary (`LIVE`, `WORKFLOW`, `AGENTS`, `PROVIDERS`) and Secondary dropdown (`MORE ▾` -> `Memory`, `History`, `Debug`, `Security`), while retaining persistent right-side telemetry.

---

## 2. Implementation Action Plan

1. **`app/utils/security.py`**: Add `capture_screen`, `screen_reading`, `web_search`, `browser_*`, `open_folder`, `open_file` to `self.safe_tools`.
2. **`app/core/runtime.py`**: Add canonical task manager, `process_text_turn(prompt)` returning `task_id`, and `cancel_active_task()`.
3. **`app/ui/server.py`**:
   - Subscribe all events (`ACTIVATION_*`, `WAKE_*`, `TRANSCRIPTION_*`, `SCREEN_*`, `TASK_*`).
   - Add task endpoints: `POST /api/task/create`, `POST /api/task/{task_id}/cancel`, `GET /api/task/{task_id}`, `GET /api/tasks/active`.
4. **`app/ui/static/js/views/live.js`**: Rebuild `LiveView` as a thin client receiving backend timestamps and canonical task steps, with real interrupt button.
5. **`app/ui/static/js/views/workflow.js`**: Implement Execution View (chronological node materialization) and Design View (persistent architecture).
6. **`app/ui/static/index.html` & CSS**: Implement simplified navbar (`MORE ▾` dropdown) and `[RETURN TO LIVE]` button.
7. **E2E Suite (`tests/e2e/phase5d2/`)**: Implement full headed Playwright + desktop automation test suite.
