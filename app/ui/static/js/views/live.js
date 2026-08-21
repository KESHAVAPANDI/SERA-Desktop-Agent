/**
 * LiveView — Primary Conversational Interface, Reactive Aura Orb, Hold-To-Talk Visualizer & Activity Rail
 */

export class LiveView {
  constructor(socketSender) {
    this.send = socketSender;
    this.chatStream = document.getElementById("chat-stream");
    this.chatForm = document.getElementById("chat-form");
    this.chatInput = document.getElementById("chat-input");
    
    // Aura & Hold-To-Talk Elements
    this.auraOrb = document.getElementById("aura-orb-main");
    this.auraStatusText = document.getElementById("aura-status-subtext");
    this.captureContainer = document.getElementById("capture-progress-container");
    this.captureTimerVal = document.getElementById("capture-timer-val");
    this.captureProgressFill = document.getElementById("capture-progress-fill");
    this.activationMethodLabel = document.getElementById("activation-method-label");

    // Current Task Elements
    this.currentTaskCard = document.getElementById("current-task-card");
    this.taskTitle = document.getElementById("task-card-title");
    this.taskStepFill = document.getElementById("task-step-fill");
    this.taskStepLabel = document.getElementById("task-step-label");
    this.taskElapsedTimer = document.getElementById("task-elapsed-timer");
    this.btnInterrupt = document.getElementById("btn-interrupt-task");

    // Activity Rail
    this.activityRail = document.getElementById("live-activity-rail");

    this.elapsedSeconds = 0.0;
    this.holdSeconds = 0.0;
    this.taskTimerInterval = null;
    this.captureTimerInterval = null;
    this.holdTimerInterval = null;

    this.init();
  }

  init() {
    this.chatForm?.addEventListener("submit", e => {
      e.preventDefault();
      const text = this.chatInput.value.trim();
      if (!text) return;
      this.appendMessage("user", text);
      this.chatInput.value = "";
      this.send({ action: "USER_PROMPT", text: text });
      this.startTask(text, 4);
    });

    this.btnInterrupt?.addEventListener("click", () => {
      this.send({ action: "INTERRUPT" });
      this.stopTask("Cancelled by user");
    });
  }

  appendMessage(sender, text) {
    if (!this.chatStream) return;
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}`;
    bubble.textContent = text;
    this.chatStream.appendChild(bubble);
    this.chatStream.scrollTop = this.chatStream.scrollHeight;
  }

  logActivity(eventType, detail) {
    if (!this.activityRail) return;
    const item = document.createElement("div");
    item.className = "activity-rail-item";
    const timeStr = new Date().toLocaleTimeString().split(" ")[0];

    item.innerHTML = `
      <span class="activity-time">${timeStr}</span>
      <span class="activity-badge">${eventType}</span>
      <span class="activity-text">${detail || ''}</span>
    `;

    this.activityRail.prepend(item);
    if (this.activityRail.children.length > 25) {
      this.activityRail.lastElementChild?.remove();
    }
  }

  setAuraState(status, meta = {}) {
    if (this.auraStatusText) {
      this.auraStatusText.textContent = status.toUpperCase();
    }

    if (status === "LISTENING") {
      if (meta.source === "HOTKEY_HOLD" || meta.mode === "HOLD_TO_TALK") {
        this.startHoldToTalkVisualizer();
      } else {
        this.startWakeWordCountdown(5.0);
      }
    } else {
      this.stopHoldToTalkVisualizer();
      this.stopWakeWordCountdown();
    }

    if (status === "BROKEN") {
      this.auraOrb?.classList.add("aura-broken");
    } else {
      this.auraOrb?.classList.remove("aura-broken");
    }
  }

  startHoldToTalkVisualizer() {
    if (!this.captureContainer || !this.captureTimerVal || !this.captureProgressFill) return;
    this.captureContainer.classList.remove("hidden");
    if (this.activationMethodLabel) {
      this.activationMethodLabel.innerHTML = `<strong>HOLD TO TALK</strong> (Release Ctrl+Space to Send)`;
    }

    this.holdSeconds = 0.0;
    this.captureProgressFill.style.width = "100%";
    this.captureProgressFill.style.background = "var(--accent-cyan)";
    this.auraOrb?.classList.add("aura-recording");

    clearInterval(this.holdTimerInterval);
    this.holdTimerInterval = setInterval(() => {
      this.holdSeconds += 0.05;
      const mins = Math.floor(this.holdSeconds / 60).toString().padStart(2, "0");
      const secs = (this.holdSeconds % 60).toFixed(2).padStart(5, "0");
      this.captureTimerVal.textContent = `${mins}:${secs}`;
    }, 50);
  }

  stopHoldToTalkVisualizer() {
    clearInterval(this.holdTimerInterval);
    this.auraOrb?.classList.remove("aura-recording");
    this.captureContainer?.classList.add("hidden");
  }

  startWakeWordCountdown(duration = 5.0) {
    if (!this.captureContainer || !this.captureTimerVal || !this.captureProgressFill) return;
    this.captureContainer.classList.remove("hidden");
    if (this.activationMethodLabel) {
      this.activationMethodLabel.textContent = `Wake Word ("SERA") Detected`;
    }

    let remaining = duration;
    clearInterval(this.captureTimerInterval);
    this.captureTimerInterval = setInterval(() => {
      remaining -= 0.1;
      if (remaining <= 0) {
        remaining = 0;
        clearInterval(this.captureTimerInterval);
        this.captureContainer.classList.add("hidden");
      }
      this.captureTimerVal.textContent = `${remaining.toFixed(1)}s`;
      const pct = (remaining / duration) * 100;
      this.captureProgressFill.style.width = `${pct}%`;
    }, 100);
  }

  stopWakeWordCountdown() {
    clearInterval(this.captureTimerInterval);
    this.captureContainer?.classList.add("hidden");
  }

  startTask(name, totalSteps = 4) {
    if (this.taskTitle) this.taskTitle.textContent = name;
    if (this.taskStepLabel) this.taskStepLabel.textContent = `Step 1 / ${totalSteps}`;
    if (this.taskStepFill) this.taskStepFill.style.width = "25%";
    
    this.elapsedSeconds = 0.0;
    clearInterval(this.taskTimerInterval);
    this.taskTimerInterval = setInterval(() => {
      this.elapsedSeconds += 0.1;
      if (this.taskElapsedTimer) {
        this.taskElapsedTimer.textContent = `${this.elapsedSeconds.toFixed(1)}s`;
      }
    }, 100);
  }

  updateTaskStep(currentStep, totalSteps, actionDescription) {
    if (this.taskStepLabel) {
      this.taskStepLabel.textContent = `Step ${currentStep} / ${totalSteps}: ${actionDescription || ''}`;
    }
    if (this.taskStepFill) {
      const pct = (currentStep / totalSteps) * 100;
      this.taskStepFill.style.width = `${pct}%`;
    }
  }

  stopTask(reason = "✓ Completed") {
    clearInterval(this.taskTimerInterval);
    if (this.taskStepLabel) this.taskStepLabel.textContent = reason;
    if (this.taskStepFill) this.taskStepFill.style.width = "100%";

    // Auto-clear after 2.5s settling
    setTimeout(() => {
      if (this.taskTitle) this.taskTitle.textContent = "Awaiting User Instruction";
      if (this.taskStepLabel) this.taskStepLabel.textContent = "Step 0 / 0";
      if (this.taskStepFill) this.taskStepFill.style.width = "0%";
      if (this.taskElapsedTimer) this.taskElapsedTimer.textContent = "0.0s";
    }, 2500);
  }
}
