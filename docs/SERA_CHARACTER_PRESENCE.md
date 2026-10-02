# SERA Character Presence

Mochi is one continuous character surface over SERA's authoritative runtime. The desktop shell does not create a second workflow state machine and does not infer activity from caption text or keywords.

## Event and presentation contract

- `presenceModel.js` reduces WebSocket facts and preserves task/turn correlation.
- Runtime states remain the states sent to `PresenceEngine`.
- `TYPING` is a presentation-only label activated by explicit `STREAM_START` or `STREAM_TOKEN` events and cleared by `STREAM_COMPLETE` or `AGENT_RESPONSE`.
- `WORKING` is a presentation-only label activated by an explicit `TOOL_STARTED` event and cleared by `TOOL_COMPLETED` or `TOOL_FAILED`. The engine continues to receive `EXECUTING`.
- TTS playback has visual priority only after explicit `TTS_STARTED`/`AUDIO_PLAYBACK_STARTED`; output bands come from `TTS_AUDIO_LEVELS`.
- Microphone bands come from the real browser audio analyser while the authoritative runtime state is `LISTENING`.

The root surface publishes `data-state`, `data-face`, `data-pose`, `data-attention`, `data-audio`, `data-progress`, and `data-approval`. These are semantic styling and inspection seams, not backend commands.

## Approval seam

`SECURITY_CONFIRMATION_REQUIRED` exposes the action and reason and marks the character as awaiting review. There are intentionally no approve/deny controls in the presence shell; decisions remain in SERA's command center. Correlated stale resolution events cannot dismiss the current request.

## Continuity and integration

The canvas remains the character. Orbit/readout/status elements support it quietly, while captions and approval context appear only when authoritative data exists. Electron minimize, close, command-center and global-activation hooks, lifecycle disposal, snapshot injection through `handleBackendEvent`, and the runtime WebSocket reducer path remain unchanged.

## Focused checks

From `presence_desktop`:

```powershell
node --test test/*.test.mjs
node --check src/integration/presenceModel.js
node --check src/ui/presentationState.js
node --check src/App.js
```
