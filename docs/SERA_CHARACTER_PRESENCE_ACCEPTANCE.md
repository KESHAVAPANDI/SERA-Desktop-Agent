# SERA Character Presence — Acceptance Matrix

This document separates renderer-only evidence from genuine runtime evidence.
The state showcase uses the real Electron Presence, the real Live2D model and
the real controller, but injects `RUNTIME_STATE_CHANGED` messages in the
development-only harness. Those rows are **RENDERER-ONLY TEST VERIFIED**.

## Baseline audit

- **Character:** `Niziiro Mao (Cubism 4)` from the official Live2D sample model,
  loaded from `presence_desktop/assets/live2d/models/mao/Mao.model3.json`.
- **Runtime:** Cubism Core 5.1.0 reported by the loaded runtime; PixiJS 6.5.10;
  `pixi-live2d-display` 0.4.0; Electron 33.2.1.
- **Verified model resources:** 8 expressions (`exp_01`–`exp_08`), `Idle`
  motions [0..1], `TapBody` motions [0..5], physics, pose, and `ParamA` lip sync.
  Verified parameters include head/body angles, eye openness/smile/form, eye
  gaze, `ParamBreath`, `ParamCheek`, and `ParamEyeEffect`.
- **Identity continuity:** one `Live2DModel` instance is attached once; state
  changes select profiles and smooth parameters rather than reloading assets.
- **Connection finding:** the Presence can load and animate while the runtime
  is unavailable. It correctly showed `MOCHI IS OFFLINE` in the standalone
  snapshot because TCP `127.0.0.1:8765` was not listening. This is not a model
  load failure and is not evidence of a healthy SERA runtime.
- **Known limitation:** the repository Python environment lacks `numpy`, so the
  Python runtime could not be started in this worker. TCP verification confirmed
  port 8765 was closed; genuine WebSocket state transitions are therefore
  **BLOCKED — REQUIRES ADDITIONAL INTEGRATION**.

## State coverage

| State | Source meaning / profile | Evidence | Status |
| --- | --- | --- | --- |
| `IDLE` | Calm, breathing, neutral expression | `live2d_01_idle.png` | RENDERER-ONLY TEST VERIFIED |
| `LISTENING` | Direct gaze, widened eyes, attentive posture | `live2d_02_listening.png` | RENDERER-ONLY TEST VERIFIED |
| `TRANSCRIBING` | Focused intake, `TapBody[0]` | `live2d_03_transcribing.png` | RENDERER-ONLY TEST VERIFIED |
| `THINKING` | Upward-left gaze, thoughtful expression | `live2d_04_thinking.png` | RENDERER-ONLY TEST VERIFIED |
| `PLANNING` | Deliberate forward posture | `live2d_05_planning.png` | RENDERER-ONLY TEST VERIFIED |
| `TYPING` | Presentation-compatible focused drafting profile | `live2d_06_typing.png` | RENDERER-ONLY TEST VERIFIED |
| `WORKING` | Presentation-compatible active tool profile | `live2d_07_working.png` | RENDERER-ONLY TEST VERIFIED |
| `EXECUTING` | Directional active posture | `live2d_08_executing.png` | RENDERER-ONLY TEST VERIFIED |
| `VERIFYING` | Precise inspection posture | `live2d_09_verifying.png` | RENDERER-ONLY TEST VERIFIED |
| `SPEAKING` | Warm expression with supplied audio envelope | `live2d_10_speaking.png` | RENDERER-ONLY TEST VERIFIED |
| `COMPLETED` | Positive acknowledgement | `live2d_13_completed.png` | RENDERER-ONLY TEST VERIFIED |
| `FAILED` | Concerned/downcast, not destroyed | `live2d_14_failed.png` | RENDERER-ONLY TEST VERIFIED |
| `CANCELLED` | Muted settling behavior | `live2d_15_cancelled.png` | RENDERER-ONLY TEST VERIFIED |
| `OFFLINE` | Eyes closed, subdued honest disconnected state | `live2d_16_offline.png` | RENDERER-ONLY TEST VERIFIED |

## Runtime and lifecycle evidence

Command:

```text
node --test tests/*.test.mjs
node tests/verify_live2d_runtime.js                 # incorrect: Node cannot provide Electron app
node_modules/electron/dist/electron.exe tests/verify_live2d_runtime.js
```

The Electron harness completed with Cubism Core 5.1.0, model `isLoaded: true`,
`loadCount: 1`, 28 state changes, 16 PNG captures, and no renderer load error.
This verifies model persistence, real resource loading, rendering, parameter
transitions, audio input path, and disposal in the Electron process. It does not
verify Python-to-WebSocket delivery.

## Speaking contract

`SPEAKING` is selected by the reducer only from `TTS_STARTED` or
`AUDIO_PLAYBACK_STARTED`; completion/interruption clears the audio overlay.
`TTS_AUDIO_LEVELS` reaches the existing controller and modulates `ParamA` using
the real `rawAmp`/`mid` envelope. The controller has a restrained cadence
fallback when telemetry is absent, documented as a fallback rather than real
audio evidence.
