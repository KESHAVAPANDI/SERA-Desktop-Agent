/**
 * SERA 2.0 Live2D State Profiles
 *
 * Authoritative SERA states mapped to data-driven Live2D character profiles.
 * Each state specifies expressions, preferred motions, eye/gaze behavior,
 * posture offsets, breathing rates, physics intensity, and color targets.
 *
 * Future states can be added via registerStateProfile() without changing
 * renderer or controller logic.
 */

// Factory helper to ensure all profiles have consistent, type-safe defaults
function defineProfile(values) {
  return Object.freeze({
    // Live2D Expression (corresponds to expressions/exp_0X.exp3.json)
    expression: "exp_01",

    // Motion group and optional motion index
    motionGroup: "Idle",
    motionIndex: 0,

    // Head posture angles (degrees)
    angleX: 0.0,
    angleY: 0.0,
    angleZ: 0.0,

    // Body posture angles (degrees)
    bodyAngleX: 0.0,
    bodyAngleY: 0.0,
    bodyAngleZ: 0.0,

    // Eye and gaze targets
    gazeX: 0.0,                // -1.0 (left) .. +1.0 (right)
    gazeY: 0.0,                // -1.0 (down) .. +1.0 (up)
    gazeSpeed: 4.0,            // Interpolation speed
    eyeOpenMultiplier: 1.0,    // Multiplier on eye openness
    eyeSmile: 0.0,             // Eye smile shape (0.0 .. 1.0)
    blinkRate: 1.0,            // Multiplier on blinking frequency

    // Continuous life layer modulation
    breathRate: 1.0,           // Speed multiplier for breathing cycle
    breathDepth: 0.035,        // Amplitude of ParamBreath
    physicsIntensity: 1.0,     // Physics responsiveness multiplier

    // State Color Target [R, G, B] in normalized 0.0 - 1.0 range
    color: [0.22, 0.74, 0.97], // Default cyan/blue
    auraIntensity: 0.35,       // Background aura/glow strength (0.0 .. 1.0)

    // Speaking behavior
    isSpeaking: false,
    mouthOpenGain: 1.0,

    // State transition duration (seconds)
    transitionDuration: 0.4,

    ...values,
  });
}

/**
 * Data-driven mapping for all authoritative SERA states.
 */
export const LIVE2D_STATE_PROFILES = {
  // 1. IDLE: Calm, present, gentle ambient breathing, stable neutral gaze
  IDLE: defineProfile({
    expression: "exp_01",
    motionGroup: "Idle",
    motionIndex: 0,
    angleX: 0.0,
    angleY: 0.0,
    angleZ: 0.0,
    bodyAngleX: 0.0,
    bodyAngleY: 0.0,
    bodyAngleZ: 0.0,
    gazeX: 0.0,
    gazeY: 0.0,
    eyeOpenMultiplier: 1.0,
    eyeSmile: 0.1,
    blinkRate: 1.0,
    breathRate: 1.0,
    breathDepth: 0.035,
    physicsIntensity: 1.0,
    color: [0.22, 0.74, 0.97], // Cyan / Blue (#38bdf8)
    auraIntensity: 0.3,
    transitionDuration: 0.45,
  }),

  // 2. LISTENING: Attentive, alert, leaning slightly forward, eyes focused on user
  LISTENING: defineProfile({
    expression: "exp_04", // Sparkle attentive eyes
    motionGroup: "Idle",
    motionIndex: 1,
    angleX: 0.0,
    angleY: 4.0,          // Lift head slightly to face user
    angleZ: 1.5,
    bodyAngleX: 0.0,
    bodyAngleY: 2.5,      // Leaning forward attentively
    bodyAngleZ: 0.0,
    gazeX: 0.0,
    gazeY: 0.12,          // Looking directly toward user
    gazeSpeed: 6.0,
    eyeOpenMultiplier: 1.15, // Eyes widened with interest
    eyeSmile: 0.15,
    blinkRate: 0.7,       // Reduced blinking during active listening
    breathRate: 1.2,
    breathDepth: 0.045,
    physicsIntensity: 1.1,
    color: [0.01, 0.52, 0.78], // Brighter Blue (#0284c7)
    auraIntensity: 0.65,
    transitionDuration: 0.35,
  }),

  // 3. TRANSCRIBING: Actively absorbing speech, slight inward concentration
  TRANSCRIBING: defineProfile({
    expression: "exp_01",
    motionGroup: "TapBody",
    motionIndex: 0,
    angleX: 3.5,
    angleY: -2.0,
    angleZ: 2.0,
    bodyAngleX: 2.0,
    bodyAngleY: -1.0,
    bodyAngleZ: 1.0,
    gazeX: 0.12,
    gazeY: -0.06,
    gazeSpeed: 5.0,
    eyeOpenMultiplier: 1.0,
    eyeSmile: 0.0,
    blinkRate: 1.2,
    breathRate: 1.3,
    breathDepth: 0.045,
    physicsIntensity: 1.2,
    color: [0.51, 0.55, 0.97], // Blue-Violet (#818cf8)
    auraIntensity: 0.7,
    transitionDuration: 0.3,
  }),

  // 4. THINKING: Cognitively active, thoughtful gaze upward-left, slight head tilt
  THINKING: defineProfile({
    expression: "exp_06", // Thoughtful inward blush
    motionGroup: "Idle",
    motionIndex: 1,
    angleX: -6.0,         // Head tilted sideways
    angleY: 5.0,          // Looking upward in thought
    angleZ: -3.5,
    bodyAngleX: -3.0,
    bodyAngleY: 1.0,
    bodyAngleZ: -2.0,
    gazeX: -0.22,         // Gazing up and away
    gazeY: 0.18,
    gazeSpeed: 3.0,
    eyeOpenMultiplier: 0.92,
    eyeSmile: 0.0,
    blinkRate: 0.8,
    breathRate: 0.9,
    breathDepth: 0.055,
    physicsIntensity: 0.9,
    color: [0.66, 0.33, 0.97], // Violet (#a855f7)
    auraIntensity: 0.75,
    transitionDuration: 0.5,
  }),

  // 5. PLANNING: Deliberate, structuring steps, focused forward gaze
  PLANNING: defineProfile({
    expression: "exp_05", // Deliberate and focused
    motionGroup: "TapBody",
    motionIndex: 1,
    angleX: 3.0,
    angleY: 3.0,
    angleZ: 1.5,
    bodyAngleX: 2.0,
    bodyAngleY: 1.5,
    bodyAngleZ: 1.0,
    gazeX: 0.1,
    gazeY: 0.08,
    gazeSpeed: 4.5,
    eyeOpenMultiplier: 1.0,
    eyeSmile: 0.05,
    blinkRate: 1.0,
    breathRate: 1.1,
    breathDepth: 0.04,
    physicsIntensity: 1.0,
    color: [0.55, 0.36, 0.96], // Blue-Violet (#8b5cf6)
    auraIntensity: 0.75,
    transitionDuration: 0.4,
  }),

  // 6. TYPING: Fast response composition, eyes glancing down toward text
  TYPING: defineProfile({
    expression: "exp_06",
    motionGroup: "TapBody",
    motionIndex: 0,
    angleX: 2.0,
    angleY: -3.5,
    angleZ: 1.0,
    bodyAngleX: 1.0,
    bodyAngleY: -2.0,
    bodyAngleZ: 0.0,
    gazeX: 0.05,
    gazeY: -0.15,         // Looking downward as if typing
    gazeSpeed: 5.5,
    eyeOpenMultiplier: 0.95,
    eyeSmile: 0.0,
    blinkRate: 1.3,
    breathRate: 1.35,
    breathDepth: 0.045,
    physicsIntensity: 1.15,
    color: [0.75, 0.52, 0.99], // Violet (#c084fc)
    auraIntensity: 0.7,
    transitionDuration: 0.3,
  }),

  // 7. WORKING: Taking action in tools/desktop, focused posture
  WORKING: defineProfile({
    expression: "exp_04",
    motionGroup: "TapBody",
    motionIndex: 2,
    angleX: 4.0,
    angleY: 1.0,
    angleZ: 2.5,
    bodyAngleX: 3.0,
    bodyAngleY: 0.5,
    bodyAngleZ: 2.0,
    gazeX: 0.12,
    gazeY: 0.0,
    gazeSpeed: 5.0,
    eyeOpenMultiplier: 1.05,
    eyeSmile: 0.1,
    blinkRate: 1.2,
    breathRate: 1.4,
    breathDepth: 0.06,
    physicsIntensity: 1.3,
    color: [0.96, 0.62, 0.04], // Amber/Violet (#f59e0b)
    auraIntensity: 0.85,
    transitionDuration: 0.35,
  }),

  // 8. EXECUTING: High energy, executing system actions, dynamic and sharp
  EXECUTING: defineProfile({
    expression: "exp_04", // Energetic sparkle
    motionGroup: "TapBody",
    motionIndex: 2,
    angleX: 5.0,
    angleY: 2.0,
    angleZ: 3.0,
    bodyAngleX: 4.0,
    bodyAngleY: 1.0,
    bodyAngleZ: 2.5,
    gazeX: 0.15,
    gazeY: 0.05,
    gazeSpeed: 6.0,
    eyeOpenMultiplier: 1.1,
    eyeSmile: 0.15,
    blinkRate: 1.4,
    breathRate: 1.5,
    breathDepth: 0.065,
    physicsIntensity: 1.4,
    color: [0.02, 0.71, 0.83], // Cyan (#06b6d4)
    auraIntensity: 0.9,
    transitionDuration: 0.3,
  }),

  // 9. VERIFYING: Precise examination, verifying output correctness
  VERIFYING: defineProfile({
    expression: "exp_05", // Precise and careful
    motionGroup: "TapBody",
    motionIndex: 1,
    angleX: -2.5,
    angleY: 1.5,
    angleZ: -1.0,
    bodyAngleX: -1.5,
    bodyAngleY: 0.5,
    bodyAngleZ: -0.5,
    gazeX: -0.06,
    gazeY: 0.05,
    gazeSpeed: 4.0,
    eyeOpenMultiplier: 0.98,
    eyeSmile: 0.05,
    blinkRate: 0.8,
    breathRate: 0.95,
    breathDepth: 0.03,
    physicsIntensity: 0.85,
    color: [0.06, 0.73, 0.51], // Green/Cyan (#10b981)
    auraIntensity: 0.8,
    transitionDuration: 0.4,
  }),

  // 10. WAITING_FOR_APPROVAL: Clear "waiting for user" posture, poised, direct eye contact
  WAITING_FOR_APPROVAL: defineProfile({
    expression: "exp_07", // Patient, expectant, alert
    motionGroup: "TapBody",
    motionIndex: 3,
    angleX: 0.0,
    angleY: 3.0,
    angleZ: 0.0,
    bodyAngleX: 0.0,
    bodyAngleY: 1.8,
    bodyAngleZ: 0.0,
    gazeX: 0.0,
    gazeY: 0.1,           // Looking right at user
    gazeSpeed: 5.0,
    eyeOpenMultiplier: 1.15,
    eyeSmile: 0.1,
    blinkRate: 0.9,
    breathRate: 0.85,
    breathDepth: 0.035,
    physicsIntensity: 0.75,
    color: [0.92, 0.70, 0.03], // Gold (#eab308)
    auraIntensity: 0.9,
    transitionDuration: 0.4,
  }),

  // 11. SPEAKING: Warm, expressive, mouth movement actively driven by audio envelope
  SPEAKING: defineProfile({
    expression: "exp_02", // Warm expressive smile
    motionGroup: "Idle",
    motionIndex: 0,
    angleX: 0.0,
    angleY: 2.0,
    angleZ: 1.0,
    bodyAngleX: 0.0,
    bodyAngleY: 1.0,
    bodyAngleZ: 0.5,
    gazeX: 0.0,
    gazeY: 0.05,
    gazeSpeed: 5.0,
    eyeOpenMultiplier: 1.05,
    eyeSmile: 0.25,
    blinkRate: 1.1,
    breathRate: 1.2,
    breathDepth: 0.05,
    physicsIntensity: 1.1,
    color: [0.06, 0.65, 0.91], // Cyan/Blue (#0ea5e9)
    auraIntensity: 0.7,
    isSpeaking: true,
    mouthOpenGain: 1.0,
    transitionDuration: 0.25,
  }),

  // 12. COMPLETED: Joyful, rewarding smile, successful resolution
  COMPLETED: defineProfile({
    expression: "exp_02", // Happy smile
    motionGroup: "TapBody",
    motionIndex: 4,
    angleX: 1.5,
    angleY: 3.5,
    angleZ: 2.0,
    bodyAngleX: 1.5,
    bodyAngleY: 2.0,
    bodyAngleZ: 1.5,
    gazeX: 0.0,
    gazeY: 0.06,
    gazeSpeed: 4.0,
    eyeOpenMultiplier: 1.0,
    eyeSmile: 0.85,       // Pronounced eye smile
    blinkRate: 1.0,
    breathRate: 1.1,
    breathDepth: 0.05,
    physicsIntensity: 1.2,
    color: [0.13, 0.77, 0.37], // Green (#22c55e)
    auraIntensity: 0.9,
    transitionDuration: 0.35,
  }),

  // 13. FAILED: Concerned, empathetic, communicates failure without looking dead/broken
  FAILED: defineProfile({
    expression: "exp_08", // Concerned pout
    motionGroup: "TapBody",
    motionIndex: 5,
    angleX: -3.5,
    angleY: -4.0,
    angleZ: -2.5,
    bodyAngleX: -2.5,
    bodyAngleY: -2.0,
    bodyAngleZ: -1.5,
    gazeX: -0.1,
    gazeY: -0.12,
    gazeSpeed: 3.0,
    eyeOpenMultiplier: 0.9,
    eyeSmile: -0.2,
    blinkRate: 0.7,
    breathRate: 0.8,
    breathDepth: 0.03,
    physicsIntensity: 0.65,
    color: [0.96, 0.25, 0.37], // Rose/Red-Violet (#f43f5e)
    auraIntensity: 0.75,
    transitionDuration: 0.5,
  }),

  // 14. CANCELLED: Settling back naturally toward idle, gentle deceleration
  CANCELLED: defineProfile({
    expression: "exp_03", // Soft neutral resting
    motionGroup: "Idle",
    motionIndex: 1,
    angleX: 0.0,
    angleY: -1.5,
    angleZ: 0.0,
    bodyAngleX: 0.0,
    bodyAngleY: -1.0,
    bodyAngleZ: 0.0,
    gazeX: 0.0,
    gazeY: -0.05,
    gazeSpeed: 2.5,
    eyeOpenMultiplier: 0.85,
    eyeSmile: 0.0,
    blinkRate: 0.7,
    breathRate: 0.85,
    breathDepth: 0.025,
    physicsIntensity: 0.7,
    color: [0.39, 0.45, 0.55], // Muted Blue (#64748b)
    auraIntensity: 0.25,
    transitionDuration: 0.6,
  }),

  // OFFLINE: Graceful resting state when disconnected from SERA Core
  OFFLINE: defineProfile({
    expression: "exp_03", // Eyes closed resting
    motionGroup: "Idle",
    motionIndex: 0,
    angleX: 0.0,
    angleY: -4.5,
    angleZ: 0.0,
    bodyAngleX: 0.0,
    bodyAngleY: -2.5,
    bodyAngleZ: 0.0,
    gazeX: 0.0,
    gazeY: -0.1,
    gazeSpeed: 1.5,
    eyeOpenMultiplier: 0.0, // Eyes closed in sleep
    eyeSmile: 0.0,
    blinkRate: 0.0,
    breathRate: 0.55,
    breathDepth: 0.02,
    physicsIntensity: 0.4,
    color: [0.28, 0.33, 0.41], // Slate (#475569)
    auraIntensity: 0.1,
    transitionDuration: 0.8,
  }),
};

/**
 * Presentation-to-profile aliases so UI synonyms map to existing state profiles
 * without creating a second state machine.
 */
export const PROFILE_ALIASES = Object.freeze({
  TASK_PLANNING: "PLANNING",
  TASK_EXECUTING: "EXECUTING",
  TASK_VERIFYING: "VERIFYING",
  TASK_RECOVERING: "THINKING",
  TASK_COMPLETED: "COMPLETED",
  TASK_FAILED: "FAILED",
  TASK_CANCELLED: "CANCELLED",
  CONFIRMING_ACTION: "WAITING_FOR_APPROVAL",
  PAUSED_APPROVAL: "WAITING_FOR_APPROVAL",
  ERROR: "FAILED",
  SHUTDOWN: "OFFLINE",
});

/**
 * Retrieve the state profile for an authoritative SERA state.
 * Gracefully falls back to IDLE profile if the state is unknown.
 */
export function getStateProfile(rawState) {
  if (!rawState) return LIVE2D_STATE_PROFILES.IDLE;
  const normalized = String(rawState).trim().toUpperCase();
  const aliased = PROFILE_ALIASES[normalized] || normalized;
  return LIVE2D_STATE_PROFILES[aliased] || LIVE2D_STATE_PROFILES.IDLE;
}

/**
 * Register a new custom state profile at runtime without modifying the renderer.
 *
 * Example:
 *   registerStateProfile("CUSTOM_RESEARCH", {
 *     expression: "exp_06",
 *     color: [0.3, 0.9, 0.9],
 *     angleY: 3.0,
 *   });
 */
export function registerStateProfile(stateName, customValues) {
  if (!stateName || typeof stateName !== "string") {
    throw new TypeError("State name must be a non-empty string");
  }
  const normalized = stateName.trim().toUpperCase();
  LIVE2D_STATE_PROFILES[normalized] = defineProfile(customValues);
  return LIVE2D_STATE_PROFILES[normalized];
}
