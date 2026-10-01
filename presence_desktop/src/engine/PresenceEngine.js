import { PresenceBehaviorEngine } from "./PresenceBehaviorEngine.js";
import { CognitiveFoldCanvasRenderer, CognitiveFoldRenderer } from "./CognitiveFoldRenderer.js";

const DEFAULT_WIDTH = 356;
const DEFAULT_HEIGHT = 250;
const MAX_DELTA = 0.05;

/**
 * Public facade for Sera's Cognitive Fold presence visualization.
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
    this.lastTime = typeof performance !== "undefined" ? performance.now() : Date.now();
    this.motionQuery = typeof window !== "undefined" && window.matchMedia
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;
    this.behavior = new PresenceBehaviorEngine({ reducedMotion: this.motionQuery?.matches });
    this.onMotionPreference = (event) => this.behavior?.setReducedMotion(event.matches);
    this.motionQuery?.addEventListener?.("change", this.onMotionPreference);

    const { width, height } = this.measure();
    try {
      this.renderer = new CognitiveFoldRenderer(canvas, width, height, this.pixelRatio());
      this.rendererType = "webgl";
    } catch (error) {
      console.warn("[PresenceEngine] WebGL unavailable; using Canvas 2D.", error);
      this.renderer = new CognitiveFoldCanvasRenderer(canvas, width, height, this.pixelRatio());
      this.rendererType = "canvas2d";
    }
    this.setupResize();
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
      this.renderer.resize(width, height, this.pixelRatio());
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
    this.behavior.setState(state, this.taskType, this.taskProgress);
  }

  setTaskVisualization(taskType, objective = "") {
    if (this.disposed) return;
    this.behavior.setTaskVisualization(taskType, objective);
  }

  triggerEvent(eventType, payload = {}) {
    if (this.disposed) return;
    this.behavior.triggerEvent(eventType, payload);
  }

  setAudioData(bands) {
    if (this.disposed) return;
    this.behavior.setAudioData(bands);
  }

  // Kept for compatibility with older audio callers.
  setAudioAmplitude(amplitude) {
    const value = Math.max(0, Math.min(1, Number(amplitude) || 0));
    this.setAudioData({ rawAmp: value, bass: value * 0.9, mid: value, treble: value * 0.7 });
  }

  update() {
    if (this.disposed) return;
    const now = typeof performance !== "undefined" ? performance.now() : Date.now();
    const delta = Math.min(MAX_DELTA, Math.max(0, (now - this.lastTime) / 1000));
    this.lastTime = now;
    this.renderer.render(this.behavior.update(delta));
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    this.resizeObserver?.disconnect();
    if (!this.resizeObserver && typeof window !== "undefined") {
      window.removeEventListener("resize", this.onResize);
    }
    this.motionQuery?.removeEventListener?.("change", this.onMotionPreference);
    this.renderer?.dispose();
    this.renderer = null;
    this.behavior = null;
  }
}
