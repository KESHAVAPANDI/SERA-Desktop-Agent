/**
 * DebugView — Real-Time Telemetry & EventBus Trace
 */
export class DebugView {
  constructor() {
    this.traceBox = document.getElementById("event-trace-box");
    this.latencyBox = document.getElementById("latency-telemetry-box");
    this.init();
  }

  init() {
    this.renderLatencyWaterfall([
      { stage: "STT Input Latency (NVIDIA Canary-Qwen)", latency: 210, color: "var(--accent-cyan)" },
      { stage: "Model Router Decision", latency: 5, color: "var(--accent-emerald)" },
      { stage: "Reasoning LLM TTFT (Groq GPT-OSS 120B)", latency: 110, color: "var(--accent-violet)" },
      { stage: "Desktop Tool Execution (Codestral)", latency: 490, color: "var(--accent-cyan)" },
      { stage: "Vision Perception (Groq Qwen 3.6 27B)", latency: 410, color: "var(--accent-violet)" },
      { stage: "TTS First Audio TTFA (Fish Audio)", latency: 180, color: "var(--accent-emerald)" },
    ]);
    this.logEvent("RUNTIME_READY", { hotkey: "ctrl+space", wake_word: "SERA" });
    this.logEvent("MODEL_ROUTER_ONLINE", { roles: 6, primary: "groq/gpt-oss-120b" });
  }

  renderLatencyWaterfall(items) {
    if (!this.latencyBox) return;
    this.latencyBox.innerHTML = "";
    items.forEach(i => {
      const row = document.createElement("div");
      row.style.display = "flex";
      row.style.justifyContent = "space-between";
      row.style.padding = "6px 10px";
      row.style.background = "var(--bg-secondary)";
      row.style.borderRadius = "6px";
      row.innerHTML = `
        <span style="color: var(--text-primary);">${i.stage}</span>
        <strong style="color: ${i.color};">${i.latency} ms</strong>
      `;
      this.latencyBox.appendChild(row);
    });
  }

  logEvent(name, data) {
    if (!this.traceBox) return;
    const timeStr = new Date().toISOString().split("T")[1].slice(0, 8);
    const line = document.createElement("div");
    line.style.marginBottom = "4px";
    line.innerHTML = `<span style="color: var(--text-muted);">${timeStr}</span> <span style="color: var(--accent-cyan);">[${name}]</span> ${JSON.stringify(data)}`;
    this.traceBox.appendChild(line);
    this.traceBox.scrollTop = this.traceBox.scrollHeight;
  }
}
