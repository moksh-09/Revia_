# REVIA — Rime / Hard-Voice Evidence

This document distinguishes implementation and deterministic evidence from
actual LiveKit runtime evidence. Tests and source inspection are not treated as
live proof.

## Hard voice claim

REVIA reliably switches conversational task authority during full-duplex voice
interaction: interruptions stop obsolete speech, obsolete model/tool work
cannot re-enter the active conversational state, and the updated request
becomes authoritative without losing valid session context.

The claim is one problem: Reliable Full-Duplex Task Switching, demonstrated
through interruption/recovery and conversation continuity during tool work.

## Acceptance test

The PS-style fixed-delay scenario is:

1. Start Task A from a real voice request.
2. Make Tool A enter a fixed delayed running state.
3. Interrupt or refine one part of the request while A is running or speaking.
4. Stop obsolete Rime speech promptly.
5. Make Task A obsolete.
6. Create Task B as the new authority.
7. Allow Tool A to finish late if necessary.
8. Reject the stale A result using both task ID and fence token.
9. Ensure A cannot generate, commit, or queue stale Rime speech.
10. Ensure Task B reaches Rime and reflects the updated request.

## Result and evidence level

The implementation and deterministic tests cover task/fence validation,
overlapping delayed work, stale-result rejection, context ordering, speech
authority, and session teardown protection.

Evidence classification:

- Task/fence and stale-result behavior: INTEGRATION TESTED.
- Delayed-tool overlap and task switching: INTEGRATION TESTED.
- Rime playback and interruption observations on the Windows runtime:
  LIVE TESTED.
- Complete single live trace proving A tool-running → refinement → A obsolete
  → B authoritative → late A rejection → no stale Rime speech → B spoken:
  NOT VERIFIED LIVE.

Deterministic tests must not be presented as live proof.

## Current Rime configuration

The exact configuration in backend/rime/tts_rime.py is:

    model:         coda
    speaker/voice: lyra
    language:      eng
    endpoint:      wss://users-ws.rime.ai/ws3
    audio format:  pcm
    sample rate:   16000 Hz
    transport:     LiveKit Agents AgentSession.say()
    websocket:     enabled

Rime is the primary spoken output. queue_rime_speech() calls
AgentSession.say() with interruptions enabled. New user speech interrupts the
active Rime playback through RimePlaybackController and emits speech lifecycle
events.

If the AgentSession is already closed or closes at the speech boundary, speech
is skipped. The known LiveKit lifecycle errors are contained narrowly; other
runtime errors propagate. This protects teardown but does not prove the full
live acceptance sequence.

## Reproducibility

From the project root, using the existing project environment:

    cd D:\revia
    python backend\voice_io\agent.py dev

Deterministic tests:

    python -m pytest backend\state -q
    python -m pytest backend\evaluation\test_backend_e2e.py -q

Required environment variable names are read from .env; credentials are not
included in source, client code, or this document.

## Limitations

- Context is same-session only; permanent and cross-session memory are not
  implemented.
- The delayed tool is neutral demonstration scaffolding, not a production
  data source.
- The complete delayed-tool full-duplex acceptance trace remains NOT VERIFIED
  LIVE and must not be claimed as proven without a preserved LiveKit event
  timeline and corresponding audible Task B result.
