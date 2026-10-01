const TERMINAL_EVENTS = new Set(["TASK_COMPLETED", "TASK_FAILED", "TASK_CANCELLED"]);

const RUNTIME_STATE_ALIASES = {
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

function text(value) {
  return typeof value === "string" ? value : "";
}

export function normalizeRuntimeState(value) {
  const state = text(value).trim().toUpperCase() || "IDLE";
  return RUNTIME_STATE_ALIASES[state] || state;
}

export function createPresenceModel() {
  return {
    connection: "CONNECTING",
    runtimeAttached: null,
    runtimeState: "IDLE",
    task: null,
    turnId: null,
    userCaption: "",
    userCaptionFinal: false,
    responseCaption: "",
    responseStatus: "",
    approval: null,
    tts: { active: false, taskId: null },
    lastEvent: null,
  };
}

function payloadOf(message) {
  if (!message || typeof message !== "object") return {};
  const candidate = message.payload ?? message.data;
  return candidate && typeof candidate === "object" ? candidate : {};
}

function idOf(payload, key) {
  const value = payload?.[key];
  return typeof value === "string" && value ? value : null;
}

function isStaleTask(model, payload) {
  const incoming = idOf(payload, "task_id");
  return Boolean(incoming && model.task?.id && incoming !== model.task.id);
}

function isStaleTurn(model, payload) {
  const incoming = idOf(payload, "turn_id");
  return Boolean(incoming && model.turnId && incoming !== model.turnId);
}

function explicitTaskType(payload) {
  const value = payload?.task_type ?? payload?.taskType ?? payload?.category;
  return text(value).trim().toUpperCase() || "GENERAL";
}

function taskFromSnapshot(snapshot) {
  const info = snapshot.active_task_info;
  if (!info || typeof info !== "object") {
    const label = text(snapshot.active_task);
    return label ? { id: null, turnId: null, text: label, type: "GENERAL", status: "" } : null;
  }
  return {
    id: idOf(info, "task_id"),
    turnId: idOf(info, "turn_id") || idOf(info, "task_id"),
    text: text(info.user_input) || text(snapshot.active_task),
    type: explicitTaskType(info),
    status: text(info.status).toUpperCase(),
  };
}

/** Pure reducer: backend facts in, presentation model out. */
export function reducePresenceMessage(current, message) {
  const model = current || createPresenceModel();
  const event = text(message?.event).toUpperCase();
  const payload = payloadOf(message);
  if (!event) return model;

  if (event === "SNAPSHOT") {
    const task = taskFromSnapshot(payload);
    return {
      ...model,
      runtimeAttached: Boolean(payload.runtime_attached),
      runtimeState: normalizeRuntimeState(payload.status),
      task,
      turnId: task?.turnId || null,
      userCaption: task?.text || model.userCaption,
      userCaptionFinal: Boolean(task?.text),
      approval: payload.pending_confirmation || null,
      tts: { active: false, taskId: null },
      lastEvent: event,
    };
  }

  if (TERMINAL_EVENTS.has(event) && isStaleTask(model, payload)) return model;
  if ((event === "PARTIAL_TRANSCRIPTION" || event === "TRANSCRIPTION_COMPLETED") && isStaleTurn(model, payload)) return model;

  const next = { ...model, lastEvent: event };
  switch (event) {
    case "RUNTIME_STATE_CHANGED":
      next.runtimeState = normalizeRuntimeState(payload.status ?? payload.state);
      if (text(payload.task) && next.task) next.task = { ...next.task, text: payload.task };
      break;
    case "ACTIVATION_STARTED":
    case "LISTENING_STARTED":
      next.runtimeState = "LISTENING";
      next.turnId = idOf(payload, "turn_id");
      next.userCaption = "";
      next.userCaptionFinal = false;
      next.responseCaption = "";
      next.responseStatus = "";
      next.approval = null;
      break;
    case "TRANSCRIPTION_STARTED":
      next.runtimeState = "TRANSCRIBING";
      next.turnId = idOf(payload, "turn_id") || next.turnId;
      break;
    case "PARTIAL_TRANSCRIPTION":
      next.turnId = idOf(payload, "turn_id") || next.turnId;
      next.userCaption = text(payload.partial) || text(payload.transcript);
      next.userCaptionFinal = false;
      break;
    case "TRANSCRIPTION_COMPLETED":
      next.turnId = idOf(payload, "turn_id") || next.turnId;
      next.userCaption = text(payload.transcript);
      next.userCaptionFinal = Boolean(payload.is_final ?? true);
      break;
    case "TASK_STARTED": {
      const taskId = idOf(payload, "task_id");
      next.task = {
        id: taskId,
        turnId: idOf(payload, "turn_id") || taskId,
        text: text(payload.user_input) || text(payload.task),
        type: explicitTaskType(payload),
        status: "STARTED",
      };
      next.turnId = next.task.turnId || next.turnId;
      // TASK_STARTED does not assert a planning state. Await runtime state.
      break;
    }
    case "TOOL_STARTED":
      if (!isStaleTask(model, payload)) next.runtimeState = "EXECUTING";
      break;
    case "SECURITY_CONFIRMATION_REQUIRED":
      if (!isStaleTask(model, payload)) {
        next.runtimeState = "WAITING_FOR_APPROVAL";
        next.approval = {
          action: text(payload.action) || text(payload.prompt),
          reason: text(payload.reason),
          requestId: idOf(payload, "request_id") || idOf(payload, "action_id"),
        };
      }
      break;
    case "APPROVAL_RESOLVED":
      next.approval = null;
      break;
    case "AGENT_RESPONSE": {
      if (isStaleTask(model, payload)) break;
      const response = text(payload.content) || text(payload.text) || text(payload.response);
      if (response) next.responseCaption = response;
      next.responseStatus = text(payload.status).toUpperCase() || "RESPONSE";
      break;
    }
    case "TTS_STARTED":
    case "AUDIO_PLAYBACK_STARTED":
      if (!isStaleTask(model, payload)) next.tts = { active: true, taskId: idOf(payload, "task_id") };
      break;
    case "TTS_COMPLETED":
    case "TTS_INTERRUPTED":
    case "AUDIO_PLAYBACK_FINISHED":
      if (!isStaleTask(model, payload)) next.tts = { active: false, taskId: null };
      break;
    case "TASK_COMPLETED":
      next.runtimeState = "COMPLETED";
      next.task = next.task ? { ...next.task, status: "COMPLETED" } : next.task;
      next.tts = { active: false, taskId: null };
      if (!next.responseCaption && text(payload.result)) next.responseCaption = payload.result;
      next.responseStatus = "COMPLETE";
      break;
    case "TASK_FAILED":
      next.runtimeState = "FAILED";
      next.task = next.task ? { ...next.task, status: "FAILED" } : next.task;
      next.tts = { active: false, taskId: null };
      next.responseStatus = "FAILED";
      break;
    case "TASK_CANCELLED":
      next.runtimeState = "CANCELLED";
      next.task = next.task ? { ...next.task, status: "CANCELLED" } : next.task;
      next.tts = { active: false, taskId: null };
      next.responseStatus = "CANCELLED";
      break;
  }
  return next;
}

export function withConnection(model, connection) {
  return { ...model, connection: text(connection).toUpperCase() || "OFFLINE" };
}

export function effectiveVisualState(model) {
  return model?.tts?.active ? "SPEAKING" : normalizeRuntimeState(model?.runtimeState);
}
