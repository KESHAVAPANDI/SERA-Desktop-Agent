# SERA 1.0 — Phase 5D Architecture Review

## 1. System Inventory & Analysis

### 1.1 Voice & Activation Subsystem
- **Current Status:**
  - `GlobalHotkeyManager` provides Windows `GetAsyncKeyState` polling loop for `Ctrl+Space` KeyDown / KeyUp.
  - `AudioRecorder` provides dynamic `start_recording()` and `stop_recording()` buffer capture alongside `record_for(5.0)`.
  - Previous wake-word detection relied on unconfigured local models and could return ambiguous health statuses.
- **Phase 5D Target:**
  - Pluggable `app/speech/wakeword/` provider architecture (`WakeWordProvider`, `LocalCustomWakeWordProvider`).
  - Truthful `NOT CONFIGURED` status when model weights (`models/wakeword/hey_sera.tflite`) are not present.
  - Strict microphone ownership controller ensuring zero concurrent audio stream collisions.

### 1.2 Runtime & Execution Engine
- **Current Status:**
  - `SERARuntime` drives state transitions (`IDLE`, `LISTENING`, `TRANSCRIBING`, `THINKING`, `EXECUTING`, `SPEAKING`).
  - Single-step fast paths exist for simple conversational greetings (`hi`, `hello`).
  - Tools are executed with bounded rounds (max 10 steps, 30s timeout).
- **Phase 5D Target:**
  - Duplicate tool protection: within a turn, `(turn_id, tool_name, normalized_args)` execution is deduplicated unless explicit recovery is initiated.
  - Automatic view navigation: initiating complex tasks dispatches an event/signal to smoothly navigate the UI from Live to Workflow.

### 1.3 Computer Action, Web, and Screen Perception Tools
- **Current Status:**
  - `OpenApplicationTool`, `OpenFolderTool`, `OpenFileTool` verify paths before returning `success=True`.
  - `WebSearchTool` queries DuckDuckGo for live structured search snippets.
  - `ScreenCaptureTool` uses native Windows UIAutomation for desktop captures (1920x1200).
- **Phase 5D Target:**
  - Enforce resource semantic distinction (Application vs Website vs Folder vs File).
  - Vision analysis only runs after a valid, verified screen capture reference is generated.

### 1.4 Temporal Aura Visualization & Graph Architecture
- **Current Status:**
  - Canvas in `app/ui/static/js/views/workflow.js` renders a horizontal candidate graph with pan and zoom.
- **Phase 5D Target:**
  - Formalize data-driven schema `workflow.graph.json` with nodes, edges, roles, and execution metadata.
  - Decouple visual $(x, y)$ spatial coordinates from semantic candidate execution order.
  - 3-Layer motion engine: Layer 1 Background Field, Layer 2 2D Graph / Temporal Corridor, Layer 3 Event-driven Runtime Energy.
  - 8-color semantic system for input, routing, reasoning, vision, desktop, verification, agents, and output.

### 1.5 Domain Views (Agents, Memory, History, Providers, Debug, Security)
- **Agent Studio:** Rich animated character identities (SERA Core, Desktop, Vision, Research, RAG, MCP) with `● ACTIVE` vs `◌ PLANNED` badges, animated data packet delegation, and Agent Inspector.
- **Memory Core:** Genuine knowledge storage; display pristine "Neural Knowledge Core — No knowledge indexed yet" empty state rather than fabricated records.
- **History Archive:** Compact execution timeline with Replay Visualization (no execution) vs Run Again (real execution).
- **Provider Control Plane:** Complete registry of all 8 providers (Groq, Gemini, Mistral, NVIDIA, Fish Audio, OpenRouter, Cerebras, Z.AI), model-level health telemetry, dynamic quotas, and provider onboarding drawer.
- **Debug & Security Console:** Structured event cards with search/filters, raw JSON drawer, and interactive security policy controls.
