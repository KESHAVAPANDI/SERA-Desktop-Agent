/**
 * SERA 2.0 — Native Windows Desktop Overlay (Electron Main Process)
 * Real Windows desktop application process with true alpha transparency.
 * 
 * Features:
 * - 100% true desktop visibility through the window
 * - Frameless & always-on-top overlay
 * - Background throttling disabled (consistent 60 FPS animation)
 * - Global shortcut (Ctrl+Space) to summon/focus
 * - Smooth drag repositioning & click-through support
 * - System tray integration
 * 
 * Author: Keshava Pandi A S <keshavapandi@gmail.com>
 */

const { app, BrowserWindow, globalShortcut, ipcMain, screen, shell, Tray, Menu, nativeImage } = require("electron");
const path = require("path");

// Prevent Chromium from throttling animations in background overlay mode
app.commandLine.appendSwitch("disable-background-timer-throttling");
app.commandLine.appendSwitch("disable-renderer-backgrounding");
app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");
app.commandLine.appendSwitch("enable-transparent-visuals");

let mainWindow = null;
let tray = null;

const WINDOW_WIDTH = 380;
const WINDOW_HEIGHT = 380;
const COMMAND_CENTER_URL = "http://127.0.0.1:8765";

function calculateDefaultPosition() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;
  const { x: areaX, y: areaY } = primaryDisplay.workArea;

  // Dock bottom-right with margin
  const marginX = 20;
  const marginY = 20;
  const x = Math.round(areaX + screenWidth - WINDOW_WIDTH - marginX);
  const y = Math.round(areaY + screenHeight - WINDOW_HEIGHT - marginY);

  return { x, y };
}

function createWindow() {
  const { x, y } = calculateDefaultPosition();

  mainWindow = new BrowserWindow({
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT,
    x,
    y,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    hasShadow: false,
    resizable: false,
    skipTaskbar: false,
    backgroundColor: "#00000000",
    title: "SERA Presence",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
      webgl: true,
    },
  });

  mainWindow.setAlwaysOnTop(true, "screen-saver");
  mainWindow.setVisibleOnAllWorkspaces?.(true, { visibleOnFullScreen: true });

  const handleBuffer = mainWindow.getNativeWindowHandle();
  console.log(`[Main] Native HWND: 0x${handleBuffer.toString("hex")}`);
  console.log(`[Main] Window bounds:`, mainWindow.getBounds());
  console.log(`[Main] Is Visible:`, mainWindow.isVisible());

  mainWindow.webContents.on("console-message", (event, level, message, line, sourceId) => {
    console.log(`[Renderer] ${message}`);
  });

  mainWindow.webContents.on("did-fail-load", (event, errorCode, errorDescription) => {
    console.error(`[Main] Failed to load: ${errorCode} - ${errorDescription}`);
  });

  mainWindow.loadFile(path.join(__dirname, "index.html"));

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  setupIpc();
  setupTray();

  if (process.argv.includes("--snapshot")) {
    setTimeout(async () => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        const image = await mainWindow.capturePage();
        const fs = require("fs");
        const outDir = path.resolve("C:\\Users\\kesha\\.gemini\\antigravity-ide\\brain\\1b818245-2543-44ee-8c22-30fd93a658f6");
        const target = path.join(outDir, "desktop_glass_box_panel.png");
        fs.writeFileSync(target, image.toPNG());
        console.log(`[Main] Glass box verification snapshot saved: ${target}`);
        app.quit();
      }
    }, 2500);
  }
}

function setupIpc() {
  ipcMain.on("set-ignore-mouse-events", (event, ignore, options) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.setIgnoreMouseEvents(ignore, { forward: true, ...options });
    }
  });

  ipcMain.on("window-drag", (event, { dx, dy }) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      const [currX, currY] = mainWindow.getPosition();
      mainWindow.setPosition(currX + dx, currY + dy);
    }
  });

  ipcMain.on("window-minimize", () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.minimize();
    }
  });

  ipcMain.on("window-close", () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.close();
    }
  });

  ipcMain.on("open-command-center", () => {
    shell.openExternal(COMMAND_CENTER_URL);
  });

  ipcMain.handle("capture-window-frame", async (_event, outPath) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      const image = await mainWindow.capturePage();
      const fs = require("fs");
      const target = outPath || path.join(__dirname, "..", "scratch", "presence_capture.png");
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, image.toPNG());
      console.log(`[Main] Window frame captured: ${target}`);
      return target;
    }
    return null;
  });
}

function createDefaultTrayIcon() {
  // Generate a minimal 16x16 cyan dot tray icon buffer
  const size = 16;
  const canvas = Buffer.alloc(size * size * 4);
  const cx = 8, cy = 8, r = 6;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 4;
      const dist = Math.hypot(x - cx, y - cy);
      if (dist <= r) {
        const alpha = Math.max(0, Math.min(255, Math.round((1 - (dist / r)) * 255)));
        canvas[idx] = 0;      // B
        canvas[idx + 1] = 240; // G
        canvas[idx + 2] = 255; // R
        canvas[idx + 3] = alpha; // A
      }
    }
  }
  return nativeImage.createFromBuffer(canvas, { width: size, height: size });
}

function setupTray() {
  if (tray) return;

  const icon = createDefaultTrayIcon();
  tray = new Tray(icon);
  tray.setToolTip("SERA 2.0 — Primary Presence");

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Show / Focus SERA (Ctrl+Space)",
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
          mainWindow.webContents.send("global-activate");
        }
      },
    },
    {
      label: "Reset Position (Bottom-Right)",
      click: () => {
        if (mainWindow) {
          const { x, y } = calculateDefaultPosition();
          mainWindow.setPosition(x, y);
        }
      },
    },
    { type: "separator" },
    {
      label: "Open Technical Command Center",
      click: () => {
        shell.openExternal(COMMAND_CENTER_URL);
      },
    },
    { type: "separator" },
    {
      label: "Quit SERA Presence",
      click: () => {
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on("click", () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.focus();
      } else {
        mainWindow.show();
      }
    }
  });
}

function registerShortcuts() {
  // Global shortcut to summon/focus SERA from anywhere in Windows
  const shortcut = "CommandOrControl+Space";
  const registered = globalShortcut.register(shortcut, () => {
    if (mainWindow) {
      if (!mainWindow.isVisible()) {
        mainWindow.show();
      }
      mainWindow.focus();
      mainWindow.webContents.send("global-activate");
    }
  });

  if (!registered) {
    console.warn(`[Main] Failed to register global shortcut ${shortcut}, attempting Alt+Space fallback.`);
    globalShortcut.register("Alt+Space", () => {
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
        mainWindow.webContents.send("global-activate");
      }
    });
  } else {
    console.log(`[Main] Successfully registered global shortcut ${shortcut}`);
  }
}

app.whenReady().then(() => {
  createWindow();
  registerShortcuts();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
