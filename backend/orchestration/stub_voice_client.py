"""
backend/orchestration/stub_voice_client.py
==========================================
Stub Rime/voice output -- CONTRACTS.md Section 5.

Behaviour (spec-literal):
  - Accepts text + task_id.
  - Immediately emits speech.started.
  - After a configurable fake delay, emits speech.stopped with stopped_reason=completed.
  - Does NOT call Rime and does NOT capture real mic audio.
  - interrupt() stops the in-progress fake speech early, emitting
    speech.stopped with stopped_reason=interrupted.

Owner: shlok (backend/orchestration/).
Replace this file when vedantk's real backend/rime/ module is done and
logged in PROGRESS.md.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class SpeechEvent:
    """Payload shape matching CONTRACTS.md Section 2 speech.* events."""
    event: str          # "speech.started" | "speech.stopped"
    task_id: str
    speech_id: str
    stopped_reason: Optional[str] = None   # "completed" | "interrupted"
    ms_spoken: Optional[int] = None        # ms of fake audio played before stop


EventListener = Callable[[SpeechEvent], None]


class StubVoiceClient:
    """
    Stub voice/Rime output client.

    Usage::

        client = StubVoiceClient(speech_duration_s=4.0)
        client.on_event(my_listener)
        await client.speak("Hello world", task_id="t-001")

    Call interrupt() from another coroutine to simulate mid-speech interruption.
    """

    def __init__(self, speech_duration_s: float = 4.0) -> None:
        """
        Args:
            speech_duration_s: How many seconds the fake speech lasts before
                               auto-completing. Must be > 0.
        """
        if speech_duration_s <= 0:
            raise ValueError("speech_duration_s must be > 0")
        self._speech_duration_s = speech_duration_s
        self._listeners: list[EventListener] = []
        self._current_task_id: Optional[str] = None
        self._current_speech_id: Optional[str] = None
        self._interrupt_event: Optional[asyncio.Event] = None
        self._speak_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_event(self, listener: EventListener) -> None:
        """Register a listener that will be called for every speech event."""
        self._listeners.append(listener)

    def off_event(self, listener: EventListener) -> None:
        """Remove a previously registered event listener (no-op if not registered)."""
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    async def speak(self, text: str, task_id: str) -> str:
        """
        Simulate speaking *text* on behalf of *task_id*.

        Returns the speech_id once speech completes or is interrupted.
        Raises RuntimeError if another speak() is already in progress.
        """
        if self._speak_lock.locked():
            raise RuntimeError(
                "StubVoiceClient: speak() called while already speaking. "
                "Call interrupt() first."
            )

        async with self._speak_lock:
            speech_id = f"speech-{uuid.uuid4().hex[:8]}"
            self._current_task_id = task_id
            self._current_speech_id = speech_id
            self._interrupt_event = asyncio.Event()

            logger.info(
                "[StubVoice] speech.started  task_id=%s  speech_id=%s  text=%r",
                task_id, speech_id, text[:80],
            )
            self._emit(SpeechEvent(
                event="speech.started",
                task_id=task_id,
                speech_id=speech_id,
            ))

            start = asyncio.get_running_loop().time()
            interrupted = False

            try:
                # Wait for either the full duration or an interrupt signal.
                done, _ = await asyncio.wait(
                    [
                        asyncio.create_task(
                            asyncio.sleep(self._speech_duration_s),
                            name="speech-timer",
                        ),
                        asyncio.create_task(
                            self._interrupt_event.wait(),
                            name="interrupt-wait",
                        ),
                    ],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                interrupted = self._interrupt_event.is_set()
            finally:
                elapsed_ms = int((asyncio.get_running_loop().time() - start) * 1000)
                stopped_reason = "interrupted" if interrupted else "completed"

                logger.info(
                    "[StubVoice] speech.stopped  task_id=%s  speech_id=%s  "
                    "reason=%s  ms_spoken=%d",
                    task_id, speech_id, stopped_reason, elapsed_ms,
                )
                self._emit(SpeechEvent(
                    event="speech.stopped",
                    task_id=task_id,
                    speech_id=speech_id,
                    stopped_reason=stopped_reason,
                    ms_spoken=elapsed_ms,
                ))
                self._current_task_id = None
                self._current_speech_id = None
                self._interrupt_event = None

            return speech_id

    def interrupt(self) -> None:
        """
        Signal the currently in-progress speak() to stop immediately.

        Safe to call even when not speaking (no-op in that case).
        Per CONTRACTS.md Section 5: stops local playback immediately,
        regardless of whether a new task exists yet.
        """
        if self._interrupt_event is not None and not self._interrupt_event.is_set():
            logger.info(
                "[StubVoice] interrupt() called  current_task_id=%s",
                self._current_task_id,
            )
            self._interrupt_event.set()
        else:
            logger.debug("[StubVoice] interrupt() called but nothing is speaking.")

    @property
    def is_speaking(self) -> bool:
        return self._speak_lock.locked()

    @property
    def current_speech_id(self) -> Optional[str]:
        return self._current_speech_id

    @property
    def current_task_id(self) -> Optional[str]:
        return self._current_task_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, event: SpeechEvent) -> None:
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("[StubVoice] listener raised an exception")


# ---------------------------------------------------------------------------
# Quick smoke-test when run as __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async def _smoke_test() -> None:
        client = StubVoiceClient(speech_duration_s=3.0)

        events: list[SpeechEvent] = []
        client.on_event(events.append)

        print("\n=== Test 1: normal completion (3 s fake speech) ===")
        await client.speak("Hello, I am the stub voice.", task_id="t-001")
        assert len(events) == 2
        assert events[0].event == "speech.started"
        assert events[1].event == "speech.stopped"
        assert events[1].stopped_reason == "completed"
        print("PASS: completed naturally")

        events.clear()
        print("\n=== Test 2: interrupt after 1 s (3 s fake speech) ===")

        async def _interrupt_later() -> None:
            await asyncio.sleep(1.0)
            client.interrupt()

        await asyncio.gather(
            client.speak("This speech will be cut short.", task_id="t-002"),
            _interrupt_later(),
        )
        assert events[1].stopped_reason == "interrupted"
        assert events[1].ms_spoken < 2000   # stopped well before 3 s
        print(f"PASS: interrupted at ~{events[1].ms_spoken} ms")

    asyncio.run(_smoke_test())
