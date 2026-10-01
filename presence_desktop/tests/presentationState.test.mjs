import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const sourcePath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src/ui/presentationState.js");
const source = await readFile(sourcePath, "utf8");
const presentation = await import(`data:text/javascript;charset=utf-8,${encodeURIComponent(source)}`);

test("Mochi presentation covers every supported visual state", () => {
  const states = [
    "OFFLINE", "IDLE", "LISTENING", "TRANSCRIBING", "THINKING", "PLANNING",
    "EXECUTING", "VERIFYING", "WAITING_FOR_APPROVAL", "SPEAKING", "COMPLETED",
    "FAILED", "BROKEN", "CANCELLED",
  ];
  for (const state of states) {
    const view = presentation.getPresentationState(state);
    assert.equal(view.state, state);
    assert.ok(view.label);
    assert.ok(view.cue);
    assert.ok(view.tone);
  }
  assert.equal(presentation.getPresentationState("TASK_RECOVERING").state, "THINKING");
  assert.equal(presentation.getPresentationState("PAUSED_APPROVAL").state, "WAITING_FOR_APPROVAL");
  assert.equal(presentation.getPresentationState("SHUTDOWN").state, "OFFLINE");
});

test("event descriptions only map events that assert a visual fact", () => {
  assert.equal(presentation.describeRuntimeEvent("LISTENING_STARTED").state, "LISTENING");
  assert.equal(presentation.describeRuntimeEvent("AUDIO_PLAYBACK_STARTED").state, "SPEAKING");
  assert.equal(presentation.describeRuntimeEvent("SECURITY_CONFIRMATION_REQUIRED").state, "WAITING_FOR_APPROVAL");
  assert.equal(presentation.describeRuntimeEvent("TASK_STARTED"), null);
  assert.equal(presentation.describeRuntimeEvent("AGENT_RESPONSE", { content: "failed" }), null);
  assert.equal(presentation.describeRuntimeEvent("AGENT_RESPONSE", { status: "FAILED" }), null);
  assert.equal(presentation.describeRuntimeEvent("RUNTIME_STATE_CHANGED", { status: "TASK_VERIFYING" }).state, "VERIFYING");
});

test("DOM projection applies semantic state class, datasets, audio, and explicit progress", () => {
  const classes = new Set(["glass-panel", "state-idle"]);
  const progress = {
    hidden: true,
    value: 0,
    attrs: {},
    setAttribute(name, value) { this.attrs[name] = value; },
  };
  const elements = {
    "[data-state-label]": { textContent: "" },
    "[data-state-cue]": { textContent: "" },
    "[data-state-index]": { textContent: "" },
    "[data-task-context]": { textContent: "" },
    "[data-task-progress]": progress,
  };
  const root = {
    dataset: { state: "IDLE" },
    classList: { add: (name) => classes.add(name), remove: (name) => classes.delete(name) },
    style: { setProperty() {} },
    querySelector: (selector) => elements[selector] || null,
    querySelectorAll: () => [],
  };

  presentation.applyPresentationState(root, presentation.getPresentationState("EXECUTING"), {
    task: "Open the report",
    progress: 0.4,
    audioActive: true,
  });
  assert.equal(root.dataset.state, "EXECUTING");
  assert.equal(root.dataset.audio, "speaking");
  assert.equal(root.dataset.taskProgress, "0.4");
  assert.equal(classes.has("state-idle"), false);
  assert.equal(classes.has("state-executing"), true);
  assert.equal(progress.hidden, false);
  assert.equal(progress.value, 0.4);
  assert.equal(progress.attrs["aria-valuenow"], "40");

  presentation.applyPresentationState(root, presentation.getPresentationState("IDLE"));
  assert.equal("taskProgress" in root.dataset, false);
  assert.equal(progress.hidden, true);
});
