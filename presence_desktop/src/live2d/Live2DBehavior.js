/**
 * Small, deterministic behavior composition layer for the Live2D presence.
 *
 * The runtime state remains the base authority.  The layers below only own
 * their declared fields:
 *
 *   life               breathing, blink and organic micro motion
 *   attention          gaze/eye intent supplied by the current state
 *   task               small, fact-backed task-type variation
 *   expressionPosture  canonical expression, posture, color and motion
 *   speech             audio-driven mouth openness
 *   transientReaction  short reactions to an accepted runtime event
 *
 * A target is composed when facts change.  `resolveFrameTarget` then writes
 * one reusable frame target, so the renderer never adds competing deltas to
 * the model or allocates a behavior object on every frame.
 */

// Ordered from lowest to highest conflict priority. Life is a modifier layer,
// not a competing base target, and is therefore resolved separately per frame.
export const BEHAVIOR_PRIORITY = Object.freeze([
  "expressionPosture",
  "task",
  "attention",
  "speech",
  "transientReaction",
]);

const PRIORITY = Object.freeze(Object.fromEntries(BEHAVIOR_PRIORITY.map((name, index) => [name, index])));

export const PARAMETER_OWNERSHIP = Object.freeze({
  life: Object.freeze(["breathValue", "blinkRatio", "saccadeX", "saccadeY", "driftAngleX", "driftAngleY", "driftAngleZ"]),
  attention: Object.freeze(["gazeX", "gazeY", "eyeOpenMultiplier", "gazeSpeed"]),
  task: Object.freeze(["gazeX", "gazeY", "angleX", "angleY", "bodyAngleX", "bodyAngleY"]),
  expressionPosture: Object.freeze([
    "expression", "motionGroup", "motionIndex", "angleX", "angleY", "angleZ",
    "bodyAngleX", "bodyAngleY", "bodyAngleZ", "eyeSmile", "blinkRate",
    "breathRate", "breathDepth", "color", "auraIntensity", "transitionDuration",
  ]),
  speech: Object.freeze(["mouthOpen"]),
  transientReaction: Object.freeze(["expression", "motionGroup", "motionIndex", "eyeSmile"]),
});

// These are intentionally small and only use the task fact already supplied
// by the runtime. Unknown task types retain the canonical profile unchanged.
const TASK_VARIANTS = Object.freeze({
  SEARCH: Object.freeze({ gazeX: -0.04, gazeY: 0.03 }),
  BROWSER: Object.freeze({ gazeX: 0.04, gazeY: 0.02 }),
  CODE: Object.freeze({ gazeY: -0.035 }),
  CODING: Object.freeze({ gazeY: -0.035 }),
});

const REACTION_VARIANTS = Object.freeze({
  TOOL_COMPLETED: Object.freeze({ expression: "exp_02", eyeSmile: 0.55, duration: 0.75, states: ["THINKING", "PLANNING", "EXECUTING", "VERIFYING", "WORKING", "TYPING"] }),
  TOOL_FAILED: Object.freeze({ expression: "exp_08", eyeSmile: -0.12, duration: 0.9, states: ["THINKING", "PLANNING", "EXECUTING", "VERIFYING", "WORKING", "TYPING", "FAILED"] }),
  SECURITY_CONFIRMATION_REQUIRED: Object.freeze({ expression: "exp_07", eyeSmile: 0.12, duration: 1.2, states: ["WAITING_FOR_APPROVAL"] }),
  APPROVAL_RESOLVED: Object.freeze({ expression: "exp_02", eyeSmile: 0.45, duration: 0.65, states: ["WAITING_FOR_APPROVAL", "EXECUTING", "VERIFYING", "COMPLETED", "FAILED", "CANCELLED"] }),
  TASK_COMPLETED: Object.freeze({ expression: "exp_02", eyeSmile: 0.8, duration: 1.1, states: ["COMPLETED"] }),
  TASK_FAILED: Object.freeze({ expression: "exp_08", eyeSmile: -0.15, duration: 1.1, states: ["FAILED"] }),
  TASK_CANCELLED: Object.freeze({ expression: "exp_03", eyeSmile: 0, duration: 0.8, states: ["CANCELLED"] }),
});

function stateName(value) {
  return String(value || "IDLE").trim().toUpperCase();
}

function taskName(value) {
  return String(value || "GENERAL").trim().toUpperCase() || "GENERAL";
}

function finite(value, fallback = 0) {
  return Number.isFinite(Number(value)) ? Number(value) : fallback;
}

/** Return a fresh context for controller-owned runtime facts. */
export function createBehaviorContext() {
  return {
    state: "IDLE",
    taskType: "GENERAL",
    taskProgress: 0,
    taskId: null,
    revision: 0,
    reaction: null,
    speechEnabled: false,
  };
}

/** Merge patches with an explicit per-field priority; higher wins. */
export function composeBehaviorLayers(profile, layers = {}) {
  const target = { ...(profile || {}) };
  const owners = new Map(Object.keys(target).map((key) => [key, PRIORITY.expressionPosture]));
  for (const layerName of BEHAVIOR_PRIORITY.slice(1)) {
    const patch = layers[layerName];
    if (!patch) continue;
    const layerPriority = PRIORITY[layerName];
    for (const [key, value] of Object.entries(patch)) {
      if (layerPriority >= (owners.get(key) ?? -1)) {
        target[key] = value;
        owners.set(key, layerPriority);
      }
    }
  }
  return target;
}

/**
 * Compose the canonical profile with only fact-backed contextual patches.
 * This is pure; callers may retain the returned target until the next fact
 * change. Model capabilities are optional and are used to avoid bad motion
 * requests when a different compatible model is attached.
 */
export function resolveBehaviorTarget({ profile, context = {}, capabilities = null, tuning = {} } = {}) {
  const source = profile || {};
  const taskPatch = {};
  const type = taskName(context.taskType);
  const taskVariant = TASK_VARIANTS[type];
  const taskScale = finite(tuning.taskVariantScale, 1);

  if (taskVariant && (context.state === "PLANNING" || context.state === "THINKING" || context.state === "WORKING" || context.state === "EXECUTING" || context.state === "VERIFYING")) {
    if (taskVariant.gazeX !== undefined) taskPatch.gazeX = finite(source.gazeX) + finite(taskVariant.gazeX) * taskScale;
    if (taskVariant.gazeY !== undefined) taskPatch.gazeY = finite(source.gazeY) + finite(taskVariant.gazeY) * taskScale;
  }

  const reaction = context.reaction;
  let reactionPatch = null;
  if (reaction && reaction.revision === context.revision && reaction.event) {
    const patch = REACTION_VARIANTS[reaction.event];
    if (patch && (!patch.states || patch.states.includes(stateName(context.state)))) {
      reactionPatch = {};
      if (patch.expression) reactionPatch.expression = patch.expression;
      if (patch.eyeSmile !== undefined) reactionPatch.eyeSmile = patch.eyeSmile;
      if (patch.motionGroup) reactionPatch.motionGroup = patch.motionGroup;
      if (patch.motionIndex !== undefined) reactionPatch.motionIndex = patch.motionIndex;
    }
  }

  const target = composeBehaviorLayers(source, {
    task: taskPatch,
    attention: {},
    speech: {},
    transientReaction: reactionPatch,
  });

  const groups = capabilities?.motionGroups;
  if (groups && (!groups[target.motionGroup] || target.motionIndex >= groups[target.motionGroup])) {
    target.motionGroup = groups.Idle ? "Idle" : Object.keys(groups)[0] || target.motionGroup;
    target.motionIndex = 0;
  }
  return target;
}

/**
 * Resolve one frame target into a caller-owned object. No arithmetic result
 * is accumulated: every field is based on the resolved target and this
 * frame's life sample.
 */
export function resolveFrameTarget(base, life, horizontalMotion, mouthOpen, out) {
  const target = out;
  const horizontal = Number.isFinite(horizontalMotion) ? horizontalMotion : 0.35;
  target.angleX = finite(base.angleX) + finite(life.driftAngleX);
  target.angleY = finite(base.angleY) * horizontal + finite(life.driftAngleY) * horizontal;
  target.angleZ = finite(base.angleZ) + finite(life.driftAngleZ);
  target.bodyAngleX = finite(base.bodyAngleX);
  target.bodyAngleY = finite(base.bodyAngleY) * horizontal;
  target.bodyAngleZ = finite(base.bodyAngleZ);
  target.gazeX = (finite(base.gazeX) + finite(life.saccadeX)) * horizontal;
  target.gazeY = finite(base.gazeY) + finite(life.saccadeY);
  target.eyeOpen = Math.max(0, finite(base.eyeOpenMultiplier, 1) * finite(life.blinkRatio, 1));
  target.eyeSmile = finite(base.eyeSmile);
  target.mouthOpen = Math.max(0, Math.min(1, finite(mouthOpen)));
  target.breathValue = finite(life.breathValue);
  target.transitionDuration = Math.max(0.1, finite(base.transitionDuration, 0.4));
  target.gazeSpeed = Math.max(0.1, finite(base.gazeSpeed, 4));
  return target;
}

export function reactionForEvent(event) {
  return REACTION_VARIANTS[stateName(event)] || null;
}

export function reactionDuration(event, durations = {}) {
  const variant = reactionForEvent(event);
  return Number.isFinite(Number(durations[event])) ? Number(durations[event]) : (variant?.duration || 0);
}

export function reactionStates(event) {
  return reactionForEvent(event)?.states || null;
}
