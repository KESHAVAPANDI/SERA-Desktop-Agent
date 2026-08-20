/**
 * LiveView — Futuristic Voice Orb & Unified Conversation Stream
 */
export class LiveView {
  constructor(socketSender) {
    this.send = socketSender;
    this.streamContainer = document.getElementById("chat-stream");
    this.form = document.getElementById("chat-form");
    this.input = document.getElementById("chat-input");
    this.orb = document.getElementById("aura-orb-main");
    this.init();
  }

  init() {
    this.form?.addEventListener("submit", e => {
      e.preventDefault();
      const text = this.input?.value.trim();
      if (!text) return;
      this.appendMessage("user", text);
      this.input.value = "";
      this.send({ action: "USER_PROMPT", text: text });
    });

    this.orb?.addEventListener("click", () => {
      this.send({ action: "INTERRUPT" });
    });
  }

  appendMessage(sender, text) {
    if (!this.streamContainer) return;
    const msg = document.createElement("div");
    msg.className = `chat-bubble ${sender}`;
    msg.textContent = text;
    this.streamContainer.appendChild(msg);
    this.streamContainer.scrollTop = this.streamContainer.scrollHeight;
  }
}
