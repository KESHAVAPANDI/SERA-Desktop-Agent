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
  constructor() {
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
  }

  randomBlinkInterval() {
    // Human average blink interval: 2.5 to 5.5 seconds
    return 2.5 + Math.random() * 3.0;
  }

  randomSaccadeInterval() {
    // Micro-fixation shift interval: 1.8 to 4.2 seconds
    return 1.8 + Math.random() * 2.4;
  }

  update(delta, profile = {}) {
    this.time += delta;

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
    this.updateBlinking(delta, blinkRateMultiplier);

    // 3. Eye Micro-Saccades
    this.updateSaccades(delta);

    // 4. Secondary Micro-Head Drift (Multi-frequency organic drift)
    this.updateMicroDrift();

    return {
      breathValue,
      torsoOffsetY,
      blinkRatio: this.blinkRatio,
      saccadeX: this.saccadeX,
      saccadeY: this.saccadeY,
      driftAngleX: this.driftAngleX,
      driftAngleY: this.driftAngleY,
      driftAngleZ: this.driftAngleZ,
    };
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
          this.isDoubleBlink = Math.random() < 0.18; // 18% chance of double-blink
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
      this.targetSaccadeX = (Math.random() - 0.5) * 0.08;
      this.targetSaccadeY = (Math.random() - 0.5) * 0.06;
    }

    // Smoothly ease toward saccade target
    const ease = 1.0 - Math.exp(-delta * 8.0);
    this.saccadeX += (this.targetSaccadeX - this.saccadeX) * ease;
    this.saccadeY += (this.targetSaccadeY - this.saccadeY) * ease;
  }

  updateMicroDrift() {
    // Organic multi-harmonic drifting (keeps head posture alive)
    const t = this.time;
    this.driftAngleX = Math.sin(t * 0.5) * 0.7 + Math.cos(t * 0.9) * 0.35;
    this.driftAngleY = Math.cos(t * 0.4) * 0.5 + Math.sin(t * 0.75) * 0.25;
    this.driftAngleZ = Math.sin(t * 0.3) * 0.45;
  }

  reset() {
    this.time = 0;
    this.blinkPhase = "INTERVAL";
    this.blinkTimer = 0;
    this.blinkRatio = 1.0;
    this.saccadeTimer = 0;
    this.saccadeX = 0;
    this.saccadeY = 0;
  }
}
