# SERA 2.0 — Visual System & Motion Language Specification

> **Aesthetic Directive:** Raphael-Like Computational Consciousness  
> **Target Fidelity:** High-End WebGL / GPGPU Shader System / Swiss Typographic Grid  
> **Guiding Principle:** Every motion communicates state, direction, attention, progress, or transformation. Zero decorative noise.

---

## 1. Color System: Celestial Computational Palette

The SERA 2.0 palette rejects generic cyber-neon clichés in favor of a curated, high-dynamic-range spectrum rooted in analytical energy and celestial computing.

```
┌─────────────────┬───────────┬────────────────────────────────────────────────────────┐
│ Role            │ Hex Token │ Description & Visual Function                          │
├─────────────────┼───────────┼────────────────────────────────────────────────────────┤
│ Void Core       │ #050811   │ Deepest chromatic black-indigo background anchor       │
│ Surface Slate   │ #0B1120   │ Secondary Command Center surface / panel canvas        │
│ High Luminous   │ #00F0FF   │ Peak cyan analytical energy; primary ring geometry     │
│ Celestial Cyan  │ #38BDF8   │ Particle trails, active focus states, verified steps   │
│ Core Hotspot    │ #FFFFFF   │ High-energy computational singularity in core center   │
│ Transcendence   │ #F43F5E   │ Vivid rose/magenta accent; state change & alert flare  │
│ Energy Gold     │ #F59E0B   │ System pause, quota warning, or user attention needed  │
│ Terminal Muted  │ #64748B   │ Monospaced metadata, inactive steps, coordinates       │
│ Pure White      │ #F8FAFC   │ Primary high-contrast typography                       │
└─────────────────┴───────────┴────────────────────────────────────────────────────────┘
```

### CSS Design Tokens
```css
:root {
  /* Core Energy Tokens */
  --sera-core-white: #ffffff;
  --sera-cyan-glow: #00f0ff;
  --sera-cyan-mid: #0284c7;
  --sera-cyan-deep: #0369a1;
  --sera-magenta-accent: #f43f5e;
  --sera-gold-accent: #f59e0b;
  
  /* Surface & Canvas Tokens */
  --sera-bg-void: #050811;
  --sera-surface-0: rgba(11, 17, 32, 0.75);
  --sera-surface-1: rgba(15, 23, 42, 0.65);
  --sera-border-subtle: rgba(56, 189, 248, 0.15);
  --sera-border-active: rgba(0, 240, 255, 0.5);

  /* Typography */
  --sera-text-primary: #f8fafc;
  --sera-text-secondary: #94a3b8;
  --sera-text-muted: #64748b;
  --sera-font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --sera-font-mono: 'Space Mono', 'JetBrains Mono', monospace;
}
```

---

## 2. Typography Hierarchy

Typographical discipline is modeled on high-density developer consoles and Swiss precision:

```
[ DISPLAY / STATUS ]     Space Mono (400) / 14px / Tracking +0.12em / Uppercase
                         "ANALYZING RUNTIME PERCEPTION..."

[ OBJECTIVE TITLE ]      Inter (600) / 20px / Tracking -0.02em / White
                         "Search YouTube for RTX 5090 Benchmarks"

[ STEP LABEL ]           Inter (400) / 14px / Leading 1.5
                         "Filter sponsored ad results and verify domains"

[ CODE & METADATA ]      JetBrains Mono (400) / 12px / Muted Slate
                         "pid: 19402 · mem: 142MB · latency: 284ms"
```

* **No Chat Accumulation:** The primary floating presence never renders conversation history. It renders only the **current active status line**, morphing between states.

---

## 3. Primary Visual Core: The Wisdom King Engine

The core is rendered on a dedicated WebGL canvas with `alpha: true`. It is a dynamic, mathematically driven computational manifestation.

```
                    ┌─── Outer Glyph Ring (Radius 120px) ───┐
                    │    Variable angular spin, fine ticks  │
                    │                                       │
                    │   ┌── Mid Analytical Ring (90px) ──┐  │
                    │   │   Counter-rotates, step-locked  │  │
                    │   │                                 │  │
                    │   │   ┌── Inner Ring (60px) ──┐     │  │
                    │   │   │   Frequency modulated │     │  │
                    │   │   │                       │     │  │
                    │   │   │    ✦ Luminous Core ✦  │     │  │
                    │   │   │    (White Singularity)│     │  │
                    │   │   └───────────────────────┘     │  │
                    │   └─────────────────────────────────┘  │
                    └────────────────────────────────────────┘
                       * * · · Orbiting GPGPU Particles · · * *
```

### Components of the Core:
1. **The Singularity Core:**
   - Central luminous sphere with dual-color radial falloff (`#FFFFFF` -> `#00F0FF` -> transparent).
   - Shader pulsates with gentle procedural sine wave at resting rate (0.2 Hz).
2. **Concentric Analytical Rings:**
   - 3 to 5 concentric geometric circles rendered with sub-pixel line precision (1px - 1.5px stroke).
   - Outer Ring: Segmented arc geometry with micro-graduations (12 major divisions, 60 minor ticks).
   - Middle Ring: Elliptical inclination (rotated on X/Y axes by 15° to 35°) creating dimensional depth.
   - Inner Ring: Rapid responsive rotation that accelerates upon state transitions.
3. **GPGPU Curl-Noise Particle Swarm:**
   - 15,000 GPU-computed points managed via ping-pong render targets.
   - Controlled by 3 velocity fields:
     - `F_curl`: Divergence-free curl noise creating organic ethereal turbulence.
     - `F_attractor`: Central gravitational vector pulling particles inward or pushing outward.
     - `F_orbital`: Tangential velocity driving orbital planetary flow.

---

## 4. State Visual Language: 9 Behavioral Modes

Every system state fundamentally shifts the physical laws governing the computational core:

```
+---------------+---------------------+--------------------+--------------------+
| System State  | Geometric Rings     | Particle Behavior  | Color & Energy     |
+---------------+---------------------+--------------------+--------------------+
| 1. IDLE       | Slow harmonic spin  | Drift lazily in    | Calming cyan/azure |
|               | (0.1 rad/s)         | calm orbital torus | gentle breathing   |
+---------------+---------------------+--------------------+--------------------+
| 2. LISTENING  | Contract inward by  | Particles pulled   | Cyan brightens to  |
|               | 20%; stabilize axis | tightly to center  | electric white-blue|
+---------------+---------------------+--------------------+--------------------+
| 3. TRANSCRIB- | Segment into        | Micro-particles    | Cyan with rapid    |
|    ING        | vertical/horizontal | form glyph-like    | horizontal white   |
|               | coordinate ticks    | matrix arrays      | scanline flashes   |
+---------------+---------------------+--------------------+--------------------+
| 4. THINKING   | Split into parallel | Accelerated motion | Concentric rings   |
|               | intersecting planes | along dual spirals | pulse magenta/cyan |
+---------------+---------------------+--------------------+--------------------+
| 5. EXECUTING  | Expand diameter;    | Project outward    | Luminous cyan rays |
|               | high-speed rotation | as fine filaments  | with sharp focus   |
+---------------+---------------------+--------------------+--------------------+
| 6. SPEAKING   | Harmonic expansion  | Ripple outwards as | Radiant waves,     |
|               | matching audio RMS  | acoustic wave rings| soft bloom aura    |
+---------------+---------------------+--------------------+--------------------+
| 7. BROKEN     | Jitter & temporary  | Scatter erratically| Cyan fractures to  |
|               | angular disconnect  | with high friction | amber/crimson haze |
+---------------+---------------------+--------------------+--------------------+
| 8. CANCELLED  | Abrupt snap &       | Rapid implosion to | Sudden flash,      |
|               | collapse inward     | zero radius        | dissipating trail  |
+---------------+---------------------+--------------------+--------------------+
| 9. COMPLETED  | Harmonic lock &     | CELLULAR RECONSTR. | Brilliant white/   |
|   (Signature) | crystalline rebuild | particles snap ->  | magenta flash into |
|               | into pristine rings | cells -> stability | tranquil idle cyan |
+---------------+---------------------+--------------------+--------------------+
```

---

## 5. Signature Completion Animation: Computational Cellular Reconstruction

The transition from `EXECUTING` to `COMPLETED` represents SERA's signature completion gesture:

```
[ PHASE 1: FRAGMENTATION ] (0ms - 200ms)
Filaments break into discrete particle clusters as execution finishes.

[ PHASE 2: CONVERGENCE ] (200ms - 500ms)
Central gravitational attractor increases by 5x. 
Particles accelerate from the outer perimeter toward mathematical centroid.

[ PHASE 3: CELLULAR NUCLEATION ] (500ms - 850ms)
Nearby particles link via procedural distance thresholds (< 8px).
Micro-geometric hexagonal cells form in mid-air.

[ PHASE 4: STRUCTURAL RECONSTRUCTION ] (850ms - 1200ms)
Cells snap into concentric circular tracks. 
Fine structural vector lines draw themselves around the perimeter.

[ PHASE 5: HARMONIC FLASH & LOCK ] (1200ms - 1500ms)
A subtle, pristine white-magenta lens flash pings across the outer ring.
Motion dampens smoothly into the slow 0.1 rad/s Idle breathing state.
```

---

## 6. Minimal Status Text & Morphing Transitions

Directly beneath the primary core (offset by +140px on Y), single status notifications render with elegant kinetic typography:

```
           [ WISDOM KING VISUAL CORE ]
                       │
                       │ (+140px)
                       ▼
           ┌───────────────────────┐
           │      ANALYZING...     │
           └───────────────────────┘
```

### Kinetic Animation Rules:
- **Duration:** 240ms enter / 180ms exit.
- **Easing:** `cubic-bezier(0.16, 1, 0.3, 1)` (smooth deceleration).
- **Exit Motion:** Fades out with slight upward translate (`translateY(-4px)`), blur increases from 0px to 4px.
- **Enter Motion:** Enters from `translateY(4px)`, blur clears from 4px to 0px, letter-spacing expands from 0.05em to 0.12em.
- **No Text Stacking:** Status lines never form a multi-line conversation thread in primary mode. Only the latest operational state exists.

---

## 7. Secondary Command Center Living Background

Unlike flat dashboards with static dark backgrounds, Body 2 features a GPU-accelerated **Living Canvas**:
- **Layer 1: Deep Chromatic Foundation**
  - Dark radial gradient from `#0A1325` (center top) to `#050811` (edges).
- **Layer 2: Living Procedural Noise & Slow Flow**
  - Ultra-low opacity canvas shader (opacity 0.025).
  - Slow Simplex noise deformation creating the sensation of tranquil computational depth.
- **Layer 3: Ambient Energy Bloom**
  - Soft, blurred radial light pools positioned beneath active task execution panels.
  - When a task runs, the ambient glow warms slightly toward active cyan; when completed, it emits a subtle celebratory harmonic pulse.
- **Zero Competition:** The background strictly adheres to luminance < 0.05 to ensure all foreground data, charts, and text maintain maximum clarity and legibility.
