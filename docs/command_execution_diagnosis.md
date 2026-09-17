# SERA Command Execution Pipeline — Root Cause Diagnosis

## Executive Summary
Simple desktop commands (e.g., *"repeat the last task"*, *"what time is it"*, *"open Chrome"*, *"lock my PC"*) frequently hung for hundreds of seconds, invoked heavy cloud LLM reasoning models unnecessarily, or produced unverified/duplicate responses. This diagnosis details the 5 root causes identified across the intent classifier, agent, runtime, router, and context tracking layers.

---

## 1. Why Simple Commands Remain Stuck For Minutes
- **Narrow Local Router**: `LocalIntentRouter` (`app/core/intent.py`) only checked 6 rigid regexes (screen capture, brightness, volume, mute, YouTube). Common desktop, system, file, power, and context commands returned `None`.
- **Unbounded Streaming LLM Loop**: When local intent returned `None`, execution fell through to `runtime.process_text()` Route 4 $\to$ `agent.run_stream()` $\to$ `router.generate_stream_with_fallback()`. 
- **Missing Per-Call Timeouts**: Streaming calls and provider generation in `agent.run_stream()` lacked strict timeouts. When cloud API endpoints (Groq, Cerebras, Mistral) hung, throttled, or suffered network socket stalls, the task remained perpetually in `"Initializing task routing..."` without ever terminating.

---

## 2. Why Commands Invoke Unnecessary Models
- **Lack of Multi-Tier Command Interpretation**: The system lacked a lightweight, structured deterministic command extractor (Layer 1 deterministic $\to$ Layer 2 structured intent $\to$ Layer 3 LLM only for genuinely ambiguous requests).
- **Defaulting to Reasoning**: Unmatched commands immediately triggered `select_role_for_task()`, which routed everyday commands like *"open Chrome"*, *"what time is it"*, and *"lock PC"* to cloud reasoning models with full tool JSON schemas.

---

## 3. Why Tasks Produce Duplicate or False Completion
- **Multiple Response Event Dispatchers**: `runtime.py`, `agent.py`, and `task_executor.py` independently emitted `STREAM_COMPLETE`, `AGENT_RESPONSE`, and `TASK_COMPLETED` on the same turn.
- **Unverified Tool Success**: Tools returned `success=True` immediately upon launching a subprocess (e.g., `os.startfile` or `subprocess.Popen`) without post-action verification (e.g., checking if the process, window, or file actually existed).

---

## 4. Why Context Commands ("Repeat Last Task", "Close It") Are Unreliable
- **Zero Local Context Resolution**: Phrases like *"repeat the last task"*, *"do it again"*, *"close it"*, and *"open it"* had no deterministic handler.
- **Unresolved Pronouns Sent to LLM**: Contextual utterances were passed verbatim to cloud LLMs without resolved entities (e.g. resolving *"it"* to the active app or cloning the previous successful command object).

---

## 5. Why Final Responses Sometimes Only Appear in Terminal
- **Decoupled Terminal Logging vs WebSocket Events**: Direct tool handlers printed results to `stdout` (`print(f"[RESULT] {tool_res}")`) but occasionally failed to emit standardized `AGENT_RESPONSE` payloads to the WebSocket gateway before resetting runtime status to `IDLE`.
- **Inconsistent Event Payloads**: UI clients expected a uniform `{ task_id, content, status }` payload for assistant message settlement.

---

## Core Architecture Overhaul Plan
1. **Canonical Command Object & Parser (`app/core/command.py`)**:
   - Normalize every user request into `{ command_id, task_id, intent, entities, parameters, required_tools, complexity, execution_plan }`.
   - Comprehensive categories: `SYSTEM`, `APPLICATIONS`, `FILES`, `BROWSER`, `SCREEN`, `WINDOW`, `POWER`, `CONVERSATION`, `CONTEXT` (repeat last task, close it, cancel), `COMPOUND`.
2. **Deterministic Layer 1 & 2 Fast-Path Engine**:
   - Zero LLM invocation for deterministic single and compound actions.
   - Strict step timeouts (5s OS, 10s browser, 15s web, 20s vision) and total task timeouts (10s simple, 30s normal, 60s complex).
3. **Contextual Command Memory**:
   - Track last normalized command object and plan.
   - Deterministically clone and re-execute on *"repeat the last task"*.
4. **Post-Action Verification & Single Response Contract**:
   - Verify process/window/file/URL.
   - Emit exactly one authoritative `AGENT_RESPONSE` to UI + terminal.
