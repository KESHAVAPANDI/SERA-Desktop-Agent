# SERA 1.0 UI Design System & Temporal Aura Tokens

## 1. Design Philosophy

- **Aesthetic**: Futuristic AI Operating System / Sci-Fi Command Center.
- **Mood**: Dark, cinematic, deep, sophisticated, technical without developer clutter.
- **Visual Metaphor**: Temporal Aura — Flowing horizontal timelines, branching energy lines, purposeful halos, and particle trajectories.

---

## 2. Color Palette & Tokens

### Background & Surface Hierarchy
- `--bg-primary`: `#06080D` (Deep void black)
- `--bg-secondary`: `#0C1019` (Elevated command deck)
- `--bg-card`: `#121826` (Floating technical card)
- `--bg-card-hover`: `#182236`
- `--border-subtle`: `rgba(255, 255, 255, 0.07)`
- `--border-active`: `rgba(0, 240, 255, 0.35)`
- `--border-glow`: `0 0 16px rgba(0, 240, 255, 0.2)`

### Temporal Energy Accents
- `--accent-cyan`: `#00F0FF` (Primary Temporal Flow / Active Node)
- `--accent-violet`: `#8A2BE2` (Reasoning & Cognition)
- `--accent-emerald`: `#00E599` (Healthy / Success / Verified)
- `--accent-amber`: `#FFB800` (Rate Limited / Cooldown / Warning)
- `--accent-crimson`: `#FF3366` (Error / Unbilled / Disconnected)
- `--accent-magenta`: `#FF007F` (Multi-Agent Synthesizer)

### Typography Colors
- `--text-primary`: `#F0F4FC` (High-contrast crisp white)
- `--text-secondary`: `#94A3B8` (Technical slate)
- `--text-muted`: `#475569` (Subdued metadata)
- `--text-accent`: `#00F0FF` (Glowing highlight)

---

## 3. State Aura Behaviors

| Runtime State | Visual Halo / Glow | Animation Signature |
|:---|:---|:---|
| **IDLE** | Subtle Cyan (`0 0 12px rgba(0, 240, 255, 0.15)`) | 4s harmonic breathing pulse |
| **LISTENING** | Expanding Amber Ring (`0 0 24px rgba(255, 184, 0, 0.4)`) | Dynamic acoustic ring expansion |
| **TRANSCRIBING** | Shifting Violet/Cyan gradient | High-speed lateral shimmer |
| **THINKING** | Rotating Dual Orbital Rings | Clockwise 2.5s orbital revolution |
| **EXECUTING** | Pulsing Emerald Flow (`0 0 20px rgba(0, 229, 153, 0.4)`) | Active particle stream through graph nodes |
| **SPEAKING** | Reactive Audio Waveform Aura | Sound-reactive frequency amplitude |
| **ERROR** | Crimson Distort (`0 0 22px rgba(255, 51, 102, 0.45)`) | Single 200ms shudder, then static warning |

---

## 4. Typography Rules

- **Headings & Brand**: `Outfit`, `Inter`, sans-serif (Clean geometric, 500-700 weight).
- **Body & Dialogue**: `Inter`, system-ui (Crisp readability, 400-500 weight).
- **Telemetry & Code**: `JetBrains Mono`, `Fira Code`, monospace (Fixed width, 400-600 weight).

---

## 5. Reusable Component Primitives

1. **Temporal Node**: Horizontal graph step node with glowing status pip, title, model label, and latency metric.
2. **Branching Edge**: SVG cubic bezier connecting parent to primary/fallback nodes with animated particle flow.
3. **Provider Health Pill**: Compact badge with colored LED dot (`HEALTHY`, `RATE_LIMITED`, `UNAVAILABLE`, `AUTH_ERROR`).
4. **Quota Meter Bar**: Multi-tiered progress gauge (requests, tokens, RPM) with reset timer countdown.
5. **Agent Card**: Stylized card showcasing agent name, avatar icon, assigned model, active tool, and status.
6. **Session Timeline Card**: Chronological history card displaying turn summary, execution duration, and replay trigger.
