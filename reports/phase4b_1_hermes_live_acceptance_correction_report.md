# PHASE 4B.1 — HERMES LIVE ACCEPTANCE CORRECTION & EXECUTION CONTROL REPORT

**Author:** Antigravity (Google DeepMind) & Keshava Pandi A S  
**Date:** September 29, 2026  
**Repository:** `KESHAVAPANDI/SERA-Desktop-Agent`  
**Branch:** `feature/phase4b_1-hermes-live-acceptance-correction`  
**Starting SHA:** `a7838044bd78fc4e38456f5001336fc741553b2a`  
**Ending SHA:** `e2cb771`  
**Official Hermes Runtime:** `C:\Users\kesha\AppData\Local\hermes\bin\hermes.exe` (`v0.21.5+2858.gb7d0620`)  
**LLM Model & Provider:** `openrouter` / `meta-llama/llama-3.3-70b-instruct`  
**Integration Mode:** `HERMES_EXPERIMENTAL` (`hermes_exp`) (with `CURRENT` and `HERMES_SHADOW` intact)  

---

## 1. Executive Summary

Phase 4B.1 was initiated after manual live testing of Phase 4B revealed execution and orchestration discrepancies between the official Nous Research Hermes Agent runtime and SERA's runtime control loop. 

### Permanent Architectural Invariant
> **"Hermes decides what should happen. SERA decides whether it is allowed, what real entity it refers to, how it is executed, what actually happened, whether it is verified, and when the task is actually finished."**

SERA does **not** reimplement Hermes, simulate reasoning, or fake agent output. The official Nous Research Hermes binary remains the sole cognitive engine. Phase 4B.1 enforces strict SERA authority over tool contracts, entity normalization, approval state machines, objective satisfaction policies, and runtime truthfulness.

---

## 2. Root Cause Analysis & Corrections

### Finding A: Ambiguous Referents vs. Provider Error Masking
* **Symptom:** When OpenRouter token limits or network failures occurred (HTTP 402), unparseable output was misclassified as requiring user clarification, masking provider failures as interactive prompts.
* **Root Cause:** In `bridge.py`, JSON parse failures defaulted to `needs_clarification = True`.
* **Correction:** 
  1. Distinguish fatal provider/network errors (`finish_reason="error"`, `needs_clarification=False`) from linguistic ambiguity.
  2. Grounded referent validation: Ambiguous pronouns ("that", "it", "this", "that window") without prior context in `ContextStore` correctly transition to `ExecutionHandoffStatus.WAITING_FOR_CLARIFICATION` (`MISSING_CONTEXT_REFERENT`) with zero substrate tool calls.
  3. Preserved `AMBIGUOUS_TARGET` (failure) for empty payloads and `UNRESOLVED_ENTITY` (failure) for missing ordinals.

### Finding B: Destructive Action Pause & Programmatic Approval State Machine
* **Symptom:** Destructive actions paused for approval, but there was no robust programmatic resumption mechanism that executed the paused step exactly once and prevented double execution.
* **Root Cause:** Coordinator lacked a stateful approval lifecycle manager.
* **Correction:** 
  1. Added `ExecutionHandoffStatus.WAITING_FOR_APPROVAL` to `schema.py`.
  2. Implemented `HermesExecutionCoordinator.resolve_approval(request_id, decision)` supporting `APPROVE`, `DENY`, `CANCEL`, and `EXPIRE`.
  3. On `APPROVE`: The paused step is executed exactly once, verified with empirical evidence, logged into step history, and evaluated against the user objective.
  4. Exposed `/api/approval/pending`, `/api/approval/resolve`, and WebSocket `RESOLVE_APPROVAL` in `app/ui/server.py`.

### Finding C: Runaway Multi-Turn Continuation Loops
* **Symptom:** For tasks like "Search YouTube for Python tutorials and open the first result", Hermes would repeatedly propose opening result 2, result 3, and result 4 indefinitely.
* **Root Cause:** The coordinator continuation condition relied solely on `plan.is_complete is False`. Hermes would continuously plan new actions because it lacked completion awareness.
* **Correction:**
  1. Implemented `is_objective_satisfied(original_objective, step_history, context_store)` in `app/adapters/hermes/coordinator.py`.
  2. Pure searches halt immediately once search results are verified in `ContextStore`.
  3. "Open first result" commands halt immediately after exactly 1 result tab has been opened and verified.
  4. Added `NO_PROGRESS_LOOP_DETECTED` to catch and terminate circular proposals without progress.

### Findings D & E: Capability Contract & Action Alias Mismatch
* **Symptom:** Hermes generated canonical actions such as `browser_switch_tab` and `browser_close_tab`, while SERA tools registered `focus_browser_tab` and `close_browser_tab`.
* **Root Cause:** Tool advertisement in `bridge.py` lacked a single canonical capability source of truth, causing tool naming mismatches.
* **Correction:**
  1. Created `app/adapters/hermes/capabilities.py` defining `CANONICAL_CAPABILITIES`, `CANONICAL_ACTION_MAP`, and `resolve_canonical_action()`.
  2. Unified capability definitions, schema parameters, target types, and expected verification evidence.
  3. Updated `HermesPlanValidator` in `validator.py` to transparently normalize aliases (`browser_switch_tab -> focus_browser_tab`, `browser_close_tab -> close_browser_tab`, `bring_window_forward -> focus_desktop_window`).
  4. Fixed `_parse_steps` in `bridge.py` so `close_browser_tab` is classified as a non-destructive tab operation rather than an application-level kill.

### Finding F: Window Focus Deep UIA Hang & Entity Preservation
* **Symptom:** `_focus_window` hung scanning deep UIA control trees and occasionally converted windows to tabs.
* **Root Cause:** `_focus_window` attempted recursive UI automation control scans before checking top-level HWNDs.
* **Correction:**
  1. Replaced deep scans with fast `get_all_windows_summary()` lookup and bounded 1.0s Win32 `SetForegroundWindow` verification.
  2. Ensured target taxonomy strictly preserves `TargetType.WINDOW` (never silently converted to `TAB`).

### Finding G: Startup Mode Consistency & Truthful UI Exposure
* **Symptom:** Inconsistent mode resolution between launcher, command pipeline, and web server.
* **Root Cause:** Ad-hoc environment variable inspection across modules.
* **Correction:**
  1. Added canonical `resolve_hermes_mode()` in `app/adapters/hermes/schema.py`.
  2. Standardized mode resolution in `sera.py`, `app/core/command_pipeline.py`, and `app/ui/server.py`.
  3. Exposed truthful `authority_architecture` and Hermes model telemetry in UI status endpoints.

---

## 3. Test Evidence & Acceptance Matrix

All tests have been run and verified. Test classifications:
- **`[UNIT]`**: Fast, isolated contract and logic validation.
- **`[SIMULATED INTEGRATION]`**: Multi-turn mock execution of the coordinator, approval lifecycle, and loop detection.
- **`[REAL HERMES]`**: Subprocess execution against official `hermes.exe` (`v0.21.5`).
- **`[REAL WORLD VERIFIED]`**: Empirical Win32 OS and browser session verification.

### Test Results Summary

| Test Suite | Tests | Result | Classification |
| :--- | :--- | :--- | :--- |
| `tests/hermes/test_hermes_phase4b1_corrections.py` | 14 | **14 / 14 PASS** | `[UNIT + SIMULATED INTEGRATION]` |
| `tests/hermes/test_hermes_execution_coordinator.py` | 13 | **13 / 13 PASS** | `[SIMULATED INTEGRATION]` |
| `tests/hermes/test_hermes_bridge.py` | 8 | **8 / 8 PASS** | `[REAL HERMES + UNIT]` |
| `tests/hermes/test_hermes_mcp_and_skills.py` | 4 | **4 / 4 PASS** | `[UNIT + CONTRACT]` |
| `tests/test_phase3a_g_architectural_stabilization.py`| 10 | **10 / 10 PASS**| `[REAL WORLD VERIFIED]` |
| `tests/test_semantic_authority_gate.py` | 24 | **24 / 24 PASS**| `[UNIT + SIMULATED INTEGRATION]` |
| `tests/test_hotkey_authority.py` | 3 | **3 / 3 PASS** | `[REAL WORLD VERIFIED]` |
| **Total Test Count** | **76** | **76 / 76 PASS (100%)** | |

### Specific Acceptance Scenarios Validated

1. **Category A: Ambiguous Referents Without Context:**
   - Input: `"open that"` with empty context.
   - Status: `ExecutionHandoffStatus.WAITING_FOR_CLARIFICATION`, zero substrate tools executed.
2. **Category B: Destructive Action Pause & Single Execution:**
   - Input: `"close notepad"`.
   - Action paused for approval -> programmatic `APPROVE` -> executed exactly once, verified with empirical evidence.
3. **Category C: Destructive Action Denial / Cancel / Expire:**
   - Input: `"close notepad"` -> `DENY` / `CANCEL` / `EXPIRE`.
   - Verified that zero destructive actions occurred; clean terminal state reached.
4. **Category D: Search + Open First Result (Continuation Boundary):**
   - Input: `"Search YouTube for Python tutorials and open the first result"`.
   - Coordinator executes search, opens exactly 1 result tab, and halts continuation immediately (`is_objective_satisfied = True`).
5. **Category E: Pure Search (No Unsolicited Open):**
   - Input: `"Search Google for quantum computing news"`.
   - Coordinator executes search, registers results in `ContextStore`, and halts without opening any results.
6. **Category F: Browser Tab Switching Alias:**
   - Action: `browser_switch_tab` normalized to `focus_browser_tab`, executed and verified.
7. **Category G: Browser Tab Closing Alias:**
   - Action: `browser_close_tab` normalized to `close_browser_tab`, executed and verified.
8. **Category H: Desktop Window Focus:**
   - Action: `bring_window_forward` targeting `Notepad` focuses window, retains `TargetType.WINDOW`.
9. **Category I: Execution Cancellation:**
   - Mid-turn cancellation event halts execution coordinator immediately.
10. **Category J: Unsupported Capabilities:**
    - Unsupported actions rejected deterministically without infinite retry loops.
11. **Category K: Loop Detection:**
    - Repeating identical proposals without state progress triggers `NO_PROGRESS_LOOP_DETECTED`.
12. **Category L: Startup Mode Consistency:**
    - Canonical `resolve_hermes_mode()` returns consistent `HermesMode.HERMES_EXPERIMENTAL` across launcher, server, and runtime.

---

## 4. Architectural Boundaries Maintained

* **Zero Fake Hermes:** All real cognitive work originates from the official `hermes.exe` binary.
* **Deterministic Ownership:** SERA remains the sole execution engine, security gate, and state verifier.
* **Safe Isolation:** `HERMES_EXPERIMENTAL` remains opt-in via `.env` (`SERA_HERMES_MODE=hermes_exp`), preserving `CURRENT` and `HERMES_SHADOW` modes.
* **No Premature Promotion:** Hermes is not promoted out of experimental mode in this phase.
* **No Scope Creep:** No Phase 5 messaging, Honcho adapters, or visual redesigns were introduced.

---

## 5. Conclusion & Next Steps

Phase 4B.1 delivers an architecturally sound, thoroughly tested control loop between the official Nous Research Hermes runtime and SERA. The platform is ready for manual live user testing.
