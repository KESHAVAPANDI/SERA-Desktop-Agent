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
