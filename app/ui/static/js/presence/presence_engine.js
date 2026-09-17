/**
 * SERA 2.0 — Presence Visual Engine
 * Three.js + WebGL Dynamic Computational Core (Wisdom King / Raphael Inspiration)
 * 100% Alpha Transparent Desktop Manifestation
 */

export class PresenceEngine {
  constructor(canvas) {
    this.canvas = canvas;
    this.state = "IDLE";
    this.time = 0;
    this.clock = new THREE.Clock();

    // State Physics Parameters
    this.stateParams = {
      coreScale: 1.0,
      ringOuterSpeed: 0.12,
      ringMidSpeed: -0.18,
      ringInnerSpeed: 0.25,
      ringRadiusScale: 1.0,
      particleAttractor: 0.05,
      particleRadialVelocity: 0.0,
      particleNoiseAmp: 1.2,
      targetTopology: "TORUS", // TORUS | NUCLEUS | GLYPH | DUAL_SPIRAL | FILAMENTS | WAVES | FRACTURE | IMPLOSION | CELLULAR
      primaryColor: new THREE.Color(0x00f0ff),
      accentColor: new THREE.Color(0x38bdf8),
      coreGlowColor: new THREE.Color(0xffffff),
      cellularProgress: 0.0, // 0.0 -> 1.0 during cellular reconstruction
    };

    // Current interpolated physics values
    this.currentParams = { ...this.stateParams };

    this._initThree();
    this._createCore();
    this._createAnalyticalRings();
    this._createParticleSwarm();
    this._createCellularReconstructionMesh();

    window.addEventListener("resize", () => this._onResize());
    this._onResize();
    this._animate();
  }

  _initThree() {
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 1000);
    this.camera.position.z = 480;

    this.renderer = new THREE.WebGLRenderer({
      canvas: this.canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
      premultipliedAlpha: false,
    });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(window.innerWidth, window.innerHeight);
  }

  _createCore() {
    this.coreGroup = new THREE.Group();
    this.scene.add(this.coreGroup);

    // 1. High-intensity White Singularity Core
    const coreGeo = new THREE.SphereGeometry(16, 32, 32);
    const coreMat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.95,
    });
    this.coreMesh = new THREE.Mesh(coreGeo, coreMat);
    this.coreGroup.add(this.coreMesh);

    // 2. Luminous Cyan Energy Halo (Additive Blending)
    const haloGeo = new THREE.SphereGeometry(26, 32, 32);
    const haloMat = new THREE.ShaderMaterial({
      uniforms: {
        uColor: { value: new THREE.Color(0x00f0ff) },
        uTime: { value: 0.0 },
      },
      vertexShader: `
        varying vec3 vNormal;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        varying vec3 vNormal;
        void main() {
          float intensity = pow(0.65 - dot(vNormal, vec3(0, 0, 1.0)), 2.0);
          gl_FragColor = vec4(uColor, intensity * 0.7);
        }
      `,
      blending: THREE.AdditiveBlending,
      transparent: true,
      side: THREE.BackSide,
    });
    this.haloMesh = new THREE.Mesh(haloGeo, haloMat);
    this.coreGroup.add(this.haloMesh);
  }

  _createAnalyticalRings() {
    this.ringsGroup = new THREE.Group();
    this.scene.add(this.ringsGroup);

    // 1. Outer Analytical Glyph Ring (Radius 135) with precision tick graduations
    const outerGeo = new THREE.BufferGeometry();
    const outerPoints = [];
    const numSegments = 120;
    const rOuter = 135;
    for (let i = 0; i <= numSegments; i++) {
      const theta = (i / numSegments) * Math.PI * 2;
      outerPoints.push(Math.cos(theta) * rOuter, Math.sin(theta) * rOuter, 0);
      // Add periodic coordinate ticks
      if (i % 6 === 0) {
        outerPoints.push(Math.cos(theta) * (rOuter + 8), Math.sin(theta) * (rOuter + 8), 0);
        outerPoints.push(Math.cos(theta) * rOuter, Math.sin(theta) * rOuter, 0);
      }
    }
    outerGeo.setAttribute("position", new THREE.Float32BufferAttribute(outerPoints, 3));
    this.ringOuterMat = new THREE.LineBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
    });
    this.ringOuter = new THREE.Line(outerGeo, this.ringOuterMat);
    this.ringsGroup.add(this.ringOuter);

    // 2. Middle Gyroscopic Ring (Radius 98) with Dimensional Inclination
    const midGeo = new THREE.BufferGeometry();
    const midPoints = [];
    const rMid = 98;
    for (let i = 0; i <= 90; i++) {
      const theta = (i / 90) * Math.PI * 2;
      midPoints.push(Math.cos(theta) * rMid, Math.sin(theta) * rMid, 0);
    }
    midGeo.setAttribute("position", new THREE.Float32BufferAttribute(midPoints, 3));
    this.ringMidMat = new THREE.LineBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending,
    });
    this.ringMid = new THREE.Line(midGeo, this.ringMidMat);
    this.ringMid.rotation.x = THREE.MathUtils.degToRad(32);
    this.ringMid.rotation.y = THREE.MathUtils.degToRad(18);
    this.ringsGroup.add(this.ringMid);

    // 3. Inner Resonant Frequency Ring (Radius 62)
    const innerGeo = new THREE.BufferGeometry();
    this.innerRingPointsCount = 80;
    this.innerRingPositions = new Float32Array(this.innerRingPointsCount * 3);
    innerGeo.setAttribute("position", new THREE.BufferAttribute(this.innerRingPositions, 3));
    this.ringInnerMat = new THREE.LineBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
    });
    this.ringInner = new THREE.Line(innerGeo, this.ringInnerMat);
    this.ringsGroup.add(this.ringInner);
  }

  _createParticleSwarm() {
    this.particleCount = 12000;
    this.particleGeo = new THREE.BufferGeometry();

    this.pPositions = new Float32Array(this.particleCount * 3);
    this.pColors = new Float32Array(this.particleCount * 3);
    this.pVelocities = new Float32Array(this.particleCount * 3);
    this.pHome = new Float32Array(this.particleCount * 3);
    this.pPhases = new Float32Array(this.particleCount);

    const cyan = new THREE.Color(0x00f0ff);
    const white = new THREE.Color(0xffffff);

    for (let i = 0; i < this.particleCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = (Math.random() - 0.5) * Math.PI * 0.7;
      const radius = 50 + Math.random() * 85;

      const x = Math.cos(theta) * Math.cos(phi) * radius;
      const y = Math.sin(theta) * Math.cos(phi) * radius;
      const z = Math.sin(phi) * radius * 0.5;

      this.pPositions[i * 3] = x;
      this.pPositions[i * 3 + 1] = y;
      this.pPositions[i * 3 + 2] = z;

      this.pHome[i * 3] = x;
      this.pHome[i * 3 + 1] = y;
      this.pHome[i * 3 + 2] = z;

      this.pVelocities[i * 3] = (Math.random() - 0.5) * 0.2;
      this.pVelocities[i * 3 + 1] = (Math.random() - 0.5) * 0.2;
      this.pVelocities[i * 3 + 2] = (Math.random() - 0.5) * 0.2;

      this.pPhases[i] = Math.random() * Math.PI * 2;

      // Color variation: mostly cyan, with pure white hotspot particles
      const col = Math.random() > 0.85 ? white : cyan;
      this.pColors[i * 3] = col.r;
      this.pColors[i * 3 + 1] = col.g;
      this.pColors[i * 3 + 2] = col.b;
    }

    this.particleGeo.setAttribute("position", new THREE.BufferAttribute(this.pPositions, 3));
    this.particleGeo.setAttribute("color", new THREE.BufferAttribute(this.pColors, 3));

    // Custom Particle Shader with soft round points and additive bloom
    const particleShaderMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uPointSize: { value: window.devicePixelRatio > 1 ? 2.8 : 2.2 },
      },
      vertexShader: `
        attribute vec3 color;
        varying vec3 vColor;
        uniform float uPointSize;
        void main() {
          vColor = color;
          vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = uPointSize * (280.0 / -mvPosition.z);
          gl_Position = projectionMatrix * mvPosition;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        void main() {
          float dist = length(gl_PointCoord - vec2(0.5));
          if (dist > 0.5) discard;
          float alpha = smoothstep(0.5, 0.05, dist);
          gl_FragColor = vec4(vColor, alpha * 0.85);
        }
      `,
      blending: THREE.AdditiveBlending,
      depthTest: false,
      transparent: true,
      vertexColors: true,
    });

    this.particles = new THREE.Points(this.particleGeo, particleShaderMat);
    this.scene.add(this.particles);
  }

  _createCellularReconstructionMesh() {
    // Structural vector lines and hexagonal nodes for the completion signature
    this.cellularGroup = new THREE.Group();
    this.cellularGroup.visible = false;
    this.scene.add(this.cellularGroup);

    // 24 Hexagonal Cellular Nodes
    const hexRadius = 90;
    const hexCount = 24;
    const cellGeo = new THREE.BufferGeometry();
    const cellPositions = [];

    for (let i = 0; i < hexCount; i++) {
      const angle = (i / hexCount) * Math.PI * 2;
      const cx = Math.cos(angle) * hexRadius;
      const cy = Math.sin(angle) * hexRadius;

      // Draw small hexagon around each node
      const rH = 12;
      for (let h = 0; h < 6; h++) {
        const a1 = angle + (h / 6) * Math.PI * 2;
        const a2 = angle + ((h + 1) / 6) * Math.PI * 2;
        cellPositions.push(cx + Math.cos(a1) * rH, cy + Math.sin(a1) * rH, 0);
        cellPositions.push(cx + Math.cos(a2) * rH, cy + Math.sin(a2) * rH, 0);
      }
    }

    cellGeo.setAttribute("position", new THREE.Float32BufferAttribute(cellPositions, 3));
    this.cellularMat = new THREE.LineBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.0,
      blending: THREE.AdditiveBlending,
    });
    this.cellularMesh = new THREE.LineSegments(cellGeo, this.cellularMat);
    this.cellularGroup.add(this.cellularMesh);
  }

  _onResize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  /**
   * Sets the operational state and smooths target physics parameters.
   * @param {string} newState - One of: IDLE | LISTENING | TRANSCRIBING | THINKING | EXECUTING | SPEAKING | BROKEN | CANCELLED | COMPLETED
   */
  setState(newState) {
    this.state = newState.toUpperCase();
    const p = this.stateParams;

    switch (this.state) {
      case "IDLE":
        p.coreScale = 1.0;
        p.ringOuterSpeed = 0.12;
        p.ringMidSpeed = -0.18;
        p.ringInnerSpeed = 0.25;
        p.ringRadiusScale = 1.0;
        p.particleAttractor = 0.04;
        p.particleRadialVelocity = 0.0;
        p.particleNoiseAmp = 1.0;
        p.targetTopology = "TORUS";
        p.primaryColor.setHex(0x00f0ff);
        p.accentColor.setHex(0x38bdf8);
        p.coreGlowColor.setHex(0xffffff);
        this.cellularGroup.visible = false;
        break;

      case "LISTENING":
        // Energy contracts tightly inward, fine particles converge
        p.coreScale = 1.25;
        p.ringOuterSpeed = 0.22;
        p.ringMidSpeed = -0.3;
        p.ringInnerSpeed = 0.45;
        p.ringRadiusScale = 0.78; // 20% contraction
        p.particleAttractor = 0.28; // Rapid inward attraction
        p.particleRadialVelocity = -0.8;
        p.particleNoiseAmp = 0.4;
        p.targetTopology = "NUCLEUS";
        p.primaryColor.setHex(0x00f0ff);
        p.accentColor.setHex(0xffffff);
        p.coreGlowColor.setHex(0xffffff);
        this.cellularGroup.visible = false;
        break;

      case "TRANSCRIBING":
        // Information glyphs and vertical/horizontal coordinate alignments
        p.coreScale = 1.15;
        p.ringOuterSpeed = 0.35;
        p.ringMidSpeed = -0.4;
        p.ringInnerSpeed = 0.6;
        p.ringRadiusScale = 0.88;
        p.particleAttractor = 0.12;
        p.particleRadialVelocity = 0.1;
        p.particleNoiseAmp = 0.8;
        p.targetTopology = "GLYPH";
        p.primaryColor.setHex(0x00f0ff);
        p.accentColor.setHex(0x38bdf8);
        p.coreGlowColor.setHex(0xffffff);
        this.cellularGroup.visible = false;
        break;

      case "THINKING":
        // Parallel rings, multiple simultaneous computation branches, magenta/cyan dual spiral
        p.coreScale = 1.35;
        p.ringOuterSpeed = 0.65;
        p.ringMidSpeed = -0.85;
        p.ringInnerSpeed = 1.1;
        p.ringRadiusScale = 1.12;
        p.particleAttractor = 0.08;
        p.particleRadialVelocity = 0.2;
        p.particleNoiseAmp = 2.4;
        p.targetTopology = "DUAL_SPIRAL";
        p.primaryColor.setHex(0x00f0ff);
        p.accentColor.setHex(0xf43f5e); // Vivid magenta/rose split
        p.coreGlowColor.setHex(0xf43f5e);
        this.cellularGroup.visible = false;
        break;

      case "EXECUTING":
        // Energy projects outward into desktop space, dynamic filaments
        p.coreScale = 1.45;
        p.ringOuterSpeed = 0.95;
        p.ringMidSpeed = -1.2;
        p.ringInnerSpeed = 1.6;
        p.ringRadiusScale = 1.35;
        p.particleAttractor = 0.02;
        p.particleRadialVelocity = 1.4; // Outward radiant projection
        p.particleNoiseAmp = 3.2;
        p.targetTopology = "FILAMENTS";
        p.primaryColor.setHex(0x00f0ff);
        p.accentColor.setHex(0x0284c7);
        p.coreGlowColor.setHex(0xffffff);
        this.cellularGroup.visible = false;
        break;

      case "SPEAKING":
        // Resonant acoustic wave expansion
        p.coreScale = 1.3;
        p.ringOuterSpeed = 0.35;
        p.ringMidSpeed = -0.4;
        p.ringInnerSpeed = 0.55;
        p.ringRadiusScale = 1.2;
        p.particleAttractor = 0.05;
        p.particleRadialVelocity = 0.6;
        p.particleNoiseAmp = 1.8;
        p.targetTopology = "WAVES";
        p.primaryColor.setHex(0x38bdf8);
        p.accentColor.setHex(0x00f0ff);
        p.coreGlowColor.setHex(0xffffff);
        this.cellularGroup.visible = false;
        break;

      case "BROKEN":
        // Structural fragmentation, angular jitter, crimson aberration
        p.coreScale = 0.85;
        p.ringOuterSpeed = 0.05;
        p.ringMidSpeed = 0.08;
        p.ringInnerSpeed = -0.1;
        p.ringRadiusScale = 0.9;
        p.particleAttractor = 0.01;
        p.particleRadialVelocity = 0.3;
        p.particleNoiseAmp = 4.5;
        p.targetTopology = "FRACTURE";
        p.primaryColor.setHex(0xf43f5e);
        p.accentColor.setHex(0xf59e0b);
        p.coreGlowColor.setHex(0xf43f5e);
        this.cellularGroup.visible = false;
        break;

      case "CANCELLED":
        // Energy abruptly collapses into void singularity
        p.coreScale = 0.2;
        p.ringOuterSpeed = 0.02;
        p.ringMidSpeed = -0.02;
        p.ringInnerSpeed = 0.03;
        p.ringRadiusScale = 0.3;
        p.particleAttractor = 0.45;
        p.particleRadialVelocity = -2.5;
        p.particleNoiseAmp = 0.2;
        p.targetTopology = "IMPLOSION";
        p.primaryColor.setHex(0x64748b);
        p.accentColor.setHex(0x334155);
        p.coreGlowColor.setHex(0x475569);
        this.cellularGroup.visible = false;
        break;

      case "COMPLETED":
        // Signature: Computational Cellular Reconstruction
        this._triggerCellularReconstruction();
        break;
    }
  }

  _triggerCellularReconstruction() {
    const p = this.stateParams;
    p.coreScale = 1.4;
    p.ringRadiusScale = 1.0;
    p.particleAttractor = 0.15;
    p.particleRadialVelocity = -0.3;
    p.targetTopology = "CELLULAR";
    p.primaryColor.setHex(0xffffff);
    p.accentColor.setHex(0x00f0ff);
    p.coreGlowColor.setHex(0xf43f5e); // Transient completion flare

    this.cellularGroup.visible = true;
    this.cellularProgress = 0.0;

    const startTime = performance.now();
    const duration = 1500; // 1.5s sequence

    const animStep = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1.0);
      this.cellularProgress = progress;

      // Hexagonal cells fade in and connect (0 to 0.6)
      if (progress < 0.6) {
        this.cellularMat.opacity = (progress / 0.6) * 0.9;
      } else {
        // Cells dissolve as outer rings lock in (0.6 to 1.0)
        this.cellularMat.opacity = (1.0 - (progress - 0.6) / 0.4) * 0.9;
      }

      if (progress < 1.0) {
        requestAnimationFrame(animStep);
      } else {
        // Settle smoothly into Idle state
        this.setState("IDLE");
      }
    };
    requestAnimationFrame(animStep);
  }

  _animate() {
    requestAnimationFrame(() => this._animate());

    const delta = this.clock.getDelta();
    this.time += delta;

    // Smooth Interpolation of Parameters toward State Targets
    const cp = this.currentParams;
    const sp = this.stateParams;
    const lerpRate = 0.06;

    cp.coreScale += (sp.coreScale - cp.coreScale) * lerpRate;
    cp.ringOuterSpeed += (sp.ringOuterSpeed - cp.ringOuterSpeed) * lerpRate;
    cp.ringMidSpeed += (sp.ringMidSpeed - cp.ringMidSpeed) * lerpRate;
    cp.ringInnerSpeed += (sp.ringInnerSpeed - cp.ringInnerSpeed) * lerpRate;
    cp.ringRadiusScale += (sp.ringRadiusScale - cp.ringRadiusScale) * lerpRate;
    cp.particleAttractor += (sp.particleAttractor - cp.particleAttractor) * lerpRate;
    cp.particleRadialVelocity += (sp.particleRadialVelocity - cp.particleRadialVelocity) * lerpRate;
    cp.particleNoiseAmp += (sp.particleNoiseAmp - cp.particleNoiseAmp) * lerpRate;
    cp.primaryColor.lerp(sp.primaryColor, lerpRate);
    cp.accentColor.lerp(sp.accentColor, lerpRate);
    cp.coreGlowColor.lerp(sp.coreGlowColor, lerpRate);

    // 1. Update Central Core (Procedural Breathing Pulse)
    const breath = 1.0 + Math.sin(this.time * 2.0) * 0.06;
    const finalCoreScale = cp.coreScale * breath;
    this.coreMesh.scale.set(finalCoreScale, finalCoreScale, finalCoreScale);
    this.haloMesh.scale.set(finalCoreScale, finalCoreScale, finalCoreScale);
    this.haloMesh.material.uniforms.uColor.value.copy(cp.primaryColor);

    // 2. Rotate Concentric Rings
    this.ringOuter.rotation.z += cp.ringOuterSpeed * delta;
    this.ringOuter.scale.set(cp.ringRadiusScale, cp.ringRadiusScale, 1.0);
    this.ringOuterMat.color.copy(cp.primaryColor);

    this.ringMid.rotation.z += cp.ringMidSpeed * delta;
    this.ringMid.scale.set(cp.ringRadiusScale, cp.ringRadiusScale, 1.0);
    this.ringMidMat.color.copy(cp.accentColor);

    this.ringInner.rotation.z += cp.ringInnerSpeed * delta;
    this.ringInner.scale.set(cp.ringRadiusScale, cp.ringRadiusScale, 1.0);

    // Dynamic wave modulation on inner ring
    const innerPos = this.ringInner.geometry.attributes.position.array;
    const rInnerBase = 62 * cp.ringRadiusScale;
    for (let i = 0; i < this.innerRingPointsCount; i++) {
      const theta = (i / this.innerRingPointsCount) * Math.PI * 2;
      const wave = Math.sin(theta * 6.0 + this.time * 8.0) * (3.0 * cp.coreScale);
      const r = rInnerBase + wave;
      innerPos[i * 3] = Math.cos(theta) * r;
      innerPos[i * 3 + 1] = Math.sin(theta) * r;
      innerPos[i * 3 + 2] = 0;
    }
    this.ringInner.geometry.attributes.position.needsUpdate = true;

    // 3. Simulate Particle Physics
    const pos = this.pPositions;
    const home = this.pHome;
    const vel = this.pVelocities;
    const topology = sp.targetTopology;

    for (let i = 0; i < this.particleCount; i++) {
      const idx = i * 3;
      let px = pos[idx];
      let py = pos[idx + 1];
      let pz = pos[idx + 2];

      const currentDist = Math.sqrt(px * px + py * py + pz * pz) || 1.0;
      const dirX = px / currentDist;
      const dirY = py / currentDist;
      const dirZ = pz / currentDist;

      // Attractor / Radial force
      const inwardForce = -dirX * cp.particleAttractor * (currentDist * 0.02);
      const outwardForce = dirX * cp.particleRadialVelocity;

      vel[idx] += inwardForce + outwardForce;
      vel[idx + 1] += (-dirY * cp.particleAttractor * (currentDist * 0.02)) + (dirY * cp.particleRadialVelocity);
      vel[idx + 2] += (-dirZ * cp.particleAttractor * (currentDist * 0.02)) + (dirZ * cp.particleRadialVelocity);

      // Tangential Orbital velocity
      const orbitSpeed = 0.015 * (140.0 / Math.max(currentDist, 20.0));
      vel[idx] += -dirY * orbitSpeed;
      vel[idx + 1] += dirX * orbitSpeed;

      // State Specific Topology Formations
      if (topology === "NUCLEUS") {
        // Contract into dense nucleus
        vel[idx] += (-px) * 0.06;
        vel[idx + 1] += (-py) * 0.06;
        vel[idx + 2] += (-pz) * 0.06;
      } else if (topology === "GLYPH") {
        // Snap to horizontal / vertical coordinate lines
        if (i % 2 === 0) {
          vel[idx + 1] += (-py) * 0.08; // Snap to X axis
        } else {
          vel[idx] += (-px) * 0.08;     // Snap to Y axis
        }
      } else if (topology === "DUAL_SPIRAL") {
        // Dual intertwining spiral branches
        const spiralSign = (i % 2 === 0) ? 1 : -1;
        const targetAngle = this.time * 2.0 * spiralSign + (i / this.particleCount) * Math.PI * 6.0;
        const targetR = 40.0 + (i / this.particleCount) * 120.0;
        vel[idx] += (Math.cos(targetAngle) * targetR - px) * 0.04;
        vel[idx + 1] += (Math.sin(targetAngle) * targetR - py) * 0.04;
      } else if (topology === "FILAMENTS") {
        // Radial filament jets
        const jetAngle = Math.floor((i / this.particleCount) * 8.0) * (Math.PI / 4.0);
        vel[idx] += Math.cos(jetAngle) * 0.8;
        vel[idx + 1] += Math.sin(jetAngle) * 0.8;
      } else if (topology === "WAVES") {
        // Concentric acoustic wave ripples
        const waveDist = ((currentDist + this.time * 60.0) % 160.0);
        vel[idx] += dirX * (waveDist * 0.005);
        vel[idx + 1] += dirY * (waveDist * 0.005);
      } else if (topology === "FRACTURE") {
        // Jitter and high entropy
        vel[idx] += (Math.random() - 0.5) * 1.5;
        vel[idx + 1] += (Math.random() - 0.5) * 1.5;
        vel[idx + 2] += (Math.random() - 0.5) * 1.5;
      }

      // Velocity damping
      vel[idx] *= 0.94;
      vel[idx + 1] *= 0.94;
      vel[idx + 2] *= 0.94;

      // Integrate position
      pos[idx] += vel[idx];
      pos[idx + 1] += vel[idx + 1];
      pos[idx + 2] += vel[idx + 2];

      // Reset boundary limits
      if (currentDist > 320 || currentDist < 10) {
        pos[idx] = home[idx];
        pos[idx + 1] = home[idx + 1];
        pos[idx + 2] = home[idx + 2];
        vel[idx] = 0;
        vel[idx + 1] = 0;
        vel[idx + 2] = 0;
      }
    }

    this.particleGeo.attributes.position.needsUpdate = true;

    // Render Scene with Alpha
    this.renderer.render(this.scene, this.camera);
  }
}
