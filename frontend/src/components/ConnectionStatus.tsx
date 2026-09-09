import type { ConnectionState } from "../state/workspaceTypes";

const labels: Record<ConnectionState, string> = {
  connecting: "Connecting",
  connected: "Connected",
  reconnecting: "Reconnecting",
  disconnected: "Preview · offline",
};

export function ConnectionStatus({ state }: { state: ConnectionState }) {
  return (
    <div className={`connection connection-${state}`} aria-live="polite">
      <span className="connection-dot" aria-hidden="true" />
      <span>{labels[state]}</span>
    </div>
  );
}
