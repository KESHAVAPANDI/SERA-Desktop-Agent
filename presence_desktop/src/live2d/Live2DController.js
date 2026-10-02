/**
 * SERA 2.0 Live2D Character Controller
 *
 * Core controller that bridges authoritative SERA runtime states with the
 * Live2D Cubism model instance.
 *
 * Architectural Principles:
 * - One persistent Live2D model instance throughout application lifetime.
 * - Changing state NEVER reloads the model or creates visible flashes.
 * - Continuous life layer (breathing, blinking, saccades) runs uninterrupted.
 * - All parameter transitions are smoothly damped (exponential decay).
 * - Speaking animation follows actual SERA TTS audio levels with clean fallback.
 * - Colors transition smoothly via Live2DColorSystem.
 */

import { getStateProfile, LIVE2D_STATE_PROFILES } from "./Live2DStateProfiles.js";
import { Live2DLifeLayer } from "./Live2DLifeLayer.js";
import { Live2DColorSystem } from "./Live2DColorSystem.js";
import { LIVE2D_CONFIG } from "./Live2DConfig.js";

export class Live2DController {
  constructor(options = {}) {
    this.config = { ...LIVE2D_CONFIG, ...options };
    this.model = null;
    this.isLoaded = false;
    this.loadError = null;

    // State management
    this.currentState = "IDLE";
    this.currentProfile = getStateProfile("IDLE");
    this.targetProfile = this.currentProfile;
    this.taskType = "GENERAL";
    this.taskProgress = 0;

    // Subsystems
    this.lifeLayer = new Live2DLifeLayer();
    this.colorSystem = new Live2DColorSystem(this.currentProfile.color, this.currentProfile.auraIntensity);

    // Audio / Speech state
    this.audioLevel = 0.0;
    this.lastAudioTime = 0;
    this.speechTime = 0;

    // Smoothed parameter state (avoids snapping)
    this.params = {
      angleX: 0,
      angleY: 0,
      angleZ: 0,
      bodyAngleX: 0,
      bodyAngleY: 0,
      bodyAngleZ: 0,
      gazeX: 0,
      gazeY: 0,
      eyeOpen: 1.0,
      mouthOpen: 0,
      eyeSmile: 0,
      cheek: 0,
    };

    // Tracking for model reload prevention verification
    this.loadCount = 0;
    this.stateChangeCount = 0;
    this.disposed = false;
  }

  /**
   * Attach an initialized Live2DModel instance.
   * Ensures the character instance is kept alive and never reloaded across state changes.
   */
  attachModel(model) {
    if (!model) {
      throw new TypeError("Cannot attach null model to Live2DController");
    }
    this.model = model;
    this.isLoaded = true;
    this.loadError = null;
    this.loadCount++;

    // Initial pose and expression
    this.applyCurrentExpression();
    this.applyCurrentMotion();

    console.log(`[Live2DController] Model attached successfully (total load count: ${this.loadCount}).`);
  }

  /**
   * Set model load error for diagnostic transparency.
   */
  setLoadError(error) {
    this.isLoaded = false;
    this.loadError = error;
    console.error("[Live2DController] Model load failure:", error);
  }

  /**
   * Authoritative SERA State change handler.
   * Crucial: Modifies state targets and profiles ONLY; never reloads model.
   */
  setState(rawState, taskType = "GENERAL", progress = 0) {
    if (this.disposed) return;

    this.stateChangeCount++;
    this.taskType = taskType || "GENERAL";
    this.taskProgress = Math.max(0, Math.min(1, Number(progress) || 0));

    const previousState = this.currentState;
    const profile = getStateProfile(rawState);
    this.currentState = rawState;
    this.targetProfile = profile;

    // Smooth color target transition
    this.colorSystem.setTargetColor(profile.color, profile.auraIntensity);

    // Expression & Motion switching (if model is attached)
    if (this.model && previousState !== rawState) {
      this.applyCurrentExpression();
      this.applyCurrentMotion();
    }
  }

  applyCurrentExpression() {
    if (!this.model || typeof this.model.expression !== "function") return;
    try {
      const expName = this.targetProfile.expression;
      if (expName) {
        this.model.expression(expName);
      }
    } catch (e) {
      console.warn("[Live2DController] Expression set warning:", e);
    }
  }

  applyCurrentMotion() {
    if (!this.model || typeof this.model.motion !== "function") return;
    try {
      const group = this.targetProfile.motionGroup || "Idle";
      const index = this.targetProfile.motionIndex || 0;
      // Normal priority (2) so it does not block emergency expressions
      this.model.motion(group, index, 2);
    } catch (e) {
      console.warn("[Live2DController] Motion set warning:", e);
    }
  }

  /**
   * Ingest real-time audio analysis from SERA TTS pipeline.
   */
  setAudioData(bands = {}) {
    if (this.disposed) return;
    // Derive speech energy from mid-range voice frequencies and raw amplitude
    const raw = Number(bands.rawAmp) || 0;
    const mid = Number(bands.mid) || 0;
    this.audioLevel = Math.max(0, Math.min(1, raw * 0.4 + mid * 0.6));
    this.lastAudioTime = Date.now();
  }

  /**
   * Main per-frame update loop.
   * Damps all parameters smoothly toward state targets + life layer micro-motions.
   */
  update(delta = 0.016) {
    if (this.disposed || !this.model || !this.isLoaded) return;

    const dt = Math.min(0.1, Math.max(0.001, delta));

    // 1. Advance Life Layer (Breathing, natural blinking, eye saccades, organic drift)
    const life = this.lifeLayer.update(dt, this.targetProfile);

    // 2. Advance Color System
    const colorInfo = this.colorSystem.update(dt);
    if (typeof this.model.tint === "number") {
      this.model.tint = this.colorSystem.getModelTint();
    }

    // 3. Smooth Damping of Head & Body Posture
    const dampSpeed = 1.0 / Math.max(0.1, this.targetProfile.transitionDuration || 0.4);
    const dampFactor = 1.0 - Math.exp(-dt * dampSpeed * 6.0);

    // Head Angles: State Target + Life Layer Organic Drift
    const targetAngleX = this.targetProfile.angleX + life.driftAngleX;
    const targetAngleY = this.targetProfile.angleY + life.driftAngleY;
    const targetAngleZ = this.targetProfile.angleZ + life.driftAngleZ;
    this.params.angleX += (targetAngleX - this.params.angleX) * dampFactor;
    this.params.angleY += (targetAngleY - this.params.angleY) * dampFactor;
    this.params.angleZ += (targetAngleZ - this.params.angleZ) * dampFactor;

    // Body Angles: State Target + Torso Lean
    const targetBodyX = this.targetProfile.bodyAngleX;
    const targetBodyY = this.targetProfile.bodyAngleY;
    const targetBodyZ = this.targetProfile.bodyAngleZ;
    this.params.bodyAngleX += (targetBodyX - this.params.bodyAngleX) * dampFactor;
    this.params.bodyAngleY += (targetBodyY - this.params.bodyAngleY) * dampFactor;
    this.params.bodyAngleZ += (targetBodyZ - this.params.bodyAngleZ) * dampFactor;

    // Eye Gaze: State Target + Micro-Saccades
    const targetGazeX = this.targetProfile.gazeX + life.saccadeX;
    const targetGazeY = this.targetProfile.gazeY + life.saccadeY;
    const gazeFactor = 1.0 - Math.exp(-dt * (this.targetProfile.gazeSpeed || 4.0));
    this.params.gazeX += (targetGazeX - this.params.gazeX) * gazeFactor;
    this.params.gazeY += (targetGazeY - this.params.gazeY) * gazeFactor;

    // Eye Openness: Multiplied by Natural Blinking State Machine
    const targetEyeOpen = (this.targetProfile.eyeOpenMultiplier ?? 1.0) * life.blinkRatio;
    this.params.eyeOpen += (targetEyeOpen - this.params.eyeOpen) * Math.min(1.0, dt * 25.0);

    // Eye Smile
    const targetEyeSmile = this.targetProfile.eyeSmile || 0.0;
    this.params.eyeSmile += (targetEyeSmile - this.params.eyeSmile) * dampFactor;

    // 4. Speech / Mouth Animation
    let targetMouthOpen = 0.0;
    if (this.targetProfile.isSpeaking) {
      this.speechTime += dt;
      const recentAudio = (Date.now() - this.lastAudioTime) < 300;
      if (recentAudio && this.audioLevel > 0.02) {
        // Real-time TTS envelope modulation
        targetMouthOpen = Math.min(1.0, this.audioLevel * 1.6);
      } else {
        // Natural speech cadence fallback when audio envelope is silent
        const wave = Math.sin(this.speechTime * this.config.speechFallbackFrequency);
        const secondary = Math.sin(this.speechTime * (this.config.speechFallbackFrequency * 0.5));
        targetMouthOpen = Math.max(0.0, (wave * 0.4 + secondary * 0.25 + 0.35) * this.targetProfile.mouthOpenGain);
      }
    } else {
      this.speechTime = 0;
      targetMouthOpen = 0.0;
    }
    this.params.mouthOpen += (targetMouthOpen - this.params.mouthOpen) * Math.min(1.0, dt * 18.0);

    // 5. Apply Directly to Live2D Cubism Core Parameters
    this.applyParametersToModel(life.breathValue, colorInfo.aura);
  }

  applyParametersToModel(breathValue, auraIntensity) {
    const internal = this.model.internalModel;
    if (!internal || !internal.coreModel) return;
    const core = internal.coreModel;

    // Head rotation
    this.safeSetParam(core, "ParamAngleX", this.params.angleX);
    this.safeSetParam(core, "ParamAngleY", this.params.angleY);
    this.safeSetParam(core, "ParamAngleZ", this.params.angleZ);

    // Torso rotation
    this.safeSetParam(core, "ParamBodyAngleX", this.params.bodyAngleX);
    this.safeSetParam(core, "ParamBodyAngleY", this.params.bodyAngleY);
    this.safeSetParam(core, "ParamBodyAngleZ", this.params.bodyAngleZ);

    // Eye gaze
    this.safeSetParam(core, "ParamEyeBallX", this.params.gazeX);
    this.safeSetParam(core, "ParamEyeBallY", this.params.gazeY);

    // Eye blinking and smile
    this.safeSetParam(core, "ParamEyeLOpen", this.params.eyeOpen);
    this.safeSetParam(core, "ParamEyeROpen", this.params.eyeOpen);
    this.safeSetParam(core, "ParamEyeLSmile", this.params.eyeSmile);
    this.safeSetParam(core, "ParamEyeRSmile", this.params.eyeSmile);

    // Continuous breathing
    this.safeSetParam(core, "ParamBreath", breathValue);

    // Lip sync / mouth
    this.safeSetParam(core, this.config.lipSyncParam || "ParamA", this.params.mouthOpen);

    // Eye effect and accessory aura response
    this.safeSetParam(core, "ParamEyeEffect", auraIntensity > 0.6 ? 1.0 : 0.0);
  }

  safeSetParam(core, paramId, value) {
    if (typeof core.setParameterValueById === "function") {
      core.setParameterValueById(paramId, value);
    }
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;

    if (this.model && typeof this.model.destroy === "function") {
      try {
        this.model.destroy({ children: true, texture: true, baseTexture: true });
      } catch (e) {
        console.warn("[Live2DController] Model destroy warning:", e);
      }
    }

    this.model = null;
    this.isLoaded = false;
    this.lifeLayer = null;
    this.colorSystem = null;
  }
}
