import test from "node:test";
import assert from "node:assert/strict";
import { Live2DController } from "../src/live2d/Live2DController.js";
import {
  getStateProfile,
  LIVE2D_STATE_PROFILES,
  registerStateProfile,
} from "../src/live2d/Live2DStateProfiles.js";
import { Live2DColorSystem } from "../src/live2d/Live2DColorSystem.js";
import { Live2DLifeLayer } from "../src/live2d/Live2DLifeLayer.js";

// Mock Live2D Model for headless unit tests
function createMockLive2DModel() {
  const params = new Map();
  let currentExpression = null;
  let currentMotion = null;
  let destroyed = false;

  return {
    tint: 0xffffff,
    internalModel: {
      coreModel: {
        setParameterValueById: (id, val) => params.set(id, val),
        getParameterValueById: (id) => params.get(id) ?? 0,
      },
    },
    expression: (name) => { currentExpression = name; },
    motion: (group, index, priority) => { currentMotion = { group, index, priority }; },
    destroy: () => { destroyed = true; },
    // Test inspection accessors
    _getParam: (id) => params.get(id),
    _getExpression: () => currentExpression,
    _getMotion: () => currentMotion,
    _isDestroyed: () => destroyed,
  };
}

test("1. Live2D controller initializes once with clean initial state", () => {
  const controller = new Live2DController();
  assert.equal(controller.currentState, "IDLE");
  assert.equal(controller.isLoaded, false);
  assert.equal(controller.loadCount, 0);
  assert.equal(controller.stateChangeCount, 0);

  const mockModel = createMockLive2DModel();
  controller.attachModel(mockModel);

  assert.equal(controller.isLoaded, true);
  assert.equal(controller.loadCount, 1);
  assert.equal(mockModel._getExpression(), "exp_01");
});

test("2. Character instance persists across state changes without reloading", () => {
  const controller = new Live2DController();
  const mockModel = createMockLive2DModel();
  controller.attachModel(mockModel);

  assert.equal(controller.loadCount, 1);

  // Exercise multiple state changes
  controller.setState("LISTENING");
  controller.setState("THINKING");
  controller.setState("EXECUTING");
  controller.setState("VERIFYING");
  controller.setState("SPEAKING");
  controller.setState("IDLE");

  // Model instance MUST remain the exact same instance, never reloaded
  assert.equal(controller.loadCount, 1);
  assert.equal(controller.model, mockModel);
  assert.equal(controller.stateChangeCount, 6);
});

test("3. Rapid state cycling does not increment model load count", () => {
  const controller = new Live2DController();
  const mockModel = createMockLive2DModel();
  controller.attachModel(mockModel);

  const states = [
    "IDLE", "LISTENING", "TRANSCRIBING", "THINKING", "PLANNING",
    "TYPING", "WORKING", "EXECUTING", "VERIFYING", "WAITING_FOR_APPROVAL",
    "SPEAKING", "COMPLETED", "FAILED", "CANCELLED",
  ];

  for (let i = 0; i < 50; i++) {
    const s = states[i % states.length];
    controller.setState(s);
  }

  assert.equal(controller.loadCount, 1);
  assert.equal(controller.stateChangeCount, 50);
});

test("4. State profiles accurately map all 14 authoritative states", () => {
  const states = [
    "IDLE", "LISTENING", "TRANSCRIBING", "THINKING", "PLANNING",
    "TYPING", "WORKING", "EXECUTING", "VERIFYING", "WAITING_FOR_APPROVAL",
    "SPEAKING", "COMPLETED", "FAILED", "CANCELLED",
  ];

  for (const s of states) {
    const profile = getStateProfile(s);
    assert.ok(profile, `Profile for ${s} must exist`);
    assert.ok(profile.expression, `Profile for ${s} must specify an expression`);
    assert.ok(profile.motionGroup, `Profile for ${s} must specify a motion group`);
    assert.ok(Array.isArray(profile.color) && profile.color.length === 3, `Profile for ${s} must have RGB color`);
    assert.ok(typeof profile.auraIntensity === "number", `Profile for ${s} must have aura intensity`);
    assert.ok(typeof profile.transitionDuration === "number", `Profile for ${s} must have transition duration`);
  }

  // Verify semantic acting postures
  assert.equal(getStateProfile("LISTENING").expression, "exp_04");
  assert.equal(getStateProfile("COMPLETED").expression, "exp_02");
  assert.equal(getStateProfile("FAILED").expression, "exp_08");
  assert.equal(getStateProfile("WAITING_FOR_APPROVAL").expression, "exp_07");
});

test("5. Color system targets match the authoritative palette across states", () => {
  const idleProfile = getStateProfile("IDLE");
  const execProfile = getStateProfile("EXECUTING");
  const failedProfile = getStateProfile("FAILED");
  const approvalProfile = getStateProfile("WAITING_FOR_APPROVAL");

  // IDLE -> Cyan/Blue
  assert.ok(idleProfile.color[1] > 0.5 && idleProfile.color[2] > 0.8, "IDLE is cyan/blue");
  // EXECUTING -> Cyan
  assert.ok(execProfile.color[1] > 0.6 && execProfile.color[2] > 0.7, "EXECUTING is cyan");
  // FAILED -> Rose/Red
  assert.ok(failedProfile.color[0] > 0.8 && failedProfile.color[1] < 0.5, "FAILED is rose/red");
  // WAITING_FOR_APPROVAL -> Gold/Amber
  assert.ok(approvalProfile.color[0] > 0.8 && approvalProfile.color[1] > 0.6 && approvalProfile.color[2] < 0.2, "APPROVAL is gold");
});

test("6. Color transitions are smooth with exponential damping", () => {
  const colorSystem = new Live2DColorSystem([0, 0, 0], 0.0);
  colorSystem.setTargetColor([1, 1, 1], 1.0);

  // Advance by 50ms
  const frame1 = colorSystem.update(0.05);
  assert.ok(frame1.rgb[0] > 0.0 && frame1.rgb[0] < 1.0, "Color starts transitioning smoothly");
  assert.ok(frame1.aura > 0.0 && frame1.aura < 1.0, "Aura starts transitioning smoothly");

  // Advance multiple frames
  for (let i = 0; i < 20; i++) {
    colorSystem.update(0.05);
  }

  const finalFrame = colorSystem.update(0.05);
  assert.ok(finalFrame.rgb[0] > 0.98, "Color smoothly reaches target without snapping");
  assert.ok(finalFrame.aura > 0.98, "Aura smoothly reaches target without snapping");
});

test("7. Unknown state safely falls back to IDLE profile", () => {
  const fallbackProfile = getStateProfile("NONEXISTENT_STATE_XYZ");
  assert.deepEqual(fallbackProfile, LIVE2D_STATE_PROFILES.IDLE);

  const controller = new Live2DController();
  controller.setState("NONEXISTENT_STATE_XYZ");
  assert.equal(controller.targetProfile, LIVE2D_STATE_PROFILES.IDLE);
});

test("8. Speaking animation follows actual speaking lifecycle with audio modulation", () => {
  const controller = new Live2DController();
  const mockModel = createMockLive2DModel();
  controller.attachModel(mockModel);

  // Transition to SPEAKING
  controller.setState("SPEAKING");
  assert.equal(controller.targetProfile.isSpeaking, true);

  // Feed audio energy from TTS envelope
  controller.setAudioData({ rawAmp: 0.6, mid: 0.8 });

  // Update frame
  controller.update(0.016);
  assert.ok(controller.params.mouthOpen > 0.0, "Mouth opens in response to audio level");

  // Stop speaking (transition to IDLE)
  controller.setState("IDLE");
  assert.equal(controller.targetProfile.isSpeaking, false);

  // Update multiple frames to allow mouth to close smoothly
  for (let i = 0; i < 30; i++) {
    controller.update(0.016);
  }
  assert.ok(controller.params.mouthOpen < 0.01, "Mouth smoothly closes when speech ends");
});

test("9. Genuine audio silence keeps the mouth closed without fabricated cadence", () => {
  const controller = new Live2DController();
  const mockModel = createMockLive2DModel();
  controller.attachModel(mockModel);

  controller.setState("SPEAKING");
  // No audio data supplied (silence)
  controller.setAudioData({ rawAmp: 0, mid: 0 });

  controller.update(0.05);
   assert.ok(controller.params.mouthOpen < 0.01, "Silent telemetry does not invent mouth motion");
});

test("10. Horizontal controller motion remains centered and damped", () => {
  const controller = new Live2DController();
  const mockModel = createMockLive2DModel();
  controller.attachModel(mockModel);
  controller.setState("THINKING");
  for (let i = 0; i < 120; i++) controller.update(0.016);
  assert.ok(Math.abs(controller.params.angleY) < 3.0, "Head yaw stays within calm range");
  assert.ok(Math.abs(controller.params.bodyAngleY) < 1.0, "Body yaw stays within calm range");
  assert.ok(Math.abs(controller.params.gazeX) < 0.2, "Gaze drift stays subtle");
});

test("11. Model-load failure is explicitly surfaced rather than silently hidden", () => {
  const controller = new Live2DController();
  const loadErr = new Error("Failed to fetch texture_00.png 404");

  controller.setLoadError(loadErr);

  assert.equal(controller.isLoaded, false);
  assert.equal(controller.loadError, loadErr);
  assert.equal(controller.loadError.message, "Failed to fetch texture_00.png 404");
});

test("12. Continuous life layer runs across state transitions", () => {
  const life = new Live2DLifeLayer();

  const frame1 = life.update(0.016, { breathRate: 1.0 });
  assert.ok(typeof frame1.breathValue === "number");
  assert.ok(typeof frame1.blinkRatio === "number");
  assert.ok(typeof frame1.driftAngleX === "number");

  // Advance time past blink interval (~4 seconds)
  let sawBlink = false;
  for (let i = 0; i < 300; i++) {
    const f = life.update(0.016, { breathRate: 1.0 });
    if (f.blinkRatio < 0.5) sawBlink = true;
  }
  assert.ok(sawBlink, "Blinking state machine naturally closes and reopens eyes");
});

test("12. Resource cleanup disposes all controller and model references without leaks", () => {
  const controller = new Live2DController();
  const mockModel = createMockLive2DModel();
  controller.attachModel(mockModel);

  controller.dispose();

  assert.equal(controller.disposed, true);
  assert.equal(controller.model, null);
  assert.equal(controller.isLoaded, false);
  assert.equal(mockModel._isDestroyed(), true);
});

test("13. Custom state profiles can be dynamically registered and consumed", () => {
  registerStateProfile("CUSTOM_RESEARCH", {
    expression: "exp_06",
    color: [0.35, 0.85, 0.95],
    angleY: 5.0,
    motionGroup: "Idle",
  });

  const custom = getStateProfile("CUSTOM_RESEARCH");
  assert.equal(custom.expression, "exp_06");
  assert.equal(custom.angleY, 5.0);
  assert.deepEqual(custom.color, [0.35, 0.85, 0.95]);

  const controller = new Live2DController();
  controller.setState("CUSTOM_RESEARCH");
  assert.equal(controller.targetProfile.expression, "exp_06");
});
