/**
 * DebugView — Engineering Telemetry, Latency Waterfall & EventBus Trace Log
 */

export class DebugView {
  constructor() {
    this.traceBox = document.getElementById("event-trace-box");
    this.waterfallBox = document.getElementById("latency-telemetry-box");
    this.filterPills = document.getElementById("event-filters");
    this.currentFilter = "ALL";
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
    const timeStr = new Date().toLocaleTimeString();
    this.eventsLog.unshift({ time: timeStr, type: eventType, data: payload });
    if (this.eventsLog.length > 80) this.eventsLog.pop();
    this.renderEventTrace();
  }

  renderEventTrace() {
    if (!this.traceBox) return;
    this.traceBox.innerHTML = "";

    const filtered = this.eventsLog.filter(ev => {
      if (this.currentFilter === "ALL") return true;
      if (this.currentFilter === "MODEL") return ev.type.includes("MODEL");
      if (this.currentFilter === "TOOL") return ev.type.includes("TOOL");
      if (this.currentFilter === "STATE") return ev.type.includes("STATE");
      return true;
    });

    filtered.forEach(ev => {
      const line = document.createElement("div");
      line.style.lineHeight = "1.4";
      line.innerHTML = `<span style="color: var(--text-muted);">${ev.time}</span> <strong style="color: var(--accent-cyan);">${ev.type}</strong>: ${JSON.stringify(ev.data)}`;
      this.traceBox.appendChild(line);
    });
  }
}
