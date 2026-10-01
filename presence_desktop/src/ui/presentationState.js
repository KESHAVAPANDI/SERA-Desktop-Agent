/**
 * Mochi presentation state for the SERA runtime.
 *
 * This is deliberately a view model, not a second runtime state machine. The
 * backend remains authoritative; this module only gives the renderer a stable
 * visual vocabulary for states and payloads that already arrived over WS.
 */

const STATE_DEFINITIONS = {
  OFFLINE: { label: "MOCHI IS OFFLINE", cue: "Waiting for SERA to reconnect", tone: "muted", index: "00", energy: 0.08 },
  IDLE: { label: "HERE WITH YOU", cue: "Ready when you are", tone: "cyan", index: "01", energy: 0.18 },
  LISTENING: { label: "I'M LISTENING", cue: "Go ahead", tone: "blue", index: "02", energy: 0.62 },
  TRANSCRIBING: { label: "CATCHING THAT", cue: "Turning your voice into context", tone: "violet", index: "03", energy: 0.76 },
  THINKING: { label: "THINKING IT THROUGH", cue: "Finding a good path", tone: "violet", index: "04", energy: 0.9 },
  PLANNING: { label: "MAKING A PLAN", cue: "Putting the steps in order", tone: "violet", index: "05", energy: 0.88 },
  EXECUTING: { label: "WORKING ON IT", cue: "Taking action in SERA", tone: "amber", index: "06", energy: 0.95 },
  VERIFYING: { label: "CHECKING MY WORK", cue: "Making sure it worked", tone: "green", index: "07", energy: 0.82 },
  WAITING_FOR_APPROVAL: { label: "YOUR CHOICE", cue: "SERA needs your approval to continue", tone: "amber", index: "08", energy: 0.55 },
  SPEAKING: { label: "SHARING BACK", cue: "Mochi is speaking", tone: "blue", index: "09", energy: 0.72 },
  COMPLETED: { label: "ALL SET", cue: "The task is complete", tone: "green", index: "10", energy: 1.0 },
  FAILED: { label: "I HIT A SNAG", cue: "SERA could not complete the task", tone: "red", index: "11", energy: 0.95 },
  BROKEN: { label: "I HIT A SNAG", cue: "SERA reported a problem", tone: "red", index: "11", energy: 0.95 },
  CANCELLED: { label: "STOPPED", cue: "The action was cancelled", tone: "muted", index: "12", energy: 0.3 },
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
    PAUSED_APPROVAL: "WAITING_FOR_APPROVAL",
    ERROR: "FAILED",
    SHUTDOWN: "OFFLINE",
  };
  const candidate = String(rawState || "IDLE").toUpperCase();
  const state = aliases[candidate] || candidate;
  return { state, ...(STATE_DEFINITIONS[state] || STATE_DEFINITIONS.IDLE) };
}

export function describeRuntimeEvent(event, payload = {}) {
  const eventName = String(event || "").toUpperCase();
  const status = payload?.status || payload?.state;
  if ((eventName === "RUNTIME_STATE_CHANGED" || eventName === "SNAPSHOT") && status) {
    return getPresentationState(status);
  }
  const eventState = {
    ACTIVATION_STARTED: "LISTENING",
    LISTENING_STARTED: "LISTENING",
    TRANSCRIPTION_STARTED: "TRANSCRIBING",
    TOOL_STARTED: "EXECUTING",
    TTS_STARTED: "SPEAKING",
    AUDIO_PLAYBACK_STARTED: "SPEAKING",
    TASK_COMPLETED: "COMPLETED",
    TASK_FAILED: "FAILED",
    TASK_CANCELLED: "CANCELLED",
    SECURITY_CONFIRMATION_REQUIRED: "WAITING_FOR_APPROVAL",
  }[eventName];
  return eventState ? getPresentationState(eventState) : null;
}

export function applyPresentationState(root, stateModel, details = {}) {
  if (!root || !stateModel) return;
  const previousState = root.dataset.state;
  if (previousState) root.classList.remove(`state-${previousState.toLowerCase()}`);
  root.classList.add(`state-${stateModel.state.toLowerCase()}`);
  root.dataset.state = stateModel.state;
  root.dataset.tone = stateModel.tone;
  root.dataset.audio = details.audioActive ? "speaking" : "idle";
  if (Number.isFinite(details.progress)) root.dataset.taskProgress = String(details.progress);
  else delete root.dataset.taskProgress;
  root.style.setProperty("--state-energy", String(stateModel.energy));
  root.style.setProperty("--state-index", `"${stateModel.index}"`);

  const label = root.querySelector("[data-state-label]");
  const cue = root.querySelector("[data-state-cue]");
  const index = root.querySelector("[data-state-index]");
  const task = root.querySelector("[data-task-context]");
  const progress = root.querySelector("[data-task-progress]");
  const rail = root.querySelectorAll(".rail-mark");
  if (label) label.textContent = stateModel.label;
  if (cue) cue.textContent = details.cue || stateModel.cue;
  if (index) index.textContent = stateModel.index;
  if (task) task.textContent = details.task || (stateModel.state === "IDLE" ? "READY WHEN YOU ARE" : stateModel.cue.toUpperCase());
  if (progress) {
    const hasProgress = Number.isFinite(details.progress);
    progress.hidden = !hasProgress;
    if (hasProgress) {
      progress.value = details.progress;
      progress.setAttribute("aria-valuenow", String(Math.round(details.progress * 100)));
    }
  }
  if (rail.length) {
    const stateIndex = Math.max(0, Number(stateModel.index) - 1);
    rail.forEach((mark, markIndex) => mark.classList.toggle("active", markIndex === stateIndex % rail.length));
  }
}
