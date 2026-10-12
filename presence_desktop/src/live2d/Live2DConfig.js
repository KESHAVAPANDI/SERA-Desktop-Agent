/**
 * SERA 2.0 Live2D Presence Configuration
 *
 * Central configuration for Live2D character model loading, viewports,
 * framing, and runtime flags. Allows easy swapping of the character model
 * without modifying the rendering or state controller logic.
 */

export const LIVE2D_CONFIG = Object.freeze({
  // Active character model settings
  activeModelName: "mao",
  modelPath: "./assets/live2d/models/mao/Mao.model3.json",
  modelLabel: "Niziiro Mao (Cubism 4)",

  // Viewport & Framing
  // Target viewport dimensions inside SERA overlay
  viewportWidth: 356,
  viewportHeight: 250,

  // Mao is a full-body model designed for VTubing. We scale and position
  // it so that the upper body / expressive face is centered and prominent.
  // Mao's source canvas includes a tall hat and full-body pose. At the compact
  // desktop Presence size, this keeps the face, hat silhouette, and shoulders
  // inside the viewport instead of clipping the crown at the top edge.
  modelScale: 0.13,
  modelOffsetX: 178,     // Centered horizontally in 356px viewport
  modelOffsetY: 405,     // Face-led 2.5D framing with safe headroom

  // Animation & Life Layer
  physics: true,
  autoInteract: false,    // Controlled by SERA state rather than raw clicks
  idleBreathing: true,
  naturalBlinking: true,
  microSaccades: true,

  // Audio / Speech
  lipSyncParam: "ParamA",
  speechFallbackFrequency: 14, // Retained for config compatibility; no synthetic fallback is used.
  speechMinOpen: 0.08,
  speechMaxOpen: 0.85,

  // Contextual behavior arbitration and continuity tuning.
  behavior: Object.freeze({
    horizontalMotion: 0.35,
    motionPriority: 2,
    speechFreshnessMs: 300,
    taskVariantScale: 1.0,
    reactionDurations: Object.freeze({
      TOOL_COMPLETED: 0.75,
      TOOL_FAILED: 0.9,
      SECURITY_CONFIRMATION_REQUIRED: 1.2,
      APPROVAL_RESOLVED: 0.65,
      TASK_COMPLETED: 1.1,
      TASK_FAILED: 1.1,
      TASK_CANCELLED: 0.8,
    }),
    life: Object.freeze({
      blinkIntervalMin: 2.5,
      blinkIntervalMax: 4.5,
      saccadeIntervalMin: 1.8,
      saccadeIntervalMax: 4.2,
      doubleBlinkProbability: 0.18,
      variationIntervalMin: 6,
      variationIntervalMax: 10,
      variationMin: 0.88,
      variationMax: 1.12,
    }),
  }),

  // WebGL Renderer settings
  webgl: {
    antialias: true,
    alpha: true,
    preserveDrawingBuffer: true,
    powerPreference: "default",
  },
});
