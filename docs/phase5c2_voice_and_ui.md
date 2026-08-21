# SERA 1.0 — Phase 5C.2 Architecture: Hold-To-Talk Voice Control, Wake Word, and Truthful Execution

## 1. Executive Summary
Phase 5C.2 introduces a precision **Hold-to-Talk Voice Interaction Subsystem**, a zero-cloud local **"SERA" Wake Word Detector**, **Strict Truthfulness in Computer Actions**, and **God-Tier Reactive Temporal UI Dynamics**.

---

## 2. Core Architecture Subsystems

### 2.1 Hold-to-Talk Global Keyboard Subsystem
- **Hotkey:** `Ctrl+Space`.
- **Mechanism:** Global asynchronous polling loop using Windows `GetAsyncKeyState` checking both Control (`VK_CONTROL`, `VK_LCONTROL`, `VK_RCONTROL`) and Space (`VK_SPACE`) key states.
- **Key Down (`on_press`):**
  - Immediately transitions state to `LISTENING`.
  - Plays the reactive listening audio cue.
  - Broadcasts `ACTIVATION_STARTED` (`mode: HOLD_TO_TALK`) and `LISTENING_STARTED` events to the WebSocket Gateway.
  - Pauses local wake word listener to yield audio device ownership.
  - Begins dynamic audio buffer capture via `AudioRecorder.start_recording()`.
- **Key Up (`on_release`):**
  - Stops audio capture via `AudioRecorder.stop_recording()`.
  - Broadcasts `ACTIVATION_RELEASED` (with exact duration) and `LISTENING_STOPPED`.
  - Immediately begins STT transcription and agent dispatch.

### 2.2 Local Wake Word Subsystem
- **Trigger:** Acoustic phrase `"SERA"`.
- **Lifecycle:**
  - `IDLE`: Listens continuously in non-blocking background thread.
  - On trigger: Emits `WAKE_WORD_DETECTED`, pauses detector stream, captures fixed 5.0 seconds of audio via `AudioRecorder.record_for(5.0)`, and transcribes.
  - Turn completion: Resumes wake word detection.

### 2.3 Computer Action Truthfulness
Tool execution explicitly validates OS operations rather than inferring success from subprocess startup:
1. **Application Launch (`open_application`):** Resolves executable path in `PATH` or standard Windows directories (`Program Files`, `AppData`, `System32`), launches, and verifies process/window presence. If not found, returns `{"success": False, "verified": False, "error": "Application 'name' could not be found."}`.
2. **Folder Launch (`open_folder`):** Resolves named standard directories (`Downloads`, `Documents`, `Desktop`, `Pictures`, or absolute paths), checks `os.path.isdir()`, and opens in Windows Explorer.
3. **File Launch (`open_file`):** Checks `os.path.isfile()`, launches with default registered handler.
4. **Web Search (`web_search`):** Executes real DuckDuckGo structured search queries and returns top snippets.
5. **Screen Capture (`capture_screen`):** Captures high-resolution desktop frame (1920x1200) via UIAutomation root capture / GDI, stores image in scratch directory, and verifies dimensions.

---

## 3. UI/UX & Temporal Aura Integration
- **Live View:**
  - Real-time Hold-To-Talk visualizer with dynamic elapsed stopwatch (`00:01.24`) and animated cyan breathing aura.
  - 5.0s countdown radial for wake word activations.
  - Real-time Live Activity Rail displaying structured timestamped event telemetry.
- **Workflow View:**
  - 3-Layer Temporal Canvas with background animated energy strands, interactive 2D node graph (pan, zoom, snap, fit, reset), and live WebSocket execution pulses.
- **Agent Studio:**
  - Identity avatars for all 6 agents (SERA Core, Desktop, Vision, Research, RAG, MCP) with active vs planned badges and animated delegation lines.
