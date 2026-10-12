# SERA contextual Live2D behaviour

This document describes the behaviour contract covered by the focused tests in
`presence_desktop/tests/livingBehaviour.test.mjs` and
`presence_desktop/tests/livingPresenceModel.test.mjs`. It reflects the current
implementation in this branch; it does not describe a proposed second
renderer or a future behaviour engine.

## Architecture

The desktop presence has one persistent model and a reducer/controller pipeline
with an explicit behavior composition layer:

```text
runtime messages
    |
    v
presenceModel.js
    - normalizes backend state and aliases
    - rejects stale task/turn/correlation events
    - derives effectiveVisualState / effectivePresentationState
    |
    v
PresenceEngine -> Live2DRenderer -> Live2DController
                                      |
                   +------------------+-----------------------+
                   |                  |                      |
                   v                  v                      v
             Live2DBehavior     state profiles         Live2DLifeLayer
             priority/ownership  + audio envelope       breathing, blink,
             + frame composition + damping              saccades, drift
```

`Live2DRenderer` attaches one `Live2DModel` to the controller. Changing state
changes targets, expression, and motion selection; it does not construct a new
model. `Live2DController.update(delta)` composes the state targets with the
continuous life frame, damps the result, and writes the Cubism parameters.

The reducer is the contextual arbitration boundary. It receives backend facts,
while the controller is the parameter/lifecycle boundary. `Live2DBehavior.js`
composes task context and bounded transient reactions before one frame target is
written. The renderer only bridges those boundaries to Pixi/Cubism.

## Parameter ownership and layer composition

| Concern | Owner | Cubism outputs / inputs |
|---|---|---|
| Canonical state and task correlation | `presenceModel.js` | Chooses runtime state, presentation alias, task identity, and TTS overlay |
| State-specific intent | `Live2DStateProfiles.js` | Expression, motion group/index, posture, gaze, breathing/blink rates, color, speaking flag |
| Contextual arbitration | `Live2DBehavior.js` | Priority merge, task-type gaze modifiers, transient event reactions, model motion capability fallback |
| Persistent biological life | `Live2DLifeLayer.js` | `breathValue`, blink ratio, saccades, harmonic drift; remains alive across state changes |
| State/life interpolation | `Live2DController.js` | Damped `ParamAngle*`, `ParamBodyAngle*`, eye gaze, eye openness, eye smile |
| Speech mouth opening | `Live2DController.js` | `ParamA` by default, only when profile is `SPEAKING` and telemetry is fresh |
| Semantic color and aura | `Live2DColorSystem.js` / renderer | Model tint and `ParamEyeEffect`; renderer aura graphic |
| Authored model animation | Cubism motion runtime | Profile-selected `motionGroup` and `motionIndex`; controller requests are bounded by inspected model capabilities |

The composed rule is additive where the parameter has separate inputs (for
example, state posture plus life drift) and multiplicative where the life layer
is a modifier (for example, profile eye openness multiplied by blink ratio).
Horizontal controller input is intentionally scaled to the tunable
`LIVE2D_CONFIG.behavior.horizontalMotion` value (`0.35` by default); gaze and
torso side motion are damped as well. This keeps controller-generated movement
calm, while model-authored motion can still contribute movement. A
`beforeModelUpdate` boundary hook reasserts the controller-owned parameter set
after Cubism motion/expression processing, and is detached before model cleanup.

## Priority and arbitration policy

The current priority order inside `Live2DBehavior.js` is low-to-high:

`expressionPosture < task < attention < speech < transientReaction`

Life is a continuous modifier layer, not a competing base target. The
controller resolves one frame from that ordered target and the current life
sample. At the runtime/reducer level, the effective visual priority is:

1. **Terminal task fact** — `TASK_COMPLETED`, `TASK_FAILED`, or
   `TASK_CANCELLED` sets the canonical runtime state and clears TTS activity.
2. **Active speech overlay** — active, correlation-valid TTS makes the effective
   visual state `SPEAKING` while preserving the underlying runtime state.
3. **Presentation-only activity alias** — `WORKING` and `TYPING` can describe a
   tool or stream phase without replacing the canonical runtime state.
4. **Canonical runtime state** — the normalized backend state drives the
   Live2D profile.
5. **Unknown profile fallback** — an unknown or empty profile lookup uses the
   `IDLE` profile. The reducer still retains an unknown normalized runtime value
   for diagnostics rather than silently rewriting backend facts.

Stale events do not win arbitration. Terminal events, transcription events, and
TTS stop events carrying a different current task/turn are ignored. The focused
tests use this as the contract for late stop packets and repeated transitions.

Transient reactions are accepted only for the current task correlation and only
for compatible canonical states. A repeated `setState` projection preserves an
accepted reaction; a conflicting state clears it. When its configured duration
ends, the controller explicitly reapplies the canonical expression and motion,
so an expired reaction cannot leave a stale visual target behind.

The continuous life layer is below semantic state arbitration but is not
stopped by it. It is updated for every loaded controller frame and is not
recreated when a state changes.

## Interruption and resumption

Speech is an overlay, not a terminal task state:

1. `TTS_STARTED` or `AUDIO_PLAYBACK_STARTED` sets `tts.active` for the current
   correlation and makes the effective visual state `SPEAKING`.
2. A runtime state change received during speech updates the preserved canonical
   state; speech remains the visible overlay while active.
3. `TTS_INTERRUPTED`, `TTS_COMPLETED`, or
   `AUDIO_PLAYBACK_FINISHED` clears the overlay only when its task correlation is
   current. The latest canonical runtime state is then visible again.
4. A terminal task event clears TTS and remains authoritative even if a late
   speech completion arrives afterward.

At the controller boundary, changing away from the `SPEAKING` profile sets the
mouth target to zero and lets damping close it. Re-entering `SPEAKING` can use
new fresh telemetry; stale amplitude is never replayed as fabricated cadence.

## Canonical state mapping

The canonical profile names are the states in `Live2DStateProfiles.js`:

`IDLE`, `LISTENING`, `TRANSCRIBING`, `THINKING`, `PLANNING`, `TYPING`,
`WORKING`, `EXECUTING`, `VERIFYING`, `WAITING_FOR_APPROVAL`, `SPEAKING`,
`COMPLETED`, `FAILED`, `CANCELLED`, and `OFFLINE`.

The reducer preserves backend truth and normalizes these aliases:

| Runtime alias | Canonical Live2D profile |
|---|---|
| `TASK_PLANNING` | `PLANNING` |
| `TASK_EXECUTING` | `EXECUTING` |
| `TASK_VERIFYING` | `VERIFYING` |
| `TASK_RECOVERING` | `THINKING` |
| `TASK_COMPLETED` | `COMPLETED` |
| `TASK_FAILED` / `ERROR` | `FAILED` |
| `TASK_CANCELLED` | `CANCELLED` |
| `CONFIRMING_ACTION` / `PAUSED_APPROVAL` | `WAITING_FOR_APPROVAL` |
| `SHUTDOWN` | `OFFLINE` |

`TOOL_STARTED` and `STREAM_START` are presentation aliases (`WORKING` and
`TYPING`) over the canonical runtime state. They do not create a second
canonical state machine. `TTS_STARTED` is an overlay and resolves to
`SPEAKING` while active.

The controller also consumes the existing event stream for bounded transient
reactions: tool completion/failure, approval request/resolution, and terminal
completion/failure/cancellation. These reactions do not change canonical state;
they only temporarily adjust expression/eye smile and restore the profile after
their deadline.

## Speech telemetry freshness

`setAudioData({ rawAmp, mid })` computes the bounded envelope
`rawAmp * 0.4 + mid * 0.6`, smooths it, and records `Date.now()` as the last
telemetry time. While `SPEAKING`, telemetry is fresh only when
`Date.now() - lastAudioTime < 300` milliseconds. At 300 ms or later the mouth
target is zero. Silent packets also produce a zero target. There is no timer or
sinusoidal speech fallback in the current controller, despite older documents
describing one.

This is amplitude lip sync, not phoneme or viseme synchronization. `ParamA` is
the default configured lip-sync parameter and is present in Mao's `LipSync`
group.

## Model capabilities

The checked-in evaluation model is Niziiro Mao (Cubism 4), loaded from
`presence_desktop/assets/live2d/models/mao/Mao.model3.json`. Its manifest
provides:

- eight expressions (`exp_01` through `exp_08`);
- `Idle` motions at indices 0–1;
- `TapBody` motions at indices 0–5;
- `ParamA` lip sync and standard head, body, eye, smile, breath, and effect
  parameters used by the controller;
- physics, pose, display metadata, and one texture atlas.

The model contract and licensing details are in
`presence_desktop/assets/live2d/models/MODEL_CONTRACT.md`. A replacement model
must provide compatible parameter IDs, expressions, and motion group/index
entries or its profile mapping must be customized.

## Focused test commands

From `presence_desktop`:

```text
node --test tests/livingBehaviour.test.mjs tests/livingPresenceModel.test.mjs
```

Run the complete dependency-free Node test set with:

```text
node --test tests/*.test.mjs
```

The tests use Node's built-in `node:test` and `node:assert/strict`; no test
dependency or browser harness is required. They control randomness and clock
where those inputs affect determinism through controller/life-layer injection,
and use a small Cubism model boundary double so controller composition can run
headlessly.

## Explicit runtime limitations

- These tests do not prove PixiJS WebGL rendering, texture loading, physics
  evaluation, or visual appearance of the Mao asset.
- They do not prove Python-to-Electron WebSocket delivery or generated TTS
  playback. Those require the Electron runtime and a listening SERA backend.
- Speech is amplitude-only and requires fresh playback telemetry; missing or
  stale packets close the mouth rather than synthesizing movement.
- The controller receives a `delta` from its caller, but the current renderer
  supplies a fixed `0.016` seconds per update. It is not a wall-clock
  scheduler by itself.
- Cubism-authored motion groups can still move parameters in the model runtime;
  the horizontal bound tests cover controller-generated output, not every
  possible authored motion frame. The controller's boundary hook prevents
  uncontrolled accumulation for its owned parameters, but it cannot alter the
  model's authored motion files.
- The implementation is intentionally a small composition module, not a
  general-purpose behavior graph. Unsupported task types retain their canonical
  profile, and only the checked-in event reactions are activated.
