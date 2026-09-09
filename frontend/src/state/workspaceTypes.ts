export type ConnectionState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";

export type VoiceState =
  | "idle"
  | "listening"
  | "thinking"
  | "working"
  | "speaking"
  | "interrupted";

export type ActivityStatus = "idle" | "working" | "switching" | "completed" | "error";

export type MessageRole = "user" | "assistant";

export interface ConversationMessage {
  id: string;
  role: MessageRole;
  text: string;
  timeLabel: string;
}

export interface ActivityState {
  currentRequest: string | null;
  status: ActivityStatus;
  currentWork: string | null;
  previousRequest: string | null;
  error: string | null;
}

export interface ReliabilityState {
  currentRequest: string | null;
  replacedRequest: string | null;
  staleResultIgnored: boolean;
  interruption: "none" | "detected" | "recovered";
}

export interface WorkspaceState {
  connectionState: ConnectionState;
  voiceState: VoiceState;
  microphoneActive: boolean;
  messages: ConversationMessage[];
  currentTranscript: string;
  activity: ActivityState;
  reliability: ReliabilityState;
}
