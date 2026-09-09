import type { VoiceState } from "../state/workspaceTypes";

const labels: Record<VoiceState, string> = {
  idle: "Ready when you are",
  listening: "Listening",
  thinking: "Thinking",
  working: "Working",
  speaking: "Speaking",
  interrupted: "Interrupted",
};

export function VoiceOrb({ state }: { state: VoiceState }) {
  return (
    <div className={`voice-stage voice-${state}`}>
      <div className="orb-halo halo-one" />
      <div className="orb-halo halo-two" />
      <div className="voice-orb" aria-label={`REVIA is ${labels[state].toLowerCase()}`}>
        <div className="orb-core">
          <span className="orb-mark">R</span>
          <span className="orb-name">REVIA</span>
        </div>
      </div>
      <div className="voice-state">
        <span className="eyebrow">VOICE STATE</span>
        <strong>{labels[state]}</strong>
      </div>
    </div>
  );
}
