/**
 * SERA Core presentation state.
 *
 * This is deliberately a view model, not a second runtime state machine. The
 * backend remains authoritative; this module only gives the renderer a stable
 * visual vocabulary for states and payloads that already arrived over WS.
 */

const STATE_DEFINITIONS = {
  OFFLINE: { label: "RUNTIME OFFLINE", cue: "Waiting for runtime connection", tone: "muted", index: "00", energy: 0.08 },
  IDLE: { label: "STANDBY", cue: "Ambient perception", tone: "cyan", index: "01", energy: 0.18 },
  LISTENING: { label: "LISTENING", cue: "Voice channel open", tone: "blue", index: "02", energy: 0.62 },
  TRANSCRIBING: { label: "DECODING", cue: "Speech becoming context", tone: "violet", index: "03", energy: 0.76 },
  THINKING: { label: "REASONING", cue: "Finding a viable path", tone: "violet", index: "04", energy: 0.9 },
  PLANNING: { label: "PLANNING", cue: "Sequencing intent", tone: "violet", index: "05", energy: 0.88 },
  EXECUTING: { label: "EXECUTING", cue: "Acting on the desktop", tone: "amber", index: "06", energy: 0.95 },
  VERIFYING: { label: "VERIFYING", cue: "Checking real-world result", tone: "green", index: "07", energy: 0.82 },
  WAITING_FOR_APPROVAL: { label: "AWAITING APPROVAL", cue: "Your decision is needed", tone: "amber", index: "08", energy: 0.55 },
  SPEAKING: { label: "SPEAKING", cue: "Voice playback active", tone: "blue", index: "09", energy: 0.72 },
  COMPLETED: { label: "COMPLETE", cue: "Task completed", tone: "green", index: "10", energy: 1.0 },
  FAILED: { label: "FAILED", cue: "Task failed", tone: "red", index: "11", energy: 0.95 },
  BROKEN: { label: "FAILED", cue: "Runtime reported a failure", tone: "red", index: "11", energy: 0.95 },
  CANCELLED: { label: "CANCELLED", cue: "Action retracted", tone: "muted", index: "12", energy: 0.3 },
};

export function getPresentationState(rawState) {
  const aliases = {
    TASK_PLANNING: "PLANNING",
    TASK_EXECUTING: "EXECUTING",
    TASK_VERIFYING: "VERIFYING",
    TASK_RECOVERING: "THINKING",
    TASK_COMPLETED: "COMPLETED",
    TASK_FAILED: "FAILED",
    TASK_CANCELLED: "CANCELLED",
    CONFIRMING_ACTION: "WAITING_FOR_APPROVAL",
    ERROR: "FAILED",
  };
  const candidate = String(rawState || "IDLE").toUpperCase();
  const state = aliases[candidate] || candidate;
  return { state, ...(STATE_DEFINITIONS[state] || STATE_DEFINITIONS.IDLE) };
}

export function describeRuntimeEvent(event, payload = {}) {
  const status = payload?.status || payload?.state;
  if (status) return getPresentationState(status);
  const eventState = {
    ACTIVATION_STARTED: "LISTENING",
    LISTENING_STARTED: "LISTENING",
    TRANSCRIPTION_STARTED: "TRANSCRIBING",
    TOOL_STARTED: "EXECUTING",
    TTS_STARTED: "SPEAKING",
    TASK_COMPLETED: "COMPLETED",
    TASK_FAILED: "FAILED",
    TASK_CANCELLED: "CANCELLED",
    SECURITY_CONFIRMATION_REQUIRED: "WAITING_FOR_APPROVAL",
  }[event];
  return eventState ? getPresentationState(eventState) : null;
}

export function applyPresentationState(root, stateModel, details = {}) {
  if (!root || !stateModel) return;
  root.dataset.state = stateModel.state;
  root.dataset.tone = stateModel.tone;
  root.style.setProperty("--state-energy", String(stateModel.energy));
  root.style.setProperty("--state-index", `"${stateModel.index}"`);

  const label = root.querySelector("[data-state-label]");
  const cue = root.querySelector("[data-state-cue]");
  const index = root.querySelector("[data-state-index]");
  const task = root.querySelector("[data-task-context]");
  const rail = root.querySelectorAll(".rail-mark");
  if (label) label.textContent = stateModel.label;
  if (cue) cue.textContent = details.cue || stateModel.cue;
  if (index) index.textContent = stateModel.index;
  if (task) task.textContent = details.task || (stateModel.state === "IDLE" ? "READY FOR A SIGNAL" : stateModel.cue.toUpperCase());
  if (rail.length) {
    const stateIndex = Math.max(0, Number(stateModel.index) - 1);
    rail.forEach((mark, markIndex) => mark.classList.toggle("active", markIndex === stateIndex % rail.length));
  }
}
