# ◈ REVIA — Full-Duplex Voice Intelligence System



# ◈ Overview

**REVIA** is a realtime voice-native conversational system designed for situations where a user does not wait for an assistant to finish.

A conventional assistant can be modeled as:

```text
User speaks
    ↓
System thinks
    ↓
System responds
    ↓
Turn ends
```

REVIA instead treats conversation as a concurrent, interruptible process:

```text
User speaks
    ↓
REVIA processes
    ↓
REVIA works / thinks / speaks
    ↓
User speaks again
    ↓
Current request changes
    ↓
Previous task loses authority
    ↓
New task becomes authoritative
    ↓
Only the current valid result can be spoken
```

The central design principle is:

> **Cancellation is helpful, but fencing is the correctness guarantee.**

If an old asynchronous operation cannot be physically cancelled, REVIA still prevents its late result from taking control of the conversation.

---

# ◈ The Hard Voice Problem

## Problem Statement

> **How does a realtime voice agent remain conversationally correct when the user interrupts it while it is speaking, generating an answer, or waiting for asynchronous work?**

This is harder than ordinary request/response chat because multiple operations can be alive simultaneously.

For example:

```text
Task A
  └── tool is running

User interrupts

Task B
  └── new request becomes active

Task A finishes late
```

Without explicit task authority, Task A can accidentally:

- update the current conversation;
- overwrite a newer response;
- produce stale speech;
- continue after the user has changed their request;
- confuse the user by answering an obsolete question.

REVIA prevents this through **task identity + fence validation + controlled speech delivery**.

---

# ◈ What Makes REVIA Different

### 1. Full-duplex interaction

REVIA is designed for voice interaction where the user can speak while the assistant is speaking or working.

### 2. Task-aware interruption

Every request becomes an explicit task rather than an anonymous conversational turn.

### 3. Authoritative current task

The system maintains one authoritative active task for the current interaction.

### 4. Stale-result rejection

A result produced by an obsolete task is not allowed to become current merely because it completed later.

### 5. Controlled Rime delivery

Even after response generation, REVIA validates task/session authority before queueing speech.

### 6. Conversation continuity

Replacing an execution task does not automatically erase valid previous conversational context.

### 7. Frontend reflects backend authority

The browser visualizes task and voice state; it does not independently implement task correctness.

---

# ◈ Core Runtime Architecture

```text
                         ┌──────────────────────┐
                         │        USER          │
                         │ Microphone / Speech  │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       LiveKit        │
                         │ Realtime WebRTC Room │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    REVIA Agent       │
                         │ backend/voice_io     │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼──────────┐
                         │     Deepgram STT    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Session Context    │
                         │   + TaskManager      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    AgentBrain        │
                         │  LLM orchestration   │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼──────────┐
                         │ Optional delayed    │
                         │ demonstration work  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │  Fence Validation    │
                         │ Is task still valid? │
                         └───────┬───────┬──────┘
                                 │       │
                               YES       NO
                                 │       │
                                 ▼       ▼
                         ┌──────────┐  ┌──────────────┐
                         │ Response │  │ Stale result │
                         │ delivery │  │ rejected     │
                         └────┬─────┘  └──────────────┘
                              │
                              ▼
                         ┌──────────┐
                         │ Rime TTS │
                         └────┬─────┘
                              │
                              ▼
                         ┌──────────┐
                         │ LiveKit  │
                         │ Playback │
                         └────┬─────┘
                              │
                              ▼
                             USER
```

The browser connects to the same LiveKit session used by the REVIA agent. The frontend does not create a second STT/TTS pipeline.

---

# ◈ Voice Pipeline

The current end-to-end runtime path is:

```text
Microphone
    ↓
LiveKit AgentSession
    ↓
Deepgram STT
    ↓
REVIA Voice Agent
    ↓
AgentBrain / Session Context
    ↓
TaskManager
    ↓
Configured LLM provider
    ↓
Optional delayed_demo_work
    ↓
Task + Fence Validation
    ↓
Response Generation
    ↓
Rime TTS
    ↓
LiveKit Audio Playback
    ↓
Browser
```

Final transcripts are processed asynchronously so that a delayed workload does not prevent later LiveKit turns from being received.

---

# ◈ Task Authority and Fencing

Every user turn creates a task containing:

```text
task_id
fence_token
task status
```

The task lifecycle is:

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

Tasks may instead become:

```text
CANCELLED
OBSOLETE
FAILED
```

## Authority transition

Suppose Task A is active:

```text
Task A
ACTIVE
```

The user changes the request:

```text
Task A
OBSOLETE
   │
   └── fence invalidated

Task B
ACTIVE
```

Task B is now authoritative.

If Task A later returns:

```text
Task A result
     ↓
Fence validation
     ↓
Task A is obsolete
     ↓
REJECT
```

Therefore:

```text
Late result ≠ valid result
```

The stale result cannot become current speech.

---

# ◈ Interruption Handling

When new user speech is detected while REVIA is speaking:

```text
USER SPEAKS
     ↓
LiveKit detects user speech
     ↓
Active Rime playback interrupted
     ↓
Current task becomes obsolete
     ↓
Fence authority invalidated
     ↓
Final transcript arrives
     ↓
New task created
     ↓
New task becomes ACTIVE
     ↓
New response generated
     ↓
Rime speaks only the new valid response
```

The backend therefore treats interruption as an authority transition, not merely an audio-volume event.

The agent also checks session liveness before queuing speech so that responses are not submitted to a closed/closing `AgentSession`.

---

# ◈ Demonstration Scenario A — Interrupt While Speaking

```text
Task A
  ↓
REVIA SPEAKING
  ↓
USER INTERRUPTS
  ↓
Rime playback stops
  ↓
Task A → OBSOLETE / REPLACED
  ↓
Task B → ACTIVE
  ↓
Task B response generated
  ↓
Rime speaks Task B
```

### Expected result

The old response must not resume or continue as the authoritative response after the user has redirected the conversation.

---

# ◈ Demonstration Scenario B — Interrupt During Async Work

The repository contains a neutral delayed demonstration workload used to exercise task switching.

It is intentionally **not** presented as a production database, analytics service, or product data source.

```text
Task A
  ↓
TOOL_RUNNING
  ↓
USER CHANGES REQUEST
  ↓
Task A → OBSOLETE
  ↓
Task B → ACTIVE
  ↓
Task A finishes late
  ↓
Fence validation
  ↓
Task A → STALE / REJECTED
  ↓
Task A result is not spoken
  ↓
Task B remains authoritative
  ↓
Rime speaks Task B
```

This is the key correctness demonstration for the project.

---

# ◈ Conversation Continuity

Task authority and conversation context are separate concepts.

When an active task is replaced:

```text
Task A becomes obsolete
```

does **not** mean:

```text
All previous conversation is deleted
```

Valid user turns are retained in session order, while only validated assistant responses are committed.

Example:

```text
User:
"Tell me about Maharashtra."

User:
"Actually, only Pune."
```

The second request can use the established session context while becoming the new authoritative task.

An obsolete task cannot commit its assistant response.

---

# ◈ Rime Configuration

REVIA uses **Rime** as its spoken-output provider.

The current implementation is configured as:

| Parameter | Configuration |
|---|---|
| Model | `coda` |
| Speaker | `lyra` |
| Language | `eng` |
| Endpoint | `wss://users-ws.rime.ai/ws3` |
| Transport | WebSocket |
| Audio format | PCM |
| Sample rate | 16 kHz |
| Playback | LiveKit `AgentSession` |

The relevant implementation is:

```text
backend/rime/tts_rime.py
backend/rime/events.py
```

The Rime API key is server-side only.

No browser Web Speech API is required as an alternative spoken-output path.

---

# ◈ Frontend

The frontend is a React + TypeScript Vite application built around a voice-first workspace.

It is not a generic analytics dashboard.

## Main interface areas

### Voice Core

The central Three.js visualization communicates the current voice/task state.

States include:

```text
IDLE
LISTENING
THINKING
WORKING
SPEAKING
INTERRUPTED
TASK_REPLACED
STALE_REJECTED
```

The visual system is state-driven rather than simply decorative.

### Live Conversation

Displays the current conversation between:

```text
USER
REVIA
```

### Current Request / Authority

Shows which request currently has authority without requiring the user to inspect raw task IDs or fence tokens.

### Request Lineage

Provides a visual history of task transitions:

```text
Previous Request
      ↓
REPLACED / OBSOLETE
      ↓
Current Request
      ↓
ACTIVE
```

When observable backend events indicate stale rejection, the interface can show:

```text
IGNORED ✓
```

### Rime Status

The workspace exposes the active voice provider and configured identity at the product level:

```text
RIME
Coda · Lyra
```

### Voice Identity Controls

The current frontend also includes controls and UI infrastructure for voice identity/presentation.

These controls are kept separate from the core task-authority mechanism.

### Transcript Export

The frontend contains a PDF transcript/dossier export utility for the conversation workspace.

---

# ◈ Frontend / Backend Responsibility Boundary

## Frontend owns

- visual UI;
- browser microphone interaction;
- LiveKit browser connection;
- connection/reconnection UX;
- transcript presentation;
- voice-state animation;
- current activity display;
- request lineage visualization;
- user-facing error states;
- responsive behavior;
- transcript/dossier presentation and export.

## Backend owns

- LiveKit agent runtime;
- Deepgram STT;
- conversation context;
- TaskManager;
- task lifecycle;
- task IDs;
- fence tokens;
- interruption correctness;
- asynchronous tool execution;
- stale-result rejection;
- LLM orchestration;
- response validation;
- controlled spoken-text delivery;
- Rime TTS;
- server-side credentials;
- backend evaluation and instrumentation.

### Critical rule

> **The frontend displays backend authority; the frontend does not become the authority.**

---

# ◈ Token and Security Architecture

The browser must never receive provider secrets.

The session authorization path is:

```text
Browser
   │
   │ GET /token?room=<room>&identity=<user>
   ▼
FastAPI Token Server
   │
   │ LIVEKIT_API_KEY
   │ LIVEKIT_API_SECRET
   ▼
Short-lived LiveKit JWT
   │
   ▼
Browser
   │
   ▼
LiveKit Room
```

The token server is implemented in:

```text
token_server.py
```

## Secrets that must remain server-side

```text
LIVEKIT_API_SECRET
RIME_API_KEY
DEEPGRAM_API_KEY
GROQ_API_KEY
GEMINI_API_KEY
any other provider secret
```

Never place these in:

```text
frontend/.env
VITE_* variables
JavaScript bundles
README files
screenshots
demo recordings
```

Only public/non-secret frontend configuration belongs in Vite environment variables.

---

# ◈ Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript |
| Build tool | Vite |
| Browser realtime client | `livekit-client` |
| Realtime transport | LiveKit |
| Voice agent runtime | LiveKit Agents |
| STT | Deepgram |
| Primary/fallback LLM orchestration | Configured Gemini / Groq providers |
| TTS | Rime |
| Backend API | FastAPI |
| ASGI server | Uvicorn |
| Async runtime | Python `asyncio` |
| Task correctness | TaskManager + fencing |
| 3D visualization | Three.js / WebGL |
| Styling | Vanilla CSS / design-token system |
| Export | PDF transcript/dossier utility |

---

# ◈ Repository Structure

```text
dataforge-new2/
│
├── backend/
│   ├── evaluation/
│   │   └── test_voice_identity.py
│   │
│   ├── orchestration/
│   │   ├── agent_brain.py
│   │   ├── tool_contract.py
│   │   └── stub_tool_client.py
│   │
│   ├── rime/
│   │   ├── events.py
│   │   └── tts_rime.py
│   │
│   ├── state/
│   │   ├── task_manager.py
│   │   └── fencing.py
│   │
│   ├── tools/
│   │   └── delayed demonstration/tool infrastructure
│   │
│   └── voice_io/
│       ├── agent.py
│       ├── rime_voice_client.py
│       └── stt_deepgram.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── VoiceCore/
│   │   │   ├── LandingPage.tsx
│   │   │   ├── VoiceWorkspace.tsx
│   │   │   ├── DossierHeader.tsx
│   │   │   ├── RequestAuthority.tsx
│   │   │   ├── RequestLineage.tsx
│   │   │   ├── AmbientWaveform.tsx
│   │   │   ├── MicInstrument.tsx
│   │   │   └── VoiceIdentityControls.tsx
│   │   │
│   │   ├── hooks/
│   │   ├── state/
│   │   │   ├── livekitSession.ts
│   │   │   ├── workspaceState.tsx
│   │   │   └── workspaceTypes.ts
│   │   │
│   │   ├── utils/
│   │   │   ├── exportTranscriptPdf.ts
│   │   │   └── theme.ts
│   │   │
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── styles.css
│   │
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.ts
│
├── token_server.py
├── quick_integration_check.py
├── run_real_scenario.py
├── requirements.txt
│
├── CONTRACTS.md
├── FLOW_README.md
├── MASTER_README.md
├── PROGRESS.md
├── RIME_EVIDENCE.md
└── .env.example
```

---

# ◈ Prerequisites

Install:

- Python 3.10+
- Node.js 18+
- npm
- a LiveKit project
- Deepgram credentials
- Rime credentials
- configured LLM provider credentials

For realtime browser use, the application also requires:

- browser microphone permission;
- network access to LiveKit;
- a running REVIA agent;
- a running token server.

---

# ◈ Environment Configuration

Create a local `.env` from `.env.example`.

A representative configuration is:

```env
# LiveKit
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# Speech
DEEPGRAM_API_KEY=your_deepgram_api_key
RIME_API_KEY=your_rime_api_key

# LLM
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key

# Provider selection
LLM_PROVIDER=gemini
LLM_FALLBACK_PROVIDER=groq
```

Do not commit the actual `.env`.

For the browser, only non-secret variables should be exposed, for example:

```env
VITE_TOKEN_SERVER_URL=http://localhost:7880
VITE_LIVEKIT_ROOM=revia-room
```

---

# ◈ Quick Start

REVIA locally consists of three main processes:

```text
1. Token Server
2. REVIA LiveKit Agent
3. React Frontend
```

## 1. Clone

```bash
git clone <repository-url>
cd dataforge-new2
```

## 2. Backend environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` from `.env.example` and configure the required credentials.

## 3. Start token server

From the repository root:

```bash
uvicorn token_server:app --port 7880 --reload
```

Check health:

```bash
curl http://localhost:7880/health
```

Token endpoint:

```text
GET /token?room=revia-room&identity=<identity>
```

## 4. Start REVIA agent

The LiveKit agent entrypoint is:

```text
backend/voice_io/agent.py
```

Use the repository's configured LiveKit/Python agent startup command for this entrypoint.

## 5. Start frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown by the terminal, normally:

```text
http://localhost:5173
```

The browser obtains a short-lived LiveKit token from the token server and then joins the configured room.

---

# ◈ Production Deployment Architecture

A typical public deployment separates the browser application, token service, and realtime agent:

```text
                     INTERNET
                        │
                        ▼
              ┌─────────────────┐
              │  Vercel / CDN   │
              │ React Frontend  │
              └────────┬────────┘
                       │ HTTPS
                       ▼
              ┌─────────────────┐
              │ Token Server    │
              │ FastAPI         │
              └────────┬────────┘
                       │
                       │ JWT
                       ▼
              ┌─────────────────┐
              │  LiveKit Cloud  │
              │ Realtime Room   │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ REVIA Agent     │
              │ LiveKit Worker  │
              └──────┬───┬──────┘
                     │   │
             ┌───────┘   └────────┐
             ▼                    ▼
        Deepgram                 Rime
             │                    │
             └────────┬───────────┘
                      ▼
                LLM Providers
```

The token server and agent must have access to their required secrets. The frontend does not.

---

# ◈ Testing and Verification

## Integration check

```bash
python3 quick_integration_check.py
```

## Real scenario runner

```bash
python3 run_real_scenario.py
```

## Evaluation tests

```bash
pytest
```

## Frontend build

```bash
cd frontend
npm install
npm run build
```

A successful frontend build should complete without TypeScript/Vite build errors.

---

# ◈ What Should Be Verified

## Normal voice flow

```text
Browser connected
    ↓
Microphone enabled
    ↓
User speaks
    ↓
Deepgram transcript
    ↓
REVIA processes request
    ↓
Response generated
    ↓
Rime synthesizes speech
    ↓
LiveKit delivers audio
    ↓
Browser plays response
```

## Multi-turn continuity

Verify:

```text
"Tell me about Maharashtra."
        ↓
"Actually, only Pune."
```

Expected:

- context is preserved;
- the second request is understood relative to the first;
- the second task becomes authoritative;
- the current answer is the one delivered through Rime.

## Speaking interruption

Verify:

- user can speak while REVIA is speaking;
- previous speech stops;
- previous task loses authority;
- new task becomes active;
- new response is the one spoken.

## Delayed-work interruption

Verify:

- Task A enters asynchronous work;
- user changes the request;
- Task A becomes obsolete;
- Task B becomes active;
- Task A may finish later;
- Task A fails task/fence validation;
- Task A is not spoken as the current response;
- Task B remains authoritative.

---

# ◈ Evidence Discipline

REVIA distinguishes between:

### Deterministically testable behavior

Examples:

- task lifecycle transitions;
- task/fence validation;
- stale-result rejection;
- conversation context behavior;
- Rime integration logic;
- speech lifecycle handling;
- session teardown handling.

### Live integration behavior

Examples:

- actual browser microphone flow;
- LiveKit room connection;
- real Deepgram transcription;
- real Rime audio playback;
- end-to-end interruption timing;
- live delayed-tool interruption sequence.

A behavior should only be described as **live verified** when it has actually been observed in the corresponding integration/evidence run.

Do not infer live behavior merely from the existence of code or unit tests.

---

# ◈ Known Limitations

1. **The delayed workload is demonstration infrastructure.** It is intentionally generic and exists to exercise interruption/fencing behavior rather than represent a production data service.

2. **Physical cancellation is not assumed.** A background operation may finish after its task becomes obsolete. Correctness is maintained by rejecting the stale result.

3. **Provider/network availability can affect realtime behavior.** LiveKit, Deepgram, LLM providers, Rime, browser permissions, and network conditions are external dependencies.

4. **Session-scoped context.** REVIA maintains conversational continuity within the active session; this is not presented as permanent cross-session memory.

5. **No unsupported latency claim.** Specific interruption or end-to-end latency figures should only be reported when measured in an evidence run.

6. **Frontend state is observational.** The frontend should not be treated as the source of truth for task authority.

7. **Live integration status must be evaluated separately from deterministic tests.** The repository documents the intended and implemented architecture, but the final evidence should report exactly what was observed.

---

# ◈ Security Checklist

Before committing or submitting:

```text
[ ] .env is ignored
[ ] .env.local is ignored
[ ] frontend/dist is ignored
[ ] node_modules is ignored
[ ] __pycache__ is ignored
[ ] no API secret is in frontend code
[ ] no API secret is in Vite variables
[ ] no LiveKit API secret is exposed to the browser
[ ] no Rime API key is exposed to the browser
[ ] no Deepgram API key is exposed to the browser
[ ] no LLM provider secret is exposed to the browser
```

The repository's `.gitignore` should remain responsible for preventing local credentials and generated frontend artifacts from entering version control.

---

# ◈ Submission Checklist

The challenge submission requires the working repository plus documentation/evidence.

Ensure the repository contains:

```text
README.md
RIME_EVIDENCE.md
CONTRACTS.md
FLOW_README.md
PROGRESS.md
.env.example
backend/
frontend/
token_server.py
requirements.txt
```

The recorded demo should demonstrate:

1. the target user/problem;
2. the normal end-to-end voice flow;
3. the selected hard voice problem;
4. a deliberate stress/failure case;
5. the observed result/measurement;
6. which speech provider is active.

The evidence document should contain:

- hard voice claim;
- acceptance test;
- procedure;
- observed result;
- limitations;
- repeatable command/script/fixture where practical.

---

# ◈ Final Product Statement

REVIA is not primarily a chatbot, analytics dashboard, or TTS wrapper.

Its core problem is:

> **Reliable Full-Duplex Task Switching.**

The system is designed so that:

```text
User can interrupt
        ↓
Current task loses authority
        ↓
New task becomes authoritative
        ↓
Old asynchronous work may finish
        ↓
Old result is fenced
        ↓
Old result cannot become current speech
        ↓
New response is delivered
```

That is the core of REVIA:

> **Talk while REVIA talks. Redirect while REVIA works.**

> **Interruptible by Design. Correct by Construction.**
