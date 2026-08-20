/**
 * HistoryView — Chronological Session Stream & Replay
 */
export class HistoryView {
  constructor(viewSwitcher) {
    this.container = document.getElementById("history-stream");
    this.switchView = viewSwitcher;
    this.sessions = [
      {
        id: "s1",
        time: "01:28:10",
        date: "Today",
        query: "Open Chrome and search for RTX 5090 benchmarks",
        pipeline: "STT (Canary-Qwen) ➔ Router ➔ Desktop (Codestral) ➔ Browser ➔ Vision (Qwen) ➔ Verify ➔ TTS",
        duration: "1.42s",
        models: ["Canary-Qwen", "Codestral", "Qwen 3.6 27B", "Fish Audio"],
        status: "COMPLETED",
      },
      {
        id: "s2",
        time: "01:15:22",
        date: "Today",
        query: "Set brightness to 40%",
        pipeline: "Local Intent ➔ Direct OS Tool (set_brightness) ➔ TTS",
        duration: "0.31s",
        models: ["Canary-Qwen", "Fish Audio"],
        status: "COMPLETED",
      },
      {
        id: "s3",
        time: "00:45:18",
        date: "Today",
        query: "Explain Python memory management and garbage collection",
        pipeline: "STT ➔ Router ➔ Reasoning (Groq GPT-OSS 120B) ➔ Streaming TTS",
        duration: "1.06s",
        models: ["Canary-Qwen", "Groq GPT-OSS 120B", "Fish Audio"],
        status: "COMPLETED",
      },
    ];
    this.render();
  }

  render() {
    if (!this.container) return;
    this.container.innerHTML = "";
    this.sessions.forEach(s => {
      const card = document.createElement("div");
      card.className = "history-session-card";
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <strong style="font-size: 1rem; color: var(--text-primary);">${s.query}</strong>
          <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${s.date} • ${s.time}</span>
        </div>
        <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--accent-cyan);">${s.pipeline}</div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-secondary);">Duration: ${s.duration} • Models: ${s.models.join(', ')}</span>
          <div class="history-actions">
            <button class="btn-action btn-replay" data-action="replay">Replay Visualization</button>
            <button class="btn-action" data-action="rerun">Run Again</button>
          </div>
        </div>
      `;

      card.querySelector('[data-action="replay"]')?.addEventListener("click", () => {
        if (this.switchView) this.switchView("workflow");
      });

      this.container.appendChild(card);
    });
  }
}
