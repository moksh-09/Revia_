"""LiveKit + Rime voice client adapter for AgentBrain integration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

RIME_DIRECTORY = Path(__file__).resolve().parents[1] / "rime"
if str(RIME_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(RIME_DIRECTORY))

from events import RimePlaybackController
from tts_rime import queue_rime_speech


EventListener = Callable[[Any], None]


class LiveKitRimeVoiceClient:
    """
    Real voice output client used by AgentBrain inside the LiveKit agent.

    Implements the same speak/on_event/off_event surface as StubVoiceClient.
    """

    def __init__(
        self,
        session: Any,
        playback_controller: RimePlaybackController,
    ) -> None:
        self._session = session
        self._playback = playback_controller
        self._listeners: list[EventListener] = []

    def on_event(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    def off_event(self, listener: EventListener) -> None:
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def _emit(self, event: dict[str, Any]) -> None:
        for listener in self._listeners:
            listener(event)

    async def speak(self, text: str, task_id: str) -> str:
        """Queue Rime speech, await playback, and emit speech lifecycle events."""
        handle = queue_rime_speech(self._session, text)
        speech_id = getattr(handle, "id", None) or f"speech_{uuid4().hex}"

        started = self._playback.start_playback(task_id, handle)
        self._emit(started)

        await handle

        stopped_reason = "interrupted" if handle.interrupted else "completed"
        stopped = self._playback.finish_playback(task_id, handle, stopped_reason)
        if stopped is not None:
            self._emit(stopped)

        return speech_id

    def interrupt(self) -> None:
        """Stop any in-progress Rime playback immediately."""
        self._playback.interrupt_on_new_user_speech()
