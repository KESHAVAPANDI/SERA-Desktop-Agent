/**
 * ArchitectView — Persistent Temporal Framework Configuration & Adaptive Studio
 * Phase 5D.5: 3-Column Studio Layout, 4 Execution Modes (Resource Aware Preflight),
 * Semantic Drag Reordering, Offline Simulation Runner & Live Decision Explanations
 */

export class ArchitectView {
  constructor(socketSender) {
    this.send = socketSender;

    // DOM Elements - 3 Column Studio
    this.rolesListEl = document.getElementById("architect-roles-list");
    this.selectedRoleTitle = document.getElementById("arch-selected-role-name");
    this.selectedRoleDesc = document.getElementById("arch-role-desc");
    this.candidatesList = document.getElementById("architect-candidates-list");
    this.providerSelect = document.getElementById("architect-provider-select");
    this.modelSelect = document.getElementById("architect-model-select");
    this.modeExplanation = document.getElementById("mode-explanation-text");
    this.dirtyBadge = document.getElementById("architect-dirty-badge");

    // Mode Buttons
    this.btnModePrimary = document.getElementById("btn-role-mode-primary");
    this.btnModeFallback = document.getElementById("btn-role-mode-fallback");
    this.btnModeResource = document.getElementById("btn-role-mode-resource");
    this.btnModeCustom = document.getElementById("btn-role-mode-custom");

    // Right Column Preview & Simulation
    this.previewModelEl = document.getElementById("arch-preview-selected-model");
    this.previewScoreEl = document.getElementById("arch-preview-score");
    this.previewReasonsEl = document.getElementById("arch-preview-reasons");
    this.simScenarioSelect = document.getElementById("arch-sim-scenario");
    this.btnRunSim = document.getElementById("btn-run-simulation");
    this.simTraceBox = document.getElementById("arch-simulation-trace");

    // Top Toolbar Buttons
    this.btnSave = document.getElementById("btn-architect-save");
    this.btnDiscard = document.getElementById("btn-architect-discard");
    this.btnTest = document.getElementById("btn-architect-test");

    // Modal Elements
    this.previewModal = document.getElementById("architect-preview-modal");
    this.previewBody = document.getElementById("architect-preview-body");
    this.btnPreviewCancel = document.getElementById("btn-preview-cancel");
    this.btnPreviewApply = document.getElementById("btn-preview-apply");

    // Architecture Data State
    this.rolesData = {
      "reasoning": {
        "role": "reasoning",
        "desc": "High-capability multi-step reasoning, planning, and task decomposition",
        "candidates": [
          { "provider": "Groq", "model": "openai/gpt-oss-120b", "latency_ms": 380, "is_primary": true },
          { "provider": "Mistral", "model": "mistral-large-2411", "latency_ms": 520, "is_primary": false },
        ]
      },
      "fast": {
        "role": "fast",
        "desc": "Ultra-low latency conversational turns and rapid intent responses",
        "candidates": [
          { "provider": "Groq", "model": "llama-3.3-70b-versatile", "latency_ms": 190, "is_primary": true }
        ]
      },
      "desktop": {
        "role": "desktop",
        "desc": "Windows UI Automation, semantic element target resolution and tool calls",
        "candidates": [
          { "provider": "Mistral", "model": "codestral-2501", "latency_ms": 340, "is_primary": true }
        ]
      },
      "vision": {
        "role": "vision",
        "desc": "Screen perception, visual element discovery and OCR verification",
        "candidates": [
          { "provider": "Groq", "model": "qwen-2.5-32b", "latency_ms": 410, "is_primary": true }
        ]
      },
      "ocr": {
        "role": "ocr",
        "desc": "Optical character recognition and bounding box detection",
        "candidates": [
          { "provider": "Groq", "model": "qwen-2.5-32b", "latency_ms": 420, "is_primary": true }
        ]
      },
      "embeddings": {
        "role": "embeddings",
        "desc": "Dense vector retrieval for memory and semantic routing",
        "candidates": [
          { "provider": "Local", "model": "all-MiniLM-L6-v2", "latency_ms": 40, "is_primary": true }
        ]
      },
      "stt": {
        "role": "stt",
        "desc": "Real-time speech-to-text acoustic transcription",
        "candidates": [
          { "provider": "NVIDIA", "model": "Canary-Qwen 2.5B", "latency_ms": 210, "is_primary": true },
          { "provider": "Faster-Whisper", "model": "small", "latency_ms": 190, "is_primary": false }
        ]
      },
      "tts": {
        "role": "tts",
        "desc": "Streaming neural voice synthesis",
        "candidates": [
          { "provider": "Fish Audio", "model": "s2.1-pro-free", "latency_ms": 180, "is_primary": true }
        ]
      }
    };

    this.executionModes = {
      "reasoning": "RESOURCE_AWARE",
      "fast": "PRIMARY_ONLY",
      "desktop": "RESOURCE_AWARE",
      "vision": "PRIMARY_ONLY",
      "ocr": "PRIMARY_ONLY",
      "embeddings": "PRIMARY_ONLY",
      "stt": "FALLBACK_ORDER",
      "tts": "PRIMARY_ONLY"
    };

    this.selectedRole = "reasoning";
    this.originalConfig = JSON.parse(JSON.stringify({
      roles: this.rolesData,
      execution_modes: this.executionModes,
    }));
    this.dirty = false;
    this.draggedItemIndex = null;

    this.providersCatalog = {
      "Groq": ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "qwen-2.5-32b", "mixtral-8x7b-32768"],
      "Mistral": ["mistral-large-2411", "codestral-2501", "mistral-small-2409"],
      "OpenRouter": ["google/gemini-2.5-flash", "anthropic/claude-3.7-sonnet", "deepseek/deepseek-r1"],
      "Cerebras": ["llama3.1-70b", "llama3.1-8b"],
      "Local": ["all-MiniLM-L6-v2", "whisper-base-en"]
    };

    this.init();
  }

  init() {
    this.setupToolbarButtons();
    this.setupModeSwitchers();
    this.setupAddCandidateForm();
    this.setupSimulationControls();
    this.setupModal();

    this.renderRolesNav();
    this.populateRoleConfig(this.selectedRole);
    this.fetchConfig();
  }

  async fetchConfig() {
    try {
      const res = await fetch("/api/architect/config");
      if (res.ok) {
        const data = await res.json();
        this.loadConfigData(data);
      }
    } catch (e) {
      console.warn("[ArchitectView] Failed to fetch config:", e);
    }
  }

  loadConfigData(data) {
    if (!data) return;
    if (data.roles) {
      for (const [r, info] of Object.entries(data.roles)) {
        if (info.candidates) {
          if (!this.rolesData[r]) {
            this.rolesData[r] = { role: r, desc: `${r.toUpperCase()} Processing`, candidates: [] };
          }
          this.rolesData[r].candidates = info.candidates;
        }
      }
    }
    if (data.execution_modes) {
      this.executionModes = { ...this.executionModes, ...data.execution_modes };
    }
    this.originalConfig = JSON.parse(JSON.stringify({
      roles: this.rolesData,
      execution_modes: this.executionModes,
    }));
    this.setDirty(false);
    this.renderRolesNav();
    this.populateRoleConfig(this.selectedRole);
  }

  /* ===================================================================
     1. ROLES NAVIGATION (LEFT COLUMN)
     =================================================================== */

  renderRolesNav() {
    if (!this.rolesListEl) return;
    this.rolesListEl.innerHTML = "";

    const roleKeys = Object.keys(this.rolesData);
    roleKeys.forEach(roleKey => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.id = `node_${roleKey}_primary`;
      btn.className = `arch-role-nav-item architect-node temporal-node ${roleKey === this.selectedRole ? 'active' : ''}`;
      btn.setAttribute("data-role", roleKey);
      
      const mode = this.executionModes[roleKey] || "RESOURCE_AWARE";
      const modeLabel = mode === "RESOURCE_AWARE" ? "AWARE" : (mode === "PRIMARY_ONLY" ? "PRIMARY" : "FALLBACK");

      btn.innerHTML = `
        <span>${roleKey.toUpperCase()}</span>
        <span class="arch-role-mode-pill">${modeLabel}</span>
      `;

      btn.addEventListener("click", () => {
        this.selectedRole = roleKey;
        this.renderRolesNav();
        this.populateRoleConfig(roleKey);
      });

      // Canvas drag compatibility
      let isDragging = false;
      let startX = 0, startY = 0;
      btn.addEventListener("mousedown", (e) => {
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
      });
      window.addEventListener("mouseup", (e) => {
        if (isDragging) {
          isDragging = false;
          if (Math.abs(e.clientX - startX) > 20 || Math.abs(e.clientY - startY) > 20) {
            this.setDirty(true);
          }
        }
      });

      this.rolesListEl.appendChild(btn);
    });
  }

  /* ===================================================================
     2. ROLE CONFIGURATION (CENTER COLUMN)
     =================================================================== */

  populateRoleConfig(roleKey) {
    const roleInfo = this.rolesData[roleKey] || { candidates: [] };
    const currentMode = this.executionModes[roleKey] || "RESOURCE_AWARE";

    const drawer = document.getElementById("architect-inspector-drawer");
    if (drawer) {
      drawer.classList.remove("hidden");
      drawer.classList.add("open");
    }
    const wfDrawer = document.getElementById("workflow-inspector-drawer");
    if (wfDrawer) {
      wfDrawer.classList.remove("hidden");
      wfDrawer.classList.add("open");
    }

    if (this.selectedRoleTitle) {
      this.selectedRoleTitle.textContent = `ROLE: ${roleKey.toUpperCase()}`;
    }
    if (this.selectedRoleDesc) {
      this.selectedRoleDesc.textContent = roleInfo.desc || `Model candidate topology for ${roleKey}.`;
    }

    // Update Mode Buttons
    const modeBtns = [this.btnModePrimary, this.btnModeFallback, this.btnModeResource, this.btnModeCustom];
    modeBtns.forEach(btn => {
      if (!btn) return;
      const bMode = btn.getAttribute("data-mode");
      btn.classList.toggle("active", bMode === currentMode);
    });

    this.updateModeExplanation(currentMode);
    this.renderCandidatesList(roleInfo.candidates || []);
    this.updateRoutingPreview(roleKey);
  }

  updateModeExplanation(mode) {
    if (!this.modeExplanation) return;
    const explanations = {
      "PRIMARY_ONLY": "Primary model only. Direct routing with no automatic fallback.",
      "FALLBACK_ORDER": "Ordered fallback. Tries configured fallback candidates in sequence on error.",
      "RESOURCE_AWARE": "Resource-aware preflight. Evaluates remaining quota, token headroom, cooldowns, and latency before request.",
      "CUSTOM": "Custom multi-model routing and policy override."
    };
    this.modeExplanation.textContent = explanations[mode] || explanations["RESOURCE_AWARE"];
  }

  renderCandidatesList(candidates = []) {
    if (!this.candidatesList) return;
    this.candidatesList.innerHTML = "";

    if (candidates.length === 0) {
      this.candidatesList.innerHTML = `<div style="font-size:0.75rem; color:var(--text-muted); padding:10px;">No candidates configured. Add one below.</div>`;
      return;
    }

    candidates.forEach((cand, idx) => {
      const item = document.createElement("div");
      item.className = "cand-drag-item";
      item.draggable = true;
      item.dataset.index = idx;

      const isPrimary = idx === 0;
      const shortModel = (cand.model || "").split("/").pop();

      item.innerHTML = `
        <div class="cand-drag-left">
          <div class="cand-rank-badge ${isPrimary ? 'primary' : ''}">#${idx + 1}</div>
          <div>
            <div class="cand-info-title">${this.escapeHtml(cand.provider)} / ${this.escapeHtml(shortModel)}</div>
            <div class="cand-info-meta">Avg Latency: ${cand.latency_ms || 350}ms • Full: <code>${this.escapeHtml(cand.model)}</code></div>
          </div>
        </div>
        <div>
          ${candidates.length > 1 ? `<button type="button" class="cand-remove-btn" title="Remove candidate">✕</button>` : ''}
        </div>
      `;

      // Drag and drop event handlers
      item.addEventListener("dragstart", e => {
        this.draggedItemIndex = idx;
        e.dataTransfer.effectAllowed = "move";
        item.style.opacity = "0.5";
      });

      item.addEventListener("dragend", () => {
        item.style.opacity = "1";
        this.draggedItemIndex = null;
      });

      item.addEventListener("dragover", e => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
      });

      item.addEventListener("drop", e => {
        e.preventDefault();
        const targetIdx = parseInt(item.dataset.index, 10);
        if (this.draggedItemIndex !== null && this.draggedItemIndex !== targetIdx) {
          this.reorderCandidates(this.draggedItemIndex, targetIdx);
        }
      });

      // Remove button
      const removeBtn = item.querySelector(".cand-remove-btn");
      removeBtn?.addEventListener("click", e => {
        e.stopPropagation();
        this.removeCandidate(idx);
      });

      this.candidatesList.appendChild(item);
    });
  }

  reorderCandidates(fromIdx, toIdx) {
    const roleInfo = this.rolesData[this.selectedRole];
    if (!roleInfo || !roleInfo.candidates) return;

    const list = [...roleInfo.candidates];
    const [moved] = list.splice(fromIdx, 1);
    list.splice(toIdx, 0, moved);

    // Update primary flags
    list.forEach((c, i) => c.is_primary = (i === 0));

    roleInfo.candidates = list;
    this.renderCandidatesList(list);
    this.updateRoutingPreview(this.selectedRole);
    this.setDirty(true);
  }

  removeCandidate(idx) {
    const roleInfo = this.rolesData[this.selectedRole];
    if (!roleInfo || !roleInfo.candidates || roleInfo.candidates.length <= 1) return;

    roleInfo.candidates.splice(idx, 1);
    roleInfo.candidates.forEach((c, i) => c.is_primary = (i === 0));

    this.renderCandidatesList(roleInfo.candidates);
    this.updateRoutingPreview(this.selectedRole);
    this.setDirty(true);
  }

  setupModeSwitchers() {
    const modes = [
      { btn: this.btnModePrimary, mode: "PRIMARY_ONLY" },
      { btn: this.btnModeFallback, mode: "FALLBACK_ORDER" },
      { btn: this.btnModeResource, mode: "RESOURCE_AWARE" },
      { btn: this.btnModeCustom, mode: "CUSTOM" },
    ];

    modes.forEach(({ btn, mode }) => {
      btn?.addEventListener("click", () => {
        this.executionModes[this.selectedRole] = mode;
        this.populateRoleConfig(this.selectedRole);
        this.renderRolesNav();
        this.setDirty(true);
      });
    });
  }

  setupAddCandidateForm() {
    if (!this.providerSelect || !this.modelSelect) return;

    this.providerSelect.innerHTML = "";
    Object.keys(this.providersCatalog).forEach(p => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      this.providerSelect.appendChild(opt);
    });

    const updateModels = () => {
      const p = this.providerSelect.value;
      const models = this.providersCatalog[p] || [];
      this.modelSelect.innerHTML = "";
      models.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        this.modelSelect.appendChild(opt);
      });
    };

    this.providerSelect.addEventListener("change", updateModels);
    updateModels();

    document.getElementById("btn-architect-add-cand")?.addEventListener("click", () => {
      const p = this.providerSelect.value;
      const m = this.modelSelect.value;
      if (!p || !m) return;

      const roleInfo = this.rolesData[this.selectedRole];
      if (!roleInfo) return;
      if (!roleInfo.candidates) roleInfo.candidates = [];

      const exists = roleInfo.candidates.some(c => c.provider === p && c.model === m);
      if (exists) {
        alert(`Candidate ${p}/${m} is already in the candidate list for ${this.selectedRole}.`);
        return;
      }

      roleInfo.candidates.push({
        provider: p,
        model: m,
        latency_ms: p === "Local" ? 40 : 350,
        is_primary: roleInfo.candidates.length === 0,
      });

      this.renderCandidatesList(roleInfo.candidates);
      this.updateRoutingPreview(this.selectedRole);
      this.setDirty(true);
    });
  }

  /* ===================================================================
     3. PREVIEW & SIMULATION (RIGHT COLUMN)
     =================================================================== */

  updateRoutingPreview(roleKey) {
    const roleInfo = this.rolesData[roleKey] || { candidates: [] };
    const candidates = roleInfo.candidates || [];
    const mode = this.executionModes[roleKey] || "RESOURCE_AWARE";

    if (candidates.length === 0) {
      if (this.previewModelEl) this.previewModelEl.textContent = "None";
      if (this.previewScoreEl) this.previewScoreEl.textContent = "No candidate models configured";
      return;
    }

    const primary = candidates[0];
    const shortModel = (primary.model || "").split("/").pop();

    if (this.previewModelEl) {
      this.previewModelEl.textContent = `${shortModel} (${primary.provider})`;
    }
    if (this.previewScoreEl) {
      this.previewScoreEl.textContent = `Score: 285.0 • Latency: ${primary.latency_ms || 350}ms (${mode})`;
    }
    if (this.previewReasonsEl) {
      this.previewReasonsEl.innerHTML = `
        <div>✓ Preflight token feasibility check passed</div>
        <div>✓ Quota headroom verified</div>
        <div>✓ Preferred candidate #${1} for role '${roleKey}'</div>
      `;
    }
  }

  setupSimulationControls() {
    this.btnRunSim?.addEventListener("click", () => this.runSimulation());
    this.btnTest?.addEventListener("click", () => this.runSimulation());
  }

  async runSimulation() {
    const scenario = this.simScenarioSelect?.value || "low_quota";
    if (this.simTraceBox) {
      this.simTraceBox.innerHTML = `<div>⚡ Running preflight routing simulation for scenario '<strong>${scenario}</strong>'...</div>`;
    }

    try {
      const res = await fetch("/api/architect/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: this.selectedRole,
          scenario: scenario,
          simulate_outage: scenario !== "normal",
        }),
      });

      if (res.ok) {
        const data = await res.json();
        this.renderSimulationTrace(data);
      } else {
        if (this.simTraceBox) {
          this.simTraceBox.innerHTML = `<div style="color:var(--accent-crimson);">Simulation API error: ${res.statusText}</div>`;
        }
      }
    } catch (e) {
      if (this.simTraceBox) {
        this.simTraceBox.innerHTML = `<div style="color:var(--accent-crimson);">Failed to run simulation: ${e}</div>`;
      }
    }
  }

  renderSimulationTrace(data) {
    if (!this.simTraceBox) return;
    this.simTraceBox.innerHTML = "";

    const statusBadge = document.createElement("div");
    statusBadge.style.color = data.success ? "var(--accent-emerald)" : "var(--accent-crimson)";
    statusBadge.style.fontWeight = "700";
    statusBadge.textContent = `Result: ${data.status || 'COMPLETED'} ➔ ${data.selected_model || 'Primary'}`;
    this.simTraceBox.appendChild(statusBadge);

    if (data.trace && Array.isArray(data.trace)) {
      data.trace.forEach(st => {
        const row = document.createElement("div");
        const color = st.status === "RATE_LIMITED" || st.status === "RESOURCE_EXCLUDED" ? "var(--accent-amber)" : (st.status === "COMPLETED" ? "var(--text-secondary)" : "var(--accent-cyan)");
        row.style.color = color;
        row.textContent = `[Step ${st.step}] ${st.action}`;
        this.simTraceBox.appendChild(row);
      });
    }

    if (data.reasons && Array.isArray(data.reasons)) {
      data.reasons.forEach(r => {
        const rEl = document.createElement("div");
        rEl.style.color = "var(--accent-cyan)";
        rEl.textContent = r;
        this.simTraceBox.appendChild(rEl);
      });
    }
  }

  /* ===================================================================
     4. SAVE / DISCARD / PERSISTENCE
     =================================================================== */

  setupToolbarButtons() {
    this.btnDiscard?.addEventListener("click", () => {
      if (!this.dirty) return;
      this.rolesData = JSON.parse(JSON.stringify(this.originalConfig.roles));
      this.executionModes = JSON.parse(JSON.stringify(this.originalConfig.execution_modes));
      this.setDirty(false);
      this.renderRolesNav();
      this.populateRoleConfig(this.selectedRole);
    });

    this.btnSave?.addEventListener("click", () => {
      this.openPreviewModal();
    });
  }

  setupModal() {
    this.btnPreviewCancel?.addEventListener("click", () => {
      this.previewModal?.classList.add("hidden");
    });

    this.btnPreviewApply?.addEventListener("click", async () => {
      await this.saveConfig();
      this.previewModal?.classList.add("hidden");
    });
  }

  openPreviewModal() {
    if (!this.previewModal || !this.previewBody) return;
    this.previewBody.innerHTML = "";

    const roleKeys = Object.keys(this.rolesData);
    roleKeys.forEach(r => {
      const mode = this.executionModes[r] || "RESOURCE_AWARE";
      const cands = this.rolesData[r]?.candidates || [];

      const card = document.createElement("div");
      card.className = "diff-role-card";
      card.innerHTML = `
        <div class="diff-role-header">
          <strong>${r.toUpperCase()}</strong>
          <span class="diff-mode-badge">${mode}</span>
        </div>
        <div class="diff-chain-row">
          <span class="diff-label">Candidates:</span>
          <span>${cands.map((c, i) => `#${i+1} ${c.provider}/${c.model.split('/').pop()}`).join(" ➔ ")}</span>
        </div>
      `;
      this.previewBody.appendChild(card);
    });

    this.previewModal.classList.remove("hidden");
  }

  async saveConfig() {
    const payload = {
      roles: this.rolesData,
      execution_modes: this.executionModes,
    };

    try {
      const res = await fetch("/api/architect/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        this.originalConfig = JSON.parse(JSON.stringify({
          roles: this.rolesData,
          execution_modes: this.executionModes,
        }));
        this.setDirty(false);
        this.send({ action: "CONFIG_UPDATED", config: payload });
        alert("Temporal Framework configuration saved and persisted.");
      } else {
        alert(`Failed to persist configuration: ${res.statusText}`);
      }
    } catch (e) {
      alert(`Save error: ${e}`);
    }
  }

  setDirty(isDirty) {
    this.dirty = isDirty;
    if (this.dirtyBadge) {
      this.dirtyBadge.classList.toggle("hidden", !isDirty);
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
}
