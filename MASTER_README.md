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
| Browser Microphone | Captures raw user audio | Person 1 |
| LiveKit Realtime Transport | Media session, turn signaling, low-level VAD | Person 1 |
| STT | Converts user audio to text | Person 1 |
| Voice Agent | Orchestrates the turn end-to-end | Person 1 / Person 2 boundary |
| Task / State Manager | Issues `task_id`s, owns the single source of truth for the active task | Person 2 |
| Interruption Manager | Detects interruption, triggers audio stop, signals task invalidation | Person 2 |
| LLM + Analytics Tools | Chooses and calls deterministic analytics functions, drafts the answer | Person 3 |
| Response Validation | Confirms a result belongs to the still-active task/fence before it can proceed | Person 2 |
| Rime TTS | Synthesizes the primary spoken output | Person 1 |
| Evaluation Engine / Metrics Store / Dashboard | Parallel path — reads the same event stream, never sits in the critical path of the answer | Person 3 / Person 4 |
| Voice UI / Timeline / Dashboard UI | User-facing surfaces | Person 4 |

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
[YYYY-MM-DD HH:MM] [Person N] [Section/Step ref] DONE — <one-line evidence: test name, command run, or output observed>
```

Example:

```
[2026-09-10 14:20] [Person 2] [State machine transitions] DONE — pytest backend/state/test_transitions.py, 14/14 passed
[2026-09-10 16:05] [Person 1] [Rime config locked] DONE — model=..., voice=..., endpoint=..., see .env.example
```

If a step is blocked, log that too, so others know not to depend on it yet:

```
[2026-09-10 17:00] [Person 3] [Tool cancellation] BLOCKED — cancellation not supported by pandas query in progress; fencing implemented as fallback per CONTRACTS.md Section 4
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
│   ├── rime/             <- Person 1 only. Rime TTS integration, audio streaming out.
│   ├── voice_io/         <- Person 1 only. Mic capture, LiveKit transport, STT wiring.
│   ├── state/            <- Person 2 only. Task Manager, state machine, fencing, interruption manager.
│   ├── tools/             <- Person 3 only. Analytics functions, sales dataset access.
│   └── evaluation/       <- Person 3 only. Stress-test scenarios (S01-S08), metrics, evidence generation scripts.
└── frontend/             <- Person 4 only. Voice UI, conversation UI, timeline, reliability dashboard.
```

**Ownership rule:** a person only ever creates, edits, or deletes files inside
their own directory. Any change to a root-level file (`MASTER_README.md`,
`CONTRACTS.md`) requires the whole team's agreement — no exceptions, no "just
a quick fix."

## 10. Per-Person Instructions

Each subsection below is what that person (and their coding agent) works
from. Read only your own subsection closely.

### Person 1 — Realtime Voice + Rime
**Owns:** `backend/rime/`, `backend/voice_io/`
**Depends on:** the `Task`/event schema in `CONTRACTS.md` Section 2 (from
Person 2). If not yet built, code against the stub in `CONTRACTS.md`
Section 5.
**Build, in order:**
1. Mic capture -> LiveKit transport -> STT -> plain text output (no Rime yet). Log to `PROGRESS.md` when a spoken sentence reliably becomes text.
2. Wire STT output into the stubbed Task Manager interface from `CONTRACTS.md`. Log when a `task_id` is correctly requested for each utterance.
3. Rime TTS integration: pick and lock the exact model/voice/language/endpoint/audio format/transport from Rime's live catalog. Write this into `.env.example` and `RIME_EVIDENCE.md` Section 3 immediately.
4. Playback of Rime's streamed audio to the browser.
5. Interruption detection: on new user speech while Rime is speaking, emit the `interrupt` event exactly as defined in `CONTRACTS.md` Section 3, and stop local playback immediately.
6. Emit `speech.started` / `speech.stopped` events with `task_id` + `speech_id` per `CONTRACTS.md` Section 3, so the state manager and timeline know exactly what the user actually heard.
**Never:** invent a different event schema; commit any Rime credential anywhere (code, docs, screenshots, recordings).

### Person 2 — Agent + State + Task (build/freeze this interface first)
**Owns:** `backend/state/`
**Depends on:** nothing upstream for the interface itself — this module's
contract is what the other three build against. Prioritize finalizing the
schema in `CONTRACTS.md` (as a team) before deep implementation.
**Build, in order:**
1. Task object + state machine (`CREATED -> ACTIVE -> TOOL_RUNNING -> GENERATING -> SPEAKING -> COMPLETED`, plus `CANCELLED`/`OBSOLETE`/`FAILED` as terminal states). Log when all transitions have passing tests.
2. Interruption handling: on receiving an `interrupt` event (from Person 1) at any non-terminal state, move the current task to `CANCELLED`/`OBSOLETE`, create a new task, mark it `ACTIVE`.
3. Fencing: every async result (from Person 3's tools or the LLM) carries a `task_id` + `fence_token`. Implement the check that rejects any result whose task is not the currently active one — regardless of whether tool cancellation succeeded.
4. Response validation gate: a generated response may only proceed to Rime if its task is still active at the moment of the check.
5. Emit the full event timeline (task created/active/obsolete/cancelled/completed, with timestamps) for Person 4's dashboard and Person 3's evidence generation.
**Never:** let any component other than the Task Manager write `status`; assume tool cancellation succeeded — always fence regardless.

### Person 3 — Data + Evaluation
**Owns:** `backend/tools/`, `backend/evaluation/`
**Depends on:** the tool-call and fencing contract in `CONTRACTS.md`
Section 4 (from Person 2). If not yet built, code against the stub in
`CONTRACTS.md` Section 5.
**Build, in order:**
1. Sales dataset + deterministic analytics functions (the actual queries REVIA can answer).
2. Wire each analytics call to carry the `task_id`/`fence_token` per `CONTRACTS.md` Section 4 so Person 2's fencing can reject stale results.
3. Stress-test scenarios: Scenario A (interrupt while speaking) and Scenario B (interrupt during tool execution), each with a fixed delay injected into a tool call to make the race reproducible on demand.
4. Metrics: interruption count, stale-result count, stale-result rejection rate, response latency, time-to-first-audio, recovery time, task success rate — every value a real measurement, never invented.
5. Evidence generation script that produces the acceptance-test PASS checklist output for `RIME_EVIDENCE.md`.
**Never:** fabricate or estimate a metric; mark a scenario as passing without a captured run.

### Person 4 — Frontend + Integration
**Owns:** `frontend/`
**Depends on:** Person 1's speech events, Person 2's task timeline, Person
3's metrics — all per `CONTRACTS.md`. Build against stubs for whichever
isn't ready yet.
**Build, in order:**
1. Voice UI: mic control, conversation transcript, active-speaker/task indicator.
2. Timeline view: renders the task-state event stream from Person 2 (created/active/obsolete/cancelled/completed) so a judge can see exactly what happened during a stress test.
3. Reliability dashboard: renders Person 3's live metrics.
4. Stress-test UI: a control to trigger Scenario A / Scenario B on demand for the live demo.
5. Own final integration: at each checkpoint (Section 11), pull all four branches, wire real modules in place of stubs, and confirm the end-to-end flow matches `CONTRACTS.md` exactly.
6. Deployment and demo recording support.
**Never:** paper over an integration mismatch by changing your own contract expectations silently — flag it to the team instead.

## 11. Integration Checkpoints (not just Day 5)

- **End of Day 2:** all four branches pulled together. Confirm: mic-to-Rime loop works end to end, and a basic interrupt stops speech (Scenario A only, rough).
- **End of Day 3:** re-integrate. Confirm: fencing correctly rejects a stale tool result (Scenario B), full state timeline recorded.
- **Day 4:** evidence + dashboard + stress-test UI wired to the real (not stubbed) pipeline.
- **Day 5:** freeze. No new features. Final integration check, README/evidence completeness pass, demo recording, credential/secret check.

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
- Only the Task Manager (Person 2's module) writes task `status`. No other
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
