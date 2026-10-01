const ivory = 0xf2eee3;
const teal = 0x5d8f89;
const ink = 0x183330;
const amber = 0xb9965a;
const rust = 0xa45f52;

const profile = (values) => Object.freeze({
  energy: 0.25,
  folds: 4,
  threads: 4,
  signals: 1,
  aperture: 1.35,
  spread: 0.72,
  skew: -0.12,
  direction: 1,
  speed: 0.18,
  ripple: 0.08,
  tension: 0.75,
  density: 0.42,
  opacity: 0.72,
  accent: teal,
  secondary: ivory,
  ...values,
});

/**
 * Geometry is deliberately part of each state profile. A transition therefore
 * changes silhouette, flow and information density rather than merely tinting.
 */
export const COGNITIVE_FOLD_PROFILES = Object.freeze({
  IDLE: profile({ folds: 3, threads: 3, aperture: 1.58, spread: 0.86, skew: -0.22, speed: 0.09, ripple: 0.045, density: 0.28 }),
  LISTENING: profile({ energy: 0.48, folds: 4, threads: 5, aperture: 1.06, spread: 0.62, skew: -0.08, direction: -1, speed: 0.16, ripple: 0.13, tension: 0.92, density: 0.58 }),
  TRANSCRIBING: profile({ energy: 0.62, folds: 5, threads: 7, signals: 3, aperture: 1.18, spread: 0.56, skew: 0.2, direction: 1, speed: 0.4, ripple: 0.1, tension: 0.86, density: 0.8 }),
  THINKING: profile({ energy: 0.78, folds: 7, threads: 8, signals: 2, aperture: 1.42, spread: 0.48, skew: -0.35, direction: -1, speed: 0.25, ripple: 0.2, tension: 0.58, density: 0.92 }),
  PLANNING: profile({ energy: 0.72, folds: 6, threads: 8, signals: 3, aperture: 1.55, spread: 0.5, skew: 0.38, direction: 1, speed: 0.2, ripple: 0.12, tension: 0.96, density: 0.86 }),
  EXECUTING: profile({ energy: 0.9, folds: 5, threads: 6, signals: 4, aperture: 1.26, spread: 0.62, skew: 0.58, direction: 1, speed: 0.62, ripple: 0.11, tension: 0.9, density: 0.76 }),
  VERIFYING: profile({ energy: 0.64, folds: 4, threads: 9, signals: 2, aperture: 1.34, spread: 0.44, skew: -0.48, direction: -1, speed: 0.18, ripple: 0.06, tension: 1, density: 0.94 }),
  WAITING_FOR_APPROVAL: profile({ energy: 0.38, folds: 3, threads: 4, signals: 1, aperture: 1.82, spread: 0.78, skew: 0.12, direction: 0, speed: 0.04, ripple: 0.035, tension: 0.98, density: 0.32, accent: amber }),
  SPEAKING: profile({ energy: 0.68, folds: 5, threads: 5, signals: 3, aperture: 1.12, spread: 0.7, skew: -0.25, direction: 1, speed: 0.34, ripple: 0.28, tension: 0.62, density: 0.62 }),
  COMPLETED: profile({ energy: 0.45, folds: 4, threads: 6, signals: 2, aperture: 1.68, spread: 0.9, skew: 0.3, direction: 1, speed: 0.12, ripple: 0.05, tension: 0.88, density: 0.5, accent: ivory, secondary: teal }),
  FAILED: profile({ energy: 0.58, folds: 6, threads: 3, signals: 1, aperture: 1.3, spread: 0.38, skew: -0.62, direction: -1, speed: 0.08, ripple: 0.24, tension: 0.3, density: 0.7, opacity: 0.6, accent: rust }),
  CANCELLED: profile({ energy: 0.12, folds: 2, threads: 2, signals: 0, aperture: 2.05, spread: 1.08, skew: 0.48, direction: -1, speed: 0.02, ripple: 0.02, tension: 0.5, density: 0.14, opacity: 0.42, accent: ink }),
});

export const DEFAULT_FOLD_STATE = "IDLE";

export function getFoldProfile(state) {
  return COGNITIVE_FOLD_PROFILES[state] || COGNITIVE_FOLD_PROFILES[DEFAULT_FOLD_STATE];
}

export function colorChannels(hex) {
  return {
    r: ((hex >> 16) & 255) / 255,
    g: ((hex >> 8) & 255) / 255,
    b: (hex & 255) / 255,
  };
}
