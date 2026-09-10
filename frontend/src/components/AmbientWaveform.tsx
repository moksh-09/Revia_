import { useRef, useEffect } from "react";
import type { VoiceState } from "../state/workspaceTypes";

/**
 * AmbientWaveform — a Three.js-powered animated waveform strip.
 * Fills the empty vertical space in the workspace right column.
 * Reacts to voiceState: idle = slow sine, listening = fast pulse,
 * speaking = rich multi-harmonic, interrupted = spike+decay.
 */

interface AmbientWaveformProps {
  voiceState: VoiceState;
}

export function AmbientWaveform({ voiceState }: AmbientWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef(voiceState);
  const frameRef = useRef<number>(0);

  // Update ref without re-running effect
  stateRef.current = voiceState;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let t = 0;
    let interruptFlash = 0;

    const draw = () => {
      frameRef.current = requestAnimationFrame(draw);
      const state = stateRef.current;
      const W = canvas.width;
      const H = canvas.height;

      // Clear
      ctx.clearRect(0, 0, W, H);

      // Per-state wave parameters
      let speed = 0.018;
      let amplitude = 0.18;
      let harmonics = 1;
      let lineAlpha = 0.35;
      let color = "var(--crimson, #7A1F2B)";

      if (state === "listening") {
        speed = 0.045; amplitude = 0.30; harmonics = 2; lineAlpha = 0.6;
      } else if (state === "thinking" || state === "working") {
        speed = 0.03; amplitude = 0.22; harmonics = 3; lineAlpha = 0.45;
      } else if (state === "speaking") {
        speed = 0.055; amplitude = 0.45; harmonics = 4; lineAlpha = 0.7;
      } else if (state === "interrupted") {
        interruptFlash = 12;
        speed = 0.07; amplitude = 0.55; harmonics = 5; lineAlpha = 0.85;
      }

      if (interruptFlash > 0) interruptFlash--;

      // In dark mode use pure white (--text-primary); in light mode use --crimson
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      const lineColor = getComputedStyle(document.documentElement)
        .getPropertyValue(isDark ? "--text-primary" : "--crimson").trim()
        || (isDark ? "#FFFFFF" : "#7A1F2B");

      if (isDark) {
        ctx.shadowColor = "rgba(56, 189, 248, 0.45)";
        ctx.shadowBlur = 5;
      } else {
        ctx.shadowColor = "transparent";
        ctx.shadowBlur = 0;
      }

      const LINES = 3;
      for (let ln = 0; ln < LINES; ln++) {
        const phaseOffset = (ln / LINES) * Math.PI * 0.7;
        const alphaFactor = 1 - (ln / LINES) * 0.55;
        ctx.beginPath();
        ctx.strokeStyle = lineColor;
        ctx.globalAlpha = lineAlpha * alphaFactor;
        ctx.lineWidth = ln === 0 ? 1.8 : 1;

        for (let x = 0; x < W; x++) {
          const nx = x / W;
          let y = 0;
          for (let h = 1; h <= harmonics; h++) {
            const freq = h * 1.8;
            const amp = amplitude * (1 / h) * H * 0.5;
            y += amp * Math.sin(freq * nx * Math.PI * 2 + t + phaseOffset + h * 0.8);
          }
          // Taper at edges
          const taper = Math.sin(nx * Math.PI);
          y *= taper;

          const py = H / 2 + y;
          x === 0 ? ctx.moveTo(x, py) : ctx.lineTo(x, py);
        }
        ctx.stroke();
      }

      // Interrupt flash: brief vertical bright line
      if (interruptFlash > 0) {
        ctx.globalAlpha = interruptFlash / 12 * 0.6;
        ctx.strokeStyle = lineColor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(W / 2, 0);
        ctx.lineTo(W / 2, H);
        ctx.stroke();
      }

      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1;
      t += speed;
    };

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      canvas.width  = parent.clientWidth;
      canvas.height = parent.clientHeight;
    };
    resize();
    window.addEventListener("resize", resize);
    draw();

    return () => {
      cancelAnimationFrame(frameRef.current);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <div className="ambient-waveform" aria-hidden="true">
      <canvas ref={canvasRef} className="ambient-waveform__canvas" />
      <div className="ambient-waveform__label">VOICE SPECTRUM</div>
    </div>
  );
}
