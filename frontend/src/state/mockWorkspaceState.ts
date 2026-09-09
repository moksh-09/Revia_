import type { WorkspaceState } from "./workspaceTypes";

/** Preview-only state source. It will be replaced by a live adapter later. */
export const mockWorkspaceState: WorkspaceState = {
  connectionState: "disconnected",
  voiceState: "idle",
  microphoneActive: false,
  messages: [
    {
      id: "preview-user-1",
      role: "user",
      text: "Can you help me organize this request?",
      timeLabel: "10:42 AM",
    },
    {
      id: "preview-assistant-1",
      role: "assistant",
      text: "Absolutely. I’m ready to work through it with you.",
      timeLabel: "10:42 AM",
    },
    {
      id: "preview-user-2",
      role: "user",
      text: "Actually, refine the current request.",
      timeLabel: "10:43 AM",
    },
  ],
  currentTranscript: "",
  activity: {
    currentRequest: "Refining the current request",
    status: "switching",
    currentWork: "Preparing a clear response",
    previousRequest: "Initial request",
    error: null,
  },
  reliability: {
    currentRequest: "Refining the current request",
    replacedRequest: "Initial request",
    staleResultIgnored: true,
    interruption: "recovered",
  },
};
