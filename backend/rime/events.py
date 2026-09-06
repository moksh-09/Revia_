"""Rime speech lifecycle and interruption events for REVIA."""

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_timestamp() -> str:
    """Return an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RimePlaybackController:
    """Tracks active Rime speech and emits contract-compliant events."""

    def __init__(self) -> None:
        self.active_task_id: str | None = None
        self.active_speech_handle: Any | None = None
        self.active_speech_id: str | None = None
        self.active_started_at: float | None = None
        self.emitted_events: list[dict[str, Any]] = []

    def start_playback(
        self,
        task_id: str,
        speech_handle: Any,
    ) -> dict[str, Any]:
        """Emit speech.started and register active playback."""
        speech_id = getattr(speech_handle, "id", None) or f"speech_{uuid4().hex}"
        self.active_task_id = task_id
        self.active_speech_handle = speech_handle
        self.active_speech_id = speech_id
        self.active_started_at = time.monotonic()

        event = {
            "event": "speech.started",
            "task_id": task_id,
            "speech_id": speech_id,
        }
        self.emitted_events.append(event)
        return event

    def finish_playback(
        self,
        task_id: str,
        speech_handle: Any,
        stopped_reason: str,
    ) -> dict[str, Any] | None:
        """Emit speech.stopped for the active speech."""
        if (
            self.active_task_id != task_id
            or self.active_speech_handle is not speech_handle
            or self.active_speech_id is None
            or self.active_started_at is None
        ):
            return None

        event = {
            "event": "speech.stopped",
            "task_id": task_id,
            "speech_id": self.active_speech_id,
            "stopped_reason": stopped_reason,
            "ms_spoken": max(
                0,
                int((time.monotonic() - self.active_started_at) * 1000),
            ),
        }
        self.emitted_events.append(event)

        self.active_task_id = None
        self.active_speech_handle = None
        self.active_speech_id = None
        self.active_started_at = None
        return event

    def interrupt_on_new_user_speech(self) -> list[dict[str, Any]]:
        """Emit interrupt, stop audio, and emit speech.stopped."""
        task_id = self.active_task_id
        handle = self.active_speech_handle
        speech_id = self.active_speech_id
        started_at = self.active_started_at

        if (
            task_id is None
            or handle is None
            or speech_id is None
            or started_at is None
            or handle.done()
        ):
            return []

        interrupt_event = {
            "event": "interrupt",
            "task_id": task_id,
            "detected_at": utc_timestamp(),
        }

        handle.interrupt(force=True)

        stopped_event = {
            "event": "speech.stopped",
            "task_id": task_id,
            "speech_id": speech_id,
            "stopped_reason": "interrupted",
            "ms_spoken": max(
                0,
                int((time.monotonic() - started_at) * 1000),
            ),
        }

        self.emitted_events.extend((interrupt_event, stopped_event))

        self.active_task_id = None
        self.active_speech_handle = None
        self.active_speech_id = None
        self.active_started_at = None

        return [interrupt_event, stopped_event]