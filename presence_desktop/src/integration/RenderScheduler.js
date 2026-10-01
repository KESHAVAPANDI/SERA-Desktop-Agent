export class RenderScheduler {
  constructor(render, options = {}) {
    this.render = render;
    this.idleFps = options.idleFps ?? 15;
    this.activeFps = options.activeFps ?? 30;
    this.isActive = options.isActive || (() => false);
    this.document = options.document || globalThis.document;
    this.raf = options.requestAnimationFrame || globalThis.requestAnimationFrame?.bind(globalThis);
    this.cancelRaf = options.cancelAnimationFrame || globalThis.cancelAnimationFrame?.bind(globalThis);
    this.running = false;
    this.frame = null;
    this.last = 0;
    this._tick = this._tick.bind(this);
    this._visibility = this._visibility.bind(this);
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.document?.addEventListener?.("visibilitychange", this._visibility);
    this._visibility();
  }

  _visibility() {
    if (!this.running) return;
    if (this.document?.hidden) {
      if (this.frame != null) this.cancelRaf?.(this.frame);
      this.frame = null;
      return;
    }
    this.last = 0;
    if (this.frame == null) this.frame = this.raf?.(this._tick);
  }

  _tick(now) {
    this.frame = null;
    if (!this.running || this.document?.hidden) return;
    const interval = 1000 / (this.isActive() ? this.activeFps : this.idleFps);
    if (!this.last || now - this.last >= interval) {
      this.last = now;
      this.render(now);
    }
    this.frame = this.raf?.(this._tick);
  }

  stop() {
    this.running = false;
    this.document?.removeEventListener?.("visibilitychange", this._visibility);
    if (this.frame != null) this.cancelRaf?.(this.frame);
    this.frame = null;
  }
}
