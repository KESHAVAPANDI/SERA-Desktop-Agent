const pearl = 0xe7f2ed;
const seaGlass = 0x79b7aa;
const deepTeal = 0x285f5b;
const lilac = 0xa89bc0;
const amber = 0xd3a45f;
const coral = 0xc56d67;
const slate = 0x596967;

const profile = (values) => Object.freeze({
  // Silhouette: deliberately non-circular even at rest.
  scale: 1,
  squash: 0.92,
  stretch: 1.08,
  lean: -0.09,
  lobes: 5,
  lobeDepth: 0.12,
  asymmetry: 0.18,
  lowerWeight: 0.12,
  tension: 0.62,
  pulse: 0.035,
  wobble: 0.07,
  speed: 0.2,
  direction: 1,

  // Interior cognition: topology and organization are state-owned parameters.
  membranes: 3,
  membraneCurl: 0.18,
  nodes: 4,
  nodeSpread: 0.54,
  nodeFocus: 0.42,
  organization: 0.4,
  density: 0.46,
  attention: 0.3,

  // Sparse marks outside the body imply flow without becoming an aura/orb.
  traces: 2,
  traceReach: 0.34,
  traceArc: 0.45,
  opacity: 0.7,
  accent: seaGlass,
  secondary: pearl,
  core: deepTeal,
  ...values,
});

/**
 * Mochi is one soft cognitive organism. Profiles alter its silhouette,
 * membrane topology and bounded internal matter—not just its palette.
 */
export const COGNITIVE_FOLD_PROFILES = Object.freeze({
  IDLE: profile({ scale: 0.94, squash: 0.96, stretch: 1.03, lean: -0.12, lobes: 4, lobeDepth: 0.1, asymmetry: 0.2, lowerWeight: 0.18, tension: 0.48, pulse: 0.025, wobble: 0.055, speed: 0.11, membranes: 2, membraneCurl: 0.14, nodes: 3, nodeSpread: 0.58, nodeFocus: 0.25, organization: 0.24, density: 0.3, attention: 0.18, traces: 1, traceReach: 0.24 }),
  LISTENING: profile({ scale: 0.98, squash: 0.88, stretch: 1.13, lean: -0.04, lobes: 5, lobeDepth: 0.13, asymmetry: 0.14, lowerWeight: 0.08, tension: 0.76, pulse: 0.04, wobble: 0.045, speed: 0.18, direction: -1, membranes: 3, membraneCurl: 0.1, nodes: 4, nodeSpread: 0.42, nodeFocus: 0.72, organization: 0.62, density: 0.48, attention: 0.92, traces: 2, traceReach: 0.3 }),
  TRANSCRIBING: profile({ scale: 1, squash: 0.84, stretch: 1.18, lean: 0.1, lobes: 6, lobeDepth: 0.1, asymmetry: 0.16, lowerWeight: 0.04, tension: 0.84, pulse: 0.045, wobble: 0.06, speed: 0.42, membranes: 4, membraneCurl: 0.28, nodes: 6, nodeSpread: 0.62, nodeFocus: 0.58, organization: 0.76, density: 0.72, attention: 0.78, traces: 3, traceReach: 0.42, traceArc: 0.28 }),
  THINKING: profile({ scale: 1.03, squash: 0.94, stretch: 1.04, lean: -0.17, lobes: 7, lobeDepth: 0.17, asymmetry: 0.28, lowerWeight: 0.1, tension: 0.42, pulse: 0.065, wobble: 0.15, speed: 0.26, direction: -1, membranes: 5, membraneCurl: 0.54, nodes: 7, nodeSpread: 0.66, nodeFocus: 0.46, organization: 0.34, density: 0.84, attention: 0.7, traces: 2, traceReach: 0.5, traceArc: 0.7, accent: lilac }),
  PLANNING: profile({ scale: 1.01, squash: 0.9, stretch: 1.1, lean: 0.15, lobes: 6, lobeDepth: 0.09, asymmetry: 0.12, lowerWeight: 0.06, tension: 0.9, pulse: 0.03, wobble: 0.045, speed: 0.22, membranes: 5, membraneCurl: 0.22, nodes: 8, nodeSpread: 0.7, nodeFocus: 0.66, organization: 0.95, density: 0.82, attention: 0.84, traces: 4, traceReach: 0.52, traceArc: 0.34 }),
  EXECUTING: profile({ scale: 1.04, squash: 0.79, stretch: 1.23, lean: 0.22, lobes: 5, lobeDepth: 0.11, asymmetry: 0.2, lowerWeight: 0.02, tension: 0.88, pulse: 0.055, wobble: 0.075, speed: 0.62, membranes: 4, membraneCurl: 0.12, nodes: 7, nodeSpread: 0.74, nodeFocus: 0.76, organization: 0.88, density: 0.7, attention: 0.76, traces: 5, traceReach: 0.68, traceArc: 0.2 }),
  VERIFYING: profile({ scale: 0.98, squash: 1.02, stretch: 0.98, lean: -0.08, lobes: 4, lobeDepth: 0.075, asymmetry: 0.09, lowerWeight: 0.06, tension: 0.98, pulse: 0.022, wobble: 0.025, speed: 0.17, direction: -1, membranes: 6, membraneCurl: 0.08, nodes: 8, nodeSpread: 0.55, nodeFocus: 0.92, organization: 1, density: 0.9, attention: 1, traces: 3, traceReach: 0.38, traceArc: 0.25 }),
  WAITING_FOR_APPROVAL: profile({ scale: 0.96, squash: 0.87, stretch: 1.14, lean: 0.02, lobes: 4, lobeDepth: 0.08, asymmetry: 0.1, lowerWeight: 0.17, tension: 0.9, pulse: 0.018, wobble: 0.02, speed: 0.055, direction: 0, membranes: 3, membraneCurl: 0.08, nodes: 3, nodeSpread: 0.34, nodeFocus: 0.94, organization: 0.82, density: 0.35, attention: 1, traces: 1, traceReach: 0.2, opacity: 0.76, accent: amber }),
  SPEAKING: profile({ scale: 1.02, squash: 0.92, stretch: 1.08, lean: -0.1, lobes: 6, lobeDepth: 0.14, asymmetry: 0.2, lowerWeight: 0.12, tension: 0.52, pulse: 0.1, wobble: 0.12, speed: 0.38, membranes: 4, membraneCurl: 0.3, nodes: 5, nodeSpread: 0.6, nodeFocus: 0.48, organization: 0.58, density: 0.56, attention: 0.6, traces: 3, traceReach: 0.46 }),
  COMPLETED: profile({ scale: 1.06, squash: 1.06, stretch: 0.96, lean: 0.08, lobes: 5, lobeDepth: 0.09, asymmetry: 0.13, lowerWeight: 0.22, tension: 0.58, pulse: 0.04, wobble: 0.035, speed: 0.13, membranes: 4, membraneCurl: 0.2, nodes: 5, nodeSpread: 0.72, nodeFocus: 0.38, organization: 0.78, density: 0.5, attention: 0.3, traces: 4, traceReach: 0.48, traceArc: 0.76, accent: pearl, secondary: seaGlass }),
  FAILED: profile({ scale: 0.93, squash: 1.12, stretch: 0.86, lean: -0.24, lobes: 6, lobeDepth: 0.2, asymmetry: 0.34, lowerWeight: 0.3, tension: 0.24, pulse: 0.025, wobble: 0.09, speed: 0.09, direction: -1, membranes: 3, membraneCurl: 0.62, nodes: 4, nodeSpread: 0.78, nodeFocus: 0.18, organization: 0.14, density: 0.66, attention: 0.44, traces: 2, traceReach: 0.3, opacity: 0.62, accent: coral, core: 0x703f42 }),
  CANCELLED: profile({ scale: 0.88, squash: 1.18, stretch: 0.78, lean: 0.18, lobes: 3, lobeDepth: 0.07, asymmetry: 0.24, lowerWeight: 0.34, tension: 0.3, pulse: 0.012, wobble: 0.018, speed: 0.025, direction: -1, membranes: 2, membraneCurl: 0.42, nodes: 2, nodeSpread: 0.74, nodeFocus: 0.1, organization: 0.18, density: 0.18, attention: 0.08, traces: 0, traceReach: 0.12, opacity: 0.44, accent: slate, secondary: deepTeal, core: 0x283d3b }),
});

export const DEFAULT_FOLD_STATE = "IDLE";

export function getFoldProfile(state) {
  return COGNITIVE_FOLD_PROFILES[state] || COGNITIVE_FOLD_PROFILES[DEFAULT_FOLD_STATE];
}

export function isFoldState(state) {
  return Object.prototype.hasOwnProperty.call(COGNITIVE_FOLD_PROFILES, state);
}
