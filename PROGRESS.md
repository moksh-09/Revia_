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
[2026-09-06 17:21] [moksh] [Step 1 — Sales dataset] DONE — python3 backend/tools/dataset.py; observed Records: 600 and first record with date=2026-01-01, region=North, product=Laptop
[2026-09-06 17:21] [moksh] [Step 2 — Deterministic analytics] DONE — verified total_sales through ToolClient; observed result=105693000
[2026-09-06 17:21] [moksh] [Step 3 — Tool client] DONE — verified 3-second artificial delay (Elapsed: 3.01 seconds) and unknown-tool error handling
```
