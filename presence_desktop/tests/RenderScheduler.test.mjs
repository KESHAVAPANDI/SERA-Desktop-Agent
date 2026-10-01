import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const source = await readFile(path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src/integration/RenderScheduler.js"), "utf8");
const { RenderScheduler } = await import(`data:text/javascript;charset=utf-8,${encodeURIComponent(source)}`);

test("scheduler pauses while hidden and removes visibility listener", () => {
  let hidden = false;
  let callback;
  let frames = 0;
  const listeners = new Map();
  const doc = {
    get hidden() { return hidden; },
    addEventListener(name, fn) { listeners.set(name, fn); },
    removeEventListener(name) { listeners.delete(name); },
  };
  const scheduler = new RenderScheduler(() => { frames += 1; }, {
    document: doc,
    requestAnimationFrame(fn) { callback = fn; return 1; },
    cancelAnimationFrame() { callback = null; },
  });
  scheduler.start();
  callback(1000);
  assert.equal(frames, 1);
  hidden = true;
  listeners.get("visibilitychange")();
  assert.equal(callback, null);
  scheduler.stop();
  assert.equal(listeners.has("visibilitychange"), false);
});
