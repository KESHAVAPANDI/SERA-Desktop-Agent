# SERA Live2D motion and speech refinement

## 2.5D continuity

The existing Mao Cubism model remains the single persistent character. PixiJS
and Cubism provide the dimensional shading, physics, layered facial planes and
soft lighting; this refinement does not replace the model or introduce a
second renderer.

## Calmer horizontal movement

Horizontal motion is composed from several independent sources:

- State `ParamAngleY` and `ParamBodyAngleY` targets.
- Life-layer harmonic yaw drift.
- Micro-saccade horizontal gaze offsets.
- Live2D motion-group animation selected by the state profile.

The controller now applies a `0.35` horizontal amplitude to its state/life/gaze
inputs, reducing controller-generated side motion by approximately 65% while
preserving vertical breathing, blinking, roll, and state-specific posture.
The life layer's own yaw drift was also reduced to keep the character centered.
Motion-group animation remains owned by Live2D and is not rewritten by the
controller; it can therefore still contribute model-authored movement.

## Real playback lip sync

The runtime already emits `TTS_AUDIO_LEVELS` from `AudioManager` while
`sounddevice` is actively playing the generated WAV. The payload contains
`rawAmp`, `bass`, `mid`, and `treble`. The existing WebSocket path is preserved:

```text
AudioManager playback → TTS_AUDIO_LEVELS → PresenceApp → PresenceEngine
  → Live2DController.setAudioData → ParamA
```

`ParamA` is verified by `Mao.model3.json`'s `LipSync` group. The controller
smooths the real raw/mid envelope and maps it to mouth opening only while the
SPEAKING profile is active and telemetry is fresh. Zero or stale telemetry
closes the mouth; TTS start, interruption, completion, cancellation, buffering,
and playback errors cannot trigger a fabricated speaking cadence.

This is amplitude-based lip sync, not phoneme/viseme synchronization. The old
timer cadence fallback is intentionally no longer used when telemetry is
silent or unavailable.

## Verification

Focused tests:

```text
cd presence_desktop
node --test tests/*.test.mjs
```

The Electron Live2D showcase remains the renderer-only acceptance tool:

```text
node_modules/electron/dist/electron.exe tests/verify_live2d_runtime.js
```

It verifies the real model loads once, state transitions do not reload it,
horizontal controller bounds remain calm, and audio payloads open/close the
mouth. It does not prove Python-to-Electron delivery or generated TTS playback.
Those require the Python environment and a listening runtime on
`127.0.0.1:8765`.
