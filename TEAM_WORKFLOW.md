# REVIA — TEAM_WORKFLOW.md

One page, start to finish. This file doesn't repeat content that already
lives elsewhere — it tells you the *order* to use `MASTER_README.md`,
`CONTRACTS.md`, `PROGRESS.md`, and your own person-file
(`VEDANTK.md`/`VEDANTKHAR.md`/`MOKSH.md`/`SHLOK.md`). Read this once, then
follow it.

---

## Phase 0 — One-time repo setup (already done by vedantk)

Repo created, `main` branch pushed with all root docs, 4 person branches
(`vedantk`, `vedantkhar`, `moksh`, `shlok`) created off `main`. Nobody else
needs to do this — it's done. Skip to Phase 1.

---

## Phase 1 — Every person's first-time setup (do this once)

Run these in order, exactly as written, from a terminal:

```
git clone https://github.com/vedantk-086/revia
cd revia
git checkout <your-name>
```
(`<your-name>` = `vedantkhar`, `moksh`, or `shlok` — vedantk is already on
his branch)

```
copy .env.example .env
```
(Mac/Linux: `cp .env.example .env` instead)

Open `.env` in your editor. Open `CONTRACTS.md`, find **Section 8 —
Credentials, who needs what**, find your row, and fill in only those keys.
Most of you need zero or one key — don't create accounts you don't need.

Install your own dependencies (already listed under your name in
`requirements.txt` at the repo root):
```
pip install -r requirements.txt
```

**Do not proceed to Phase 2 until this is done.**

---

## Phase 2 — Read your instructions (5 minutes, every session)

1. Open `MASTER_README.md` Section 0 (Boot Sequence) — read it once fully,
   now, so you understand the rules everyone follows.
2. Open `CONTRACTS.md` fully — this is the frozen shape of data that
   connects everyone's work. You don't need to memorize it, but read it
   once before writing code so nothing surprises you later.
3. Open **your own file** — `VEDANTK.md`, `VEDANTKHAR.md`, `MOKSH.md`, or
   `SHLOK.md`. This has everything specific to you: your build order, your
   credentials, and your exact starter prompt.
4. Open `PROGRESS.md` — see what, if anything, the others have already
   verified done. (On Day 1, this will be mostly empty — that's expected.)

---

## Phase 3 — Who works in parallel, who's sequential

```
DAY 1                    DAY 2                    DAY 3              DAY 4          DAY 5
─────────────────────────────────────────────────────────────────────────────────────────
vedantk     |=== build against stubs ===|===========|                |
vedantkhar  |=== build (no dependency) =|===========|                |  (polish,
moksh       |=== build against stubs ===|===========|                |   evidence,
shlok       |== orchestration skeleton =|= real eval starts here ====|   demo)
                                          ^                    ^        ^
                                    integration           integration  shlok
                                    checkpoint 1          checkpoint 2 starts
                                    (vedantk merges)      (vedantk     frontend
                                                           merges)     (Phase 2)
```

**vedantk, vedantkhar, moksh: fully parallel, starting right now.** None of
you wait for each other — you each build against the stub interfaces in
`CONTRACTS.md` Section 5 until the real modules exist.

**shlok: mostly parallel, partially sequential.** You can start your
orchestration skeleton and evaluation scripts against stubs immediately —
but *meaningful, real* stress-test evidence needs real modules to test
against, so your genuinely useful evaluation work naturally picks up after
Day 2's integration checkpoint. Don't sit idle before then — build the
skeleton now.

**Nobody starts frontend before Day 4.** This is the one hard sequencing
rule in this whole project. See Phase 6.

---

## Phase 4 — Give your coding agent its instructions

Open your own file, copy the block under **"Starter prompt"**, paste it
directly into Cursor / Antigravity / Codex / whichever agent you're using.
Nothing else needs to be typed — the prompt already tells your agent to
read `MASTER_README.md`, `CONTRACTS.md`, and `PROGRESS.md` itself before
starting.

---

## Phase 5 — The build loop (repeat this for every step in your file)

This is the same loop for all 4 people, every single step:

1. **Let the agent build one step** (your file lists them in order — the
   agent stops after each one for your review, per the prompt).
2. **Actually run it.** Don't trust "this should work" — run the code,
   speak into the mic, run the test, whatever proves that step.
3. **If it works:** append one line to `PROGRESS.md` in the format shown in
   that file, using your real name.
   **If it's blocked:** log a `BLOCKED` line instead, explaining what's
   missing and what stub/fallback you're using meanwhile.
4. **Commit and push, inside your own folder only:**
   ```
   git add backend/<your-folder(s)>
   git commit -m "Step N: <what was built>"
   git push
   ```
5. **Tell your agent to continue to the next step.** Repeat from 1.

This loop is what prevents conflicts: you only ever touch your own folder,
you only ever push to your own branch, and `PROGRESS.md` is append-only so
two people writing to it at slightly different times never collide (git
merges append-only file changes cleanly almost every time).

---

## Phase 6 — Integration checkpoints (vedantk does this part)

At the end of Day 2 and Day 3, **vedantk** (the integrator) runs:
```
git checkout main
git pull
git merge vedantkhar
git merge moksh
git merge vedantk
```
Tests that the merged result actually runs, pushes `main`. Before merging
anyone's branch, vedantk checks `PROGRESS.md` for that person's `DONE`
lines with real evidence — an unverified claim gets tested first, not
merged blind.

**After each checkpoint, everyone else pulls the update into their own
branch** so they're not building against outdated stubs forever:
```
git checkout <your-name>
git merge main
git push
```

**Day 4:** once vedantk confirms `main` has a real, working, merged
backend, he tells shlok directly. Only then does shlok open the **Phase 2**
section of `SHLOK.md`, pull `main`, and start frontend work — against the
real backend, not stubs.

**Day 5:** vedantk merges `shlok`'s finished frontend branch into `main`.
Freeze. No new features. Final check against `MASTER_README.md` Section 13
(Definition of Done), record the demo, done.

---

## Phase 7 — What never causes a conflict, if everyone follows this

- Everyone stays inside their own folder (`backend/voice_io/`+`backend/rime/`
  for vedantk, `backend/state/` for vedantkhar, `backend/tools/` for moksh,
  `backend/orchestration/`+`backend/evaluation/` then `frontend/` for shlok).
- Nobody edits `MASTER_README.md` or `CONTRACTS.md` without the whole team
  agreeing first.
- Nobody commits to `main` except vedantk, and only at the two checkpoints.
- `PROGRESS.md` is append-only — add a line, never edit someone else's.
- `requirements.txt` is append-only, sectioned by name — add under your own
  heading only.

If you ever see a merge conflict despite following this, it means someone
touched a file outside their own folder — stop and figure out who, rather
than force-resolving it blind.
