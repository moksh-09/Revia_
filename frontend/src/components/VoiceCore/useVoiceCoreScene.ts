/**
 * useVoiceCoreScene.ts
 * ────────────────────
 * Three.js scene hook for REVIA's Voice Core.
 *
 * The Voice Core is REVIA's visual nervous system — not decoration.
 * It represents internal task/voice state through restrained,
 * premium 3D geometry. Colors match the dossier palette.
 *
 * State → visual behavior:
 *   idle        → almost still, slow breathing
 *   listening   → controlled pulse, warm glow
 *   thinking    → subtle internal geometric movement
 *   working     → structured activity, stronger rhythm
 *   speaking    → active oscillation
 *   interrupted → speaking cuts immediately, brief shock, settle
 *   task_replaced → outer field recedes, new state emerges
 *   stale_rejected → brief OBSOLETE visual mark
 *
 * Performance:
 *   - requestAnimationFrame loop with proper cleanup
 *   - ResizeObserver for canvas sizing
 *   - Full disposal of geometry, material, renderer on unmount
 *   - No memory leaks
 */

import { useEffect, useRef, useCallback } from "react";
import * as THREE from "three";
import type { VoiceState } from "../../state/workspaceTypes";

// ── Dossier palette (light mode) ─────────────────────────────────────────
const COL = {
  paper:       new THREE.Color("#F5F0E8"),
  parchment:   new THREE.Color("#EDE8DE"),
  crimson:     new THREE.Color("#7A1F2B"),
  crimsonDark: new THREE.Color("#4A1018"),
  crimsonGlow: new THREE.Color("#9B3040"),
  charcoal:    new THREE.Color("#2C2825"),
  muted:       new THREE.Color("#6B5E52"),
  warm:        new THREE.Color("#C4A882"),
  workingBlue: new THREE.Color("#2A3060"),
  speakBlue:   new THREE.Color("#1A4A6A"),
  rule:        new THREE.Color("#C8BFB3"),
};

// ── Dark mode pure white luminous orb palette ─────────────────────────────
const DARK = {
  // Pure brilliant white cores with crisp high contrast
  pureWhite:    new THREE.Color("#FFFFFF"),
  softWhite:    new THREE.Color("#F1F5F9"),

  // Crystalline translucent outer shell
  idleOuter:    new THREE.Color("#142036"),
  listenOuter:  new THREE.Color("#0C2A45"),
  thinkOuter:   new THREE.Color("#1E1B4B"),
  speakOuter:   new THREE.Color("#0C2A45"),
  interruptOut: new THREE.Color("#142036"),

  // Wireframe lattice (crisp white & electric accents)
  idleWire:     new THREE.Color("#FFFFFF"),
  listenWire:   new THREE.Color("#38BDF8"),
  thinkWire:    new THREE.Color("#818CF8"),
  speakWire:    new THREE.Color("#38BDF8"),
  interruptWire: new THREE.Color("#94A3B8"),

  // Emissive glows (luminous illumination so white orb glows brightly)
  emissiveWhite:   new THREE.Color("#334155"),
  emissiveListen:  new THREE.Color("#164E63"),
  emissiveThink:   new THREE.Color("#2E1065"),
  emissiveSpeak:   new THREE.Color("#0891B2"),
  emissiveSettle:  new THREE.Color("#1E293B"),

  // Particles: diamond white & vibrant electric cyan
  pA:           new THREE.Color("#FFFFFF"),
  pB:           new THREE.Color("#E0F2FE"),
  pC:           new THREE.Color("#38BDF8"),
};

function isDarkMode(): boolean {
  return document.documentElement.getAttribute("data-theme") === "dark";
}


// ── Animation targets per state ───────────────────────────────────────────
interface StateTarget {
  innerScale:    number;
  outerScale:    number;
  innerSpeed:    number;
  outerSpeed:    number;
  innerColor:    THREE.Color;
  outerColor:    THREE.Color;
  wireColor:     THREE.Color;
  emissiveInner: THREE.Color;
  emissiveOuter: THREE.Color;
  outerOpacity:  number;
  rotationSpeed: number;
  pulseAmp:      number;
}

const STATE_TARGETS: Record<VoiceState, StateTarget> = {
  idle: {
    innerScale: 0.72, outerScale: 1.0,
    innerSpeed: 0.4,  outerSpeed: 0.2,
    innerColor: COL.muted,
    outerColor: COL.rule,
    wireColor:  COL.rule,
    emissiveInner: new THREE.Color("#1A1210"),
    emissiveOuter: new THREE.Color("#0A0908"),
    outerOpacity: 0.18,
    rotationSpeed: 0.003,
    pulseAmp: 0.012,
  },
  listening: {
    innerScale: 0.82, outerScale: 1.08,
    innerSpeed: 1.2,  outerSpeed: 0.6,
    innerColor: COL.crimson,
    outerColor: COL.crimsonDark,
    wireColor:  COL.crimsonGlow,
    emissiveInner: new THREE.Color("#3A0C12"),
    emissiveOuter: new THREE.Color("#1A0608"),
    outerOpacity: 0.28,
    rotationSpeed: 0.007,
    pulseAmp: 0.032,
  },
  thinking: {
    innerScale: 0.78, outerScale: 1.04,
    innerSpeed: 0.9,  outerSpeed: 0.5,
    innerColor: COL.workingBlue,
    outerColor: new THREE.Color("#1E2848"),
    wireColor:  new THREE.Color("#3A4880"),
    emissiveInner: new THREE.Color("#0A0C18"),
    emissiveOuter: new THREE.Color("#050608"),
    outerOpacity: 0.22,
    rotationSpeed: 0.01,
    pulseAmp: 0.018,
  },
  working: {
    innerScale: 0.85, outerScale: 1.1,
    innerSpeed: 1.6,  outerSpeed: 0.9,
    innerColor: COL.workingBlue,
    outerColor: new THREE.Color("#252C5A"),
    wireColor:  new THREE.Color("#4A5490"),
    emissiveInner: new THREE.Color("#0C0F20"),
    emissiveOuter: new THREE.Color("#08090F"),
    outerOpacity: 0.32,
    rotationSpeed: 0.018,
    pulseAmp: 0.045,
  },
  speaking: {
    innerScale: 0.88, outerScale: 1.14,
    innerSpeed: 2.2,  outerSpeed: 1.4,
    innerColor: COL.speakBlue,
    outerColor: new THREE.Color("#1E3A52"),
    wireColor:  new THREE.Color("#3A6890"),
    emissiveInner: new THREE.Color("#0A1820"),
    emissiveOuter: new THREE.Color("#060C10"),
    outerOpacity: 0.35,
    rotationSpeed: 0.022,
    pulseAmp: 0.06,
  },
  interrupted: {
    innerScale: 0.65, outerScale: 0.9,
    innerSpeed: 0.6,  outerSpeed: 0.3,
    innerColor: COL.warm,
    outerColor: COL.muted,
    wireColor:  COL.rule,
    emissiveInner: new THREE.Color("#201510"),
    emissiveOuter: new THREE.Color("#100808"),
    outerOpacity: 0.15,
    rotationSpeed: 0.005,
    pulseAmp: 0.025,
  },
  task_replaced: {
    innerScale: 0.68, outerScale: 0.88,
    innerSpeed: 0.5,  outerSpeed: 0.25,
    innerColor: COL.muted,
    outerColor: COL.rule,
    wireColor:  COL.rule,
    emissiveInner: new THREE.Color("#14100C"),
    emissiveOuter: new THREE.Color("#080604"),
    outerOpacity: 0.12,
    rotationSpeed: 0.004,
    pulseAmp: 0.015,
  },
  stale_rejected: {
    innerScale: 0.6,  outerScale: 0.82,
    innerSpeed: 0.3,  outerSpeed: 0.15,
    innerColor: COL.warm,
    outerColor: COL.muted,
    wireColor:  COL.rule,
    emissiveInner: new THREE.Color("#0E0A08"),
    emissiveOuter: new THREE.Color("#060402"),
    outerOpacity: 0.1,
    rotationSpeed: 0.003,
    pulseAmp: 0.008,
  },
};

// -- Dark mode state targets (pure brilliant white orb) -----------------------
const DARK_STATE_TARGETS: Record<VoiceState, StateTarget> = {
  idle: {
    innerScale: 0.72, outerScale: 1.0,
    innerSpeed: 0.4,  outerSpeed: 0.2,
    innerColor: DARK.pureWhite,
    outerColor: DARK.idleOuter,
    wireColor:  DARK.idleWire,
    emissiveInner: DARK.emissiveWhite,
    emissiveOuter: new THREE.Color("#0B1322"),
    outerOpacity: 0.22,
    rotationSpeed: 0.003,
    pulseAmp: 0.012,
  },
  listening: {
    innerScale: 0.82, outerScale: 1.08,
    innerSpeed: 1.2,  outerSpeed: 0.6,
    innerColor: DARK.pureWhite,
    outerColor: DARK.listenOuter,
    wireColor:  DARK.listenWire,
    emissiveInner: DARK.emissiveListen,
    emissiveOuter: new THREE.Color("#081F33"),
    outerOpacity: 0.35,
    rotationSpeed: 0.007,
    pulseAmp: 0.036,
  },
  thinking: {
    innerScale: 0.78, outerScale: 1.04,
    innerSpeed: 0.9,  outerSpeed: 0.5,
    innerColor: DARK.pureWhite,
    outerColor: DARK.thinkOuter,
    wireColor:  DARK.thinkWire,
    emissiveInner: DARK.emissiveThink,
    emissiveOuter: new THREE.Color("#120E2E"),
    outerOpacity: 0.28,
    rotationSpeed: 0.01,
    pulseAmp: 0.020,
  },
  working: {
    innerScale: 0.85, outerScale: 1.1,
    innerSpeed: 1.6,  outerSpeed: 0.9,
    innerColor: DARK.pureWhite,
    outerColor: DARK.thinkOuter,
    wireColor:  DARK.thinkWire,
    emissiveInner: DARK.emissiveThink,
    emissiveOuter: new THREE.Color("#161238"),
    outerOpacity: 0.36,
    rotationSpeed: 0.018,
    pulseAmp: 0.048,
  },
  speaking: {
    innerScale: 0.88, outerScale: 1.14,
    innerSpeed: 2.2,  outerSpeed: 1.4,
    innerColor: DARK.pureWhite,
    outerColor: DARK.speakOuter,
    wireColor:  DARK.speakWire,
    emissiveInner: DARK.emissiveSpeak,
    emissiveOuter: new THREE.Color("#0A2840"),
    outerOpacity: 0.42,
    rotationSpeed: 0.022,
    pulseAmp: 0.065,
  },
  interrupted: {
    innerScale: 0.65, outerScale: 0.9,
    innerSpeed: 0.6,  outerSpeed: 0.3,
    innerColor: DARK.softWhite,
    outerColor: DARK.interruptOut,
    wireColor:  DARK.interruptWire,
    emissiveInner: DARK.emissiveSettle,
    emissiveOuter: new THREE.Color("#0A111E"),
    outerOpacity: 0.18,
    rotationSpeed: 0.005,
    pulseAmp: 0.025,
  },
  task_replaced: {
    innerScale: 0.68, outerScale: 0.88,
    innerSpeed: 0.5,  outerSpeed: 0.25,
    innerColor: DARK.softWhite,
    outerColor: DARK.idleOuter,
    wireColor:  DARK.idleWire,
    emissiveInner: DARK.emissiveWhite,
    emissiveOuter: new THREE.Color("#0A111E"),
    outerOpacity: 0.15,
    rotationSpeed: 0.004,
    pulseAmp: 0.015,
  },
  stale_rejected: {
    innerScale: 0.6,  outerScale: 0.82,
    innerSpeed: 0.3,  outerSpeed: 0.15,
    innerColor: DARK.softWhite,
    outerColor: DARK.interruptOut,
    wireColor:  DARK.interruptWire,
    emissiveInner: DARK.emissiveSettle,
    emissiveOuter: new THREE.Color("#080D18"),
    outerOpacity: 0.12,
    rotationSpeed: 0.003,
    pulseAmp: 0.008,
  },
};

// ── Lerp helpers ──────────────────────────────────────────────────────────
function lerpN(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}
function lerpColor(
  col: THREE.Color,
  target: THREE.Color,
  t: number
): THREE.Color {
  return col.lerp(target.clone(), t);
}

// ── Hook ──────────────────────────────────────────────────────────────────
export function useVoiceCoreScene(
  containerRef: React.RefObject<HTMLDivElement | null>,
  voiceState: VoiceState,
  amplitude: number = 0 // 0–1 mic amplitude, optional
) {
  const rendererRef  = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef     = useRef<THREE.Scene | null>(null);
  const cameraRef    = useRef<THREE.PerspectiveCamera | null>(null);
  const innerMeshRef = useRef<THREE.Mesh | null>(null);
  const outerMeshRef = useRef<THREE.Mesh | null>(null);
  const outerWireRef = useRef<THREE.Mesh | null>(null);
  const frameRef     = useRef<number>(0);
  const clockRef     = useRef<THREE.Clock>(new THREE.Clock());

  // Current animated values (mutated each frame for performance)
  const animRef = useRef({
    innerScale:    STATE_TARGETS.idle.innerScale,
    outerScale:    STATE_TARGETS.idle.outerScale,
    outerOpacity:  STATE_TARGETS.idle.outerOpacity,
    rotationSpeed: STATE_TARGETS.idle.rotationSpeed,
    pulseAmp:      STATE_TARGETS.idle.pulseAmp,
    innerSpeedMul: STATE_TARGETS.idle.innerSpeed,
    outerSpeedMul: STATE_TARGETS.idle.outerSpeed,
  });

  const voiceStateRef = useRef<VoiceState>(voiceState);
  const amplitudeRef  = useRef<number>(amplitude);

  useEffect(() => { voiceStateRef.current = voiceState; }, [voiceState]);
  useEffect(() => { amplitudeRef.current = amplitude; }, [amplitude]);

  const initScene = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const W = container.clientWidth  || 380;
    const H = container.clientHeight || 380;

    // Renderer
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "low-power",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W, H);
    renderer.setClearColor(0x000000, 0); // transparent
    renderer.shadowMap.enabled = false;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 100);
    camera.position.set(0, 0, 4.5);
    cameraRef.current = camera;

    // Lighting — switches between warm (light mode) and radiant pure white / cyan (dark mode)
    const dark = isDarkMode();
    const ambientColor = dark ? 0xE2E8F0 : 0xF5F0E8;
    const keyColor    = dark ? 0xFFFFFF : 0xC4A882;
    const fillColor   = dark ? 0x38BDF8 : 0x7A1F2B;

    const ambient = new THREE.AmbientLight(ambientColor, dark ? 1.2 : 0.9);
    scene.add(ambient);

    const keyLight = new THREE.DirectionalLight(keyColor, dark ? 2.2 : 1.2);
    keyLight.position.set(2, 3, 4);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(fillColor, dark ? 0.9 : 0.4);
    fillLight.position.set(-3, -1, 2);
    scene.add(fillLight);

    // ── Inner core — IcosahedronGeometry with multi-harmonic organic deformation
    const innerGeo = new THREE.IcosahedronGeometry(1, 4);
    const basePositions = innerGeo.attributes.position.clone();
    const innerMat = new THREE.MeshStandardMaterial({
      color: COL.muted,
      roughness: 0.78,
      metalness: 0.12,
      emissive: new THREE.Color("#1A1210"),
      emissiveIntensity: 1,
    });
    const innerMesh = new THREE.Mesh(innerGeo, innerMat);
    scene.add(innerMesh);
    innerMeshRef.current = innerMesh;

    // ── Outer field — larger icosahedron, transparent ───────────────────
    const outerGeo = new THREE.IcosahedronGeometry(1.52, 2);
    const outerMat = new THREE.MeshStandardMaterial({
      color: COL.rule,
      roughness: 0.95,
      metalness: 0.02,
      transparent: true,
      opacity: 0.16,
      side: THREE.FrontSide,
    });
    const outerMesh = new THREE.Mesh(outerGeo, outerMat);
    scene.add(outerMesh);
    outerMeshRef.current = outerMesh;

    // ── Outer wireframe lattice ─────────────────────────────────────────
    const wireGeo = new THREE.IcosahedronGeometry(1.54, 2);
    const wireMat = new THREE.MeshBasicMaterial({
      color: COL.rule,
      wireframe: true,
      transparent: true,
      opacity: 0.14,
    });
    const wireMesh = new THREE.Mesh(wireGeo, wireMat);
    scene.add(wireMesh);
    outerWireRef.current = wireMesh;

    // ── Dense audio-reactive celestial particle constellation (180 particles)
    const particleCount = 180;
    const particleGeo = new THREE.BufferGeometry();
    const particlePositions = new Float32Array(particleCount * 3);
    const particleAngles = new Float32Array(particleCount);
    const particleRadii = new Float32Array(particleCount);
    const particleHeights = new Float32Array(particleCount);
    const particleSpeeds = new Float32Array(particleCount);
    const particlePhases = new Float32Array(particleCount);
    const particleColors = new Float32Array(particleCount * 3);

    const baseCrimson = new THREE.Color("#7A1F2B");
    const baseWarm    = new THREE.Color("#C4A882");
    const basePaper   = new THREE.Color("#F5F0E8");
    // dark mode particle colors: diamond white & electric cyan
    const baseDarkA   = new THREE.Color("#FFFFFF");
    const baseDarkB   = new THREE.Color("#E0F2FE");
    const baseDarkC   = new THREE.Color("#38BDF8");

    const darkNow = isDarkMode();
    for (let i = 0; i < particleCount; i++) {
      particleAngles[i] = (i / particleCount) * Math.PI * 2 + (Math.random() - 0.5) * 0.3;
      particleRadii[i] = 1.42 + Math.random() * 0.95;
      particleHeights[i] = (Math.random() - 0.5) * 1.1;
      particleSpeeds[i] = 0.12 + Math.random() * 0.28;
      particlePhases[i] = Math.random() * Math.PI * 2;

      const pick = i % 3;
      const c = darkNow
        ? (pick === 0 ? baseDarkA : pick === 1 ? baseDarkB : baseDarkC)
        : (pick === 0 ? baseWarm  : pick === 1 ? baseCrimson : basePaper);
      particleColors[i * 3]     = c.r;
      particleColors[i * 3 + 1] = c.g;
      particleColors[i * 3 + 2] = c.b;

      particlePositions[i * 3]     = Math.cos(particleAngles[i]) * particleRadii[i];
      particlePositions[i * 3 + 1] = particleHeights[i];
      particlePositions[i * 3 + 2] = Math.sin(particleAngles[i]) * particleRadii[i];
    }
    particleGeo.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
    particleGeo.setAttribute("color", new THREE.BufferAttribute(particleColors, 3));

    const particleMat = new THREE.PointsMaterial({
      vertexColors: true,
      size: 0.034,
      transparent: true,
      opacity: 0.52,
    });
    const particleSystem = new THREE.Points(particleGeo, particleMat);
    scene.add(particleSystem);

    // ── Mouse / Pointer Interactive Tilt ────────────────────────────────
    let targetTiltX = 0;
    let targetTiltY = 0;
    let currentTiltX = 0;
    let currentTiltY = 0;
    let hoverIntensity = 0;
    let clickShock = 0;

    const onPointerMove = (e: PointerEvent) => {
      const rect = container.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      targetTiltX = y * 0.25;
      targetTiltY = x * 0.35;
    };

    const onPointerEnter = () => {
      hoverIntensity = 1;
    };

    const onPointerLeave = () => {
      targetTiltX = 0;
      targetTiltY = 0;
      hoverIntensity = 0;
    };

    const onPointerDown = () => {
      clickShock = 0.8;
    };

    container.addEventListener("pointermove", onPointerMove);
    container.addEventListener("pointerenter", onPointerEnter);
    container.addEventListener("pointerleave", onPointerLeave);
    container.addEventListener("pointerdown", onPointerDown);

    // ── Resize observer ─────────────────────────────────────────────────
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    });
    ro.observe(container);

    clockRef.current.start();

    // ── Animation loop ───────────────────────────────────────────────────
    function animate() {
      frameRef.current = requestAnimationFrame(animate);

      const t      = clockRef.current.getElapsedTime();
      const st     = voiceStateRef.current;
      // Pick target set based on current theme
      const dark   = isDarkMode();
      const target = dark ? DARK_STATE_TARGETS[st] : STATE_TARGETS[st];
      const rawAmp = amplitudeRef.current;

      // Synthetic dynamic voice rhythm when speaking / listening / thinking
      const isSpeaking = st === "speaking";
      const isListening = st === "listening";
      const isThinking = st === "thinking" || st === "working";
      const isInterrupted = st === "interrupted";

      const synthAmp = isSpeaking
        ? 0.42 + 0.35 * Math.sin(t * 7.8) * Math.cos(t * 4.3)
        : isListening
          ? 0.22 + 0.18 * Math.sin(t * 5.2)
          : isThinking
            ? 0.12 + 0.08 * Math.sin(t * 3.2)
            : 0.0;
      const effectiveAmp = Math.max(rawAmp, synthAmp);

      const anim   = animRef.current;
      const lerpT  = 0.04;

      // Update scene lighting dynamically on theme change
      const targetAmb = dark ? 0xE2E8F0 : 0xF5F0E8;
      const targetKey = dark ? 0xFFFFFF : 0xC4A882;
      const targetFill = dark ? 0x38BDF8 : 0x7A1F2B;
      ambient.color.lerp(new THREE.Color(targetAmb), lerpT);
      keyLight.color.lerp(new THREE.Color(targetKey), lerpT);
      fillLight.color.lerp(new THREE.Color(targetFill), lerpT);
      keyLight.intensity = lerpN(keyLight.intensity, dark ? 2.2 : 1.2, lerpT);
      fillLight.intensity = lerpN(fillLight.intensity, dark ? 0.9 : 0.4, lerpT);

      // Lerp animated scalars toward targets
      anim.innerScale    = lerpN(anim.innerScale,    target.innerScale + effectiveAmp * 0.16 + hoverIntensity * 0.04, lerpT);
      anim.outerScale    = lerpN(anim.outerScale,    target.outerScale + effectiveAmp * 0.10 + hoverIntensity * 0.02, lerpT);
      anim.outerOpacity  = lerpN(anim.outerOpacity,  target.outerOpacity,                                             lerpT);
      anim.rotationSpeed = lerpN(anim.rotationSpeed, target.rotationSpeed + (isSpeaking ? 0.008 : 0),               lerpT);
      anim.pulseAmp      = lerpN(anim.pulseAmp,      target.pulseAmp + effectiveAmp * 0.045,                         lerpT);
      anim.innerSpeedMul = lerpN(anim.innerSpeedMul, target.innerSpeed,                                              lerpT);
      anim.outerSpeedMul = lerpN(anim.outerSpeedMul, target.outerSpeed,                                              lerpT);

      // Smooth interactive tilt
      currentTiltX = lerpN(currentTiltX, targetTiltX, 0.08);
      currentTiltY = lerpN(currentTiltY, targetTiltY, 0.08);

      // Click shockwave decay
      clickShock *= 0.91;

      // Pulse factors
      const innerPulse = Math.sin(t * anim.innerSpeedMul) * anim.pulseAmp;
      const outerPulse = Math.sin(t * anim.outerSpeedMul + 1.2) * anim.pulseAmp * 0.6;

      // Inner mesh with multi-harmonic acoustic wave deformation
      if (innerMesh) {
        const s = anim.innerScale + innerPulse + clickShock * 0.12;
        innerMesh.scale.setScalar(s);
        innerMesh.rotation.y += anim.rotationSpeed;
        innerMesh.rotation.x = currentTiltX + Math.sin(t * 0.3) * 0.04;
        innerMesh.rotation.z = currentTiltY;

        // Dynamic multi-octave surface harmonics
        const pos = innerGeo.attributes.position;
        const count = pos.count;
        const waveSpeed = t * anim.innerSpeedMul * 1.6;
        for (let i = 0; i < count; i++) {
          const bx = basePositions.getX(i);
          const by = basePositions.getY(i);
          const bz = basePositions.getZ(i);

          const w1 = Math.sin(bx * 2.3 + waveSpeed) * Math.cos(by * 2.3 + waveSpeed * 0.7);
          const w2 = Math.sin((bx + bz) * 4.5 - waveSpeed * 1.3) * 0.32;
          const w3 = Math.cos((by + bz) * 3.2 + waveSpeed * 1.1) * 0.18;
          const ripple = (w1 + w2 + w3) * (anim.pulseAmp + effectiveAmp * 0.06);
          const shock = clickShock * Math.sin(bx * 6 + by * 6 - t * 14) * 0.08;

          const factor = 1 + ripple + shock;
          pos.setXYZ(i, bx * factor, by * factor, bz * factor);
        }
        pos.needsUpdate = true;
        innerGeo.computeVertexNormals();

        const mat = innerMesh.material as THREE.MeshStandardMaterial;
        lerpColor(mat.color, target.innerColor, lerpT);
        lerpColor(mat.emissive, target.emissiveInner, lerpT);
        mat.emissiveIntensity = 1.0 + hoverIntensity * 0.25 + effectiveAmp * 0.4;
        mat.roughness = lerpN(mat.roughness, dark ? 0.30 : 0.78, lerpT);
        mat.metalness = lerpN(mat.metalness, dark ? 0.15 : 0.12, lerpT);
      }

      // Outer mesh
      if (outerMesh) {
        const s = anim.outerScale + outerPulse;
        outerMesh.scale.setScalar(s);
        outerMesh.rotation.y -= anim.rotationSpeed * 0.55;
        outerMesh.rotation.x = currentTiltX * 0.6;
        outerMesh.rotation.z = currentTiltY * 0.6 + anim.rotationSpeed * 0.2;

        const mat = outerMesh.material as THREE.MeshStandardMaterial;
        lerpColor(mat.color, target.outerColor, lerpT);
        mat.opacity = anim.outerOpacity;
      }

      // Wireframe lattice
      if (wireMesh) {
        wireMesh.scale.setScalar(anim.outerScale + outerPulse * 1.02);
        wireMesh.rotation.y = outerMesh?.rotation.y ?? 0;
        wireMesh.rotation.x = outerMesh?.rotation.x ?? 0;
        wireMesh.rotation.z = outerMesh?.rotation.z ?? 0;

        const mat = wireMesh.material as THREE.MeshBasicMaterial;
        lerpColor(mat.color, target.wireColor, lerpT);
        mat.opacity = anim.outerOpacity * 0.7;
      }

      // Audio-reactive celestial particles (180 particles)
      if (particleSystem) {
        const pPos = particleGeo.attributes.position;
        const dispersion = isInterrupted
          ? 0.88
          : 1.0 + effectiveAmp * 0.38 + hoverIntensity * 0.06 + clickShock * 0.25;

        for (let i = 0; i < particleCount; i++) {
          particleAngles[i] += particleSpeeds[i] * 0.009 * (1 + anim.innerSpeedMul * 0.4 + effectiveAmp * 0.6);
          const rad = particleRadii[i] * dispersion;
          const x = Math.cos(particleAngles[i]) * rad;
          const z = Math.sin(particleAngles[i]) * rad;
          const y = particleHeights[i] + Math.sin(t * 1.2 + particlePhases[i] + particleAngles[i] * 2) * (0.08 + effectiveAmp * 0.12);
          pPos.setXYZ(i, x, y, z);
        }
        pPos.needsUpdate = true;

        // Dynamically interpolate particle colors on theme toggle
        const colAttr = particleGeo.attributes.color as THREE.BufferAttribute;
        if (colAttr) {
          const pTargetA = dark ? baseDarkA : baseWarm;
          const pTargetB = dark ? baseDarkB : baseCrimson;
          const pTargetC = dark ? baseDarkC : basePaper;
          for (let i = 0; i < particleCount; i++) {
            const pick = i % 3;
            const target = pick === 0 ? pTargetA : pick === 1 ? pTargetB : pTargetC;
            const curR = colAttr.getX(i);
            const curG = colAttr.getY(i);
            const curB = colAttr.getZ(i);
            colAttr.setXYZ(i, curR + (target.r - curR) * 0.08, curG + (target.g - curG) * 0.08, curB + (target.b - curB) * 0.08);
          }
          colAttr.needsUpdate = true;
        }

        const pMat = particleSystem.material as THREE.PointsMaterial;
        pMat.opacity = Math.min(0.75, anim.outerOpacity * 1.8 + effectiveAmp * 0.3 + hoverIntensity * 0.1);
      }

      renderer.render(scene, camera);
    }

    animate();

    // Return cleanup
    return () => {
      container.removeEventListener("pointermove", onPointerMove);
      container.removeEventListener("pointerenter", onPointerEnter);
      container.removeEventListener("pointerleave", onPointerLeave);
      container.removeEventListener("pointerdown", onPointerDown);
      ro.disconnect();
      cancelAnimationFrame(frameRef.current);
      renderer.dispose();
      innerGeo.dispose();
      innerMat.dispose();
      outerGeo.dispose();
      outerMat.dispose();
      wireGeo.dispose();
      wireMat.dispose();
      particleGeo.dispose();
      particleMat.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      rendererRef.current  = null;
      innerMeshRef.current = null;
      outerMeshRef.current = null;
      outerWireRef.current = null;
    };
  }, [containerRef]);

  useEffect(() => {
    const cleanup = initScene();
    return cleanup;
  }, [initScene]);
}
