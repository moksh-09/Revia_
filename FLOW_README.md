# REVIA — Current Backend Flow

## Purpose

REVIA is a general conversational voice agent focused on one hard voice
problem: Reliable Full-Duplex Task Switching.

The problem has two behavioral dimensions:

1. Interruption and recovery while REVIA is speaking or working.
2. Conversation continuity when a new turn arrives during tool work.

Sales analytics and synthetic sales data are not part of the product. The only
tool retained in the current backend is a neutral delayed demonstration
workload used to exercise task switching.

## Current end-to-end flow

Microphone
→ LiveKit AgentSession
→ Deepgram STT
→ REVIA Agent
→ AgentBrain session context
→ TaskManager
→ Groq general reasoning
→ Optional delayed_demo_work
→ task/fence validation
→ response generation
→ Rime TTS
→ LiveKit playback
→ User

The LiveKit entrypoint is backend/voice_io/agent.py. Final transcripts are
dispatched asynchronously to ReviaVoiceAgent.process_transcript(), so a
delayed tool does not block receipt of later LiveKit turns.

## Component responsibilities

- backend/voice_io/agent.py receives final Deepgram transcripts, observes
  user-speaking interruptions, starts the brain pipeline, and owns the final
  session-liveness and speech-queue boundary.
- backend/orchestration/agent_brain.py owns same-session conversation context,
  calls Groq for general reasoning, optionally calls the delayed demo tool,
  validates results, and drafts the spoken response.
- backend/state/task_manager.py owns task lifecycle and the authoritative
  active task.
- backend/state/fencing.py validates task/fence provenance for tool results
  and LLM responses.
- backend/orchestration/tool_contract.py defines ToolRequest and ToolResponse.
- backend/orchestration/stub_tool_client.py implements the neutral
  delayed_demo_work workload and echoes the originating task ID and fence.
- backend/rime/tts_rime.py creates the configured Rime TTS and queues speech
  through AgentSession.say().
- backend/rime/events.py tracks speech lifecycle and interrupts active Rime
  playback when new user speech is detected.

## Task authority and fencing

Every user turn creates a task with a task_id and fence_token. TaskManager owns
task status and authority. When a new turn interrupts or replaces an active
task, the old task becomes obsolete and its mutable fence is invalidated; the
new task becomes authoritative.

Tool requests and responses carry both the originating task ID and fence.
Results are checked before response generation. LLM responses are checked
again before conversation commit and before the voice agent queues Rime speech.
An obsolete result therefore cannot become current merely because its work
finished late. Correctness does not depend on tool cancellation succeeding.

Conversation context is separate from execution authority. User turns are
recorded in session order. Validated assistant responses are committed once.
Invalidating a task does not erase established context, while an obsolete task
cannot commit its assistant response.

## Interruption and recovery

When LiveKit reports new user speech, the agent interrupts active Rime playback
and obsoletes the active task. The subsequent final transcript creates the new
authoritative task. Detached asynchronous work may finish, but task/fence
validation rejects its result before generation or speech.

The agent also tracks the public AgentSession close event. It checks session
liveness immediately before queueing Rime speech and narrowly contains the two
known LiveKit teardown errors: AgentSession isn't running and AgentSession is
closing, cannot use say().

## Generic delayed workload

delayed_demo_work is demonstration/test scaffolding only. It waits for a
configured delay and returns Delayed operation completed. with the original
task ID and fence token. It is not a database, analytics service, or product
data source.

## Rime and frontend boundary

Rime is REVIA's primary spoken output. Substantive responses use Rime through
LiveKit AgentSession.say() with interruptions enabled. The frontend does not
own task IDs, fences, task invalidation, or stale-result decisions.

The current repository contains the backend voice worker and LiveKit session
boundary; it does not define a frontend API or frontend task-state protocol.
A future frontend should consume the existing voice/session behavior and must
not implement a second task or fence authority.

## Setup and run

Use the existing project environment and .env values for LiveKit, Deepgram,
Rime, and Groq credentials. Secrets are not documented.

Start the worker from the project root:

    cd D:\revia
    python backend\voice_io\agent.py dev

Useful deterministic checks are:

    python -m pytest backend\state -q
    python -m pytest backend\evaluation\test_backend_e2e.py -q

## Current limitations

- Same-session context is not permanent or cross-session memory.
- Tool cancellation is best effort; stale-result rejection is the correctness
  mechanism.
- The complete real LiveKit delayed-tool refinement trace is NOT VERIFIED LIVE
  in one preserved event timeline. Deterministic tests are not live proof.
- Exact installed package versions are environment-dependent because the
  repository does not provide a complete lockfile.
