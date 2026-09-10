import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { WorkspaceProvider } from "./state/workspaceState";
import { VoiceWorkspace } from "./components/VoiceWorkspace";
import { LandingPage } from "./components/LandingPage";
import "./styles.css";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Landing page — entry point */}
        <Route path="/" element={<LandingPage />} />

        {/* Voice workspace — wrapped with LiveKit/state provider */}
        <Route
          path="/workspace"
          element={
            <WorkspaceProvider>
              <VoiceWorkspace />
            </WorkspaceProvider>
          }
        />

        {/* Catch-all redirect to landing */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
