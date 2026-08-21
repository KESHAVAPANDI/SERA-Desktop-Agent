import { LiveView } from './views/live.js';
import { WorkflowView } from './views/workflow.js';
import { AgentsView } from './views/agents.js';
import { MemoryView } from './views/memory.js';
import { ProvidersView } from './views/providers.js';
import { HistoryView } from './views/history.js';
import { DebugView } from './views/debug.js';
import { SecurityView } from './views/security.js';

class SERAApp {
  constructor() {
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
    // 1. Initialize 8 First-Class Views
    this.views.live = new LiveView(msg => this.sendMessage(msg));
    this.views.workflow = new WorkflowView(msg => this.sendMessage(msg));
    this.views.agents = new AgentsView();
    this.views.memory = new MemoryView();
    this.views.providers = new ProvidersView((provider, model) => {
      this.switchView("workflow");
      this.views.workflow?.highlightModel(provider, model);
    });
    this.views.history = new HistoryView(targetView => this.switchView(targetView));
    this.views.debug = new DebugView();
    this.views.security = new SecurityView(msg => this.sendMessage(msg));

    // 2. Setup Navigation (1 - 8)
    this.setupNavigation();

    // 3. Connect WebSocket Gateway
    this.connectWebSocket();
  }

  setupNavigation() {
    const tabs = document.querySelectorAll(".nav-tab-btn");
    tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        const targetView = tab.getAttribute("data-view");
        if (targetView) this.switchView(targetView);
      });
    });

    // Keyboard Shortcuts (1-8 across COMMAND, INTELLIGENCE, SYSTEM)
    window.addEventListener("keydown", e => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
      const keyMap = {
        "1": "live",
        "2": "workflow",
        "3": "agents",
        "4": "memory",
        "5": "providers",
        "6": "history",
        "7": "debug",
        "8": "security",
      };
      if (keyMap[e.key]) {
        this.switchView(keyMap[e.key]);
      }
    });
  }

  switchView(viewName) {
    if (this.currentView === viewName) return;

    document.querySelectorAll(".nav-tab-btn").forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-view") === viewName);
    });

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

    if (eventType === "SNAPSHOT") {
      const isAttached = Boolean(data.runtime_attached);
      this.setRuntimeConnectionStatus(isAttached ? "ONLINE" : "STANDALONE");

      this.updateRuntimeState(data.status, data.active_task);
      if (data.providers) this.views.providers?.update(data.providers);
      if (data.workflow) this.views.workflow?.updateGraphData(data.workflow);
    } else if (eventType === "RUNTIME_STATE_CHANGED") {
      this.updateRuntimeState(data.status, data.task);
      this.views.live?.setAuraState(data.status);
    } else if (eventType === "CAPTURE_COUNTDOWN") {
      this.views.live?.startCaptureCountdown(data.duration_seconds || 5.0, data.activation_method || "HOTKEY");
      if (this.captureBadge) {
        this.captureBadge.classList.remove("hidden");
        let rem = data.duration_seconds || 5.0;
        const intv = setInterval(() => {
          rem -= 0.1;
          if (rem <= 0) {
            clearInterval(intv);
            this.captureBadge.classList.add("hidden");
          } else {
            this.captureBadge.textContent = `${rem.toFixed(1)}s`;
          }
        }, 100);
      }
    } else if (eventType === "TRANSCRIPT_RECEIVED") {
      this.views.live?.appendMessage("user", data.text);
      this.views.live?.startTask(data.text);
    } else if (eventType === "AGENT_RESPONSE") {
      this.views.live?.appendMessage("sera", data.text);
    } else if (eventType === "TOOL_STARTED") {
      this.views.live?.updateTaskStep(2, 4, `Executing ${data.tool}`);
    } else if (eventType === "VISION_STARTED") {
      this.views.live?.updateTaskStep(3, 4, "Inspecting screen context");
    } else if (eventType === "TASK_COMPLETED") {
      this.views.live?.stopTask("Task completed");
    } else if (eventType === "TASK_CANCELLED") {
      this.views.live?.stopTask("Task cancelled");
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
});
