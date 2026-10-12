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
import {
  createBehaviorContext,
  reactionDuration,
  reactionForEvent,
  reactionStates,
  resolveBehaviorTarget,
  resolveFrameTarget,
} from "./Live2DBehavior.js";

export class Live2DController {
  constructor(options = {}) {
    this.config = { ...LIVE2D_CONFIG, ...options };
    this.behaviorConfig = { ...LIVE2D_CONFIG.behavior, ...(options.behavior || {}) };
    this.now = typeof options.now === "function" ? options.now : Date.now;
    this.model = null;
    this.isLoaded = false;
    this.loadError = null;

    // State management
    this.currentState = "IDLE";
    this.currentProfile = getStateProfile("IDLE");
    this.targetProfile = this.currentProfile;
    this.behaviorContext = createBehaviorContext();
    this.resolvedTarget = this.currentProfile;
    this.frameTarget = {
      angleX: 0, angleY: 0, angleZ: 0,
      bodyAngleX: 0, bodyAngleY: 0, bodyAngleZ: 0,
      gazeX: 0, gazeY: 0, eyeOpen: 1, eyeSmile: 0,
      mouthOpen: 0, breathValue: 0, transitionDuration: 0.4, gazeSpeed: 4,
    };
    this.modelCapabilities = null;
    this.behaviorRevision = 0;
    this.lastEventSequence = 0;
    this.modelUpdateHandler = null;
    this.hookedInternalModel = null;
    this.lastBreathValue = 0;
    this.lastAuraIntensity = 0;
    this.taskType = "GENERAL";
    this.taskProgress = 0;

    // Subsystems
    this.lifeLayer = new Live2DLifeLayer({
      random: this.config.random || Math.random,
      config: this.behaviorConfig.life,
    });
    this.colorSystem = new Live2DColorSystem(this.currentProfile.color, this.currentProfile.auraIntensity);

    // Audio / Speech state
    this.audioLevel = 0.0;
    this.hasAudioTelemetry = false;
    this.lastAudioTime = 0;
    this.speechTime = 0;
    this.speechEnabled = false;

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
    this.modelCapabilities = this.inspectModelCapabilities(model);
    this.rebuildBehaviorTarget();
    this.attachModelUpdateHook();

    // Initial pose and expression
    this.applyCurrentExpression(this.behaviorRevision);
    this.applyCurrentMotion(this.behaviorRevision);

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
    this.currentProfile = profile;
    this.behaviorRevision++;
    this.behaviorContext.state = String(rawState || "IDLE").trim().toUpperCase() || "IDLE";
    this.behaviorContext.taskType = String(taskType || "GENERAL").trim().toUpperCase() || "GENERAL";
    this.behaviorContext.taskProgress = this.taskProgress;
    this.behaviorContext.revision = this.behaviorRevision;
    this.targetProfile = profile;
    this.speechEnabled = Boolean(profile.isSpeaking);
    this.behaviorContext.speechEnabled = this.speechEnabled;
    if (this.behaviorContext.reaction?.states
      && !this.behaviorContext.reaction.states.includes(this.behaviorContext.state)) {
      this.behaviorContext.reaction = null;
    } else if (this.behaviorContext.reaction) {
      // Reapplying the same authoritative state must not invalidate a reaction
      // accepted immediately before projectModel() calls setState().
      this.behaviorContext.reaction.revision = this.behaviorRevision;
    }
    this.rebuildBehaviorTarget();

    // Smooth color target transition
    this.colorSystem.setTargetColor(profile.color, profile.auraIntensity);

    // Expression & Motion switching (if model is attached)
    if (this.model && previousState !== rawState) {
      this.applyCurrentExpression(this.behaviorRevision);
      this.applyCurrentMotion(this.behaviorRevision);
    }
  }

  /** Forward runtime event facts into the transient reaction layer. */
  triggerEvent(eventType, payload = {}) {
    if (this.disposed) return;
    const event = String(eventType || "").trim().toUpperCase();
    if (!event) return;
    const incomingTaskId = typeof payload?.task_id === "string" ? payload.task_id : null;
    const activeTaskId = this.behaviorContext.taskId;
    if (incomingTaskId && activeTaskId && incomingTaskId !== activeTaskId) return;
    if (event === "TASK_STARTED" && incomingTaskId) this.behaviorContext.taskId = incomingTaskId;

    this.lastEventSequence++;
    const reaction = reactionForEvent(event);
    this.behaviorRevision++;
    this.behaviorContext.revision = this.behaviorRevision;
    this.behaviorContext.reaction = reaction
      ? {
        event,
        revision: this.behaviorRevision,
        remaining: reactionDuration(event, this.behaviorConfig.reactionDurations),
        states: reactionStates(event),
      }
      : null;

    if (event === "TTS_COMPLETED" || event === "TTS_INTERRUPTED" || event === "AUDIO_PLAYBACK_FINISHED") {
      this.speechEnabled = false;
      this.behaviorContext.speechEnabled = false;
      this.audioLevel = 0;
      this.hasAudioTelemetry = false;
      this.lastAudioTime = 0;
    }
    this.rebuildBehaviorTarget();
    if (this.model && reaction) {
      this.applyCurrentExpression(this.behaviorRevision);
      this.applyCurrentMotion(this.behaviorRevision);
    }
  }

  rebuildBehaviorTarget() {
    this.resolvedTarget = resolveBehaviorTarget({
      profile: this.targetProfile,
      context: this.behaviorContext,
      capabilities: this.modelCapabilities,
      tuning: this.behaviorConfig,
    });
  }

  inspectModelCapabilities(model) {
    const definitions = model?.internalModel?.motionManager?.definitions;
    if (!definitions || typeof definitions !== "object") return null;
    const motionGroups = {};
    for (const [group, entries] of Object.entries(definitions)) {
      if (Array.isArray(entries)) motionGroups[group] = entries.length;
    }
    return { motionGroups };
  }

  attachModelUpdateHook() {
    const internal = this.model?.internalModel;
    if (!internal || typeof internal.on !== "function") return;
    this.detachModelUpdateHook();
    this.modelUpdateHandler = () => {
      if (this.disposed || !this.model) return;
      // Cubism applies motion, expression, focus, physics and pose before
      // this hook. Reassert the single resolved controller target at the
      // boundary so those subsystems cannot accumulate or own these fields.
      this.applyParametersToModel(this.lastBreathValue, this.lastAuraIntensity);
    };
    this.hookedInternalModel = internal;
    internal.on("beforeModelUpdate", this.modelUpdateHandler);
  }

  detachModelUpdateHook() {
    const internal = this.hookedInternalModel || this.model?.internalModel;
    if (internal && this.modelUpdateHandler && typeof internal.off === "function") {
      internal.off("beforeModelUpdate", this.modelUpdateHandler);
    }
    this.modelUpdateHandler = null;
    this.hookedInternalModel = null;
  }

  applyCurrentExpression(revision = this.behaviorRevision) {
    if (!this.model || typeof this.model.expression !== "function") return;
    try {
      const expName = this.resolvedTarget.expression;
      if (expName) {
        const result = this.model.expression(expName);
        if (result && typeof result.then === "function") {
          result.catch(() => {}).then(() => {
            // The runtime owns the eventual model write; this guard ensures
            // controller continuations never restore an obsolete target.
            if (this.disposed || revision !== this.behaviorRevision) return;
          });
        }
      }
    } catch (e) {
      console.warn("[Live2DController] Expression set warning:", e);
    }
  }

  applyCurrentMotion(revision = this.behaviorRevision) {
    if (!this.model || typeof this.model.motion !== "function") return;
    try {
      const group = this.resolvedTarget.motionGroup || "Idle";
      const index = this.resolvedTarget.motionIndex || 0;
      // Normal priority so it does not block model/runtime emergency motion.
      const result = this.model.motion(group, index, this.behaviorConfig.motionPriority);
      if (result && typeof result.then === "function") {
        result.catch(() => {}).then(() => {
          if (this.disposed || revision !== this.behaviorRevision) return;
        });
      }
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
    const incoming = Math.max(0, Math.min(1, raw * 0.4 + mid * 0.6));
    // TTS_AUDIO_LEVELS is an authoritative playback envelope. Smooth the
    // envelope here, but never synthesize mouth motion when it is silent or
    // absent. This keeps queued/generated text from looking like speech.
    const smoothing = incoming > this.audioLevel ? 0.62 : 0.2;
    this.audioLevel += (incoming - this.audioLevel) * smoothing;
    // Zero is a playback fact, not a heartbeat. A silent sampled frame must
    // close speech instead of keeping telemetry fresh indefinitely.
    if (incoming <= 0.0005) {
      this.audioLevel = 0;
      this.hasAudioTelemetry = false;
      this.lastAudioTime = 0;
    } else {
      this.hasAudioTelemetry = true;
      this.lastAudioTime = this.now();
    }
  }

  /**
   * Main per-frame update loop.
   * Damps all parameters smoothly toward state targets + life layer micro-motions.
   */
  update(delta = 0.016) {
    if (this.disposed || !this.model || !this.isLoaded) return;

    const dt = Math.min(0.1, Math.max(0.001, delta));

    if (this.behaviorContext.reaction) {
      this.behaviorContext.reaction.remaining -= dt;
      if (this.behaviorContext.reaction.remaining <= 0) {
        this.behaviorRevision++;
        this.behaviorContext.revision = this.behaviorRevision;
        this.behaviorContext.reaction = null;
        this.rebuildBehaviorTarget();
        if (this.model) {
          this.applyCurrentExpression(this.behaviorRevision);
          this.applyCurrentMotion(this.behaviorRevision);
        }
      }
    }

    // 1. Advance Life Layer (Breathing, natural blinking, eye saccades, organic drift)
    const life = this.lifeLayer.update(dt, this.resolvedTarget);

    // Compose one target for this frame from immutable state facts and the
    // current life sample. Nothing is added back into the base target.
    let targetMouthOpen = 0.0;
    if (this.resolvedTarget.isSpeaking && this.speechEnabled) {
      this.speechTime += dt;
      const telemetryFresh = this.hasAudioTelemetry
        && (this.now() - this.lastAudioTime) < this.behaviorConfig.speechFreshnessMs;
      targetMouthOpen = telemetryFresh
        ? Math.min(1.0, this.audioLevel * 1.6 * (this.resolvedTarget.mouthOpenGain || 1))
        : 0.0;
    } else {
      this.speechTime = 0;
    }
    const horizontalMotion = this.behaviorConfig.horizontalMotion;
    resolveFrameTarget(this.resolvedTarget, life, horizontalMotion, targetMouthOpen, this.frameTarget);

    // 2. Advance Color System
    const colorInfo = this.colorSystem.update(dt);
    if (typeof this.model.tint === "number") {
      this.model.tint = this.colorSystem.getModelTint();
    }

    // 3. Smooth Damping of Head & Body Posture
    const dampSpeed = 1.0 / this.frameTarget.transitionDuration;
    const dampFactor = 1.0 - Math.exp(-dt * dampSpeed * 6.0);

    // Head Angles: State Target + Life Layer Organic Drift
    const targetAngleX = this.frameTarget.angleX;
    // ParamAngleY/ParamBodyAngleY and horizontal gaze are the dominant
    // left-right motion sources. Keep their expressive intent, but damp the
    // controller-generated amplitude to a calm ~35% of the previous range.
    const targetAngleY = this.frameTarget.angleY;
    const targetAngleZ = this.frameTarget.angleZ;
    this.params.angleX += (targetAngleX - this.params.angleX) * dampFactor;
    this.params.angleY += (targetAngleY - this.params.angleY) * dampFactor;
    this.params.angleZ += (targetAngleZ - this.params.angleZ) * dampFactor;

    // Body Angles: State Target + Torso Lean
    const targetBodyX = this.frameTarget.bodyAngleX;
    const targetBodyY = this.frameTarget.bodyAngleY;
    const targetBodyZ = this.frameTarget.bodyAngleZ;
    this.params.bodyAngleX += (targetBodyX - this.params.bodyAngleX) * dampFactor;
    this.params.bodyAngleY += (targetBodyY - this.params.bodyAngleY) * dampFactor;
    this.params.bodyAngleZ += (targetBodyZ - this.params.bodyAngleZ) * dampFactor;

    // Eye Gaze: State Target + Micro-Saccades
    const targetGazeX = this.frameTarget.gazeX;
    const targetGazeY = this.frameTarget.gazeY;
    const gazeFactor = 1.0 - Math.exp(-dt * this.frameTarget.gazeSpeed);
    this.params.gazeX += (targetGazeX - this.params.gazeX) * gazeFactor;
    this.params.gazeY += (targetGazeY - this.params.gazeY) * gazeFactor;

    // Eye Openness: Multiplied by Natural Blinking State Machine
    const targetEyeOpen = this.frameTarget.eyeOpen;
    this.params.eyeOpen += (targetEyeOpen - this.params.eyeOpen) * Math.min(1.0, dt * 25.0);

    // Eye Smile
    const targetEyeSmile = this.frameTarget.eyeSmile;
    this.params.eyeSmile += (targetEyeSmile - this.params.eyeSmile) * dampFactor;

    // 4. Speech / Mouth Animation. The target is actual TTS telemetry only.
    this.params.mouthOpen += (this.frameTarget.mouthOpen - this.params.mouthOpen) * Math.min(1.0, dt * 18.0);

    // 5. Apply Directly to Live2D Cubism Core Parameters
    this.lastBreathValue = life.breathValue;
    this.lastAuraIntensity = colorInfo.aura;
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

    this.detachModelUpdateHook();
    if (this.model && typeof this.model.destroy === "function") {
      try {
        this.model.destroy({ children: true, texture: true, baseTexture: true });
      } catch (e) {
        console.warn("[Live2DController] Model destroy warning:", e);
      }
    }

    this.model = null;
    this.isLoaded = false;
    this.lifeLayer?.dispose?.();
    this.lifeLayer = null;
    this.colorSystem = null;
    this.resolvedTarget = null;
    this.frameTarget = null;
  }
}
