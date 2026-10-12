/**
 * SERA 2.0 Live2D Renderer Engine
 *
 * WebGL-based Live2D renderer for Electron transparent overlay.
 * Conforms to the PresenceEngine interface and drives the persistent
 * Live2D character model.
 *
 * Features:
 * - 100% transparent WebGL canvas integration
 * - Persistent single-model lifecycle (never reloads on state changes)
 * - Clear diagnostic error fallback if model fails to load
 * - Dynamic window resizing support
 * - Clean WebGL context teardown without leaks
 */

import { Live2DController } from "./Live2DController.js";
import { LIVE2D_CONFIG } from "./Live2DConfig.js";

export class Live2DRenderer {
  constructor(canvas, width = 356, height = 250, dpr = 1.0) {
    if (!canvas) throw new TypeError("Live2DRenderer requires a canvas element");
    this.canvas = canvas;
    this.width = width;
    this.height = height;
    this.dpr = Math.min(1.5, dpr || 1.0);
    this.disposed = false;
    this.isLoading = true;
    this.initError = null;

    this.controller = new Live2DController(LIVE2D_CONFIG);
    this.pixiApp = null;
    this.auraGraphic = null;
    this.modelContainer = null;

    this.initPixiAndModel();
  }

  async initPixiAndModel() {
    try {
      // 1. Verify PIXI and Live2D runtime availability
      const PIXI = window.PIXI;
      if (!PIXI) {
        throw new Error("PIXI.js library not found on window. Ensure pixi.min.js is loaded.");
      }
      const Live2DModel = PIXI.live2d?.Live2DModel;
      if (!Live2DModel) {
        throw new Error("Live2DModel runtime not found. Ensure cubism4.min.js and Live2DCubismCore are loaded.");
      }

      // 2. Initialize PixiJS Application
      this.pixiApp = new PIXI.Application({
        view: this.canvas,
        width: this.width,
        height: this.height,
        resolution: this.dpr,
        autoDensity: true,
        backgroundAlpha: 0,
        antialias: true,
        preserveDrawingBuffer: true, // For window snapshot captures
        powerPreference: LIVE2D_CONFIG.webgl.powerPreference || "default",
      });

      // Disable default ticker so App.js RenderScheduler controls the frame rate
      this.pixiApp.ticker.autoStart = false;
      this.pixiApp.ticker.stop();

      // 3. Create Scene Graph: Aura Layer -> Model Container
      this.auraGraphic = new PIXI.Graphics();
      this.pixiApp.stage.addChild(this.auraGraphic);

      this.modelContainer = new PIXI.Container();
      this.pixiApp.stage.addChild(this.modelContainer);

      // 4. Asynchronously Load Configured Live2D Model
      console.log(`[Live2DRenderer] Loading Live2D model from: ${LIVE2D_CONFIG.modelPath}`);
      const model = await Live2DModel.from(LIVE2D_CONFIG.modelPath, {
        autoInteract: LIVE2D_CONFIG.autoInteract,
      });

      if (this.disposed) {
        model.destroy({ children: true, texture: true, baseTexture: true });
        return;
      }

      // 5. Position & Frame Character
      this.setupModelTransform(model);
      this.modelContainer.addChild(model);
      this.controller.attachModel(model);
      this.isLoading = false;

      console.log("[Live2DRenderer] Live2D persistent character online.");
    } catch (error) {
      this.isLoading = false;
      this.initError = error;
      this.controller.setLoadError(error);
      console.error("[Live2DRenderer] Initialization failure:", error);
      this.renderFallbackError(error);
    }
  }

  setupModelTransform(model) {
    if (!model) return;
    const scale = LIVE2D_CONFIG.modelScale || 0.22;
    model.scale.set(scale);
    model.anchor.set(0.5, 0.5);

    const cx = this.width * 0.5;
    const cy = LIVE2D_CONFIG.modelOffsetY || 355;
    model.position.set(cx, cy);
  }

  resize(width, height, dpr) {
    if (this.disposed) return;
    this.width = width;
    this.height = height;
    this.dpr = Math.min(1.5, dpr || 1.0);

    if (this.pixiApp?.renderer) {
      this.pixiApp.renderer.resolution = this.dpr;
      this.pixiApp.renderer.resize(width, height);
    }

    if (this.controller.model) {
      this.setupModelTransform(this.controller.model);
    }
  }

  setState(state, taskType = "GENERAL", progress = 0) {
    if (this.disposed) return;
    this.controller.setState(state, taskType, progress);
  }

  setTaskVisualization(taskType, objective = "") {
    // Preserved for status bar synchronicity
  }

  triggerEvent(eventType, payload = {}) {
    if (this.disposed) return;
    this.controller.triggerEvent(eventType, payload);
    if (eventType === "ACTIVATION_STARTED") {
      this.setState("LISTENING");
    }
  }

  setAudioData(bands) {
    if (this.disposed) return;
    this.controller.setAudioData(bands);
  }

  update() {
    if (this.disposed) return;

    // Advance controller animation frame
    this.controller.update(0.016);

    // Update dynamic background aura
    this.renderAura();

    // Render PixiJS scene graph to WebGL canvas
    if (this.pixiApp?.renderer) {
      try {
        this.pixiApp.renderer.render(this.pixiApp.stage);
      } catch (e) {
        console.warn("[Live2DRenderer] WebGL render warning:", e);
      }
    }
  }

  renderAura() {
    if (!this.auraGraphic || this.disposed) return;
    this.auraGraphic.clear();

    const auraColor = this.controller.colorSystem.getHexColor();
    const auraAlpha = this.controller.colorSystem.currentAura * 0.25;

    if (auraAlpha > 0.01) {
      const cx = this.width * 0.5;
      const cy = this.height * 0.48;
      const radius = Math.min(this.width, this.height) * 0.42;

      // Soft radial aura glow
      this.auraGraphic.beginFill(auraColor, auraAlpha);
      this.auraGraphic.drawCircle(cx, cy, radius);
      this.auraGraphic.endFill();

      this.auraGraphic.beginFill(auraColor, auraAlpha * 0.5);
      this.auraGraphic.drawCircle(cx, cy, radius * 1.35);
      this.auraGraphic.endFill();
    }
  }

  renderFallbackError(error) {
    if (!this.canvas) return;
    const ctx = this.canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.fillStyle = "rgba(239, 68, 68, 0.15)";
    ctx.fillRect(10, 10, this.width - 20, this.height - 20);

    ctx.strokeStyle = "rgba(239, 68, 68, 0.6)";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(10, 10, this.width - 20, this.height - 20);

    ctx.fillStyle = "#f87171";
    ctx.font = "bold 12px Segoe UI, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("LIVE2D RENDERER INITIALIZATION ERROR", this.width / 2, this.height / 2 - 14);

    ctx.fillStyle = "#e2e8f0";
    ctx.font = "10px Segoe UI, sans-serif";
    const msg = error?.message || String(error);
    ctx.fillText(msg.slice(0, 50), this.width / 2, this.height / 2 + 8);
    ctx.fillText("Check Live2D assets and WebGL configuration.", this.width / 2, this.height / 2 + 24);
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;

    this.controller.dispose();

    if (this.pixiApp) {
      try {
        this.pixiApp.destroy(true, { children: true, texture: true, baseTexture: true });
      } catch (e) {
        console.warn("[Live2DRenderer] Pixi destroy warning:", e);
      }
      this.pixiApp = null;
    }

    this.auraGraphic = null;
    this.modelContainer = null;
    this.canvas = null;
  }
}
