import { useWorkspace } from "../state/workspaceState";
import type { VoiceState, ConnectionState } from "../state/workspaceTypes";

const MIC_STATE_LABELS: Record<string, string> = {
  idle:          "READY",
  listening:     "LISTENING",
  thinking:      "PROCESSING",
  working:       "PROCESSING",
  speaking:      "SPEAKING",
  interrupted:   "INTERRUPTED",
  task_replaced: "TRANSITIONING",
  stale_rejected:"REJECTED",
};

const MIC_HINTS: Record<string, string> = {
  idle:          "Click to begin speaking",
  listening:     "Speak naturally",
  thinking:      "REVIA is processing",
  working:       "REVIA is working on a task",
  speaking:      "REVIA is speaking — interrupt freely",
  interrupted:   "Request intercepted",
  task_replaced: "New request active",
  stale_rejected:"Previous result rejected",
};

const CONN_STATES_BLOCKING: ConnectionState[] = [
  "connecting", "reconnecting", "disconnected", "error"
];

export function MicInstrument() {
  const { state, toggleMicrophone, connect } = useWorkspace();
  const { voiceState, microphoneEnabled, connectionState } = state;

  const isDisconnected = CONN_STATES_BLOCKING.includes(connectionState);
  const isActive = microphoneEnabled && !isDisconnected;

  const micLabel = isDisconnected
    ? connectionState === "connecting" || connectionState === "reconnecting"
      ? "CONNECTING"
      : "SESSION INACTIVE"
    : MIC_STATE_LABELS[voiceState] ?? "READY";

  const micHint = isDisconnected
    ? connectionState === "connecting" || connectionState === "reconnecting"
      ? "Establishing connection..."
      : "Start a session to begin"
    : MIC_HINTS[voiceState] ?? "";

  const handleClick = async () => {
    if (isDisconnected) {
      await connect();
    } else {
      await toggleMicrophone();
    }
  };

  // Mic icon — SVG path
  const micIcon = microphoneEnabled && !isDisconnected ? (
    // Active — filled mic
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 1a4 4 0 0 0-4 4v7a4 4 0 0 0 8 0V5a4 4 0 0 0-4-4zm-1 19.93A8.001 8.001 0 0 1 4 13H2a10 10 0 0 0 9 9.95V22h-3v2h8v-2h-3v-.07A10 10 0 0 0 22 13h-2a8.001 8.001 0 0 1-7 7.93z"/>
    </svg>
  ) : (
    // Inactive — outline mic
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M12 1a4 4 0 0 0-4 4v7a4 4 0 0 0 8 0V5a4 4 0 0 0-4-4z"/>
      <path d="M4 13a8 8 0 0 0 16 0M12 19v4M8 23h8"/>
    </svg>
  );

  return (
    <div
      className={`mic-instrument ${isActive ? "mic-instrument--active" : ""}`}
      role="group"
      aria-label="REVIA microphone control"
    >
      <div className="mic-instrument__info">
        <span className="mic-instrument__eyebrow">Microphone</span>
        <span className="mic-instrument__state" aria-live="polite" aria-atomic="true">
          {micLabel}
        </span>
        <span className="mic-instrument__hint">{micHint}</span>
      </div>

      <button
        className={`mic-btn ${isActive ? "mic-btn--active" : ""}`}
        onClick={handleClick}
        disabled={
          connectionState === "connecting" || connectionState === "reconnecting"
        }
        aria-label={
          isDisconnected
            ? "Start session"
            : microphoneEnabled
              ? "Disable microphone"
              : "Enable microphone"
        }
        aria-pressed={isActive}
      >
        {micIcon}
      </button>
    </div>
  );
}
