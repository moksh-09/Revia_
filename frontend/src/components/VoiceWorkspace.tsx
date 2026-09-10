import { useWorkspace } from "../state/workspaceState";
import { DossierHeader } from "./DossierHeader";
import { VoiceCore } from "./VoiceCore/VoiceCore";
import { ConversationPanel } from "./ConversationPanel";
import { RequestAuthority } from "./RequestAuthority";
import { RequestLineage } from "./RequestLineage";
import { VoiceIdentityControls } from "./VoiceIdentityControls";
import { AmbientWaveform } from "./AmbientWaveform";

export function VoiceWorkspace() {
  const { state, clearError } = useWorkspace();
  const { voiceState, connectionState, messages, currentTranscript, lineage, error } = state;

  const isPreview = connectionState === "disconnected" || connectionState === "error";

  return (
    <div className="dossier-shell">
      {/* Header */}
      <DossierHeader />

      {/* Preview banner — shown when not connected */}
      {isPreview && connectionState !== "error" && (
        <div className="preview-banner" role="status" aria-label="Session not active">
          <span aria-hidden="true">◌</span>
          <span>
            Preview workspace · Start a session to connect to the REVIA agent
          </span>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="dossier-error" role="alert" aria-live="assertive">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ marginBottom: "4px", fontWeight: 500 }}>Connection Issue</div>
              <div style={{ textTransform: "none", fontSize: "11px", fontFamily: "var(--font-body)", letterSpacing: 0 }}>
                {error}
              </div>
            </div>
            <button
              onClick={clearError}
              style={{
                background: "none",
                border: "none",
                color: "var(--stamp-replaced)",
                cursor: "pointer",
                fontFamily: "var(--font-mono)",
                fontSize: "10px",
                padding: "0 0 0 16px",
                flexShrink: 0,
              }}
              aria-label="Dismiss error"
            >
              DISMISS
            </button>
          </div>
        </div>
      )}

      {/* Main grid */}
      <div className="workspace-grid">
        {/* Left column — Voice Core + Mic */}
        <section className="voice-column" aria-label="Voice interface">
          {/* Hero copy */}
          <div style={{ width: "100%", maxWidth: "380px", marginBottom: "8px" }}>
            <div style={{
              fontFamily: "var(--font-mono)",
              fontSize: "8px",
              letterSpacing: "0.22em",
              textTransform: "uppercase",
              color: "var(--text-meta)",
              marginBottom: "6px",
            }}>
              Full-Duplex Voice Intelligence
            </div>
            <div style={{
              fontFamily: "var(--font-display)",
              fontSize: "clamp(18px, 2.5vw, 26px)",
              fontWeight: 600,
              color: "var(--crimson)",
              lineHeight: 1.2,
              letterSpacing: "0.02em",
            }}>
              Talk while REVIA talks.
              <br />
              Redirect while REVIA works.
            </div>
            <div style={{
              fontFamily: "var(--font-body)",
              fontSize: "12px",
              color: "var(--text-secondary)",
              marginTop: "6px",
              lineHeight: 1.55,
            }}>
              Only the latest valid request gets through.
            </div>
          </div>

          {/* Three.js Voice Core with Integrated Microphone Orb */}
          <VoiceCore voiceState={voiceState} />

          {/* Voice identity & delivery controls */}
          <div style={{ width: "100%", maxWidth: "380px" }}>
            <VoiceIdentityControls />
          </div>

          {/* Request Authority (on mobile: below mic) */}
          <div style={{ width: "100%", maxWidth: "380px" }} className="mobile-authority">
            <RequestAuthority state={state} />
          </div>
        </section>

        {/* Right column — Conversation + Lineage */}
        <section className="detail-column" aria-label="Conversation and task authority">
          {/* Request authority (desktop) */}
          <div className="desktop-authority">
            <RequestAuthority state={state} />
          </div>

          {/* Conversation */}
          <ConversationPanel messages={messages} currentTranscript={currentTranscript} />

          {/* Voice spectrum ambient visualiser — fills empty space */}
          <AmbientWaveform voiceState={voiceState} />

          {/* Request lineage drawer */}
          <div className="sheet" style={{ overflow: "visible" }}>
            <RequestLineage lineage={lineage} />
          </div>
        </section>
      </div>

      {/* Footer */}
      <footer className="dossier-footer" aria-label="Session metadata">
        <span>REVIA · Full-Duplex Voice Intelligence</span>
        <span>Interruptible by design · Correct by construction</span>
        <span style={{ color: "var(--text-meta)" }}>
          Rime · Coda · Lyra · Deepgram
        </span>
      </footer>
    </div>
  );
}
