import {
  DEFAULT_FOLD_STATE,
  getBackendCompatibleProfileState,
  getFoldProfile,
  isFoldState,
} from "./CognitiveFoldProfiles.js";

const clamp01 = (value) => Math.max(0, Math.min(1, Number(value) || 0));
const damp = (current, target, rate, delta) => current + (target - current) * (1 - Math.exp(-rate * delta));
const dampColor = (current, target, rate, delta) => {
  const amount = 1 - Math.exp(-rate * delta);
  const channel = (shift) => Math.round(((current >> shift) & 255) + (((target >> shift) & 255) - ((current >> shift) & 255)) * amount);
  return (channel(16) << 16) | (channel(8) << 8) | channel(0);
};
const COLOR_KEYS = ["accent", "secondary", "core"];
const NUMERIC_KEYS = Object.keys(getFoldProfile(DEFAULT_FOLD_STATE)).filter((key) => !COLOR_KEYS.includes(key));

/**
 * Converts runtime-owned state into continuous acting parameters for SERA.
 * It never advances or repairs operational state; renderers only consume the
 * interpolated pose returned by update().
 */
export class PresenceBehaviorEngine {
  constructor({ reducedMotion = false, lowPower = false } = {}) {
    this.state = DEFAULT_FOLD_STATE;
    this.profileState = DEFAULT_FOLD_STATE;
    this.taskType = "GENERAL";
    this.taskProgress = 0;
    this.time = 0;
    this.reducedMotion = Boolean(reducedMotion);
    this.lowPower = Boolean(lowPower);
    this.target = getFoldProfile(this.state);
    this.values = { ...this.target };
    this.colors = Object.fromEntries(COLOR_KEYS.map((key) => [key, this.target[key]]));
    this.audio = { rawAmp: 0, bass: 0, mid: 0, treble: 0 };
    this.impulses = { flash: 0, projection: 0, return: 0, anomaly: 0 };
    this.task = { type: null, objective: "", direction: 0 };
  }

  setReducedMotion(value) {
    this.reducedMotion = Boolean(value);
  }

  setState(state, taskType = "GENERAL", progress = 0) {
    this.state = isFoldState(state) ? state : DEFAULT_FOLD_STATE;
    this.profileState = getBackendCompatibleProfileState(this.state);
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
    if (eventType === "PROGRESS_UPDATE" && payload.progress !== undefined) this.taskProgress = clamp01(payload.progress);
    // Events may add a brief gesture, but cannot manufacture runtime state.
  }

  setAudioData(bands = {}) {
    for (const key of Object.keys(this.audio)) {
      const incoming = clamp01(bands[key]);
      this.audio[key] += (incoming - this.audio[key]) * (incoming > this.audio[key] ? 0.62 : 0.16);
      if (this.audio[key] < 0.008) this.audio[key] = 0;
    }
  }

  update(delta) {
    const dt = Math.min(0.05, Math.max(0, Number(delta) || 0));
    this.time += dt;
    for (const key of NUMERIC_KEYS) this.values[key] = damp(this.values[key], this.target[key], 4.4, dt);
    for (const key of COLOR_KEYS) this.colors[key] = dampColor(this.colors[key], this.target[key], 3.2, dt);

    const decay = Math.exp(-3.4 * dt);
    for (const key of Object.keys(this.impulses)) this.impulses[key] *= decay;

    const motionScale = this.reducedMotion ? 0.12 : (this.lowPower ? 0.7 : 1);
    const voice = (this.audio.rawAmp * 0.5 + this.audio.mid * 0.32 + this.audio.bass * 0.18) * motionScale;
    const blinkPhase = Math.sin(this.time * Math.PI * 2 * this.values.blinkRate + 1.1);
    const blink = clamp01((blinkPhase - 0.92) / 0.08) * this.values.blinkDepth;

    return {
      ...this.values,
      ...this.colors,
      state: this.state,
      profileState: this.profileState,
      taskType: this.taskType,
      progress: this.taskProgress,
      time: this.time,
      phase: this.time * this.values.speed * motionScale,
      motionScale,
      lowPower: this.lowPower,
      voice,
      blink,
      audio: { ...this.audio },
      impulses: { ...this.impulses },
      task: this.task,
    };
  }
}
