import { useRef } from "react";
import { useVoiceCoreScene } from "./useVoiceCoreScene";
import { useWorkspace } from "../../state/workspaceState";
import type { VoiceState } from "../../state/workspaceTypes";

const STATE_LABELS: Record<VoiceState, string> = {
  idle: "Ready",
  listening: "Listening",
  thinking: "Thinking",
  working: "Working",
  speaking: "Speaking",
  interrupted: "Interrupted",
  task_replaced: "Transitioning",
  stale_rejected: "Rejected",
};

interface VoiceCoreProps {
  voiceState?: VoiceState;
  amplitude?: number; // 0–1 microphone amplitude
}

export function VoiceCore({ voiceState: propVoiceState, amplitude = 0 }: VoiceCoreProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { state, toggleMicrophone, connect } = useWorkspace();
  const { voiceState: contextVoiceState, connectionState, microphoneEnabled } = state;

  const currentVoiceState = propVoiceState ?? contextVoiceState;
  useVoiceCoreScene(containerRef, currentVoiceState, amplitude);

  const isDisconnected = connectionState === "disconnected" || connectionState === "error";
  const isConnecting = connectionState === "connecting" || connectionState === "reconnecting";
  const isMicActive = microphoneEnabled && !isDisconnected;

  const handleOrbClick = async () => {
    if (isConnecting) return;
    if (isDisconnected) {
      await connect();
    } else {
      await toggleMicrophone();
    }
  };
  const stateClass = `voice-state-label__state--${currentVoiceState}`;

  return (
    <div className="voice-core-stage" aria-label={`REVIA voice state: ${STATE_LABELS[currentVoiceState]}`}>
      <div
        className="voice-core-canvas-wrap"
        onClick={handleOrbClick}
        role="button"
        tabIndex={0}
        aria-label={`Orb Voice Control: ${STATE_LABELS[currentVoiceState]}. Click to ${isDisconnected ? "start session" : "toggle speech"}`}
        title={`Click orb to ${isDisconnected ? "start session" : isMicActive ? "mute microphone" : "speak"}`}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleOrbClick();
          }
        }}
      >
        {/* Three.js renders into this div */}
        <div ref={containerRef} style={{ width: "100%", height: "100%", borderRadius: "50%", overflow: "hidden" }} />

        {/* Dossier overlay rings */}
        <div className="voice-core-ring" aria-hidden="true" />

        {/* Registration marks */}
        <span className="voice-core-mark voice-core-mark--top" aria-hidden="true">R·001</span>
        <span className="voice-core-mark voice-core-mark--bottom" aria-hidden="true">REVIA</span>
        <span className="voice-core-mark voice-core-mark--left" aria-hidden="true">SYS</span>
        <span className="voice-core-mark voice-core-mark--right" aria-hidden="true">VCI</span>
      </div>

      {/* State label — always visible, accessible without Three.js */}
      <div className="voice-state-label" aria-live="polite" aria-atomic="true">
        <span className="voice-state-label__eyebrow"></span>
        <span className={`voice-state-label__state ${stateClass}`}>
          {STATE_LABELS[currentVoiceState]}
        </span>
      </div>
    </div>
  );
}
