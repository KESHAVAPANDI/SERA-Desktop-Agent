/**
 * MemoryView — Neural Knowledge Core & Categorical Semantic Memory
 */

export class MemoryView {
  constructor() {
    this.container = document.getElementById("memory-grid");
    this.searchInput = document.getElementById("memory-search");
    this.categoryFilter = document.getElementById("memory-category-filter");

    this.items = [];
    this.init();
  }

  async init() {
    this.searchInput?.addEventListener("input", () => this.render());
    this.categoryFilter?.addEventListener("change", () => this.render());
    await this.fetchMemory();
  }

  async fetchMemory() {
    try {
      const resp = await fetch("/api/memory");
      if (resp.ok) {
        this.items = await resp.json();
        this.render();
      }
    } catch (e) {
      console.warn("[MemoryView] Failed to fetch memory items.");
    }
  }

  async forgetItem(itemId) {
    try {
      const resp = await fetch("/api/memory/forget", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: itemId }),
      });
      if (resp.ok) {
        this.items = this.items.filter(i => i.id !== itemId);
        this.render();
      }
    } catch (e) {
      console.warn("[MemoryView] Forget item failed:", e);
    }
  }

  render() {
    if (!this.container) return;
    this.container.innerHTML = "";

    const query = (this.searchInput?.value || "").toLowerCase();
    const category = this.categoryFilter?.value || "ALL";

    const filtered = this.items.filter(item => {
      const matchCat = (category === "ALL" || item.category === category);
      const matchSearch = (!query || item.content.toLowerCase().includes(query) || item.source.toLowerCase().includes(query));
      return matchCat && matchSearch;
    });

    if (filtered.length === 0) {
      this.container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 20px;">No memory items match the selected filter.</div>`;
      return;
    }

    filtered.forEach(item => {
      const card = document.createElement("div");
      card.className = "memory-item-card";

      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="memory-category-tag">${item.category}</span>
          <span class="cap-pill" style="color: var(--accent-cyan);">${item.confidence} CONFIDENCE</span>
        </div>
        <div class="memory-content-text">${item.content}</div>
        <div class="memory-meta-row">
          <span>Source: ${item.source}</span>
          <span>${item.date}</span>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px;">
          <button class="btn-mini btn-forget" data-id="${item.id}" style="color: var(--accent-crimson);">Forget</button>
        </div>
      `;

      card.querySelector(".btn-forget")?.addEventListener("click", () => {
        this.forgetItem(item.id);
      });

      this.container.appendChild(card);
    });
  }
}
