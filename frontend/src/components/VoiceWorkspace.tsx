import { useWorkspace } from "../state/workspaceState";
import { ActivityPanel } from "./ActivityPanel";
import { ConnectionStatus } from "./ConnectionStatus";
import { ConversationPanel } from "./ConversationPanel";
import { MicrophoneControl } from "./MicrophoneControl";
import { ReliabilityPanel } from "./ReliabilityPanel";
import { RimeIndicator } from "./RimeIndicator";
import { VoiceOrb } from "./VoiceOrb";

export function VoiceWorkspace() {
  const { state } = useWorkspace();

  return (
    <main className="workspace-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-glyph">R</span>
          <span><strong>REVIA</strong><small>VOICE WORKSPACE</small></span>
        </div>
        <div className="topbar-actions">
          <RimeIndicator />
          <ConnectionStatus state={state.connectionState} />
          <button className="settings-button" aria-label="Open workspace settings">•••</button>
        </div>
      </header>

      <div className="preview-banner" role="status">
        <span className="preview-dot" />
        Preview workspace · live session not connected yet
      </div>

      <div className="workspace-grid">
        <section className="hero-column" aria-labelledby="workspace-title">
          <div className="hero-copy">
            <span className="eyebrow">FULL-DUPLEX VOICE</span>
            <h1 id="workspace-title">Stay in the flow.</h1>
            <p>Speak naturally. REVIA keeps the thread while your requests evolve.</p>
          </div>
          <VoiceOrb state={state.voiceState} />
          <MicrophoneControl />
          <p className="mic-note">Microphone preview only · Live audio arrives in a later phase</p>
        </section>

        <section className="detail-column" aria-label="Conversation and activity">
          <ConversationPanel messages={state.messages} />
          <div className="detail-row">
            <ActivityPanel activity={state.activity} />
            <ReliabilityPanel reliability={state.reliability} />
          </div>
        </section>
      </div>
      <footer className="workspace-footer">
        <span>General conversational voice agent</span>
        <span>Reliable full-duplex task switching</span>
      </footer>
    </main>
  );
}
