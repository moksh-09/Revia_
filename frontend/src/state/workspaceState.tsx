import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";
import { v4 as uuidv4 } from "uuid";
import {
  LiveKitSession,
  getTaskSerial,
  resetTaskSerials,
  eventToVoiceState,
  eventToTaskStatus,
  type DataChannelEvent,
  type SessionCallbacks,
} from "./livekitSession";
import type {
  WorkspaceState,
  ConversationMessage,
  TaskEntry,
  VoiceState,
  ConnectionState,
  VoiceIdentityConfig,
  WakeWordStatus,
} from "./workspaceTypes";

// ── Initial state ─────────────────────────────────────────────────────────
const INITIAL_STATE: WorkspaceState = {
  connectionState: "disconnected",
  voiceState: "idle",
  microphoneEnabled: false,
  messages: [],
  currentTranscript: "",
  lineage: { tasks: [] },
  rime: { model: "coda", voice: "lyra", language: "eng", active: false },
  sessionId: null,
  error: null,
  voiceConfig: {
    persona: "signature",
    language: "eng",
    telephonyMode: false,
    speedAlpha: 1.0,
  },
  wakeWordStatus: "idle",
};

// ── Context shape ──────────────────────────────────────────────────────────
interface WorkspaceContextValue {
  state: WorkspaceState;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  toggleMicrophone: () => Promise<void>;
  updateVoiceConfig: (partial: Partial<VoiceIdentityConfig>) => void;
  setWakeWordStatus: (status: WakeWordStatus) => void;
  clearError: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

// ── Provider ───────────────────────────────────────────────────────────────
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WorkspaceState>(INITIAL_STATE);
  const sessionRef = useRef<LiveKitSession | null>(null);
  // Stable identity per browser session
  const identityRef = useRef<string>(`revia-user-${uuidv4().slice(0, 8)}`);

  // ── State updaters ───────────────────────────────────────────────────────

  const setConnection = useCallback((connectionState: ConnectionState) => {
    setState((s) => ({ ...s, connectionState }));
  }, []);

  const setVoiceState = useCallback((voiceState: VoiceState) => {
    setState((s) => ({ ...s, voiceState }));
  }, []);

  const setError = useCallback((error: string | null) => {
    setState((s) => ({ ...s, error }));
  }, []);

  const clearError = useCallback(() => {
    setState((s) => ({ ...s, error: null }));
  }, []);

  // ── Transcript handling ───────────────────────────────────────────────────
  const handleTranscript = useCallback((text: string, isFinal: boolean) => {
    if (!text.trim()) return;
    const now = new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });

    setState((s) => {
      if (!isFinal) {
        return { ...s, currentTranscript: text };
      }
      // Final transcript — add as a confirmed user message
      const msg: ConversationMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        text,
        timeLabel: now,
      };
      return {
        ...s,
        currentTranscript: "",
        messages: [...s.messages, msg],
      };
    });
  }, []);

  // ── Data channel event dispatch ───────────────────────────────────────────
  const handleTaskEvent = useCallback((rawEvent: DataChannelEvent) => {
    const raw = rawEvent as any;
    const payload = (typeof raw.payload === "object" && raw.payload !== null) ? raw.payload : {};
    const eventName: string = raw.event || raw.event_name || "";
    const task_id: string | undefined = raw.task_id || payload.task_id;
    const transcriptText: string | undefined = raw.transcript ?? payload.transcript;
    const isFinal: boolean = Boolean(raw.is_final ?? payload.is_final);
    const requestText: string = raw.request_text || payload.request_text || "...";
    const toolName: string | undefined = raw.tool_name || payload.tool_name;
    const speechId: string | undefined = raw.speech_id || payload.speech_id;
    const createdAt: string = raw.created_at || payload.created_at || new Date().toISOString();
    const responseText: string | undefined = raw.response_text || payload.response_text;
    const msSpoken: number | undefined = raw.ms_spoken ?? payload.ms_spoken;
    const stoppedReason: "completed" | "interrupted" | undefined = raw.stopped_reason || payload.stopped_reason;
    const detectedAt: string | undefined = raw.detected_at || payload.detected_at;

    // ── Transcript from data channel ──────────────────────────────────────
    if (eventName === "transcript" && transcriptText !== undefined) {
      handleTranscript(transcriptText, isFinal);
      return;
    }

    // ── Config applied acknowledgment ─────────────────────────────────────
    if (eventName === "config.applied") {
      const rimeModel = raw.rime_model || "coda";
      const rimeVoice = raw.rime_voice || "lyra";
      const rimeLang = raw.language || "eng";
      setState((s) => ({
        ...s,
        rime: {
          ...s.rime,
          model: rimeModel,
          voice: rimeVoice,
          language: rimeLang,
        },
      }));
      return;
    }

    // ── Voice state update ────────────────────────────────────────────────
    const newVoiceState = eventToVoiceState(eventName);
    if (newVoiceState) {
      setState((s) => ({ ...s, voiceState: newVoiceState }));
    }

    // ── LLM response drafted → add assistant message ──────────────────
    if (eventName === "llm.response_drafted" && responseText) {
      const now = new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
      const assistantMsg: ConversationMessage = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        text: responseText,
        timeLabel: now,
      };
      setState((s) => ({ ...s, messages: [...s.messages, assistantMsg] }));
    }

    // ── Lineage update ────────────────────────────────────────────────────
    if (!task_id) return;

    const newTaskStatus = eventToTaskStatus(eventName);

    setState((s) => {
      const tasks = [...s.lineage.tasks];
      const existingIdx = tasks.findIndex((t) => t.taskId === task_id);

      if (eventName === "task.created") {
        if (existingIdx === -1) {
          const serial = getTaskSerial(task_id);
          const newEntry: TaskEntry = {
            taskId: task_id,
            serialNumber: serial,
            requestText: requestText,
            status: "CREATED",
            createdAt: createdAt,
          };
          return {
            ...s,
            lineage: { ...s.lineage, tasks: [...tasks, newEntry] },
          };
        }
        return s;
      }

      if (newTaskStatus && existingIdx !== -1) {
        const updated = { ...tasks[existingIdx], status: newTaskStatus };

        // Enrich with event-specific fields
        if (eventName === "task.tool_running" && toolName) {
          updated.toolName = toolName;
        }
        if (eventName === "task.speaking" && speechId) {
          updated.speechId = speechId;
        }

        tasks[existingIdx] = updated;
        return { ...s, lineage: { ...s.lineage, tasks } };
      }

      // ── Interruption ────────────────────────────────────────────────────
      if (eventName === "interrupt") {
        sessionRef.current?.stopPlayback();
        return {
          ...s,
          voiceState: "interrupted",
          lineage: {
            ...s.lineage,
            interruptionDetectedAt: detectedAt ?? new Date().toISOString(),
          },
        };
      }

      // ── Speech started ──────────────────────────────────────────────────
      if (eventName === "speech.started") {
        sessionRef.current?.resumePlayback();
      }

      // ── Speech stopped ──────────────────────────────────────────────────
      if (eventName === "speech.stopped" && existingIdx !== -1) {
        if (stoppedReason === "interrupted") {
          sessionRef.current?.stopPlayback();
        }
        const updated = {
          ...tasks[existingIdx],
          msSpoken: msSpoken,
          stoppedReason: stoppedReason,
        };
        tasks[existingIdx] = updated;
        return { ...s, lineage: { ...s.lineage, tasks } };
      }

      return s;
    });
  }, [handleTranscript]);

  // ── Agent presence ────────────────────────────────────────────────────────
  const handleAgentConnected = useCallback(() => {
    setState((s) => ({ ...s, rime: { ...s.rime, active: true } }));
  }, []);

  const handleAgentDisconnected = useCallback(() => {
    setState((s) => ({ ...s, rime: { ...s.rime, active: false } }));
  }, []);

  // ── Session callbacks (stable ref) ─────────────────────────────────────
  const callbacks: SessionCallbacks = useMemo(() => ({
    onConnectionStateChange: setConnection,
    onVoiceStateChange: setVoiceState,
    onTranscript: handleTranscript,
    onTaskEvent: handleTaskEvent,
    onError: setError,
    onAgentConnected: handleAgentConnected,
    onAgentDisconnected: handleAgentDisconnected,
  }), [setConnection, setVoiceState, handleTranscript, handleTaskEvent, setError, handleAgentConnected, handleAgentDisconnected]);

  // ── Public connect/disconnect ──────────────────────────────────────────
  const connect = useCallback(async () => {
    if (sessionRef.current) {
      await sessionRef.current.disconnect();
    }
    resetTaskSerials();
    setState((s) => ({
      ...s,
      messages: [],
      currentTranscript: "",
      lineage: { tasks: [] },
      error: null,
    }));

    const session = new LiveKitSession(callbacks);
    sessionRef.current = session;
    setState((s) => ({ ...s, sessionId: identityRef.current }));
    await session.connect(identityRef.current);
    await session.unlockAudio();

    // Synchronize active voice config to newly connected session
    await session.sendConfigUpdate({
      persona: state.voiceConfig.persona,
      language: state.voiceConfig.language,
      speed_alpha: state.voiceConfig.speedAlpha,
      telephony_mode: state.voiceConfig.telephonyMode,
    });

    setState((s) => ({
      ...s,
      microphoneEnabled: session.isMicrophoneEnabled,
    }));
  }, [callbacks, state.voiceConfig]);

  const disconnect = useCallback(async () => {
    if (sessionRef.current) {
      await sessionRef.current.disconnect();
      sessionRef.current = null;
    }
    setState((s) => ({
      ...s,
      connectionState: "disconnected",
      voiceState: "idle",
      microphoneEnabled: false,
      rime: { ...s.rime, active: false },
    }));
  }, []);

  const toggleMicrophone = useCallback(async () => {
    const session = sessionRef.current;
    if (!session) return;
    await session.unlockAudio();
    const next = !state.microphoneEnabled;
    await session.setMicrophoneEnabled(next);
    setState((s) => ({
      ...s,
      microphoneEnabled: next,
      voiceState: next ? "listening" : "idle",
    }));
  }, [state.microphoneEnabled]);

  const updateVoiceConfig = useCallback((partial: Partial<VoiceIdentityConfig>) => {
    setState((s) => {
      const nextConfig = { ...s.voiceConfig, ...partial };
      const rimeModel = nextConfig.persona === "concierge" ? "mistv2" : "coda";
      const rimeVoice = nextConfig.persona === "concierge" ? "cove" : "lyra";
      const rimeLang = nextConfig.language;
      if (sessionRef.current) {
        sessionRef.current.sendConfigUpdate({
          persona: nextConfig.persona,
          language: nextConfig.language,
          speed_alpha: nextConfig.speedAlpha,
          telephony_mode: nextConfig.telephonyMode,
        });
      }
      return {
        ...s,
        voiceConfig: nextConfig,
        rime: {
          ...s.rime,
          model: rimeModel as any,
          voice: rimeVoice as any,
          language: rimeLang as any,
        },
      };
    });
  }, []);

  const setWakeWordStatus = useCallback((wakeWordStatus: WakeWordStatus) => {
    setState((s) => ({ ...s, wakeWordStatus }));
  }, []);

  // ── Cleanup on unmount ────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      sessionRef.current?.disconnect();
    };
  }, []);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      state,
      connect,
      disconnect,
      toggleMicrophone,
      updateVoiceConfig,
      setWakeWordStatus,
      clearError,
    }),
    [state, connect, disconnect, toggleMicrophone, updateVoiceConfig, setWakeWordStatus, clearError]
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextValue {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return value;
}
