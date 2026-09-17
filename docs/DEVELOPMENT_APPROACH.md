# SERA Development Approach & Engineering Philosophy

> **Author:** Keshava Pandi A S  
> **Creator:** Keshava Pandi A S  
> **Developer:** Keshava Pandi A S  
> **Core Mandate:** Observable real-world verification over theoretical assertions. Zero false passes.

---

## 1. Core Engineering Principles

The development of SERA is governed by 10 non-negotiable principles designed to eliminate the common pitfalls of autonomous AI development:

### 1. Vertical-Slice Development
Rather than building horizontal layers across the entire system simultaneously (e.g., creating all UI tabs before backend tools exist, or building all model adapters before executing commands), development proceeds in **end-to-end vertical slices**. A single capability (such as "Open Chrome" or "Search Web") is built from user trigger -> intent classification -> tool execution -> real-world verification -> UI event broadcast -> visual rendering.

### 2. One Task at a Time
Never attempt to solve multiple disparate problems in a single pass. Work proceeds sequentially: complete Task 1, verify it with empirical evidence in Chrome/Windows, and only then proceed to Task 2.

### 3. Real-World Side-Effect Verification
A tool is **never** considered complete simply because a Python subprocess exited with code 0 or an API returned HTTP 200. The tool must verify that the intended physical side-effect actually materialized:
* For application launch: Verify the operating system process ID exists and the application window handle is registered in the desktop window manager.
* For web search: Verify that structured data records (title, URL, snippet, source) were extracted and that non-zero results were obtained.
* For file operations: Verify that the file content exists on disk and matches the intended checksum.

### 4. Browser & Manual Acceptance
Automated headless assertions are insufficient for user-facing features. Every visual state, task completion indicator, and interaction flow must be verified in a real browser session (via headed tests, browser subagents, or human visual inspection).

### 5. No False PASS Based Only on Mocks
Mocking external systems (such as search engines or OS processes) is permitted solely for isolated unit tests. Acceptance testing requires real execution against real endpoints. A test that asserts `tool.execute()` returned a hardcoded mock dictionary is not proof that the feature works.

### 6. Small Targeted Tests Over Monolithic Suites
Avoid giant, brittle test suites that take 15 minutes to run and fail on unrelated timeouts. Tests are partitioned into concise vertical slices (`tests/vertical_slices/<slice>/`) containing 3 to 5 targeted scenarios that run in seconds and pinpoint failures immediately.

### 7. Provider & Model Agnostic Architecture
SERA is not an "OpenAI wrapper" or a "Gemini script." The core reasoning engine is decoupled from specific LLM providers. Models are treated as interchangeable compute nodes routed dynamically according to task role and capability.

### 8. Capability-Based Routing
Routing decisions are made based on verified model capabilities (structured tool calling, vision perception, context window size, latency limits) rather than brand names.

### 9. Strict Backend / UI Synchronization
The Command Center and Primary Presence never maintain independent state or invent mock data. Every visual indicator, task progress bar, and tool badge is a direct reflection of an immutable event emitted by the backend `EventBus`.

### 10. Observable Real-World Results
Every user interaction must culminate in an observable outcome: an application opened, a structured summary delivered, an audio response spoken, or a crystal-clear error explanation when an action is blocked.

---

## 2. Verification Hierarchy: The Four Pass Levels

To ensure absolute technical honesty, every feature in SERA must advance through a four-tier verification hierarchy:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           VERIFICATION HIERARCHY                        │
├──────────────────┬──────────────────────────────────────────────────────┤
│ Level            │ Criteria & Scope                                     │
├──────────────────┼──────────────────────────────────────────────────────┤
│ 1. UNIT PASS     │ Logic verification in isolation. Function returns    │
│                  │ correct data structures given known inputs.          │
├──────────────────┼──────────────────────────────────────────────────────┤
│ 2. INTEGRATION   │ Multi-component contract verification. EventBus      │
│    PASS          │ delivers events from runtime to WebSocket server.    │
├──────────────────┼──────────────────────────────────────────────────────┤
│ 3. E2E PASS      │ End-to-end pipeline execution from user trigger to   │
│                  │ OS tool execution with real-world side-effects.      │
├──────────────────┼──────────────────────────────────────────────────────┤
│ 4. MANUAL        │ Human or headed-browser visual confirmation in the   │
│    ACCEPTANCE    │ actual UI. Verified observable result in Chrome.     │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### Distinguishing the Levels with an Example: "Open Chrome"
1. **Unit Pass:** `test_parse_open_command()` confirms that the regex or LLM correctly parses the text `"Open Chrome"` into intent `OPEN_APPLICATION` with argument `app_name="chrome"`.
2. **Integration Pass:** `test_pipeline_routes_to_app_tool()` confirms that `CommandPipeline` instantiates `WindowsApplicationTool` and emits `TOOL_STARTED`.
3. **E2E Pass:** `test_chrome_actually_launches()` runs the real tool on Windows, queries `powershell Get-Process chrome`, and confirms that a process named `chrome.exe` with a valid window handle exists.
4. **Manual Acceptance:** An operator or browser subagent opens Chrome, observes the window appear on the Windows desktop, and confirms that the Command Center transitions to `COMPLETED`.

> [!CAUTION]
> A feature is considered **COMPLETED** only when Level 3 (E2E Pass) and Level 4 (Manual Acceptance) are satisfied. Level 1 or 2 alone does not constitute completion.

---

## 3. Vertical-Slice Testing Methodology

The repository structure reflects this testing philosophy under `tests/vertical_slices/`:

```
tests/vertical_slices/
├── applications/
│   └── test_application_lifecycle.py   # Verifies real process launch & window checks
├── browser/
│   └── test_browser_navigation.py      # Verifies tab creation and URL loading
├── screenshot/
│   └── test_screen_capture.py          # Verifies real DXGI/PIL screen capture
├── web_search/
│   └── test_web_search_suite.py        # Verifies DuckDuckGo parsing, ad-filtering & contracts
├── system/
│   └── test_system_controls.py         # Verifies audio volume and power settings
├── voice/
│   └── test_gemini_transcribe.py       # Verifies real microphone audio transcription
└── context/
    └── test_runtime_synchronization.py # Verifies WebSocket event telemetry sync
```

Each slice contains:
1. A live execution test with real parameters.
2. A strict schema contract test ensuring all expected fields exist.
3. A controlled failure/zero-result test ensuring the pipeline transitions to `BROKEN` rather than falsely claiming success.
4. A performance/latency boundary test.
