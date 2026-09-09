import { WorkspaceProvider } from "./state/workspaceState";
import { VoiceWorkspace } from "./components/VoiceWorkspace";
import "./styles.css";

export default function App() {
  return (
    <WorkspaceProvider>
      <VoiceWorkspace />
    </WorkspaceProvider>
  );
}
