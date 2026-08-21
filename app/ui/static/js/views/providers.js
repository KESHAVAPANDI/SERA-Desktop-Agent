/**
 * ProvidersView — Model Infrastructure, Dynamic Quota Dashboard & Provider Onboarding
 */

export class ProvidersView {
  constructor(onShowInWorkflow) {
    this.container = document.getElementById("providers-container");
    this.onShowInWorkflow = onShowInWorkflow;
    this.btnAddProvider = document.getElementById("btn-open-add-provider");
    this.modalAddProvider = document.getElementById("modal-add-provider");
    this.btnCloseModal = document.getElementById("btn-close-add-provider");
    this.btnTestConn = document.getElementById("btn-test-provider-conn");
    this.btnSaveProvider = document.getElementById("btn-save-provider");
    this.testResultBox = document.getElementById("add-provider-test-result");

    this.providers = [];
    this.init();
  }

  async init() {
    this.setupModal();
    await this.fetchProviders();
  }

  setupModal() {
    this.btnAddProvider?.addEventListener("click", () => {
      this.modalAddProvider?.classList.remove("hidden");
      this.testResultBox?.classList.add("hidden");
    });

    this.btnCloseModal?.addEventListener("click", () => {
      this.modalAddProvider?.classList.add("hidden");
    });

    this.btnTestConn?.addEventListener("click", async () => {
      const url = document.getElementById("add-prov-url")?.value.trim();
      if (!url) return;
      this.testResultBox?.classList.remove("hidden");
      this.testResultBox.textContent = `Connecting to ${url}...`;
      try {
        const resp = await fetch("/api/providers/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ base_url: url }),
        });
        const data = await resp.json();
        this.testResultBox.textContent = data.message || "✓ Connection verified.";
      } catch (e) {
        this.testResultBox.textContent = "✗ Connection failed.";
      }
    });

    this.btnSaveProvider?.addEventListener("click", async () => {
      const name = document.getElementById("add-prov-name")?.value.trim();
      const url = document.getElementById("add-prov-url")?.value.trim();
      const envRef = document.getElementById("add-prov-env")?.value.trim();
      const format = document.getElementById("add-prov-format")?.value;

      if (!name || !url) return;

      try {
        const resp = await fetch("/api/providers/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider_name: name, base_url: url, api_key_env: envRef, format: format }),
        });
        if (resp.ok) {
          this.modalAddProvider?.classList.add("hidden");
          await this.fetchProviders();
        }
      } catch (e) {
        console.warn("[ProvidersView] Save provider failed:", e);
      }
    });
  }

  async fetchProviders() {
    try {
      const resp = await fetch("/api/providers");
      if (resp.ok) {
        this.providers = await resp.json();
        this.render();
      }
    } catch (e) {
      console.warn("[ProvidersView] Failed to fetch providers.");
    }
  }

  update(providersList) {
    if (providersList) {
      this.providers = providersList;
      this.render();
    }
  }

  render() {
    if (!this.container) return;
    this.container.innerHTML = "";

    this.providers.forEach(prov => {
      const card = document.createElement("div");
      card.className = "provider-card";

      let modelsHtml = "";
      prov.models.forEach(m => {
        const isHealthy = m.health_status === "HEALTHY";
        const isRateLimited = m.health_status === "RATE_LIMITED";
        const isBroken = m.health_status === "BROKEN" || m.health_status === "AUTH_ERROR";

        let healthClass = "health-healthy";
        let healthLabel = "● HEALTHY";
        if (isRateLimited) { healthClass = "health-ratelimited"; healthLabel = "● RATE LIMITED"; }
        if (isBroken) { healthClass = "health-broken"; healthLabel = "● UNAVAILABLE"; }

        // Dynamic Quota Meters
        let quotaHtml = "";
        if (m.quota_metrics && m.quota_metrics.length > 0) {
          quotaHtml = m.quota_metrics.map(q => {
            const pct = q.percentage_remaining != null ? q.percentage_remaining : 100;
            return `
              <div class="quota-bar-wrapper">
                <div class="quota-bar-label">
                  <span>${q.label} (${q.window})</span>
                  <span>${q.remaining != null ? `${q.remaining} ${q.unit} left` : `${pct}% remaining`}</span>
                </div>
                <div class="quota-bar-track">
                  <div class="quota-bar-fill" style="width: ${pct}%; background: ${pct < 15 ? 'var(--accent-amber)' : 'var(--accent-cyan)'};"></div>
                </div>
              </div>
            `;
          }).join("");
        } else {
          quotaHtml = `<div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted); margin-top: 6px;">Quota: Unknown / Not Reported</div>`;
        }

        const caps = Object.entries(m.capabilities || {})
          .filter(([_, v]) => v === true)
          .map(([k]) => `<span class="cap-pill">${k}</span>`)
          .join(" ");

        modelsHtml += `
          <div class="model-item-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <strong style="font-size: 0.95rem;">${m.display_name}</strong>
                <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-secondary);">${m.model_id}</div>
              </div>
              <span class="cap-pill ${healthClass}">${healthLabel}</span>
            </div>

            <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px;">
              ${caps}
            </div>

            <div style="margin-top: 8px;">${quotaHtml}</div>

            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
              <span style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">
                ${m.recent_avg_latency_ms ? `Avg Latency: ${m.recent_avg_latency_ms}ms` : ''}
              </span>
              <button class="btn-show-workflow" data-provider="${prov.provider_name}" data-model="${m.model_id}">Show in Workflow ➔</button>
            </div>
          </div>
        `;
      });

      card.innerHTML = `
        <div class="provider-header">
          <div>
            <div class="provider-title">${prov.display_name}</div>
            <div style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-secondary);">${prov.api_key_reference}</div>
          </div>
          <span class="cap-pill health-healthy">${prov.status}</span>
        </div>
        <div class="models-list">${modelsHtml}</div>
      `;

      card.querySelectorAll(".btn-show-workflow").forEach(btn => {
        btn.addEventListener("click", () => {
          const p = btn.getAttribute("data-provider");
          const m = btn.getAttribute("data-model");
          if (this.onShowInWorkflow) this.onShowInWorkflow(p, m);
        });
      });

      this.container.appendChild(card);
    });
  }
}
