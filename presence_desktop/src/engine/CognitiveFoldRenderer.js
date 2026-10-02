import * as THREE from "../../node_modules/three/build/three.module.js";

const DPR_CAP = 1.5;
const MAX_PARTICLES = 12;
const MAX_TRACES = 4;
const TRACE_SEGMENTS = 20;
const MOUTH_SEGMENTS = 20;
const hexCss = (value) => `#${Math.round(value).toString(16).padStart(6, "0")}`;

function makeDynamicLine(segments) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array((segments + 1) * 3), 3));
  return geometry;
}

function makeEarGeometry() {
  // A softly curved, unmistakably pointed elf ear. Both ears share this geometry.
  const shape = new THREE.Shape();
  shape.moveTo(0, 0.3);
  shape.quadraticCurveTo(0.78, 0.58, 1.48, 0.02);
  shape.quadraticCurveTo(0.78, -0.5, 0, -0.28);
  shape.quadraticCurveTo(0.16, 0, 0, 0.3);
  return new THREE.ShapeGeometry(shape, 16);
}

function setLinePoint(line, index, x, y, z = 0) {
  line.geometry.attributes.position.setXYZ(index, x, y, z);
}

/**
 * WebGL renderer for one persistent SERA character. Geometry and materials are
 * allocated once; state updates only pose, tint and continuous facial motion.
 */
export class CognitiveFoldRenderer {
  constructor(canvas, width, height, dpr) {
    this.canvas = canvas;
    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-4, 4, 3.2, -3.2, -20, 20);
    this.camera.position.z = 8;
    this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "low-power", premultipliedAlpha: true });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.root = new THREE.Group();
    this.scene.add(this.root);
    this.geometries = new Set();
    this.materials = new Set();
    this.lastFrame = -Infinity;
    this.build();
    this.resize(width, height, dpr);
  }

  rememberGeometry(geometry) {
    this.geometries.add(geometry);
    return geometry;
  }

  rememberMaterial(material) {
    this.materials.add(material);
    return material;
  }

  build() {
    this.scene.add(new THREE.HemisphereLight(0xe9fbff, 0x6f5a91, 2.15));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.2);
    keyLight.position.set(-3, 4, 6);
    this.scene.add(keyLight);

    const bodyGeometry = this.rememberGeometry(new THREE.SphereGeometry(1, 40, 28));
    const bodyMaterial = this.rememberMaterial(new THREE.MeshPhysicalMaterial({
      color: 0xbdeff1,
      emissive: 0x435778,
      emissiveIntensity: 0.28,
      roughness: 0.34,
      metalness: 0.02,
      transparent: true,
      opacity: 0.92,
      clearcoat: 0.75,
      clearcoatRoughness: 0.28,
      depthWrite: false,
    }));
    this.bodyRoot = new THREE.Group();
    this.root.add(this.bodyRoot);

    // Overlapping head and lower body read as one rounded floating creature.
    this.body = new THREE.Mesh(bodyGeometry, bodyMaterial);
    this.body.scale.set(1.12, 1.28, 0.76);
    this.body.position.y = -0.25;
    this.body.renderOrder = 2;
    this.bodyRoot.add(this.body);
    this.head = new THREE.Mesh(bodyGeometry, bodyMaterial);
    this.head.scale.set(1.08, 0.91, 0.72);
    this.head.position.set(0, 0.58, 0.08);
    this.head.renderOrder = 3;
    this.bodyRoot.add(this.head);

    const glowMaterial = this.rememberMaterial(new THREE.MeshBasicMaterial({ color: 0xc8b8ef, transparent: true, opacity: 0.12, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.innerGlow = new THREE.Mesh(bodyGeometry, glowMaterial);
    this.innerGlow.scale.set(0.76, 0.92, 0.58);
    this.innerGlow.position.set(0, -0.04, 0.42);
    this.innerGlow.renderOrder = 4;
    this.bodyRoot.add(this.innerGlow);

    const earGeometry = this.rememberGeometry(makeEarGeometry());
    const earMaterial = this.rememberMaterial(new THREE.MeshPhysicalMaterial({ color: 0xc8b8ef, emissive: 0x554a79, emissiveIntensity: 0.18, roughness: 0.4, clearcoat: 0.6, side: THREE.DoubleSide, transparent: true, opacity: 0.9, depthWrite: false }));
    this.ears = [-1, 1].map((side) => {
      const ear = new THREE.Mesh(earGeometry, earMaterial);
      ear.scale.x = side;
      ear.position.set(side * 0.82, 0.55, -0.06);
      ear.renderOrder = 1;
      this.bodyRoot.add(ear);
      return ear;
    });

    const eyeWhiteGeometry = this.rememberGeometry(new THREE.SphereGeometry(0.31, 24, 18));
    const irisGeometry = this.rememberGeometry(new THREE.CircleGeometry(0.2, 24));
    const pupilGeometry = this.rememberGeometry(new THREE.CircleGeometry(0.1, 20));
    const highlightGeometry = this.rememberGeometry(new THREE.CircleGeometry(0.035, 14));
    const eyeWhiteMaterial = this.rememberMaterial(new THREE.MeshStandardMaterial({ color: 0xf5fbff, roughness: 0.24, transparent: true, opacity: 0.96, depthWrite: false }));
    const irisMaterial = this.rememberMaterial(new THREE.MeshBasicMaterial({ color: 0x5dbbc6, side: THREE.DoubleSide, depthTest: false, depthWrite: false }));
    const pupilMaterial = this.rememberMaterial(new THREE.MeshBasicMaterial({ color: 0x172a43, side: THREE.DoubleSide, depthTest: false, depthWrite: false }));
    const highlightMaterial = this.rememberMaterial(new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide, transparent: true, opacity: 0.9, depthTest: false, depthWrite: false }));
    this.eyes = [-1, 1].map((side) => {
      const group = new THREE.Group();
      group.position.set(side * 0.4, 0.59, 0.75);
      const white = new THREE.Mesh(eyeWhiteGeometry, eyeWhiteMaterial);
      white.scale.set(0.94, 1.18, 0.3);
      group.add(white);
      const iris = new THREE.Mesh(irisGeometry, irisMaterial);
      // Keep the layered facial planes in front of the rounded eye whites.
      // The camera looks down +Z, so these offsets are intentionally generous
      // to avoid depth-buffer/floating-point overlap hiding the iris.
      iris.position.z = 0.31;
      iris.renderOrder = 10;
      const pupil = new THREE.Mesh(pupilGeometry, pupilMaterial);
      pupil.position.z = 0.34;
      pupil.renderOrder = 11;
      const highlight = new THREE.Mesh(highlightGeometry, highlightMaterial);
      highlight.position.set(-0.035, 0.055, 0.38);
      highlight.renderOrder = 12;
      group.add(iris, pupil, highlight);
      group.renderOrder = 7;
      this.bodyRoot.add(group);
      return { group, iris, pupil, highlight };
    });

    const cheekGeometry = this.rememberGeometry(new THREE.CircleGeometry(0.13, 20));
    const cheekMaterial = this.rememberMaterial(new THREE.MeshBasicMaterial({ color: 0xe9a8cf, transparent: true, opacity: 0.16, depthWrite: false }));
    this.cheeks = [-1, 1].map((side) => {
      const cheek = new THREE.Mesh(cheekGeometry, cheekMaterial);
      cheek.position.set(side * 0.62, 0.18, 0.83);
      cheek.scale.y = 0.48;
      this.bodyRoot.add(cheek);
      return cheek;
    });

    const faceMaterial = this.rememberMaterial(new THREE.LineBasicMaterial({ color: 0x294b67, transparent: true, opacity: 0.78, depthWrite: false }));
    this.mouth = new THREE.Line(makeDynamicLine(MOUTH_SEGMENTS), faceMaterial);
    this.rememberGeometry(this.mouth.geometry);
    this.mouth.renderOrder = 8;
    this.bodyRoot.add(this.mouth);
    const noseMaterial = this.rememberMaterial(new THREE.MeshBasicMaterial({ color: 0x7598aa, transparent: true, opacity: 0.45, depthWrite: false }));
    this.nose = new THREE.Mesh(this.rememberGeometry(new THREE.CircleGeometry(0.035, 12)), noseMaterial);
    this.nose.position.set(0, 0.29, 0.87);
    this.nose.scale.y = 0.58;
    this.bodyRoot.add(this.nose);

    const antennaMaterial = this.rememberMaterial(new THREE.LineBasicMaterial({ color: 0xbdeff1, transparent: true, opacity: 0.72, depthWrite: false }));
    this.antenna = new THREE.Line(makeDynamicLine(12), antennaMaterial);
    this.rememberGeometry(this.antenna.geometry);
    this.antenna.renderOrder = 1;
    this.root.add(this.antenna);
    const tipGeometry = this.rememberGeometry(new THREE.SphereGeometry(0.09, 18, 12));
    const tipMaterial = this.rememberMaterial(new THREE.MeshBasicMaterial({ color: 0xbdeff1, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.antennaTip = new THREE.Mesh(tipGeometry, tipMaterial);
    this.root.add(this.antennaTip);

    const particleGeometry = this.rememberGeometry(new THREE.BufferGeometry());
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(MAX_PARTICLES * 3), 3));
    const particleMaterial = this.rememberMaterial(new THREE.PointsMaterial({ color: 0xbdeff1, size: 0.065, transparent: true, opacity: 0.52, blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true }));
    this.particles = new THREE.Points(particleGeometry, particleMaterial);
    this.root.add(this.particles);

    this.traces = Array.from({ length: MAX_TRACES }, (_, index) => {
      const material = this.rememberMaterial(new THREE.LineBasicMaterial({ color: index % 2 ? 0xc8b8ef : 0xbdeff1, transparent: true, opacity: 0.15, depthWrite: false }));
      const line = new THREE.Line(this.rememberGeometry(makeDynamicLine(TRACE_SEGMENTS)), material);
      this.root.add(line);
      return line;
    });
  }

  resize(width, height, dpr) {
    const safeWidth = Math.max(1, width);
    const safeHeight = Math.max(1, height);
    const aspect = safeWidth / safeHeight;
    const vertical = 3.15;
    this.camera.left = -vertical * aspect;
    this.camera.right = vertical * aspect;
    this.camera.top = vertical;
    this.camera.bottom = -vertical;
    this.camera.updateProjectionMatrix();
    this.renderer.setPixelRatio(Math.min(DPR_CAP, Math.max(1, dpr || 1)));
    this.renderer.setSize(safeWidth, safeHeight, false);
  }

  updateMouth(behavior) {
    const openness = Math.min(0.32, behavior.mouthOpen + behavior.voice * 0.3 + behavior.audio.mid * 0.07);
    const width = 0.25 + Math.abs(behavior.smile) * 0.1 + behavior.voice * 0.06;
    for (let index = 0; index <= MOUTH_SEGMENTS; index += 1) {
      const t = index / MOUTH_SEGMENTS;
      const x = (t - 0.5) * width * 2;
      const edge = Math.abs(t - 0.5) * 2;
      const smileCurve = (edge * edge - 0.5) * behavior.smile * -0.16;
      const openCurve = Math.sin(t * Math.PI) * openness;
      setLinePoint(this.mouth, index, x, -0.02 + smileCurve - openCurve * 0.48, 0.9);
    }
    this.mouth.geometry.attributes.position.needsUpdate = true;
  }

  updateAmbientMatter(behavior) {
    const count = Math.max(0, Math.min(MAX_PARTICLES, Math.round(behavior.particles)));
    this.particles.geometry.setDrawRange(0, count);
    const positions = this.particles.geometry.attributes.position;
    for (let index = 0; index < count; index += 1) {
      const angle = index * 2.399963 + behavior.phase * (0.9 + index * 0.03);
      const radius = 1.45 + (index % 3) * 0.2 + behavior.traceReach * 0.18;
      positions.setXYZ(index, Math.cos(angle) * radius, -0.05 + Math.sin(angle) * radius * 0.84, -0.2);
    }
    positions.needsUpdate = true;

    const traceCount = Math.max(0, Math.min(MAX_TRACES, Math.round(behavior.traces)));
    this.traces.forEach((line, index) => {
      line.visible = index < traceCount;
      if (!line.visible) return;
      for (let step = 0; step <= TRACE_SEGMENTS; step += 1) {
        const t = step / TRACE_SEGMENTS;
        const side = index % 2 ? 1 : -1;
        const y = -1.05 + t * 2.25;
        const x = side * (1.32 + Math.sin(t * Math.PI + index) * behavior.traceReach * 0.34);
        setLinePoint(line, step, x, y, -0.3);
      }
      line.geometry.attributes.position.needsUpdate = true;
      line.material.opacity = (0.08 + behavior.internalGlow * 0.13) * behavior.opacity;
    });
  }

  render(behavior) {
    const interval = behavior.motionScale < 0.5 || behavior.lowPower ? 1 / 20 : 1 / 30;
    if (behavior.time - this.lastFrame < interval) return;
    this.lastFrame = behavior.time;

    const accent = new THREE.Color(behavior.accent);
    const secondary = new THREE.Color(behavior.secondary);
    const core = new THREE.Color(behavior.core);
    const bob = Math.sin(behavior.time * (1.3 + behavior.speed)) * behavior.bounce * behavior.motionScale;
    const audioLift = behavior.audio.bass * 0.055 * behavior.motionScale;
    this.root.position.set(behavior.impulses.return * -0.06, bob + behavior.posture + audioLift - 0.12, 0);
    this.root.rotation.z = behavior.lean * -0.22 + Math.sin(behavior.phase * 1.7) * 0.012 * behavior.motionScale;
    this.bodyRoot.scale.set(
      behavior.scale * behavior.squash * (1 + behavior.audio.bass * 0.025),
      behavior.scale * behavior.stretch * (1 + behavior.breath * Math.sin(behavior.time * 1.4) * behavior.motionScale + behavior.voice * 0.035),
      1,
    );

    this.body.material.color.copy(accent).lerp(secondary, 0.24);
    this.body.material.emissive.copy(secondary).multiplyScalar(0.38);
    this.body.material.emissiveIntensity = 0.18 + behavior.internalGlow * 0.46 + behavior.impulses.flash * 0.25;
    this.body.material.opacity = behavior.opacity;
    this.innerGlow.material.color.copy(secondary);
    this.innerGlow.material.opacity = 0.05 + behavior.internalGlow * 0.18 + behavior.voice * 0.08;
    const glowScale = 1 + behavior.audio.bass * 0.09;
    this.innerGlow.scale.set(0.76 * glowScale, 0.92 * glowScale, 0.58 * glowScale);

    this.ears[0].rotation.z = -behavior.earAngle;
    this.ears[1].rotation.z = behavior.earAngle;
    this.ears.forEach((ear, index) => {
      ear.position.y = 0.55 + behavior.earLift + Math.sin(behavior.phase * 2 + index) * 0.025 * behavior.motionScale;
      ear.material.color.copy(secondary).lerp(accent, 0.35);
      ear.material.opacity = behavior.opacity * 0.92;
    });

    const gazeX = (behavior.gazeX + behavior.task.direction * 0.05 * behavior.gazeFocus) * 0.11;
    const gazeY = behavior.gazeY * 0.1;
    this.eyes.forEach((eye, index) => {
      eye.group.scale.y = Math.max(0.07, 1 - behavior.blink * 0.94);
      eye.group.rotation.z = (index === 0 ? -1 : 1) * behavior.expression * 0.08;
      eye.iris.position.set(gazeX, gazeY, 0.31);
      eye.pupil.position.set(gazeX, gazeY, 0.34);
      eye.highlight.position.set(gazeX - 0.035, gazeY + 0.055, 0.38);
      eye.iris.material.color.copy(accent).lerp(core, 0.28);
      eye.pupil.material.color.copy(core);
    });
    this.cheeks.forEach((cheek) => { cheek.material.opacity = (0.11 + Math.max(0, behavior.smile) * 0.13) * behavior.opacity; });
    this.mouth.material.color.copy(core);
    this.updateMouth(behavior);

    const sway = Math.sin(behavior.time * (1.2 + behavior.speed) + behavior.task.direction) * behavior.antennaSway * behavior.motionScale;
    for (let index = 0; index <= 12; index += 1) {
      const t = index / 12;
      setLinePoint(this.antenna, index, sway * t * t, 1.36 + t * 0.7, -0.08 + t * 0.08);
    }
    this.antenna.geometry.attributes.position.needsUpdate = true;
    this.antenna.material.color.copy(accent);
    this.antennaTip.position.set(sway, 2.06, 0.02);
    this.antennaTip.material.color.copy(accent).lerp(secondary, 0.38);
    this.antennaTip.material.opacity = 0.5 + behavior.antennaGlow * 0.42;
    this.antennaTip.scale.setScalar(0.8 + behavior.antennaGlow * 0.42 + behavior.audio.treble * 0.25);

    this.particles.material.color.copy(secondary);
    this.particles.material.opacity = (0.18 + behavior.internalGlow * 0.42) * behavior.opacity;
    this.updateAmbientMatter(behavior);
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.geometries.forEach((geometry) => geometry.dispose());
    this.materials.forEach((material) => material.dispose());
    this.renderer.dispose();
    this.renderer.forceContextLoss?.();
  }
}

/** Canvas 2D fallback draws the same face, ears, antenna and stable silhouette. */
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

  drawEar(ctx, side, behavior) {
    ctx.save();
    ctx.translate(side * 0.77, -0.45 - behavior.earLift);
    ctx.rotate(side * (-0.05 - behavior.earAngle));
    ctx.scale(side, 1);
    ctx.beginPath();
    ctx.moveTo(0, -0.28);
    ctx.quadraticCurveTo(0.75, -0.55, 1.42, 0);
    ctx.quadraticCurveTo(0.75, 0.48, 0, 0.27);
    ctx.closePath();
    ctx.globalAlpha = behavior.opacity * 0.84;
    ctx.fillStyle = hexCss(behavior.secondary);
    ctx.fill();
    ctx.restore();
  }

  render(behavior) {
    const interval = behavior.motionScale < 0.5 || behavior.lowPower ? 1 / 15 : 1 / 24;
    if (behavior.time - this.lastFrame < interval) return;
    this.lastFrame = behavior.time;
    const ctx = this.context;
    ctx.clearRect(0, 0, this.width, this.height);
    const unit = Math.min(this.width / 7.2, this.height / 6.15);
    const bob = Math.sin(behavior.time * (1.3 + behavior.speed)) * behavior.bounce * behavior.motionScale;
    ctx.save();
    ctx.translate(this.width / 2, this.height / 2 + unit * (0.12 - behavior.posture - bob));
    ctx.scale(unit, unit);
    ctx.rotate(behavior.lean * -0.22);

    // Bounded cognition trails sit behind the body, never replacing its identity.
    ctx.lineWidth = 0.018;
    const traceCount = Math.max(0, Math.min(MAX_TRACES, Math.round(behavior.traces)));
    for (let index = 0; index < traceCount; index += 1) {
      const side = index % 2 ? 1 : -1;
      ctx.beginPath();
      for (let step = 0; step <= TRACE_SEGMENTS; step += 1) {
        const t = step / TRACE_SEGMENTS;
        const x = side * (1.32 + Math.sin(t * Math.PI + index) * behavior.traceReach * 0.34);
        const y = 1.05 - t * 2.25;
        if (step === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.globalAlpha = 0.08 + behavior.internalGlow * 0.12;
      ctx.strokeStyle = index % 2 ? hexCss(behavior.secondary) : hexCss(behavior.accent);
      ctx.stroke();
    }

    const sway = Math.sin(behavior.time * (1.2 + behavior.speed) + behavior.task.direction) * behavior.antennaSway * behavior.motionScale;
    ctx.beginPath();
    ctx.moveTo(0, -1.31);
    ctx.quadraticCurveTo(sway * 0.25, -1.72, sway, -2.03);
    ctx.globalAlpha = 0.72;
    ctx.strokeStyle = hexCss(behavior.accent);
    ctx.lineWidth = 0.025;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(sway, -2.03, 0.075 + behavior.antennaGlow * 0.025 + behavior.audio.treble * 0.02, 0, Math.PI * 2);
    ctx.globalAlpha = 0.55 + behavior.antennaGlow * 0.35;
    ctx.fillStyle = hexCss(behavior.secondary);
    ctx.fill();

    this.drawEar(ctx, -1, behavior);
    this.drawEar(ctx, 1, behavior);
    const sx = behavior.scale * behavior.squash * (1 + behavior.audio.bass * 0.025);
    const sy = behavior.scale * behavior.stretch * (1 + behavior.voice * 0.035);
    ctx.save();
    ctx.scale(sx, sy);
    const gradient = ctx.createRadialGradient(-0.38, -0.62, 0.05, 0, 0, 1.5);
    gradient.addColorStop(0, hexCss(behavior.secondary));
    gradient.addColorStop(0.52, hexCss(behavior.accent));
    gradient.addColorStop(1, hexCss(behavior.core));
    ctx.beginPath();
    ctx.moveTo(0, -1.27);
    ctx.bezierCurveTo(0.8, -1.27, 1.16, -0.72, 1.09, 0.1);
    ctx.bezierCurveTo(1.02, 1.04, 0.58, 1.38, 0, 1.42);
    ctx.bezierCurveTo(-0.58, 1.38, -1.02, 1.04, -1.09, 0.1);
    ctx.bezierCurveTo(-1.16, -0.72, -0.8, -1.27, 0, -1.27);
    ctx.closePath();
    ctx.globalAlpha = behavior.opacity;
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.beginPath();
    ctx.ellipse(0, 0.18, 0.72, 0.9, 0, 0, Math.PI * 2);
    ctx.globalAlpha = 0.04 + behavior.internalGlow * 0.14;
    ctx.fillStyle = hexCss(behavior.secondary);
    ctx.fill();

    const gazeX = (behavior.gazeX + behavior.task.direction * 0.05 * behavior.gazeFocus) * 0.1;
    const gazeY = behavior.gazeY * 0.09;
    const eyeHeight = Math.max(0.025, 0.31 * (1 - behavior.blink * 0.94));
    for (const side of [-1, 1]) {
      ctx.beginPath();
      ctx.ellipse(side * 0.4, -0.52, 0.27, eyeHeight, 0, 0, Math.PI * 2);
      ctx.globalAlpha = 0.96;
      ctx.fillStyle = "#f5fbff";
      ctx.fill();
      ctx.beginPath();
      ctx.ellipse(side * 0.4 + gazeX, -0.52 + gazeY, 0.14, Math.max(0.02, eyeHeight * 0.62), 0, 0, Math.PI * 2);
      ctx.fillStyle = hexCss(behavior.accent);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(side * 0.4 + gazeX, -0.52 + gazeY, Math.min(0.067, eyeHeight * 0.48), 0, Math.PI * 2);
      ctx.fillStyle = hexCss(behavior.core);
      ctx.fill();
    }

    ctx.beginPath();
    ctx.ellipse(0, -0.22, 0.035, 0.02, 0, 0, Math.PI * 2);
    ctx.globalAlpha = 0.42;
    ctx.fillStyle = hexCss(behavior.core);
    ctx.fill();
    const openness = Math.min(0.32, behavior.mouthOpen + behavior.voice * 0.3 + behavior.audio.mid * 0.07);
    ctx.beginPath();
    for (let index = 0; index <= MOUTH_SEGMENTS; index += 1) {
      const t = index / MOUTH_SEGMENTS;
      const edge = Math.abs(t - 0.5) * 2;
      const x = (t - 0.5) * (0.5 + Math.abs(behavior.smile) * 0.2);
      const y = 0.02 + (edge * edge - 0.5) * behavior.smile * -0.16 + Math.sin(t * Math.PI) * openness * 0.48;
      if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.globalAlpha = 0.76;
    ctx.strokeStyle = hexCss(behavior.core);
    ctx.lineWidth = 0.025;
    ctx.stroke();
    ctx.restore();

    const particleCount = Math.max(0, Math.min(MAX_PARTICLES, Math.round(behavior.particles)));
    for (let index = 0; index < particleCount; index += 1) {
      const angle = index * 2.399963 + behavior.phase * (0.9 + index * 0.03);
      const radius = 1.45 + (index % 3) * 0.2;
      ctx.beginPath();
      ctx.arc(Math.cos(angle) * radius, Math.sin(angle) * radius * 0.84, 0.025, 0, Math.PI * 2);
      ctx.globalAlpha = 0.16 + behavior.internalGlow * 0.34;
      ctx.fillStyle = hexCss(behavior.secondary);
      ctx.fill();
    }
    ctx.restore();
    ctx.globalAlpha = 1;
  }

  dispose() {
    this.context.clearRect(0, 0, this.width, this.height);
  }
}
