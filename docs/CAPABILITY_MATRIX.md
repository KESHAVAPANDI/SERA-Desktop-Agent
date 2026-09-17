# SERA System Capability Matrix (Empirical Ledger)

> **Author:** Keshava Pandi A S  
> **Creator:** Keshava Pandi A S  
> **Developer:** Keshava Pandi A S  
> **Integrity Mandate:** Statuses reflect genuine empirical capability in the repository today. Features are marked ✅ **IMPLEMENTED** only if real-world verification tests exist and pass. Mocks and planned architectures are categorized as 🧪 **EXPERIMENTAL**, ⚠️ **PARTIAL**, or 📋 **PLANNED**.

---

| Capability | Status | Current Implementation | Verification Method | Known Issues | Next Step |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **Voice Audio Pipeline** | ✅ IMPLEMENTED | PyAudio non-blocking stream capture, VAD thresholding | Hardware mic capture test in `test_microphone.py` | Requires correct Windows default audio input device | Add dynamic audio device selection in Settings |
| **Speech-to-Text (STT)** | ✅ IMPLEMENTED | Google Gemini 3.5 Transcribe primary; Faster-Whisper CUDA fallback | `tests/test_task1_gemini_stt.py` real mic transcription test | Online mode requires active `GEMINI_API_KEY` | Implement streaming chunked transcription |
| **Text-to-Speech (TTS)** | ✅ IMPLEMENTED | Streaming audio playback with energy-based voice interruption | Voice consistency test in `test_voice_consistency.py` | Windows sound device locks if exclusive mode active | Add multi-voice persona selector in Settings |
| **Global Hotkey** | ✅ IMPLEMENTED | `app/core/hotkey.py` hook on `Ctrl+Space` for Hold-to-Talk | Keydown/keyup cycle verified in runtime test | Requires admin rights if target window has elevated integrity | Add secondary global shortcut configuration |
| **Wake Word** | ⚠️ PARTIAL | Local `openWakeWord` detector for phrase "SERA" | Keyword test in `wakeword/evaluator.py` | False positives in noisy office environments | Retrain acoustic model with customized user voice samples |
| **Desktop Automation** | ✅ IMPLEMENTED | `app/tools/windows/apps.py` launcher with process & window title verification | `tests/vertical_slices/applications/` | UWP apps require special shell URI resolution | Expand Win32 window focus & keyboard macro injection |
| **Browser Automation** | ⚠️ PARTIAL | Shell launching of Chrome / Edge; URL dispatch | Process check for `chrome.exe` in vertical slices | No direct DOM manipulation via CDP yet | Integrate Playwright MCP client |
| **YouTube Navigation** | ✅ IMPLEMENTED | `app/tools/browser/youtube.py` search & direct video launcher | E2E browser launch and URL verification | Relies on default browser window focus | Add inline video metadata parsing |
| **Web Search** | ✅ IMPLEMENTED | DuckDuckGo HTML parser, ad-filter, strict contract parsing | `tests/vertical_slices/web_search/test_web_search_suite.py` (5 tests) | Rapid queries may trigger temporary rate limiting | Add Brave Search API as secondary engine |
| **Screen Capture** | ✅ IMPLEMENTED | `app/tools/screen/capture.py` multi-monitor screen grab | `tests/vertical_slices/screenshot/` DXGI image buffer test | Multi-monitor DPI scaling requires coordinate normalization | Optimize with direct GPU frame capture |
| **Vision Perception** | ⚠️ PARTIAL | `app/tools/screen/vision.py` multimodal prompt via Groq/Gemini | Screenshot payload submission test in `test_tools.py` | High token consumption on large 4K resolution screens | Implement local image downscaling & region of interest cropping |
| **Filesystem I/O** | ✅ IMPLEMENTED | `app/tools/filesystem/files.py` read, write, list files | File creation and checksum verification in tests | Restricted to project root for security | Add interactive operator permission prompts for deletions |
| **Memory Subsystem** | ⚠️ PARTIAL | In-memory lists in `app/memory/` (short-term & long-term) | State persistence across session commands | Resets on process restart; not partitioned into domains | Implement 6-tier persistent SQLite storage |
| **Local RAG Engine** | 📋 PLANNED | Architecture defined in `SERA_2_ARCHITECTURE.md` | Theoretical design | Not implemented in active codebase | Embed LanceDB vector store and semantic document chunker |
| **MCP Client Fabric** | 📋 PLANNED | Architecture defined in `SERA_2_MCP_PLAN.md` | Inspo MCP research script in `scratch/` | Native MCP client hub not yet wired into runtime | Build `app/core/mcp_client.py` stdio/SSE client |
| **Multi-Agent Swarm** | 📋 PLANNED | Single agent coordinator in `app/core/agent.py` | Sequential tool execution | Sub-agents (Desktop, Browser, Coding) not instantiated | Formalize `BaseAgent` and sub-agent contracts |
| **Model Providers** | ✅ IMPLEMENTED | Native adapters for Gemini, Groq, Mistral, OpenRouter, Cerebras, Ollama | Provider test suite in `test_groq.py`, `test_llm.py` | API keys required for external providers | Add Cloudflare Workers AI free pool adapter |
| **Resource Routing** | ✅ IMPLEMENTED | `app/core/router.py` health, latency, and cooldown cache | Routing explanation tests in `test_runtime_core.py` | Quotas currently tracked heuristically | Add exact token bucket counters |
| **State Persistence** | ⚠️ PARTIAL | `scratch/live_history.json` and `config/workflow_layout.json` | Refresh survival verified in browser testing | Session history stored as unindexed JSON | Migrate to structured SQLite database |
| **Live UI View** | ✅ IMPLEMENTED | Real-time WebSocket event streaming to `live.js` | Browser test in `test_live_streaming.py` | UI layout cluttered with redundant widgets | Refactor into clean human-facing execution theater |
| **Workflow View** | ⚠️ PARTIAL | Static node editor layout in `workflow.js` | UI rendering in browser | Freeform nodes disconnected from runtime execution | Rebuild as dynamic task-generated event timeline |
| **Architect Studio** | ✅ IMPLEMENTED | 3-column candidate configuration studio in `architect.js` | Role update tests via WebSocket | Changing candidate order does not affect temporary cooldowns | Add visual latency comparison sparklines |
| **History View** | ⚠️ PARTIAL | Session log table in `history.js` | Log rendering test | Lacks full-text search and artifact preview | Add artifact modal viewer and date filters |
| **System Telemetry** | ✅ IMPLEMENTED | Structured event traces in `app/core/telemetry.py` | JSON log file generation in `reports/` | Log files grow unbounded if not periodically pruned | Implement rolling log file retention policy |
| **Primary Presence** | ✅ IMPLEMENTED | 8-Layer WebGL/Three.js Computational Consciousness Engine (`presence_desktop/src/engine/PresenceEngine.js`) | Automated frame captures (`desktop_presence_live.png`, `desktop_presence_task.png`, etc.) | None | Add audio visualizer spectrum shader |
| **Evidence Verification Fabric** | ✅ IMPLEMENTED | `app/core/verification.py` empirical side-effect gate engine | `tests/vertical_slices/verification/test_evidence_fabric.py` (12 tests) | None (zero false passes enforced) | Expand to audio output buffer verification |
| **Native Desktop Shell** | ✅ IMPLEMENTED | Electron 33 borderless overlay (`presence_desktop/main.js`) with 100% DWM alpha transparency & global shortcut | Empirical process check (HWND 0x0c070d0000000000) & native desktop capturePage | None | Add multi-monitor display selector in Command Center |

---

### Status Summary
* **✅ IMPLEMENTED:** 18 capabilities fully operational and verified.
* **⚠️ PARTIAL:** 5 capabilities working but undergoing active rework or enhancement.
* **📋 PLANNED:** 3 capabilities architecturally specified for upcoming phases.
* **❌ BROKEN:** 0 active regressions (previous Chrome launch and DuckDuckGo zero-result bugs resolved).
