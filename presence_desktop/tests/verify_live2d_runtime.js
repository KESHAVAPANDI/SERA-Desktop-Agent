/**
 * Real Manual & Runtime Verification for SERA Live2D Presence.
 *
 * Launches the actual Electron desktop overlay with transparent visuals,
 * loads the Live2D model, and exercises the complete required state lifecycle:
 *
 * Sequence A:
 *   IDLE -> LISTENING -> THINKING -> EXECUTING -> VERIFYING -> SPEAKING -> IDLE
 *
 * Sequence B:
 *   WAITING_FOR_APPROVAL -> COMPLETED -> FAILED -> CANCELLED
 *
 * Captures PNG evidence for each state to the artifact directory.
 */

const { app, BrowserWindow, screen } = require("electron");
const path = require("path");
const fs = require("fs");

// Ensure GPU and transparent visuals
app.commandLine.appendSwitch("disable-background-timer-throttling");
app.commandLine.appendSwitch("disable-renderer-backgrounding");
app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");
app.commandLine.appendSwitch("enable-transparent-visuals");
app.commandLine.appendSwitch("allow-file-access-from-files");

const ARTIFACT_DIR = path.resolve("C:\\Users\\kesha\\.gemini\\antigravity-ide\\brain\\1b818245-2543-44ee-8c22-30fd93a658f6");
fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runVerification() {
  console.log("=================================================");
  console.log("  SERA Live2D Presence — Real Runtime Verification");
  console.log("=================================================");

  const win = new BrowserWindow({
    width: 380,
    height: 560,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    backgroundColor: "#00000000",
    webPreferences: {
      preload: path.join(__dirname, "..", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
      webgl: true,
    },
  });

  win.webContents.on("console-message", (_event, level, message) => {
    console.log(`[Renderer Console] ${message}`);
  });

  win.webContents.on("did-fail-load", (_event, code, desc) => {
    console.error(`[Main] Failed to load index.html: ${code} - ${desc}`);
  });

  await win.loadFile(path.join(__dirname, "..", "index.html"));
  console.log("[Verification] index.html loaded. Waiting for Live2D model initialization...");

  // Wait 3.5 seconds for PixiJS and Live2D model to initialize
  await sleep(3500);

  // Check if window.seraApp and Live2D model are active
  const statusCheck = await win.webContents.executeJavaScript(`
    (() => {
      const app = window.seraApp;
      if (!app) return { ok: false, error: "window.seraApp is missing" };
      const renderer = app.engine?.renderer;
      if (!renderer) return { ok: false, error: "engine.renderer is missing" };
      const controller = renderer.controller;
      return {
        ok: true,
        isLoaded: controller?.isLoaded,
        loadError: controller?.loadError ? String(controller.loadError) : null,
        loadCount: controller?.loadCount,
        currentState: controller?.currentState,
        hasModel: Boolean(controller?.model),
      };
    })()
  `);

  console.log("[Verification] Status Check:", JSON.stringify(statusCheck, null, 2));

  if (!statusCheck.ok || !statusCheck.isLoaded) {
    console.error("[Verification FAIL] Live2D model is not loaded:", statusCheck);
    const errImg = await win.capturePage();
    fs.writeFileSync(path.join(ARTIFACT_DIR, "live2d_init_failure.png"), errImg.toPNG());
    app.quit();
    process.exit(1);
    return;
  }

  console.log("[Verification PASS] Live2D Model attached and persistent.");

  // States to test in exact sequence
  const sequenceA = [
    { state: "IDLE", wait: 800, name: "live2d_01_idle" },
    { state: "LISTENING", wait: 800, name: "live2d_02_listening" },
    { state: "THINKING", wait: 800, name: "live2d_03_thinking" },
    { state: "EXECUTING", wait: 800, name: "live2d_04_executing" },
    { state: "VERIFYING", wait: 800, name: "live2d_05_verifying" },
    { state: "SPEAKING", wait: 800, name: "live2d_06_speaking", audio: { rawAmp: 0.7, mid: 0.8 } },
    { state: "IDLE", wait: 800, name: "live2d_07_idle_return" },
  ];

  const sequenceB = [
    { state: "WAITING_FOR_APPROVAL", wait: 800, name: "live2d_08_waiting_approval" },
    { state: "COMPLETED", wait: 800, name: "live2d_09_completed" },
    { state: "FAILED", wait: 800, name: "live2d_10_failed" },
    { state: "CANCELLED", wait: 800, name: "live2d_11_cancelled" },
  ];

  const allSteps = [...sequenceA, ...sequenceB];

  for (const step of allSteps) {
    console.log(`[Verification] Testing transition to: ${step.state}...`);

    await win.webContents.executeJavaScript(`
      (() => {
        const app = window.seraApp;
        app.setConnection("ONLINE");
        if (${JSON.stringify(Boolean(step.audio))}) {
          app.engine.setAudioData(${JSON.stringify(step.audio || {})});
        }
        app.handleBackendMessage({
          event: "RUNTIME_STATE_CHANGED",
          payload: { status: "${step.state}", task: "Live2D Verification" }
        });
      })()
    `);

    // Wait for smooth parameter and color interpolation to settle
    await sleep(step.wait);

    // Capture screenshot
    const shot = await win.capturePage();
    const outPath = path.join(ARTIFACT_DIR, `${step.name}.png`);
    fs.writeFileSync(outPath, shot.toPNG());
    console.log(`[Verification] Captured: ${step.name}.png (${shot.toPNG().length} bytes)`);
  }

  // Verify that loadCount is STILL 1 (model was NEVER reloaded)
  const finalCheck = await win.webContents.executeJavaScript(`
    (() => {
      const controller = window.seraApp?.engine?.renderer?.controller;
      return {
        loadCount: controller?.loadCount,
        stateChangeCount: controller?.stateChangeCount,
        params: controller?.params,
      };
    })()
  `);

  console.log("=================================================");
  console.log("  Final Continuity Verification Metrics:");
  console.log(`  - Model Load Count: ${finalCheck.loadCount} (MUST BE EXACTLY 1)`);
  console.log(`  - Total State Changes: ${finalCheck.stateChangeCount}`);
  console.log(`  - Final Posture AngleX: ${finalCheck.params?.angleX?.toFixed(2)}`);
  console.log(`  - Final Eye Open: ${finalCheck.params?.eyeOpen?.toFixed(2)}`);
  console.log("=================================================");

  if (finalCheck.loadCount === 1) {
    console.log("[Verification PASS] Perfect model persistence across all state transitions!");
  } else {
    console.error(`[Verification FAIL] Model was reloaded ${finalCheck.loadCount} times!`);
  }

  await sleep(1000);
  app.quit();
}

app.whenReady().then(runVerification);
