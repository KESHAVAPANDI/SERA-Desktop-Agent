/**
 * MemoryView — Neural Knowledge Core & Searchable Items
 */
export class MemoryView {
  constructor() {
    this.container = document.getElementById("memory-grid");
    this.searchInput = document.getElementById("memory-search");
    this.items = [
      { id: "m1", category: "PREFERENCE", content: "Preferred Browser: Google Chrome", confidence: "HIGH", usage: 42 },
      { id: "m2", category: "FACT", content: "Primary Display: 1920x1200 @ 60Hz 16:10", confidence: "HIGH", usage: 18 },
      { id: "m3", category: "PROJECT", content: "Active Workspace: c:/Users/kesha/OneDrive/Documents/Sera", confidence: "HIGH", usage: 89 },
      { id: "m4", category: "PREFERENCE", content: "Default Screen Brightness: 40%", confidence: "MEDIUM", usage: 12 },
      { id: "m5", category: "TASK", content: "SERA 1.0 Architecture Validation Phases 1-5", confidence: "HIGH", usage: 65 },
    ];
    this.init();
  }

  init() {
    this.render(this.items);
    this.searchInput?.addEventListener("input", e => {
      const q = e.target.value.toLowerCase().trim();
      const filtered = this.items.filter(i => i.content.toLowerCase().includes(q) || i.category.toLowerCase().includes(q));
      this.render(filtered);
    });
  }

  render(items) {
    if (!this.container) return;
    this.container.innerHTML = "";
    items.forEach(item => {
      const card = document.createElement("div");
      card.className = "memory-item-card";
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
          <span style="font-family: var(--font-brand); font-size: 0.7rem; color: var(--accent-cyan); font-weight: 700;">${item.category}</span>
          <span style="font-size: 0.7rem; color: var(--accent-emerald);">● ${item.confidence} CONFIDENCE</span>
        </div>
        <div style="font-size: 0.9rem; font-weight: 500;">${item.content}</div>
        <div style="font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted); margin-top: 8px;">Recall Count: ${item.usage} times</div>
      `;
      this.container.appendChild(card);
    });
  }
}
