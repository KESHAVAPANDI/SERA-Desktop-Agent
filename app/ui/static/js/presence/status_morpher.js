/**
 * SERA 2.0 — Status Morpher
 * Manages kinetic single-line typography beneath the computational core.
 * Adheres to: No chat bubbles, zero accumulating chat history.
 */

export class StatusMorpher {
  constructor(statusLineEl, subtextEl) {
    this.statusLine = statusLineEl;
    this.subtext = subtextEl;
    this.currentText = "IDLE • AWAITING INTENT";
    this.currentSubtext = "";
    this._isTransitioning = false;
  }

  /**
   * Sets the prominent status line with a smooth kinetic blur/fade transition.
   * @param {string} text - Primary status text (e.g. "LISTENING...", "SEARCHING THE WEB...")
   * @param {string} subtext - Optional supporting context (e.g. "RTX 5090 benchmarks")
   * @param {string} stateClass - Optional CSS modifier (e.g. "state-thinking", "state-broken")
   */
  setStatus(text, subtext = "", stateClass = "") {
    if (!this.statusLine) return;
    if (this.currentText === text && this.currentSubtext === subtext) return;

    this.currentText = text;
    this.currentSubtext = subtext;

    // Kinetic Exit Transition
    this.statusLine.style.opacity = "0";
    this.statusLine.style.transform = "translateY(-4px)";
    this.statusLine.style.filter = "blur(4px)";

    if (this.subtext) {
      this.subtext.style.opacity = "0";
    }

    setTimeout(() => {
      this.statusLine.textContent = text;

      // Color tint adjustments based on state
      if (text.includes("BROKEN") || text.includes("FAIL")) {
        this.statusLine.style.color = "#f43f5e";
        this.statusLine.style.borderColor = "rgba(244, 63, 94, 0.4)";
        this.statusLine.style.boxShadow = "0 0 16px rgba(244, 63, 94, 0.35)";
      } else if (text.includes("THINKING") || text.includes("ANALYZING")) {
        this.statusLine.style.color = "#ec4899";
        this.statusLine.style.borderColor = "rgba(236, 72, 153, 0.4)";
        this.statusLine.style.boxShadow = "0 0 16px rgba(236, 72, 153, 0.35)";
      } else if (text.includes("COMPLETED")) {
        this.statusLine.style.color = "#38bdf8";
        this.statusLine.style.borderColor = "rgba(56, 189, 248, 0.5)";
        this.statusLine.style.boxShadow = "0 0 20px rgba(56, 189, 248, 0.5)";
      } else {
        this.statusLine.style.color = "var(--sera-cyan-bright)";
        this.statusLine.style.borderColor = "rgba(0, 240, 255, 0.25)";
        this.statusLine.style.boxShadow = "0 0 16px var(--sera-cyan-glow)";
      }

      if (this.subtext) {
        this.subtext.textContent = subtext || "";
        this.subtext.style.opacity = subtext ? "1" : "0";
      }

      // Kinetic Enter Transition
      this.statusLine.style.opacity = "1";
      this.statusLine.style.transform = "translateY(0)";
      this.statusLine.style.filter = "blur(0px)";
    }, 180);
  }
}
