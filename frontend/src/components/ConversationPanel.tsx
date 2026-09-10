import { useWorkspace } from "../state/workspaceState";
import { exportTranscriptPdf } from "../utils/exportTranscriptPdf";
import type { ConversationMessage } from "../state/workspaceTypes";

interface ConversationPanelProps {
  messages: ConversationMessage[];
  currentTranscript: string;
}

export function ConversationPanel({ messages, currentTranscript }: ConversationPanelProps) {
  const { state } = useWorkspace();
  const isEmpty = messages.length === 0 && !currentTranscript;

  return (
    <section className="sheet" aria-labelledby="conversation-title">
      <div className="sheet-header">
        <div>
          <span className="sheet-eyebrow">Live Transcript</span>
          <h2 className="sheet-title" id="conversation-title">Conversation</h2>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button
            onClick={() => exportTranscriptPdf(state)}
            disabled={messages.length === 0}
            style={{
              padding: "3px 8px",
              border: "1px solid var(--border-subtle)",
              background: messages.length > 0 ? "rgba(184, 41, 47, 0.08)" : "transparent",
              color: messages.length > 0 ? "var(--crimson)" : "var(--text-meta)",
              fontFamily: "var(--font-mono)",
              fontSize: "8.5px",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              cursor: messages.length > 0 ? "pointer" : "not-allowed",
              borderRadius: "2px",
              transition: "all 140ms",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
            title={messages.length > 0 ? "Download transcript dossier as PDF" : "Speak to generate transcript"}
            aria-label="Export transcript as PDF"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
            </svg>
            Export PDF
          </button>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "9px",
              color: "var(--text-meta)",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
            aria-live="polite"
          >
            {messages.length > 0 ? `${messages.length} TURN${messages.length === 1 ? "" : "S"}` : "—"}
          </span>
        </div>
      </div>

      <div className="sheet-body" style={{ padding: "0" }}>
        {isEmpty ? (
          <p className="conversation-empty" role="status">
            Awaiting voice input · Session {"\u2014"} begin speaking to see the transcript
          </p>
        ) : (
          <div className="conversation-list" role="log" aria-label="Conversation transcript" aria-live="polite">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`message message--${msg.role}${msg.isSuperseded ? " message--superseded" : ""}`}
                aria-label={`${msg.role === "user" ? "You" : "REVIA"}: ${msg.text}`}
              >
                <div className="message__meta">
                  <span className="message__role">
                    {msg.role === "user" ? "YOU" : "REVIA"}
                  </span>
                  <span className="message__time">{msg.timeLabel}</span>
                </div>
                <p className="message__text">{msg.text}</p>
              </div>
            ))}

            {/* Interim transcript in progress */}
            {currentTranscript && (
              <div className="message message--user message--interim" aria-live="polite">
                <div className="message__meta">
                  <span className="message__role">YOU</span>
                  <span className="message__time" style={{ fontStyle: "italic" }}>speaking…</span>
                </div>
                <p className="message__text">{currentTranscript}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
