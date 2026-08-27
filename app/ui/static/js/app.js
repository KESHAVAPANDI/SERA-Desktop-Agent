import { LiveView } from './views/live.js';
import { WorkflowView } from './views/workflow.js';
import { ArchitectView } from './views/architect.js';
import { AgentsView } from './views/agents.js';
import { MemoryView } from './views/memory.js';
import { ProvidersView } from './views/providers.js';
import { HistoryView } from './views/history.js';
import { DebugView } from './views/debug.js';
import { SecurityView } from './views/security.js';

class SERAApp {
  constructor() {
    window.SERA_APP = this;
    window.seraApp = this;
    window.SERA_BUILD_ID = "5D.2";
    this.ws = null;
    this.currentView = "live";
    this.views = {};
    this.stateIndicator = document.getElementById("state-indicator");
    this.stateText = document.getElementById("state-text");
    this.taskTicker = document.getElementById("task-ticker");
    this.captureBadge = document.getElementById("capture-countdown-badge");
    this.privacyModeText = document.getElementById("privacy-mode-text");

    // Runtime Connection Indicator
    this.runtimeIndicator = document.getElementById("runtime-indicator");
    this.runtimeText = document.getElementById("runtime-text");

    this.init();
  }

  init() {
    // 1. Initialize Views with First-Class Live/Workflow/Architect Separation
    this.views.live = new LiveView(msg => this.sendMessage(msg), targetView => this.switchView(targetView));
    this.views.workflow = new WorkflowView(msg => this.sendMessage(msg), targetView => this.switchView(targetView));
    this.views.architect = new ArchitectView(msg => this.sendMessage(msg));
    this.views.agents = new AgentsView();
    this.views.memory = new MemoryView();
    this.views.providers = new ProvidersView((provider, model) => {
      this.switchView("workflow");
      this.views.workflow?.highlightModel(provider, model);
    });
    this.views.history = new HistoryView(targetView => this.switchView(targetView));
    this.views.debug = new DebugView();
    this.views.security = new SecurityView(msg => this.sendMessage(msg));

    // 2. Setup Navigation (1 - 9)
    this.setupNavigation();

    // 3. Connect WebSocket Gateway
    this.connectWebSocket();
  }

  setupNavigation() {
    const tabs = document.querySelectorAll(".nav-tab-btn, .dropdown-item");
    tabs.forEach(tab => {
      tab.addEventListener("click", e => {
        const btn = e.target.closest(".nav-tab-btn, .dropdown-item") || tab;
        const targetView = btn.getAttribute("data-view");
        if (targetView) this.switchView(targetView);
      });
    });

    document.getElementById("btn-mode-design")?.addEventListener("click", () => {
      this.switchView("architect");
    });

    // Keyboard Shortcuts (1-9 across primary and dropdown views)
    window.addEventListener("keydown", e => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
      const keyMap = {
        "1": "live",
        "2": "workflow",
        "3": "architect",
        "4": "agents",
        "5": "providers",
        "6": "memory",
        "7": "history",
        "8": "debug",
        "9": "security",
      };
      if (keyMap[e.key]) {
        this.switchView(keyMap[e.key]);
      }
    });
  }

  switchView(viewName) {
    if (this.currentView === viewName) return;

    document.querySelectorAll(".nav-tab-btn, .dropdown-item").forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-view") === viewName);
    });

    const isDropdownItem = ["memory", "history", "debug", "security"].includes(viewName);
    const moreBtn = document.getElementById("tab-more-btn");
    if (moreBtn) {
      moreBtn.classList.toggle("active", isDropdownItem);
    }

    document.querySelectorAll(".view-container").forEach(c => {
      c.classList.toggle("active", c.id === `view-${viewName}`);
    });

    this.currentView = viewName;
  }

  connectWebSocket() {
    const loc = window.location;
    const wsUrl = `ws://${loc.hostname || '127.0.0.1'}:${loc.port || '8765'}/ws`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.views.debug?.logEvent("GATEWAY_CONNECTED", { url: wsUrl });
      };

      this.ws.onmessage = evt => {
        try {
          const payload = JSON.parse(evt.data);
          this.handleEvent(payload.event, payload.data);
        } catch (e) {
          console.error("[SERA UI] Failed to parse event:", e);
        }
      };

      this.ws.onclose = () => {
        this.setRuntimeConnectionStatus("DISCONNECTED");
        this.views.live?.appendSystemNotice("init", "RUNTIME OFFLINE — Attempting automatic reconnect...");
        this.views.debug?.logEvent("GATEWAY_DISCONNECTED", { retry_in: "3s" });
        setTimeout(() => this.connectWebSocket(), 3000);
      };
    } catch (e) {
      this.setRuntimeConnectionStatus("DISCONNECTED");
      console.warn("[SERA UI] Standalone mode.");
    }
  }

  setRuntimeConnectionStatus(status) {
    if (!this.runtimeIndicator || !this.runtimeText) return;
    this.runtimeIndicator.className = "runtime-badge";

    if (status === "ONLINE") {
      this.runtimeIndicator.classList.add("runtime-online");
      this.runtimeText.textContent = "RUNTIME: ONLINE";
    } else if (status === "STANDALONE") {
      this.runtimeIndicator.classList.add("runtime-standalone");
      this.runtimeText.textContent = "RUNTIME: STANDALONE";
    } else {
      this.runtimeIndicator.classList.add("runtime-disconnected");
      this.runtimeText.textContent = "RUNTIME: DISCONNECTED";
    }
  }

  sendMessage(msg) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  handleEvent(eventType, data) {
    this.views.debug?.logEvent(eventType, data);
    this.views.workflow?.handleRuntimeEvent(eventType, data);
    this.views.live?.handleRuntimeEvent(eventType, data);

    if (eventType === "SNAPSHOT") {
      const isAttached = Boolean(data.runtime_attached);
      this.setRuntimeConnectionStatus(isAttached ? "ONLINE" : "STANDALONE");

      this.updateRuntimeState(data.status, data.active_task);
      if (data.providers) this.views.providers?.update(data.providers);
      if (data.architect) this.views.architect?.loadConfigData(data.architect);
      if (data.capabilities) this.views.live?.renderCapabilities(data.capabilities);

      // Dev Unrestricted Pill
      const devPill = document.getElementById("dev-unrestricted-pill");
      if (devPill) {
        devPill.classList.toggle("hidden", !Boolean(data.dev_mode_unrestricted));
      }

      if (data.active_task_info && data.active_task_info.status === "EXECUTING") {
        this.views.live?.startTask(data.active_task_info);
      }

      // Truthful Header Telemetry Pills
      const wakeEl = document.getElementById("wake-status-text");
      if (wakeEl && data.wake_word_status) wakeEl.textContent = `WAKE: ${data.wake_word_status}`;

      const sttEl = document.getElementById("stt-status-text");
      if (sttEl && data.stt_info?.status) sttEl.textContent = `STT: ${data.stt_info.status.toUpperCase()}`;

      const micEl = document.getElementById("mic-status-text");
      if (micEl && data.mic_status) micEl.textContent = `MIC: ${data.mic_status.toUpperCase()}`;

      const gpuEl = document.getElementById("gpu-gauge");
      if (gpuEl && data.gpu_usage_pct != null) gpuEl.textContent = `${data.gpu_usage_pct}%`;

      const ramEl = document.getElementById("ram-gauge");
      if (ramEl && data.system_memory_mb != null) ramEl.textContent = `${(data.system_memory_mb / 1024).toFixed(1)} GB`;

    } else if (eventType === "ARCHITECT_CONFIG" || eventType === "ARCHITECT_CONFIG_SAVED" || eventType === "CONFIG_UPDATED") {
      this.views.architect?.loadConfigData(data.config || data);
    } else if (eventType === "ARCHITECT_TEST_RESULT") {
      this.views.architect?.renderSimulationTrace(data);
    } else if (eventType === "RUNTIME_STATE_CHANGED") {
      this.updateRuntimeState(data.status, data.task);
    } else if (eventType === "ACTIVATION_STARTED") {
      this.updateRuntimeState("LISTENING");
    } else if (eventType === "ACTIVATION_RELEASED" || eventType === "TRANSCRIPTION_STARTED") {
      this.updateRuntimeState("TRANSCRIBING");
    } else if (eventType === "TASK_STARTED") {
      this.updateRuntimeState("EXECUTING", data.user_input);
    } else if (eventType === "TASK_COMPLETED" || eventType === "TASK_CANCELLED" || eventType === "TASK_FAILED") {
      this.updateRuntimeState("IDLE");
    } else if (eventType === "SECURITY_CONFIRMATION_REQUIRED") {
      this.views.security?.showConfirmationRequest(data.action_id, data.tool_name, data.prompt, data.arguments);
      this.updateRuntimeState("CONFIRMING_ACTION", `Confirmation required: ${data.tool_name}`);
    }
  }

  updateRuntimeState(status, task) {
    if (!status) return;
    const sLower = status.toLowerCase();

    if (this.stateIndicator && this.stateText) {
      this.stateIndicator.className = `state-indicator state-${sLower}`;
      this.stateText.textContent = status.toUpperCase();
    }

    if (this.taskTicker && task) {
      this.taskTicker.textContent = `Task: ${task}`;
    }
  }
}

window.addEventListener("DOMContentLoaded", () => {
  window.seraApp = new SERAApp();
  window.SERA_APP = window.seraApp;
});
