# Changelog

All notable changes to the SERA project are documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.0-design] — 2026-09-17

### Added
* **SERA 2.0 Architectural Specifications:**
  * `docs/SERA_2_PRODUCT_VISION.md`: Dual-body paradigm (floating transparent presence vs. technical command center).
  * `docs/SERA_2_ARCHITECTURE.md`: Decoupled micro-kernel, unified event bus, and Model Fabric.
  * `docs/SERA_2_VISUAL_SYSTEM.md`: Three.js WebGL shader specifications, concentric ring mathematics, GPGPU curl particles, and 9 state modes.
  * `docs/SERA_2_CAPABILITY_MATRIX.md`: 16-dimension capability audit with verification gates.
  * `docs/SERA_2_MCP_PLAN.md`: Native Model Context Protocol (MCP) client architecture and initial catalog.
* **Primary SERA Presence (Phase B Engine):**
  * Created `app/ui/static/presence.html`, `presence.css`, `presence_engine.js`, `status_morpher.js`, and `presence_controller.js`.
  * Implemented 100% alpha-transparent WebGL canvas with Wisdom King / Raphael computational core.
  * Implemented 9 interactive physics states: `IDLE`, `LISTENING`, `TRANSCRIBING`, `THINKING`, `EXECUTING`, `SPEAKING`, `BROKEN`, `CANCELLED`, `COMPLETED`.
  * Implemented signature **Computational Cellular Reconstruction** completion animation.
  * Added single-line kinetic status text morpher with blur/fade transitions.
  * Vendored offline `three.min.js` (603 KB) in `app/ui/static/js/vendor/`.
* **Empirical Web Search Engine:**
  * Implemented `parse_duckduckgo_html` in `app/tools/browser/web_search.py` with multi-line title cleaning, sponsored ad filtering, and strict data contracts (`title`, `url`, `snippet`, `source`).
  * Added live search preview event streaming to the UI.
  * Created comprehensive 5-test vertical slice in `tests/vertical_slices/web_search/test_web_search_suite.py`.
* **Google Gemini 3.5 Transcribe STT:**
  * Added dedicated `gemini-3.5-transcribe` integration in `app/models/stt/gemini.py`.
  * Preserved local Faster-Whisper CUDA FP16 as automatic offline fallback.
* **Real Application Launch Verification:**
  * Added process table lookup (`Get-Process`) and window title handle confirmation to `app/tools/windows/apps.py` to eliminate false passes.

---

## [1.5.0-phase5d5] — 2026-08-31

### Added
* **Adaptive Temporal Runtime:**
  * Resource-aware router with model-level health tracking and volatile cooldowns (`app/core/resource_cache.py`).
  * 3-column Architect Studio in `architect.js` for primary, fallback, and disabled model assignment.
  * Live embedded execution theater in `live.js` with structured tool badges and inline telemetry.
  * Multi-step bounded security manager enforcing 5-step loop limits and 10s action timeouts.

---

## [1.4.0-phase5d] — 2026-08-25

### Added
* **Temporal Aura Operating Interface:**
  * High-density dark workstation design system in `app/ui/static/css/`.
  * Asynchronous WebSocket gateway server on port 8765 in `app/ui/server.py`.
  * E2E test suites using Playwright for navigation and runtime UI synchronization.

---

## [1.3.0-phase5c2] — 2026-08-20

### Added
* **Hold-to-Talk Voice Architecture:**
  * Global Windows keyboard hook on `Ctrl+Space` for dedicated audio capture.
  * Wake-word yielding logic ensuring clean audio handoffs between background listeners and intentional speech.
  * Real-time acoustic interruption cutting off TTS playback upon user speech detection.

---

## [1.2.0-phase4] — 2026-08-10

### Added
* **Multi-Provider LLM Expansion:**
  * Integration of Mistral AI (Codestral, Mistral Small/Large), Groq (Llama-3.3-70B, Qwen-2.5), and OpenRouter.
  * Per-model health tracking and latency exponential moving average calculations.

---

## [1.1.0-phase2] — 2026-07-28

### Added
* **Local Speech & Tool Infrastructure:**
  * Local Faster-Whisper CUDA speech recognition.
  * Streaming TTS audio engine.
  * Windows system automation tools (PowerShell execution, volume control, window title queries).

---

## [1.0.0] — 2026-07-15

### Added
* **Core Agent Foundation:**
  * Initial `SERARuntime` event loop and `SERAState` state machine.
  * Async `EventBus` pub/sub infrastructure.
  * CLI voice agent entry point in `main.py`.
