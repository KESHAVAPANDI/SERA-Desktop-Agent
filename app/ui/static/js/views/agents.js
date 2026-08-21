/**
 * AgentsView — Agent Studio with Stylized Animated Agent Identities & Delegation Hierarchy
 */

export class AgentsView {
  constructor() {
    this.container = document.getElementById("agents-grid");
    this.selectedAgentId = "agent_core";

    this.agents = [
      {
        id: "agent_core",
        name: "SERA Core Controller",
        role: "Master Orchestrator & Planner",
        is_implemented: true,
        status: "ACTIVE",
        avatar_type: "core",
        model: "openai/gpt-oss-120b",
        provider: "Groq",
        permissions: "Full Orchestration & System State Control",
        memory_scope: "Global Session & Preferences",
        tools: ["IntentRouter", "StateInspector", "SecurityManager", "Delegator"],
        parent: null,
        children: ["agent_desktop", "agent_vision"],
        description: "Deconstructs voice & typed commands, executes intent routing, and dispatches subtasks to specialized desktop and vision agents.",
      },
      {
        id: "agent_desktop",
        name: "Desktop Automation Agent",
        role: "Windows OS & UI Execution Specialist",
        is_implemented: true,
        status: "IDLE",
        avatar_type: "desktop",
        model: "codestral-latest",
        provider: "Mistral",
        permissions: "Windows UI Automation, Process Control, File Operations",
        memory_scope: "Active Window & Desktop Tree Cache",
        tools: ["open_application", "close_application", "set_brightness", "set_volume", "TargetResolver"],
        parent: "agent_core",
        children: [],
        description: "Interacts directly with native Windows UI elements, manages application windows, and executes desktop tools.",
      },
      {
        id: "agent_vision",
        name: "Screen Perception Specialist",
        role: "Multimodal Vision & Visual Verification",
        is_implemented: true,
        status: "IDLE",
        avatar_type: "vision",
        model: "qwen/qwen3.6-27b",
        provider: "Groq",
        permissions: "Screen Capture & OCR Inspection",
        memory_scope: "Visual Viewport Frame Buffer",
        tools: ["ScreenCapture", "Mistral OCR", "StateVerifier"],
        parent: "agent_core",
        children: [],
        description: "Captures screen geometry, detects active UI bounding boxes, and visually verifies desktop state changes.",
      },
      {
        id: "agent_research",
        name: "Deep Research Agent",
        role: "Autonomous Web & Document Synthesizer",
        is_implemented: false,
        status: "PLANNED",
        avatar_type: "research",
        model: "mistral-large-latest",
        provider: "Mistral",
        permissions: "Web Search & External Document Parsing",
        memory_scope: "Episodic Knowledge Index",
        tools: ["WebSearch", "HtmlParser", "CitationsGenerator"],
        parent: "agent_core",
        children: [],
        description: "Autonomously searches the web, parses research documentation, and generates synthesized reports with citations.",
      },
      {
        id: "agent_rag",
        name: "Neural RAG Memory Agent",
        role: "Categorical Semantic Retrieval Specialist",
        is_implemented: false,
        status: "PLANNED",
        avatar_type: "rag",
        model: "mistral-embed",
        provider: "Mistral",
        permissions: "Vector DB Embedding & Chunks Retrieval",
        memory_scope: "Semantic Knowledge Vector Core",
        tools: ["VectorIndex", "SemanticReranker", "ChunkRetriever"],
        parent: "agent_core",
        children: [],
        description: "Indexes local codebases, documents, and preferences into local vector embeddings for low-latency retrieval.",
      },
      {
        id: "agent_mcp",
        name: "MCP Extensibility Gateway",
        role: "Model Context Protocol Hub",
        is_implemented: false,
        status: "PLANNED",
        avatar_type: "mcp",
        model: "mistral-small-latest",
        provider: "Mistral",
        permissions: "External MCP Server Tool Execution",
        memory_scope: "MCP Context Registry",
        tools: ["MCPServerConnector", "JSONRPCDriver"],
        parent: "agent_core",
        children: [],
        description: "Connects SERA to external MCP tool servers (GitHub, SQLite, Filesystem, Browser) via standardized JSON-RPC.",
      },
    ];

    this.render();
  }

  getAvatarSvg(type, status) {
    const isWorking = status === "EXECUTING" || status === "ACTIVE";
    if (type === "core") {
      return `
        <svg class="agent-avatar-svg ${isWorking ? 'anim-core-pulse' : 'anim-core-idle'}" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="42" fill="none" stroke="var(--accent-cyan)" stroke-width="3" stroke-dasharray="6,4"/>
          <circle cx="50" cy="50" r="32" fill="rgba(0, 240, 255, 0.12)" stroke="var(--accent-cyan)" stroke-width="2"/>
          <circle cx="38" cy="44" r="5" fill="var(--accent-cyan)"/>
          <circle cx="62" cy="44" r="5" fill="var(--accent-cyan)"/>
          <path d="M 40 60 Q 50 70 60 60" fill="none" stroke="var(--accent-cyan)" stroke-width="3" stroke-linecap="round"/>
        </svg>
      `;
    } else if (type === "desktop") {
      return `
        <svg class="agent-avatar-svg ${isWorking ? 'anim-typing' : 'anim-idle'}" viewBox="0 0 100 100">
          <rect x="20" y="20" width="60" height="42" rx="6" fill="rgba(157, 0, 255, 0.15)" stroke="var(--accent-violet)" stroke-width="3"/>
          <rect x="28" y="28" width="44" height="26" rx="3" fill="#0c0d14"/>
          <circle cx="40" cy="40" r="3" fill="var(--accent-cyan)"/>
          <circle cx="60" cy="40" r="3" fill="var(--accent-cyan)"/>
          <path d="M 45 47 L 55 47" stroke="var(--accent-violet)" stroke-width="2"/>
          <rect x="30" y="66" width="40" height="12" rx="3" fill="none" stroke="var(--accent-violet)" stroke-width="2"/>
        </svg>
      `;
    } else if (type === "vision") {
      return `
        <svg class="agent-avatar-svg ${isWorking ? 'anim-scanning' : 'anim-idle'}" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="38" fill="rgba(0, 255, 163, 0.1)" stroke="var(--accent-emerald)" stroke-width="3"/>
          <circle cx="50" cy="50" r="22" fill="none" stroke="var(--accent-emerald)" stroke-width="2"/>
          <circle cx="50" cy="50" r="10" fill="var(--accent-emerald)"/>
          <line x1="20" y1="50" x2="80" y2="50" stroke="var(--accent-emerald)" stroke-width="2" stroke-dasharray="3,3"/>
        </svg>
      `;
    } else if (type === "research") {
      return `
        <svg class="agent-avatar-svg anim-idle" viewBox="0 0 100 100">
          <circle cx="44" cy="44" r="24" fill="rgba(255, 184, 0, 0.1)" stroke="var(--accent-amber)" stroke-width="3"/>
          <circle cx="38" cy="40" r="3" fill="var(--accent-amber)"/>
          <circle cx="50" cy="40" r="3" fill="var(--accent-amber)"/>
          <line x1="60" y1="60" x2="82" y2="82" stroke="var(--accent-amber)" stroke-width="5" stroke-linecap="round"/>
        </svg>
      `;
    } else if (type === "rag") {
      return `
        <svg class="agent-avatar-svg anim-idle" viewBox="0 0 100 100">
          <rect x="24" y="20" width="52" height="60" rx="4" fill="rgba(0, 240, 255, 0.08)" stroke="var(--accent-cyan)" stroke-width="2.5"/>
          <line x1="34" y1="34" x2="66" y2="34" stroke="var(--accent-cyan)" stroke-width="2.5"/>
          <line x1="34" y1="46" x2="66" y2="46" stroke="var(--accent-cyan)" stroke-width="2.5"/>
          <line x1="34" y1="58" x2="54" y2="58" stroke="var(--accent-cyan)" stroke-width="2.5"/>
        </svg>
      `;
    } else {
      return `
        <svg class="agent-avatar-svg anim-idle" viewBox="0 0 100 100">
          <polygon points="50,16 80,34 80,68 50,86 20,68 20,34" fill="rgba(255, 0, 85, 0.1)" stroke="var(--accent-broken)" stroke-width="2.5"/>
          <circle cx="50" cy="51" r="12" fill="none" stroke="var(--accent-broken)" stroke-width="2"/>
        </svg>
      `;
    }
  }

  render() {
    if (!this.container) return;
    this.container.innerHTML = "";

    // 1. Hierarchy Tree Bar
    const treeBar = document.createElement("div");
    treeBar.className = "agent-tree-bar";
    treeBar.innerHTML = `
      <div class="tree-node parent">SERA CORE (Orchestrator)</div>
      <div class="tree-branch-line"></div>
      <div class="tree-children-row">
        <div class="tree-node child active-agent">Desktop Agent (UIA)</div>
        <div class="tree-node child active-agent">Vision Agent (OCR)</div>
        <div class="tree-node child planned-agent">Research Agent (Planned)</div>
        <div class="tree-node child planned-agent">RAG Memory (Planned)</div>
        <div class="tree-node child planned-agent">MCP Hub (Planned)</div>
      </div>
    `;
    this.container.appendChild(treeBar);

    // 2. Agents Grid
    const grid = document.createElement("div");
    grid.className = "agent-grid-inner";

    this.agents.forEach(agent => {
      const card = document.createElement("div");
      const isSelected = this.selectedAgentId === agent.id;
      const isImplemented = agent.is_implemented;

      card.className = `agent-studio-card ${isSelected ? 'selected' : ''} ${!isImplemented ? 'planned-card' : ''}`;
      
      const badgeHtml = isImplemented 
        ? `<span class="agent-status-tag status-active">● RUNTIME READY</span>`
        : `<span class="agent-status-tag status-planned">◌ PLANNED</span>`;

      const toolsPills = agent.tools.map(t => `<span class="cap-pill">${t}</span>`).join(" ");

      card.innerHTML = `
        <div class="agent-card-top">
          <div class="agent-avatar-frame">
            ${this.getAvatarSvg(agent.avatar_type, agent.status)}
          </div>
          <div class="agent-header-meta">
            <div class="agent-card-title">${agent.name}</div>
            <div class="agent-role-subtitle">${agent.role}</div>
            <div style="margin-top: 4px;">${badgeHtml}</div>
          </div>
        </div>

        <div class="agent-desc-box">${agent.description}</div>

        <div class="agent-spec-row">
          <span>Assigned Model:</span>
          <strong>${agent.provider} • ${agent.model.split('/').pop()}</strong>
        </div>

        <div class="agent-spec-row">
          <span>Memory Scope:</span>
          <span>${agent.memory_scope}</span>
        </div>

        <div class="agent-tools-container">
          <div style="font-family: var(--font-brand); font-size: 0.7rem; color: var(--text-muted); font-weight: 700; margin-bottom: 4px;">CAPABILITIES & TOOLS:</div>
          <div style="display: flex; gap: 4px; flex-wrap: wrap;">${toolsPills}</div>
        </div>

        <div class="agent-card-actions">
          <button class="btn-mini btn-inspect-agent" data-id="${agent.id}">Inspect Spec</button>
          ${isImplemented 
            ? `<button class="btn-mini btn-test-agent" data-id="${agent.id}">Test Subagent</button>`
            : `<button class="btn-mini" disabled style="opacity: 0.5;">Coming Soon</button>`
          }
        </div>
      `;

      card.addEventListener("click", () => {
        this.selectedAgentId = agent.id;
        this.render();
      });

      grid.appendChild(card);
    });

    this.container.appendChild(grid);
  }
}
