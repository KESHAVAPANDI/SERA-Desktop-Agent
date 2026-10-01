import * as THREE from "../../node_modules/three/build/three.module.js";

const BODY_SEGMENTS = 72;
const MEMBRANE_SEGMENTS = 52;
const TRACE_SEGMENTS = 18;
const MAX_MEMBRANES = 6;
const MAX_NODES = 8;
const MAX_TRACES = 5;
const DPR_CAP = 1.5;

const hexCss = (value) => `#${Math.round(value).toString(16).padStart(6, "0")}`;

function makeDiscGeometry() {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array((BODY_SEGMENTS + 1) * 3), 3));
  const indices = [];
  for (let index = 0; index < BODY_SEGMENTS; index += 1) indices.push(0, index + 1, ((index + 1) % BODY_SEGMENTS) + 1);
  geometry.setIndex(indices);
  return geometry;
}

function makeLineGeometry(segments, loop = false) {
  const count = segments + (loop ? 0 : 1);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  return geometry;
}

/** Sample the single asymmetric body. Every secondary element is derived from this boundary. */
function bodyPoint(angle, behavior, inset = 1) {
  const motion = behavior.motionScale;
  const phase = behavior.phase;
  const lobe = Math.sin(angle * behavior.lobes + 0.65 + phase * 0.7) * behavior.lobeDepth * (1.18 - behavior.tension * 0.24);
  const asymmetric = behavior.asymmetry * (
    Math.sin(angle - 0.42) * 0.52 + Math.sin(angle * 2 + 1.34) * 0.28 + Math.sin(angle * 3 - 0.8) * 0.12
  );
  const living = Math.sin(angle * 3.2 - phase * 2.4) * behavior.wobble * (1.2 - behavior.tension * 0.3) * motion;
  const audio = Math.sin(angle * 4 - behavior.time * 3.4) * behavior.voice * 0.13;
  const anomaly = Math.sin(angle * 9.7 + behavior.time * 5) * behavior.impulses.anomaly * 0.035;
  const breath = 1 + Math.sin(behavior.time * (0.8 + behavior.speed) + 0.4) * behavior.pulse * motion;
  const radius = 2.05 * behavior.scale * inset * breath * (1 + lobe + asymmetric + living + audio + anomaly);
  const sine = Math.sin(angle);
  const weightedBottom = -behavior.lowerWeight * Math.max(0, -sine) ** 2;
  let x = Math.cos(angle) * radius * behavior.stretch;
  const y = sine * radius * behavior.squash + weightedBottom;
  x += behavior.lean * (y + 0.25) + behavior.task.direction * 0.05 * behavior.attention;
  x += behavior.impulses.projection * Math.max(0, Math.cos(angle)) * 0.1;
  x -= behavior.impulses.return * 0.035;
  return { x, y };
}

function updateDisc(mesh, behavior, inset, z) {
  const positions = mesh.geometry.attributes.position;
  positions.setXYZ(0, behavior.lean * -0.08, -behavior.lowerWeight * 0.18, z);
  for (let index = 0; index < BODY_SEGMENTS; index += 1) {
    const point = bodyPoint((index / BODY_SEGMENTS) * Math.PI * 2, behavior, inset);
    positions.setXYZ(index + 1, point.x, point.y, z);
  }
  positions.needsUpdate = true;
}

function nodePoint(index, behavior) {
  const golden = 2.399963229728653;
  const orderedAngle = behavior.task.direction * 0.38 + (index / Math.max(1, behavior.nodes - 1) - 0.5) * 1.25;
  const orbitAngle = index * golden + behavior.phase * (0.9 + index * 0.04);
  const angle = orbitAngle * (1 - behavior.organization) + orderedAngle * behavior.organization;
  const radialLane = 0.22 + ((index * 0.37) % 0.66);
  const radius = behavior.nodeSpread * radialLane * 1.6 * (1 - behavior.nodeFocus * 0.44);
  const progressPull = (behavior.progress - 0.5) * behavior.organization * 0.34;
  return {
    x: Math.cos(angle) * radius * behavior.stretch + behavior.lean * 0.15 + progressPull,
    y: Math.sin(angle) * radius * behavior.squash - behavior.lowerWeight * 0.08,
  };
}

export class CognitiveFoldRenderer {
  constructor(canvas, width, height, dpr) {
    this.canvas = canvas;
    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-4, 4, 3, -3, -20, 20);
    this.camera.position.z = 8;
    this.group = new THREE.Group();
    this.group.rotation.z = -0.025;
    this.scene.add(this.group);
    this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, powerPreference: "low-power", premultipliedAlpha: true });
    this.renderer.setClearColor(0x000000, 0);
    this.shells = [];
    this.membranes = [];
    this.nodes = [];
    this.traces = [];
    this.lastFrame = -Infinity;
    this.build();
    this.resize(width, height, dpr);
  }

  build() {
    // Three coincident, inset translucent skins produce gel depth without post-processing.
    [1, 0.91, 0.72].forEach((inset, index) => {
      const material = new THREE.MeshBasicMaterial({
        color: index === 0 ? 0x79b7aa : (index === 1 ? 0xe7f2ed : 0x285f5b),
        transparent: true,
        opacity: 0.3,
        side: THREE.DoubleSide,
        depthWrite: false,
        blending: THREE.NormalBlending,
      });
      const mesh = new THREE.Mesh(makeDiscGeometry(), material);
      mesh.userData.inset = inset;
      mesh.renderOrder = index;
      this.shells.push(mesh);
      this.group.add(mesh);
    });

    for (let index = 0; index < MAX_MEMBRANES; index += 1) {
      const material = new THREE.LineBasicMaterial({ color: 0xe7f2ed, transparent: true, opacity: 0.2, depthWrite: false });
      const line = new THREE.LineLoop(makeLineGeometry(MEMBRANE_SEGMENTS, true), material);
      line.renderOrder = 5 + index;
      this.membranes.push(line);
      this.group.add(line);
    }

    for (let index = 0; index < MAX_NODES; index += 1) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3), 3));
      const material = new THREE.PointsMaterial({ color: 0xe7f2ed, size: 0.07, transparent: true, opacity: 0.75, depthWrite: false, sizeAttenuation: true });
      const point = new THREE.Points(geometry, material);
      point.renderOrder = 20;
      this.nodes.push(point);
      this.group.add(point);
    }

    for (let index = 0; index < MAX_TRACES; index += 1) {
      const material = new THREE.LineBasicMaterial({ color: 0x79b7aa, transparent: true, opacity: 0.25, depthWrite: false });
      const line = new THREE.Line(makeLineGeometry(TRACE_SEGMENTS), material);
      line.renderOrder = 4;
      this.traces.push(line);
      this.group.add(line);
    }
  }

  resize(width, height, dpr) {
    const safeWidth = Math.max(1, width);
    const safeHeight = Math.max(1, height);
    const aspect = safeWidth / safeHeight;
    const vertical = 3.05;
    this.camera.left = -vertical * aspect;
    this.camera.right = vertical * aspect;
    this.camera.top = vertical;
    this.camera.bottom = -vertical;
    this.camera.updateProjectionMatrix();
    this.renderer.setPixelRatio(Math.min(DPR_CAP, Math.max(1, dpr || 1)));
    this.renderer.setSize(safeWidth, safeHeight, false);
  }

  render(behavior) {
    const interval = behavior.motionScale < 0.5 || behavior.lowPower ? 1 / 20 : 1 / 30;
    if (behavior.time - this.lastFrame < interval) return;
    this.lastFrame = behavior.time;
    const accent = new THREE.Color(behavior.accent);
    const secondary = new THREE.Color(behavior.secondary);
    const core = new THREE.Color(behavior.core);

    this.shells.forEach((mesh, index) => {
      updateDisc(mesh, behavior, mesh.userData.inset, index * 0.015);
      mesh.material.color.copy(index === 0 ? accent : (index === 1 ? secondary : core));
      const alpha = [0.28, 0.16, 0.17][index] * behavior.opacity;
      mesh.material.opacity = alpha + behavior.impulses.flash * (index === 1 ? 0.14 : 0.04);
    });

    const membraneCount = Math.max(1, Math.min(MAX_MEMBRANES, Math.round(behavior.membranes)));
    this.membranes.forEach((line, index) => {
      line.visible = index < membraneCount;
      if (!line.visible) return;
      const positions = line.geometry.attributes.position;
      const inset = 0.3 + (index / Math.max(1, membraneCount - 1)) * 0.5;
      for (let step = 0; step < MEMBRANE_SEGMENTS; step += 1) {
        const angle = (step / MEMBRANE_SEGMENTS) * Math.PI * 2;
        const curl = Math.sin(angle * (2 + index % 3) + behavior.phase * 2 + index) * behavior.membraneCurl * 0.08;
        const point = bodyPoint(angle + curl, behavior, inset + curl);
        positions.setXYZ(step, point.x, point.y, 0.08 + index * 0.004);
      }
      positions.needsUpdate = true;
      line.material.color.copy(index % 3 === 0 ? secondary : accent);
      line.material.opacity = 0.07 + behavior.density * 0.16 + behavior.attention * (index === membraneCount - 1 ? 0.08 : 0);
    });

    const nodeCount = Math.max(0, Math.min(MAX_NODES, Math.round(behavior.nodes)));
    this.nodes.forEach((node, index) => {
      node.visible = index < nodeCount;
      if (!node.visible) return;
      const point = nodePoint(index, behavior);
      node.geometry.attributes.position.setXYZ(0, point.x, point.y, 0.18);
      node.geometry.attributes.position.needsUpdate = true;
      node.material.color.copy(index % 3 === 0 ? secondary : core);
      node.material.size = 0.045 + behavior.attention * 0.04 + (index === 0 ? behavior.audio.treble * 0.035 : 0);
      node.material.opacity = 0.36 + behavior.density * 0.46;
    });

    const traceCount = Math.max(0, Math.min(MAX_TRACES, Math.round(behavior.traces)));
    this.traces.forEach((line, index) => {
      line.visible = index < traceCount;
      if (!line.visible) return;
      const positions = line.geometry.attributes.position;
      const anchor = -0.8 + index * 1.27 + behavior.phase * 0.6 * behavior.direction;
      for (let step = 0; step <= TRACE_SEGMENTS; step += 1) {
        const t = step / TRACE_SEGMENTS;
        const angle = anchor + (t - 0.5) * behavior.traceArc;
        const outside = 1.08 + Math.sin(t * Math.PI) * behavior.traceReach * 0.13;
        const point = bodyPoint(angle, behavior, outside);
        positions.setXYZ(step, point.x, point.y, -0.02);
      }
      positions.needsUpdate = true;
      line.material.color.copy(index % 2 ? secondary : accent);
      line.material.opacity = (0.09 + behavior.attention * 0.13) * Math.sin((index + 1) / (traceCount + 1) * Math.PI);
    });

    this.group.position.x = behavior.impulses.return * -0.055;
    this.group.scale.y = 1 + behavior.impulses.flash * 0.025;
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.group.traverse((object) => {
      object.geometry?.dispose();
      object.material?.dispose();
    });
    this.renderer.dispose();
    this.renderer.forceContextLoss?.();
  }
}

/** Canvas fallback mirrors the same organism model with fixed-size buffers and no dependencies. */
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
    this.dpr = Math.min(DPR_CAP, Math.max(1, dpr || 1));
    this.canvas.width = Math.round(this.width * this.dpr);
    this.canvas.height = Math.round(this.height * this.dpr);
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;
    this.context.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  }

  traceBody(ctx, behavior, inset = 1) {
    for (let index = 0; index <= BODY_SEGMENTS; index += 1) {
      const point = bodyPoint((index % BODY_SEGMENTS) / BODY_SEGMENTS * Math.PI * 2, behavior, inset);
      const x = this.width / 2 + point.x * this.unit;
      const y = this.height / 2 - point.y * this.unit;
      if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
  }

  render(behavior) {
    const interval = behavior.motionScale < 0.5 || behavior.lowPower ? 1 / 15 : 1 / 24;
    if (behavior.time - this.lastFrame < interval) return;
    this.lastFrame = behavior.time;
    const ctx = this.context;
    ctx.clearRect(0, 0, this.width, this.height);
    this.unit = Math.min(this.width / 7.1, this.height / 5.5);

    // Peripheral traces are outside the clipping region and intentionally sparse.
    const traceCount = Math.max(0, Math.min(MAX_TRACES, Math.round(behavior.traces)));
    ctx.lineWidth = Math.max(0.75, this.unit * 0.012);
    ctx.strokeStyle = hexCss(behavior.accent);
    for (let index = 0; index < traceCount; index += 1) {
      ctx.beginPath();
      const anchor = -0.8 + index * 1.27 + behavior.phase * 0.6 * behavior.direction;
      for (let step = 0; step <= TRACE_SEGMENTS; step += 1) {
        const t = step / TRACE_SEGMENTS;
        const point = bodyPoint(anchor + (t - 0.5) * behavior.traceArc, behavior, 1.08 + Math.sin(t * Math.PI) * behavior.traceReach * 0.13);
        const x = this.width / 2 + point.x * this.unit;
        const y = this.height / 2 - point.y * this.unit;
        if (step === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.globalAlpha = 0.08 + behavior.attention * 0.12;
      ctx.stroke();
    }

    const gradient = ctx.createRadialGradient(this.width * 0.44, this.height * 0.4, this.unit * 0.08, this.width / 2, this.height / 2, this.unit * 2.4);
    gradient.addColorStop(0, hexCss(behavior.secondary));
    gradient.addColorStop(0.56, hexCss(behavior.accent));
    gradient.addColorStop(1, hexCss(behavior.core));
    ctx.beginPath();
    this.traceBody(ctx, behavior);
    ctx.globalAlpha = behavior.opacity * 0.48 + behavior.impulses.flash * 0.08;
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.save();
    ctx.beginPath();
    this.traceBody(ctx, behavior, 0.98);
    ctx.clip();
    const membraneCount = Math.max(1, Math.min(MAX_MEMBRANES, Math.round(behavior.membranes)));
    ctx.lineWidth = Math.max(0.7, this.unit * 0.01);
    for (let index = 0; index < membraneCount; index += 1) {
      ctx.beginPath();
      this.traceBody(ctx, behavior, 0.3 + (index / Math.max(1, membraneCount - 1)) * 0.5);
      ctx.globalAlpha = 0.09 + behavior.density * 0.14;
      ctx.strokeStyle = index % 3 === 0 ? hexCss(behavior.secondary) : hexCss(behavior.accent);
      ctx.stroke();
    }
    const nodeCount = Math.max(0, Math.min(MAX_NODES, Math.round(behavior.nodes)));
    for (let index = 0; index < nodeCount; index += 1) {
      const point = nodePoint(index, behavior);
      ctx.beginPath();
      ctx.arc(this.width / 2 + point.x * this.unit, this.height / 2 - point.y * this.unit, this.unit * (0.025 + behavior.attention * 0.012), 0, Math.PI * 2);
      ctx.globalAlpha = 0.35 + behavior.density * 0.45;
      ctx.fillStyle = index % 3 === 0 ? hexCss(behavior.secondary) : hexCss(behavior.core);
      ctx.fill();
    }
    ctx.restore();
    ctx.globalAlpha = 1;
  }

  dispose() {
    this.context.clearRect(0, 0, this.width, this.height);
  }
}
