import test from "node:test";
import assert from "node:assert/strict";
import { Live2DController } from "../src/live2d/Live2DController.js";
import { Live2DLifeLayer } from "../src/live2d/Live2DLifeLayer.js";
import { getStateProfile, LIVE2D_STATE_PROFILES } from "../src/live2d/Live2DStateProfiles.js";
import {
  BEHAVIOR_PRIORITY,
  PARAMETER_OWNERSHIP,
  composeBehaviorLayers,
} from "../src/live2d/Live2DBehavior.js";

// Mock only the Cubism boundary. Parameter composition, damping, profiles,
// life-layer scheduling, and speech freshness all run production code.
function fixture(t, options = {}) {
  const values = new Map();
  const listeners = new Map();
  const calls = { expressions: [], motions: [], hooks: [] };
  const model = {
    tint: 0xffffff,
    internalModel: {
      coreModel: {
        setParameterValueById(id, value) { values.set(id, value); },
        getParameterValueById(id) { return values.get(id) ?? 0; },
      },
      motionManager: { definitions: options.motionDefinitions },
      on(event, handler) { listeners.set(event, handler); calls.hooks.push(["on", event]); },
      off(event, handler) {
        if (listeners.get(event) === handler) listeners.delete(event);
        calls.hooks.push(["off", event]);
      },
    },
    expression(name) { calls.expressions.push(name); },
    motion(...args) { calls.motions.push(args); },
    destroy() {},
    _emit(event) { listeners.get(event)?.(); },
  };
  const controller = new Live2DController(options);
  controller.attachModel(model);
  t.after(() => controller.dispose());
  return { controller, model, values, calls };
}

function step(controller, frames, delta = 1 / 60) {
  for (let i = 0; i < frames; i++) controller.update(delta);
}

function seededRandom(seed) {
  let value = seed >>> 0;
  return () => {
    value = (Math.imul(value, 1664525) + 1013904223) >>> 0;
    return value / 0x100000000;
  };
}

test("behavior layers have explicit ownership and higher-priority conflict resolution", () => {
  assert.deepEqual(BEHAVIOR_PRIORITY, ["expressionPosture", "task", "attention", "speech", "transientReaction"]);
  assert.ok(PARAMETER_OWNERSHIP.life.includes("driftAngleY"));
  assert.ok(PARAMETER_OWNERSHIP.speech.includes("mouthOpen"));
  const target = composeBehaviorLayers(
    { gazeX: 0, eyeSmile: 0, mouthOpen: 0 },
    {
      task: { gazeX: 0.1, eyeSmile: 0.2 },
      attention: { gazeX: 0.2 },
      speech: { mouthOpen: 0.8 },
      transientReaction: { gazeX: 0.3, eyeSmile: 0.9 },
    },
  );
  assert.equal(target.gazeX, 0.3);
  assert.equal(target.eyeSmile, 0.9);
  assert.equal(target.mouthOpen, 0.8);
});

test("transient reactions survive state projection, then restore the canonical profile", (t) => {
  const { controller, calls } = fixture(t, { random: () => 0.5 });
  controller.setState("EXECUTING");
  const baseExpression = getStateProfile("EXECUTING").expression;
  controller.triggerEvent("TOOL_COMPLETED");
  controller.setState("EXECUTING");
  assert.equal(controller.resolvedTarget.expression, "exp_02");
  assert.equal(controller.params.eyeSmile, 0);
  step(controller, 1);
  assert.ok(calls.expressions.includes("exp_02"));
  step(controller, 50);
  assert.equal(controller.resolvedTarget.expression, baseExpression);
  assert.equal(calls.expressions.at(-1), baseExpression);
});

test("task context activates only in processing states and offline remains non-speaking", (t) => {
  const { controller, values } = fixture(t, { random: () => 0.5, now: () => 10000 });
  controller.setState("IDLE", "SEARCH");
  assert.equal(controller.resolvedTarget.gazeX, getStateProfile("IDLE").gazeX);
  controller.setState("EXECUTING", "SEARCH");
  assert.equal(controller.resolvedTarget.gazeX, getStateProfile("EXECUTING").gazeX - 0.04);
  controller.setState("WAITING_FOR_APPROVAL", "GENERAL");
  controller.triggerEvent("SECURITY_CONFIRMATION_REQUIRED");
  assert.equal(controller.resolvedTarget.expression, "exp_07");
  controller.setState("OFFLINE");
  controller.setAudioData({ rawAmp: 1, mid: 1 });
  controller.update(1 / 60);
  assert.equal(controller.resolvedTarget.expression, "exp_03");
  assert.equal(values.get("ParamA"), 0);
});

test("stale task reactions are ignored and model motion falls back to supported capabilities", (t) => {
  const { controller, calls } = fixture(t, {
    random: () => 0.5,
    motionDefinitions: { Idle: [{}], TapBody: [{}] },
  });
  controller.triggerEvent("TASK_STARTED", { task_id: "current" });
  controller.setState("EXECUTING");
  controller.triggerEvent("TASK_COMPLETED", { task_id: "old" });
  assert.equal(controller.behaviorContext.reaction, null);
  assert.equal(controller.resolvedTarget.expression, getStateProfile("EXECUTING").expression);
  assert.deepEqual(calls.motions.at(-1), ["Idle", 0, 2]);
});

test("Cubism parameter ownership hook is removed before model destruction", (t) => {
  const { controller, model, calls } = fixture(t);
  controller.update(1 / 60);
  model._emit("beforeModelUpdate");
  assert.ok(calls.hooks.some(([kind, event]) => kind === "on" && event === "beforeModelUpdate"));
  controller.dispose();
  assert.ok(calls.hooks.some(([kind, event]) => kind === "off" && event === "beforeModelUpdate"));
  model._emit("beforeModelUpdate");
});

test("life layer replay is deterministic under controlled randomness and still varies during idle", () => {
  const sample = () => {
    const life = new Live2DLifeLayer({ random: seededRandom(2026) });
    return Array.from({ length: 900 }, () => ({ ...life.update(1 / 60, getStateProfile("IDLE")) }));
  };
  const first = sample();
  assert.deepEqual(sample(), first, "same input clock and random stream must reproduce the life layer");
  const other = new Live2DLifeLayer({ random: seededRandom(2027) });
  const otherFrames = Array.from({ length: 900 }, () => ({ ...other.update(1 / 60, getStateProfile("IDLE")) }));
  assert.notDeepEqual(otherFrames, first, "different random streams vary gaze/blink timing");
  assert.ok(first.some((frame) => frame.blinkRatio < 0.1), "idle includes a blink");
  assert.ok(first.some((frame) => Math.abs(frame.saccadeX) > 0.001), "idle changes fixation");
  assert.ok(Math.max(...first.map((frame) => frame.breathValue)) > 0.9);
  assert.ok(Math.min(...first.map((frame) => frame.breathValue)) < 0.1);
  for (const frame of first) {
    assert.ok(frame.blinkRatio >= 0 && frame.blinkRatio <= 1);
    assert.ok(frame.breathValue >= 0 && frame.breathValue <= 1);
    assert.ok(Math.abs(frame.saccadeX) <= 0.04);
    assert.ok(Math.abs(frame.saccadeY) <= 0.03);
  }
});

test("state posture, continuous breathing, blinking and gaze compose on the same model", (t) => {
  const { controller, model, values } = fixture(t, { random: () => 0.5 });
  controller.setState("THINKING");
  const breaths = [];
  let sawBlink = false;
  for (let i = 0; i < 450; i++) {
    controller.update(1 / 60);
    breaths.push(values.get("ParamBreath"));
    sawBlink ||= values.get("ParamEyeLOpen") < 0.5;
    assert.equal(values.get("ParamEyeLOpen"), values.get("ParamEyeROpen"));
    assert.equal(values.get("ParamA"), 0, "thinking does not fabricate speech");
  }
  assert.ok(sawBlink, "a semantic posture does not suppress all biological blinking");
  assert.ok(Math.max(...breaths) - Math.min(...breaths) > 0.8);
  assert.ok(Math.abs(values.get("ParamAngleX")) > 0.5, "thinking contributes a visible posture");
  assert.notEqual(values.get("ParamEyeBallX"), 0, "thinking contributes gaze intent");
  assert.equal(controller.model, model);
  assert.equal(controller.loadCount, 1);
});

test("life phase continues through listening, work, speaking interruption and idle resumption", (t) => {
  const { controller } = fixture(t, { random: () => 0.5 });
  const life = controller.lifeLayer;
  let elapsed = 0;
  for (const state of ["IDLE", "LISTENING", "EXECUTING", "SPEAKING", "EXECUTING", "IDLE"]) {
    controller.setState(state);
    step(controller, 30, 0.02);
    elapsed += 0.6;
    assert.equal(controller.lifeLayer, life, "transition retains the continuous layer");
    assert.ok(Math.abs(life.time - elapsed) < 1e-9, "transition must not reset accumulated life time");
  }
});

test("every built-in state stays horizontally bounded over a long transition sequence", (t) => {
  const { controller, values } = fixture(t, { random: seededRandom(42) });
  for (let cycle = 0; cycle < 8; cycle++) {
    for (const state of Object.keys(LIVE2D_STATE_PROFILES)) {
      controller.setState(state);
      for (let i = 0; i < 90; i++) {
        controller.update(1 / 60);
        // Cubism X is yaw; retain checks on Y too because the legacy controller
        // also dampens that channel as part of its side-motion policy.
        for (const [id, bound] of [["ParamAngleX", 8], ["ParamAngleY", 3], ["ParamBodyAngleX", 5], ["ParamBodyAngleY", 1.5], ["ParamEyeBallX", 0.2]]) {
          const value = values.get(id);
          assert.ok(Number.isFinite(value) && Math.abs(value) <= bound, `${state}: ${id}=${value} exceeds ${bound}`);
        }
      }
    }
  }
  assert.equal(controller.loadCount, 1);
});

test("repeated state delivery does not restart authored motion or expression", (t) => {
  const { controller, calls } = fixture(t);
  controller.setState("EXECUTING", "GENERAL", 0.2);
  const motionCount = calls.motions.length;
  const expressionCount = calls.expressions.length;
  for (let i = 0; i < 200; i++) {
    controller.setState("EXECUTING", "GENERAL", i / 200);
    controller.update(1 / 60);
  }
  assert.equal(calls.motions.length, motionCount);
  assert.equal(calls.expressions.length, expressionCount);
  assert.equal(controller.loadCount, 1);
});

test("repeated interruptions settle back to idle without cumulative posture drift", (t) => {
  const { controller, values } = fixture(t, { random: () => 0.5 });
  for (let i = 0; i < 100; i++) {
    for (const state of ["THINKING", "LISTENING", "EXECUTING", "FAILED", "IDLE"]) {
      controller.setState(state);
      step(controller, 5);
    }
  }
  step(controller, 600);
  for (const id of ["ParamBodyAngleX", "ParamBodyAngleY", "ParamBodyAngleZ"]) {
    assert.ok(Math.abs(values.get(id)) < 0.01, `${id} must recover its neutral baseline`);
  }
  assert.ok(Math.abs(values.get("ParamAngleX")) < 1.2, "only bounded idle life drift remains");
  assert.ok(Math.abs(values.get("ParamEyeBallX")) < 0.05);
  assert.equal(values.get("ParamA"), 0);
  assert.equal(controller.loadCount, 1);
});

test("unknown and empty states have the same safe profile fallback as IDLE", (t) => {
  const { controller, values } = fixture(t);
  for (const state of ["UNRECOGNIZED_BACKEND_STATE", "", null, undefined, "  "]) {
    assert.equal(getStateProfile(state), LIVE2D_STATE_PROFILES.IDLE);
    controller.setState(state);
    step(controller, 10);
    assert.equal(controller.targetProfile, LIVE2D_STATE_PROFILES.IDLE);
    assert.ok([...values.values()].every(Number.isFinite));
    assert.equal(values.get("ParamA"), 0);
  }
});

test("speech accepts fresh telemetry but closes exactly at the stale cutoff", (t) => {
  let now = 10000;
  const { controller, values } = fixture(t, { now: () => now });
  controller.setState("SPEAKING");
  controller.setAudioData({ rawAmp: 0.9, mid: 0.9 });
  now += 299;
  controller.update(0.1);
  assert.ok(values.get("ParamA") > 0.5, "299 ms old telemetry remains usable");
  now += 1;
  controller.update(0.1);
  assert.equal(values.get("ParamA"), 0, "300 ms old telemetry must stop driving speech");
  now += 60000;
  step(controller, 60);
  assert.equal(values.get("ParamA"), 0, "stale amplitude never invents a speech cadence");
  controller.setAudioData({ rawAmp: 0.7, mid: 0.7 });
  controller.update(0.1);
  assert.ok(values.get("ParamA") > 0.1, "fresh playback can resume after stale stop");
});

test("speech interruption overrides still-fresh amplitude and closes smoothly", (t) => {
  const { controller, values } = fixture(t, { now: () => 10000 });
  controller.setState("SPEAKING");
  controller.setAudioData({ rawAmp: 1, mid: 1 });
  step(controller, 10);
  const open = values.get("ParamA");
  assert.ok(open > 0.5);
  controller.setState("LISTENING");
  controller.update(1 / 60);
  assert.ok(values.get("ParamA") < open, "new semantic state immediately stops opening the mouth");
  step(controller, 90);
  assert.ok(values.get("ParamA") < 1e-6);
});

test("silent and absent telemetry never animate a speaking mouth", (t) => {
  const { controller, values } = fixture(t, { now: () => 10000 });
  controller.setState("SPEAKING");
  step(controller, 120);
  assert.equal(values.get("ParamA"), 0);
  controller.setAudioData({ rawAmp: 0, mid: 0 });
  step(controller, 120);
  assert.equal(values.get("ParamA"), 0);
  controller.setAudioData({ rawAmp: 1, mid: 1 });
  step(controller, 10);
  for (let i = 0; i < 100; i++) {
    controller.setAudioData({ rawAmp: 0, mid: 0 });
    controller.update(1 / 60);
  }
  assert.ok(values.get("ParamA") < 1e-6, "silence settles even while fresh packets keep arriving");
});

test("fresh amplitude alone does not authorize speech in non-speaking states", (t) => {
  const { controller, values } = fixture(t, { now: () => 10000 });
  for (const state of ["IDLE", "LISTENING", "THINKING", "EXECUTING", "WAITING_FOR_APPROVAL", "FAILED", "OFFLINE"]) {
    controller.setState(state);
    controller.setAudioData({ rawAmp: 1, mid: 1 });
    step(controller, 30);
    assert.equal(values.get("ParamA"), 0, `${state} cannot become speech from amplitude alone`);
  }
});
