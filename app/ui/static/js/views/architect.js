/**
 * ArchitectView — Persistent Temporal Framework Configuration & Topology Designer
 * Phase 5D.4: 3 Execution Modes, Semantic Priority Dragging, Configuration Preview & Test Simulation
 */

export class ArchitectView {
  constructor(socketSender) {
    this.send = socketSender;

    // DOM Elements
    this.canvas = document.getElementById("architect-canvas");
    this.viewport = document.getElementById("architect-viewport");
    this.nodesContainer = document.getElementById("architect-nodes-container");
    this.svg = document.getElementById("architect-svg");
    this.drawer = document.getElementById("architect-inspector-drawer");
    this.dirtyBadge = document.getElementById("architect-dirty-badge");
    this.roleTitle = document.getElementById("architect-role-title");
    this.candidatesList = document.getElementById("architect-candidates-list");
    this.providerSelect = document.getElementById("architect-provider-select");
    this.modelSelect = document.getElementById("architect-model-select");
    this.modeExplanation = document.getElementById("mode-explanation-text");

    // Modal Elements
    this.previewModal = document.getElementById("architect-preview-modal");
    this.previewBody = document.getElementById("architect-preview-body");
    this.btnPreviewCancel = document.getElementById("btn-preview-cancel");
    this.btnPreviewApply = document.getElementById("btn-preview-apply");

    // Canvas Transform State
    this.scale = 1.0;
    this.panX = 60;
    this.panY = 100;
    this.isPanning = false;
    this.isDraggingNode = false;
    this.draggedNode = null;
    this.dragOffset = { x: 0, y: 0 };

    // Architecture Data State
    this.rolesData = {
      "reasoning": {
        "role": "reasoning",
        "candidates": [
          { "provider": "Groq", "model": "openai/gpt-oss-120b", "latency_ms": 380, "is_primary": true },
          { "provider": "Mistral", "model": "mistral-large-2411", "latency_ms": 520, "is_primary": false },
        ]
      },
      "fast": {
        "role": "fast",
        "candidates": [
          { "provider": "Groq", "model": "llama-3.3-70b-versatile", "latency_ms": 190, "is_primary": true }
        ]
      },
      "desktop": {
        "role": "desktop",
        "candidates": [
          { "provider": "Mistral", "model": "codestral-2501", "latency_ms": 340, "is_primary": true }
        ]
      },
      "vision": {
        "role": "vision",
        "candidates": [
          { "provider": "Groq", "model": "qwen-2.5-32b", "latency_ms": 410, "is_primary": true }
        ]
      }
    };
    this.executionModes = {
      "reasoning": "FALLBACK_ORDER",
      "fast": "PRIMARY_ONLY",
      "desktop": "PRIMARY_ONLY",
      "vision": "PRIMARY_ONLY"
    };
    this.customLayout = {};
    this.originalConfig = JSON.parse(JSON.stringify({
      roles: this.rolesData,
      execution_modes: this.executionModes,
      layout: { nodes: this.customLayout },
    }));
    this.dirty = false;
    this.selectedRole = "reasoning";
    this.providersList = [];

    this.init();
  }

  init() {
    this.setupPanZoom();
    this.setupNodeDragEvents();
    this.setupToolbarButtons();
    this.setupDrawer();
    this.setupModal();
    this.render();
    this.populateRoleInspector(this.selectedRole);
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
      console.warn("[ArchitectView] Failed to fetch config via HTTP:", e);
    }
  }

  loadConfigData(data) {
    if (!data) return;
    const rawRoles = data.roles || {};
    const normalizedRoles = {};
    for (const [rName, rVal] of Object.entries(rawRoles)) {
      if (Array.isArray(rVal)) {
        normalizedRoles[rName] = {
          role: rName,
          candidates: rVal.map((c, idx) => ({
            provider: c.provider,
            model: c.model,
            latency_ms: c.latency_ms || 350,
            is_primary: idx === 0,
            fallback_rank: idx,
            health: c.health || "HEALTHY",
          })),
          execution_mode: this.executionModes[rName] || "FALLBACK_ORDER",
        };
      } else if (rVal && typeof rVal === "object") {
        normalizedRoles[rName] = {
          role: rName,
          candidates: (rVal.candidates || []).map((c, idx) => ({
            provider: c.provider,
            model: c.model,
            latency_ms: c.latency_ms || 350,
            is_primary: idx === 0,
            fallback_rank: idx,
            health: c.health || "HEALTHY",
          })),
          execution_mode: rVal.execution_mode || this.executionModes[rName] || "FALLBACK_ORDER",
        };
      }
    }
    if (Object.keys(normalizedRoles).length > 0) {
      this.rolesData = normalizedRoles;
    }
    this.executionModes = data.execution_modes || this.executionModes;
    this.customLayout = (data.layout && data.layout.nodes) ? data.layout.nodes : (data.workflow_layout && data.workflow_layout.nodes ? data.workflow_layout.nodes : this.customLayout);
    this.originalConfig = JSON.parse(JSON.stringify({
      roles: this.rolesData,
      execution_modes: this.executionModes,
      layout: { nodes: this.customLayout },
    }));
    this.setDirty(false);
    this.render();
    this.populateRoleInspector(this.selectedRole);
    this.fetchProvidersList();
  }

  async fetchProvidersList() {
    try {
      const res = await fetch("/api/providers");
      if (res.ok) {
        const data = await res.json();
        this.providersList = data.providers || [];
        this.populateProviderDropdowns();
      }
    } catch (e) {
      console.debug("Failed to fetch providers for dropdown:", e);
    }
  }

  populateProviderDropdowns() {
    if (!this.providerSelect || !this.modelSelect) return;
    this.providerSelect.innerHTML = "";
    
    this.providersList.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p.provider_name;
      opt.textContent = p.display_name || p.provider_name;
      this.providerSelect.appendChild(opt);
    });

    const updateModels = () => {
      const selP = this.providersList.find(p => p.provider_name === this.providerSelect.value);
      this.modelSelect.innerHTML = "";
      if (selP && selP.models) {
        selP.models.forEach(m => {
          const mOpt = document.createElement("option");
          mOpt.value = m.model_id;
          mOpt.textContent = m.display_name || m.model_id;
          this.modelSelect.appendChild(mOpt);
        });
      }
    };

    this.providerSelect.addEventListener("change", updateModels);
    updateModels();
  }

  setupToolbarButtons() {
    // 1. Test Simulation
    document.getElementById("btn-architect-test")?.addEventListener("click", () => this.runSimulationTest());

    // 2. Discard Changes
    document.getElementById("btn-architect-discard")?.addEventListener("click", () => {
      if (this.dirty) {
        if (confirm("Discard all unsaved architectural changes?")) {
          this.loadConfigData(this.originalConfig);
        }
      }
    });

    // 3. Save Changes
    document.getElementById("btn-architect-save")?.addEventListener("click", () => this.openSavePreviewModal());

    // 4. Reset Layout
    document.getElementById("btn-architect-reset-layout")?.addEventListener("click", () => {
      if (confirm("Reset visual node positions to standard topology?")) {
        this.customLayout = {};
        this.setDirty(true);
        this.render();
      }
    });

    // 5. Add Candidate Button
    document.getElementById("btn-architect-add-cand")?.addEventListener("click", () => {
      const p = this.providerSelect?.value;
      const m = this.modelSelect?.value;
      if (p && m && this.selectedRole) {
        this.addCandidateToRole(this.selectedRole, p, m);
      }
    });
  }

  setupDrawer() {
    document.getElementById("architect-drawer-close")?.addEventListener("click", () => {
      this.drawer?.classList.remove("open");
    });

    // Execution Mode Buttons
    ["PRIMARY_ONLY", "FALLBACK_ORDER", "CUSTOM"].forEach(mode => {
      const btn = document.getElementById(`btn-role-mode-${mode.toLowerCase().split('_')[0]}`);
      btn?.addEventListener("click", () => {
        if (!this.selectedRole) return;
        this.executionModes[this.selectedRole] = mode;
        this.setDirty(true);
        this.updateModeButtons(mode);
        this.render();
      });
    });
  }

  setupModal() {
    this.btnPreviewCancel?.addEventListener("click", () => {
      this.previewModal?.classList.add("hidden");
    });

    this.btnPreviewApply?.addEventListener("click", async () => {
      await this.saveConfiguration();
      this.previewModal?.classList.add("hidden");
    });
  }

  setDirty(isDirty) {
    this.dirty = isDirty;
    if (this.dirtyBadge) {
      this.dirtyBadge.classList.toggle("hidden", !isDirty);
    }
  }

  /* ===================================================================
     CANVAS PAN, ZOOM & NODE DRAG
     =================================================================== */

  setupPanZoom() {
    let startX = 0, startY = 0;

    this.canvas?.addEventListener("mousedown", e => {
      if (e.target.closest(".architect-node") || e.target.closest(".architect-toolbar") || e.target.closest("#architect-inspector-drawer")) return;
      this.isPanning = true;
      startX = e.clientX - this.panX;
      startY = e.clientY - this.panY;
      if (this.canvas) this.canvas.style.cursor = "grabbing";
    });

    window.addEventListener("mousemove", e => {
      if (this.isPanning) {
        this.panX = e.clientX - startX;
        this.panY = e.clientY - startY;
        this.updateViewportTransform();
      }
    });

    window.addEventListener("mouseup", () => {
      this.isPanning = false;
      if (this.canvas) this.canvas.style.cursor = "default";
    });

    this.canvas?.addEventListener("wheel", e => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
      this.scale = Math.min(Math.max(this.scale * zoomFactor, 0.4), 2.2);
      this.updateViewportTransform();
    });
  }

  updateViewportTransform() {
    if (this.viewport) {
      this.viewport.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
    }
  }

  setupNodeDragEvents() {
    this.nodesContainer?.addEventListener("mousedown", e => {
      const nodeEl = e.target.closest(".architect-node");
      if (!nodeEl) return;

      this.isDraggingNode = true;
      this.draggedNode = nodeEl;
      const rect = nodeEl.getBoundingClientRect();
      this.dragOffset = {
        x: (e.clientX - rect.left) / this.scale,
        y: (e.clientY - rect.top) / this.scale,
      };

      const role = nodeEl.getAttribute("data-role");
      if (role) {
        this.selectRole(role);
      }
      e.stopPropagation();
    });

    window.addEventListener("mousemove", e => {
      if (!this.isDraggingNode || !this.draggedNode) return;
      const viewportRect = this.viewport.getBoundingClientRect();
      const x = Math.round((e.clientX - viewportRect.left) / this.scale - this.dragOffset.x);
      const y = Math.round((e.clientY - viewportRect.top) / this.scale - this.dragOffset.y);

      this.draggedNode.style.left = `${x}px`;
      this.draggedNode.style.top = `${y}px`;

      const nodeId = this.draggedNode.id;
      this.customLayout[nodeId] = { x, y };
      this.setDirty(true);
      this.renderEdges();
    });

    window.addEventListener("mouseup", () => {
      this.isDraggingNode = false;
      this.draggedNode = null;
    });
  }

  /* ===================================================================
     GRAPH RENDERING
     =================================================================== */

  render() {
    if (!this.nodesContainer || !this.svg) return;
    this.nodesContainer.innerHTML = "";

    const roleYMap = {
      "stt": 80,
      "fast": 200,
      "reasoning": 320,
      "desktop": 440,
      "vision": 560,
      "ocr": 680,
      "embeddings": 800,
      "tts": 920,
    };

    // 1. Entry / STT Node
    this.renderNode({
      id: "arch_node_stt",
      label: "STT TRANSCRIPTION",
      sub: "Canary-Qwen / Whisper",
      role: "stt",
      x: this.customLayout["arch_node_stt"]?.x || 60,
      y: this.customLayout["arch_node_stt"]?.y || 320,
      kind: "entry",
    });

    // 2. Intent Router Node
    this.renderNode({
      id: "arch_node_router",
      label: "INTENT ROUTER",
      sub: "Policy & Dispatch",
      role: "router",
      x: this.customLayout["arch_node_router"]?.x || 320,
      y: this.customLayout["arch_node_router"]?.y || 320,
      kind: "router",
    });

    // 3. Render Configured Roles
    let roleIdx = 0;
    for (const [rName, rData] of Object.entries(this.rolesData)) {
      const mode = this.executionModes[rName] || "FALLBACK_ORDER";
      const cands = Array.isArray(rData) ? rData : (rData?.candidates || []);
      const baseY = roleYMap[rName] || (120 + roleIdx * 120);
      roleIdx++;

      cands.forEach((c, cIdx) => {
        if (mode === "PRIMARY_ONLY" && cIdx > 0) return;
        const nodeId = (rName === "reasoning" && cIdx === 0) ? "node_reasoning_primary" : `arch_node_${rName}_${cIdx}`;
        const defaultX = 580 + (cIdx * 240);
        const defaultY = baseY;

        this.renderNode({
          id: nodeId,
          label: `${rName.toUpperCase()}: ${c.model.split('/').pop()}`,
          sub: `${c.provider} (${c.latency_ms || 380}ms)`,
          role: rName,
          candidateIndex: cIdx,
          isPrimary: cIdx === 0,
          mode: mode,
          x: this.customLayout[nodeId]?.x || defaultX,
          y: this.customLayout[nodeId]?.y || defaultY,
          kind: "candidate",
        });
      });
    }

    // 4. Verification & Output
    this.renderNode({
      id: "arch_node_verify",
      label: "VERIFY & SYNTHESIZE",
      sub: "State Validation",
      role: "verification",
      x: this.customLayout["arch_node_verify"]?.x || 1320,
      y: this.customLayout["arch_node_verify"]?.y || 320,
      kind: "system",
    });

    this.renderNode({
      id: "arch_node_tts",
      label: "STREAMING TTS",
      sub: "Fish Audio S2.1",
      role: "tts",
      x: this.customLayout["arch_node_tts"]?.x || 1580,
      y: this.customLayout["arch_node_tts"]?.y || 320,
      kind: "system",
    });

    this.renderEdges();
  }

  renderNode(data) {
    const el = document.createElement("div");
    el.id = data.id;
    el.className = `architect-node temporal-node ${data.kind || ''} ${data.isPrimary ? 'primary-candidate' : ''} ${data.role === this.selectedRole ? 'selected' : ''}`;
    el.setAttribute("data-role", data.role || "");
    el.style.left = `${data.x}px`;
    el.style.top = `${data.y}px`;

    const modeBadge = data.mode ? `<span class="arch-mode-pill">${data.mode}</span>` : '';
    const primaryBadge = data.isPrimary ? '<span class="arch-primary-star">★ PRIMARY</span>' : (data.candidateIndex != null ? `<span class="arch-fallback-rank">#${data.candidateIndex + 1}</span>` : '');

    el.innerHTML = `
      <div class="arch-node-header">
        <span class="arch-node-label">${data.label}</span>
        ${primaryBadge}
      </div>
      <div class="arch-node-sub">${data.sub || ''}</div>
      <div class="arch-node-footer">
        ${modeBadge}
      </div>
    `;

    el.addEventListener("click", () => {
      if (data.role && data.role !== "router" && data.role !== "entry" && data.role !== "system") {
        this.selectRole(data.role);
      }
    });

    this.nodesContainer.appendChild(el);
  }

  renderEdges() {
    if (!this.svg) return;
    this.svg.innerHTML = "";

    const drawLine = (fromId, toId, type = "PRIMARY") => {
      const fromEl = document.getElementById(fromId);
      const toEl = document.getElementById(toId);
      if (!fromEl || !toEl) return;

      const fx = parseInt(fromEl.style.left) + fromEl.offsetWidth;
      const fy = parseInt(fromEl.style.top) + fromEl.offsetHeight / 2;
      const tx = parseInt(toEl.style.left);
      const ty = parseInt(toEl.style.top) + toEl.offsetHeight / 2;

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const dx = (tx - fx) * 0.5;
      const d = `M ${fx} ${fy} C ${fx + dx} ${fy}, ${tx - dx} ${ty}, ${tx} ${ty}`;
      path.setAttribute("d", d);
      path.setAttribute("class", `arch-edge-path ${type.toLowerCase()}`);
      this.svg.appendChild(path);
    };

    // Connect Entry ➔ Router
    drawLine("arch_node_stt", "arch_node_router", "PRIMARY");

    // Connect Router ➔ Candidates
    for (const [rName, rData] of Object.entries(this.rolesData)) {
      const mode = this.executionModes[rName] || "FALLBACK_ORDER";
      const cands = rData.candidates || [];

      if (cands.length > 0) {
        const firstId = (rName === "reasoning") ? "node_reasoning_primary" : `arch_node_${rName}_0`;
        drawLine("arch_node_router", firstId, "PRIMARY");
        if (mode !== "PRIMARY_ONLY") {
          for (let i = 1; i < cands.length; i++) {
            const prevId = (rName === "reasoning" && i === 1) ? "node_reasoning_primary" : `arch_node_${rName}_${i-1}`;
            const currId = `arch_node_${rName}_${i}`;
            drawLine(prevId, currId, "FALLBACK");
          }
        }
        // Connect last candidate to Verify
        const lastIdx = mode === "PRIMARY_ONLY" ? 0 : cands.length - 1;
        const lastId = (rName === "reasoning" && lastIdx === 0) ? "node_reasoning_primary" : `arch_node_${rName}_${lastIdx}`;
        drawLine(lastId, "arch_node_verify", "PRIMARY");
      }
    }

    drawLine("arch_node_verify", "arch_node_tts", "PRIMARY");
  }

  /* ===================================================================
     ROLE INSPECTOR & PRIORITY DRAGGING
     =================================================================== */

  selectRole(role) {
    this.selectedRole = role;
    document.querySelectorAll(".architect-node").forEach(n => {
      n.classList.toggle("selected", n.getAttribute("data-role") === role);
    });
    this.populateRoleInspector(role);
    this.drawer?.classList.add("open");
    document.getElementById("workflow-inspector-drawer")?.classList.add("open");
  }

  populateRoleInspector(role) {
    if (!this.roleTitle || !this.candidatesList) return;
    this.roleTitle.textContent = `ROLE: ${role.toUpperCase()}`;

    const mode = this.executionModes[role] || "FALLBACK_ORDER";
    this.updateModeButtons(mode);

    const rData = this.rolesData[role] || { candidates: [] };
    const cands = rData.candidates || [];

    this.candidatesList.innerHTML = "";
    cands.forEach((c, idx) => {
      const item = document.createElement("div");
      item.className = `cand-drag-item ${idx === 0 ? 'is-primary' : ''}`;
      item.draggable = true;
      item.setAttribute("data-index", idx);

      item.innerHTML = `
        <div class="cand-drag-left">
          <span class="cand-drag-handle" title="Drag to reorder priority">⠿</span>
          <div class="cand-meta">
            <span class="cand-model-name">${c.model}</span>
            <span class="cand-provider-tag">${c.provider}</span>
          </div>
        </div>
        <div class="cand-drag-right">
          ${idx === 0 ? '<span class="cand-primary-badge">★ PRIMARY</span>' : `<span class="cand-rank-badge">#${idx + 1}</span>`}
          <button type="button" class="btn-cand-remove" title="Remove candidate">✕</button>
        </div>
      `;

      // Remove button
      item.querySelector(".btn-cand-remove")?.addEventListener("click", e => {
        e.stopPropagation();
        this.removeCandidateFromRole(role, idx);
      });

      // Semantic Priority Drag & Drop Reordering
      item.addEventListener("dragstart", e => {
        e.dataTransfer.setData("text/plain", idx.toString());
        item.classList.add("dragging");
      });

      item.addEventListener("dragend", () => {
        item.classList.remove("dragging");
      });

      item.addEventListener("dragover", e => {
        e.preventDefault();
        item.classList.add("drag-over");
      });

      item.addEventListener("dragleave", () => {
        item.classList.remove("drag-over");
      });

      item.addEventListener("drop", e => {
        e.preventDefault();
        item.classList.remove("drag-over");
        const fromIdx = parseInt(e.dataTransfer.getData("text/plain"), 10);
        const toIdx = idx;
        if (!isNaN(fromIdx) && fromIdx !== toIdx) {
          this.reorderCandidates(role, fromIdx, toIdx);
        }
      });

      this.candidatesList.appendChild(item);
    });
  }

  updateModeButtons(mode) {
    const pBtn = document.getElementById("btn-role-mode-primary");
    const fBtn = document.getElementById("btn-role-mode-fallback");
    const cBtn = document.getElementById("btn-role-mode-custom");

    pBtn?.classList.toggle("active", mode === "PRIMARY_ONLY");
    fBtn?.classList.toggle("active", mode === "FALLBACK_ORDER");
    cBtn?.classList.toggle("active", mode === "CUSTOM");

    if (this.modeExplanation) {
      if (mode === "PRIMARY_ONLY") {
        this.modeExplanation.textContent = "Dispatches Primary model only. If primary fails or is rate-limited, execution stops with BROKEN status.";
      } else if (mode === "FALLBACK_ORDER") {
        this.modeExplanation.textContent = "Dispatches Primary. If rate-limited or unavailable, automatically cascades through fallback candidates in sequence.";
      } else {
        this.modeExplanation.textContent = "Custom multi-model routing topology with capability matching and parallel validation.";
      }
    }
  }

  reorderCandidates(role, fromIdx, toIdx) {
    const cands = this.rolesData[role]?.candidates;
    if (!cands) return;
    const [moved] = cands.splice(fromIdx, 1);
    cands.splice(toIdx, 0, moved);
    this.setDirty(true);
    this.populateRoleInspector(role);
    this.render();
  }

  addCandidateToRole(role, provider, model) {
    if (!this.rolesData[role]) {
      this.rolesData[role] = { candidates: [] };
    }
    const cands = this.rolesData[role].candidates;
    if (cands.some(c => c.provider === provider && c.model === model)) {
      alert(`Model '${model}' is already added to role '${role}'.`);
      return;
    }
    cands.push({
      provider: provider,
      model: model,
      latency_ms: 350,
      health: "HEALTHY",
      is_primary: cands.length === 0,
    });
    this.setDirty(true);
    this.populateRoleInspector(role);
    this.render();
  }

  removeCandidateFromRole(role, idx) {
    const cands = this.rolesData[role]?.candidates;
    if (!cands || cands.length <= 1) {
      alert("Role must have at least one primary candidate.");
      return;
    }
    cands.splice(idx, 1);
    this.setDirty(true);
    this.populateRoleInspector(role);
    this.render();
  }

  /* ===================================================================
     PREVIEW MODAL, SAVE & TEST SIMULATION
     =================================================================== */

  openSavePreviewModal() {
    if (!this.previewModal || !this.previewBody) return;

    let diffHtml = '<div class="preview-diff-grid">';
    for (const [rName, rData] of Object.entries(this.rolesData)) {
      const origCands = this.originalConfig?.roles?.[rName]?.candidates || [];
      const newCands = rData.candidates || [];
      const origMode = this.originalConfig?.execution_modes?.[rName] || "FALLBACK_ORDER";
      const newMode = this.executionModes[rName] || "FALLBACK_ORDER";

      const origChain = origCands.map(c => c.model.split('/').pop()).join(' ➔ ');
      const newChain = newCands.map(c => c.model.split('/').pop()).join(' ➔ ');

      diffHtml += `
        <div class="diff-role-card">
          <div class="diff-role-header">
            <strong>${rName.toUpperCase()}</strong>
            <span class="diff-mode-badge">${newMode}</span>
          </div>
          <div class="diff-chain-row">
            <span class="diff-label">Before:</span>
            <code>${origChain || '(none)'}</code>
          </div>
          <div class="diff-chain-row">
            <span class="diff-label">After:</span>
            <code style="color: var(--accent-cyan); font-weight: 700;">${newChain || '(none)'}</code>
          </div>
        </div>
      `;
    }
    diffHtml += '</div>';

    this.previewBody.innerHTML = diffHtml;
    this.previewModal.classList.remove("hidden");
  }

  async saveConfiguration() {
    const payload = {
      roles: this.rolesData,
      execution_modes: this.executionModes,
      layout: { nodes: this.customLayout },
    };

    try {
      const res = await fetch("/api/architect/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        this.originalConfig = JSON.parse(JSON.stringify(payload));
        this.setDirty(false);
        this.send({ action: "SAVE_ARCHITECT_CONFIG", config: payload });
      }
    } catch (e) {
      console.error("Failed to save architect config:", e);
    }
  }

  async runSimulationTest() {
    try {
      const res = await fetch("/api/architect/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: this.selectedRole,
          simulate_outage: true,
        }),
      });

      if (res.ok) {
        const testRes = await res.json();
        this.visualizeSimulationTrace(testRes);
      }
    } catch (e) {
      console.warn("Simulation test failed:", e);
    }
  }

  visualizeSimulationTrace(testRes) {
    if (!testRes || !testRes.trace) return;
    
    // Highlight simulated active path
    testRes.trace.forEach((step, idx) => {
      setTimeout(() => {
        const nodeEl = document.getElementById(step.node);
        if (nodeEl) {
          nodeEl.classList.add("sim-active");
          if (step.status === "RATE_LIMITED") {
            nodeEl.classList.add("sim-fracture");
          } else if (step.status === "FALLBACK_ACTIVE") {
            nodeEl.classList.add("sim-fallback");
          }
          setTimeout(() => {
            nodeEl.classList.remove("sim-active", "sim-fracture", "sim-fallback");
          }, 3000);
        }
      }, idx * 400);
    });
  }
}
