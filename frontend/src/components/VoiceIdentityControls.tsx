import { useWorkspace } from "../state/workspaceState";
import type { VoicePersona, SupportedLanguage } from "../state/workspaceTypes";

const PERSONAS: Array<{
  id: VoicePersona;
  name: string;
  voice: string;
  tagline: string;
}> = [
  {
    id: "signature",
    name: "Signature REVIA",
    voice: "Lyra (Coda)",
    tagline: "Balanced, articulate, crisp conversational delivery",
  },
  {
    id: "concierge",
    name: "Empathetic Concierge",
    voice: "Cove (Mistv2)",
    tagline: "Warm, patient, reassuring & thoughtful pauses",
  },
  {
    id: "dispatcher",
    name: "Telephony Dispatcher",
    voice: "Lyra (Coda 8kHz)",
    tagline: "High-throughput, rapid confirmation & phone etiquette",
  },
  {
    id: "copilot",
    name: "Technical Co-Pilot",
    voice: "Lyra (Coda)",
    tagline: "Direct, technically astute with zero filler",
  },
];

const LANGUAGES: Array<{ id: SupportedLanguage; label: string }> = [
  { id: "eng", label: "English (US)" },
  { id: "spa", label: "Español" },
  { id: "fra", label: "Français" },
  { id: "ger", label: "Deutsch" },
  { id: "hin", label: "Hindi (हिंदी)" },
  { id: "auto", label: "Auto-Detect" },
];

export function VoiceIdentityControls() {
  const { state, updateVoiceConfig } = useWorkspace();
  const { voiceConfig, connectionState } = state;
  const isConnected = connectionState === "connected";

  const handlePersonaChange = (persona: VoicePersona) => {
    const defaultSpeed = persona === "dispatcher" ? 1.15 : persona === "concierge" ? 0.95 : 1.0;
    const isTelephony = persona === "dispatcher" ? true : voiceConfig.telephonyMode;
    updateVoiceConfig({
      persona,
      speedAlpha: defaultSpeed,
      telephonyMode: isTelephony,
    });
  };

  const handleLanguageChange = (language: SupportedLanguage) => {
    updateVoiceConfig({ language });
  };

  const handleTelephonyToggle = () => {
    updateVoiceConfig({ telephonyMode: !voiceConfig.telephonyMode });
  };

  const handleSpeedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const speedAlpha = parseFloat(e.target.value);
    updateVoiceConfig({ speedAlpha });
  };

  return (
    <div className="identity-card" aria-label="Voice identity and delivery controls">
      {/* Header */}
      <div className="identity-card__header">
        <div>
          <span className="identity-card__eyebrow">Acoustic &amp; Persona Authority</span>
          <span className="identity-card__title">Voice Identity &amp; Delivery</span>
        </div>

        {/* Telephony Profile Badge Toggle */}
        <button
          onClick={handleTelephonyToggle}
          className={`identity-card__telephony-btn ${voiceConfig.telephonyMode ? "is-active" : ""}`}
          title="Toggle Telephony (8kHz narrowband G.711u profile)"
          aria-pressed={voiceConfig.telephonyMode}
        >
          <span className="identity-card__dot" aria-hidden="true" />
          {voiceConfig.telephonyMode ? "Telephony: 8kHz" : "Studio: 16kHz"}
        </button>
      </div>

      {/* Persona Presets */}
      <div>
        <label className="identity-card__section-label">Expressive Persona</label>
        <div className="identity-card__persona-grid">
          {PERSONAS.map((p) => {
            const isSelected = voiceConfig.persona === p.id;
            return (
              <button
                key={p.id}
                onClick={() => handlePersonaChange(p.id)}
                className={`identity-card__persona-btn ${isSelected ? "is-selected" : ""}`}
              >
                <div className="identity-card__persona-name">{p.name}</div>
                <div className="identity-card__persona-sub">{p.voice}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Multilingual & Pacing Row */}
      <div className="identity-card__controls-grid">
        {/* Language selector */}
        <div>
          <label htmlFor="lang-select" className="identity-card__section-label">
            Language Routing
          </label>
          <select
            id="lang-select"
            value={voiceConfig.language}
            onChange={(e) => handleLanguageChange(e.target.value as SupportedLanguage)}
            className="identity-card__select"
          >
            {LANGUAGES.map((l) => (
              <option key={l.id} value={l.id}>
                {l.label}
              </option>
            ))}
          </select>
        </div>

        {/* Pacing Slider */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
            <label htmlFor="pacing-slider" className="identity-card__section-label" style={{ marginBottom: 0 }}>
              Pacing Speed
            </label>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "8.5px",
                color: "var(--crimson)",
                fontWeight: 600,
              }}
            >
              {voiceConfig.speedAlpha.toFixed(2)}x
            </span>
          </div>
          <input
            id="pacing-slider"
            type="range"
            min="0.85"
            max="1.25"
            step="0.05"
            value={voiceConfig.speedAlpha}
            onChange={handleSpeedChange}
            className="identity-card__slider"
          />
        </div>
      </div>

      {/* Synchronized status note */}
      <div className="identity-card__footer">
        <span>{isConnected ? "● Live synced to Rime worker" : "○ Local preset armed"}</span>
        <span>Writing for the Ear: ACTIVE</span>
      </div>
    </div>
  );
}
