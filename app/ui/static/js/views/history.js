/**
 * HistoryView — Compact Session Timeline, Turn Trace Inspection & Replay System
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
      }
    } catch (e) {
      console.warn("[HistoryView] Local history state used.");
    }
    this.render();
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

    if (!this.sessions.length) {
      this.container.innerHTML = `
        <div style="color: var(--text-muted); font-size: 0.85rem; padding: 30px; text-align: center;">
          No interaction sessions recorded yet. Start by speaking or typing a command.
        </div>
      `;
      return;
    }

    const timeline = document.createElement("div");
    timeline.className = "history-timeline";

    this.sessions.forEach(sess => {
      const item = document.createElement("div");
      item.className = "timeline-session-row";

      const isCompleted = sess.status === "COMPLETED";
      const statusClass = isCompleted ? "status-done" : "status-fail";
      const statusIcon = isCompleted ? "✓" : "✕";

      const modelsHtml = (sess.models_used || []).map(m => `<span class="cap-pill">${m}</span>`).join(" ");

      item.innerHTML = `
        <div class="timeline-time-col">
          <div class="timeline-time-val">${sess.time}</div>
          <div class="timeline-date-val">${sess.date}</div>
        </div>

        <div class="timeline-node-dot ${statusClass}">${statusIcon}</div>

        <div class="timeline-content-card">
          <div class="timeline-card-header">
            <div class="timeline-query">"${sess.query}"</div>
            <div class="timeline-duration-badge">${sess.total_duration}</div>
          </div>

          <div class="timeline-pipeline-bar">${sess.pipeline}</div>

          <div class="timeline-models-row">
            ${modelsHtml}
          </div>

          <div class="timeline-actions-row">
            <button class="btn-mini btn-replay-viz" data-id="${sess.session_id}">Replay Visualization</button>
            <button class="btn-mini btn-run-again" data-query="${sess.query}">Run Again ➔</button>
          </div>
        </div>
      `;

      item.querySelector(".btn-replay-viz")?.addEventListener("click", () => {
        if (this.onReplayWorkflow) this.onReplayWorkflow("workflow");
      });

      item.querySelector(".btn-run-again")?.addEventListener("click", () => {
        this.rerunTask(sess.query);
      });

      timeline.appendChild(item);
    });

    this.container.appendChild(timeline);
  }
}
