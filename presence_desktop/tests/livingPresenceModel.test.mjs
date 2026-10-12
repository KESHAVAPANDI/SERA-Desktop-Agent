import test from "node:test";
import assert from "node:assert/strict";
import {
  createPresenceModel,
  reducePresenceMessage,
  effectiveVisualState,
  effectivePresentationState,
  normalizeRuntimeState,
} from "../src/integration/presenceModel.js";
import { getStateProfile, LIVE2D_STATE_PROFILES, PROFILE_ALIASES } from "../src/live2d/Live2DStateProfiles.js";

const receive = (model, event, payload = {}) => reducePresenceMessage(model, { event, payload });

function workingModel() {
  let model = receive(createPresenceModel(), "TASK_STARTED", { task_id: "current", user_input: "inspect the document" });
  return receive(model, "RUNTIME_STATE_CHANGED", { status: "TASK_EXECUTING" });
}

test("speech overlay resumes the latest authoritative task state after interruption", () => {
  let model = workingModel();
  model = receive(model, "AUDIO_PLAYBACK_STARTED", { task_id: "current" });
  assert.equal(effectiveVisualState(model), "SPEAKING");
  assert.equal(model.runtimeState, "EXECUTING");
  model = receive(model, "RUNTIME_STATE_CHANGED", { status: "TASK_VERIFYING" });
  assert.equal(effectiveVisualState(model), "SPEAKING");
  model = receive(model, "TTS_INTERRUPTED", { task_id: "current" });
  assert.equal(effectiveVisualState(model), "VERIFYING", "resume current work, not the obsolete pre-speech state");
  assert.equal(model.task.status, "STARTED", "ending speech cannot mark work completed");
});

test("terminal task outcomes arbitrate above an active speech overlay", () => {
  for (const [event, expected] of [["TASK_COMPLETED", "COMPLETED"], ["TASK_FAILED", "FAILED"], ["TASK_CANCELLED", "CANCELLED"]]) {
    let model = receive(workingModel(), "TTS_STARTED", { task_id: "current" });
    model = receive(model, event, { task_id: "current" });
    assert.equal(effectiveVisualState(model), expected);
    assert.equal(model.tts.active, false);
    model = receive(model, "TTS_COMPLETED", { task_id: "current" });
    assert.equal(effectiveVisualState(model), expected, "late speech completion must not erase a terminal result");
  }
});

test("stale task speech-stop events cannot interrupt the current speech session", () => {
  for (const event of ["TTS_COMPLETED", "TTS_INTERRUPTED", "AUDIO_PLAYBACK_FINISHED"]) {
    const active = receive(workingModel(), "TTS_STARTED", { task_id: "current" });
    const model = receive(active, event, { task_id: "previous" });
    assert.equal(model.tts.active, true);
    assert.equal(effectiveVisualState(model), "SPEAKING");
    assert.equal(model.runtimeState, "EXECUTING");
  }
});

test("presentation aliases describe activity without replacing canonical runtime state", () => {
  let model = workingModel();
  model = receive(model, "TOOL_STARTED", { task_id: "current" });
  assert.equal(effectivePresentationState(model), "WORKING");
  assert.equal(effectiveVisualState(model), "EXECUTING");
  model = receive(model, "TOOL_COMPLETED", { task_id: "current" });
  assert.equal(effectivePresentationState(model), "EXECUTING");
  model = receive(model, "STREAM_START", { task_id: "current" });
  assert.equal(effectivePresentationState(model), "TYPING");
  assert.equal(effectiveVisualState(model), "EXECUTING");
  model = receive(model, "STREAM_COMPLETE", { task_id: "current" });
  assert.equal(effectivePresentationState(model), "EXECUTING");
});

test("canonical runtime aliases and Live2D profiles agree including casing and whitespace", () => {
  for (const [alias, canonical] of Object.entries(PROFILE_ALIASES)) {
    const input = `  ${alias.toLowerCase()}  `;
    assert.equal(normalizeRuntimeState(input), canonical);
    assert.equal(getStateProfile(input), LIVE2D_STATE_PROFILES[canonical]);
  }
  const unknown = normalizeRuntimeState("new_backend_state");
  assert.equal(unknown, "NEW_BACKEND_STATE", "runtime facts are retained for diagnostics");
  assert.equal(getStateProfile(unknown), LIVE2D_STATE_PROFILES.IDLE, "renderer safely handles a new backend state");
});

test("many speech start-stop cycles retain task identity, progress and runtime truth", () => {
  let model = receive(workingModel(), "PROGRESS_UPDATE", { task_id: "current", progress: 0.4 });
  for (let i = 0; i < 200; i++) {
    model = receive(model, "TTS_STARTED", { task_id: "current" });
    assert.equal(effectiveVisualState(model), "SPEAKING");
    model = receive(model, i % 2 ? "TTS_INTERRUPTED" : "AUDIO_PLAYBACK_FINISHED", { task_id: "current" });
    assert.equal(effectiveVisualState(model), "EXECUTING");
    assert.equal(model.task.id, "current");
    assert.equal(model.task.progress, 0.4);
    assert.equal(model.task.status, "STARTED");
  }
});
