REVIA

## Realtime Voice Intelligence with Reliable Full-Duplex Task Switching

REVIA is a realtime, voice-native conversational assistant designed for conversations where users interrupt, refine, or change their requests while the system is still speaking or working.

### Core idea

> **REVIA is interruptible by design and correct by construction.**

The central problem is **reliable full-duplex task switching**:

> When a user interrupts REVIA while it is speaking or while an asynchronous operation is still running, how can the system guarantee that an outdated request does not later become the response the user hears?

REVIA addresses this with **task-aware interruption recovery and stale-result protection**.

Every user request receives a unique `task_id` and `fence_token`. Only the currently authoritative task may update conversation state or produce spoken output. When a user interrupts or changes their request, the previous task loses authority. If an older asynchronous operation finishes later, its result is checked against the current task/fence and rejected when stale.

Cancellation is helpful when available; **fencing is the correctness guarantee**.

---

# 1. What REVIA Demonstrates

REVIA focuses on one hard voice problem and demonstrates it through two related stress cases.

## Scenario A — Interrupt While Speaking

REVIA begins speaking a response through Rime.

The user starts speaking before the response finishes.

Expected behavior:

```text
REVIA SPEAKING
      ↓
USER INTERRUPTS
      ↓
OLD SPEECH STOPS
      ↓
OLD TASK BECOMES OBSOLETE
      ↓
NEW TASK BECOMES ACTIVE
      ↓
NEW REQUEST IS PROCESSED
      ↓
NEW RESPONSE IS SPOKEN
```

The previous response must not resume as the current answer.

## Scenario B — Interrupt During Tool Execution

REVIA starts a request that invokes an asynchronous delayed demonstration workload.

Before the workload finishes, the user changes the request.

Expected behavior:

```text
Task A
  ↓
TOOL_RUNNING
  ↓
USER CHANGES REQUEST
  ↓
Task A → OBSOLETE / REPLACED
  ↓
Task B → ACTIVE
  ↓
Task A FINISHES LATE
  ↓
FENCE VALIDATION
  ↓
TASK A RESULT REJECTED
  ↓
TASK A RESULT IS NOT SPOKEN
  ↓
TASK B REMAINS AUTHORITATIVE
  ↓
RIME SPEAKS TASK B
```

The delayed workload is test/demo infrastructure. It is not presented as the product itself.

---

# 2. Why Voice Is Necessary

The failure mode REVIA addresses is fundamentally a voice interaction problem.

In a typed chat interface, a message is generally complete once it is submitted. In a realtime voice conversation, the user can begin speaking while the assistant is still producing an answer.

That creates states that must be handled concurrently:

- the assistant is speaking;
- the user starts another utterance;
- an older tool may still be running;
- an older model request may finish later;
- the newest request must take authority;
- stale output must not reach the user.

REVIA treats interruption as a first-class control path rather than as a normal sequential pipeline stage.

---

# 3. Core Correctness Model

Each request is associated with:

- `task_id`
- `fence_token`
- task lifecycle state

The task lifecycle includes:

```text
CREATED
   ↓
ACTIVE
   ↓
TOOL_RUNNING
   ↓
GENERATING
   ↓
SPEAKING
   ↓
COMPLETED
```

Terminal/replacement states include:

```text
CANCELLED
OBSOLETE
FAILED
```

When a new request supersedes an existing task:

```text
OLD TASK
   ↓
OBSOLETE / CANCELLED
   ↓
FENCE INVALIDATED

NEW TASK
   ↓
ACTIVE
```

Asynchronous results retain the identity of the task that produced them.

Before a result can affect current conversation state or proceed to spoken output, REVIA validates that its task/fence is still authoritative.

Therefore:

```text
Late result ≠ valid result
```

Even when arbitrary background work cannot be physically cancelled, its stale result can still be prevented from becoming the current response.

---

# 4. Architecture

```text
                         REVIA
                           │
                           ▼
                  Browser Microphone
                           │
                           ▼
                LiveKit Realtime Transport
                           │
                           ▼
                   REVIA Voice Agent
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
        Deepgram STT             Session / Context
                                        │
                                        ▼
                                 Task Manager
                                        │
                         ┌──────────────┴──────────────┐
                         │                             │
                         ▼                             ▼
                 Interruption                  Task / Fence
                   Handling                    Validation
                         │                             │
                         └──────────────┬──────────────┘
                                        ▼
                              LLM / Orchestration
                                        │
                              ┌─────────┴─────────┐
                              │                   │
                              ▼                   ▼
                           Gemini                Groq
                         / primary            / fallback
                              │                   │
                              └─────────┬─────────┘
                                        ▼
                              Optional Delayed Work
                                        │
                                        ▼
                              Response Validation
                                        │
                                        ▼
                                   Rime TTS
                                        │
                                        ▼
                              LiveKit Audio Playback
                                        │
                                        ▼
                                      USER
```

The application also emits task/voice events used by the evaluation and reliability UI.

---

# 5. Runtime Flow

The realtime path is:

```text
Microphone
    ↓
LiveKit
    ↓
Deepgram STT
    ↓
REVIA Voice Agent
    ↓
Task / Conversation State
    ↓
LLM Orchestration
    ↓
Optional asynchronous workload
    ↓
Task + Fence Validation
    ↓
Response
    ↓
Rime TTS
    ↓
LiveKit Audio
    ↓
Browser
```

Interruption is not treated as a normal sequential stage. It can preempt the flow while the agent is:

- working on a tool;
- generating a response;
- speaking through Rime.

---

# 6. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript |
| Frontend build | Vite |
| Browser realtime client | `livekit-client` |
| Realtime transport | LiveKit |
| Voice agent runtime | LiveKit Agents |
| Speech-to-text | Deepgram |
| Primary LLM configuration | Gemini |
| LLM fallback | Groq |
| Text-to-speech | Rime |
| Backend API/token service | FastAPI |
| Task management | REVIA TaskManager |
| Task correctness | Fence tokens + stale-result validation |

---

# 7. Rime Configuration

Rime is the **primary spoken-output provider** for REVIA.

The exact Rime configuration used by the implementation is:

| Parameter | Value |
|---|---|
| Model | `coda` |
| Speaker | `lyra` |
| Language | `eng` |
| Endpoint | `wss://users-ws.rime.ai/ws3` |
| Audio format | `pcm` |
| Sample rate | `16000 Hz` |
| Transport | WebSocket |
| Playback path | Rime → LiveKit AgentSession → Browser |

Rime is used for substantive spoken responses.

REVIA does not use browser Web Speech API or another client-side TTS system as a competing spoken-output path.

The Rime API key is server-side only.

---

# 8. Conversation and Task State

REVIA preserves valid conversation context within the active session.

An interruption does not erase previously valid conversation state merely because the latest task was replaced.

Instead:

```text
Valid previous context
        +
New authoritative request
        ↓
Current response
```

An obsolete task cannot commit its result as the current conversation state.

This allows interactions such as:

```text
User:
"Tell me about Maharashtra."

User:
"Now make that only Pune."
```

The second request is interpreted in the context of the first while becoming the authoritative current task.

---

# 9. Interruption Handling

When the user begins speaking while REVIA is speaking:

1. Rime playback is interrupted.
2. The current task is invalidated/marked obsolete.
3. The new utterance is accepted.
4. A new task is created.
5. The new task becomes authoritative.
6. The new request is processed.
7. Only the new valid response is sent to Rime.

Conceptually:

```text
                    INTERRUPT
                       │
                       ▼
              Stop current speech
                       │
                       ▼
             Invalidate old task
                       │
                       ▼
              Create new task
                       │
                       ▼
              New task ACTIVE
                       │
                       ▼
              Process new request
                       │
                       ▼
                Rime speaks
```

---

# 10. Stale-Result Protection

The most important correctness property is that an asynchronous operation cannot regain authority after its task has been replaced.

Example:

```text
Task A → delayed operation starts

User changes request

Task A → OBSOLETE
Task B → ACTIVE

Task A → operation finishes

                ↓
         fence validation
                ↓
          Task A is stale
                ↓
             REJECT
```

The result is therefore prevented from:

- updating authoritative state;
- replacing the current response;
- being spoken as current information.

This protection is independent of whether the underlying operation supports physical cancellation.

---

# 11. Backend Components

The repository is organized into the following major areas:

```text
backend/
├── evaluation/
├── orchestration/
├── rime/
├── state/
├── tools/
└── voice_io/
```

Important runtime responsibilities include:

### `backend/voice_io/`

LiveKit voice-agent runtime, microphone/session handling, and Deepgram integration.

### `backend/rime/`

Rime TTS integration and speech lifecycle handling.

### `backend/state/`

Task lifecycle, active-task authority, interruption invalidation, and fencing.

### `backend/orchestration/`

LLM orchestration, response generation, tool coordination, and validation.

### `backend/tools/`

Deterministic tools and the delayed demonstration workload used for task-switching tests.

### `backend/evaluation/`

Evaluation, stress testing, metrics, and evidence support.

---

# 12. Frontend

The frontend is a React + TypeScript Vite application.

The interface is designed as a voice-first workspace rather than a conventional analytics dashboard.

It provides user-facing views for:

- microphone interaction;
- listening/speaking/working states;
- realtime conversation;
- current request;
- request lineage;
- reliability/task state;
- Rime status;
- connection state;
- error states.

The frontend is a **viewer of backend authority**.

It does not independently decide whether a task is current, obsolete, or valid.

---

# 13. LiveKit Session and Token Flow

The browser does not receive provider API secrets.

The intended authorization flow is:

```text
Browser
   │
   │ GET /token?room=revia-room&identity=<user>
   ▼
FastAPI token server
   │
   │ signs short-lived JWT
   ▼
Browser
   │
   │ LiveKit JWT
   ▼
LiveKit room
```

The token server uses:

```text
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
```

server-side.

Only the public token-server URL is exposed to the browser.

The following must never be exposed through Vite/client-side configuration:

```text
LIVEKIT_API_SECRET
RIME_API_KEY
DEEPGRAM_API_KEY
GROQ_API_KEY
other provider secrets
```

---

# 14. Environment Configuration

Create a local `.env` using `.env.example` as the template.

Secrets belong only in the local/server environment.

Do not commit:

```text
.env
.env.local
API keys
API secrets
access tokens
```

The repository should contain placeholder configuration only.

For the frontend, only non-secret configuration should use Vite environment variables.

Example:

```text
VITE_TOKEN_SERVER_URL=<public token server URL>
VITE_LIVEKIT_ROOM=revia-room
```

---

# 15. Local Setup

## Clone the repository

```bash
git clone https://github.com/vedantk-086/revia.git
cd revia
```

## Backend dependencies

Create/activate a Python environment and install:

```bash
pip install -r requirements.txt
```

Create `.env` from `.env.example` and populate the required server-side credentials.

---

# 16. Run the Token Server

From the repository root:

```bash
uvicorn token_server:app --port 7880 --reload
```

Health check:

```bash
curl http://localhost:7880/health
```

The token endpoint follows the form:

```text
GET /token?room=<room>&identity=<identity>
```

The token response contains the LiveKit session information required by the browser without exposing the LiveKit API secret.

---

# 17. Run the Frontend

```bash
cd frontend
npm install
npm run dev
```

For a production build:

```bash
npm run build
```

The frontend then connects to the configured token server and joins the LiveKit room.

---

# 18. Run the REVIA Agent

The LiveKit agent entrypoint is located at:

```text
backend/voice_io/agent.py
```

The exact production/startup command should follow the LiveKit agent configuration used for the deployed worker.

For direct local execution, use the repository's configured Python entrypoint for the agent.

Do not expose provider credentials when starting the agent.

---

# 19. Testing the Core Behavior

## Normal voice flow

Verify:

```text
Browser connected
      ↓
Microphone active
      ↓
User speaks
      ↓
Deepgram transcript
      ↓
REVIA processes request
      ↓
Response generated
      ↓
Rime speaks
      ↓
Audio heard in browser
```

## Scenario A

While REVIA is speaking, interrupt with a new request.

Verify:

- old speech stops;
- old task becomes obsolete/replaced;
- new task becomes active;
- new response is generated;
- Rime speaks the new response.

## Scenario B

Start the delayed demonstration workload.

While it is running, change the request.

Verify:

- Task A becomes obsolete/replaced;
- Task B becomes active;
- Task A may finish later;
- Task A's late result fails fence validation;
- Task A's stale result is not spoken;
- Task B remains authoritative and is spoken.

---

# 20. Evidence and Reproducibility

The repository contains:

```text
RIME_EVIDENCE.md
```

This document records:

- the hard voice claim;
- acceptance criteria;
- test procedure;
- observed results;
- Rime configuration;
- repeatability information;
- limitations.

The evidence file should contain only behavior that has actually been run and observed.

The implementation itself is not treated as proof of a live integration.

---

# 21. Known Limitations

1. The delayed workload is controlled demonstration/test infrastructure rather than a production external database or analytics service.
2. Physical cancellation of arbitrary external work is not assumed. REVIA relies on task/fence validation to prevent stale results from becoming authoritative.
3. Network conditions, browser microphone permissions, LiveKit connectivity, and third-party provider availability can affect realtime behavior.
4. Conversation continuity is maintained within the active session; this is not a permanent cross-session memory system.
5. Full-duplex correctness is an application-level property involving realtime transport, interruption handling, task authority, orchestration, and speech delivery. It is not claimed as a property of Rime alone.
6. Specific latency or end-to-end performance numbers should only be reported when measured in the corresponding evidence run.
7. Frontend reliability indicators reflect backend events that are actually observable; the UI must not fabricate task state.

---

# 22. Security

REVIA keeps provider secrets on the server.

Never commit or expose:

```text
LIVEKIT_API_SECRET
RIME_API_KEY
DEEPGRAM_API_KEY
GROQ_API_KEY
other provider credentials
```

Never place these values in:

```text
frontend/.env
VITE_* variables
JavaScript bundles
screenshots
demo recordings
README files
```

Use `.env.example` for placeholders only.

---

# 23. Repository Structure

```text
revia/
│
├── backend/
│   ├── evaluation/
│   ├── orchestration/
│   ├── rime/
│   ├── state/
│   ├── tools/
│   └── voice_io/
│
├── frontend/
│   ├── src/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.ts
│
├── token_server.py
├── requirements.txt
├── .env.example
├── CONTRACTS.md
├── FLOW_README.md
├── PROGRESS.md
├── RIME_EVIDENCE.md
└── README.md
```

---

# 24. Project Differentiator

Most voice assistants can produce a response.

REVIA focuses on what happens when the user **does not wait for that response to finish**.

The system therefore treats:

```text
interrupt
change request
cancel
refine
new request
```

as first-class realtime events.

The resulting design is:

```text
Voice
  +
Realtime transport
  +
Task authority
  +
Fencing
  +
Stale-result rejection
  +
Controlled speech delivery
```

The objective is not simply to make a voice assistant that talks.

It is to make one that remains **correct while the conversation is changing**.

---

# 25. Submission Checklist

Before submission, verify:

- [ ] Working source repository is accessible to judges.
- [ ] `README.md` is present.
- [ ] `RIME_EVIDENCE.md` is present.
- [ ] `.env.example` contains placeholders only.
- [ ] No `.env` or provider secrets are committed.
- [ ] Exact Rime model is documented.
- [ ] Exact Rime speaker is documented.
- [ ] Exact Rime language is documented.
- [ ] Exact Rime endpoint is documented.
- [ ] Exact Rime audio format is documented.
- [ ] Exact Rime transport is documented.
- [ ] Setup instructions are reproducible.
- [ ] Architecture is documented.
- [ ] Third-party services are documented.
- [ ] Known limitations are documented.
- [ ] The recorded demo demonstrates the hard voice problem.
- [ ] Evidence contains actual observed results rather than unverified claims.

---

# 26. One-Line Summary

> **REVIA is a realtime voice agent that lets users interrupt, refine, and change their minds without allowing stale work or outdated responses to take over the conversation.**

---

## Built for the DataForge Rime Challenge

REVIA uses Rime as its primary spoken-output provider and LiveKit as the realtime transport layer.

**Interruptible by design. Correct by construction.**
