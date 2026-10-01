import { PresenceEngine } from "./engine/PresenceEngine.js";
import { applyPresentationState, getPresentationState } from "./ui/presentationState.js";
import { AudioInput } from "./integration/AudioInput.js";
import { RenderScheduler } from "./integration/RenderScheduler.js";
import { RuntimeSocket } from "./integration/RuntimeSocket.js";
import {
  createPresenceModel,
  effectiveVisualState,
  reducePresenceMessage,
  withConnection,
} from "./integration/presenceModel.js";

const ACTIVE_STATES = new Set([
  "LISTENING", "TRANSCRIBING", "THINKING", "PLANNING", "EXECUTING",
  "VERIFYING", "WAITING_FOR_APPROVAL", "SPEAKING",
]);

class PresenceApp {
  constructor() {
    this.canvas = document.getElementById("presence-canvas");
    this.root = document.getElementById("glass-panel");
    this.bottomDrawer = document.getElementById("bottom-drawer");
    this.convContainer = document.getElementById("conversation-container");
    this.userTextEl = document.getElementById("user-caption-text");
    this.userStatusPill = document.getElementById("user-status-pill");
    this.seraBox = document.getElementById("sera-caption-box");
    this.seraTextEl = document.getElementById("sera-caption-text");
    this.seraStatusPill = document.getElementById("sera-status-pill");
    this.statusEl = document.getElementById("kinetic-status");
    this.substatusEl = document.getElementById("kinetic-substatus");
    this.connectionEl = document.getElementById("connection-status");
    this.detailsToggle = document.getElementById("details-toggle");
    this.approvalContext = document.getElementById("approval-context");
    this.approvalAction = document.getElementById("approval-action");
    this.approvalReason = document.getElementById("approval-reason");
    this.ttsStatus = document.getElementById("tts-status");
    this.commandCenterBtn = document.getElementById("command-center-btn");
    this.minimizeBtn = document.getElementById("minimize-btn");
    this.closeBtn = document.getElementById("close-btn");

    this.engine = new PresenceEngine(this.canvas);
    this.model = createPresenceModel();
    this.audio = new AudioInput();
    this.cleanupCallbacks = [];
    this.collapseTimer = null;
    this.disposed = false;
    this.lastTaskVisualization = "";

    this.socket = new RuntimeSocket("ws://127.0.0.1:8765", {
      onStatus: (status) => this.setConnection(status),
      onMessage: (message) => this.handleBackendMessage(message),
      onError: (error) => console.warn("[PresenceApp] Runtime socket:", error),
    });
    this.scheduler = new RenderScheduler(() => this.renderFrame(), {
      idleFps: 15,
      activeFps: 30,
      isActive: () => ACTIVE_STATES.has(effectiveVisualState(this.model)),
    });

    this.setupWindowInteractions();
    this.setupUIControls();
    this.setupLifecycle();
    this.projectModel();
    this.scheduler.start();
    this.socket.start();
  }

  listen(target, event, handler, options) {
    if (!target?.addEventListener) return;
    target.addEventListener(event, handler, options);
    this.cleanupCallbacks.push(() => target.removeEventListener(event, handler, options));
  }

  setupLifecycle() {
    this.listen(window, "beforeunload", () => this.dispose(), { once: true });
  }

  setupWindowInteractions() {
    if (window.seraNative?.onGlobalActivate) {
      const unsubscribe = window.seraNative.onGlobalActivate(() => this.expandConversation());
      if (typeof unsubscribe === "function") this.cleanupCallbacks.push(unsubscribe);
    }
    this.listen(this.canvas, "click", () => {
      if (this.convContainer?.classList.contains("active")) this.scheduleConversationCollapse(3000);
      else {
        this.expandConversation();
        this.scheduleConversationCollapse(5000);
      }
    });
  }

  setupUIControls() {
    this.listen(this.commandCenterBtn, "click", (event) => {
      event.stopPropagation();
      if (window.seraNative?.openCommandCenter) window.seraNative.openCommandCenter();
      else window.open("http://127.0.0.1:8765", "_blank", "noopener");
    });
    this.listen(this.minimizeBtn, "click", (event) => {
      event.stopPropagation();
      window.seraNative?.minimize?.();
    });
    this.listen(this.closeBtn, "click", (event) => {
      event.stopPropagation();
      if (window.seraNative?.close) window.seraNative.close();
      else window.close();
    });
    this.listen(this.detailsToggle, "click", (event) => {
      event.stopPropagation();
      const expanded = this.detailsToggle.getAttribute("aria-expanded") === "true";
      this.detailsToggle.setAttribute("aria-expanded", String(!expanded));
      this.root?.classList.toggle("details-visible", !expanded);
    });
    if (this.detailsToggle && !this.detailsToggle.hasAttribute("aria-expanded")) {
      this.detailsToggle.setAttribute("aria-expanded", "false");
    }
  }

  setConnection(status) {
    if (this.disposed) return;
    this.model = withConnection(this.model, status);
    this.projectModel();
  }

  handleBackendMessage(message) {
    if (this.disposed) return;
    const previous = this.model;
    this.model = reducePresenceMessage(previous, message);

    if (message?.event === "TTS_AUDIO_LEVELS") {
      this.audio.setOutputLevels(message.payload || message.data || {});
    }
    if (message?.event && message.event !== "SNAPSHOT") {
      this.engine.triggerEvent(message.event, message.payload || message.data || {});
    }
    if (message?.event === "PRESENCE_CLOSE") {
      if (window.seraNative?.selfClose) window.seraNative.selfClose();
      else window.close();
      return;
    }

    this.projectModel(previous);
  }

  // Kept for Electron snapshot tooling and local diagnostics. Production
  // traffic enters through RuntimeSocket and follows the same reducer path.
  handleBackendEvent(message) {
    this.handleBackendMessage(message);
  }

  projectModel(previous = null) {
    const runtimeAvailable = this.model.connection === "ONLINE" && this.model.runtimeAttached !== false;
    const visualState = runtimeAvailable ? effectiveVisualState(this.model) : "OFFLINE";
    const presentation = getPresentationState(visualState);
    const taskText = this.model.task?.text || "";
    const taskProgress = this.model.task?.progress;
    applyPresentationState(this.root, presentation, {
      task: taskText,
      progress: taskProgress,
      audioActive: this.model.tts.active,
    });
    this.root?.setAttribute("aria-busy", String(ACTIVE_STATES.has(visualState)));
    this.engine.setState(visualState, this.model.task?.type || "GENERAL", taskProgress ?? 0);

    const taskKey = `${this.model.task?.id || ""}:${this.model.task?.type || "GENERAL"}`;
    if (this.model.task && taskKey !== this.lastTaskVisualization) {
      this.lastTaskVisualization = taskKey;
      this.engine.setTaskVisualization(this.model.task.type || "GENERAL", this.model.task.text || "");
    }

    this.renderConnection();
    this.renderCaptions();
    this.renderApproval();
    this.renderAudioStatus();

    const listening = this.model.connection === "ONLINE" && this.model.runtimeState === "LISTENING";
    if (!previous || previous.runtimeState !== this.model.runtimeState || previous.connection !== this.model.connection) {
      this.audio.setListening(listening);
    }

    if (ACTIVE_STATES.has(visualState) || this.model.userCaption || this.model.responseCaption || this.model.approval) {
      this.expandConversation();
    }
  }

  renderConnection() {
    const labels = {
      ONLINE: "Runtime connected",
      CONNECTING: "Connecting to runtime",
      RECONNECTING: "Runtime disconnected — reconnecting",
      OFFLINE: "Runtime offline",
    };
    const label = this.model.connection === "ONLINE" && this.model.runtimeAttached === false
      ? "Connected — SERA runtime unavailable"
      : (labels[this.model.connection] || labels.OFFLINE);
    if (this.connectionEl) {
      this.connectionEl.textContent = label;
      this.connectionEl.dataset.connection = this.model.connection;
    }
    this.root?.setAttribute("data-connection", this.model.connection);
    this.root?.setAttribute("data-runtime-attached", String(this.model.runtimeAttached !== false));
    if (this.model.connection !== "ONLINE" || this.model.runtimeAttached === false) {
      if (this.statusEl) this.statusEl.textContent = "MOCHI IS OFFLINE";
      if (this.substatusEl) this.substatusEl.textContent = label;
    }
  }

  renderCaptions() {
    if (this.userTextEl) {
      if (this.model.userCaption) {
        this.userTextEl.textContent = this.model.userCaption;
        this.userTextEl.className = `caption-text user-text ${this.model.userCaptionFinal ? "finalized" : "partial"}`;
      } else if (this.model.runtimeState === "LISTENING") {
        this.userTextEl.textContent = "Listening…";
        this.userTextEl.className = "caption-text user-text partial";
      } else {
        this.userTextEl.textContent = "Hold Ctrl+Alt+Space to speak…";
        this.userTextEl.className = "caption-text user-text placeholder-text";
      }
    }
    if (this.userStatusPill) {
      this.userStatusPill.textContent = this.model.userCaptionFinal ? "COMMAND" : (this.model.runtimeState === "LISTENING" ? "LISTENING" : "VOICE");
      this.userStatusPill.className = `status-pill ${this.model.userCaptionFinal ? "confirmed-pill" : "listening-pill"}`;
    }

    if (this.seraBox) this.seraBox.classList.toggle("hidden", !this.model.responseCaption);
    if (this.seraTextEl) this.seraTextEl.textContent = this.model.responseCaption;
    if (this.seraStatusPill) {
      this.seraStatusPill.textContent = this.model.tts.active ? "SPEAKING" : (this.model.responseStatus || "RESPONSE");
    }
    if (this.convContainer) this.convContainer.scrollTop = this.convContainer.scrollHeight;
  }

  renderApproval() {
    if (!this.approvalContext) return;
    const approval = this.model.approval;
    this.approvalContext.hidden = !approval;
    this.root?.setAttribute("data-approval", approval ? "pending" : "none");
    if (this.approvalAction) this.approvalAction.textContent = approval?.action || "SERA is waiting for your review.";
    if (this.approvalReason) {
      this.approvalReason.textContent = approval?.reason || "Open SERA to review this request.";
      this.approvalReason.hidden = !approval;
    }
  }

  renderAudioStatus() {
    if (!this.ttsStatus) return;
    this.ttsStatus.textContent = this.model.tts.active ? "Mochi voice playback active" : "Voice playback idle";
  }

  renderFrame() {
    const levels = this.audio.sample(this.model.tts.active);
    this.engine.setAudioData(levels);
    this.engine.update();
  }

  expandConversation() {
    clearTimeout(this.collapseTimer);
    this.collapseTimer = null;
    this.convContainer?.classList.add("active");
    this.bottomDrawer?.classList.add("active");
    this.root?.classList.add("conversation-active");
  }

  collapseConversation() {
    this.convContainer?.classList.remove("active");
    this.bottomDrawer?.classList.remove("active");
    this.root?.classList.remove("conversation-active");
  }

  scheduleConversationCollapse(delayMs) {
    clearTimeout(this.collapseTimer);
    this.collapseTimer = setTimeout(() => {
      this.collapseTimer = null;
      if (!ACTIVE_STATES.has(effectiveVisualState(this.model))) this.collapseConversation();
    }, delayMs);
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    clearTimeout(this.collapseTimer);
    this.socket.stop();
    this.scheduler.stop();
    this.audio.dispose();
    for (const cleanup of this.cleanupCallbacks.splice(0)) {
      try { cleanup(); } catch { /* best-effort native callback cleanup */ }
    }
    this.engine.dispose?.();
  }
}

window.addEventListener("DOMContentLoaded", () => {
  window.seraApp = new PresenceApp();
}, { once: true });
