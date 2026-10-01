export class RuntimeSocket {
  constructor(url, handlers = {}, options = {}) {
    this.url = url;
    this.handlers = handlers;
    this.WebSocketImpl = options.WebSocketImpl || globalThis.WebSocket;
    this.minDelay = options.minDelay ?? 500;
    this.maxDelay = options.maxDelay ?? 15000;
    this.random = options.random || Math.random;
    this.attempt = 0;
    this.socket = null;
    this.timer = null;
    this.closed = true;
    this.generation = 0;
  }

  start() {
    if (!this.closed) return;
    this.closed = false;
    this.handlers.onStatus?.("CONNECTING");
    this._connect();
  }

  _connect() {
    if (this.closed || !this.WebSocketImpl) {
      if (!this.WebSocketImpl) this.handlers.onStatus?.("OFFLINE");
      return;
    }
    const generation = ++this.generation;
    let socket;
    try {
      socket = new this.WebSocketImpl(this.url);
    } catch (error) {
      this.handlers.onError?.(error);
      this._retry(generation);
      return;
    }
    this.socket = socket;
    socket.onopen = () => {
      if (this.closed || generation !== this.generation) return socket.close();
      this.attempt = 0;
      this.handlers.onStatus?.("ONLINE");
    };
    socket.onmessage = (event) => {
      if (this.closed || generation !== this.generation) return;
      try {
        this.handlers.onMessage?.(JSON.parse(event.data));
      } catch (error) {
        this.handlers.onError?.(error);
      }
    };
    socket.onerror = (error) => this.handlers.onError?.(error);
    socket.onclose = () => {
      if (generation !== this.generation) return;
      this.socket = null;
      if (!this.closed) this._retry(generation);
    };
  }

  _retry(generation) {
    if (this.closed || generation !== this.generation) return;
    this.handlers.onStatus?.("RECONNECTING");
    const base = Math.min(this.maxDelay, this.minDelay * (2 ** this.attempt++));
    const delay = Math.round(base * (0.8 + this.random() * 0.4));
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.timer = null;
      this._connect();
    }, delay);
  }

  stop() {
    if (this.closed) return;
    this.closed = true;
    this.generation += 1;
    clearTimeout(this.timer);
    this.timer = null;
    const socket = this.socket;
    this.socket = null;
    if (socket && socket.readyState < 2) socket.close();
    this.handlers.onStatus?.("OFFLINE");
  }
}
