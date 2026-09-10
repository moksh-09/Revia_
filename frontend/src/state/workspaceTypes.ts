// ── Workspace types for REVIA frontend ──────────────────────────
// These are DISPLAY-ONLY types. The backend remains authoritative.
// The frontend observes and renders — it never enforces task authority.

export type ConnectionState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "error";

/**
 * Maps directly to backend TaskStatus values plus two visual-only states.
 * task_replaced / stale_rejected are derived from task.obsolete + timing,
 * not separate backend states.
 */
export type VoiceState =
  | "idle"
  | "listening"
  | "thinking"
  | "working"       // TOOL_RUNNING
  | "speaking"
  | "interrupted"
  | "task_replaced" // transitional: old task receding, new arriving
  | "stale_rejected"; // brief visual state when fence rejection observed

/** Backend task statuses — mirrors backend/state/task.py TaskStatus */
export type TaskStatus =
  | "CREATED"
  | "ACTIVE"
  | "TOOL_RUNNING"
  | "GENERATING"
  | "SPEAKING"
  | "COMPLETED"
  | "CANCELLED"
  | "OBSOLETE"
  | "FAILED";

export type MessageRole = "user" | "assistant";

export interface ConversationMessage {
  id: string;
  role: MessageRole;
  text: string;
  timeLabel: string;
  isInterim?: boolean;   // true while transcript not yet finalized
  isSuperseded?: boolean; // true if a newer request replaced this one
}

/**
 * Represents a single task entry in the lineage display.
 * Populated from LiveKit data channel events.
 */
export interface TaskEntry {
  taskId: string;       // shortened for display — no raw UUIDs shown in UI
  serialNumber: number; // 001, 002, 003...
  requestText: string;
  status: TaskStatus;
  createdAt: string;    // ISO timestamp
  toolName?: string;    // set when TOOL_RUNNING observed
  staleRejected?: boolean; // true if fence rejection event received
  speechId?: string;    // set when SPEAKING observed
  msSpoken?: number;    // set from speech.stopped event
  stoppedReason?: "completed" | "interrupted";
}

/** State for the request lineage panel */
export interface LineageState {
  tasks: TaskEntry[];        // ordered oldest-first
  interruptionDetectedAt?: string; // ISO timestamp from interrupt event
}

export interface RimeState {
  // Values from backend/rime/tts_rime.py — verified against source
  model: "coda";
  voice: "lyra";
  language: "eng";
  active: boolean; // true when agent participant is connected
}

export type VoicePersona = "signature" | "concierge" | "dispatcher" | "copilot";
export type SupportedLanguage = "eng" | "spa" | "fra" | "ger" | "hin" | "auto";
export type WakeWordStatus = "idle" | "listening" | "detected" | "unsupported";

export interface VoiceIdentityConfig {
  persona: VoicePersona;
  language: SupportedLanguage;
  telephonyMode: boolean;
  speedAlpha: number;
}

export interface WorkspaceState {
  connectionState: ConnectionState;
  voiceState: VoiceState;
  microphoneEnabled: boolean;
  messages: ConversationMessage[];
  currentTranscript: string; // interim transcript in progress
  lineage: LineageState;
  rime: RimeState;
  sessionId: string | null;  // participant identity for this session
  error: string | null;
  voiceConfig: VoiceIdentityConfig;
  wakeWordStatus: WakeWordStatus;
}
