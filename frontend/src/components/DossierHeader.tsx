import { useState, useRef, useEffect } from "react";
import { useWorkspace } from "../state/workspaceState";
import { useTheme } from "../hooks/useTheme";

export function DossierHeader() {
  const { state, connect, disconnect, setWakeWordStatus } = useWorkspace();
  const { connectionState, rime, sessionId } = state;

  const isConnected = connectionState === "connected";
  const isConnecting = connectionState === "connecting" || connectionState === "reconnecting";

  // ── Dark mode state ──────────────────────────────────────────
  const { theme, toggleTheme } = useTheme();

  // Wake word passive listener for "Hey Revia"
  const [wakeWordArmed, setWakeWordArmed] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    if (!wakeWordArmed || isConnected || isConnecting) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {}
        recognitionRef.current = null;
      }
      setWakeWordStatus("idle");
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setWakeWordStatus("unsupported");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognitionRef.current = recognition;

    recognition.onstart = () => {
      setWakeWordStatus("listening");
    };

    recognition.onresult = (event: any) => {
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcript = event.results[i][0].transcript.toLowerCase().trim();
        if (
          transcript.includes("hey revia") ||
          transcript.includes("revia") ||
          transcript.includes("hi revia") ||
          transcript.includes("ok revia")
        ) {
          setWakeWordStatus("detected");
          try {
            recognition.abort();
          } catch {}
          setWakeWordArmed(false);
          connect();
          break;
        }
      }
    };

    recognition.onerror = (e: any) => {
      console.debug("[WakeWord] recognition error:", e.error);
      if (e.error === "not-allowed") {
        setWakeWordArmed(false);
        setWakeWordStatus("unsupported");
      }
    };

    recognition.onend = () => {
      if (wakeWordArmed && !isConnected && !isConnecting && recognitionRef.current) {
        try {
          recognition.start();
        } catch {}
      } else {
        setWakeWordStatus("idle");
      }
    };

    try {
      recognition.start();
    } catch (err) {
      console.warn("[WakeWord] start failed:", err);
    }

    return () => {
      try {
        recognition.abort();
      } catch {}
      recognitionRef.current = null;
    };
  }, [wakeWordArmed, isConnected, isConnecting, connect, setWakeWordStatus]);

  const dotClass =
    isConnected   ? "conn-dot conn-dot--live" :
    isConnecting  ? "conn-dot conn-dot--working" :
    connectionState === "error" ? "conn-dot conn-dot--error" :
    "conn-dot";

  const connLabel =
    connectionState === "connected"    ? "CONNECTED" :
    connectionState === "connecting"   ? "CONNECTING" :
    connectionState === "reconnecting" ? "RECONNECTING" :
    connectionState === "error"        ? "ERROR" :
    "DISCONNECTED";

  return (
    <header className="dossier-header" role="banner">
      {/* Brand */}
      <div className="dossier-brand">
        <span className="dossier-wordmark" aria-label="REVIA Voice Intelligence">
          REVIA
        </span>
        <span className="dossier-tagline">
          Interruptible by design · Correct by construction
        </span>
      </div>

      {/* Status metadata + session control */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: "24px", flexWrap: "wrap" }}>
        <div className="dossier-meta-row">
          {/* Session */}
          <div className="meta-label">
            <span className="meta-label__key">Session</span>
            <span className={`meta-label__value ${isConnected ? "meta-label__value--active" : ""}`}>
              {isConnected ? "ACTIVE" : "INACTIVE"}
            </span>
          </div>

          {/* Connection */}
          <div className="meta-label">
            <span className="meta-label__key">Connection</span>
            <span className={`meta-label__value ${isConnected ? "meta-label__value--crimson" : ""}`}>
              <span className={dotClass} aria-hidden="true" />
              {connLabel}
            </span>
          </div>

          {/* Voice engine */}
          <div className="rime-status">
            <span className="rime-status__label">Voice Engine</span>
            <span className="rime-status__config">
              <span
                className={`rime-status__dot ${rime.active ? "rime-status__dot--active" : ""}`}
                aria-hidden="true"
              />
              RIME · {rime.model.toUpperCase()} · {rime.voice.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Connect / disconnect button + dark mode toggle */}
        {!isConnected && !isConnecting ? (
          <div style={{ display: "flex", alignItems: "center", gap: "8px", alignSelf: "center" }}>
            <button
              onClick={connect}
              style={{
                padding: "6px 14px",
                border: "1px solid var(--crimson)",
                background: "transparent",
                color: "var(--crimson)",
                fontFamily: "var(--font-mono)",
                fontSize: "10px",
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                cursor: "pointer",
                transition: "all 180ms",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "var(--crimson)";
                (e.currentTarget as HTMLButtonElement).style.color = "var(--text-white)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                (e.currentTarget as HTMLButtonElement).style.color = "var(--crimson)";
              }}
              aria-label="Start REVIA session"
            >
              Enter Session
            </button>

            <button
              onClick={() => setWakeWordArmed((prev) => !prev)}
              style={{
                padding: "6px 12px",
                border: `1px solid ${wakeWordArmed ? "var(--crimson)" : "var(--border-subtle)"}`,
                background: wakeWordArmed ? "rgba(184, 41, 47, 0.1)" : "transparent",
                color: wakeWordArmed ? "var(--crimson)" : "var(--text-secondary)",
                fontFamily: "var(--font-mono)",
                fontSize: "9.5px",
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                cursor: "pointer",
                borderRadius: "2px",
                transition: "all 180ms",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
              title="Listen passively for 'Hey Revia' to automatically start hands-free"
              aria-pressed={wakeWordArmed}
            >
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: wakeWordArmed ? "var(--crimson)" : "var(--text-meta)",
                  display: "inline-block",
                  boxShadow: wakeWordArmed ? "0 0 8px var(--crimson)" : "none",
                }}
                aria-hidden="true"
              />
              {wakeWordArmed ? '👂 Listening: "Hey Revia"' : "Wake Word: Off"}
            </button>

            {/* Dark mode toggle */}
            <button
              onClick={toggleTheme}
              className="theme-toggle-btn"
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <circle cx="12" cy="12" r="5"/>
                  <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                  <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                </svg>
              )}
            </button>
          </div>
        ) : isConnected ? (
          <div style={{ display: "flex", alignItems: "center", gap: "8px", alignSelf: "center" }}>
            <button
              onClick={disconnect}
              style={{
                padding: "6px 14px",
                border: "1px solid var(--rule-strong)",
                background: "transparent",
                color: "var(--text-meta)",
                fontFamily: "var(--font-mono)",
                fontSize: "10px",
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                cursor: "pointer",
              }}
              aria-label="End REVIA session"
            >
              End Session
            </button>
            {/* Dark mode toggle always visible */}
            <button
              onClick={toggleTheme}
              className="theme-toggle-btn"
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <circle cx="12" cy="12" r="5"/>
                  <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                  <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                </svg>
              )}
            </button>
          </div>
        ) : (
          <span style={{
            fontFamily: "var(--font-mono)",
            fontSize: "9px",
            color: "var(--text-meta)",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            alignSelf: "center",
          }}>
            {connLabel}...
          </span>
        )}
      </div>
    </header>
  );
}
