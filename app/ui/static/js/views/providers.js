/**
 * ProvidersView — Model Infrastructure, Health Status & Quota Meters
 */
export class ProvidersView {
  constructor() {
    this.container = document.getElementById("providers-container");
    this.providersData = [];
  }

  update(providers) {
    this.providersData = providers;
    this.render();
  }

  render() {
    if (!this.container || !this.providersData) return;
    this.container.innerHTML = "";

    this.providersData.forEach(p => {
      const card = document.createElement("div");
      card.className = "provider-card";

      const isHealthy = p.status === "HEALTHY";
      const statusColor = isHealthy ? "var(--accent-emerald)" : (p.status === "RATE_LIMITED" ? "var(--accent-amber)" : "var(--accent-crimson)");

      let modelsHtml = "";
      p.models.forEach(m => {
        const reqUsed = m.quota?.requests_used ?? 0;
        const reqLimit = m.quota?.requests_limit ?? 100;
        const reqPct = m.quota?.is_unknown ? 0 : Math.min(100, Math.round((reqUsed / reqLimit) * 100));

        modelsHtml += `
          <div class="model-item-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <strong style="font-size: 0.95rem;">${m.display_name}</strong>
                <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--accent-cyan);">${m.role} ${m.is_primary ? '• PRIMARY' : ''}</div>
              </div>
              <span style="font-size: 0.75rem; color: ${m.health_status === 'HEALTHY' ? 'var(--accent-emerald)' : 'var(--accent-amber)'}; font-weight: 600;">
                ● ${m.health_status}
              </span>
            </div>

            <div class="quota-bar-wrapper">
              <div style="display: flex; justify-content: space-between; font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-secondary); margin-bottom: 4px;">
                <span>Quota Usage: ${m.quota?.is_unknown ? 'UNKNOWN' : `${reqUsed}/${reqLimit} reqs`}</span>
                <span>Reset: ${m.quota?.reset_time_str || 'N/A'}</span>
              </div>
              <div class="quota-bar-track">
                <div class="quota-bar-fill" style="width: ${reqPct}%;"></div>
              </div>
            </div>

            <div style="display: flex; gap: 12px; font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted); margin-top: 8px;">
              <span>TTFT: ${m.recent_avg_ttft_ms ? `${m.recent_avg_ttft_ms}ms` : 'N/A'}</span>
              <span>Avg Latency: ${m.recent_avg_latency_ms ? `${m.recent_avg_latency_ms}ms` : 'N/A'}</span>
            </div>
          </div>
        `;
      });

      card.innerHTML = `
        <div class="provider-header">
          <div class="provider-title">${p.display_name}</div>
          <span style="font-size: 0.8rem; font-weight: 700; color: ${statusColor};">● ${p.status}</span>
        </div>
        <div class="models-list">${modelsHtml}</div>
      `;
      this.container.appendChild(card);
    });
  }
}
