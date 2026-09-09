import { useWorkspace } from "../state/workspaceState";

export function MicrophoneControl() {
  const { state, toggleMicrophone } = useWorkspace();
  const label = state.microphoneActive ? "Stop microphone preview" : "Start microphone preview";

  return (
    <button className={`mic-control ${state.microphoneActive ? "is-active" : ""}`} onClick={toggleMicrophone} aria-label={label}>
      <span className="mic-icon" aria-hidden="true">{state.microphoneActive ? "■" : "⌁"}</span>
      <span>{state.microphoneActive ? "Listening" : "Start speaking"}</span>
    </button>
  );
}
