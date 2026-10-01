# SERA Core — Astra Presence Spike

## Design concept: The Cognitive Field

SERA Core is presented as a compact computational field rather than an avatar,
chat panel, or HUD. The Three.js layer now renders a **Cognitive Fold**: an
asymmetric set of folded ribbons, contour threads, and sparse signal points
with a deliberate negative-space aperture. A semantic shell surrounds it with
a sparse field, orbit, readout, and state rail. The system is intentionally
quiet in standby and becomes structurally different as SERA listens, reasons,
acts, verifies, speaks, or needs a decision.

The visual grammar is:

- **Core** — the current computational focus and audio-reactive energy.
- **Orbit** — the shape of the current mode: inward focus, scanning, parallel
  reasoning, outward execution, verification loop, approval hold, or fracture.
- **Field** — low-opacity context signals and nodes; a living system without
  decorative particle noise.
- **Readout** — a small operational index, not a dashboard.
- **Conversation drawer** — only the active utterance/result, revealed on
  activity and collapsed when the system returns to standby.

The palette uses cyan/blue for perception and voice, violet for cognition,
amber for action and attention, green for verification/completion, and rose for
failure. Color reinforces changes in movement and geometry; it does not carry
state alone.

## State-to-visual mapping

| Runtime state | Visual behavior | User meaning |
| --- | --- | --- |
| `IDLE` | Slow breathing orbit, sparse field | Ambient perception / ready |
| `LISTENING` | Orbit contracts and stabilizes | Voice channel is open |
| `TRANSCRIBING` | Orbit scans continuously | Speech is becoming context |
| `THINKING` / `PLANNING` | Counter-rotating reasoning orbit | SERA is finding a path |
| `EXECUTING` | Tilted, expanded, high-energy orbit | Desktop action is in motion |
| `VERIFYING` | Dashed orbit and verification sweep | Result is being checked |
| `WAITING_FOR_APPROVAL` | Held vertical orbit / amber attention | The user must decide |
| `SPEAKING` | Existing core responds to TTS bands | SERA is returning context |
| `COMPLETED` | Ivory/teal convergence and structural lock | Result verified |
| `FAILED` | Fractured rose orbit and anomaly state | Execution did not verify |
| `CANCELLED` | Implosion and quiet retraction | Action was stopped |

## Integration architecture

`SERAUIServer` remains the source of runtime events over the existing WebSocket
contract. `PresenceApp` remains the event integration boundary. The new
`src/ui/presentationState.js` module is a pure presentation adapter: it maps
authoritative runtime states/events to stable labels, tones, indexes, and DOM
attributes. It does not create or transition backend states.

The flow is:

```text
runtime EventBus → SERAUIServer WebSocket → PresenceApp
  → PresenceEngine / PresenceBehaviorEngine
  → presentationState view model → semantic DOM shell + Three.js behavior
```

Approval is reserved through the real `SECURITY_CONFIRMATION_REQUIRED` event;
this spike exposes the visual waiting state and current action context but does
not implement permission decisions.

## Performance and extension notes

- The new shell uses CSS transforms/opacity and a few DOM nodes; it does not
  add a second canvas or particle simulation.
- Three.js uses a capped device pixel ratio, bounded ribbon/thread buffers, and
  resize observation so DPI changes do not silently increase GPU cost.
- `prefers-reduced-motion` disables the semantic shell's motion.
- Future Hermes activity, task progress, evidence, and approval actions can
  populate the existing task context/readout without coupling the renderer to
  Hermes internals.
- The Electron window is now resizable within sane minimum bounds; the layout
  uses viewport clamps and a compact-height breakpoint.
