import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { mockWorkspaceState } from "./mockWorkspaceState";
import type { ConnectionState, VoiceState, WorkspaceState } from "./workspaceTypes";

interface WorkspaceContextValue {
  state: WorkspaceState;
  setConnectionState: (value: ConnectionState) => void;
  setVoiceState: (value: VoiceState) => void;
  toggleMicrophone: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WorkspaceState>(mockWorkspaceState);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      state,
      setConnectionState: (connectionState) =>
        setState((current) => ({ ...current, connectionState })),
      setVoiceState: (voiceState) => setState((current) => ({ ...current, voiceState })),
      toggleMicrophone: () =>
        setState((current) => ({
          ...current,
          microphoneActive: !current.microphoneActive,
          voiceState: !current.microphoneActive ? "listening" : "idle",
        })),
    }),
    [state],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return value;
}
