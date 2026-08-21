/**
 * MemoryView — Neural Knowledge Core & Categorical Semantic Memory
 * Clean, truthful empty state with zero fabricated production data.
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
      } else {
        this.items = [];
      }
    } catch (e) {
      this.items = [];
    }
    this.render();
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
      this.items = this.items.filter(i => i.id !== itemId);
      this.render();
    }
  }

  render() {
    if (!this.container) return;
    this.container.innerHTML = "";

    const query = (this.searchInput?.value || "").toLowerCase();
    const category = this.categoryFilter?.value || "ALL";

    const filtered = this.items.filter(item => {
      const matchCat = (category === "ALL" || item.category === category);
      const matchSearch = (!query || item.content.toLowerCase().includes(query) || (item.source && item.source.toLowerCase().includes(query)));
      return matchCat && matchSearch;
    });

    if (this.items.length === 0) {
      // Intentional Clean Empty State (Truthful, No Fake Data)
      this.container.innerHTML = `
        <div class="memory-empty-state">
          <div class="memory-empty-icon">
            <svg viewBox="0 0 64 64" width="48" height="48" fill="none" stroke="var(--accent-cyan)" stroke-width="2">
              <circle cx="32" cy="32" r="28" stroke-dasharray="4,4"/>
              <path d="M 22 26 Q 32 18 42 26 Q 32 34 22 26 Z" fill="rgba(0, 240, 255, 0.1)"/>
              <circle cx="32" cy="42" r="4" fill="var(--accent-cyan)"/>
              <line x1="32" y1="34" x2="32" y2="38" stroke="var(--accent-cyan)" stroke-width="2"/>
            </svg>
          </div>
          <div class="memory-empty-title">NEURAL KNOWLEDGE CORE</div>
          <div class="memory-empty-subtext">No knowledge or document embeddings indexed yet.</div>
          <div class="memory-empty-capabilities">
            <div>SERA can remember and synthesize:</div>
            <ul>
              <li>• User Preferences & Desktop Routines</li>
              <li>• Active Coding Projects & Documents</li>
              <li>• Historical Conversations & Decisions</li>
              <li>• Local File System Documentation</li>
            </ul>
          </div>
          <div class="memory-empty-actions">
            <button class="btn-action btn-primary-glow" id="btn-add-memory">+ Add Memory Item</button>
            <button class="btn-action" id="btn-index-folder">Index Folder</button>
            <button class="btn-action" id="btn-import-doc">Import Document</button>
          </div>
        </div>
      `;

      this.container.querySelector("#btn-add-memory")?.addEventListener("click", () => {
        const text = prompt("Enter a preference or memory note to save:");
        if (text && text.trim()) {
          this.items.push({
            id: `mem_${Date.now()}`,
            category: "PREFERENCES",
            content: text.trim(),
            source: "User Input",
            date: "Just now",
            confidence: "1.0",
          });
          this.render();
        }
      });

      return;
    }

    if (filtered.length === 0) {
      this.container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 20px;">No memory items match '${query}' in category '${category}'.</div>`;
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
          <button class="btn-mini btn-forget" data-id="${item.id}" style="color: var(--accent-broken);">Forget</button>
        </div>
      `;

      card.querySelector(".btn-forget")?.addEventListener("click", () => {
        this.forgetItem(item.id);
      });

      this.container.appendChild(card);
    });
  }
}
