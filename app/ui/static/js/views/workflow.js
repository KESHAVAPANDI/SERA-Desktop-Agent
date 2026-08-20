/**
 * WorkflowView — Horizontal Temporal Execution Graph Visualizer
 */
export class WorkflowView {
  constructor() {
    this.container = document.getElementById("workflow-nodes-container");
    this.svg = document.getElementById("workflow-svg");
    this.canvas = document.getElementById("workflow-canvas");
    this.zoom = 1.0;
    this.panX = 40;
    this.panY = 60;
    this.nodes = [
      { id: "input", label: "VOICE / TEXT INPUT", role: "input", model: "NVIDIA Canary-Qwen", x: 40, y: 160, status: "COMPLETED", latency: 210 },
      { id: "router", label: "LOCAL / MODEL ROUTER", role: "router", model: "Intent Engine", x: 280, y: 160, status: "COMPLETED", latency: 5 },
      { id: "primary_llm", label: "PRIMARY REASONING", role: "reasoning", model: "Groq GPT-OSS 120B", x: 540, y: 100, status: "COMPLETED", latency: 380 },
      { id: "fallback_llm", label: "REASONING FALLBACK", role: "reasoning", model: "Mistral Large", x: 540, y: 260, status: "SKIPPED", latency: null },
      { id: "desktop_tool", label: "DESKTOP AUTOMATION", role: "desktop", model: "Codestral Latest", x: 800, y: 100, status: "COMPLETED", latency: 490 },
      { id: "vision_verify", label: "SCREEN PERCEPTION", role: "vision", model: "Groq Qwen 3.6 27B", x: 1060, y: 100, status: "COMPLETED", latency: 410 },
      { id: "tts_output", label: "STREAMING TTS", role: "tts", model: "Fish Audio S2.1", x: 1320, y: 100, status: "ACTIVE", latency: 180 },
    ];
    this.edges = [
      { from: "input", to: "router", type: "primary" },
      { from: "router", to: "primary_llm", type: "primary" },
      { from: "router", to: "fallback_llm", type: "fallback" },
      { from: "primary_llm", to: "desktop_tool", type: "primary" },
      { from: "desktop_tool", to: "vision_verify", type: "primary" },
      { from: "vision_verify", to: "tts_output", type: "primary" },
    ];
    this.init();
  }

  init() {
    this.render();
    this.setupPanZoom();
  }

  render() {
    if (!this.container || !this.svg) return;
    this.container.innerHTML = "";
    this.svg.innerHTML = "";

    // Draw Nodes
    this.nodes.forEach(n => {
      const el = document.createElement("div");
      el.className = `temporal-node ${n.status === "ACTIVE" ? "node-active" : (n.role.includes("fallback") ? "node-fallback" : "")}`;
      el.style.left = `${n.x * this.zoom + this.panX}px`;
      el.style.top = `${n.y * this.zoom + this.panY}px`;
      el.innerHTML = `
        <div class="node-header">
          <span class="node-role-badge">${n.role}</span>
          <span style="font-size: 0.75rem; color: ${n.status === 'ACTIVE' ? 'var(--accent-cyan)' : 'var(--accent-emerald)'}; font-weight: 600;">● ${n.status}</span>
        </div>
        <div class="node-title">${n.label}</div>
        <div class="node-meta">${n.model} ${n.latency ? `• ${n.latency}ms` : ''}</div>
      `;
      this.container.appendChild(el);
    });

    // Draw SVG Curved Connecting Edges
    this.edges.forEach(e => {
      const src = this.nodes.find(n => n.id === e.from);
      const tgt = this.nodes.find(n => n.id === e.to);
      if (src && tgt) {
        const x1 = (src.x + 190) * this.zoom + this.panX;
        const y1 = (src.y + 40) * this.zoom + this.panY;
        const x2 = tgt.x * this.zoom + this.panX;
        const y2 = (tgt.y + 40) * this.zoom + this.panY;
        const dx = (x2 - x1) / 2;

        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`);
        path.setAttribute("stroke", e.type === "fallback" ? "rgba(255, 184, 0, 0.4)" : "rgba(0, 240, 255, 0.5)");
        path.setAttribute("stroke-width", "2");
        path.setAttribute("fill", "none");
        if (e.type === "fallback") {
          path.setAttribute("stroke-dasharray", "4,4");
        }
        this.svg.appendChild(path);
      }
    });
  }

  setupPanZoom() {
    let isDragging = false;
    let startX = 0, startY = 0;

    this.canvas.addEventListener("mousedown", e => {
      isDragging = true;
      startX = e.clientX - this.panX;
      startY = e.clientY - this.panY;
    });

    window.addEventListener("mousemove", e => {
      if (isDragging) {
        this.panX = e.clientX - startX;
        this.panY = e.clientY - startY;
        this.render();
      }
    });

    window.addEventListener("mouseup", () => { isDragging = false; });

    document.getElementById("btn-zoom-in")?.addEventListener("click", () => { this.zoom = Math.min(2.0, this.zoom + 0.15); this.render(); });
    document.getElementById("btn-zoom-out")?.addEventListener("click", () => { this.zoom = Math.max(0.5, this.zoom - 0.15); this.render(); });
    document.getElementById("btn-reset-view")?.addEventListener("click", () => { this.zoom = 1.0; this.panX = 40; this.panY = 60; this.render(); });
  }
}
