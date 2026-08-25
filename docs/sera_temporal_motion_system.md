# SERA 1.0 — Temporal Motion & Animation System

## 1. System Architecture
The Temporal Motion Engine is a multi-layered rendering pipeline designed to reflect real-time computational flow without imposing CPU/GPU overhead on runtime execution.

```
┌──────────────────────────────────────────────────────────┐
│ LAYER 4: STATE FX (Aura blooms, fractures, ripples)      │
├──────────────────────────────────────────────────────────┤
│ LAYER 3: RUNTIME ENERGY (Event-driven pulses & trails)   │
├──────────────────────────────────────────────────────────┤
│ LAYER 2: WORKFLOW GRAPH (2D node graph & conduits)       │
├──────────────────────────────────────────────────────────┤
│ LAYER 1: BACKGROUND FIELD (Drifting strands & particles) │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Layer Definitions

### Layer 1: Background Temporal Field
- **Visuals:** 24-36 randomized Bézier curves representing dimensional energy strands drifting horizontally at 0.05-0.15 px/frame.
- **Atmosphere:** Depth blur with radial luminescence radiating from active nodes.
- **Performance:** Rendered via hardware-accelerated HTML5 Canvas with dirty-region clipping or low-overhead CSS keyframe matrices.

### Layer 2: 2D Spatial Graph & Temporal Corridors
- **Conduits:** Thick energy conduits connecting execution steps.
- **State Styling:**
  - `WAITING`: Dim slate line (`#1E2235`).
  - `ACTIVE`: Luminous glowing beam matching domain color.
  - `COMPLETED`: Soft neon trace.
  - `FALLBACK`: Secondary route ignited on primary failure.

### Layer 3: Runtime Energy Pulses
- **Trigger:** Generated exclusively upon WebSocket telemetry events:
  - `MODEL_SELECTED`: High-speed energy packet launched toward the chosen model node.
  - `TOOL_STARTED`: Amber pulse flowing into the selected tool.
  - `TOOL_COMPLETED`: Radial expansion burst at the tool output port.
  - `VISION_STARTED`: Purple wave propagating across vision nodes.
  - `TTS_STARTED`: Gold resonance waveform.

### Layer 4: State FX & Terminal Transitions
- `COMPLETED`: A gentle radial cyan/gold ripple expanding across the canvas.
- `BROKEN`: A crimson temporal fracture splitting the conduit with particle scatter.
- `CANCELLED`: Smooth conduit collapse pulling back to origin.
- `RATE_LIMITED`: Amber pulsing cooldown ring on model node.

---

## 3. Quality Profiles & Accessibility
- **Profiles:**
  - `LOW`: Static conduits, zero background particles, 30fps CSS transitions.
  - `MEDIUM`: Standard conduit glow, 12 background strands, 60fps animations.
  - `HIGH` (Default): Full 3-layer motion system, particle pooling, energy trails.
  - `CINEMATIC`: Expanded bloom filters, chromatic dispersion, volumetric depth blur.
- **Accessibility:** Fully honors `prefers-reduced-motion: reduce` by disabling ambient drifting and replacing particle pulses with instantaneous color highlights.
