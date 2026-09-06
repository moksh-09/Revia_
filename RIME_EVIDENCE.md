# RIME_EVIDENCE.md

Updated incrementally as each piece becomes true and provable — see
`MASTER_README.md` Section 7. No fabricated or estimated results.

## 1. Hard Voice Claim

REVIA remains conversationally correct — never speaking or acting on a stale
or wrong result — when the user interrupts it while it is speaking
(Scenario A) or while a background tool/data operation is still running
(Scenario B). Both are solved by one mechanism: task IDs + fencing +
stale-result rejection.

## 2. Why Voice Is Necessary

The failure mode under test — interruption, mid-sentence correction, changing
your mind mid-request — only exists in a live, spoken, interruptible
conversation. A typed message is already final the instant it is sent, so
there is nothing mid-flight to interrupt and no stale result to reject.
Removing voice removes the problem this project exists to solve, not just
the interface it's delivered through.

## 3. Rime Configuration

```
MODEL:        coda        (Rime's current flagship model; Arcana sunset 2026-08-15)
VOICE:        lyra
LANGUAGE:     eng
ENDPOINT:     wss://users-ws.rime.ai/ws3
AUDIO_FORMAT: pcm, sample_rate=16000
TRANSPORT:    LiveKit Agents, `livekit.plugins.rime.TTS(model="coda", speaker="lyra", use_websocket=True)`
```

These six values must always match `CONTRACTS.md` Section 7 and
`.env.example` exactly — update all three together, never one at a time.

## 4. Acceptance Test

**Scenario A — Interrupt while speaking**
<TODO: fill after Scenario A is built and run — exact steps, e.g. T001
created, Rime begins speaking, user interrupts at Xs, verify old speech
stops, T001 -> OBSOLETE, T002 created and active, T002 answer spoken.>

**Scenario B — Interrupt during tool execution**
<TODO: fill after Scenario B is built and run — T001 created, tool call
delayed N seconds, user interrupts mid-delay, T001 -> OBSOLETE, T002 active,
T001's late tool result rejected via fence_token mismatch and never spoken,
T002's answer generated and spoken.>

## 5. Test Setup

<TODO: environment, fixed delay values used, how reproducibility is ensured.>

## 6. Procedure

<TODO: exact reproducible steps or script/command to run each scenario.>

## 7. Results

<TODO: real observed output only — timestamps, event timeline excerpts,
PASS/FAIL per checklist item below. Never estimate.>

**PASS checklist (per scenario):**
- [ ] old task invalidated
- [ ] old speech stopped if speaking
- [ ] new task created
- [ ] new task becomes active
- [ ] stale result rejected
- [ ] stale result not spoken
- [ ] active state not overwritten
- [ ] final answer matches latest request
- [ ] events recorded in timeline
- [ ] measurable evidence captured (logs/metrics attached)

## 8. Stress Case

<TODO: describe the deliberate failure case demonstrated in the recorded demo.>

## 9. Evidence / Artifacts

<TODO: links or paths to logs, timeline exports, recorded clips, metrics
snapshots — committed to the repo, not just described.>

## 10. Limitations

<TODO: log honestly and immediately as discovered — e.g. specific tool types
where cancellation isn't supported (fencing still applies as the safety net),
any input types not yet handled, any fallback TTS path and when it triggers.>

## 11. Reproduction Command / Script

```
<TODO: exact command, e.g. `python evaluation/run_scenario.py --scenario A`>
```
