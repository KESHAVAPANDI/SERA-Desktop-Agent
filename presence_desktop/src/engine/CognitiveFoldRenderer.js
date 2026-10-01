import * as THREE from "../../node_modules/three/build/three.module.js";

const MAX_FOLDS = 7;
const MAX_THREADS = 9;
const MAX_SIGNALS = 4;
const SEGMENTS = 36;
const WORLD_WIDTH = 10.4;

function makeRibbonGeometry() {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(SEGMENTS * 2 * 3), 3));
  const indices = [];
  for (let index = 0; index < SEGMENTS - 1; index += 1) {
    const point = index * 2;
    indices.push(point, point + 1, point + 2, point + 1, point + 3, point + 2);
  }
  geometry.setIndex(indices);
  return geometry;
}

function makeLineGeometry() {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(SEGMENTS * 3), 3));
  return geometry;
}

function foldPoint(index, step, behavior, edgeOffset = 0) {
  const t = step / (SEGMENTS - 1);
  const x = (t - 0.5) * WORLD_WIDTH;
  const side = index % 2 === 0 ? 1 : -1;
  const lane = Math.floor(index / 2);
  const taskBias = behavior.task.direction * 0.16;
  const skew = behavior.skew + taskBias + behavior.impulses.projection * 0.22;
  const voidShoulder = Math.exp(-Math.pow((t - 0.5) / 0.31, 4));
  const creaseCenter = 0.24 + ((index * 0.17 + Math.abs(skew) * 0.19) % 0.53);
  const crease = Math.max(0, 1 - Math.abs(t - creaseCenter) * 8.5);
  const secondaryCrease = Math.max(0, 1 - Math.abs(t - (0.76 - index * 0.025)) * 12);
  const wave = Math.sin(t * Math.PI * (2.2 + behavior.density) + behavior.phase * 3 + index) * behavior.ripple;
  const voice = Math.sin(t * Math.PI * 5 - behavior.time * 3.2) * behavior.voice * 0.18;
  const broken = behavior.impulses.anomaly * Math.sin(step * 2.17 + index * 4.3) * 0.2;
  const y = side * (
    behavior.aperture + lane * behavior.spread + voidShoulder * 0.42
    + crease * (0.42 + lane * 0.06) - secondaryCrease * 0.22
    + wave + voice + broken + edgeOffset
  ) + x * skew * 0.13;
  const z = lane * -0.16 + crease * 0.42 + secondaryCrease * -0.22 + side * skew * 0.18;
  return { x, y, z, side };
}

export class CognitiveFoldRenderer {
  constructor(canvas, width, height, dpr) {
    this.canvas = canvas;
    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-5.8, 5.8, 3.8, -3.8, -20, 20);
    this.camera.position.z = 8;
    this.group = new THREE.Group();
    this.group.rotation.x = -0.08;
    this.scene.add(this.group);
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: false,
      powerPreference: "low-power",
      premultipliedAlpha: true,
    });
    this.renderer.setClearColor(0x000000, 0);
    this.ribbons = [];
    this.threads = [];
    this.signals = [];
    this.lastFrame = -Infinity;
    this.build();
    this.resize(width, height, dpr);
  }

  build() {
    for (let index = 0; index < MAX_FOLDS; index += 1) {
      const material = new THREE.MeshBasicMaterial({
        color: 0xf2eee3,
        transparent: true,
        opacity: 0.55,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const mesh = new THREE.Mesh(makeRibbonGeometry(), material);
      mesh.renderOrder = index;
      this.ribbons.push(mesh);
      this.group.add(mesh);
    }
    for (let index = 0; index < MAX_THREADS; index += 1) {
      const material = new THREE.LineBasicMaterial({ color: 0x5d8f89, transparent: true, opacity: 0.4, depthWrite: false });
      const line = new THREE.Line(makeLineGeometry(), material);
      line.renderOrder = MAX_FOLDS + index;
      this.threads.push(line);
      this.group.add(line);
    }
    for (let index = 0; index < MAX_SIGNALS; index += 1) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3), 3));
      const material = new THREE.PointsMaterial({ color: 0xf2eee3, size: 0.095, transparent: true, opacity: 0.8, depthWrite: false });
      const point = new THREE.Points(geometry, material);
      point.renderOrder = 30;
      this.signals.push(point);
      this.group.add(point);
    }
  }

  resize(width, height, dpr) {
    const safeWidth = Math.max(1, width);
    const safeHeight = Math.max(1, height);
    const aspect = safeWidth / safeHeight;
    const vertical = 3.65;
    this.camera.left = -vertical * aspect;
    this.camera.right = vertical * aspect;
    this.camera.top = vertical;
    this.camera.bottom = -vertical;
    this.camera.updateProjectionMatrix();
    this.renderer.setPixelRatio(Math.min(1.5, Math.max(1, dpr || 1)));
    this.renderer.setSize(safeWidth, safeHeight, false);
  }

  render(behavior) {
    const minimumInterval = behavior.motionScale < 0.5 ? 1 / 15 : 1 / 30;
    if (behavior.time - this.lastFrame < minimumInterval) return;
    this.lastFrame = behavior.time;
    const foldCount = Math.max(1, Math.min(MAX_FOLDS, Math.round(behavior.folds)));
    const threadCount = Math.max(0, Math.min(MAX_THREADS, Math.round(behavior.threads)));
    const signalCount = Math.max(0, Math.min(MAX_SIGNALS, Math.round(behavior.signals)));
    const accent = new THREE.Color(behavior.accent);
    const secondary = new THREE.Color(behavior.secondary);

    this.ribbons.forEach((mesh, index) => {
      mesh.visible = index < foldCount;
      if (!mesh.visible) return;
      const positions = mesh.geometry.attributes.position;
      const width = 0.12 + behavior.density * 0.13 + (index % 2) * 0.025;
      for (let step = 0; step < SEGMENTS; step += 1) {
        const center = foldPoint(index, step, behavior);
        positions.setXYZ(step * 2, center.x, center.y - center.side * width, center.z);
        positions.setXYZ(step * 2 + 1, center.x, center.y + center.side * width, center.z + 0.045);
      }
      positions.needsUpdate = true;
      mesh.geometry.computeBoundingSphere();
      mesh.material.color.copy(index % 3 === 0 ? secondary : accent);
      mesh.material.opacity = behavior.opacity * (0.72 - index * 0.055) + behavior.impulses.flash * 0.18;
    });

    this.threads.forEach((line, index) => {
      line.visible = index < threadCount;
      if (!line.visible) return;
      const positions = line.geometry.attributes.position;
      const foldIndex = index % Math.max(1, foldCount);
      const offset = 0.26 + Math.floor(index / Math.max(1, foldCount)) * 0.16;
      for (let step = 0; step < SEGMENTS; step += 1) {
        const point = foldPoint(foldIndex, step, behavior, offset);
        positions.setXYZ(step, point.x, point.y, point.z + 0.08);
      }
      positions.needsUpdate = true;
      line.material.color.copy(index % 4 === 0 ? secondary : accent);
      line.material.opacity = 0.14 + behavior.density * 0.35;
    });

    this.signals.forEach((signal, index) => {
      signal.visible = index < signalCount;
      if (!signal.visible) return;
      const travel = ((behavior.phase * 0.35 + index / Math.max(1, signalCount) + behavior.progress * 0.4) % 1 + 1) % 1;
      const step = Math.min(SEGMENTS - 1, Math.floor(travel * SEGMENTS));
      const point = foldPoint(index % foldCount, step, behavior, 0.28);
      signal.geometry.attributes.position.setXYZ(0, point.x, point.y, point.z + 0.14);
      signal.geometry.attributes.position.needsUpdate = true;
      signal.material.color.copy(index % 2 ? accent : secondary);
      signal.material.opacity = 0.45 + behavior.impulses.projection * 0.45;
    });

    this.group.position.x = behavior.impulses.return * -0.12;
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.group.traverse((object) => {
      if (object.geometry) object.geometry.dispose();
      if (object.material) object.material.dispose();
    });
    this.renderer.dispose();
    this.renderer.forceContextLoss?.();
  }
}

/** Lightweight fallback for unavailable/lost WebGL contexts. */
export class CognitiveFoldCanvasRenderer {
  constructor(canvas, width, height, dpr) {
    this.canvas = canvas;
    this.context = canvas.getContext("2d", { alpha: true });
    if (!this.context) throw new Error("No supported rendering context");
    this.lastFrame = -Infinity;
    this.resize(width, height, dpr);
  }

  resize(width, height, dpr) {
    this.width = Math.max(1, width);
    this.height = Math.max(1, height);
    this.dpr = Math.min(1.5, Math.max(1, dpr || 1));
    this.canvas.width = Math.round(this.width * this.dpr);
    this.canvas.height = Math.round(this.height * this.dpr);
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;
    this.context.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  }

  render(behavior) {
    const interval = behavior.motionScale < 0.5 ? 1 / 12 : 1 / 24;
    if (behavior.time - this.lastFrame < interval) return;
    this.lastFrame = behavior.time;
    const ctx = this.context;
    ctx.clearRect(0, 0, this.width, this.height);
    const scaleX = this.width / 12;
    const scaleY = this.height / 7.5;
    const folds = Math.max(1, Math.min(MAX_FOLDS, Math.round(behavior.folds)));
    for (let index = folds - 1; index >= 0; index -= 1) {
      ctx.beginPath();
      for (let step = 0; step < SEGMENTS; step += 1) {
        const point = foldPoint(index, step, behavior);
        const x = this.width / 2 + point.x * scaleX;
        const y = this.height / 2 - point.y * scaleY;
        if (step === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.lineWidth = 3 + behavior.density * 5;
      ctx.globalAlpha = behavior.opacity * (0.55 - index * 0.045);
      ctx.strokeStyle = index % 3 === 0 ? `#${behavior.secondary.toString(16).padStart(6, "0")}` : `#${behavior.accent.toString(16).padStart(6, "0")}`;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  dispose() {
    this.context.clearRect(0, 0, this.width, this.height);
  }
}
