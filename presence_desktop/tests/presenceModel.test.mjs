import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src");
async function importJs(relative) {
  const source = await readFile(path.join(root, relative), "utf8");
  return import(`data:text/javascript;charset=utf-8,${encodeURIComponent(source)}`);
}
const model = await importJs("integration/presenceModel.js");

test("snapshot establishes runtime and active task identity", () => {
  let state = model.createPresenceModel();
  state = model.reducePresenceMessage(state, {
    event: "SNAPSHOT",
    data: { status: "TASK_EXECUTING", runtime_attached: true, active_task_info: { task_id: "t-1", user_input: "open file", status: "EXECUTING" } },
  });
  assert.equal(state.runtimeState, "EXECUTING");
  assert.equal(state.task.id, "t-1");
  assert.equal(state.userCaption, "open file");
});

test("TASK_STARTED does not invent PLANNING and terminal events reject stale task ids", () => {
  let state = model.createPresenceModel();
  state = model.reducePresenceMessage(state, { event: "RUNTIME_STATE_CHANGED", payload: { status: "THINKING" } });
  state = model.reducePresenceMessage(state, { event: "TASK_STARTED", payload: { task_id: "new", user_input: "actual task" } });
  assert.equal(state.runtimeState, "THINKING");
  const unchanged = model.reducePresenceMessage(state, { event: "TASK_COMPLETED", payload: { task_id: "old", result: "stale" } });
  assert.equal(unchanged.runtimeState, "THINKING");
  assert.equal(unchanged.responseCaption, "");
});

test("TTS is an overlay and does not terminally complete the task", () => {
  let state = model.createPresenceModel();
  state = model.reducePresenceMessage(state, { event: "TASK_STARTED", payload: { task_id: "t-2", user_input: "say it" } });
  state = model.reducePresenceMessage(state, { event: "TTS_STARTED", payload: { task_id: "t-2" } });
  assert.equal(state.tts.active, true);
  assert.equal(state.runtimeState, "IDLE");
  assert.equal(model.effectiveVisualState(state), "SPEAKING");
  state = model.reducePresenceMessage(state, { event: "TTS_COMPLETED", payload: { task_id: "t-2" } });
  assert.equal(state.tts.active, false);
  assert.equal(state.runtimeState, "IDLE");
});

test("turn ids prevent late transcription from replacing current caption", () => {
  let state = model.createPresenceModel();
  state = model.reducePresenceMessage(state, { event: "LISTENING_STARTED", payload: { turn_id: "turn-2" } });
  state = model.reducePresenceMessage(state, { event: "PARTIAL_TRANSCRIPTION", payload: { turn_id: "turn-1", partial: "late" } });
  assert.equal(state.userCaption, "");
});

test("runtime aliases cover lifecycle, approval, error, and shutdown states", () => {
  const mappings = {
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
  };
  for (const [runtimeState, visualState] of Object.entries(mappings)) {
    assert.equal(model.normalizeRuntimeState(runtimeState), visualState);
  }
});

test("only explicit runtime progress is carried and normalized", () => {
  let state = model.createPresenceModel();
  state = model.reducePresenceMessage(state, {
    event: "TASK_STARTED",
    payload: { task_id: "progress-task", user_input: "do several steps", progress: 25 },
  });
  assert.equal(state.task.progress, 0.25);
  state = model.reducePresenceMessage(state, {
    event: "PROGRESS_UPDATE",
    payload: { task_id: "progress-task", progress: { current: 3, total: 4 } },
  });
  assert.equal(state.task.progress, 0.75);

  const unchanged = model.reducePresenceMessage(state, {
    event: "PROGRESS_UPDATE",
    payload: { task_id: "another-task", progress: 1 },
  });
  assert.equal(unchanged.task.progress, 0.75);
  assert.equal(model.progressOf({}), null);
});

test("approval and response facts do not fabricate follow-on runtime states", () => {
  let state = model.createPresenceModel();
  state = model.reducePresenceMessage(state, { event: "TASK_STARTED", payload: { task_id: "approval-task" } });
  state = model.reducePresenceMessage(state, {
    event: "SECURITY_CONFIRMATION_REQUIRED",
    payload: { task_id: "approval-task", action: "Delete file", reason: "Destructive action", request_id: "r-1" },
  });
  assert.equal(state.runtimeState, "WAITING_FOR_APPROVAL");
  assert.deepEqual(state.approval, { action: "Delete file", reason: "Destructive action", requestId: "r-1" });

  state = model.reducePresenceMessage(state, {
    event: "AGENT_RESPONSE",
    payload: { task_id: "approval-task", content: "The operation failed in this sentence." },
  });
  assert.equal(state.runtimeState, "WAITING_FOR_APPROVAL");
  state = model.reducePresenceMessage(state, { event: "APPROVAL_RESOLVED", payload: { task_id: "approval-task" } });
  assert.equal(state.approval, null);
  assert.equal(state.runtimeState, "WAITING_FOR_APPROVAL");
});

test("connection and audio status remain independent runtime facts", () => {
  let state = model.withConnection(model.createPresenceModel(), "online");
  assert.equal(state.connection, "ONLINE");
  state = model.reducePresenceMessage(state, { event: "RUNTIME_STATE_CHANGED", payload: { status: "TASK_VERIFYING" } });
  state = model.reducePresenceMessage(state, { event: "AUDIO_PLAYBACK_STARTED", payload: {} });
  assert.equal(state.runtimeState, "VERIFYING");
  assert.equal(model.effectiveVisualState(state), "SPEAKING");
  state = model.reducePresenceMessage(state, { event: "AUDIO_PLAYBACK_FINISHED", payload: {} });
  assert.equal(model.effectiveVisualState(state), "VERIFYING");
});
