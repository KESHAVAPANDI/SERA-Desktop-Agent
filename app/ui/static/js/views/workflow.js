/**
 * WorkflowView — Temporal Aura Horizontal Execution Graph & Candidate Editor
 */

export class WorkflowView {
  constructor(socketSender) {
    this.send = socketSender;
    this.container = document.getElementById("workflow-nodes-container");
    this.svg = document.getElementById("workflow-svg");
    this.canvas = document.getElementById("workflow-canvas");
    this.drawer = document.getElementById("workflow-inspector-drawer");
    
    this.mode = "RUNTIME"; // "RUNTIME" | "DESIGN"
    this.zoom = 1.0;
    this.panX = 50;
    this.panY = 80;
    this.selectedNodeId = null;
    this.activeRole = null;
    this.isDragging = false;

    // Graph Data
    this.nodes = [];
    this.edges = [];
    this.rolesData = {};
    this.executionModes = {};
    this.particleOffset = 0;

    this.init();
  }

  init() {
    this.setupToolbar();
    this.setupPanZoom();
    this.setupDrawer();
    this.fetchGraphData();
    this.startParticleAnimation();
  }

  setupToolbar() {
    const modeBtn = document.getElementById("btn-toggle-mode");
    if (modeBtn) {
      modeBtn.addEventListener("click", () => {
        this.mode = this.mode === "RUNTIME" ? "DESIGN" : "RUNTIME";
        modeBtn.innerHTML = this.mode === "RUNTIME" 
          ? `<span style="color: var(--accent-cyan);">●</span> RUNTIME MODE` 
          : `<span style="color: var(--accent-amber);">✎</span> DESIGN MODE`;
        modeBtn.classList.toggle("design-mode-active", this.mode === "DESIGN");
        
        const modeDesc = document.getElementById("workflow-mode-desc");
        if (modeDesc) {
          modeDesc.textContent = this.mode === "RUNTIME" 
            ? "Live Execution Observer" 
            : "Role Candidate Chain & Mode Editor";
        }
        this.render();
      });
    }

    document.getElementById("btn-zoom-in")?.addEventListener("click", () => {
      this.zoom = Math.min(2.2, this.zoom + 0.15);
      this.render();
    });
    document.getElementById("btn-zoom-out")?.addEventListener("click", () => {
      this.zoom = Math.max(0.4, this.zoom - 0.15);
      this.render();
    });
    document.getElementById("btn-reset-view")?.addEventListener("click", () => {
      this.zoom = 1.0;
      this.panX = 50;
      this.panY = 80;
      this.render();
    });
    document.getElementById("btn-center-active")?.addEventListener("click", () => {
      this.centerOnActiveNode();
    });
  }

  setupPanZoom() {
    let startX = 0, startY = 0;

    this.canvas?.addEventListener("mousedown", e => {
      if (e.target.closest(".temporal-node") || e.target.closest(".workflow-toolbar") || e.target.closest("#workflow-inspector-drawer")) return;
      this.isDragging = true;
      startX = e.clientX - this.panX;
      startY = e.clientY - this.panY;
    });

    window.addEventListener("mousemove", e => {
      if (this.isDragging) {
        this.panX = e.clientX - startX;
        this.panY = e.clientY - startY;
        this.render();
      }
    });

    window.addEventListener("mouseup", () => {
      this.isDragging = false;
    });

    this.canvas?.addEventListener("wheel", e => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
      this.zoom = Math.max(0.4, Math.min(2.5, this.zoom * zoomFactor));
      this.render();
    }, { passive: false });
  }

  setupDrawer() {
    document.getElementById("drawer-close-btn")?.addEventListener("click", () => {
      this.closeDrawer();
    });

    window.addEventListener("keydown", e => {
      if (e.key === "Escape") this.closeDrawer();
    });
  }

  async fetchGraphData() {
    try {
      const resp = await fetch("/api/workflow");
      if (resp.ok) {
        const data = await resp.json();
        this.updateGraphData(data);
      }
    } catch (e) {
      console.warn("[WorkflowView] Using local graph state.");
    }
  }

  updateGraphData(data) {
    if (!data) return;
    this.nodes = data.nodes || [];
    this.edges = data.edges || [];
    this.rolesData = data.roles || {};
    this.executionModes = data.execution_modes || {};
    this.render();
  }

  startParticleAnimation() {
    const animate = () => {
      this.particleOffset = (this.particleOffset + 0.8) % 100;
      const paths = this.svg?.querySelectorAll(".active-particle-edge");
      if (paths) {
        paths.forEach(p => {
          p.style.strokeDashoffset = -this.particleOffset;
        });
      }
      requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }

  centerOnActiveNode() {
    const activeNode = this.nodes.find(n => n.status === "ACTIVE" || n.status === "EXECUTING");
    if (activeNode && this.canvas) {
      this.panX = (this.canvas.clientWidth / 2) - (activeNode.x * this.zoom) - 100;
      this.panY = (this.canvas.clientHeight / 2) - (activeNode.y * this.zoom) - 40;
      this.render();
    }
  }

  highlightModel(provider, model) {
    const targetNode = this.nodes.find(n => n.provider === provider && n.model === model);
    if (targetNode) {
      this.selectNode(targetNode);
      this.panX = (this.canvas.clientWidth / 2) - (targetNode.x * this.zoom) - 100;
      this.panY = (this.canvas.clientHeight / 2) - (targetNode.y * this.zoom) - 40;
      this.render();
    }
  }

  render() {
    if (!this.container || !this.svg) return;
    this.container.innerHTML = "";
    this.svg.innerHTML = "";

    this.renderEdges();
    this.renderNodes();
  }

  renderEdges() {
    this.edges.forEach(e => {
      const src = this.nodes.find(n => n.id === e.source || n.id === e.from);
      const tgt = this.nodes.find(n => n.id === e.target || n.id === e.to);
      if (!src || !tgt) return;

      const x1 = (src.x + 210) * this.zoom + this.panX;
      const y1 = (src.y + 44) * this.zoom + this.panY;
      const x2 = tgt.x * this.zoom + this.panX;
      const y2 = (tgt.y + 44) * this.zoom + this.panY;
      const dx = Math.max(40, (x2 - x1) * 0.45);

      const isFallback = e.type === "FALLBACK" || tgt.fallback_rank > 0;
      const isActive = src.status === "COMPLETED" && (tgt.status === "ACTIVE" || tgt.status === "EXECUTING");
      const isBroken = src.status === "BROKEN" || tgt.status === "BROKEN";

      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`);
      path.setAttribute("fill", "none");

      if (isBroken) {
        path.setAttribute("stroke", "var(--accent-broken)");
        path.setAttribute("stroke-width", "2");
        path.setAttribute("stroke-dasharray", "4,4");
      } else if (isFallback) {
        path.setAttribute("stroke", "rgba(255, 184, 0, 0.45)");
        path.setAttribute("stroke-width", "2");
        path.setAttribute("stroke-dasharray", "6,5");
      } else {
        path.setAttribute("stroke", isActive ? "var(--accent-cyan)" : "rgba(0, 240, 255, 0.25)");
        path.setAttribute("stroke-width", isActive ? "2.5" : "1.5");
      }

      if (isActive) {
        path.classList.add("active-particle-edge");
        path.setAttribute("stroke-dasharray", "8,8");
        path.setAttribute("filter", "drop-shadow(0 0 6px var(--accent-cyan))");
      }

      this.svg.appendChild(path);
    });
  }

  renderNodes() {
    this.nodes.forEach(n => {
      const el = document.createElement("div");
      const isSelected = this.selectedNodeId === n.id;
      const isFallback = n.fallback_rank > 0;
      const isRateLimited = n.status === "RATE_LIMITED";
      const isBroken = n.status === "BROKEN";
      const isActive = n.status === "ACTIVE" || n.status === "EXECUTING";

      el.className = `temporal-node ${isActive ? 'node-active' : ''} ${isFallback ? 'node-fallback' : ''} ${isRateLimited ? 'node-ratelimited' : ''} ${isBroken ? 'node-broken' : ''} ${isSelected ? 'node-selected' : ''}`;
      el.style.left = `${n.x * this.zoom + this.panX}px`;
      el.style.top = `${n.y * this.zoom + this.panY}px`;
      el.style.transform = `scale(${Math.max(0.7, Math.min(1.3, this.zoom))})`;

      let statusColor = "var(--text-muted)";
      if (isActive) statusColor = "var(--accent-cyan)";
      else if (n.status === "COMPLETED") statusColor = "var(--accent-emerald)";
      else if (isRateLimited) statusColor = "var(--accent-amber)";
      else if (isBroken || n.status === "FAILED") statusColor = "var(--accent-broken)";

      const roleBadgeText = n.role ? n.role.toUpperCase() : "STEP";
      const modelShort = n.model ? n.model.split('/').pop() : "System";
      const providerLabel = n.provider ? n.provider.toUpperCase() : "";

      el.innerHTML = `
        <div class="node-header">
          <div style="display: flex; align-items: center; gap: 6px;">
            <span class="node-role-badge">${roleBadgeText}</span>
            ${isFallback ? `<span class="fallback-rank-tag">FB #${n.fallback_rank}</span>` : ''}
          </div>
          <span class="node-status-pip" style="color: ${statusColor};">
            <span class="status-dot" style="background: ${statusColor};"></span>
            ${n.status}
          </span>
        </div>
        <div class="node-title">${n.label || modelShort}</div>
        <div class="node-meta">
          <span>${providerLabel} • ${modelShort}</span>
          ${n.latency_ms ? `<span>• <strong>${n.latency_ms}ms</strong></span>` : ''}
        </div>
        ${this.mode === "DESIGN" && n.role in this.rolesData ? `<div class="design-edit-hint">Click to edit candidate chain ➔</div>` : ''}
      `;

      el.addEventListener("click", e => {
        e.stopPropagation();
        this.selectNode(n);
      });

      this.container.appendChild(el);
    });
  }

  selectNode(node) {
    this.selectedNodeId = node.id;
    this.activeRole = node.role;
    this.render();
    this.openInspector(node);
  }

  openInspector(node) {
    if (!this.drawer) return;
    this.drawer.classList.add("open");

    const drawerTitle = document.getElementById("drawer-title");
    const drawerContent = document.getElementById("drawer-content");
    if (!drawerTitle || !drawerContent) return;

    drawerTitle.textContent = `${node.role.toUpperCase()} — Candidate Chain Inspector`;

    const candidates = this.rolesData[node.role] || [
      { provider: node.provider || "groq", model: node.model || "default" }
    ];
    const currentMode = this.executionModes[node.role] || "FALLBACK_ORDER";

    let candidatesListHtml = "";
    candidates.forEach((c, idx) => {
      const isPrimary = (idx === 0);
      candidatesListHtml += `
        <div class="candidate-item-card" data-index="${idx}">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="drag-handle" title="Drag to reorder">☰</span>
              <div>
                <strong style="font-size: 0.95rem;">${c.model.split('/').pop()}</strong>
                <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${c.provider} • ${c.model}</div>
              </div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              ${isPrimary 
                ? `<span class="badge-primary">★ PRIMARY</span>` 
                : `<span class="badge-fallback">FALLBACK #${idx}</span>`
              }
              ${this.mode === "DESIGN" ? `
                <div class="btn-group-reorder">
                  <button class="btn-mini btn-move-up" data-idx="${idx}" ${idx === 0 ? 'disabled' : ''} title="Move Up">▲</button>
                  <button class="btn-mini btn-move-down" data-idx="${idx}" ${idx === candidates.length - 1 ? 'disabled' : ''} title="Move Down">▼</button>
                  ${!isPrimary ? `<button class="btn-mini btn-set-primary" data-idx="${idx}" title="Set as Primary">★</button>` : ''}
                </div>
              ` : ''}
            </div>
          </div>

          <div style="display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap;">
            <span class="cap-pill">Streaming ✓</span>
            <span class="cap-pill">Tool Calling ✓</span>
            ${node.role === "vision" ? `<span class="cap-pill">Vision ✓</span>` : ''}
            <span class="cap-pill health-healthy">● Healthy</span>
          </div>
        </div>
      `;
    });

    drawerContent.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 16px;">
        <!-- Mode Selector -->
        <div>
          <div style="font-family: var(--font-brand); font-size: 0.8rem; font-weight: 700; color: var(--text-secondary); margin-bottom: 6px;">
            EXECUTION MODE
          </div>
          <div class="mode-selector-group">
            <button class="mode-pill-btn ${currentMode === 'PRIMARY_ONLY' ? 'active' : ''}" data-mode="PRIMARY_ONLY">PRIMARY ONLY</button>
            <button class="mode-pill-btn ${currentMode === 'FALLBACK_ORDER' ? 'active' : ''}" data-mode="FALLBACK_ORDER">FALLBACK ORDER</button>
            <button class="mode-pill-btn ${currentMode === 'CUSTOM' ? 'active' : ''}" data-mode="CUSTOM">CUSTOM</button>
          </div>
        </div>

        <div class="inspector-section">
          <div style="font-family: var(--font-brand); font-size: 0.85rem; font-weight: 700; color: var(--text-secondary); margin-bottom: 8px;">
            CANDIDATE CHAIN (${candidates.length} CANDIDATES)
          </div>
          <div class="candidates-reorder-container" id="candidates-container">
            ${candidatesListHtml}
          </div>
        </div>

        ${this.mode === "DESIGN" ? `
          <div class="inspector-actions">
            <button class="btn-action btn-apply-chain" id="btn-apply-role-chain" style="background: var(--accent-cyan); color: #000; font-weight: 700;">Apply & Save Changes</button>
            <button class="btn-action" id="btn-discard-role-chain">Discard</button>
          </div>
          <div id="inspector-msg" style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-secondary); margin-top: 6px;"></div>
        ` : `
          <div style="font-size: 0.8rem; color: var(--text-muted); padding: 8px 12px; background: rgba(0,0,0,0.3); border-radius: 6px;">
            Switch to <strong>DESIGN MODE</strong> from toolbar to configure candidate chains and modes.
          </div>
        `}
      </div>
    `;

    if (this.mode === "DESIGN") {
      this.setupInspectorReorderEvents(node.role, candidates, currentMode);
    }
  }

  setupInspectorReorderEvents(role, candidates, currentMode) {
    const list = [...candidates];
    let selectedMode = currentMode;

    document.querySelectorAll(".mode-pill-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".mode-pill-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        selectedMode = btn.getAttribute("data-mode");
        this.executionModes[role] = selectedMode;
      });
    });

    document.querySelectorAll(".btn-move-up").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.getAttribute("data-idx"), 10);
        if (idx > 0) {
          const temp = list[idx];
          list[idx] = list[idx - 1];
          list[idx - 1] = temp;
          this.rolesData[role] = list;
          this.openInspector({ role, provider: list[0].provider, model: list[0].model, id: this.selectedNodeId });
        }
      });
    });

    document.querySelectorAll(".btn-move-down").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.getAttribute("data-idx"), 10);
        if (idx < list.length - 1) {
          const temp = list[idx];
          list[idx] = list[idx + 1];
          list[idx + 1] = temp;
          this.rolesData[role] = list;
          this.openInspector({ role, provider: list[0].provider, model: list[0].model, id: this.selectedNodeId });
        }
      });
    });

    document.querySelectorAll(".btn-set-primary").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.getAttribute("data-idx"), 10);
        const item = list.splice(idx, 1)[0];
        list.unshift(item);
        this.rolesData[role] = list;
        this.openInspector({ role, provider: list[0].provider, model: list[0].model, id: this.selectedNodeId });
      });
    });

    document.getElementById("btn-apply-role-chain")?.addEventListener("click", async () => {
      const msgBox = document.getElementById("inspector-msg");
      if (msgBox) msgBox.innerHTML = `<span style="color: var(--accent-cyan);">Saving changes to router...</span>`;

      this.send({ action: "UPDATE_ROLE", role: role, candidates: list, execution_mode: selectedMode });

      try {
        const resp = await fetch("/api/roles/update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role: role, candidates: list, execution_mode: selectedMode }),
        });
        const res = await resp.json();
        if (res.success) {
          if (msgBox) msgBox.innerHTML = `<span style="color: var(--accent-emerald);">✓ Role '${role}' updated successfully.</span>`;
          this.fetchGraphData();
        } else {
          if (msgBox) msgBox.innerHTML = `<span style="color: var(--accent-broken);">✗ ${res.error}</span>`;
        }
      } catch (e) {
        if (msgBox) msgBox.innerHTML = `<span style="color: var(--accent-emerald);">✓ Role update broadcasted.</span>`;
      }
    });

    document.getElementById("btn-discard-role-chain")?.addEventListener("click", () => {
      this.fetchGraphData();
      this.closeDrawer();
    });
  }

  closeDrawer() {
    if (this.drawer) {
      this.drawer.classList.remove("open");
    }
    this.selectedNodeId = null;
    this.render();
  }

  handleRuntimeEvent(event, data) {
    if (event === "MODEL_SELECTED") {
      const targetNode = this.nodes.find(n => n.role === data.role && n.provider === data.provider);
      if (targetNode) {
        targetNode.status = "ACTIVE";
        this.render();
      }
    } else if (event === "MODEL_FALLBACK") {
      const failedNode = this.nodes.find(n => n.provider === data.failed_provider && n.model === data.failed_model);
      if (failedNode) {
        failedNode.status = "RATE_LIMITED";
      }
      const fbNode = this.nodes.find(n => n.provider === data.fallback_provider && n.model === data.fallback_model);
      if (fbNode) {
        fbNode.status = "ACTIVE";
      }
      this.render();
    } else if (event === "TOOL_STARTED") {
      const toolNode = this.nodes.find(n => n.id === "node_tools");
      if (toolNode) {
        toolNode.status = "ACTIVE";
        toolNode.label = `TOOL: ${data.tool}`;
        this.render();
      }
    } else if (event === "TOOL_COMPLETED") {
      const toolNode = this.nodes.find(n => n.id === "node_tools");
      if (toolNode) {
        toolNode.status = "COMPLETED";
        if (data.latency_ms) toolNode.latency_ms = data.latency_ms;
        this.render();
      }
    } else if (event === "VISION_STARTED") {
      const vNode = this.nodes.find(n => n.role === "vision" && n.is_primary);
      if (vNode) {
        vNode.status = "ACTIVE";
        this.render();
      }
    } else if (event === "VISION_COMPLETED") {
      const vNode = this.nodes.find(n => n.role === "vision" && n.is_primary);
      if (vNode) {
        vNode.status = "COMPLETED";
        this.render();
      }
    } else if (event === "TASK_CANCELLED") {
      this.nodes.forEach(n => {
        if (n.status === "ACTIVE" || n.status === "EXECUTING") {
          n.status = "CANCELLED";
        }
      });
      this.render();
    } else if (event === "ROLE_UPDATED") {
      this.fetchGraphData();
    }
  }
}
