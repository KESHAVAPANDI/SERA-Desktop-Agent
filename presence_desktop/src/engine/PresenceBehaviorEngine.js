import { DEFAULT_FOLD_STATE, getFoldProfile } from "./CognitiveFoldProfiles.js";

const clamp01 = (value) => Math.max(0, Math.min(1, Number(value) || 0));
const damp = (current, target, rate, delta) => current + (target - current) * (1 - Math.exp(-rate * delta));

/** Smooths runtime-owned state into renderer parameters. Never changes state. */
export class PresenceBehaviorEngine {
  constructor({ reducedMotion = false } = {}) {
    this.state = DEFAULT_FOLD_STATE;
    this.taskType = "GENERAL";
    this.taskProgress = 0;
    this.time = 0;
    this.reducedMotion = reducedMotion;
    this.target = getFoldProfile(this.state);
    this.values = { ...this.target };
    this.audio = { rawAmp: 0, bass: 0, mid: 0, treble: 0 };
    this.impulses = { flash: 0, projection: 0, return: 0, anomaly: 0 };
    this.task = { type: null, objective: "", direction: 0 };
  }

  setReducedMotion(value) {
    this.reducedMotion = Boolean(value);
  }

  setState(state, taskType = "GENERAL", progress = 0) {
    this.state = getFoldProfile(state) === getFoldProfile(DEFAULT_FOLD_STATE) && state !== DEFAULT_FOLD_STATE
      ? DEFAULT_FOLD_STATE
      : state;
    this.taskType = taskType || "GENERAL";
    this.taskProgress = clamp01(progress);
    this.target = getFoldProfile(this.state);
  }

  setTaskVisualization(taskType, objective = "") {
    const text = `${taskType || ""}:${objective || ""}`;
    let hash = 0;
    for (let index = 0; index < text.length; index += 1) hash = ((hash << 5) - hash + text.charCodeAt(index)) | 0;
    this.task = {
      type: taskType || null,
      objective: String(objective || ""),
      direction: ((Math.abs(hash) % 201) / 100) - 1,
    };
  }

  triggerEvent(eventType, payload = {}) {
    if (eventType === "MODEL_SELECTED") this.impulses.flash = 0.8;
    if (eventType === "TOOL_STARTED") this.impulses.projection = 1;
    if (eventType === "TOOL_COMPLETED") this.impulses.return = 1;
    if (eventType === "FALLBACK") this.impulses.anomaly = 0.85;
    if (eventType === "PROGRESS_UPDATE" && payload.progress !== undefined) {
      this.taskProgress = clamp01(payload.progress);
    }
    // TASK_COMPLETED and TASK_CANCELLED intentionally do not mutate state.
  }

  setAudioData(bands = {}) {
    for (const key of Object.keys(this.audio)) {
      const incoming = clamp01(bands[key]);
      const amount = incoming > this.audio[key] ? 0.62 : 0.16;
      this.audio[key] += (incoming - this.audio[key]) * amount;
      if (this.audio[key] < 0.008) this.audio[key] = 0;
    }
  }

  update(delta) {
    const dt = Math.min(0.05, Math.max(0, delta || 0));
    this.time += dt;
    const geometryKeys = ["energy", "aperture", "spread", "skew", "direction", "speed", "ripple", "tension", "density", "opacity"];
    for (const key of geometryKeys) this.values[key] = damp(this.values[key], this.target[key], 4.2, dt);
    for (const key of ["folds", "threads", "signals"]) this.values[key] = damp(this.values[key], this.target[key], 6, dt);

    const decay = Math.exp(-3.4 * dt);
    for (const key of Object.keys(this.impulses)) this.impulses[key] *= decay;

    const motionScale = this.reducedMotion ? 0.12 : 1;
    const voice = this.audio.rawAmp * 0.55 + this.audio.mid * 0.3;
    return {
      ...this.values,
      state: this.state,
      taskType: this.taskType,
      progress: this.taskProgress,
      accent: this.target.accent,
      secondary: this.target.secondary,
      time: this.time,
      phase: this.time * this.values.speed * this.values.direction * motionScale,
      motionScale,
      voice,
      audio: this.audio,
      impulses: this.impulses,
      task: this.task,
    };
  }
}
