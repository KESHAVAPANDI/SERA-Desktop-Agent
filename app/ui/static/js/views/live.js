/**
 * LiveView — SERA Human-Facing Conversational Operating Surface
 * Phase 5D.5: Embedded Temporal Execution Theater, Guaranteed Assistant Response Contract,
 * Streaming Token Settlement, Adaptive Model Reason Inspection & Context-Aware Task Minimization
 */

export class LiveView {
  constructor(socketSender, switchViewCallback) {
    this.send = socketSender;
    this.switchView = switchViewCallback || (() => {});

    // DOM Elements
    this.chatStream = document.getElementById("chat-stream");
    this.chatForm = document.getElementById("chat-form");
    this.chatInput = document.getElementById("chat-input");
    this.scrollAnchorBtn = document.getElementById("scroll-anchor-btn");

    // Aura & Voice Elements
    this.auraOrb = document.getElementById("aura-orb-main");
    this.auraStatusText = document.getElementById("aura-status-subtext");
    this.captureContainer = document.getElementById("capture-progress-container");
    this.captureTimerVal = document.getElementById("capture-timer-val");
    this.captureProgressFill = document.getElementById("capture-progress-fill");
    this.activationMethodLabel = document.getElementById("activation-method-label");
    this.audioBars = document.getElementById("audio-spectrum-bars");

    // Authoritative Task Card Elements
    this.currentTaskCard = document.getElementById("current-task-card");
    this.taskTitle = document.getElementById("task-card-title");
    this.taskStepFill = document.getElementById("task-step-fill");
    this.taskStepLabel = document.getElementById("task-step-label");
    this.taskElapsedTimer = document.getElementById("task-elapsed-timer");
    this.btnInterrupt = document.getElementById("btn-interrupt-task");

    // Task In Progress Minimization Overlay Elements
    this.taskOverlay = document.getElementById("live-task-overlay");
    this.taskOverlayTitle = document.getElementById("task-overlay-title");
    this.taskOverlayStep = document.getElementById("task-overlay-step");
    this.taskOverlayTimer = document.getElementById("task-overlay-timer");
    this.btnOverlayExpand = document.getElementById("btn-overlay-expand");
    this.btnOverlayStop = document.getElementById("btn-overlay-stop");
    this.btnOverlayWorkflow = document.getElementById("btn-overlay-workflow");
    this.isChatMinimized = false;

    // Embedded Live Temporal Execution Theater Elements
    this.embeddedTheater = document.getElementById("live-embedded-theater");
    this.embeddedTheaterNodes = document.getElementById("live-theater-nodes");
    this.embeddedTheaterSvg = document.getElementById("live-theater-svg");
    this.embeddedStepText = document.getElementById("live-theater-step-text");
    this.currentModelBadge = document.getElementById("live-current-model-badge");
    this.modelNameText = document.getElementById("live-model-name-text");
    this.btnTheaterExpand = document.getElementById("btn-theater-expand-chat");
    this.btnTheaterStop = document.getElementById("btn-theater-stop");
    this.btnTheaterWorkflow = document.getElementById("btn-theater-open-workflow");

    // Why This Model Modal Elements
    this.whyModelModal = document.getElementById("why-model-modal");
    this.whyModelRole = document.getElementById("why-role-label");
    this.whyModelName = document.getElementById("why-model-name");
    this.whyModelScore = document.getElementById("why-score-pill");
    this.whyReasonsContainer = document.getElementById("why-reasons-container");
    this.btnWhyClose = document.getElementById("btn-why-model-close");

    // Data-Driven Contextual Capabilities Grid
    this.capabilitiesGrid = document.getElementById("quick-chips-grid");

    // Internal State
    this.activeTaskId = null;
    this.currentTurnId = null;
    this.startedAt = 0;
    this.runtimeState = "IDLE";
    this.activeStreamBubble = null;
    this.activeWorkCards = new Map(); // call_id / tool_name -> DOM Element
    this.embeddedNodes = new Map(); // node_id -> { el, status }
    this.shouldAutoScroll = true;

    // Timers
    this.taskTimerInterval = null;
    this.captureTimerInterval = null;
    this.holdTimerInterval = null;
    this.holdSeconds = 0.0;

    this.init();
  }

  init() {
    // 1. Chat Form Submit
    this.chatForm?.addEventListener("submit", e => {
      e.preventDefault();
      const text = this.chatInput.value.trim();
      if (!text) return;
      this.appendUserMessage(text, "TEXT");
      this.chatInput.value = "";
      this.send({ action: "USER_PROMPT", text: text });
    });

    // 2. Context-Aware Interrupt Button
    this.btnInterrupt?.addEventListener("click", () => this.handleInterruptClick());

    // 2b. Task Overlay & Theater Action Buttons
    this.btnOverlayStop?.addEventListener("click", () => this.handleInterruptClick());
    this.btnTheaterStop?.addEventListener("click", () => this.handleInterruptClick());

    this.btnOverlayWorkflow?.addEventListener("click", () => this.switchView("workflow"));
    this.btnTheaterWorkflow?.addEventListener("click", () => this.switchView("workflow"));

    const toggleChatMinimize = () => {
      this.isChatMinimized = !this.isChatMinimized;
      this.chatStream?.classList.toggle("chat-compact-mode", this.isChatMinimized);
      const label = this.isChatMinimized ? "Expand Chat" : "Compact Mode";
      if (this.btnOverlayExpand) this.btnOverlayExpand.textContent = label;
      if (this.btnTheaterExpand) this.btnTheaterExpand.textContent = label;
    };

    this.btnOverlayExpand?.addEventListener("click", toggleChatMinimize);
    this.btnTheaterExpand?.addEventListener("click", toggleChatMinimize);

    // 2c. Why This Model Modal Trigger & Close
    this.currentModelBadge?.addEventListener("click", () => this.openWhyModelModal());
    this.btnWhyClose?.addEventListener("click", () => this.closeWhyModelModal());
    this.whyModelModal?.addEventListener("click", e => {
      if (e.target === this.whyModelModal) this.closeWhyModelModal();
    });

    // 3. Scroll Anchoring
    this.chatStream?.addEventListener("scroll", () => {
      if (!this.chatStream) return;
      const distanceFromBottom = this.chatStream.scrollHeight - this.chatStream.scrollTop - this.chatStream.clientHeight;
      this.shouldAutoScroll = distanceFromBottom < 60;
      if (this.scrollAnchorBtn) {
        this.scrollAnchorBtn.classList.toggle("hidden", this.shouldAutoScroll);
      }
    });

    this.scrollAnchorBtn?.addEventListener("click", () => {
      this.scrollToBottom(true);
    });

    // 4. Click Aura Orb to Focus
    this.auraOrb?.addEventListener("click", () => {
      this.chatInput?.focus();
    });

    // 5. Setup static chip click handlers
    this.setupStaticChips();

    // 6. Initial Contextual Capabilities Query
    this.fetchCapabilities("IDLE");
    this.updateInterruptButton("IDLE");
  }

  setupStaticChips() {
    this.capabilitiesGrid?.querySelectorAll(".quick-chip-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const prompt = btn.getAttribute("data-prompt") || btn.textContent.trim();
        if (prompt) {
          this.appendUserMessage(prompt, "TEXT");
          this.send({ action: "USER_PROMPT", text: prompt });
        }
      });
    });
  }

  /* ===================================================================
     1. CONVERSATION STREAM & GUARANTEED RESPONSE CONTRACT
     =================================================================== */

  appendUserMessage(text, source = "TEXT") {
    if (!this.chatStream) return;
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble user";
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const sourceTag = source === "HOTKEY_HOLD" || source === "VOICE" || source === "WAKE_WORD"
      ? '<span class="user-source-tag">🎙 VOICE</span>'
      : '<span class="user-source-tag">⌨ TEXT</span>';

    bubble.innerHTML = `
      <div class="bubble-sender" style="justify-content: flex-end;">
        <span class="bubble-time">${timeStr}</span>
        ${sourceTag}
      </div>
      <div class="bubble-content">${this.escapeHtml(text)}</div>
    `;

    this.chatStream.appendChild(bubble);
    this.scrollToBottom();
  }

  startAssistantStreaming(turnId = null) {
    if (!this.chatStream) return;
    if (this.activeStreamBubble) {
      this.completeAssistantResponse();
    }

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble sera streaming-active";
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    bubble.innerHTML = `
      <div class="bubble-sender">
        <span class="sender-badge">SERA</span>
        <span class="bubble-time">${timeStr}</span>
      </div>
      <div class="bubble-content"><span class="stream-text"></span><span class="streaming-caret"></span></div>
    `;

    this.chatStream.appendChild(bubble);
    this.activeStreamBubble = bubble;
    this.scrollToBottom();
  }

  appendStreamToken(token) {
    if (!this.activeStreamBubble) {
      this.startAssistantStreaming();
    }
    const textSpan = this.activeStreamBubble?.querySelector(".stream-text");
    if (textSpan) {
      textSpan.textContent += token;
      this.scrollToBottom();
    }
  }

  completeAssistantResponse(finalText = null) {
    if (!this.activeStreamBubble) {
      if (finalText) this.appendStaticAssistantMessage(finalText);
      return;
    }

    const textSpan = this.activeStreamBubble.querySelector(".stream-text");
    if (finalText && textSpan) {
      textSpan.innerHTML = this.formatMarkdown(finalText);
    }

    const caret = this.activeStreamBubble.querySelector(".streaming-caret");
    if (caret) caret.remove();

    this.activeStreamBubble.classList.remove("streaming-active");
    this.activeStreamBubble = null;
    this.scrollToBottom();
  }

  appendStaticAssistantMessage(text) {
    if (!this.chatStream || !text) return;
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble sera";
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    bubble.innerHTML = `
      <div class="bubble-sender">
        <span class="sender-badge">SERA</span>
        <span class="bubble-time">${timeStr}</span>
      </div>
      <div class="bubble-content">${this.formatMarkdown(text)}</div>
    `;

    this.chatStream.appendChild(bubble);
    this.scrollToBottom();
  }

  /* ===================================================================
     2. INLINE WORK CARDS & ARTIFACTS
     =================================================================== */

  createInlineWorkCard(toolName, args = {}, callId = null) {
    if (!this.chatStream) return null;
    const cardId = callId || `work_${toolName}_${Date.now()}`;
    const card = document.createElement("div");
    card.id = cardId;
    card.className = "inline-work-card status-running";

    const toolMeta = this.getToolMetadata(toolName);
    const argsSummary = this.summarizeArgs(toolName, args);

    card.innerHTML = `
      <div class="work-card-header">
        <div class="work-header-left">
          <span class="work-icon">${toolMeta.icon}</span>
          <span class="work-title">${toolMeta.label.toUpperCase()}</span>
        </div>
        <div class="work-header-right">
          <span class="work-status-badge badge-running">● RUNNING</span>
          <button class="work-toggle-btn" title="Toggle Details">▾</button>
        </div>
      </div>
      <div class="work-card-summary">${argsSummary}</div>
      <div class="work-card-details hidden">
        <div class="work-detail-row"><strong>Tool:</strong> <code>${toolName}</code></div>
        <div class="work-detail-row"><strong>Parameters:</strong> <code>${JSON.stringify(args)}</code></div>
        <div class="work-actions-row">
          <button class="work-workflow-btn" data-task="${this.activeTaskId || ''}">
            <span>View in Workflow</span> <span>➔</span>
          </button>
        </div>
      </div>
      <div class="artifact-container"></div>
    `;

    // Collapsible toggle
    const toggleBtn = card.querySelector(".work-toggle-btn");
    const details = card.querySelector(".work-card-details");
    toggleBtn?.addEventListener("click", () => {
      const isHidden = details?.classList.toggle("hidden");
      toggleBtn.classList.toggle("expanded", !isHidden);
    });

    // Workflow jump button
    const workflowBtn = card.querySelector(".work-workflow-btn");
    workflowBtn?.addEventListener("click", () => {
      this.switchView("workflow");
    });

    this.chatStream.appendChild(card);
    this.activeWorkCards.set(cardId, card);
    this.activeWorkCards.set(toolName, card);
    this.scrollToBottom();
    return card;
  }

  completeInlineWorkCard(toolName, result = {}, latencyMs = 0, callId = null) {
    const card = this.activeWorkCards.get(callId) || this.activeWorkCards.get(toolName);
    if (!card) return;

    card.className = "inline-work-card status-completed";
    const statusBadge = card.querySelector(".work-status-badge");
    if (statusBadge) {
      statusBadge.className = "work-status-badge badge-completed";
      statusBadge.textContent = `✓ COMPLETED (${latencyMs}ms)`;
    }

    const artifactContainer = card.querySelector(".artifact-container");
    if (artifactContainer) {
      this.renderArtifacts(toolName, result, artifactContainer);
    }

    this.scrollToBottom();
  }

  failInlineWorkCard(toolName, error = "Operation failed", callId = null) {
    const card = this.activeWorkCards.get(callId) || this.activeWorkCards.get(toolName);
    if (!card) return;

    card.className = "inline-work-card status-failed";
    const statusBadge = card.querySelector(".work-status-badge");
    if (statusBadge) {
      statusBadge.className = "work-status-badge badge-broken";
      statusBadge.textContent = "✕ FAILED";
    }

    const summary = card.querySelector(".work-card-summary");
    if (summary) {
      summary.innerHTML = `<span style="color: var(--accent-broken);">${this.escapeHtml(error)}</span>`;
    }

    this.scrollToBottom();
  }

  renderArtifacts(toolName, result, container) {
    if (!result || typeof result !== "object") return;

    // 1. Web Search Results Artifact
    if (toolName === "web_search" || result.results || result.sources) {
      const results = result.results || [];
      if (results.length > 0) {
        const grid = document.createElement("div");
        grid.className = "artifact-web-grid";
        results.slice(0, 3).forEach((item, idx) => {
          const el = document.createElement("div");
          el.className = "web-result-item";
          el.innerHTML = `
            <div class="web-result-top">
              <a href="${item.url || '#'}" target="_blank" class="web-result-title">${this.escapeHtml(item.title || `Source ${idx+1}`)}</a>
              <span class="web-result-source">${this.escapeHtml(item.domain || item.source || 'Web')}</span>
            </div>
            <div class="web-result-snippet">${this.escapeHtml(item.snippet || item.text || '')}</div>
          `;
          grid.appendChild(el);
        });
        container.appendChild(grid);
      }

      // Sources Citation Pills
      if (result.sources && result.sources.length > 0) {
        const sourcesRow = document.createElement("div");
        sourcesRow.className = "artifact-sources-row";
        result.sources.forEach((src, idx) => {
          const pill = document.createElement("span");
          pill.className = "source-citation-pill";
          pill.innerHTML = `<span class="source-num">[${idx + 1}]</span> <span>${this.escapeHtml(src)}</span>`;
          sourcesRow.appendChild(pill);
        });
        container.appendChild(sourcesRow);
      }
    }

    // 2. Screen Capture Artifact
    if (toolName === "capture_screen" || toolName === "screen_reading") {
      const box = document.createElement("div");
      box.className = "artifact-screenshot-box";
      const resolution = result.resolution || (result.width && result.height ? `${result.width}×${result.height}` : "1920×1080");

      box.innerHTML = `
        <div class="screenshot-thumb-wrapper">
          <div style="display:flex; align-items:center; justify-content:center; height:100%; color:var(--text-muted); background:radial-gradient(circle, rgba(0,240,255,0.1) 0%, #050810 80%);">
            <span style="font-size:2rem;">🖥️</span>
          </div>
          <span class="screenshot-meta-badge">CAPTURED • ${resolution}</span>
        </div>
      `;
      container.appendChild(box);
    }

    // 3. File Listing Artifact
    if (toolName === "list_folder_contents" || toolName === "read_file") {
      const files = result.files || (Array.isArray(result) ? result : []);
      if (files.length > 0) {
        const list = document.createElement("div");
        list.style.display = "flex";
        list.style.flexDirection = "column";
        list.style.gap = "6px";
        list.style.marginTop = "4px";

        files.slice(0, 4).forEach(f => {
          const item = document.createElement("div");
          item.className = "artifact-file-item";
          const fName = typeof f === "string" ? f : (f.name || f.path || "file");
          const fSize = f.size ? `${(f.size / 1024).toFixed(1)} KB` : "FILE";
          item.innerHTML = `
            <div class="file-info-left">
              <span>📄</span>
              <span class="file-name">${this.escapeHtml(fName)}</span>
            </div>
            <span class="file-meta-tag">${fSize}</span>
          `;
          list.appendChild(item);
        });
        container.appendChild(list);
      }
    }
  }

  appendSystemNotice(type, text) {
    if (!this.chatStream) return;
    const notice = document.createElement("div");
    notice.className = `system-notice-card ${type === "cancelled" ? "system-notice-cancelled" : "system-notice-init"}`;
    notice.textContent = text;
    this.chatStream.appendChild(notice);
    this.scrollToBottom();
  }

  /* ===================================================================
     3. EMBEDDED LIVE TEMPORAL THEATER & NODE MATERIALIZATION
     =================================================================== */

  addMiniNode(id, label, sub, status = "active") {
    if (!this.embeddedTheaterNodes) return;
    if (this.embeddedNodes.has(id)) {
      this.updateMiniNode(id, status);
      return;
    }

    const nodeEl = document.createElement("div");
    nodeEl.id = `mini_${id}`;
    nodeEl.className = `mini-node ${status}`;
    nodeEl.innerHTML = `
      <span class="mini-node-title">${this.escapeHtml(label)}</span>
      <span class="mini-node-sub">${this.escapeHtml(sub || '')}</span>
    `;

    this.embeddedTheaterNodes.appendChild(nodeEl);
    this.embeddedNodes.set(id, { el: nodeEl, status });
    this.renderMiniPlasmaEdges();
  }

  updateMiniNode(id, status) {
    const nodeObj = this.embeddedNodes.get(id);
    if (!nodeObj || !nodeObj.el) return;
    nodeObj.status = status;
    nodeObj.el.className = `mini-node ${status}`;
    this.renderMiniPlasmaEdges();
  }

  renderMiniPlasmaEdges() {
    if (!this.embeddedTheaterSvg || !this.embeddedTheaterNodes) return;
    this.embeddedTheaterSvg.innerHTML = "";

    const nodesArr = Array.from(this.embeddedNodes.keys());
    for (let i = 0; i < nodesArr.length - 1; i++) {
      const fromEl = document.getElementById(`mini_${nodesArr[i]}`);
      const toEl = document.getElementById(`mini_${nodesArr[i+1]}`);
      if (!fromEl || !toEl) continue;

      const fx = fromEl.offsetLeft + fromEl.offsetWidth;
      const fy = fromEl.offsetTop + fromEl.offsetHeight / 2;
      const tx = toEl.offsetLeft;
      const ty = toEl.offsetTop + toEl.offsetHeight / 2;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const dx = (tx - fx) * 0.5;
      const d = `M ${fx} ${fy} C ${fx + dx} ${fy}, ${tx - dx} ${ty}, ${tx} ${ty}`;
      path.setAttribute("d", d);
      path.setAttribute("class", "plasma-edge-channel");
      path.setAttribute("stroke", "var(--accent-cyan)");
      path.setAttribute("stroke-width", "2");
      path.setAttribute("fill", "none");
      path.setAttribute("filter", "drop-shadow(0 0 6px var(--accent-cyan))");
      this.embeddedTheaterSvg.appendChild(path);
    }
  }

  async openWhyModelModal(role = "reasoning") {
    if (!this.whyModelModal) return;
    try {
      const res = await fetch(`/api/router/why-model?role=${encodeURIComponent(role)}`);
      if (res.ok) {
        const data = await res.json();
        const expl = data.explanation || {};
        if (this.whyModelRole) this.whyModelRole.textContent = `Role: ${(expl.role || role).toUpperCase()}`;
        if (this.whyModelName) this.whyModelName.textContent = expl.selected_model || "Mistral Large";
        if (this.whyModelScore) this.whyModelScore.textContent = `Adaptive Score: ${expl.selected_score || 285.0} • Preflight Verified`;

        if (this.whyReasonsContainer && expl.reasons) {
          this.whyReasonsContainer.innerHTML = "";
          expl.reasons.forEach(r => {
            const rEl = document.createElement("div");
            rEl.className = "why-reason-item";
            rEl.textContent = r;
            this.whyReasonsContainer.appendChild(rEl);
          });
        }
      }
    } catch (e) {
      console.debug("Failed to fetch why-model info:", e);
    }
    this.whyModelModal.classList.remove("hidden");
  }

  closeWhyModelModal() {
    this.whyModelModal?.classList.add("hidden");
  }

  /* ===================================================================
     4. CONTEXT-AWARE INTERRUPT & CAPABILITIES
     =================================================================== */

  updateInterruptButton(state) {
    this.runtimeState = state;
    if (!this.btnInterrupt) return;

    this.btnInterrupt.className = "btn-interrupt";

    switch (state) {
      case "LISTENING":
        this.btnInterrupt.classList.add("btn-interrupt-listening");
        this.btnInterrupt.innerHTML = `<span>■</span> Cancel Capture`;
        this.btnInterrupt.disabled = false;
        break;
      case "THINKING":
        this.btnInterrupt.classList.add("btn-interrupt-thinking");
        this.btnInterrupt.innerHTML = `<span>■</span> Interrupt`;
        this.btnInterrupt.disabled = false;
        break;
      case "EXECUTING":
        this.btnInterrupt.classList.add("btn-interrupt-executing");
        this.btnInterrupt.innerHTML = `<span>■</span> Stop Task`;
        this.btnInterrupt.disabled = false;
        break;
      case "SPEAKING":
        this.btnInterrupt.classList.add("btn-interrupt-speaking");
        this.btnInterrupt.innerHTML = `<span>■</span> Stop Speaking`;
        this.btnInterrupt.disabled = false;
        break;
      default: // IDLE, BROKEN, CANCELLED
        this.btnInterrupt.classList.add("btn-interrupt-idle");
        this.btnInterrupt.innerHTML = `Interrupt`;
        this.btnInterrupt.disabled = true;
        break;
    }
  }

  async handleInterruptClick() {
    if (!this.btnInterrupt || this.runtimeState === "IDLE") return;

    this.btnInterrupt.className = "btn-interrupt btn-interrupt-cancelling";
    this.btnInterrupt.innerHTML = `<span>⏳</span> Cancelling...`;
    this.send({ action: "INTERRUPT" });

    try {
      await fetch("/api/task/cancel", { method: "POST" });
    } catch (e) {
      console.warn("Task cancellation API error:", e);
    }
  }

  async fetchCapabilities(contextState = "IDLE") {
    try {
      const res = await fetch(`/api/capabilities?context=${encodeURIComponent(contextState)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.capabilities) {
          this.renderCapabilities(data.capabilities);
        }
      }
    } catch (e) {
      console.debug("Failed to fetch capabilities:", e);
    }
  }

  renderCapabilities(capabilities = []) {
    if (!this.capabilitiesGrid) return;
    this.capabilitiesGrid.innerHTML = "";

    capabilities.forEach(cap => {
      const btn = document.createElement("button");
      btn.className = "quick-chip-btn";
      btn.setAttribute("data-prompt", cap.prompt_template || cap.label);
      btn.innerHTML = `<span class="chip-icon">${cap.icon || '⚡'}</span> ${this.escapeHtml(cap.label)}`;

      btn.addEventListener("click", () => {
        const prompt = btn.getAttribute("data-prompt");
        if (prompt) {
          this.appendUserMessage(prompt, "TEXT");
          this.send({ action: "USER_PROMPT", text: prompt });
        }
      });

      this.capabilitiesGrid.appendChild(btn);
    });
  }

  /* ===================================================================
     5. AURA & TASK CARD SYNCHRONIZATION
     =================================================================== */

  setAuraState(status, meta = {}) {
    this.runtimeState = status;
    this.updateInterruptButton(status);
    this.fetchCapabilities(status);

    if (this.auraStatusText) {
      this.auraStatusText.textContent = status.toUpperCase();
    }

    if (this.auraOrb) {
      this.auraOrb.className = `aura-orb-main state-${status.toLowerCase()}`;
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
  }

  startHoldToTalkVisualizer() {
    if (!this.captureContainer || !this.captureTimerVal || !this.captureProgressFill) return;
    this.captureContainer.classList.remove("hidden");
    if (this.activationMethodLabel) {
      this.activationMethodLabel.innerHTML = `<strong>HOLD TO TALK</strong> (Release Ctrl+Space to Send)`;
    }

    this.holdSeconds = 0.0;
    this.captureProgressFill.style.width = "100%";
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

  startTask(data) {
    const taskName = typeof data === "string" ? data : (data.user_input || data.task || "Executing Task");
    this.activeTaskId = (typeof data === "object" && data.task_id) ? data.task_id : `task_${Date.now()}`;
    const startedAtSec = (typeof data === "object" && data.started_at) ? data.started_at : (Date.now() / 1000);
    this.startedAt = startedAtSec * 1000;

    if (this.taskTitle) this.taskTitle.textContent = taskName;
    if (this.taskStepLabel) this.taskStepLabel.textContent = `Step 1 / 4: Intent & Routing`;
    if (this.taskStepFill) {
      this.taskStepFill.style.width = "25%";
      this.taskStepFill.style.background = "var(--accent-cyan)";
    }

    // Update Compact Task Overlay
    if (this.taskOverlay) this.taskOverlay.classList.remove("hidden");
    if (this.taskOverlayTitle) this.taskOverlayTitle.textContent = taskName;
    if (this.taskOverlayStep) this.taskOverlayStep.textContent = "CURRENT STEP: Initializing task routing...";

    // Activate Embedded Live Temporal Theater
    if (this.embeddedTheater) {
      this.embeddedTheater.classList.remove("hidden");
      if (this.embeddedTheaterNodes) this.embeddedTheaterNodes.innerHTML = "";
      if (this.embeddedTheaterSvg) this.embeddedTheaterSvg.innerHTML = "";
      this.embeddedNodes.clear();
      this.addMiniNode("stt", "SPEECH INPUT", "Canary-Qwen 2.5B", "completed");
    }

    this.updateInterruptButton("EXECUTING");
    
    clearInterval(this.taskTimerInterval);
    this.taskTimerInterval = setInterval(() => {
      const elapsed = ((Date.now() - this.startedAt) / 1000).toFixed(1);
      if (this.taskElapsedTimer) {
        this.taskElapsedTimer.textContent = `${elapsed}s`;
      }
      if (this.taskOverlayTimer) {
        this.taskOverlayTimer.textContent = `${elapsed}s`;
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
    if (this.taskOverlayStep && actionDescription) {
      this.taskOverlayStep.textContent = `CURRENT STEP: ${actionDescription}`;
    }
    if (this.embeddedStepText && actionDescription) {
      this.embeddedStepText.textContent = actionDescription;
    }
  }

  stopTask(reason = "✓ Completed", data = {}) {
    clearInterval(this.taskTimerInterval);
    const completedTaskId = this.activeTaskId;
    this.activeTaskId = null;

    if (this.taskStepLabel) this.taskStepLabel.textContent = reason;
    if (this.taskStepFill) {
      this.taskStepFill.style.width = "100%";
      this.taskStepFill.style.background = reason.includes("Cancelled") || reason.includes("Failed") ? "var(--accent-broken)" : "var(--accent-emerald)";
    }

    if (data.duration_seconds && this.taskElapsedTimer) {
      this.taskElapsedTimer.textContent = `${data.duration_seconds.toFixed(1)}s`;
    }

    if (this.taskOverlayStep) {
      this.taskOverlayStep.textContent = reason;
    }

    if (this.embeddedStepText) {
      this.embeddedStepText.textContent = reason;
    }

    this.updateInterruptButton("IDLE");

    if (reason.includes("Cancelled")) {
      this.appendSystemNotice("cancelled", "✕ Task cancelled by user");
      // Mark any active work cards as cancelled
      this.activeWorkCards.forEach(card => {
        if (card.classList.contains("status-running")) {
          card.className = "inline-work-card status-cancelled";
          const b = card.querySelector(".work-status-badge");
          if (b) {
            b.className = "work-status-badge badge-cancelled";
            b.textContent = "CANCELLED";
          }
        }
      });
      this.embeddedNodes.forEach((nodeObj, id) => {
        this.updateMiniNode(id, "broken");
      });
    } else {
      this.embeddedNodes.forEach((nodeObj, id) => {
        this.updateMiniNode(id, "completed");
      });
    }

    // Ensure any streaming bubble settles into completed state
    if (this.activeStreamBubble) {
      this.completeAssistantResponse(data.result || null);
    } else if (data.result && typeof data.result === "string" && data.result.trim()) {
      this.appendStaticAssistantMessage(data.result);
    }

    setTimeout(() => {
      if (!this.activeTaskId) {
        if (this.taskTitle) this.taskTitle.textContent = "Awaiting User Instruction";
        if (this.taskStepLabel) this.taskStepLabel.textContent = "Step 0 / 0";
        if (this.taskStepFill) this.taskStepFill.style.width = "0%";
        if (this.taskElapsedTimer) this.taskElapsedTimer.textContent = "0.0s";
        if (this.taskOverlay) this.taskOverlay.classList.add("hidden");
        if (this.embeddedTheater) this.embeddedTheater.classList.add("hidden");
      }
    }, 4000);
  }

  /* ===================================================================
     6. UNIFIED RUNTIME EVENT HANDLER
     =================================================================== */

  handleRuntimeEvent(eventName, data = {}) {
    switch (eventName) {
      case "CAPABILITIES_LIST":
        if (data.capabilities) this.renderCapabilities(data.capabilities);
        break;

      case "ACTIVATION_STARTED":
      case "LISTENING_STARTED":
        this.setAuraState("LISTENING", data);
        break;

      case "TRANSCRIPTION_STARTED":
        this.setAuraState("TRANSCRIBING", data);
        break;

      case "TRANSCRIPTION_COMPLETED":
        if (data.transcript) {
          this.appendUserMessage(data.transcript, data.source || "VOICE");
          this.addMiniNode("router", "INTENT ROUTER", "Policy & Dispatch", "active");
        }
        this.setAuraState("THINKING", data);
        break;

      case "TASK_STARTED":
        this.startTask(data);
        this.setAuraState("EXECUTING", data);
        break;

      case "MODEL_SELECTED":
        const mName = data.model || "openai/gpt-oss-120b";
        const mShort = mName.split("/").pop();
        if (this.modelNameText) {
          this.modelNameText.textContent = mShort;
        }
        this.addMiniNode(`model_${data.role || 'reasoning'}`, `${(data.role || 'MODEL').toUpperCase()}: ${mShort}`, data.provider || 'Groq', "active");
        this.updateTaskStep(2, 4, `Model routed: ${mShort}`);
        break;

      case "MODEL_FALLBACK":
        this.updateMiniNode("model_reasoning", "fractured");
        this.addMiniNode("fallback", `FALLBACK: ${data.model?.split('/').pop() || 'Mistral'}`, data.provider || "Mistral", "fallback-active");
        this.updateTaskStep(2, 4, `Fallback activated: ${data.model || 'Alternate'}`);
        break;

      case "TOOL_STARTED": {
        const tName = data.tool_name || data.tool || "tool";
        this.createInlineWorkCard(tName, data.arguments || data.params, data.call_id);
        this.addMiniNode(`tool_${tName}`, tName.toUpperCase(), "Executing Action", "active");
        this.updateTaskStep(3, 4, `Executing ${tName}`);
        break;
      }

      case "TOOL_COMPLETED": {
        const tcName = data.tool_name || data.tool || "tool";
        this.completeInlineWorkCard(tcName, data.result, data.latency_ms || 0, data.call_id);
        this.updateMiniNode(`tool_${tcName}`, "completed");
        break;
      }

      case "TOOL_FAILED": {
        const tfName = data.tool_name || data.tool || "tool";
        this.failInlineWorkCard(tfName, data.error, data.call_id);
        this.updateMiniNode(`tool_${tfName}`, "broken");
        break;
      }

      case "SCREEN_CAPTURE_STARTED":
        this.createInlineWorkCard("capture_screen", data, data.call_id);
        break;

      case "SCREEN_CAPTURED":
        this.addMiniNode("vision", "SCREEN VISION", "Qwen 2.5 32B", "active");
        this.completeInlineWorkCard("capture_screen", data, data.latency_ms || 0, data.call_id);
        break;

      case "VISION_STARTED":
        this.createInlineWorkCard("inspect_screen", data, data.call_id);
        break;

      case "VISION_COMPLETED":
        this.completeInlineWorkCard("inspect_screen", data, data.latency_ms || 0, data.call_id);
        break;

      case "WEB_SEARCH_STARTED":
        this.addMiniNode("search", "WEB SEARCH", "DuckDuckGo API", "active");
        this.createInlineWorkCard("web_search", data, data.call_id);
        break;

      case "VERIFICATION_STARTED":
        this.addMiniNode("verify", "VERIFY & SYNTHESIZE", "State Validation", "active");
        this.updateTaskStep(4, 4, "Verifying results...");
        break;

      case "STREAM_START":
        this.startAssistantStreaming(data.turn_id);
        break;

      case "STREAM_TOKEN":
        if (data.token || data.text) {
          this.appendStreamToken(data.token || data.text);
        }
        break;

      case "STREAM_COMPLETE":
        this.completeAssistantResponse(data.content || data.text);
        break;

      case "AGENT_RESPONSE": {
        // Authoritative final assistant response settlement
        const respText = data.content || data.text || data.result || "Task completed.";
        this.completeAssistantResponse(respText);
        break;
      }

      case "SPEAKING_STARTED":
      case "TTS_STARTED":
        this.setAuraState("SPEAKING", data);
        this.addMiniNode("tts", "STREAMING TTS", "Fish Audio", "active");
        break;

      case "TASK_COMPLETED":
        this.stopTask("✓ Task Completed", data);
        this.setAuraState("IDLE", data);
        break;

      case "TASK_CANCELLED":
        this.stopTask("✕ Task Cancelled", data);
        this.setAuraState("IDLE", data);
        break;

      case "TASK_FAILED":
        this.stopTask(`✕ Failed: ${data.error || 'Error'}`, data);
        this.setAuraState("BROKEN", data);
        break;
    }
  }

  /* ===================================================================
     7. UTILITY HELPERS
     =================================================================== */

  scrollToBottom(force = false) {
    if (!this.chatStream) return;
    if (force || this.shouldAutoScroll) {
      this.chatStream.scrollTop = this.chatStream.scrollHeight;
    }
  }

  escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  formatMarkdown(str) {
    if (!str) return "";
    let escaped = this.escapeHtml(str);
    escaped = escaped.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/\n/g, '<br>');
    return escaped;
  }

  getToolMetadata(toolName) {
    const metaMap = {
      "capture_screen": { icon: "📸", label: "Screen Capture" },
      "inspect_screen": { icon: "🔍", label: "Vision Analysis" },
      "screen_reading": { icon: "👁️", label: "Screen Perception" },
      "web_search": { icon: "🌐", label: "Web Search" },
      "browser_open": { icon: "🖥️", label: "Browser Launch" },
      "browser_search": { icon: "🔎", label: "Page Search" },
      "browser_read": { icon: "📄", label: "Page Extractor" },
      "open_application": { icon: "🚀", label: "App Launch" },
      "list_folder_contents": { icon: "📁", label: "File Discovery" },
      "read_file": { icon: "📖", label: "File Reader" },
      "check_system_health": { icon: "⚡", label: "Health Audit" },
    };
    return metaMap[toolName] || { icon: "⚡", label: toolName || "Tool Activity" };
  }

  summarizeArgs(toolName, args = {}) {
    if (!args || Object.keys(args).length === 0) return "Executing tool action...";
    if (args.query) return `Query: <em>${this.escapeHtml(args.query)}</em>`;
    if (args.app_name) return `Target Application: <strong>${this.escapeHtml(args.app_name)}</strong>`;
    if (args.path) return `Path: <code>${this.escapeHtml(args.path)}</code>`;
    if (args.url) return `URL: <code>${this.escapeHtml(args.url)}</code>`;
    return `Arguments: ${this.escapeHtml(JSON.stringify(args))}`;
  }
}
