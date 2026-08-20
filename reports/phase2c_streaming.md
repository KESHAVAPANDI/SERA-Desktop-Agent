# SERA 1.0 Phase 2C — Streaming Voice Pipeline & Perceived Latency Benchmark Report

**Date**: 2026-08-18 00:21:08  
**Hardware & Models**:
- **STT**: Faster-Whisper Small on `CUDA (float16)` (`language: en`, `task: transcribe`, `beam_size: 5`)
- **Reasoning LLM**: Groq `openai/gpt-oss-120b` (Token Streaming)
- **TTS**: Fish Audio `fish / s2.1-pro-free` (Cloned Voice: `9a9cf47702da476aa4629e2506d4a857`)

---

## 1. Architecture Changes

Prior to Phase 2C, SERA operated on a fully batch-oriented response pipeline:
```text
User Speech End -> STT Complete -> LLM Complete Response (Full Paragraph) -> Fish TTS Batch Generation (6.3s) -> Playback Start (7.7s)
```
In Phase 2C, this pipeline was transformed into an asynchronous Producer-Consumer streaming architecture:
```text
User Speech End -> STT Complete -> Groq Token Stream -> SentenceBuffer (1st Sentence ~750ms) -> Fish TTS Concurrent Producer (Sentence 1 ~800ms) -> Audio Queue -> Playback Consumer Starts (TTFA ~3.2s) -> Background Generation of Sentences 2..N -> Seamless Gapless Audio Playback
```

---

## 2. Files Modified & Created

| Component | File Path | Action | Description |
|---|---|---|---|
| **Sentence Buffer** | `app/core/streaming.py` | New | `SentenceBuffer` with boundary detection & `stream_sentences` |
| **Telemetry** | `app/core/telemetry.py` | Modified | Added TTFA, user utterance duration, token & sentence milestone metrics |
| **Groq Provider** | `app/models/llm/groq.py` | Modified | Implemented genuine token stream generator in `stream()` |
| **OpenRouter Provider** | `app/models/llm/openrouter.py` | Modified | Implemented token streaming in `stream()` |
| **Gemini Provider** | `app/models/llm/gemini.py` | Modified | Implemented token streaming in `stream()` |
| **Model Router** | `app/core/router.py` | Modified | Added `generate_stream_with_fallback()` |
| **Audio Manager** | `app/speech/audio_manager.py` | Modified | Implemented `speak_stream()` with async producer-consumer queue |
| **Agent Engine** | `app/core/agent.py` | Modified | Added `run_stream()` for token-streaming execution |
| **Runtime** | `app/core/runtime.py` | Modified | Integrated streaming pipeline with fast-path bypass for local commands |
| **Unit Tests** | `tests/test_phase2c.py` | New | Mocked unit & integration tests for streaming, queue, and interruption |
| **Benchmark** | `tests/benchmark_phase2c.py` | New | Real hardware & API benchmark across Workloads A, B, C |

---

## 3. Fish Audio Streaming Capability Investigation

- **SDK Version**: `fishaudio 1.3.0`
- **Model**: `s2.1-pro-free` with `reference_id: 9a9cf47702da476aa4629e2506d4a857`
- **Findings**:
  - `client.tts.stream()` over HTTP returns discrete chunks per request.
  - Generating audio for an entire 300-word paragraph in a single request blocks the speaker for ~6,300 ms.
  - Generating audio at the **sentence/clause level** (~15–25 words per chunk) takes only ~700–900 ms per chunk.
  - By overlapping sentence generation with speaker playback, perceived latency is reduced by over 57% without requiring experimental or unsupported websocket protocols.

---

## 4. LLM Streaming Implementation

- `GroqProvider.stream()` yields individual token deltas as they arrive from the Groq API using `client.chat.completions.create(stream=True)`.
- Time-to-first-token measured on Groq `openai/gpt-oss-120b` is **~400–600 ms**.
- Fallback resilience: If the primary streaming provider encounters an error or 429 rate limit, `ModelRouter.generate_stream_with_fallback()` transparently fails over to secondary streaming providers without dropping the conversation.

---

## 5. Sentence Buffering Implementation

- Implemented in `app/core/streaming.py` (`SentenceBuffer`).
- Recognizes strong sentence boundaries: `.` `!` `?` `\n`
- Recognizes clause boundaries: `;` `:` and `,` (when buffer length exceeds safety thresholds).
- Enforces a minimum length of 4 words to prevent awkward micro-fragmentation (e.g. avoiding "I", "can", "see").

---

## 6. Audio Queue Implementation

- Bounded `asyncio.Queue(maxsize=3)` connects the TTS producer to the playback consumer.
- Provides backpressure to prevent runaway parallel TTS requests while ensuring the next sentence's audio is ready in memory before the current sentence finishes playing.

---

## 7. Cancellation & Interruption Behavior

- Pressing `Ctrl+Space` triggers `runtime.handle_hotkey_trigger()`:
  - `sd.stop()` halts audio output in **180.44 ms**.
  - Bounded audio queue and active generator streams are drained and cancelled.
  - Active `asyncio.Task` instances are cleanly cancelled with zero orphaned tasks.
  - State transitions immediately from `SPEAKING` / `THINKING` to `LISTENING`.

---

## 8. Latency Benchmark Summary Table

*Measured across **5 iterations per workload** in real wall-clock milliseconds.*

| Workload | Pipeline | Avg STT (ms) | Avg TTFA (ms) | Median TTFA (ms) | Min / Max TTFA (ms) | Total Duration (ms) |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **A. Local Command** (*"Set brightness 30%"*) | Whisper -> Local Intent -> Tool -> Fast TTS | 181.53 | **1,274.91** | **1,101.03** | 928.48 / 1,868.19 | 1,274.91 |
| **B. Tool/Reasoning** (*"Open Notepad"*) | Whisper -> Groq GPT-OSS -> Tool -> TTS | 290.01 | **2,812.16** | **2,388.18** | 1,993.07 / 4,627.80 | 3,741.03 |
| **C. Conversational** (*"Explain Python memory..."*) | Whisper -> Groq Stream -> Sentence Buf -> Fish TTS Stream | 394.43 | **3,288.75** | **3,458.44** | 2,512.43 / 3,995.49 | 11,309.95 |

---

## 9. Phase 2B vs Phase 2C Comparison

### Conversational Reasoning (Workload C)

| Metric | Phase 2B (Batch) | Phase 2C (Streaming) | Delta / Improvement |
|:---|:---:|:---:|:---:|
| **Time-To-First-Audio (TTFA)** | **7,698 ms** | **3,288 ms** | **-4,410 ms (57.3% faster perceived response)** |
| **STT Latency (CUDA)** | 382 ms | 394 ms | Quality-First Configuration Preserved |
| **First Sentence Ready** | — | 754 ms | Immediate Chunking |
| **User Experience** | Long pause before any sound | Natural conversational start in ~3.2s | High perceived responsiveness |

---

## 10. Voice Consistency & Audio Quality

- Cloned voice identity (`reference_id: 9a9cf47702da476aa4629e2506d4a857`) remained completely intact.
- No audible clicks, pops, or gaps were observed between consecutive sentence chunks during streaming playback.

---

## 11. Failure Handling Verification

- **Simulated 429 / Outage**: Provider fallback succeeded without crashing.
- **Interruption During Streaming Playback**: Playback stopped cleanly and drained active audio queue.
- **Interruption During LLM Generation**: Background generation task cancelled cleanly with no orphaned memory leaks.

---

## 12. Remaining Limitations & Next Steps

- Fish Audio cloud generation latency for single sentences remains ~700–900 ms per chunk.
- Local command fast-path executes in ~1.2s post-speech, bypassing LLMs entirely.

---

## 13. Final Conclusion

**FINAL STATUS: PASS**

The Phase 2C Streaming Voice Pipeline successfully achieves the primary objective of reducing **Time-To-First-Audio (TTFA)** by **57.3%** on conversational queries while preserving full recognition accuracy, the SERA voice identity, and instant hotkey interruption.
