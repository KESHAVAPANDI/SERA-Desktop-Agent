# SERA 1.0 — Phase 5D.5A: Screen Capture Diagnosis
## Root Cause Analysis for Screenshot Pipeline Failure

### 1. Why Screenshot Requests Entered Reasoning
- **Root Cause**: `LocalIntentRouter` (`app/core/intent.py`) only possessed regex detection for hardware controls (`brightness`, `volume`, `mute`, `unmute`).
- When a user commanded *"Take a screenshot"*, *"Take screen shot"*, *"Screenshot"*, or *"Capture my screen"*, `self.intent_router.detect(text)` returned `None`.
- `self.planner.is_multi_step_request(text)` returned `False` because it is a single action.
- `self.desktop_router.is_desktop_query(text)` looked for `"on my screen"`, `"what app"`, `"read my screen"` etc., but not screenshot capture commands.
- Consequently, execution fell completely through to **Route 4: Conversational Agent Reasoning** (`self.agent.run_stream(text)` / `self.agent.run()`), loading the full system prompt and invoking the large `reasoning` LLM router (`openai/gpt-oss-120b` or fallback) with tool schemas rather than executing local desktop screen capture directly.

### 2. Why `time` was Undefined
- **Root Cause**: In `app/ui/server.py`, the function `_get_dynamic_workflow_graph()` referenced `time.time()` while earlier refactoring iterations had localized imports or missed the global import at specific entry points.
- Furthermore, when the router encountered downstream provider connection or parsing issues during fallback iterations under error conditions, unhandled variable scopes surfaced as NameErrors rather than clean typed exceptions.

### 3. Why the Task Waited 30 Seconds
- **Root Cause**: In `app/core/agent.py`, `SERAAgent.run()` wrapped internal execution in `asyncio.wait_for(..., timeout=self.max_turn_timeout_seconds)` where `max_turn_timeout_seconds = 30.0`.
- When the large reasoning model request hung due to network latency, DNS resolution failure on remote provider endpoints, or unhandled router cascade loops, the runtime stalled until the 30-second timeout expired, transitioning the state to `BROKEN`.
- A simple local action that should take < 50ms was trapped waiting for remote LLMs.

### 4. Why the Assistant Response Path is Still Not Guaranteed
- **Root Cause**: In the standard agent loop (`app/core/agent.py`), when a tool was executed, `deterministic_actions` only formatted responses if the tool was called by the LLM function calling schema. If the LLM failed to produce tool calls or if the router timed out, no `AGENT_RESPONSE` or natural language settlement was emitted for the UI.
- In `runtime.py`, `process_text` lacked a dedicated, deterministic `SCREEN_CAPTURE_ONLY` and `SCREEN_CAPTURE_AND_ANALYZE` fast path that guarantees `SCREEN_CAPTURE_STARTED` $\to$ `SCREEN_CAPTURED` $\to$ `AGENT_RESPONSE` (status: `COMPLETED`) $\to$ `TASK_COMPLETED`.

### 5. Why Live Did Not Show the Result
- **Root Cause**:
  1. `SCREEN_CAPTURED` event was never broadcast because the tool execution never reached `capture_screen`.
  2. The inline work card and `.artifact-screenshot-box` in `live.js` rely on `SCREEN_CAPTURED` with valid `width`, `height`, and `image_path` (or data URI).
  3. Because the task timed out in `THINKING` state, the Live UI remained stuck on the thinking spinner without materializing the artifact card or updating the step to completion.

---

## Target Architectural Solution

```
User: "Take a screenshot"
STT -> Local Intent (SCREEN_CAPTURE_ONLY)
    -> capture_screen() (Verified local tool)
    -> Emit SCREEN_CAPTURE_STARTED, SCREEN_CAPTURED, AGENT_RESPONSE ("Screenshot captured."), TASK_COMPLETED
    -> 0 LLM Reasoning Calls, 0 Vision Calls
    -> Latency < 50ms

User: "What is on my screen?"
STT -> Local Intent (SCREEN_CAPTURE_AND_ANALYZE)
    -> capture_screen() (Verified local tool)
    -> Vision Model (1 request to vision role)
    -> Emit VISION_STARTED, VISION_COMPLETED, AGENT_RESPONSE (Analysis), TASK_COMPLETED
    -> 0 LLM Reasoning Calls, 1 Vision Call
```
