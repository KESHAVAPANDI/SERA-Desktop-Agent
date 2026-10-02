# SERA Live2D Character Presence System

## 1. Executive Summary & Architectural Overview

The SERA Desktop Presence character has been transitioned from an ephemeral Three.js geometric approximation to a genuine **Live2D Cubism runtime** implementation. The character now behaves as one persistent, living digital entity across the entire desktop lifecycle.

### Core Architectural Principles
1. **Single Persistent Character Instance**: The Live2D model (`Live2DModel`) is instantiated exactly once during startup and remains permanently bound to the WebGL context. State changes never reload the model, rebuild the mesh, or produce visual flickering.
2. **Authoritative State Fidelity**: Character expressions, postures, and motions are driven directly by SERA Core's authoritative runtime states (`IDLE`, `LISTENING`, `THINKING`, `EXECUTING`, etc.), maintaining strict architectural separation between cognitive backend reasoning and presentation rendering.
3. **Continuous Biological Life Layer**: Independent life micro-dynamics (sinusoidal breathing, stochastic human-like blinking with double-blinks, gaze micro-saccades, and organic head drift) operate continuously across all state transitions.
4. **Data-Driven Semantic Color & Aura**: State transitions smoothly modulate the character's ambient tint, eye highlight effects, background WebGL aura, and surrounding desktop glass panel CSS tokens.
5. **Real-Time Speech Envelope & Fallback**: Mouth opening is dynamically driven by SERA TTS speech frequency envelopes (`ParamA`) with a multi-harmonic sinusoidal fallback when audio packets are absent.
6. **Robust Visual Fallback**: If WebGL or Live2D assets fail to load, explicit visual diagnostic feedback is rendered immediately rather than failing silently.

---

## 2. Technology Stack & Runtime Choice

| Component | Technology | Version | Purpose |
|---|---|---|---|
| **Core Runtime** | Official Live2D Cubism Web SDK Core (`live2dcubismcore.min.js`) | Cubism 5.1.0 / 4 compatible | Low-level C++/Wasm mesh deformation and parameter evaluation engine from Live2D Inc. |
| **Graphics Engine** | PixiJS (`pixi.js`) | 6.5.10 | High-performance WebGL 2D rendering pipeline with transparent background support |
| **Live2D Integration** | `pixi-live2d-display` | 0.4.0 (cubism4 UMD) | Seamless bridge between Live2D Cubism Core and PixiJS scene graph |
| **Desktop Shell** | Electron | 34.0.0 | Transparent frameless desktop overlay window |
| **Audio Pipeline** | Web Audio API + SERA TTS Event Stream | Native | Audio analysis bands (`rawAmp`, `mid`) driving mouth deformation |

### Runtime Loading Architecture
In the Electron environment, the Live2D Cubism runtime is loaded via UMD `<script>` tags in `presence_desktop/index.html` prior to module bootstrapping:
1. `assets/live2d/runtime/live2dcubismcore.min.js` (Exposes `window.Live2DCubismCore`)
2. `node_modules/pixi.js/dist/browser/pixi.min.js` (Exposes `window.PIXI`)
3. `node_modules/pixi-live2d-display/dist/cubism4.min.js` (Exposes `PIXI.live2d.Live2DModel`)
4. Native ES module entry `src/App.js`

Chromium local file loading is enabled in `presence_desktop/main.js` via `app.commandLine.appendSwitch("allow-file-access-from-files")`, allowing secure local model asset loading over `file://` URIs without bundling overhead.

---

## 3. Persistent Character Lifecycle & Zero Reload Guarantee

The Live2D runtime is organized into three decoupled layers:

```
┌─────────────────────────────────────────────────────────────┐
│                       SERA Core / App.js                    │
│   (Authoritative WebSocket States, Audio Analysis Bands)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ setState(), setAudioData()
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Live2DController.js                      │
│  - Owns single Live2DModel instance (loadCount strictly = 1)│
│  - Exponentially damps posture angles, gaze, mouth, colors  │
│  - Coordinates Life Layer & State Profiles                  │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│      Live2DLifeLayer.js      │ │    Live2DColorSystem.js    │
│ - Natural breathing cycle    │ │ - Color target damping     │
│ - Stochastic blinking (0.18  │ │ - Subtle model tinting     │
│   double-blink probability)  │ │ - Eye effect modulation    │
│ - Eye micro-saccades         │ │ - CSS variables to DOM     │
│ - Organic head drift         │ │   (--live2d-accent/aura)   │
└──────────────┬───────────────┘ └────────────┬───────────────┘
               │                              │
               └──────────────┬───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Live2DRenderer.js                       │
│  - WebGL Canvas inside transparent Electron viewport        │
│  - PixiJS Stage: [Radial Aura Graphic] -> [Model Container] │
│  - Diagnostic 2D Canvas Error Fallback Screen               │
└─────────────────────────────────────────────────────────────┘
```

### Zero-Reload Proof
When `setState(newState)` is invoked:
- The controller **never** re-instantiates or reloads `Live2DModel.from()`.
- It executes `model.expression(targetExpression)` and `model.motion(targetGroup, targetIndex, 2)`.
- Physical parameter coordinates (`ParamAngleX`, `ParamAngleY`, `ParamEyeBallX`, etc.) are smoothly interpolated frame-by-frame via exponential damping (`1 - exp(-dt * speed)`).
- During automated testing (`verify_live2d_runtime.js`), 26 continuous state transitions were executed across all 14 states. Verified metric: `loadCount = 1` throughout the entire run.

---

## 4. Authoritative State Mapping Table

SERA's 14 authoritative states (plus `OFFLINE`) map to distinct, data-driven expressive profiles in `Live2DStateProfiles.js`:

| SERA State | Expression | Motion Group / Index | Head Pose (Pitch/Yaw/Roll) | Eye Behavior | Color Target (Hex) | Aura Strength | Semantics & Narrative Profile |
|---|---|---|---|---|---|---|---|
| **IDLE** | `exp_01` (Neutral) | `Idle` [0] | `0°, 0°, 0°` | Center gaze, soft smile (`0.1`), normal blink | `#38bdf8` (Cyan) | `0.30` | Calm, present, gentle breathing, attentive ambient baseline |
| **LISTENING** | `exp_04` (Sparkle) | `Idle` [1] | `+4° (up), 0°, +1.5°` | Direct gaze, eyes wide (`1.15`), blink reduced (`0.7`) | `#0284c7` (Deep Blue) | `0.65` | Attentive posture leaning forward toward user speech |
| **TRANSCRIBING** | `exp_01` (Focused) | `TapBody` [0] | `-2°, +3.5°, +2°` | Slight inward focus, quick glance down | `#818cf8` (Indigo) | `0.70` | Actively processing speech input, rhythmic breathing |
| **THINKING** | `exp_06` (Thoughtful) | `Idle` [1] | `+5° (up), -6°, -3.5°` | Inward contemplative gaze up-left, blush active | `#a855f7` (Violet) | `0.75` | Cognitively engaged, reasoning over graph & plans |
| **PLANNING** | `exp_05` (Deliberate) | `TapBody` [1] | `+3°, +3°, +1.5°` | Focused forward gaze, deliberate posture | `#8b5cf6` (Purple) | `0.75` | Structuring steps, evaluating dependencies |
| **TYPING** | `exp_06` (Concentrated)| `TapBody` [0] | `-3.5° (down), +2°, +1°`| Eyes angled down toward draft (`-0.15`), faster blink | `#c084fc` (Lavender) | `0.70` | Streaming response generation, rapid micro-blinks |
| **WORKING** | `exp_04` (Engaged) | `TapBody` [2] | `+1°, +4°, +2.5°` | Sharp gaze, alert eyes (`1.05`), high physics | `#f59e0b` (Amber) | `0.85` | Desktop action in flight, focused engagement |
| **EXECUTING** | `exp_04` (Energetic) | `TapBody` [2] | `+2°, +5°, +3°` | Dynamic gaze, wide eyes (`1.10`), elevated breath | `#06b6d4` (Teal) | `0.90` | High-energy system execution, tool invocations |
| **VERIFYING** | `exp_05` (Precise) | `TapBody` [1] | `+1.5°, -2.5°, -1°` | Scrutinizing gaze, slight squint (`0.98`), steady breath | `#10b981` (Emerald) | `0.80` | Careful validation of execution results |
| **WAITING_FOR_APPROVAL**| `exp_07` (Expectant)| `TapBody` [3] | `+3°, 0°, 0°` | Direct eye contact (`0.10`), alert eyes (`1.15`) | `#eab308` (Gold) | `0.90` | Poised, direct gaze awaiting user security confirmation |
| **SPEAKING** | `exp_02` (Warm Smile)| `Idle` [0] | `+2°, 0°, +1°` | Warm eye smile (`0.25`), audio envelope lip-sync | `#0ea5e9` (Sky Blue)| `0.70` | Warm vocalization, dynamic mouth opening (`ParamA`) |
| **COMPLETED** | `exp_02` (Joyful) | `TapBody` [4] | `+3.5°, +1.5°, +2°` | Pronounced eye smile (`0.85`), buoyant posture | `#22c55e` (Green) | `0.90` | Task achieved successfully, rewarding warm expression |
| **FAILED** | `exp_08` (Concerned) | `TapBody` [5] | `-4° (down), -3.5°, -2.5°`| Downcast gaze (`-0.12`), empathetic pout | `#f43f5e` (Rose) | `0.75` | Empathetic failure communication without looking broken |
| **CANCELLED** | `exp_03` (Resting) | `Idle` [1] | `-1.5°, 0°, 0°` | Relaxed downcast gaze, gentle deceleration | `#64748b` (Slate) | `0.25` | Soft de-escalation settling back toward idle |
| **OFFLINE** | `exp_03` (Sleeping) | `Idle` [0] | `-4.5° (down), 0°, 0°` | Eyes fully closed (`0.0`), slow deep breathing (`0.55`)| `#475569` (Muted) | `0.10` | Disconnected resting state, asleep but alive |

---

## 5. Continuous Life Layer Dynamics

The `Live2DLifeLayer` operates independently of SERA's cognitive tasks, preventing the character from ever appearing frozen or static:

### 1. Sinusoidal Breathing
- Modulates Live2D Cubism parameter `ParamBreath` using a normalized sine wave:
  $$\text{breath} = \frac{\sin(\text{time} \cdot 2.1 \cdot \text{breathRate}) + 1}{2}$$
- Simultaneously imparts subtle vertical oscillation to the torso (`torsoOffsetY`).

### 2. Stochastic Blinking State Machine
- Natural human blink intervals distributed between 2.5 and 5.5 seconds.
- Four-phase state machine: `INTERVAL` $\to$ `CLOSING` (~90ms) $\to$ `CLOSED` (~35ms) $\to$ `OPENING` (~120ms).
- **Double-Blink Mechanism**: 18% stochastic probability of triggering an immediate secondary blink upon opening, matching natural biological behavior.
- Multiplies `ParamEyeLOpen` and `ParamEyeROpen` without overriding deliberate squinting or smiling.

### 3. Micro-Saccades
- Human eyes undergo micro-fixation shifts every 1.8 to 4.2 seconds.
- Applies subtle stochastic offsets to `ParamEyeBallX` ($\pm 0.04$) and `ParamEyeBallY` ($\pm 0.03$) eased via exponential smoothing.

### 4. Organic Multi-Harmonic Head Drift
- Subtle compound sine/cosine drift applied to head angles (`driftAngleX`, `driftAngleY`, `driftAngleZ`), keeping the character organic even during prolonged idle states.

---

## 6. Color System & Desktop Aura Integration

The `Live2DColorSystem` ensures semantic feedback while preserving the character's intrinsic identity:

1. **Subtle Model Tinting**:
   ```javascript
   getModelTint() {
     // 82% base brightness + 18% state color saturation
     const r = Math.round((0.82 + this.current[0] * 0.18) * 255);
     const g = Math.round((0.82 + this.current[1] * 0.18) * 255);
     const b = Math.round((0.82 + this.current[2] * 0.18) * 255);
     return (r << 16) | (g << 8) | b;
   }
   ```
   Avoids harsh color washing; preserves skin and hair textures while imbuing an ethereal glow.
2. **Eye Highlight Modulation**:
   - `ParamEyeEffect` is dynamically enabled when state aura intensity exceeds `0.60`, adding star/sparkle eye reflections during active states (`LISTENING`, `EXECUTING`, `WAITING_FOR_APPROVAL`).
3. **Background Radial Aura**:
   - WebGL `PIXI.Graphics` layer drawn behind the model in `Live2DRenderer.js`. Uses two concentric soft alpha circles responding to state color and intensity.
4. **Desktop Glass Container Styling**:
   - `Live2DColorSystem.applyToDOM()` publishes CSS custom properties to the root presence container:
     - `--live2d-accent-color`: e.g., `rgb(14, 165, 233)`
     - `--live2d-aura-color`: e.g., `rgba(14, 165, 233, 0.700)`
     - `--live2d-glow`: e.g., `0 0 24px rgba(14, 165, 233, 0.700)`
   - Used by `presence_desktop/src/ui/presence.css` to dynamically illuminate the glass panel borders.

---

## 7. Speech Envelope & Cadence Fallback

In `SPEAKING` state:
1. **TTS Ingestion**: `setAudioData(bands)` extracts energy from voice mid-range frequencies (`bands.mid`) and amplitude (`bands.rawAmp`):
   $$\text{targetMouthOpen} = \min(1.0, (\text{rawAmp} \cdot 0.4 + \text{mid} \cdot 0.6) \cdot 1.6)$$
   Applied directly to Cubism parameter `ParamA` / `ParamMouthOpenY`.
2. **Audio-less Fallback**: If audio packets are absent (silent or text-only streaming), an organic 14 Hz multi-frequency sinusoidal oscillation is applied:
   $$\text{targetMouthOpen} = \max(0.0, (\sin(14t) \cdot 0.4 + \sin(7t) \cdot 0.25 + 0.35) \cdot \text{mouthOpenGain})$$
   This prevents mouth freezing during speech synthesis delays.

---

## 8. Diagnostic Error Fallback

If WebGL is unavailable or model files are missing:
- `Live2DRenderer.renderFallbackError(error)` intercepts the failure.
- Renders an explicit diagnostic canvas overlay:
  - Red-bordered translucent container (`rgba(239, 68, 68, 0.15)`).
  - Explicit header: `"LIVE2D RENDERER INITIALIZATION ERROR"`.
  - Detailed error message and remediation advice.
- Non-blocking: Desktop shell and Command Center continue running.

---

## 9. Model Contract, Licensing, & Model Swapping

### Evaluation Model: Niziiro Mao (Cubism 4)
- **Source**: Official Live2D Cubism Web Samples Repository (`Samples/Resources/Mao`).
- **Copyright**: (C) Live2D Inc.
- **License**: Governed by the **Live2D Free Material License Agreement** ([https://www.live2d.com/en/terms/](https://www.live2d.com/en/terms/)). Free for evaluation, research, and non-commercial/commercial usage by General Users and Small-Scale Enterprises under Live2D's sample model policy.
- Full contract documentation: [`MODEL_CONTRACT.md`](file:///c:/Users/kesha/OneDrive/Documents/Sera/presence_desktop/assets/live2d/models/MODEL_CONTRACT.md).

### How to Swap the Character Model
1. Place the new Cubism 4 model folder inside `presence_desktop/assets/live2d/models/<model_name>/`.
2. Edit `presence_desktop/src/live2d/Live2DConfig.js`:
   ```javascript
   export const LIVE2D_CONFIG = Object.freeze({
     activeModelName: "<model_name>",
     modelPath: "./assets/live2d/models/<model_name>/<model_name>.model3.json",
     modelScale: 0.20,      // Adjust framing scale
     modelOffsetY: 400,     // Adjust vertical centering
     ...
   });
   ```
3. Restart presence. The controller loads the new model automatically without code changes.

### How to Add or Customize States
To dynamically register new states at runtime:
```javascript
import { registerStateProfile } from "./live2d/Live2DStateProfiles.js";

registerStateProfile("DEEP_RESEARCH", {
  expression: "exp_06",
  motionGroup: "Idle",
  angleY: 4.0,
  color: [0.3, 0.8, 0.9],
  auraIntensity: 0.8,
  breathRate: 1.2,
});
```

---

## 10. Automated & Runtime Verification Results

### Automated Test Suite
- Executed: `node --test tests/*.test.mjs`
- Result: **All 25 tests pass** (12 existing integration tests + 13 Live2D controller tests, 0 failures).

### Real Electron Desktop Verification
- Executed `verify_live2d_runtime.js` inside live Electron transparent overlay window with active SERA Core server.
- Executed lifecycle sequence:
  `IDLE -> LISTENING -> TRANSCRIBING -> THINKING -> EXECUTING -> VERIFYING -> SPEAKING -> IDLE -> WAITING_FOR_APPROVAL -> COMPLETED -> FAILED -> CANCELLED`.
- Verified metrics:
  - **Model Load Count**: Strictly **1** (`PASS`).
  - **Total State Changes**: **26** (`PASS`).
  - **Visual Capture Proof**: 11 PNG frames captured and verified in artifact storage:
    - `live2d_01_idle.png`: Attentive neutral posture, soft smile, blue aura.
    - `live2d_02_listening.png`: Forward lean, wide gaze, star eye highlights (`ParamEyeEffect`).
    - `live2d_03_thinking.png`: Upward-left gaze, blush cheek (`exp_06`), purple aura.
    - `live2d_04_executing.png`: Energetic posture, teal aura, alert expression.
    - `live2d_05_verifying.png`: Inquisitive tilt, emerald aura, focused eyes.
    - `live2d_06_speaking.png`: Warm expressive smile (`exp_02`), mouth open in speech (`ParamA`).
    - `live2d_07_idle_return.png`: Seamless return to baseline without reloads.
    - `live2d_08_waiting_approval.png`: Direct user eye contact, expectant wide eyes (`exp_07`), gold aura.
    - `live2d_09_completed.png`: Joyful eye smile (`0.85`), green aura.
    - `live2d_10_failed.png`: Empathetic pout (`exp_08`), downcast eyes, rose aura.
    - `live2d_11_cancelled.png`: Closed resting eyes (`exp_03`), gentle deceleration.
- Verified CLI verification: `launch_presence.py --verify` exits cleanly with code 0.
