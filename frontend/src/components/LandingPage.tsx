import { useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import * as THREE from "three";
import { useTheme } from "../hooks/useTheme";
import { isDarkMode } from "../utils/theme";

function useHeroOrb(containerRef: React.RefObject<HTMLDivElement | null>) {
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 100);
    camera.position.set(0, 0, 3.5);

    // Initial theme check
    const initiallyDark = isDarkMode();

    const orbGeo = new THREE.IcosahedronGeometry(1, 6);
    const orbMat = new THREE.MeshStandardMaterial({
      color: initiallyDark ? new THREE.Color("#FFFFFF") : new THREE.Color("#7A1F2B"),
      roughness: initiallyDark ? 0.2 : 0.35,
      metalness: initiallyDark ? 0.25 : 0.55,
    });
    const orb = new THREE.Mesh(orbGeo, orbMat);
    scene.add(orb);
    const basePositions = (orbGeo.attributes.position.array as Float32Array).slice();

    const glowGeo = new THREE.SphereGeometry(0.88, 32, 32);
    const glowMat = new THREE.MeshBasicMaterial({
      color: initiallyDark ? new THREE.Color("#FFFFFF") : new THREE.Color("#9B3040"),
      transparent: true,
      opacity: initiallyDark ? 0.22 : 0.18,
    });
    scene.add(new THREE.Mesh(glowGeo, glowMat));

    const PARTICLE_COUNT = 200;
    const pPositions = new Float32Array(PARTICLE_COUNT * 3);
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 1.25 + Math.random() * 1.4;
      pPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pPositions[i * 3 + 2] = r * Math.cos(phi);
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute("position", new THREE.BufferAttribute(pPositions, 3));
    const pMat = new THREE.PointsMaterial({
      color: initiallyDark ? new THREE.Color("#FFFFFF") : new THREE.Color("#7A1F2B"),
      size: 0.022,
      transparent: true,
      opacity: 0.7,
      sizeAttenuation: true,
    });
    const particles = new THREE.Points(pGeo, pMat);
    scene.add(particles);

    const ambient = new THREE.AmbientLight(initiallyDark ? 0xe2e8f0 : 0xfff5e8, initiallyDark ? 1.6 : 0.6);
    scene.add(ambient);
    const key = new THREE.PointLight(initiallyDark ? 0xffffff : 0xffe0cc, initiallyDark ? 4.0 : 2.5, 10);
    key.position.set(3, 3, 3);
    scene.add(key);
    const fill = new THREE.PointLight(initiallyDark ? 0x38bdf8 : 0x7a1f2b, initiallyDark ? 2.5 : 1.8, 8);
    fill.position.set(-3, -2, -2);
    scene.add(fill);
    const frontLight = new THREE.DirectionalLight(initiallyDark ? 0xffffff : 0xffe0cc, initiallyDark ? 2.0 : 0.8);
    frontLight.position.set(0, 0, 4);
    scene.add(frontLight);

    // Color targets for smooth theme transition
    const lightOrbColor = new THREE.Color("#7A1F2B");
    const lightGlowColor = new THREE.Color("#9B3040");
    const lightPColor = new THREE.Color("#7A1F2B");
    const lightKeyColor = new THREE.Color(0xffe0cc);
    const lightFillColor = new THREE.Color(0x7a1f2b);
    const lightAmbColor = new THREE.Color(0xfff5e8);
    const lightEmissive = new THREE.Color("#000000");

    const darkOrbColor = new THREE.Color("#FFFFFF");
    const darkGlowColor = new THREE.Color("#FFFFFF");
    const darkPColor = new THREE.Color("#FFFFFF");
    const darkKeyColor = new THREE.Color(0xffffff);
    const darkFillColor = new THREE.Color(0x38bdf8);
    const darkAmbColor = new THREE.Color(0xe2e8f0);
    const darkEmissive = new THREE.Color("#334155");

    let frameId: number;
    const clock = new THREE.Clock();
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      // Theme-reactive color interpolation
      const dark = isDarkMode();
      orbMat.color.lerp(dark ? darkOrbColor : lightOrbColor, 0.08);
      orbMat.emissive.lerp(dark ? darkEmissive : lightEmissive, 0.08);
      glowMat.color.lerp(dark ? darkGlowColor : lightGlowColor, 0.08);
      pMat.color.lerp(dark ? darkPColor : lightPColor, 0.08);
      key.color.lerp(dark ? darkKeyColor : lightKeyColor, 0.08);
      fill.color.lerp(dark ? darkFillColor : lightFillColor, 0.08);
      ambient.color.lerp(dark ? darkAmbColor : lightAmbColor, 0.08);
      frontLight.color.lerp(dark ? new THREE.Color(0xffffff) : new THREE.Color(0xffe0cc), 0.08);
      ambient.intensity += ((dark ? 1.6 : 0.6) - ambient.intensity) * 0.08;
      key.intensity += ((dark ? 4.0 : 2.5) - key.intensity) * 0.08;
      frontLight.intensity += ((dark ? 2.0 : 0.8) - frontLight.intensity) * 0.08;
      orbMat.roughness += ((dark ? 0.25 : 0.35) - orbMat.roughness) * 0.08;
      orbMat.metalness += ((dark ? 0.15 : 0.55) - orbMat.metalness) * 0.08;
      glowMat.opacity += ((dark ? 0.30 : 0.18) - glowMat.opacity) * 0.08;

      orb.rotation.y = t * 0.12;
      orb.rotation.x = Math.sin(t * 0.08) * 0.1;
      const pos = orbGeo.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < pos.count; i++) {
        const ox = basePositions[i * 3], oy = basePositions[i * 3 + 1], oz = basePositions[i * 3 + 2];
        const wave = Math.sin(t * 0.9 + ox * 2.5 + oy * 2.0) * 0.04;
        pos.setXYZ(i, ox + ox * wave, oy + oy * wave, oz + oz * wave);
      }
      pos.needsUpdate = true;
      particles.rotation.y = t * 0.04;
      particles.rotation.x = t * 0.02;
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      if (!container) return;
      renderer.setSize(container.clientWidth, container.clientHeight);
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", onResize);
      renderer.dispose();
      orbGeo.dispose(); orbMat.dispose(); glowGeo.dispose(); glowMat.dispose(); pGeo.dispose(); pMat.dispose();
      if (container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
    };
  }, []);
}

const FEATURES = [
  { code: "F-001", title: "Expressive Voice Identity", body: "REVIA adapts cadence, tone, and personality across Signature and Concierge personas — a consistent presence across every call.", tag: "ACOUSTIC · PERSONA" },
  { code: "F-002", title: "Multilingual Intelligence", body: "Speak in English, Hindi, Spanish, French, German, or Italian. REVIA switches language in real-time with native Rime voice models — no machine translation.", tag: "LANGUAGE · ROUTING" },
  { code: "F-003", title: "Telephony-Grade Quality", body: "8 kHz PCM output optimised for SIP/PSTN pipelines. The same agent brain that handles WebRTC delivers pristine telephony audio.", tag: "TELEPHONY · PSTN" },
  { code: "F-004", title: "Instant Interruption", body: "Talk while REVIA talks. It stops within 200 ms of your first word — no overlap, no awkward pauses, no conversation collision.", tag: "FULL-DUPLEX · VAD" },
];

export function LandingPage() {
  const navigate = useNavigate();
  const heroOrbRef = useRef<HTMLDivElement>(null);
  useHeroOrb(heroOrbRef);
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="landing-shell">
      <nav className="landing-nav">
        <span className="landing-nav__brand">
          <span className="landing-nav__sigil">◈</span>
          <span className="landing-nav__name">REVIA</span>
        </span>
        <span className="landing-nav__meta">VOICE INTELLIGENCE SYSTEM · v2.0</span>
        <div className="landing-nav__right">
          <button
            onClick={toggleTheme}
            className="theme-toggle-btn"
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            id="landing-theme-toggle"
          >
            {theme === "dark" ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            )}
          </button>
          <button className="landing-nav__cta" onClick={() => navigate("/workspace")} id="nav-open-workspace">
            Open Console →
          </button>
        </div>
      </nav>

      <section className="landing-hero" aria-label="REVIA hero">
        <div className="landing-hero__copy">
          <p className="landing-hero__eyebrow">CLASSIFIED · VOICE INTELLIGENCE</p>
          <h1 className="landing-hero__headline">Meet&nbsp;<em>REVIA</em></h1>
          <p className="landing-hero__sub">
            Full-duplex voice AI built for the people who can't wait.<br />
            Interrupt it. Switch languages. Hang up mid-sentence.
          </p>
          <div className="landing-hero__actions">
            <button className="btn-dossier-primary" onClick={() => navigate("/workspace")} id="hero-start-session">
              Start Session
            </button>
            <a className="btn-dossier-ghost" href="#features" id="hero-learn-more">About ↓</a>
          </div>
          <div className="landing-hero__specs">
            {["Rime · Coda · Lyra", "Deepgram STT", "MultiLingual", "LiveKit WebRTC"].map((s) => (
              <span key={s} className="landing-spec-pill">{s}</span>
            ))}
          </div>
        </div>

        <div className="landing-hero__orb-wrap" aria-hidden="true">
          <div ref={heroOrbRef} className="landing-hero__orb-canvas" />
          <span className="landing-orb-mark landing-orb-mark--top">R·001</span>
          <span className="landing-orb-mark landing-orb-mark--bottom">REVIA</span>
          <span className="landing-orb-mark landing-orb-mark--left">SYS</span>
          <span className="landing-orb-mark landing-orb-mark--right">VCI</span>
        </div>
      </section>

      <div className="landing-divider" aria-hidden="true"><span>· · INTELLIGENCE VOICE ASSISSTANT · ·</span></div>

      <section id="features" className="landing-features" aria-label="Feature dossier">
        <h2 className="landing-features__heading">Dossier</h2>
        <div className="landing-features__grid">
          {FEATURES.map((f) => (
            <article key={f.code} className="feature-card">
              <header className="feature-card__header">
                <span className="feature-card__code">{f.code}</span>
                <span className="feature-card__tag">{f.tag}</span>
              </header>
              <h3 className="feature-card__title">{f.title}</h3>
              <p className="feature-card__body">{f.body}</p>
              <div className="feature-card__stamp" aria-hidden="true">ACTIVE</div>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-cta-banner">
        <p className="landing-cta-banner__label">READY TO ENGAGE</p>
        <p className="landing-cta-banner__headline">The console is waiting.</p>
        <button className="btn-dossier-primary btn-dossier-primary--large" onClick={() => navigate("/workspace")} id="banner-start-session">
          Open Voice Console →
        </button>
      </section>

      <footer className="landing-footer">
        <span>REVIA · Full-Duplex Voice Intelligence</span>
        <span>Interruptible by design · Correct by construction</span>
        <span>Rime · Coda · Lyra · Deepgram </span>
      </footer>
    </div>
  );
}
