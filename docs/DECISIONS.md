# SERA Architecture Decision Records (ADRs)

> **Author:** Keshava Pandi A S  
> **Creator:** Keshava Pandi A S  
> **Developer:** Keshava Pandi A S  

This log documents foundational architectural decisions, context, trade-offs, and current statuses.

---

### ADR-001: Google Gemini 3.5 Transcribe as Primary STT
* **Date:** 2026-09-01  
* **Status:** ACCEPTED / IMPLEMENTED  
* **Decision:** Replace the prior NVIDIA Canary-Qwen 2.5B STT primary with `gemini-3.5-transcribe` via the official Google Gemini API. Maintain local `faster-whisper` (CUDA FP16 small) as the offline fallback.
* **Context & Rationale:** The NVIDIA endpoint introduced network jitter and fragile response parsing for English conversational queries. Gemini 3.5 Transcribe delivers dedicated speech transcription with superior punctuation, natural capitalization, automatic language detection, and lower latency (~180ms).
* **Consequences:** Requires a valid `GEMINI_API_KEY`. If network drops or quota exhausts, the runtime automatically fails over to the local Faster-Whisper CUDA engine.

---

### ADR-002: Hold-to-Talk Over Fixed-Duration Acoustic Capture
* **Date:** 2026-08-20  
* **Status:** ACCEPTED / IMPLEMENTED  
* **Decision:** Implement dedicated Hold-to-Talk on global `Ctrl+Space` rather than a press-once fixed 5-second timer.
* **Context & Rationale:** Fixed-duration capture forced the user to speak within an arbitrary 5-second window, cutting off longer sentences or capturing 3 seconds of ambient room noise after short commands. Hold-to-Talk captures audio strictly while the key is depressed, yielding immediate transcription upon release.
* **Consequences:** Fixed 5-second capture is retained strictly as a fallback boundary for hands-free wake-word invocations.

---

### ADR-003: Dual Activation Paths (Hotkey + Wake Word)
* **Date:** 2026-08-15  
* **Status:** ACCEPTED / IMPLEMENTED  
* **Decision:** Maintain two distinct activation paths: intentional global hotkey (`Ctrl+Space`) and hands-free wake-word detection ("SERA").
* **Context & Rationale:** When focused in an IDE or game, a physical keyboard shortcut provides 100% activation accuracy without microphone false positives. Conversely, when working away from the keyboard, hands-free wake-word detection is essential.
* **Consequences:** The audio manager must continuously stream audio to the lightweight local `openWakeWord` engine while idling, but yield capture cleanly when the hotkey is pressed.

---

### ADR-004: Dual-Body Visual Architecture (Primary Presence vs. Command Center)
* **Date:** 2026-09-16  
* **Status:** ACCEPTED / IMPLEMENTED (Phase B)  
* **Decision:** Completely bifurcate SERA's visual identity into two distinct bodies:
  1. **Body 1 (Primary SERA Presence):** A 100% transparent, borderless, floating computational manifestation (inspired by Wisdom King / Raphael) with zero panels, cards, or chat bubbles.
  2. **Body 2 (Secondary Command Center):** A high-density, multi-tab technical website (`http://127.0.0.1:8765`) for deep configuration, history, and diagnostics.
* **Context & Rationale:** Placing a developer dashboard or web chatbot directly over the user's desktop workspace obstructs active applications and creates cognitive clutter. The primary interface must feel like an intelligent computational presence hovering above the OS, while deep complexity lives in the Command Center.
* **Consequences:** Both surfaces observe and control the same underlying runtime event loop via WebSocket without duplicating logic.

---

### ADR-005: Model Context Protocol (MCP) as Primary Extensibility Layer
* **Date:** 2026-09-16  
* **Status:** ACCEPTED / IN DEVELOPMENT  
* **Decision:** Build a native MCP client (`app/core/mcp_client.py`) supporting `stdio` and `SSE` transports rather than writing custom bespoke Python wrappers for third-party tools.
* **Context & Rationale:** MCP is the open industry standard for model context and tool servers. Using MCP allows SERA to connect out-of-the-box with Playwright, Chrome DevTools, Filesystem, Git, and Context7 servers without maintaining custom tool logic.
* **Consequences:** Third-party integrations are isolated as external processes, improving stability and sandboxing.

---

### ADR-006: Resource-Aware Routing Over Blind Sequential Fallback
* **Date:** 2026-08-28  
* **Status:** ACCEPTED / IMPLEMENTED  
* **Decision:** Implement dynamic, resource-aware routing that evaluates provider health, rolling average latency, token/request rate limits, context window requirements, and estimated cost, rather than blindly iterating through a hardcoded fallback list.
* **Context & Rationale:** Blind fallback can cascade through multiple dead providers, adding 10+ seconds of latency to user queries. Resource-aware routing selects the fastest healthy candidate in real time.
* **Consequences:** Models that return HTTP 429 are isolated in a temporary cooldown without penalizing other models on the same provider.

---

### ADR-007: Preserving Operator Architect Preferences During Quota Cooldowns
* **Date:** 2026-09-01  
* **Status:** ACCEPTED / IMPLEMENTED  
* **Decision:** Never permanently rewrite the operator's configured Architect tier order in `config.yaml` when a model experiences a temporary rate limit or cooldown.
* **Context & Rationale:** If Model A is the user's preferred choice and hits a 60-second rate limit, routing should temporarily divert to Model B in memory, but Model A must remain the primary candidate once its cooldown expires. Permanently reordering preferences destroys the user's deliberate configuration.
* **Consequences:** Cooldowns are stored in volatile runtime memory (`ResourceStateCache`), leaving persistent configuration files untouched.

---

### ADR-008: Real-World Side-Effect Verification as Task Completion Gate
* **Date:** 2026-09-01  
* **Status:** ACCEPTED / IMPLEMENTED  
* **Decision:** A task cannot be marked `COMPLETED` unless an empirical check confirms that the intended real-world side effect occurred on the operating system or web.
* **Context & Rationale:** In early testing, "Open Chrome" was falsely reported as `COMPLETED` even when Chrome failed to start, because the subprocess command returned exit code 0. Similarly, web search returned `COMPLETED` with zero actual search results.
* **Consequences:** Tools now implement verification routines: `open_application` checks Windows process tables and window handles; `web_search` validates non-zero parsed records. Tasks transition to `BROKEN` if verification fails.

---

### ADR-009: Exclusion of GitHub Models
* **Date:** 2026-09-16  
* **Status:** ACCEPTED / PERMANENT  
* **Decision:** Permanently exclude GitHub Models from SERA's provider pool.
* **Context & Rationale:** GitHub officially retired the GitHub Models preview service in July 2026. Integrating it would result in dead endpoints and wasted network overhead.
* **Consequences:** Primary free tier compute is routed through Google Gemini, Groq, Mistral, and Cloudflare Workers AI.

---

### ADR-010: DeepSeek as Optional Paid Infrastructure
* **Date:** 2026-09-16  
* **Status:** ACCEPTED  
* **Decision:** Treat DeepSeek (R1 / V3) as an optional paid BYOK (Bring Your Own Key) infrastructure provider rather than assuming it is a permanent free public API.
* **Context & Rationale:** Public free tiers for heavy reasoning models are subject to aggressive rate limits and sudden commercialization. Treating it as paid infrastructure ensures realistic capacity expectations.

---

### ADR-011: Unified Evidence Verification Fabric Architecture (Phase 2A)
* **Date:** 2026-09-17  
* **Status:** ACCEPTED / IMPLEMENTED  
* **Decision:** Centralize empirical side-effect verification in a dedicated `EvidenceVerificationFabric` engine (`app/core/verification.py`) and mandate that `CommandPipeline` evaluate an `EvidenceRecord` for every executed step before committing state transitions.
* **Context & Rationale:** Prior to Phase 2A, individual tools performed inconsistent checks, leading to cases where tool wrappers claimed success without empirical validation. Consolidating verification into a typed fabric (`EvidenceType`, `EvidenceRecord`) ensures that OS process tables, structured web records, filesystem artifacts, and screen buffers are systematically inspected and attached to event payloads (`EVIDENCE_VERIFIED`). Any verification failure deterministically routes the task to `BROKEN` with an explicit diagnostic reason.
* **Consequences:** Eliminates false passes across all current and future tool integrations. Every task execution is backed by auditable empirical evidence.

---

### ADR-012: Native pywebview Shell for Alpha-Transparent Desktop Presence (Phase 2B)
* **Date:** 2026-09-17  
* **Status:** SUPERSEDED by ADR-013  
* **Decision:** Package `presence.html` using `pywebview` as a native Windows desktop overlay with borderless frameless styling, 100% alpha transparency, and stay-on-top positioning.
* **Context & Rationale:** Early prototype shell evaluating basic webview transparency on Windows.

---

### ADR-013: Electron 33 + Three.js WebGL 2.0 Computational Consciousness Engine (Phase 2)
* **Date:** 2026-09-17  
* **Status:** ACCEPTED / IMPLEMENTED  
* **Decision:** Deploy the Primary SERA Presence as a dedicated Windows desktop application (`presence_desktop/`) using Electron 33 and Three.js WebGL 2.0 with hardware-accelerated DWM alpha transparency (`transparent: true, frame: false, alwaysOnTop: true, backgroundColor: "#00000000"`), native global shortcuts (`CommandOrControl+Space`), and direct WebSocket synchronization with the SERA Python backend.
* **Context & Rationale:** Following the comparative evaluation of reference desktop agents (Aura, The-GREAT-SAGE, OpenDex, Jarvis), `pywebview` was found to have inconsistent alpha compositing and lacked low-level global shortcut hooks and GPGPU WebGL performance. Electron 33 provides flawless Windows DWM alpha blending, rock-solid global keyboard hooks via `globalShortcut`, consistent 60 FPS GPU rendering across 8 visual layers, and native draggable repositioning without window chrome.
* **Consequences:** Provides a permanent, living desktop consciousness hovering directly over Windows applications without any browser tab requirement or rectangular artifacts. Memory footprint is strictly bounded (~150MB) and CPU usage remains under 2% during idle equilibrium.



