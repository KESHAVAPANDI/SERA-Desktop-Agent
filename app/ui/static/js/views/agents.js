/**
 * AgentsView — Multi-Agent Hierarchy & Delegated Work Executors
 */

export class AgentsView {
  constructor() {
    this.container = document.getElementById("agents-grid");
    this.agents = [
      {
        id: "agent_core",
        name: "SERA Core Controller",
        role: "Primary Orchestrator",
        status: "ACTIVE",
        model: "openai/gpt-oss-120b",
        provider: "Groq",
        tools: ["Router", "StateInspector", "SecurityManager"],
        children: ["agent_desktop", "agent_vision", "agent_research"],
        description: "Deconstructs voice & typed commands, plans step sequences, and delegates specialized subtasks.",
      },
      {
        id: "agent_desktop",
        name: "Desktop Automation Agent",
        role: "OS & UI Specialist",
        status: "IDLE",
        model: "codestral-latest",
        provider: "Mistral",
        tools: ["Windows UI Automation", "open_application", "click_ui_element", "set_ui_input_text"],
        children: [],
        description: "Interacts directly with native Windows UI elements, manages application windows, and executes desktop tools.",
      },
      {
        id: "agent_vision",
        name: "Screen Perception Specialist",
        role: "Multimodal Vision & OCR",
        status: "IDLE",
        model: "qwen/qwen3.6-27b",
        provider: "Groq",
        tools: ["ScreenCapture", "TargetResolver", "Mistral OCR"],
        children: [],
        description: "Captures screen geometry, detects active UI bounding boxes, and visually verifies desktop state changes.",
      },
      {
        id: "agent_research",
        name: "Knowledge & RAG Agent (Future)",
        role: "Retrieval & Research Specialist",
        status: "STANDBY",
        model: "mistral-large-latest",
        provider: "Mistral",
        tools: ["MemoryCore", "DocumentRetriever", "VectorSearch"],
        children: [],
        description: "Queries categorical neural memory and retrieves relevant project documentation and semantic context.",
      },
    ];

    this.render();
  }

  render() {
    if (!this.container) return;
    this.container.innerHTML = "";

    this.agents.forEach(agent => {
      const card = document.createElement("div");
      card.className = "agent-card";

      const toolsPills = agent.tools.map(t => `<span class="cap-pill">${t}</span>`).join(" ");
      const childrenHtml = agent.children.length > 0
        ? `<div style="font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted); margin-top: 6px;">Delegates To: ${agent.children.join(", ")}</div>`
        : "";

      card.innerHTML = `
        <div class="agent-card-header">
          <div>
            <div class="agent-name">${agent.name}</div>
            <div style="font-family: var(--font-brand); font-size: 0.75rem; color: var(--accent-violet); font-weight: 600;">${agent.role}</div>
          </div>
          <span class="agent-status-pill">${agent.status}</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.4;">${agent.description}</div>
        <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">
          Model: <strong style="color: var(--text-primary);">${agent.provider} • ${agent.model.split('/').pop()}</strong>
        </div>
        <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
          ${toolsPills}
        </div>
        ${childrenHtml}
      `;

      this.container.appendChild(card);
    });
  }
}
