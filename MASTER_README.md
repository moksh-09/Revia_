# REVIA — Master README

Realtime voice-native data analyst. Built for **DataForge 2026 — Rime Hackathon Challenge**.

This is the single source of truth for this repo. Every human and every AI
coding agent (Claude Code, Cursor, etc.) working on this project MUST read
this file, in the order given in Section 0, before writing or editing any code.

This file does not get copy-pasted between machines. It lives in the git repo.
Every person clones the same repo and reads it from their own local copy.

---

## 0. Boot Sequence — read this first, every session

Any agent or person starting or resuming work on this repo does the following,
in order, before touching any code:

1. Read this file (`MASTER_README.md`) in full.
2. Read `CONTRACTS.md` in full. This file is **frozen**. Never edit it. If your
   work requires a change to it, stop and report the needed change to the
   team — do not edit it yourself, and do not work around it silently.
3. Read `PROGRESS.md` in full. This tells you what is actually done (with
   evidence) versus merely planned. A step is only "done" if it has an
   evidence line in `PROGRESS.md` — a mention in this README is not
   completion.
4. Find your own section under Section 10 ("Per-Person Instructions") by name
   or role. Read only that section closely — you do not need to memorize the
   other three people's sections.
5. Check `PROGRESS.md` for whether your upstream dependency (see your
   section's "Depends on" line) is marked done with evidence.
   - If yes: build and test against the real upstream module.
   - If no: build and test against the **stub** defined for that interface in
     `CONTRACTS.md`. Do not wait idle for someone else to finish.
6. Work only inside your own owned directory (see Section 9, Repo Structure).
   Never create, edit, or delete files outside it, and never edit
   `MASTER_README.md`, `CONTRACTS.md`, or another person's directory.
7. When you complete and verify a step, append one line to `PROGRESS.md`
   (format in Section 8) and, if it relates to the hard voice claim, update
   `RIME_EVIDENCE.md` (format in Section 7). Do not batch this for later —
   log it the moment it is proven, not before.

**Hard rule, non-negotiable:** never let an obsolete, cancelled, or failed
task produce speech or update state. This is the single rule the whole
project exists to prove. If a shortcut or feature request conflicts with it,
stop and prioritize this rule over the feature.

---

## 1. Project

REVIA is a voice agent that answers spoken questions about structured sales
data, using Rime for all substantive spoken output. The user talks, the
system analyzes data, Rime speaks the answer back — in realtime, and
correctly even when interrupted or when a request changes mid-computation.

## 2. The One Hard Voice Problem (do not split this into two problems)

> How does a realtime voice agent stay conversationally correct — never
> speaking or acting on a stale or wrong result — when the user interrupts it
> at any point in the pipeline: while it is speaking, or while a background
> tool/data operation is still running?

This is **one mechanism** (task IDs + fencing + stale-result rejection),
proven with **two stress scenarios**:

- **Scenario A — Interrupt while speaking.** User interrupts mid-answer.
  Queued Rime audio stops immediately, the task is invalidated, a new task
  takes over.
- **Scenario B — Interrupt during tool execution.** User interrupts (or
  changes their request) while a background analytics/tool call is still in
  flight. The stale result must never update state and must never be spoken,
  even if the tool call cannot be physically cancelled.

Never describe this in the demo, README, or evidence file as "two problems"
or "problem 2 and problem 3." It is one claim, two demonstrations of the same
mechanism. This framing is deliberate — see Section 2 rationale below.

**Why this pair, briefly:** it is the only failure mode on the hackathon's
problem list that cannot be demonstrated in text at all (a typed message is
already final the instant it's sent — nothing to interrupt, nothing stale to
reject), it maps to the two heaviest judging criteria (problem necessity 25%,
hard voice engineering 25%), and both scenarios are solved by one shared
mechanism rather than two separate builds.

## 3. Target User

An analyst or manager who wants quick spoken answers about sales data —
hands-busy, asking natural follow-up questions, and prone to correcting or
narrowing their own request mid-conversation the way people actually talk.

## 4. Why Voice Is Necessary

The failure mode under test — interruption, mid-sentence correction, changing
your mind — only exists in a spoken, interruptible conversation. A text chat
box does not expose this problem: typed messages are already final by the
time they're sent, so there is nothing to interrupt and nothing stale to
reject. Removing voice would remove the problem itself, not just the
interface.

## 5. Core USP

**Task-aware interruption recovery + stale-result protection.**

- Every user request gets a `task_id`.
- Only the currently active task may affect conversation state or speak
  through Rime.
- On interruption: old speech stops, the old task becomes
  obsolete/cancelled, background work is cancelled where possible —
  otherwise its result is fenced off and rejected.
- Stale results can never update active state and can never be spoken.
- The newest valid request becomes the active task; Rime speaks only its
  answer.
- **Rime's role:** Rime is the primary and only judged spoken output. Every
  substantive answer, including every stress-test result, is spoken by Rime —
  never a confirmation beep, never optional playback.

## 6. Architecture

```
USER
 |
 v
Browser Microphone
 |
 v
LiveKit Realtime Transport
 |
 v
STT
 |
 v
Voice Agent
 |
 v
Task / State Manager
 |
 v
Interruption Manager
 |
 v
LLM + Deterministic Analytics Tools
 |
 v
Response Validation
 |
 v
Rime TTS
 |
 v
Realtime Audio -> USER

(parallel)
Voice + Task Events -> Evaluation Engine -> Metrics Store -> Reliability Dashboard
```

| Component | Responsibility | Owner |
|---|---|---|
| Browser Microphone | Captures raw user audio | vedantk |
| LiveKit Realtime Transport | Media session, turn signaling, low-level VAD | vedantk |
| STT | Converts user audio to text | vedantk |
| Rime TTS | Synthesizes the primary spoken output | vedantk |
| Task / State Manager | Issues `task_id`s, owns the single source of truth for the active task | vedantkhar |
| Interruption Manager | Detects interruption, triggers audio stop, signals task invalidation | vedantkhar |
| Fencing / Response Validation | Confirms a result belongs to the still-active task/fence before it can proceed | vedantkhar |
| Analytics Tools | Deterministic sales-data functions the agent can call | moksh |
| LLM + Orchestration | Chooses and calls tools, drafts the answer, wires voice+state+tools together | shlok |
| Evaluation Engine / Metrics / Evidence | Stress-test scenarios, real measurements, RIME_EVIDENCE.md generation | shlok |
| Voice UI / Timeline / Dashboard UI | User-facing surfaces — **Phase 2, deferred until backend is integrated** | shlok (later) |

**Phasing note:** Frontend work is intentionally deferred. All 4 people work
on backend only until an integrator (see Section 10) merges working backend
branches into `main`. Only then does frontend building start, against the
real running backend rather than stubs.

**Interruption is not a sequential pipeline stage.** It is a parallel
control/event path that can preempt the pipeline above at any point — during
tool execution, during generation, or during speech. See `CONTRACTS.md` for
the exact event schema this requires.

## 7. RIME_EVIDENCE.md — how it gets updated

`RIME_EVIDENCE.md` lives at the repo root. It is **not** written once at the
end. Update it incrementally, the moment each piece becomes true and
provable:

- As soon as the Rime model/voice/language/endpoint/format/transport is
  finalized -> fill Section 3 (Rime configuration) immediately.
- As soon as Scenario A (interrupt-while-speaking) passes with a real
  recorded run -> fill Sections 4–7 for that scenario.
- As soon as Scenario B (interrupt-during-tool) passes -> extend Sections
  4–7 with that scenario's evidence.
- As soon as a limitation is discovered (e.g. tool cancellation not
  supported for a given tool type) -> add it to Section 10 immediately, not
  at the end.

Never write a result into this file that has not actually been run and
observed. No estimated numbers, no "should work" claims.

## 8. PROGRESS.md — how it gets updated

`PROGRESS.md` is **append-only**. Nobody edits or deletes another person's
line. Add a new line at the bottom when, and only when, a step is complete
and verified (test passed, output observed). Format:

```
[YYYY-MM-DD HH:MM] [name] [Section/Step ref] DONE — <one-line evidence: test name, command run, or output observed>
```

Example:

```
[2026-09-10 14:20] [vedantkhar] [State machine transitions] DONE — pytest backend/state/test_transitions.py, 14/14 passed
[2026-09-10 16:05] [vedantk] [Rime config locked] DONE — model=coda, voice=lyra, endpoint=wss://users-ws.rime.ai/ws3, see .env.example
```

If a step is blocked, log that too, so others know not to depend on it yet:

```
[2026-09-10 17:00] [moksh] [Tool cancellation] BLOCKED — cancellation not supported by pandas query in progress; fencing implemented as fallback per CONTRACTS.md Section 4
```

## 9. Repo Structure

```
revia/
├── MASTER_README.md      <- this file. Architecture + workflow. Edited only by team agreement.
├── CONTRACTS.md          <- frozen interface schemas. Never edited solo.
├── PROGRESS.md           <- append-only step log with evidence.
├── RIME_EVIDENCE.md      <- hard voice claim + real test evidence, updated incrementally.
├── .env.example          <- placeholders only. Real .env is never committed.
├── backend/
│   ├── voice_io/         <- vedantk only. Mic capture, LiveKit transport, STT wiring.
│   ├── rime/             <- vedantk only. Rime TTS integration, interruption detection, audio streaming out.
│   ├── state/            <- vedantkhar only. Task Manager, state machine, fencing, interruption manager.
│   ├── tools/            <- moksh only. Analytics functions, sales dataset access.
│   └── orchestration/    <- shlok only. LLM wiring, agent brain, ties voice+state+tools together.
│   └── evaluation/       <- shlok only. Stress-test scenarios, metrics, evidence generation scripts.
└── frontend/             <- untouched until Phase 2 (see Section 10, shlok's Phase 2 note). Owner: shlok.
```

**Phase 1 = backend only.** All 4 people work inside `backend/` in parallel.
`frontend/` stays empty until an integrator (see below) merges working
backend branches into `main` and hands off real, running behavior to build
the UI against — no one builds frontend against guesses.

**Ownership rule:** a person only ever creates, edits, or deletes files inside
their own directory. Any change to a root-level file (`MASTER_README.md`,
`CONTRACTS.md`) requires the whole team's agreement — no exceptions, no "just
a quick fix."

**Branches:** `main`, `vedantk`, `vedantkhar`, `moksh`, `shlok` — one branch
per person, named after them directly. Nobody commits to `main` directly;
`main` only receives merges at integration checkpoints (Section 11).

## 10. Per-Person Instructions

Each subsection below is what that person's coding agent (Cursor, Antigravity,
Codex, etc.) works from — paste the "Starter prompt" for your name directly
into your agent to begin. Read only your own subsection closely.

### vedantk — Realtime Voice + Rime
**Owns:** `backend/voice_io/`, `backend/rime/`
**Branch:** `vedantk`
**Depends on:** the `Task`/event schema in `CONTRACTS.md` Section 2 (from
vedantkhar). Not built yet -> code against the stub in `CONTRACTS.md`
Section 5. Fully parallel — no need to wait for anyone.
**Build, in order:**
1. Mic capture -> LiveKit transport -> Deepgram STT -> plain text output. Log to `PROGRESS.md` when a spoken sentence reliably becomes text.
2. Wire STT output into the stubbed Task Manager interface from `CONTRACTS.md` Section 5. Log when a `task_id` is correctly requested for each utterance.
3. Rime TTS integration using the locked config in `CONTRACTS.md` Section 6 (model=coda, voice=lyra, endpoint=wss://users-ws.rime.ai/ws3, pcm@16000, use_websocket=True).
4. Playback of Rime's streamed audio back into the LiveKit room.
5. Interruption detection: on new user speech while Rime is speaking, emit the `interrupt` event exactly per `CONTRACTS.md` Section 2/3, and stop local playback immediately.
6. Emit `speech.started` / `speech.stopped` events with `task_id` + `speech_id` per `CONTRACTS.md` Section 2.
**Never:** invent a different event schema; commit any credential anywhere (code, docs, screenshots, recordings).

**Starter prompt:**
```
Read MASTER_README.md, CONTRACTS.md, and PROGRESS.md in this repo fully before writing any code.

Follow the Boot Sequence in MASTER_README.md Section 0. I am vedantk — work only inside backend/voice_io/ and backend/rime/. Never edit MASTER_README.md, CONTRACTS.md, or any other person's directory.

My dependency (the real Task Manager in backend/state/, owned by vedantkhar) is not built yet. Build backend/voice_io/stub_task_client.py implementing the exact Stub Task Manager behavior described in CONTRACTS.md Section 5, and use that stub for now.

Build in this exact order, one file at a time, and stop after each step so I can review before you continue:

1. backend/voice_io/agent.py + backend/voice_io/stt_deepgram.py — a LiveKit Agents entrypoint that joins a room, captures microphone audio, sends it to Deepgram STT, and prints the transcribed text to console. Read credentials from .env (LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, DEEPGRAM_API_KEY) using python-dotenv. Never hardcode a key.

2. backend/voice_io/stub_task_client.py — implement the Stub Task Manager exactly per CONTRACTS.md Section 5. Wire step 1's transcribed output into it so each utterance requests a task_id.

3. backend/rime/tts_rime.py — integrate Rime TTS using the exact locked configuration in CONTRACTS.md Section 6 (model=coda, speaker=lyra, endpoint=wss://users-ws.rime.ai/ws3, audio_format=pcm sample_rate=16000, use_websocket=True). Read RIME_API_KEY from .env.

4. Extend backend/rime/tts_rime.py to stream the synthesized audio back into the LiveKit room for playback.

5. backend/rime/events.py — detect when the user starts speaking while Rime audio is still playing, and emit an `interrupt` event exactly matching CONTRACTS.md Section 2. Stop local playback immediately when this fires.

6. Extend backend/rime/events.py to emit `speech.started` and `speech.stopped` events (with task_id and speech_id) per CONTRACTS.md Section 2.

After each step is working and I've verified it, append one line to PROGRESS.md using my name "vedantk" in the exact format that file specifies. Never mark anything DONE without me confirming it actually ran. Never touch files outside backend/voice_io/ and backend/rime/.
```

### vedantkhar — State + Fencing (build/freeze this interface first)
**Owns:** `backend/state/`
**Branch:** `vedantkhar`
**Depends on:** nothing upstream for the interface itself — this module's
contract is what everyone else builds against. Fully parallel — start
immediately, do not wait.
**Build, in order:**
1. Task object + state machine (`CREATED -> ACTIVE -> TOOL_RUNNING -> GENERATING -> SPEAKING -> COMPLETED`, plus `CANCELLED`/`OBSOLETE`/`FAILED` as terminal states). Log when all transitions have passing tests.
2. Interruption handling: on receiving an `interrupt` event (from vedantk) at any non-terminal state, move the current task to `CANCELLED`/`OBSOLETE`, create a new task, mark it `ACTIVE`.
3. Fencing: every async result (from moksh's tools or shlok's LLM) carries a `task_id` + `fence_token`. Implement the check that rejects any result whose task is not the currently active one — regardless of whether tool cancellation succeeded.
4. Response validation gate: a generated response may only proceed to Rime if its task is still active at the moment of the check.
5. Emit the full event timeline (task created/active/obsolete/cancelled/completed, with timestamps) for shlok's evaluation and future dashboard work.
**Never:** let any component other than this module write `status`; assume tool cancellation succeeded — always fence regardless.

**Starter prompt:**
```
Read MASTER_README.md, CONTRACTS.md, and PROGRESS.md in this repo fully before writing any code.

Follow the Boot Sequence in MASTER_README.md Section 0. I am vedantkhar — work only inside backend/state/. Never edit MASTER_README.md, CONTRACTS.md, or any other person's directory.

My module is the interface everyone else builds against — CONTRACTS.md Section 1 (Task schema), Section 2 (events), Section 3 (interruption flow), Section 4 (tool contract) describe exactly what I must implement. Build stub_voice_client.py and stub_tool_client.py matching CONTRACTS.md Section 5 so I can test against fake upstream/downstream modules until vedantk and moksh's real code exists.

Build in this exact order, stopping after each step for my review:

1. backend/state/task.py — the Task object exactly per CONTRACTS.md Section 1. Only this module may ever write `status`.

2. backend/state/state_machine.py — implement all transitions: CREATED -> ACTIVE -> TOOL_RUNNING -> GENERATING -> SPEAKING -> COMPLETED, plus CANCELLED/OBSOLETE/FAILED as terminal states that can never re-enter a non-terminal state. Write tests for every transition.

3. backend/state/interruption_manager.py — on receiving an `interrupt` event (per CONTRACTS.md Section 2/3) at any non-terminal state, move the current task to CANCELLED or OBSOLETE, invalidate its fence_token, create a new task, mark it ACTIVE.

4. backend/state/fencing.py — the check that rejects any `tool.result` whose fence_token doesn't match the currently active task's fence_token, regardless of whether tool cancellation succeeded. This is the single most important correctness rule in the whole project — never assume cancellation worked.

5. backend/state/events.py — emit the full event timeline (task.created, task.active, task.tool_running, task.speaking, task.completed, task.cancelled, task.obsolete) exactly per CONTRACTS.md Section 2.

After each step is working and I've verified it, append one line to PROGRESS.md using my name "vedantkhar" in the exact format that file specifies. Never mark anything DONE without me confirming it actually ran and passed. Never let any module other than this one write task status. Never touch files outside backend/state/.
```

### moksh — Data + Analytics Tools
**Owns:** `backend/tools/`
**Branch:** `moksh`
**Depends on:** the tool-call and fencing contract in `CONTRACTS.md`
Section 4 (from vedantkhar). Not built yet -> code against the stub in
`CONTRACTS.md` Section 5. Fully parallel.
**Build, in order:**
1. Sales dataset + deterministic analytics functions (the actual queries REVIA can answer). Use synthetic data only — never real customer/financial data.
2. Wire each analytics call to carry the `task_id`/`fence_token` per `CONTRACTS.md` Section 4 so vedantkhar's fencing can reject stale results.
3. A configurable artificial delay parameter on tool calls, so Scenario B (interrupt during tool execution) is reliably reproducible on demand.
**Never:** fabricate or estimate a result; make an analytics function non-deterministic — same input must always give the same output, since this is what gets fenced and tested.

**Starter prompt:**
```
Read MASTER_README.md, CONTRACTS.md, and PROGRESS.md in this repo fully before writing any code.

Follow the Boot Sequence in MASTER_README.md Section 0. I am moksh — work only inside backend/tools/. Never edit MASTER_README.md, CONTRACTS.md, or any other person's directory.

My dependency (the real fencing/Task Manager in backend/state/, owned by vedantkhar) may not be built yet. Build a stub_task_client.py implementing the Stub Task Manager from CONTRACTS.md Section 5 so I can develop and test independently.

Build in this exact order, stopping after each step for my review:

1. backend/tools/dataset.py — load/prepare a realistic synthetic sales dataset. Never use real customer/financial data, per MASTER_README.md Section 17's "Design for real use" rule.

2. backend/tools/analytics.py — deterministic analytics functions the voice agent can call (e.g. total sales by region, top products, trend over time). Every function must be deterministic — same input always gives same output.

3. backend/tools/tool_client.py — wrap every analytics call with the exact request/response contract in CONTRACTS.md Section 4 (task_id, fence_token, tool_name, args in; task_id, fence_token, tool_name, result, error out). Add a configurable artificial delay parameter so race conditions are reliably reproducible for stress testing.

After each step is working and I've verified it, append one line to PROGRESS.md using my name "moksh" in the exact format that file specifies. Never mark anything DONE without me confirming it actually ran. Never touch files outside backend/tools/.
```

### shlok — Orchestration + Evaluation (then Frontend, Phase 2)
**Owns (Phase 1):** `backend/orchestration/`, `backend/evaluation/`
**Owns (Phase 2, later):** `frontend/`
**Branch:** `shlok`
**Depends on:** all three other modules to actually integrate and test end
to end. This role is **partially sequential** — the orchestration skeleton
and evaluation scripts can be built against the Section 5 stubs in parallel
with everyone else starting Day 1, but real, meaningful stress-test runs
require vedantk, vedantkhar, and moksh's real modules to exist. Expect to
do the most real testing work from Day 2 onward, once real pieces land.
**Build, in order (Phase 1 — backend):**
1. `backend/orchestration/agent_brain.py` — the LLM layer (Groq) that decides which analytics tool to call and drafts the spoken answer text, wired against the stubs from `CONTRACTS.md` Section 5 initially.
2. `backend/evaluation/scenarios.py` — Scenario A (interrupt while Rime is speaking) and Scenario B (interrupt during a delayed tool call), as reproducible scripted tests, matching Section 2's definition exactly. Never treat these as two separate problems — one mechanism, two demonstrations.
3. `backend/evaluation/metrics.py` — real, measured metrics only: interruption count, stale-result rejection rate, time-to-first-audio, recovery time. Never fabricate or estimate.
4. `backend/evaluation/evidence_generator.py` — a script that runs the scenarios and outputs a PASS/FAIL checklist matching `RIME_EVIDENCE.md` Section 4's format.
5. Once vedantk, vedantkhar, and moksh have real working modules merged into `main` (see Section 11), re-point `agent_brain.py` and the evaluation scripts at the real modules instead of stubs, and re-run everything for real evidence.
**Phase 2 (later, after backend integration):** build `frontend/` — voice UI,
timeline view, reliability dashboard, stress-test control panel — against
the real running backend, using the Phase 2 prompt the integrator provides
once `main` has a working backend.
**Never:** fabricate or mock data to make evaluation output look complete;
treat a stub-based test result as real evidence for `RIME_EVIDENCE.md`.

**Starter prompt (Phase 1):**
```
Read MASTER_README.md, CONTRACTS.md, and PROGRESS.md in this repo fully before writing any code.

Follow the Boot Sequence in MASTER_README.md Section 0. I am shlok — work only inside backend/orchestration/ and backend/evaluation/ for now (frontend/ comes later, Phase 2, once backend is integrated). Never edit MASTER_README.md, CONTRACTS.md, or any other person's directory.

My work depends on all three other modules (voice/vedantk, state/vedantkhar, tools/moksh) to fully integrate, but I can start now against the stubs in CONTRACTS.md Section 5. Build stub_voice_client.py, stub_task_client.py, and stub_tool_client.py matching Section 5 so I can build and test in isolation until real modules land.

Build in this exact order, stopping after each step for my review:

1. backend/orchestration/agent_brain.py — an LLM layer using Groq that takes a transcribed request, decides which analytics tool to call (against the stub for now), and drafts a spoken-answer text response.

2. backend/evaluation/scenarios.py — implement Scenario A (interrupt while Rime is speaking) and Scenario B (interrupt during a delayed tool call) as reproducible, scripted test scenarios, matching MASTER_README.md Section 2's definition exactly. Treat this as one mechanism with two demonstrations, never as two separate problems.

3. backend/evaluation/metrics.py — real, measured metrics only: interruption count, stale-result rejection rate, time-to-first-audio, recovery time. Never fabricate or estimate a value, even against the stubs — mark stub-based numbers clearly as "stub test, not real evidence."

4. backend/evaluation/evidence_generator.py — a script that runs the scenarios and outputs a PASS/FAIL checklist matching RIME_EVIDENCE.md Section 4's format.

After each step is working and I've verified it, append one line to PROGRESS.md using my name "shlok" in the exact format that file specifies, and note clearly if a result came from stubs rather than real modules. Never touch files outside backend/orchestration/ and backend/evaluation/.
```

**Phase 2 prompt for shlok (do not use until the integrator says the backend is merged into `main` and working):**
```
Read MASTER_README.md and CONTRACTS.md in this repo fully before writing any code.

Do NOT build against the stub interfaces in CONTRACTS.md Section 5 — the real backend is now merged into main and working. Pull the latest main and build directly against the real, running modules.

Work only inside frontend/. Never edit MASTER_README.md, CONTRACTS.md, backend/, or PROGRESS.md's existing entries — only append your own new lines.

Before writing any UI code, first read through the actual backend code in backend/state/events.py and backend/rime/events.py to see the real event names and payload shapes, and how to actually connect to them — do not assume CONTRACTS.md's stub shapes are unchanged if the real code differs; ask the integrator if anything is unclear.

Build in this exact order, stopping after each step for review:

1. A voice UI: mic control, live conversation transcript, an indicator showing which task_id is currently active and its state — wired to the real event stream.

2. A timeline view rendering the actual task-state event stream (task.created/active/tool_running/speaking/obsolete/cancelled/completed) as it really comes from the backend.

3. A reliability dashboard rendering the real live metrics from backend/evaluation/metrics.py.

4. A stress-test control panel: buttons to trigger Scenario A and Scenario B for real against the live backend, for the demo recording.

After each step is working and verified against the real backend, append one line to PROGRESS.md as "shlok" in the exact format specified. Never fabricate or mock data to make the UI look done — if a backend piece isn't ready when you reach it, stop and report rather than faking it.
```

## 11. Integration Checkpoints & The Integrator Role

**vedantk acts as integrator** for Phase 1 (this can be reassigned by team
agreement, but must be exactly one person, decided before Day 1 ends, so
merges don't collide).

- **End of Day 2:** integrator pulls `vedantk`, `vedantkhar`, `moksh` into
  `main`. Confirm: mic-to-Rime loop works end to end, and a basic interrupt
  stops speech (Scenario A only, rough). Resolve conflicts — should be
  minimal since everyone stayed inside their own folder.
- **End of Day 3:** re-integrate the same three branches. Confirm: fencing
  correctly rejects a stale tool result (Scenario B), full state timeline
  recorded. shlok's real (non-stub) evaluation runs against this merged
  `main` from this point forward.
- **Day 4:** integrator confirms `main` has a real, working backend, then
  tells shlok to start Phase 2 (frontend) using the Phase 2 prompt above,
  pulling from `main` directly — not from stubs.
- **Day 5:** integrator merges `shlok`'s frontend branch into `main`. Freeze.
  No new features. Final integration check, README/evidence completeness
  pass, demo recording, credential/secret check.

**Before merging anyone's branch, the integrator checks `PROGRESS.md` for
that person's DONE entries with real evidence** — not just "looks
finished." No evidence-backed entries for a claimed feature means test it
yourself before merging, don't trust it blind.

**To avoid push/pull/merge conflicts:**
- Everyone stays inside their own folder — this alone prevents almost all
  conflicts, since git only flags conflicts on lines/files two people both
  touched.
- Nobody commits directly to `main` except the integrator, and only at the
  checkpoints above.
- Before each checkpoint, everyone should `git push` their own branch first
  so the integrator is merging the latest version, not stale local commits.
- After each checkpoint, everyone should `git pull origin main` into their
  own branch (`git checkout <name> && git merge main`) so their branch stays
  aware of what actually landed, rather than working forever against
  outdated stubs.

## 12. 5-Day Plan

| Day | Goal | Key work |
|---|---|---|
| 1 | Voice loop | Mic -> LiveKit -> STT -> Agent -> Rime -> Audio; basic task object; contracts frozen |
| 2 | Interruption MVP | Interruption detection, stop speech, invalidate task, create new task, answer updated request |
| 3 | Correctness | Tool delay, task fencing, stale-result rejection, state timeline, change-my-mind |
| 4 | Evidence + UI | Dashboard, stress-test lab, evaluation runner, RIME_EVIDENCE.md complete, multilingual only if stable (not in current scope) |
| 5 | Freeze | Integration, bug fixes, exact Rime configuration, tests, documentation, demo, final repo check — no major new features |

## 13. Definition of Done

- [ ] Voice input works
- [ ] STT works
- [ ] Analytics tools work
- [ ] Agent works
- [ ] Rime speaks normal responses
- [ ] User can interrupt speech (Scenario A)
- [ ] Old audio stops
- [ ] Old task invalidated
- [ ] New task created and becomes active
- [ ] Tool results are fenced with task_id + fence_token
- [ ] Stale results rejected (Scenario B)
- [ ] Stale results never spoken
- [ ] Tool-in-progress interruption works
- [ ] Change-my-mind (revise request mid-flight) works
- [ ] Timeline UI works
- [ ] Reliability dashboard works
- [ ] Stress tests (S01-S08 subset covering A and B) work and are recorded
- [ ] RIME_EVIDENCE.md complete with real evidence
- [ ] Rime configuration documented exactly (model/voice/language/endpoint/format/transport)
- [ ] Secrets protected (never committed, never in demo recording)
- [ ] Limitations documented honestly
- [ ] Demo recorded (4-5 min)
- [ ] README complete and accurate against actual shipped code

## 14. Demo Script (4-5 minutes)

| Time | Content |
|---|---|
| 0:00-0:30 | User + problem + why voice matters |
| 0:30-1:15 | Normal voice analytics (happy path) |
| 1:15-2:00 | Scenario A: interrupt while Rime is speaking |
| 2:00-2:45 | Scenario B: interrupt during a delayed tool call |
| 2:45-3:30 | Timeline + stale-result evidence walkthrough |
| 3:30-4:15 | Dashboard + live stress test |
| 4:15-4:45 | Rime configuration + architecture + conclusion |

## 15. What Judges Score (for calibration only — do not chase this instead of correctness)

Problem/necessity of voice 25% · Hard voice engineering 25% · Evidence/
reproducibility 20% · Rime integration/voice experience 20% · Demo clarity
10%. Confirmed against the official PS PDF.

## 16. Eligibility — never do these

- Ship code with no verifiable Rime integration.
- Use Rime only for a welcome message, confirmation, or incidental speech —
  every substantive answer must be spoken by Rime.
- Submit static screens, a concept deck, or a scripted mock with no working
  product path.
- Omit the demo.
- Expose a live credential anywhere (code, docs, screenshots, recordings).
- Ship a model/voice/language combination that fails the event's preflight
  check without correcting it before the deadline.

## 17. Rules For AI Coding Agents (binding on every agent, every session)

- Follow the Boot Sequence (Section 0) at the start of every session, no
  exceptions.
- Never edit `MASTER_README.md` or `CONTRACTS.md`. Flag needed changes
  instead.
- Never edit or create files outside your assigned directory (Section 9).
- Never invent a different architecture than Section 6 / `CONTRACTS.md`.
- Only the Task Manager (vedantkhar's module) writes task `status`. No other
  module may do so.
- Every async result must carry `task_id` + `fence_token` and pass the
  fencing check before it can update state or be spoken.
- Never assume tool cancellation succeeded — always fence the result
  regardless of cancellation outcome.
- Never let an obsolete/cancelled/failed task produce speech.
- Never fabricate a metric, a test result, or example numbers.
- Never fake or skip a test to make it pass.
- Never claim a capability (e.g. multilingual support) that has not been
  verified with a real run.
- Log every completed, verified step to `PROGRESS.md` immediately, and
  update `RIME_EVIDENCE.md` the moment real evidence exists — never batch
  this for later.
- If a shortcut conflicts with the interruption/fencing correctness rule
  (Section 2), stop and prioritize correctness over the shortcut or feature.
