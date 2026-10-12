/**
 * SERA 2.0 Live2D Continuous Life Layer
 *
 * Persistent biological micro-motions running independently of task state:
 * - Natural breathing cycle (modulating chest expansion and vertical posture)
 * - Stochastic realistic blinking (including occasional double-blinks)
 * - Micro-saccades (subtle eye drifting and fixation shifts)
 * - Tiny continuous head and body drift
 *
 * This layer persists across all state changes, guaranteeing that the character
 * always feels alive, conscious, and continuous.
 */

export class Live2DLifeLayer {
  constructor(options = {}) {
    this.random = typeof options === "function" ? options : (options.random || Math.random);
    this.config = {
      blinkIntervalMin: 2.5,
      blinkIntervalMax: 4.5,
      saccadeIntervalMin: 1.8,
      saccadeIntervalMax: 4.2,
      doubleBlinkProbability: 0.18,
      variationIntervalMin: 6,
      variationIntervalMax: 10,
      variationMin: 0.88,
      variationMax: 1.12,
      ...(typeof options === "object" ? (options.config || {}) : {}),
    };
    this.disposed = false;
    this.time = 0;

    // Blinking state machine
    this.blinkPhase = "INTERVAL"; // INTERVAL -> CLOSING -> CLOSED -> OPENING
    this.blinkTimer = 0;
    this.nextBlinkInterval = this.randomBlinkInterval();
    this.blinkRatio = 1.0; // 1.0 = fully open, 0.0 = fully closed
    this.isDoubleBlink = false;

    // Micro-saccades (eye fixation micro-movements)
    this.saccadeTimer = 0;
    this.nextSaccadeInterval = this.randomSaccadeInterval();
    this.saccadeX = 0;
    this.saccadeY = 0;
    this.targetSaccadeX = 0;
    this.targetSaccadeY = 0;

    // Micro-drift state
    this.driftAngleX = 0;
    this.driftAngleY = 0;
    this.driftAngleZ = 0;

    // Bounded idle variation changes slowly rather than introducing noisy
    // per-frame randomness. It is deliberately kept within +/-12%.
    this.variationTimer = 0;
    this.nextVariationInterval = this.randomRange(this.config.variationIntervalMin, this.config.variationIntervalMax);
    this.variation = 1;
    this.targetVariation = 1;

    // Reused output avoids a short-lived object on every render frame.
    this.output = {
      breathValue: 0,
      torsoOffsetY: 0,
      blinkRatio: 1,
      saccadeX: 0,
      saccadeY: 0,
      driftAngleX: 0,
      driftAngleY: 0,
      driftAngleZ: 0,
    };
  }

  randomRange(min, max) {
    const sample = this.randomValue();
    const normalized = Number.isFinite(sample) ? Math.max(0, Math.min(1, sample)) : 0.5;
    return min + normalized * (max - min);
  }

  randomValue() {
    const sample = Number(this.random());
    return Number.isFinite(sample) ? Math.max(0, Math.min(1, sample)) : 0.5;
  }

  randomBlinkInterval() {
    return this.randomRange(this.config.blinkIntervalMin, this.config.blinkIntervalMax);
  }

  randomSaccadeInterval() {
    return this.randomRange(this.config.saccadeIntervalMin, this.config.saccadeIntervalMax);
  }

  update(delta, profile = {}) {
    if (this.disposed) return this.output;
    const dt = Math.min(0.1, Math.max(0, Number(delta) || 0));
    this.time += dt;

    const breathRate = profile.breathRate || 1.0;
    const breathDepth = profile.breathDepth || 0.035;
    const blinkRateMultiplier = profile.blinkRate !== undefined ? profile.blinkRate : 1.0;

    // 1. Natural Breathing
    // Breathing cycle operates between 0.0 and 1.0 for ParamBreath
    const breathPhase = this.time * 2.1 * breathRate;
    const rawSine = Math.sin(breathPhase);
    const breathValue = (rawSine + 1.0) * 0.5; // Normalized 0..1
    const torsoOffsetY = rawSine * breathDepth * 20.0;

    // 2. Realistic Blinking State Machine
    this.updateBlinking(dt, blinkRateMultiplier);

    // 3. Eye Micro-Saccades
    this.updateSaccades(dt);

    // 4. Secondary Micro-Head Drift (Multi-frequency organic drift)
    this.updateMicroDrift(dt);

    this.output.breathValue = breathValue;
    this.output.torsoOffsetY = torsoOffsetY;
    this.output.blinkRatio = this.blinkRatio;
    this.output.saccadeX = this.saccadeX;
    this.output.saccadeY = this.saccadeY;
    this.output.driftAngleX = this.driftAngleX;
    this.output.driftAngleY = this.driftAngleY;
    this.output.driftAngleZ = this.driftAngleZ;
    return this.output;
  }

  updateBlinking(delta, blinkRateMultiplier) {
    if (blinkRateMultiplier <= 0) {
      // Eyes remain fixed in current state (e.g. OFFLINE eyes closed)
      this.blinkRatio = 1.0;
      return;
    }

    const closingDuration = 0.09; // Fast closing (~90ms)
    const closedDuration = 0.035; // Brief hold (~35ms)
    const openingDuration = 0.12; // Natural reopening (~120ms)

    switch (this.blinkPhase) {
      case "INTERVAL":
        this.blinkTimer += delta;
        const adjustedInterval = this.nextBlinkInterval / Math.max(0.1, blinkRateMultiplier);
        if (this.blinkTimer >= adjustedInterval) {
          this.blinkPhase = "CLOSING";
          this.blinkTimer = 0;
          this.isDoubleBlink = this.randomValue() < this.config.doubleBlinkProbability;
        }
        this.blinkRatio = 1.0;
        break;

      case "CLOSING":
        this.blinkTimer += delta;
        const closingProgress = Math.min(1.0, this.blinkTimer / closingDuration);
        this.blinkRatio = 1.0 - closingProgress;
        if (closingProgress >= 1.0) {
          this.blinkPhase = "CLOSED";
          this.blinkTimer = 0;
          this.blinkRatio = 0.0;
        }
        break;

      case "CLOSED":
        this.blinkTimer += delta;
        this.blinkRatio = 0.0;
        if (this.blinkTimer >= closedDuration) {
          this.blinkPhase = "OPENING";
          this.blinkTimer = 0;
        }
        break;

      case "OPENING":
        this.blinkTimer += delta;
        const openingProgress = Math.min(1.0, this.blinkTimer / openingDuration);
        this.blinkRatio = openingProgress;
        if (openingProgress >= 1.0) {
          this.blinkRatio = 1.0;
          if (this.isDoubleBlink) {
            // Immediately trigger second fast blink
            this.isDoubleBlink = false;
            this.blinkPhase = "CLOSING";
            this.blinkTimer = 0;
          } else {
            this.blinkPhase = "INTERVAL";
            this.blinkTimer = 0;
            this.nextBlinkInterval = this.randomBlinkInterval();
          }
        }
        break;
    }
  }

  updateSaccades(delta) {
    this.saccadeTimer += delta;
    if (this.saccadeTimer >= this.nextSaccadeInterval) {
      this.saccadeTimer = 0;
      this.nextSaccadeInterval = this.randomSaccadeInterval();
      // Generate small random micro-saccade offset
      this.targetSaccadeX = (this.randomValue() - 0.5) * 0.08;
      this.targetSaccadeY = (this.randomValue() - 0.5) * 0.06;
    }

    // Smoothly ease toward saccade target
    const ease = 1.0 - Math.exp(-delta * 8.0);
    this.saccadeX += (this.targetSaccadeX - this.saccadeX) * ease;
    this.saccadeY += (this.targetSaccadeY - this.saccadeY) * ease;
  }

  updateMicroDrift(delta = 0) {
    this.variationTimer += delta;
    if (this.variationTimer >= this.nextVariationInterval) {
      this.variationTimer = 0;
      this.nextVariationInterval = this.randomRange(this.config.variationIntervalMin, this.config.variationIntervalMax);
      this.targetVariation = this.config.variationMin
        + this.randomValue() * (this.config.variationMax - this.config.variationMin);
    }
    const variationEase = 1 - Math.exp(-delta * 0.8);
    this.variation += (this.targetVariation - this.variation) * variationEase;

    // Organic multi-harmonic drifting (keeps head posture alive)
    const t = this.time;
    this.driftAngleX = (Math.sin(t * 0.5) * 0.7 + Math.cos(t * 0.9) * 0.35) * this.variation;
    // Horizontal yaw is additionally damped by Live2DController; keep this
    // source small so idle life never pulls the character off-center.
    this.driftAngleY = (Math.cos(t * 0.4) * 0.18 + Math.sin(t * 0.75) * 0.09) * this.variation;
    this.driftAngleZ = Math.sin(t * 0.3) * 0.45 * this.variation;
  }

  reset() {
    this.time = 0;
    this.blinkPhase = "INTERVAL";
    this.blinkTimer = 0;
    this.blinkRatio = 1.0;
    this.saccadeTimer = 0;
    this.saccadeX = 0;
    this.saccadeY = 0;
    this.nextBlinkInterval = this.randomBlinkInterval();
    this.nextSaccadeInterval = this.randomSaccadeInterval();
    this.variationTimer = 0;
    this.nextVariationInterval = this.randomRange(this.config.variationIntervalMin, this.config.variationIntervalMax);
    this.variation = 1;
    this.targetVariation = 1;
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    this.reset();
  }
}
