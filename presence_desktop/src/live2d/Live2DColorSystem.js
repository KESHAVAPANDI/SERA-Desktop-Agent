/**
 * SERA 2.0 Live2D State Color System
 *
 * Implements smooth data-driven color transitions that influence:
 * - Subtle ambient tint on the Live2D model (preserving natural skin/hair textures)
 * - Eye effect and accessory parameters (e.g. ParamEyeEffect, ParamHeartColorLight)
 * - Luminous background aura and particles
 * - Surrounding desktop glass container styling via CSS variables
 *
 * Keeps character identity stable while providing rich semantic state signaling.
 */

export class Live2DColorSystem {
  constructor(initialColor = [0.22, 0.74, 0.97], initialAura = 0.35) {
    this.current = [...initialColor];
    this.target = [...initialColor];
    this.currentAura = initialAura;
    this.targetAura = initialAura;
    this.smoothingSpeed = 4.0; // Higher = faster transition
  }

  setTargetColor(rgb, auraIntensity = 0.5) {
    if (Array.isArray(rgb) && rgb.length >= 3) {
      this.target = [
        Math.max(0, Math.min(1, rgb[0])),
        Math.max(0, Math.min(1, rgb[1])),
        Math.max(0, Math.min(1, rgb[2])),
      ];
    }
    this.targetAura = Math.max(0, Math.min(1, auraIntensity));
  }

  update(delta) {
    const factor = 1.0 - Math.exp(-delta * this.smoothingSpeed);

    for (let i = 0; i < 3; i++) {
      this.current[i] += (this.target[i] - this.current[i]) * factor;
    }
    this.currentAura += (this.targetAura - this.currentAura) * factor;

    return {
      rgb: this.current,
      aura: this.currentAura,
      hex: this.getHexColor(),
      cssRgb: this.getCssRgb(),
      cssAura: this.getCssAura(),
    };
  }

  getHexColor() {
    const r = Math.round(this.current[0] * 255);
    const g = Math.round(this.current[1] * 255);
    const b = Math.round(this.current[2] * 255);
    return (r << 16) | (g << 8) | b;
  }

  getCssRgb() {
    const r = Math.round(this.current[0] * 255);
    const g = Math.round(this.current[1] * 255);
    const b = Math.round(this.current[2] * 255);
    return `rgb(${r}, ${g}, ${b})`;
  }

  getCssAura() {
    const r = Math.round(this.current[0] * 255);
    const g = Math.round(this.current[1] * 255);
    const b = Math.round(this.current[2] * 255);
    const a = this.currentAura.toFixed(3);
    return `rgba(${r}, ${g}, ${b}, ${a})`;
  }

  /**
   * Calculate subtle model tint that preserves skin and facial textures
   * while imparting a delicate state-specific luminescence.
   */
  getModelTint() {
    // 82% base brightness + 18% state color saturation
    const r = Math.round((0.82 + this.current[0] * 0.18) * 255);
    const g = Math.round((0.82 + this.current[1] * 0.18) * 255);
    const b = Math.round((0.82 + this.current[2] * 0.18) * 255);
    return (r << 16) | (g << 8) | b;
  }

  /**
   * Apply CSS variables to a root DOM element for unified window styling.
   */
  applyToDOM(element) {
    if (!element || !element.style) return;
    const cssRgb = this.getCssRgb();
    const cssAura = this.getCssAura();
    element.style.setProperty("--live2d-accent-color", cssRgb);
    element.style.setProperty("--live2d-aura-color", cssAura);
    element.style.setProperty("--live2d-glow", `0 0 24px ${cssAura}`);
  }
}
