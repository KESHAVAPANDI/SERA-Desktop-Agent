/**
 * HistoryView — Chronological Session Timeline, Turn Pipelines & Replay Actions
 */

export class HistoryView {
  constructor(onReplayWorkflow) {
    this.container = document.getElementById("history-stream");
    this.onReplayWorkflow = onReplayWorkflow;
    this.sessions = [];
    this.init();
  }

  async init() {
    await this.fetchHistory();
  }

  async fetchHistory() {
    try {
      const resp = await fetch("/api/history");
      if (resp.ok) {
        this.sessions = await resp.json();
        this.render();
      }
    } catch (e) {
      console.warn("[HistoryView] Failed to fetch history sessions.");
    }
  }

  async rerunTask(query) {
    try {
      await fetch("/api/history/rerun", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query }),
      });
      if (this.onReplayWorkflow) this.onReplayWorkflow("live");
    } catch (e) {
      console.warn("[HistoryView] Task rerun failed:", e);
    }
  }

  render() {
    if (!this.container) return;
    this.container.innerHTML = "";

    this.sessions.forEach(sess => {
      const card = document.createElement("div");
      card.className = "history-session-card";

      const stepsHtml = sess.steps.map(s => `
        <div style="display: flex; justify-content: space-between;">
          <span>Step ${s.step}: ${s.action}</span>
          <span style="color: var(--text-muted);">${s.duration_ms}ms</span>
        </div>
      `).join("");

      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${sess.date} • ${sess.time}</span>
          <span class="cap-pill health-healthy">${sess.status} (${sess.total_duration})</span>
        </div>
        <div class="history-query-text">"${sess.query}"</div>
        <div class="history-pipeline-tag">${sess.pipeline}</div>
        <div class="history-steps-list">${stepsHtml}</div>
        <div class="history-actions">
          <button class="btn-action btn-replay" data-id="${sess.session_id}">Replay Visualization</button>
          <button class="btn-action btn-rerun" data-query="${sess.query}">Run Again ➔</button>
        </div>
      `;

      card.querySelector(".btn-replay")?.addEventListener("click", () => {
        if (this.onReplayWorkflow) this.onReplayWorkflow("workflow");
      });

      card.querySelector(".btn-rerun")?.addEventListener("click", () => {
        this.rerunTask(sess.query);
      });

      this.container.appendChild(card);
    });
  }
}
