# Mochi × SERA desktop presence

Mochi is the supportive presentation layer for SERA's desktop runtime. The
central WebGL presence remains the focus; the surrounding DOM gives a quiet,
human-readable account of facts supplied by the runtime.

## Authority and data flow

The Python runtime and its WebSocket stream remain authoritative:

```text
SERA runtime → RuntimeSocket → reducePresenceMessage → PresenceApp projection
```

`presenceModel.js` is a pure reducer. It does not infer intent from text, invent
runtime events, or advance a local state machine. `TASK_STARTED`, for example,
records task identity but waits for `RUNTIME_STATE_CHANGED` before changing the
runtime state. TTS is an audio overlay: playback can present `SPEAKING` without
overwriting the underlying task state.

## Presentation contract

- The root `#glass-panel` exposes `data-state`, `data-tone`,
  `data-connection`, `data-runtime-attached`, `data-audio`, `data-approval`, and
  (only when supplied) `data-task-progress`.
- It also receives one `state-<lowercase state>` class. Existing element IDs and
  Electron window controls are unchanged.
- Runtime task progress is shown only when an explicit `progress` or
  `task_progress` value arrives. Fractions, percentages, and `{current,total}`
  values are normalized to `0..1` and passed to the existing presence engine.
- Connection loss, or a snapshot that explicitly says the runtime is not
  attached, presents Mochi as offline without mutating the remembered runtime
  state.
- TTS start/finish events update `data-audio`, the response status, an ARIA live
  status, and the existing audio-reactive rendering path.

## Approval seam

`SECURITY_CONFIRMATION_REQUIRED` exposes a small semantic `section` containing
the runtime-provided action and reason. It intentionally has no allow, deny, or
decision controls. Approval remains owned by SERA; a future approval surface can
bind to the stored `requestId` without changing the visual state contract.

## Supported visual vocabulary

Mochi presents offline, idle, listening, transcribing, thinking, planning,
executing, verifying, waiting for approval, speaking, completed, failed/broken,
and cancelled states. Task-prefixed runtime lifecycle states and the runtime's
approval/error/shutdown aliases map to that vocabulary. Unknown states are not
derived from captions or keywords.

## Current limitations

- The current server bridge may not emit progress updates in every task path;
  the UI renders progress only when the WebSocket payload contains it.
- Approval decisions are deliberately out of scope.
- No local persistence is added; reconnect snapshots repopulate available task
  and approval facts.
