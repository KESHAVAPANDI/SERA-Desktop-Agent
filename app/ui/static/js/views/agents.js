/**
 * AgentsView — Multi-Agent Hierarchy & Status Visualizer
 */
export class AgentsView {
  constructor() {
    this.container = document.getElementById("agents-grid");
    this.agents = [
      { id: "planner", name: "Task Planner", role: "Decomposition & Step Ordering", model: "Groq GPT-OSS 120B", status: "READY", tool: "PlanValidator" },
      { id: "desktop", name: "Desktop Automation", role: "Native Windows UI Actions", model: "Mistral Codestral", status: "ACTIVE", tool: "TargetResolver" },
      { id: "vision", name: "Perception Specialist", role: "Multimodal Screen Analysis", model: "Groq Qwen 3.6 27B", status: "READY", tool: "ScreenCapture" },
      { id: "researcher", name: "Fast Researcher", role: "Lightweight Query Synthesis", model: "Mistral Small", status: "READY", tool: "WebSearch" },
      { id: "memory", name: "Memory Engine", role: "Knowledge Retrieval & Indexing", model: "Mistral Embed", status: "READY", tool: "VectorStore" },
      { id: "verifier", name: "Verification Guard", role: "Observe → Act → Verify", model: "System Rulebase", status: "READY", tool: "StateInspector" },
      { id: "synthesizer", name: "Voice Synthesizer", role: "Acoustic TTS Streaming", model: "Fish Audio S2.1", status: "READY", tool: "SentenceBuffer" },
    ];
    this.render();
  }

  render() {
    if (!this.container) return;
    this.container.innerHTML = "";
    this.agents.forEach(a => {
      const card = document.createElement("div");
      card.className = "agent-card";
      card.innerHTML = `
        <div class="agent-card-header">
          <div class="agent-name">${a.name}</div>
          <span class="agent-status-pill">${a.status}</span>
        </div>
        <div style="font-size: 0.8rem; color: var(--text-secondary);">${a.role}</div>
        <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--accent-cyan);">Model: ${a.model}</div>
        <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">Specialist Tool: ${a.tool}</div>
      `;
      this.container.appendChild(card);
    });
  }
}
