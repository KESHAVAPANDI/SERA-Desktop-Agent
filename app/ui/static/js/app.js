import { WorkflowView } from './views/workflow.js';
import { LiveView } from './views/live.js';
import { AgentsView } from './views/agents.js';
import { MemoryView } from './views/memory.js';
import { ProvidersView } from './views/providers.js';
import { HistoryView } from './views/history.js';
import { DebugView } from './views/debug.js';

class SERAApp {
  constructor() {
    this.ws = null;
    this.currentView = "workflow";
    this.views = {};
    this.stateIndicator = document.getElementById("state-indicator");
    this.stateText = document.getElementById("state-text");
    this.taskTicker = document.getElementById("task-ticker");
    this.init();
  }

  init() {
    // 1. Initialize Views
    this.views.workflow = new WorkflowView();
    this.views.live = new LiveView(msg => this.sendMessage(msg));
    this.views.agents = new AgentsView();
    this.views.memory = new MemoryView();
    this.views.providers = new ProvidersView();
    this.views.history = new HistoryView(viewName => this.switchView(viewName));
    this.views.debug = new DebugView();

    // 2. Setup Navigation
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

    // Keyboard Shortcuts (1-7)
    window.addEventListener("keydown", e => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      const keyMap = {
        "1": "workflow",
        "2": "live",
        "3": "agents",
        "4": "memory",
        "5": "providers",
        "6": "history",
        "7": "debug",
      };
      if (keyMap[e.key]) {
        this.switchView(keyMap[e.key]);
      }
    });
  }

  switchView(viewName) {
    if (this.currentView === viewName) return;

    // Update Tab Buttons
    document.querySelectorAll(".nav-tab-btn").forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-view") === viewName);
    });

    // Update Containers
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
        this.views.debug?.logEvent("GATEWAY_DISCONNECTED", { retry_in: "3s" });
        setTimeout(() => this.connectWebSocket(), 3000);
      };
    } catch (e) {
      console.warn("[SERA UI] WebSocket connection unavailable. Operating in standalone demo mode.");
    }
  }

  sendMessage(msg) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  handleEvent(eventType, data) {
    this.views.debug?.logEvent(eventType, data);

    if (eventType === "SNAPSHOT") {
      this.updateRuntimeState(data.status, data.active_task);
      if (data.providers) {
        this.views.providers?.update(data.providers);
      }
    } else if (eventType === "RUNTIME_STATE_CHANGED") {
      this.updateRuntimeState(data.status, data.task);
    } else if (eventType === "TRANSCRIPT_RECEIVED") {
      this.views.live?.appendMessage("user", data.text);
    } else if (eventType === "AGENT_RESPONSE") {
      this.views.live?.appendMessage("sera", data.text);
    }
  }

  updateRuntimeState(status, task) {
    if (!status) return;
    const sLower = status.toLowerCase();

    // Update Header Badge
    if (this.stateIndicator && this.stateText) {
      this.stateIndicator.className = `state-indicator state-${sLower}`;
      this.stateText.textContent = status.toUpperCase();
    }

    if (this.taskTicker && task) {
      this.taskTicker.textContent = `Task: ${task}`;
    }
  }
}

// Bootstrap on DOM Ready
window.addEventListener("DOMContentLoaded", () => {
  window.seraApp = new SERAApp();
});
