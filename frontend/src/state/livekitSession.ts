/**
 * livekitSession.ts
 * ─────────────────
 * Manages the browser's LiveKit room connection for REVIA.
 *
 * Architecture:
 *   Browser → GET /token (server-side) → short-lived JWT
 *           → LiveKit room join
 *           → observe remote agent participant
 *           → receive data channel events (task timeline)
 *           → publish local microphone
 *
 * The backend remains authoritative for all task/fence logic.
 * This module is a pure observer and microphone publisher.
 *
 * Security: LIVEKIT_API_SECRET never reaches this file.
 * Only VITE_TOKEN_SERVER_URL is used (public URL, no secret).
 */

import {
  Room,
  RoomEvent,
  ConnectionState,
  RemoteParticipant,
  TrackPublication,
  Track,
  ParticipantEvent,
  DisconnectReason,
} from "livekit-client";
import type {
  ConnectionState as AppConnectionState,
  VoiceState,
  TaskEntry,
  TaskStatus,
} from "./workspaceTypes";

// ── Config ───────────────────────────────────────────────────────────────
const TOKEN_SERVER_URL = import.meta.env.VITE_TOKEN_SERVER_URL ?? "http://localhost:7880";
const ROOM_NAME        = import.meta.env.VITE_LIVEKIT_ROOM    ?? "revia-room";

// ── Event callbacks passed in from WorkspaceProvider ─────────────────────
export interface SessionCallbacks {
  onConnectionStateChange: (state: AppConnectionState) => void;
  onVoiceStateChange:      (state: VoiceState) => void;
  onTranscript:            (text: string, isFinal: boolean) => void;
  onTaskEvent:             (event: DataChannelEvent) => void;
  onError:                 (message: string) => void;
  onAgentConnected:        () => void;
  onAgentDisconnected:     () => void;
}

/** Shape of events the backend publishes over the LiveKit data channel */
export interface DataChannelEvent {
  event: string;
  task_id?: string;
  speech_id?: string;
  stopped_reason?: "completed" | "interrupted";
  ms_spoken?: number;
  detected_at?: string;
  tool_name?: string;
  request_text?: string;
  created_at?: string;
  previous_task_id?: string;
  superseded_by_task_id?: string;
  error?: string;
  fence_token?: string;
  response_text?: string;
  // transcript events
  transcript?: string;
  is_final?: boolean;
}

// ── Session ───────────────────────────────────────────────────────────────
export class LiveKitSession {
  private room: Room | null = null;
  private callbacks: SessionCallbacks;
  private agentSpeaking = false;
  private _disposed = false;
  private attachedAudioElements = new Map<string, HTMLMediaElement>();

  private attachTrack(track: Track): void {
    if (track.kind !== Track.Kind.Audio) return;
    const trackSid = track.sid || (track as any).mediaStreamTrack?.id || "default";
    if (this.attachedAudioElements.has(trackSid)) {
      const existing = this.attachedAudioElements.get(trackSid)!;
      existing.muted = false;
      existing.play().catch(() => {});
      return; // Prevent duplicate audio elements (fixes echo / double voice)
    }

    const el = track.attach();
    el.id = `livekit-audio-${trackSid}`;
    document.body.appendChild(el);
    el.muted = false;
    el.volume = 1.0;
    this.attachedAudioElements.set(trackSid, el);

    // Play immediately and unlock room audio if blocked by autoplay
    el.play().catch((err) => {
      console.warn("[LiveKitSession] Audio play() blocked:", err);
      this.room?.startAudio().catch(() => {});
    });
  }

  private detachTrack(track: Track): void {
    const trackSid = track.sid || (track as any).mediaStreamTrack?.id || "default";
    if (this.attachedAudioElements.has(trackSid)) {
      const el = this.attachedAudioElements.get(trackSid)!;
      el.pause();
      el.remove();
      this.attachedAudioElements.delete(trackSid);
    }
    track.detach();
  }

  public stopPlayback(): void {
    this.attachedAudioElements.forEach((el) => {
      el.muted = true;
    });
  }

  public resumePlayback(): void {
    this.attachedAudioElements.forEach((el) => {
      el.muted = false;
      el.play().catch(() => {});
    });
  }

  public async unlockAudio(): Promise<void> {
    if (this.room) {
      try {
        await this.room.startAudio();
      } catch (err) {
        console.warn("[LiveKitSession] room.startAudio error:", err);
      }
    }
    this.resumePlayback();
  }

  public async sendConfigUpdate(config: {
    persona: string;
    language: string;
    speed_alpha: number;
    telephony_mode: boolean;
  }): Promise<void> {
    if (!this.room || this.room.state !== ConnectionState.Connected) return;
    try {
      const payload = JSON.stringify({
        event: "config.update",
        ...config,
      });
      await this.room.localParticipant.publishData(
        new TextEncoder().encode(payload),
        { reliable: true }
      );
    } catch (err) {
      console.warn("[LiveKitSession] sendConfigUpdate failed:", err);
    }
  }

  constructor(callbacks: SessionCallbacks) {
    this.callbacks = callbacks;
  }

  /** Fetch a short-lived token from the server-side token endpoint. */
  private async fetchToken(identity: string): Promise<{ token: string; url: string }> {
    const url = `${TOKEN_SERVER_URL}/token?room=${encodeURIComponent(ROOM_NAME)}&identity=${encodeURIComponent(identity)}`;
    const res = await fetch(url);
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`Token server error ${res.status}: ${body}`);
    }
    return res.json();
  }

  /** Connect to the LiveKit room. Idempotent — safe to call multiple times. */
  async connect(identity: string): Promise<void> {
    if (this._disposed) return;
    if (this.room && this.room.state !== ConnectionState.Disconnected) return;

    this.callbacks.onConnectionStateChange("connecting");

    let tokenData: { token: string; url: string };
    try {
      tokenData = await this.fetchToken(identity);
    } catch (err) {
      this.callbacks.onError(`Failed to get session token: ${(err as Error).message}`);
      this.callbacks.onConnectionStateChange("error");
      return;
    }

    const room = new Room({
      adaptiveStream: true,
      dynacast: true,
    });
    this.room = room;

    // ── Room-level events ────────────────────────────────────────────────
    room.on(RoomEvent.ConnectionStateChanged, (state) => {
      switch (state) {
        case ConnectionState.Connected:
          this.callbacks.onConnectionStateChange("connected");
          break;
        case ConnectionState.Reconnecting:
          this.callbacks.onConnectionStateChange("reconnecting");
          break;
        case ConnectionState.Disconnected:
          this.callbacks.onConnectionStateChange("disconnected");
          break;
        case ConnectionState.Connecting:
          this.callbacks.onConnectionStateChange("connecting");
          break;
      }
    });

    room.on(RoomEvent.Disconnected, (reason?: DisconnectReason) => {
      if (!this._disposed) {
        this.callbacks.onConnectionStateChange("disconnected");
        if (reason !== undefined && reason !== DisconnectReason.CLIENT_INITIATED) {
          this.callbacks.onError(`Disconnected (reason: ${reason}). Reconnecting...`);
        }
      }
    });

    // ── Data channel — task/speech events from agent ─────────────────────
    room.on(RoomEvent.DataReceived, (payload: Uint8Array) => {
      try {
        const text = new TextDecoder().decode(payload);
        const event: DataChannelEvent = JSON.parse(text);
        this.callbacks.onTaskEvent(event);
      } catch {
        // ignore malformed payloads
      }
    });

    // ── Remote participant (agent) events ────────────────────────────────
    room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
      this.callbacks.onAgentConnected();
      this._bindParticipantEvents(participant);
    });

    room.on(RoomEvent.ParticipantDisconnected, () => {
      this.agentSpeaking = false;
      this.callbacks.onAgentDisconnected();
    });

    room.on(
      RoomEvent.TrackSubscribed,
      (track: Track) => {
        this.attachTrack(track);
      }
    );

    room.on(
      RoomEvent.TrackUnsubscribed,
      (track: Track) => {
        this.detachTrack(track);
      }
    );

    // ── Connect ──────────────────────────────────────────────────────────
    try {
      await room.connect(tokenData.url, tokenData.token);
      // Unlock browser audio context in user-initiated connection flow
      await room.startAudio().catch((err) => {
        console.warn("[LiveKitSession] startAudio on connect note:", err);
      });
    } catch (err) {
      this.callbacks.onError(`LiveKit connection failed: ${(err as Error).message}`);
      this.callbacks.onConnectionStateChange("error");
      return;
    }

    // Bind all participants already in room after connect() succeeds
    room.remoteParticipants.forEach((p) => {
      this._bindParticipantEvents(p);
      if (p.isSpeaking) {
        this.agentSpeaking = true;
      }
      p.trackPublications.forEach((pub) => {
        if (pub.track && pub.track.kind === Track.Kind.Audio) {
          this.attachTrack(pub.track);
        }
      });
    });

    // Enable microphone
    try {
      await room.localParticipant.setMicrophoneEnabled(true);
    } catch (err) {
      this.callbacks.onError(`Microphone access denied: ${(err as Error).message}`);
    }

    // Check for agent already in room
    if (room.remoteParticipants.size > 0) {
      this.callbacks.onAgentConnected();
    }
  }

  /** Enable or disable the local microphone. */
  async setMicrophoneEnabled(enabled: boolean): Promise<void> {
    if (!this.room) return;
    try {
      await this.room.localParticipant.setMicrophoneEnabled(enabled);
    } catch (err) {
      this.callbacks.onError(`Microphone toggle failed: ${(err as Error).message}`);
    }
  }

  /** Disconnect and clean up all listeners. */
  async disconnect(): Promise<void> {
    this._disposed = true;
    this.attachedAudioElements.forEach((el) => {
      try {
        el.pause();
        el.remove();
      } catch {}
    });
    this.attachedAudioElements.clear();
    if (this.room) {
      this.room.removeAllListeners();
      await this.room.disconnect();
      this.room = null;
    }
  }

  get isMicrophoneEnabled(): boolean {
    return this.room?.localParticipant.isMicrophoneEnabled ?? false;
  }

  get connectionState(): AppConnectionState {
    if (!this.room) return "disconnected";
    switch (this.room.state) {
      case ConnectionState.Connected:    return "connected";
      case ConnectionState.Reconnecting: return "reconnecting";
      case ConnectionState.Connecting:  return "connecting";
      default:                           return "disconnected";
    }
  }

  // ── Private helpers ────────────────────────────────────────────────────

  private _bindParticipantEvents(participant: RemoteParticipant): void {
    // Check tracks already published by this participant
    participant.trackPublications.forEach((pub) => {
      if (pub.track && pub.track.kind === Track.Kind.Audio) {
        this.attachTrack(pub.track);
      }
    });

    participant.on(ParticipantEvent.IsSpeakingChanged, (speaking: boolean) => {
      this.agentSpeaking = speaking;
      // Voice state is primarily driven by data channel events.
      // Participant speaking gives us a fallback when data channel isn't active.
      if (speaking) {
        this.callbacks.onVoiceStateChange("speaking");
      } else {
        this.callbacks.onVoiceStateChange("idle");
      }
    });

    participant.on(
      ParticipantEvent.TrackPublished,
      (pub: TrackPublication) => {
        if (pub.track && pub.track.kind === Track.Kind.Audio) {
          this.attachTrack(pub.track);
        }
      }
    );

    participant.on(
      ParticipantEvent.TrackSubscribed,
      (track: Track) => {
        this.attachTrack(track);
      }
    );

    participant.on(
      ParticipantEvent.TrackUnsubscribed,
      (track: Track) => {
        this.detachTrack(track);
      }
    );
  }
}

// ── Task event → TaskEntry conversion ────────────────────────────────────
let _taskCounter = 0;
const _taskSerialMap = new Map<string, number>();

export function getTaskSerial(taskId: string): number {
  if (!_taskSerialMap.has(taskId)) {
    _taskSerialMap.set(taskId, ++_taskCounter);
  }
  return _taskSerialMap.get(taskId)!;
}

export function resetTaskSerials(): void {
  _taskCounter = 0;
  _taskSerialMap.clear();
}

/** Map a data channel event name to a display-friendly VoiceState */
export function eventToVoiceState(eventName: string): VoiceState | null {
  switch (eventName) {
    case "task.active":       return "thinking";
    case "task.tool_running": return "working";
    case "task.generating":   return "thinking";
    case "task.speaking":     return "speaking";
    case "task.completed":    return "idle";
    case "task.cancelled":    return "idle";
    case "task.obsolete":     return "interrupted";
    case "task.failed":       return "idle";
    case "interrupt":         return "interrupted";
    case "speech.started":    return "speaking";
    case "speech.stopped":    return "idle";
    default:                  return null;
  }
}

/** Map data channel event name to TaskStatus for lineage tracking */
export function eventToTaskStatus(eventName: string): TaskStatus | null {
  switch (eventName) {
    case "task.created":      return "CREATED";
    case "task.active":       return "ACTIVE";
    case "task.tool_running": return "TOOL_RUNNING";
    case "task.generating":   return "GENERATING";
    case "task.speaking":     return "SPEAKING";
    case "task.completed":    return "COMPLETED";
    case "task.cancelled":    return "CANCELLED";
    case "task.obsolete":     return "OBSOLETE";
    case "task.failed":       return "FAILED";
    default:                  return null;
  }
}
