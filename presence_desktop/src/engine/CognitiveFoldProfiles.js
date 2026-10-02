const pearlCyan = 0xbdeff1;
const moonLilac = 0xc8b8ef;
const deepIris = 0x294b67;
const warmPearl = 0xf4e8f5;
const approvalGold = 0xf1c979;
const failureRose = 0xd98a9a;
const quietSlate = 0x7890a3;

// Profiles describe acting choices only. SERA's anatomy is built once by the
// renderer and is never replaced when operational state changes.
const profile = (values) => Object.freeze({
  scale: 1,
  posture: 0,
  lean: 0,
  squash: 1,
  stretch: 1,
  gazeX: 0,
  gazeY: 0,
  gazeFocus: 0.55,
  blinkRate: 0.16,
  blinkDepth: 1,
  earAngle: 0.08,
  earLift: 0,
  antennaSway: 0.16,
  antennaGlow: 0.62,
  bounce: 0.045,
  breath: 0.025,
  speed: 0.25,
  mouthOpen: 0.04,
  smile: 0.22,
  expression: 0,
  internalGlow: 0.42,
  particles: 2,
  traces: 1,
  traceReach: 0.32,
  opacity: 0.9,
  accent: pearlCyan,
  secondary: moonLilac,
  core: deepIris,
  ...values,
});

/** Continuous acting profiles for the one persistent SERA 2.5D character. */
export const COGNITIVE_FOLD_PROFILES = Object.freeze({
  IDLE: profile({ scale: 0.98, posture: -0.03, gazeY: -0.03, gazeFocus: 0.35, blinkRate: 0.13, earAngle: 0.04, antennaSway: 0.12, bounce: 0.028, speed: 0.14, smile: 0.2, internalGlow: 0.34, particles: 1, traces: 0 }),
  LISTENING: profile({ posture: 0.08, stretch: 1.035, gazeY: 0.08, gazeFocus: 0.95, blinkRate: 0.11, earAngle: 0.22, earLift: 0.1, antennaSway: 0.1, antennaGlow: 0.76, bounce: 0.025, speed: 0.18, mouthOpen: 0.025, smile: 0.08, internalGlow: 0.5, particles: 2, traces: 1 }),
  TRANSCRIBING: profile({ posture: 0.06, lean: 0.06, squash: 0.98, stretch: 1.04, gazeX: 0.14, gazeY: -0.05, gazeFocus: 0.86, blinkRate: 0.2, earAngle: 0.14, antennaSway: 0.24, antennaGlow: 0.74, bounce: 0.045, speed: 0.48, mouthOpen: 0.035, smile: 0.12, internalGlow: 0.55, particles: 5, traces: 3, traceReach: 0.48 }),
  THINKING: profile({ posture: 0.04, lean: -0.1, squash: 1.025, stretch: 0.98, gazeX: -0.2, gazeY: 0.16, gazeFocus: 0.72, blinkRate: 0.1, earAngle: -0.02, earLift: 0.05, antennaSway: 0.34, antennaGlow: 0.86, bounce: 0.035, breath: 0.035, speed: 0.3, mouthOpen: 0.02, smile: -0.04, expression: 0.26, internalGlow: 0.68, particles: 6, traces: 2, traceReach: 0.54, accent: moonLilac, secondary: pearlCyan }),
  PLANNING: profile({ posture: 0.11, lean: 0.08, stretch: 1.035, gazeX: 0.12, gazeY: 0.1, gazeFocus: 0.9, blinkRate: 0.14, earAngle: 0.13, earLift: 0.08, antennaSway: 0.2, antennaGlow: 0.84, bounce: 0.025, speed: 0.28, mouthOpen: 0.025, smile: 0.12, expression: 0.12, internalGlow: 0.64, particles: 7, traces: 3, traceReach: 0.58 }),
  EXECUTING: profile({ posture: 0.14, lean: 0.13, squash: 0.96, stretch: 1.065, gazeX: 0.18, gazeFocus: 0.82, blinkRate: 0.2, earAngle: 0.1, antennaSway: 0.3, antennaGlow: 0.9, bounce: 0.075, speed: 0.68, mouthOpen: 0.06, smile: 0.14, internalGlow: 0.72, particles: 10, traces: 4, traceReach: 0.72 }),
  VERIFYING: profile({ posture: 0.1, lean: -0.03, squash: 1.01, stretch: 0.995, gazeY: 0.04, gazeFocus: 1, blinkRate: 0.08, earAngle: 0.18, earLift: 0.06, antennaSway: 0.08, antennaGlow: 0.92, bounce: 0.018, speed: 0.2, mouthOpen: 0.015, smile: 0.02, expression: 0.08, internalGlow: 0.66, particles: 4, traces: 2, traceReach: 0.38 }),
  WAITING_FOR_APPROVAL: profile({ posture: 0.09, stretch: 1.025, gazeY: 0.08, gazeFocus: 1, blinkRate: 0.12, earAngle: 0.24, earLift: 0.12, antennaSway: 0.06, antennaGlow: 1, bounce: 0.018, speed: 0.1, mouthOpen: 0.02, smile: 0.04, expression: 0.16, internalGlow: 0.62, particles: 3, traces: 1, accent: approvalGold, secondary: warmPearl }),
  SPEAKING: profile({ posture: 0.08, squash: 0.985, stretch: 1.03, gazeFocus: 0.75, blinkRate: 0.17, earAngle: 0.1, antennaSway: 0.22, antennaGlow: 0.82, bounce: 0.07, breath: 0.045, speed: 0.44, mouthOpen: 0.2, smile: 0.24, internalGlow: 0.62, particles: 5, traces: 2, traceReach: 0.45 }),
  COMPLETED: profile({ scale: 1.035, posture: 0.12, squash: 1.03, stretch: 0.98, gazeY: 0.04, gazeFocus: 0.55, blinkRate: 0.14, earAngle: 0.16, earLift: 0.1, antennaSway: 0.16, antennaGlow: 0.9, bounce: 0.055, speed: 0.22, mouthOpen: 0.045, smile: 0.62, expression: -0.1, internalGlow: 0.72, particles: 8, traces: 3, traceReach: 0.56, secondary: warmPearl }),
  FAILED: profile({ scale: 0.96, posture: -0.11, lean: -0.08, squash: 1.055, stretch: 0.94, gazeX: -0.08, gazeY: -0.13, gazeFocus: 0.42, blinkRate: 0.07, blinkDepth: 0.78, earAngle: -0.2, earLift: -0.1, antennaSway: 0.1, antennaGlow: 0.34, bounce: 0.018, speed: 0.12, mouthOpen: 0.055, smile: -0.34, expression: 0.38, internalGlow: 0.3, particles: 2, traces: 1, opacity: 0.82, accent: failureRose, secondary: moonLilac, core: 0x653f58 }),
  CANCELLED: profile({ scale: 0.94, posture: -0.08, squash: 1.04, stretch: 0.95, gazeY: -0.08, gazeFocus: 0.25, blinkRate: 0.08, blinkDepth: 0.7, earAngle: -0.14, earLift: -0.08, antennaSway: 0.05, antennaGlow: 0.2, bounce: 0.012, speed: 0.07, mouthOpen: 0.02, smile: -0.12, expression: 0.18, internalGlow: 0.2, particles: 0, traces: 0, opacity: 0.72, accent: quietSlate, secondary: moonLilac, core: 0x344a5a }),
});

// These UI-only labels borrow an existing runtime profile. They do not add a
// state transition or suggest that the backend owns TYPING/WORKING states.
export const PRESENTATION_PROFILE_MAP = Object.freeze({
  TYPING: "TRANSCRIBING",
  WORKING: "EXECUTING",
});

export const DEFAULT_FOLD_STATE = "IDLE";

export function getBackendCompatibleProfileState(state) {
  return PRESENTATION_PROFILE_MAP[state] || state;
}

export function getFoldProfile(state) {
  const profileState = getBackendCompatibleProfileState(state);
  return COGNITIVE_FOLD_PROFILES[profileState] || COGNITIVE_FOLD_PROFILES[DEFAULT_FOLD_STATE];
}

export function isFoldState(state) {
  return Object.prototype.hasOwnProperty.call(COGNITIVE_FOLD_PROFILES, state)
    || Object.prototype.hasOwnProperty.call(PRESENTATION_PROFILE_MAP, state);
}
