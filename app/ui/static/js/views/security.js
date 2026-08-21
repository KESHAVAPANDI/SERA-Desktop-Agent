/**
 * SecurityView — Security Manager Policies, Permission Matrix & Action Confirmations
 */

export class SecurityView {
  constructor(socketSender) {
    this.send = socketSender;
    this.permissionsList = document.getElementById("security-permissions-list");
    this.privacyList = document.getElementById("privacy-breakdown-list");
    
    // Action Confirmation Modal
    this.modalConfirm = document.getElementById("modal-confirmation");
    this.modalPrompt = document.getElementById("modal-confirm-prompt");
    this.modalAction = document.getElementById("modal-confirm-action");
    this.btnAllow = document.getElementById("btn-confirm-allow");
    this.btnDeny = document.getElementById("btn-confirm-deny");

    this.pendingActionId = null;
    this.init();
  }

  async init() {
    this.setupConfirmationModal();
    await this.fetchSecurityData();
  }

  setupConfirmationModal() {
    this.btnAllow?.addEventListener("click", () => {
      if (this.pendingActionId) {
        this.send({ action: "CONFIRM_ACTION", action_id: this.pendingActionId, allowed: true });
        this.closeModal();
      }
    });

    this.btnDeny?.addEventListener("click", () => {
      if (this.pendingActionId) {
        this.send({ action: "CONFIRM_ACTION", action_id: this.pendingActionId, allowed: false });
        this.closeModal();
      }
    });
  }

  showConfirmationRequest(actionId, toolName, promptText, argumentsJson) {
    this.pendingActionId = actionId;
    if (this.modalPrompt) this.modalPrompt.textContent = promptText || "SERA wants to execute a sensitive desktop action:";
    if (this.modalAction) {
      this.modalAction.innerHTML = `<strong>Tool: ${toolName}</strong><br><pre style="margin-top: 4px; font-size: 0.75rem;">${JSON.stringify(argumentsJson || {}, null, 2)}</pre>`;
    }
    this.modalConfirm?.classList.remove("hidden");
  }

  closeModal() {
    this.modalConfirm?.classList.add("hidden");
    this.pendingActionId = null;
  }

  async fetchSecurityData() {
    try {
      const resp = await fetch("/api/security");
      if (resp.ok) {
        const data = await resp.json();
        this.render(data);
      }
    } catch (e) {
      console.warn("[SecurityView] Failed to fetch security data.");
    }
  }

  render(data) {
    if (this.permissionsList && data.permissions) {
      this.permissionsList.innerHTML = "";
      Object.entries(data.permissions).forEach(([key, val]) => {
        const row = document.createElement("div");
        row.className = "permission-item-card";

        let badgeClass = "perm-badge-allowed";
        if (val.status === "CONFIRM_ALWAYS") badgeClass = "perm-badge-confirm";
        if (val.status === "BLOCKED") badgeClass = "perm-badge-blocked";

        row.innerHTML = `
          <div>
            <strong style="text-transform: capitalize;">${key.replace('_', ' ')}</strong>
            <div style="font-size: 0.75rem; color: var(--text-secondary);">${val.description}</div>
          </div>
          <span class="${badgeClass}">${val.status}</span>
        `;
        this.permissionsList.appendChild(row);
      });
    }

    if (this.privacyList && data.privacy) {
      this.privacyList.innerHTML = "";
      Object.entries(data.privacy).forEach(([key, val]) => {
        const row = document.createElement("div");
        row.className = "privacy-item-card";

        const isLocal = val.includes("LOCAL");
        row.innerHTML = `
          <div>
            <strong style="text-transform: capitalize;">${key.replace('_', ' ')}</strong>
          </div>
          <span class="cap-pill" style="color: ${isLocal ? 'var(--accent-emerald)' : 'var(--accent-cyan)'}; font-weight: 700;">
            ${val}
          </span>
        `;
        this.privacyList.appendChild(row);
      });
    }
  }
}
