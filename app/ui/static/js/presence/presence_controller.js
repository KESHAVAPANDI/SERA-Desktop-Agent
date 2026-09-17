/**
 * SERA 2.0 — Presence Controller
 * Bridges WebSocket runtime events, user interactions, and visual state execution.
 */

import { PresenceEngine } from "./presence_engine.js";
import { StatusMorpher } from "./status_morpher.js";

export class PresenceController {
  constructor() {
    this.canvas = document.getElementById("presence-canvas");
    this.statusLine = document.getElementById("status-line");
    this.statusSubtext = document.getElementById("status-subtext");
    this.inputOverlay = document.getElementById("floating-input-overlay");
    this.promptInput = document.getElementById("prompt-input");
    this.sendBtn = document.getElementById("send-prompt-btn");

    this.engine = new PresenceEngine(this.canvas);
    this.morpher = new StatusMorpher(this.statusLine, this.statusSubtext);

    this.ws = null;
    this.reconnectTimer = null;

    this._setupUserInteractions();
    this._setupSimulationPills();
    this._connectWebSocket();
  }

  _setupUserInteractions() {
    // Click on core canvas toggles the minimal floating prompt input
    this.canvas.addEventListener("click", () => {
      this._toggleInput(true);
    });

    // Send Prompt Handler
    const submitPrompt = () => {
      const text = this.promptInput.value.trim();
      if (!text) return;
      this._sendUserPrompt(text);
      this.promptInput.value = "";
      this._toggleInput(false);
    };

    this.sendBtn.addEventListener("click", submitPrompt);
    this.promptInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        submitPrompt();
      } else if (e.key === "Escape") {
        this._toggleInput(false);
      }
    });

    // Global keyboard shortcuts
    window.addEventListener("keydown", (e) => {
      // Toggle input on Space or Enter (if not already focused)
      if ((e.code === "Space" || e.code === "Enter") && document.activeElement !== this.promptInput) {
        if (!this.inputOverlay.classList.contains("visible")) {
          e.preventDefault();
          this._toggleInput(true);
        }
      }

      // Quick Numeric Keys 1-9 for instant simulation & testing
      if (document.activeElement !== this.promptInput) {
        const keyMap = {
          "1": "IDLE",
          "2": "LISTENING",
          "3": "TRANSCRIBING",
          "4": "THINKING",
          "5": "EXECUTING",
          "6": "SPEAKING",
          "7": "BROKEN",
          "8": "CANCELLED",
          "9": "COMPLETED",
        };
        if (keyMap[e.key]) {
          this.triggerState(keyMap[e.key]);
        }
      }
    });
  }

  _toggleInput(show) {
    if (show) {
      this.inputOverlay.classList.add("visible");
      this.promptInput.focus();
    } else {
      this.inputOverlay.classList.remove("visible");
      this.promptInput.blur();
    }
  }

  _setupSimulationPills() {
    const pills = document.querySelectorAll(".state-pill-btn");
    pills.forEach((btn) => {
      btn.addEventListener("click", () => {
        pills.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const state = btn.getAttribute("data-state");
        this.triggerState(state);
      });
    });
  }

  /**
   * Triggers visual state and updates status text.
   * @param {string} state - The state name
   * @param {string} [customText] - Optional custom status text
   * @param {string} [subtext] - Optional subtext
   */
  triggerState(state, customText = null, subtext = null) {
    const s = state.toUpperCase();
    this.engine.setState(s);

    // Update simulation pills active class if matching
    const pill = document.querySelector(`.state-pill-btn[data-state="${s}"]`);
    if (pill) {
      document.querySelectorAll(".state-pill-btn").forEach((b) => b.classList.remove("active"));
      pill.classList.add("active");
    }

    // Default status texts
    const defaultTexts = {
      IDLE: "IDLE • AWAITING INTENT",
      LISTENING: "LISTENING • PERCEIVING AUDIO",
      TRANSCRIBING: "TRANSCRIBING SPEECH STREAM...",
      THINKING: "ANALYZING OBJECTIVE & TOOLS...",
      EXECUTING: "EXECUTING SYSTEM ACTIONS...",
      SPEAKING: "TRANSMITTING ACOUSTIC RESPONSE...",
      BROKEN: "EXECUTION DISRUPTED • BROKEN STATE",
      CANCELLED: "OPERATION ABORTED BY OPERATOR",
      COMPLETED: "STRUCTURE RECONSTRUCTED • COMPLETE",
    };

    const displayText = customText || defaultTexts[s] || s;
    this.morpher.setStatus(displayText, subtext || "");
  }

  _connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("[SERA Presence] Connected to runtime WebSocket.");
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this._handleServerEvent(msg);
        } catch (e) {
          console.error("[SERA Presence] JSON parse error:", e);
        }
      };

      this.ws.onclose = () => {
        console.warn("[SERA Presence] WebSocket disconnected. Retrying in 2s...");
        this._scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.ws.close();
      };
    } catch (e) {
      this._scheduleReconnect();
    }
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this._connectWebSocket(), 2000);
  }

  _sendUserPrompt(text) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "USER_PROMPT", text }));
      this.triggerState("THINKING", "PROCESSING OBJECTIVE...", text);
    } else {
      // Fallback via HTTP REST API
      fetch("/api/task/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      }).catch((e) => console.error("REST task fallback error:", e));
      this.triggerState("THINKING", "PROCESSING OBJECTIVE...", text);
    }
  }

  _handleServerEvent(msg) {
    const ev = msg.event;
    const data = msg.data || {};

    switch (ev) {
      case "RUNTIME_STATE_CHANGED":
        if (data.status) {
          this.triggerState(data.status, null, data.task || "");
        }
        break;

      case "LISTENING_STARTED":
      case "ACTIVATION_STARTED":
        this.triggerState("LISTENING", "LISTENING • SPEAK NOW...");
        break;

      case "TRANSCRIPTION_STARTED":
        this.triggerState("TRANSCRIBING", "TRANSCRIBING PERCEIVED AUDIO...");
        break;

      case "TRANSCRIPTION_COMPLETED":
        const transcript = data.text || data.transcript || "";
        this.triggerState("THINKING", "ANALYZING INTENT...", transcript);
        break;

      case "TASK_STARTED":
        const input = data.user_input || data.prompt || "";
        this.triggerState("THINKING", "DECONSTRUCTING OBJECTIVE...", input);
        break;

      case "TOOL_STARTED":
        const toolName = (data.tool || data.name || "System Action").replace(/_/g, " ");
        this.triggerState("EXECUTING", `EXECUTING: ${toolName.toUpperCase()}...`);
        break;

      case "TOOL_COMPLETED":
        const completedTool = (data.tool || data.name || "Tool").replace(/_/g, " ");
        this.morpher.setStatus("VERIFIED TOOL EXECUTION", `✓ ${completedTool} verified`);
        break;

      case "AGENT_RESPONSE":
        this.triggerState("SPEAKING", "SERA TRANSMITTING RESPONSE...", (data.text || "").slice(0, 80));
        break;

      case "TASK_COMPLETED":
        this.triggerState("COMPLETED", "OBJECTIVE VERIFIED & COMPLETED");
        break;

      case "TASK_FAILED":
        this.triggerState("BROKEN", "EXECUTION FAILED", data.error || "");
        break;

      case "TASK_CANCELLED":
        this.triggerState("CANCELLED", "OPERATION CANCELLED");
        break;
    }
  }
}
