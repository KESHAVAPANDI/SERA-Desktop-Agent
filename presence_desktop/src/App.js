/**
 * SERA 2.0 — Desktop Presence Main Application Controller
 * Handles UI interactions, drag positioning, WebSocket bridge to Python backend,
 * and kinetic status typography.
 * 
 * Author: Keshava Pandi A S <keshavapandi@gmail.com>
 */

import { PresenceEngine } from "./engine/PresenceEngine.js";

class PresenceApp {
  constructor() {
    this.canvas = document.getElementById("presence-canvas");
    this.statusEl = document.getElementById("kinetic-status");
    this.substatusEl = document.getElementById("kinetic-substatus");
    this.inputWrapper = document.getElementById("input-capsule-wrapper");
    this.promptInput = document.getElementById("presence-prompt-input");
    this.promptForm = document.getElementById("presence-prompt-form");
    this.commandCenterBtn = document.getElementById("command-center-btn");
    this.minimizeBtn = document.getElementById("minimize-btn");

    this.engine = new PresenceEngine(this.canvas);
    this.ws = null;
    this.isDragging = false;
    this.lastMousePos = { x: 0, y: 0 };

    this.setupWindowInteractions();
    this.setupUIControls();
    this.initAudioReactivity();
    this.connectBackendWebSocket();
    this.startRenderLoop();
  }

  async initAudioReactivity() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 128;
      analyser.smoothingTimeConstant = 0.8;
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateAudio = () => {
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        let bassSum = 0, midSum = 0, trebleSum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
          if (i < 8) bassSum += dataArray[i];
          else if (i < 28) midSum += dataArray[i];
          else trebleSum += dataArray[i];
        }
        const avg = sum / dataArray.length;
        const rawAmp = Math.min(1.0, avg / 60.0);
        const bass = Math.min(1.0, (bassSum / 8) / 65.0);
        const mid = Math.min(1.0, (midSum / 20) / 55.0);
        const treble = Math.min(1.0, (trebleSum / Math.max(1, dataArray.length - 28)) / 45.0);

        this.engine.setAudioData({ rawAmp, bass, mid, treble });
        requestAnimationFrame(updateAudio);
      };
      updateAudio();
      console.log("[PresenceApp] Live audio-reactive microphone input activated (multi-band).");
    } catch (err) {
      console.log("[PresenceApp] Microphone stream optional/unavailable:", err);
    }
  }

  setupWindowInteractions() {
    const glassPanel = document.getElementById("glass-panel") || this.canvas;
    let dragDistance = 0;

    // Glass panel mouse drag repositioning
    glassPanel.addEventListener("mousedown", (e) => {
      if (e.target.closest("button") || e.target.closest("input") || e.target.closest("form")) {
        return;
      }
      if (e.button === 0) {
        this.isDragging = true;
        dragDistance = 0;
        this.lastMousePos = { x: e.screenX, y: e.screenY };
      }
    });

    window.addEventListener("mousemove", (e) => {
      if (this.isDragging && window.seraNative) {
        const dx = e.screenX - this.lastMousePos.x;
        const dy = e.screenY - this.lastMousePos.y;
        dragDistance += Math.abs(dx) + Math.abs(dy);
        this.lastMousePos = { x: e.screenX, y: e.screenY };
        window.seraNative.dragWindow(dx, dy);
      }
    });

    window.addEventListener("mouseup", () => {
      this.isDragging = false;
    });

    // Global Shortcut summon / toggle
    if (window.seraNative && window.seraNative.onGlobalActivate) {
      window.seraNative.onGlobalActivate(() => {
        this.togglePromptInput();
      });
    }

    // Panel click toggles prompt input if not dragging
    glassPanel.addEventListener("click", (e) => {
      if (e.target.closest("button") || e.target.closest("input") || e.target.closest("form")) {
        return;
      }
      if (dragDistance < 6) {
        this.togglePromptInput();
      }
    });
  }

  setupUIControls() {
    // Command Center external trigger
    if (this.commandCenterBtn) {
      this.commandCenterBtn.addEventListener("click", () => {
        if (window.seraNative) {
          window.seraNative.openCommandCenter();
        } else {
          window.open("http://127.0.0.1:8765", "_blank");
        }
      });
    }

    // Minimize trigger
    if (this.minimizeBtn) {
      this.minimizeBtn.addEventListener("click", () => {
        if (window.seraNative) {
          window.seraNative.minimize();
        }
      });
    }

    // Prompt Submission
    if (this.promptForm) {
      this.promptForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = this.promptInput.value.trim();
        if (text) {
          this.submitObjective(text);
          this.promptInput.value = "";
          this.hidePromptInput();
        }
      });
    }

    // Escape closes input
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        this.hidePromptInput();
      }
    });
  }

  togglePromptInput() {
    if (this.inputWrapper.classList.contains("active")) {
      this.hidePromptInput();
    } else {
      this.showPromptInput();
    }
  }

  showPromptInput() {
    this.inputWrapper.classList.add("active");
    this.promptInput.focus();
    this.setStatus("AWAITING OBJECTIVE", "TYPE INTENT OR PRESS ESCAPE TO CANCEL");
  }

  hidePromptInput() {
    this.inputWrapper.classList.remove("active");
    this.promptInput.blur();
    if (this.engine.state === "IDLE") {
      this.setStatus("COGNITIVE EQUILIBRIUM", "AWAITING INTENT • CTRL+SPACE");
    }
  }

  setStatus(mainText, subText = null) {
    if (this.statusEl) {
      // Kinetic blur/fade transition
      this.statusEl.style.opacity = "0";
      this.statusEl.style.filter = "blur(4px)";
      this.statusEl.style.transform = "translateY(2px)";

      setTimeout(() => {
        this.statusEl.textContent = mainText;
        this.statusEl.style.opacity = "1";
        this.statusEl.style.filter = "none";
        this.statusEl.style.transform = "translateY(0)";
      }, 150);
    }

    if (subText && this.substatusEl) {
      this.substatusEl.textContent = subText;
    }
  }

  classifyTask(text) {
    if (!text) return "GENERAL";
    const t = text.toLowerCase().trim();
    if (t === "hi" || t === "hello" || t === "hey" || t.startsWith("hi ") || t.startsWith("hello ")) return "GREETING";
    if (t.includes("time") || t.includes("date") || t.includes("day is it") || t.includes("clock")) return "TIME";
    if (t.includes("chrome") || t.includes("browser") || t.includes("open ") || t.includes("launch ") || t.includes("app")) return "BROWSER";
    if (t.includes("search") || t.includes("google") || t.includes("youtube") || t.includes("find ") || t.includes("lookup")) return "WEB_SEARCH";
    if (t.includes("screen") || t.includes("screenshot") || t.includes("vision") || t.includes("look at") || t.includes("analyze my screen")) return "VISION";
    if (t.includes("file") || t.includes("folder") || t.includes("organize") || t.includes("directory") || t.includes("downloads")) return "FILES";
    if (t.includes("code") || t.includes("script") || t.includes("write ") || t.includes("develop") || t.includes("program") || t.includes("python")) return "CODE";
    if (t.includes("diagnostic") || t.includes("health") || t.includes("status") || t.includes("system") || t.includes("diagnose")) return "DIAGNOSTICS";
    return "GENERAL";
  }

  submitObjective(text) {
    console.log(`[PresenceApp] Submitting Objective: ${text}`);
    const taskType = this.classifyTask(text);
    this.engine.setState("THINKING", taskType, 0.0);
    this.engine.setTaskVisualization(taskType, text);
    this.engine.triggerEvent("MODEL_SELECTED", { task: text, model: "SERA-Fabric" });
    this.setStatus("ANALYZING OBJECTIVE", text.toUpperCase());

    // Transmit to Python backend via WebSocket if available
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "USER_INPUT",
        content: text,
        task_type: taskType,
        timestamp: Date.now() / 1000,
      }));
    } else {
      // Local adaptive fallback simulation if backend is not currently running
      setTimeout(() => {
        this.engine.setState("EXECUTING", taskType, 0.25);
        this.engine.triggerEvent("TOOL_STARTED", { tool_name: taskType });
        this.setStatus(`EXECUTING [${taskType}]`, text.toUpperCase());

        setTimeout(() => {
          this.engine.setState("EXECUTING", taskType, 0.75);
          this.engine.triggerEvent("PROGRESS_UPDATE", { progress: 0.75 });

          setTimeout(() => {
            this.engine.triggerEvent("TOOL_COMPLETED", { tool_name: taskType });
            this.engine.setState("COMPLETED", taskType, 1.0);
            this.setStatus("OBJECTIVE COMPLETE", "COMPUTATIONAL REGENERATION");

            setTimeout(() => {
              this.engine.setState("IDLE");
              this.setStatus("COGNITIVE EQUILIBRIUM", "AWAITING INTENT • CTRL+SPACE");
            }, 2600);
          }, 1400);
        }, 1400);
      }, 1400);
    }
  }

  connectBackendWebSocket() {
    const wsUrl = "ws://127.0.0.1:8765";
    console.log(`[PresenceApp] Connecting to SERA Runtime at ${wsUrl}...`);

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("[PresenceApp] Connected to SERA Python Runtime EventBus.");
        this.setStatus("COGNITIVE EQUILIBRIUM", "AWAITING INTENT • CTRL+SPACE");
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          this.handleBackendEvent(msg);
        } catch (e) {
          console.warn("[PresenceApp] Failed to parse backend event:", e);
        }
      };

      this.ws.onerror = () => {
        console.warn("[PresenceApp] WebSocket error (runtime may be offline, retrying...)");
      };

      this.ws.onclose = () => {
        console.log("[PresenceApp] Disconnected from SERA Runtime. Reconnecting in 3s...");
        setTimeout(() => this.connectBackendWebSocket(), 3000);
      };
    } catch (e) {
      console.warn("[PresenceApp] WebSocket init error:", e);
      setTimeout(() => this.connectBackendWebSocket(), 3000);
    }
  }

  handleBackendEvent(msg) {
    const { event, payload } = msg;
    if (!event) return;

    switch (event) {
      case "RUNTIME_STATE_CHANGED": {
        const status = payload?.status?.toUpperCase() || "IDLE";
        const taskText = payload?.task || "";
        const taskType = this.classifyTask(taskText);
        this.engine.setState(status, taskType);
        if (taskType !== "GENERAL") {
          this.engine.setTaskVisualization(taskType, taskText);
        }
        this.setStatus(status, payload?.task || "PROCESSING RUNTIME STATE");
        break;
      }
      case "ACTIVATION_STARTED":
      case "LISTENING_STARTED":
        this.engine.setState("LISTENING");
        this.setStatus("LISTENING TO AUDIO STREAM", "VOICE VAD ACTIVE");
        break;

      case "TRANSCRIPTION_STARTED":
        this.engine.setState("TRANSCRIBING");
        this.setStatus("TRANSCRIBING AUDIO", "EXTRACTING PHONEMIC TOKENS");
        break;

      case "MODEL_SELECTED":
        this.engine.triggerEvent("MODEL_SELECTED", payload);
        break;

      case "TASK_STARTED": {
        const taskText = payload?.task || "COMPUTING";
        const taskType = this.classifyTask(taskText);
        this.engine.setState("THINKING", taskType);
        this.engine.setTaskVisualization(taskType, taskText);
        this.engine.triggerEvent("MODEL_SELECTED", payload);
        this.setStatus("SYNTHESIZING COGNITIVE PATH", taskText.toUpperCase());
        break;
      }

      case "TOOL_STARTED": {
        const toolName = payload?.tool_name || "SYSTEM TOOL";
        const taskType = this.classifyTask(toolName);
        this.engine.setState("EXECUTING", taskType);
        this.engine.setTaskVisualization(taskType, toolName);
        this.engine.triggerEvent("TOOL_STARTED", payload);
        this.setStatus(`EXECUTING: ${toolName.toUpperCase()}`, "HARDWARE ACTIONS");
        break;
      }

      case "TOOL_COMPLETED":
        this.engine.triggerEvent("TOOL_COMPLETED", payload);
        break;

      case "FALLBACK":
        this.engine.triggerEvent("FALLBACK", payload);
        this.setStatus("ADAPTING ROUTE", "PROVIDER FALLBACK ENGAGED");
        break;

      case "PROGRESS_UPDATE":
        this.engine.triggerEvent("PROGRESS_UPDATE", payload);
        break;

      case "TTS_STARTED":
        this.engine.setState("SPEAKING");
        this.setStatus("SYNTHESIZING SPEECH", "F5-TTS STREAMING");
        break;

      case "TASK_COMPLETED":
        this.engine.setState("COMPLETED");
        this.engine.triggerEvent("TASK_COMPLETED", payload);
        this.setStatus("TASK ACCOMPLISHED", "COMPUTATIONAL REGENERATION");
        setTimeout(() => {
          this.engine.setState("IDLE");
          this.setStatus("COGNITIVE EQUILIBRIUM", "AWAITING INTENT • CTRL+SPACE");
        }, 2600);
        break;

      case "TASK_CANCELLED":
        this.engine.triggerEvent("TASK_CANCELLED", payload);
        this.setStatus("TASK CANCELLED", "RETRACTING STRUCTURES");
        break;

      case "TASK_FAILED":
        this.engine.setState("BROKEN");
        this.setStatus("ANOMALY DETECTED", payload?.error || "TASK FAILURE");
        break;
    }
  }

  startRenderLoop() {
    const loop = () => {
      this.engine.update();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }
}

// Bootstrap on DOM Ready
window.addEventListener("DOMContentLoaded", () => {
  window.seraApp = new PresenceApp();
});
