/**
 * SERA 2.0 — PRIMARY PRESENCE BEHAVIOR ENGINE
 * 
 * Orchestrates adaptive, non-deterministic, biological & computational dynamics:
 * - Dynamic Energy Budget (0.0 Dormant -> 0.25 Calm -> 0.50 Active -> 0.85 Thinking -> 1.0 Extreme)
 * - Visual Attention Model (Layer dominance weights preventing visual overload)
 * - Organic Pacing ("No Constant Motion": pauses, accelerations, drift, asymmetrical pulses)
 * - Visual Memory (Spatial orientation & branch seeds inherited across transitions)
 * - Event-Driven Micro Behaviors (Model selection pulses, tool projections, fallback recovery)
 * - Continuous Multi-Stage State Transitions & Computational Regeneration
 * 
 * Author: Keshava Pandi A S <keshavapandi@gmail.com>
 */

export class PresenceBehaviorEngine {
  constructor() {
    // 1. Operational State & Pacing
    this.currentState = "IDLE";
    this.targetState = "IDLE";
    this.taskType = "GENERAL";
    this.taskProgress = 0.0;
    this.time = 0;

    // 2. Global Energy Budget (0.0 -> 1.0)
    this.energyBudget = 0.25;
    this.targetEnergyBudget = 0.25;
    this.energyLevels = {
      DORMANT: 0.05,
      IDLE: 0.25,
      LISTENING: 0.52,
      TRANSCRIBING: 0.68,
      THINKING: 0.88,
      EXECUTING: 0.92,
      SPEAKING: 0.72,
      BROKEN: 0.98,
      CANCELLED: 0.20,
      COMPLETED: 1.0,
    };

    // 3. Visual Attention Model (Layer Dominance Weights)
    // Range 0.0 to 1.0 per visual layer
    this.attentionWeights = {
      core: 1.0,
      innerLattice: 0.8,
      rings: 0.7,
      glyphs: 0.6,
      topology: 0.7,
      filaments: 0.5,
      particles: 0.65,
      taskBridge: 0.0,
    };

    // Target attention weights for smooth interpolation
    this.targetAttention = { ...this.attentionWeights };

    // 4. Organic Pacing & Non-Deterministic Oscillators
    // Rings independent gear ratios, pause timers, and phase shifts
    this.ringStates = [
      { speedMult: 1.0, targetMult: 1.0, pauseTimer: 0, phase: 0.0, driftOffset: 0.0 },
      { speedMult: -1.0, targetMult: -1.0, pauseTimer: 0, phase: 0.4, driftOffset: 0.0 },
      { speedMult: 1.2, targetMult: 1.2, pauseTimer: 0, phase: 0.8, driftOffset: 0.0 },
      { speedMult: -0.8, targetMult: -0.8, pauseTimer: 0, phase: 1.2, driftOffset: 0.0 },
      { speedMult: 0.6, targetMult: 0.6, pauseTimer: 0, phase: 1.6, driftOffset: 0.0 },
    ];

    // 5. Visual Memory (Persistence across state transitions)
    this.visualMemory = {
      primaryBranchAngle: 0.5,
      spatialSeed: Math.random() * 1000,
      lastToolTarget: { x: 4.2, y: 0.8 },
      dominantFrequency: 0.0,
      activeBranchCount: 5,
      reconstructionStage: 0,
      reconstructionTimer: 0,
    };

    // 6. Micro-Event Impulse Buffer
    this.impulse = {
      coreShock: 0.0,       // Radial impulse (0.0 to 1.0)
      energyFlash: 0.0,      // Emissive burst (0.0 to 1.0)
      anomalyGlitch: 0.0,    // Red/magenta glitch (0.0 to 1.0)
      toolProjection: 0.0,   // Outward beam projection (0.0 to 1.0)
      returnPulse: 0.0,      // Inward convergence pulse (0.0 to 1.0)
    };

    // 7. Multi-Band Audio Decomposition
    this.audioBands = {
      bass: 0.0,
      mid: 0.0,
      treble: 0.0,
      rawAmp: 0.0,
    };

    // 8. Controlled Procedural Noise Generators
    this.nextIdleEventTime = 2.5;
    this.nextBurstTime = 4.0;
  }

  // ─── State & Task Transitions ─────────────────────────────────────────────
  setState(state, taskType = "GENERAL", taskProgress = 0.0) {
    this.targetState = state;
    this.taskType = taskType;
    this.taskProgress = taskProgress;

    // Adjust Target Energy Budget
    if (this.energyLevels[state] !== undefined) {
      this.targetEnergyBudget = this.energyLevels[state];
    }

    // Recompute Attention Dominance
    this.recomputeAttention(state, taskType);

    // Update Visual Memory when transitioning into thinking or executing
    if (state === "THINKING") {
      // Seed a new non-deterministic computational orientation
      this.visualMemory.primaryBranchAngle = (Math.random() * 0.8 - 0.4) + (taskType === "BROWSER" ? 0.2 : 0.0);
      this.visualMemory.activeBranchCount = Math.floor(Math.random() * 4) + 4;
      this.impulse.energyFlash = 0.6;
    } else if (state === "EXECUTING") {
      // Inherit thinking branch orientation for directional execution conduit
      this.visualMemory.lastToolTarget = {
        x: 3.8 + Math.cos(this.visualMemory.primaryBranchAngle) * 0.8,
        y: 0.6 + Math.sin(this.visualMemory.primaryBranchAngle) * 0.6,
      };
      this.impulse.toolProjection = 1.0;
    } else if (state === "COMPLETED") {
      this.visualMemory.reconstructionStage = 1;
      this.visualMemory.reconstructionTimer = 0.0;
      this.impulse.coreShock = 1.0;
    } else if (state === "CANCELLED") {
      this.impulse.returnPulse = 1.0;
    } else if (state === "BROKEN") {
      this.impulse.anomalyGlitch = 1.0;
    }

    console.log(`[PresenceBehaviorEngine] Transition -> ${state} (Task: ${taskType}, Energy: ${this.targetEnergyBudget.toFixed(2)})`);
  }

  recomputeAttention(state, taskType) {
    switch (state) {
      case "IDLE":
        this.targetAttention = {
          core: 0.8,
          innerLattice: 0.6,
          rings: 0.65,
          glyphs: 0.5,
          topology: 0.55,
          filaments: 0.35,
          particles: 0.5,
          taskBridge: 0.0,
        };
        break;

      case "LISTENING":
        // Inward focus: core and inner lattice become dominant, outer filaments quiet
        this.targetAttention = {
          core: 1.0,
          innerLattice: 0.95,
          rings: 0.5,
          glyphs: 0.4,
          topology: 0.45,
          filaments: 0.2,
          particles: 0.8,
          taskBridge: 0.0,
        };
        break;

      case "TRANSCRIBING":
        // Rapid ingestion: glyphs and particles dominant
        this.targetAttention = {
          core: 0.9,
          innerLattice: 0.85,
          rings: 0.6,
          glyphs: 1.0,
          topology: 0.6,
          filaments: 0.25,
          particles: 0.9,
          taskBridge: 0.0,
        };
        break;

      case "THINKING":
        // Parallel computation: topology and rings dominant
        this.targetAttention = {
          core: 0.85,
          innerLattice: 0.9,
          rings: 0.95,
          glyphs: 0.8,
          topology: 1.0,
          filaments: 0.3,
          particles: 0.75,
          taskBridge: 0.4,
        };
        break;

      case "EXECUTING":
        // Action manifestation: task bridge dominant, topology subservient
        this.targetAttention = {
          core: 0.8,
          innerLattice: 0.7,
          rings: 0.6,
          glyphs: 0.5,
          topology: 0.4,
          filaments: 0.35,
          particles: 0.7,
          taskBridge: 1.0, // Focal dominance
        };
        break;

      case "SPEAKING":
        // Acoustic resonance: filaments and core dominant
        this.targetAttention = {
          core: 0.95,
          innerLattice: 0.75,
          rings: 0.5,
          glyphs: 0.35,
          topology: 0.25,
          filaments: 1.0, // Primary communication channel
          particles: 0.6,
          taskBridge: 0.1,
        };
        break;

      case "BROKEN":
        this.targetAttention = {
          core: 1.0,
          innerLattice: 0.4,
          rings: 0.3,
          glyphs: 0.2,
          topology: 0.9, // Visible destabilization
          filaments: 0.1,
          particles: 0.85,
          taskBridge: 0.0,
        };
        break;

      case "COMPLETED":
        this.targetAttention = {
          core: 1.0,
          innerLattice: 0.9,
          rings: 0.85,
          glyphs: 0.7,
          topology: 0.9,
          filaments: 0.5,
          particles: 0.95,
          taskBridge: 0.15,
        };
        break;

      default:
        break;
    }
  }

  // ─── Micro-Event Reactions ────────────────────────────────────────────────
  triggerEvent(eventType, payload = {}) {
    console.log(`[PresenceBehaviorEngine] Event Reaction: ${eventType}`, payload);

    switch (eventType) {
      case "MODEL_SELECTED":
        // Temporary crisp computational energy pulse
        this.impulse.energyFlash = 0.85;
        this.impulse.coreShock = 0.5;
        break;

      case "TOOL_STARTED":
        // Kinetic outward projection towards target
        this.impulse.toolProjection = 1.0;
        this.targetEnergyBudget = Math.min(1.0, this.targetEnergyBudget + 0.15);
        break;

      case "TOOL_COMPLETED":
        // Synthesizing return pulse into core singularity
        this.impulse.returnPulse = 1.0;
        this.impulse.energyFlash = 0.6;
        break;

      case "FALLBACK":
        // Primary structure destabilizes momentarily with magenta anomaly, then recovers
        this.impulse.anomalyGlitch = 0.75;
        this.visualMemory.primaryBranchAngle += Math.PI * 0.5; // Rotate to alternate spatial path
        break;

      case "PROGRESS_UPDATE":
        if (payload.progress !== undefined) {
          this.taskProgress = Math.max(0.0, Math.min(1.0, payload.progress));
        }
        break;

      case "TASK_CANCELLED":
        this.setState("CANCELLED");
        break;

      case "TASK_COMPLETED":
        this.setState("COMPLETED", this.taskType, 1.0);
        break;
    }
  }

  setAudioData(bands) {
    if (!bands) return;
    this.audioBands.rawAmp = bands.rawAmp || 0.0;
    this.audioBands.bass = bands.bass || 0.0;
    this.audioBands.mid = bands.mid || 0.0;
    this.audioBands.treble = bands.treble || 0.0;
  }

  // ─── Per-Frame Simulation Loop ────────────────────────────────────────────
  update(delta) {
    this.time += delta;

    // 1. Smooth Energy Budget Interpolation
    const energyLerpSpeed = this.targetState === "COMPLETED" ? 2.5 : 3.5;
    this.energyBudget += (this.targetEnergyBudget - this.energyBudget) * Math.min(1.0, delta * energyLerpSpeed);

    // 2. Smooth Attention Weight Interpolation
    const attSpeed = 4.0;
    for (const key of Object.keys(this.attentionWeights)) {
      this.attentionWeights[key] += (this.targetAttention[key] - this.attentionWeights[key]) * Math.min(1.0, delta * attSpeed);
    }

    // 3. Exponential Decay for Micro-Impulses
    const impulseDecay = Math.max(0.0, 1.0 - delta * 3.5);
    this.impulse.coreShock *= impulseDecay;
    this.impulse.energyFlash *= impulseDecay;
    this.impulse.anomalyGlitch *= Math.max(0.0, 1.0 - delta * 4.5);
    this.impulse.toolProjection *= Math.max(0.0, 1.0 - delta * 2.8);
    this.impulse.returnPulse *= Math.max(0.0, 1.0 - delta * 3.2);

    // 4. Organic Pacing & Non-Deterministic Gear Shifts ("No Constant Motion")
    this.updateRingPacing(delta);

    // 5. Procedural Asymmetry & Idle Bursts
    this.updateProceduralVariation(delta);

    // 6. Multi-Stage Completion Cellular Regeneration
    if (this.targetState === "COMPLETED") {
      this.updateReconstruction(delta);
    }

    // Produce Composite Behavior Output Vector
    return {
      time: this.time,
      state: this.targetState,
      taskType: this.taskType,
      taskProgress: this.taskProgress,
      energy: this.energyBudget,
      attention: this.attentionWeights,
      impulses: this.impulse,
      rings: this.ringStates,
      audio: this.audioBands,
      memory: this.visualMemory,
      // Organic Modulators:
      breathing: this.computeOrganicBreathing(),
      topologyWanderRate: this.computeTopologyWanderRate(),
      coreDistortion: this.computeCoreDistortion(),
    };
  }

  updateRingPacing(delta) {
    // Individual rings can pause, accelerate, or drift independently
    this.ringStates.forEach((ring, idx) => {
      if (ring.pauseTimer > 0) {
        ring.pauseTimer -= delta;
        // Damp speed to zero during pause
        ring.speedMult += (0.0 - ring.speedMult) * Math.min(1.0, delta * 3.0);
      } else {
        // Return to natural target speed
        ring.speedMult += (ring.targetMult - ring.speedMult) * Math.min(1.0, delta * 2.0);

        // Occasional spontaneous pause or gear shift during IDLE (every 8-15s per ring)
        if (this.targetState === "IDLE" && Math.random() < 0.003) {
          ring.pauseTimer = 1.0 + Math.random() * 2.0; // 1-3 second pause
          ring.targetMult = (Math.random() * 0.8 + 0.3) * (idx % 2 === 0 ? 1 : -1);
        }
      }

      // Add non-linear phase drift
      ring.phase += ring.speedMult * delta * (0.8 + this.energyBudget * 1.5);
    });
  }

  updateProceduralVariation(delta) {
    if (this.time >= this.nextIdleEventTime && this.targetState === "IDLE") {
      // Trigger a subtle, localized structural ripple or micro-burst
      this.impulse.coreShock = Math.random() * 0.25 + 0.1;
      this.nextIdleEventTime = this.time + (Math.random() * 4.0 + 3.5); // Every 3.5 to 7.5 seconds
    }
  }

  updateReconstruction(delta) {
    this.visualMemory.reconstructionTimer += delta;
    const t = this.visualMemory.reconstructionTimer;

    if (t < 0.8) {
      // Stage 1: Active structure fragments and particles pull inward
      this.visualMemory.reconstructionStage = 1;
      this.targetAttention.taskBridge = Math.max(0.0, 1.0 - t * 1.5);
      this.targetAttention.core = 1.0;
    } else if (t < 1.8) {
      // Stage 2: Topology snaps back and stabilizes
      this.visualMemory.reconstructionStage = 2;
      this.targetAttention.topology = 0.95;
      this.targetAttention.rings = 0.9;
    } else if (t < 2.6) {
      // Stage 3: Core intense white-hot flare
      this.visualMemory.reconstructionStage = 3;
      this.impulse.energyFlash = Math.max(0.0, 1.0 - (t - 1.8) * 1.5);
    } else {
      // Stage 4: Settling back to Calm Equilibrium
      this.visualMemory.reconstructionStage = 4;
      this.targetState = "IDLE";
      this.targetEnergyBudget = this.energyLevels.IDLE;
      this.recomputeAttention("IDLE", "GENERAL");
    }
  }

  computeOrganicBreathing() {
    // Non-linear cardiac oscillation: slow diastolic expansion, swift systolic intake
    const cycle = (this.time * 0.6) % (Math.PI * 2);
    const asymmetricWave = Math.sin(cycle) + Math.sin(cycle * 2.0) * 0.25;
    return 1.0 + asymmetricWave * (0.04 + this.energyBudget * 0.08);
  }

  computeTopologyWanderRate() {
    // Wandering velocity scales with energy budget and state
    if (this.targetState === "THINKING") return 0.045;
    if (this.targetState === "EXECUTING") return 0.030;
    if (this.targetState === "BROKEN") return 0.080;
    return 0.012 + (this.energyBudget - 0.25) * 0.02;
  }

  computeCoreDistortion() {
    const base = 0.28 + this.energyBudget * 0.45;
    const impulse = this.impulse.coreShock * 0.4 + this.impulse.anomalyGlitch * 0.6;
    const audioMod = this.audioBands.bass * 0.35;
    return base + impulse + audioMod;
  }
}
