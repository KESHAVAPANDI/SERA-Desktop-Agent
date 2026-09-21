/**
 * SERA 2.0 — Desktop Presence Preload Script
 * Secure contextBridge exposing native window management and hardware access
 * Author: Keshava Pandi A S
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("seraNative", {
  isDesktop: true,
  platform: process.platform,

  // Window control
  setIgnoreMouseEvents: (ignore, options) => {
    ipcRenderer.send("set-ignore-mouse-events", ignore, options);
  },
  minimize: () => ipcRenderer.send("window-minimize"),
  close: () => ipcRenderer.send("window-close"),
  showAndFocus: () => ipcRenderer.send("window-show-and-focus"),
  selfClose: () => ipcRenderer.send("self-close"),
  
  // Custom drag
  dragWindow: (dx, dy) => ipcRenderer.send("window-drag", { dx, dy }),
  
  // Capture Window Frame
  captureWindowFrame: (outPath) => ipcRenderer.invoke("capture-window-frame", outPath),

  // External Navigation
  openCommandCenter: () => ipcRenderer.send("open-command-center"),
  
  // Global Shortcut / Focus Listener
  onGlobalActivate: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("global-activate", handler);
    return () => ipcRenderer.removeListener("global-activate", handler);
  },

  // State sync from Python backend (if bridged through main process)
  onBackendMessage: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on("backend-message", handler);
    return () => ipcRenderer.removeListener("backend-message", handler);
  }
});
