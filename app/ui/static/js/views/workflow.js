/**
 * WorkflowView — Dynamic Temporal Execution Theater & Plasma Pipeline Engine
 * Phase 5D.4: Real-time event-driven node materialization, multi-filament plasma channels,
 * directional energy flow, fallback ignition, and cancellation collapse on a pure black canvas.
 */

export class WorkflowView {
  constructor(socketSender, onNavigate) {
    this.send = socketSender;
    this.onNavigate = onNavigate;

    // DOM Elements
    this.canvas = document.getElementById("workflow-canvas");
    this.viewport = document.getElementById("canvas-viewport");
    this.nodesContainer = document.getElementById("workflow-nodes-container");
    this.svg = document.getElementById("workflow-svg");
    this.canvasBg = document.getElementById("temporal-canvas-bg");
    this.taskLabel = document.getElementById("workflow-task-label");
    this.stepBadge = document.getElementById("workflow-step-badge");
    this.stepLabel = document.getElementById("workflow-step-label");
    this.executionBanner = document.getElementById("workflow-execution-banner");
    this.bannerSummary = document.getElementById("banner-task-summary");
    this.zoomText = document.getElementById("zoom-level-text");
    this.container = document.getElementById("temporal-theater-container");

    // Canvas Transform State
    this.scale = 1.0;
    this.panX = 80;
    this.panY = 160;
    this.isPanning = false;

    // Dynamic Execution Graph State
    this.activeTaskId = null;
    this.currentTurnId = null;
    this.nodes = []; // Array of dynamically materialized node objects
    this.edges = []; // Array of dynamically materialized edge objects
    this.activeNodeId = null;
    this.activeEdgeId = null;

    // Plasma Animation State
    this.animFrameId = null;
    this.particleOffset = 0;
    this.ambientParticles = [];

    this.init();
  }

  init() {
    this.setupPanZoom();
    this.setupHUDControls();
    this.setupPlasmaDefs();
    this.initAmbientCanvas();
    this.startPlasmaAnimation();
  }

  setupHUDControls() {
    // 1. Return to Live
    const returnLive = () => {
      this.executionBanner?.classList.add("hidden");
      if (this.onNavigate) {
        this.onNavigate("live");
      } else if (window.SERA_APP) {
        window.SERA_APP.switchView("live");
      } else {
        document.getElementById("tab-live")?.click();
      }
    };

    document.getElementById("btn-return-to-live")?.addEventListener("click", returnLive);
    document.getElementById("btn-banner-return-live")?.addEventListener("click", returnLive);

    // 2. Zoom Controls
    document.getElementById("btn-zoom-in")?.addEventListener("click", () => this.zoomAt(1.15));
    document.getElementById("btn-zoom-out")?.addEventListener("click", () => this.zoomAt(0.85));
    document.getElementById("btn-reset-view")?.addEventListener("click", () => {
      this.scale = 1.0;
      this.panX = 80;
      this.panY = 160;
      this.updateViewportTransform();
    });
    document.getElementById("btn-fit-screen")?.addEventListener("click", () => this.fitToScreen());
    document.getElementById("btn-center-active")?.addEventListener("click", () => this.centerOnActiveNode());
  }

  setupPanZoom() {
    let startX = 0, startY = 0;

    this.canvas?.addEventListener("mousedown", e => {
      if (e.target.closest(".workflow-theater-hud") || e.target.closest("#workflow-execution-banner")) return;
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

  zoomAt(factor) {
    this.scale = Math.min(Math.max(this.scale * factor, 0.4), 2.2);
    this.updateViewportTransform();
  }

  updateViewportTransform() {
    if (this.viewport) {
      this.viewport.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
    }
    if (this.zoomText) {
      this.zoomText.textContent = `${Math.round(this.scale * 100)}%`;
    }
  }

  fitToScreen() {
    if (this.nodes.length === 0) return;
    const minX = Math.min(...this.nodes.map(n => n.x));
    const maxX = Math.max(...this.nodes.map(n => n.x + 220));
    const minY = Math.min(...this.nodes.map(n => n.y));
    const maxY = Math.max(...this.nodes.map(n => n.y + 80));

    const w = maxX - minX + 160;
    const h = maxY - minY + 160;
    const canvasW = this.canvas?.clientWidth || 1200;
    const canvasH = this.canvas?.clientHeight || 800;

    this.scale = Math.min(Math.max(Math.min(canvasW / w, canvasH / h), 0.5), 1.2);
    this.panX = (canvasW - (maxX + minX) * this.scale) / 2;
    this.panY = (canvasH - (maxY + minY) * this.scale) / 2;
    this.updateViewportTransform();
  }

  centerOnActiveNode() {
    const activeNode = this.nodes.find(n => n.id === this.activeNodeId) || this.nodes[this.nodes.length - 1];
    if (!activeNode) return;
    const canvasW = this.canvas?.clientWidth || 1200;
    const canvasH = this.canvas?.clientHeight || 800;
    this.panX = canvasW / 2 - (activeNode.x + 110) * this.scale;
    this.panY = canvasH / 2 - (activeNode.y + 40) * this.scale;
    this.updateViewportTransform();
  }

  /* ===================================================================
     SVG PLASMA DEFINITIONS & AMBIENT CANVAS
     =================================================================== */

  setupPlasmaDefs() {
    if (!this.svg) return;
    this.svg.innerHTML = `
      <defs>
        <!-- Luminous Glow Filter for Plasma Core & Filaments -->
        <filter id="plasma-glow-cyan" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="4" result="blur1" />
          <feGaussianBlur stdDeviation="10" result="blur2" />
          <feMerge>
            <feMergeNode in="blur2" />
            <feMergeNode in="blur1" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="plasma-glow-amber" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <filter id="plasma-glow-crimson" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="6" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <g id="plasma-edges-group"></g>
      <g id="plasma-particles-group"></g>
    `;
  }

  initAmbientCanvas() {
    if (!this.canvasBg) return;
    const ctx = this.canvasBg.getContext("2d");
    if (!ctx) return;

    this.resizeCanvasBg();
    window.addEventListener("resize", () => this.resizeCanvasBg());

    // Create subtle ambient particles
    this.ambientParticles = [];
    for (let i = 0; i < 35; i++) {
      this.ambientParticles.push({
        x: Math.random() * (this.canvasBg.width || 1400),
        y: Math.random() * (this.canvasBg.height || 900),
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        radius: Math.random() * 1.5 + 0.5,
        alpha: Math.random() * 0.2 + 0.05,
      });
    }
  }

  resizeCanvasBg() {
    if (!this.canvasBg || !this.canvas) return;
    this.canvasBg.width = this.canvas.clientWidth;
    this.canvasBg.height = this.canvas.clientHeight;
  }

  startPlasmaAnimation() {
    const renderFrame = () => {
      this.particleOffset = (this.particleOffset + 1.2) % 1000;
      this.updateAmbientCanvas();
      this.updatePlasmaEdges();
      this.animFrameId = requestAnimationFrame(renderFrame);
    };
    renderFrame();
  }

  updateAmbientCanvas() {
    if (!this.canvasBg) return;
    const ctx = this.canvasBg.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, this.canvasBg.width, this.canvasBg.height);

    // Draw dark radial energy vignette
    const grad = ctx.createRadialGradient(
      this.canvasBg.width / 2, this.canvasBg.height / 2, 80,
      this.canvasBg.width / 2, this.canvasBg.height / 2, this.canvasBg.width * 0.7
    );
    grad.addColorStop(0, "rgba(0, 240, 255, 0.03)");
    grad.addColorStop(0.5, "rgba(8, 12, 22, 0.4)");
    grad.addColorStop(1, "rgba(2, 4, 8, 0.95)");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, this.canvasBg.width, this.canvasBg.height);

    // Draw subtle floating ambient energy particles
    this.ambientParticles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0) p.x = this.canvasBg.width;
      if (p.x > this.canvasBg.width) p.x = 0;
      if (p.y < 0) p.y = this.canvasBg.height;
      if (p.y > this.canvasBg.height) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0, 240, 255, ${p.alpha})`;
      ctx.fill();
    });
  }

  /* ===================================================================
     DYNAMIC EVENT-DRIVEN GRAPH MATERIALIZATION
     =================================================================== */

  resetGraph(taskTitle = "Executing Task", taskId = null) {
    this.activeTaskId = taskId || `task_${Date.now()}`;
    this.nodes = [];
    this.edges = [];
    this.activeNodeId = null;
    this.activeEdgeId = null;

    if (this.nodesContainer) this.nodesContainer.innerHTML = "";
    if (this.taskLabel) this.taskLabel.textContent = taskTitle;
    if (this.stepBadge) this.stepBadge.classList.remove("hidden");
    if (this.executionBanner) this.executionBanner.classList.add("hidden");

    this.panX = 80;
    this.panY = 240;
    this.updateViewportTransform();
  }

  handleRuntimeEvent(eventType, data = {}) {
    // 1. Task Started / Voice Activation
    if (eventType === "TASK_STARTED" || eventType === "ACTIVATION_STARTED") {
      const prompt = data.user_input || data.prompt || (data.source ? `Voice Command (${data.source})` : "Executing Task");
      this.resetGraph(prompt, data.task_id);

      // Materialize STT
      this.materializeNode({
        id: "node_stt",
        label: "STT INPUT",
        sub: data.source === "VOICE" ? "NVIDIA Canary-Qwen" : "User Prompt",
        status: "ACTIVE",
        role: "stt",
        x: 40,
        y: 180,
      });

      // Materialize Router
      setTimeout(() => {
        this.materializeNode({
          id: "node_router",
          label: "INTENT ROUTER",
          sub: "Intent & Policy Dispatch",
          status: "ACTIVE",
          role: "router",
          x: 280,
          y: 180,
        });
        this.materializeEdge("e_stt_router", "node_stt", "node_router", "ACTIVE");
        this.updateStep(1, 4, "Routing Intent");
      }, 200);
    }

    // 2. Model Selection
    else if (eventType === "MODEL_SELECTED") {
      const modelId = `node_model_${data.role || 'reasoning'}`;
      const aliasIds = [];
      if (data.provider) aliasIds.push(`node_model_${data.provider.toLowerCase()}`);
      this.materializeNode({
        id: modelId,
        aliasIds: aliasIds,
        label: `${(data.role || 'REASONING').toUpperCase()}`,
        sub: `${data.provider} • ${data.model ? data.model.split('/').pop() : 'Model'}`,
        status: "ACTIVE",
        role: data.role || "reasoning",
        x: 520,
        y: 180,
      });
      this.materializeEdge(`e_router_${modelId}`, "node_router", modelId, "ACTIVE");
      this.updateStep(2, 4, `Selected ${data.model || 'Model'}`);
    }

    // 3. Model Fallback / Rate Limited
    else if (eventType === "MODEL_FALLBACK" || eventType === "MODEL_RATE_LIMITED") {
      const primaryNode = this.nodes.find(n => n.role === data.role) || this.nodes[this.nodes.length - 1];
      if (primaryNode) {
        primaryNode.status = "RATE_LIMITED";
        const el = document.getElementById(primaryNode.id);
        if (el) el.className = "temporal-theater-node rate-limited";
      }

      // Materialize Fallback Node
      const fallbackId = `node_model_${data.role || 'reasoning'}_fallback`;
      this.materializeNode({
        id: fallbackId,
        label: `FALLBACK: ${(data.role || 'REASONING').toUpperCase()}`,
        sub: `${data.provider} • ${data.model ? data.model.split('/').pop() : 'Fallback'}`,
        status: "FALLBACK_ACTIVE",
        role: data.role || "reasoning",
        x: 520,
        y: 300,
      });

      if (primaryNode) {
        this.materializeEdge(`e_fb_${fallbackId}`, primaryNode.id, fallbackId, "FALLBACK");
      }
    }

    // 4. Tool Execution / Screen Perception
    else if (eventType === "TOOL_STARTED" || eventType === "SCREEN_CAPTURE_STARTED" || eventType === "VISION_STARTED") {
      const toolName = data.tool || (eventType === "SCREEN_CAPTURE_STARTED" ? "capture_screen" : (eventType === "VISION_STARTED" ? "inspect_screen" : "tool"));
      const toolId = `node_tool_${toolName}`;
      const aliasIds = [];
      if (eventType === "SCREEN_CAPTURE_STARTED" || eventType === "VISION_STARTED" || toolName === "capture_screen" || toolName === "inspect_screen") {
        aliasIds.push("node_vision");
      }

      this.materializeNode({
        id: toolId,
        aliasIds: aliasIds,
        label: toolName.toUpperCase().replace(/_/g, " "),
        sub: data.arguments?.query ? `Query: ${data.arguments.query}` : "Executing Action",
        status: "ACTIVE",
        role: "tool",
        x: 760,
        y: 180,
      });

      const prevNode = this.nodes[this.nodes.length - 2];
      if (prevNode) {
        this.materializeEdge(`e_model_tool`, prevNode.id, toolId, "ACTIVE");
      }
      this.updateStep(3, 4, `Executing ${toolName}`);
    }

    // 5. Tool Completed / Screen Captured
    else if (eventType === "TOOL_COMPLETED" || eventType === "SCREEN_CAPTURED") {
      const toolNode = this.nodes.find(n => n.role === "tool") || this.nodes[this.nodes.length - 1];
      if (toolNode) {
        toolNode.status = "COMPLETED";
        const el = document.getElementById(toolNode.id);
        if (el) el.className = "temporal-theater-node completed";
      }

      // Materialize Verification Node
      this.materializeNode({
        id: "node_verify",
        label: "VERIFY & SYNTHESIZE",
        sub: `Latency: ${data.latency_ms || 180}ms`,
        status: "ACTIVE",
        role: "verify",
        x: 1000,
        y: 180,
      });

      if (toolNode) {
        this.materializeEdge("e_tool_verify", toolNode.id, "node_verify", "ACTIVE");
      }
    }

    // 6. Agent Response / TTS
    else if (eventType === "AGENT_RESPONSE" || eventType === "TTS_STARTED") {
      this.materializeNode({
        id: "node_tts",
        label: "STREAMING TTS",
        sub: "Fish Audio S2.1",
        status: "ACTIVE",
        role: "tts",
        x: 1240,
        y: 180,
      });

      const verifyNode = this.nodes.find(n => n.id === "node_verify") || this.nodes[this.nodes.length - 2];
      if (verifyNode) {
        this.materializeEdge("e_verify_tts", verifyNode.id, "node_tts", "ACTIVE");
      }
      this.updateStep(4, 4, "Synthesizing Audio");
    }

    // 7. Task Completed
    else if (eventType === "TASK_COMPLETED") {
      this.nodes.forEach(n => {
        n.status = "COMPLETED";
        const el = document.getElementById(n.id);
        if (el) el.className = "temporal-theater-node completed";
      });
      this.edges.forEach(e => e.status = "COMPLETED");
      this.renderEdges();

      if (this.taskLabel) this.taskLabel.textContent = "✓ COMPLETED";
      if (this.executionBanner) {
        if (this.bannerSummary && data.result) {
          this.bannerSummary.textContent = typeof data.result === "string" ? data.result : "Task execution completed successfully.";
        }
        this.executionBanner.classList.remove("hidden");
      }
    }

    // 8. Task Cancelled
    else if (eventType === "TASK_CANCELLED") {
      this.nodes.forEach(n => {
        if (n.status === "ACTIVE") n.status = "CANCELLED";
        const el = document.getElementById(n.id);
        if (el) el.className = "temporal-theater-node cancelled";
      });
      this.edges = [];
      this.renderEdges();
      this.canvas?.classList.add("cancelled");
      if (this.taskLabel) this.taskLabel.textContent = "✕ CANCELLED BY USER";
    }

    // 9. Task Failed / Broken
    else if (eventType === "TASK_FAILED" || eventType === "TOOL_FAILED") {
      const activeNode = this.nodes.find(n => n.status === "ACTIVE") || this.nodes[this.nodes.length - 1];
      if (activeNode) {
        activeNode.status = "BROKEN";
        const el = document.getElementById(activeNode.id);
        if (el) el.className = "temporal-theater-node broken";
      }
      if (this.taskLabel) this.taskLabel.textContent = `✗ BROKEN: ${data.error || ''}`;
    }
  }

  materializeNode(nodeData) {
    if (this.nodes.some(n => n.id === nodeData.id)) return;
    this.nodes.push(nodeData);
    this.activeNodeId = nodeData.id;

    const el = document.createElement("div");
    el.id = nodeData.id;
    el.className = `temporal-theater-node ${nodeData.status ? nodeData.status.toLowerCase() : 'active'}`;
    el.style.left = `${nodeData.x}px`;
    el.style.top = `${nodeData.y}px`;

    let aliasHtml = "";
    if (nodeData.aliasIds && Array.isArray(nodeData.aliasIds)) {
      aliasHtml = nodeData.aliasIds.map(aid => `<span id="${aid}" class="hidden"></span>`).join("");
    }

    el.innerHTML = `
      <div class="node-aura-pulse"></div>
      <div class="node-content-box">
        <div class="node-label-row">
          <span class="node-status-dot"></span>
          <span class="node-label">${nodeData.label}</span>
        </div>
        <div class="node-sub">${nodeData.sub || ''}</div>
      </div>
      ${aliasHtml}
    `;

    this.nodesContainer?.appendChild(el);
    this.renderEdges();
    this.centerOnActiveNode();
  }

  materializeEdge(id, fromId, toId, status = "ACTIVE") {
    if (this.edges.some(e => e.id === id)) return;
    this.edges.push({ id, source: fromId, target: toId, status });
    this.activeEdgeId = id;
    this.renderEdges();
  }

  updateStep(current, total, label) {
    if (this.stepLabel) {
      this.stepLabel.textContent = `Step ${current}/${total}: ${label}`;
    }
  }

  /* ===================================================================
     PLASMA PIPELINES RENDERER
     =================================================================== */

  renderEdges() {
    const edgesGroup = this.svg?.querySelector("#plasma-edges-group");
    if (!edgesGroup) return;
    edgesGroup.innerHTML = "";

    this.edges.forEach(edge => {
      const fromEl = document.getElementById(edge.source);
      const toEl = document.getElementById(edge.target);
      if (!fromEl || !toEl) return;

      const fx = parseInt(fromEl.style.left) + fromEl.offsetWidth;
      const fy = parseInt(fromEl.style.top) + fromEl.offsetHeight / 2;
      const tx = parseInt(toEl.style.left);
      const ty = parseInt(toEl.style.top) + toEl.offsetHeight / 2;

      const dx = (tx - fx) * 0.5;
      const d = `M ${fx} ${fy} C ${fx + dx} ${fy}, ${tx - dx} ${ty}, ${tx} ${ty}`;

      // 1. Plasma Outer Glow Strand
      const outerPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      outerPath.setAttribute("d", d);
      outerPath.setAttribute("class", `plasma-strand-outer ${edge.status ? edge.status.toLowerCase() : 'active'}`);
      edgesGroup.appendChild(outerPath);

      // 2. Plasma Multi-Filaments (Thin energy threads)
      [-2, 2].forEach(offset => {
        const filPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const filD = `M ${fx} ${fy + offset} C ${fx + dx} ${fy - offset}, ${tx - dx} ${ty + offset}, ${tx} ${ty}`;
        filPath.setAttribute("d", filD);
        filPath.setAttribute("class", `plasma-filament ${edge.status ? edge.status.toLowerCase() : 'active'}`);
        edgesGroup.appendChild(filPath);
      });

      // 3. Plasma Core Luminous Line
      const corePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      corePath.setAttribute("d", d);
      corePath.setAttribute("class", `plasma-core ${edge.status ? edge.status.toLowerCase() : 'active'}`);
      edgesGroup.appendChild(corePath);
    });
  }

  updatePlasmaEdges() {
    const particlesGroup = this.svg?.querySelector("#plasma-particles-group");
    if (!particlesGroup) return;
    particlesGroup.innerHTML = "";

    // Draw active directional energy pulses traveling along active edges
    this.edges.forEach(edge => {
      if (edge.status !== "ACTIVE" && edge.status !== "FALLBACK") return;

      const fromEl = document.getElementById(edge.source);
      const toEl = document.getElementById(edge.target);
      if (!fromEl || !toEl) return;

      const fx = parseInt(fromEl.style.left) + fromEl.offsetWidth;
      const fy = parseInt(fromEl.style.top) + fromEl.offsetHeight / 2;
      const tx = parseInt(toEl.style.left);
      const ty = parseInt(toEl.style.top) + toEl.offsetHeight / 2;

      // Calculate directional bezier interpolation
      const t = (this.particleOffset % 100) / 100;
      const u = 1 - t;
      const cx1 = fx + (tx - fx) * 0.5;
      const cy1 = fy;
      const cx2 = tx - (tx - fx) * 0.5;
      const cy2 = ty;

      const px = u * u * u * fx + 3 * u * u * t * cx1 + 3 * u * t * t * cx2 + t * t * t * tx;
      const py = u * u * u * fy + 3 * u * u * t * cy1 + 3 * u * t * t * cy2 + t * t * t * ty;

      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", px);
      circle.setAttribute("cy", py);
      circle.setAttribute("r", "3.5");
      circle.setAttribute("class", `plasma-energy-particle ${edge.status === 'FALLBACK' ? 'fallback' : ''}`);
      particlesGroup.appendChild(circle);
    });
  }

  // Compatibility helper for legacy callers
  updateGraphData() {}
  highlightModel() {}
}
