/**
 * SERA 2.0 — PRIMARY PRESENCE ENGINE
 * Dedicated WebGL/Three.js Computational Consciousness Visualization Engine
 * 
 * 8-Layer Architecture:
 * - Layer 1: Central Core (White-hot center, 3D simplex noise distortion, cyan/violet corona)
 * - Layer 2: Inner Energy (Branching filaments, plasma streams, localized turbulence)
 * - Layer 3: Computational Rings (Independent radii, speeds, ticks, segmentation, breaks)
 * - Layer 4: Information / Glyph Band (Procedural cybernetic glyphs, compression, expansion)
 * - Layer 5: Geometric Topology Network (Dynamic 3D KNN graph forming & dissolving)
 * - Layer 6: Radial Filaments (Turbulent outward energy tendrils, audio responsive)
 * - Layer 7: Particle Field (Volumetric GPU particle system with state-driven vector fields)
 * - Layer 8: Event Effects & Task Visualization Bridge (Objective-specific structures)
 * 
 * Author: Keshava Pandi A S <keshavapandi@gmail.com>
 */

import * as THREE from "../../node_modules/three/build/three.module.js";
import { PresenceBehaviorEngine } from "./PresenceBehaviorEngine.js";

// Simplex Noise 3D GLSL Snippet
const GLSL_SIMPLEX_NOISE = `
vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x, 289.0);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}
float snoise(vec3 v){
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + 1.0 * C.xxx;
  vec3 x2 = x0 - i2 + 2.0 * C.xxx;
  vec3 x3 = x0 - 1.0 + 3.0 * C.xxx;
  i = mod(i, 289.0);
  vec4 p = permute(permute(permute(
             i.z + vec4(0.0, i1.z, i2.z, 1.0))
           + i.y + vec4(0.0, i1.y, i2.y, 1.0))
           + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3  ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}
`;

export class PresenceEngine {
  constructor(canvas) {
    this.canvas = canvas;
    this.width = canvas.clientWidth || 356;
    this.height = canvas.clientHeight || 250;

    // Operational State
    this.state = "IDLE";
    this.taskType = "GENERAL";
    this.audioAmplitude = 0.0;
    this.audioFrequency = 0.0;
    this.visualEntropy = 0.0;
    this.targetState = "IDLE";
    this.stateBlend = 1.0;

    // Master Animation Clock
    this.clock = new THREE.Clock();
    this.time = 0;

    // Presence Behavior Engine (Dynamic Energy, Attention & Organic Variation)
    this.behavior = new PresenceBehaviorEngine();

    this.initScene();
    this.initLayers();
    this.setupResize();
  }

  initScene() {
    // 1. Scene
    this.scene = new THREE.Scene();

    // 2. Camera (Perspective with good depth, scaled for compact glass box)
    this.camera = new THREE.PerspectiveCamera(45, this.width / this.height, 0.1, 1000);
    this.camera.position.set(0, 0, 18.5);

    // 3. Renderer with True Alpha Transparency
    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
      premultipliedAlpha: false,
    });
    this.renderer.setSize(this.width, this.height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setClearColor(0x000000, 0); // 100% Alpha Transparent
  }

  initLayers() {
    this.rootGroup = new THREE.Group();
    this.scene.add(this.rootGroup);

    // Layer 1: Central Core
    this.buildLayer1_CentralCore();

    // Layer 2: Inner Energy & Filaments
    this.buildLayer2_InnerEnergy();

    // Layer 3: Computational Concentric Rings
    this.buildLayer3_ComputationalRings();

    // Layer 4: Information / Glyph Band
    this.buildLayer4_GlyphBand();

    // Layer 5: Geometric Topology Network
    this.buildLayer5_TopologyNetwork();

    // Layer 6: Radial Filaments
    this.buildLayer6_RadialFilaments();

    // Layer 7: Particle Field
    this.buildLayer7_ParticleField();

    // Layer 8: Task Visualization Bridge
    this.buildLayer8_TaskBridge();
  }

  // ─── Layer 1: Central Core ────────────────────────────────────────────────
  buildLayer1_CentralCore() {
    this.coreGroup = new THREE.Group();
    this.rootGroup.add(this.coreGroup);

    // Shader Material for Luminous Organic Computing Core
    this.coreUniforms = {
      uTime: { value: 0 },
      uAmplitude: { value: 0 },
      uStatePulse: { value: 1.0 },
      uNoiseScale: { value: 1.8 },
      uDistortion: { value: 0.35 },
      uWhiteHot: { value: new THREE.Color(0xffffff) },
      uCyan: { value: new THREE.Color(0x00f0ff) },
      uCobalt: { value: new THREE.Color(0x0055ff) },
      uViolet: { value: new THREE.Color(0x8a2be2) },
      uGlitchRed: { value: new THREE.Color(0xff0055) },
      uGlitchIntensity: { value: 0.0 },
    };

    const coreVertexShader = `
      ${GLSL_SIMPLEX_NOISE}
      varying vec3 vNormal;
      varying vec3 vPosition;
      varying float vNoise;
      uniform float uTime;
      uniform float uDistortion;
      uniform float uNoiseScale;
      uniform float uAmplitude;

      void main() {
        vNormal = normalize(normalMatrix * normal);
        
        // Multi-octave organic noise displacement
        float n1 = snoise(position * uNoiseScale + vec3(uTime * 0.4));
        float n2 = snoise(position * (uNoiseScale * 2.0) - vec3(uTime * 0.7));
        float combinedNoise = (n1 * 0.65 + n2 * 0.35);
        vNoise = combinedNoise;

        // Radial pressure displacement
        float disp = combinedNoise * (uDistortion + uAmplitude * 0.4);
        vec3 newPos = position + normal * disp;

        vPosition = newPos;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(newPos, 1.0);
      }
    `;

    const coreFragmentShader = `
      varying vec3 vNormal;
      varying vec3 vPosition;
      varying float vNoise;
      uniform vec3 uWhiteHot;
      uniform vec3 uCyan;
      uniform vec3 uCobalt;
      uniform vec3 uViolet;
      uniform vec3 uGlitchRed;
      uniform float uGlitchIntensity;
      uniform float uAmplitude;

      void main() {
        // Fresnel glow
        vec3 viewDir = normalize(-vPosition);
        float fresnel = dot(viewDir, vNormal);
        fresnel = clamp(1.0 - abs(fresnel), 0.0, 1.0);
        float coreCenter = clamp(dot(viewDir, vNormal), 0.0, 1.0);

        // Gradient: White-Hot Center -> Cyan -> Cobalt -> Violet Edge
        vec3 color = mix(uCobalt, uCyan, smoothstep(0.15, 0.75, coreCenter + vNoise * 0.35));
        color = mix(color, uWhiteHot, smoothstep(0.75, 0.98, coreCenter + uAmplitude * 0.25));
        color = mix(color, uViolet, smoothstep(0.35, 0.85, fresnel));

        // Glitch injection for BROKEN state
        if (uGlitchIntensity > 0.0) {
          color = mix(color, uGlitchRed, uGlitchIntensity * (sin(vPosition.y * 35.0 + vPosition.x * 20.0) * 0.5 + 0.5));
        }

        // Emissive alpha with smooth organic falloff allowing inner structure to shine through
        float alpha = clamp(coreCenter * 0.65 + pow(fresnel, 1.8) * 0.75, 0.0, 0.92);
        gl_FragColor = vec4(color, alpha);
      }
    `;

    const coreGeo = new THREE.IcosahedronGeometry(1.6, 64);
    this.coreMaterial = new THREE.ShaderMaterial({
      uniforms: this.coreUniforms,
      vertexShader: coreVertexShader,
      fragmentShader: coreFragmentShader,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.coreMesh = new THREE.Mesh(coreGeo, this.coreMaterial);
    this.coreGroup.add(this.coreMesh);

    // Dynamic Inner Wireframe Lattice (Evolving Geometric Topology)
    const latticeGeo = new THREE.IcosahedronGeometry(0.95, 1);
    const latticeMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      wireframe: true,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending,
    });
    this.innerLattice = new THREE.Mesh(latticeGeo, latticeMat);
    this.coreGroup.add(this.innerLattice);

    // Inner Singularity Micro-Particles (Swirling High-Energy Core)
    const singCount = 180;
    const singPositions = new Float32Array(singCount * 3);
    this.singParticles = [];

    for (let s = 0; s < singCount; s++) {
      const r = 0.2 + Math.random() * 0.65;
      const th = Math.random() * Math.PI * 2;
      const ph = Math.random() * Math.PI;
      const x = r * Math.sin(ph) * Math.cos(th);
      const y = r * Math.sin(ph) * Math.sin(th);
      const z = r * Math.cos(ph);

      singPositions[s * 3] = x;
      singPositions[s * 3 + 1] = y;
      singPositions[s * 3 + 2] = z;

      this.singParticles.push({
        r,
        th,
        ph,
        speedTh: (Math.random() * 2.5 + 1.2) * (Math.random() > 0.5 ? 1 : -1),
        speedPh: (Math.random() * 1.8 + 0.6) * (Math.random() > 0.5 ? 1 : -1),
      });
    }

    const singGeo = new THREE.BufferGeometry();
    singGeo.setAttribute("position", new THREE.BufferAttribute(singPositions, 3));
    const singMat = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 0.05,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
    });
    this.singularityMesh = new THREE.Points(singGeo, singMat);
    this.coreGroup.add(this.singularityMesh);
  }

  // ─── Layer 2: Inner Energy ────────────────────────────────────────────────
  buildLayer2_InnerEnergy() {
    this.energyGroup = new THREE.Group();
    this.rootGroup.add(this.energyGroup);

    // Dynamic Energy Filaments connecting core to computation perimeter
    const strandCount = 18;
    this.energyStrands = [];

    for (let i = 0; i < strandCount; i++) {
      const points = [];
      const numPoints = 24;
      const angle = (i / strandCount) * Math.PI * 2;
      const rStart = 1.0;
      const rEnd = 2.8;

      for (let j = 0; j < numPoints; j++) {
        const t = j / (numPoints - 1);
        const r = rStart + (rEnd - rStart) * t;
        points.push(new THREE.Vector3(
          Math.cos(angle) * r,
          Math.sin(angle) * r,
          (Math.random() - 0.5) * 0.5
        ));
      }

      const curve = new THREE.CatmullRomCurve3(points);
      const tubeGeo = new THREE.TubeGeometry(curve, 32, 0.02, 6, false);
      const tubeMat = new THREE.MeshBasicMaterial({
        color: i % 2 === 0 ? 0x00f0ff : 0x8a2be2,
        transparent: true,
        opacity: 0.45,
        blending: THREE.AdditiveBlending,
      });

      const strandMesh = new THREE.Mesh(tubeGeo, tubeMat);
      strandMesh.userData = {
        baseAngle: angle,
        speed: (Math.random() * 0.4 + 0.2) * (i % 2 === 0 ? 1 : -1),
        originalPoints: points.map(p => p.clone()),
      };

      this.energyStrands.push(strandMesh);
      this.energyGroup.add(strandMesh);
    }
  }

  // ─── Layer 3: Computational Rings ─────────────────────────────────────────
  buildLayer3_ComputationalRings() {
    this.ringsGroup = new THREE.Group();
    this.rootGroup.add(this.ringsGroup);

    this.rings = [];
    const ringConfigs = [
      { radius: 2.2, width: 0.04, segments: 6, speed: 0.4, color: 0x00f0ff, dash: 0.7 },
      { radius: 2.6, width: 0.02, segments: 12, speed: -0.3, color: 0x00aaff, dash: 0.4 },
      { radius: 3.1, width: 0.06, segments: 4, speed: 0.6, color: 0x8a2be2, dash: 0.8 },
      { radius: 3.7, width: 0.03, segments: 16, speed: -0.2, color: 0x00f0ff, dash: 0.5 },
      { radius: 4.4, width: 0.015, segments: 24, speed: 0.15, color: 0x00ffff, dash: 0.3 },
    ];

    ringConfigs.forEach((cfg, idx) => {
      const ringContainer = new THREE.Group();

      // Broken arc segments with precise gaps
      const arcCount = cfg.segments;
      const arcSpan = (Math.PI * 2 / arcCount) * cfg.dash;

      for (let a = 0; a < arcCount; a++) {
        const startAng = (a / arcCount) * Math.PI * 2;
        const arcGeo = new THREE.RingGeometry(cfg.radius, cfg.radius + cfg.width, 32, 1, startAng, arcSpan);
        const arcMat = new THREE.MeshBasicMaterial({
          color: cfg.color,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.75,
          blending: THREE.AdditiveBlending,
        });
        const arcMesh = new THREE.Mesh(arcGeo, arcMat);
        ringContainer.add(arcMesh);
      }

      // Add sub-ticks on outer rings
      if (idx >= 2) {
        const tickCount = cfg.segments * 4;
        const tickGeo = new THREE.BufferGeometry();
        const tickPositions = [];

        for (let t = 0; t < tickCount; t++) {
          const ang = (t / tickCount) * Math.PI * 2;
          const r1 = cfg.radius + cfg.width * 1.5;
          const r2 = r1 + 0.08;
          tickPositions.push(Math.cos(ang) * r1, Math.sin(ang) * r1, 0);
          tickPositions.push(Math.cos(ang) * r2, Math.sin(ang) * r2, 0);
        }

        tickGeo.setAttribute("position", new THREE.Float32BufferAttribute(tickPositions, 3));
        const tickMat = new THREE.LineBasicMaterial({
          color: 0x00f0ff,
          transparent: true,
          opacity: 0.4,
          blending: THREE.AdditiveBlending,
        });
        const tickLines = new THREE.LineSegments(tickGeo, tickMat);
        ringContainer.add(tickLines);
      }

      ringContainer.userData = {
        baseSpeed: cfg.speed,
        currentSpeed: cfg.speed,
        radius: cfg.radius,
      };

      this.rings.push(ringContainer);
      this.ringsGroup.add(ringContainer);
    });
  }

  // ─── Layer 4: Information / Glyph Band ────────────────────────────────────
  buildLayer4_GlyphBand() {
    this.glyphGroup = new THREE.Group();
    this.rootGroup.add(this.glyphGroup);

    // Procedural SERA Cybernetic Glyph Texture on Dynamic Canvas
    const canvas = document.createElement("canvas");
    canvas.width = 2048;
    canvas.height = 128;
    const ctx = canvas.getContext("2d");

    // Draw procedural cybernetic glyphs & data marks (NOT anime glyphs)
    ctx.fillStyle = "rgba(0,0,0,0)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = "#00f0ff";
    ctx.fillStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.font = "bold 20px 'JetBrains Mono', monospace";

    const symbols = [
      "⟦SERA::ANALYSIS⟧", "0x7F4A", "⟁", "⌬", "⎔", "⋈", "∇·E=ρ", "∑λ_i",
      "⟨01101001⟩", "⊳⊳PARALLEL_SYNC", "⟐", "⌖", "0xFF80", "⎇", "⎈",
      "TOPOLOGY_RECONFIG", "λ→∞", "§101", "⟡", "⧉", "INTENT::RECOGNIZE"
    ];

    let x = 20;
    while (x < canvas.width - 100) {
      const sym = symbols[Math.floor(Math.random() * symbols.length)];
      ctx.fillText(sym, x, 70);

      // Micro ticks and geometric marks
      ctx.strokeRect(x - 6, 40, 2, 40);
      ctx.beginPath();
      ctx.moveTo(x + 120, 50);
      ctx.lineTo(x + 150, 50);
      ctx.lineTo(x + 160, 65);
      ctx.stroke();

      x += 180;
    }

    this.glyphTexture = new THREE.CanvasTexture(canvas);
    this.glyphTexture.wrapS = THREE.RepeatWrapping;
    this.glyphTexture.wrapT = THREE.ClampToEdgeWrapping;

    // Cylindrical / Toroidal Band
    const bandRadius = 3.35;
    const bandHeight = 0.45;
    const bandGeo = new THREE.CylinderGeometry(bandRadius, bandRadius, bandHeight, 64, 1, true);
    const bandMat = new THREE.MeshBasicMaterial({
      map: this.glyphTexture,
      transparent: true,
      opacity: 0.85,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.glyphMesh = new THREE.Mesh(bandGeo, bandMat);
    this.glyphMesh.rotation.x = Math.PI * 0.42; // Tilted holographic angle
    this.glyphGroup.add(this.glyphMesh);
  }

  // ─── Layer 5: Geometric Topology Network ──────────────────────────────────
  buildLayer5_TopologyNetwork() {
    this.topologyGroup = new THREE.Group();
    this.rootGroup.add(this.topologyGroup);

    // 3D Nodes floating in space
    this.topologyNodeCount = 48;
    this.nodes = [];
    const nodePositions = new Float32Array(this.topologyNodeCount * 3);

    for (let i = 0; i < this.topologyNodeCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos((Math.random() * 2) - 1);
      const r = Math.random() * 2.2 + 2.0;

      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi) * 0.6; // Slight flattening

      this.nodes.push({
        pos: new THREE.Vector3(x, y, z),
        basePos: new THREE.Vector3(x, y, z),
        vel: new THREE.Vector3(
          (Math.random() - 0.5) * 0.015,
          (Math.random() - 0.5) * 0.015,
          (Math.random() - 0.5) * 0.015
        ),
      });

      nodePositions[i * 3] = x;
      nodePositions[i * 3 + 1] = y;
      nodePositions[i * 3 + 2] = z;
    }

    // Node Points Mesh
    const nodeGeo = new THREE.BufferGeometry();
    nodeGeo.setAttribute("position", new THREE.BufferAttribute(nodePositions, 3));
    const nodeMat = new THREE.PointsMaterial({
      color: 0x00f0ff,
      size: 0.12,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
    });
    this.nodePoints = new THREE.Points(nodeGeo, nodeMat);
    this.topologyGroup.add(this.nodePoints);

    // Dynamic Connections (Line Segments)
    const maxLines = (this.topologyNodeCount * (this.topologyNodeCount - 1)) / 2;
    this.edgePositions = new Float32Array(maxLines * 6);
    this.edgeColors = new Float32Array(maxLines * 6);

    this.edgeGeo = new THREE.BufferGeometry();
    this.edgeGeo.setAttribute("position", new THREE.BufferAttribute(this.edgePositions, 3));
    this.edgeGeo.setAttribute("color", new THREE.BufferAttribute(this.edgeColors, 3));

    const edgeMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.7,
      blending: THREE.AdditiveBlending,
    });

    this.edgeLines = new THREE.LineSegments(this.edgeGeo, edgeMat);
    this.topologyGroup.add(this.edgeLines);
  }

  // ─── Layer 6: Radial Filaments ────────────────────────────────────────────
  buildLayer6_RadialFilaments() {
    this.filamentGroup = new THREE.Group();
    this.rootGroup.add(this.filamentGroup);

    const filamentCount = 14;
    this.filaments = [];

    for (let f = 0; f < filamentCount; f++) {
      const angle = (f / filamentCount) * Math.PI * 2;
      const pts = [];
      const numPts = 16;
      for (let p = 0; p < numPts; p++) {
        const t = p / (numPts - 1);
        const r = 2.5 + t * 2.8;
        pts.push(new THREE.Vector3(
          Math.cos(angle) * r,
          Math.sin(angle) * r,
          0
        ));
      }

      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const mat = new THREE.LineBasicMaterial({
        color: f % 3 === 0 ? 0x8a2be2 : 0x00f0ff,
        transparent: true,
        opacity: 0.35,
        blending: THREE.AdditiveBlending,
      });

      const line = new THREE.Line(geo, mat);
      line.userData = { angle, basePts: pts.map(pt => pt.clone()) };
      this.filaments.push(line);
      this.filamentGroup.add(line);
    }
  }

  // ─── Layer 7: Particle Field ──────────────────────────────────────────────
  buildLayer7_ParticleField() {
    this.particleGroup = new THREE.Group();
    this.rootGroup.add(this.particleGroup);

    this.particleCount = 2800;
    this.particlePositions = new Float32Array(this.particleCount * 3);
    this.particleVelocities = [];
    this.particleOriginals = [];

    for (let i = 0; i < this.particleCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos((Math.random() * 2) - 1);
      const r = Math.random() * 4.8 + 0.6;

      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = (Math.random() - 0.5) * 2.5;

      this.particlePositions[i * 3] = x;
      this.particlePositions[i * 3 + 1] = y;
      this.particlePositions[i * 3 + 2] = z;

      this.particleOriginals.push(new THREE.Vector3(x, y, z));
      this.particleVelocities.push(new THREE.Vector3(
        (Math.random() - 0.5) * 0.01,
        (Math.random() - 0.5) * 0.01,
        (Math.random() - 0.5) * 0.01
      ));
    }

    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.BufferAttribute(this.particlePositions, 3));

    // Particle sprite
    const pMat = new THREE.PointsMaterial({
      color: 0x00f0ff,
      size: 0.065,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    this.particleSystem = new THREE.Points(pGeo, pMat);
    this.particleGroup.add(this.particleSystem);
  }

  // ─── Layer 8: Task Visualization Bridge (Multi-Task Structural Engine) ──
  buildLayer8_TaskBridge() {
    this.taskBridgeGroup = new THREE.Group();
    this.rootGroup.add(this.taskBridgeGroup);

    this.activeTaskType = null;
    this.taskStartTime = 0;
    this.taskStructureOpacity = 0.0;
    this.targetTaskOpacity = 0.0;

    // 1. GREETING STRUCTURE ("Hi", "Hello")
    // Subtle localized harmonic ripple ring
    this.greetingGroup = new THREE.Group();
    this.taskBridgeGroup.add(this.greetingGroup);
    const greetGeo = new THREE.RingGeometry(1.6, 1.66, 64);
    const greetMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.0,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    });
    this.greetingMesh = new THREE.Mesh(greetGeo, greetMat);
    this.greetingGroup.add(this.greetingMesh);

    // 2. TIME / QUERY INSTANT STRUCTURE ("What time is it?")
    // Chronometer dial with 12 radial hour markers, 60 sub-ticks, and fast needle
    this.timeGroup = new THREE.Group();
    this.taskBridgeGroup.add(this.timeGroup);
    
    const timeDialGeo = new THREE.RingGeometry(3.6, 3.65, 64);
    const timeDialMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.0,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    });
    this.timeDialMesh = new THREE.Mesh(timeDialGeo, timeDialMat);
    this.timeGroup.add(this.timeDialMesh);

    // 12 hour tick marks
    const tickPositions = [];
    for (let h = 0; h < 12; h++) {
      const ang = (h / 12) * Math.PI * 2;
      tickPositions.push(Math.cos(ang) * 3.4, Math.sin(ang) * 3.4, 0);
      tickPositions.push(Math.cos(ang) * 3.8, Math.sin(ang) * 3.8, 0);
    }
    const timeTickGeo = new THREE.BufferGeometry();
    timeTickGeo.setAttribute("position", new THREE.Float32BufferAttribute(tickPositions, 3));
    this.timeTickMat = new THREE.LineBasicMaterial({
      color: 0x8a2be2,
      transparent: true,
      opacity: 0.0,
      blending: THREE.AdditiveBlending,
    });
    this.timeTicks = new THREE.LineSegments(timeTickGeo, this.timeTickMat);
    this.timeGroup.add(this.timeTicks);

    // Rotating chronometer vector hand
    const handGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(0, 3.55, 0)
    ]);
    this.timeHandMat = new THREE.LineBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.0,
      linewidth: 2,
      blending: THREE.AdditiveBlending,
    });
    this.timeHand = new THREE.Line(handGeo, this.timeHandMat);
    this.timeGroup.add(this.timeHand);

    // 3. BROWSER / OPEN APP STRUCTURE ("Open Chrome")
    // Directional conduit beam + flowing packets + holographic target reticle
    this.browserGroup = new THREE.Group();
    this.taskBridgeGroup.add(this.browserGroup);

    // Directional conduit curves
    const conduitCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(1.6, 0.4, 0.2),
      new THREE.Vector3(3.0, 0.6, -0.1),
      new THREE.Vector3(4.2, 0.8, 0),
    ]);
    const conduitGeo = new THREE.TubeGeometry(conduitCurve, 40, 0.035, 8, false);
    this.browserConduitMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.0,
      blending: THREE.AdditiveBlending,
    });
    this.browserConduit = new THREE.Mesh(conduitGeo, this.browserConduitMat);
    this.browserGroup.add(this.browserConduit);

    // Flowing packets along conduit
    this.conduitPackets = [];
    for (let p = 0; p < 6; p++) {
      const pGeo = new THREE.SphereGeometry(0.08, 12, 12);
      const pMat = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.0,
        blending: THREE.AdditiveBlending,
      });
      const pMesh = new THREE.Mesh(pGeo, pMat);
      pMesh.userData = { offset: p / 6 };
      this.conduitPackets.push(pMesh);
      this.browserGroup.add(pMesh);
    }

    // Target reticle at destination
    const reticleGeo = new THREE.RingGeometry(0.45, 0.52, 32);
    this.browserReticleMat = new THREE.MeshBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.0,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    });
    this.browserReticle = new THREE.Mesh(reticleGeo, this.browserReticleMat);
    this.browserReticle.position.set(4.2, 0.8, 0);
    this.browserGroup.add(this.browserReticle);

    // 4. WEB SEARCH / RESEARCH STRUCTURE ("Search the web")
    // Branching fractal tree terminating in query result nodes
    this.searchGroup = new THREE.Group();
    this.taskBridgeGroup.add(this.searchGroup);

    this.searchBranches = [];
    this.searchNodes = [];
    const branchAngles = [0.35, 1.1, 2.4, -0.7, -2.1];
    
    branchAngles.forEach((ang, idx) => {
      // Main branch
      const r1 = 1.4;
      const r2 = 3.6;
      const p1 = new THREE.Vector3(Math.cos(ang) * r1, Math.sin(ang) * r1, 0);
      const p2 = new THREE.Vector3(Math.cos(ang) * r2, Math.sin(ang) * r2, (idx % 2 === 0 ? 0.4 : -0.4));
      
      const bGeo = new THREE.BufferGeometry().setFromPoints([p1, p2]);
      const bMat = new THREE.LineBasicMaterial({
        color: idx % 2 === 0 ? 0x00f0ff : 0x8a2be2,
        transparent: true,
        opacity: 0.0,
        blending: THREE.AdditiveBlending,
      });
      const bLine = new THREE.Line(bGeo, bMat);
      this.searchBranches.push(bLine);
      this.searchGroup.add(bLine);

      // Sub-forks terminating in result nodes
      [-0.25, 0.25].forEach(subAng => {
        const p3 = new THREE.Vector3(
          Math.cos(ang + subAng) * (r2 + 1.2),
          Math.sin(ang + subAng) * (r2 + 1.2),
          p2.z + (subAng > 0 ? 0.3 : -0.3)
        );
        const subGeo = new THREE.BufferGeometry().setFromPoints([p2, p3]);
        const subMat = new THREE.LineBasicMaterial({
          color: 0x00f0ff,
          transparent: true,
          opacity: 0.0,
          blending: THREE.AdditiveBlending,
        });
        const subLine = new THREE.Line(subGeo, subMat);
        this.searchBranches.push(subLine);
        this.searchGroup.add(subLine);

        // Result node
        const nGeo = new THREE.SphereGeometry(0.12, 16, 16);
        const nMat = new THREE.MeshBasicMaterial({
          color: 0xffffff,
          transparent: true,
          opacity: 0.0,
          blending: THREE.AdditiveBlending,
        });
        const nMesh = new THREE.Mesh(nGeo, nMat);
        nMesh.position.copy(p3);
        this.searchNodes.push(nMesh);
        this.searchGroup.add(nMesh);
      });
    });

    // 5. VISION / SCREEN ANALYSIS STRUCTURE ("Analyze my screen")
    // Holographic capture frame + grid + sweeping laser line
    this.visionGroup = new THREE.Group();
    this.taskBridgeGroup.add(this.visionGroup);

    // Rectangular frame
    const framePts = [
      new THREE.Vector3(-2.8, -1.8, 0),
      new THREE.Vector3(2.8, -1.8, 0),
      new THREE.Vector3(2.8, 1.8, 0),
      new THREE.Vector3(-2.8, 1.8, 0),
      new THREE.Vector3(-2.8, -1.8, 0),
    ];
    const frameGeo = new THREE.BufferGeometry().setFromPoints(framePts);
    this.visionFrameMat = new THREE.LineBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.0,
      linewidth: 2,
      blending: THREE.AdditiveBlending,
    });
    this.visionFrame = new THREE.Line(frameGeo, this.visionFrameMat);
    this.visionGroup.add(this.visionFrame);

    // Screen grid lines
    const gridPositions = [];
    for (let gx = -2.0; gx <= 2.0; gx += 0.8) {
      gridPositions.push(gx, -1.8, 0, gx, 1.8, 0);
    }
    for (let gy = -1.2; gy <= 1.2; gy += 0.6) {
      gridPositions.push(-2.8, gy, 0, 2.8, gy, 0);
    }
    const gridGeo = new THREE.BufferGeometry();
    gridGeo.setAttribute("position", new THREE.Float32BufferAttribute(gridPositions, 3));
    this.visionGridMat = new THREE.LineBasicMaterial({
      color: 0x0055ff,
      transparent: true,
      opacity: 0.0,
      blending: THREE.AdditiveBlending,
    });
    this.visionGrid = new THREE.LineSegments(gridGeo, this.visionGridMat);
    this.visionGroup.add(this.visionGrid);

    // Sweeping laser scanline
    const laserGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-2.8, 0, 0.02),
      new THREE.Vector3(2.8, 0, 0.02),
    ]);
    this.visionLaserMat = new THREE.LineBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.0,
      linewidth: 3,
      blending: THREE.AdditiveBlending,
    });
    this.visionLaser = new THREE.Line(laserGeo, this.visionLaserMat);
    this.visionGroup.add(this.visionLaser);

    // 6. FILES ORGANIZATION STRUCTURE ("Organize these files")
    // 36 discrete file particles clustering from chaos into 6x6 matrix
    this.filesGroup = new THREE.Group();
    this.taskBridgeGroup.add(this.filesGroup);

    this.fileBlocks = [];
    const fileCount = 36;
    for (let f = 0; f < fileCount; f++) {
      const bGeo = new THREE.RingGeometry(0.08, 0.12, 4); // Diamond / square glyph
      const bMat = new THREE.MeshBasicMaterial({
        color: f % 2 === 0 ? 0x00f0ff : 0x8a2be2,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending,
      });
      const bMesh = new THREE.Mesh(bGeo, bMat);
      
      // Random chaotic start position
      const rChaos = Math.random() * 2.5 + 2.2;
      const angChaos = Math.random() * Math.PI * 2;
      bMesh.userData = {
        chaosPos: new THREE.Vector3(Math.cos(angChaos) * rChaos, Math.sin(angChaos) * rChaos, (Math.random() - 0.5) * 1.5),
        targetPos: new THREE.Vector3(
          ((f % 6) - 2.5) * 0.75,
          (Math.floor(f / 6) - 2.5) * 0.75,
          0
        ),
      };
      bMesh.position.copy(bMesh.userData.chaosPos);
      this.fileBlocks.push(bMesh);
      this.filesGroup.add(bMesh);
    }

    // 7. CODE / SCRIPTING STRUCTURE ("Write code")
    // 6 vertical cascading cybernetic code streams
    this.codeGroup = new THREE.Group();
    this.taskBridgeGroup.add(this.codeGroup);

    this.codeStreams = [];
    const streamCols = 6;
    for (let c = 0; c < streamCols; c++) {
      const colX = ((c / (streamCols - 1)) - 0.5) * 5.0;
      const pts = [];
      const codeDots = 14;
      for (let d = 0; d < codeDots; d++) {
        pts.push(new THREE.Vector3(colX, 2.8 - d * 0.42, (Math.random() - 0.5) * 0.4));
      }
      const cGeo = new THREE.BufferGeometry().setFromPoints(pts);
      const cMat = new THREE.PointsMaterial({
        color: 0x00f0ff,
        size: 0.09,
        transparent: true,
        opacity: 0.0,
        blending: THREE.AdditiveBlending,
      });
      const cPoints = new THREE.Points(cGeo, cMat);
      cPoints.userData = { colX, speed: Math.random() * 1.2 + 0.8 };
      this.codeStreams.push(cPoints);
      this.codeGroup.add(cPoints);
    }

    // 8. DIAGNOSTICS / SYSTEM SCAN STRUCTURE ("Run system diagnostics")
    // Rotating 360-degree radar/lidar sweep + 3 range rings + 8 status beacons
    this.diagGroup = new THREE.Group();
    this.taskBridgeGroup.add(this.diagGroup);

    // 3 Range rings
    this.diagRings = [];
    [2.0, 3.4, 4.8].forEach(r => {
      const dGeo = new THREE.RingGeometry(r, r + 0.02, 64);
      const dMat = new THREE.MeshBasicMaterial({
        color: 0x00f0ff,
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending,
      });
      const dMesh = new THREE.Mesh(dGeo, dMat);
      this.diagRings.push(dMesh);
      this.diagGroup.add(dMesh);
    });

    // Radar sweep line
    const sweepGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(4.8, 0, 0),
    ]);
    this.diagSweepMat = new THREE.LineBasicMaterial({
      color: 0x00ffff,
      transparent: true,
      opacity: 0.0,
      linewidth: 3,
      blending: THREE.AdditiveBlending,
    });
    this.diagSweep = new THREE.Line(sweepGeo, this.diagSweepMat);
    this.diagGroup.add(this.diagSweep);

    // 8 Peripheral status beacons
    this.diagBeacons = [];
    for (let b = 0; b < 8; b++) {
      const bAng = (b / 8) * Math.PI * 2;
      const bGeo = new THREE.SphereGeometry(0.1, 16, 16);
      const bMat = new THREE.MeshBasicMaterial({
        color: 0x00ff88,
        transparent: true,
        opacity: 0.0,
        blending: THREE.AdditiveBlending,
      });
      const bMesh = new THREE.Mesh(bGeo, bMat);
      bMesh.position.set(Math.cos(bAng) * 4.8, Math.sin(bAng) * 4.8, 0);
      bMesh.userData = { angle: bAng };
      this.diagBeacons.push(bMesh);
      this.diagGroup.add(bMesh);
    }
  }

  // ─── Set Task Visualization Bridge ────────────────────────────────────────
  // ─── Task Visualization & Behavior Bridge ─────────────────────────────────
  setTaskVisualization(taskType, objective = "") {
    this.activeTaskType = taskType;
    this.taskStartTime = this.time;
    if (this.behavior) {
      this.behavior.setState(this.state, taskType, 0.0);
    }
    console.log(`[PresenceEngine] Manifesting Task Structure: ${taskType} ("${objective}")`);
  }

  // ─── State Behavior Transition ────────────────────────────────────────────
  setState(newState, taskType = "GENERAL", taskProgress = 0.0) {
    if (this.state === newState && this.taskType === taskType && newState !== "COMPLETED") {
      return;
    }
    this.state = newState;
    this.taskType = taskType;
    if (this.behavior) {
      this.behavior.setState(newState, taskType, taskProgress);
    }
  }

  // ─── Event-Driven Micro Behaviors ─────────────────────────────────────────
  triggerEvent(eventType, payload = {}) {
    if (this.behavior) {
      this.behavior.triggerEvent(eventType, payload);
    }
  }

  setAudioData(bands) {
    if (this.behavior) {
      this.behavior.setAudioData(bands);
    }
  }

  setAudioAmplitude(amp) {
    this.audioAmplitude = Math.max(0.0, Math.min(1.0, amp));
    if (this.behavior) {
      this.behavior.setAudioData({
        rawAmp: this.audioAmplitude,
        bass: this.audioAmplitude * 1.3,
        mid: this.audioAmplitude,
        treble: this.audioAmplitude * 0.75,
      });
    }
  }

  // ─── Adaptive Simulation Loop ─────────────────────────────────────────────
  update() {
    const delta = this.clock.getDelta();
    this.time += delta;
    this.coreUniforms.uTime.value = this.time;

    // 0. Update PresenceBehaviorEngine
    const b = this.behavior ? this.behavior.update(delta) : {
      energy: 0.25,
      attention: { core: 1, innerLattice: 0.8, rings: 0.7, glyphs: 0.6, topology: 0.7, filaments: 0.5, particles: 0.65, taskBridge: 0.0 },
      impulses: { coreShock: 0, energyFlash: 0, anomalyGlitch: 0, toolProjection: 0, returnPulse: 0 },
      rings: [ { speedMult: 1 }, { speedMult: -1 }, { speedMult: 1 }, { speedMult: -1 }, { speedMult: 1 } ],
      audio: { rawAmp: 0, bass: 0, mid: 0, treble: 0 },
      memory: { primaryBranchAngle: 0.5, lastToolTarget: { x: 4.2, y: 0.8 } },
      breathing: 1.0,
      topologyWanderRate: 0.015,
      coreDistortion: 0.35,
      taskProgress: 0.0,
    };

    // Master subtle continuous drift influenced by visual memory orientation
    this.rootGroup.rotation.z = Math.sin(this.time * 0.12 + b.memory.primaryBranchAngle) * 0.06;

    // 1. Layer 1: Core Rotation, Lattice & Micro-Singularity
    this.coreUniforms.uDistortion.value = b.coreDistortion;
    this.coreUniforms.uGlitchIntensity.value = b.impulses.anomalyGlitch;
    this.coreUniforms.uAmplitude.value = b.audio.rawAmp * 2.0 + b.audio.mid * 0.75 + b.impulses.energyFlash * 0.7;

    const coreAtt = b.attention.core;
    const audioScale = 1.0 + (b.audio.bass * 0.22 + b.audio.rawAmp * 0.15);
    this.coreGroup.scale.setScalar(b.breathing * (0.85 + coreAtt * 0.2) * audioScale);
    this.coreMesh.rotation.y += (0.25 + b.energy * 0.45 + b.audio.mid * 0.6) * delta;
    this.coreMesh.rotation.x = Math.sin(this.time * 0.25) * (0.15 + b.energy * 0.15);

    if (this.innerLattice) {
      this.innerLattice.material.opacity = b.attention.innerLattice * 0.75 + b.audio.mid * 0.25;
      const latSpeed = (0.5 + b.energy * 0.8 + b.audio.mid * 1.6) * delta;
      this.innerLattice.rotation.x -= latSpeed;
      this.innerLattice.rotation.y += latSpeed * 1.3;
    }

    if (this.singParticles && this.singularityMesh) {
      this.singularityMesh.material.opacity = b.attention.innerLattice * 0.95;
      const sPos = this.singularityMesh.geometry.attributes.position.array;
      const sSpeedMult = 0.8 + b.energy * 2.2 + b.audio.mid * 2.8;
      for (let s = 0; s < this.singParticles.length; s++) {
        const sp = this.singParticles[s];
        sp.th += sp.speedTh * delta * sSpeedMult;
        sp.ph += sp.speedPh * delta * sSpeedMult;
        sPos[s * 3] = sp.r * Math.sin(sp.ph) * Math.cos(sp.th);
        sPos[s * 3 + 1] = sp.r * Math.sin(sp.ph) * Math.sin(sp.th);
        sPos[s * 3 + 2] = sp.r * Math.cos(sp.ph);
      }
      this.singularityMesh.geometry.attributes.position.needsUpdate = true;
    }

    // 2. Layer 3: Concentric Rings Rotation (Driven by Behavior Engine Ring States)
    this.rings.forEach((ring, idx) => {
      const rState = b.rings[idx] || { speedMult: 1.0, phase: 0.0 };
      ring.rotation.z += ring.userData.baseSpeed * rState.speedMult * delta;
      ring.children.forEach(c => {
        if (c.material) c.material.opacity = Math.min(1.0, b.attention.rings * 0.85);
      });
    });

    // 3. Layer 4: Glyph Band Orbital Motion
    if (this.glyphTexture && this.glyphMesh) {
      this.glyphTexture.offset.x += 0.03 * (0.6 + b.energy * 1.8) * delta;
      this.glyphMesh.material.opacity = b.attention.glyphs * 0.85;
    }

    // 4. Layer 5: Dynamic Geometric Topology Update
    this.updateTopology(delta, b);

    // 5. Layer 7: Particle Field State-Driven Vector Field
    this.updateParticles(delta, b);

    // 6. Layer 6: Radial Filaments Turbulence & Audio Reactivity
    this.updateFilaments(b);

    // 7. Layer 8: Active Task Structural Engine Update
    this.updateTaskStructures(delta, b);

    // Render Scene with 100% Alpha Transparency
    this.renderer.render(this.scene, this.camera);
  }

  updateTaskStructures(delta, b) {
    const op = b.attention.taskBridge;
    const active = this.activeTaskType;
    const progress = b.taskProgress;
    const elapsed = this.time - this.taskStartTime;

    const isAct = (type) => (active === type && op > 0.01);

    // 1. GREETING
    if (this.greetingMesh) {
      const gOp = isAct("GREETING") ? op * Math.max(0, 1.0 - (elapsed * 0.35)) : 0.0;
      this.greetingMesh.material.opacity = gOp * 0.8;
      const gScale = 1.0 + (elapsed * 0.8);
      this.greetingMesh.scale.set(gScale, gScale, 1.0);
    }

    // 2. TIME
    if (this.timeDialMesh) {
      const tOp = isAct("TIME") ? op : 0.0;
      this.timeDialMesh.material.opacity = tOp * 0.85;
      this.timeTickMat.opacity = tOp * 0.75;
      this.timeHandMat.opacity = tOp * 0.95;
      if (tOp > 0) {
        this.timeGroup.rotation.z -= delta * 1.5;
        this.timeHand.rotation.z -= delta * 4.0;
      }
    }

    // 3. BROWSER
    if (this.browserConduit) {
      const bOp = isAct("BROWSER") ? op : 0.0;
      this.browserConduitMat.opacity = bOp * 0.85;
      this.browserReticleMat.opacity = bOp * 0.95;
      this.browserReticle.rotation.z += delta * 2.0;

      // Conduit flowing packets modulated by progress & energy
      this.conduitPackets.forEach((pMesh, idx) => {
        pMesh.material.opacity = bOp * 0.9;
        const pSpeed = 0.8 + b.energy * 0.8;
        const pktProgress = (this.time * pSpeed + idx * 0.16) % 1.0;
        pMesh.position.set(pktProgress * 4.2, pktProgress * 0.8, Math.sin(pktProgress * Math.PI) * 0.3);
      });
    }

    // 4. WEB SEARCH
    if (this.searchBranches.length > 0) {
      const sOp = isAct("WEB_SEARCH") ? op : 0.0;
      this.searchBranches.forEach((br) => { br.material.opacity = sOp * 0.75; });
      this.searchNodes.forEach((n, idx) => {
        const nodeThreshold = idx / this.searchNodes.length;
        const isLit = progress > 0.0 ? progress >= nodeThreshold : true;
        const pulse = Math.sin(this.time * 4.0 + idx) * 0.35 + 0.65;
        n.material.opacity = isLit ? sOp * pulse : sOp * 0.2;
      });
    }

    // 5. VISION / SCREEN SCAN
    if (this.visionFrame) {
      const vOp = isAct("VISION") ? op : 0.0;
      this.visionFrameMat.opacity = vOp * 0.85;
      this.visionGridMat.opacity = vOp * 0.45;
      this.visionLaserMat.opacity = vOp * 0.95;
      if (vOp > 0) {
        const sweepY = Math.sin(this.time * 3.0) * 1.7;
        this.visionLaser.position.y = sweepY;
      }
    }

    // 6. FILES ORGANIZATION
    if (this.fileBlocks.length > 0) {
      const fOp = isAct("FILES") ? op : 0.0;
      const clusterT = progress > 0.0 ? progress : Math.min(1.0, elapsed * 0.45);
      this.fileBlocks.forEach((blk) => {
        blk.material.opacity = fOp * 0.85;
        if (fOp > 0) {
          blk.position.lerpVectors(blk.userData.chaosPos, blk.userData.targetPos, clusterT);
          blk.rotation.z += delta * 0.8;
        }
      });
    }

    // 7. CODE CONSTRUCTION
    if (this.codeStreams.length > 0) {
      const cOp = isAct("CODE") ? op : 0.0;
      this.codeStreams.forEach((cs) => {
        cs.material.opacity = cOp * 0.85;
        if (cOp > 0) {
          const pts = cs.geometry.attributes.position.array;
          for (let d = 0; d < 14; d++) {
            pts[d * 3 + 1] -= cs.userData.speed * delta * (1.5 + b.energy * 1.5);
            if (pts[d * 3 + 1] < -2.8) pts[d * 3 + 1] = 2.8;
          }
          cs.geometry.attributes.position.needsUpdate = true;
        }
      });
    }

    // 8. DIAGNOSTICS
    if (this.diagSweep) {
      const dOp = isAct("DIAGNOSTICS") ? op : 0.0;
      this.diagRings.forEach((r) => { r.material.opacity = dOp * 0.55; });
      this.diagSweepMat.opacity = dOp * 0.9;
      if (dOp > 0) {
        this.diagSweep.rotation.z += delta * (2.0 + b.energy * 2.0);
        const curSweepAng = this.diagSweep.rotation.z % (Math.PI * 2);
        this.diagBeacons.forEach((beacon) => {
          const diff = Math.abs(curSweepAng - beacon.userData.angle);
          const flash = diff < 0.35 ? 1.0 : 0.25;
          beacon.material.opacity = dOp * flash;
        });
      } else {
        this.diagBeacons.forEach((beacon) => { beacon.material.opacity = 0.0; });
      }
    }
  }

  updateTopology(delta, b) {
    const posAttr = this.nodePoints.geometry.attributes.position;
    const positions = posAttr.array;
    const wanderRate = b.topologyWanderRate;

    // Update node positions with wandering velocity
    for (let i = 0; i < this.topologyNodeCount; i++) {
      const node = this.nodes[i];
      node.pos.addScaledVector(node.vel, wanderRate / 0.015);

      // Leash to base region
      if (node.pos.distanceTo(node.basePos) > 0.75) {
        node.vel.negate();
      }

      positions[i * 3] = node.pos.x;
      positions[i * 3 + 1] = node.pos.y;
      positions[i * 3 + 2] = node.pos.z;
    }
    posAttr.needsUpdate = true;
    this.nodePoints.material.opacity = b.attention.topology * 0.9;

    // Dynamic edge distance threshold modulated by energy budget & voice formants
    const maxDist = 1.5 + b.energy * 1.1 + b.audio.mid * 0.7;
    let lineIdx = 0;
    const maxLines = (this.topologyNodeCount * (this.topologyNodeCount - 1)) / 2;

    const isAnomaly = b.impulses.anomalyGlitch > 0.05 || this.state === "BROKEN";

    for (let i = 0; i < this.topologyNodeCount; i++) {
      for (let j = i + 1; j < this.topologyNodeCount; j++) {
        const d = this.nodes[i].pos.distanceTo(this.nodes[j].pos);
        if (d < maxDist && lineIdx < maxLines) {
          const alpha = (1.0 - (d / maxDist)) * b.attention.topology;
          
          this.edgePositions[lineIdx * 6] = this.nodes[i].pos.x;
          this.edgePositions[lineIdx * 6 + 1] = this.nodes[i].pos.y;
          this.edgePositions[lineIdx * 6 + 2] = this.nodes[i].pos.z;

          this.edgePositions[lineIdx * 6 + 3] = this.nodes[j].pos.x;
          this.edgePositions[lineIdx * 6 + 4] = this.nodes[j].pos.y;
          this.edgePositions[lineIdx * 6 + 5] = this.nodes[j].pos.z;

          // Color tint based on anomaly state
          const r = isAnomaly ? 1.0 : (b.impulses.energyFlash * 0.5);
          const g = isAnomaly ? 0.05 : (0.9 * alpha);
          const bCol = isAnomaly ? 0.25 : (1.0 * alpha);

          this.edgeColors[lineIdx * 6] = r;
          this.edgeColors[lineIdx * 6 + 1] = g;
          this.edgeColors[lineIdx * 6 + 2] = bCol;
          this.edgeColors[lineIdx * 6 + 3] = r;
          this.edgeColors[lineIdx * 6 + 4] = g;
          this.edgeColors[lineIdx * 6 + 5] = bCol;

          lineIdx++;
        }
      }
    }

    this.edgeGeo.setDrawRange(0, lineIdx * 2);
    this.edgeGeo.attributes.position.needsUpdate = true;
    this.edgeGeo.attributes.color.needsUpdate = true;
  }

  updateParticles(delta, b) {
    const pos = this.particlePositions;
    const count = this.particleCount;
    this.particleSystem.material.opacity = b.attention.particles * 0.8;

    const pullInward = this.state === "LISTENING" || this.state === "TRANSCRIBING" || b.impulses.returnPulse > 0.05;
    const isExecuting = this.state === "EXECUTING" || b.impulses.toolProjection > 0.05;
    const isBroken = this.state === "BROKEN" || b.impulses.anomalyGlitch > 0.05;
    const isCompleted = this.state === "COMPLETED";

    const dirX = Math.cos(b.memory.primaryBranchAngle);
    const dirY = Math.sin(b.memory.primaryBranchAngle);

    for (let i = 0; i < count; i++) {
      let x = pos[i * 3];
      let y = pos[i * 3 + 1];
      let z = pos[i * 3 + 2];

      if (pullInward) {
        // Particles pulled INWARD toward central core
        const dist = Math.hypot(x, y);
        if (dist > 0.7) {
          const inSpeed = (0.025 + b.energy * 0.035);
          x -= (x / dist) * inSpeed;
          y -= (y / dist) * inSpeed;
        } else {
          // Respawn at outer rim
          const ang = Math.random() * Math.PI * 2;
          x = Math.cos(ang) * 4.8;
          y = Math.sin(ang) * 4.8;
        }
      } else if (isExecuting) {
        // Directional flow toward task target vector (using visual memory orientation)
        const flowSpeed = 0.035 + b.energy * 0.03;
        x += dirX * flowSpeed;
        y += dirY * flowSpeed;
        if (Math.hypot(x, y) > 5.5) {
          x = -dirX * 2.5 + (Math.random() - 0.5) * 1.5;
          y = -dirY * 2.5 + (Math.random() - 0.5) * 1.5;
        }
      } else if (isBroken) {
        // Chaotic dispersal outward
        const disperse = 0.06 + b.impulses.anomalyGlitch * 0.06;
        x += (Math.random() - 0.5) * disperse;
        y += (Math.random() - 0.5) * disperse;
        z += (Math.random() - 0.5) * disperse;
      } else if (isCompleted) {
        // Computational Regeneration: converge back to baseline orbits
        const orig = this.particleOriginals[i];
        x += (orig.x - x) * 0.08;
        y += (orig.y - y) * 0.08;
        z += (orig.z - z) * 0.08;
      } else {
        // IDLE / General: Gentle orbital drift with organic breathing
        const driftSpeed = 0.005 + b.energy * 0.01;
        const ang = Math.atan2(y, x) + driftSpeed;
        const r = Math.hypot(x, y);
        x = Math.cos(ang) * r;
        y = Math.sin(ang) * r;
      }

      pos[i * 3] = x;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = z;
    }

    this.particleSystem.geometry.attributes.position.needsUpdate = true;
  }

  updateFilaments(b) {
    const filOpacity = b.attention.filaments * (0.35 + b.audio.treble * 0.5);
    const waveAmp = (0.04 + b.energy * 0.08 + b.audio.treble * 0.25);

    this.filaments.forEach((fil, idx) => {
      fil.material.opacity = filOpacity;
      const geo = fil.geometry;
      const pos = geo.attributes.position;
      const basePts = fil.userData.basePts;

      for (let p = 0; p < basePts.length; p++) {
        const bp = basePts[p];
        const wave = Math.sin(this.time * 2.5 + p * 0.4 + idx) * waveAmp;
        pos.setXYZ(p, bp.x + wave, bp.y - wave, bp.z + wave * 0.5);
      }
      pos.needsUpdate = true;
    });
  }

  setupResize() {
    window.addEventListener("resize", () => {
      this.width = this.canvas.clientWidth || 356;
      this.height = this.canvas.clientHeight || 250;
      this.camera.aspect = this.width / this.height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(this.width, this.height);
    });
  }
}
