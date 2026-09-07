# REVIA — PROGRESS.md

**Append-only.** Never edit or delete another person's line. Never rewrite
history — if something needs correcting, add a new line noting the
correction; don't alter the old one.

A step counts as done only when it has real evidence behind it (a test that
passed, a command that was run, an observed output) — not because an agent
says it's finished. See `MASTER_README.md` Section 0, step 3 and Section 8.

## Format

```
[YYYY-MM-DD HH:MM] [name] [Section/Step ref] DONE — <evidence: test name, command, or observed output>
[YYYY-MM-DD HH:MM] [name] [Section/Step ref] BLOCKED — <what's blocking, and what stub/fallback is used instead>
```

Use your real name exactly as it appears in `MASTER_README.md` Section 10:
`vedantk`, `vedantkhar`, `moksh`, or `shlok`.

## How another person picks up work after someone else finishes a step

1. Read this file top to bottom (or from your last visit) to see what's
   actually done, with evidence, versus still pending.
2. Cross-check any "DONE" line against `CONTRACTS.md` — the interface it
   implements should still match. If it doesn't, that's a BLOCKED-worthy
   flag to raise, not something to quietly patch around.
3. If your dependency shows DONE with evidence: pull that branch, swap your
   stub for the real module, re-test your own step, then log your result
   here.
4. If your dependency is not yet DONE: keep building against the stub in
   `CONTRACTS.md` Section 5. Do not wait idle.
5. Tell your coding agent to append its own line here the moment a step is
   verified — this is what makes the next person's step 1 possible without
   them having to ask anyone directly.

## Log

```
[2026-09-09 10:00] [All] [Day 0] DONE — CONTRACTS.md drafted and agreed by all 4 in sync call
[2026-09-06 18:27] [shlok] [Orchestration Step 1] DONE — stub_voice_client.py, stub_task_client.py, stub_tool_client.py, agent_brain.py built and smoke-tested. python -m backend.orchestration.agent_brain: EXIT 0, Groq tool-call correct (get_total_sales selected, spoken answer drafted), both stub tests PASS. Model: openai/gpt-oss-20b on Groq. [STUB TEST -- not real evidence for RIME_EVIDENCE.md]
[2026-09-06 18:38] [shlok] [Evaluation Step 2] DONE — backend/evaluation/scenarios.py: Scenario A PASS (8/8 checks, 2 N/A), Scenario B PASS (8/8 checks, 2 N/A). python -m backend.evaluation.scenarios: EXIT 0. ScenA: speech.stopped=interrupted at 1011ms, T1->OBSOLETE, T2 answered. ScenB: fence_token mismatch detected at t=5.80s (interrupt at 2.01s), stale result rejected, never spoken. [STUB TEST -- not real evidence for RIME_EVIDENCE.md]
[2026-09-06 18:43] [shlok] [Evaluation Step 3] DONE — backend/evaluation/metrics.py: all 4 metrics computed from real timestamps. ScenA: interruptions=1, stale_rate=0.0%, ttfa=2105ms, recovery=2179ms. ScenB: interruptions=1, stale_rate=100.0%, ttfa=6046ms, recovery=9840ms. Both assertion sets PASS. EXIT 0. [STUB TEST -- not real evidence for RIME_EVIDENCE.md]
[2026-09-06 18:46] [shlok] [Evaluation Step 4] DONE — backend/evaluation/evidence_generator.py: PASS/FAIL checklist printed in RIME_EVIDENCE.md Section 4 format. ScenA [PASS] 8/8, ScenB [PASS] 8/8. python -m backend.evaluation.evidence_generator: EXIT 0. [STUB TEST -- not real evidence for RIME_EVIDENCE.md]

[2026-09-06 17:56] [vedantk] [Step 1 — Deepgram STT] DONE — lk agent console backend\voice_io\agent.py; real microphone speech produced TRANSCRIPT lines
[2026-09-06 18:03] [vedantk] [Step 2 — Stub Task Manager] DONE — lk agent console backend\voice_io\agent.py; each transcript produced a unique task_id with status=ACTIVE
[2026-09-06 18:23] [vedantk] [Step 3 — Rime TTS integration] DONE — py backend\rime\tts_rime.py; RIME VERIFIED: coda/lyra, PCM 16000 Hz, 23 frames, 48800 bytes
[2026-09-06 18:36] [vedantk] [Step 4 — Rime LiveKit playback] DONE — lk agent console backend\voice_io\agent.py; RIME PLAYBACK FINISHED observed and Rime acknowledgement heard
[2026-09-06 18:46] [vedantk] [Step 5 — Interrupt playback] DONE — lk agent console backend\voice_io\agent.py; interrupt event emitted and RIME PLAYBACK STOPPED with reason=interrupted
[2026-09-06 19:02] [vedantk] [Step 6 — Speech lifecycle events] DONE — lk agent console backend\voice_io\agent.py; speech.started/speech.stopped emitted with task_id, speech_id, stopped_reason, and ms_spoken
[2026-09-06 18:57] [vedantk] [Endpointing tuning] DONE — lk agent console backend\voice_io\agent.py; flowing request committed as one task with no late-transcript warning
[2026-09-06 17:21] [moksh] [Step 1 — Sales dataset] DONE — python3 backend/tools/dataset.py; observed Records: 600 and first record with date=2026-01-01, region=North, product=Laptop
[2026-09-06 17:21] [moksh] [Step 2 — Deterministic analytics] DONE — verified total_sales through ToolClient; observed result=105693000
[2026-09-06 17:21] [moksh] [Step 3 — Tool client] DONE — verified 3-second artificial delay (Elapsed: 3.01 seconds) and unknown-tool error handling
[2026-09-07 13:05] [shlok] [Code quality Fix 1 — off_event()] DONE — added public off_event() to StubTaskClient and StubVoiceClient; agent_brain.py now uses off_event() instead of direct _listeners access. python -m backend.orchestration.agent_brain: all smoke tests PASS. [STUB TEST -- not real evidence for RIME_EVIDENCE.md]
[2026-09-07 13:05] [shlok] [Code quality Fix 2 — Task.status enum] DONE — confirmed TaskStatus(str, Enum) makes OBSOLETE == "OBSOLETE" True; no string comparisons changed. python -m backend.evaluation.scenarios: OVERALL PASS. [STUB TEST]
[2026-09-07 13:05] [shlok] [Code quality Fix 3 — metrics rate assertion] DONE — replaced fragile == 0.0 with is None or 0.0 <= rate <= 1.0 range check in metrics.py. python -m backend.evaluation.scenarios: OVERALL PASS. [STUB TEST]
[2026-09-07 13:05] [shlok] [Code quality Fix 4 — asyncio.get_running_loop()] DONE — replaced deprecated get_event_loop().time() with get_running_loop().time() in stub_voice_client.py. python -m backend.evaluation.scenarios: OVERALL PASS. [STUB TEST]
[2026-09-07 13:05] [shlok] [Code quality Fix 5 — requirements.txt pinning] DONE — pinned groq==1.7.0 and python-dotenv==1.2.3 (the two packages installed in this env); added NOTE comments for packages belonging to other owners. [STUB TEST]
[2026-09-07 13:05] [shlok] [Code quality Fix 6 — inline imports] DONE — moved TaskEvent/SpeechEvent imports from inside _render_scenario_block() to top of evidence_generator.py. python -m backend.evaluation.evidence_generator: OVERALL PASS. [STUB TEST]
[2026-09-07 13:05] [shlok] [Code quality Fix 7 — GROQ_MODEL env var] DONE — hardcoded "openai/gpt-oss-20b" removed from agent_brain.py; now reads os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"); GROQ_MODEL added to .env and .env.example. python -m backend.orchestration.agent_brain: PASS, model=openai/gpt-oss-20b. [STUB TEST]
```
