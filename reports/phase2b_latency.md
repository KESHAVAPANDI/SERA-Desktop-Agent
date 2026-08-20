# SERA 1.0 Phase 2B — Real-World Voice Latency Benchmark & Runtime Hardening Report

**Date**: 2026-08-18 00:05:55  
**Hardware & Models**:
- **STT**: Faster-Whisper Small on `CUDA (float16)`
- **Reasoning LLM**: `groq / openai/gpt-oss-120b`
- **TTS**: Fish Audio `fish / s2.1-pro-free`

---

## 1. Latency Benchmark Summary

All numbers below represent real wall-clock latency in milliseconds measured across **5 iterations per workload**.

> [!NOTE]
> **Post-Speech Latency** measures the exact time from when the user finishes speaking until the first audio output is synthesized and ready to play. It does **not** include user speaking time.

### Latency Summary Table

| Workload | Pipeline | Avg STT (ms) | Avg LLM/Intent (ms) | Avg Tool (ms) | Avg TTS Gen (ms) | **Avg Total Post-Speech (ms)** | **Median (ms)** | **Min / Max (ms)** |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **A. Local Command** (*"Set brightness 30%"*) | Whisper -> Local Intent -> Tool -> TTS | 177.25 | 0.04 | 50.57 | 989.59 | **1217.5** | **1314.68** | 1007.35 / 1386.98 |
| **B. Tool/Reasoning** (*"Open Notepad"*) | Whisper -> Groq GPT-OSS -> Tool -> TTS | 307.64 | 1832.23 | 0.0 | 1358.31 | **3501.59** | **3520.73** | 2577.92 / 4919.59 |
| **C. Conversational** (*"Explain Python memory..."*) | Whisper -> Groq GPT-OSS -> TTS | 381.9 | 952.17 | — | 6363.63 | **7697.77** | **7349.7** | 6936.24 / 8525.39 |

---

## 2. Workload Breakdown & Analysis

### Workload A: Local Deterministic Command
- **Phrase**: `"Set my brightness to 30 percent"`
- **Routing**: `Local Intent Router` (Bypassed all cloud LLMs with 0 API overhead)
- **STT (CUDA)**: Min `121.72ms`, Avg `177.25ms`, Max `383.6ms`
- **Local Intent & Tool**: `0.04ms` + `50.57ms`
- **TTS Generation**: `989.59ms`
- **Total Post-Speech Latency**: Avg **1217.5ms**

### Workload B: Agentic Tool Command (Open Application)
- **Phrase**: `"Open Notepad"`
- **Routing**: Groq `openai/gpt-oss-120b` reasoning model
- **STT (CUDA)**: Avg `307.64ms`
- **Groq LLM + Tool Calling**: Avg `1832.23ms`
- **TTS Generation**: Avg `1358.31ms`
- **Total Post-Speech Latency**: Avg **3501.59ms**

### Workload C: Conversational Reasoning
- **Phrase**: `"Explain why Python programs can become slow when they use too much memory."`
- **Routing**: Groq `openai/gpt-oss-120b` (complex multi-sentence technical reasoning)
- **STT (CUDA)**: Avg `381.9ms`
- **Groq LLM Generation**: Avg `952.17ms`
- **TTS Generation**: Avg `6363.63ms`
- **Total Post-Speech Latency**: Avg **7697.77ms**

---

## 3. Model Routing Verification

- **Local Intent Bypass**: Confirmed (`True`) — Local volume/brightness/mute commands never trigger cloud inference.
- **Fast Model Route**: Confirmed for lightweight queries (`hello` -> `fast`).
- **Reasoning Model Route**: Confirmed for complex multi-step reasoning (`reasoning`).
- **Vision Model Route**: Confirmed for image/screenshot tasks (`vision`).
- **Automated Fallback**: Confirmed — When primary provider returns error/429, router automatically failed over to `fallback`.

---

## 4. Real Audio Interruption & Cancellation

- **Interruption Latency**: Average **0.06ms** (Min: `0.05ms`, Max: `0.07ms`).
- **Immediate Audio Cutoff**: Verified that `sd.stop()` halts speaker stream in under `0.07ms`.
- **Task Cancellation During Thinking**: Verified — when `Ctrl+Space` is pressed during LLM generation, the active `asyncio.Task` is cancelled cleanly in **62.64ms** without orphan background tasks.

---

## 5. Safety Confirmation & Resilience Verification

- **Safety Gating**:
  - `restart_computer`: Blocked without confirmation (`Blocked: True`)
  - `shutdown_computer`: Blocked without confirmation (`Blocked: True`)
- **Rapid Hotkey Presses**: Handled 5 triggers within 20ms without state corruption or task collision.
- **Provider Outage / 429 Recovery**: Transparently fell back to OpenRouter.

---

## 6. Identified Bottlenecks & Ranked Optimizations

| Rank | Component | Observed Bottleneck | Proposed Optimization | Estimated Impact |
|:---:|:---|:---|:---|:---:|
| **1** | **Fish Audio TTS API** | Cloud TTS roundtrip takes ~800–1200ms for generation | Implement chunked streaming playback (`audio/mpeg` stream chunks) as soon as the first sentence is generated | **-400ms to -600ms perceived latency** |
| **2** | **STT Beam Size** | Faster-Whisper with `beam_size=5` takes ~200–450ms on CUDA | Use `beam_size=1` (greedy decoding) with `vad_filter=True` for voice commands | **-100ms to -200ms STT latency** |
| **3** | **Streaming LLM to TTS** | LLM waits for full generation before passing text to TTS | Stream LLM tokens and feed first complete clause/sentence directly into TTS pipeline | **-300ms to -500ms conversational latency** |
| **4** | **Local Cache for Tools** | App discovery checks process table on every command | Cache common app executable paths in memory | **-20ms to -50ms tool latency** |
