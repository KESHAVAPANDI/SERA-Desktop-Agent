import { Live2DRenderer } from "../live2d/Live2DRenderer.js";

const DEFAULT_WIDTH = 356;
const DEFAULT_HEIGHT = 250;

/**
 * Public facade for SERA's persistent Live2D character presence.
 * Runtime messages are the sole authority for operational state.
 */
export class PresenceEngine {
  constructor(canvas) {
    if (!canvas) throw new TypeError("PresenceEngine requires a canvas");
    this.canvas = canvas;
    this.state = "IDLE";
    this.taskType = "GENERAL";
    this.taskProgress = 0;
    this.disposed = false;

    const { width, height } = this.measure();
    this.renderer = new Live2DRenderer(canvas, width, height, this.pixelRatio());
    this.setupResize();
  }

  get controller() {
    return this.renderer?.controller;
  }

  measure() {
    return {
      width: this.canvas.clientWidth || DEFAULT_WIDTH,
      height: this.canvas.clientHeight || DEFAULT_HEIGHT,
    };
  }

  pixelRatio() {
    return Math.min(1.5, typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1);
  }

  setupResize() {
    this.onResize = () => {
      if (this.disposed) return;
      const { width, height } = this.measure();
      this.renderer?.resize(width, height, this.pixelRatio());
    };
    if (typeof ResizeObserver !== "undefined") {
      this.resizeObserver = new ResizeObserver(this.onResize);
      this.resizeObserver.observe(this.canvas);
    } else if (typeof window !== "undefined") {
      window.addEventListener("resize", this.onResize, { passive: true });
    }
  }

  setState(state, taskType = "GENERAL", progress = 0) {
    if (this.disposed) return;
    this.state = state;
    this.taskType = taskType || "GENERAL";
    this.taskProgress = Math.max(0, Math.min(1, Number(progress) || 0));
    this.renderer?.setState(state, this.taskType, this.taskProgress);
  }

  setTaskVisualization(taskType, objective = "") {
    if (this.disposed) return;
    this.renderer?.setTaskVisualization(taskType, objective);
  }

  triggerEvent(eventType, payload = {}) {
    if (this.disposed) return;
    this.renderer?.triggerEvent(eventType, payload);
  }

  setAudioData(bands) {
    if (this.disposed) return;
    this.renderer?.setAudioData(bands);
  }

  setAudioAmplitude(amplitude) {
    const value = Math.max(0, Math.min(1, Number(amplitude) || 0));
    this.setAudioData({ rawAmp: value, bass: value * 0.9, mid: value, treble: value * 0.7 });
  }

  update() {
    if (this.disposed) return;
    this.renderer?.update();
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    this.resizeObserver?.disconnect();
    if (!this.resizeObserver && typeof window !== "undefined") {
      window.removeEventListener("resize", this.onResize);
    }
    this.renderer?.dispose();
    this.renderer = null;
  }
}
