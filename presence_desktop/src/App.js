/**
 * SERA 2.0 — Desktop Presence Main Application Controller
 * Completely Voice-Driven Interaction Engine
 * 
 * Features:
 * - Pure voice interaction (Hold-To-Talk via Ctrl+Alt+Space & Wake Word)
 * - Real-time multi-band microphone audio driving the 3D core shaders
 * - Live STT partial captions streaming during speech
 * - Finalized command caption stays pinned and visible
 * - SERA response caption renders directly beneath the command
 * - Smooth animated conversation card expansion
 * 
 * Author: Keshava Pandi A S <keshavapandi@gmail.com>
 */

import { PresenceEngine } from "./engine/PresenceEngine.js";

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

class PresenceApp {
  constructor() {
    this.canvas = document.getElementById("presence-canvas");
    this.statusEl = document.getElementById("kinetic-status");
    this.substatusEl = document.getElementById("kinetic-substatus");

    // Voice Conversation Container Elements
    this.glassPanel = document.getElementById("glass-panel");
    this.bottomDrawer = document.getElementById("bottom-drawer");
    this.convContainer = document.getElementById("conversation-container");
    this.userBox = document.getElementById("user-caption-box");
    this.userTextEl = document.getElementById("user-caption-text");
    this.userStatusPill = document.getElementById("user-status-pill");
    this.seraBox = document.getElementById("sera-caption-box");
    this.seraTextEl = document.getElementById("sera-caption-text");
    this.seraStatusPill = document.getElementById("sera-status-pill");

    // Header Controls
    this.commandCenterBtn = document.getElementById("command-center-btn");
    this.minimizeBtn = document.getElementById("minimize-btn");
    this.closeBtn = document.getElementById("close-btn");

    this.engine = new PresenceEngine(this.canvas);
    this.ws = null;
    this._collapseTimer = null;

    this.setupWindowInteractions();
    this.setupUIControls();
    this.initAudioReactivity();
    this.connectBackendWebSocket();
    this.startRenderLoop();
  }

  /**
   * Real microphone stream using Web Audio API to continuously modulate the 3D presence core.
   */
  async initAudioReactivity() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.65;
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateAudio = () => {
        // While SERA speaks, output audio levels from backend have priority
        if (this.engine.state !== "SPEAKING") {
          analyser.getByteFrequencyData(dataArray);
          let sum = 0;
          let bassSum = 0, midSum = 0, trebleSum = 0;
          const count = dataArray.length;

          for (let i = 0; i < count; i++) {
            const v = dataArray[i];
            sum += v;
            if (i >= 1 && i <= 10) bassSum += v;
            else if (i > 10 && i <= 45) midSum += v;
            else if (i > 45 && i <= 90) trebleSum += v;
          }

          const avg = sum / count;
          // Noise-floor gating (< 3.0 out of 255 is ambient quiet room)
          if (avg < 3.0) {
            this.engine.setAudioData({ rawAmp: 0.0, bass: 0.0, mid: 0.0, treble: 0.0 });
          } else {
            // Dynamic AGC expansion with non-linear curve so vocal inflection visibly deforms the core
            const rawAmp = Math.min(1.0, Math.pow(avg / 42.0, 0.85));
            const bass = Math.min(1.0, Math.pow((bassSum / 10) / 45.0, 0.8));
            const mid = Math.min(1.0, Math.pow((midSum / 35) / 38.0, 0.85));
            const treble = Math.min(1.0, Math.pow((trebleSum / 45) / 30.0, 0.9));
            this.engine.setAudioData({ rawAmp, bass, mid, treble });
          }
        }
        requestAnimationFrame(updateAudio);
      };
      updateAudio();
      console.log("[PresenceApp] Live audio-reactive microphone input activated (multi-band).");
    } catch (err) {
      console.log("[PresenceApp] Microphone stream optional/unavailable:", err);
    }
  }

  setupWindowInteractions() {
    // Global Shortcut summon / toggle
    if (window.seraNative && window.seraNative.onGlobalActivate) {
      window.seraNative.onGlobalActivate(() => {
        this.expandConversation();
        this.setStatus("VOICE ACTIVE", "HOLD CTRL+ALT+SPACE TO SPEAK");
      });
    }

    // Canvas click expands/reveals voice status
    this.canvas.addEventListener("click", () => {
      if (this.convContainer.classList.contains("active")) {
        this.scheduleConversationCollapse(3000);
      } else {
        this.expandConversation();
        this.setStatus("VOICE READY", "HOLD CTRL+ALT+SPACE TO SPEAK");
        this.scheduleConversationCollapse(5000);
      }
    });
  }

  setupUIControls() {
    // Command Center external trigger
    if (this.commandCenterBtn) {
      this.commandCenterBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (window.seraNative) {
          window.seraNative.openCommandCenter();
        } else {
          window.open("http://127.0.0.1:8765", "_blank");
        }
      });
    }

    // Minimize trigger
    if (this.minimizeBtn) {
      this.minimizeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (window.seraNative) {
          window.seraNative.minimize();
        }
      });
    }

    // Close trigger
    if (this.closeBtn) {
      this.closeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (window.seraNative) {
          window.seraNative.close();
        } else {
          window.close();
        }
      });
    }
  }

  /* Conversation Container Controls */

  expandConversation() {
    if (this._collapseTimer) {
      clearTimeout(this._collapseTimer);
      this._collapseTimer = null;
    }
    if (this.convContainer) {
      this.convContainer.classList.add("active");
    }
    if (this.bottomDrawer) {
      this.bottomDrawer.classList.add("active");
    }
    if (this.glassPanel) {
      this.glassPanel.classList.add("conversation-active");
    }
  }

  collapseConversation() {
    if (this.convContainer) {
      this.convContainer.classList.remove("active");
    }
    if (this.bottomDrawer) {
      this.bottomDrawer.classList.remove("active");
    }
    if (this.glassPanel) {
      this.glassPanel.classList.remove("conversation-active");
    }
  }

  scheduleConversationCollapse(delayMs = 8000) {
    if (this._collapseTimer) {
      clearTimeout(this._collapseTimer);
    }
    this._collapseTimer = setTimeout(() => {
      if (this.engine.state === "IDLE") {
        this.collapseConversation();
      }
    }, delayMs);
  }

  resetConversationForNewUtterance() {
    this.expandConversation();
    if (this.seraBox) {
      this.seraBox.classList.add("hidden");
    }
    if (this.seraTextEl) {
      this.seraTextEl.textContent = "";
    }
    if (this.userTextEl) {
      this.userTextEl.className = "caption-text user-text partial";
      this.userTextEl.innerHTML = '<span class="caption-placeholder">Listening to voice...</span><span class="caption-cursor"></span>';
    }
    if (this.userStatusPill) {
      this.userStatusPill.className = "status-pill listening-pill";
      this.userStatusPill.textContent = "LISTENING";
    }
  }

  updateUserCaption(text, isFinal = false) {
    this.expandConversation();
    if (!this.userTextEl) return;

    if (isFinal) {
      this.userTextEl.className = "caption-text user-text finalized";
      this.userTextEl.textContent = text;
      if (this.userStatusPill) {
        this.userStatusPill.className = "status-pill confirmed-pill";
        this.userStatusPill.textContent = "COMMAND";
      }
    } else {
      this.userTextEl.className = "caption-text user-text partial";
      this.userTextEl.innerHTML = `${escapeHtml(text)}<span class="caption-cursor"></span>`;
      if (this.userStatusPill) {
        this.userStatusPill.className = "status-pill listening-pill";
        this.userStatusPill.textContent = "LISTENING";
      }
    }

    // Auto-scroll inside container
    if (this.convContainer) {
      this.convContainer.scrollTop = this.convContainer.scrollHeight;
    }
  }

  updateSeraResponse(text, statusLabel = "RESPONSE") {
    this.expandConversation();
    if (!this.seraBox || !this.seraTextEl) return;

    this.seraBox.classList.remove("hidden");
    this.seraTextEl.textContent = text;

    if (this.seraStatusPill) {
      this.seraStatusPill.className = "status-pill responding-pill";
      this.seraStatusPill.textContent = statusLabel;
    }

    if (this.convContainer) {
      this.convContainer.scrollTop = this.convContainer.scrollHeight;
    }
  }

  setStatus(mainText, subText = null) {
    if (this.statusEl) {
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

  connectBackendWebSocket() {
    const wsUrl = "ws://127.0.0.1:8765";
    console.log(`[PresenceApp] Connecting to SERA Runtime at ${wsUrl}...`);

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log("[PresenceApp] Connected to SERA Python Runtime EventBus.");
        this.setStatus("VOICE READY", "HOLD CTRL+ALT+SPACE TO SPEAK");
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
    const { event } = msg;
    const payload = msg.payload || msg.data || {};
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
        if (status === "IDLE") {
          this.setStatus("VOICE READY", "HOLD CTRL+ALT+SPACE TO SPEAK");
        } else {
          this.setStatus(status, payload?.task || "PROCESSING RUNTIME STATE");
        }
        break;
      }

      case "ACTIVATION_STARTED":
        if (window.seraNative && window.seraNative.showAndFocus) {
          window.seraNative.showAndFocus();
        }
        if (this.engine.state !== "LISTENING") {
          this.engine.setState("LISTENING");
          this.setStatus("LISTENING TO AUDIO STREAM", "HOLD CTRL+ALT+SPACE • RELEASE TO EXECUTE");
          this.resetConversationForNewUtterance();
        }
        break;

      case "LISTENING_STARTED":
        if (this.engine.state !== "LISTENING") {
          this.engine.setState("LISTENING");
          this.setStatus("LISTENING TO AUDIO STREAM", "HOLD CTRL+ALT+SPACE • RELEASE TO EXECUTE");
          this.resetConversationForNewUtterance();
        }
        break;

      case "PARTIAL_TRANSCRIPTION": {
        const partialText = payload.partial || payload.transcript || "";
        if (partialText) {
          this.updateUserCaption(partialText, false);
          this.setStatus("CAPTURING SPEECH", partialText.toUpperCase());
        }
        break;
      }

      case "TRANSCRIPTION_STARTED":
        this.engine.setState("TRANSCRIBING");
        this.setStatus("TRANSCRIBING AUDIO", "EXTRACTING PHONEMIC TOKENS");
        break;

      case "TRANSCRIPTION_COMPLETED": {
        const finalText = payload.transcript || "";
        if (finalText) {
          this.updateUserCaption(finalText, true);
          const taskType = this.classifyTask(finalText);
          this.engine.setState("THINKING", taskType);
          this.engine.setTaskVisualization(taskType, finalText);
          this.setStatus("ANALYZING OBJECTIVE", finalText.toUpperCase());
        }
        break;
      }

      case "MODEL_SELECTED":
        this.engine.triggerEvent("MODEL_SELECTED", payload);
        break;

      case "TASK_STARTED": {
        const taskText = payload?.user_input || payload?.task || "COMPUTING";
        const taskType = this.classifyTask(taskText);
        this.engine.setState("THINKING", taskType);
        this.engine.setTaskVisualization(taskType, taskText);
        this.setStatus("SYNTHESIZING PATH", taskText.toUpperCase());
        this.updateSeraResponse("Synthesizing neural execution plan...", "PLANNING");
        break;
      }

      case "TOOL_STARTED": {
        const toolName = payload?.tool_name || "SYSTEM TOOL";
        const taskType = this.classifyTask(toolName);
        this.engine.setState("EXECUTING", taskType);
        this.engine.setTaskVisualization(taskType, toolName);
        this.engine.triggerEvent("TOOL_STARTED", payload);
        this.setStatus(`EXECUTING: ${toolName.toUpperCase()}`, "HARDWARE ACTIONS");
        this.updateSeraResponse(`Executing: ${toolName}...`, "EXECUTING");
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

      case "AGENT_RESPONSE": {
        const responseText = payload.content || payload.text || payload.response || "";
        if (responseText) {
          this.updateSeraResponse(responseText, "RESPONSE");
          this.setStatus("SERA RESPONSE", "COGNITIVE CONVERSATION");
        }
        break;
      }

      case "TTS_STARTED":
        this.engine.setState("SPEAKING");
        this.setStatus("SERA SPEAKING", "STREAMING VOICE AUDIO");
        if (this.seraStatusPill) {
          this.seraStatusPill.textContent = "SPEAKING";
        }
        break;

      case "TTS_AUDIO_LEVELS": {
        if (payload && this.engine) {
          this.engine.setAudioData({
            rawAmp: payload.rawAmp || 0.0,
            bass: payload.bass || 0.0,
            mid: payload.mid || 0.0,
            treble: payload.treble || 0.0,
          });
        }
        break;
      }

      case "TTS_COMPLETED":
        if (this.seraStatusPill) {
          this.seraStatusPill.textContent = "COMPLETE";
        }
        break;

      case "PRESENCE_CLOSE":
        console.log("[PresenceApp] Native self-close requested by SERA Runtime.");
        this.setStatus("CLOSING PRESENCE", "SHUTDOWN VERIFIED");
        if (window.seraNative && window.seraNative.selfClose) {
          window.seraNative.selfClose();
        } else {
          window.close();
        }
        break;

      case "TASK_COMPLETED": {
        this.engine.setState("COMPLETED");
        this.engine.triggerEvent("TASK_COMPLETED", payload);
        const resultText = payload.result;
        if (resultText && !this.seraTextEl.textContent) {
          this.updateSeraResponse(resultText, "COMPLETE");
        } else if (this.seraStatusPill) {
          this.seraStatusPill.textContent = "COMPLETE";
        }
        this.setStatus("OBJECTIVE COMPLETE", "COMPUTATIONAL REGENERATION");
        setTimeout(() => {
          this.engine.setState("IDLE");
          this.setStatus("VOICE READY", "HOLD CTRL+ALT+SPACE TO SPEAK");
        }, 2200);
        this.scheduleConversationCollapse(8000);
        break;
      }

      case "TASK_CANCELLED":
        this.engine.triggerEvent("TASK_CANCELLED", payload);
        this.setStatus("TASK CANCELLED", "RETRACTING STRUCTURES");
        this.updateSeraResponse("Task execution cancelled.", "CANCELLED");
        this.scheduleConversationCollapse(6000);
        break;

      case "TASK_FAILED":
        this.engine.setState("BROKEN");
        this.setStatus("ANOMALY DETECTED", payload?.error || "TASK FAILURE");
        this.updateSeraResponse(payload?.error || "Execution anomaly encountered.", "ERROR");
        this.scheduleConversationCollapse(8000);
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
