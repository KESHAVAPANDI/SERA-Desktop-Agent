/**
 * DebugView — Engineering Telemetry, Structured Event Cards, Latency Waterfall & Export
 */

export class DebugView {
  constructor() {
    this.traceBox = document.getElementById("event-trace-box");
    this.waterfallBox = document.getElementById("latency-telemetry-box");
    this.filterPills = document.getElementById("event-filters");
    this.currentFilter = "ALL";
    this.searchQuery = "";
    this.isPaused = false;
    this.eventsLog = [];

    this.init();
  }

  init() {
    this.filterPills?.querySelectorAll(".filter-pill").forEach(btn => {
      btn.addEventListener("click", () => {
        this.filterPills.querySelectorAll(".filter-pill").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.currentFilter = btn.getAttribute("data-filter");
        this.renderEventTrace();
      });
    });

    this.fetchWaterfall();
  }

  async fetchWaterfall() {
    try {
      const resp = await fetch("/api/telemetry");
      if (resp.ok) {
        const data = await resp.json();
        this.renderWaterfall(data);
      }
    } catch (e) {
      console.warn("[DebugView] Failed to fetch telemetry waterfall.");
    }
  }

  renderWaterfall(data) {
    if (!this.waterfallBox || !data.stages) return;
    this.waterfallBox.innerHTML = "";

    const totalMs = data.total_turn_latency_ms || 1000;
    data.stages.forEach(s => {
      const pct = Math.max(4, Math.min(100, (s.latency_ms / totalMs) * 100));
      const row = document.createElement("div");
      row.className = "waterfall-stage-row";

      row.innerHTML = `
        <div class="waterfall-stage-header">
          <span>${s.stage}</span>
          <strong style="color: var(--text-primary);">${s.latency_ms}ms</strong>
        </div>
        <div class="waterfall-track">
          <div class="waterfall-fill" style="width: ${pct}%; background: ${s.color || 'var(--accent-cyan)'};"></div>
        </div>
      `;
      this.waterfallBox.appendChild(row);
    });
  }

  logEvent(eventType, payload) {
    if (this.isPaused) return;

    const timeStr = new Date().toLocaleTimeString();
    const id = `ev_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`;
    this.eventsLog.unshift({ id, time: timeStr, type: eventType, data: payload || {} });
    if (this.eventsLog.length > 100) this.eventsLog.pop();
    this.renderEventTrace();
  }

  renderEventTrace() {
    if (!this.traceBox) return;
    this.traceBox.innerHTML = "";

    const filtered = this.eventsLog.filter(ev => {
      if (this.currentFilter === "STATE" && !ev.type.includes("STATE") && !ev.type.includes("SNAPSHOT")) return false;
      if (this.currentFilter === "MODEL" && !ev.type.includes("MODEL") && !ev.type.includes("ROLE")) return false;
      if (this.currentFilter === "TOOL" && !ev.type.includes("TOOL")) return false;
      if (this.currentFilter === "VISION" && !ev.type.includes("VISION")) return false;
      if (this.currentFilter === "AUDIO" && !ev.type.includes("CAPTURE") && !ev.type.includes("TRANSCRIPT") && !ev.type.includes("WAKE")) return false;
      if (this.currentFilter === "SECURITY" && !ev.type.includes("SECURITY")) return false;

      if (this.searchQuery) {
        const str = JSON.stringify(ev).toLowerCase();
        if (!str.includes(this.searchQuery.toLowerCase())) return false;
      }
      return true;
    });

    if (!filtered.length) {
      this.traceBox.innerHTML = `<div style="color: var(--text-muted); font-size: 0.8rem; padding: 16px;">No events match the selected filter.</div>`;
      return;
    }

    filtered.forEach(ev => {
      const card = document.createElement("div");
      card.className = "structured-event-card";

      let typeColor = "var(--accent-cyan)";
      if (ev.type.includes("MODEL")) typeColor = "var(--accent-violet)";
      else if (ev.type.includes("TOOL")) typeColor = "var(--accent-cyan)";
      else if (ev.type.includes("STATE")) typeColor = "var(--accent-emerald)";
      else if (ev.type.includes("SECURITY")) typeColor = "var(--accent-amber)";
      else if (ev.type.includes("BROKEN") || ev.type.includes("FAIL")) typeColor = "var(--accent-broken)";

      const rawJson = JSON.stringify(ev.data, null, 2);

      card.innerHTML = `
        <div class="event-card-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="event-time-tag">${ev.time}</span>
            <span class="event-type-badge" style="color: ${typeColor}; border-color: ${typeColor};">${ev.type}</span>
          </div>
          <button class="btn-mini btn-toggle-raw" style="font-size: 0.68rem;">Show JSON</button>
        </div>

        <div class="event-summary-line">
          ${this.formatEventSummary(ev.type, ev.data)}
        </div>

        <div class="event-raw-details hidden">
          <pre>${rawJson}</pre>
        </div>
      `;

      card.querySelector(".btn-toggle-raw")?.addEventListener("click", e => {
        const btn = e.target;
        const details = card.querySelector(".event-raw-details");
        if (details) {
          const isHidden = details.classList.toggle("hidden");
          btn.textContent = isHidden ? "Show JSON" : "Hide JSON";
        }
      });

      this.traceBox.appendChild(card);
    });
  }

  formatEventSummary(type, data) {
    if (!data || Object.keys(data).length === 0) return `<span style="color: var(--text-muted);">No payload</span>`;
    if (type === "SNAPSHOT") return `Status: <strong>${data.status}</strong> • Runtime: ${data.runtime_attached ? 'ONLINE' : 'STANDALONE'}`;
    if (type === "RUNTIME_STATE_CHANGED") return `Transition to: <strong style="color: var(--accent-cyan);">${data.status}</strong> (${data.task || 'No task'})`;
    if (type === "MODEL_SELECTED") return `Role: <strong>${data.role}</strong> ➔ <span>${data.provider} • ${data.model}</span>`;
    if (type === "TOOL_STARTED") return `Invoked tool: <strong style="color: var(--accent-cyan);">${data.tool}</strong>`;
    if (type === "TOOL_COMPLETED") return `Completed tool: <strong>${data.tool}</strong> (${data.latency_ms || 0}ms)`;
    if (type === "CAPTURE_COUNTDOWN") return `Voice Capture: <strong>${data.duration_seconds}s</strong> via <span>${data.activation_method}</span>`;
    if (type === "TRANSCRIPT_RECEIVED") return `Transcript: <em>"${data.text}"</em>`;
    return Object.entries(data).slice(0, 3).map(([k, v]) => `<span>${k}: <strong>${typeof v === 'object' ? '...' : v}</strong></span>`).join(" • ");
  }
}
